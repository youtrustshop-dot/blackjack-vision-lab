"""Safe stage attribution without constructing a paid lot or making DNS/HTTP calls."""
from threading import Lock
from types import SimpleNamespace

from PIL import Image
import pytest

from bjlab.dns_lease import DnsLeaseUnavailable
from bjlab.state_reader import prepare_frame
from validation.tools import integrated_r1_session as runner


@pytest.mark.parametrize('stage', ['dns_lease', 'payload_binding', 'owned_pixel_and_payload_verification'])
def test_failed_local_guard_records_exact_stage_then_closes_without_a_post(monkeypatch, stage):
    frame = prepare_frame(Image.new('RGB', (200, 150), 'white'), {
        'table': (0, 0, 1, 1), 'dealer': (0, 0, 1, .4), 'player:0': (0, .4, 1, .6)})
    lot = runner.OwnedCloudLot.__new__(runner.OwnedCloudLot)
    lot.lock = Lock(); lot.closed = False; lot.pending = False; lot.used = set()
    lot.frames = {'stable-overlap': ({'payload': {'canonical_sha256': 'frozen-test'}}, frame)}
    lot.rows = []; lot.transports = []; lot.budget = object(); lot.key = 'test-only-not-a-credential'
    monkeypatch.setattr(runner, 'ORDER', ('stable-overlap',))
    saved = []
    monkeypatch.setattr(runner, 'save', lambda path, value: saved.append(value))
    def stop():
        lot.closed = True
    lot.close = stop
    def snapshot():
        if stage == 'dns_lease':
            raise DnsLeaseUnavailable('insufficient_remaining_lease')
        return {}
    lot.dns = SimpleNamespace(snapshot=snapshot)

    class Transport:
        _request_count = 0
        def __init__(self, **kwargs): pass
        def bind(self, *args):
            if stage == 'payload_binding': raise PermissionError('test private details')
        def close(self): self.closed = True
        def __call__(self, *args, **kwargs): raise AssertionError('No HTTP permitted.')
    monkeypatch.setattr(runner, 'PersistentScopedTransport', Transport)
    monkeypatch.setattr(runner, '_OutputTap', lambda transport: SimpleNamespace(text=None))
    monkeypatch.setattr(runner, 'VisiblePhaseDeadlineReader',
        lambda config, *args, **kwargs: SimpleNamespace(config=config))
    class Scope:
        def __init__(self, *args): pass
        def verify(self, *args): raise PermissionError('test private pixel details')
    monkeypatch.setattr(runner, 'OwnedOutputScope', Scope)

    result = lot.read(frame, capture_ns=123)
    assert result.status == 'blocked' and lot.closed and not lot.pending
    assert saved and lot.rows[0]['guard_stage'] == stage
    assert lot.rows[0]['http_post_attempts'] == 0 and not lot.rows[0]['raw_error_saved']
    assert 'private details' not in str(result.diagnostics) and 'test-only' not in str(saved)
    if stage == 'dns_lease':
        assert result.diagnostics['guard_code'] == 'insufficient_remaining_lease'
    assert all(t.closed for t in lot.transports)
