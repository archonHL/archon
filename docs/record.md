# The record

Everything the desk registers, counts, judges and forward-tests is a line in one append-only
record. [`record.py`](../src/archon_contract/record.py) reads it and checks it.

## Inputs for verification

The verifier needs a complete `record.jsonl` file. The website’s timeline shows selected fields;
its rows do not contain all the bytes needed to recompute each hash. Production record and verdict
files are not included in this repository. The demo creates its own small sample.

A complete record lets `verify` check the chain and the decisions recorded in it. To recompute S2
from daily figures, also supply the full verdict files, named by their hashes, in a `verdicts`
folder beside the record. The command accepts `--bodies` for a different folder.

## Lines and the chain

The record is one file with one JSON object per line, written with sorted keys and no spaces.
Every line carries:

| Field | What it is |
|---|---|
| `seq` | The line's number, from 1 |
| `kind` | What the line records (below) |
| `prev_sha256` | The sha256 of the exact bytes of the line before it, without its line break; `null` on line 1 |
| `written_utc` | When it was written |

Line 1 is the genesis, and no other line is. Editing, deleting, reordering or slipping in a line
changes a hash that the next line names, so the chain breaks there. The newest line has no line
after it, so a copy proves everything up to its head, and two copies with the same head hold the
same record. `python -m archon_contract verify` prints the head.

A count looks like this:

```json
{"kind":"spend","prev_sha256":"…","procedure_hash":"…","seq":3,"store":"hyperliquid","written_utc":"…"}
```

## Kinds

| Kind | Written | Holds |
|---|---|---|
| `genesis` | First, once | How many strategies were tried on each store before the record opened (`prior_groups`) |
| `register` | Before anything runs the strategy | Its hash. A hash registers once |
| `spend` | Before a counted run | The store and the strategy's hash. Each raises that store's Neff by one |
| `verdict` | After the run | R1, the S2 p-value with the Neff and cut it was judged at, the figures at both costs, and the sha256 of the whole verdict, whose daily figures are kept beside the record |
| `window-open` | Before the window's first bar | The strategy, the setting it trades, and the window's first and last bar |
| `demotion` | When a window withdraws a strategy | The window and why |
| `window-close` | Once the window has ended | The replay, the hosted run's return, and the verdict it was compared with |
| `flagship` | When a strategy becomes the one every hosted account trades | Its hash, the day it took over, why, and the strategy it replaced. The latest is current. It never changes a verdict, a listing or a window |

## What `verify` checks

- Every line follows the one before it, numbered in order, and the genesis is line 1.
- A strategy is counted only once registered, and judged only once counted on that store.
- Each verdict's Neff is every strategy tried on its store before it, its cut is the Sidak cut
  for that Neff, and its R1 and S2 follow from its own figures. The overlapping `hyperliquid`
  and `hyperliquid-all` stores share the sum of their genesis counts and every evaluation on
  either store. Other stores keep separate counts; counting the same strategy on both
  Hyperliquid stores adds two evaluations, even if only one reaches a verdict.
- With the whole verdicts in a `verdicts` folder beside the record, each matches its sha256 and
  its line, and its S2 p-value is recomputed from its daily figures.
- Each window opened before its first bar, runs 50 days, closed only after it
  ended, was compared with its strategy's latest verdict, and withdrew its strategy exactly when
  the standard says it must. Its withdrawal and close rows must name the procedure in its opening.
