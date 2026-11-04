"""Check a copy of the record, print a cut, or watch the record refuse an edit.

    python -m archon_contract verify RECORD     # the chain, then every verdict and window against the standard
    python -m archon_contract cut NEFF          # the p-value S2 must fall below after NEFF procedures
    python -m archon_contract demo              # write a small record, edit it, watch verify refuse
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from archon_contract import record, standard, windows

STORE = 'hyperliquid'
WHEN = '2026-10-26T08:00:00+00:00'


def verify(path: Path, bodies: Path | None) -> int:
    found = record.rows(path.read_bytes())
    if not found:
        raise record.RecordError(f'{path} holds no genesis')
    seen = record.check(found, bodies)
    head = record.sha256(path.read_bytes().rstrip(b'\n').rsplit(b'\n', 1)[-1])
    print(f'chain     {len(found)} lines, head {head}')
    print(f'verdicts  {seen["verdicts"]} as the standard says'
          + (', each S2 recomputed from its daily excess' if bodies else ''))
    print(f'windows   {seen["windows_closed"]} closed as opened, {seen["windows_open"]} open')
    for store, n in seen['neff'].items():
        print(f'neff      {store} {n}, cut {standard.sidak(n):.6f}' if n else f'neff      {store} 0')
    return 0


def demo() -> int:
    rng = random.Random(7)
    excess = [rng.gauss(0.002, 0.01) for _ in range(730)]
    proc = record.sha256(b'a demo procedure')
    levels = {str(fee): {'return_pct': 55.0, 'drawdown_pct': -18.0, 'hold': {'return_pct': 40.0, 'drawdown_pct': -52.0}}
              for fee in (standard.FEE_BPS, standard.STRESS_FEE_BPS)}
    with tempfile.TemporaryDirectory() as tmp:
        path, bodies = Path(tmp) / 'record.jsonl', Path(tmp) / 'verdicts'
        bodies.mkdir()
        p, n = standard.psr_p(excess), 3
        doc = {'levels': levels, 'r1': standard.r1(levels), 's2': {'psr_p': p}}
        whole = json.dumps({**doc, 'daily_excess': dict(enumerate(excess))}, sort_keys=True).encode()
        (bodies / f'{record.sha256(whole)}.json').write_bytes(whole)
        start, end = windows.opening(int(datetime.fromisoformat(WHEN).timestamp() * 1000), 4 * 3_600_000)
        lines = [('genesis', {'prior_groups': {STORE: 2}}),
                 ('register', {'procedure_hash': proc}),
                 ('spend', {'store': STORE, 'procedure_hash': proc}),
                 ('verdict', {'store': STORE, 'procedure_hash': proc, 'r1': doc['r1'], 'verdict': doc,
                              'verdict_sha256': record.sha256(whole),
                              's2': {'psr_p': p, 'neff': n, 'cut': standard.sidak(n), 'passes': p < standard.sidak(n)}}),
                 ('window-open', {'procedure_hash': proc, 'venue': STORE, 'start_ms': start, 'end_ms': end})]
        for kind, body in lines:
            r = record.append(path, kind, body, written_utc=WHEN)
            print(f'wrote     {r["seq"]} {kind:<11} prev {str(r["prev_sha256"])[:12]}')
        verify(path, bodies)

        text = path.read_text()
        path.write_text(text.replace('"r1":true', '"r1":false', 1))
        print('edited    line 4: R1 true -> false')
        try:
            record.rows(path.read_bytes())
            return 1
        except record.RecordError as exc:
            print(f'refused   {exc}')

        path.unlink()
        for kind, body in lines:
            if kind == 'verdict':
                body = {**body, 'r1': False}
            record.append(path, kind, body, written_utc=WHEN)
        print('rewrote   the chain from line 4 on, so every hash links again')
        try:
            record.check(record.rows(path.read_bytes()), bodies)
            return 1
        except record.RecordError as exc:
            print(f'refused   {exc}')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m archon_contract', description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    ve = sub.add_parser('verify', help='check a copy of the record against its chain and the standard')
    ve.add_argument('record', type=Path)
    ve.add_argument('--bodies', type=Path, help='the whole verdicts (default: verdicts/ beside the record, if present)')
    cu = sub.add_parser('cut', help='the p-value S2 must fall below after NEFF procedures')
    cu.add_argument('neff', type=int)
    sub.add_parser('demo', help='write a small record, edit it, and watch verify refuse')
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            beside = args.record.parent / 'verdicts'
            return verify(args.record, args.bodies or (beside if beside.is_dir() else None))
        if args.command == 'cut':
            print(f'{standard.sidak(args.neff):.6g}')
            return 0
        return demo()
    except (record.RecordError, ValueError) as exc:
        print(f'refused   {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
