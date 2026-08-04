# 02 — Catálogo de Ligas y Modelos ML de BetMind AI

> Documento maestro del motor cuantitativo, fiel al código fuente de `apps/api/config.py`, `apps/api/orchestrators/prediction_orchestrator.py`, `apps/api/repositories/match_repository.py` y `packages/ml/betmind_ml/`.

---

## 1. Catálogo de Ligas (26 ligas en `FEATURED_LEAGUES`)

### 1.1 Fuente única de verdad: `apps/api/config.py`

```python
FEATURED_LEAGUES: dict[str, dict]  # cada entrada: {api_football_id, name, country, match_type}
```

**A.** `FEATURED_LEAGUES` (26 ligas) → `FEATURED_LEAGUE_IDS: list[int]` y `KNOCKOUT_CUP_LEAGUE_IDS: set[int]` (9 copas).

**B.** `apps/api/orchestrators/prediction_orchestrator.py:30` — `LEAGUE_EXTERNAL_ID_TO_KEY`, diccionario derivado automáticamente de `FEATURED_LEAGUES` (fuente única de verdad → clave Poisson):

```python
LEAGUE_EXTERNAL_ID_TO_KEY = {info["api_football_id"]: league_key for league_key, info in FEATURED_LEAGUES.items()}
```

**C.** `apps/api/repositories/match_repository.py:31` — `LEAGUE_KEY_TO_EXTERNAL_ID` (mismo mapeo, usado por filtros y backtesting).

**D.** Frontend: `LEAGUE_ID_MAP` en `apps/web/lib/api.ts` y `LEAGUE_METADATA` en `apps/web/lib/league-metadata.ts`.

### 1.2 Tabla maestra (26 ligas)

| # | `league_key` (ML) | `api_football_id` | Nombre | País | `match_type` |
|---|---|---|---|---|---|
| 1 | `liga_betplay` | **239** | Liga BetPlay Dimayor | Colombia | LEAGUE |
| 2 | `copa_colombia` | **241** | Copa Colombia | Colombia | KNOCKOUT_CUP |
| 3 | `liga_profesional_arg` | **128** | Liga Profesional | Argentina | LEAGUE |
| 4 | `copa_arg` | **130** | Copa de la Liga Profesional | Argentina | KNOCKOUT_CUP |
| 5 | `serie_a_bra` | **71** | Serie A | Brasil | LEAGUE |
| 6 | `serie_b_bra` | **72** | Serie B | Brasil | LEAGUE |
| 7 | `copa_do_brasil` | **73** | Copa do Brasil | Brasil | KNOCKOUT_CUP |
| 8 | `liga_mx` | **262** | Liga MX | Mexico | LEAGUE |
| 9 | `mls` | **253** | Major League Soccer | USA | LEAGUE |
| 10 | `mls_open_cup` | **254** | US Open Cup | USA | KNOCKOUT_CUP |
| 11 | `libertadores` | **13** | CONMEBOL Libertadores | Sudamerica | KNOCKOUT_CUP |
| 12 | `sudamericana` | **11** | CONMEBOL Sudamericana | Sudamerica | KNOCKOUT_CUP |
| 13 | `liga_pro_ecu` | **275** | Liga Pro | Ecuador | LEAGUE |
| 14 | `primera_chile` | **274** | Primera Division | Chile | LEAGUE |
| 15 | `liga_1_peru` | **281** | Liga 1 Peru | Peru | LEAGUE |
| 16 | `premier_league` | **39** | Premier League | England | LEAGUE |
| 17 | `efl_championship` | **40** | EFL Championship | England | LEAGUE |
| 18 | `laliga` | **140** | LaLiga | Spain | LEAGUE |
| 19 | `laliga_hypermotion` | **141** | LaLiga Hypermotion | Spain | LEAGUE |
| 20 | `bundesliga` | **78** | Bundesliga | Germany | LEAGUE |
| 21 | `serie_a` | **135** | Serie A | Italy | LEAGUE |
| 22 | `ligue_1` | **61** | Ligue 1 | France | LEAGUE |
| 23 | `eredivisie` | **88** | Eredivisie | Netherlands | LEAGUE |
| 24 | `ucl` | **2** | UEFA Champions League | Europa | KNOCKOUT_CUP |
| 25 | `uel` | **3** | UEFA Europa League | Europa | KNOCKOUT_CUP |
| 26 | `uecl` | **848** | UEFA Conference League | Europa | KNOCKOUT_CUP |

> 17 ligas `LEAGUE` + 9 `KNOCKOUT_CUP`. El mapeo se espeja en:
> - `LEAGUE_KEY_TO_EXTERNAL_ID` (match_repository) — 26 claves idénticas.
> - Migración `011_add_match_type.sql` — backfill de `match_type='KNOCKOUT_CUP'` para los IDs `{241, 130, 73, 254, 13, 11, 2, 3, 848}`.
> - `KNOCKOUT_CUP_LEAGUE_IDS` (config.py) — asignación automática de `match_type` al sincronizar (usado en `sync_today_matches.py`).
> - Nota: `packages/ml` referencia `HOME_ADVANTAGE_BY_LEAGUE`, `CARDS_LINE_BY_LEAGUE`, `CORNERS_LEAGUE_AVG` y `KNOWN_LEAGUE_BASELINES` por estas mismas claves; cualquier clave no configurada cae al valor `"default"`.

### 1.3 Resolución de clave ML en el orquestador

```python
def _get_league_key(self, league) -> str:
    return LEAGUE_EXTERNAL_ID_TO_KEY.get(league.external_id, "default")
```

Fix aplicado (ver doc 04): antes solo 3 ligas (39/140/239) mapeaban; ahora las 26 mapean y ninguna cae en `"default"`.

---

## 2. Motor Matemático & EV (`betmind_ml.ev.ev_calculator`)

### 2.1 Fórmulas centrales (documentadas en el módulo)

```
EV = (P_real * (cuota - 1)) - (1 - P_real)      [stake = 1 unidad]
Edge = P_real - P_implicita = P_real - (1 / cuota)
```

- **Umbrales (`config.py`):** `EV_POSITIVE_THRESHOLD = 0.05` (5% de margen conservador) y `EV_AVOID_THRESHOLD = -0.10`.
- **Overround del bookmaker:** las cuotas incluyen margen típico 5–8% (ej. cuotas 2.0/3.5/3.5 → P_implicita_total = 1.072 → overround 7.2%). El modelo trabaja con probabilidades **reales que suman 1.0**.

### 2.2 Desmarquinización (fair probability) — `_compute_fair_probability()`

Elimina el margen del bookmaker para obtener una probabilidad implícita justa comparable con la del modelo:

```python
overround = (1/odds_a) + (1/odds_b)        # sumando los lados opuestos
fair_prob = (1/odds) / overround
```

- Grupo **1X2**: si están las 3 cuotas (`1X2_HOME`, `1X2_DRAW`, `1X2_AWAY`): `overround = 1/home + 1/draw + 1/away`, `fair = (1/odds)/overround`.
- **Over/Under**: busca el opuesto intercambiando el prefijo `OVER_` ↔ `UNDER_`.
- **BTTS**: `BTTS_YES` ↔ `BTTS_NO`.
- Si no hay lado opuesto → probabilidad implícita cruda `1/odds`.

### 2.3 Funciones públicas de `ev_calculator.py`

| Función | Comportamiento |
|---|---|
| `calculate_ev_metrics(probability, bookmaker_odds, odds_dict, market_name)` | Retorna `(implied_probability, edge*100, expected_value)` redondeados (4/2/4); `ValueError` si `bookmaker_odds <= 1.0`. Centraliza el cálculo usado por orquestador y ruta de tickets |
| `enrich_market_with_ev(market, bookmaker_odds, fair_implied_prob=None)` | Setea `bookmaker_odds`, `implied_probability`, `edge`, `expected_value`, `verdict` en el `MarketProbability`. Verdicts: `POSITIVE_EV` si `EV >= 0.05`, `AVOID` si `EV <= -0.10`, `NO_VALUE` en el medio |
| `enrich_markets_batch(markets, odds_dict)` | Enriquece todos los mercados; sin cuota → deja el mercado intacto (probabilidad sin EV) |
| `get_top_ev_opportunities(markets, min_ev=0.0, top_n=3)` | Top N mercados con `expected_value >= min_ev`, ordenados desc — "Top 3 apuestas de valor" |

### 2.4 Clasificación `NO_ODDS_AVAILABLE` (cuotas faltantes)

- **API (`schemas/prediction.py`):** `Verdict` enum: `POSITIVE_VALUE`, `NO_VALUE`, `INSUFFICIENT_DATA`, **`NO_ODDS_AVAILABLE`**.
- En `_build_response()` del orquestador, cada mercado sin `bookmaker_odds` se serializa como:
  ```python
  EVAnalysis(market, our_probability, bookmaker_implied_probability=None,
             bookmaker_odds=None, edge_percentage=None, expected_value=None,
             kelly_stake=None, verdict=Verdict.NO_ODDS_AVAILABLE)
  ```
- **Ticket builder (`engine/ticket_builder.py`):** un mercado sin cuotas reales (`bm_odds <= 1.0` o `implied is None` o `ev is None`) **no es candidato a ticket** — nunca se sintetizan cuotas.
- **Ruta de tickets (`routes/v1/tickets.py`):** `_stored_market_rows()` recalcula EV con `calculate_ev_metrics` solo si hay cuota real; si no: `verdict = "NO_ODDS_AVAILABLE"`. `total_ev_opportunities` solo cuenta EV numérico real (`expected_value > 0.05`).
- **Verdicts del pipeline ML (`packages/ml/betmind_ml/schemas/prediction_output.py`):** `PredictionVerdict`: `POSITIVE_EV`, `NO_VALUE`, `AVOID` (EV negativo marcado), `INSUFFICIENT` (datos insuficientes).

### 2.5 Criterio de Kelly (Quarter-Kelly) — `apps/api/engine/kelly.py`

```python
f* = (p * b - q) / b        # Kelly completo; b = odds - 1, q = 1 - p
stake = max(0.0, 0.25 * f*) # Quarter-Kelly (25%)
```

- `calculate_quarter_kelly(p_real, odds)` → fracción 0–1; 0.0 si no hay EV+. Usada por leg (`kelly_stake` en `TicketLegSchema`, 0–1) y por el orquestador en `_build_response()`.
- `calculate_kelly_percentage()` y `get_staking_suggestion()` generan la sugerencia de stake legible.

---

## 3. Distribución de Poisson & Calibración

### 3.1 Cálculo de lambdas (xG) — `models/poisson_engine.py`

```
λ_home = attack_home × defense_away × league_avg × home_advantage × form_mult_home × h2h_adj_home
λ_away = attack_away × defense_home × league_avg × form_mult_away × h2h_adj_away
```

- **Índices relativos** (`features/strength_calculator.py`):
  - `attack_index = (goles_marcados_equipo / partidos) / (goles_totales_liga / partidos_liga / 2)`
  - `defense_index = (goles_totales_liga / partidos_liga / 2) / (goles_recibidos_equipo / partidos)`
- **Ajuste de forma:** `form_points` (0–15) → multiplicador `1 + FORM_WEIGHT × (normalized − 0.5)` con `FORM_WEIGHT = 0.25` → rango `0.875–1.125`.
- **Ajuste H2H:** máximo ±5% (`h2h_win_rate − 0.5) × 0.10`), solo si `h2h_matches_available >= 3`.
- **Clamp:** `[0.1, 6.0]` (lambdas fuera de rango = señal de datos corruptos).
- **Validación por liga:** `validate_lambda()` clampea contra `KNOWN_LEAGUE_BASELINES` (rangos `lambda_range_home`/`lambda_range_away` por liga).
- **Ventaja de local por liga** (`HOME_ADVANTAGE_BY_LEAGUE`): `premier_league=1.20`, `laliga=1.22`, `serie_a=1.18`, `bundesliga=1.25`, `liga_betplay=1.30`, `default=1.20` (referencia Dixon-Coles 1997).

### 3.2 Blending bayesiano y safety floor (`pipeline/prediction_pipeline.py`)

- `MIN_MATCHES_FOR_STRENGTH = 5`: si un equipo tiene < 5 partidos, su λ se funde con el prior de liga:
  ```python
  weight = home_matches_count / MIN_MATCHES_FOR_STRENGTH
  lambda_home = lambda_home * weight + league_prior * (1 - weight)
  ```
- **Safety floor** `MIN_LAMBDA = 0.15`: nunca se permite λ = 0; se usa `league_base` (default 1.35) × ventaja de local como mínimo.
- `estimate_lambdas_from_odds()` está **deprecado** (predicción tautológica: probabilidades derivadas de las mismas cuotas con las que se compara EV) — el pipeline principal retorna `INSUFFICIENT` cuando no hay datos históricos confiables.

### 3.3 Matriz de Poisson bivariada con Dixon-Coles

- `MAX_GOALS_MATRIX = 8` → matriz 9×9 (cubre > 99.9% de partidos reales).
- `P(X=i, Y=j) = pmf(i, λh) × pmf(j, λa)` con `scipy.stats.poisson`.
- **Corrección Dixon-Coles** (`rho = -0.09`) aplicada a las 4 celdas críticas:
  - `τ(0,0) = 1 − (λh·λa·ρ)`, `τ(1,0) = 1 + (λa·ρ)`, `τ(0,1) = 1 + (λh·ρ)`, `τ(1,1) = 1 − ρ`; resto `τ = 1.0`.
- **Renormalización** a suma exacta 1.0 y extracción del marcador más probable (`ScoreMatrix.most_likely_score`).

### 3.4 Mercados calculados (`models/market_calculator.py`, 60+ mercados)

Desde la matriz: `1X2_HOME/DRAW/AWAY`, `DOUBLE_1X/X2/12`, `DNB_HOME/AWAY`, `OVER/UNDER_0_5/1_5/2_5/3_5`, `BTTS_YES/NO`, `HOME/AWAY_OVER_0_5/1_5`.

Modelos auxiliares con líneas por liga:
- **Córneres** — Binomial Negativa (`K_DISPERSION = 1.3`), líneas `6.5–12.5`, promedio por liga `CORNERS_LEAGUE_AVG` (ej. `premier_league=10.4`, `liga_betplay=8.8`, `default=9.5`).
- **Tarjetas** — Poisson con línea base por liga `CARDS_LINE_BY_LEAGUE` (Sudamérica 4.5–5.5, Europa 3.5–4.0) modulada por `referee_strictness` y `cards_mti`; líneas `3.5–7.5`.
- **Remates a puerta** — Poisson, `SHOTS_OT_LEAGUE_AVG` (ej. `premier_league=9.2`, `default=8.0`); líneas `6.5–10.5`.

### 3.5 Calibración empírica por liga (`calibration/league_calibrator.py`)

- `KNOWN_LEAGUE_BASELINES` — 13 ligas con: `avg_goals_per_team`, `lambda_range_home`, `lambda_range_away`, `home_win_rate_historical`. Ejemplos: `premier_league` (1.35; home 0.8–3.0; away 0.5–2.5; 46%), `laliga` (1.30; 0.7–2.8; 0.5–2.3; 47%), `liga_betplay` (1.15; 0.6–2.4; 0.4–2.0; 44%), `mls` (1.48; 0.8–3.1; 0.6–2.6; 47%).
- `calibrate_league(league_key, all_matches, min_matches_required=20)` → `LeagueCalibrationReport`:
  - Advierte si `avg_goals_per_team` empírico es **> 1.5×** o **< 0.5×** el baseline.
  - Reporta `home_win_rate` empírica y estados `CALIBRADO` / `REQUIERE REVISION`.
- `validate_lambda(lambda_value, league_key, team_role)` → clampeo a rango histórico + warnings (usado en `poisson_engine.calculate_lambdas`).

### 3.6 Tipos de partido: `LEAGUE` vs `KNOCKOUT_CUP`

- Columna `matches.match_type` (`String(20)`, default `LEAGUE`, indexada — migración 011).
- Asignación automática en sincronización vía `KNOCKOUT_CUP_LEAGUE_IDS` (`sync_today_matches.py`) y backfill SQL en migración 011.
- El frontend la consume como `Match.matchType` (`mapBackendMatch` con `raw.match_type ?? 'LEAGUE'`) y muestra el badge **COPA** (`match-card.tsx` `MatchTypeBadge`) para eliminación directa.
- Los mercados y lambdas **solo consideran tiempo reglamentario (90 min)**: `regulation_time_only=True` en toda la ingesta, forma (`get_recent_form`) y H2H filtran por `status=FINISHED` + `regulation_time_only`.

### 3.7 Score de confianza dinámico

`_calculate_confidence()` → 0–100 ponderado por `CONFIDENCE_WEIGHTS`:

| Peso | Factor | Regla |
|---|---|---|
| 0.35 | `strength_reliability` | 100 si ambos ≥ 5 partidos; 50–80 si suma ≥ 5; 35 si odds-based; 30 si ambos sin datos |
| 0.25 | `form_data_completeness` | `(form_matches_used_h + form_matches_used_a) / (2 × 5)` |
| 0.20 | `h2h_available` | `min((n_h2h / 4) × 100, 100)` |
| 0.20 | `season_maturity` | `min((n_partidos_liga / 60) × 100, 100)` |

- Flags de advertencia en `confidence_flags` (muestra limitada, forma incompleta < 0.6, sin H2H, temporada joven < 20 partidos).
- `_compute_risk_level()` → `LOW` (confianza ≥ 75, o ≥ 55 con mejor prob ≥ 0.70), `MEDIUM` (≥ 55), `HIGH` (< 55). `NARRATIVE` bonus: hasta +15 puntos en el cerebro táctico; `data_completeness_score` (+0.35 árbitro confiable, +0.35 córneres, +0.30 H2H ≥ 3).

### 3.8 Modos de boleto (`engine/ticket_builder.py`)

| Parámetro | EDGE | VALUE | BOLD |
|---|---|---|---|
| `min_ev` | 0.005 | 0.005 | 0.005 |
| `max_selections` | 2 | 3 | 4 |
| `min_our_probability` | 0.40 | 0.30 | 0.22 |
| `target_odds_min/max` | 1.50–3.50 | 2.50–12.00 | 8.00–30.00 |
| `max_individual_odds` | 2.10 | 4.00 | 8.00 |
| `allowed_markets` | 1X2, O1.5/O2.5, BTTS_YES, CORNERS_OVER_7_5, CARDS_OVER_3_5/4_5, SHOTS_OT_OVER_6_5 | 1X2, O/U goles, BTTS, CORNERS 8.5/9.5/UNDER_10_5, CARDS_OVER_4_5/UNDER_5_5, SHOTS 7.5/8.5 | None (todos) |
| `require_correlation` | — | — | False |
| staking sugerido | 1–2% bankroll | 0.5–1% bankroll | 0.25–0.5% bankroll |

Reglas de construcción:
- `FORBIDDEN_COMBINATIONS` (8 pares con correlación negativa, ej. `UNDER_2_5 + BTTS_YES`, `1X2_DRAW + BTTS_NO`).
- `POSITIVE_CORRELATIONS` (7 pares con peso, ej. `BTTS_YES+OVER_2_5 → 0.81`, `1X2_HOME+OVER_1_5 → 0.72`) → bonus de confianza `corr_bonus × 20`.
- `MAX_DRAWS_PER_TICKET = 1` (máximo 1 empate por boleto); un partido no puede repetirse por fixture (`home|away`) ni por `match_id`.
- Filtro **anti-cáscara** (`_passes_anti_cascara_filter`): en ligas de alta varianza (`HIGH_VARIANCE_LEAGUES`: betplay, profesional_arg, liga_mx, primera_chile, liga_pro_ecu, liga_1_peru, serie_a_bra) se rechazan selecciones con cuota < 1.25 (favoritos sin valor).
- `1X2_DRAW` exige cuota ≥ 2.10; EV aceptado en `[0.005, 0.35]`.
- Confianza del boleto: `min(avg_ev × 400 + corr_bonus × 20 + n_legs × 5, 95)`.
- Recorte de piernas si `combined_odds > target_max` (ordenadas por odds asc) y expansión si `combined < target_min`.
