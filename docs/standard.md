# The standard

One evaluator decides whether a strategy beats holding the same markets, and whether that win is
more than luck. Every strategy is judged by it the same way, and nothing else lists one. The
code in [`standard.py`](../src/archon_contract/standard.py) states the cut, the luck test and the
comparison with holding; this page states the whole standard.

## One strategy is one trial

A strategy is written down and hashed before anything runs it. It names its signal and bar
width, a grid of up to 100 parameter settings fixed in advance, how each test window's
setting is picked from the windows before it, how its positions become one book, and the markets
it may trade. Before a run, the strategy is counted on the store it's tested on (one venue's
market data), so a run that crashes still counts.

The settings are chosen inside the walk-forward, on earlier prices only, so a grid of many
settings is still one trial. A strategy that changes in any way is a new strategy, with a new
hash and a new count.

## The walk-forward

- **Markets, as known at the time.** A market joins a window when, at the window's first bar, it
  has the history the strategy needs, still trades, and has funding on record for every hour it
  could be held. Flat candles from before a market listed are dropped before anything reads them.
- **Windows.** Six-month windows start on 1 January and 1 July (UTC). Every setting is measured
  on every window. The first test window starts at least 365 days after the first
  window, and each test window trades the setting that scored best on all the windows before it.
  A test window is never scored with settings fitted on it.
- **One curve.** The test windows chain into one curve, and changing settings between windows
  pays to rebuild the whole book.
- **No look-ahead.** A decision at a close reads prices up to that close and nothing after it.

## Costs

Every change of position is charged 5.5 bps a side: the venue's taker fee plus
Archon's builder fee. Funding is charged on both sides as it settled: a long pays a positive
rate, a short receives it. The whole walk-forward, the choice of settings included, runs
again at 8.5 bps.

## The benchmark

Holding is an equal-weight basket of the markets eligible at the first test bar, bought there
with one entry fee, never rebalanced, and charged funding. A market that stops trading leaves its
share in cash.

## The verdict

- **R1, beat holding.** The curve makes more than holding and has a shallower worst fall, at
  both costs. Level with holding isn't beating it, and making more by falling further isn't
  either.
- **S2, more than luck.** The probabilistic Sharpe test (Bailey and Lopez de Prado), adjusted for
  skew and fat tails, of the strategy's daily log return over holding (UTC midnight to midnight,
  at the base cost) gives a p-value. It must fall below the Sidak cut `1 - (1 - 0.05)^(1/Neff)`,
  where Neff counts every strategy tried on that store: the ones tried before the record opened,
  and every one counted since, whether or not it reached a verdict. The cut holds the chance that
  luck alone passes S2 for any strategy on that store to 5%, and it tightens with every
  count.
  Hyperliquid's crypto store and its store including builder-deployed markets overlap, so their
  prior counts and every evaluation on either store share one Neff. Moving a strategy from one
  to the other cannot give it a looser luck-test bar. Other stores retain separate counts.
- **Verdict pass** exactly when R1 and S2 both pass. The listing tiers below distinguish this
  result from an Early listing.

Every verdict also reports, without judging on them, the share of test windows that beat their
hold on both counts, the median window's edge, and the mean edge without the two best windows.

## Listing

A strategy is listed from its verdict on the markets Hyperliquid trades. That verdict and its
latest verdict on every other store it was tested on must meet the applicable tier's requirements
under the current standard:

- **Proven.** Every verdict passes R1 and S2, each at its store's Neff today.
- **Early.** Every verdict passes R1 and made money at both costs, but S2 is not met on at least
  one store. Each also
  needs at least 548 tested days, at least 8 independent bets, an
  annual return of at least 10% at the higher cost, and a luck-test p-value
  below 0.05. No closed forward window may have fallen as far as holding did over the
  same days.

Independent bets measure how broadly returns are spread across consecutive 30-day blocks,
rather than being carried by a few blocks. The Early floor does not replace S2's across-trial
luck control: an Early strategy has not earned Proven status.

A failure of R1 on any store withholds the strategy. A forward-window demotion withdraws it
from both tiers. As later counts tighten S2, a Proven strategy can fall to Early if it still
qualifies. Entries rank Proven first, then by annual excess Sharpe, then by drawdown advantage
at the higher cost; near-duplicates list once. A strategy is offered for Hosted only while its
tested span, replayed on the market data it trades on, still makes money and beats holding on
return and worst fall.

Nothing keeps the catalogue full. When no strategy passes, nothing is listed.

## Forward windows

A 50-day forward window trades one setting of a strategy on live Hyperliquid
prices from the next close after it's written. It's never shortened, re-dated or scored early. Once
it ends, it's scored once, by replaying the strategy on the window's closed prices with the same
book and costs as the test.

A window checks that real trading matches the test, and it never lists a strategy. It withdraws
one for good when:

- a hosted run of the same window strays from the replay by more than 2 points of
  return, or
- the window falls deeper than the strategy fell over its whole walk-forward at
  8.5 bps.
