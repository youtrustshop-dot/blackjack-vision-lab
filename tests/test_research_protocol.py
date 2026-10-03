import json
import stat

import pytest

from bjlab.research_protocol import seal, verify, disjoint, consume_final


def corpus(tmp_path, name, split='train', group='session-1'):
    root = tmp_path / name; root.mkdir()
    (root/'frame.txt').write_text('original pixels or annotation bytes')
    record = seal(root, split=split, groups=[group], scope='unit fixture')
    return root, record


def test_frozen_content_and_manifest_tampering_are_detected(tmp_path):
    root, sealed = corpus(tmp_path, 'one')
    assert verify(root, sealed['seal_sha256']) == sealed['record']
    with pytest.raises(ValueError): seal(root, split='train', groups=['session-1'], scope='unit fixture')
    path=root/'frame.txt'; path.chmod(stat.S_IWRITE | stat.S_IREAD); path.write_text('changed')
    with pytest.raises(ValueError): verify(root, sealed['seal_sha256'])


def test_recording_group_cannot_leak_across_splits(tmp_path):
    _, first = corpus(tmp_path, 'train')
    _, second = corpus(tmp_path, 'validation', 'validation')
    with pytest.raises(ValueError): disjoint([first['record'], second['record']])


def test_final_holdout_is_consumed_once_even_when_candidate_changes(tmp_path):
    root, sealed = corpus(tmp_path, 'final', 'final_holdout')
    ledger = root/'.final-evaluation.json'
    consume_final(root, sealed['seal_sha256'], ledger, candidate='candidate-a', baseline='baseline-a')
    with pytest.raises(FileExistsError):
        consume_final(root, sealed['seal_sha256'], ledger, candidate='candidate-b', baseline='baseline-a')
    with pytest.raises(ValueError):
        consume_final(root, sealed['seal_sha256'], tmp_path/'other.json', candidate='candidate-b', baseline='baseline-a')


def test_seal_traversal_and_empty_corpus_are_rejected(tmp_path):
    empty=tmp_path/'empty'; empty.mkdir()
    with pytest.raises(ValueError): seal(empty, split='train', groups=['g'], scope='unit')
    root, sealed=corpus(tmp_path,'full')
    record=sealed['record']; record['files'][0]['file']='../outside.txt'
    target=root/'seal.json';target.chmod(stat.S_IWRITE | stat.S_IREAD)
    target.write_text(json.dumps(record))
    from bjlab.research_protocol import digest
    with pytest.raises(ValueError): verify(root,digest(target))
