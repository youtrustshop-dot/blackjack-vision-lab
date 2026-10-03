import io
import math

import cv2
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest

from bjlab.api import app, sessions, session_locks, perception_trackers
from bjlab.engine import Rules, initial_counts
from bjlab.live import ContextReader, LiveObserver, estimate_actions
from bjlab.live_api import observers
from bjlab.solver import Solver


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
    sessions.clear(); session_locks.clear(); perception_trackers.clear(); observers.clear()


def source(client):
    state = client.post('/api/sessions', json={'seed': 42}).json()
    sid = state['session_id']
    client.post(f'/api/sessions/{sid}/deal', json={})
    return sid


def pixels(client, sid):
    return client.get(f'/api/sessions/{sid}/frame?live_context=true').content


def feed(client, stream, content, start, number=5):
    values = []
    for i in range(start, start + number):
        response = client.post(f'/api/live/{stream}/frame?sequence={i}&timestamp={i+1}',
                               content=content, headers={'Content-Type': 'image/png'})
        assert response.status_code == 200, response.text
        values.append(response.json())
    return values


def test_pixels_stabilize_once_and_never_count_repeated_video_cards_twice(client):
    sid = source(client)
    stream = client.post('/api/live', json={'samples': 500, 'fresh_shoe': True}).json()['stream_id']
    results = feed(client, stream, pixels(client, sid), 0, 8)
    assert all(r['decision'] is None for r in results[:3])
    final = results[-1]
    assert final['source'] == 'live-video-pixels'
    assert final['player'] == ['2', '8'] and final['dealer'] == ['4']
    assert final['observed_cards'] == 3 and final['running_count'] == 2
    assert final['advice']['basic_action'] == 'double'
    assert sum(e['kind'] == 'CARD_CONFIRMED' for e in client.get(f'/api/live/{stream}/events').json()['events']) == 4
    assert results[3]['decision'] is None  # Base arrives before the scheduled estimate.
    assert results[3]['advice']['basic_action'] == final['advice']['basic_action']
    completed = [r['decision'] for r in results if r['decision'] is not None]
    assert all(r == completed[0] for r in completed)
    assert client.post('/api/live', json={'session_id': sid}).status_code == 422


def test_identical_pixels_reuse_detection_but_still_consume_each_video_observation(client, monkeypatch):
    from bjlab.vision import TemplateCardDetector
    original = TemplateCardDetector.detect
    calls = []
    def detected(self, image):
        calls.append(image.size)
        return original(self, image)
    monkeypatch.setattr(TemplateCardDetector, 'detect', detected)
    sid = source(client)
    stream = client.post('/api/live', json={'samples': 100}).json()['stream_id']
    image = pixels(client, sid)
    results = feed(client, stream, image, 0, 7)
    assert len(calls) == 1
    assert [r['processed_frames'] for r in results] == list(range(1, 8))
    assert results[0]['advice'] is None and results[-1]['advice']
    changed = Image.open(io.BytesIO(image)).convert('RGB')
    changed.putpixel((0, 0), (11, 12, 13))
    buffer = io.BytesIO(); changed.save(buffer, format='PNG')
    last = feed(client, stream, buffer.getvalue(), 7, 1)[0]
    assert len(calls) == 2
    assert last['observed_cards'] == results[-1]['observed_cards']


def test_five_observers_do_not_merge_cards_counts_or_sessions(client):
    reports = []
    for cards in (['10', '6', '10', '9'], ['A', '9', '7', '6'], ['8', '10', '8', '7'],
                  ['5', '6', '6', '9'], ['9', '7', '9', '6']):
        sid = client.post('/api/sessions', json={}).json()['session_id']
        sessions[sid].set_shoe(cards + ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'A'] * 6)
        client.post(f'/api/sessions/{sid}/deal', json={})
        stream = client.post('/api/live', json={'samples': 500, 'fresh_shoe': True}).json()['stream_id']
        image = client.get(f'/api/sessions/{sid}/frame?theme=black&live_context=true').content
        report = feed(client, stream, image, 0, 5)[-1]
        assert report['advice']['best_action'] in report['advice']['legal_actions']
        assert report['observed_cards'] == 3
        assert 'session_id' not in report
        reports.append(report)
    assert [r['advice']['hand']['total'] for r in reports] == [20, 18, 16, 11, 18]
    assert [r['running_count'] for r in reports] == [-1, -1, -1, 3, 0]


def test_new_source_session_with_same_shoe_number_resets_from_visible_label(client):
    stream = client.post('/api/live', json={'samples': 100, 'fresh_shoe': True}).json()['stream_id']
    first_sid = source(client)
    first = feed(client, stream, pixels(client, first_sid), 0)[-1]
    second_sid = client.post('/api/sessions', json={'seed': 139}).json()['session_id']
    client.post(f'/api/sessions/{second_sid}/deal', json={})
    second = feed(client, stream, pixels(client, second_sid), 5)[-1]
    assert first['context']['shoe'] == second['context']['shoe'] == 1
    assert first['context']['session'] != second['context']['session']
    assert second['observed_cards'] == 3
    assert second['running_count'] == sessions[second_sid].snapshot()['shoe']['running_count']


def test_reveal_round_and_shoe_boundaries_are_read_from_pixels(client):
    sid = source(client)
    stream = client.post('/api/live', json={'samples': 100}).json()['stream_id']
    first = feed(client, stream, pixels(client, sid), 0)[-1]
    client.post(f'/api/sessions/{sid}/action', json={'action': 'stand'})
    settled = feed(client, stream, pixels(client, sid), 5)
    assert settled[0]['decision'] is None
    assert settled[-1]['phase'] == 'settled' and settled[-1]['decision'] is None
    assert settled[-1]['observed_cards'] > first['observed_cards']
    client.post(f'/api/sessions/{sid}/deal', json={})
    second = feed(client, stream, pixels(client, sid), 10)[-1]
    assert second['round'] == 2
    assert second['observed_cards'] == sessions[sid].snapshot()['shoe']['seen']
    # Clear the round, then shuffle; observer sees only its newly rendered labels.
    session = sessions[sid]
    while session.phase not in ('ready', 'settled'):
        client.post(f'/api/sessions/{sid}/bot-step', json={})
    client.post(f'/api/sessions/{sid}/action', json={'action': 'shuffle'})
    client.post(f'/api/sessions/{sid}/deal', json={})
    shuffled = feed(client, stream, pixels(client, sid), 15)[-1]
    assert shuffled['context']['shoe'] == 2
    assert shuffled['observed_cards'] == sessions[sid].snapshot()['shoe']['seen']


def test_stale_sequences_and_invalid_configuration_are_rejected(client):
    sid = source(client)
    stream = client.post('/api/live', json={'samples': 100}).json()['stream_id']
    feed(client, stream, pixels(client, sid), 0)
    before = client.get(f'/api/live/{stream}/events').json()
    assert client.post(f'/api/live/{stream}/frame?sequence=0&timestamp=9', content=pixels(client, sid)).status_code == 422
    assert client.post(f'/api/live/{stream}/frame?sequence=5&timestamp=2', content=pixels(client, sid)).status_code == 422
    assert before == client.get(f'/api/live/{stream}/events').json()
    assert client.post('/api/live', json={'rules': {'decks': 3}}).status_code == 422
    assert client.post('/api/live', json={'samples': 0}).status_code == 422
    assert client.post('/api/live', json={'corners': [[0,0],[1,1]]}).status_code == 422
    assert client.post(f'/api/live/{stream}/frame?sequence=5&timestamp=9', content=b'bad video').status_code == 422
    assert client.delete(f'/api/live/{stream}').json()['stopped']
    assert client.post(f'/api/live/{stream}/frame?sequence=6&timestamp=10', content=pixels(client, sid)).status_code == 404


def test_card_occlusion_immediately_removes_previous_advice(client):
    sid = source(client)
    content = pixels(client, sid)
    observer = LiveObserver(Rules(), samples=100)
    image = Image.open(io.BytesIO(content)).convert('RGB')
    for i in range(5):
        result = observer.process(image, i, i+1.)
    assert result['advice'] is not None
    # Hide a real player-card region with felt while leaving context visible.
    hidden = image.copy()
    hidden.paste(image.getpixel((40,290)), (55,305,165,465))
    result = observer.process(hidden, 5, 6.)
    assert result['decision'] is None and not result['gate']['solver_allowed']


def test_known_outcomes_and_ev_units_are_not_win_percentages():
    pool = [0]*9+[60]
    result = estimate_actions(['2','8'], '6', pool, Rules(), ['stand','hit','double','surrender'], samples=200)
    assert result['actions']['double']['win'] == 1
    assert result['actions']['double']['ev'] == 2
    assert result['actions']['surrender']['loss'] == 1
    assert result['actions']['surrender']['ev'] == -.5
    assert result['best_action'] == 'double' and not result['exact']
    for row in result['actions'].values():
        assert math.isclose(row['win']+row['push']+row['loss'], 1.)


def test_finite_stand_estimate_agrees_with_independent_exact_enumeration():
    pool = list(initial_counts(6))
    pool[9] -= 2; pool[5] -= 1
    exact = Solver(Rules()).analyze(['10','10'], '6', pool, can_double=False,
                                   can_split=False, can_surrender=False, timeout_ms=1500)
    estimate = estimate_actions(['10','10'], '6', pool, Rules(), ['stand'], samples=8000, seed=91)
    row = estimate['actions']['stand']
    assert abs(row['ev']-exact['actions']['stand']) < .035
    assert row['win_ci95'][0] <= row['win'] <= row['win_ci95'][1]


def test_negative_peek_marginalizes_the_hidden_card():
    pool = [10]+[0]*8+[50]
    conditioned = estimate_actions(['10','10'], 'A', pool, Rules(), ['stand'], samples=200, peeked=True)
    assert conditioned['actions']['stand']['win'] == 1
    unconditioned = estimate_actions(['10','10'], 'A', pool, Rules(), ['stand'], samples=2000, peeked=False)
    assert .79 < unconditioned['actions']['stand']['loss'] < .87


@pytest.mark.parametrize('round_id,hand,shoe',[(1,1,1),(12,2,3),(108,4,12)])
def test_visible_context_reads_multiple_digits(client,round_id,hand,shoe):
    sid = source(client)
    from PIL import ImageDraw
    from bjlab.datasets import card_font
    image=Image.open(io.BytesIO(pixels(client,sid))).convert('RGB')
    for x,value,width in ((120,shoe,70),(305,round_id,70),(470,hand,45)):
        image.paste(image.getpixel((40,250)),(x-6,255,x+width,285))
        ImageDraw.Draw(image).text((x,260),str(value),font=card_font(16),fill=(212,220,213),anchor='lt')
    context = ContextReader().read(image)
    assert {key: context[key] for key in ('shoe', 'round', 'hand', 'phase')} == {
        'shoe': shoe, 'round': round_id, 'hand': hand, 'phase': 'player'}
    assert context['session'] > 0


def test_decoded_lossless_video_reconstructs_real_action_sequence(client,tmp_path):
    sid = source(client)
    frames=[]
    expected=[]
    for _ in range(7):
        image=np.asarray(Image.open(io.BytesIO(pixels(client,sid))).convert('RGB'))
        frames.extend([image]*5)
        expected.append(sessions[sid].snapshot()['shoe']['seen'])
        client.post(f'/api/sessions/{sid}/bot-step',json={})
    path=tmp_path/'lab-video.avi'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'FFV1'),12,(960,600))
    assert writer.isOpened(), 'Lossless video encoder required for the video-path regression'
    for image in frames:writer.write(cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
    writer.release()
    decoder=cv2.VideoCapture(str(path));observer=LiveObserver(Rules(),samples=100)
    sequence=0
    while True:
        ok,bgr=decoder.read()
        if not ok:break
        result=observer.process(Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)),sequence,(sequence+1)/12)
        if sequence%5==4:assert result['observed_cards']==expected[sequence//5]
        sequence+=1
    decoder.release()
    assert sequence==35 and observer.frame_count==35


def test_browser_handoff_rejects_other_origins_without_opening(client,monkeypatch):
    opened=[]
    monkeypatch.setattr('webbrowser.open',lambda url:opened.append(url) or True)
    assert client.post('/api/live/browser',json={}).status_code==403  # Test host is not localhost.
    assert not opened


def test_full_screen_table_calibration_preserves_cards_and_decision(client):
    sid=source(client)
    table=Image.open(io.BytesIO(pixels(client,sid))).convert('RGB')
    screen=Image.new('RGB',(1600,1000),(40,40,40));screen.paste(table,(300,100))
    corners=[[300/1599,100/999],[1259/1599,100/999],[1259/1599,699/999],[300/1599,699/999]]
    encoded=io.BytesIO();screen.save(encoded,format='PNG')
    stream=client.post('/api/live',json={'samples':100,'corners':corners}).json()['stream_id']
    result=feed(client,stream,encoded.getvalue(),0)[-1]
    assert result['player']==['2','8'] and result['dealer']==['4']
    assert result['advice']['best_action']=='double' and result['observed_cards']==3
