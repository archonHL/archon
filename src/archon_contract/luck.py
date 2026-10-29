"""How much of a best result is luck. Three figures, because they answer three questions.

``reality_check``: White's reality check with the Politis and Romano stationary bootstrap.
Of the candidates a search tried, could the best mean daily excess have come from candidates with no
edge at all? It knows only its own grid.

``deflated_sharpe``: Bailey and Lopez de Prado's deflated Sharpe ratio. The probability the
winner's Sharpe beats the best Sharpe expected from ``trials`` skill-free attempts. Archon
passes the global trial counter, so every candidate ever measured counts against it.

``pbo``: the probability of backtest overfitting by combinatorially symmetric
cross-validation (Bailey, Borwein, Lopez de Prado and Zhu). How often the in-sample winner
of a split ranks at or below the median on the half it was not chosen on.
"""
from __future__ import annotations

import itertools
import math
import random
import statistics as st
from statistics import NormalDist
from typing import Sequence

EULER_GAMMA = 0.5772156649015329
NORMAL = NormalDist()


def stationary_indices(length: int, mean_block: float, rng: random.Random) -> list[int]:
    """One resample of ``range(length)`` in blocks of geometric length, wrapping at the end."""
    p = 1.0 / mean_block
    out, k = [], rng.randrange(length)
    for _ in range(length):
        out.append(k)
        k = rng.randrange(length) if rng.random() < p else (k + 1) % length
    return out


def reality_check(series: Sequence[Sequence[float]], *, resamples: int = 1000, mean_block: float = 10.0,
                  seed: int = 0) -> float:
    """p-value that the best mean in ``series`` (one equal-length list per candidate) is luck.

    The null recentres every resampled mean on the candidate's own, so a search with no edge has its
    best observed mean land inside the resampled maxima. One resample index serves every candidate,
    which keeps the candidates' cross-correlation: that is the point of the test.
    """
    if not series or len(series[0]) < 2:
        raise ValueError('the reality check needs at least two observations')
    length = len(series[0])
    if any(len(s) != length for s in series):
        raise ValueError('every candidate needs the same days')
    means = [st.fmean(s) for s in series]
    observed = max(means)
    rng = random.Random(seed)
    exceed = 0
    for _ in range(resamples):
        idx = stationary_indices(length, mean_block, rng)
        best = max(sum(s[k] for k in idx) / length - m for s, m in zip(series, means))
        exceed += best >= observed
    return (1 + exceed) / (1 + resamples)


def sharpe(returns: Sequence[float]) -> float:
    sd = st.pstdev(returns)
    return st.fmean(returns) / sd if sd > 0 else 0.0


def expected_max_sharpe(variance: float, trials: int) -> float:
    """The best Sharpe expected from ``trials`` skill-free attempts whose Sharpes have this variance."""
    if trials < 2 or variance <= 0:
        return 0.0
    return math.sqrt(variance) * ((1 - EULER_GAMMA) * NORMAL.inv_cdf(1 - 1 / trials)
                                  + EULER_GAMMA * NORMAL.inv_cdf(1 - 1 / (trials * math.e)))


def deflated_sharpe(returns: Sequence[float], *, trial_sharpes: Sequence[float], trials: int) -> float:
    """Probability the true Sharpe of ``returns`` beats the best of ``trials`` lucky ones.

    Sharpes are per observation, not annualised. ``trial_sharpes`` are the grid's, used only
    for their spread; ``trials`` is how many candidates were tried in all.
    """
    n = len(returns)
    if n < 3:
        raise ValueError('the deflated Sharpe needs at least three observations')
    mean, sd = st.fmean(returns), st.pstdev(returns)
    skew = sum(((r - mean) / sd) ** 3 for r in returns) / n if sd > 0 else 0.0
    kurt = sum(((r - mean) / sd) ** 4 for r in returns) / n if sd > 0 else 3.0
    variance = st.pvariance(trial_sharpes) if len(trial_sharpes) > 1 else 0.0
    return probabilistic_sharpe(sharpe(returns), n=n, skew=skew, kurtosis=kurt,
                                benchmark=expected_max_sharpe(variance, trials))


def probabilistic_sharpe(sr: float, *, n: int, skew: float, kurtosis: float, benchmark: float) -> float:
    """Probability the true Sharpe beats ``benchmark``, given ``n`` observations' Sharpe, skew and kurtosis.

    These four figures and the benchmark are all the deflated Sharpe reads from the returns, so
    a record that publishes them can be checked without its returns.
    """
    spread = 1 - skew * sr + (kurtosis - 1) / 4 * sr * sr
    z = (sr - benchmark) * math.sqrt(n - 1) / math.sqrt(spread) if spread > 0 else 0.0
    return NORMAL.cdf(z)


def pbo(series: Sequence[Sequence[float]], *, blocks: int = 16) -> float:
    """Probability of backtest overfitting of picking the best of ``series`` by Sharpe.

    The days are cut into ``blocks`` consecutive blocks. For every way of taking half of them
    as the training set (12,870 for 16), the candidate with the best Sharpe on those blocks is
    ranked by its Sharpe on the other half. The PBO is the share of splits where it ranks at
    or below the median. Noise gives about 0.5; an edge that persists gives about 0.
    """
    cells = len(series)
    if cells < 2 or blocks < 2 or blocks % 2:
        raise ValueError('the PBO needs at least two candidates and an even number of blocks')
    days = len(series[0])
    if any(len(s) != days for s in series) or days < 2 * blocks:
        raise ValueError('every candidate needs the same days, at least two a block')
    bounds = [round(b * days / blocks) for b in range(blocks + 1)]
    # Per block and candidate: count, sum and sum of squares, so a split's Sharpe is a few additions.
    stats = [[(hi - lo, sum(s[lo:hi]), sum(x * x for x in s[lo:hi])) for s in series]
             for lo, hi in zip(bounds, bounds[1:])]

    def sharpes(chosen) -> list[float]:
        out = []
        for c in range(cells):
            n = sum(stats[b][c][0] for b in chosen)
            total = sum(stats[b][c][1] for b in chosen)
            squares = sum(stats[b][c][2] for b in chosen)
            mean = total / n
            variance = max(squares / n - mean * mean, 0.0)
            out.append(mean / math.sqrt(variance) if variance > 0 else 0.0)
        return out

    overfit = splits = 0
    for train in itertools.combinations(range(blocks), blocks // 2):
        test = [b for b in range(blocks) if b not in train]
        fitted, held = sharpes(train), sharpes(test)
        pick = held[max(range(cells), key=fitted.__getitem__)]
        rank = sum(h < pick for h in held) + 1 + (sum(h == pick for h in held) - 1) / 2
        w = rank / (cells + 1)
        overfit += math.log(w / (1 - w)) <= 0
        splits += 1
    return overfit / splits
