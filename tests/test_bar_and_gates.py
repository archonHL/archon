import pytest

from archon_contract import bar, gates
from archon_contract.bar import Measurement

# The walk-forward in published decision record 0026 (breadth-trend, 2026-03-01 to 2026-10-28),
# rounded to two places.
RECORD_0026 = Measurement(return_pct=36.29, drawdown_pct=-14.17, hold_return_pct=60.66,
                          hold_drawdown_pct=-26.51, cash_return_pct=2.62, median_market_pct=10.54,
                          mean_ex_top2_pct=18.06)


def m(**over):
    base = dict(return_pct=40.0, drawdown_pct=-15.0, hold_return_pct=30.0, hold_drawdown_pct=-30.0,
                cash_return_pct=3.0, median_market_pct=8.0, mean_ex_top2_pct=12.0)
    return Measurement(**{**base, **over})


def test_a_strategy_that_makes_more_and_falls_less_passes():
    assert bar.passes(m())


def test_falling_less_is_not_enough():
    assert not bar.clauses(m(return_pct=31.0))['beats_hold']


def test_making_more_by_falling_further_is_not_enough():
    assert not bar.clauses(m(drawdown_pct=-31.0))['beats_hold']


def test_losing_less_than_a_falling_market_fails():
    c = bar.clauses(m(return_pct=-5.0, hold_return_pct=-30.0))
    assert not c['positive'] and not c['beats_cash']


def test_a_strategy_carried_by_its_winners_fails():
    assert not bar.clauses(m(median_market_pct=-0.3))['not_carried']


def test_one_unfunded_hour_fails_the_strategy():
    assert not bar.passes(m(unfunded_hours=1))


def test_record_0026_fails_the_bar_and_clears_the_floor():
    assert not bar.passes(RECORD_0026)
    assert bar.passes_floor(RECORD_0026)


def test_cash_earns_four_percent_a_year():
    assert bar.cash_pct(365.25) == pytest.approx(4.0)


def test_a_correction_never_passes_the_out_of_sample_gate():
    read = gates.OutOfSampleRead(passed_bar=True, correction=True)
    assert not gates.out_of_sample(read).passes


def test_a_read_that_scored_in_sample_days_is_not_clean():
    assert not gates.out_of_sample(gates.OutOfSampleRead(passed_bar=True, in_sample_days_scored=40)).passes
    assert gates.out_of_sample(gates.OutOfSampleRead(passed_bar=True)).passes


def test_the_luck_gate_needs_both_figures():
    # The first sweep's best pick: a reality check of 0.018, and a 0.244 chance of luck against 5,231 trials.
    assert not gates.luck(0.018, 1 - 0.244, 5231).passes
    # The first candidate: reality check 0.48, deflated Sharpe probability 0.54 against 1,023 trials.
    assert not gates.luck(0.48, 0.54, 1023).passes
    assert gates.luck(0.02, 0.95, 5231).passes


def test_the_forward_gate():
    assert not gates.forward(None, -20.0).passes
    assert not gates.forward(gates.ForwardResult(days=20, return_pct=5.0, drawdown_pct=-8.0), -20.0).passes
    assert not gates.forward(gates.ForwardResult(days=60, return_pct=-1.0, drawdown_pct=-8.0), -20.0).passes
    assert not gates.forward(gates.ForwardResult(days=60, return_pct=5.0, drawdown_pct=-31.0), -20.0).passes
    assert gates.forward(gates.ForwardResult(days=60, return_pct=5.0, drawdown_pct=-29.0), -20.0).passes


def test_listing_needs_all_four_gates():
    ok = gates.Gate(True, '')
    assert gates.promote(ok, ok, ok, ok)
    assert not gates.promote(ok, ok, ok, gates.engine(False))
    with pytest.raises(ValueError):
        gates.promote(ok, ok, ok)
