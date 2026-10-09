"""Integrated opt-in phase contract: request changes, safety does not."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import socket
import time

import pytest

from bjlab import paired_deadline_reader as path
from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_state import wire_schema
from bjlab.visible_phase_deadline_reader import VisiblePhaseDeadlineReader, add_visible_phase_vocabulary, PHASE_RULES
from tests.test_available_view_deadline_reader import setup as bound_setup, Local
from tests.test_numeric_provenance import state, number


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args,**kwargs):raise AssertionError('Fixture boundary only: no DNS or sockets.')
    monkeypatch.setattr(socket,'socket',fail);monkeypatch.setattr(socket,'getaddrinfo',fail)


def setup(observation=None):
    native,evidence,stamp,budget,transport,bound=bound_setup(observation)
    cloud=VisiblePhaseDeadlineReader(GeminiConfig(),budget,
        [sha256(p).hexdigest() for _,p in native.images()],transport=transport)
    return native,evidence,stamp,budget,transport,bound,cloud


def test_only_first_instruction_changes_no_schema_images_config_or_baseline_mutation():
    native,_,_,_,_,bound,cloud=setup()
    before_schema=deepcopy(wire_schema());baseline=bound.payload(native);original=deepcopy(baseline)
    expected=deepcopy(baseline);expected['systemInstruction']['parts'][0]['text']+=PHASE_RULES
    assert cloud.payload(native)==expected
    assert add_visible_phase_vocabulary(baseline)==expected and baseline==original
    assert wire_schema()==before_schema
    assert 'settled' in PHASE_RULES and 'waiting' in PHASE_RULES and 'conflicting' in PHASE_RULES


@pytest.mark.parametrize('change',['already_bound','no_view_binding','not_json'])
def test_invalid_request_cannot_receive_phase_rule(change):
    native,_,_,_,_,bound,cloud=setup();payload=bound.payload(native)
    if change=='already_bound':payload=cloud.payload(native)
    elif change=='no_view_binding':payload['systemInstruction']['parts'][0]['text']='unverified instruction'
    else:payload['generationConfig']['responseMimeType']='text/plain'
    with pytest.raises(ValueError):add_visible_phase_vocabulary(payload)


def test_actual_post_is_phase_bound_and_keeps_original_capture_deadline():
    native,evidence,stamp,budget,transport,bound,cloud=setup()
    result=path.local_first_attempt(evidence,Local(False),cloud)
    assert result['route']=='fallback' and result['presented'] and len(transport.calls)==1
    payload,deadline,_=transport.calls[0]
    assert payload==cloud.payload(native) and PHASE_RULES in payload['systemInstruction']['parts'][0]['text']
    assert deadline==stamp.capture_ns+3_000_000_000 and len(budget.reserves)==1
    assert result['advisor_payload']['evidence_capture_ns']==stamp.capture_ns


def test_sufficient_local_result_still_uses_zero_cloud_requests():
    native,evidence,stamp,budget,transport,bound,cloud=setup()
    result=path.local_first_attempt(evidence,Local(True),cloud)
    assert result['route']=='local' and result['presented']
    assert not transport.calls and not budget.reserves


@pytest.mark.parametrize('phase',['waiting','settled','unknown','player'])
def test_phase_isolated_gate_calls_solver_only_for_player(phase,monkeypatch):
    calls=[];solve=path.recommend
    def counted(*args,**kwargs):calls.append(True);return solve(*args,**kwargs)
    monkeypatch.setattr(path,'recommend',counted)
    observation=state().model_copy(update={'phase':phase})
    native,evidence,stamp,budget,transport,bound,cloud=setup(observation)
    result=path.local_first_attempt(evidence,Local(False),cloud)
    expected=phase=='player'
    assert result['status']=='completed' and result['presented']==expected and len(transport.calls)==1
    assert len(calls)==int(expected) and bool(result['advisor_payload'])==expected


@pytest.mark.parametrize('numbers',[
    [number('SESSION 20',20,'ui','dealer')],
    [number('PLAYER TOTAL 21',21,'player_total')],
])
def test_phase_rule_cannot_override_number_or_source_gate(numbers,monkeypatch):
    calls=[];monkeypatch.setattr(path,'recommend',lambda *a,**k:calls.append(True))
    native,evidence,stamp,budget,transport,bound,cloud=setup(state(numbers))
    result=path.local_first_attempt(evidence,Local(False),cloud)
    assert result['status']=='completed' and not result['presented']
    assert result['advisor_payload'] is None and result['advice'] is None and not calls
    assert len(transport.calls)==1


@pytest.mark.parametrize('change',['pixels_return','disconnect_reconnect','source','table','geometry'])
def test_new_phase_request_does_not_revive_old_evidence(change):
    native,evidence,stamp,budget,transport,bound,cloud=setup()
    def changed():
        if change=='pixels_return':
            evidence.capture(replace(native,table_png=b'changed'),source=stamp.source,table=stamp.table)
            evidence.capture(native,source=stamp.source,table=stamp.table)
        elif change=='disconnect_reconnect':
            evidence.disconnect();evidence.capture(native,source=stamp.source,table=stamp.table)
        elif change=='source':evidence.capture(native,source='another-source',table=stamp.table)
        elif change=='table':evidence.capture(native,source=stamp.source,table='another-table')
        else:evidence.capture(replace(native,source_size=(200,200)),source=stamp.source,table=stamp.table)
    transport.after=changed
    result=path.local_first_attempt(evidence,Local(False),cloud)
    assert len(transport.calls)==1 and not result['presented'] and result['advisor_payload'] is None


@pytest.mark.parametrize('stage',['local','gate','solver','serialization'])
def test_visible_phase_keeps_deadline_across_all_stages(stage,monkeypatch):
    native,evidence,stamp,budget,transport,bound,cloud=setup()
    clock=[stamp.capture_ns+1_000_000];monkeypatch.setattr(time,'monotonic_ns',lambda:clock[0])
    local=Local(False)
    def advance(ms):
        while ms:
            step=min(ms,80);ms-=step;clock[0]+=step*1_000_000
            evidence.capture(native,source=stamp.source,table=stamp.table,capture_ns=clock[0])
    if stage=='local':
        read=local.read
        def slow(frame):result=read(frame);advance(2900);return result
        local.read=slow;transport.after=lambda:advance(200)
    elif stage=='gate':
        gate=path.semantic_gate
        def slow(*a,**k):result=gate(*a,**k);advance(3001);return result
        monkeypatch.setattr(path,'semantic_gate',slow)
    elif stage=='solver':
        solver=path.recommend
        def slow(*a,**k):result=solver(*a,**k);advance(3001);return result
        monkeypatch.setattr(path,'recommend',slow)
    else:
        dumps=path.json.dumps
        def slow(value,*a,**k):
            result=dumps(value,*a,**k)
            if isinstance(value,dict) and value.get('action') and 'evidence_capture_ns' in value:advance(3001)
            return result
        monkeypatch.setattr(path.json,'dumps',slow)
    result=path.local_first_attempt(evidence,local,cloud)
    assert len(transport.calls)==1 and transport.calls[0][1]==stamp.capture_ns+3_000_000_000
    assert not result['presented'] and result['advisor_payload'] is None and result['advice'] is None
    assert 'original_evidence_deadline_expired' in result['revalidation']['reasons']
