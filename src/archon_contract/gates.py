"""The four gates a candidate passes to be listed. All four, or nothing is listed.

The gates were fixed in code before any candidate had a trial result. Changing one is a
code change with its own commit, never a parameter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

LUCK_P = 0.1
FORWARD_MIN_DAYS = 30
FORWARD_DRAWDOWN_RATIO = 1.5


@dataclass(frozen=True)
class Gate:
    passes: bool
    detail: str


@dataclass(frozen=True)
class OutOfSampleRead:
    """The candidate's one read of the prices the search never saw."""
    passed_bar: bool
    in_sample_days_scored: int = 0  # days the search had also read; a clean read has none
    correction: bool = False        # a re-score of an already opened slice


@dataclass(frozen=True)
class ForwardResult:
    """A frozen trial's result, written once when the window closed whole."""
    days: int
    return_pct: float
    drawdown_pct: float


def out_of_sample(read: Optional[OutOfSampleRead]) -> Gate:
    if read is None:
        return Gate(False, 'its unseen slice has not been opened')
    if read.correction:
        return Gate(False, 'a correction re-scores a slice already opened; it never counts')
    if read.in_sample_days_scored:
        return Gate(False, f'its read scored {read.in_sample_days_scored} days the search had seen')
    if not read.passed_bar:
        return Gate(False, 'it missed the listing bar on unseen prices')
    return Gate(True, 'passed the listing bar on prices the search never read')


def luck(reality_check_p: float, deflated_sharpe_probability: float, trials: int) -> Gate:
    """Both figures must leave less than ``LUCK_P`` chance the edge is luck.

    The reality check knows only its own search; the deflated Sharpe charges every trial the
    counter holds against the winner.
    """
    deflated_p = 1 - deflated_sharpe_probability
    detail = (f'reality check p {reality_check_p:.3f}; a {deflated_p:.3f} chance its edge is the best of '
              f'{trials:,} skill-free tries; both must be under {LUCK_P:g}')
    return Gate(reality_check_p < LUCK_P and deflated_p < LUCK_P, detail)


def forward(result: Optional[ForwardResult], in_sample_drawdown_pct: float) -> Gate:
    if result is None:
        return Gate(False, 'its trial has no result; one is written only when it closes whole')
    worst, limit = abs(result.drawdown_pct), FORWARD_DRAWDOWN_RATIO * abs(in_sample_drawdown_pct)
    fails = []
    if result.days < FORWARD_MIN_DAYS:
        fails.append(f'the window was {result.days} days, under {FORWARD_MIN_DAYS}')
    if result.return_pct <= 0:
        fails.append(f'it returned {result.return_pct:+.1f}%')
    if worst > limit:
        fails.append(f'its worst drawdown, {worst:.1f}%, was over {FORWARD_DRAWDOWN_RATIO:g} times its in-sample one')
    if fails:
        return Gate(False, '; '.join(fails))
    return Gate(True, f'{result.days} trial days at {result.return_pct:+.1f}%, worst drawdown {worst:.1f}%')


def engine(reproduces: bool) -> Gate:
    """The live signal and the planner reproduce, bar for bar, the curve the desk measured."""
    if reproduces:
        return Gate(True, 'the engine trades exactly what was measured')
    return Gate(False, 'the engine does not reproduce the measured curve')


def promote(*gates: Gate) -> bool:
    if len(gates) != 4:
        raise ValueError('listing reads exactly four gates')
    return all(g.passes for g in gates)
