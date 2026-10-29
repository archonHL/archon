# Methodology

How the desk measures a strategy, searches for better ones and decides how much of what it
finds is luck. [The research contract](research-contract.md) is the summary; this is the working
detail.

## Data

The market store holds Hyperliquid's own candles and the hourly funding every perp settled,
from the venue's public API. The research universe is the liquid perps of the day it was
frozen, and every figure declares that survivorship. A wider store of perps above a daily
volume floor serves in-sample research, with the same declaration.

Bar width is a dimension of the search: a slice is 1h, 2h, 4h or 1d bars, funding is summed per
bar whatever its width, and a warm-up is the same span of time on any width. The venue decides
which widths have an in-sample slice at all. Hyperliquid returns the last 5,000 candles of an
interval, which on 1h bars is about 208 days, all after the split, so 1h candidates go straight
to trial. The longer widths reach back as far as the stored funding does.

## Measuring a strategy

A strategy is measured as the engine trades it. It's long or flat per market, either equal-weight
across the universe or holding a set number of positions at once, each sized at entry and left
to drift. Leverage multiplies the notional, and fees and funding are charged on the levered
notional. Every measurement applies the account's 30% drawdown halt: from the
first close that far under its peak, the account goes flat, as a deployed one would.

The engine is held to this. A test drives the planner on a simulated account and checks it
reproduces the desk's curve bar for bar at 1, 1.5 and 2x.

## The listing bar

One copy of the bar judges every measurement, net of fees and realised funding, against holding
the same markets from the same seed bar:

1. The return is positive.
2. It beats cash earning 4% a year over the same span.
3. It beats holding by at least 5 points of return, with a worst drawdown no
   deeper than holding's.
4. It isn't carried by its winners: the median market return and the mean excluding the top two
   are both positive.
5. Every held market-hour was charged the funding it settled.

Beside it sits the floor: the same bar with clause 3 met by at least
5 points of return or by at least 10 points of
shallower drawdown. The floor lists nothing. It only decides whether a listed strategy that
slips below the bar is being upgraded or withdrawn ([listing](promotion.md)).

## Search

The desk only instantiates what has been written down first. A strategy enters research as a
short module with a one-sentence economic reason and the candidates it will try, declared
before anything is measured. A module is never edited in place: a change is a new module, and
every record carries the sha256 of the code and constants it measured, so a record always names
exactly what produced it.

Sweeps run the same contract at volume. Each sweep declares its candidates, hashes the
declaration with the code that decides and scores each one, and adds them to the trial counter
before one is measured. A cursor beside the registry records every candidate ever declared, so
each is measured once, ever, and repeated sweeps walk forward through the space in a seeded
low-discrepancy order instead of finishing one corner first.

Measurement at that volume uses vectorised kernels, one market-by-bar matrix per slice. The
kernels are held to the reference implementation to 1e-9 on every figure, and wherever float
error could flip a decision (a close exactly on its average, funding exactly on a cap) the bar
is decided again with the reference arithmetic. Before anything is written, each finalist is
measured again by the reference code, and a difference above 1e-6 stops the run.

## Selection

Selection reads only the in-sample slice:

1. Eligible: the candidate passes the listing bar on the whole in-sample slice, and its account
   halt never fired.
2. Ranked by the median, across anchored folds of the in-sample days, of the mean daily excess
   over holding; then by the mean excluding the top two markets; then by the median market.
3. De-duplicated: a candidate whose daily excess correlates above 0.9 with a better
   one is skipped.
4. Overfitting checked per group by PBO, below.

The best few per group are finalists, and the next few go on trial unread as their neighbours.

A strategy can also pre-register controls, measured on the same candidates and counted as
trials: for a ranked strategy, the same positions filled in name order, in reverse rank and in
seeded random order. If the controls do as well, the ranking adds nothing, the strategy is
retired and its finalists are never read on unseen prices.

## How much is luck

Every figure here is computed on the daily return of the candidate's portfolio minus the daily
return of holding the same markets.

White's reality check asks whether the best candidate in the search could be luck. The
stationary bootstrap (Politis and Romano) resamples days in blocks of geometric length, mean
10 days, 1,000 times. One resample index serves every candidate, which
keeps their cross-correlation.

The deflated Sharpe ratio (Bailey and Lopez de Prado) gives the probability that the winner's
Sharpe beats the best Sharpe expected from N skill-free tries, adjusted for the skew and
kurtosis of its returns. N is the global trial counter.

The probability of backtest overfitting (Bailey, Borwein, Lopez de Prado and Zhu) cuts the
in-sample days of a sweep group into 16 consecutive blocks. For every way to take
half of them, the candidate with the best Sharpe on that half is ranked on the other half. The
PBO is the share of splits where it lands at or below the median: pure noise gives about 0.5
and a persistent edge about 0. A group whose PBO is above 0.5 proposes nothing.

All three are implemented in [`luck.py`](../src/archon_contract/luck.py), with tests that plant
an edge in noise and check each figure finds it. A proposal records the Sharpe, skew, kurtosis,
day count and benchmark its deflated Sharpe was computed from, so `python -m archon_contract
recompute` can rebuild the probability from the published record alone.

## Unseen test, then trial

A finalist gets its one unseen read, written at once. A pass is frozen into a
60-day trial. Every sweep reads the same post-split slice, so for a sweep that
read is a selection step rather than a holdout: the sweep adds one trial per read to the
counter first, and its proposals are deflated against the count that includes them.

Neighbours go on trial without any unseen read. They can never be listed, since listing needs a
passing read, but their trials collect evidence on the finalists' neighbours on prices nobody
has seen.

A trial frozen with a plan is read once a day by an always-valid 95%
confidence sequence on the daily return over holding, from day 21 to day
60. It passes the first day its lower bound is above zero with a worst drawdown no
deeper than holding's, and fails the first day its upper bound is below zero. Otherwise the
window's own result at its close decides.

## Where the next budget goes

The desk keeps a memory beside the registry, append-only and hash-chained like it: per group
and per sweep, how many candidates it measured, how many beat the group's previous best in
sample, the PBO and the finalists' unseen verdicts. When a sweep runs with a budget, Thompson
sampling splits it across groups by each group's odds of producing an improvement, with an
unseen verdict weighing ten candidates. A fifth of the budget is split evenly first, so no group
with candidates left starves. A group still setting records gets more of the next sweep, and a
group never tried gets explored.

The memory never opens a slice and never copies an unseen figure. It only records what the
registry already holds, and verification refuses a memory row that doesn't name its registry
record by sequence number and hash.
