"""The listing bar: what a strategy must clear, net of fees and funding, to be listed.

One copy judges every measurement: an in-sample search, an out-of-sample read, a forward
window and the daily recheck of a listed strategy. Beside it is the floor, which lists nothing.
The floor decides only what happens to a listed strategy that misses the bar: on the floor it
stays listed while the desk finds its replacement, under it it is withdrawn.
"""
from __future__ import annotations

from dataclasses import dataclass

CASH_YIELD_PCT = 4.0        # idle USDC at a money-market rate
RETURN_MARGIN_PTS = 5.0     # clearly more than holding, not level with it inside one regime
DRAWDOWN_MARGIN_PTS = 10.0  # the floor's other way past holding
YEAR_DAYS = 365.25


@dataclass(frozen=True)
class Measurement:
    """One strategy on one slice of history against holding the same markets from the same bar.

    Returns and drawdowns are in percent, drawdowns negative. The hold is charged the same
    funding as the strategy. ``unfunded_hours`` counts held market-hours with no funding
    settlement on record.
    """
    return_pct: float
    drawdown_pct: float
    hold_return_pct: float
    hold_drawdown_pct: float
    cash_return_pct: float
    median_market_pct: float
    mean_ex_top2_pct: float
    unfunded_hours: int = 0


def cash_pct(days: float) -> float:
    """What cash at ``CASH_YIELD_PCT`` a year earns over ``days``, in percent."""
    return ((1 + CASH_YIELD_PCT / 100) ** (days / YEAR_DAYS) - 1) * 100


def clauses(m: Measurement) -> dict[str, bool]:
    """The bar, clause by clause. A strategy passes only on all five.

    ``beats_hold`` asks for more return by the margin AND a worst drawdown no deeper: falling
    less is not enough, and making more by falling further is not either. ``positive`` and
    ``beats_cash`` stop a strategy that merely lost less than a falling market. ``not_carried``
    stops one carried by a market or two. ``funded`` fails any strategy holding an hour whose
    funding is not on record, rather than printing the gap beside a pass.
    """
    return {
        'positive': m.return_pct > 0,
        'beats_cash': m.return_pct > m.cash_return_pct,
        'beats_hold': (m.return_pct >= m.hold_return_pct + RETURN_MARGIN_PTS
                       and m.drawdown_pct >= m.hold_drawdown_pct),
        'not_carried': m.median_market_pct > 0 and m.mean_ex_top2_pct > 0,
        'funded': m.unfunded_hours == 0,
    }


def floor_clauses(m: Measurement) -> dict[str, bool]:
    """The floor: the bar with holding beaten by the return margin OR the drawdown margin."""
    return {**clauses(m),
            'beats_hold': (m.return_pct >= m.hold_return_pct + RETURN_MARGIN_PTS
                           or m.drawdown_pct >= m.hold_drawdown_pct + DRAWDOWN_MARGIN_PTS)}


def passes(m: Measurement) -> bool:
    return all(clauses(m).values())


def passes_floor(m: Measurement) -> bool:
    return all(floor_clauses(m).values())
