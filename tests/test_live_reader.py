"""Boundary/diagnostic tests; injected timings are never provider evidence."""
from hashlib import sha256
import json
import time
import asyncio

import pytest
from pydantic import ValidationError

from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_cloud import DiagnosticReader, sanitized_error
from bjlab.live_state import LiveObservation, live_gate, wire_schema
from bjlab.openai_reader import RequestBudget
from tests.test_r1_readers import frame
from validation.tools.api_reader_tournament import config
from validation.tools.live_reader_diagnosis import rest_errors, schema_issues, summarize


def observed(**changes):
    value={'c':[{'z':'player:0','r':'A','s':'H','v':'readable'},
        {'z':'player:0','r':'5','s':'D','v':'readable'},
        {'z':'dealer','r':'2','s':'C','v':'readable'},
        {'z':'dealer','r':None,'s':None,'v':'covered'}],
        't':'cards_present','p':'player','a':['hit','stand'],'n':[],'b':[]}
    value.update(changes)
    return LiveObservation.model_validate_json(json.dumps(value))


def test_live_number_label_provenance_survives_without_inventing_coordinates():
    ui={'v':20,'r':'ui','l':'SESSION','w':'table'}
    unknown={'v':20,'r':'unknown','l':None,'w':'table'}
    seen=observed(n=[ui,unknown])
    assert live_gate(seen)['usable'] and seen.totals()==({},[])
    assert len(seen.numbers)==2 and not hasattr(seen.numbers[0],'box')
    with pytest.raises(ValidationError):observed(n=[dict(ui,r='dealer_total')])
    with pytest.raises(ValidationError):observed(n=[dict(ui,r='dealer_total',l=None)])
    assert not live_gate(observed(n=[dict(ui,r='dealer_total',l='DEALER TOTAL')]))['usable']
    assert not live_gate(observed(n=[{'v':2,'r':'dealer_total','l':'DEALER TOTAL','w':'dealer'},
        {'v':8,'r':'dealer_total','l':'DEALER TOTAL','w':'dealer'}]))['usable']
    assert live_gate(seen)['contract']=='grounded-r1-live-v3'
    assert not live_gate(seen)['r2_certified']


def test_compact_schema_retains_unknown_objects_blockers_and_strict_validation():
    seen=observed();value=seen.model_dump(by_alias=True);value['c'][0].update(r=None,s=None,v='unreadable')
    assert not live_gate(observed(**value))['usable']
    value=seen.model_dump(by_alias=True);value['c'][-1]['r']='A'
    with pytest.raises(ValidationError):observed(**value)
    assert not live_gate(observed(b=['insurance']))['usable']
    with pytest.raises(ValidationError):observed(n=[{'v':20,'r':'ui','l':'x'*81,'w':'table'}])
    with pytest.raises(ValidationError):observed(confidence=.99)
    with pytest.raises(ValidationError):observed(a=['hit','hit'])
    assert not schema_issues(wire_schema())
    assert 'maxLength' not in json.dumps(wire_schema())


def test_providers_receive_identical_live_schema_and_pixels():
    f=frame();allowed={sha256(p).hexdigest() for _,p in f.images()}
    a=DiagnosticReader(config(fast=True),RequestBudget(1,1),allowed,provider='openai',variant='live',transport=object()).payload(f)
    b=DiagnosticReader(GeminiConfig(),RequestBudget(1,1),allowed,provider='gemini',variant='live',transport=object()).payload(f)
    assert a['text']['format']['schema']==b['generationConfig']['responseFormat']['text']['schema']
    assert b['generationConfig']['responseFormat']['text']['mimeType']=='APPLICATION_JSON'
    assert a['instructions']==b['systemInstruction']['parts'][0]['text']
    ai=[p['image_url'].split(',',1)[1] for p in a['input'][0]['content'] if p['type']=='input_image']
    bi=[p['inlineData']['data'] for p in b['contents'][0]['parts'] if 'inlineData' in p]
    assert ai==bi
    with pytest.raises(PermissionError):DiagnosticReader(config(fast=True),RequestBudget(1,1),[],provider='openai',variant='live',transport=object()).payload(f)


def test_rest_lint_and_safe_error_never_echo_secrets_or_free_text():
    discovery={'schemas':{'G':{'type':'object','properties':{'thinkingLevel':{'type':'string','enum':['MINIMAL']}}}}}
    assert rest_errors({'thinkingLevel':'MINIMAL'},{'$ref':'G'},discovery)==[]
    assert rest_errors({'thinkingLevel':'OFF','private_key':'secret'},{'$ref':'G'},discovery)==[
        'request.thinkingLevel:invalid_string_or_enum','request.private_key:unknown_field']
    private=b'{"error":{"status":"INVALID_ARGUMENT","message":"schema maxLength rejected: sk-private-token and private image label"}}'
    safe=sanitized_error(private)
    assert safe['category']=='invalid_schema' and safe['mentioned_fields']==['maxlength']
    assert 'sk-private' not in json.dumps(safe) and 'private image' not in json.dumps(safe)
    assert sanitized_error(b'not JSON')['category']=='unclassified'
    generic=b'{"error":{"code":400,"status":"INVALID_ARGUMENT","message":"Request contains an invalid argument."}}'
    assert sanitized_error(generic)['category']=='generic_invalid_argument'
    assert sanitized_error(generic)['mentioned_fields']==[]


class Response:
    def __init__(self,delay=0):self.delay=delay
    def post(self,payload,timeout):
        time.sleep(self.delay)
        return {'model':'gpt-6-luna','status':'completed','service_tier':'fast',
            'usage':{'input_tokens':120,'output_tokens':80},
            'output':[{'type':'message','content':[{'type':'output_text','text':observed().model_dump_json(by_alias=True)}]}]}


@pytest.mark.parametrize('change', ['model', 'usage', 'output_limit'])
def test_unreconciled_provider_usage_cannot_yield_a_usable_observation(change):
    class Unreconciled(Response):
        def post(self,payload,timeout):
            result=super().post(payload,timeout)
            if change=='model':result['model']='unpriced-provider-model'
            elif change=='usage':result['usage']['input_tokens']=True
            else:result['usage']['output_tokens']=1025
            return result
    f=frame();allowed={sha256(p).hexdigest() for _,p in f.images()}
    ceiling=RequestBudget(1,1)
    result=DiagnosticReader(config(fast=True),ceiling,allowed,provider='openai',variant='live',transport=Unreconciled()).read(f)
    assert result.status=='error' and result.observation is None
    assert result.diagnostics['unreconciled_usage'] and ceiling.requests==1
    assert 'observation_parse_validate_ms' not in result.diagnostics['timing']


def test_complete_json_deadline_rejects_late_injected_response_and_keeps_timings():
    from dataclasses import replace
    f=frame();allowed={sha256(p).hexdigest() for _,p in f.images()}
    result=DiagnosticReader(replace(config(fast=True),timeout_seconds=.03),RequestBudget(1,1),allowed,
        provider='openai',variant='live',transport=Response(.05)).read(f)
    assert result.status=='timeout' and result.observation is None
    assert result.diagnostics['late_complete_json_discarded']
    assert result.diagnostics['usage']['output_tokens']==80
    assert result.diagnostics['timing']['observation_parse_validate_ms']>=0


def test_hybrid_requires_correct_timely_grounded_states_not_legacy_or_survivor_latency():
    def item(name='luna-fast-live',status='completed',elapsed=1900,correct=True):
        return dict(reader=name,status=status,elapsed_ms=elapsed,inventory_exact=correct,
            rank_presence_exact=correct,phase_correct=correct,controls_correct=correct,
            complete_grounded_state=correct,correct_usable_r1=correct,false_accepted_state=False)
    rows=[item(),item(),item()]
    assert summarize(rows)['luna-fast-live']['hybrid_gate_passed']
    rows[-1]=item(status='timeout',elapsed=3100,correct=False)
    result=summarize(rows)['luna-fast-live']
    assert not result['hybrid_gate_passed'] and result['failure_rate_attempted']==pytest.approx(1/3)
    assert result['latency_complete_ms']['p95']==1900  # must accompany failure rate
    assert not summarize([item('luna-fast-v1')]*3)['luna-fast-v1']['hybrid_gate_passed']


def test_deadline_does_not_join_a_slow_dns_style_executor_on_caller_exit():
    from bjlab.bounded_network import NETWORK
    async def slow_lookup():
        await asyncio.get_running_loop().run_in_executor(None,time.sleep,.35)
        raise AssertionError('A cancelled lookup must never reach submission/output.')
    started=time.perf_counter()
    with pytest.raises(TimeoutError):asyncio.run(NETWORK.request(slow_lookup(),.04))
    assert time.perf_counter()-started<.2


def test_authorization_is_checked_before_reserving_network_attempt(monkeypatch):
    from validation.tools import live_reader_diagnosis as runner
    def blocked(epoch):raise PermissionError('blocked_zero_api_budget')
    monkeypatch.setattr(runner,'require_inference_authorization',blocked)
    ceiling=RequestBudget(2,1)
    with pytest.raises(PermissionError):runner.readers(set(),ceiling)
    assert ceiling.requests==0
