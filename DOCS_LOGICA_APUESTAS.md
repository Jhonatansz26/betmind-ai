# BetMind AI — Logica de Pronosticos y Calculo de Apuestas

> Documento tecnico para analistas deportivos y tipsters.
> Ultima actualizacion: Julio 2026

---

## Tabla de Contenidos

1. [Resumen General del Algoritmo](#1-resumen-general-del-algoritmo)
2. [Desglose por Mercado](#2-desglose-por-mercado)
3. [Estructura de Prompts y Metricas](#3-estructura-de-prompts-y-metricas)
4. [Generacion de Boletos (Tickets)](#4-generacion-de-boletos-tickets)
5. [Glosario de Terminos](#5-glosario-de-terminos)

---

## 1. Resumen General del Algoritmo

### 1.1 Arquitectura en Dos Fases

El sistema opera en dos capas complementarias:

| Fase | Nombre | Descripcion | Modelo |
|------|--------|-------------|--------|
| **Fase 3** | Motor Cuantitativo | Calcula probabilidades matematicas puras usando Distribucion de Poisson | Estadistico (sin IA) |
| **Fase 4** | Cerebro Tactico | Genera analisis narrativo con contexto cualitativo (lesiones, clima, arbitro) | LLM (Groq Llama 3.1-8b) |

**Regla estricta:** Todos los calculos consideran **exclusivamente los 90 minutos de juego reglamentario**. Goles de prorroga o penales NO se incluyen en ninguna estadistica.

### 1.2 Flujo de Datos

```
DATOS DE ENTRADA
    |
    v
1. Partidos historicos del equipo (ultimos 10) --> indices de fuerza
2. Forma reciente (ultimos 5 partidos)         --> momento actual
3. Enfrentamientos directos H2H (ultimos 6)    --> dominio historico
4. Promedios de la liga completa               --> baseline contextual
    |
    v
MOTOR CUANTITATIVO (Fase 3)
    |
    +--> Calcula goles esperados (lambda) para cada equipo
    +--> Construye matriz de probabilidades de marcadores (0-0 hasta 8-8)
    +--> Deriva probabilidades de todos los mercados
    +--> Compara contra cuotas de bookmaker --> calcula Valor Esperado (+EV)
    |
    v
CEREBRO TACTICO (Fase 4)
    |
    +--> Analisis narrativo de goles (LLM)
    +--> Analisis narrativo de tarjetas (LLM)
    +--> Analisis narrativo de corneres (LLM)
    +--> Sugerencias de combinadas correlacionadas (LLM)
    |
    v
RESPUESTA FINAL: Probabilidades + EV + Narrativa + Confianza
```

### 1.3 Formula Central: Goles Esperados (Lambda)

El corazon del modelo es el calculo de **lambdas** (goles esperados) para cada equipo:

```
lambda_local  = ataque_local x defensa_visitante x promedio_liga x ventaja_local x ajuste_forma x ajuste_H2H
lambda_visita = ataque_visita x defensa_local x promedio_liga x ajuste_forma x ajuste_H2H
```

Cada componente se explica a continuacion:

#### Indices de Ataque y Defensa (Dixon-Robinson simplificado)

```
ataque  = (goles_marcados_equipo / partidos) / (goles_totales_liga / partidos_liga / 2)
defensa = (goles_totales_liga / partidos_liga / 2) / (goles_recibidos_equipo / partidos)
```

| Valor | Interpretacion |
|-------|----------------|
| `ataque = 1.0` | Equipo promedio de la liga |
| `ataque = 1.3` | Marca 30% mas goles que el promedio |
| `defensa = 1.2` | Recibe 20% menos goles que el promedio (buena defensa) |
| `defensa < 1.0` | Recibe mas goles que el promedio (defensa fragil) |

**Ventana de calculo:** Ultimos 10 partidos de la temporada actual (`STRENGTH_WINDOW = 10`).
**Minimo de confiabilidad:** 5 partidos (`MIN_MATCHES_FOR_STRENGTH = 5`). Si un equipo tiene menos, el perfil se marca como "no confiable".

### 1.4 Peso Relativo de Cada Factor

| Factor | Peso en el calculo | Rango de impacto | Descripcion |
|--------|:------------------:|:----------------:|-------------|
| **Indices de fuerza (ataque/defensa)** | ~55% | Multiplicador directo del lambda | Base estadistica principal |
| **Ventaja de localia** | ~15% | 1.18x - 1.30x segun liga | Calibrado empiricamente por liga |
| **Forma reciente (ultimos 5)** | ~12.5% | Multiplicador 0.875x - 1.125x | Captura el "momento" del equipo |
| **H2H (enfrentamientos directos)** | ~5% | Multiplicador maximo 0.95x - 1.05x | Ajuste leve, requiere minimo 3 partidos |
| **Promedio de la liga** | Base | Escala absoluta | Contexto de la competicion |

### 1.5 Ventaja de Localia por Liga

| Liga | Factor de localia | Tendencia historica |
|------|:-----------------:|:-------------------:|
| Liga BetPlay (Colombia) | **1.30** | Mayor ventaja local (altitud, viajes) |
| Bundesliga (Alemania) | **1.25** | Publico muy influyente |
| LaLiga (Espana) | **1.22** | Ventaja moderada-alta |
| Premier League (Inglaterra) | **1.20** | Liga mas competitiva, ventaja moderada |
| Serie A (Italia) | **1.18** | Menor ventaja de las top europeas |
| Default (otras ligas) | **1.20** | Valor por defecto |

### 1.6 Ajuste por Forma Reciente

La forma se mide en **puntos de los ultimos 5 partidos** (victoria=3, empate=1, derrota=0). Maximo posible: 15 puntos.

```
multiplicador_forma = 1.0 + 0.25 x (puntos_forma / 15 - 0.5)
```

| Forma (ultimos 5) | Puntos | Multiplicador | Efecto |
|--------------------|:------:|:-------------:|--------|
| 5 victorias | 15 | **1.125** | +12.5% goles esperados |
| 4V + 1E | 13 | **1.063** | +6.3% |
| 3V + 2E | 11 | **1.000** | Sin ajuste (neutral) |
| 2V + 1E + 2D | 7 | **0.875** | -12.5% |
| 5 derrotas | 0 | **0.875** | -12.5% (minimo) |

### 1.7 Ajuste por H2H (Enfrentamientos Directos)

```
Si hay >= 3 partidos H2H:
    dominancia_local = tasa_victorias_local - 0.5    (rango: -0.5 a +0.5)
    ajuste = dominancia_local x 0.10                  (maximo +/- 5%)

Si hay < 3 partidos H2H:
    Sin ajuste (neutro: 1.0, 1.0)
```

**Nota importante:** El H2H tiene un peso deliberadamente bajo (maximo +/-5%) para evitar sobre-ponderar historiales pequenos o desactualizados. La forma actual y la fuerza del equipo pesan mucho mas.

### 1.8 Calibracion por Liga (Validacion de Lambdas)

Despues de calcular los lambdas, el sistema valida que esten dentro de rangos historicos conocidos para cada liga. Si un lambda excede el rango, se **clampea** al limite:

| Liga | Rango lambda local | Rango lambda visitante | Goles/equipo esperados |
|------|:------------------:|:----------------------:|:----------------------:|
| Premier League | 0.8 - 3.0 | 0.5 - 2.5 | 1.35 |
| LaLiga | 0.7 - 2.8 | 0.5 - 2.3 | 1.30 |
| Liga BetPlay | 0.6 - 2.4 | 0.4 - 2.0 | 1.15 |
| Serie A (Brasil) | 0.7 - 2.6 | 0.5 - 2.2 | 1.25 |
| Liga Profesional (Arg) | 0.6 - 2.3 | 0.4 - 1.9 | 1.12 |
| Liga MX | 0.7 - 2.7 | 0.5 - 2.4 | 1.32 |
| MLS | 0.8 - 3.1 | 0.6 - 2.6 | 1.48 |
| Primera Chile | 0.7 - 2.6 | 0.5 - 2.3 | 1.28 |
| Liga Pro (Ecuador) | 0.7 - 2.6 | 0.5 - 2.1 | 1.22 |
| Liga 1 (Peru) | 0.7 - 2.7 | 0.4 - 2.2 | 1.25 |
| Allsvenskan (Suecia) | 0.8 - 2.9 | 0.5 - 2.5 | 1.38 |
| Superliga (Dinamarca) | 0.7 - 2.8 | 0.5 - 2.4 | 1.35 |
| Super League (Suiza) | 0.8 - 3.0 | 0.6 - 2.6 | 1.42 |

---

## 2. Desglose por Mercado

### 2.1 Matriz de Poisson (Base de Todos los Mercados)

A partir de los lambdas, se construye una **matriz de 9x9** (de 0-0 a 8-8) con la probabilidad de cada marcador exacto:

```
P(local_marcas_i, visitante_marca_j) = P(Poisson(lambda_local, i)) x P(Poisson(lambda_visita, j))
```

Donde:
```
P(Poisson(lambda, k)) = (lambda^k x e^(-lambda)) / k!
```

**Ejemplo:** Si lambda_local=1.8 y lambda_visita=1.1:
- P(1-0) = 30.1% x 33.3% = 10.0%
- P(2-1) = 27.1% x 18.3% = 5.0%
- La suma de toda la matriz = 1.0 (100%)

De esta matriz se derivan **todos** los mercados siguientes.

### 2.2 Goles: Over/Under

**Formula general:**

```
P(Over X.5) = Suma de todas las celdas de la matriz donde (goles_local + goles_visitante) > X.5
P(Under X.5) = 1.0 - P(Over X.5)
```

| Mercado | Umbral | Calculo |
|---------|:------:|---------|
| Over/Under 0.5 | 0.5 | Suma de celdas con total_goles > 0.5 |
| Over/Under 1.5 | 1.5 | Suma de celdas con total_goles > 1.5 |
| **Over/Under 2.5** | **2.5** | **Suma de celdas con total_goles > 2.5** (mercado principal) |
| Over/Under 3.5 | 3.5 | Suma de celdas con total_goles > 3.5 |

**Ejemplo practico:**
```
lambda_local = 1.8, lambda_visita = 1.1
Goles esperados totales = 2.9

P(Over 2.5) = P(total >= 3) = 61.2%
P(Under 2.5) = P(total <= 2) = 38.8%
```

**Regla de decision narrativa (fallback sin LLM):**
- P(Over 2.5) > 55% --> Recomendacion: "Over 2.5"
- P(Over 2.5) < 45% --> Recomendacion: "Under 2.5"
- Entre 45-55% --> "Mercado neutral"

### 2.3 BTTS (Ambos Equipos Anotan)

**Formula:**

```
P(BTTS_Si) = Suma de celdas donde (goles_local >= 1 Y goles_visitante >= 1)
P(BTTS_No) = 1.0 - P(BTTS_Si)
```

**Equivalentemente:**
```
P(BTTS_Si) = 1 - P(local_no_anota) - P(visitante_no_anota) + P(0-0)
```

**Ejemplo:**
```
lambda_local = 1.8, lambda_visita = 1.1
P(local no anota) = P(Poisson(1.8, 0)) = 16.5%
P(visitante no anota) = P(Poisson(1.1, 0)) = 33.3%
P(0-0) = 16.5% x 33.3% = 5.5%

P(BTTS_Si) = 1 - 16.5% - 33.3% + 5.5% = 55.7%
```

### 2.4 Ganador / Resultado Final (1X2)

**Formula:**

```
P(Local gana)  = Suma de celdas donde goles_local > goles_visitante
P(Empate)      = Suma de celdas donde goles_local = goles_visitante
P(Visitante gana) = Suma de celdas donde goles_local < goles_visitante
```

Las tres probabilidades se **normalizan** para asegurar que sumen exactamente 1.0.

**Ejemplo:**
```
lambda_local = 1.8, lambda_visita = 1.1

P(Local gana)  = 52.3%
P(Empate)      = 24.1%
P(Visitante gana) = 23.6%
```

### 2.5 Corneres (Tiros de Esquina)

Los corneres **no se calculan con Poisson** directamente. El modelo usa un enfoque hibrido:

#### Capa Cuantitativa (Fallback estadistico)
Cuando no hay datos detallados de corneres, el sistema genera un analisis basico con senal de confianza LOW.

#### Capa Cualitativa (LLM con datos)
Cuando hay datos de corneres disponibles, el LLM recibe el siguiente payload:

| Variable | Descripcion | Fuente |
|----------|-------------|--------|
| `home_corners_for_avg` | Corneres a favor promedio del local | Ultimos 10 partidos |
| `home_corners_against_avg` | Corneres en contra promedio del local | Ultimos 10 partidos |
| `home_blocked_shots_avg` | Tiros bloqueados promedio (generan corneres) | Estadistica avanzada |
| `home_tactical_style` | Estilo tactico del equipo | Clasificacion |
| `away_corners_for_avg` | Corneres a favor promedio del visitante | Ultimos 10 partidos |
| `away_corners_against_avg` | Corneres en contra promedio del visitante | Ultimos 10 partidos |
| `away_blocked_shots_avg` | Tiros bloqueados promedio del visitante | Estadistica avanzada |
| `expected_corners_home` | Corneres esperados del local | Modelo |
| `expected_corners_away` | Corneres esperados del visitante | Modelo |
| `expected_corners_total` | Total de corneres esperados | Modelo |
| `h2h_corners_avg` | Promedio de corneres en H2H | Historial directo |
| `h2h_over_corners_count` | Partidos H2H con Over la linea | Historial directo |
| `home_high_press_index` | Indice de presion alta del local | Estadistica avanzada |
| `away_wide_play_index` | Indice de juego por bandas del visitante | Estadistica avanzada |
| `corners_line` | Linea de corneres a analizar (default: 9.5) | Configuracion |

**Regla de confianza:** El sistema indica que los corneres tienen **alta varianza** y que el `signal_strength` raramente debe ser "strong" a menos que el modelo indique >68% de probabilidad Y los datos H2H lo confirmen.

### 2.6 Tarjetas (Amarillas / Rojas / Disciplina)

El mercado de tarjetas tiene una particularidad: **el arbitro es el factor dominante** (>40% del analisis segun las instrucciones del prompt).

#### Variables que intervienen:

| Variable | Peso estimado | Descripcion |
|----------|:-------------:|-------------|
| **Arbitro: promedio amarillas/partido** | **Alto (>40%)** | Cuantas amarillas muestra el arbitro en promedio |
| **Arbitro: indice de estrictez** | Alto | 1.0 = promedio de la liga, >1.0 = mas estricto |
| **Arbitro: tendencia reciente** | Medio | "increasing", "decreasing", "stable" |
| **Arbitro: promedio en derbis** | Medio | Amarillas en partidos de alta tension |
| Equipos: faltas cometidas promedio | Medio | Faltas por partido de cada equipo |
| Equipos: amarillas recibidas promedio | Medio | Tarjetas por partido de cada equipo |
| Contexto: es derby/clasico | Medio | Si/No + intensidad de rivalidad (1-5) |
| Contexto: importancia del partido | Medio | FINAL, DERBY, RELEGATION, REGULAR, etc. |
| Jugadores con >3 amarillas acumuladas | Bajo | Riesgo de suspension |

#### Linea de tarjetas:
- Linea por defecto: **3.5 tarjetas totales** (`CARDS_LINE_DEFAULT`)
- Se analiza Over/Under de esa linea

#### Logica de degradacion:
- Si el arbitro NO tiene datos confiables (<5 partidos en muestra):
  - Se indica explicitamente en un "con"
  - Se reduce `signal_strength` a "weak" o "moderate" maximo
  - El LLM recibe una advertencia explicita: *"ADVERTENCIA: No hay datos historicos del arbitro"*

### 2.7 Valor Esperado (+EV)

Una vez calculadas las probabilidades reales del modelo, se comparan contra las cuotas del bookmaker:

```
Probabilidad_implicita = 1 / cuota
Edge = Probabilidad_real - Probabilidad_implicita
EV = (Probabilidad_real x (cuota - 1)) - (1 - Probabilidad_real)
```

**Ejemplo practico:**
```
Modelo dice: P(Over 2.5) = 61.2%
Bookmaker ofrece: cuota 1.70

Probabilidad_implicita = 1 / 1.70 = 58.8%
Edge = 61.2% - 58.8% = +2.4%
EV = (0.612 x 0.70) - (1 - 0.612) = 0.428 - 0.388 = +0.041

EV = +0.041 (4.1% de retorno esperado por unidad apostada)
```

#### Clasificacion de Veredictos:

| EV | Veredicto | Significado |
|:--:|-----------|-------------|
| >= +5% | **POSITIVE_EV** | Apuesta con valor real detectado |
| 0% a +5% | **NO_VALUE** | Zona gris (ruido estadistico) |
| <= -10% | **AVOID** | Evitar activamente |
| -10% a 0% | **NO_VALUE** | Sin valor suficiente |

**Nota sobre el overround:** Las cuotas del bookmaker incluyen un margen (tipicamente 5-8%). Nuestro modelo trabaja con probabilidades REALES que suman 1.0, por lo que el edge detectado ya descuenta ese margen implicito.

---

## 3. Estructura de Prompts y Metricas

### 3.1 Sistema Anti-Alucinacion (SYSTEM_BASE)

Todos los prompts del LLM heredan estas reglas criticas:

1. **SOLO datos proporcionados:** Cada afirmacion debe estar respaldada por un numero explicito. Si el dato no esta, decir "no hay informacion disponible" -- NUNCA inventar estadisticas.
2. **Honestidad obligatoria:** SIEMPRE al menos 1 factor EN CONTRA (cons) de la apuesta recomendada.
3. **Probabilidades coherentes:** Si Poisson dice P(Over 2.5)=54%, la narrativa NO puede decir "muy probable" ni "improbable".
4. **Calibracion de lenguaje:**
   - 65-100%: "alta probabilidad", "favorecido ampliamente"
   - 55-65%: "ligera ventaja", "levemente favorable"
   - 45-55%: "partido equilibrado", "mercado disputado"
   - <45%: "en contra de la tendencia", "apuesta de riesgo"
5. **Factores ausentes:** Si no hay datos del arbitro, NO mencionar al arbitro. Si no hay datos de jugadores, NO hacer props.
6. **Formato:** Respuesta exclusivamente en JSON schema.

### 3.2 Payload Enviado al LLM para Goles (Over/Under + BTTS)

```
DATOS DEL PARTIDO
==================
Local vs Visitante | Liga | Fecha

Motor Cuantitativo (Poisson)
------------------------------
- Goles esperados Local (lambda): [valor]
- Goles esperados Visitante (lambda): [valor]
- P(Over 2.5 goles): [porcentaje]%
- P(Under 2.5 goles): [porcentaje]%
- P(BTTS - Ambos Anotan): [porcentaje]%
- Marcador mas probable: [X-Y] ([Z]%)

Forma Reciente (ultimos 5 partidos -- solo 90 min)
---------------------------------------------------
Local:
- Puntos: [X]/15
- Goles marcados promedio: [X]
- Goles recibidos promedio: [X]
- Indice de ataque (vs liga): [X] (1.0 = promedio)
- Indice de defensa (vs liga): [X] (>1.0 = mejor que promedio)

Visitante:
- [mismos campos]

Historial H2H (ultimos N enfrentamientos)
------------------------------------------
- Promedio de goles totales: [X]
- Partidos Over 2.5: [X]/[N]
- BTTS en H2H: [X]/[N]

Contexto del Partido
---------------------
- Importancia: [REGULAR / DERBY / FINAL / RELEGATION / TITLE_DECIDER]
- Altitud estadio: [X] msnm (impacto: high/moderate/none)
- Clima esperado: [texto]
- Bajas local: [nombres o "Ninguna baja confirmada"]
- Bajas visitante: [nombres o "Ninguna baja confirmada"]
- Dias desde ultimo partido (local): [X]
- Dias desde ultimo partido (visitante): [X]

Cuotas del Bookmaker (si disponibles)
--------------------------------------
- Over 2.5: [cuota] (P. implicita: [X]%)
- Under 2.5: [cuota] (P. implicita: [X]%)
- EV Over 2.5: [+/-X.XXX]
- EV Under 2.5: [+/-X.XXX]
- Edge detectado: [+/-X.X]%
```

### 3.3 Payload Enviado al LLM para Tarjetas

```
DATOS DEL PARTIDO
==================
Local vs Visitante | Liga

Arbitro Designado: [nombre]
-----------------------------
- Partidos como arbitro (muestra): [N]
- Amarillas promedio por partido: [X]
- Rojas promedio por partido: [X]
- Faltas pitadas promedio: [X]
- Indice de estrictez (vs liga): [X] (1.0 = promedio)
- En derbis/alta tension: [X] amarillas promedio
- Tendencia reciente: [increasing/decreasing/stable]

  O si no hay datos:
  "ADVERTENCIA: No hay datos historicos del arbitro [nombre]"

Disciplina de los Equipos (ultimos 10 partidos -- 90 min)
----------------------------------------------------------
Local:
- Faltas cometidas promedio: [X]
- Tarjetas amarillas promedio recibidas: [X]
- Jugadores con >3 amarillas en la temporada: [nombres]

Visitante:
- [mismos campos]

Contexto de Tension
--------------------
- Tipo de partido: [REGULAR / DERBY / FINAL]
- Es derby/clasico: [Si/No]
- Intensidad de la rivalidad: [1-5]/5
- Situacion en tabla: local posicion [X] vs visitante posicion [Y]

Linea de Tarjetas a Analizar
------------------------------
- Over [X] tarjetas totales
- Promedio esperado del modelo: [X] tarjetas
```

### 3.4 Payload Enviado al LLM para Corneres

```
DATOS DEL PARTIDO
==================
Local vs Visitante | Liga

Estadisticas de Corneres (ultimos 10 partidos -- 90 min)
---------------------------------------------------------
Local (jugando de LOCAL):
- Corneres a favor promedio: [X]
- Corneres en contra promedio: [X]
- Tiros bloqueados promedio (generan corneres): [X]
- Estilo tactico: [texto]

Visitante (jugando de VISITANTE):
- [mismos campos]

Total esperado por el modelo
------------------------------
- Corneres esperados local: [X]
- Corneres esperados visitante: [X]
- Total esperado: [X]

H2H de Corneres
----------------
- Promedio de corneres totales en H2H: [X]
- Partidos con Over [linea]: [X]/[N]

Factores Tacticos Especiales
------------------------------
- Datos de presion alta del local: [X]
- Dato de juego por bandas del visitante: [X]
```

### 3.5 Payload para Bet Builder (Combinadas Correlacionadas)

El Bet Builder se ejecuta **despues** de los otros tres generadores porque necesita sus resultados como contexto. Recibe:

1. **Resumen de probabilidades** de todos los mercados (1X2, Over/Under, BTTS)
2. **Resumen de narrativas** previas (goles, tarjetas, corneres)
3. **Reglas de correlacion positiva** (ej: Local gana + Over 1.5 = correlacion alta)
4. **Reglas de correlacion negativa** (ej: Under goles + Over corneres = NUNCA combinar)

Se generan hasta **3 combinadas** de 2-4 legs cada una.

### 3.6 Calculo del Score de Confianza (0-100)

El score de confianza es **ponderado** con 4 componentes:

| Componente | Peso | Criterio |
|------------|:----:|----------|
| **Confiabilidad de perfiles** | 35% | Ambos equipos tienen >= 5 partidos? (100/50/0) |
| **Completitud de forma** | 25% | Cuantos de los ultimos 5 partidos tienen datos? |
| **H2H disponible** | 20% | Cuantos enfrentamientos directos hay? (max 4 = 100%) |
| **Madurez de temporada** | 20% | Cuantos partidos hay en la liga? (60+ = 100%) |

```
confianza = (35% x perfil) + (25% x forma) + (20% x H2H) + (20% x temporada)
```

**Bonus por narrativas LLM:**
```
confianza_final = min(confianza_base + (narrativas_generadas / 3) x 15, 100)
```

Si se generaron las 3 narrativas (goles, tarjetas, corneres): +15 puntos extra.

### 3.7 Data Completeness Score (0.0 - 1.0)

Indica cuanta informacion contextual estuvo disponible:

| Dato disponible | Puntos |
|-----------------|:------:|
| Arbitro confiable (>=5 partidos en muestra) | +0.35 |
| Datos de corneres disponibles | +0.35 |
| H2H con >= 3 partidos | +0.30 |
| **Maximo** | **1.00** |

---

## 4. Generacion de Boletos (Tickets)

### 4.1 Modos de Riesgo

El sistema genera boletos parlays en 3 modos con umbrales distintos:

| Parametro | EDGE | VALUE | BOLD |
|-----------|:----:|:-----:|:----:|
| EV minimo por pata | 0.5% | 0.5% | 0.5% |
| Maximo de patas | 2 | 3 | 4 |
| Probabilidad minima | 40% | 30% | 22% |
| Cuota combinada objetivo | 1.50 - 3.50 | 2.50 - 12.00 | 8.00 - 30.00 |
| Cuota maxima individual | 2.10 | 4.00 | 8.00 |
| Staking sugerido | 1-2% bankroll | 0.5-1% bankroll | 0.25-0.5% bankroll |

### 4.2 Mercados Permitidos por Modo

| Mercado | EDGE | VALUE | BOLD |
|---------|:----:|:-----:|:----:|
| 1X2_HOME | Si | Si | Si |
| 1X2_DRAW | Si | Si | Si |
| 1X2_AWAY | No | Si | Si |
| OVER_2_5 | Si | Si | Si |
| OVER_1_5 | Si | Si | Si |
| BTTS_YES | Si | Si | Si |
| Otros | No | No | Si (todos) |

### 4.3 Reglas de Correlacion

#### Combinaciones Prohibidas (Correlacion Negativa)

Estas combinaciones NUNCA aparecen juntas en un boleto:

| Combinacion | Razon |
|-------------|-------|
| Under 2.5 + BTTS_Si | Contradictorio: pocos goles implica que quizas no ambos anotan |
| Under 1.5 + BTTS_Si | Casi imposible: menos de 2 goles y que ambos anoten |
| Over 3.5 + Under tarjetas | Partido abierto genera mas infracciones, no menos |
| Empate + BTTS_No | Empate sin goles es muy raro |
| Over 2.5 + Under tarjetas | Alta tension ofensiva = mas tarjetas |
| Visita gana + Over corneres local | Si visita domina, local genera menos corneres |

#### Combinaciones con Bonus (Correlacion Positiva)

Estas combinaciones suben la confianza del boleto:

| Combinacion | Correlacion |
|-------------|:-----------:|
| Local gana + Over 1.5 goles | 0.72 |
| Local gana + Over corneres | 0.65 |
| BTTS_Si + Over 2.5 goles | **0.81** (muy alta) |
| Over tarjetas + Empate | 0.58 |
| Over 3.5 + BTTS_Si | 0.76 |

### 4.4 Algoritmo de Construccion del Boleto

```
1. Recopilar todos los mercados de todos los partidos disponibles
2. Filtrar por:
   - Mercado permitido para el modo
   - Probabilidad >= minimo del modo
   - Cuota individual <= maximo del modo
   - EV >= 0.5%
3. Ordenar candidatos por EV descendente
4. Seleccionar iterativamente:
   a. Tomar el mejor candidato
   b. Verificar que no duplique partido (1 mercado por partido)
   c. Verificar que no active correlacion negativa
   d. Agregar al boleto
5. Repetir hasta alcanzar maximo de patas
6. Verificar que la cuota combinada este en el rango objetivo
7. Si cuota muy baja: agregar patas adicionales
8. Si cuota muy alta: remover patas de menor EV
9. Si la cuota final NO esta en rango objetivo: descartar boleto (return None)
10. Calcular confianza:
    confianza = min(EV_promedio x 400 + bonus_correlacion x 20 + num_patas x 5, 95)
```

### 4.5 Desduplicacion Cross-Modo

Los 3 boletos (EDGE, VALUE, BOLD) se generan **secuencialmente** con exclusion mutua:
- Los partidos usados en EDGE NO se usan en VALUE
- Los partidos usados en VALUE NO se usan en BOLD

Esto garantiza que los 3 boletos cubran escenarios diferentes y no concentren riesgo en los mismos partidos.

### 4.6 Mercados sin Cuotas Reales

Cuando un partido no tiene cuotas de bookmaker disponibles, el sistema **deriva mercados sinteticos** desde las probabilidades de Poisson:

```
Para cada mercado (1X2_HOME, DRAW, AWAY, OVER_2_5, OVER_1_5):
    probabilidad_implícita = probabilidad_Poisson / 1.08   (overround sintetico del 8%)
    cuota_estimada = round(1 / probabilidad_implicita, 2)
    EV = (probabilidad_Poisson - probabilidad_implicita) / probabilidad_implicita
```

Esto permite que partidos sin cuotas reales aun participen en los boletos con cuotas estimadas justas.

---

## 5. Glosario de Terminos

| Termino | Definicion |
|---------|------------|
| **Lambda (λ)** | Goles esperados de un equipo en un partido. Es el parametro central de la distribucion de Poisson. |
| **xG (Expected Goals)** | Sinonimo de lambda en este contexto. Goles que se espera que marque un equipo. |
| **Edge** | Diferencia entre nuestra probabilidad real y la probabilidad implicita de la cuota. |
| **EV (Expected Value / Valor Esperado)** | Retorno esperado por unidad apostada. EV positivo = apuesta rentable a largo plazo. |
| **Overround** | Margen del bookmaker. La suma de probabilidades implicitas de todas las cuotas supera el 100%. |
| **BTTS** | Both Teams To Score (Ambos Equipos Anotan). |
| **H2H** | Head-to-Head (enfrentamientos directos entre dos equipos). |
| **Signal Strength** | Nivel de confianza de la narrativa: STRONG (3+ factores), MODERATE (2 factores), WEAK (1 factor). |
| **Data Completeness** | Score 0-1 que indica cuanta informacion contextual estuvo disponible para el analisis. |
| **FORM_WEIGHT** | Peso de la forma reciente vs. fuerza historica. Actualmente 0.25 (25% forma, 75% historico). |
| **Staking** | Porcentaje del bankroll sugerido para apostar segun el modo de riesgo. |
| **90-min rule** | Regla estricta: solo se consideran goles de tiempo reglamentario (90 min), excluyendo prorrogas. |

---

> **Nota final:** Este documento refleja la logica implementada en el codigo fuente del proyecto BetMind AI. Los modelos estadisticos se calibran periodicamente con backtesting walk-forward para validar su precision predictiva.
