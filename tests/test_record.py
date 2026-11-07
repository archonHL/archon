import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from archon_contract import record, standard, windows
from archon_contract.__main__ import main

STORE = 'hyperliquid'
PROC = record.sha256(b'procedure one')
OPENED = datetime(2026, 10, 26, 8, tzinfo=timezone.utc)
BAR = 4 * 3_600_000


def utc(when: datetime) -> str:
    return when.isoformat(timespec='seconds')


def verdict_lines(tmp_path, n: int, *, r1=True):
    rng = random.Random(5)
    excess = [rng.gauss(0.002, 0.01) for _ in range(500)]
    ret = 30.0 if r1 else 20.0
    levels = {str(fee): {'return_pct': ret, 'drawdown_pct': -20.0, 'hold': {'return_pct': 25.0, 'drawdown_pct': -40.0}}
              for fee in (standard.FEE_BPS, standard.STRESS_FEE_BPS)}
    p, cut = standard.psr_p(excess), standard.sidak(n)
    doc = {'levels': levels, 's2': {'psr_p': p}}
    whole = json.dumps({**doc, 'daily_excess': {str(i): x for i, x in enumerate(excess)}}, sort_keys=True).encode()
    bodies = tmp_path / 'verdicts'
    bodies.mkdir(exist_ok=True)
    (bodies / f'{record.sha256(whole)}.json').write_bytes(whole)
    return {'store': STORE, 'procedure_hash': PROC, 'r1': r1, 'verdict': doc, 'verdict_sha256': record.sha256(whole),
            's2': {'psr_p': p, 'neff': n, 'cut': cut, 'passes': p < cut}}


def write(tmp_path, lines, name='record.jsonl'):
    path = tmp_path / name
    for kind, body, when in lines:
        record.append(path, kind, body, written_utc=utc(when))
    return path


def base(tmp_path):
    start, end = windows.opening(int(OPENED.timestamp() * 1000), BAR)
    return [('genesis', {'prior_groups': {STORE: 2}}, OPENED),
            ('register', {'procedure_hash': PROC}, OPENED),
            ('spend', {'store': STORE, 'procedure_hash': PROC}, OPENED),
            ('verdict', verdict_lines(tmp_path, 3), OPENED),
            ('window-open', {'procedure_hash': PROC, 'venue': STORE, 'start_ms': start, 'end_ms': end}, OPENED)]


def closed(tmp_path, *, drawdown=-10.0, demoted=False, verdict_seq=4):
    lines = base(tmp_path)
    after = OPENED + timedelta(days=windows.FORWARD_DAYS + 1)
    if demoted:
        lines.append(('demotion', {'procedure_hash': PROC, 'window': 5, 'reasons': ['risk']}, after))
    lines.append(('window-close', {'window': 5, 'procedure_hash': PROC, 'verdict_seq': verdict_seq,
                                   'paper': {'return_pct': 3.0, 'drawdown_pct': drawdown},
                                   'testnet_return_pct': None, 'reasons': []}, after))
    return lines


@pytest.fixture
def path(tmp_path):
    return write(tmp_path, closed(tmp_path))


def test_a_whole_record_checks(path, tmp_path):
    found = record.rows(path.read_bytes())
    assert [r['seq'] for r in found] == [1, 2, 3, 4, 5, 6]
    assert found[0]['prev_sha256'] is None
    assert found[1]['prev_sha256'] == record.sha256(path.read_bytes().split(b'\n')[0])
    seen = record.check(found, tmp_path / 'verdicts')
    assert seen == {'verdicts': 1, 'windows_open': 0, 'windows_closed': 1, 'neff': {STORE: 3}}


def test_lines_are_canonical_json(path):
    for line in path.read_bytes().splitlines():
        assert line == json.dumps(json.loads(line), sort_keys=True, separators=(',', ':')).encode()


def lines_of(path):
    return path.read_bytes().split(b'\n')[:-1]


def put(path, lines):
    path.write_bytes(b''.join(line + b'\n' for line in lines))


@pytest.mark.parametrize('change', [
    lambda ls: [ls[0], ls[1].replace(b'"seq":2', b'"seq":2,"x":1'), *ls[2:]],  # an edit
    lambda ls: [ls[0], *ls[2:]],                                             # a deletion
    lambda ls: [ls[0], ls[2], ls[1], *ls[3:]],                               # a swap
    lambda ls: [*ls[:2], ls[1], *ls[2:]],                                    # an insertion
])
def test_any_change_but_to_the_newest_line_breaks_the_chain(path, change):
    put(path, change(lines_of(path)))
    with pytest.raises(record.RecordError, match='out of sequence or its chain is broken'):
        record.rows(path.read_bytes())


def test_the_genesis_is_first_and_only_first(tmp_path):
    with pytest.raises(record.RecordError):
        write(tmp_path, [('register', {'procedure_hash': PROC}, OPENED)])
    with pytest.raises(record.RecordError):
        write(tmp_path, [('genesis', {'prior_groups': {}}, OPENED), ('genesis', {'prior_groups': {}}, OPENED)], 'b.jsonl')


def test_a_cut_off_line_or_an_unknown_kind_fails(path, tmp_path):
    data = path.read_bytes()
    with pytest.raises(record.RecordError, match='not a whole record'):
        record.rows(data[:-1])
    with pytest.raises(record.RecordError, match='not a record'):
        record.rows(data + b'{"seq": 7\n')
    with pytest.raises(record.RecordError):
        record.append(path, 'promotion', {}, written_utc=utc(OPENED))


def test_no_write_after_tampering_and_no_body_sets_the_chain(path):
    put(path, [lines_of(path)[0], lines_of(path)[1].replace(PROC.encode(), b'0' * 64), *lines_of(path)[2:]])
    with pytest.raises(record.RecordError):
        record.append(path, 'register', {'procedure_hash': 'x'}, written_utc=utc(OPENED))
    with pytest.raises(record.RecordError, match='cannot set'):
        record.append(path.with_name('new.jsonl'), 'genesis', {'seq': 9}, written_utc=utc(OPENED))


def rewritten(tmp_path, at: int, edit):
    """The base record with line ``at``'s body edited and the chain written again, as a forger would."""
    lines = base(tmp_path)
    kind, body, when = lines[at - 1]
    lines[at - 1] = (kind, edit(json.loads(json.dumps(body))), when)
    return record.rows(write(tmp_path, lines, 'forged.jsonl').read_bytes())


def loosened(body):
    body['s2'].update(neff=1, cut=standard.sidak(1))
    return body


@pytest.mark.parametrize('at, edit, match', [
    (4, loosened, 'judged at Neff 1'),
    (4, lambda b: {**b, 's2': {**b['s2'], 'passes': not b['s2']['passes']}}, 'S2 says'),
    (4, lambda b: {**b, 'r1': False}, 'R1 says False'),
    (3, lambda b: {**b, 'store': 'elsewhere'}, 'not counted'),
    (2, lambda b: {'procedure_hash': 'another'}, 'not registered'),
])
def test_a_rechained_forgery_still_breaks_the_standard(tmp_path, at, edit, match):
    with pytest.raises(record.RecordError, match=match):
        record.check(rewritten(tmp_path, at, edit), tmp_path / 'verdicts')


def test_a_verdict_body_must_match_its_line_and_its_p_value(path, tmp_path):
    found = record.rows(path.read_bytes())
    body = tmp_path / 'verdicts' / f'{found[3]["verdict_sha256"]}.json'
    whole = json.loads(body.read_bytes())
    whole['daily_excess']['0'] += 1.0
    body.write_bytes(json.dumps(whole, sort_keys=True).encode())
    with pytest.raises(record.RecordError, match='not the one it recorded'):
        record.check(found, tmp_path / 'verdicts')
    body.unlink()
    with pytest.raises(record.RecordError, match='missing'):
        record.check(found, tmp_path / 'verdicts')
    assert record.check(found)['verdicts'] == 1  # without the bodies, the line alone


def test_a_window_must_open_before_its_first_bar_and_run_its_days(tmp_path):
    lines = base(tmp_path)
    start = lines[4][1]['start_ms']
    lines[4] = ('window-open', {**lines[4][1], 'end_ms': start + windows.DAY_MS}, OPENED)
    with pytest.raises(record.RecordError, match='days long'):
        record.check(record.rows(write(tmp_path, lines, 'short.jsonl').read_bytes()))
    lines = base(tmp_path)
    late = datetime.fromtimestamp(start / 1000, tz=timezone.utc)
    lines[4] = (*lines[4][:2], late)
    with pytest.raises(record.RecordError, match='after its first bar'):
        record.check(record.rows(write(tmp_path, lines, 'late.jsonl').read_bytes()))


def test_a_window_is_never_read_early(tmp_path):
    lines = closed(tmp_path)
    lines[-1] = (*lines[-1][:2], OPENED + timedelta(days=windows.FORWARD_DAYS - 1))
    with pytest.raises(record.RecordError, match='before it ended'):
        record.check(record.rows(write(tmp_path, lines).read_bytes()))


@pytest.mark.parametrize('drawdown, demoted, ok', [(-10.0, False, True), (-25.0, True, True),
                                                   (-25.0, False, False), (-10.0, True, False)])
def test_a_window_withdraws_its_strategy_exactly_when_it_should(tmp_path, drawdown, demoted, ok):
    found = record.rows(write(tmp_path, closed(tmp_path, drawdown=drawdown, demoted=demoted)).read_bytes())
    if ok:
        record.check(found)
    else:
        with pytest.raises(record.RecordError, match='withdrawal does not follow'):
            record.check(found)


@pytest.mark.parametrize('kind', ['demotion', 'window-close'])
def test_a_window_s_closing_rows_must_name_its_procedure(tmp_path, kind):
    lines = closed(tmp_path, drawdown=-25.0, demoted=True)
    other = record.sha256(b'procedure two')
    # A second registered procedure is valid, but cannot replace this window's identity.
    lines.insert(5, ('register', {'procedure_hash': other}, lines[5][2]))
    at = next(i for i, (row_kind, _, _) in enumerate(lines) if row_kind == kind)
    _, body, when = lines[at]
    lines[at] = (kind, {**body, 'procedure_hash': other}, when)
    found = record.rows(write(tmp_path, lines).read_bytes())
    with pytest.raises(record.RecordError, match='different procedure'):
        record.check(found, tmp_path / 'verdicts')


@pytest.mark.parametrize('kind', ['demotion', 'window-close'])
def test_a_window_s_closing_rows_refuse_a_missing_procedure(tmp_path, capsys, kind):
    lines = closed(tmp_path, drawdown=-25.0, demoted=True)
    at = next(i for i, (row_kind, _, _) in enumerate(lines) if row_kind == kind)
    _, body, when = lines[at]
    lines[at] = (kind, {k: v for k, v in body.items() if k != 'procedure_hash'}, when)
    path = write(tmp_path, lines)
    with pytest.raises(record.RecordError, match='missing procedure_hash'):
        record.check(record.rows(path.read_bytes()), tmp_path / 'verdicts')
    assert main(['verify', str(path)]) == 1
    assert 'missing procedure_hash' in capsys.readouterr().err


def test_a_window_is_scored_against_its_procedure_s_latest_verdict(tmp_path):
    with pytest.raises(record.RecordError, match='latest'):
        record.check(record.rows(write(tmp_path, closed(tmp_path, verdict_seq=None)).read_bytes()))
