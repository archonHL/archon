import random

import pytest

from archon_contract import standard


def level(ret, dd, hold_ret, hold_dd):
    return {'return_pct': ret, 'drawdown_pct': dd, 'hold': {'return_pct': hold_ret, 'drawdown_pct': hold_dd}}


def levels(base, stress):
    return {str(standard.FEE_BPS): base, str(standard.STRESS_FEE_BPS): stress}


@pytest.mark.parametrize('neff', [1, 2, 31, 1000])
def test_the_cut_holds_the_false_listing_chance_at_fwer(neff):
    cut = standard.sidak(neff)
    assert 1 - (1 - cut) ** neff == pytest.approx(standard.FWER)


def test_the_cut_tightens_with_every_procedure_tried():
    cuts = [standard.sidak(n) for n in range(1, 200)]
    assert cuts[0] == pytest.approx(standard.FWER)
    assert all(a > b for a, b in zip(cuts, cuts[1:]))


@pytest.mark.parametrize('neff', [0, -1, 2.0, True])
def test_the_cut_needs_a_count_of_at_least_one(neff):
    with pytest.raises(ValueError):
        standard.sidak(neff)


def test_a_series_with_no_spread_or_too_few_days_proves_nothing():
    assert standard.psr_p([0.001] * 500) == 1.0
    assert standard.psr_p([0.01, 0.02]) == 1.0


def test_a_planted_edge_passes_and_its_negative_fails():
    rng = random.Random(1)
    edge = [rng.gauss(0.002, 0.01) for _ in range(730)]
    assert standard.psr_p(edge) < standard.sidak(31)
    assert standard.psr_p([-x for x in edge]) > 0.99


def test_noise_passes_about_as_often_as_the_cut_allows():
    rng = random.Random(2)
    hits = sum(standard.psr_p([rng.gauss(0, 0.01) for _ in range(365)]) < 0.05 for _ in range(1000))
    assert 25 <= hits <= 80


def test_heavy_tails_and_left_skew_widen_the_doubt():
    # One crash day among small gains: same mean as a plain series, but a far weaker case.
    plain = [0.001 + (0.004 if i % 2 else -0.004) for i in range(400)]
    mean = sum(plain) / len(plain)
    crash = [0.0025] * 399
    crash.append(mean * 400 - sum(crash))
    assert standard.psr_p(crash) > standard.psr_p(plain)


def test_drawdown_is_the_deepest_fall_from_a_running_high():
    assert standard.drawdown_pct([100, 120, 90, 130, 104]) == pytest.approx(-25.0)
    assert standard.drawdown_pct([1, 2, 3]) == 0.0
    assert standard.return_pct([100, 150]) == pytest.approx(50.0)


def test_r1_needs_more_return_and_a_shallower_fall_at_both_costs():
    win = level(30.0, -20.0, 25.0, -40.0)
    assert standard.r1(levels(win, win))
    assert not standard.r1(levels(win, level(24.0, -20.0, 25.0, -40.0)))  # the stress cost loses on return
    assert not standard.r1(levels(level(30.0, -45.0, 25.0, -40.0), win))  # more return by falling further
    assert not standard.r1(levels(level(25.0, -20.0, 25.0, -40.0), win))  # level with holding is not beating it
    assert not standard.r1(levels(level(10.0, -5.0, 25.0, -40.0), win))   # falling less alone is not enough
    with pytest.raises(KeyError):
        standard.r1({str(standard.FEE_BPS): win})                          # one cost is not both


def test_listable_needs_r1_and_s2():
    rng = random.Random(3)
    edge = [rng.gauss(0.003, 0.01) for _ in range(730)]
    win, lose = level(30.0, -20.0, 25.0, -40.0), level(20.0, -20.0, 25.0, -40.0)
    assert standard.listable(levels(win, win), edge, 31)
    assert not standard.listable(levels(win, lose), edge, 31)
    assert not standard.listable(levels(win, win), [rng.gauss(0, 0.01) for _ in range(730)], 31)
