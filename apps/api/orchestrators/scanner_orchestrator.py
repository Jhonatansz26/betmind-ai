from apps.api.core.result import Ok, Err
from apps.api.models.match import Match
from apps.api.schemas.scanner import ScannerMatchItem, ScannerResponse
from apps.api.repositories.match_repository import MatchRepository


class ScannerOrchestrator:
    def __init__(
        self,
        match_repo: MatchRepository,
    ):
        self._match_repo = match_repo

    async def scan_opportunities(
        self,
        league: str | None = None,
        min_value_score: float = 0.6,
        limit: int = 10,
    ) -> Ok[ScannerResponse] | Err:
        try:
            from datetime import datetime

            return Ok(
                value=ScannerResponse(
                    opportunities=[],
                    total=0,
                    scanned_at=datetime.utcnow().isoformat(),
                )
            )

        except Exception as e:
            return Err(message=str(e), code="SCANNER_ERROR")
