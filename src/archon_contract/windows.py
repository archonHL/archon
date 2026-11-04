"""Forward windows: a strategy traded on live Hyperliquid prices for ``FORWARD_DAYS`` from its next close.

A window checks execution and can withdraw a strategy; it never lists one, since a window this
short cannot tell skill from luck. It is written into the record before its first bar exists,
never shortened, re-dated or read early, and scored once after it ends by replaying the strategy
on the window's closed prices. The strategy is withdrawn when a hosted run of the same window
strays from the replay by more than ``PARITY_PTS`` points of return, or when the window falls
deeper than the strategy's verdict fell over its whole walk-forward at ``STRESS_FEE_BPS``.
"""
from __future__ import annotations

from typing import Mapping

from archon_contract.standard import STRESS_FEE_BPS

FORWARD_DAYS = 50
PARITY_PTS = 2.0
DAY_MS = 86_400_000


def opening(now_ms: int, bar_ms: int) -> tuple[int, int]:
    """A window opened at ``now_ms``: from the first bar close strictly after it, for ``FORWARD_DAYS``."""
    start = (now_ms // bar_ms + 1) * bar_ms
    return start, start + FORWARD_DAYS * DAY_MS


def withdraws(close: Mapping, verdict: Mapping | None) -> bool:
    """Whether a closed window withdraws its strategy, from the close and the verdict it names."""
    replay = close['paper']
    hosted = close.get('testnet_return_pct')
    strayed = hosted is not None and abs(hosted - replay['return_pct']) > PARITY_PTS
    deepest = verdict['levels'][str(STRESS_FEE_BPS)]['drawdown_pct'] if verdict else None
    return strayed or (deepest is not None and replay['drawdown_pct'] < deepest)
