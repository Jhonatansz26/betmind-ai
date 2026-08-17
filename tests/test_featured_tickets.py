"""
Tests de la sección pública "Resultados" (featured_tickets).

Cubre:
  - Job de generación diaria: persiste boletos con snapshot inmutable y
    status PENDING, uno por modo, sin recalcular si el día ya existe.
  - Job de resolución contra prediction_outcomes: todas WON -> WON, una LOST
    -> LOST de inmediato (sin esperar a las demás), faltan patas -> PENDING.
  - Endpoint público GET /public/results?date=YYYY-MM-DD (sin auth) con el
    resumen agregado de 7/30 días.
"""
import asyncio
import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.api.dependencies import get_async_session
from apps.api.models import Base
from apps.api.models.bookmaker_odd import BookmakerOdd
from apps.api.models.featured_ticket import FeaturedTicket
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.prediction import Prediction
from apps.api.models.prediction_outcome import PredictionOutcome
from apps.api.models.team import Team
from apps.api.routes.v1.public_results import router as public_results_router

import apps.api.jobs.generate_featured_tickets as generate_job
import apps.api.jobs.evaluate_predictions as evaluate_job

COT = ZoneInfo("America/Bogota")


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        # Una sola conexión compartida: las sesiones del TestClient ven los
        # datos sembrados (sqlite in-memory es per-connection por defecto).
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def _today_cot() -> str:
    return datetime.now(COT).date().isoformat()


async def _seed_matches(session):
    """3-4 partidos SCHEDULED hoy con predicciones y cuotas parlay-eligible."""
    league = League(external_id=39, name="Premier League", country="England")
    session.add(league)
    await session.flush()

    teams = [
        ("Arsenal", "Chelsea"),
        ("Liverpool", "Man City"),
        ("Tottenham", "Newcastle"),
        ("Villareal", "Valencia"),
    ]
    team_objs = []
    for idx, (home_name, away_name) in enumerate(teams):
        home = Team(external_id=900 + idx * 2, name=home_name, country="England")
        away = Team(external_id=901 + idx * 2, name=away_name, country="England")
        session.add_all([home, away])
        await session.flush()
        team_objs.append((home, away))

    markets_per_match = [
        # OVER_2_5 @ 1.75 (prob 0.62) — parlay-eligible
        [("OVER_2_5", 0.62, 1.75), ("UNDER_2_5", None, 2.05)],
        # 1X2_HOME @ 1.85 (prob 0.58) y 1X2_DRAW @ 3.20 (prob 0.38)
        [("1X2_HOME", 0.58, 1.85), ("1X2_DRAW", 0.38, 3.20), ("1X2_AWAY", None, 4.20)],
        # BTTS_YES @ 1.90 (prob 0.55)
        [("BTTS_YES", 0.55, 1.90), ("BTTS_NO", None, 2.05)],
        # OVER_3_5 @ 2.60 (prob 0.45) — solo BOLD (fuera de allowed EDGE/VALUE)
        [("OVER_3_5", 0.45, 2.60), ("UNDER_3_5", None, 2.75)],
    ]

    today = datetime.now(COT).date()
    matches = []
    for idx, ((home, away), markets) in enumerate(zip(team_objs, markets_per_match)):
        match = Match(
            external_id=8000 + idx,
            league_id=league.id,
            home_team_id=home.id,
            away_team_id=away.id,
            match_date=datetime.combine(today, time(15, 0), tzinfo=COT).astimezone(timezone.utc),
            status="SCHEDULED",
        )
        session.add(match)
        await session.flush()

        market_rows = [
            {"market_name": name, "our_probability": prob}
            for name, prob, _odds in markets
            if prob is not None
        ]
        session.add(Prediction(
            match_id=match.id,
            prediction_type="quant_v1",
            confidence="60",
            value_score=0.05,
            markets_json=json.dumps(market_rows),
        ))
        for name, _prob, odds in markets:
            session.add(BookmakerOdd(
                match_id=match.id,
                market_name=name,
                bookmaker_name="api_football",
                odds_value=odds,
                # El server_default "now()" del modelo es un literal en sqlite;
                # se fija explícitamente para no romper el parseo del DateTime.
                fetched_at=datetime.now(timezone.utc),
            ))
        matches.append(match)

    await session.commit()
    return matches


# ── Generación ───────────────────────────────────────────────────────────────

def test_generation_job_persists_one_ticket_per_mode(monkeypatch):
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            await _seed_matches(session)

        monkeypatch.setattr(generate_job, "async_session_factory", factory)
        stats = await generate_job.generate_featured_tickets()

        assert stats["generated"] == 3  # edge + value + bold

        async with factory() as session:
            tickets = (await session.execute(
                select(FeaturedTicket).order_by(FeaturedTicket.mode)
            )).scalars().all()
            by_mode = {t.mode: t for t in tickets}
            assert set(by_mode) == {"edge", "value", "bold"}

            edge = by_mode["edge"]
            assert edge.status == "PENDING"
            assert edge.ticket_date.isoformat() == _today_cot()
            assert edge.combined_odds == round(1.75 * 1.85, 2)
            assert len(edge.legs) == 2
            # Snapshot inmutable: cada pata trae cuota + probabilidad del momento.
            leg = edge.legs[0]
            for field in ("match_id", "home_team", "away_team", "league",
                          "market_name", "market_label", "our_probability",
                          "bookmaker_odds"):
                assert field in leg and leg[field] is not None
            assert leg["bookmaker_odds"] > 1.0
            assert 0.0 <= leg["our_probability"] <= 1.0

            # real_ev = P_conjunta × cuota − 1 (no el promedio viejo).
            combined_prob = 0.62 * 0.58
            assert edge.real_ev == round(combined_prob * edge.combined_odds - 1, 4)
            assert edge.real_ev > 0
        await engine.dispose()

    _run(scenario())


def test_generation_job_is_idempotent_and_keeps_snapshot(monkeypatch):
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            await _seed_matches(session)

        monkeypatch.setattr(generate_job, "async_session_factory", factory)
        first = await generate_job.generate_featured_tickets()
        second = await generate_job.generate_featured_tickets()

        assert first["generated"] == 3
        # ON CONFLICT DO NOTHING: el segundo run no re-genera ni pisa el snapshot.
        assert second["generated"] == 3
        assert second["skipped_existing"] == 3

        async with factory() as session:
            count = (await session.execute(select(FeaturedTicket.id))).scalars().all()
            assert len(count) == 3
        await engine.dispose()

    _run(scenario())


# ── Resolución ───────────────────────────────────────────────────────────────

async def _seed_featured(session, legs, status="PENDING"):
    ticket = FeaturedTicket(
        ticket_date=datetime.now(COT).date(),
        mode="edge",
        legs=legs,
        combined_odds=3.0,
        real_ev=0.1,
        status=status,
    )
    session.add(ticket)
    await session.flush()
    await session.commit()
    return ticket


def _leg(match_id: int, market: str) -> dict:
    return {
        "match_id": match_id,
        "home_team": f"Home{match_id}",
        "away_team": f"Away{match_id}",
        "league": "Premier League",
        "market_name": market,
        "market_label": market.replace("_", " ").title(),
        "our_probability": 0.6,
        "bookmaker_odds": 1.8,
    }


async def _seed_outcome(session, match_id: int, market: str, actual: str):
    session.add(PredictionOutcome(
        match_id=match_id,
        market_name=market,
        our_probability=0.6,
        actual_outcome=actual,
        brier_component=round((0.6 - (1 if actual == "WON" else 0)) ** 2, 6),
    ))
    await session.flush()


def test_resolution_all_legs_won(monkeypatch):
    """Todas las patas WON -> el boleto queda WON."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            legs = [_leg(1, "OVER_2_5"), _leg(2, "1X2_HOME"), _leg(3, "BTTS_YES")]
            ticket = await _seed_featured(session, legs)
            for i, market in enumerate(["OVER_2_5", "1X2_HOME", "BTTS_YES"]):
                await _seed_outcome(session, i + 1, market, "WON")
            await session.commit()

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        stats = await evaluate_job.resolve_featured_tickets()
        assert stats["won"] == 1
        assert stats["lost"] == 0
        assert stats["still_pending"] == 0

        async with factory() as session:
            refreshed = (await session.execute(
                select(FeaturedTicket).where(FeaturedTicket.id == ticket.id)
            )).scalar_one()
            assert refreshed.status == "WON"
            assert refreshed.resolved_at is not None
        await engine.dispose()

    _run(scenario())


def test_resolution_any_lost_marks_lost_immediately(monkeypatch):
    """Una pata LOST -> LOST apenas se detecta, sin esperar a las demás."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            legs = [_leg(1, "OVER_2_5"), _leg(2, "1X2_HOME"), _leg(3, "BTTS_YES")]
            ticket = await _seed_featured(session, legs)
            await _seed_outcome(session, 1, "OVER_2_5", "WON")
            await _seed_outcome(session, 2, "1X2_HOME", "LOST")
            # La pata 3 todavía no tiene outcome: no bloquea el LOST.
            await session.commit()

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        stats = await evaluate_job.resolve_featured_tickets()
        assert stats["lost"] == 1
        assert stats["won"] == 0

        async with factory() as session:
            refreshed = (await session.execute(
                select(FeaturedTicket).where(FeaturedTicket.id == ticket.id)
            )).scalar_one()
            assert refreshed.status == "LOST"
        await engine.dispose()

    _run(scenario())


def test_resolution_stays_pending_while_legs_unresolved(monkeypatch):
    """Falta alguna pata por resolver y ninguna perdió -> sigue PENDING."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            legs = [_leg(1, "OVER_2_5"), _leg(2, "1X2_HOME")]
            ticket = await _seed_featured(session, legs)
            await _seed_outcome(session, 1, "OVER_2_5", "WON")
            # Pata 2 sin outcome.
            await session.commit()

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        stats = await evaluate_job.resolve_featured_tickets()
        assert stats["still_pending"] == 1
        assert stats["won"] == 0
        assert stats["lost"] == 0

        async with factory() as session:
            refreshed = (await session.execute(
                select(FeaturedTicket).where(FeaturedTicket.id == ticket.id)
            )).scalar_one()
            assert refreshed.status == "PENDING"
            assert refreshed.resolved_at is None
        await engine.dispose()

    _run(scenario())


# ── Endpoint público ─────────────────────────────────────────────────────────

def test_public_results_endpoint_returns_day_and_summary():
    """GET /public/results devuelve boletos del día + resumen 7/30 días, sin auth."""
    async def scenario():
        engine, factory = await _db()
        today = datetime.now(COT).date()

        async with factory() as session:
            # 2 boletos hoy: 1 WON, 1 PENDING.
            for mode, status in (("edge", "WON"), ("value", "PENDING")):
                session.add(FeaturedTicket(
                    ticket_date=today, mode=mode,
                    legs=[_leg(1, "OVER_2_5")], combined_odds=1.8, real_ev=0.08,
                    status=status,
                ))
            # 1 boleto hace 3 días: LOST (cae dentro de 7d y 30d).
            session.add(FeaturedTicket(
                ticket_date=today - timedelta(days=3), mode="bold",
                legs=[_leg(2, "1X2_HOME")], combined_odds=2.0, real_ev=0.05,
                status="LOST",
            ))
            await session.commit()

        async def _override_session():
            async with factory() as session:
                yield session

        app = FastAPI()
        app.include_router(public_results_router)
        app.dependency_overrides[get_async_session] = _override_session

        with TestClient(app) as client:
            response = client.get(f"/public/results?date={today.isoformat()}")
            assert response.status_code == 200
            body = response.json()
            assert body["date"] == today.isoformat()
            assert len(body["tickets"]) == 2
            statuses = {t["status"] for t in body["tickets"]}
            assert statuses == {"WON", "PENDING"}
            edge = next(t for t in body["tickets"] if t["mode"] == "edge")
            assert edge["mode_label"] == "EDGE MODE"
            assert edge["combined_odds"] == 1.8
            assert edge["real_ev"] == 0.08
            assert edge["legs"][0]["market_name"] == "OVER_2_5"
            assert edge["legs"][0]["bookmaker_odds"] == 1.8

            # Resumen 7d: total 3, 1 won, 1 lost, 1 pending.
            s7 = body["summary_7d"]
            assert s7["total"] == 3
            assert s7["won"] == 1
            assert s7["lost"] == 1
            assert s7["pending"] == 1
            assert s7["resolved"] == 2
            assert s7["win_rate"] == 0.5

            # Resumen 30d: mismo universo (los 3 boletos están dentro de 30 días).
            s30 = body["summary_30d"]
            assert s30["total"] == 3
            assert s30["won"] == 1
            assert s30["lost"] == 1

        await engine.dispose()

    _run(scenario())


def test_public_results_endpoint_defaults_to_today():
    """Sin ?date -> default a hoy (COT)."""
    async def scenario():
        engine, factory = await _db()
        today = datetime.now(COT).date()

        async with factory() as session:
            session.add(FeaturedTicket(
                ticket_date=today, mode="edge",
                legs=[_leg(1, "OVER_2_5")], combined_odds=1.8, real_ev=0.08,
                status="PENDING",
            ))
            # Boleto de ayer NO debe aparecer en el día actual.
            session.add(FeaturedTicket(
                ticket_date=today - timedelta(days=1), mode="value",
                legs=[_leg(2, "1X2_HOME")], combined_odds=2.0, real_ev=0.05,
                status="WON",
            ))
            await session.commit()

        async def _override_session():
            async with factory() as session:
                yield session

        app = FastAPI()
        app.include_router(public_results_router)
        app.dependency_overrides[get_async_session] = _override_session

        with TestClient(app) as client:
            response = client.get("/public/results")
            assert response.status_code == 200
            body = response.json()
            assert body["date"] == today.isoformat()
            assert len(body["tickets"]) == 1

        await engine.dispose()

    _run(scenario())