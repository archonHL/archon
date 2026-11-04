from archon_contract import standard, windows

HOUR = 3_600_000


def test_a_window_opens_at_the_next_close_and_runs_forward_days():
    start, end = windows.opening(10 * HOUR + 1, 4 * HOUR)
    assert start == 12 * HOUR
    assert end - start == windows.FORWARD_DAYS * windows.DAY_MS
    assert windows.opening(12 * HOUR, 4 * HOUR)[0] == 16 * HOUR  # strictly after: a close that has happened is not next


def close(ret, dd, hosted=None):
    return {'paper': {'return_pct': ret, 'drawdown_pct': dd}, 'testnet_return_pct': hosted}


VERDICT = {'levels': {str(standard.STRESS_FEE_BPS): {'drawdown_pct': -30.0}}}


def test_a_window_withdraws_on_a_parity_miss_or_a_deeper_fall():
    assert not windows.withdraws(close(4.0, -12.0, hosted=4.0 + windows.PARITY_PTS), VERDICT)
    assert windows.withdraws(close(4.0, -12.0, hosted=4.0 - windows.PARITY_PTS - 0.01), VERDICT)
    assert windows.withdraws(close(4.0, -30.5), VERDICT)
    assert not windows.withdraws(close(-9.0, -29.0), VERDICT)  # a loss alone withdraws nothing
    assert not windows.withdraws(close(4.0, -60.0), None)  # no verdict, no fall to compare with
