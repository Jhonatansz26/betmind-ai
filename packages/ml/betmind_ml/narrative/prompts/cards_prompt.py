"""
Prompt para el mercado de disciplina y tarjetas.
El árbitro es el factor diferencial de este mercado.
"""

CARDS_ANALYSIS_USER = """
Analiza el mercado de TARJETAS para el siguiente partido.

## DATOS DEL PARTIDO
**{home_team} vs {away_team}** | {league}

### Árbitro Designado: {referee_name}
{referee_section}

### Disciplina de los Equipos (últimos {strength_window} partidos — 90 min)
**{home_team}:**
- Faltas cometidas promedio: {home_avg_fouls}
- Tarjetas amarillas promedio recibidas: {home_avg_yellows}
- Jugadores con > 3 amarillas en la temporada: {home_booked_players}

**{away_team}:**
- Faltas cometidas promedio: {away_avg_fouls}
- Tarjetas amarillas promedio recibidas: {away_avg_yellows}
- Jugadores con > 3 amarillas en la temporada: {away_booked_players}

### Contexto de Tensión
- Tipo de partido: {match_importance}
- Es derby/clásico: {is_derby}
- Intensidad de la rivalidad: {rivalry_intensity}/5
- Situación en tabla (local posición {home_position} vs visitante posición {away_position})

### Línea de Tarjetas a Analizar
- Over {cards_line} tarjetas totales
- Promedio esperado del modelo: {expected_total_cards} tarjetas

{bookmaker_cards_section}

## REGLA ESPECIAL PARA TARJETAS
El árbitro es el factor con MAYOR peso en este mercado (>40% del análisis).
Si no hay datos confiables del árbitro (matches_sample < 5), indícalo explícitamente
en un "con" y reduce el signal_strength a "weak" o "moderate" máximo.

Responde con exactamente este JSON schema:
{json_schema}
"""

REFEREE_DATA_AVAILABLE = """
- Partidos como árbitro (muestra): {referee_matches}
- Amarillas promedio por partido: {referee_avg_yellows}
- Rojas promedio por partido: {referee_avg_reds}
- Faltas pitadas promedio: {referee_avg_fouls}
- Índice de estrictez (vs árbitros de la liga): {referee_strictness} (1.0 = promedio)
- En derbis/alta tensión: {referee_high_stakes_avg} amarillas promedio
- Tendencia reciente: {referee_trend}
"""

REFEREE_DATA_UNAVAILABLE = """
- ADVERTENCIA: No hay datos históricos del árbitro {referee_name} en nuestra base.
  El análisis de tarjetas tendrá menor confiabilidad.
  Usa solo los datos de disciplina de equipos y contexto del partido.
"""
