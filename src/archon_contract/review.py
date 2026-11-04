"""The daily recheck of every listed strategy: it stays listed only while it beats holding.

Each day a listed strategy's walk-forward is measured again, every bar since the split, and its
drawdown since listing against its in-sample one. A strategy that misses the bar, or breaks its
drawdown limit, is withdrawn, and a withdrawal is final: it comes back only as a new proposal
through every gate. The catalogue may be empty while research is under way.

The latest decision per strategy is its state, and a recheck that keeps a strategy writes nothing.
The registry still holds the ``upgrade`` records of 2026-10-28, from a never-empty policy withdrawn
on 2026-11-04; a strategy whose latest decision is one is rechecked like a listed one.
"""
from __future__ import annotations

from dataclasses import dataclass

from archon_contract.bar import Measurement, clauses

DEMOTE_DRAWDOWN_RATIO = 2.0
ON_OFFER = frozenset({'listed', 'upgrade'})


@dataclass(frozen=True)
class Outcome:
    outcome: str  # 'keep' or 'demote'
    reasons: tuple[str, ...]


def judge(walk_forward: Measurement, *, in_sample_drawdown_pct: float, drawdown_since_listing_pct: float) -> Outcome:
    """What one recheck means."""
    reasons = [f'its walk-forward failed {name}' for name, ok in clauses(walk_forward).items() if not ok]
    if abs(drawdown_since_listing_pct) > DEMOTE_DRAWDOWN_RATIO * abs(in_sample_drawdown_pct):
        reasons.append(f'its drawdown since listing is over {DEMOTE_DRAWDOWN_RATIO:g} times its in-sample one')
    return Outcome('demote' if reasons else 'keep', tuple(reasons))


def step(state: str, outcome: str) -> tuple[str, str | None]:
    """The strategy's next state and the verdict to write, or None when nothing changes."""
    if state in ON_OFFER and outcome == 'demote':
        return 'demote', 'demote'
    return state, None


def on_offer(state: str) -> bool:
    return state in ON_OFFER
