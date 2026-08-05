from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from enum import Enum


class TicketMode(str, Enum):
    EDGE = "edge"
    VALUE = "value"
    BOLD = "bold"


class TicketLegSchema(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    league: str
    market_name: str
    market_label: str
    our_probability: float
    bookmaker_odds: float
    implied_probability: float
    edge_percentage: float
    expected_value: float
    kelly_stake: float = Field(0.0, ge=0, le=1, description="Quarter-Kelly stake (0-1)")
    match_time_cot: str


class GeneratedTicket(BaseModel):
    mode: TicketMode
    mode_label: str
    legs: list[TicketLegSchema]
    combined_odds: float
    average_ev: float
    kelly_stake: float = Field(0.0, ge=0, le=1, description="Combined Quarter-Kelly stake for ticket")
    confidence_score: int
    correlation_validated: bool
    tactical_summary: str
    pros: list[str]
    cons: list[str]
    staking_suggestion: str


class TicketGenerateRequest(BaseModel):
    modes: list[TicketMode] = Field(
        default=[TicketMode.EDGE, TicketMode.VALUE, TicketMode.BOLD]
    )
    league_filter: list[str] | None = None
    date: str | None = None
    force_refresh: bool = False


class TicketGenerateResponse(BaseModel):
    generated_at: str
    tickets: list[GeneratedTicket]
    total_ev_opportunities: int
    matches_analyzed: int


class SavedTicketStatus(str, Enum):
    PENDING = "PENDING"
    WON = "WON"
    LOST = "LOST"
    VOID = "VOID"


class SaveTicketRequest(BaseModel):
    ticket_data: dict[str, Any]
    total_odds: float = Field(..., gt=1.0)
    total_ev: float


class UpdateTicketStatusRequest(BaseModel):
    status: SavedTicketStatus


class ClaimTicketsRequest(BaseModel):
    ticket_ids: list[int] = Field(default_factory=list)


class ClaimTicketsResponse(BaseModel):
    claimed_count: int
    message: str


class SavedTicketResponse(BaseModel):
    id: int
    ticket_data: dict[str, Any]
    status: SavedTicketStatus
    total_odds: float
    total_ev: float
    created_at: datetime

    model_config = {"from_attributes": True}
