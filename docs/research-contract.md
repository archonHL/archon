# The research contract

A trading desk that improves itself has one obvious way to fail: it finds whatever fits the
past best, calls it an improvement and trades it. Try a few thousand candidates of anything and
some will look brilliant on history by chance. Archon's research desk runs on a contract built
to stop that, and every line of it is code with a test.

The lines below are the whole contract. Each one closes a specific way of fooling yourself.

## 1. Every trial counts

The desk keeps one global trial counter. It started from the configurations evaluated before
the desk existed, counted source by source from the evidence on disk. Every
candidate the desk or a sweep instantiates is added to it before it's measured, so a run that
crashes halfway still counts what it tried. The counter refuses to load if its log doesn't add
up, and it only goes up.

It matters because significance is deflated by it. A winner found after 5,000 tries has to be
far stronger than one found after 50, and the desk charges every try ever made against it, not
just the ones in the current search.

## 2. The search never sees the unseen prices

History is cut at a fixed split, 2026-03-01. A search reads bars that close before it and
nothing after. A test changes every later bar and checks that the proposal comes out identical;
another seals the later prices entirely and checks the search still runs the same. Look-ahead
inside a strategy is tested the same way: perturb every bar after `i`, and the funding settled
after it, and no decision at or before `i` may move.

## 3. Unseen prices are read once

Right after a search writes its in-sample record, its winner alone is measured on the prices
after the split, and that result is written at once, pass or fail. The registry refuses a second
read. Bars before the split serve only as warm-up, so no day the search saw is scored twice.

When a slice isn't fresh, the record says so. If earlier research looked at that slice for a
related strategy, the pass is written as `exposed`: a lead, which only a trial can turn into a
listing. A read later found to have scored days the search saw is corrected by a new record,
labelled a correction, which can never list anything.

## 4. Trials are fixed before they open

A candidate that passes its one read is frozen into a 60-day trial starting at the
next close of its own bar width. The freeze record carries the hash of the code that will score
it, the universe and the bar it must clear. The window is never shortened or re-dated. While it
runs, the registry records only coverage, never a return. The result is written once, when the
window has closed with every bar and every hourly funding settlement on record. A hole anywhere
leaves it `incomplete` and unscored.

New sweeps use the fixed forward window. Older records retain their preregistered sequential
plans and results; the [methodology](methodology.md#historical-read-then-trial) describes their
nominal confidence levels and unverified time-uniform calibration.

If the strategy's code has changed since the freeze, scoring is refused. A frozen candidate
can't be re-fitted to its own test.

## 5. Luck is measured three ways

Each proposal carries the figures that say how much of its result is luck:

| Figure | Question it answers |
|---|---|
| White's reality check | Over every candidate the search tried, could the best result have come from candidates with no edge? Stationary bootstrap, mean blocks of 10 days, 1,000 resamples. |
| Deflated Sharpe ratio | Does the winner's Sharpe beat the best Sharpe expected from that many skill-free tries? The count is the global trial counter. |
| Probability of backtest overfitting | Across every half-and-half split of the in-sample days, how often does the best candidate on one half rank at or below the median on the other? |

Listing needs both the reality check and the deflated Sharpe under 0.10. A sweep group
whose PBO is above 0.5 proposes nothing and spends no unseen read.

## 6. The gates are fixed in code

Listing and withdrawal run on gates in code. Changing one is a code change with its own commit,
never a setting, and the decisions made before the change stay in the record. A Proven
candidate passes the unseen read, luck, trial and engine gates. A Qualified candidate may list
before its trial ends if its additional qualification gates pass and the trial has not failed.
Qualification checks value-bound receipts and exposure references against a reviewed ledger.
Each measured leg also needs applicable provenance and a review of broader data exposure.
The engine gate compares the planner with fixed equal-weight shares or positions sized at
entry, as measured. It checks allocation without fees, funding or halts; executed-order
parity requires reconciliation with venue fills. Listing follows these gates automatically.
[Listing](promotion.md) has the detail.

## 7. Costs are never optional

The desk's realised-funding replay charges 5 bps on each unit of exposure changed
and each market's settled funding to both strategy and holding. The breakout's cost-matched
comparison uses realised funding; its older frozen constant-funding verdict charges funding
only to the strategy and is reported separately. A held hour with no settlement on record
fails the candidate outright. Holding starts on the strategy's own seed bar, keeping the
comparison aligned from the start.

## 8. Rank by the middle, not the tail

Candidates rank by their median, then by the mean with the two best markets removed, never by
the plain mean. One market that went up tenfold can make a weak strategy's average look great.

## 9. One record, append-only

Every proposal, read, freeze, result and decision is a record in a registry chained by SHA-256.
Verification detects broken links and stops the desk writing; comparison with an
independently retained head detects a rewritten chain. A correction is a new record that
names the old one.
[The registry](registry.md) shows how, and the [reference code](../src/archon_contract/chain.py)
lets anyone check it.

## 10. Replace, never empty

A listed strategy that falls short of the bar isn't dropped, which would leave subscribers with
nothing while research continues. If it still clears a lower floor and hasn't broken its
drawdown limit, it stays listed and trading, marked as being upgraded, until a stronger
candidate that passes the full bar takes its place. A strategy under the floor, or past its
drawdown limit, is withdrawn the same day.

## 11. Every number is declared

Each record says what it's net of and what it isn't: the universe and its survivorship, the
venue's history cap, how far stored funding reaches, how many held bars have no settlement,
and the costs not modelled. These are replays on closed candles, and the records say that too.
