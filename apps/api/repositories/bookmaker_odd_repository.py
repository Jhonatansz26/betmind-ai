import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.bookmaker_odd import BookmakerOdd

logger = logging.getLogger(__name__)

# Fuentes de cuotas activas. API-Football fue la fuente historica; ESPN
# (sin API key) cubre 1X2 + Over/Under y SofaScore los mercados especiales
# (córneres, tarjetas, remates, BTTS). Las lecturas consideran todas.
ESPN_BOOKMAKER_NAME = "espn"
SOFASCORE_BOOKMAKER_NAME = "sofascore"
DEFAULT_BOOKMAKER_NAMES: tuple[str, ...] = (
    "api_football",
    ESPN_BOOKMAKER_NAME,
    SOFASCORE_BOOKMAKER_NAME,
)


class BookmakerOddsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_odds(
        self,
        match_id: int,
        odds_list: list[dict],
        bookmaker_name: str = "api_football",
    ) -> int:
        count = 0
        for odd_data in odds_list:
            market_name = odd_data["market_name"]
            odds_value = odd_data["odds_value"]
            external_fixture_id = odd_data.get("external_fixture_id")

            stmt = select(BookmakerOdd).where(
                and_(
                    BookmakerOdd.match_id == match_id,
                    BookmakerOdd.market_name == market_name,
                    BookmakerOdd.bookmaker_name == bookmaker_name,
                )
            )
            result = await self._session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # UPDATE in-place: se refresca la cuota actual pero NUNCA se
                # toca la línea de apertura (opening_odds_value y
                # opening_odds_captured_at se escriben una sola vez, al crear).
                existing.odds_value = odds_value
                existing.external_fixture_id = external_fixture_id
                existing.fetched_at = datetime.now(timezone.utc)
            else:
                new_odd = BookmakerOdd(
                    match_id=match_id,
                    market_name=market_name,
                    bookmaker_name=bookmaker_name,
                    odds_value=odds_value,
                    external_fixture_id=external_fixture_id,
                    # Línea de apertura verdadera: solo el primer insert.
                    opening_odds_value=odds_value,
                    opening_odds_captured_at=datetime.now(timezone.utc),
                )
                self._session.add(new_odd)
            count += 1

        await self._session.flush()
        logger.info(f"Upserted {count} odds for match_id={match_id}")
        return count

    async def get_odds_for_match(
        self,
        match_id: int,
        bookmaker_names: tuple[str, ...] = DEFAULT_BOOKMAKER_NAMES,
    ) -> list[BookmakerOdd]:
        stmt = (
            select(BookmakerOdd)
            .where(
                and_(
                    BookmakerOdd.match_id == match_id,
                    BookmakerOdd.bookmaker_name.in_(bookmaker_names),
                )
            )
            .order_by(BookmakerOdd.bookmaker_name, BookmakerOdd.market_name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_opening_odds_for_match(
        self,
        match_id: int,
        bookmaker_names: tuple[str, ...] = DEFAULT_BOOKMAKER_NAMES,
    ) -> list[BookmakerOdd]:
        """
        Línea de apertura verdadera por mercado: filas con
        opening_odds_value no nulo (primer sync de cada (match_id, market)).
        Filas creadas antes de la migración 021 quedan con NULL y se omiten.
        """
        stmt = (
            select(BookmakerOdd)
            .where(
                and_(
                    BookmakerOdd.match_id == match_id,
                    BookmakerOdd.bookmaker_name.in_(bookmaker_names),
                    BookmakerOdd.opening_odds_value.is_not(None),
                )
            )
            .order_by(BookmakerOdd.bookmaker_name, BookmakerOdd.market_name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_odds_for_matches(
        self,
        match_ids: list[int],
        bookmaker_names: tuple[str, ...] = DEFAULT_BOOKMAKER_NAMES,
    ) -> dict[int, list[BookmakerOdd]]:
        if not match_ids:
            return {}

        stmt = (
            select(BookmakerOdd)
            .where(
                and_(
                    BookmakerOdd.match_id.in_(match_ids),
                    BookmakerOdd.bookmaker_name.in_(bookmaker_names),
                )
            )
            .order_by(BookmakerOdd.match_id, BookmakerOdd.bookmaker_name, BookmakerOdd.market_name)
        )
        result = await self._session.execute(stmt)
        odds = list(result.scalars().all())

        grouped: dict[int, list[BookmakerOdd]] = {}
        for odd in odds:
            grouped.setdefault(odd.match_id, []).append(odd)
        return grouped
