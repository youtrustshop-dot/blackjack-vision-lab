"""VISION-020 bounded causal schema ablations on one reused owned dev still.

No performance/promotion claim, oracle in prompt, retry, billing action or new
monetary allowance. Deliberate reintroduction is a named causal control.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from pydantic import ValidationError

from bjlab.api_access_policy import MATRIX
from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_cloud import DiagnosticReader, DiagnosticHTTPError, MeasuredGeminiTransport
from bjlab.live_state import LiveObservation, wire_schema
from bjlab.openai_reader import ProviderHTTPError
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from validation.tools.api_reader_tournament import ROOT, file_hash
from validation.tools.gemini_request_diagnosis import owned_input, write

EPOCH = '2026-10-05-exact-gemini-schema-cause-eur10'
AUTHORIZATION_ID = 'card-lab-eur10-total-20261004'
MAX_NEW = 12
NEW_CEILING = 102
NOTE = 'User explicitly requests the exact Gemini HTTP400 culprit; at most twelve causal probes, unchanged USD8 aggregate monetary cap.'
BOUND_PATHS = ('/properties/c/maxItems', '/properties/a/maxItems', '/properties/n/maxItems',
               '/properties/b/maxItems', '/$defs/LiveNumber/properties/v/minimum',
               '/$defs/LiveNumber/properties/v/maximum')
PROBES = ('tiny', 'full', 'full-rechallenge', 'tiny-rechallenge',
    'tiny-lowercase', 'full-lowercase', 'tiny-legacy-json', 'full-legacy-json',
    'full-no-bounds', 'full-no-array-bounds', 'full-no-numeric-bounds',
    'full-only-card-bound', 'full-inline', 'full-nullable-types', 'full-no-extra-strict') + tuple(
        'full-minus-bound-'+str(i) for i in range(len(BOUND_PATHS)))
TINY = {'type':'object','properties':{'ok':{'type':'boolean'}},
        'required':['ok'],'additionalProperties':False}
SOURCE_FILES = ('validation/tools/gemini_schema_cause.py','bjlab/research_budget.py',
                'bjlab/live_cloud.py','bjlab/live_state.py','bjlab/grounded_cloud.py')


def digest(value):
    return sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def differences(before, after, path=''):
    """JSON-pointer leaf changes; values may be public schema, never secrets."""
    if isinstance(before,dict) and isinstance(after,dict):
        result=[]
        for key in sorted(before.keys()|after.keys()):
            pointer=path+'/'+key.replace('~','~0').replace('/','~1')
            if key not in before: result.append({'pointer':pointer,'operation':'add','after':after[key]})
            elif key not in after: result.append({'pointer':pointer,'operation':'remove','before':before[key]})
            else: result.extend(differences(before[key],after[key],pointer))
        return result
    return [] if before==after else [{'pointer':path,'operation':'replace','before':before,'after':after}]


def remove(schema, path):
    keys=path.lstrip('/').split('/'); target=schema
    for key in keys[:-1]: target=target[key]
    target.pop(keys[-1])


def schema_for(probe):
    schema=wire_schema()
    if probe.startswith('tiny'): return deepcopy(TINY)
    if probe.startswith('full-minus-bound-'):
        remove(schema,BOUND_PATHS[int(probe.rsplit('-',1)[1])])
    elif probe=='full-no-bounds':
        for path in BOUND_PATHS: remove(schema,path)
    elif probe=='full-no-array-bounds':
        for path in BOUND_PATHS[:4]: remove(schema,path)
    elif probe=='full-no-numeric-bounds':
        for path in BOUND_PATHS[4:]: remove(schema,path)
    elif probe=='full-only-card-bound':
        for path in BOUND_PATHS[1:]: remove(schema,path)
    elif probe=='full-inline':
        definitions=schema['$defs']
        def inline(node):
            if isinstance(node,list): return [inline(n) for n in node]
            if not isinstance(node,dict): return node
            if '$ref' in node: return inline(definitions[node['$ref'].removeprefix('#/$defs/')])
            return {k:inline(v) for k,v in node.items() if k!='$defs'}
        schema=inline(schema)
    elif probe in ('full-nullable-types','full-no-extra-strict'):
        def convert(node):
            if isinstance(node,list): return [convert(n) for n in node]
            if not isinstance(node,dict): return node
            if probe=='full-nullable-types' and 'anyOf' in node:
                nonnull=next(n for n in node['anyOf'] if n.get('type')!='null')
                result=deepcopy(nonnull); result['type']=[nonnull['type'],'null']
                if 'enum' in result: result['enum'].append(None)
                return result
            return {k:convert(v) for k,v in node.items() if not (probe=='full-no-extra-strict' and k=='additionalProperties')}
        schema=convert(schema)
    return schema


def payload_for(probe):
    if probe not in PROBES: raise ValueError('Undeclared causal probe.')
    record,frame,allowed=owned_input()
    payload=DiagnosticReader(GeminiConfig(),None,allowed,provider='gemini',variant='live',transport=object()).payload(frame)
    schema=schema_for(probe)
    payload['generationConfig']['responseFormat']['text']['schema']=schema
    if probe.endswith('-lowercase'):
        payload['generationConfig']['responseFormat']['text']['mimeType']='application/json'
    elif probe.endswith('-legacy-json'):
        payload['generationConfig'].pop('responseFormat')
        payload['generationConfig'].update(responseMimeType='application/json',responseJsonSchema=schema)
    return payload,record,frame


def ceiling():
    return PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,max_requests=NEW_CEILING,max_usd='8')


def authorize(output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    if (output/'plan.json').exists(): raise PermissionError('This scope is already frozen; do not amend again.')
    old=PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,max_requests=90,max_usd='8')
    before=old.receipt()
    if before['requests_attempted']!=90 or before['stopped']:
        raise PermissionError('Expected the intact prior exhausted request ceiling.')
    _,record,_=payload_for('full')
    policy=json.loads(MATRIX.read_text(encoding='utf-8'))['api_access_policy']
    if policy.get('inference_authorized') is not False:
        raise PermissionError('Existing inference scope must be disarmed.')
    plan={'experiment_id':'VISION-020','authorization_epoch':EPOCH,'authorization_note':NOTE,
        'max_new_submissions':MAX_NEW,'unchanged_max_usd':'8','budget_before':before,
        'input_id':record['id'],'images':record['images'],'probes':PROBES,
        'strategy':'Tiny structured control, exact full recheck, single-bound ablation; adapt to format controls or bounded constraint groups. Require single-pointer rescue plus deliberate reintroduction for causal attribution.',
        'source_hashes':{p:file_hash(ROOT/p) for p in SOURCE_FILES},'diagnostic_deadline_ms':10000,
        'live_deadline_ms_unchanged':3000,'oracle_sent':False,'advisor_presented':False,
        'final_holdout':'not_opened','initial_disarmed_policy':policy}
    # Freeze intent before the audited count-only amendment. A crash never resets it.
    with (output/'plan.json').open('x',encoding='utf-8') as handle: json.dump(plan,handle,indent=2)
    amended=old.extend_request_ceiling(max_requests=NEW_CEILING,authorization_epoch=EPOCH,authorization_note=NOTE)
    return amended.receipt()


def execute(probe,output):
    output=Path(output); plan=json.loads((output/'plan.json').read_text())
    if plan['authorization_epoch']!=EPOCH or plan['max_new_submissions']!=MAX_NEW:
        raise PermissionError('Wrong bounded scope.')
    if any(file_hash(ROOT/p)!=h for p,h in plan['source_hashes'].items()):
        raise PermissionError('Executed source changed after the diagnostic plan was frozen.')
    if (output/'STOP.json').exists(): raise PermissionError('Diagnostic batch stopped; no retry.')
    if (output/(probe+'.json')).exists() or (output/(probe+'-claim.json')).exists():
        raise PermissionError('Named probe consumed; no blind retry.')
    if probe.endswith('rechallenge'):
        existing=[json.loads(p.read_text()) for p in output.glob('*.json') if p.stem in PROBES]
        prefix=probe.removesuffix('-rechallenge')
        if not any(v['probe']==prefix and v.get('http_status')==400 for v in existing) or not any(v.get('http_status')==200 for v in existing):
            raise PermissionError('Reintroduction needs an observed failing original and successful control.')
    # Load only the previously authorized ignored Gemini credential; never emit it.
    for line in (ROOT/'.env.gemini.local').read_text(encoding='utf-8-sig').splitlines():
        name,sep,value=line.partition('=')
        if sep and name.strip() in ('GEMINI_API_KEY','GOOGLE_API_KEY'):
            os.environ['GEMINI_API_KEY']=value.strip().strip('"').strip("'")
    budget=ceiling(); before=budget.receipt()
    if before['requests_attempted']-plan['budget_before']['requests_attempted']>=MAX_NEW:
        raise PermissionError('Twelve-probe operational ceiling exhausted.')
    config=GeminiConfig();payload,record,frame=payload_for(probe);reference,_,_=payload_for('full')
    if record['images']!=plan['images']: raise PermissionError('Frozen owned pixels changed.')
    config_delta=differences(reference['generationConfig'],payload['generationConfig'],'/generationConfig')
    claim={'probe':probe,'payload_sha256':digest(payload),'schema_sha256':digest(schema_for(probe)),
        'original_payload_sha256':digest(reference),'generation_config_delta':config_delta,
        'contents_sha256':digest(payload['contents']),'system_instruction_sha256':digest(payload['systemInstruction']),
        'schema':schema_for(probe),'config':asdict(config),'budget_before':before,
        'source_sha256':file_hash(__file__),'diagnostic_deadline_ms':10000,
        'unchanged_live_deadline_ms':3000,'retry_count':0}
    with (output/(probe+'-claim.json')).open('x',encoding='utf-8') as handle: json.dump(claim,handle,indent=2)
    policy=json.loads(MATRIX.read_text(encoding='utf-8'));saved=policy['api_access_policy'].copy()
    policy['api_access_policy'].update(inference_authorized=True,authorization_epoch=EPOCH,
        max_requests=NEW_CEILING-before['requests_attempted'],
        max_usd=str(Decimal('8')-Decimal(before['accounted_upper_usd'])),reason=NOTE)
    write(MATRIX,policy)
    result={'probe':probe,'status':'error','diagnostic_only':True,'advisor_presented':False,
        'retry_count':0,'raw_error_saved':False,'generation_config_delta':config_delta}
    started=time.perf_counter();transport=None
    try:
        transport=MeasuredGeminiTransport(authorization_epoch=EPOCH,budget=budget)
        reservation=budget.reserve(config.reserve_usd)
        response=transport.post(payload,10.,reservation_id=reservation)
        result['http_status']=200
        usage=response.get('usage') or {};inputs=usage.get('input_tokens');outputs=usage.get('output_tokens')
        model=response.get('model','')
        if (type(inputs) is not int or type(outputs) is not int or inputs<0 or outputs<0 or
                inputs>config.context_token_limit or outputs>config.max_output_tokens or
                not isinstance(model,str) or not (model==config.model or model.startswith(config.model+'-'))):
            result['unreconciled_usage']=True
            raise ValueError('Unaudited usage; retain reservation and stop batch.')
        cost=config.cost(inputs,outputs);budget.settle(reservation,cost)
        result.update(model_returned=model,usage=usage,reported_usage_upper_usd=str(cost),
            provider_finish_reason=response.get('provider_finish_reason'),status='accepted')
        texts=[p['text'] for o in response.get('output',[]) if o.get('type')=='message'
            for p in o.get('content',[]) if p.get('type')=='output_text']
        if response.get('status')=='completed' and len(texts)==1:
            try:
                observation=LiveObservation.model_validate_json(texts[0])
                result.update(validated_full_contract=True,observation=observation.model_dump())
            except ValidationError:
                result['validated_full_contract']=False
            result['output_json_bytes']=len(texts[0].encode())
    except Exception as exc:
        result['status']='timeout' if isinstance(exc,TimeoutError) or 'timeout' in type(exc).__name__.lower() else 'error'
        result['error_type']=type(exc).__name__
        if isinstance(exc,ProviderHTTPError):result['http_status']=exc.status_code
        if isinstance(exc,DiagnosticHTTPError):result['provider_error']=exc.safe_diagnostic
        if result.get('http_status')!=400:
            write(output/'STOP.json',{'reason':'Non-schema failure or unaudited response; no automatic retry.','probe':probe})
    finally:
        result['elapsed_ms']=(time.perf_counter()-started)*1000
        result['network_timing']=getattr(transport,'timings',{})
        result['budget_after']=budget.receipt()
        write(output/(probe+'.json'),result)
        policy=json.loads(MATRIX.read_text(encoding='utf-8'));policy['api_access_policy']=saved
        write(MATRIX,policy)
    return {k:v for k,v in result.items() if k not in ('observation','generation_config_delta')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe',choices=('authorize',)+PROBES)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(authorize(args.output) if args.probe=='authorize' else execute(args.probe,args.output),indent=2))
