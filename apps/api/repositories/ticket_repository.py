from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.bankroll import Bankroll, BankrollMovement
from apps.api.models.ticket import SavedTicket


class TicketStatusConflict(Exception):
    """Raised when a ticket with an existing bankroll movement is changed."""


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        ticket_data: dict,
        total_odds: float,
        total_ev: float,
        stake_amount: float | None = None,
        status: str = "PENDING",
        user_id: int | None = None,
    ) -> SavedTicket:
        ticket = SavedTicket(
            ticket_data=ticket_data,
            total_odds=total_odds,
            total_ev=total_ev,
            stake_amount=stake_amount,
            status=status,
            user_id=user_id,
        )
        self._session.add(ticket)
        await self._session.flush()
        await self._session.refresh(ticket)
        return ticket

    async def list_history(self, user_id: int, limit: int = 100) -> list[SavedTicket]:
        result = await self._session.execute(
            select(SavedTicket).where(SavedTicket.user_id == user_id)
            .order_by(SavedTicket.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_id(self, ticket_id: int, user_id: int | None = None) -> SavedTicket | None:
        conditions = [SavedTicket.id == ticket_id]
        if user_id is not None:
            conditions.append(SavedTicket.user_id == user_id)
        result = await self._session.execute(
            select(SavedTicket).where(*conditions)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        ticket_id: int,
        status: str,
        user_id: int,
    ) -> SavedTicket | None:
        """Update a ticket while preserving the repository's old return shape."""
        result = await self.update_status_with_movement(ticket_id, status, user_id)
        return result[0] if result is not None else None

    async def update_status_with_movement(
        self,
        ticket_id: int,
        status: str,
        user_id: int,
    ) -> tuple[SavedTicket, BankrollMovement | None] | None:
        """Update status and bankroll in one caller-owned transaction.

        This method deliberately does not commit. The API session commits only
        after the handler returns, so any failure rolls back both writes.
        """
        # Lock the ticket first so concurrent status updates cannot both create
        # a movement for the same ticket.
        result = await self._session.execute(
            select(SavedTicket)
            .where(SavedTicket.id == ticket_id, SavedTicket.user_id == user_id)
            .with_for_update()
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            return None

        movement_result = await self._session.execute(
            select(BankrollMovement)
            .where(BankrollMovement.ticket_id == ticket.id)
            .order_by(BankrollMovement.created_at.desc())
            .with_for_update()
        )
        existing_movement = movement_result.scalars().first()
        if existing_movement is not None:
            if ticket.status == status and status in {"WON", "LOST", "VOID"}:
                await self._session.refresh(ticket)
                await self._session.refresh(existing_movement)
                return ticket, existing_movement
            raise TicketStatusConflict(
                "El ticket ya tiene un movimiento de bankroll y no puede cambiar de estado."
            )

        if ticket.status == status:
            await self._session.refresh(ticket)
            return ticket, None

        ticket.status = status
        movement = None

        if status in {"WON", "LOST", "VOID"} and ticket.stake_amount is not None:
            bankroll_result = await self._session.execute(
                select(Bankroll)
                .where(Bankroll.user_id == user_id)
                .with_for_update()
            )
            bankroll = bankroll_result.scalar_one_or_none()
            if bankroll is not None:
                if status == "WON":
                    amount = ticket.stake_amount * (ticket.total_odds - 1)
                    movement_type = "ticket_won"
                elif status == "LOST":
                    amount = -ticket.stake_amount
                    movement_type = "ticket_lost"
                else:
                    amount = 0.0
                    movement_type = "ticket_void"

                movement = BankrollMovement(
                    bankroll_id=bankroll.id,
                    type=movement_type,
                    amount=amount,
                    ticket_id=ticket.id,
                    created_at=datetime.now(timezone.utc),
                )
                self._session.add(movement)
                bankroll.current_capital += amount

        await self._session.flush()
        await self._session.refresh(ticket)
        if movement is not None:
            await self._session.refresh(movement)
        return ticket, movement

    async def claim_anonymous_tickets(self, ticket_ids: list[int], user_id: int) -> int:
        """Claim anonymous tickets and preserve the legacy count-only API."""
        if not ticket_ids:
            return 0
        result = await self._session.execute(
            update(SavedTicket)
            .where(
                SavedTicket.id.in_(ticket_ids),
                SavedTicket.user_id.is_(None),
            )
            .values(user_id=user_id)
        )
        return result.rowcount or 0

    async def claim_anonymous_ticket_ids(self, ticket_ids: list[int], user_id: int) -> list[int]:
        """Return only the IDs whose anonymous owner was changed."""
        if not ticket_ids:
            return []
        result = await self._session.execute(
            update(SavedTicket)
            .where(
                SavedTicket.id.in_(ticket_ids),
                SavedTicket.user_id.is_(None),
            )
            .values(user_id=user_id)
            .returning(SavedTicket.id)
        )
        return list(result.scalars().all())
