"""
Prompt para el mercado de córneres.
"""

CORNERS_ANALYSIS_USER = """
Analiza el mercado de CÓRNERES para el siguiente partido.

## DATOS DEL PARTIDO
**{home_team} vs {away_team}** | {league}

### Estadísticas de Córneres (últimos {strength_window} partidos — 90 min)
**{home_team} (jugando de LOCAL):**
- Córneres a favor promedio: {home_corners_for_avg}
- Córneres en contra promedio: {home_corners_against_avg}
- Tiros bloqueados promedio (generan córners): {home_blocked_shots_avg}
- Estilo táctico: {home_tactical_style}

**{away_team} (jugando de VISITANTE):**
- Córneres a favor promedio: {away_corners_for_avg}
- Córneres en contra promedio: {away_corners_against_avg}
- Tiros bloqueados promedio: {away_blocked_shots_avg}
- Estilo táctico: {away_tactical_style}

### Total esperado por el modelo
- Córneres esperados local: {expected_corners_home}
- Córneres esperados visitante: {expected_corners_away}
- Total esperado: {expected_corners_total}

### H2H de Córneres
- Promedio de córneres totales en H2H: {h2h_corners_avg}
- Partidos con Over {corners_line}: {h2h_over_corners_count}/{h2h_count}

### Factores Tácticos Especiales
- Si {away_team} va perdiendo → tiende a presionar más = más córneres
- Datos de presión alta del local: {home_high_press_index}
- Dato de juego por bandas del visitante: {away_wide_play_index}

{bookmaker_corners_section}

## NOTA
Los córneres tienen alta varianza. El signal_strength raramente debe ser "strong"
a menos que el modelo indique > 68% de probabilidad Y los datos H2H lo confirmen.

Responde con exactamente este JSON schema:
{json_schema}
"""
