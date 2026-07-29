"""
Prompt para apuestas combinadas (Bet Builder) con correlación positiva.
"""

BET_BUILDER_USER = """
Eres un especialista en apuestas combinadas (Bet Builder) con enfoque en correlación positiva.

## DATOS DEL PARTIDO
**{home_team} vs {away_team}** | {league}

### Probabilidades del Modelo
{markets_summary}

### Análisis de Correlación Disponible
Estas jugadas tienden a correlacionarse positivamente en el fútbol:
- Victoria Local + Over 1.5 goles: correlación positiva (el local marca para ganar)
- Victoria amplia + Más córneres del local: correlación positiva (dominancia = más córneres)  
- Árbitro estricto + Over tarjetas: correlación directa
- Derby + Over tarjetas + Under goles: correlación moderada (tensión → más infracciones, menos espacio)
- Equipo inferior fuera + BTTS: moderada (necesita marcar = más abierto)

### Restricción Crítica
Las siguientes jugadas tienen correlación NEGATIVA — NUNCA las combines:
- Under goles + Over córneres del favorito (si hay pocos goles, hay menos córneres del atacante)
- Victoria visitante amplia + Over córneres del local (si el local pierde amplio, genera menos)
- Árbitro permisivo + Over tarjetas

### Datos Disponibles
{all_analysis_data}

## INSTRUCCIÓN
Genera exactamente {n_suggestions} combinadas que tengan sentido táctico.
Cada combinada debe tener 2-4 legs y estar justificada por correlación real.
RECHAZA cualquier combinada con correlación negativa.

Responde con un array JSON de objetos. Cada objeto debe tener los campos:
"name" (string), "legs" (array de strings), "combined_probability" (float 0-1),
"combined_odds_estimate" (float), "correlation_rationale" (string), "risk_level" (string).
"""
