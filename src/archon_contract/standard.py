"""The standard a strategy must meet to be listed, as pure functions.

A strategy is one procedure, written down and hashed before it runs: a signal, a grid of up to
``MAX_CELLS`` parameter settings fixed in advance, how each test window's setting is picked from
the windows before it, and how the book is built. It counts as one trial however many settings
its grid holds, because the settings are chosen inside the walk-forward on earlier prices only.

The walk-forward expands. Six-month windows start on 1 January and 1 July (UTC); the first test
window starts at least ``FIT_DAYS`` after the first window, and each test window trades the setting
that scored best on every window before it. The test windows chain into one curve, charged
``FEE_BPS`` a side and the funding each position paid or received, and again at ``STRESS_FEE_BPS``.

R1 asks that curve to make more than holding the same markets, bought at its first test bar, and
to fall less from its best, at both costs. S2 asks the probabilistic Sharpe of its daily log
excess over holding to clear the Sidak cut for the procedures tried on the store, ``neff``. A
verdict is listable exactly when both pass.
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Mapping, Sequence

FEE_BPS = 5.5
STRESS_FEE_BPS = 8.5
FIT_DAYS = 365
FWER = 0.05
MAX_CELLS = 100


def sidak(neff: int) -> float:
    """The p-value S2 must fall below once ``neff`` procedures have been tried on a store.

    Over ``neff`` independent procedures with no edge, the chance that any one passes is ``FWER``.
    """
    if not isinstance(neff, int) or isinstance(neff, bool) or neff < 1:
        raise ValueError('neff counts at least the procedure being judged')
    return 1 - (1 - FWER) ** (1 / neff)


def psr_p(excess: Sequence[float]) -> float:
    """One-sided p-value that the true Sharpe of ``excess`` is not above zero (Bailey and Lopez de Prado).

    The Sharpe's standard error is adjusted for the sample's skew and kurtosis. A series with
    fewer than three points or no spread proves nothing and returns 1.
    """
    n = len(excess)
    if n < 3 or max(excess) == min(excess):
        return 1.0
    mean = math.fsum(excess) / n
    sd = math.sqrt(math.fsum((x - mean) ** 2 for x in excess) / n)
    sr = mean / sd
    skew = math.fsum(((x - mean) / sd) ** 3 for x in excess) / n
    kurt = math.fsum(((x - mean) / sd) ** 4 for x in excess) / n
    spread = 1 - skew * sr + (kurt - 1) / 4 * sr * sr
    z = sr * math.sqrt(n - 1) / math.sqrt(spread) if spread > 0 else 0.0
    return 1 - NormalDist().cdf(z)


def return_pct(curve: Sequence[float]) -> float:
    return (curve[-1] / curve[0] - 1) * 100


def drawdown_pct(curve: Sequence[float]) -> float:
    """The deepest fall from a running high, in percent: 0 or negative."""
    top, worst = curve[0], 0.0
    for value in curve:
        top = max(top, value)
        worst = min(worst, (value / top - 1) * 100)
    return worst


def beats_hold(level: Mapping) -> bool:
    """R1 at one cost: more return than the hold AND a shallower worst fall. Level with it is not enough."""
    hold = level['hold']
    return level['return_pct'] > hold['return_pct'] and level['drawdown_pct'] > hold['drawdown_pct']


def r1(levels: Mapping[str, Mapping]) -> bool:
    """R1 on a verdict's cost levels, keyed by fee as text: it must beat the hold at both costs."""
    return all(beats_hold(levels[str(fee)]) for fee in (FEE_BPS, STRESS_FEE_BPS))


def listable(levels: Mapping[str, Mapping], excess: Sequence[float], neff: int) -> bool:
    return r1(levels) and psr_p(excess) < sidak(neff)
