# INFORME DEFINITIVO — Deduplicación de Partidos & Arquitectura de Cuotas Props (Córneres / Tarjetas / Remates)

**Autor:** Principal Data Architect & Senior Sports Betting Engineer — BetMind AI
**Fecha:** 2026-08-03
**Alcance:** Corrección de duplicados (código + DB producción), diagnóstico verificado en vivo, investigación de APIs (Reddit/web), matriz comparativa y plan de arquitectura híbrida.

---

## 1. CAUSA RAIZ Y FIX DE PARTIDOS DUPLICADOS

### 1.1 Diagnóstico (verificado en código y en DB de producción)

El pipeline de ingesta de BetMind usa **tres fuentes que escriben el MISMO partido real con external_id de namespaces distintos**:

| Fuente | Namespace de `external_id` | Ejemplo real (prod) |
|---|---|---|
| ESPN Scoreboard (`espn_provider.py`) | IDs de 9 dígitos | `401841443` |
| API-Football (`api_football.py`) | IDs de 7 dígitos | `1493009` |
| football-data.org (`football_data_provider.py`) | IDs de ~5 dígitos | `430xxx` |

`MatchRepository.upsert_match()` solo deduplicaba por `external_id` (único por namespace). Como cada proveedor reporta un ID distinto para el mismo partido, el upsert insertaba un segundo registro en lugar de actualizar el existente.

**Verificación en Supabase (proyecto `sruhpmucytkaksdtkrsi`):**
- `716` partidos totales → **57 grupos duplicados** (misma pareja de equipos en ventana < 2h, external_id diferente).
- Ejemplos reales: `Huracán vs Banfield` (ext `1493009` vs `401841443`), `Orlando City vs Nashville` (hora ESPN `00:46 UTC` vs API-Football `23:30 UTC`, 46 min de diferencia).
- Los duplicados tenían datos huérfanos: `13` bookmaker_odds, `39` predicciones, `36` análisis tácticos.

### 1.2 Fix aplicado (3 capas)

**Capa A — Write-time dedup (backend, permanente):** `apps/api/repositories/match_repository.py`
- Nuevo método `get_by_team_pair_window(home, away, match_date, window_hours=2)`: busca la misma pareja de equipos dentro de ±2h.
- `upsert_match()` ahora consolida: si no existe por external_id pero sí por pareja+ventana, **actualiza el registro existente**, guarda el external_id entrante en la nueva columna `matches.alternate_external_ids` (JSON array) y aplica reglas de riqueza de datos:
  - Status: `FINISHED` (3) > `LIVE` (2) > resto (1) — nunca se degrada un partido finalizado.
  - Marcador: solo se sobreescribe cuando el nuevo registro trae datos (no `None`).

**Capa B — Limpieza de producción (migración aplicada `011_cross_provider_match_dedup`):**
1. `ALTER TABLE matches ADD COLUMN alternate_external_ids TEXT`
2. Consolidación de los 57 pares: selección de canónico por prioridad (FINISHED + marcador + cuotas + predicción + external_id no-ESPN + id menor), re-parenting de `bookmaker_odds`, `predictions`, `tactical_analyses`, `match_events`, `match_advanced_stats` al canónico, registro del external_id alternativo y borrado del duplicado.
3. Índice único de red de seguridad: `(league_id, home_team_id, away_team_id, date_trunc('hour', match_date AT TIME ZONE 'UTC'))`.

**Capa C — Client-side (frontend):** `apps/web/lib/api.ts`
- `dedupeMatches()`: agrupa por `league|homeTeamId|awayTeamId`, ventana de 2h, conserva el registro más rico (predicción > cuotas > marcador). Defensa en profundidad para el Dashboard.

### 1.3 Verificación post-fix (producción)

```
Total partidos:         716 → 659  (57 duplicados eliminados)
Pares duplicados restantes: 0
Partidos con alternate_external_ids: 57
Huérfanos (odds/predicciones/tácticos): 0
Dashboard (ventana -2h/+36h): 19 partidos, 0 duplicados
```

**Pruebas:** `tests/test_match_dedup.py` (4 tests: upsert mismo ID, consolidación cross-provider 2h, partidos legítimos >2h, no-degradación FINISHED→LIVE) — **4 passed**.

---

## 2. CAUSA RAIZ DE LA FALTA DE CUOTAS DE PROPS (VERIFICADO EN VIVO)

### 2.1 Bug #1 — Parser detenido en el primer bookmaker

`odds_service.py::_fetch_and_parse_odds` tenía `if parsed: break`: se detenía tras el **primer bookmaker** con cualquier mercado parseado. Si ese bookmaker no ofrecía córneres/tarjetas, se perdían aunque los tuvieran los otros 13.

### 2.2 Bug #2 — Nombres de mercado reales no coincidían con los parseados

Probe en vivo (key free plan, fixture `1493040` Lanus vs Instituto, 14 bookmakers):

| Mercado buscado por el parser | Nombre REAL en la API |
|---|---|
| `"Corners Over/Under"` (con slash) | **`"Corners Over Under"`** (con espacio) — 10Bet, Bet365, Pinnacle, 1xBet, Betano, Superbet, Marathonbet, Unibet |
| `"Shots on Target Over/Under"` | **`"Total ShotOnGoal"`** (Betano, Superbet) |
| `"Cards Over/Under"` ✓ | `"Cards Over/Under"` (Bet365, Unibet, 1xBet, Betano, Superbet) ✓ |

Resultado: aunque la API SI entrega córneres/tarjetas/remates **incluso en el plan free**, el pipeline guardaba **cero** de estos mercados (confirmado: 0 filas `CORNERS_*`/`CARDS_*`/`SHOTS_*` en `bookmaker_odds` de producción).

### 2.3 Fix aplicado

- Refactor: `_parse_raw_odds_payload()` — **agrega TODOS los bookmakers** y por mercado conserva la mejor cuota (máxima).
- Mapas expandidos con los nombres reales (`CORNERS_BET_NAMES`, `CARDS_BET_NAMES`, `SHOTS_OT_BET_NAMES`) y líneas reales (córneres 4.5–13.5 + líneas enteras 4–13 de Pinnacle/1xBet; tarjetas 2.5–7.5; remates 4.5–10.5).

### 2.4 Verificación E2E en vivo (mismo key, 10 fixtures del 2026-08-03)

```
Córneres O/U:  8/10 fixtures (antes: 0 en producción)
Tarjetas O/U:  3/10
Remates O/U:   2/10
Mercados por fixture: 43–71 (antes: 5–13 solo 1X2/BTTS/goles)
```

Además la API entrega **player props reales** en el plan free: `Player Shots On Target` (Bet365, valores `"Matias Sepulveda - 1+"`), `Home/Away Player Shots`, `Corners 1x2`, `Cards Asian Handicap`, `Home Team Yellow Cards`. → oportunidad para Fase B.

**Pruebas:** `tests/test_odds_parser_real_payload.py` (5 tests con payload real recortado) — **5 passed**.

---

## 3. INVESTIGACIÓN DE APIS — COMUNIDADES (REDDIT) Y FUENTES PRIMARIAS

Fuentes consultadas: `r/algobetting`, `r/sportsbook`, `r/arbitragebetting`, `r/SoccerBetting`, `r/webscraping`, `r/webdev` (via búsqueda), docs y pricing de `the-odds-api.com`, `sportmonks.com`, `oddsjam.com`, `surebets.bet` (review OddsJam/OpticOdds 2026), `footyapps.com/guide/free-football-apis` (benchmark 2026), y **probes en vivo contra la API-Football con la key real del proyecto**.

### Hallazgos clave de la comunidad

1. **Props = mercado difícil**: "getting props is notoriously more difficult & historical archives of them aren't really that available" (`r/algobetting`). Las opciones reales son: API comercial, scraper propio (frágil) o agregador.
2. **The Odds API es la respuesta recurrente** para props: "I'm using the-odds-api.com currently for player prop odds across a number of sportsbooks. They have a free tier but limit your monthly requests" (`r/algobetting`). Request = 1 deporte + 1 mercado + 1 región (retorna TODOS los partidos de ese deporte/mercado).
3. **Scrapers propios se rompen**: "I have a few scrapers working on fanduel.. but damn thing breaks a ton and a pain" (`r/sportsbook`); "all options on the USD20 price range are bad. Most of them fail because the sites change the layout or block the scrapers" (`r/arbitragebetting`).
4. **API-Football/Sportmonks data quality**: "api-football might be the best [of the cheap ones], I built a platform around it that detects most problems they have"; "sportmonks has much more problems with matches that aren't updated" (`r/arbitragebetting`). Para mercados de tarjetas pre-match multi-bookmaker solo LSports (€1500/bookie) — fuera de presupuesto (`r/algobetting`).
5. **The Odds API confirmó** (docs primarias): mercados soccer `alternate_totals_corners` (Total Corners O/U), `alternate_team_totals_corners`, `alternate_spreads_corners` (Handicap Corners), `alternate_totals_cards` (Total Cards O/U), `alternate_spreads_cards`, `corners_1x2`, y player props soccer (`player_shots_on_target`, `player_shots`, `player_to_receive_card`, `player_goal_scorer_anytime`) para EPL/Ligue1/Bundesliga/SerieA/LaLiga/MLS — **solo bookmakers US**.
6. **OddsJam/OpticOdds**: feed enterprise sales-gated, sin precios públicos, props más profundos del mercado (100-200+ books), tras demanda Swish Analytics por datos scrapeados — no apto para <$10/mes.

---

## 4. MATRIZ COMPARATIVA DE APIS

| API | Free tier | Costo | Requests | Córneres O/U | Tarjetas O/U | Remates (shots OT) | Player Props | 1X2/Goles | Liga BetPlay (CO) | Veredicto |
|---|---|---|---|---|---|---|---|---|---|---|
| **API-Football (actual)** | 100 req/día | $19/mo Pro (7.5K/día) | x2 por fixture | ✅ `Corners Over Under` (8/10 fixtures, VERIFICADO) | ✅ `Cards Over/Under` (3/10) | ✅ `Total ShotOnGoal` + player props Bet365 (2/10) | ✅ parcial (Bet365) | ✅ | ✅ | **KEEP — fixture/scores/odds base** |
| **The Odds API** | **500 créditos/mes (todos los mercados)** | $30/mo (20K) / $59 (100K) | 1 por deporte+mercado+región | ✅ `alternate_totals_corners` | ✅ `alternate_totals_cards` | ✅ `player_shots_on_target` (soccer props) | ✅ soccer props US books | ✅ h2h/totals/btts | ❌ (no LATAM) | **ADOPTAR — fuente de props reales** |
| **Sportmonks Football** | 2 ligas (DK+SCO), sin expiración | €29/mo (5 ligas) + €15/mo Odds add-on (150+ mercados, 50+ books) | por llamada | ✅ (odds add-on) | ✅ | ✅ | ✅ | ✅ | ✅ (2,200 ligas) | **PLAN B — migración a medio plazo** |
| **OddsJam / OpticOdds** | ❌ | Sales-gated (empresa) | push/pull | ✅ profundidad máxima | ✅ | ✅ | ✅ (los mejores) | ✅ | ❌ | **FASE C — solo si escala** |
| **SofaScore (scraper, ya integrado)** | Gratis (sin key) | $0 | ~4 req/partido | stats post-match | stats post-match | stats post-match | ❌ | ❌ (solo stats) | ✅ | **KEEP — stats avanzadas + verificación** |
| **Scraper directo (Bet365/Pinnacle)** | Gratis | $0 + mantenimiento | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **ÚLTIMO RECURSO — frágil (consenso comunidad)** |

**Presupuesto recomendado:** $0 hoy (key free ya funciona con el parser corregido) → $19/mo API-Football Pro + $30/mo The Odds API (o $59) = **$49–78/mes** para cobertura completa; o **$0** con solo el fix actual (córneres 80%, tarjetas 30%, remates 20% de cobertura).

---

## 5. PLAN DE ARQUITECTURA HÍBRIDA (Fases)

### Fase A — Inmediata (YA implementada, $0)
1. ✅ Dedup 3 capas (backend + migración + frontend).
2. ✅ Parser multi-bookmaker + nombres reales (córneres 8/10, tarjetas 3/10, remates 2/10 en vivo).
3. Ejecutar `scripts/sync_today_matches.py` (o el cron) para poblar `bookmaker_odds` con córneres/tarjetas/remates de los próximos partidos.

### Fase B — Cuotas de Props reales (1 semana, $30/mes)
1. **The Odds API**: nueva integración `apps/api/services/odds_service.py` + `TheOddsAPIClient` (modelo `the_odds_provider`).
   - Fetch por sport_key soccer (`soccer_epl`, `soccer_spain_la_liga`, `soccer_germany_bundesliga`, `soccer_italy_serie_a`, `soccer_france_ligue_one`, `soccer_usa_mls`, ...) + mercados `alternate_totals_corners`, `alternate_totals_cards`, `player_shots_on_target`, `h2h`, `totals`.
   - Región `us` para props; `eu` para 1X2/goles (Pinnacle, 1xBet, Betfair, Unibet, William Hill, BetVictor).
   - Mapeo de partido por nombre+commence_time (ventana 2h) → `match_id` local; **nunca** inserta partidos (la ingesta sigue en ESPN/API-Football).
   - Uso: 5 sport_keys × 4 mercados × 1 región = 20 créditos/refresh → ~600/mes con 1 refresh cada 3h → cabe en el tier free (500) o $30 (20K).
   - Persistencia: `bookmaker_odds` con `bookmaker_name='the_odds_api'`; el lector (`get_odds_for_match`) ya une por `market_name` — sin cambios en ML.
2. **Player props reales** (API-Football Bet365 `Player Shots On Target` ya disponible): nueva tabla `player_prop_odds(match_id, player_name, market, line, odds, bookmaker_name)` + endpoint de props; conectar a `player_props_model.py`.

### Fase C — Migración a Sportmonks (opcional, €29–44/mes)
- Reemplaza API-Football para fixtures/odds cuando se requieran los 150+ mercados y 50+ bookmakers en una sola fuente; el odds add-on incluye córneres/tarjetas/remates con cobertura latina completa (incluye Liga BetPlay).
- El dedup 2h ya soporta un 4º namespace (solo añadir el provider a `provider_registry`).

### Fase D — Escalamiento (si el negocio lo requiere)
- OddsJam/OpticOdds: feed enterprise para alta frecuencia (sub-segundo) y props deep. Nota legal: datos de odds agregados tienen disputas de licencia (caso Swish vs OpticOdds).

### Monitoreo y guardarraíles
- Cron diario: `sync_today_matches.py` + dedup automático (write-time) + limpieza de `bookmaker_odds` stale (>12h pre-match).
- Alerta si `matches` vuelve a tener pares <2h (query de diagnóstico incluida en la migración) o si un partido queda sin cuotas de córneres con disponibilidad confirmada.
- Cache: los fixtures no cambian minuto a minuto → cachear por 1h y refrescar odds cada 3-6h.

---

## 6. RESULTADOS CUANTITATIVOS FINALES

| Métrica | Antes | Después |
|---|---|---|
| Partidos duplicados en producción | 57 pares (716 filas) | **0** (659 filas, 57 alternate_ids) |
| Dashboard ventana -2h/+36h | duplicados visibles | **0 duplicados** (19 partidos) |
| Fixtures con cuotas de córneres (probe 10) | 0 (parser roto) | **8/10** |
| Fixtures con cuotas de tarjetas | 0 | **3/10** |
| Fixtures con cuotas de remates | 0 | **2/10** |
| Mercados por fixture | 5–13 | **43–71** |
| Tests | — | **113 passed** (9 nuevos) |
