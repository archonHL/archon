import json
from pathlib import Path

import pytest

from archon_contract import __main__ as cli
from archon_contract import chain

EVIDENCE = Path(__file__).resolve().parents[1] / 'evidence'


@pytest.fixture
def evidence(tmp_path):
    (tmp_path / 'registry').mkdir()
    for rel in ('registry/manifest.json', 'records.json'):
        (tmp_path / rel).write_bytes((EVIDENCE / rel).read_bytes())
    return tmp_path


def edit_records(root, change):
    data = json.loads((root / 'records.json').read_text())
    change(data['records'])
    (root / 'records.json').write_text(json.dumps(data))


def test_the_shipped_evidence_checks_and_recomputes_as_recorded(evidence):
    assert cli.evidence(evidence) == 0
    assert cli.recompute(evidence) == 0


def test_an_excerpt_that_is_not_its_manifest_line_is_refused(evidence):
    edit_records(evidence, lambda rs: rs[0].update(sha256='0' * 64))
    with pytest.raises(chain.ChainError):
        cli.excerpts(evidence)


def test_a_changed_figure_no_longer_recomputes_as_recorded(evidence):
    def flip(rs):
        read = next(r for r in rs if r['kind'].endswith('oos') and r['passes'] and 'funded' in r['result']['clauses'])
        read['result']['hold_return_pct'] = read['result']['port_return_pct']
    edit_records(evidence, flip)
    assert cli.recompute(evidence) == 1


def test_a_changed_luck_figure_no_longer_recomputes_as_recorded(evidence):
    def skew(rs):
        p = next(r for r in rs if r['kind'].endswith('proposal'))
        p['significance']['deflated_sharpe']['skew'] += 0.5
    edit_records(evidence, skew)
    assert cli.recompute(evidence) == 1


def test_every_unseen_test_in_the_manifest_is_an_excerpt(evidence):
    entries = json.loads((evidence / 'registry/manifest.json').read_text())['records']
    records = json.loads((evidence / 'records.json').read_text())['records']
    wanted = {e['seq'] for e in entries if e['kind'].endswith(('proposal', 'oos', 'oos-correction'))}
    assert wanted == {r['seq'] for r in records}
