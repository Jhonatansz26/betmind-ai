from __future__ import annotations

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models import Base, Bankroll, BankrollMovement, SavedTicket, User
from apps.api.repositories.ticket_repository import TicketRepository, TicketStatusConflict


@pytest.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session
    await engine.dispose()


async def _create_ticket(
    session,
    *,
    user_id: int,
    stake_amount: float | None = 100.0,
    total_odds: float = 3.5,
) -> SavedTicket:
    ticket = SavedTicket(
        ticket_data={"mode": "edge"},
        status="PENDING",
        total_odds=total_odds,
        total_ev=0.2,
        stake_amount=stake_amount,
        user_id=user_id,
    )
    session.add(ticket)
    await session.flush()
    return ticket


@pytest.fixture
async def user_and_bankroll(session):
    user = User(
        email="bankroll-test@example.com",
        hashed_password="not-a-real-password",
    )
    session.add(user)
    await session.flush()
    bankroll = Bankroll(user_id=user.id, current_capital=1000.0)
    session.add(bankroll)
    await session.commit()
    return user, bankroll


@pytest.mark.asyncio
async def test_status_update_creates_correct_won_movement_atomically(
    session, user_and_bankroll
):
    user, bankroll = user_and_bankroll
    ticket = await _create_ticket(session, user_id=user.id)

    updated, movement = await TicketRepository(session).update_status_with_movement(
        ticket.id, "WON", user.id
    )
    await session.commit()

    assert updated.status == "WON"
    assert movement is not None
    assert movement.type == "ticket_won"
    assert movement.amount == pytest.approx(250.0)
    await session.refresh(bankroll)
    assert bankroll.current_capital == pytest.approx(1250.0)


@pytest.mark.asyncio
async def test_lost_and_void_amounts_and_missing_configuration(session):
    user = User(email="no-bankroll@example.com", hashed_password="password")
    session.add(user)
    await session.flush()
    ticket_without_bankroll = await _create_ticket(session, user_id=user.id)

    updated, movement = await TicketRepository(session).update_status_with_movement(
        ticket_without_bankroll.id, "LOST", user.id
    )
    await session.commit()
    assert updated.status == "LOST"
    assert movement is None

    bankroll = Bankroll(user_id=user.id, current_capital=1000.0)
    session.add(bankroll)
    void_ticket = await _create_ticket(session, user_id=user.id, stake_amount=50.0)
    updated, movement = await TicketRepository(session).update_status_with_movement(
        void_ticket.id, "VOID", user.id
    )
    await session.commit()

    assert updated.status == "VOID"
    assert movement is not None
    assert movement.type == "ticket_void"
    assert movement.amount == 0.0
    await session.refresh(bankroll)
    assert bankroll.current_capital == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_status_update_is_idempotent_and_rejects_a_different_second_result(
    session, user_and_bankroll
):
    user, bankroll = user_and_bankroll
    ticket = await _create_ticket(session, user_id=user.id)
    ticket_id = ticket.id
    repository = TicketRepository(session)

    _, first_movement = await repository.update_status_with_movement(ticket.id, "WON", user.id)
    await session.commit()
    _, repeated_movement = await repository.update_status_with_movement(
        ticket.id, "WON", user.id
    )

    assert repeated_movement is not None
    assert repeated_movement.id == first_movement.id
    with pytest.raises(TicketStatusConflict):
        await repository.update_status_with_movement(ticket.id, "LOST", user.id)
    await session.rollback()

    movements = (
        await session.execute(
            select(BankrollMovement).where(BankrollMovement.ticket_id == ticket_id)
        )
    ).scalars().all()
    await session.refresh(bankroll)
    assert len(movements) == 1
    assert bankroll.current_capital == pytest.approx(1250.0)


@pytest.mark.asyncio
async def test_movement_failure_rolls_back_ticket_and_capital(session, user_and_bankroll):
    user, bankroll = user_and_bankroll
    ticket = await _create_ticket(session, user_id=user.id)
    ticket_id = ticket.id
    bankroll_id = bankroll.id
    await session.commit()

    def fail_before_insert(*_args, **_kwargs):
        raise RuntimeError("simulated movement insert failure")

    event.listen(BankrollMovement, "before_insert", fail_before_insert)
    try:
        with pytest.raises(RuntimeError, match="simulated movement insert failure"):
            await TicketRepository(session).update_status_with_movement(
                ticket.id, "LOST", user.id
            )
    finally:
        event.remove(BankrollMovement, "before_insert", fail_before_insert)

    await session.rollback()
    persisted_ticket = (
        await session.execute(select(SavedTicket).where(SavedTicket.id == ticket_id))
    ).scalar_one()
    persisted_bankroll = (
        await session.execute(select(Bankroll).where(Bankroll.id == bankroll_id))
    ).scalar_one()
    assert persisted_ticket.status == "PENDING"
    assert persisted_bankroll.current_capital == pytest.approx(1000.0)
    movements = (
        await session.execute(
            select(BankrollMovement).where(BankrollMovement.ticket_id == ticket_id)
        )
    ).scalars().all()
    assert movements == []
