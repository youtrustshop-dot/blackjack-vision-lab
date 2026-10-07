"""Standalone diagnostic deadlines and safe stops; no provider sockets/DNS."""
from dataclasses import replace
import json
import os
import socket
import subprocess
import time

import pytest

from bjlab.offline_response_collector import OfflineResponseCollector
from bjlab.private_observation_store import PrivateObservationStore
from validation.tools.rejected_output_offline import base_output, contract_cases, fixture_reader


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No provider sockets or DNS in offline collector tests.')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)


@pytest.fixture
def protected_store(tmp_path):
    if os.name != 'nt':
        pytest.skip('Actual Windows DPAPI required; no plaintext substitute.')
    subprocess.run(['git', 'init', '--quiet', str(tmp_path)], check=True, capture_output=True)
    (tmp_path/'.gitignore').write_text('artifacts/\n')
    return PrivateObservationStore(tmp_path)


def setup_timed(monkeypatch, text, elapsed_ms, *, absent=False, provider='openai'):
    frame, reader, scope = fixture_reader(text, provider=provider)
    now = time.monotonic_ns(); start = now
    monkeypatch.setattr(time, 'monotonic_ns', lambda: now)
    transport = reader.transport; original = transport.post
    transport.closed = False
    def close():
        transport.closed = True
    transport.close = close
    def post(payload, *, deadline_ns, reservation_id):
        nonlocal now
        if absent:
            transport.submissions += 1; transport.deadline_ns = deadline_ns
            now = deadline_ns; transport.timings = {'worker_completed': False, 'pool_closed': True}
            raise TimeoutError('No complete body before diagnostic cap.')
        result = original(payload, deadline_ns=deadline_ns, reservation_id=reservation_id)
        now += int(elapsed_ms*1e6)
        transport.timings = {'http_status': 200, 'headers_received_ms': elapsed_ms-5,
            'body_complete_ms': elapsed_ms, 'submission_claim_ms': 0, 'worker_completed': True}
        return result
    transport.post = post
    return frame, reader, scope, start


@pytest.mark.parametrize('elapsed_ms', [2200, 4500, 9800])
def test_fast_and_late_complete_content_is_retained_but_never_advisor(protected_store, monkeypatch, elapsed_ms):
    text = json.dumps(base_output())
    frame, reader, scope, began = setup_timed(monkeypatch, text, elapsed_ms)
    result = OfflineResponseCollector(reader, protected_store, scope).collect(frame)
    assert result['status'] == 'completed' and result['total_through_validation_ms'] == elapsed_ms
    assert result['within_unchanged_live_boundary'] is (elapsed_ms < 3000)
    assert result['content_diagnosis']['category'] == 'valid_usable_content'
    assert result['eligible_for_live'] is False and result['advisor_connected'] is False and result['advice'] is None
    assert protected_store.read(result['retention']['record_id'])['output_text'] == text
    assert reader.transport.deadline_ns == began+10_000_000_000
    assert reader.config.timeout_seconds == 3 and reader.transport.closed
    assert reader.transport.submissions == reader.budget.reserved == reader.budget.settled == 1


def test_no_response_is_censored_at_ten_seconds_and_keeps_charge_reserved(protected_store, monkeypatch):
    frame, reader, scope, began = setup_timed(monkeypatch, '{}', 10000, absent=True)
    result = OfflineResponseCollector(reader, protected_store, scope).collect(frame)
    assert result['status'] == 'timeout' and result['no_complete_response_within_10s'] is True
    assert result['total_through_validation_ms'] == 10000
    assert result['reported_usage_upper_usd'] is None and not result['usage_settled']
    assert not result['retention']['retained'] and result['advice'] is None
    assert reader.transport.submissions == reader.budget.reserved == 1 and reader.budget.settled == 0
    assert reader.transport.closed


def test_rejected_gemini_label_is_retained_without_relaxing_the_invariant(protected_store, monkeypatch):
    text = next(t for n, t, _ in contract_cases() if n == 'actor_without_total')
    frame, reader, scope, _ = setup_timed(monkeypatch, text, 2400, provider='gemini')
    result = OfflineResponseCollector(reader, protected_store, scope).collect(frame)
    assert result['content_diagnosis']['category'] == 'pre_normalization_invariant_rejection'
    assert result['content_diagnosis']['issues'][0]['rule'] == 'explicit_total_label_required'
    record = protected_store.read(result['retention']['record_id'])
    assert record['output_text'] == text and record['diagnosis']['private']['normalized_numbers'] == []
    assert result['usage_settled'] and not result['stop_before_next_request']
    assert 'fixture-envelope' not in json.dumps(record) and 'DEALER 6' not in json.dumps(result)


def test_retention_failure_requires_stop_before_another_provider(protected_store, monkeypatch):
    frame, reader, scope, _ = setup_timed(monkeypatch, json.dumps(base_output()), 4500)
    def failed(record):
        raise OSError('Private failure details must not reach public logs.')
    monkeypatch.setattr(protected_store, 'write', failed)
    result = OfflineResponseCollector(reader, protected_store, scope).collect(frame)
    assert result['retention'] == {'retained': False, 'reason': 'protected_storage_failed', 'error_type': 'OSError'}
    assert result['stop_before_next_request'] and reader.transport.submissions == 1 and reader.transport.closed
    assert result['output_sha256'] and result['output_bytes'] > 0
    assert result['eligible_for_live'] is False


def test_one_shot_rejects_a_second_submission_even_after_success(protected_store, monkeypatch):
    frame, reader, scope, _ = setup_timed(monkeypatch, json.dumps(base_output()), 2200)
    collector = OfflineResponseCollector(reader, protected_store, scope)
    collector.collect(frame)
    with pytest.raises(PermissionError):
        collector.collect(frame)
    assert reader.transport.submissions == reader.budget.reserved == 1


def test_changed_scope_cannot_reserve_or_submit(protected_store, monkeypatch):
    frame, reader, scope, _ = setup_timed(monkeypatch, '{}', 2200)
    with pytest.raises(PermissionError):
        OfflineResponseCollector(reader, protected_store, replace(scope, payload_sha256='0'*64)).collect(frame)
    assert reader.transport.submissions == reader.budget.reserved == 0


def test_usage_rejection_retains_content_and_stops_without_releasing_charge(protected_store, monkeypatch):
    text = json.dumps(base_output()); frame, reader, scope, _ = setup_timed(monkeypatch, text, 2200)
    original = reader.transport.post
    def wrong_usage(*args, **kwargs):
        result = original(*args, **kwargs); result['usage']['output_tokens'] = 'invalid'
        return result
    reader.transport.post = wrong_usage
    result = OfflineResponseCollector(reader, protected_store, scope).collect(frame)
    assert result['status'] == 'error' and result['stop_before_next_request'] and not result['usage_settled']
    assert result['reported_usage_upper_usd'] is None and reader.budget.settled == 0
    assert protected_store.read(result['retention']['record_id'])['output_text'] == text
    assert result['content_diagnosis']['category'] == 'valid_usable_content' and result['advice'] is None


def test_separate_path_never_calls_the_three_second_reader(protected_store, monkeypatch):
    frame, reader, scope, _ = setup_timed(monkeypatch, json.dumps(base_output()), 4500)
    def forbidden(*args, **kwargs):
        raise AssertionError('Live read path cannot be used by the diagnostic collector.')
    monkeypatch.setattr(reader, 'read', forbidden)
    before = reader.payload(frame)
    result = OfflineResponseCollector(reader, protected_store, scope).collect(frame)
    assert result['status'] == 'completed' and reader.transport.last_payload == before


@pytest.mark.parametrize('tampered', [False, True])
def test_prerequisites_bind_reviewed_native_pixels_before_any_network_or_reservation(tmp_path, monkeypatch, tampered):
    from dataclasses import asdict
    from hashlib import sha256
    import validation.tools.two_provider_diagnostics as tool
    from bjlab.paired_persistent_http import canonical_digest
    frame, _, _ = fixture_reader('{}')
    readers = tool.candidates([sha256(p).hexdigest() for _, p in frame.images()])
    prior = tmp_path/'prior'; prior.mkdir(); (prior/'freeze.json').write_text('{}')
    entries = {name: {'sha256': 'a'*64, 'canonical_sha256': canonical_digest(readers[name].payload(frame))}
        for name in tool.ORDER}
    record = {'payloads': entries}
    monkeypatch.setattr(tool, 'checked', lambda: ({'configs': {n: asdict(r.config) for n,r in readers.items()}},
        {tool.CASE: (record, frame)}, {}))
    monkeypatch.setattr(tool, 'ROOT', tmp_path); monkeypatch.setattr(tool, 'PRIOR', prior)
    folder = tmp_path/'validation/results/rejected-output-diagnostics'; folder.mkdir(parents=True)
    (folder/'proposal.json').write_text(json.dumps({'prior_freeze_sha256': tool.file_hash(prior/'freeze.json'),
        'request_payload_sha256': {n: e['sha256'] for n,e in entries.items()},
        'request_canonical_sha256': {n: e['canonical_sha256'] for n,e in entries.items()}}))
    policy = tmp_path/'matrix.json'; policy.write_text(json.dumps({'api_access_policy': {
        'inference_authorized': False, 'max_requests': 0, 'max_usd': '0'}}))
    monkeypatch.setattr(tool, 'MATRIX', policy)
    monkeypatch.setattr(tool, 'snapshot', lambda: {'sha256': tool.BEFORE_LEDGER_SHA, 'receipt': {
        'requests_attempted': 104, 'max_requests': 105, 'stopped': False, 'accounted_upper_usd': '6.153279850'}})
    if tampered:
        entries[tool.ORDER[0]]['canonical_sha256'] = '0'*64
        with pytest.raises(PermissionError):
            tool.prerequisites()
    else:
        assert tool.prerequisites()[1] is frame
