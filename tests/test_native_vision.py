import io
import json
import zipfile

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from bjlab.api import app
from bjlab.corner_vision import CornerCardDetector,validate_layout
from bjlab.engine import Rules
from bjlab.live import LiveObserver
from bjlab.vision_diagnostics import diagnostic_bundle
from classic_fixture import classic_table


def layout():
    return {'table':(0,0,1,1),'dealer':(500/1280,400/1439,270/1280,175/1439),
            'player:0':(500/1280,665/1439,270/1280,175/1439)}


def test_card_roles_need_disjoint_explicit_regions():
    for invalid in ({'table':(0,0,1,1)},layout()|{'dealer':layout()['player:0']},
                    layout()|{'table':(.6,.6,.1,.1)},layout()|{'dealer':(0,0,float('nan'),.1)}):
        with pytest.raises(ValueError):validate_layout(invalid)


def test_upright_ranks_and_identical_instances_do_not_need_green_surface():
    image=classic_table(('7','7'),('A',))
    # Change the green background only; card recognition is role/pixel-based.
    import numpy as np
    pixels=np.asarray(image).copy();pixels[(pixels[:,:,1]>100)&(pixels[:,:,0]<30)]=(70,20,90)
    detector=CornerCardDetector(layout());found=detector.detect(Image.fromarray(pixels))
    assert [d.rank for d in found if d.zone=='player:0']==['7','7']
    assert [d.rank for d in found if d.zone=='dealer']==['A']
    assert detector.context['phase']=='unknown' and not detector.context['player_totals']
    assert all(c['provenance']=='current-pixel-ocr' for c in detector.last_diagnostics['candidates'])


def test_unknown_pixels_do_not_create_certain_cards_or_certified_count():
    observer=LiveObserver(Rules(),samples=100,layout=layout(),fresh_shoe=True,manual_turn=True)
    image=classic_table(('7','2'),obscure_rank=True)
    for i in range(4):report=observer.process(image,i,i+1.)
    assert report['advice'] is None and report['count_reliable'] is False
    assert report['true_count'] is None and report['running_count'] is None
    with pytest.raises(ValueError,match='geometry changed'):
        observer.process(image.resize((640,720)),4,5.)


def test_requested_zip_replays_exact_upload_and_retains_provenance():
    observer=LiveObserver(Rules(),samples=100,layout=layout())
    image=classic_table();raw=io.BytesIO();image.save(raw,format='PNG')
    observer.process(image,0,1.)
    bundle=diagnostic_bundle(observer,image,raw.getvalue(),{'source_size':[1280,1439]})
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        assert archive.read('received-upload.bin')==raw.getvalue()
        record=json.loads(archive.read('diagnostic.json'))
        assert record['source_id']==observer.source_id
        assert record['received_size']==[1280,1439]
        assert record['configuration']['layout']
        assert any(name.startswith('crops/candidate-') for name in archive.namelist())


def test_capture_source_geometry_change_is_rejected_even_if_upload_size_matches():
    with TestClient(app) as client:
        stream=client.post('/api/live',json={'layout':layout(),'samples':100}).json()['stream_id']
        image=classic_table();raw=io.BytesIO();image.save(raw,format='PNG')
        headers={'x-bjlab-capture':json.dumps({'source_size':[1280,1439],'source_rect':[0,0,1280,1439]})}
        first=client.post(f'/api/live/{stream}/frame?sequence=0&timestamp=1&diagnostic=true',content=raw.getvalue(),headers=headers)
        assert first.status_code==200 and first.headers['content-type']=='application/zip'
        headers['x-bjlab-capture']=json.dumps({'source_size':[2560,2878],'source_rect':[0,0,1280,1439]})
        changed=client.post(f'/api/live/{stream}/frame?sequence=1&timestamp=2',content=raw.getvalue(),headers=headers)
        assert changed.status_code==422 and 'Recalibrate' in changed.json()['detail']
        client.delete('/api/live/'+stream)
