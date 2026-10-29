import itertools
import random
from datetime import datetime, timedelta, timezone

from archon_contract import review, windows
from archon_contract.bar import Measurement

PASSING = Measurement(40.0, -15.0, 30.0, -30.0, 3.0, 8.0, 12.0)
ON_THE_FLOOR = Measurement(36.29, -14.17, 60.66, -26.51, 2.62, 10.54, 18.06)  # record 0026
UNDER_THE_FLOOR = Measurement(24.8, -22.3, 60.7, -26.5, 2.6, 9.8, 14.6)       # record 0017


def judge(walk, since=-1.0, replacement=None):
    return review.judge(walk, in_sample_drawdown_pct=-24.0, drawdown_since_listing_pct=since,
                        replacement=replacement).outcome


def test_outcomes():
    assert judge(PASSING) == 'keep'
    assert judge(ON_THE_FLOOR) == 'upgrade'
    assert judge(ON_THE_FLOOR, replacement='desk-f014') == 'replaced'
    assert judge(UNDER_THE_FLOOR) == 'demote'
    assert judge(PASSING, since=-49.0) == 'demote'


def test_a_withdrawal_written_before_the_floor_is_reviewed_again():
    # The desk's first rechecks withdrew against the bar alone; the first recheck with the floor
    # put the ones that clear it back on offer, as being upgraded.
    state, verdict = review.step('listed', judge(UNDER_THE_FLOOR))
    assert (state, verdict) == ('demote', 'demote')
    assert review.step(state, judge(ON_THE_FLOOR), final=False) == ('upgrade', 'upgrade')
    assert review.step(state, judge(PASSING), final=False) == ('listed', 'restore')
    assert review.step(state, judge(ON_THE_FLOOR)) == ('demote', None)


def test_a_review_that_changes_nothing_writes_nothing():
    assert review.step('listed', 'keep') == ('listed', None)
    assert review.step('upgrade', 'upgrade') == ('upgrade', None)


def test_a_final_demotion_never_moves():
    for outcome in ('keep', 'upgrade', 'replaced', 'demote'):
        assert review.step('demote', outcome) == ('demote', None)


def test_a_replaced_strategy_comes_back_if_its_replacement_goes():
    state, _ = review.step('upgrade', 'replaced')
    assert state == 'replaced' and not review.on_offer(state)
    assert review.step(state, 'upgrade') == ('upgrade', 'upgrade')
    assert review.step(state, 'keep') == ('listed', 'restore')


def test_never_empty_without_a_replacement():
    """However the reviews go, a strategy that stays on the floor and inside its drawdown limit stays on offer
    until a passing replacement is listed."""
    rng = random.Random(0)
    for _ in range(2000):
        state = 'listed'
        for walk in (rng.choice([PASSING, ON_THE_FLOOR]) for _ in range(rng.randint(1, 12))):
            state, _ = review.step(state, judge(walk))
            assert review.on_offer(state)


def test_freeze_starts_at_the_next_close():
    # Record 0003: written 10:59:43Z, a 4h window from 12:00Z to 2026-12-27 12:00Z.
    w = windows.freeze(datetime(2026, 10, 28, 10, 59, 43, tzinfo=timezone.utc), timedelta(hours=4))
    assert (w.start.isoformat(), w.end.isoformat(), w.days) == (
        '2026-10-28T12:00:00+00:00', '2026-12-27T12:00:00+00:00', 60)
    # Record 0042: a daily-bar candidate frozen at 13:08:01Z starts at the next midnight.
    d = windows.freeze(datetime(2026, 10, 28, 13, 8, 1, tzinfo=timezone.utc), timedelta(days=1))
    assert d.end.isoformat() == '2026-12-28T00:00:00+00:00'


def test_a_window_is_scored_only_once_closed_and_whole():
    w = windows.freeze(datetime(2026, 10, 28, 11, tzinfo=timezone.utc), timedelta(hours=4))
    during, after = w.start + timedelta(days=59), w.end + timedelta(hours=1)
    for missing in itertools.product([0, 3], [0, 1]):
        assert windows.status(w, during, missing_bars=missing[0], missing_settlements=missing[1]) == 'open'
    assert windows.status(w, after, missing_bars=0, missing_settlements=0) == 'complete'
    assert windows.status(w, after, missing_bars=0, missing_settlements=1) == 'incomplete'
