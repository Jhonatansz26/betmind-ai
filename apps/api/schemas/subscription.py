from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Plan = Literal["mensual", "anual"]
SubscriptionStatus = Literal[
    "trial",
    "pending_payment",
    "active",
    "past_due",
    "cancelled",
    "cancellation_pending",
    "refund_requested",
]


class SubscriptionTrialResponse(BaseModel):
    id: int
    plan: Plan
    status: SubscriptionStatus
    current_period_end: datetime
    trial_ends_at: datetime | None = None
    recurrence_enabled: bool | None = None
    last_transaction: "LastSubscriptionTransactionResponse | None" = None
    refund_eligible: bool = False

    model_config = {"from_attributes": True}


class LastSubscriptionTransactionResponse(BaseModel):
    id: str
    status: str
    status_message: str | None = None
    processor_response_code: str | None = None


class SubscriptionActivateRequest(BaseModel):
    card_token: str = Field(min_length=1, max_length=255)
    plan: Plan
    acceptance_token: str = Field(min_length=1)
    accept_personal_auth: str = Field(min_length=1)


class SubscriptionActivationResponse(SubscriptionTrialResponse):
    transaction_id: str
    transaction_status: str


class SubscriptionCancelResponse(SubscriptionTrialResponse):
    pass


class SubscriptionRefundResponse(SubscriptionTrialResponse):
    pass
