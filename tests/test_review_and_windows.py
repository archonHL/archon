import itertools
import random
from datetime import datetime, timedelta, timezone

from archon_contract import review, windows
from archon_contract.bar import Measurement

PASSING = Measurement(40.0, -15.0, 30.0, -30.0, 3.0, 8.0, 12.0)
SHALLOWER_BUT_BEHIND = Measurement(36.29, -14.17, 60.66, -26.51, 2.62, 10.54, 18.06)  # record 0026


def judge(walk, since=-1.0):
    return review.judge(walk, in_sample_drawdown_pct=-24.0, drawdown_since_listing_pct=since).outcome


def test_outcomes():
    assert judge(PASSING) == 'keep'
    assert judge(SHALLOWER_BUT_BEHIND) == 'demote'  # falling less than holding is not enough
    assert judge(PASSING, since=-49.0) == 'demote'


def test_a_review_that_keeps_a_strategy_writes_nothing():
    assert review.step('listed', 'keep') == ('listed', None)


def test_a_demotion_is_final():
    assert review.step('listed', 'demote') == ('demote', 'demote')
    for outcome in ('keep', 'demote'):
        assert review.step('demote', outcome) == ('demote', None)
    assert not review.on_offer('demote')


def test_an_upgrade_record_is_rechecked_on_the_bar_alone():
    """The never-empty records of 2026-10-28 keep nothing on offer that fails the bar."""
    assert review.step('upgrade', judge(SHALLOWER_BUT_BEHIND)) == ('demote', 'demote')


def test_nothing_that_fails_the_bar_stays_on_offer():
    rng = random.Random(0)
    for _ in range(2000):
        state, failed = 'listed', False
        for walk in (rng.choice([PASSING, SHALLOWER_BUT_BEHIND]) for _ in range(rng.randint(1, 12))):
            state, _ = review.step(state, judge(walk))
            failed = failed or walk is SHALLOWER_BUT_BEHIND
            assert review.on_offer(state) is not failed


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
