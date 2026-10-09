"""Frozen request identity and the five-cell diagnostic stop boundary; no network."""
from copy import deepcopy
from dataclasses import replace
import json
import socket

import pytest

from bjlab.live_state import LiveObservation
from bjlab.paired_persistent_http import canonical_digest
from tests.test_r1_readers import frame
from validation.tools.gemini_request_ablation import request_payload
from validation.tools.gemini_five_diagnostics import FrozenRequestReader, ordered_collection, transcription_components
from validation.tools.rejected_output_offline import base_output


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No sockets or DNS in prepared diagnostic tests.')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)


def reader_for(original, payload=None):
    payload = request_payload(original, 'structured-card-limit-local') if payload is None else payload
    return FrozenRequestReader(original, payload, canonical_digest(payload), object(), object())


def test_reader_returns_independent_exact_prepared_payloads():
    original = frame()
    payload = request_payload(original, 'json-mode')
    reader = reader_for(original, payload)
    output = reader.payload(original); output['generationConfig']['maxOutputTokens'] = 1
    payload['generationConfig']['maxOutputTokens'] = 2
    assert reader.payload(original)['generationConfig']['maxOutputTokens'] == 1024


def test_different_detail_cannot_reuse_prepared_request():
    original = frame(); reader = reader_for(original)
    changed = replace(original, details=((original.details[0][0], b'other-acquisition'),) + original.details[1:])
    with pytest.raises(PermissionError, match='native packet'):
        reader.payload(changed)


@pytest.mark.parametrize('change', ['checksum', 'output_cap', 'thinking'])
def test_changed_prepared_request_rejected_before_collection(change):
    original = frame(); payload = request_payload(original, 'json-mode')
    expected = canonical_digest(payload)
    if change == 'output_cap': payload['generationConfig']['maxOutputTokens'] = 1023
    elif change == 'thinking': payload['generationConfig']['thinkingConfig']['thinkingLevel'] = 'HIGH'
    else: payload['contents'][0]['parts'][0]['text'] += 'changed'
    with pytest.raises(PermissionError):
        FrozenRequestReader(original, payload, expected if change == 'checksum' else canonical_digest(payload), object(), object())


def test_diagnostic_reader_cannot_be_used_as_live_reader():
    with pytest.raises(PermissionError, match='diagnostic-only'):
        reader_for(frame()).read(frame(), capture_ns=0)


def test_ordered_cells_have_exactly_five_no_duplicate_submissions():
    seen, saved = [], []
    def collect(cell):
        seen.append(cell); return {'stop_before_next_request': False}
    ordered_collection(collect, lambda cell, result: saved.append(cell))
    assert seen == saved == list('ABCDE')


@pytest.mark.parametrize('failure', ['storage', 'auth', 'usage'])
def test_stop_cause_prevents_later_cells_without_retry(failure):
    seen, saved = [], []
    def collect(cell):
        seen.append(cell)
        return {'stop_before_next_request': cell == 'B',
            'transport': {'http_status': 401 if failure == 'auth' else 200},
            'error_type': 'provider_http_rejection' if failure == 'auth' else 'ValueError',
            'retention': {'reason': 'protected_storage_failed' if failure == 'storage' else 'no_complete_observation_received'}}
    with pytest.raises(PermissionError):
        ordered_collection(collect, lambda cell, result: saved.append(cell))
    assert seen == saved == ['A', 'B']


def test_http400_form_failure_can_continue_only_to_other_frozen_cells():
    seen = []
    def collect(cell):
        seen.append(cell)
        return {'stop_before_next_request': True, 'error_type': 'provider_http_rejection',
            'transport': {'http_status': 400}, 'retention': {'reason': 'no_complete_observation_received'}}
    ordered_collection(collect, lambda *args: None)
    assert seen == list('ABCDE')


def test_cards_in_rejected_number_output_are_diagnostic_only_not_repaired():
    valid = base_output()
    truth = LiveObservation.model_validate(valid).model_dump()
    rejected = deepcopy(valid); rejected['n'][0].update(l=None)
    text = json.dumps(rejected)
    with pytest.raises(ValueError): LiveObservation.model_validate_json(text)
    diagnostic = transcription_components(text, truth)
    assert diagnostic['rank'] == {'correct': 3, 'expected': 3}
    assert diagnostic['suit'] == {'correct': 3, 'expected': 3}
    assert diagnostic['backs'] == {'correct': 1, 'expected': 1}
    assert diagnostic['exact_card_inventory']
    assert 'cannot make rejected full state usable' in diagnostic['scope']
    assert json.loads(text)['n'][0]['l'] is None
