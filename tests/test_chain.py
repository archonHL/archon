import json
from pathlib import Path

import pytest

from archon_contract import chain

ROOT = Path(__file__).resolve().parents[1]
WHEN = '2026-10-28T12:00:00+00:00'


@pytest.fixture
def registry(tmp_path):
    chain.append(tmp_path, 'proposal', 'C001', {'candidates': 6}, written_utc=WHEN)
    chain.append(tmp_path, 'oos', 'C001', {'passes': True}, written_utc=WHEN, once=True)
    chain.append(tmp_path, 'freeze', 'C001', {'days': 60}, written_utc=WHEN, once=True)
    return tmp_path


def test_records_chain_in_order(registry):
    records = chain.verify(registry)
    assert [r['seq'] for r in records] == [1, 2, 3]
    assert records[0]['prev_sha256'] is None
    entries = chain.read_manifest(registry)
    assert records[1]['prev_sha256'] == entries[0]['sha256']
    assert records[2]['prev_sha256'] == entries[1]['sha256']


def test_an_edited_record_fails(registry):
    path = registry / '0002-oos-C001.json'
    path.write_text(path.read_text().replace('true', 'false'))
    with pytest.raises(chain.ChainError, match='edited after it was written'):
        chain.verify(registry)


def test_an_edit_with_its_manifest_line_fixed_still_fails(registry):
    path = registry / '0002-oos-C001.json'
    path.write_text(path.read_text().replace('true', 'false'))
    manifest = json.loads((registry / 'manifest.json').read_text())
    manifest['records'][1]['sha256'] = chain.sha256(path.read_bytes())
    (registry / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(chain.ChainError, match='does not follow'):
        chain.verify(registry)


def test_a_deleted_record_fails(registry):
    (registry / '0002-oos-C001.json').unlink()
    with pytest.raises(chain.ChainError, match='missing'):
        chain.verify(registry)


def test_a_record_slipped_in_fails(registry):
    (registry / '0004-oos-C002.json').write_bytes(chain.encode({'seq': 4}))
    with pytest.raises(chain.ChainError, match='not in the manifest'):
        chain.verify(registry)


def test_a_dropped_manifest_line_fails(registry):
    manifest = json.loads((registry / 'manifest.json').read_text())
    del manifest['records'][1]
    (registry / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(chain.ChainError):
        chain.verify(registry)


def test_no_write_after_tampering(registry):
    path = registry / '0001-proposal-C001.json'
    path.write_text(path.read_text().replace('6', '5'))
    with pytest.raises(chain.ChainError):
        chain.append(registry, 'decision', 'C001', {'verdict': 'promote'}, written_utc=WHEN)
    assert len(chain.read_manifest(registry)) == 3


def test_a_once_record_is_written_once(registry):
    with pytest.raises(chain.ChainError, match='written once'):
        chain.append(registry, 'oos', 'C001', {'passes': False}, written_utc=WHEN, once=True)
    chain.append(registry, 'oos', 'C002', {'passes': False}, written_utc=WHEN, once=True)


def test_a_body_cannot_set_the_chain_fields(tmp_path):
    with pytest.raises(chain.ChainError, match='cannot set'):
        chain.append(tmp_path, 'proposal', 'C001', {'prev_sha256': None}, written_utc=WHEN)


def test_the_published_manifest_chains():
    entries = json.loads((ROOT / 'evidence' / 'registry' / 'manifest.json').read_text())['records']
    head = chain.check_manifest(entries)
    assert [e['seq'] for e in entries] == list(range(1, len(entries) + 1))
    assert head == entries[-1]['sha256']


def test_a_reordered_manifest_fails():
    entries = json.loads((ROOT / 'evidence' / 'registry' / 'manifest.json').read_text())['records']
    swapped = [*entries[:10], entries[11], entries[10], *entries[12:]]
    with pytest.raises(chain.ChainError):
        chain.check_manifest(swapped)
