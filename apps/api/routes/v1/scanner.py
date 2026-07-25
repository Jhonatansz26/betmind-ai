from fastapi import APIRouter

from apps.api.schemas.scanner import ScannerRequest, ScannerResponse

router = APIRouter()


@router.post("/", response_model=ScannerResponse)
async def scan_opportunities(request: ScannerRequest):
    return ScannerResponse(
        opportunities=[],
        total=0,
        scanned_at="2024-01-01T00:00:00",
    )
