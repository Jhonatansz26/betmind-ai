from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ScannerRequest(BaseModel):
    league: Optional[str] = None
    min_value_score: float = Field(default=0.6, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=50)


class ScannerMatchItem(BaseModel):
    match_id: int
    league: str
    home_team: str
    away_team: str
    market: str
    value_score: float
    confidence: str


class ScannerResponse(BaseModel):
    opportunities: list[ScannerMatchItem]
    total: int
    scanned_at: str
