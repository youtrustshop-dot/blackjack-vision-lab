"""Acceptance cases from the f4f7579 audit, independent of new vision models."""
import json
from pathlib import Path
import re
import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from bjlab import __version__
from bjlab.engine import Rules
from bjlab.live import LiveObserver
from side_fixture import side_table
from bjlab.api import app
from bjlab.live import AnalysisStopped, estimate_actions
from bjlab.live_api import observers
from bjlab.live_work import LiveAnalysisPool, LiveFramePool


def stable(observer, image=None, start=0, timestamp=1.):
    image = image if image is not None else side_table()
    for index in range(6):
        result = observer.process(image, start + index, timestamp + index * .35)
    return result


def test_joining_mid_shoe_keeps_basic_advice_but_not_physical_inventory_or_tc():
    result = stable(LiveObserver(Rules(decks=4, surrender='none'), samples=100))
    assert result['advice']['best_action'] == 'hit'
    assert result['true_count'] is None
    assert result['physical_remaining'] is None
    assert result['observed_running_count'] == 1
    assert result['count_history'] == 'partial'
    assert not result['advice']['count_comparison_reliable']


def test_valid_basic_response_does_not_call_monte_carlo(monkeypatch):
    calls = []
    def slow_estimate(*args, **kwargs):
        calls.append(True)
        return {'best_action': 'hit', 'actions': {}, 'exact': False}
    monkeypatch.setattr('bjlab.live.estimate_actions', slow_estimate)
    result = stable(LiveObserver(Rules(decks=4, surrender='none'), samples=100, fresh_shoe=True))
    assert result['advice']['best_action'] == 'hit'
    assert not calls, 'The video/basic-policy response must not run Monte Carlo.'


def test_confirmed_shoe_gap_stays_compromised_after_readable_video_returns():
    observer = LiveObserver(Rules(decks=4, surrender='none'), samples=100, fresh_shoe=True)
    first = stable(observer)
    assert first['true_count'] is not None
    later = stable(observer, start=6, timestamp=10.)
    assert later['advice']['best_action'] == 'hit'
    assert later['true_count'] is None
    assert later['physical_remaining'] is None
    assert later['count_history'] == 'compromised'
    # Only an explicit new-shoe declaration restores this provenance.
    reset = stable(LiveObserver(observer.rules, samples=100, fresh_shoe=True))
    assert reset['count_history'] == 'complete'
    assert reset['true_count'] is not None


def test_current_requirement_summary_has_one_version_and_one_frontend_count():
    root = Path(__file__).resolve().parents[1]
    summary = json.loads((root / 'docs/REQUIREMENTS.json').read_text(encoding='utf-8'))['verification']
    assert summary['version'] == __version__
    assert re.search(r'\d+', summary['frontend_tests']).group() == re.search(r'\d+', summary['frontend_build']).group()


def encoded(image):
    buffer = io.BytesIO(); image.save(buffer, format='PNG'); return buffer.getvalue()


def test_slow_monte_carlo_response_and_late_result_are_independent_from_video(monkeypatch):
    pool = LiveAnalysisPool(workers=1)
    monkeypatch.setattr('bjlab.live_api.analysis_pool', pool)
    entered, finish = threading.Event(), threading.Event()
    def delayed(*args, **kwargs):
        entered.set(); assert finish.wait(4)
        # Deliberately ignore cancellation to exercise the final publication gate.
        return {'best_action': 'stand', 'ranking_resolved': True, 'actions': {}}
    monkeypatch.setattr('bjlab.live.estimate_actions', delayed)
    identity = None
    try:
        with TestClient(app) as client:
            identity = client.post('/api/live', json={'rules': {'decks':4, 'surrender':'none'}, 'samples':100, 'fresh_shoe':True}).json()['stream_id']
            for index in range(6):
                response = client.post(f'/api/live/{identity}/frame?sequence={index}&timestamp={1+index*.35}', content=encoded(side_table()))
                assert response.status_code == 200, response.text
            base = response.json()
            assert entered.wait(1) and not finish.is_set()
            assert base['advice']['best_action'] == 'hit' and base['decision'] is None
            pending = client.get(f'/api/live/{identity}/analysis', params={'state_id':base['state_id']}).json()
            assert pending['analysis']['status'] == 'pending' and pending['advice']['best_action'] == 'hit'
            # Same hand, different observed composition after a transition is a
            # different generation even if a previous visible hand reappears.
            for index in range(6,12):
                newer = client.post(f'/api/live/{identity}/frame?sequence={index}&timestamp={1+index*.35}', content=encoded(side_table(('9','8'),('7',)))).json()
            assert newer['advice']['best_action'] == 'stand'
            assert client.get(f'/api/live/{identity}/analysis', params={'state_id':base['state_id']}).status_code == 409
            finish.set(); pool.shutdown()
            current = client.get(f'/api/live/{identity}/analysis', params={'state_id':newer['state_id']}).json()
            assert current['decision'] is None
            assert current['advice']['basic_action'] == 'stand'
            client.delete('/api/live/'+identity)
    finally:
        finish.set(); pool.shutdown()
        if identity: observers.pop(identity, None)


def test_estimate_workers_do_not_queue_and_release_only_after_work_ends(monkeypatch):
    pool = LiveAnalysisPool(workers=1)
    finish, entered = threading.Event(), threading.Event()
    def delayed(*args, **kwargs):
        entered.set(); assert finish.wait(3)
        return {'best_action':'hit', 'ranking_resolved':False, 'actions':{}}
    monkeypatch.setattr('bjlab.live.estimate_actions', delayed)
    sources = [LiveObserver(Rules(decks=4,surrender='none'), samples=100, fresh_shoe=True) for _ in range(3)]
    for observer in sources: stable(observer)
    try:
        assert pool.submit(sources[0]) and entered.wait(1)
        assert not pool.submit(sources[0])  # No duplicate same-state work.
        assert not pool.submit(sources[1]) and not pool.submit(sources[2])
        assert pool.metrics()['active']==pool.metrics()['peak']==1
        assert pool.metrics()['queue_capacity']==0
        sources[0].stop()
        assert pool.metrics()['active']==1  # Cancellation is not a freed worker.
    finally:
        finish.set(); pool.shutdown()
    assert pool.metrics()['active']==0
    assert sources[0].decision is None


def test_live_monte_carlo_has_a_cooperative_deadline_and_cancellation(monkeypatch):
    from bjlab import live
    cancel = threading.Event(); original = live.check_analysis_budget; checks = []
    def checked(deadline, cancellation):
        checks.append(True)
        if len(checks)==10: cancel.set()
        original(deadline, cancellation)
    monkeypatch.setattr(live, 'check_analysis_budget', checked)
    with pytest.raises(AnalysisStopped, match='cancelled'):
        estimate_actions(['10','10'],'6',[24]*9+[96],Rules(),['stand'],samples=8000,cancel_event=cancel)
    assert len(checks)==10
    monkeypatch.setattr(live, 'check_analysis_budget', original)
    with pytest.raises(AnalysisStopped, match='timeout'):
        estimate_actions(['10','10'],'6',[24]*9+[96],Rules(),['stand'],samples=8000,timeout_ms=0)


def test_estimate_timeout_preserves_base_policy_and_does_not_retry_forever(monkeypatch):
    pool = LiveAnalysisPool(workers=1, timeout_ms=0)
    observer = LiveObserver(Rules(decks=4,surrender='none'),samples=100,fresh_shoe=True)
    result = stable(observer)
    assert pool.submit(observer); pool.shutdown()
    assert observer.analysis_result(result['state_id'])['analysis']['status']=='timeout'
    assert observer.analysis_result(result['state_id'])['advice']['best_action']=='hit'
    assert observer.decision is None
    assert not pool.submit(observer)


def test_frame_work_is_bounded_and_same_stream_cannot_queue(monkeypatch):
    pool = LiveFramePool(workers=1)
    monkeypatch.setattr('bjlab.live_api.frame_pool', pool)
    entered, finish = threading.Event(), threading.Event()
    identities=[]
    with TestClient(app) as client:
        try:
            identities=[client.post('/api/live',json={}).json()['stream_id'] for _ in range(2)]
            observer=observers[identities[0]]; original=observer.process
            def delayed(*args):
                entered.set(); assert finish.wait(3); return original(*args)
            monkeypatch.setattr(observer,'process',delayed)
            def send(identity, seq=0):
                return client.post(f'/api/live/{identity}/frame?sequence={seq}&timestamp={seq+1}',content=encoded(side_table()))
            with ThreadPoolExecutor(max_workers=1) as caller:
                first=caller.submit(send,identities[0]); assert entered.wait(1)
                assert send(identities[0],1).status_code==429
                assert send(identities[1]).status_code==429
                finish.set(); assert first.result(timeout=3).status_code==200
            assert send(identities[1]).status_code==200
        finally:
            finish.set()
            for identity in identities: client.delete('/api/live/'+identity)
            pool.executor.shutdown(wait=True)


def test_partial_history_never_presents_a_hilo_index_as_reliable():
    from bjlab.advice import recommend
    advice=recommend(['10','6'],'10',Rules(),true_count=8,peeked=True,count_complete=False)
    assert advice['count_action'] is None and advice['best_action']=='surrender'


def test_evidence_guard_detects_the_original_contradictory_summary(tmp_path):
    from bjlab.evidence import evidence_errors
    root=Path(__file__).resolve().parents[1]
    paths=('pyproject.toml','bjlab/__init__.py','ui/package.json','ui/package-lock.json',
           'ui/src-tauri/tauri.conf.json','ui/src-tauri/Cargo.toml','docs/REQUIREMENTS.json')
    for name in paths:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((root/name).read_bytes())
    assert evidence_errors(tmp_path)==[]
    path=tmp_path/'docs/REQUIREMENTS.json';document=json.loads(path.read_text(encoding='utf-8'))
    document['verification'].update(version='1.0.0',frontend_tests='23 passed',frontend_build='34 tests; build passed')
    path.write_text(json.dumps(document),encoding='utf-8')
    errors=evidence_errors(tmp_path)
    assert any('version' in error for error in errors) and any('counts' in error for error in errors)


def test_source_ids_are_distinct_even_for_identical_hands():
    first=stable(LiveObserver(Rules(decks=4,surrender='none'),samples=100))
    second=stable(LiveObserver(Rules(decks=4,surrender='none'),samples=100))
    assert first['player']==second['player'] and first['state_id']!=second['state_id']
