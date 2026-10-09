"""New sessions, observable abstention cases and oracle-free request identity."""
from copy import deepcopy
import json
from pathlib import Path
import socket

import pytest

from bjlab.live_state import LiveObservation
from bjlab.numeric_provenance import semantic_gate
from validation.tools.gemini_request_ablation import request_payload
from validation.tools.gemini_new_session_prepare import CASES, ORDER, corpus_case


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args,**kwargs): raise AssertionError('No network during corpus tests.')
    monkeypatch.setattr(socket,'socket',fail); monkeypatch.setattr(socket,'getaddrinfo',fail)


@pytest.fixture(params=CASES,ids=ORDER)
def owned_case(request):
    if not Path('C:/Windows/Fonts/'+request.param[3]).is_file():
        pytest.skip('Declared Windows artwork font unavailable; no substitute.')
    return request.param,corpus_case(request.param)


def test_five_sessions_are_distinct_and_predeclared():
    assert len(set(ORDER)) == len(ORDER) == len({s[2] for s in CASES}) == 5
    assert [s[-1] for s in CASES] == [True,True,True,False,False]


def test_natural_pixels_only_make_predeclared_decision_or_abstention(owned_case):
    spec,(frame,observed,truth,visibility,stage,family)=owned_case
    assert frame.details == () and [n for n,_ in frame.images()] == ['table']
    assert semantic_gate(observed,available_views={'table'})['usable'] == spec[-1]
    assert stage['round'] >= 1
    if spec[0] == 'new-unreadable':
        assert any(c.visibility == 'unreadable' and c.rank is None and c.suit is None for c in observed.cards)
    if spec[0] == 'new-settled':
        assert observed.phase == 'settled' and not observed.controls


def test_table_request_has_no_truth_metadata_and_identical_configuration(owned_case):
    spec,(frame,observed,truth,visibility,stage,family)=owned_case
    payload=request_payload(frame,'json-mode')
    parts=payload['contents'][0]['parts']
    assert sum('inlineData' in part for part in parts) == 1
    texts=' '.join(part.get('text','') for part in parts)
    assert spec[0] not in texts and str(spec[2]) not in texts
    assert 'physical_instance' not in texts and 'expected_usable_r1' not in texts
    assert payload['generationConfig']['maxOutputTokens'] == 1024
    assert payload['generationConfig']['thinkingConfig'] == {'thinkingLevel':'MINIMAL','includeThoughts':False}
    assert payload['generationConfig']['responseMimeType'] == 'application/json'


def test_table_only_rejects_any_numeric_claim_to_unsent_detail(owned_case):
    spec,(frame,observed,*_)=owned_case
    raw=observed.model_dump(); raw['numbers'][0]['view']='dealer'
    changed=LiveObservation.model_validate(raw)
    result=semantic_gate(changed,available_views={'table'})
    assert not result['usable']
    assert any(n['blocks_r1'] for n in result['normalized_numbers'])
