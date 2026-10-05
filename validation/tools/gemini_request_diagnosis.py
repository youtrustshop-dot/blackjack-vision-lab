"""VISION-019 request isolation, not a performance or final-holdout benchmark.

Every generation consumes the existing lifetime ledger. Each named probe is
one-shot, with no retry. Ten-second offline diagnosis never relaxes live's 3s
deadline. Private observations remain under artifacts; no raw error is saved.
"""
import argparse
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import time

from bjlab.api_access_policy import MATRIX, require_inference_authorization
from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_cloud import DiagnosticReader, DiagnosticHTTPError, MeasuredGeminiTransport
from bjlab.live_state import LiveObservation, wire_schema
from bjlab.openai_reader import ProviderHTTPError
from validation.tools.api_reader_tournament import ROOT, budget, file_hash
from validation.tools.live_reader_diagnosis import row
from validation.tools.state_reader_comparison import load_frame

EPOCH = '2026-10-05-gemini-request-isolation-eur10'
PROBES = ('minimal-text', 'compatibility-image', 'json-mode-image')
SOURCE = ROOT/'artifacts/live-reader-diagnosis-20261005-authorized/development'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def owned_input():
    records = json.loads((SOURCE/'frames.json').read_text())
    record = next(r for r in records if r['id']=='labelled-totals')
    if record['split']!='development' or record['evidence_kind']!='new-owned-synthetic-live-v3':
        raise PermissionError('Only already reviewed owned development pixels are allowed.')
    for image in record['images']:
        if file_hash(SOURCE/image['file'])!=image['sha256']:
            raise PermissionError('Native reviewed pixels changed.')
    frame = load_frame(SOURCE,record)
    allowed = {image['sha256'] for image in record['images']}
    return record, frame, allowed


def openapi_schema():
    """Same contract as wire_schema, encoded in Gemini's OpenAPI subset.

    Inline acyclic refs and encode nullable scalar enums with nullable:true.
    Recognition/provenance fields and local strict validation remain identical.
    The legacy Schema cannot express additionalProperties:false; strict local
    parsing still rejects extra fields. Its int64 cardinalities are JSON strings.
    """
    schema = wire_schema(); definitions = schema.get('$defs',{})
    def convert(node):
        if isinstance(node,list): return [convert(n) for n in node]
        if not isinstance(node,dict): return node
        if '$ref' in node:
            return convert(definitions[node['$ref'].removeprefix('#/$defs/')])
        if 'anyOf' in node:
            nonnull=[n for n in node['anyOf'] if n.get('type')!='null']
            if len(nonnull)!=1 or len(node['anyOf'])!=2:
                raise ValueError('Only nullable scalars are supported by this exact contract.')
            return {**convert(nonnull[0]),'nullable':True}
        value={k:convert(v) for k,v in node.items() if k not in ('$defs','additionalProperties')}
        if 'type' in value: value['type']=value['type'].upper()
        for key in ('minItems','maxItems','minProperties','maxProperties','minLength','maxLength'):
            if key in value: value[key]=str(value[key])
        return value
    return convert(schema)


def payload_for(probe):
    if probe=='minimal-text':
        return {'contents':[{'role':'user','parts':[{'text':'Reply with exactly OK.'}]}],
                'generationConfig':{'maxOutputTokens':64}}, None
    record,frame,allowed=owned_input()
    if probe=='json-mode-image':
        payload=DiagnosticReader(GeminiConfig(),None,allowed,provider='gemini',variant='live',
            transport=object(),gemini_output='json-mode').payload(frame)
        return payload,(record,frame)
    payload=DiagnosticReader(GeminiConfig(),None,allowed,provider='gemini',variant='live',transport=object()).payload(frame)
    payload['generationConfig']={'maxOutputTokens':1024,
        'responseMimeType':'application/json','responseSchema':openapi_schema()}
    return payload,(record,frame)


def execute(probe,output):
    if probe not in PROBES: raise ValueError('Only predeclared isolation probes are allowed.')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    if (output/(probe+'.json')).exists() or (output/(probe+'-claim.json')).exists():
        raise PermissionError('This probe has already been attempted; no retry.')
    if probe!='minimal-text':
        prior=json.loads((output/'minimal-text.json').read_text())
        if prior['status']!='completed' or not prior['expected_text_correct']:
            raise PermissionError('Minimal generation must succeed before image diagnosis.')
    if probe=='json-mode-image':
        prior=json.loads((output/'compatibility-image.json').read_text())
        if prior.get('http_status')!=400:
            raise PermissionError('This control is only declared for the structured HTTP400 failure.')
    ceiling=budget(); before=ceiling.receipt()
    if before['requests_attempted']>=90: raise PermissionError('Lifetime request cap exhausted.')
    payload,owned=payload_for(probe)
    config=GeminiConfig(max_output_tokens=64 if probe=='minimal-text' else 1024)
    # Offline diagnosis can observe acceptance/validation up to 10s, but it can
    # never feed an advisor or present a late reply as a live success.
    timeout=10.
    digest=sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    claim={'probe':probe,'payload_sha256':digest,'config':asdict(config),
        'diagnostic_deadline_ms':10000,'unchanged_live_deadline_ms':3000,
        'source_sha256':file_hash(__file__),'budget_before':before,
        'images':[] if owned is None else owned[0]['images'],'retry_count':0,
        'scope':'request isolation on reused development, not independent accuracy evidence'}
    with (output/(probe+'-claim.json')).open('x',encoding='utf-8') as handle:
        json.dump(claim,handle,indent=2)
    policy=json.loads(MATRIX.read_text(encoding='utf-8'))
    saved=policy['api_access_policy'].copy()
    policy['api_access_policy'].update(inference_authorized=True,authorization_epoch=EPOCH,
        max_requests=90-before['requests_attempted'],max_usd=str(Decimal('8')-Decimal(before['accounted_upper_usd'])),
        reason='Latest explicit user request: bounded Gemini request diagnosis, same lifetime cap')
    write(MATRIX,policy)
    result={'probe':probe,'status':'error','diagnostic_only':True,'advisor_presented':False,
        'raw_error_saved':False,'retry_count':0,'expected_text_correct':False}
    started=time.perf_counter()
    try:
        require_inference_authorization(EPOCH)
        transport=MeasuredGeminiTransport(authorization_epoch=EPOCH,budget=ceiling)
        reservation=ceiling.reserve(config.reserve_usd)
        response=transport.post(payload,timeout,reservation_id=reservation)
        usage=response.get('usage') or {}; inputs=usage.get('input_tokens'); outputs=usage.get('output_tokens')
        returned=response.get('model','')
        if (type(inputs) is not int or type(outputs) is not int or inputs<0 or outputs<0 or
                inputs>config.context_token_limit or outputs>config.max_output_tokens or
                not isinstance(returned,str) or not (returned==config.model or returned.startswith(config.model+'-'))):
            result['unreconciled_usage']=True
            raise ValueError('Unaudited model/usage; retain worst-case reservation.')
        cost=config.cost(inputs,outputs); ceiling.settle(reservation,cost)
        result.update(model_returned=returned,usage=usage,reported_usage_upper_usd=str(cost),
            provider_finish_reason=response.get('provider_finish_reason'))
        texts=[p['text'] for o in response.get('output',[]) if o.get('type')=='message'
            for p in o.get('content',[]) if p.get('type')=='output_text']
        if response.get('status')!='completed' or len(texts)!=1:
            result['status']='incomplete'
        elif probe=='minimal-text':
            result.update(status='completed',expected_text_correct=texts[0].strip()=='OK')
        else:
            observation=LiveObservation.model_validate_json(texts[0])
            result.update(status='completed',observation=observation.model_dump(),
                validated_json=True,output_json_bytes=len(texts[0].encode()))
            from bjlab.grounded_state import GroundedResult
            truth=json.loads((SOURCE/'oracle.json').read_text())[owned[0]['id']]
            measured=GroundedResult(owned[1].frame_id,'gemini-lite-live','completed',observation,
                (time.perf_counter()-started)*1000,{})
            result['development_metrics']=row(owned[0],measured,truth)
        result['network_timing']=transport.timings
    except Exception as exc:
        result['status']='timeout' if isinstance(exc,TimeoutError) or 'timeout' in type(exc).__name__.lower() else 'error'
        result['error_type']=type(exc).__name__
        if isinstance(exc,ProviderHTTPError):result['http_status']=exc.status_code
        if isinstance(exc,DiagnosticHTTPError):result['provider_error']=exc.safe_diagnostic
    finally:
        result['elapsed_ms']=(time.perf_counter()-started)*1000
        result['within_live_deadline']=owned is not None and result['status']=='completed' and result['elapsed_ms']<=3000
        result['budget_after']=ceiling.receipt()
        write(output/(probe+'.json'),result)
        policy=json.loads(MATRIX.read_text(encoding='utf-8'));policy['api_access_policy']=saved
        write(MATRIX,policy)
    return {k:v for k,v in result.items() if k not in ('observation','development_metrics')}


def summarize(output):
    """Pure local replay/public aggregation; never loads a key or submits."""
    output=Path(output)
    values=[json.loads((output/(p+'.json')).read_text()) for p in PROBES]
    rows=[]
    for value in values:
        probe=value['probe'];claim=json.loads((output/(probe+'-claim.json')).read_text())
        payload,_=payload_for(probe)
        matches=sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()==claim['payload_sha256']
        if not matches:raise ValueError('Final research payload differs from executed probe.')
        metrics=value.get('development_metrics') or {}
        row={k:value.get(k) for k in ('probe','status','elapsed_ms','http_status','provider_error',
            'usage','reported_usage_upper_usd','validated_json','output_json_bytes','network_timing') if k in value}
        row['payload_matches_executed_probe']=matches
        if value.get('observation'):
            observed=LiveObservation.model_validate(value['observation'])
            row.update(visible_faces=len([c for c in observed.cards if c.visibility!='covered']),
                backs=len([c for c in observed.cards if c.visibility=='covered']),
                visible_numbers=len(observed.numbers),
                metrics={k:metrics.get(k) for k in ('inventory_exact','rank_presence_exact','phase_correct',
                    'controls_correct','numeric_roles_exact','complete_grounded_state','correct_usable_r1',
                    'false_accepted_state')})
        rows.append(row)
    before=json.loads((output/'minimal-text-claim.json').read_text())['budget_before']
    after=values[-1]['budget_after']
    return {'experiment_id':'VISION-019','parent_commit':'7717ec222436b47d45d5520ce67091f0e66c38ab',
        'model':'gemini-3.5-flash-lite','api_submissions':3,'rows':rows,
        'diagnosis':'Minimal generation and identical native images work; configured full structured hand schemas are rejected. Exact offending constraint/server reason remains unknown.',
        'workaround':'Explicit json-mode variant: application/json output + unchanged hand schema in prompt, strict local validation.',
        'successful_image_cases':1,'independent_verification_sessions':0,
        'sample_scope':'One reused owned development still, four identical native views; not generalization or live hybrid evidence.',
        'diagnostic_network_deadline_ms':10000,'unchanged_reader_deadline_ms':3000,
        'latency_p50_p95':None,'invoice_charge':None,
        'new_reported_usage_upper_usd':str(sum((Decimal(v.get('reported_usage_upper_usd','0')) for v in values),Decimal(0))),
        'new_accounted_upper_including_uncertain_usd':str(Decimal(after['accounted_upper_usd'])-Decimal(before['accounted_upper_usd'])),
        'budget_before':before,'budget_after':after,'runtime_inference_authorized':False,
        'final_holdout':'not_opened','reader_promoted':False,'installed_release_changed':False,
        'not_tested':['Fresh session-disjoint verification','Provider transfer','Actual local-first hybrid',
            'Native advisor capture-to-paint','Final holdout','Exact single schema-constraint rejection cause'],
        'source_hashes':{p:file_hash(ROOT/p) for p in ('bjlab/live_cloud.py','bjlab/live_state.py',
            'validation/tools/live_reader_diagnosis.py','validation/tools/gemini_request_diagnosis.py')}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe',choices=PROBES+('replay',));parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(summarize(args.output) if args.probe=='replay' else execute(args.probe,args.output),indent=2))
