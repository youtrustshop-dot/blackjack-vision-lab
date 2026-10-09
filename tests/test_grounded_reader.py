"""Contract tests, not cloud accuracy/latency evidence."""
import asyncio
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import json

from PIL import Image
import pytest
from pydantic import ValidationError

from bjlab.grounded_cloud import GeminiConfig, GeminiTransport, GroundedCloudReader
from bjlab.grounded_state import GroundedObservation, VisibleNumber, grounded_gate, adapt_legacy
from bjlab.hybrid_evidence import CurrentEvidence, FrozenGroundedLocal, hybrid_attempt
from bjlab.openai_reader import RequestBudget
from bjlab.state_reader import prepare_frame
from tests.test_r1_readers import frame, observation
from validation.tools.api_reader_tournament import config
from validation.tools.grounded_corpus import PARTITIONS, render, checked_inputs, card_tile, SUITS
from validation.tools.grounded_reader_tournament import score, summaries


def grounded(**kwargs):
    value=observation(phase='player',controls=['hit','stand']).model_dump()
    value.pop('player_total');value.pop('dealer_total');value['numbers']=[]
    value.update(kwargs)
    return GroundedObservation.model_validate_json(json.dumps(value))


def number(value=20,role='ui',label='SESSION'):
    return {'value':value,'role':role,'label':label,'view':'table','box':[.8,.1,.1,.04]}


def test_numeric_provenance_retained_instead_of_silently_repairing_total():
    seen=grounded(numbers=[number(),number(role='unknown',label=None)])
    assert grounded_gate(seen)['usable']
    assert seen.totals()==({},[])
    assert len(seen.model_dump()['numbers'])==2
    wrong=grounded(numbers=[number(role='dealer_total',label='DEALER TOTAL')])
    assert not grounded_gate(wrong)['usable']
    assert 'disagrees' in ' '.join(grounded_gate(wrong)['reasons'])
    with pytest.raises(ValidationError):grounded(numbers=[number(role='dealer_total',label='SESSION')])
    with pytest.raises(ValidationError):grounded(numbers=[number(role='dealer_total',label=None)])


def test_conflicting_attributed_totals_and_unsupported_controls_block():
    seen=grounded(numbers=[number(7,'dealer_total','DEALER TOTAL'),number(8,'dealer_total','DEALER TOTAL')])
    assert not grounded_gate(seen)['usable']
    assert not grounded_gate(grounded(controls=[]))['usable']
    assert not grounded_gate(grounded(phase='settled'))['usable']


@pytest.mark.parametrize('box',[[-.1,.1,.1,.1],[.9,.1,.5,.1],[.1,.1,0,.1],[.1,.1,.1],[float('nan'),.1,.1,.1]])
def test_numeric_regions_reject_ungrounded_or_nonfinite_coordinates(box):
    with pytest.raises(ValidationError):grounded(numbers=[dict(number(),box=box)])


def test_partial_face_is_separate_from_back_unknown_and_absence():
    cards=grounded().model_dump()['cards']
    cards[0]['visibility']='partial';cards[0]['suit']=None
    assert grounded_gate(grounded(cards=cards))['usable']
    assert not grounded_gate(grounded(cards=cards),capability='poker-cards')['usable']
    cards[0].update(visibility='unreadable',rank=None,suit=None)
    assert not grounded_gate(grounded(cards=cards))['usable']
    cards[0]['rank']='A'
    with pytest.raises(ValidationError):grounded(cards=cards)
    assert grounded(table_state='empty',cards=[]).table_state=='empty'


def test_legacy_adapter_never_invents_number_region_label_or_certified_history():
    assert adapt_legacy(observation(player_total=None,dealer_total=None)).numbers==[]
    with pytest.raises(ValueError):adapt_legacy(observation(dealer_total=20))
    gate=grounded_gate(grounded())
    assert not gate['r2_certified'] and not gate['shoe_history_certified']


def test_same_input_schema_prompt_and_native_crops_for_both_providers():
    prepared=frame();allowed={sha256(p).hexdigest() for _,p in prepared.images()}
    fake=object()
    a=GroundedCloudReader(config(fast=True),RequestBudget(1,'1'),allowed,provider='openai',transport=fake).payload(prepared)
    b=GroundedCloudReader(GeminiConfig(),RequestBudget(1,'1'),allowed,provider='gemini',transport=fake).payload(prepared)
    assert a['text']['format']['schema']==b['generationConfig']['responseJsonSchema']
    assert b['generationConfig']['responseMimeType']=='application/json'
    assert a['instructions']==b['systemInstruction']['parts'][0]['text']
    assert a['reasoning']['effort']=='none' and a['service_tier']=='fast' and not a['store']
    assert b['generationConfig']['thinkingConfig']['thinkingLevel']=='MINIMAL'
    assert 'tools' not in a and 'tools' not in b
    assert len([c for c in a['input'][0]['content'] if c['type']=='input_image'])==len(prepared.images())
    with pytest.raises(PermissionError):
        GroundedCloudReader(GeminiConfig(),RequestBudget(1,'1'),[],provider='gemini',transport=fake).payload(prepared)


def test_gemini_config_reserves_paid_full_context_even_if_free_tier_listed():
    assert GeminiConfig().reserve_usd==Decimal('.3171328')
    assert GeminiConfig().cost(1000,100)==Decimal('.00055')
    with pytest.raises(ValueError):replace(GeminiConfig(),model='gemini-latest')
    with pytest.raises(ValueError):replace(GeminiConfig(),input_usd_per_million='0')


def test_gemini_normalization_counts_thinking_and_never_logs_error_body(monkeypatch,tmp_path):
    from bjlab.research_budget import PersistentRequestBudget
    path=tmp_path/'ledger.json'
    ledger=PersistentRequestBudget.initialize(path,authorization_id='contract',max_requests=1,max_usd='1')
    monkeypatch.setattr('bjlab.grounded_cloud.CANONICAL_LEDGER',path)
    monkeypatch.setattr('bjlab.grounded_cloud.require_inference_authorization',lambda epoch:epoch)
    transport=GeminiTransport(authorization_epoch='contract',budget=ledger,api_key='fictional-not-a-credential')
    async def response(*args):
        return {'modelVersion':'gemini-3.5-flash-lite','usageMetadata':{'promptTokenCount':1000,'candidatesTokenCount':100,'thoughtsTokenCount':12},
            'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'private thought','thought':True},{'text':grounded().model_dump_json()}]}}]}
    monkeypatch.setattr(transport,'_request',response)
    identifier=ledger.reserve(Decimal('.3171328'))
    result=transport.post({},.2,reservation_id=identifier)
    assert result['usage']=={'input_tokens':1000,'output_tokens':112}
    assert len(result['output'][0]['content'])==1 and 'private thought' not in json.dumps(result['output'])
    with pytest.raises(PermissionError):transport.post({},.2,reservation_id=identifier)


def test_real_gemini_transport_refuses_memory_budget_before_network(monkeypatch):
    monkeypatch.setattr('bjlab.grounded_cloud.require_inference_authorization',lambda epoch:epoch)
    transport=GeminiTransport(authorization_epoch='contract',budget=RequestBudget(1,'1'),api_key='fictional-not-a-credential')
    with pytest.raises(PermissionError,match='canonical_persistent_budget'):transport.post({},.2)


def test_cloud_validation_failure_records_only_locations_not_inputs():
    class Transport:
        def post(self,*args):return {'model':'gpt-6-luna','status':'completed','usage':{'input_tokens':100,'output_tokens':80},
            'output':[{'type':'message','content':[{'type':'output_text','text':'{"private":"secret-like text"}'}]}]}
    prepared=frame();value=GroundedCloudReader(config(fast=True),RequestBudget(1,'1'),
        {sha256(p).hexdigest() for _,p in prepared.images()},provider='openai',transport=Transport()).read(prepared)
    assert value.status=='error' and value.diagnostics['validation_issues']
    assert 'secret-like text' not in json.dumps(value.diagnostics)
    assert all(set(e)=={'location','type'} for e in value.diagnostics['validation_issues'])


def test_unknown_returned_model_retains_reservation_and_stops():
    class Transport:
        def post(self,*args):return {'model':'unpriced-model','status':'completed','usage':{'input_tokens':1,'output_tokens':1}}
    prepared=frame();ledger=RequestBudget(1,'1')
    result=GroundedCloudReader(config(fast=True),ledger,{sha256(p).hexdigest() for _,p in prepared.images()},provider='openai',transport=Transport()).read(prepared)
    assert result.status=='error' and ledger.stopped and ledger.reserved==config(fast=True).reserve_usd


def test_continuous_same_pixels_revalidate_without_refreshing_original_deadline():
    value=CurrentEvidence();prepared=frame();stamp=value.capture(prepared,source='one',table='one',capture_ns=1_000_000_000)
    for tick in range(1,30):value.capture(prepared,source='one',table='one',capture_ns=1_000_000_000+tick*100_000_000)
    assert value.revalidate(stamp,now_ns=3_950_000_000)['valid']
    expired=value.revalidate(stamp,now_ns=4_100_000_000)
    assert not expired['valid'] and 'original_evidence_deadline_expired' in expired['reasons']


@pytest.mark.parametrize('mode',['changed','changed_back','source','table','gap','disconnect'])
def test_late_response_never_survives_a_change_even_when_pixels_return(mode):
    value=CurrentEvidence();prepared=frame();stamp=value.capture(prepared,source='one',table='one',capture_ns=1_000_000_000)
    if mode=='disconnect':value.disconnect()
    elif mode=='gap':value.capture(prepared,source='one',table='one',capture_ns=1_300_000_000)
    else:
        changed=replace(prepared,table_png=b'different-test-native-pixels',frame_id='changed')
        value.capture(changed if mode in ('changed','changed_back') else prepared,
            source='two' if mode=='source' else 'one',table='two' if mode=='table' else 'one',capture_ns=1_100_000_000)
        if mode=='changed_back':value.capture(prepared,source='one',table='one',capture_ns=1_200_000_000)
    assert not value.revalidate(stamp,now_ns=1_300_000_000)['valid']


def test_revalidation_rejects_stale_latest_capture_and_clock_regression():
    value=CurrentEvidence();prepared=frame();stamp=value.capture(prepared,source='one',table='one',capture_ns=1_000_000_000)
    assert not value.revalidate(stamp,now_ns=1_251_000_000)['valid']
    with pytest.raises(ValueError):value.capture(prepared,source='one',table='one',capture_ns=900_000_000)


def test_fallback_routes_on_local_gate_not_oracle_or_known_suit():
    from bjlab.grounded_state import GroundedResult
    prepared=frame();value=CurrentEvidence();value.capture(prepared,source='one',table='one')
    class Reader:
        name='mock-local'
        def read(self,f):return GroundedResult(f.frame_id,self.name,'completed',grounded(),1,{})
    class Never:
        def read(self,f):raise AssertionError('Accepted local must never be replaced using evaluator truth.')
    row=hybrid_attempt(value,Reader(),Never())
    assert row['route']=='local' and row['presented'] and not row['r2_certified']


def test_visibility_proxy_checks_alternate_index_not_only_top_corner():
    family=PARTITIONS['development']
    stage={'phase':'player','controls':['hit','stand'],'cards':[
        {'id':'d','zone':'dealer','rank':'7','suit':'C'},
        {'id':'p0','zone':'player:0','rank':'10','suit':'D'},
        {'id':'p1','zone':'player:0','rank':'8','suit':'C'}]}
    _,truth,evidence=render(stage,'clipping-alt-index',family)
    player=next(c for c in truth['cards'] if c['zone']=='player:0')
    part=next(c for c in evidence if c['physical_instance']=='p0')
    assert part['glyph_fractions']['top_rank']<.97 and part['glyph_fractions']['bottom_rank']>=.97
    assert player['rank']=='10'
    _,popup,detail=render(stage,'popup-unreadable',family)
    assert popup['cards'][1]['visibility']=='unreadable' and popup['cards'][1]['rank'] is None


def test_holdout_guard_runs_before_reading_any_manifest(tmp_path):
    with pytest.raises(PermissionError,match='sealed'):checked_inputs(tmp_path,'final_holdout')


def test_generated_suits_are_distinct_glyphs_not_font_fallback_boxes():
    glyphs=[card_tile({'rank':'7','suit':s},PARTITIONS['validation'][2],'white')[1]['pip'].tobytes() for s in SUITS]
    assert len(set(glyphs))==4


def test_model_failure_and_unexecuted_input_are_not_hidden_from_coverage():
    expected=grounded().model_dump();record={'id':'one','condition':'clean','split':'validation'}
    rows=[score(record, __import__('bjlab.grounded_state',fromlist=['GroundedResult']).GroundedResult('f','mock',s,None,t,{}),expected)
          for s,t in [('timeout',3000),('not_executed',0)]]
    result=summaries(rows)['mock']
    assert result['planned_inputs']==2 and result['attempted_inputs']==1
    assert result['statuses']=={'timeout':1,'not_executed':1}
    assert result['completed_latency_ms']['p95'] is None
    assert result['metrics']['correct_usable_rank_state']==0 and result['metrics']['player_opportunity']==2


@pytest.mark.parametrize('change',[False,True])
def test_capture_producer_continues_during_slow_cloud_and_rejects_changed_pixels(change):
    """Actual concurrent producer + injected transport; no API-quality claim."""
    import threading
    import time
    from bjlab.grounded_state import GroundedResult
    evidence=CurrentEvidence();prepared=frame();done=threading.Event();ready=threading.Event()
    started=time.monotonic()
    def capture():
        while not done.is_set():
            pixels=replace(prepared,table_png=b'changed-native-test-pixels') if change and time.monotonic()-started>.08 else prepared
            evidence.capture(pixels,source='contract-source',table='contract-table')
            ready.set();done.wait(.02)
    class Local:
        name='mock-local'
        def read(self,f):return GroundedResult(f.frame_id,self.name,'completed',grounded(phase='unknown'),1,{})
    class SlowCloud:
        name='mock-cloud'
        def read(self,f):
            time.sleep(.2)
            return GroundedResult(f.frame_id,self.name,'completed',grounded(),200,{'contract_mock':True})
    producer=threading.Thread(target=capture,daemon=True);producer.start()
    try:
        assert ready.wait(2)
        row=hybrid_attempt(evidence,Local(),SlowCloud())
        assert row['route']=='fallback' and row['diagnostics']['contract_mock']
        assert row['revalidation']['latest_sequence']>=5
        assert row['presented'] is (not change)
        if change:
            assert row['advice'] is None and 'pixels_or_continuity_changed' in row['revalidation']['reasons']
    finally:
        done.set();producer.join(2);evidence.disconnect()


def test_gemini_error_diagnostic_cannot_expose_echoed_secret_or_private_body():
    from bjlab.grounded_cloud import GeminiHTTPError
    error=GeminiHTTPError(400,json.dumps({'error':{'message':'Unknown name sk-fictional-secret at responseFormat'}}).encode())
    assert error.category=='unsupported_request_field'
    assert 'sk-fictional-secret' not in str(error) and not hasattr(error,'private_body')


def test_usage_reconciliation_requires_all_frozen_requests_and_audited_models():
    from validation.tools.reconcile_api_usage import EXPECTED,verified_groups
    rows=[{'model':model,'service_tier':tier,'num_model_requests':str(count),'batch':'false',
           'input_tokens':'100','output_tokens':'50'} for (model,tier),count in EXPECTED.items()]
    assert sum(v[0] for v in verified_groups(rows).values())==69
    with pytest.raises(ValueError,match='exactly'):verified_groups(rows[:-1])
    rows[0]['num_model_requests']='50'
    with pytest.raises(ValueError,match='exactly'):verified_groups(rows)
    rows[0].update(model='unpriced-model')
    with pytest.raises(ValueError,match='Unexpected'):verified_groups(rows)
