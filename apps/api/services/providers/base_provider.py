from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class RawFixture:
    external_id: int
    league_code: str
    league_name: str
    home_team: str
    home_team_external_id: int
    away_team: str
    away_team_external_id: int
    match_date: datetime
    status: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    went_to_extra_time: bool = False
    regulation_time_only: bool = True
    matchday: Optional[int] = None
    home_logo: Optional[str] = None
    away_logo: Optional[str] = None


@dataclass(frozen=True)
class RawTeam:
    external_id: int
    name: str
    league_code: str
    logo_url: Optional[str] = None
    country: Optional[str] = None
    venue: Optional[str] = None
    founded: Optional[int] = None


class DataProviderPort(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def get_finished_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 50,
    ) -> list[RawFixture]:
        ...

    @abstractmethod
    async def get_teams(
        self,
        league_code: str,
        season: int,
    ) -> list[RawTeam]:
        ...

    @abstractmethod
    async def get_upcoming_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 20,
    ) -> list[RawFixture]:
        ...

    @abstractmethod
    async def get_leagues(self) -> list[dict]:
        ...

    async def close(self) -> None:
        pass
