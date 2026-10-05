"""Limited VISION-018: request audit, paired schema timing, conditional hybrid.

Owned new development sessions only. No final holdout, training, provider assets,
release change or automatic retry. Twelve still requests plus at most four
hybrid requests share the unchanged lifetime USD8/90 ledger.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import threading
import time

import numpy as np
from PIL import Image

from bjlab.api_access_policy import require_inference_authorization
from bjlab.grounded_cloud import GeminiConfig, PROMPT as V2_PROMPT
from bjlab.grounded_state import grounded_gate
from bjlab.hybrid_evidence import CurrentEvidence, FrozenGroundedLocal, hybrid_attempt
from bjlab.live_cloud import DiagnosticReader, MeasuredResponsesTransport, MeasuredGeminiTransport, PROMPT
from bjlab.live_state import CONTRACT_VERSION, live_gate, wire_schema
from bjlab.openai_reader import PROMPT as V1_PROMPT
from bjlab.state_reader import HandObservation, prepare_frame, analysis_gate
from validation.tools.api_reader_tournament import budget, config, FrozenLocalObservation, file_hash, RUNNER_FILES
from validation.tools.grounded_corpus import PARTITIONS, render, save, ROOT
from validation.tools.independent_tournament import scenario_timeline
from validation.tools.state_reader_comparison import load_frame
from validation.tools.api_reader_tournament import native_record
from validation.tools.stress_lab import LAYOUT

EPOCH = '2026-10-05-live-r1-diagnosis-eur10'
CASES = ('clean-ui','labelled-totals','rotation')
NAMES = ('luna-fast-v1','luna-fast-v2','luna-fast-live','gemini-lite-live')
NEW_SOURCES = ('bjlab/live_state.py','bjlab/live_cloud.py','bjlab/bounded_network.py',
    'validation/tools/live_reader_diagnosis.py')


def prepare(output, reader_manifest):
    manifest_digest=file_hash(reader_manifest)  # fail before producing any corpus
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    directory=output/'development'; directory.mkdir(exist_ok=False)
    records=[];truths={}; visibility={}
    for index,case in enumerate(CASES+('empty',)):
        seed=6100511+index*17
        stages=scenario_timeline(seed)
        stage=next(s for s in stages if s['phase']==('waiting' if case=='empty' else 'player'))
        family=(seed,'owned-live-v3-arial-'+str(seed),*PARTITIONS['development'][2:])
        image,truth,evidence=render(stage,case,family)
        record=native_record(directory,case,prepare_frame(image,LAYOUT),
            independent_session=seed,seed=seed,family=family[1],condition=case,
            evidence_kind='new-owned-synthetic-live-v3',split='development')
        records.append(record); truths[case]=truth; visibility[case]=evidence
    save(directory/'frames.json',records);save(directory/'oracle.json',truths);save(directory/'visibility-evidence.json',visibility)
    freeze={'contract':CONTRACT_VERSION,'historical_head':'b4b95168aa0cd290b47e4e780c7450d11764283f',
        'sources':{p:file_hash(ROOT/p) for p in RUNNER_FILES+NEW_SOURCES+('bjlab/grounded_cloud.py','bjlab/grounded_state.py','bjlab/hybrid_evidence.py')},
        'reader_manifest':str(Path(reader_manifest).resolve()),'reader_manifest_sha256':manifest_digest,
        'inputs':{n:file_hash(directory/n) for n in ('frames.json','oracle.json','visibility-evidence.json')},
        'cases':CASES,'models':{'luna':asdict(config(fast=True)),'gemini':asdict(GeminiConfig())},
        'prompts':{n:sha256(p.encode()).hexdigest() for n,p in [('v1',V1_PROMPT),('v2',V2_PROMPT),('live',PROMPT)]},
        'wire_schema_sha256':sha256(json.dumps(wire_schema(),sort_keys=True).encode()).hexdigest(),
        'epoch':EPOCH,'max_still_submissions':12,'max_hybrid_submissions':4,'retry_count':0,
        'gate_before_hybrid':{'inputs':3,'all_complete_json_within_ms':3000,'p95_at_most_ms':2500,
            'false_accepted_states':0,'all_three_r1_states_correct_and_usable':True},
        'timeout_policy':'Continue only predeclared different still comparisons; retain each charge; no retries. HTTP/auth/schema errors stop that candidate. Unknown reported pricing stops all.',
        'truth':'geometric visibility proxy plus assistant audit, not independent human annotation',
        'final_holdout':'not_opened_or_created','provider_transfer':'not_measured'}
    save(output/'freeze-live.json',freeze)
    return freeze


def checked(output, *, upload=False):
    output=Path(output); freeze=json.loads((output/'freeze-live.json').read_text())
    for name,digest in freeze['sources'].items():
        if file_hash(ROOT/name)!=digest: raise ValueError('Frozen candidate source changed.')
    if file_hash(freeze['reader_manifest'])!=freeze['reader_manifest_sha256']: raise ValueError('Frozen weights changed.')
    for name,digest in freeze['inputs'].items():
        if file_hash(output/'development'/name)!=digest: raise ValueError('Frozen development annotations changed.')
    records=json.loads((output/'development/frames.json').read_text());allowed=set();inputs=[]
    for record in records:
        if record['split']!='development' or record['evidence_kind']!='new-owned-synthetic-live-v3':
            raise PermissionError('Only this new owned development corpus is allowed.')
        for image in record['images']:
            if file_hash(output/'development'/image['file'])!=image['sha256']:raise ValueError('Pixels changed.')
            allowed.add(image['sha256'])
        inputs.append((record,load_frame(output/'development',record)))
    if upload:
        review=json.loads((output/'upload-review-live.json').read_text())
        if (review.get('approved_owned_only') is not True or review.get('epoch')!=EPOCH or
            review.get('freeze_sha256')!=file_hash(output/'freeze-live.json') or set(review.get('hashes',[]))!=allowed):
            raise PermissionError('Exact upload review missing or stale.')
        audit=json.loads((output/'request-audit.json').read_text())
        if not audit.get('new_gemini_request_locally_valid') or audit['freeze_sha256']!=file_hash(output/'freeze-live.json'):
            raise PermissionError('Documental/local request audit missing.')
    return freeze,inputs,json.loads((output/'development/oracle.json').read_text()),allowed


def rest_errors(value, schema, discovery, path='request'):
    if '$ref' in schema: schema=discovery['schemas'][schema['$ref']]
    kind=schema.get('type')
    if kind=='any':return []
    if kind=='object':
        if not isinstance(value,dict):return [path+':object_required']
        fields=schema.get('properties',{});issues=[]
        for key,item in value.items():
            if key not in fields: issues.append(path+'.'+key+':unknown_field')
            else:issues.extend(rest_errors(item,fields[key],discovery,path+'.'+key))
        return issues
    if kind=='array':
        if not isinstance(value,list):return [path+':array_required']
        return [e for item in value for e in rest_errors(item,schema['items'],discovery,path+'[]')]
    if kind=='string' and (not isinstance(value,str) or ('enum' in schema and value not in schema['enum'])):
        return [path+':invalid_string_or_enum']
    if kind=='integer' and type(value) is not int:return [path+':integer_required']
    if kind=='boolean' and type(value) is not bool:return [path+':boolean_required']
    return []


JSON_KEYS={'$id','$defs','$ref','$anchor','type','format','title','description','enum','items','prefixItems',
    'minItems','maxItems','minimum','maximum','anyOf','oneOf','properties','additionalProperties','required'}
def schema_issues(schema, path='schema'):
    issues=[]
    if not isinstance(schema,dict):return issues
    for key,value in schema.items():
        if key not in JSON_KEYS:issues.append(path+'.'+key+':not_in_documented_subset')
        if key in ('properties','$defs'):
            for name,item in value.items():issues.extend(schema_issues(item,path+'.'+key+'.'+name))
        elif key in ('anyOf','oneOf','prefixItems'):
            for index,item in enumerate(value):issues.extend(schema_issues(item,path+'.'+key+'.'+str(index)))
        elif key=='items':issues.extend(schema_issues(value,path+'.items'))
    return issues


def audit_requests(output):
    freeze,inputs,_,allowed=checked(output);frame=inputs[0][1];ceiling=budget()
    discovery=json.loads((Path(output)/'google-discovery.json').read_text())
    gemini=DiagnosticReader(GeminiConfig(),ceiling,allowed,provider='gemini',variant='live',transport=object())
    payload=gemini.payload(frame)
    errors=rest_errors(payload,discovery['schemas']['GenerateContentRequest'],discovery)
    errors+=schema_issues(wire_schema())
    model=json.loads((Path(output)/'gemini-model-readonly.json').read_text())
    if model.get('name')!='models/gemini-3.5-flash-lite' or 'generateContent' not in model.get('supportedGenerationMethods',[]):
        errors.append('model:generateContent_unavailable')
    sizes={}
    for variant in ('v1','v2','live'):
        reader=DiagnosticReader(config(fast=True),ceiling,allowed,provider='openai',variant=variant,transport=object())
        p=reader.payload(frame)
        schema=p['text']['format']['schema']
        sizes[variant]={'prompt_utf8_bytes':len(p['instructions'].encode()),
            'schema_compact_bytes':len(json.dumps(schema,separators=(',',':'))),
            'request_compact_bytes':len(json.dumps(p,separators=(',',':'))),
            'same_native_images':True,'detail':'high','max_output_tokens':1024}
    from bjlab.grounded_state import GroundedObservation
    report={'freeze_sha256':file_hash(Path(output)/'freeze-live.json'),'new_gemini_request_locally_valid':not errors,
        'local_rest_errors':errors,'legacy_v2_schema_subset_issues':schema_issues(GroundedObservation.model_json_schema()),
        'historical_http400_exact_cause':'unrecoverable: no retained provider field violation/message; schema subset mismatch is a hypothesis, not established cause',
        'new_request_format':'generationConfig.responseFormat.text with APPLICATION_JSON and common trimmed live schema',
        'readonly_model_access':model,'comparative_sizes':sizes,'network_inference_submissions':0,
        'official_sources':['https://ai.google.dev/api/generate-content',
            'https://ai.google.dev/gemini-api/docs/generate-content/structured-output',
            'https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite',
            'https://developers.openai.com/api/docs/guides/latency-optimization']}
    save(Path(output)/'request-audit.json',report);return report


def row(record,result,truth):
    obs=result.observation;legacy=isinstance(obs,HandObservation)
    cards=obs.cards if obs else []
    def inventory(values):return Counter((v['zone'],v['rank'],v['suit'],v['visibility']=='covered') for v in values)
    objects=inventory([c.model_dump() for c in cards]);expected=inventory(truth['cards'])
    ranks=Counter((c.zone,c.rank,c.visibility=='covered') for c in cards)
    target=Counter((c['zone'],c['rank'],c['visibility']=='covered') for c in truth['cards'])
    numbers=None if legacy or not obs else Counter((n.role,n.value) for n in obs.numbers)
    wanted=Counter((n['role'],n['value']) for n in truth['numbers'])
    phase=bool(obs and obs.phase==truth['phase']);controls=bool(obs and set(obs.controls)==set(truth['controls']))
    gate=(analysis_gate(obs) if legacy else live_gate(obs)) if obs else {'usable':False,'reasons':[result.status]}
    r1=bool(obs and ranks==target and phase and controls)
    attributed=Counter((n.role,n.value) for n in obs.numbers if n.role.endswith('_total')) if numbers is not None else Counter()
    actual=Counter((n['role'],n['value']) for n in truth['numbers'] if n['role'].endswith('_total'))
    false_total=bool(attributed-actual)
    # v1 intentionally has no grounded provenance; never becomes eligible for
    # the new live advisor merely because its legacy gate accepted an image.
    usable=bool(gate['usable'] and not legacy)
    return {'case_id':record['id'],'reader':result.reader,'status':result.status,'elapsed_ms':result.elapsed_ms,
        'inventory_exact':bool(obs and objects==expected),'rank_presence_exact':bool(obs and ranks==target),
        'phase_correct':phase,'controls_correct':controls,'numeric_roles_exact':None if legacy else bool(numbers==wanted),
        'complete_grounded_state':bool(not legacy and obs and objects==expected and phase and controls and numbers==wanted),
        'correct_usable_r1':bool(usable and r1 and not false_total and result.elapsed_ms<=3000),
        'false_accepted_state':bool(usable and (not r1 or false_total)),
        'historical_contract_without_numeric_provenance':legacy,'gate':gate,
        'observation':obs.model_dump() if obs else None,'diagnostics':result.diagnostics}


def summarize(rows):
    output={}
    for name in sorted({r['reader'] for r in rows}):
        values=[r for r in rows if r['reader']==name];complete=[r['elapsed_ms'] for r in values if r['status']=='completed']
        attempted=[r for r in values if r['status']!='not_executed']
        within=sum(r['status']=='completed' and r['elapsed_ms']<=3000 for r in values)
        output[name]={'planned':len(values),'attempted':len(attempted),'statuses':dict(Counter(r['status'] for r in values)),
            'validated_json_within_3s':within,'failure_rate_attempted':1-within/len(attempted) if attempted else None,
            'latency_complete_ms':{k:float(np.percentile(complete,p)) if complete else None for k,p in [('p50',50),('p95',95),('max',100)]},
            'inventory_exact':sum(r['inventory_exact'] for r in values),'rank_presence_exact':sum(r['rank_presence_exact'] for r in values),
            'phase_correct':sum(r['phase_correct'] for r in values),'controls_correct':sum(r['controls_correct'] for r in values),
            'complete_grounded_state':None if name.endswith('-v1') else sum(r['complete_grounded_state'] for r in values),
            'correct_usable_r1':sum(r['correct_usable_r1'] for r in values),'false_accepted_states':sum(r['false_accepted_state'] for r in values),
            'sample_scope':'three predeclared development scenes; synthetic common renderer, not a population p95 or provider transfer'}
        output[name]['hybrid_gate_passed']=bool(name.endswith('-live') and len(values)==3 and within==3 and
            max(complete)<=3000 and np.percentile(complete,95)<=2500 and
            output[name]['correct_usable_r1']==3 and output[name]['false_accepted_states']==0)
    return output


def readers(allowed,ceiling):
    require_inference_authorization(EPOCH)  # fail before reserving any submission
    return {name:DiagnosticReader(GeminiConfig() if name.startswith('gemini') else config(fast=True),ceiling,allowed,
        provider='gemini' if name.startswith('gemini') else 'openai',variant=name.rsplit('-',1)[-1],
        transport=MeasuredGeminiTransport(authorization_epoch=EPOCH,budget=ceiling) if name.startswith('gemini') else
            MeasuredResponsesTransport(authorization_epoch=EPOCH,budget=ceiling)) for name in NAMES}


def compare(output):
    freeze,inputs,truth,allowed=checked(output,upload=True);ceiling=budget();cloud=readers(allowed,ceiling)
    with (Path(output)/'execution-claim.json').open('x') as handle:json.dump({'epoch':EPOCH,'budget_before':ceiling.receipt()},handle)
    rows=[];halt=set();halt_all=False
    for index,case in enumerate(CASES):
        record,frame=next((r,f) for r,f in inputs if r['id']==case)
        # Latin ordering of Luna schemas; Gemini smoke first, subsequent cases
        # interleaved. Every row is a distinct predeclared comparison, no retry.
        order=list(NAMES[:3]);order=order[index:]+order[:index]
        order.insert(0 if index==0 else 2,'gemini-lite-live')
        for name in order:
            if halt_all or name in halt:
                from bjlab.grounded_state import GroundedResult
                result=GroundedResult(frame.frame_id,name,'not_executed',None,0,{'reason':'candidate_or_budget_stop'})
            else:result=cloud[name].read(frame)
            rows.append(row(record,result,truth[case]));save(Path(output)/'cloud-private-results.json',rows)
            if result.status=='blocked' or result.diagnostics.get('unreconciled_usage'):halt_all=True
            if result.diagnostics.get('http_status') or result.status in ('error','refused','incomplete'):halt.add(name)
            print(json.dumps({'case':case,'reader':name,'status':result.status,'elapsed_ms':round(result.elapsed_ms),
                'safe_error':result.diagnostics.get('provider_error'),'budget_upper_usd':ceiling.receipt()['accounted_upper_usd']}),flush=True)
    report={'contract':CONTRACT_VERSION,'readers':summarize(rows),'budget':ceiling.receipt(),
        'final_holdout':'not_opened','release_changed':False,'hybrid':'conditional_not_yet_executed'}
    save(Path(output)/'cloud-summary.json',report);return report


def hybrid(output, *, warm=False):
    freeze,inputs,truth,allowed=checked(output,upload=True);ceiling=budget()
    report=json.loads((Path(output)/'cloud-summary.json').read_text());candidates=[n for n in ('luna-fast-live','gemini-lite-live')
        if report['readers'][n]['hybrid_gate_passed']]
    lookup={r['id']:(r,f) for r,f in inputs};cloud=readers(allowed,ceiling);rows=[]
    with (Path(output)/'hybrid-claim.json').open('x') as handle:json.dump({'eligible':candidates,'budget_before':ceiling.receipt()},handle)
    for name in candidates:
        for changed in (False,True):
            record,frame=lookup['rotation'];empty=lookup['empty'][1];evidence=CurrentEvidence()
            local=FrozenGroundedLocal(FrozenLocalObservation(specialized_manifest=freeze['reader_manifest']))
            warmup_ms=None
            if warm:
                start=time.perf_counter();local.read(frame);warmup_ms=(time.perf_counter()-start)*1000
            done=threading.Event();ready=threading.Event();origin=time.monotonic()
            def producer():
                while not done.is_set():
                    evidence.capture(empty if changed and time.monotonic()-origin>=.65 else frame,source='owned-live-dev',table='one')
                    ready.set();done.wait(1/12)
            thread=threading.Thread(target=producer,daemon=True);thread.start();ready.wait(2)
            try:
                value=hybrid_attempt(evidence,local,cloud[name]);latest,_=evidence.snapshot()
                value.update(candidate=name,scenario='changed' if changed else 'stable',
                    capture_updates=latest.sequence if latest else 0,initialization_outside_capture_ms=warmup_ms)
                if value.get('gate') and value['reader']==name:
                    value['gate'].update(contract=CONTRACT_VERSION,numeric_provenance='observed_label_and_named_native_view',
                        number_coordinates='not_supported')
                observed=value.get('observation');metrics=None
                if observed:
                    from bjlab.live_state import LiveObservation
                    from bjlab.grounded_state import GroundedResult
                    metrics=row(record,GroundedResult(frame.frame_id,name,value['status'],
                        LiveObservation.model_validate_json(json.dumps(observed)),value['timing']['capture_to_headless_presentation_ms'],{}),truth['rotation'])
                value['correct_presented_state']=bool(value['presented'] and not changed and metrics and metrics['correct_usable_r1'])
                value['false_presented_state']=bool(value['presented'] and (changed or not metrics or not metrics['correct_usable_r1']))
                rows.append(value);save(Path(output)/'hybrid-private-results.json',rows)
                print(json.dumps({k:value.get(k) for k in ('candidate','scenario','route','status','presented','capture_updates','false_presented_state')}),flush=True)
                if value.get('status') in ('timeout','blocked','error') or value.get('diagnostics',{}).get('unreconciled_usage'):break
            finally:done.set();thread.join(2);evidence.disconnect()
    report={'eligible_candidates':candidates,'planned_trials':4,'executed_trials':len(rows),
        'scope':'real API plus independent native owned pixel producer to headless advisor payload; not desktop capture or native window paint',
        'correct_presented_states':sum(r['correct_presented_state'] for r in rows),
        'false_presented_states':sum(r['false_presented_state'] for r in rows),
        'rows':[{k:r.get(k) for k in ('candidate','scenario','route','status','presented','capture_updates','initialization_outside_capture_ms','revalidation','timing','correct_presented_state','false_presented_state')} for r in rows],
        'budget':ceiling.receipt(),'r2_certified':False,'final_holdout':'not_opened'}
    save(Path(output)/'hybrid-summary.json',report);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','audit','compare','hybrid','hybrid-warm'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reader-manifest',type=Path)
    args=parser.parse_args()
    if args.command=='prepare' and args.reader_manifest is None:
        parser.error('prepare requires --reader-manifest for the frozen existing weights')
    if args.command=='prepare':result=prepare(args.output,args.reader_manifest)
    elif args.command=='audit':result=audit_requests(args.output)
    elif args.command=='compare':result=compare(args.output)
    else:result=hybrid(args.output,warm=args.command=='hybrid-warm')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
