import pytest

from apps.api.repositories.ticket_repository import TicketRepository


class _Result:
    rowcount = 1


class _ReturningResult:
    def __init__(self, ids):
        self._ids = ids

    def scalars(self):
        return self

    def all(self):
        return self._ids


class _Session:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Result()


@pytest.mark.asyncio
async def test_claim_anonymous_tickets_is_single_atomic_owner_update():
    session = _Session()
    claimed = await TicketRepository(session).claim_anonymous_tickets([17, 18], user_id=42)

    assert claimed == 1
    assert len(session.statements) == 1
    statement = session.statements[0]
    where_sql = " ".join(str(criteria) for criteria in statement._where_criteria)
    assert "saved_tickets.user_id IS NULL" in where_sql
    assert "saved_tickets.id IN" in where_sql


@pytest.mark.asyncio
async def test_claim_anonymous_ticket_ids_returns_only_updated_ids():
    class _ReturningSession(_Session):
        async def execute(self, statement):
            self.statements.append(statement)
            return _ReturningResult([17, 19])

    session = _ReturningSession()
    claimed_ids = await TicketRepository(session).claim_anonymous_ticket_ids(
        [17, 18, 19], user_id=42
    )

    assert claimed_ids == [17, 19]
    assert len(session.statements) == 1
    assert session.statements[0]._returning
