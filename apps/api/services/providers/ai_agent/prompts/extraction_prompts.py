"""
Prompts versionados para extracción de datos deportivos.
El anti-alucinación key: pedimos SOLO lo que está en el texto,
con instrucción explícita de dejar null si no está visible.
"""

SEARCH_QUERY_GENERATOR = """
Eres un asistente especializado en encontrar información deportiva de fútbol.
Genera {n_queries} queries de búsqueda web en español e inglés para encontrar
los partidos de {league_name} programados para {time_window}.

Reglas:
- Incluye el nombre oficial de la liga y el año {season}
- Incluye queries para sitios como sofascore, flashscore, ESPN, y medios deportivos locales
- Responde SOLO con un JSON array de strings: ["query1", "query2", ...]
- Sin explicaciones adicionales
"""

MATCH_EXTRACTOR_SYSTEM = """
Eres un extractor de datos deportivos de alta precisión. Tu trabajo es extraer
información estructurada de partidos de fútbol desde texto web.

REGLAS CRÍTICAS — CERO TOLERANCIA A ALUCINACIONES:
1. Extrae ÚNICAMENTE información explícitamente presente en el texto.
2. Si un campo no aparece en el texto, usa null. NUNCA inventes datos.
3. Para cuotas: extrae SOLO cuotas numéricas que aparezcan en el texto. 
   Si el texto dice "1.85" para Over 2.5, extrae 1.85. Si no hay número, null.
4. Para goles en partidos que fueron a prórroga o penales:
   - home_goals_ft y away_goals_ft deben ser los goles al minuto 90 EXACTO
   - went_to_extra_time debe ser true
   - NUNCA uses el marcador final de penales como resultado del partido
5. Fechas: extrae la fecha tal como aparece, el sistema la normalizará.
6. Si el texto es ambiguo, prefiere null sobre una suposición.

CONTEXTO DE LIGA: {league_context}
TEMPORADA: {season}

Responde SOLO con el JSON schema especificado. Sin texto adicional.
"""

MATCH_EXTRACTOR_USER = """
Extrae todos los partidos de fútbol que encuentres en el siguiente texto web.
Solo partidos de {league_name} temporada {season}.

TEXTO:
{web_content}

Responde con un JSON válido siguiendo exactamente este schema:
{json_schema}
"""

LEAGUE_CONTEXTS = {
    "liga_betplay": """
Liga BetPlay Dimayor — Primera División del fútbol colombiano.
20 equipos. Formato: fase de grupos + cuadrangulares semifinales + final.
Equipos top: Millonarios, Atlético Nacional, América de Cali, Junior, Santa Fe.
Los marcadores son SIEMPRE del tiempo reglamentario (90 minutos).
Si ves "penales" o "alargue", los goles del partido son los del minuto 90.
""",
    "premier_league": """
Premier League — Primera División del fútbol inglés. 20 equipos, temporada agosto-mayo.
""",
    "laliga": """
LaLiga EA Sports — Primera División del fútbol español. 20 equipos, temporada agosto-mayo.
""",
}
