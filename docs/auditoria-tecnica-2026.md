# Auditoría Técnica BetMind AI — Cómo manejamos APIs, Mercados y Predicciones (2026)

> Auditoría interna previa a revisión externa. Complementa `docs/contexto-proyecto.md`.
> Fecha: 2026-08-10. Todo lo citado corresponde al código real del monorepo (archivo:línea).

---

## 1. Cómo se usa cada API en la práctica

### 1.1 ESPN API pública — nuestra fuente PRIMARIA de fixtures
| Aspecto | Detalle |
|---|---|
| Quién la llama | `EspnDataProvider` (provider_registry) + `EspnSummaryScraper` + `clv_tracker` (moneyline de cierre) |
| Cuándo | Sync de ligas (manual vía admin), `DataIngestionService` cascade, CLV antes del kickoff |
| Endpoints | `site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates=`, `.../{slug}/teams/{id}/schedule`, `.../{slug}/standings` |
| Cobertura | ~23 ligas (Big 5, Sudamérica, Concacaf, nórdicas) + UEFA (espn_provider.py:44) |
| Fallo | Devuelve `{}` y loguea; la cascada pasa al siguiente proveedor (espn_provider.py:142-155) |
| Costo | Gratis, sin key, **sin SLA ni contrato de datos** |

Detalle operativo:
- `get_finished_matches` = 1 request por equipo (~20-30 req/liga) con semáforo 8 y batches de 15 + sleep 0.3s (espn_provider.py:199-232).
- `get_leagues` = ~23 requests **secuenciales** por arranque (espn_provider.py:157-175).
- `get_upcoming_matches` = 7 requests (1 por día de la semana).
- **No tiene xG** → los stats avanzados (xG, SOT, córneres, tarjetas) los trae SofaScore post-partido.
- Sin retry/backoff: si ESPN está caído o geobloqueado, el sync simplemente no trae datos de esa liga (y la cascada intenta con API-Football).

### 1.2 football-data.org — Plan A para Premier y LaLiga
- Solo 2 ligas (`football_data_provider.py:24`). Requiere `FOOTBALL_DATA_KEY`.
- Se registra en el registry solo si la key existe (provider_registry.py:41-46).
- Maneja 429/403 explícitamente con `ExternalAPIException`.

### 1.3 API-Football (api-sports.io) — ÚNICA fuente de cuotas + fallback de datos
| Aspecto | Detalle |
|---|---|
| Quién la llama | `APIFootballService`: sync de cuotas (`OddsService`), sync de datos (`DataIngestionService`), CLV (línea de cierre), marcadores en `sync_today_matches` |
| Cuándo | Cada 2h (job CI) para cuotas; CLV 5-10 min antes del kickoff |
| Endpoints | `/fixtures`, `/odds?fixture=`, `/teams`, `/leagues`, `/standings` |
| Rate limit | ~10 req/min (plan actual) → throttle fijo de 6s entre fixtures (odds_service.py:203,209; clv_tracker.py:225) |
| Costo | Key pagada (plan Pro ≈ $20-30/mes según tier) |

Detalle operativo:
- `sync_odds_for_matches`: agrupa partidos por fecha y llama `/fixtures?date=` (SIN filtro de liga → trae TODOS los partidos del planeta ese día, miles de fixtures en el payload, muchos descartados). Luego matchea contra nuestros partidos por **nombres de equipos** con substring matching (`odds_service.py:255-272`).
- Por fixture hace 1 request a `/odds` y **duerme 6 segundos** (para respetar el límite de 10 req/min).
- Con ~30 ligas y ~50-80 partidos en la ventana, solo la fase de cuotas puede tomar **8-15 minutos** de reloj.
- El parser recorre TODOS los bookmakers y guarda la **MEJOR cuota por mercado** (`best_odds = max(...)`, odds_service.py:379) — sin validar ejecutabilidad ni consistencia entre casas.
- Filtro hardcodeado: cuota de empate < 2.10 se descarta como "Doble Oportunidad sospechosa" (odds_service.py:334-341, 403, 461).
- Bloques explícitos: mercados que contengan "double/chance/dnb/no bet/handicap" se descartan del parseo (odds_service.py:316, 326).
- Mapea: 1X2, O/U 0.5-3.5, BTTS, córneres (.5 y líneas enteras), tarjetas, remates a puerta.

### 1.4 Scrapers deterministas (Plan B — cero IA)
- `espn_summary_scraper.py`: parseo estricto del summary de ESPN (JSON con retries/backoff).
- `uefa_qualifiers_scraper.py`: Flashscore para eliminatorias UEFA (solo si el proveedor devuelve vacío en ligas UEFA).
- **⚠ CRÍTICO: `match_fixture_scraper.py` ya NO existe en `apps/api/services/scrapers/` pero `scripts/sync_today_matches.py:24` todavía hace `from ...scrapers.match_fixture_scraper import MatchFixtureScraper`** → el job diario de CI (`.github/workflows/daily_predictions.yml`) revienta con ImportError en el primer paso. Solo queda la referencia en `docs/archive/PROJECT_LOG.md:2301`.

### 1.5 Agente IA de datos (Plan C — último recurso, casi nunca se usa)
- LangGraph: `search` (DuckDuckGo) → `scrape` (crawl4ai) → `parse` → `validate` (graph.py).
- El parse usa **Claude `claude-3-5-sonnet-20241022`** vía instructor con JSON Schema estricto (parse_node.py:106).
- Valida que los fixtures extraídos no "contaminen" el modelo (validate_node.py:91).
- **⚠ Genera external_id con `hash()` de Python** (agent_provider.py:145,149-151) → el hash de Python cambia entre procesos (PYTHONHASHSEED random) → si el agente corre dos veces, los IDs no coinciden y el dedup debe absorber la diferencia por fuzzy.
- Solo devuelve datos si A y B fallaron (provider_registry.py:71-109).

### 1.6 SofaScore (stats post-partido)
- xG, shots, SOT, corners, fouls, incidentes, shotmap, perfil de árbitro (sofascore_ingester.py).
- Sin key; 1s de pausa entre los 4 endpoints por partido. Se invoca como ingesta post-partido (no está en el cron de 2h).

### 1.7 La identidad de entidades (el problema transversal)
Los IDs de `matches.external_id` y `teams.external_id` mezclan **4 namespaces** sin prefijo:
1. ESPN event/team IDs (numéricos)
2. API-Football fixture/team IDs (numéricos, rango distinto)
3. `sha256` truncado → módulo 2.000.000.000 (sync_today_matches.py:203-209, 231-235, 373-379)
4. `hash()` de Python (agente IA)

Lo que sí existe: `upsert_match` tiene dedup multi-proveedor en 3 niveles (match_repository.py:366-503):
1. Por external_id (mismo proveedor)
2. Por pareja de equipos exacta (team_id) en ventana ±2h → consolida y guarda el otro ID en `alternate_external_ids` (JSON)
3. Fuzzy por nombres canonicalizados ≥85% (Jaccard sobre tokens, team_normalizer.py)

**Aun así**, las capas defensivas siguen vivas: dedup en el frontend (apps/web/lib/api.ts:547-576) y dedup "defensivo" en batch_predict (batch_predict.py:49-91). Señal de que el dedup del backend no se considera suficiente en la práctica. El fuzzy scan es O(n) sobre la ventana ±2h sin índice. Y `alternate_external_ids` es una lista JSON sin metadata de proveedor ni dedup por fuente.

---

## 2. Cómo usamos la IA (y dónde NO la usamos)

### 2.1 Principio
**El LLM jamás toca la predicción.** Los números salen 100% del motor Poisson/EV. La IA solo redacta el "análisis táctico" DESPUÉS de que el motor calculó todo.

### 2.2 Cascada de análisis táctico (por partido, máx 400 tokens, JSON estricto)
```
llm_cascade.py: LLMCascadeService.generate_tactical_json()
  1. Groq   llama-3.1-8b-instant   (timeout 25s, temp 0.3, response_format json_object)
  2. Gemini gemini-2.0-flash       (fallback automático, mismo timeout)
  3. None  → narrativa sintética determinística (cero tokens, cero latencia)
```
- El output se valida contra `TacticalAnalysisOutput` (Pydantic) — si no cumple el contrato, se descarta y se usa sintético (llm_cascade.py:228-233).
- El prompt del táctico es mínimo: xG, probabilidades 1X2/O-U, EV del Over2.5, marcador más probable, confianza (prediction_orchestrator.py:625-660).
- Clientes síncronos en `run_in_executor` (no async nativo); `LLMCascadeService` se instancia **por request**.
- Costo por partido: ~400-800 tokens de output + prompt pequeño → céntimos; el problema no es el costo sino la calidad (modelo de 8B).
- Solo se persiste si el modelo devolvió contenido real (no sintético), y se cachea 6h en DB+Redis (prediction_orchestrator.py:117-119).
- El análisis táctico completo está gated por PRO (predictions.py:124-126: free ve 10 mercados y sin bet builder).

### 2.3 Agente IA de datos (Plan C)
Solo si ESPN y los scrapers fallan (casi nunca). Claude sonnet parsea el contenido web. Costo real por invocación: varias llamadas LLM + scrape → dólares por liga. Riesgo: es la fuente MÁS cara y MÁS frágil del sistema.

---

## 3. Superficie de API del backend (qué expone el producto)

| Endpoint | Función |
|---|---|
| `GET /api/v1/matches?date=&date_filter=&limit=` | Partidos + cuotas + predicción resumida (matches.py:28) |
| `GET /api/v1/matches/upcoming/` | Ventana -2h/+36h (matches.py:118) |
| `GET /api/v1/matches/{id}` | Detalle: odds, stats avanzadas, árbitro, eventos (matches.py:146) |
| `GET /api/v1/matches/{id}/h2h` | H2H + forma de ambos equipos (matches.py:314) |
| `POST /api/v1/matches/sync/{league_id}` (admin) | Sync manual de liga (matches.py:215) |
| `POST /api/v1/matches/sync-all` (admin) | Sync de las 3 ligas objetivo (matches.py:276) |
| `GET /api/v1/predictions/{match_id}` | Predicción completa + EV + táctico (predictions.py:59) — calcula on-demand si no hay cache |
| `POST /api/v1/tickets/generate` | Boletos por modo (EDGE/VALUE/BOLD) con filtros (tickets.py:396) |
| `POST /api/v1/tickets/save` | Guarda boleto (límites free: 5; anónimos 5/día por IP) (tickets.py:49) |
| `GET /api/v1/tickets/history` | Historial del usuario (tickets.py:103) |
| `PATCH /api/v1/tickets/{id}/status` | Marca WON/LOST/VOID → movimiento de bankroll (tickets.py:112) |
| `POST /api/v1/tickets/claim` | Reclama boletos anónimos (tickets.py:136) |
| `POST /api/v1/webhooks/wompi` | Webhook firmado de pagos (anti-replay ±5 min) |
| `POST /api/v1/subscriptions/*` | Activación/renovación vía Wompi |
| `GET /api/v1/leagues` | Catálogo de ligas |
| Auth | Supabase Auth (JWT, acceso 7 días sin refresh — decisión consciente de MVP) |

Rate limiting global: 200/min y 2000/hora por IP (main.py:32-36).

---

## 4. Modelo de datos (Supabase Postgres)

| Tabla | Rol | Notas |
|---|---|---|
| `leagues` | Catálogo (~30 ligas en FEATURED_LEAGUES, config.py:200) | external_id = API-Football ID |
| `teams` | Equipos | external_id = namespace mezclado (ESPN/AF/hash) |
| `matches` | Partidos, marcadores, estados | external_id mezclado; `alternate_external_ids` JSON; `regulation_time_only`; stats agregadas (corners, fouls, SOT) |
| `bookmaker_odds` | Cuotas por partido/mercado | `bookmaker_name='api_football'`; la "apertura" del modelo |
| `predictions` | Predicción cuantitativa persistida (lambda, índices, markets_json, value_score) | 1 por partido (upsert) |
| `tactical_analysis` | Narrativa IA persistida (goles/tarjetas/córneres/bet builder) | frescura 6h |
| `match_advanced_stats` | xG, SOT, corners, fouls (SofaScore) | |
| `match_events` | Goles, tarjetas, sustituciones (SofaScore) | |
| `referee_profiles` | Perfil de árbitro (SofaScore) | |
| `subscriptions` / `subscription_transactions` | Pagos Wompi | RLS estricto (solo SELECT authenticated; escritura solo backend) |
| `tickets` / `bankroll_movements` | Boletos guardados + bankroll | RLS por usuario |
| `users` | Usuarios (auth_uid de Supabase) | Sin SELECT público (se lee vía FastAPI `/users/me`) |

---

## 5. El motor cuantitativo — recorrido completo por partido

### Paso 0: Datos de entrada (match_repository → prediction_pipeline)
- `get_recent_form` (10 últimos por equipo, solo 90 min), `get_h2h` (6), `get_league_matches` (TODOS los finalizados de la liga, para promedios).
- Cuotas: solo 1X2 + O/U 2.5 se usan como input del EV (OddsInput, predictions.py:89-108).

### Paso 1: Promedios de liga (`calculate_league_averages`)
- `avg_goals_per_team_per_match` = total goles / (partidos × 2). Fallback global hardcodeado: 1.35.

### Paso 2: Fuerza de equipos (`calculate_team_strength`)
- Ventana 12 partidos, pesos `0.85^k` (el más reciente pesa 1.0).
- `avg_scored` / `avg_conceded` ponderados → **shrinkage Bayesiano k=5** hacia el promedio de liga.
- `attack_index = avg_scored / league_avg`; `defense_index = league_avg / avg_conceded` (>1 = buena defensa).
- Forma = puntos de los últimos 5. H2H = win rate de los últimos ≤6.

### Paso 3: Lambdas (xG) (`calculate_lambdas`, poisson_engine.py:34-100)
```
λ_home = atk_home / def_away × league_avg × ventaja_local × forma_home × h2h_home
λ_away = atk_away / def_home × league_avg × forma_away × h2h_away
```
- ventaja_local por liga hardcodeada (config.py:60-67): PL 1.20, LaLiga 1.22, BetPlay 1.30, default 1.20.
- forma: ±12.5% (FORM_WEIGHT=0.25). H2H: ±5% si hay ≥3 partidos.
- Clamps: λ ∈ [0.1, 6.0] + `validate_lambda` contra rangos "históricos" por liga hardcodeados (league_calibrator.py:186-215).
- **Mezcla Bayesiana extra** si un equipo tiene <5 partidos (prediction_pipeline.py:105-125): λ = λ×w + prior×(1−w), w = N/5. Floor absoluto: λ ≥ 0.15.

### Paso 4: Matriz de marcadores (`build_score_matrix`)
- Matriz 9×9 (0-8 goles) Poisson independiente + **corrección Dixon-Coles con ρ = −0.09 FIJO** (poisson_engine.py:218) en las 4 celdas (0-0, 1-0, 0-1, 1-1) + renorm.

### Paso 5: Mercados (`build_all_markets`, market_calculator.py)
| Mercado | Fórmula |
|---|---|
| 1X2, Doble Oportunidad, DNB | Sumas sobre la matriz (renorm) |
| O/U 0.5-3.5 | Sumas P(i+j) sobre el umbral |
| BTTS | 1 − P(home=0) − P(away=0) + P(0-0) |
| Goles por equipo O0.5/O1.5 | `1 − e^(−λ)` y `1 − e^(−λ)(1+λ)` |
| Córneres (6.5-12.5) | **Binomial Negativa** con K_DISPERSION=1.3 fijo; λ_córneres = promedio confuso de for/against × ventaja local (market_calculator.py:188-191) |
| Tarjetas (3.5-7.5) | **Poisson** con línea base por liga × MTI × strictness árbitro (market_calculator.py:214-242) |
| Remates (6.5-10.5) | **Poisson** con promedio por liga (market_calculator.py:245-279) |

**Nota:** los inputs de córneres/tarjetas/remates (home_yellows_avg, home_corners_for_avg, etc.) casi siempre llegan como defaults/cero desde el orquestador → el modelo cae al promedio de liga hardcodeado. La "personalización por partido" de estos mercados es en la práctica un promedio de liga con etiqueta de análisis.

### Paso 6: EV (`enrich_markets_batch`, ev_calculator.py)
- Desmargen del overround: 1X2 usa las 3 cuotas; O/U y BTTS usan su par opuesto; si falta el opuesto → `INSUFFICIENT` (sin EV certificado).
- `EV = P_modelo × cuota − 1`; `edge = P_modelo − P_fair`.
- Verdict: **POSITIVE_EV si EV ≥ 0.5%**, AVOID si ≤ −10%, NO_VALUE en medio (config.py:80-83).
- En la API: cuota < 1.20 con EV+ se degrada a NO_VALUE (prediction_orchestrator.py:755).

### Paso 7: Confidence y riesgo
- Score 0-100: 35% fiabilidad de fuerza, 25% forma, 20% H2H, 20% madurez de temporada (CONFIDENCE_WEIGHTS, config.py:119-124). **Heurístico, no calibrado.**
- Risk: LOW ≥75, MEDIUM ≥55 (con prob max ≥0.70 → LOW), si no HIGH (prediction_pipeline.py:187-196).
- `value_score` persistido = promedio de EV de TODOS los mercados (incluye los sin cuota → diluye el valor real) (prediction_orchestrator.py:389-393).

### Paso 8: Staking (kelly.py)
- Quarter-Kelly: `f* = (p×b − q)/b`, stake = 0.25×f*, clampado a [0.25%, 2%] del bankroll.
- En parlays: suma de Kellys por pata, tope 2% (ticket_builder.py:197-208).

### Paso 9: Boletos (`build_ticket_for_mode`, ticket_builder.py)
- Modos con configs (ticket_builder.py:12-61): EDGE (2 patas, cuotas 1.5-3.5, prob min 40%, mercados restringidos), VALUE (3 patas, 2.5-12), BOLD (4 patas, 8-30, sin restricción de mercados).
- Filtros: anti-cáscara (favoritos <1.25 en ligas de alta varianza, ticket_builder.py:184-194), máx 1 empate por boleto, combinaciones prohibidas (UNDER_2_5+BTTS_YES, 1X2_AWAY+CORNERS_OVER_8_5, etc., ticket_builder.py:63-73), correlaciones positivas conocidas con bonus (ticket_builder.py:75-83).
- Recalcula EV con las cuotas reales en el momento de generar (tickets.py:267-302) y evita repetir partidos entre modos.
- **Horizon shifting**: si "hoy" no tiene suficientes oportunidades +EV, expande a +24h/+48h (tickets.py:467-483).

---

## 6. Sospechas detectadas por el equipo — SIN VALIDAR

> ⚠️ **IMPORTANTE PARA EL REVISOR EXTERNO:** esta lista es lo que NOSOTROS creemos que puede estar mal, no verdades confirmadas. Trátala como material crudo: las referencias (archivo:línea) son verificables, pero la interpretación puede estar equivocada, incompleta o ser exagerada. **No des nada de esta lista por bueno.** Confirma, corrige o descarta cada ítem con tu propio análisis — y sobre todo, busca problemas que NO estén aquí: lo que no vimos es justamente lo que más necesitamos.

### 🔴 Sospechas críticas (nuestra prioridad)
1. **Job de producción posiblemente roto**: `sync_today_matches.py:24` importa `MatchFixtureScraper` desde `apps.api.services.scrapers.match_fixture_scraper`, y ese archivo NO existe en el repo (solo quedó el `.pyc` en `__pycache__` y la referencia en `docs/archive/PROJECT_LOG.md:2301`). Si es así, el cron de 2h muere en el paso 1 y no hay sync de partidos ni cuotas. **¿Lo confirmas? ¿Hay algo que se nos escape (otro import, un módulo reconstruido en runtime)?**
2. **Posible sesgo de supervivencia en el EV**: guardamos la MEJOR cuota entre todos los bookmakers (`odds_service.py:379`, `best_odds = max(...)`) sin validar ejecutabilidad, suspensión ni consistencia entre casas. Sospechamos que esto infla el EV reportado. **¿Cuánto? ¿Es defendible en algún caso?**
3. **Umbral +EV de 0.5% posiblemente menor que el error del modelo**: con ρ fijo, parámetros hardcodeados y muestras de 5-12 partidos, sospechamos que el ruido del modelo supera 0.5% y la etiqueta "+EV" es en gran parte clasificación de ruido. **¿Cómo estimar el umbral correcto?**
4. **Identidad de entidades frágil**: 4 namespaces de IDs conviven en `external_id` (ESPN, API-Football, sha256 truncado, `hash()` de Python). Sospechamos que `hash()` (agent_provider.py:145,149-151) es inestable entre procesos (PYTHONHASHSEED) y que el dedup del backend (match_repository.py:366-503) no es suficiente: por eso siguen vivas capas defensivas en el frontend (api.ts:547-576) y en batch_predict (batch_predict.py:49-91). **¿Es el dedup backend sólido o un parche? ¿Qué rompería en el peor caso?**

### 🟠 Sospechas altas
5. **ρ = −0.09 fijo** en Dixon-Coles (poisson_engine.py:218), sin estimar por liga/temporada. El paper original lo estima. **¿Cuánto daña esto la calibración?**
6. **Parámetros "calibrados empíricamente" hardcodeados y duplicados en 3 archivos** (config.py, market_calculator.py, league_calibrator.py): ventaja local, líneas de tarjetas, promedios de córneres/SOT, rangos de λ. Sin evidencia de backtest que los respalde. **¿Están bien? ¿Cómo se deben calibrar de verdad?**
7. **Sin loop de evaluación en producción**: el backtesting es offline/manual; nadie mide hit rate/Brier/ROI real de las predicciones persistidas. Sospechamos que es imposible saber si el sistema funciona. **¿Qué pipeline de evaluación propondrías?**
8. **Mercados fantasma**: el modelo calcula DNB y Doble Oportunidad pero el parser de cuotas los bloquea explícitamente (odds_service.py:316,326) → siempre "sin cuota" en el producto. **¿Es un bug, una decisión, y qué impacto tiene?**
9. **Mercados secundarios sin datos reales por partido**: los inputs de córneres/tarjetas/remates casi nunca llegan al pipeline (el orquestador no los pasa) → caen al promedio de liga hardcodeado. Sospechamos que el "análisis de córneres/tarjetas" es un promedio de liga con narrativa. **¿Vale la pena mantenerlos?**
10. **Modelo LLM débil para el táctico premium**: llama-3.1-8b-instant con 400 tokens como "cerebro táctico". **¿Aporta valor o resta credibilidad?**
11. **CLV con apertura falsa**: la "apertura" es la cuota del último sync, no la apertura real del mercado → sospechamos que el CLV mide drift del sync, no edge del modelo (clv_tracker.py:233).
12. **Sync de cuotas ineficiente**: `/fixtures?date=` sin filtro de liga trae miles de fixtures de todo el mundo; 6s de sleep fijo por partido (odds_service.py:203) → 8-15 min por corrida y alto riesgo de rate limit.

### 🟡 Sospechas medias
13. `scanner_orchestrator.py` es un stub que siempre devuelve lista vacía → la página `/senales` no funciona.
14. **Código muerto en producción** (solo lo importan los tests): `apps/api/engine/{corners_model,player_props_model,match_tension}.py`; `estimate_lambdas_from_odds` (deprecado); `_fallback_quant_with_gemini` / `_try_gemini_analysis`; path `odds_based` inalcanzable; `packages/ml/betmind_ml/pipeline/{trainer,feature_store,ingestion}.py` con NotImplementedError.
15. Dedup por substring en `odds_service._fuzzy_team_match` (odds_service.py:255-272), inconsistente con el Jaccard canónico de `team_normalizer`.
16. Throttle fijo sin backoff adaptativo; ESPN sin retry; los errores se tragan con `return {}` sin alertas (espn_provider.py:142-155).
17. `LLMCascadeService` instanciado por request; clientes LLM síncronos en executor.
18. Confidence score heurístico sin calibración; `value_score` = promedio de EV de todos los mercados (incluye los sin cuota) — sospechamos que no significa nada (prediction_orchestrator.py:389-393).
19. `MIN_KELLY_STAKE` 0.25% obliga a apostar en edges mínimos (kelly.py:17-18).
20. Sin ruff/mypy/lint; `API_BASE` hardcodeado a localhost:8000 en el frontend (api.ts:6).
21. `get_leagues` de ESPN: ~23 requests secuenciales por arranque del registry.

### Escalabilidad / operación (sospechas)
- Todo es síncrono en un job de CI cada 2h: sin cola, sin workers, sin retries programados. Un fallo de API externa = datos viejos hasta la siguiente corrida.
- `tickets/generate` lee todas las predicciones de la ventana con N+1 queries y sin paginación.
- El costo de IA actual es bajo (400 tokens × ~100 partidos × 12 corridas/día), pero el agente IA de datos (Claude + crawl4ai) es caro y frágil, y no hay guardrail de costo si empieza a usarse con frecuencia.

---

## 7. Preguntas abiertas para el revisor externo

1. **Fuentes de cuotas**: ¿API-Football es defendible para EV? ¿The Odds API / Pinnacle API / Oddsblaze / exchanges? ¿Cómo validar líneas ejecutables?
2. **Ground truth**: ¿cuotas de cierre como etiqueta de calibración? ¿Protocolo de monitoreo de calibración en producción?
3. **Modelo de goles**: ¿ρ por liga? ¿Poisson-Dirichlet / Dixon-Robinson moderno / cópulas? ¿O el edge real está solo en 1X2/O-U con datos de mercado?
4. **Mercados secundarios**: ¿valen la pena córneres/tarjetas/remates sin datos por partido? ¿Regresión vs NB con K fijo?
5. **¿ML real (XGBoost) o el problema es de features/cuotas?**
6. **¿El LLM táctico aporta o resta** (contradicción entre "terminal cuantitativa" y narrativa de un 8B)?
7. **Umbrales**: ¿0.5% EV y quarter-Kelly racionales dado el error del modelo? ¿Cómo fijarlos empíricamente?
8. **Regulatorio/comercial**: +EV a minoristas en BetPlay, riesgo de boletos desiertos (sin cuota real), Coljuegos/T&C.
9. **Identidad**: ¿cómo ordenar los namespaces (proveedor + ID) y el merge sin reescribir todo?
10. **Métricas públicas**: qué mostrar en el dashboard para generar confianza real (y detectar drift).

---

## 8. Archivos clave para referencia

| Área | Archivo |
|---|---|
| Contexto del proyecto | `docs/contexto-proyecto.md` |
| Proveedores de datos | `apps/api/services/providers/{espn_provider,football_data_provider,provider_registry,deterministic_scraper_provider}.py` |
| Agente IA datos | `apps/api/services/providers/ai_agent/**` |
| Cuotas | `apps/api/services/odds_service.py` |
| Ingestión | `apps/api/services/data_ingestion.py`, `scripts/sync_today_matches.py` |
| LLM cascade | `apps/api/services/llm_cascade.py` |
| Orquestador | `apps/api/orchestrators/prediction_orchestrator.py` |
| Rutas | `apps/api/routes/v1/{matches,predictions,tickets,scanner}.py` |
| Repos | `apps/api/repositories/{match_repository,team_repository,bookmaker_odd_repository}.py` |
| Motor ML | `packages/ml/betmind_ml/{models,features,ev,calibration,backtesting,pipeline}/**` |
| Config/parámetros | `packages/ml/betmind_ml/config.py` |
| Kelly/Tickets | `apps/api/engine/{kelly,ticket_builder}.py` |
| CLV | `apps/api/jobs/clv_tracker.py` |
| CI | `.github/workflows/daily_predictions.yml` |
| Frontend | `apps/web/lib/api.ts` |
