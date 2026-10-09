"""Same pixels per pair, preserved contradiction and numeric omission failures."""
from copy import deepcopy
from pathlib import Path
import socket

import pytest

from bjlab.live_state import LiveObservation
from bjlab.numeric_provenance import semantic_gate
from validation.tools.gemini_request_ablation import request_payload
from validation.tools.gemini_paired_total_check import PAIRS,SPECS,scene,relevant_totals_exact
from validation.tools.numeric_semantic_score import semantic_score


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args,**kwargs): raise AssertionError('No sockets or DNS in paired preparation tests.')
    monkeypatch.setattr(socket,'socket',fail); monkeypatch.setattr(socket,'getaddrinfo',fail)


@pytest.fixture(params=SPECS,ids=['usable','contradictory'])
def owned_scene(request):
    if not Path('C:/Windows/Fonts/'+request.param[3]).is_file():
        pytest.skip('Declared Windows artwork unavailable; no silent substitute.')
    return scene(request.param)


def test_predeclared_counterbalanced_order_and_new_sessions():
    assert PAIRS == (('S1','C'),('S1','D'),('S2','D'),('S2','C'))
    assert len({spec[2] for spec in SPECS})==2
    assert all(seed > 91008047 for seed in (spec[2] for spec in SPECS))


def test_each_pair_has_identical_single_native_image(owned_scene):
    frame,observation,truth,*_=owned_scene
    payloads=[request_payload(frame,mode) for mode in ('structured-card-limit-local','json-mode')]
    images=[[part['inlineData'] for part in p['contents'][0]['parts'] if 'inlineData' in part] for p in payloads]
    assert images[0]==images[1] and len(images[0])==1 and not frame.details
    assert payloads[0]['generationConfig']['thinkingConfig']==payloads[1]['generationConfig']['thinkingConfig']
    assert payloads[0]['generationConfig']['maxOutputTokens']==payloads[1]['generationConfig']['maxOutputTokens']==1024


def test_reference_and_pixels_preserve_counterfactual_digit_change(owned_scene):
    frame,observation,truth,visibility,stage,change,original=owned_scene
    assert stage['phase']=='player'
    assert semantic_gate(observation,available_views={'table'})['usable'] == (change is None)
    if change:
        assert change['printed_total']==change['natural_visible_card_total']+3
        assert change['cards_controls_labels_unchanged'] and change['changed_pixels'] > 0
        assert original.table_png!=frame.table_png
        assert any('total' in reason.lower() for reason in semantic_gate(observation,available_views={'table'})['reasons'])
    else:
        assert any(n.role=='unknown' and n.label is None for n in observation.numbers)


def test_irrelevant_ui_role_error_remains_transcription_error_without_total_invention():
    if not Path('C:/Windows/Fonts/candarab.ttf').is_file(): pytest.skip('Windows artwork required.')
    frame,expected,*_=scene(SPECS[0]); truth=expected.model_dump()
    altered=deepcopy(truth); altered['numbers'][-1]['role']='ui'
    actual=LiveObservation.model_validate(altered)
    scored=semantic_score(actual,truth,elapsed_ms=1000,available_views={'table'})
    assert scored['semantic_correct_usable_r1'] and not scored['semantic_false_accept']
    assert not scored['semantic_numeric_provenance_exact']
    assert relevant_totals_exact(actual,truth)


def test_omitted_contradictory_total_is_false_accept_not_success():
    if not Path('C:/Windows/Fonts/constanb.ttf').is_file(): pytest.skip('Windows artwork required.')
    frame,expected,*_=scene(SPECS[1]); truth=expected.model_dump()
    altered=deepcopy(truth); altered['numbers']=[n for n in altered['numbers'] if n['role']!='player_total']
    actual=LiveObservation.model_validate(altered)
    assert semantic_gate(actual,available_views={'table'})['usable']
    scored=semantic_score(actual,truth,elapsed_ms=1000,available_views={'table'})
    assert not scored['expected_usable_r1'] and scored['semantic_false_accept']
    assert not scored['semantic_correct_usable_r1'] and not relevant_totals_exact(actual,truth)


def test_unsent_numeric_view_fails_gate_and_evaluator(owned_scene):
    frame,expected,*_=owned_scene; truth=expected.model_dump()
    altered=deepcopy(truth); altered['numbers'][0]['view']='dealer'
    actual=LiveObservation.model_validate(altered)
    scored=semantic_score(actual,truth,elapsed_ms=1000,available_views={'table'})
    assert not semantic_gate(actual,available_views={'table'})['usable']
    assert not scored['semantic_usable_r1'] and not scored['semantic_numeric_provenance_exact']
