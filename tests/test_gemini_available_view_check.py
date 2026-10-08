"""Corrected packet preserves the consumed counterfactual without oracle hints."""
from copy import deepcopy
from dataclasses import replace
import socket

import pytest

from bjlab.available_image_views import bind_available_numeric_views
from bjlab.paired_persistent_http import canonical_digest
from tests.test_r1_readers import frame
from validation.tools.gemini_available_view_check import GATE, ORDER, MODE, MAX_RESERVATION
from validation.tools.gemini_five_diagnostics import FrozenRequestReader
from validation.tools.gemini_request_ablation import request_payload


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs): raise AssertionError('No network in corrected-control tests.')
    monkeypatch.setattr(socket,'socket',fail); monkeypatch.setattr(socket,'getaddrinfo',fail)


def test_two_consumed_controls_do_not_claim_new_session_validation():
    assert ORDER==('S1','S2') and MODE=='json-mode'
    assert str(MAX_RESERVATION)=='0.6342656'
    assert GATE['positive_timely_usable']==GATE['negative_grounded_content_abstention']==1
    assert GATE['relevant_total_provenance_exact']==2 and GATE['false_accepts']==0
    assert GATE['original_live_ms']==3000 and 'consumed' in GATE['scope']


def test_corrected_request_is_frozen_and_permanently_diagnostic_only():
    native=replace(frame(),details=())
    payload=bind_available_numeric_views(request_payload(native,MODE),native,mode=MODE)
    reader=FrozenRequestReader(native,payload,canonical_digest(payload),object(),object())
    assert reader.payload(native)==payload
    with pytest.raises(PermissionError,match='diagnostic-only'): reader.read(native,capture_ns=0)
    corrupted=deepcopy(payload); corrupted['systemInstruction']['parts'][0]['text']+='more'
    with pytest.raises(PermissionError,match='checksum'):
        FrozenRequestReader(native,corrupted,canonical_digest(payload),object(),object())


def test_role_layout_change_cannot_reuse_the_corrected_image_packet():
    native=replace(frame(),details=())
    payload=bind_available_numeric_views(request_payload(native,MODE),native,mode=MODE)
    reader=FrozenRequestReader(native,payload,canonical_digest(payload),object(),object())
    changed=replace(native,layout={**native.layout,'dealer':[0,0,.1,.1]})
    with pytest.raises(PermissionError,match='native packet'): reader.payload(changed)
