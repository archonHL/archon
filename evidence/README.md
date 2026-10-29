# Evidence

What the verify commands read, from Archon's research record.

| File | What it is |
|---|---|
| [`registry/manifest.json`](registry/manifest.json) | The registry's manifest, byte for byte: every record with its sha256 and its predecessor's. |
| [`records.json`](records.json) | Every proposal and unseen test in the registry, passes and failures alike, as excerpts at full precision: no parameters, cells or per-market rows. Each carries the sha256 its manifest line lists. |

```sh
python -m archon_contract evidence     # the manifest's chain, and each excerpt against its line
python -m archon_contract recompute    # the listing bar and the luck gate, rebuilt from the excerpts
```

An unseen test whose record has no funding clause was written under the earlier bar, which is
today's floor; `recompute` judges it by that and says so.
