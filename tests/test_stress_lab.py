import json

import cv2
import numpy as np
import pytest

from validation.tools.stress_lab import PROFILES, bulk, generate, render, run, timeline


def test_hidden_cards_do_not_expose_rank_and_occlusion_is_measured():
    card = {'id':'face','rank':'A','suit':'S','zone':'player:0'}
    stage = {'phase':'player','cards':[card,dict(card,id='second',rank='5',suit='H'),
             {'id':'hole','face_down':True,'zone':'dealer'}]}
    _, clean = render(stage, PROFILES['clean'])
    _, overlap = render(stage, PROFILES['overlap'])
    hole = next(c for c in overlap if c['card_id']=='hole')
    assert hole['presence']=='covered'
    assert hole['rank'] is None and hole['physical_rank'] is None and hole['suit'] is None
    assert next(c for c in overlap if c['card_id']=='face')['body_visible_fraction'] < next(c for c in clean if c['card_id']=='face')['body_visible_fraction']
    assert next(c for c in overlap if c['card_id']=='face')['corner_visible_fraction'] == 1
    _, clipped = render(stage, PROFILES['clipped'])
    assert next(c for c in clipped if c['card_id']=='face')['corner_visible_fraction'] < .85


def test_seeded_complete_sessions_have_visible_boundaries_and_no_hidden_ids_in_pixels():
    stages = timeline(41990, 2)
    assert stages == timeline(41990, 2)
    phases = {s['phase'] for s in stages}
    assert {'waiting','dealing','dealer','settled'} <= phases
    assert sum(s['phase']=='settled' for s in stages)==2
    stage = next(s for s in stages if s['cards'])
    changed = dict(stage,cards=[dict(c,id='different') for c in stage['cards']])
    assert np.array_equal(np.asarray(render(stage,PROFILES['clean'])[0]),np.asarray(render(changed,PROFILES['clean'])[0]))


def test_generated_video_decodes_full_timeline_and_freezes_inputs(tmp_path):
    target = tmp_path/'corpus'
    manifest = generate(target,rounds=1,seed=41232,profiles=['clean'])
    session = manifest['sessions'][0]
    cap = cv2.VideoCapture(str(target/session['video']))
    count = 0
    while cap.read()[0]: count += 1
    cap.release()
    truth = json.loads((target/session['truth']).read_text())
    assert count == session['frames'] == len(truth) and count > 12
    assert truth[0]['cards']==[] and truth[0]['seen']=={}
    first_face = next(r for r in truth if any(c['physical_rank'] for c in r['cards']))
    assert len(first_face['seen'])==1  # Future dealt cards must not enter exposure truth.
    with pytest.raises(FileExistsError): generate(target,1,41232,['clean'])
    (target/session['video']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash mismatch'): run(target/'manifest.json',target/'result.json')


def test_synthetic_runner_rejects_provider_or_holdout_claims(tmp_path):
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps({'kind':'original-provider-video','partition':'development'}))
    with pytest.raises(ValueError,match='development synthetic'): run(path,tmp_path/'result.json')
    path.write_text(json.dumps({'kind':'own-synthetic-continuous-video','partition':'final-holdout'}))
    with pytest.raises(ValueError,match='development synthetic'): run(path,tmp_path/'result.json')


def test_bounded_engine_batch_includes_splits_without_claiming_training():
    result = bulk(150,seed=4423)
    assert result['rounds']==150 and result['actions']['split']>0
    assert result['api_requests']==0 and not result['independent_evaluator']
    assert 'no vision' in result['scope']
