"""Bound request with genuine local-first deadline/revalidation; mock network."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import socket
import time

import pytest

from bjlab.available_image_views import bind_available_numeric_views
from bjlab.available_view_deadline_reader import AvailableViewDeadlineReader
from bjlab.grounded_cloud import GeminiConfig
from bjlab.grounded_state import GroundedResult, adapt_legacy
from bjlab.hybrid_evidence import CurrentEvidence
from bjlab.paired_deadline_reader import local_first_attempt
from tests.test_numeric_provenance import state, number
from tests.test_r1_readers import frame
from validation.tools.gemini_request_ablation import request_payload


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs): raise AssertionError('Mock boundary only; no DNS or sockets.')
    monkeypatch.setattr(socket,'socket',fail); monkeypatch.setattr(socket,'getaddrinfo',fail)


class Budget:
    def __init__(self): self.reserves=[]; self.settlements=[]
    def reserve(self,cost): self.reserves.append(cost); return 'fixture-reservation'
    def settle(self,identity,cost): self.settlements.append((identity,cost))
    def receipt(self): return {'requests_attempted':len(self.reserves)}


class Transport:
    def __init__(self, observation, after=None):
        self.observation=observation; self.after=after; self.timings={}; self.calls=[]
    def post(self,payload,*,deadline_ns,reservation_id):
        self.calls.append((deepcopy(payload),deadline_ns,reservation_id))
        if self.after: self.after()
        return {'model':'gemini-3.5-flash-lite','status':'completed',
            'usage':{'input_tokens':500,'output_tokens':180},
            'output':[{'type':'message','content':[{'type':'output_text',
                'text':self.observation.model_dump_json(by_alias=True)}]}]}


class Local:
    name='fixture-local'
    def __init__(self,usable=False): self.usable=usable; self.calls=0
    def read(self,native):
        self.calls+=1
        legacy=state().legacy_gate_view()
        if not self.usable: legacy.phase='unknown'; legacy.controls=[]
        return GroundedResult(native.frame_id,self.name,'completed',adapt_legacy(legacy),0,{})


def setup(observation=None,after=None):
    native=replace(frame(),details=()); evidence=CurrentEvidence()
    stamp=evidence.capture(native,source='fixture-owned',table='one')
    budget=Budget(); transport=Transport(observation or state(),after)
    cloud=AvailableViewDeadlineReader(GeminiConfig(),budget,
        [sha256(p).hexdigest() for _,p in native.images()],transport=transport)
    return native,evidence,stamp,budget,transport,cloud


def test_live_adapter_serializes_exact_same_corrected_D_request():
    native,_,_,_,_,cloud=setup()
    expected=bind_available_numeric_views(request_payload(native,'json-mode'),native,mode='json-mode')
    assert cloud.payload(native)==expected


def test_usable_local_route_performs_no_network_or_reservation():
    native,evidence,stamp,budget,transport,cloud=setup()
    local=Local(True); result=local_first_attempt(evidence,local,cloud)
    assert result['route']=='local' and result['presented'] and local.calls==1
    assert not transport.calls and not budget.reserves


def test_natural_fallback_keeps_original_capture_deadline_and_bound_payload():
    native,evidence,stamp,budget,transport,cloud=setup()
    result=local_first_attempt(evidence,Local(False),cloud)
    assert result['route']=='fallback' and result['presented'] and len(transport.calls)==1
    payload,deadline,_=transport.calls[0]
    assert deadline==stamp.capture_ns+3_000_000_000
    assert payload==cloud.payload(native) and result['local_gate']['usable'] is False
    assert result['advisor_payload']['evidence_capture_ns']==stamp.capture_ns
    assert result['advisor_payload']['r2_certified'] is False


@pytest.mark.parametrize('view',['dealer','controls'])
def test_cloud_ignoring_bound_names_is_rejected_before_advice(view,monkeypatch):
    from bjlab import paired_deadline_reader as path
    calls=[];monkeypatch.setattr(path,'recommend',lambda *a,**k:calls.append((a,k)))
    native,evidence,stamp,budget,transport,cloud=setup(state([number('SESSION 20',20,'ui',view)]))
    result=local_first_attempt(evidence,Local(False),cloud)
    assert result['route']=='fallback' and not result['presented']
    assert result['advice'] is None and result['advisor_payload'] is None
    assert any('source_view_not_available' in r for r in result['gate']['reasons'])
    assert result['status']=='completed' and calls==[] and len(transport.calls)==1


def test_cloud_contradictory_total_remains_blocked_after_view_repair(monkeypatch):
    from bjlab import paired_deadline_reader as path
    calls=[];monkeypatch.setattr(path,'recommend',lambda *a,**k:calls.append((a,k)))
    native,evidence,stamp,budget,transport,cloud=setup(state([number('PLAYER TOTAL 21',21,'player_total')]))
    result=local_first_attempt(evidence,Local(False),cloud)
    assert not result['presented'] and result['advisor_payload'] is None
    assert any('total disagrees' in r.lower() for r in result['gate']['reasons'])
    assert result['observation']['numbers'][0]['value']==21
    assert result['status']=='completed' and calls==[] and len(transport.calls)==1


def test_terminal_phase_is_rejected_for_phase_and_disabled_controls(monkeypatch):
    from bjlab import paired_deadline_reader as path
    calls=[];monkeypatch.setattr(path,'recommend',lambda *a,**k:calls.append((a,k)))
    native,evidence,stamp,budget,transport,cloud=setup(state().model_copy(update={'phase':'settled','controls':[]}))
    result=local_first_attempt(evidence,Local(False),cloud)
    assert result['status']=='completed' and not result['presented'] and result['advisor_payload'] is None
    assert calls==[] and len(transport.calls)==1
    assert 'Player turn is not established.' in result['gate']['reasons']
    assert not any('source_view_not_available' in r for r in result['gate']['reasons'])


@pytest.mark.parametrize('change',['pixels','disconnect','table','geometry','source','disconnect_reconnect','pixels_return'])
def test_pending_bound_response_cannot_survive_changed_current_evidence(change):
    native,evidence,stamp,budget,transport,cloud=setup()
    def after():
        if change=='disconnect': evidence.disconnect()
        elif change=='table': evidence.capture(native,source='fixture-owned',table='other')
        elif change=='geometry': evidence.capture(replace(native,source_size=(200,200)),source='fixture-owned',table='one')
        elif change=='source': evidence.capture(native,source='another-source',table='one')
        elif change=='disconnect_reconnect':
            evidence.disconnect();evidence.capture(native,source='fixture-owned',table='one')
        elif change=='pixels_return':
            evidence.capture(replace(native,table_png=b'changed-acquisition'),source='fixture-owned',table='one')
            evidence.capture(native,source='fixture-owned',table='one')
        else: evidence.capture(replace(native,table_png=b'changed-acquisition'),source='fixture-owned',table='one')
    transport.after=after
    result=local_first_attempt(evidence,Local(False),cloud)
    assert len(transport.calls)==1 and not result['presented']
    assert result['advice'] is None and result['advisor_payload'] is None


def test_changed_unreviewed_pixels_cannot_be_posted_by_the_adapter():
    native,evidence,stamp,budget,transport,cloud=setup()
    changed=replace(native,table_png=b'unreviewed')
    result=cloud.read(changed,capture_ns=time.monotonic_ns())
    assert result.status=='blocked' and result.observation is None
    assert not transport.calls and not budget.reserves


@pytest.mark.parametrize('slow_stage',['local','gate','solver','serialization'])
def test_fresh_held_pixels_never_renew_the_original_deadline(monkeypatch,slow_stage):
    from bjlab import paired_deadline_reader as path
    native,evidence,stamp,budget,transport,cloud=setup()
    clock=[stamp.capture_ns+1_000_000]
    monkeypatch.setattr(time,'monotonic_ns',lambda:clock[0])
    local=Local(False)
    def advance(milliseconds):
        while milliseconds:
            step=min(milliseconds,80);milliseconds-=step;clock[0]+=step*1_000_000
            evidence.capture(native,source=stamp.source,table=stamp.table,capture_ns=clock[0])
    if slow_stage=='local':
        read=local.read
        def slow_local(frame):
            value=read(frame);advance(2900);return value
        local.read=slow_local;transport.after=lambda:advance(200)
    elif slow_stage=='gate':
        gate=path.semantic_gate
        def slow_gate(*args,**kwargs):
            value=gate(*args,**kwargs);advance(3001);return value
        monkeypatch.setattr(path,'semantic_gate',slow_gate)
    elif slow_stage=='solver':
        solve=path.recommend
        def slow_solver(*args,**kwargs):
            value=solve(*args,**kwargs);advance(3001);return value
        monkeypatch.setattr(path,'recommend',slow_solver)
    else:
        dumps=path.json.dumps
        def slow_serialize(value,*args,**kwargs):
            text=dumps(value,*args,**kwargs)
            if isinstance(value,dict) and value.get('action') and 'evidence_capture_ns' in value:
                advance(3001)
            return text
        monkeypatch.setattr(path.json,'dumps',slow_serialize)
    result=local_first_attempt(evidence,local,cloud)
    assert len(transport.calls)==1 and transport.calls[0][1]==stamp.capture_ns+3_000_000_000
    assert not result['presented'] and result['advisor_payload'] is None and result['advice'] is None
    assert 'original_evidence_deadline_expired' in result['revalidation']['reasons']
    assert result['original_evidence']['capture_ns']==stamp.capture_ns
