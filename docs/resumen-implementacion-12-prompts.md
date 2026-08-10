# Resumen de implementación: 12 prompts de la auditoría (P0-1 → P2-3)

> Documento para Claude: resumen ejecutivo de lo implementado en OpenCode, cómo
> se hizo, los errores que aparecieron en el camino y cómo se resolvieron.
>
> **Estado final: suite de tests completa VERDE — 264 passed, 0 failed, 0 errors**
> (`python -m pytest tests/`).

---

## 1. Resumen ejecutivo

Los 12 prompts de la auditoría BetMind AI se implementaron en orden
(P0-1 → P0-4, P1-1 → P1-5, P2-1 → P2-3). Cada prompt se trabajó por separado,
con tests nuevos por unidad. Durante la verificación final aparecieron **3
problemas preexistentes** (ninguno causado por los prompts) que se arreglaron
para dejar la suite 100% verde.

**Archivos nuevos (9):**
- `apps/api/engine/outcome_resolver.py` — resolución WON/LOST por mercado
- `apps/api/engine/ticket_builder.py` (modificado, no nuevo) — EV real del parlay
- `apps/api/jobs/evaluate_predictions.py` — job de evaluación post-partido
- `apps/api/jobs/report_prediction_accuracy.py` — reporte Brier/calibración
- `apps/api/models/prediction_outcome.py` — tabla prediction_outcomes
- `apps/api/migrations/021_add_opening_odds.sql` — línea de apertura
- `apps/api/migrations/022_create_prediction_outcomes.sql` — evaluación
- `tests/conftest.py` — fix global JSONB-en-sqlite
- 10 archivos de test nuevos

**Migraciones aplicadas a producción (Supabase, via MCP):**
- `021_add_opening_odds` (bookmaker_odds.opening_odds_value / _captured_at)
- `022_create_prediction_outcomes` (tabla prediction_outcomes con RLS)

**Pendiente:** los cambios están sin commitear en el working tree (se pidió
confirmación antes de commitear).

---

## 2. Detalle por prompt

### P0-1 — Idempotencia sobre EV (scripts/batch_predict.py)

**Problema:** `_has_narrative` salteaba un partido si existía CUALQUIER fila en
`predictions`, sin importar si tenía EV. Una predicción generada sin cuotas
quedaba persistida con todos los mercados en `verdict=INSUFFICIENT` y
`expected_value=null` PARA SIEMPRE.

**Solución:**
- Se separó en dos funciones:
  - `_has_valid_tactical_narrative` — la lógica previa de TacticalAnalysis
    (llm_model_used != "none" AND goals_narrative != None).
  - `_has_predictions_with_ev` — nueva: parsea `markets_json` y retorna True
    solo si AL MENOS un mercado tiene `expected_value` no nulo (maneja fila
    ausente, markets_json null, JSON inválido o no-lista).
- Loop principal: se saltea solo si `tactical_valid AND (has_ev OR sin cuotas)`.
  Si hay cuotas y la predicción quedó sin EV, SIEMPRE se recomputa la parte
  cuantitativa, pero con `include_tactical_analysis=False` si la narrativa
  táctica ya es válida (ahorra tokens LLM).
- Docstring de la Capa 4 actualizado (idempotencia sobre EV).

**Tests:** `tests/test_batch_predict.py` (3): sin EV + cuotas después → no se
saltea; con EV + narrativa → se saltea; markets_json null → no cuenta.

**Errores encontrados:** la tabla `matches` no compilaba en sqlite (JSONB de
postgres en `closing_odds`) — se resolvió creando solo las tablas necesarias
en el test; luego el fix global quedó en `conftest.py` (ver sección 4).

---

### P0-2 — Cron muerto (scripts/sync_today_matches.py + .github/workflows/daily_predictions.yml)

**Problema:** `from apps.api.services.scrapers.match_fixture_scraper import
MatchFixtureScraper` — archivo ELIMINADO del repo (commit d160ffc). El cron de
GitHub Actions moría con ImportError en el primer paso y `batch_predict` nunca
corría.

**Solución:**
- **Investigación:** `EspnSummaryScraper` (Plan B) solo expone
  `fetch_fixtures_for_date(slug, date) -> list[RawFixture]` por UNA liga, y
  `DeterministicLeagueScraperProvider` solo cubre ligas colombianas
  (SUPPORTED_LEAGUES = col.1/col.copa). Ninguno tiene
  `fetch_all_leagues_fixtures(days_ahead)` que es lo que el script necesita
  (dict league_key → list de dicts con home_team/away_team/external_id).
  El mapeo league_key→slug de ESPN vivía dentro del archivo eliminado.
- **Decisión (según el prompt):** NO se reimplementó. Import comentado con
  TODO explícito documentando la investigación. El script loguea un error
  claro y continúa usando solo el fallback API-Football (sección de marcadores
  que ya existía). El loop de ligas ESPN se omite con `break` y el sync de
  cuotas se omite con log (la cola de odds dependía de los fixtures ESPN).
- **Workflow:** paso "Sincronizar partidos en ventana móvil" con
  `id: sync-matches` + `continue-on-error: true`; nuevo paso final "Verificar
  sync de partidos" con `if: steps.sync-matches.outcome == 'failure'` y
  `exit 1` → el job corre batch_predict siempre, pero falla visiblemente al
  final si el sync se rompió (nunca más muere en silencio).

**Verificación:** `python -c "import ast; ast.parse(open('scripts/sync_today_matches.py').read())"` OK + import del módulo sin errores + YAML validado.

---

### P0-3 — Sync de cuotas acotado por liga (apps/api/services/odds_service.py)

**Problema:** `sync_odds_for_matches` llamaba `get_fixtures_by_date` SIN
`league` → traía TODOS los fixtures del mundo por fecha (miles) y hacía
fuzzy-match por nombre contra esa lista gigante: lento (8-15 min) y con riesgo
de colisión entre ligas (mismo par de nombres el mismo día → EV contaminado).

**Solución:**
- Agrupa por `(league_external_id, season)`; `season` = año del
  `match_date_str` (misma convención que `match.match_date.year` del resto
  del código).
- Una llamada `get_fixtures_by_date_range(league, season, date_from=min del
  grupo, date_to=max del grupo)` por grupo — una sola vez por liga.
- `_build_fixture_map` se construye POR LIGA (`league_fixture_maps[league_id]`)
  y el loop busca solo dentro del mapa de su liga: el fuzzy-match ya no cruza
  ligas.
- Fallback al comportamiento viejo (global por fecha) SOLO para partidos sin
  `league_external_id`, con `logger.warning`.
- Resto del flujo intacto: `_fetch_and_parse_odds`, `_parse_raw_odds_payload`,
  sleep de 6s, upsert.

**Tests:** `tests/test_odds_service.py` (5): mapa por liga, una llamada range
por liga, rango min-max con varias fechas, fallback global sin liga, y el caso
clave: mismo par de nombres en otra liga NO matchea.

**Verificado:** el único caller en producción es `sync_today_matches.py:329`,
cuyos dicts ya incluyen `league_external_id`.

---

### P0-4 — EV real del parlay (apps/api/engine/ticket_builder.py)

**Problema:** `calculate_average_ev` promediaba los EV individuales de las
patas — NO era el EV del boleto combinado. Para patas del mismo partido
(1X2_HOME + OVER_1_5) multiplicar como independientes ignora la correlación.

**Solución:**
- **`calculate_true_combined_probability(legs, match_score_matrices)`**:
  - Agrupa por match_id.
  - Patas del mismo partido derivables de la matriz de goles (1X2, OVER/UNDER,
    BTTS, DOUBLE, DNB — los mercados que market_calculator calcula con la
    matriz): recorre las celdas [i][j] y suma las que cumplen TODAS las
    condiciones a la vez (ej. 1X2_HOME + OVER_1_5 → celdas con `i>j Y i+j>1.5`).
  - El resto (córneres/tarjetas/remates y partidos distintos) se multiplica
    como independiente, con TODO explícito documentando la simplificación
    (no son completamente independientes en la realidad).
- **`build_ticket_for_mode`**: `real_ev = combined_prob * combined_odds - 1`,
  usado en `average_ev` (nombre CONSERVADO porque el frontend
  `apps/web/lib/api.ts` lo consume — el valor ahora es el correcto),
  `base_confidence` (con clamp inferior a 0 para EVs negativos legítimos de
  parlays) y `tactical_summary`. `calculate_combined_odds` intacto (la
  multiplicación de cuotas es correcta).
- **Datos:** la matriz de score NO está persistida en crudo — se reconstruye
  en `apps/api/routes/v1/tickets.py::_prediction_rows` desde los
  `lambda_home`/`lambda_away` persistidos con `build_score_matrix`
  (la misma función que usó el pipeline).
- `swap_ticket_leg` quedó fuera de scope (sigue con el promedio naive — no
  recibe matrices; nota para iteración futura).

**Tests:** `tests/test_ticket_true_ev.py` (7): suma manual de celdas,
diferencia vs producto ingenuo, córneres como independiente, partidos
distintos, patas mutuamente excluyentes (joint=0), e integración con el
builder. **Verificación manual antes/después:** edge 2 patas → avg 10.5% vs
EV real 6.3%; patas correlacionadas → promedio 10%, producto ingenuo 16.2%,
conjunta real 27%.

---

### P1-1 — Promedios reales por equipo para córneres/tarjetas/remates

**Problema:** `run_prediction` aceptaba 12 parámetros de promedios por equipo
(corners, yellows, shots on target) pero NINGÚN call-site los pasaba →
market_calculator siempre caía al promedio de liga hardcodeado.

**Solución:**
- **Confirmación de datos (paso 1):** SofaScore puebla
  `home/away_corners` y `home/away_shots_on_target` (+ xG/fouls) en Match y
  MatchAdvancedStats para partidos FINISHED. Las amarillas
  (`home_yellows`/`away_yellows`) vienen del fallback ESPN (más esparsas).
  `referee_profiles` existe (yellow_cards_avg, matches_count, link vía
  match.referee_id). Datos suficientes → se continuó con los pasos 2-6.
- **`get_team_stats_averages(team_id, window=STRENGTH_WINDOW)`** en
  match_repository: últimos 12 partidos FINISHED + regulation_time_only,
  ponderados con `DECAY_FACTOR ** k` (0.85, misma convención que
  strength_calculator). Calcula corners_for/against, yellows, sot_for/against
  (marcador "for" = datos propios de local/via visitante, "against" = del
  rival). Métrica sin valores válidos → `None` → fallback de liga (diseñado).
- **Orquestador** (`_run_quantitative_analysis`, único call-site de
  run_prediction): obtiene stats de ambos equipos y pasa los 12 parámetros.
  `home_yellows_avg`/`away_yellows_avg` con `or 0.0` (el pipeline no acepta
  None en esos dos).
- **`referee_strictness`:** cableado con dato REAL — nuevo helper
  `_get_referee_strictness`: `yellow_cards_avg` del perfil SofaScore ÷ línea
  de tarjetas de la liga (CARDS_LINE_BY_LEAGUE), solo si `matches_count >= 5`,
  clamp [0.5, 1.5].
- **`cards_mti`:** queda en 1.0 con comentario explícito — el contexto del
  partido (derby/descenso/clasificación) NO está persistido por partido; no se
  inventó un valor sintético.
- **market_calculator.py docstring:** actualizado (la nota citada por el
  prompt "promedio de liga con etiqueta de análisis" NO existía verbatim en el
  archivo actual — se corrigió el docstring del módulo).
- **Verificación antes/después (offline):** equipo con 16 córneres a favor vs
  liga 9.5 → `CORNERS_OVER_9_5` pasó de 0.0918 → 0.6655; `CARDS_OVER_4_5`
  0.2746 → 0.6425; `SHOTS_OT_OVER_7_5` 0.0951 → 0.2224. Los mercados ya no son
  idénticos al promedio de liga.

**Tests:** `tests/test_team_stats_averages.py` (4): promedio ponderado decay
verificado a mano, None sin datos, solo FINISHED cuenta, y el pipeline
responde a los promedios de equipo.

---

### P1-2 — Línea de apertura verdadera (bookmaker_odds)

**Problema:** `upsert_odds` hacía UPDATE in-place sobre
(match_id, market_name, bookmaker_name) — sin historial, el CLV medía drift de
sincronización, no el edge contra la apertura verdadera.

**Solución:**
- **Modelo:** `opening_odds_value: Mapped[float | None]` y
  `opening_odds_captured_at: Mapped[datetime | None]` en BookmakerOdd.
- **`upsert_odds`:** rama `else` (fila nueva) escribe apertura = odds_value +
  timestamp. Rama `if existing` NO toca la apertura (comentario explícito).
- **Repo:** nuevo `get_opening_odds_for_match` filtrando
  `opening_odds_value IS NOT NULL` (filas legacy pre-migración quedan NULL y se
  omiten — NO se backfilleó a propósito: atribuir la línea actual como
  "apertura" repetiría el sesgo).
- **Service:** `get_opening_odds_for_match` ya no es alias de
  `get_odds_for_match` — lee el método del repo (con el filtro de empate
  anómalo < 2.10 aplicado a la apertura).
- **clv_tracker.py:** cero cambios necesarios (ya llamaba al service y
  consume el mismo dict).
- **Migración 021** aplicada y verificada en Supabase (columnas
  double precision / timestamptz, nullable).

**Tests:** `tests/test_opening_odds.py` (5): apertura capturada en el primer
insert, nunca sobrescrita por upserts posteriores, el service devuelve la
apertura (2.10) y no el último sync (1.75), filas legacy NULL omitidas, filtro
de empate anómalo.

---

### P1-3 — Loop de evaluación de predicciones (prediction_outcomes)

**Problema:** no existía ningún mecanismo que comparara predicciones
persistidas contra el resultado real — por eso el bug de idempotencia (P0-1)
pasó desapercibido durante meses.

**Solución (dividido en sub-tareas, como pidió el prompt):**
1. **Modelo + migración 022** (aplicada via MCP, verificada): tabla
   `prediction_outcomes` con match_id, market_name, our_probability,
   predicted_verdict, actual_outcome (WON/LOST con CHECK), brier_component,
   evaluated_at, UNIQUE (match_id, market_name), RLS + política de lectura.
2. **`apps/api/engine/outcome_resolver.py`:** función pura
   `resolve_market_outcome(market_name, MatchFinalScore)` cubriendo TODOS los
   mercados de market_calculator: 1X2, DOUBLE_1X/X2/12, DNB (empate = LOST,
   convención documentada), OVER/UNDER de goles y por equipo (HOME_OVER_*/AWAY_OVER_*),
   BTTS_YES/NO, CORNERS/CARDS/SHOTS_OT over/under. Datos faltantes (corners
   null) → None → se saltea.
3. **Job `apps/api/jobs/evaluate_predictions.py`** (patrón clv_tracker):
   escanea partidos FINISHED de los últimos 30 días con predicción y sin
   evaluar, resuelve cada mercado del markets_json, inserta con
   `ON CONFLICT DO NOTHING` (idempotente — verificado: segunda corrida inserta
   0). Registrado como paso nuevo en el cron (corre cada 2h, solo evalúa lo
   nuevo). Sin alertas conectadas (como pidió el prompt).
4. **Reporte `apps/api/jobs/report_prediction_accuracy.py`:** Brier promedio,
   win rate real y probabilidad predicha promedio, agrupado por mercado y por
   liga, últimos 30 días.

**Tests:** `test_outcome_resolver.py` (34 parametrizados) +
`test_evaluate_predictions.py` (4): Brier exacto, idempotencia, skip de datos
faltantes, partidos sin predicción ignorados.

---

### P1-4 — Umbral EV 3% (packages/ml/betmind_ml/config.py)

**Cambio:** `EV_POSITIVE_THRESHOLD = 0.005` → `0.03`. `EV_AVOID_THRESHOLD`
intacto (-0.10).

**Solución:**
- Comentario corregido: el viejo decía "5% de margen conservador" (mentira —
  era 0.5%); ahora documenta el paso de 0.5% (apenas sobre breakeven, dejaba
  pasar mercados marginales) a 3% como **default temporal conservador SIN
  backtest todavía, sujeto a recalibración cuando P1-3 tenga suficientes
  datos**.
- **Limpieza colateral necesaria** (comentarios/contratos que decían 0.5%):
  - `ev_calculator.py`: docstring ("Si EV >= 0.005...") y el comentario del
    boundary de precisión flotante (0.5025×2.0−1.0 → 0.515×2.0−1.0).
  - `test_kelly_and_filters.py`: `test_ev_threshold_is_single_half_percent_contract`
    (assert == 0.005) → `test_ev_threshold_is_three_percent_temporal_default`
    (== 0.03); el test de boundary usa p=0.515, odds=2.0 → EV exacto 0.03.

**Verificación:** boletos de prueba en los 3 modos con el nuevo umbral;
mercado con EV=0.02 (antes válido) ahora se filtra correctamente.

---

### P1-5 — OddsInput expandido (23 mercados)

**Problema:** OddsInput solo tenía 4 campos (home_win, draw, away_win,
over_2_5) — el pipeline no podía mostrar EV de BTTS, corners, cards, shots.

**Solución:**
- **Schema:** 23 campos (1X2, over/under 1.5/2.5/3.5, btts_yes/no, y las
  líneas más usadas de corners/cards/shots — siempre AMBOS lados del par
  porque el EV se certifica desmarginando el overround contra el lado
  opuesto). Criterio documentado en el docstring.
  - `under_2_5` se agregó porque sin él OVER_2_5 NUNCA tenía EV (faltaba el
    lado opuesto).
  - `FIELD_TO_MARKET: ClassVar[dict]` — única fuente de verdad campo→mercado.
  - `from_market_dict(odds_map)` — factory para construir desde el dict de la
    DB (ignora mercados ausentes o cuotas ≤ 1.0).
- **`_build_bookmaker_odds`:** ahora itera `FIELD_TO_MARKET` (cubre los 23
  automáticamente, sin lista duplicada).
- **Callers:** `batch_predict.py` y el fallback de la ruta
  `apps/api/routes/v1/predictions.py` (el /partidos/[id]) usan
  `OddsInput.from_market_dict(odds_map)` — el dato ya estaba disponible en
  `get_odds_for_matches`/`get_odds_for_match`.
- **Hallazgo importante del test end-to-end:** `_compute_fair_probability` en
  ev_calculator.py solo manejaba `OVER_`/`UNDER_` AL INICIO del nombre —
  `CORNERS_OVER_8_5` NUNCA podía obtener fair probability (EV INSUFFICIENT
  para siempre, aun con ambas cuotas). Se extendió para resolver el opuesto en
  familias con prefijo (CORNERS_/CARDS_/SHOTS_OT_). Sin esto, los mercados
  nuevos no habrían materializado EV.

**Tests:** `tests/test_odds_input.py` (5): mapeo completo, ignorar odds
inválidas, roundtrip, EV real en pipeline para BTTS/OVER_1_5/OVER_3_5/
córneres/tarjetas/remates, y el fix de fair probability con prefijos.

---

### P2-1 — Unificar CARDS_LINE_BY_LEAGUE

**Problema:** dos diccionarios "idénticos" definidos de forma independiente en
config.py y market_calculator.py.

**Solución:**
- **Verificación previa (ciclo de imports):** config.py solo importa `os` —
  sin riesgo de ciclo.
- **Hallazgo:** NO eran idénticos — market_calculator tenía una clave extra
  `"default": 4.0` que config no tenía (ahí usaba CARDS_LINE_DEFAULT = 3.5).
  Por eso `calculate_cards_markets` usaba 4.0 para ligas desconocidas mientras
  el narrative usaba 3.5 — inconsistencia latente en producción.
- **Cambio:** config.py ahora incluye `"default": 4.0` (con comentario: lo usa
  calculate_cards_markets como fallback). market_calculator importa
  `from betmind_ml.config import CARDS_LINE_BY_LEAGUE`; la definición
  duplicada se eliminó. `get_cards_line` no se usa en market_calculator (solo
  en narrative_orchestrator), no hacía falta importarla.
- **Efecto colateral positivo:** `get_cards_line("default")` ahora devuelve
  4.0 (antes 3.5) — la narrativa de tarjetas queda alineada con el mercado
  cuantitativo para ligas no listadas.

**Verificación:** `mc is cfg` → True (misma referencia), 43 tests en los
suites afectados.

---

### P2-2 — Kelly: MIN como umbral, no piso (apps/api/engine/kelly.py)

**Problema:** `max(MIN_KELLY_STAKE, stake)` forzaba a apostar 0.25% del
bankroll aunque el Kelly real fuera 0.01%.

**Solución:**
- `if stake < MIN_KELLY_STAKE: return 0.0` (edge demasiado chico para una
  apuesta mínima operable) seguido de `round(min(MAX_KELLY_STAKE, stake), 4)`.
- Docstring del módulo y de la función actualizados. **El ejemplo del
  docstring estaba mal desde antes** (decía `0.60, 2.00 → 0.125` cuando en
  realidad da 0.02 por el clamp de MAX) — corregido con ejemplos reales:
  `0.54, 1.90 → 0.0072` y `0.501, 2.01 → 0.0`.
- `get_staking_suggestion` consistente: mensaje de "No apostar" cubre ambos
  casos (sin EV o edge < mínimo) y las bandas muestran el % real calculado en
  vez de rangos fijos que asumían el piso.

**Tests:** `test_stake_below_minimum_is_not_forced_up` (0.501, 2.01 → 0.0) +
`test_stake_above_minimum_passes_through` (0.54, 1.90 → 0.0072).

**Efecto colateral esperado:** en build_ticket_for_mode, las patas con edge
marginal aportan kelly_stake=0.0 — el kelly combinado baja en esos casos.

---

### P2-3 — Visibilidad del fallback de tokens en el fuzzy-match

**Problema:** el matching difuso de equipos usaba un fallback por tokens sin
dejar rastro — imposible auditar matches débiles.

**Solución (verificación + refuerzo):**
- **Confirmación P0-3:** en el flujo de sync, `_build_fixture_map` solo recibe
  fixtures acotados por liga (get_fixtures_by_date_range con league=). El único
  path global es el fallback explícito para partidos sin league_external_id
  (por diseño). Nota: el path de CLV (`fetch_closing_odds_for_match`) sigue
  con mapa global por fecha, pero es un match único en una sola fecha — fuera
  del flujo de sync.
- **`_team_match_strength(name_a, name_b) -> str | None`:** clasifica el match
  como `"exact"` | `"substring"` | `"tokens"` | `None`. `_fuzzy_team_match`
  ahora delega en él (contrato booleano idéntico — CERO cambio de
  comportamiento, no se tocó el umbral).
- **`_find_api_fixture`:** cuando el match usa el fallback de tokens (en
  cualquiera de las dos patas), loguea WARNING con los nombres completos de
  ambos equipos comparados y la fuerza de cada lado. Exacto y substring no
  loguean.

**Tests:** clasificación de fuerza, WARNING con nombres completos (caplog),
y ausencia de WARNING en exact/substring.

---

## 3. Errores encontrados durante la verificación final y sus soluciones

Al correr la suite completa (`pytest tests/`) aparecieron **3 problemas
PREEXISTENTES** (ninguno causado por los prompts):

### 3.1 — `test_subscriptions.py` roto en la colección

**Síntoma:** `ImportError: cannot import name '_valid_event_signature' from
'apps.api.routes.v1.subscriptions'` — el test importaba una función que nunca
existió en el módulo.

**Investigación:** la funcionalidad SÍ existía en
`apps/api/services/wompi_service.py` (`compute_wompi_event_checksum` +
`is_valid_wompi_event_signature`), pero `is_valid_wompi_event_signature`
acepta el checksum del body también — no cumplía el contrato del test (con un
checksum malo y el body correcto, retornaba True; el test espera False).

**Solución:** se implementó `_valid_event_signature(payload, checksum)` en
subscriptions.py como adaptador delgado: recalcula el checksum con
`compute_wompi_event_checksum` + `settings.WOMPI_EVENTS_SECRET` y compara SOLO
contra el checksum provisto con `secrets.compare_digest` (tiempo constante).
Sin comportamiento inventado — reusa la lógica ya validada de wompi_service.

### 3.2 — Bug de JSONB en SQLite (afectaba a 4 archivos de test)

**Síntoma:** `UnsupportedCompilationError: Compiler can't render element of
type JSONB` en el setup de test_match_dedup.py, test_ticket_bankroll.py,
test_security_fixes.py y test_subscriptions.py — el modelo `Match` tiene
`closing_odds` JSONB (postgres) y `Base.metadata.create_all` reventaba en
sqlite in-memory.

**Solución:** registración `@compiles(JSONB, "sqlite")` (compila JSONB como
JSON) movida a **`tests/conftest.py`** — antes vivía duplicada en 2 archivos de
test donde solo funcionaba cuando corrían en la misma sesión pytest. Ahora
aplica a TODA la suite, incluso con archivos en aislamiento. Los 4 archivos
pasaron de error a pasar.

### 3.3 — Bug real expuesto por 3.1: renovación DECLINED sin período de gracia

**Síntoma:** al poder correr por primera vez,
`test_declined_renewal_enters_grace_period` falló: `user.is_pro is False`.

**Causa raíz:** `apply_transaction_status` (subscription_service.py) cortaba
el PRO al instante ante una renovación DECLINED (`user.is_pro = False;
pro_expires_at = now`), ignorando el período de gracia que el propio test y
`settings.SUBSCRIPTION_GRACE_DAYS = 3` documentan. El bug existía desde antes
pero nunca se ejercitó porque el test siempre moría en el setup.

**Solución:** para `transaction.kind == "renewal"` con status
DECLINED/ERROR/VOIDED: `subscription.status = "past_due"` y el usuario
conserva PRO hasta `max(period_end, now) + SUBSCRIPTION_GRACE_DAYS`. Para
transacciones initial sigue cortando (cancelled, is_pro=False).

---

## 4. Estado final

- **`python -m pytest tests/` → 264 passed, 0 failed, 0 errors** (antes de los
  fixes: 236 passed + 1 error de colección + 13 errores de setup JSONB).
- Migraciones 021 y 022 aplicadas y verificadas en producción (Supabase,
  proyecto `sruhpmucytkaksdtkrsi` — Betmind Apuestas Deportivas).
- Cambios SIN commitear en el working tree (a la espera de confirmación).

## 5. Notas pendientes / deuda técnica documentada en el código

- `swap_ticket_leg` (ticket_builder) sigue usando el promedio naive de EV —
  no recibe las matrices de score (iteración futura).
- `fetch_closing_odds_for_match` (CLV) sigue usando fixtures globales por
  fecha — aceptable para un match único, pero podría acotarse por liga.
- Las filas de bookmaker_odds creadas ANTES de la migración 021 quedaron con
  `opening_odds_value = NULL` a propósito — el CLV las omite hasta que existan
  filas nuevas con apertura real.
- `cards_mti` queda en 1.0 hasta que el contexto del partido (derby/descenso/
  clasificación) se persista por partido.
- El sync ESPN de fixtures (MatchFixtureScraper) sigue desactivado con TODO —
  se puede reimplementar con el mapeo league_key→slug cuando se decida.
- El umbral EV 3% es temporal — recalibrar cuando prediction_outcomes acumule
  datos (reporte: `python -m apps.api.jobs.report_prediction_accuracy`).
