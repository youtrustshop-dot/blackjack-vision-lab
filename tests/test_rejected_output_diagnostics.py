"""Failure-boundary and private-retention regression tests; no API evidence."""
from dataclasses import replace
import json
import os
import socket
import subprocess
import time

import pytest
from pydantic import ValidationError

from bjlab.live_state import LiveObservation
from bjlab.private_observation_store import PrivateObservationStore, WindowsUserProtection, RETENTION_SECONDS
from bjlab.rejected_output_diagnostics import RetainingStillDiagnostic, delivery_category, inspect_output
from validation.tools.rejected_output_offline import base_output, contract_cases, fixture_reader, run_offline


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No provider sockets or DNS in offline diagnostic tests.')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)


@pytest.mark.parametrize('name,text,expected', contract_cases(), ids=[c[0] for c in contract_cases()])
def test_frozen_contract_failure_boundaries(name, text, expected):
    public, private = inspect_output(text)
    assert public['category'] == expected and public['eligible_for_live'] is False
    if expected == 'pre_normalization_invariant_rejection':
        with pytest.raises(ValidationError):
            LiveObservation.model_validate_json(text)
        assert not private['normalized_numbers']
        assert [s['stage'] for s in public['stages']] == ['json_syntax', 'strict_contract_fields_and_invariants']
    assert 'private-value' not in json.dumps(public)


def test_public_rejection_names_exact_rule_and_position_without_leaking_label():
    value = base_output(); value['n'][0]['l'] = 'private-output-label'
    public, private = inspect_output(json.dumps(value))
    assert public['issues'] == [{'location': ['n', 0], 'type': 'value_error', 'rule': 'explicit_total_label_required'}]
    assert 'private-output-label' not in json.dumps(public)
    assert private['normalized_numbers'] == []


def test_positive_normalization_keeps_original_label_and_arithmetic_still_blocks():
    value = base_output(); value['n'][0]['l'] = ' dealer  total : 6 '
    _, private = inspect_output(json.dumps(value))
    assert private['normalized_numbers'][0]['observed_text'] == value['n'][0]['l']
    value['n'][0].update(v=5, l='DEALER TOTAL 5')
    public, _ = inspect_output(json.dumps(value))
    assert public['category'] == 'r1_integrity_rejection'
    assert 'dealer_total_card_mismatch' in public['r1_issue_codes']


@pytest.mark.parametrize('kwargs,expected', [
    ({'status': 'completed', 'elapsed_ms': 4500, 'content_category': 'valid_usable_content'}, 'timeout'),
    ({'status': 'timeout', 'elapsed_ms': 3016}, 'timeout'),
    ({'status': 'completed', 'elapsed_ms': 3000, 'content_category': 'valid_usable_content'}, 'timeout'),
    ({'status': 'completed', 'elapsed_ms': 2219, 'evidence_current': False}, 'stale_response'),
    ({'status': 'error', 'elapsed_ms': 2100, 'http_status': 400}, 'provider_http_rejection'),
    ({'status': 'error', 'elapsed_ms': 2100, 'unreconciled_usage': True, 'content_category': 'valid_usable_content'}, 'usage_audit_rejection'),
    ({'status': 'error', 'elapsed_ms': 2100, 'content_category': 'valid_usable_content'}, 'reader_error'),
])
def test_timeout_stale_http_and_accounting_do_not_become_content_failures(kwargs, expected):
    assert delivery_category(**kwargs) == expected


@pytest.fixture
def private_store(tmp_path):
    if os.name != 'nt':
        pytest.skip('Actual Windows DPAPI/DACL requires Windows; no plaintext test substitute.')
    subprocess.run(['git', 'init', '--quiet', str(tmp_path)], check=True, capture_output=True)
    (tmp_path/'.gitignore').write_text('artifacts/\n')
    return PrivateObservationStore(tmp_path)


def test_actual_windows_protection_roundtrip_and_corruption_rejected():
    if os.name != 'nt':
        with pytest.raises(PermissionError):
            WindowsUserProtection()
        return
    protection = WindowsUserProtection(); text = b'fabricated private diagnostic observation'
    encrypted = protection.protect(text)
    assert text not in encrypted and protection.unprotect(encrypted) == text
    corrupt = bytearray(encrypted); corrupt[-1] ^= 1
    with pytest.raises(PermissionError):
        protection.unprotect(bytes(corrupt))


def test_untracked_storage_is_mandatory(tmp_path):
    if os.name != 'nt':
        pytest.skip('Protected storage is Windows-only.')
    subprocess.run(['git', 'init', '--quiet', str(tmp_path)], check=True, capture_output=True)
    with pytest.raises(PermissionError):
        PrivateObservationStore(tmp_path)
    assert not (tmp_path/'artifacts').exists()


@pytest.mark.parametrize('provider', ['openai', 'gemini'])
def test_output_is_saved_before_strict_failure_and_envelope_never_saved(private_store, provider):
    text = next(t for n, t, _ in contract_cases() if n == 'actor_without_total')
    frame, reader, scope = fixture_reader(text, provider=provider); payload_before = reader.payload(frame)
    wrapped = RetainingStillDiagnostic(reader, private_store, scope)
    capture = time.monotonic_ns(); receipt = wrapped.run(frame, capture_ns=capture)
    assert receipt['reader_status'] == 'error' and receipt['category'] == 'pre_normalization_invariant_rejection'
    assert receipt['eligible_for_live'] is False and receipt['advice'] is None
    assert reader.transport.submissions == reader.budget.settled == 1
    assert reader.transport.last_payload == payload_before
    assert reader.transport.deadline_ns == capture+3_000_000_000
    record = private_store.read(receipt['retention']['record_id'])
    assert record['output_text'] == text
    assert record['provenance']['contract'] == 'grounded-r1-live-v3'
    assert 'fixture-envelope' not in json.dumps(record)
    assert text not in json.dumps(receipt)
    ciphertext = private_store._path(receipt['retention']['record_id']).read_bytes()
    assert b'DEALER 6' not in ciphertext and b'output_text' not in ciphertext
    with pytest.raises(PermissionError):
        wrapped.run(frame, capture_ns=capture)
    assert reader.transport.submissions == 1


def test_slow_diagnostic_storage_cannot_extend_live_reader_clock(private_store, monkeypatch):
    frame, reader, scope = fixture_reader(json.dumps(base_output()))
    original_write = private_store.write; clock = time.monotonic_ns()
    monkeypatch.setattr(time, 'monotonic_ns', lambda: clock)
    def slow(record):
        nonlocal clock
        clock += 4_000_000_000
        return original_write(record)
    monkeypatch.setattr(private_store, 'write', slow)
    receipt = RetainingStillDiagnostic(reader, private_store, scope).run(frame, capture_ns=clock)
    assert receipt['reader_elapsed_ms'] == 0 and receipt['post_read_diagnostic_ms'] == 4000
    assert receipt['eligible_for_live'] is False and receipt['advice'] is None


def test_changed_review_scope_never_submits_or_reserves(private_store):
    frame, reader, scope = fixture_reader(json.dumps(base_output()))
    for bad in (replace(scope, owned_synthetic=False), replace(scope, payload_sha256='0'*64),
                replace(scope, image_sha256=('0'*64,))):
        with pytest.raises(PermissionError):
            RetainingStillDiagnostic(reader, private_store, bad).run(frame, capture_ns=time.monotonic_ns())
    assert reader.transport.submissions == reader.budget.reserved == 0


def test_storage_failure_never_retries_or_returns_observation(private_store, monkeypatch):
    frame, reader, scope = fixture_reader(json.dumps(base_output()))
    def failed(record):
        raise OSError('private disk failure must not be copied into public output')
    monkeypatch.setattr(private_store, 'write', failed)
    receipt = RetainingStillDiagnostic(reader, private_store, scope).run(frame, capture_ns=time.monotonic_ns())
    assert receipt['retention'] == {'retained': False, 'reason': 'protected_storage_failed', 'error_type': 'OSError'}
    assert reader.transport.submissions == 1 and 'observation' not in receipt


def test_expired_capture_has_no_output_no_submission_and_no_storage(private_store):
    frame, reader, scope = fixture_reader(json.dumps(base_output()))
    receipt = RetainingStillDiagnostic(reader, private_store, scope).run(frame, capture_ns=time.monotonic_ns()-4_000_000_000)
    assert receipt['category'] == 'timeout' and receipt['retention']['retained'] is False
    assert reader.transport.submissions == reader.budget.reserved == 0
    assert list(private_store.directory.glob('*.r1diag')) == []


def test_retention_expiry_is_explicit_bounded_and_cannot_escape_directory(private_store, monkeypatch):
    record = {'output_text': '{}', 'provenance': {}, 'diagnosis': {}}
    now = time.time(); monkeypatch.setattr(time, 'time', lambda: now)
    saved = private_store.write(record)
    with pytest.raises(PermissionError):
        private_store.read('../outside')
    assert private_store.read(saved['record_id']) == record
    monkeypatch.setattr(time, 'time', lambda: now+RETENTION_SECONDS+1)
    with pytest.raises(PermissionError):
        private_store.read(saved['record_id'])
    assert private_store.purge_expired() == {'expired_records_removed': 1, 'recursive': False}


def test_credential_bearing_text_and_full_envelopes_are_not_retained(private_store):
    credential = 'sk-'+'fictional_secret_for_test_only'
    with pytest.raises(PermissionError):
        private_store.write({'output_text': credential, 'provenance': {}, 'diagnosis': {}})
    with pytest.raises(PermissionError):
        private_store.write({'output_text': '{}', 'headers': {'Authorization': 'do-not-save'}})
    assert list(private_store.directory.glob('*.r1diag')) == []


def test_store_does_not_follow_record_hardlink(private_store, tmp_path):
    saved = private_store.write({'output_text': '{}', 'provenance': {}, 'diagnosis': {}})
    os.link(private_store._path(saved['record_id']), tmp_path/'outside-link')
    with pytest.raises(PermissionError):
        private_store.read(saved['record_id'])


def test_expired_records_are_cleaned_on_next_store_open(private_store, monkeypatch):
    now = time.time(); monkeypatch.setattr(time, 'time', lambda: now)
    private_store.write({'output_text': '{}', 'provenance': {}, 'diagnosis': {}})
    monkeypatch.setattr(time, 'time', lambda: now+RETENTION_SECONDS+1)
    reopened = PrivateObservationStore(private_store.root)
    assert reopened.expiry_cleanup_on_open['expired_records_removed'] == 1
    assert list(reopened.directory.glob('*.r1diag')) == []


def test_capacity_is_bounded_and_never_removes_unexpired_records(private_store, monkeypatch):
    import bjlab.private_observation_store as storage
    monkeypatch.setattr(storage, 'MAX_RECORDS', 1)
    saved = private_store.write({'output_text': '{}', 'provenance': {}, 'diagnosis': {}})
    with pytest.raises(PermissionError):
        private_store.write({'output_text': '{}', 'provenance': {}, 'diagnosis': {}})
    assert private_store.read(saved['record_id'])['output_text'] == '{}'


def test_wrong_protection_context_never_returns_plaintext(private_store, monkeypatch):
    saved = private_store.write({'output_text': 'private-only', 'provenance': {}, 'diagnosis': {}})
    def inaccessible(data):
        raise PermissionError('Different account cannot decrypt.')
    monkeypatch.setattr(private_store.protection, 'unprotect', inaccessible)
    with pytest.raises(PermissionError):
        private_store.read(saved['record_id'])


def test_schema_invalid_text_is_retained_without_becoming_live(private_store):
    text = '{"c":'
    frame, reader, scope = fixture_reader(text)
    receipt = RetainingStillDiagnostic(reader, private_store, scope).run(frame, capture_ns=time.monotonic_ns())
    assert receipt['category'] == 'json_format_rejection'
    assert private_store.read(receipt['retention']['record_id'])['output_text'] == text
    assert receipt['eligible_for_live'] is False


def test_late_valid_output_remains_diagnostic_only_and_is_not_resurrected(private_store, monkeypatch):
    text = json.dumps(base_output()); frame, reader, scope = fixture_reader(text)
    clock = time.monotonic_ns(); capture = clock
    monkeypatch.setattr(time, 'monotonic_ns', lambda: clock)
    original = reader.transport.post
    def late(*args, **kwargs):
        nonlocal clock
        value = original(*args, **kwargs); clock += 4_500_000_000
        return value
    monkeypatch.setattr(reader.transport, 'post', late)
    receipt = RetainingStillDiagnostic(reader, private_store, scope).run(frame, capture_ns=capture)
    assert receipt['reader_status'] == receipt['category'] == 'timeout'
    assert receipt['reader_elapsed_ms'] == 4500
    assert receipt['content_diagnosis']['category'] == 'valid_usable_content'
    assert receipt['eligible_for_live'] is False and receipt['advice'] is None
    assert private_store.read(receipt['retention']['record_id'])['output_text'] == text
    assert reader.transport.submissions == reader.budget.settled == 1


def test_stale_reply_has_separate_category_and_never_returns_an_advisor(private_store):
    frame, reader, scope = fixture_reader(json.dumps(base_output()))
    receipt = RetainingStillDiagnostic(reader, private_store, scope).run(frame,
        capture_ns=time.monotonic_ns(), evidence_current=False)
    assert receipt['category'] == 'stale_response'
    assert receipt['content_diagnosis']['category'] == 'valid_usable_content'
    assert receipt['eligible_for_live'] is False and receipt['advice'] is None


def test_offline_command_has_no_inference_or_advisor():
    result = run_offline()
    assert result['provider_calls'] == 0 and result['cases_passed'] == 15
    assert result['credentials_loaded'] is False and result['advisor_connected'] is False
