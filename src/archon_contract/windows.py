"""Trials: windows on live prices, frozen before a single bar of them exists.

A candidate that passed its unseen read is frozen into a window that starts at the
next close of its own bar width and runs ``FORWARD_DAYS`` days. The window is never shortened, re-dated
or read early. Its result is written once, when it has closed and every bar and every
funding settlement of it is on record; a hole anywhere leaves it incomplete and unscored.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

FORWARD_DAYS = 60


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    @property
    def days(self) -> int:
        return (self.end - self.start).days


def next_close(now: datetime, bar: timedelta) -> datetime:
    """The first bar boundary strictly after ``now``, on a UTC grid."""
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return epoch + ((now - epoch) // bar + 1) * bar


def freeze(now: datetime, bar: timedelta) -> Window:
    start = next_close(now, bar)
    return Window(start, start + timedelta(days=FORWARD_DAYS))


def status(window: Window, now: datetime, *, missing_bars: int, missing_settlements: int) -> str:
    """'open' until the window closes; then 'complete' only if nothing is missing, else 'incomplete'.

    An open window reports coverage, never a return.
    """
    if now < window.end:
        return 'open'
    return 'complete' if missing_bars == 0 and missing_settlements == 0 else 'incomplete'
