"""
Proveedor de búsqueda web en vivo para enriquecer narrativas.
Usa DuckDuckGo para extraer noticias, bajas y alineaciones recientes.
"""
import asyncio
import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


async def fetch_match_live_context(home_team: str, away_team: str, league_name: str) -> str:
    """
    Busca noticias recientes, bajas de ultima hora y alineaciones.
    Ejecuta la busqueda en un thread sincrono con control de errores.
    """
    query = f"{home_team} vs {away_team} {league_name} bajas lesionados alineaciones noticias"

    def _search() -> str:
        snippets = []
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                for r in results:
                    title = r.get("title", "")
                    body = r.get("body", "")
                    if body:
                        snippets.append(f"- {title}: {body}")
            return "\n".join(snippets) if snippets else "Sin noticias recientes de impacto encontradas."
        except Exception as e:
            logger.warning("Busqueda web no disponible para %s vs %s: %s", home_team, away_team, e)
            return "Informacion web no disponible temporalmente."

    await asyncio.sleep(1.2)
    return await asyncio.to_thread(_search)
