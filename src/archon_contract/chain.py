"""An append-only record in which every entry is chained to the one before it by SHA-256.

The layout is the research desk's registry: one JSON file per record, numbered in the order
written, and ``manifest.json`` listing each file with its sha256 and the sha256 of the record
before it. Editing a record, deleting one, slipping one in, or editing one and then fixing
its manifest line all fail ``verify``. A correction is a new record that names the old one.

The checks are pure functions over bytes; ``verify`` and ``append`` are the thin layer that
reads and writes a directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Mapping, Sequence

MANIFEST = 'manifest.json'
RESERVED = frozenset({'seq', 'kind', 'subject', 'prev_sha256', 'written_utc'})


class ChainError(ValueError):
    """The record is not exactly as it was written, or a write would make it dishonest."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(body: Mapping) -> bytes:
    """The one serialisation every record and manifest is written in."""
    return (json.dumps(body, indent=1, sort_keys=True) + '\n').encode()


def check_manifest(entries: Sequence[Mapping]) -> str | None:
    """Check that the manifest's lines chain: numbered 1 to n, each naming the hash before it.

    This needs no record bodies, so it runs on a published manifest alone. Returns the head
    of the chain, the sha256 of the newest record, or None for an empty manifest.
    """
    previous = None
    for seq, entry in enumerate(entries, start=1):
        if entry.get('seq') != seq:
            raise ChainError(f'manifest line {seq} is numbered {entry.get("seq")}')
        if entry.get('prev_sha256') != previous:
            raise ChainError(f'manifest line {seq} ({entry.get("file")}) does not follow the line before it')
        if not re.fullmatch(r'[0-9a-f]{64}', str(entry.get('sha256'))):
            raise ChainError(f'manifest line {seq} ({entry.get("file")}) has no sha256')
        previous = entry['sha256']
    return previous


def verify_entries(entries: Sequence[Mapping], files: Mapping[str, bytes]) -> list[dict]:
    """Every record exactly as written, in order, or ChainError naming what changed.

    ``files`` maps each record file name present on disk to its bytes.
    """
    check_manifest(entries)
    listed = {e['file'] for e in entries}
    extra = sorted(set(files) - listed)
    if extra:
        raise ChainError(f'records not in the manifest: {", ".join(extra)}')
    records, previous = [], None
    for entry in entries:
        name = entry['file']
        if name not in files:
            raise ChainError(f'record {name} is in the manifest but missing')
        if sha256(files[name]) != entry['sha256']:
            raise ChainError(f'record {name} was edited after it was written')
        record = json.loads(files[name])
        if record.get('seq') != entry['seq'] or record.get('prev_sha256') != previous:
            raise ChainError(f'record {name} is out of sequence or its chain is broken')
        previous = entry['sha256']
        records.append(record)
    return records


def next_record(entries: Sequence[Mapping], records: Sequence[Mapping], kind: str, subject: str,
                body: Mapping, *, written_utc: str, once: bool = False) -> tuple[str, bytes, dict]:
    """The file name, bytes and manifest line of the record that would come next.

    ``once`` refuses a second record of this kind for this subject: an out-of-sample read,
    a freeze or a forward result is written once, whatever it says.
    """
    clash = RESERVED & set(body)
    if clash:
        raise ChainError(f'a record body cannot set {", ".join(sorted(clash))}')
    if once and any(r['kind'] == kind and r['subject'] == subject for r in records):
        raise ChainError(f'{subject} already has its {kind} record; it is written once')
    seq = len(entries) + 1
    previous = entries[-1]['sha256'] if entries else None
    record = {'seq': seq, 'kind': kind, 'subject': subject, 'prev_sha256': previous,
              'written_utc': written_utc, **body}
    name = f'{seq:04d}-{kind}-{re.sub(r"[^A-Za-z0-9_.-]+", "-", subject)}.json'
    data = encode(record)
    entry = {'seq': seq, 'file': name, 'kind': kind, 'subject': subject,
             'sha256': sha256(data), 'prev_sha256': previous}
    return name, data, entry


def read_manifest(directory: Path) -> list[dict]:
    path = Path(directory) / MANIFEST
    return json.loads(path.read_text())['records'] if path.exists() else []


def verify(directory: Path) -> list[dict]:
    """Verify a registry directory: the manifest, every record it lists, and nothing else."""
    directory = Path(directory)
    files = {p.name: p.read_bytes() for p in directory.glob('*.json') if p.name != MANIFEST}
    return verify_entries(read_manifest(directory), files)


def _write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, path)  # a reader never sees half a file


def append(directory: Path, kind: str, subject: str, body: Mapping, *, written_utc: str,
           once: bool = False) -> dict:
    """Write one record and its manifest line, refusing if the chain is already broken."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    records = verify(directory)
    entries = read_manifest(directory)
    name, data, entry = next_record(entries, records, kind, subject, body, written_utc=written_utc, once=once)
    path = directory / name
    if path.exists():
        raise ChainError(f'{name} already exists')
    _write(path, data)
    _write(directory / MANIFEST, encode({'records': [*entries, entry]}))
    return json.loads(data)
