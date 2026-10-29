# The registry

Everything the desk does is written down once, in order, in a registry nobody can edit after
the fact. It's the reason a listing means something: anyone holding the records can replay the
chain and see that the proposal came before the read, the read before the freeze, and the freeze
before the trial opened.

## Records

Each record is one JSON file, numbered in the order written and never changed after.

| Kind | Written when |
|---|---|
| `proposal`, `family-proposal` | A search finishes in sample. Carries every candidate counted, the winner, the split, the trial count and the luck figures. |
| `oos`, `family-oos` | The winner's one read of the prices after the split. Written at once, pass or fail, and only once per candidate. |
| `oos-correction` | A read is found to have scored days the search saw. The original stays; the correction names it and can never list anything. |
| `freeze`, `family-freeze` | A passing candidate, or a neighbour, is frozen into a 60-day trial with the hash of the code that will score it. |
| `sequential-plan` | The daily test a trial will be read by, written before the trial's first bar. |
| `qualify` | The seven qualification tests, written once, pass or fail. |
| `forward-result`, `family-forward-result` | The trial has closed with every bar and settlement on record. Written once. |
| `decision` | A listing, withdrawal, upgrade or restore, with every gate's figures and the hashes of the records it rests on. |

Every record also carries the sha256 of the candles and funding it read, and its declarations:
universe and survivorship, history cap, funding coverage, costs not modelled.

## The chain

`manifest.json` lists every record with its sha256 and the sha256 of the record before it, and
every record carries its sequence number and its predecessor's hash inside it. So:

- an edited record no longer matches its hash;
- an edited record with its manifest line fixed breaks the next line's link;
- a deleted record leaves a gap in the sequence;
- a record slipped in isn't in the manifest, or breaks the links after it.

Each of those fails verification, and the desk refuses to write anything once verification
fails. Writers take an exclusive lock on the registry and readers a shared one, and every file
is written to a temporary name and renamed, so a reader never sees half a record or a record its
manifest doesn't list yet.

## The trial counter

The trial counter sits beside the registry: a baseline counted from the evidence that existed before
the desk, then a log of every addition with its running total. Additions happen before
measurement. The counter refuses to load if the baseline doesn't add up to its sources, if a log
entry doesn't follow the one before it, or if the count isn't the last total.

## One writer

A hash chain has exactly one writer, or it forks. The production server is the only writer of
the record.

Research runs elsewhere, on a copy, and comes back as a bundle: the new records byte for byte,
the record they follow, and every trial-counter entry the run added. The server appends a bundle
only if its own chain still ends where the bundle began and its counter still stands where the
bundle's trials started. Otherwise it refuses, and the research is rebased and run again. Trials
are counted before anything is measured, so a run that crashes still carries its count back to
the server.

## The public record

The desk's feed serves the registry to anyone without signing in: a summary, the timeline of
every record newest first with its hash and its predecessor's, the trials in progress and the
trial counter. The feed verifies the chain before serving it, and a registry that fails
verification is withheld rather than served.

An open trial shows its progress, days elapsed and performance so far against holding, labelled
as tracking. The registry itself writes no partial return, and listing reads only the result
written when the trial closes or the test its plan fixed in advance.

## Check it

This repository ships the registry's manifest, and excerpts of its proposals and unseen tests.

```sh
python -m archon_contract evidence
```

`evidence` checks the shipped manifest: its lines are numbered in order, each names the hash of
the line before it, and every excerpt in [`records.json`](../evidence/records.json) is the
record its manifest line lists. The record bodies stay on the desk, so this checks the manifest's
own chain rather than every byte of every record; the head hash it prints is the one the desk's
public feed serves. [`chain.py`](../src/archon_contract/chain.py) is the verifier, and
`python -m archon_contract demo` writes three records, edits one and shows verification refuse it.
