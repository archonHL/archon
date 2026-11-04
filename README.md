<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/hero-dark.svg">
  <img alt="Archon: the trading desk that improves itself" src="assets/readme/hero-light.svg" width="100%">
</picture>

# Archon

**The first self-improving trading desk on Hyperliquid.**

Agents propose strategies around the clock. One evaluator tests each one on prices it was never
tuned on, and Archon lists a strategy only when it beats simply holding the same markets, on
return and on its worst fall, by more than luck can explain. Every step is a line in an
append-only record, each line chained to the one before it by its hash.

This repository is that standard and the code that checks it: small, dependency-free, tested
Python, and the standard in plain words.

## How a strategy is listed

1. **Counted.** A strategy is written down and hashed before anything runs it, then counted on
   the market data it's tested on. One strategy is one trial, and every count makes the bar for
   the next one stricter.
2. **Tested.** It's tested walk-forward: each six months trades the settings that did best on
   the prices before them, never the prices it's scored on. Every trade is charged
   5.5 bps a side plus funding, and the whole test runs again at 8.5 bps.
3. **Judged.** It must make more than holding the same markets and fall less from its best, at
   both costs. Its daily edge over holding must also pass a luck test that tightens with every
   strategy ever tried on that data.
4. **Listed.** Only while both hold. No person approves a listing, nothing keeps the catalogue
   full, and the catalogue may be empty.

A strategy can also run a 50-day forward window on live prices. The window
checks that real trading matches the test, and it can withdraw a strategy. It never lists one.

## Verify it yourself

Python 3.10 or later; the package has no dependencies.

```sh
git clone https://github.com/archonHL/archon.git && cd archon
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'
python -m pytest -q
python -m archon_contract demo                 # write a small record, edit it, watch verify refuse
python -m archon_contract cut 31               # the luck test's bar after 31 strategies on one store
python -m archon_contract verify record.jsonl  # check a copy of the record
```

`verify` checks the chain line by line, then holds every verdict and forward window in it to the
standard: each verdict's luck bar is the one its store had earned, its pass or fail follows from
its own figures, and each window opened before its first bar, ran its full length and withdrew
its strategy exactly when it should. With the whole verdicts beside the record, it recomputes
each luck test from its daily figures.

## Layout

| Path | What it is |
|---|---|
| [`src/archon_contract/`](src/archon_contract/) | The standard's cut, luck test and comparison with holding, the forward windows, and the record's verifier |
| [`tests/`](tests/) | Their tests, including planted edges, pure noise and forged records |
| [`docs/standard.md`](docs/standard.md) | The standard in plain words: one strategy, one trial; the walk-forward; costs; the two tests; listing; forward windows |
| [`docs/record.md`](docs/record.md) | The record: its lines, its kinds and what a copy proves |

## License

[Apache-2.0](LICENSE), code and docs alike.
