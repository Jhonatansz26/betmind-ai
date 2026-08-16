# Arquitectura Lógica del Motor de Pronósticos BetMind

**Documento de Arquitectura Lógica — Auditoría de Lógica Predictiva**

- **Versión del documento:** 1.0
- **Versión del modelo:** `poisson_v1.0` (`packages/ml/betmind_ml/config.py:7`)
- **Fecha:** 2026-08-14
- **Ámbito:** Metodología integral de pronósticos: filosofía matemática, selección de mercados, perfilamiento de ligas, filtros de riesgo y gestión de banca.
- **Base del documento:** Revisión exhaustiva del código productivo (`packages/`, `apps/api/`), con referencias `archivo:línea` verificables para auditoría externa.

---

## 1. Filosofía Matemática y Gestión de Banca

### 1.1 La regla inquebrantable: Valor Esperado Positivo (+EV)

Toda selección emitida por el sistema debe superar el umbral de EV positivo. No existe apuesta por "intuición", por jerarquía de equipos ni por favoritismo de mercado: **la única moneda de entrada es el EV**.

La definición operativa (`packages/ml/betmind_ml/ev/ev_calculator.py:32-53`):

```
edge = p_modelo − p_implícita_desvigada
EV   = p_modelo × cuota_bookmaker − 1.0
```

Veredictos (`ev_calculator.py:157-162`, umbrales en `betmind_ml/config.py:107-110`):

| Veredicto | Condición | Decisión |
|---|---|---|
| `POSITIVE_EV` | `EV ≥ +0.03` (3%) | Elegible para boleto |
| `NO_VALUE` | `−0.10 < EV < +0.03` | Descartado |
| `AVOID` | `EV ≤ −0.10` | Descartado con señal de riesgo |
| `INSUFFICIENT` | Falta la cuota de la contra-pierna | EV nunca certificado |

Reglas complementarias de rigor:

- **Cenit de escepticismo:** un EV > 0.35 se descarta como anomalía (sobreajuste o error de cuota), no se apuesta (`apps/api/engine/ticket_builder.py:416`).
- **Piso de cuota:** EV positivo con cuota < 1.20 se degrada a `NO_VALUE` — un EV aparente a cuota chica no compensa el costo de varianza (`apps/api/orchestrators/prediction_orchestrator.py:801-805`).
- **Anti-cáscara de guineo:** en ligas de alta varianza, cuotas < 1.25 se rechazan de plano (ver §5.1 y §4.6).
- **Certificación estricta:** la probabilidad justa se obtiene por **desvigado** (eliminación del margen). Para 1X2 se usan las tres piernas; para O/U, BTTS, córners, tarjetas y remates se exige la contra-pierna (`1/odds_A + 1/odds_B`); sin contra-pierna no hay EV (`ev_calculator.py:56-112,139-146`).

### 1.2 Directriz simple vs. combinada: donde la varianza decide

**Política declarada:** las oportunidades de +EV puro y alta volatilidad se procesan obligatoriamente como **apuestas simples (singles)**, porque en una combinada su ventaja marginal se multiplica contra el producto de las varianzas y destruye el apalancamiento. Las **combinadas (parlays)** se limitan a eventos de alta probabilidad implícita y cuotas controladas para aplanar la varianza matemática del boleto.

**Implementación actual (verificar §8, brechas):**

- El generador automático de boletos construye combinadas de 2-4 piernas según el modo; una pierna única solo se genera si el usuario solicita explícitamente `requested_count=1` (`ticket_builder.py:487-488`).
- **No existe aún un ruteo automático simple vs. parlay por volatilidad del EV.** La tabla §1.3 muestra los controles de cuota que materializan el "aplanamiento de varianza".

### 1.3 Control de varianza en combinadas (modos de boleto)

Configuración por modo (`apps/api/engine/ticket_builder.py:12-61`):

| Parámetro | EDGE | VALUE | BOLD |
|---|---|---|---|
| Piernas máx. | 2 | 3 | 4 |
| Exposición máx. del boleto | 2.0% | 1.5% | 1.0% |
| Prob. mínima del modelo por pierna | 0.40 | 0.30 | 0.22 |
| Cuota combinada objetivo | 1.50 – 3.50 | 2.50 – 12.00 | 8.00 – 30.00 |
| Cuota individual máx. | 2.10 | 4.00 | 8.00 |
| Mercados permitidos | Restringidos (9) | Ampliados (13) | Todos |
| Correlación requerida | Sí (default) | Sí (default) | No |

Principios de aplanamiento de varianza:

1. **Techo de cuota individual** — ninguna pierna puede ser un "bono" de bajo precio ni un "milagro": el rango de probabilidad implícita está acotado.
2. **Techo de cuota combinada** — si la combinada excede el máximo, se descartan piernas desde la cuota más baja hacia arriba hasta volver al rango; si no alcanza el mínimo, se agregan piernas (`ticket_builder.py:492-521`). Un boleto fuera del rango nunca se emite.
3. **Máximo 1 empate por boleto** (`MAX_DRAWS_PER_TICKET = 1`, `ticket_builder.py:86`).
4. **Una sola selección por partido** por boleto (`ticket_builder.py:471-473`).
5. **Combinaciones prohibidas por correlación negativa** (§5.2).

### 1.4 Staking: Quarter-Kelly con umbral operable

El único motor de staking es **Quarter-Kelly** (`apps/api/engine/kelly.py`):

```
f*     = (p × odds − 1) / (odds − 1)     # Kelly completo
stake  = 0.25 × f*                        # Quarter-Kelly (25%)
stake  = 0.0  si  stake < MIN_KELLY_STAKE # 0.25% — umbral, no piso
stake  = min(MAX_KELLY_STAKE, stake)      # tope 2.0% del bankroll
```

- **`MIN_KELLY_STAKE = 0.0025`** (0.25%): si el edge calculado no alcanza para una apuesta mínima operable, la recomendación es **0.0 — no apostar** (`kelly.py:70-73`). No se inflan stakes pequeños.
- **`MAX_KELLY_STAKE = 0.02`** (2.0%): tope institucional, nunca más del 2% del bankroll en una sola apuesta (`kelly.py:24-25,75`).
- El Quarter-Kelly reduce la varianza y el riesgo de ruina frente al Kelly completo.
- Banda de stake por modo: EDGE 1-2%, VALUE 0.5-1%, BOLD 0.25-0.5% (`ticket_builder.py:29,47,59`).
- Kelly combinado: suma de los Kelly positivos de las piernas, con tope en la exposición máxima del modo (`ticket_builder.py:306-317`).

### 1.5 Probabilidad conjunta real del parlay (anti-sobreprecio)

El EV de una combinada **nunca** se calcula como promedio ingenuo de EV por pierna. Se reconstruye la matriz de goles conjunta desde los lambdas persistidos y se evalúa cada pierna del mismo partido contra esa matriz conjunta: solo las celdas que satisfacen **todas** las condiciones simultáneamente cuentan (`ticket_builder.py:176-236`). Piernas de partidos distintos o de mercados no matriciales (córners, tarjetas, remates) se combinan como independientes. El EV real del boleto:

```
real_ev = P_conjunta × cuota_combinada − 1.0
```

Además, los patrones de bet-builder incorporan correlación Pearson entre mercados: `P(A∩B) = P(A)·P(B) + ρ·√(P(A)(1−P(A))·P(B)(1−P(B)))` con `ρ = 0.25` (`packages/ml/betmind_ml/bet_builder_patterns.py:58-79`), y coeficientes fijos para combinaciones conocidas (p. ej. BTTS_YES + OVER_2_5 → 0.81, `ticket_builder.py:75-83`).

---

## 2. Modelo Subyacente: Motor Bivariado de Poisson con Dixon-Coles

Todas las probabilidades de mercados de goles derivan de **una única distribución**: la matriz de marcadores del partido.

### 2.1 Índices de fuerza (estilo Dixon-Robinson con decaimiento temporal)

`packages/ml/betmind_ml/features/strength_calculator.py`:

- **Ventana:** últimos 12 partidos (`STRENGTH_WINDOW`, `config.py:62`).
- **Decaimiento exponencial:** peso = `0.85^k` (partido más reciente = 1.0) (`strength_calculator.py:26-44`).
- **Contracción bayesiana hacia el prior de liga** con pseudo-conteo `k=5`: `promedio = (n/(n+5))·promedio_ponderado + (5/(n+5))·promedio_liga` (`strength_calculator.py:119-127`).
- **Índices:** `attack_index = goles_anotados_ponderados / promedio_liga`; `defense_index = promedio_liga / goles_recibidos_ponderados` (`strength_calculator.py:130-131`).
- **Forma:** últimos 5 partidos (puntos + diferencia de gol) (`strength_calculator.py:159-188`).
- **H2H:** últimos 6 cruces con prior neutral 0.5 (`strength_calculator.py:191-227`).
- **Dato:** la fuerza se calcula con goles reales de 90 minutos; el xG se ingesta y persiste, pero **no** alimenta los índices (documentado en §8).

### 2.2 Cálculo de lambdas (goles esperados por equipo)

`packages/ml/betmind_ml/models/poisson_engine.py:34-100`:

```
λ_local  = (attack_local / defense_visitante) × avg_goles_liga × ventaja_local × forma_mult × h2h_adj
λ_visit  = (attack_visitante / defense_local) × avg_goles_liga × forma_mult × h2h_adj
```

- Clamp: `λ ∈ [0.1, 6.0]` (`poisson_engine.py:83-84`) y validación contra rangos calibrados por liga (`league_calibrator.py:186-215`).
- `forma_mult = 1 + 0.25 × (puntos_forma/15 − 0.5)` (`poisson_engine.py:314-323`).
- `h2h_adj = ±5%` máximo según win-rate histórico (`poisson_engine.py:326-341`).
- **Ventaja local** por liga (§4.2), anulada en sede neutral (`poisson_engine.py:51-54`).
- **Blend bayesiano:** con menos de 5 partidos, λ se mezcla hacia el prior de liga; piso de seguridad `MIN_LAMBDA = 0.15` (`prediction_pipeline.py:105-125`).

### 2.3 Matriz de marcador y corrección Dixon-Coles

- Matriz 0-8 goles (`MAX_GOALS_MATRIX = 8`, cubre >99.9% de partidos).
- Producto de PMF de Poisson bivariado + **factor τ de Dixon-Coles** con `ρ = −0.09` aplicado a las celdas 0-0, 1-0, 0-1, 1-1, y renormalización (`poisson_engine.py:196-309`). La correlación negativa modela que 0-0 y 1-1 son más probables de lo que el Poisson independiente sugiere.

---

## 3. Lógica y Triggers por Mercado (La Toma de Decisiones)

Cada familia de mercado tiene una distribución estadística, un conjunto de inputs y un contexto táctico que la detona. Tabla maestra:

| Mercado | Claves emitidas | Distribución | Inputs principales |
|---|---|---|---|
| Resultado | `1X2_HOME/DRAW/AWAY` | Matriz Poisson (sumas) | λ_local, λ_visit |
| Doble oportunidad | `DOUBLE_1X/X2/12` | Sumas aditivas de 1X2 | Ídem |
| DNB | `DNB_HOME/AWAY` | 1X2 renormalizado sin empate | Ídem |
| Goles O/U | `OVER/UNDER_0_5…3_5` | Sumas de matriz (i+j) | Matriz |
| BTTS | `BTTS_YES/NO` | Sumas de matriz (i≥1 ∧ j≥1) | Matriz |
| Totales por equipo | `HOME/AWAY_OVER_0_5/1_5` | Supervivencia de Poisson `1−e^(−λ)` | λ del equipo |
| Córners | `CORNERS_OVER/UNDER_6_5…12_5` | Binomial Negativa (k=1.3) | Prom. córners for/against, ventaja local, avg liga |
| Tarjetas | `CARDS_OVER/UNDER_3_5…7_5` | Poisson CDF | Prom. amarillas, rigor arbitral, MTI, línea liga |
| Remates a puerta | `SHOTS_OT_OVER/UNDER_6_5…10_5` | Poisson CDF | Prom. SOT for/against, avg liga |
| Marcador exacto | `most_likely_score` | Celda máx. de la matriz | Matriz |
| Player props | `shots_on_target`, `shots_total`, `yellow_card` | per-90 × min × factor oponente, Poisson | Perfil jugador (standalone) |

### 3.1 Mercados de Asedio (Córners y Remates a Puerta)

**Córners** (`market_calculator.py:179-217`, `apps/api/engine/corners_model.py:27-118`):

- **Distribución: Binomial Negativa** con dispersión `k = 1.3` (`K_DISPERSION`, `market_calculator.py:34`). El exceso de dispersión modela la realidad: los córners tienen cola pesada y no siguen Poisson (`p = 1/k`, `r = μ/(k−1)`, `P(under) = nbinom.cdf(floor(line))`).
- **Esperanza μ:** promedios reales del equipo (córners a favor y en contra, con decaimiento 0.85) ponderados por el factor de ventaja local; si un equipo no tiene historial, cae al promedio de liga calibrado (`CORNERS_LEAGUE_AVG`, §4.2) — fallback legítimo, no el único camino.
- **Líneas emitidas:** 6.5 a 12.5.

**Remates a puerta** (`market_calculator.py:251-285`):

- **Distribución: Poisson CDF** con μ de promedios SOT for/against por equipo; fallback `SHOTS_OT_LEAGUE_AVG`.
- **Líneas emitidas:** 6.5 a 10.5.

**Triggers tácticos que favorecen estos mercados:**

1. **Posesión dominante y juego por bandas:** equipos que acumulan posesión y centros exigen córners altos; el modelo lo captura vía promedios reales del equipo (los córners for/against del rival son el proxy del bloque bajo).
2. **Bloques bajos rivales:** un local dominante frente a un rival ultradefensivo infla la esperanza de córners y remates a puerta del local (la asimetría for/against lo refleja).
3. **Localía dominante:** el factor de ventaja local pondera la esperanza de córners del local (`market_calculator.py:185-197`).
4. **Fase de asedio = consecuencia ofensiva:** el motor no "adivina" el asedio: lo infiere de la acumulación de remates/córners históricos del atacante y de la concesión del defensor.

### 3.2 Mercados de Fricción (Tarjetas)

`market_calculator.py:220-248`, `apps/api/engine/match_tension.py`, `prediction_orchestrator.py:317-336`:

```
μ_tarjetas = (prom_amarillas_local + prom_amarillas_visitante) × rigor_arbitral × MTI
P(under)   = poisson.cdf(floor(línea), μ)
```

- **Rigor arbitral local:** `strictness = prom_amarillas_árbitro / línea_tarjetas_liga`, clampeado a [0.5, 1.5], solo si el árbitro tiene ≥ 5 partidos de perfil (`prediction_orchestrator.py:317-336`).
- **Índice de Tensión de Partido (MTI):** partido regular 1.00, choque de clasificación 1.15, derby 1.35, lucha por el descenso 1.35 (`match_tension.py:31-36`). La **urgencia de puntos** (clasificación/descenso) y la **rivalidad** escalan la esperanza de tarjetas.
- **Línea base por liga** (`CARDS_LINE_BY_LEAGUE`, §4.2): Sudamérica 4.5-5.5 (más física), Europa 3.5-4.0 (más táctica).
- **Historial de juego trabado:** promedios de amarillas for/against de ambos equipos (decay 0.85).
- **Líneas emitidas:** 3.5 a 7.5.

**Triggers tácticos:** rigores arbitrales estrictos, derbis, contextos de descenso/clasificación, equipos con alta media de amarillas, y ligas de perfil físico (BetPlay, Argentina, Brasil).

### 3.3 Mercados de Goles (Over/Under y Ambos Marcan)

Derivados de la matriz conjunta: `P(over) = Σ celdas donde i+j > línea`; `P(BTTS_YES) = Σ celdas donde i≥1 ∧ j≥1` (`market_calculator.py:97-137`).

- **La alta (Over 2.5 / BTTS):** se recomienda cuando el ADN ofensivo de la liga o de los equipos eleva los lambdas — ligas con `avg_goals` altos (MLS 1.48, Premier 1.35, Liga MX 1.32, Eredivisie), defensas adelantadas (defense_index bajo del rival), forma goleadora (form_mult > 1) y contextos abiertos.
- **La baja (Under 2.5 / BTTS NO):** se blinda en canchas difíciles (efecto localía fuerte), esquemas ultradefensivos (defense_index alto del rival), ligas de bajo promedio (Argentina 1.12, BetPlay 1.15), fases de partido con tiempos efectivos bajos capturados por promedios históricos y bloques bajos.
- **Totales por equipo** (`HOME/AWAY_OVER_0_5/1_5`): supervivencia de Poisson directa del λ — el "al menos un gol" del favorito o del equipo en racha.
- **Combinaciones prohibidas** para proteger coherencia: UNDER_2_5 + BTTS_YES (contradictorio), OVER_3_5 + CARDS_UNDER_3_5/4_5, etc. (§5.2).

### 3.4 Mercados de Resultado (1X2 / Doble Oportunidad / DNB)

- **1X2 directo:** se justifica cuando hay **desnivel de plantilla y jerarquía** — diferencias grandes de attack/defense index, forma y H2H que hacen que una celda del marcador (o un lado de la matriz) concentre probabilidad. Se usa la suma de celdas i>j / i=j / i<j normalizada.
- **Doble oportunidad:** cuando la jerarquía favorece un lado pero la varianza del empate es alta; es la suma aditiva de dos resultados — el modelo la elige en configuraciones donde el 1X2 directo no alcanza el umbral de confianza.
- **DNB:** cuando el empate es el resultado más probable pero no apostable; renormaliza sin empate.
- **Reglas duras:** cuota de empate < 2.10 se bloquea en ingesta (sospecha de Doble Oportunidad/DNB disfrazado) (`odds_service.py:501-508`); máximo 1 empate por boleto; `1X2_DRAW + BTTS_NO` prohibido (correlación negativa conocida).

### 3.5 Mercados excluidos del alcance

- **Handicap Asiático:** bloqueado en ingesta de cuotas y fuera del catálogo de predicción (`odds_service.py:483,493`; solo existe el enum `ASIAN_HANDICAP`).
- **Player props:** el motor de proyección existe (`apps/api/engine/player_props_model.py`, `per-90 × minutos × factor oponente` con líneas Poisson, gates de minutos ≥ 60 y titular confirmado), pero **no está conectado al pipeline principal de predicción** — el pipeline no emite estos mercados aún (§8).
- **Monte Carlo:** no existe simulación Monte Carlo para mercados; todo deriva de la matriz de Poisson y las CDF paramétricas (§8).

---

## 4. Perfilamiento Geográfico y Táctico (Análisis Global)

### 4.1 Catálogo de ligas

- **Alcance operativo (`ACTIVE_LEAGUE_IDS`, `betmind_ml/config.py:12-25`) — 12 ligas:** Premier League (39), LaLiga (140), UCL (2), UEL (3), Libertadores (13), Sudamericana (11), Brasileirão (71), Liga Profesional Argentina (128), Liga BetPlay (239), Liga MX (262), MLS (253), Eredivisie (88). Esta lista es la única puerta de entrada para fixtures, odds, estadísticas y CLV.
- **Catálogo producto (`FEATURED_LEAGUES`, `apps/api/config.py:204-363`) — 25+:** agrega Championship, LaLiga Hypermotion, Bundesliga, Serie A, Ligue 1, UECL, copas (Copa Colombia, Copa de la Liga Argentina, Copa do Brasil, US Open Cup) y ligas sudamericanas secundarias (Ecuador, Chile, Perú), más nórdicas vía ESPN (Allsvenskan, Superliga Danesa, Superliga Suiza).
- **Clasificación por región:** Big 5 europeo (PL, LaLiga, Bundesliga, Serie A, Ligue 1), Copas UEFA, Sudamérica, Otras (`apps/api/routes/v1/leagues.py:17-29`).

### 4.2 Parámetros calibrados por liga (el algoritmo NO trata las ligas por igual)

**Ventaja de local** (`betmind_ml/config.py:81-88`):

| Liga | Factor | Liga | Factor |
|---|---|---|---|
| Bundesliga | 1.25 | LaLiga | 1.22 |
| Premier League | 1.20 | Serie A | 1.18 |
| Liga BetPlay | **1.30** | Default | 1.20 |

**Línea base de tarjetas** (`config.py:118-147`):

| Región | Liga | Línea |
|---|---|---|
| Sudamérica (física) | BetPlay, Liga Prof. Argentina | 5.5 |
| | Brasileirão, Chile, Ecuador, Perú | 5.0 |
| | Liga MX | 4.5 |
| Europa (táctica) | Premier, Bundesliga | 3.5 |
| | LaLiga, Serie A, UCL/UEL/Libertadores/Sudamericana | 4.0 |
| Europa del Norte | Allsvenskan, Dinamarca, Suiza | 3.5 |

**Promedio de córners por liga** (`market_calculator.py:36-47`): Premier 10.4, Bundesliga 10.1, Serie A 9.6, LaLiga 9.2, MLS 9.1, Argentina 9.0, BetPlay 8.8, Perú 8.6; copas UEFA/CONMEBOL 9.5 (fallback).

**Remates a puerta por liga** (`market_calculator.py:52-59`): Bundesliga 9.6, Premier 9.2, LaLiga 8.4, MLS 8.2, Serie A 8.0, Brasil 7.8, Liga MX 7.5, BetPlay 7.2, Argentina 7.0, Perú 6.8.

**Baselines de goles y rangos de λ** (`league_calibrator.py:25-104`):

| Liga | Goles/equipo/partido | Rango λ local | Rango λ visitante | Win-rate local hist. |
|---|---|---|---|---|
| MLS | 1.48 | 0.8–3.1 | 0.6–2.6 | 0.47 |
| Premier | 1.35 | 0.8–3.0 | 0.5–2.5 | 0.46 |
| Liga MX | 1.32 | 0.7–2.7 | 0.5–2.4 | 0.46 |
| LaLiga | 1.30 | 0.7–2.8 | 0.5–2.3 | 0.47 |
| Brasileirão | 1.25 | 0.7–2.6 | 0.5–2.2 | 0.45 |
| BetPlay | 1.15 | 0.6–2.4 | 0.4–2.0 | 0.44 |
| Argentina | 1.12 | 0.6–2.3 | 0.4–1.9 | 0.43 |

**Ligas de alta varianza** (`ticket_builder.py:6-10`): BetPlay, Argentina, Liga MX, Chile, Ecuador, Perú, Brasileirão → activan el filtro anti-cáscara (§5.1).

### 4.3 La Élite Europea (Premier League, La Liga, Champions, Europa League)

- **Estabilidad estadística alta:** ventanas de 12 partidos son representativas; los índices de fuerza convergen rápido (menos ruido por equipo); el modelo confía más en strength y menos en forma.
- **Rango de λ moderado y controlado** (0.5-3.0); home advantage moderado (1.18-1.25).
- **Mercados de goles y resultado dominan:** las cuotas de Over/BTTS y 1X2 son las más calibradas; la fricción es baja (líneas de tarjetas 3.5-4.0) — las tarjetas se eligen solo con rigor arbitral alto o derbis.
- **Copas UEFA (UCL/UEL/UECL):** tratadas como contexto de copa (`match_type = KNOCKOUT_CUP`); los equipos de élite minimizan rotaciones en fases eliminatorias, pero el modelo aplica los mismos baselines (córners/remates 9.5, tarjetas 4.0) con fallback explícito hasta tener muestra propia.

### 4.4 Las Ligas de América (Libertadores, Sudamericana, MLS, Liga MX)

- **Libertadores/Sudamericana:** contexto de copa CONMEBOL; baselines de goles intermedios, tarjetas 4.0 (más disciplinadas que la liga local — arbitraje CONMEBOL), córners/remates 9.5 (fallback).
- **MLS:** el perfil más ofensivo del catálogo (1.48 goles/equipo, λ local hasta 3.1). Alta de goles y asedio; localía relevante (46-47% win-rate local). Mercados de goles y córners (9.1) favorecidos.
- **Liga MX:** ofensiva (1.32) con más fricción (tarjetas 4.5); media liguilla y viagejes largos se reflejan en la forma; el anti-cáscara aplica.
- **Tendencia compartida:** mayor varianza de localía y partidos más abiertos que la élite europea; el sistema evita cuotas de favorito ultra-cortas (§5.1).

### 4.5 El Rigor del Fútbol Sudamericano (Brasil, Argentina, Colombia, etc.)

- **Estilo condiciona el mercado:**
  - **Verticalidad (Brasil):** promedio de goles medio (1.25) y remates altos (7.8 SOT) — mercados de goles y asedio viables, tarjetas medias (5.0).
  - **Fricción (Argentina, Colombia):** bajo promedio de goles (1.12 / 1.15), la fricción es el "mercado natural": línea de tarjetas máxima del catálogo (5.5), BetPlay con la mayor ventaja de localía (1.30) y la menor producción de córners (8.8) — el asedio se dosifica.
- **Localía dominante:** las ligas latinoamericanas reciben el mayor boost de local (BetPlay 1.30 vs. 1.20 default) — el modelo confía más en el local en estas canchas, y el under/la fricción en canchas difíciles (altitud, viajes, clima capturados en forma/contexto).
- **Riesgo estructural:** son las ligas de **mayor varianza** (sorpresas, crisis institucionales, rotaciones por calendario apretado de copas) — por eso aplica el anti-cáscara (<1.25 rechazado) y la confianza baja cuando las muestras son cortas.

### 4.6 Otros condicionantes que afectan el pronóstico

- **Sede neutral:** anula el factor de localía (finales, copas) (`poisson_engine.py:51-54`).
- **Altitud:** `altitude_impact` se integra al contexto de partido y a la narrativa de goles (estadios a >2.600 m) (`schemas/match_context.py:60-65`).
- **Árbitro:** rigor relativo a la liga (§3.2) — solo con perfil de ≥5 partidos.
- **Fase de temporada:** la confianza pondera madurez de temporada (20%) y completitud de forma (25%) (§6).
- **Tipo de partido:** MTI (derby, descenso, clasificación) escala la fricción (§3.2); copas marcan `match_type` y neutralizan localía en finales.

---

## 5. Filtros de Riesgo y "Red Flags"

### 5.1 Filtros cuantitativos implementados (orden de aplicación en `ticket_builder.py:384-456`)

1. **EV fuera de banda** `[0.03, 0.35]` → rechazado (anomalías y edges marginales).
2. **Sin cuota real** (`odds ≤ 1.0`, sin contra-pierna, sin EV certificado) → descartado.
3. **Piso de cuota 1.20** → degradado a `NO_VALUE` (`prediction_orchestrator.py:801-805`).
4. **Anti-cáscara:** cuota < 1.25 en ligas de alta varianza → rechazado (`ticket_builder.py:293-303`).
5. **Empate < 2.10** → bloqueado en ingesta y lectura (`odds_service.py:501-508,572-599`).
6. **Mercado fuera del allowlist del modo** → descartado (`ticket_builder.py:396-397`).
7. **Cuota individual > techo del modo** (2.10/4.00/8.00) → descartado.
8. **Probabilidad del modelo < mínimo del modo** (0.40/0.30/0.22) → descartado.
9. **Combinación prohibida** (§5.2) → boleto inválido.
10. **> 1 empate por boleto** → pierna rechazada.
11. **Partido ya usado en el boleto** → rechazado (una selección por partido).
12. **Cuota combinada fuera del rango objetivo** → boleto no emitido.

### 5.2 Combinaciones prohibidas (correlación negativa)

`ticket_builder.py:63-73`: UNDER_2_5+BTTS_YES, UNDER_1_5+BTTS_YES, OVER_3_5+CARDS_UNDER_3_5/4_5, 1X2_DRAW+BTTS_NO, OVER_2_5+CARDS_UNDER_3_5/4_5, 1X2_AWAY+CORNERS_OVER_8_5/9_5. Un par de mercados con correlación negativa conocida jamás comparte boleto.

### 5.3 Suspensiones y anomalías de datos

- **Mercado suspendido** (SofaScore): la elección devuelve None y se salta; solo se aceptan mercados FT (`sofascore_odds_service.py:78-82,259-263`).
- **Cuenta suspendida (API-Football):** detección de payload de suspensión, pre-flight de estado y aborto del sync completo de cuotas (`api_football.py:137-165,322-353`, `odds_service.py:199-207`).
- **Allowlist de ligas:** solo se procesan las 12 ligas activas — cualquier competición fuera del alcance no genera predicción, odds ni CLV.
- **Fallas de proveedor:** cascada ESPN → football-data → scraper determinista → agente IA con cache resiliente (`data_ingestion.py:87-112`).

### 5.4 Red flags declarados: escenarios penalizados y brecha de implementación

Política declarada — el sistema debe penalizar/rechazar:

| Red flag | Estado en código |
|---|---|
| **Ligas filiales / equipos juveniles** (inexperiencia, inestabilidad) | **Brecha — NO implementado.** No existe detección de divisiones menores ni equipos sub-X. Mitigación indirecta: allowlist de 12 ligas de primera división. |
| **Copas nacionales / fases tempranas con rotación de plantillas** | **Brecha — NO implementado.** No hay filtro por fase temprana ni por rotación. Solo existe el flag `match_type = KNOCKOUT_CUP` y el patrón TIGHT_MATCH para derbis/copas en bet-builder. |
| **Accidentes tempranos** (roja/penal en los primeros minutos) | **Brecha — NO implementado.** No existe lógica de mercado de en vivo/early red card. Los promedios históricos capturan la tendencia, no el accidente. |

Estas tres brechas son la prioridad de la hoja de ruta (§8) y deben declararse explícitamente ante un auditor: hoy la protección del bankroll contra estos escenarios es indirecta (allowlist de ligas, ventanas de 12 partidos, filtros de cuota), no directa.

---

## 6. Confianza y Nivel de Riesgo

Score compuesto 0-100 (`prediction_pipeline.py:199-258`, pesos `config.py:155-159`):

| Componente | Peso | Qué mide |
|---|---|---|
| Fiabilidad de fuerza | 0.35 | Ambos equipos ≥ 5 partidos |
| Completitud de forma | 0.25 | Partidos de forma disponibles / 10 |
| H2H disponible | 0.20 | Cruces H2H / 4 |
| Madurez de temporada | 0.20 | Partidos de liga / 60 |

Nivel de riesgo: confianza ≥ 75 → LOW; ≥ 55 → LOW si el mejor mercado ≥ 0.70 de prob., si no MEDIUM; resto HIGH (`prediction_pipeline.py:187-196`).

Confianza de pierna en boleto: `min(100, max(0, prob×70 + EV×100))` (`ticket_builder.py:423`); confianza de boleto: `real_ev×400 + bono_correlación×20 + piernas×5`, tope 95 (`ticket_builder.py:537-539`).

---

## 7. Evaluación y Cierre del Ciclo (Backtesting / CLV)

- **Métricas de backtest:** Brier score, hit rate, ROI a stake plano, yield, curvas de calibración por cubos de probabilidad (`packages/ml/betmind_ml/backtesting/metrics.py:59-204`). Mercados evaluados: 1X2, OVER_2_5, BTTS.
- **Evaluación de pronósticos:** job de outcomes con resolución WON/LOST + Brier por mercado (`apps/api/jobs/evaluate_predictions.py`, `engine/outcome_resolver.py`).
- **CLV (Closing Line Value):** `CLV = (cuota_apertura/cuota_cierre) − 1` (`apps/api/jobs/clv_tracker.py:85-89`), solo para las 12 ligas activas. Si el modelo no supera sistemáticamente la línea de cierre, el "edge" es ruido — criterio de parada.
- **Kelly y backtest:** el ROI plano con `EV ≥ 0.03` mide la calidad del umbral sin la distorsión del tamaño de stake.

---

## 8. Estado de Implementación vs. Política Declarada (para auditoría)

| Política declarada | Estado | Referencia |
|---|---|---|
| +EV como única moneda de entrada, umbral 3% | Implementado | `ev_calculator.py`, `config.py:107` |
| EV > 0.35 descartado como anomalía | Implementado | `ticket_builder.py:416` |
| +EV puro y alta volatilidad → **single obligatorio** | **Brecha:** no existe ruteo automático simple vs. parlay; los boletos automáticos son combinados de 2-4 piernas y el single solo con `requested_count=1` | `ticket_builder.py:487-488` |
| Parlays limitados a cuotas 1.30-1.75 | **Parcial:** el rango real es por modo (EDGE 1.50-3.50 combinado, individual ≤ 2.10); el piso anti-cáscara es 1.25 y el piso de EV es 1.20 | `ticket_builder.py:12-61,293-303` |
| Varianza de parlay aplanada (piernas probables) | Implementado (prob. mínima 0.22-0.40, techos de cuota, correlación negativa prohibida) | `ticket_builder.py` |
| EV real del parlay (no promedio ingenuo) | Implementado (matriz conjunta) | `ticket_builder.py:176-236,524-534` |
| Quarter-Kelly con techo 2% y umbral operable | Implementado | `kelly.py` |
| Perfilamiento por liga (no tratar ligas igual) | Implementado (5 tablas calibradas + alta varianza) | §4.2 |
| Red flags: juveniles, copas tempranas, accidentes | **Brecha:** no implementado | §5.4 |
| Handicap asiático excluido | Implementado (bloqueado) | `odds_service.py:483,493` |
| Player props en pipeline principal | **Brecha:** modelo standalone, no conectado | `player_props_model.py` |
| xG alimentando fuerza | **Brecha:** xG se ingesta pero la fuerza es goal-based | `strength_calculator.py` |

---

## 9. Índice de Referencias del Código

| Componente | Ubicación |
|---|---|
| Motor de Poisson + Dixon-Coles | `packages/ml/betmind_ml/models/poisson_engine.py` |
| Cálculo de mercados (todas las familias) | `packages/ml/betmind_ml/models/market_calculator.py` |
| Índices de fuerza | `packages/ml/betmind_ml/features/strength_calculator.py` |
| Calibración por liga | `packages/ml/betmind_ml/calibration/league_calibrator.py` |
| EV / edge / veredictos | `packages/ml/betmind_ml/ev/ev_calculator.py` |
| Constantes del modelo (ligas, umbrales, ventaja local) | `packages/ml/betmind_ml/config.py` |
| Kelly fraccional | `apps/api/engine/kelly.py` |
| Constructor de boletos (modos, filtros, correlaciones) | `apps/api/engine/ticket_builder.py` |
| Índice de tensión de partido (MTI) | `apps/api/engine/match_tension.py` |
| Modelo de córners | `apps/api/engine/corners_model.py` |
| Modelo de player props | `apps/api/engine/player_props_model.py` |
| Resolución de outcomes | `apps/api/engine/outcome_resolver.py` |
| Ingesta de cuotas y filtros | `apps/api/services/odds_service.py`, `sofascore_odds_service.py`, `espn_odds_service.py` |
| Proveedores de datos | `apps/api/services/providers/` |
| CLV | `apps/api/jobs/clv_tracker.py` |
| Evaluación de pronósticos | `apps/api/jobs/evaluate_predictions.py` |
| Backtesting | `packages/ml/betmind_ml/backtesting/` |
| Patrones de bet-builder correlacionados | `packages/ml/betmind_ml/bet_builder_patterns.py` |
