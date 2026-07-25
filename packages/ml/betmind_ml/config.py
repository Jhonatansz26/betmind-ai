"""
Constantes del modelo. Centralizadas aquí para ajuste sin tocar la lógica.
Estos valores son el resultado de calibración empírica — se actualizan con backtesting.
"""
import os

MODEL_VERSION = "poisson_v1.0"

# ── Configuración de API Keys ─────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Modelo Narrativo (LLM) ────────────────────────────────────────────────────
NARRATIVE_MODEL = "llama-3.3-70b-versatile"

# ── Parámetros del Feature Engineering ────────────────────────────────────────

# Mínimo de partidos para que un TeamStrengthProfile sea confiable
MIN_MATCHES_FOR_STRENGTH = 5

# Ventana de partidos para calcular fuerza de ataque/defensa
STRENGTH_WINDOW = 10  # últimos 10 partidos de la temporada actual

# Ventana para forma reciente (más corta — captura momento actual)
FORM_WINDOW = 5

# Ventana H2H
H2H_WINDOW = 6

# ── Factores de Ventaja de Local por Liga ─────────────────────────────────────
# Calibrados empíricamente sobre datos históricos
# Fuente de referencia: Dixon-Coles (1997), ajustados por liga
HOME_ADVANTAGE_BY_LEAGUE: dict[str, float] = {
    "premier_league":  1.20,   # Ligas top europeas: ventaja moderada
    "laliga":          1.22,
    "serie_a":         1.18,
    "bundesliga":      1.25,
    "liga_betplay":    1.30,   # Ligas latinoamericanas: mayor ventaja local
    "default":         1.20,
}

# ── Parámetros del Motor de Poisson ───────────────────────────────────────────

# Dimensión de la matriz de goles (0 a MAX_GOALS inclusive)
MAX_GOALS_MATRIX = 8  # cubre > 99.9% de partidos reales

# Peso de la forma reciente vs fuerza histórica (0.0 = solo histórico, 1.0 = solo forma)
FORM_WEIGHT = 0.25

# ── Umbrales de EV ────────────────────────────────────────────────────────────

# EV mínimo para clasificar como POSITIVE_EV (5% de margen conservador)
EV_POSITIVE_THRESHOLD = 0.05

# EV por debajo del cual clasificamos como AVOID
EV_AVOID_THRESHOLD = -0.10

# ── Mercado de Tarjetas ──────────────────────────────────────────────────────
CARDS_LINE_DEFAULT = 3.5

# ── Score de Confianza ────────────────────────────────────────────────────────
CONFIDENCE_WEIGHTS = {
    "strength_reliability":    0.35,  # ¿Los dos equipos tienen >= MIN_MATCHES?
    "form_data_completeness":  0.25,  # ¿Hay datos de forma de los últimos 5 partidos?
    "h2h_available":           0.20,  # ¿Hay historial H2H?
    "season_maturity":         0.20,  # ¿Han jugado suficientes jornadas?
}
