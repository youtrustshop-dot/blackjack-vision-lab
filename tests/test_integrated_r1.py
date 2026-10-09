"""Original-pixel acquisition and UI receipt safety; cloud here is a fixture."""
from dataclasses import replace
from io import BytesIO
from threading import Event, Thread
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from bjlab import integration_api as api
from bjlab.grounded_state import GroundedResult, adapt_legacy
from bjlab.integrated_r1 import IntegratedR1Session, pixel_digest
from tests.test_available_view_deadline_reader import Local

LAYOUT = {'table': (0, 0, 1, 1), 'dealer': (0, 0, 1, .4), 'player:0': (0, .4, 1, .6)}


def png(color):
    image = Image.new('RGB', (200, 150), color)
    output = BytesIO(); image.save(output, 'PNG')
    return image, output.getvalue()


def setup(local=None, cloud=None):
    image, content = png('white'); changed, other = png('gray')
    session = IntegratedR1Session(local or Local(True), cloud=cloud, layout=LAYOUT,
        approved_pixels=[pixel_digest(image), pixel_digest(changed)])
    return session, content, other


def test_valid_local_zero_cloud_and_repeated_view_cannot_create_second_engine():
    class Fail:
        def read(self, *a, **k): raise AssertionError('Usable local must not call cloud.')
    session, content, _ = setup(cloud=Fail())
    session.capture(content, sequence=0)
    state = session.analyze()
    assert state['report']['gate']['solver_allowed'] and not state['stale']
    assert state['report']['gate']['reasons'] == []
    assert state['route'] == 'local' and not state['report']['count_reliable']
    for _ in range(6): assert session.snapshot()['counts']['analysis_count'] == 1
    assert session.receipt()['analysis_count'] == 1


@pytest.mark.parametrize('change', ['different_pixels', 'leave_and_return', 'disconnect'])
def test_capture_continues_during_pending_read_and_stale_reply_cannot_be_advice(change):
    began, release = Event(), Event()
    class Delayed(Local):
        def read(self, frame):
            began.set(); assert release.wait(2)
            return super().read(frame)
    session, content, other = setup(local=Delayed(True))
    session.capture(content, sequence=0)
    worker = Thread(target=session.analyze); worker.start()
    assert began.wait(1)
    if change == 'disconnect': session.disconnect()
    else:
        time.sleep(.020)  # Windows monotonic clock granularity can exceed 15 ms.
        session.capture(other, sequence=1)
        if change == 'leave_and_return':
            time.sleep(.020)
            session.capture(content, sequence=2)
    release.set(); worker.join(2)
    assert not worker.is_alive()
    state = session.snapshot()
    assert state['report']['advice'] is None and state['stale']
    assert not session.receipt()['attempts'][0]['presented']


def test_absent_capture_preserves_cause_and_no_timing_or_advice():
    session, _, _ = setup()
    state = session.analyze()
    attempt = session.receipt()['attempts'][0]
    assert attempt == {'route': 'none', 'presented': False, 'reason': 'no_current_capture'}
    assert state['timing'] is None and state['report']['advice'] is None


def test_native_pixel_allowlist_and_sequence_do_not_accept_annotation_or_foreign_frame():
    session, content, _ = setup()
    session.capture(content, sequence=10)
    with pytest.raises(ValueError, match='Out-of-order'): session.capture(content, sequence=10)
    with pytest.raises(PermissionError): session.capture(png('red')[1], sequence=11)
    with pytest.raises(ValueError): session.capture(content, sequence=11, capture_age_ms=float('nan'))
    assert session.capture_count == 1


def test_original_age_expires_even_when_identical_new_frames_arrive(monkeypatch):
    session, content, _ = setup()
    session.capture(content, sequence=0); session.analyze()
    original = session.attempt['original_evidence']['capture_ns']
    clock = original+3_000_000_001
    session.clock = lambda: clock
    session.capture(content, sequence=1)
    state = session.snapshot()
    assert state['stale'] and state['report']['advice'] is None
    assert 'original_evidence_deadline_expired' in state['revalidation']['reasons']


def test_decoding_delay_consumes_lifetime_instead_of_renewing_capture(monkeypatch):
    from bjlab import integrated_r1 as implementation
    session, content, _ = setup()
    received = time.monotonic_ns()
    tick = [received]
    session.clock = lambda: tick[0]
    prepare = implementation.prepare_frame
    def delayed_prepare(*args, **kwargs):
        tick[0] += 4_000_000_000
        return prepare(*args, **kwargs)
    monkeypatch.setattr(implementation, 'prepare_frame', delayed_prepare)
    ack = session.capture(content, sequence=0)
    stamp, _ = session.evidence.snapshot()
    validity = session.evidence.revalidate(stamp, now_ns=tick[0])
    assert ack['capture_ns'] == received and ack['ingested_ns'] == tick[0]
    assert not validity['valid']
    assert 'original_evidence_deadline_expired' in validity['reasons']


def test_queue_delay_preserves_the_http_boundary_and_original_browser_age():
    session, content, _ = setup()
    received = time.monotonic_ns()
    session.clock = lambda: received+4_000_000_000
    ack = session.capture(content, sequence=0, received_ns=received, capture_age_ms=90)
    stamp, _ = session.evidence.snapshot()
    assert ack['capture_ns'] == received-90_000_000
    assert ack['received_ns'] == received
    assert not session.evidence.revalidate(stamp, now_ns=session.clock())['valid']


def test_dom_receipt_is_bound_to_original_action_and_not_a_freshness_renewal():
    session, content, other = setup()
    session.capture(content, sequence=0); state = session.analyze()
    stamp, action = state['evidence_capture_ns'], state['report']['advice']['best_action']
    with pytest.raises(ValueError):
        session.display(evidence_capture_ns=stamp+1, action=action,
            capture_to_dom_ms=40., boundary='browser-dom-two-raf')
    with pytest.raises(ValueError):
        session.display(evidence_capture_ns=stamp, action='invented',
            capture_to_dom_ms=40., boundary='browser-dom-two-raf')
    time.sleep(.020); session.capture(other, sequence=1)
    row = session.display(evidence_capture_ns=stamp, action=action,
        capture_to_dom_ms=40., boundary='browser-dom-two-raf')
    assert not row['eligible_at_receipt'] and not row['physical_scanout_measured']
    assert session.snapshot()['report']['advice'] is None
    with pytest.raises(ValueError):
        session.display(evidence_capture_ns=stamp, action=action,
            capture_to_dom_ms=40., boundary='browser-dom-two-raf')


@pytest.fixture
def client(monkeypatch, tmp_path):
    image, content = png('white'); path = tmp_path/'owned.png'; path.write_bytes(content)
    monkeypatch.setattr(api, 'sessions', {})
    monkeypatch.setattr(api, 'configuration', None)
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        yield client, path, image, content


def test_default_backend_disabled_and_controlled_configuration_contains_no_oracle(client):
    client, path, image, content = client
    assert client.get('/api/research/r1/configuration').status_code == 503
    api.configure(layout=LAYOUT, sources={
        'owned': {'title': 'Owned scene', 'path': str(path), 'pixel_sha256': pixel_digest(image)}},
        local_factory=lambda: Local(True))
    config = client.get('/api/research/r1/configuration').json()
    assert not config['cloud_configured'] and 'truth' not in str(config)
    response = client.post('/api/research/r1/sessions', json={'cloud': True}, headers={'x-bjlab-local': '1'})
    assert response.status_code == 403
    assert client.post('/api/research/r1/sessions', json={'phase':'player'}, headers={'x-bjlab-local': '1'}).status_code == 422


def test_cross_origin_rejected_and_cloud_unconfigured_no_inference(client):
    client, path, image, content = client
    api.configure(layout=LAYOUT, sources={
        'owned': {'title': 'Owned', 'path': str(path), 'pixel_sha256': pixel_digest(image)}},
        local_factory=lambda: Local(True))
    prefix = '/api/research/r1'
    assert client.post(prefix+'/sessions', json={}, headers={'x-bjlab-local':'1','origin':'https://evil.example'}).status_code == 403
    headers = {'x-bjlab-local':'1'}
    identity = client.post(prefix+'/sessions', json={}, headers=headers).json()['session_id']
    response = client.post(prefix+'/sessions/'+identity+'/capture', content=content, headers=headers,
        params={'sequence':0, 'captured_epoch_ms':time.time()*1000})
    assert response.status_code == 200 and isinstance(response.json()['capture_ns'], str)
    assert client.post(prefix+'/sessions/'+identity+'/analyze', headers=headers).status_code == 200
    assert client.get(prefix+'/sessions/'+identity+'/state').json()['counts']['analysis_count'] == 1
    assert client.delete(prefix+'/sessions/'+identity, headers=headers).status_code == 200
    state = client.get(prefix+'/sessions/'+identity+'/state').json()
    assert state['stale'] and state['report']['advice'] is None
    assert client.post(prefix+'/sessions/'+identity+'/capture', content=content, headers=headers,
        params={'sequence':1,'captured_epoch_ms':time.time()*1000}).status_code == 422


def test_http_capture_timestamps_before_dispatching_to_a_delayed_threadpool(client, monkeypatch):
    client, path, image, content = client
    api.configure(layout=LAYOUT, sources={
        'owned': {'title': 'Owned', 'path': str(path), 'pixel_sha256': pixel_digest(image)}},
        local_factory=lambda: Local(True))
    prefix = '/api/research/r1'
    headers = {'x-bjlab-local': '1'}
    identity = client.post(prefix+'/sessions', json={}, headers=headers).json()['session_id']
    value = api.sessions[identity]
    received = time.monotonic_ns()
    tick = [received]
    value.clock = lambda: tick[0]
    async def delayed_dispatch(fn, *args, **kwargs):
        tick[0] += 4_000_000_000
        return fn(*args, **kwargs)
    monkeypatch.setattr(api, 'run_in_threadpool', delayed_dispatch)
    monkeypatch.setattr(api.time, 'time', lambda: 100.)
    response = client.post(prefix+'/sessions/'+identity+'/capture', content=content,
        headers=headers, params={'sequence':0, 'captured_epoch_ms':99_980.})
    assert response.status_code == 200
    assert int(response.json()['capture_ns']) == received-20_000_000
    stamp, _ = value.evidence.snapshot()
    validity = value.evidence.revalidate(stamp, now_ns=tick[0])
    assert not validity['valid']
    assert 'original_evidence_deadline_expired' in validity['reasons']
