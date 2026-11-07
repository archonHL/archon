"""The desk's record: an append-only hash chain of what was registered, counted, judged and forward-tested.

The record is one file of lines, each one JSON object. Line ``seq`` names its own number and
``prev_sha256``, the sha256 of the exact bytes of the line before it (without its line break), so
editing, deleting, reordering or slipping in a line breaks the chain. The first line is the
genesis, and only the first. Nothing anchors the newest line, so only a copy that holds it catches
its removal. The kinds:

- ``genesis``: the procedures tried before the record opened, per store (``prior_groups``).
- ``register``: a procedure's hash, written before anything runs it. A hash registers once.
- ``spend``: one counted evaluation of a registered procedure on a store, written before it runs,
  so a run that crashes still counts. Every count raises the store's Neff by one.
- ``verdict``: the evaluator's verdict, with R1, the S2 p-value and the Neff and cut it was judged
  at, and the sha256 of the whole verdict, whose daily series is kept beside the record.
- ``window-open``, ``window-close``, ``demotion``: forward windows (``archon_contract.windows``).

``rows`` checks the chain; ``check`` then holds every verdict and window to the standard.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from archon_contract import standard, windows

KINDS = ('genesis', 'register', 'spend', 'verdict', 'window-open', 'window-close', 'demotion', 'flagship')
HYPERLIQUID = 'hyperliquid'
HYPERLIQUID_ALL = 'hyperliquid-all'
SHARED_STORES = (HYPERLIQUID, HYPERLIQUID_ALL)
SERIES = ('daily_excess', 'daily_book')


class RecordError(ValueError):
    """The record is not exactly as it was written, or a line breaks the standard."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rows(data: bytes) -> list[dict]:
    """Every line of a record, in order, or RecordError naming the first line that breaks the chain."""
    *lines, rest = data.split(b'\n')
    out, previous = [], None
    for seq, text in enumerate(lines, start=1):
        try:
            row = json.loads(text)
        except ValueError:
            raise RecordError(f'line {seq} is not a record') from None
        if (not isinstance(row, dict) or row.get('seq') != seq or row.get('prev_sha256') != previous
                or row.get('kind') not in KINDS or (row['kind'] == 'genesis') != (seq == 1)):
            raise RecordError(f'line {seq} is out of sequence or its chain is broken')
        previous = sha256(text)
        out.append(row)
    if rest:
        raise RecordError(f'line {len(out) + 1} is not a whole record')
    return out


def append(path: Path, kind: str, body: Mapping, *, written_utc: str) -> dict:
    """Write one line after the chain verifies, as canonical JSON."""
    path = Path(path)
    data = path.read_bytes() if path.exists() else b''
    found = rows(data)
    clash = set(body) & {'seq', 'kind', 'prev_sha256', 'written_utc'}
    if clash:
        raise RecordError(f'a record body cannot set {", ".join(sorted(clash))}')
    previous = sha256(data.rstrip(b'\n').rsplit(b'\n', 1)[-1]) if found else None
    line = json.dumps({'seq': len(found) + 1, 'kind': kind, 'prev_sha256': previous, 'written_utc': written_utc,
                       **body}, sort_keys=True, separators=(',', ':')).encode()
    rows(data + line + b'\n')
    path.write_bytes(data + line + b'\n')
    return json.loads(line)


def _ms(utc: str) -> int:
    return int(datetime.fromisoformat(utc.replace('Z', '+00:00')).timestamp() * 1000)


def _verdict(r: Mapping, n: int, bodies: Path | None) -> None:
    s2, at = r['s2'], f'record {r["seq"]}'
    if s2['neff'] != n or not math.isclose(s2['cut'], standard.sidak(n), rel_tol=1e-12):
        raise RecordError(f'{at}: judged at Neff {s2["neff"]}, cut {s2["cut"]}; the store had tried {n} procedures')
    if s2['passes'] != (s2['psr_p'] < s2['cut']):
        raise RecordError(f'{at}: S2 says {s2["passes"]} for p {s2["psr_p"]} against the cut {s2["cut"]}')
    if r['r1'] != standard.r1(r['verdict']['levels']):
        raise RecordError(f'{at}: R1 says {r["r1"]}, and its figures at both costs say otherwise')
    if bodies is None:
        return
    try:
        whole = (bodies / f'{r["verdict_sha256"]}.json').read_bytes()
    except FileNotFoundError:
        raise RecordError(f'{at}: its whole verdict is missing') from None
    doc = json.loads(whole)
    if sha256(whole) != r['verdict_sha256'] or {k: v for k, v in doc.items() if k not in SERIES} != r['verdict']:
        raise RecordError(f'{at}: its whole verdict is not the one it recorded')
    if not math.isclose(standard.psr_p(list(doc['daily_excess'].values())), s2['psr_p'], rel_tol=1e-9, abs_tol=1e-12):
        raise RecordError(f'{at}: its daily excess does not give the S2 p-value it recorded')


def _neff(store: str, prior: Mapping, tried: Mapping) -> int:
    group = SHARED_STORES if store in SHARED_STORES else (store,)
    return sum(prior.get(s, 0) + tried.get(s, 0) for s in group)


def check(found: Sequence[Mapping], bodies: Path | None = None) -> dict:
    """Hold every verdict and forward window in ``found`` to the standard, or RecordError naming the first that breaks it.

    A procedure is counted only once registered, and judged only once counted. A verdict's Neff is
    every procedure tried on its store before it (the genesis' ``prior_groups`` plus every count),
    shared across the two overlapping Hyperliquid stores,
    its cut is the Sidak cut there, and its R1 and S2 follow from its own figures. With ``bodies``,
    the directory of whole verdicts, each verdict's daily excess is read again and its S2 p-value
    recomputed. A window opens before its first bar, runs ``windows.FORWARD_DAYS``, closes only
    after it ends, and withdraws its strategy exactly when ``windows.withdraws`` says so. Returns
    the counts it checked and each store's Neff now.
    """
    registered, counted, tried, latest, opened, withdrawn = set(), set(), {}, {}, {}, set()
    prior = found[0]['prior_groups'] if found else {}
    closed = verdicts = 0
    for r in found[1:]:
        kind, at = r['kind'], f'record {r["seq"]}'
        if kind == 'register':
            if r['procedure_hash'] in registered:
                raise RecordError(f'{at}: the procedure is already registered')
            registered.add(r['procedure_hash'])
        elif kind == 'spend':
            key = (r['store'], r['procedure_hash'])
            if r['procedure_hash'] not in registered or key in counted:
                raise RecordError(f'{at}: a count of a procedure not registered, or counted there already')
            counted.add(key)
            tried[r['store']] = tried.get(r['store'], 0) + 1
        elif kind == 'verdict':
            key = (r['store'], r['procedure_hash'])
            if key not in counted:
                raise RecordError(f'{at}: a verdict on a procedure not counted on its store before it ran')
            _verdict(r, _neff(r['store'], prior, tried), bodies)
            latest[key] = r['seq']
            verdicts += 1
        elif kind == 'window-open':
            if r['procedure_hash'] not in registered:
                raise RecordError(f'{at}: a window on a procedure not registered')
            if r['end_ms'] - r['start_ms'] != windows.FORWARD_DAYS * windows.DAY_MS:
                raise RecordError(f'{at}: a window not {windows.FORWARD_DAYS} days long')
            if _ms(r['written_utc']) >= r['start_ms']:
                raise RecordError(f'{at}: a window written after its first bar')
            opened[r['seq']] = r
        elif kind == 'demotion':
            if r['window'] not in opened:
                raise RecordError(f'{at}: a withdrawal by no open window')
            if 'procedure_hash' not in r:
                raise RecordError(f'{at}: missing procedure_hash')
            if r['procedure_hash'] != opened[r['window']]['procedure_hash']:
                raise RecordError(f'{at}: withdraws a different procedure from its window')
            withdrawn.add(r['window'])
        elif kind == 'window-close':
            w = opened.pop(r['window'], None)
            if w is None or _ms(r['written_utc']) < w['end_ms']:
                raise RecordError(f'{at}: closes no open window, or closes one before it ended')
            if 'procedure_hash' not in r:
                raise RecordError(f'{at}: missing procedure_hash')
            if r['procedure_hash'] != w['procedure_hash']:
                raise RecordError(f'{at}: closes a different procedure from its window')
            if r['verdict_seq'] != latest.get((w['venue'], w['procedure_hash'])):
                raise RecordError(f'{at}: scored against a verdict other than its procedure\'s latest')
            verdict = found[r['verdict_seq'] - 1]['verdict'] if r['verdict_seq'] else None
            if windows.withdraws(r, verdict) != (r['window'] in withdrawn):
                raise RecordError(f'{at}: its strategy\'s withdrawal does not follow from the window')
            closed += 1
    return {'verdicts': verdicts, 'windows_open': len(opened), 'windows_closed': closed,
            'neff': {s: _neff(s, prior, tried) for s in sorted({*prior, *tried})}}
