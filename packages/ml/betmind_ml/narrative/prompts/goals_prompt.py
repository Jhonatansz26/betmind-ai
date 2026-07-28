"""
Prompt especializado para el mercado de goles: Over/Under y BTTS.
"""

GOALS_ANALYSIS_USER = """
Analiza el mercado de GOLES para el siguiente partido y devuelve el JSON.

## DATOS DEL PARTIDO
**{home_team} vs {away_team}** | {league} | {match_date}

### Motor Cuantitativo (Poisson)
- Goles esperados Local (λ): {lambda_home}
- Goles esperados Visitante (λ): {lambda_away}
- P(Más de 2.5 goles): {p_over_25}%
- P(Menos de 2.5 goles): {p_under_25}%
- P(BTTS - Ambos Anotan): {p_btts}%
- Marcador más probable: {most_likely_score} ({most_likely_prob}%)

### Forma Reciente (últimos 5 partidos — solo 90 min)
**{home_team}:**
- Puntos: {home_form_points}/15
- Goles marcados promedio: {home_avg_scored}
- Goles recibidos promedio: {home_avg_conceded}
- Índice de ataque (vs liga): {home_attack_index} (1.0 = promedio)
- Índice de defensa (vs liga): {home_defense_index} (>1.0 = mejor que promedio)

**{away_team}:**
- Puntos: {away_form_points}/15
- Goles marcados promedio: {away_avg_scored}
- Goles recibidos promedio: {away_avg_conceded}
- Índice de ataque (vs liga): {away_attack_index}
- Índice de defensa (vs liga): {away_defense_index}

### Historial H2H (últimos {h2h_count} enfrentamientos)
- Promedio de goles totales: {h2h_avg_goals}
- Partidos Más de 2.5: {h2h_over_25_count}/{h2h_count}
- BTTS en H2H: {h2h_btts_count}/{h2h_count}

### Contexto del Partido
- Importancia: {match_importance}
- Altitud estadio: {altitude_masl} msnm (impacto: {altitude_impact})
- Clima esperado: {weather}
- Bajas local: {home_players_out}
- Bajas visitante: {away_players_out}
- Días desde último partido (local): {home_days_rest}
- Días desde último partido (visitante): {away_days_rest}

{bookmaker_section}

## INSTRUCCIÓN
Basándote SOLO en los datos anteriores, genera el análisis para el mercado de Más/Menos de 2.5 goles.
La recommendation debe ser la opción con mayor valor esperado o mayor probabilidad si no hay cuotas.

Responde con exactamente este JSON schema:
{json_schema}
"""

BOOKMAKER_SECTION_WITH_ODDS = """
### Cuotas del Bookmaker
- Over 2.5: {odds_over} (P. implícita: {implied_over}%)
- Under 2.5: {odds_under} (P. implícita: {implied_under}%)
- EV Over 2.5: {ev_over}
- EV Under 2.5: {ev_under}
- **Edge detectado:** {edge}%
"""

BOOKMAKER_SECTION_NO_ODDS = """
### Cuotas del Bookmaker
No disponibles para este análisis. Análisis basado solo en probabilidades del modelo.
"""
