from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_async_session, get_current_user_id
from apps.api.models.bankroll import Bankroll, BankrollMovement
from apps.api.schemas.bankroll import (
    BankrollAdjust,
    BankrollPatch,
    BankrollResponse,
    BankrollSetup,
    MovementOut,
)

router = APIRouter()


async def _get_bankroll_or_404(
    user_id: int,
    session: AsyncSession,
    *,
    for_update: bool = False,
) -> Bankroll:
    query = select(Bankroll).where(Bankroll.user_id == user_id)
    if for_update:
        query = query.with_for_update()
    result = await session.execute(query)
    bankroll = result.scalar_one_or_none()
    if bankroll is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no tiene un bankroll configurado todavía.",
        )
    return bankroll


async def _load_bankroll_response(bankroll: Bankroll, session: AsyncSession) -> BankrollResponse:
    """Fetch movements and build the full response object."""
    movements_result = await session.execute(
        select(BankrollMovement)
        .where(BankrollMovement.bankroll_id == bankroll.id)
        .order_by(BankrollMovement.created_at.desc())
    )
    movements = movements_result.scalars().all()
    return BankrollResponse(
        id=bankroll.id,
        current_capital=bankroll.current_capital,
        risk_profile=bankroll.risk_profile,
        created_at=bankroll.created_at,
        movements=[MovementOut.model_validate(m) for m in movements],
    )


@router.post("/setup", response_model=BankrollResponse)
async def setup_bankroll(
    body: BankrollSetup,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> BankrollResponse:
    """Initialize a bankroll for the authenticated user.

    Returns 409 if the user already has one.
    """
    existing = await session.execute(
        select(Bankroll.id).where(Bankroll.user_id == user_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tienes un bankroll configurado. Usa PATCH /bankroll para modificarlo.",
        )

    bankroll = Bankroll(
        user_id=user_id,
        current_capital=body.initial_capital,
        risk_profile=body.risk_profile,
    )
    session.add(bankroll)
    await session.flush()  # populate bankroll.id

    # Record the initial deposit as a movement
    movement = BankrollMovement(
        bankroll_id=bankroll.id,
        type="manual_adjustment",
        amount=body.initial_capital,
        reason="Capital inicial",
    )
    session.add(movement)
    await session.commit()

    return await _load_bankroll_response(bankroll, session)


@router.get("", response_model=BankrollResponse)
async def get_bankroll(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> BankrollResponse:
    """Return the current bankroll state with full movement history."""
    bankroll = await _get_bankroll_or_404(user_id, session)
    return await _load_bankroll_response(bankroll, session)


@router.patch("", response_model=BankrollResponse)
async def patch_bankroll(
    body: BankrollPatch,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> BankrollResponse:
    """Update mutable bankroll fields (currently: risk_profile)."""
    bankroll = await _get_bankroll_or_404(user_id, session)

    if body.risk_profile is not None:
        bankroll.risk_profile = body.risk_profile

    await session.commit()
    return await _load_bankroll_response(bankroll, session)


@router.post("/adjust", response_model=BankrollResponse)
async def adjust_bankroll(
    body: BankrollAdjust,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> BankrollResponse:
    """Record a manual capital adjustment (deposit or withdrawal).

    Positive ``amount`` = deposit, negative = withdrawal.
    Capital cannot go below zero.
    """
    bankroll = await _get_bankroll_or_404(user_id, session, for_update=True)

    new_capital = bankroll.current_capital + body.amount
    if new_capital < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El retiro de {body.amount} dejaría el capital en negativo ({new_capital:.2f}).",
        )

    bankroll.current_capital = new_capital
    movement = BankrollMovement(
        bankroll_id=bankroll.id,
        type="manual_adjustment",
        amount=body.amount,
        reason=body.reason,
    )
    session.add(movement)
    await session.commit()

    return await _load_bankroll_response(bankroll, session)
