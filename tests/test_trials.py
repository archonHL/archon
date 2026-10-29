import copy

import pytest

from archon_contract import trials


@pytest.fixture
def counter():
    """A counter the way the desk keeps one: a baseline by source, then every addition logged."""
    state = {'baseline': {'by_source': {'early simulations': 8, 'walk-forward study': 39}, 'total': 47},
             'count': 47, 'log': []}
    for n, size in enumerate((6, 15, 10, 12, 2000)):
        state = trials.add(state, size, f'proposal {n}', utc=f'2026-10-28T1{n}:00:00+00:00')
    return state


def test_a_kept_counter_adds_up(counter):
    assert trials.check(counter) == counter['count'] > counter['baseline']['total']


def test_a_lowered_count_fails(counter):
    counter['count'] -= 1
    with pytest.raises(trials.TrialError):
        trials.check(counter)


def test_a_dropped_log_entry_fails(counter):
    del counter['log'][3]
    with pytest.raises(trials.TrialError):
        trials.check(counter)


def test_a_baseline_that_does_not_add_up_fails(counter):
    counter['baseline']['total'] += 10
    with pytest.raises(trials.TrialError):
        trials.check(counter)


def test_add_counts_before_measuring_and_leaves_the_input_alone(counter):
    before = copy.deepcopy(counter)
    total = counter['count'] + 2000
    after = trials.add(counter, 2000, 'sweep: 2,000 candidates', utc='2026-10-28T16:00:00+00:00')
    assert trials.check(after) == total
    assert after['log'][-1] == {'utc': '2026-10-28T16:00:00+00:00', 'added': 2000,
                                'what': 'sweep: 2,000 candidates', 'total': total}
    assert counter == before


@pytest.mark.parametrize('count', [0, -5])
def test_the_counter_only_goes_up(counter, count):
    with pytest.raises(trials.TrialError):
        trials.add(counter, count, 'nothing', utc='2026-10-28T16:00:00+00:00')
