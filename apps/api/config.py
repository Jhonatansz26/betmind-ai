import logging
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _find_env_files() -> list[Path]:
    """
    Busca archivos .env en multiples ubicaciones.
    Prioridad: apps/api/.env > betmind-ai/.env (raiz del monorepo)
    """
    env_files = []
    
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent
    
    candidate_paths = [
        current_dir / ".env",
        project_root / ".env",
    ]
    
    for path in candidate_paths:
        if path.exists() and path.is_file():
            env_files.append(path)
            logger.debug(f"Found .env file at: {path}")
    
    if not env_files:
        logger.warning(
            f"No .env file found. Searched in: {[str(p) for p in candidate_paths]}"
        )
    
    return env_files


class Settings(BaseSettings):
    APP_NAME: str = "BetMind AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite+aiosqlite:///./betmind.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    API_FOOTBALL_KEY: str = ""
    FOOTBALL_DATA_KEY: str | None = None
    GROQ_API_KEY: str = ""
    GROQ_API_KEYS: str = ""
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ADMIN_API_KEY: str = ""

    GROQ_TIMEOUT_SECONDS: float = 90.0
    GROQ_SINGLE_CALL_TIMEOUT: float = 25.0
    GROQ_NARRATIVE_TIMEOUT: float = 80.0

    model_config = {
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "case_sensitive": True,
    }

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: Any) -> str:
        """
        Normaliza DATABASE_URL para usar driver asincrono.
        Convierte postgresql:// o postgres:// a postgresql+asyncpg://
        """
        if not isinstance(v, str):
            return v
        
        v = v.strip()
        
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            logger.info("Normalized DATABASE_URL: postgres:// -> postgresql+asyncpg://")
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            logger.info("Normalized DATABASE_URL: postgresql:// -> postgresql+asyncpg://")
        elif v.startswith("postgresql+asyncpg://"):
            pass
        elif v.startswith("sqlite"):
            pass
        else:
            logger.warning(f"Unknown DATABASE_URL scheme: {v[:50]}...")
        
        return v

    def __init__(self, **kwargs: Any):
        env_files = _find_env_files()
        
        if env_files:
            self.model_config["env_file"] = str(env_files[0])
            logger.info(f"Loading .env from: {env_files[0]}")
        else:
            logger.warning("No .env file found, using default values")
        
        super().__init__(**kwargs)
        
        logger.info(f"DATABASE_URL: {self.DATABASE_URL[:80]}...")

    def get_groq_api_keys(self) -> list[str]:
        """
        Retorna lista de API keys de Groq.
        Prioriza GROQ_API_KEYS (lista separada por comas) sobre GROQ_API_KEY.
        """
        if self.GROQ_API_KEYS:
            keys = [k.strip() for k in self.GROQ_API_KEYS.split(",") if k.strip()]
            if keys:
                return keys
        if self.GROQ_API_KEY:
            return [self.GROQ_API_KEY]
        return []


settings = Settings()


# ─────────────────────────────────────────────────────────────────────────────
# CATALOGO MASTER DE LIGAS ACTIVAS
# match_type: "LEAGUE" | "KNOCKOUT_CUP"
# ─────────────────────────────────────────────────────────────────────────────

FEATURED_LEAGUES: dict[str, dict] = {
    # ========================= LATAM ======================================
    "liga_betplay": {
        "api_football_id": 239,
        "name": "Liga BetPlay Dimayor",
        "country": "Colombia",
        "match_type": "LEAGUE",
    },
    "copa_colombia": {
        "api_football_id": 241,
        "name": "Copa Colombia",
        "country": "Colombia",
        "match_type": "KNOCKOUT_CUP",
    },
    "liga_profesional_arg": {
        "api_football_id": 128,
        "name": "Liga Profesional",
        "country": "Argentina",
        "match_type": "LEAGUE",
    },
    "copa_arg": {
        "api_football_id": 130,
        "name": "Copa de la Liga Profesional",
        "country": "Argentina",
        "match_type": "KNOCKOUT_CUP",
    },
    "serie_a_bra": {
        "api_football_id": 71,
        "name": "Serie A",
        "country": "Brasil",
        "match_type": "LEAGUE",
    },
    "serie_b_bra": {
        "api_football_id": 72,
        "name": "Serie B",
        "country": "Brasil",
        "match_type": "LEAGUE",
    },
    "copa_do_brasil": {
        "api_football_id": 73,
        "name": "Copa do Brasil",
        "country": "Brasil",
        "match_type": "KNOCKOUT_CUP",
    },
    "liga_mx": {
        "api_football_id": 262,
        "name": "Liga MX",
        "country": "Mexico",
        "match_type": "LEAGUE",
    },
    "mls": {
        "api_football_id": 253,
        "name": "Major League Soccer",
        "country": "USA",
        "match_type": "LEAGUE",
    },
    "mls_open_cup": {
        "api_football_id": 254,
        "name": "US Open Cup",
        "country": "USA",
        "match_type": "KNOCKOUT_CUP",
    },
    "libertadores": {
        "api_football_id": 13,
        "name": "CONMEBOL Libertadores",
        "country": "Sudamerica",
        "match_type": "KNOCKOUT_CUP",
    },
    "sudamericana": {
        "api_football_id": 11,
        "name": "CONMEBOL Sudamericana",
        "country": "Sudamerica",
        "match_type": "KNOCKOUT_CUP",
    },
    "liga_pro_ecu": {
        "api_football_id": 275,
        "name": "Liga Pro",
        "country": "Ecuador",
        "match_type": "LEAGUE",
    },
    "primera_chile": {
        "api_football_id": 274,
        "name": "Primera Division",
        "country": "Chile",
        "match_type": "LEAGUE",
    },
    "liga_1_peru": {
        "api_football_id": 281,
        "name": "Liga 1 Peru",
        "country": "Peru",
        "match_type": "LEAGUE",
    },
    # ========================= EUROPA TOP =================================
    "premier_league": {
        "api_football_id": 39,
        "name": "Premier League",
        "country": "England",
        "match_type": "LEAGUE",
    },
    "efl_championship": {
        "api_football_id": 40,
        "name": "EFL Championship",
        "country": "England",
        "match_type": "LEAGUE",
    },
    "laliga": {
        "api_football_id": 140,
        "name": "LaLiga",
        "country": "Spain",
        "match_type": "LEAGUE",
    },
    "laliga_hypermotion": {
        "api_football_id": 141,
        "name": "LaLiga Hypermotion",
        "country": "Spain",
        "match_type": "LEAGUE",
    },
    "bundesliga": {
        "api_football_id": 78,
        "name": "Bundesliga",
        "country": "Germany",
        "match_type": "LEAGUE",
    },
    "serie_a": {
        "api_football_id": 135,
        "name": "Serie A",
        "country": "Italy",
        "match_type": "LEAGUE",
    },
    "ligue_1": {
        "api_football_id": 61,
        "name": "Ligue 1",
        "country": "France",
        "match_type": "LEAGUE",
    },
    "eredivisie": {
        "api_football_id": 88,
        "name": "Eredivisie",
        "country": "Netherlands",
        "match_type": "LEAGUE",
    },
    "ucl": {
        "api_football_id": 2,
        "name": "UEFA Champions League",
        "country": "Europa",
        "match_type": "KNOCKOUT_CUP",
    },
    "uel": {
        "api_football_id": 3,
        "name": "UEFA Europa League",
        "country": "Europa",
        "match_type": "KNOCKOUT_CUP",
    },
    "uecl": {
        "api_football_id": 848,
        "name": "UEFA Conference League",
        "country": "Europa",
        "match_type": "KNOCKOUT_CUP",
    },
}

FEATURED_LEAGUE_IDS: list[int] = [
    league["api_football_id"] for league in FEATURED_LEAGUES.values()
]

# IDs de ligas que son eliminatorias/copas (para asignacion automatica de match_type)
KNOCKOUT_CUP_LEAGUE_IDS: set[int] = {
    info["api_football_id"]
    for info in FEATURED_LEAGUES.values()
    if info.get("match_type") == "KNOCKOUT_CUP"
}
