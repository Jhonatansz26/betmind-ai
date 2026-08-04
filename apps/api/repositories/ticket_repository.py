from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.ticket import SavedTicket


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        ticket_data: dict,
        total_odds: float,
        total_ev: float,
        status: str = "PENDING",
    ) -> SavedTicket:
        ticket = SavedTicket(
            ticket_data=ticket_data,
            total_odds=total_odds,
            total_ev=total_ev,
            status=status,
        )
        self._session.add(ticket)
        await self._session.flush()
        await self._session.refresh(ticket)
        return ticket

    async def list_history(self, limit: int = 100) -> list[SavedTicket]:
        result = await self._session.execute(
            select(SavedTicket)
            .order_by(SavedTicket.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_id(self, ticket_id: int) -> SavedTicket | None:
        result = await self._session.execute(
            select(SavedTicket).where(SavedTicket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, ticket_id: int, status: str) -> SavedTicket | None:
        ticket = await self.get_by_id(ticket_id)
        if ticket is None:
            return None
        ticket.status = status
        await self._session.flush()
        await self._session.refresh(ticket)
        return ticket
