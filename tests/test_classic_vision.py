import base64
import io
import pytest
from fastapi.testclient import TestClient
from bjlab.api import app
from bjlab.engine import Rules
from bjlab.external_vision import AdaptiveCardDetector, ClassicCasinoDetector
from bjlab.live import LiveObserver
from classic_fixture import classic_table


@pytest.mark.parametrize('rank', ('A','2','3','4','5','6','7','8','9','10','J','Q','K'))
def test_printed_ranks_with_symbol_pips(rank):
    detector=ClassicCasinoDetector()
    found=detector.detect(classic_table((rank,'2')))
    assert [d.rank for d in found if d.zone=='player:0']==[rank,'2']
    assert [d.rank for d in found if d.zone=='dealer']==['6']
    assert detector.context['phase']=='player'
    assert set(detector.context['controls'])=={'hit','stand','double'}
    assert not detector.context['reasons']


@pytest.mark.parametrize('scale', (.75,1,1.25))
def test_window_scale_and_nested_preview_do_not_create_extra_hands(scale):
    detector=AdaptiveCardDetector()
    found=detector.detect(classic_table(scale=scale,duplicate=True))
    assert [d.rank for d in found]==['6','7','2']
    assert detector.context['table_bounds'][0]>=1280*scale
    assert not detector.context['reasons']


def test_missed_card_and_wrong_total_withhold_guidance():
    observer=LiveObserver(Rules(decks=4),samples=100)
    image=classic_table(('7','2','3'),obscure_rank=True)
    for i in range(4):report=observer.process(image,i,i+1.)
    assert report['advice'] is None
    assert any('total' in reason for reason in report['gate']['reasons'])


def test_live_hit_reveal_settlement_and_identical_next_hand_count_once():
    observer=LiveObserver(Rules(decks=4),samples=100)
    sequence=0
    def observe(image,n=5):
        nonlocal sequence
        for _ in range(n):
            report=observer.process(image,sequence,sequence+1.)
            sequence+=1
        return report
    first=observe(classic_table())
    assert first['advice']['best_action']=='double'
    assert (first['observed_cards'],first['running_count'])==(3,2)
    repeat=observe(classic_table())
    assert repeat['observed_cards']==3
    hit=observe(classic_table(('7','2','J'),actions=('HIT','STAND')))
    assert hit['advice']['best_action']=='stand'
    assert (hit['observed_cards'],hit['running_count'])==(4,1)
    settled=observe(classic_table(('7','2','J'),('6','10'),message='You win',actions=()))
    assert settled['advice'] is None and settled['phase']=='settled'
    assert (settled['observed_cards'],settled['running_count'])==(5,0)
    next_hand=observe(classic_table())
    assert next_hand['advice']['best_action']=='double'
    assert (next_hand['observed_cards'],next_hand['running_count'])==(8,2)
    assert next_hand['round']==2


def test_image_api_reads_printed_cards_without_manual_confirmation_fields():
    image=classic_table(('10','Q'),('8',))
    data=io.BytesIO();image.save(data,format='PNG')
    with TestClient(app) as client:
        response=client.post('/api/advisor/image',json={'image_base64':base64.b64encode(data.getvalue()).decode(),'rules':{'decks':4}})
    assert response.status_code==200
    report=response.json()
    assert report['source']=='single-image-pixels'
    assert report['player']==['10','Q'] and report['dealer']==['8']
    assert report['advice']['best_action']=='stand'
    assert report['observed_cards']==3 and report['recognition_profile']=='classic-casino-ocr'


def test_actual_compressed_video_decoding_tracks_new_cards_and_redeals(tmp_path):
    import cv2
    import numpy as np
    stages=[classic_table(),classic_table(('7','2','J'),actions=('HIT','STAND')),
            classic_table(('7','2','J'),('6','10'),message='You win',actions=()),
            classic_table(blank=True),classic_table()]
    path=tmp_path/'printed-table.avi'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),5.,stages[0].size)
    assert writer.isOpened()
    for stage in stages:
        for _ in range(5):writer.write(np.asarray(stage)[:,:,::-1])
    writer.release()
    observer=LiveObserver(Rules(decks=4),samples=100)
    capture=cv2.VideoCapture(str(path))
    reports=[];i=0
    try:
        while True:
            ok,bgr=capture.read()
            if not ok:break
            from PIL import Image
            result=observer.process(Image.fromarray(bgr[:,:,::-1]),i,i+1.)
            if i%5==4:reports.append(result)
            i+=1
    finally:capture.release()
    assert i==25
    assert [r['observed_cards'] for r in reports]==[3,4,5,5,8]
    assert [r['advice']['best_action'] if r['advice'] else None for r in reports]==['double','stand',None,None,'double']
