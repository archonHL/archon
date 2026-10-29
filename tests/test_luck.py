import random

import pytest

from archon_contract import luck


def noise(cells, days, seed=1, sd=0.01):
    rng = random.Random(seed)
    return [[rng.gauss(0.0, sd) for _ in range(days)] for _ in range(cells)]


def test_the_reality_check_finds_no_edge_in_noise():
    assert luck.reality_check(noise(10, 250), resamples=300) > 0.1


def test_the_reality_check_finds_a_planted_edge():
    grid = noise(10, 250)
    grid[4] = [x + 0.004 for x in grid[4]]
    assert luck.reality_check(grid, resamples=300) < 0.05


def test_the_reality_check_needs_equal_days():
    with pytest.raises(ValueError):
        luck.reality_check([[0.1, 0.2], [0.1]])


def test_one_trial_expects_no_lucky_sharpe():
    assert luck.expected_max_sharpe(0.01, 1) == 0.0


def test_more_trials_expect_a_luckier_best():
    assert luck.expected_max_sharpe(0.01, 10_000) > luck.expected_max_sharpe(0.01, 100) > 0


def test_every_trial_counted_deflates_the_winner():
    rng = random.Random(7)
    winner = [rng.gauss(0.002, 0.01) for _ in range(500)]
    spread = [rng.gauss(0.0, 0.05) for _ in range(50)]
    few = luck.deflated_sharpe(winner, trial_sharpes=spread, trials=10)
    many = luck.deflated_sharpe(winner, trial_sharpes=spread, trials=5231)
    assert 0 < many < few < 1


def test_pbo_of_noise_is_near_a_half():
    assert 0.3 < luck.pbo(noise(20, 320, seed=3), blocks=10) < 0.7


def test_pbo_of_a_persistent_edge_is_near_zero():
    grid = noise(20, 320, seed=3)
    grid[11] = [x + 0.006 for x in grid[11]]
    assert luck.pbo(grid, blocks=10) < 0.05


def test_pbo_uses_every_half_and_half_split_of_sixteen_blocks():
    grid = noise(3, 64, seed=5)
    value = luck.pbo(grid)
    assert value * 12870 == pytest.approx(round(value * 12870))


@pytest.mark.parametrize('blocks', [1, 7])
def test_pbo_needs_an_even_number_of_blocks(blocks):
    with pytest.raises(ValueError):
        luck.pbo(noise(3, 64), blocks=blocks)
