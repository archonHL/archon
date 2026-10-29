"""The daily recheck of every listed strategy: replace, never empty.

Each day a listed strategy's walk-forward is measured again, every bar since the split. A
strategy that misses the bar is not simply dropped. If it still clears the floor and has not broken
its drawdown limit, it stays listed and keeps trading, marked as being upgraded, until a
stronger candidate that passes the bar is listed in its place. The catalogue never goes empty
because research is still under way.

The latest decision per strategy is its state, and a recheck that leaves the state as it was
writes nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from archon_contract.bar import Measurement, clauses, floor_clauses

DEMOTE_DRAWDOWN_RATIO = 2.0

# What a recheck writes, by the strategy's state and the review's outcome. Anything else writes nothing.
# 'replaced' is a withdrawal that lasts while its replacement stays listed and passing.
TRANSITIONS = {
    ('listed', 'upgrade'): 'upgrade', ('listed', 'demote'): 'demote', ('listed', 'replaced'): 'demote',
    ('upgrade', 'keep'): 'restore', ('upgrade', 'demote'): 'demote', ('upgrade', 'replaced'): 'demote',
    ('replaced', 'keep'): 'restore', ('replaced', 'upgrade'): 'upgrade', ('replaced', 'demote'): 'demote',
}
# A withdrawal that was never judged against the floor (one written before the floor existed) is
# reviewed again like any other state; only one judged against it is final.
UNJUDGED = {('demote', 'keep'): 'restore', ('demote', 'upgrade'): 'upgrade'}
ON_OFFER = frozenset({'listed', 'upgrade'})


@dataclass(frozen=True)
class Outcome:
    outcome: str  # 'keep', 'upgrade', 'replaced' or 'demote'
    reasons: tuple[str, ...]


def judge(walk_forward: Measurement, *, in_sample_drawdown_pct: float, drawdown_since_listing_pct: float,
          replacement: Optional[str] = None) -> Outcome:
    """What one recheck means. ``replacement`` is a listed candidate on offer that passes the bar today."""
    reasons = [f'its walk-forward failed {name}' for name, ok in clauses(walk_forward).items() if not ok]
    if abs(drawdown_since_listing_pct) > DEMOTE_DRAWDOWN_RATIO * abs(in_sample_drawdown_pct):
        reasons.append(f'its drawdown since listing is over {DEMOTE_DRAWDOWN_RATIO:g} times its in-sample one')
        return Outcome('demote', tuple(reasons))
    if not reasons:
        return Outcome('keep', ())
    if not all(floor_clauses(walk_forward).values()):
        return Outcome('demote', (*reasons, 'it also failed the floor'))
    if replacement:
        return Outcome('replaced', (*reasons, f'{replacement} passes the bar and is listed in its place'))
    return Outcome('upgrade', tuple(reasons))


def step(state: str, outcome: str, *, final: bool = True) -> tuple[str, Optional[str]]:
    """The strategy's next state and the verdict to write, or None when nothing changes.

    A final withdrawal ('demote') never moves again; a re-test is a new proposal. ``final`` is
    False only for a withdrawal written before the floor existed, which was never judged against it.
    """
    verdict = TRANSITIONS.get((state, outcome)) or (None if final else UNJUDGED.get((state, outcome)))
    if verdict is None:
        return state, None
    if verdict == 'restore':
        return 'listed', verdict
    if verdict == 'demote':
        return ('replaced' if outcome == 'replaced' else 'demote'), verdict
    return verdict, verdict


def on_offer(state: str) -> bool:
    return state in ON_OFFER
