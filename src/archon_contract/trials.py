"""The global trial counter: every candidate ever measured, counted before it is measured.

It starts from a baseline counted out of the evidence that existed before the desk, and only
ever goes up. Each entry in its log names what was added and the running total, so a counter
edited by hand stops adding up. The deflated Sharpe ratio reads this count as the number of
tries a winner has to beat, so a thousand tries cannot buy a lucky winner.
"""
from __future__ import annotations

import copy
from typing import Mapping


class TrialError(ValueError):
    """The counter does not add up, or a write would make it go down."""


def check(state: Mapping) -> int:
    """The count, or TrialError if the baseline, the log or the total disagree."""
    baseline = state['baseline']
    if sum(baseline['by_source'].values()) != baseline['total']:
        raise TrialError('the baseline does not add up to its sources')
    totals = [baseline['total']]
    for entry in state['log']:
        if entry['added'] <= 0:
            raise TrialError(f'a log entry added {entry["added"]}; the counter only goes up')
        if entry['total'] != totals[-1] + entry['added']:
            raise TrialError(f'the log entry at {entry["utc"]} does not follow the one before it')
        totals.append(entry['total'])
    if state['count'] != totals[-1]:
        raise TrialError('the count is not the last total in the log')
    return state['count']


def add(state: Mapping, count: int, what: str, *, utc: str) -> dict:
    """A new counter with ``count`` more trials, logged. Call it before measuring them."""
    if count <= 0:
        raise TrialError('the counter only goes up')
    total = check(state) + count
    new = copy.deepcopy(dict(state))
    new['count'] = total
    new['log'].append({'utc': utc, 'added': count, 'what': what, 'total': total})
    return new
