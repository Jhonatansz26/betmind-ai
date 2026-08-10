"""
SRP: Resuelve el resultado real (WON/LOST) de un mercado de apuestas dado el
resultado final de un partido. Sin I/O — función pura, testeable.

Cubre todos los nombres de mercado que genera market_calculator.py:
  - Goles: 1X2_*, DOUBLE_*, DNB_*, OVER_*/UNDER_*, BTTS_*, HOME_OVER_*/AWAY_OVER_*
  - Córneres: CORNERS_OVER_*/CORNERS_UNDER_*
  - Tarjetas: CARDS_OVER_*/CARDS_UNDER_*
  - Remates a puerta: SHOTS_OT_OVER_*/SHOTS_OT_UNDER_*

Convenciones:
  - DNB con empate se resuelve LOST (la apuesta se anula, no es WON; para
    calibración Brier el evento "ganó la pata" es falso).
  - Mercados sin datos necesarios (córneres/tarjetas/remates con campos null
    porque SofaScore/ESPN no los trajeron) retornan None: el job los saltea.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MatchFinalScore:
    """Resultado final de un partido, tal como se resuelven los mercados."""
    home_goals: int | None
    away_goals: int | None
    home_corners: int | None = None
    away_corners: int | None = None
    home_yellows: float | None = None
    away_yellows: float | None = None
    home_shots_on_target: int | None = None
    away_shots_on_target: int | None = None


def _parse_threshold(value: str) -> float | None:
    """Convierte el sufijo de línea ('2_5', '8_5') a número (2.5, 8.5)."""
    try:
        return float(value.replace("_", "."))
    except ValueError:
        return None


def _sum_or_none(*values: int | float | None) -> float | None:
    if any(v is None for v in values):
        return None
    return float(sum(values))  # type: ignore[arg-type]


def resolve_market_outcome(
    market_name: str,
    score: MatchFinalScore,
) -> bool | None:
    """
    Resuelve un mercado contra el resultado real.

    Returns:
        True  = WON (la selección ganó)
        False = LOST (la selección perdió)
        None  = no se puede resolver (mercado desconocido o datos faltantes)
    """
    name = market_name.strip().upper()

    # ── Mercados de goles (1X2, doble chance, DNB) ──────────────────────────
    if name in ("1X2_HOME", "DNB_HOME"):
        return _compare_goals(score, home_wins=True)
    if name in ("1X2_AWAY", "DNB_AWAY"):
        return _compare_goals(score, home_wins=False)
    if name == "1X2_DRAW":
        return _goals_draw(score)
    if name == "DOUBLE_12":
        return _goals_differ(score)
    if name == "DOUBLE_1X":
        return _home_at_least_draw(score)
    if name == "DOUBLE_X2":
        return _home_at_most_draw(score)

    # ── BTTS ────────────────────────────────────────────────────────────────
    if name == "BTTS_YES":
        return _btts(score, yes=True)
    if name == "BTTS_NO":
        return _btts(score, yes=False)

    # ── Over/Under de goles totales ─────────────────────────────────────────
    if name.startswith("OVER_") or name.startswith("UNDER_"):
        threshold = _parse_threshold(name.split("_", 1)[1])
        if threshold is None:
            return None
        total = _sum_or_none(score.home_goals, score.away_goals)
        return _over_under(total, threshold, name.startswith("OVER_"))

    # ── Goles individuales por equipo (HOME_OVER_* / AWAY_OVER_*) ──────────
    if name.startswith("HOME_OVER_") or name.startswith("AWAY_OVER_"):
        prefix = "HOME_OVER_" if name.startswith("HOME_OVER_") else "AWAY_OVER_"
        threshold = _parse_threshold(name[len(prefix):])
        if threshold is None:
            return None
        goals = score.home_goals if prefix == "HOME_OVER_" else score.away_goals
        if goals is None:
            return None
        return goals > threshold

    # ── Córneres / Tarjetas / Remates a puerta ──────────────────────────────
    if name.startswith("CORNERS_"):
        total = _sum_or_none(score.home_corners, score.away_corners)
        return _over_under(total, _line_after_prefix(name, "CORNERS_"), name.split("_")[1] == "OVER")

    if name.startswith("CARDS_"):
        total = _sum_or_none(score.home_yellows, score.away_yellows)
        return _over_under(total, _line_after_prefix(name, "CARDS_"), name.split("_")[1] == "OVER")

    if name.startswith("SHOTS_OT_"):
        total = _sum_or_none(score.home_shots_on_target, score.away_shots_on_target)
        return _over_under(total, _line_after_prefix(name, "SHOTS_OT_"), name.split("_")[2] == "OVER")

    return None


def _line_after_prefix(name: str, prefix: str) -> float | None:
    """'CORNERS_OVER_8_5' + 'CORNERS_' -> 'OVER_8_5' -> 8.5"""
    rest = name[len(prefix):]
    parts = rest.split("_", 1)
    if len(parts) != 2 or parts[0] not in ("OVER", "UNDER"):
        return None
    return _parse_threshold(parts[1])


def _compare_goals(score: MatchFinalScore, home_wins: bool) -> bool | None:
    if score.home_goals is None or score.away_goals is None:
        return None
    if home_wins:
        return score.home_goals > score.away_goals
    return score.away_goals > score.home_goals


def _goals_draw(score: MatchFinalScore) -> bool | None:
    if score.home_goals is None or score.away_goals is None:
        return None
    return score.home_goals == score.away_goals


def _goals_differ(score: MatchFinalScore) -> bool | None:
    if score.home_goals is None or score.away_goals is None:
        return None
    return score.home_goals != score.away_goals


def _home_at_least_draw(score: MatchFinalScore) -> bool | None:
    if score.home_goals is None or score.away_goals is None:
        return None
    return score.home_goals >= score.away_goals


def _home_at_most_draw(score: MatchFinalScore) -> bool | None:
    if score.home_goals is None or score.away_goals is None:
        return None
    return score.home_goals <= score.away_goals


def _btts(score: MatchFinalScore, yes: bool) -> bool | None:
    if score.home_goals is None or score.away_goals is None:
        return None
    both_scored = score.home_goals >= 1 and score.away_goals >= 1
    return both_scored if yes else not both_scored


def _over_under(total: float | None, threshold: float | None, is_over: bool) -> bool | None:
    if total is None or threshold is None:
        return None
    if is_over:
        return total > threshold
    return total < threshold
