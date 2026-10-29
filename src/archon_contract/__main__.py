"""Check the published evidence, or watch the registry catch an edited record.

    python -m archon_contract evidence          # the shipped manifest's chain, and each excerpt against its line
    python -m archon_contract recompute         # the listing bar and the luck gate, rebuilt from the excerpts
    python -m archon_contract verify DIR        # a registry directory, record by record
    python -m archon_contract demo              # write three records, edit one, watch verify refuse
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from archon_contract import bar, chain, gates, luck

EVIDENCE = Path('evidence')


def excerpts(root: Path) -> tuple[list[dict], list[dict]]:
    """The manifest's lines and the record excerpts, each excerpt checked against its line."""
    entries = json.loads((root / 'registry' / 'manifest.json').read_text())['records']
    chain.check_manifest(entries)
    lines = {e['seq']: e for e in entries}
    records = json.loads((root / 'records.json').read_text())['records']
    for r in records:
        line = lines.get(r['seq'], {})
        if any(line.get(k) != r[k] for k in ('sha256', 'prev_sha256', 'kind', 'subject')):
            raise chain.ChainError(f'excerpt {r["seq"]:04d} is not the record its manifest line lists')
    return entries, records


def evidence(root: Path) -> int:
    entries, records = excerpts(root)
    print(f'manifest  {len(entries)} lines chained, head {entries[-1]["sha256"] if entries else None}')
    print(f'excerpts  {len(records)} records, each the one its manifest line lists')
    return 0


def days_between(first_utc: str, last_utc: str) -> float:
    first, last = (datetime.fromisoformat(t.replace('Z', '+00:00')) for t in (first_utc, last_utc))
    return (last - first).total_seconds() / 86400


def unseen_test(r: dict) -> tuple[bool, str]:
    """The listing bar rebuilt from an unseen test's figures. A record with no funding clause was
    written under the earlier bar, which is today's floor, and is judged by that."""
    res = r['result']
    m = bar.Measurement(
        return_pct=res['port_return_pct'], drawdown_pct=res['port_drawdown_pct'],
        hold_return_pct=res['hold_return_pct'], hold_drawdown_pct=res['hold_drawdown_pct'],
        cash_return_pct=bar.cash_pct(days_between(res['first_close_utc'], res['last_close_utc'])),
        median_market_pct=res['median_pct'], mean_ex_top2_pct=res['mean_ex_top2_pct'],
        unfunded_hours=res.get('funding_hours_missing', 0))
    earlier = 'funded' not in res['clauses']
    judged = bar.floor_clauses(m) if earlier else bar.clauses(m)
    clauses = {k: judged[k] for k in res['clauses']}
    passes = all(clauses.values())
    same = clauses == res['clauses'] and passes == r['passes']
    which = 'earlier bar (today\'s floor)' if earlier else 'bar'
    return same, (f'{which} {"pass" if passes else "fail"}: {m.return_pct:+.1f}% against holding\'s '
                  f'{m.hold_return_pct:+.1f}%, worst drawdown {m.drawdown_pct:.1f}% against {m.hold_drawdown_pct:.1f}%')


def proposal(r: dict) -> tuple[bool, str]:
    """The deflated Sharpe rebuilt from a proposal's published moments, and the luck gate on it."""
    sig, ds = r['significance'], r['significance']['deflated_sharpe']
    probability = luck.probabilistic_sharpe(ds['sharpe_daily'], n=sig['days'], skew=ds['skew'],
                                            kurtosis=ds['kurtosis'], benchmark=ds['expected_max_sharpe_daily'])
    gate = gates.luck(sig['reality_check_p'], probability, ds['trials'])
    return abs(probability - ds['probability']) < 1e-9, f'luck {"pass" if gate.passes else "fail"}: {gate.detail}'


def recompute(root: Path) -> int:
    """Rebuild, from the excerpts alone, the listing bar on every unseen test and the luck gate on
    every proposal, and compare each with what the record says."""
    _, records = excerpts(root)
    checked = differ = 0
    for r in records:
        if r['kind'].endswith('proposal'):
            same, line = proposal(r)
        elif 'oos' in r['kind']:
            same, line = unseen_test(r)
        else:
            continue
        what = 'correction' if r['kind'] == 'oos-correction' else 'unseen test' if 'oos' in r['kind'] else 'proposal'
        print(f'{r["seq"]:04d}  {r["subject"].split("-")[0]:<5} {what:<12} {line}'
              f'{"" if same else "  DIFFERS from the record"}')
        checked += 1
        differ += not same
    print(f'{checked} recomputed, {checked - differ} as recorded')
    return 1 if differ else 0


def verify(directory: Path) -> int:
    records = chain.verify(directory)
    print(f'{len(records)} records intact')
    return 0


def demo() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        steps = [('proposal', {'candidates_counted': 12, 'winner': 'candidate 7'}),
                 ('oos', {'passes': True}),
                 ('freeze', {'window': {'start_utc': '2026-10-28T16:00Z', 'end_utc': '2026-12-27T16:00Z'}})]
        for kind, body in steps:
            r = chain.append(root, kind, 'F001-demo', body, written_utc='2026-10-28T13:08:01+00:00',
                             once=kind != 'proposal')
            print(f'wrote     {r["seq"]:04d} {kind:<9} prev {str(r["prev_sha256"])[:12]}')
        print(f'verify    {len(chain.verify(root))} records intact')
        try:
            chain.append(root, 'oos', 'F001-demo', {'passes': False}, written_utc='2026-10-28T13:09:00+00:00',
                         once=True)
        except chain.ChainError as exc:
            print(f'refused   {exc}')
        target = root / '0002-oos-F001-demo.json'
        target.write_text(target.read_text().replace('true', 'false'))
        print('edited    0002: "passes": true -> false')
        try:
            chain.verify(root)
        except chain.ChainError as exc:
            print(f'refused   {exc}')
            return 0
    print('the edit went unnoticed', file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m archon_contract', description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    ev = sub.add_parser('evidence', help="check the shipped manifest's chain and each excerpt against its line")
    ev.add_argument('root', nargs='?', type=Path, default=EVIDENCE)
    ve = sub.add_parser('verify', help='verify a registry directory record by record')
    ve.add_argument('directory', type=Path)
    re_ = sub.add_parser('recompute', help='rebuild the listing bar and the luck gate from the excerpts')
    re_.add_argument('root', nargs='?', type=Path, default=EVIDENCE)
    sub.add_parser('demo', help='write three records, edit one, and watch verify refuse')
    args = parser.parse_args(argv)
    try:
        if args.command == 'evidence':
            return evidence(args.root)
        if args.command == 'recompute':
            return recompute(args.root)
        if args.command == 'verify':
            return verify(args.directory)
        return demo()
    except chain.ChainError as exc:
        print(f'refused   {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
