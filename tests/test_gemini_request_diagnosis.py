"""Local contract/preflight tests, never recorded as provider evidence."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from bjlab.live_state import LiveObservation
from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_cloud import DiagnosticReader
from bjlab.openai_reader import RequestBudget
from tests.test_live_reader import observed, frame
from hashlib import sha256
from validation.tools.gemini_request_diagnosis import openapi_schema
from validation.tools.live_reader_diagnosis import rest_errors


def test_legacy_schema_keeps_nullable_unknowns_roles_and_cardinality():
    schema=openapi_schema()
    card=schema['properties']['c']['items']
    assert schema['required']==['c','t','p','a','n','b']
    assert schema['properties']['c']['maxItems']=='52'
    assert card['properties']['r']['nullable'] is True
    assert card['properties']['s']['nullable'] is True
    assert card['properties']['v']['enum']==['readable','partial','covered','unreadable']
    number=schema['properties']['n']['items']
    assert number['required']==['v','r','l','w']
    assert number['properties']['l']['nullable'] is True
    assert number['properties']['r']['enum']==['player_total','dealer_total','ui','unknown']
    assert '$ref' not in json.dumps(schema) and 'additionalProperties' not in json.dumps(schema)


def test_legacy_wire_limitation_does_not_weaken_local_integrity():
    value=observed().model_dump(by_alias=True)
    value['n']=[{'v':20,'r':'dealer_total','l':'SESSION','w':'table'}]
    with pytest.raises(ValidationError):LiveObservation.model_validate(value)
    value=observed().model_dump(by_alias=True)
    value['c'][-1]['r']='A'
    with pytest.raises(ValidationError):LiveObservation.model_validate(value)
    value=observed().model_dump(by_alias=True);value['nonsense']='ignored?'
    with pytest.raises(ValidationError):LiveObservation.model_validate(value)


def test_rest_linter_checks_dynamic_maps_instead_of_rejecting_property_names():
    discovery={'schemas':{'Schema':{'type':'object','properties':{
        'type':{'type':'string','enum':['OBJECT','STRING']},
        'properties':{'type':'object','additionalProperties':{'$ref':'Schema'}}}}}}
    value={'type':'OBJECT','properties':{'my_field':{'type':'STRING'}}}
    assert rest_errors(value,{'$ref':'Schema'},discovery)==[]
    bad=deepcopy(value);bad['properties']['my_field']['type']='WRONG'
    assert rest_errors(bad,{'$ref':'Schema'},discovery)==['request.properties.my_field.type:invalid_string_or_enum']
    bad=deepcopy(value);bad['additionalProperties']=False
    assert rest_errors(bad,{'$ref':'Schema'},discovery)==['request.additionalProperties:unknown_field']


def json_reader(transport):
    f=frame();allowed={sha256(p).hexdigest() for _,p in f.images()}
    return f,DiagnosticReader(GeminiConfig(),RequestBudget(1,1),allowed,provider='gemini',
        variant='live',transport=transport,gemini_output='json-mode')


def test_json_mode_requires_local_contract_and_does_not_change_frozen_mode():
    f,reader=json_reader(object());payload=reader.payload(f)
    cfg=payload['generationConfig']
    assert cfg=={'maxOutputTokens':1024,'responseMimeType':'application/json'}
    assert len(payload['systemInstruction']['parts'])==2
    assert '"$defs"' in payload['systemInstruction']['parts'][1]['text']
    old=DiagnosticReader(GeminiConfig(),reader.budget,reader.hashes,provider='gemini',variant='live',transport=object()).payload(f)
    assert old['generationConfig']['responseFormat']['text']['mimeType']=='APPLICATION_JSON'
    assert payload['contents']==old['contents']
    with pytest.raises(ValueError):DiagnosticReader(GeminiConfig(),reader.budget,reader.hashes,
        provider='openai',variant='live',transport=object(),gemini_output='json-mode')


@pytest.mark.parametrize('invalid', ['extra_field','invented_total','covered_rank','malformed_json'])
def test_json_mode_rejects_invalid_provider_json_without_advice(invalid):
    value=observed().model_dump(by_alias=True)
    if invalid=='extra_field':value['confidence']=1
    if invalid=='invented_total':value['n']=[{'v':20,'r':'dealer_total','l':'SESSION','w':'table'}]
    if invalid=='covered_rank':value['c'][-1]['r']='A'
    text='{broken' if invalid=='malformed_json' else json.dumps(value)
    class Reply:
        def post(self,payload,timeout):
            return {'model':'gemini-3.5-flash-lite','status':'completed','service_tier':'default',
                'usage':{'input_tokens':100,'output_tokens':90},
                'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}
    f,reader=json_reader(Reply());result=reader.read(f)
    assert result.status=='error' and result.observation is None
    assert result.diagnostics['schema_enforcement']=='strict_local_validation'
    assert result.diagnostics['validation_issues']


def test_json_mode_discard_late_valid_reply_preserves_three_second_contract():
    from dataclasses import replace
    import time
    class Reply:
        def post(self,payload,timeout):
            time.sleep(.03)
            return {'model':'gemini-3.5-flash-lite','status':'completed','service_tier':'default',
                'usage':{'input_tokens':100,'output_tokens':90},
                'output':[{'type':'message','content':[{'type':'output_text','text':observed().model_dump_json(by_alias=True)}]}]}
    f,reader=json_reader(Reply());reader.config=replace(reader.config,timeout_seconds=.01)
    result=reader.read(f)
    assert result.status=='timeout' and result.observation is None
    assert result.diagnostics['late_complete_json_discarded']
    assert GeminiConfig().timeout_seconds==3
