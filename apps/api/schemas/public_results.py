"""Schemas de la sección pública "Resultados" (featured_tickets)."""
from pydantic import BaseModel

from apps.api.schemas.ticket import TicketMode


class FeaturedTicketLegOut(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    league: str
    market_name: str
    market_label: str
    our_probability: float
    bookmaker_odds: float


class FeaturedTicketOut(BaseModel):
    id: int
    mode: TicketMode
    mode_label: str
    combined_odds: float
    real_ev: float
    status: str
    legs: list[FeaturedTicketLegOut]

    model_config = {"from_attributes": True}


class ResultsSummary(BaseModel):
    """Resumen agregado para una ventana de días (7 / 30)."""

    total: int
    resolved: int
    won: int
    lost: int
    pending: int
    win_rate: float | None = None


class PublicResultsResponse(BaseModel):
    date: str
    tickets: list[FeaturedTicketOut]
    summary_7d: ResultsSummary
    summary_30d: ResultsSummary