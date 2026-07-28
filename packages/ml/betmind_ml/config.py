"""
Constantes del modelo. Centralizadas aquí para ajuste sin tocar la lógica.
Estos valores son el resultado de calibración empírica — se actualizan con backtesting.
"""
import os

MODEL_VERSION = "poisson_v1.0"

# ── Configuración de API Keys ─────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_groq_api_keys() -> list[str]:
    """Retorna lista limpia de API keys desde GROQ_API_KEYS (coma) y GROQ_API_KEY."""
    keys: list[str] = []
    raw_keys = os.getenv("GROQ_API_KEYS", "")
    if raw_keys:
        keys.extend([k.strip() for k in raw_keys.split(",") if k.strip()])
    single_key = os.getenv("GROQ_API_KEY", "")
    if single_key and single_key not in keys:
        keys.insert(0, single_key.strip())
    return keys


GROQ_API_KEYS_LIST = get_groq_api_keys()

# ── Timeouts de Groq ───────────────────────────────────────────────────────────
GROQ_TIMEOUT_SECONDS = 90.0
GROQ_SINGLE_CALL_TIMEOUT = 25.0
GROQ_NARRATIVE_TIMEOUT = 80.0

# ── Modelo Narrativo (LLM) ────────────────────────────────────────────────────
NARRATIVE_MODEL = "llama-3.3-70b-versatile"

# ── Parámetros del Feature Engineering ────────────────────────────────────────

# Mínimo de partidos para que un TeamStrengthProfile sea confiable
MIN_MATCHES_FOR_STRENGTH = 5

# Ventana de partidos para calcular fuerza de ataque/defensa
STRENGTH_WINDOW = 12  # últimos 12 partidos de la temporada actual

# Ventana para forma reciente (más corta — captura momento actual)
FORM_WINDOW = 5

# Ventana H2H
H2H_WINDOW = 6

# ── Ponderación Exponencial por Tiempo (Time Decay) ─────────────────────────
# Factor de decaimiento por índice de partido: peso[k] = DECAY_FACTOR^k
# k=0 (más reciente) → peso=1.0, k=11 (más antiguo) → peso=0.85^11≈0.167
DECAY_FACTOR = 0.85

# Decaimiento alternativo por días transcurridos: peso = exp(-DAYS_DECAY_RATE * días)
DAYS_DECAY_RATE = 0.005

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

# Baselines dinámicos de tarjetas por liga/región
# Ligas sudamericanas tienden a más tarjetas (4.5-5.5)
# Ligas europeas tienden a menos tarjetas (3.5-4.5)
CARDS_LINE_BY_LEAGUE: dict[str, float] = {
    # Sudamérica (más físicas, más tarjetas)
    "liga_betplay": 5.5,
    "liga_profesional_arg": 5.5,
    "serie_a_bra": 5.0,
    "liga_mx": 4.5,
    "primera_chile": 5.0,
    "liga_pro_ecu": 5.0,
    "liga_1_peru": 5.0,
    # Europa (más tácticas, menos tarjetas)
    "premier_league": 3.5,
    "laliga": 4.0,
    "bundesliga": 3.5,
    "serie_a": 4.0,
    # Norteamérica
    "mls": 4.0,
    # Europa del Norte
    "allsvenskan": 3.5,
    "superliga_den": 3.5,
    "super_league_sui": 3.5,
}


def get_cards_line(league_key: str) -> float:
    """Retorna la línea de tarjetas para una liga específica."""
    return CARDS_LINE_BY_LEAGUE.get(league_key, CARDS_LINE_DEFAULT)

# ── Score de Confianza ────────────────────────────────────────────────────────
CONFIDENCE_WEIGHTS = {
    "strength_reliability":    0.35,  # ¿Los dos equipos tienen >= MIN_MATCHES?
    "form_data_completeness":  0.25,  # ¿Hay datos de forma de los últimos 5 partidos?
    "h2h_available":           0.20,  # ¿Hay historial H2H?
    "season_maturity":         0.20,  # ¿Han jugado suficientes jornadas?
}
