"""Independent matching and verification-access contracts, not model accuracy."""
import json
import pytest

from validation.tools.specialized_card_compare import geometry_pairs,load_corpus,digest


def test_global_pairing_never_uses_rank_to_rescue_a_wrong_read():
    a=[{'bbox':(10,10,20,40),'rank':'A'},{'bbox':(40,10,20,40),'rank':'5'}]
    b=[{'bbox':(10,10,20,40),'rank':'5'},{'bbox':(40,10,20,40),'rank':'A'}]
    pairs,missing,extra=geometry_pairs(a,b)
    assert not missing and not extra
    assert all(x['rank']!=y['rank'] for x,y in pairs)


def test_duplicate_boxes_do_not_create_second_correct_instance():
    a=[{'bbox':(10,10,20,40)}]
    b=[{'bbox':(10,10,20,40)},{'bbox':(10,10,20,40)}]
    pairs,missing,extra=geometry_pairs(a,b)
    assert len(pairs)==1 and len(extra)==1 and not missing


def test_unrelated_object_is_not_matched_to_missing_card():
    pairs,missing,extra=geometry_pairs([{'bbox':(0,0,20,40)}],[{'bbox':(80,80,20,40)}])
    assert not pairs and len(missing)==len(extra)==1


def test_verification_requires_preselected_corpus_and_unused_status(tmp_path):
    truth=tmp_path/'verification.truth.json'; truth.write_text('[]')
    (tmp_path/'manifest.json').write_text(json.dumps({'partitions':{'verification':{'truth_sha256':digest(truth)}}}))
    with pytest.raises(ValueError,match='preselected'): load_corpus(tmp_path,'verification')
    select=tmp_path/'selected.json'; select.write_text(json.dumps({'data_manifest_sha256':digest(tmp_path/'manifest.json'),'verification_previously_used':True}))
    with pytest.raises(ValueError,match='Consumed'): load_corpus(tmp_path,'verification',select)


def test_final_holdout_is_not_accepted(tmp_path):
    (tmp_path/'manifest.json').write_text('{}')
    with pytest.raises(ValueError,match='final holdout'): load_corpus(tmp_path,'final_holdout')


def test_interrupted_verification_is_consumed_but_paired_baseline_is_allowed(tmp_path):
    from validation.tools import specialized_card_compare as comparison
    from validation.tools.overlap_session import sources
    selection=tmp_path/'selection.json'
    selection.write_text(json.dumps({
        'evaluator_sha256':digest(comparison.__file__),
        'verification_previously_used':False,
        'verification_jobs':{key:{'corpus_sha256':'frozen','source_hashes':sources(tmp_path)}
                             for key in ('perception-specialized','perception-current')},
    }))
    comparison.verification_claim(selection,'perception-specialized','frozen',None,tmp_path)
    with pytest.raises(ValueError,match='already consumed'):
        comparison.verification_claim(selection,'perception-specialized','frozen',None,tmp_path)
    claim=comparison.verification_claim(selection,'perception-current','frozen',None,tmp_path)
    result=tmp_path/'result.json'; result.write_text('{}')
    comparison.verification_complete(claim,result)
    ledger=json.loads(selection.with_suffix('.consumption.json').read_text())
    assert ledger['jobs']['perception-specialized']['status']=='started'
    assert ledger['jobs']['perception-current']['result_sha256']==digest(result)


def test_verification_selection_cannot_change_evaluator_or_inference(tmp_path):
    from validation.tools import specialized_card_compare as comparison
    selection=tmp_path/'selection.json'
    record={'evaluator_sha256':'changed','verification_previously_used':False,
            'verification_jobs':{'perception-current':{'corpus_sha256':'frozen','source_hashes':{}}}}
    selection.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='Evaluator changed'):
        comparison.verification_claim(selection,'perception-current','frozen',None,tmp_path)
    record['evaluator_sha256']=digest(comparison.__file__)
    record['verification_jobs']['perception-current']['source_hashes']={'bjlab/reader.py':'old'}
    selection.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='Inference source changed'):
        comparison.verification_claim(selection,'perception-current','frozen',None,tmp_path)
