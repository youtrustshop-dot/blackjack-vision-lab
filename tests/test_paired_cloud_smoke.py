"""Offline guards against repeated or changed paid submissions. No credentials."""
import json

import pytest

from validation.tools.paired_cloud_prepare import NAMES, SMOKE, digest
from validation.tools.paired_cloud_smoke import FrozenPayloadGuard, PAIRS, claim, prerequisites


class OfflineTransport:
    def post(self, payload, timeout, *, reservation_id=None):
        self.calls.append((payload, timeout, reservation_id))
        return 'offline response'


class Guard(FrozenPayloadGuard, OfflineTransport):
    def __init__(self): self.calls = []


def test_one_attempt_then_repeat_is_blocked(tmp_path):
    guard = Guard(); payload = {'model': 'offline'}; path = tmp_path/'attempt.json'
    guard.bind(payload_sha256=digest(payload), attempt_claim=path)
    assert guard.post(payload, 3, reservation_id='offline reservation') == 'offline response'
    with pytest.raises(PermissionError): guard.post(payload, 3)
    guard.bind(payload_sha256=digest(payload), attempt_claim=path)
    with pytest.raises(FileExistsError): guard.post(payload, 3)
    assert len(guard.calls) == 1


def test_altered_payload_is_blocked_before_claim_or_transport(tmp_path):
    guard = Guard(); path = tmp_path/'attempt.json'
    guard.bind(payload_sha256=digest({'model': 'declared'}), attempt_claim=path)
    with pytest.raises(PermissionError): guard.post({'model': 'different'}, 3)
    assert not path.exists() and not guard.calls


def test_batch_claim_cannot_be_reused(tmp_path):
    path = tmp_path/'batch.json'; claim(path, {'pairs': PAIRS})
    with pytest.raises(FileExistsError): claim(path, {'pairs': PAIRS})


def test_exact_six_scope_has_no_retry_or_hybrid():
    assert len(PAIRS) == len(set(PAIRS)) == 6
    assert {case for case, _ in PAIRS} == set(SMOKE)
    assert {name for _, name in PAIRS} == set(NAMES)


def test_prerequisites_are_read_only_and_use_only_the_frozen_validation(monkeypatch, tmp_path):
    # A fixture ledger/corpus keeps CI independent of private artifacts and paid calls.
    import validation.tools.paired_cloud_smoke as module
    monkeypatch.setattr(module, 'credentials', lambda: pytest.fail('No credential loading'))
    monkeypatch.setattr(module, 'resolve_scope', lambda: pytest.fail('No network'))
    calls = []
    def checked(output, split, *, expected_freeze_sha256):
        calls.append((split, expected_freeze_sha256))
        return {}, [({'id': case, 'condition': case, 'independent_session': 'session-'+case}, object())
                    for case in SMOKE], {case: {} for case in SMOKE}
    matrix = tmp_path/'matrix.json'
    matrix.write_text(json.dumps({'api_access_policy': {'inference_authorized': False}}))
    monkeypatch.setattr(module, 'MATRIX', matrix)
    monkeypatch.setattr(module, 'checked', checked)
    monkeypatch.setattr(module, 'ledger_snapshot', lambda: {
        'sha256': module.INITIAL_LEDGER_SHA256, 'receipt': {'requests_attempted': 94,
        'unknown_charge_requests': 13, 'stopped': False, 'max_requests': 102,
        'accounted_upper_usd': '5.087190600', 'max_usd': '8'}})
    _, selected, truths, before, worst, policy = prerequisites()
    assert policy['inference_authorized'] is False and len(selected) == 3
    assert before['receipt']['requests_attempted'] == 94
    assert str(worst) == '2.5310064'
    assert calls == [('validation', module.FREEZE_SHA256)]
    assert all(record['id'] in truths for record, _ in selected.values())
