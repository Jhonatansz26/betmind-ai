from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MatchBase(BaseModel):
    external_id: int
    league: str
    home_team: str
    away_team: str
    match_date: datetime
    status: str = "SCHEDULED"


class MatchCreate(MatchBase):
    pass


class MatchResponse(MatchBase):
    id: int
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MatchListResponse(BaseModel):
    matches: list[MatchResponse]
    total: int
