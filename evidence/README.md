# Evidence

The research-record snapshot used by the verification commands. Its head hash identifies
the snapshot for comparison with another copy or the desk's live feed.

| File | What it is |
|---|---|
| [`registry/manifest.json`](registry/manifest.json) | The registry's manifest, byte for byte: every record with its sha256 and its predecessor's. |
| [`records.json`](records.json) | Every proposal and unseen test in the registry, passes and failures alike, as excerpts at full precision: no parameters, cells or per-market rows. Each carries the sha256 its manifest line lists. |

```sh
python -m archon_contract evidence     # the manifest chain and excerpt identifying fields
python -m archon_contract recompute    # the listing bar and the luck gate, rebuilt from the excerpts
```

`evidence` verifies the manifest's sequence and hash links, then matches the identifying
fields of each excerpt to its manifest entry. Authenticating all excerpted values against
their record hashes requires the complete original records.

`recompute` checks the listing and luck calculations using the excerpted figures.
Reproducing the underlying backtests additionally requires their market data and scoring
implementation.

An unseen test whose record has no funding clause was written under the bar before 28 Oct 2026,
which beat holding on return or drawdown; `recompute` judges it by that and says so.
