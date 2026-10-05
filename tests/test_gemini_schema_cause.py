"""Offline causal controls, not provider evidence."""
from copy import deepcopy

from bjlab.live_state import LiveObservation, wire_schema
from validation.tools.gemini_schema_cause import BOUND_PATHS, differences, payload_for, schema_for
from tests.test_r1_readers import frame


def test_single_constraint_ablations_are_one_pointer_and_preserve_baseline():
    baseline=wire_schema(); frozen=deepcopy(baseline)
    for i,path in enumerate(BOUND_PATHS):
        changed=schema_for('full-minus-bound-'+str(i))
        assert differences(baseline,changed)==[{'pointer':path,'operation':'remove',
            'before':52 if i==0 else 5 if i in (1,3) else 12 if i==2 else 0 if i==4 else 1_000_000}]
    assert wire_schema()==frozen==schema_for('full')==schema_for('full-rechallenge')
    assert {d['pointer'] for d in differences(baseline,schema_for('full-no-bounds'))}==set(BOUND_PATHS)
    assert len(differences(baseline,schema_for('full-only-card-bound')))==5


def test_format_controls_keep_images_prompt_model_settings_identical(monkeypatch):
    prepared=frame();record={'id':'offline-contract'}
    from hashlib import sha256
    monkeypatch.setattr('validation.tools.gemini_schema_cause.owned_input',
        lambda:(record,prepared,{sha256(p).hexdigest() for _,p in prepared.images()}))
    original,_,_=payload_for('tiny')
    changed,_,_=payload_for('tiny-lowercase')
    assert differences(original,changed)==[{'pointer':'/generationConfig/responseFormat/text/mimeType',
        'operation':'replace','before':'APPLICATION_JSON','after':'application/json'}]
    legacy,_,_=payload_for('tiny-legacy-json')
    assert legacy['contents']==original['contents'] and legacy['systemInstruction']==original['systemInstruction']
    assert legacy['generationConfig']['thinkingConfig']==original['generationConfig']['thinkingConfig']
    assert legacy['generationConfig']['responseJsonSchema']==schema_for('tiny')


def test_wire_ablation_does_not_relax_local_integer_or_card_validation():
    from pydantic import ValidationError
    import pytest
    assert 'maximum' not in schema_for('full-minus-bound-5')['$defs']['LiveNumber']['properties']['v']
    value={'c':[],'t':'empty','p':'waiting','a':[],'n':[{'v':1_000_001,'r':'ui','l':None,'w':'table'}],'b':[]}
    with pytest.raises(ValidationError): LiveObservation.model_validate(value)


def test_opt_in_structured_fix_is_exactly_one_constraint_not_an_output_contract_change():
    from bjlab.live_state import gemini_structured_schema
    assert gemini_structured_schema()==schema_for('full-minus-bound-0')
    assert differences(wire_schema(),gemini_structured_schema())==[
        {'pointer':'/properties/c/maxItems','operation':'remove','before':52}]


def test_structured_fix_never_accepts_more_than_fifty_two_cards():
    import json
    from hashlib import sha256
    from bjlab.grounded_cloud import GeminiConfig
    from bjlab.live_cloud import DiagnosticReader
    from bjlab.openai_reader import RequestBudget
    from tests.test_live_reader import frame, observed
    value=observed().model_dump(by_alias=True)
    value['c']=[value['c'][0]]*53
    class Reply:
        def post(self,payload,timeout):
            return {'model':'gemini-3.5-flash-lite','status':'completed','usage':{'input_tokens':100,'output_tokens':100},
                'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
    prepared=frame(); hashes={sha256(p).hexdigest() for _,p in prepared.images()}
    reader=DiagnosticReader(GeminiConfig(),RequestBudget(1,1),hashes,provider='gemini',variant='live',
        transport=Reply(),gemini_output='structured-card-limit-local')
    baseline=DiagnosticReader(reader.config,reader.budget,hashes,provider='gemini',variant='live',transport=object())
    assert differences(baseline.payload(prepared),reader.payload(prepared))==[
        {'pointer':'/generationConfig/responseFormat/text/schema/properties/c/maxItems','operation':'remove','before':52}]
    result=reader.read(prepared)
    assert result.observation is None and result.status=='error'
    assert result.diagnostics['local_card_count_limit']==52
    assert result.diagnostics['validation_issues'][0]['type']=='too_long'
