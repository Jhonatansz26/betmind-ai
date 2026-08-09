from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

MovementType = Literal["ticket_won", "ticket_lost", "ticket_void", "manual_adjustment"]
RiskProfile = Literal["conservador", "moderado", "agresivo"]


class BankrollSetup(BaseModel):
    initial_capital: float = Field(gt=0, description="Capital inicial en COP")
    risk_profile: RiskProfile = "moderado"


class BankrollPatch(BaseModel):
    risk_profile: Optional[RiskProfile] = None


class BankrollAdjust(BaseModel):
    amount: float = Field(description="Positivo = depósito, negativo = retiro")
    reason: str = Field(max_length=500)


class MovementOut(BaseModel):
    id: int
    type: MovementType
    amount: float
    ticket_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BankrollResponse(BaseModel):
    id: int
    current_capital: float
    risk_profile: str
    created_at: datetime
    movements: List[MovementOut] = []

    model_config = {"from_attributes": True}
