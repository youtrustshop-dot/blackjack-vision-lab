"""Four bounded C/D diagnostics on new usable and contradictory owned scenes.

The human continuation authorizes this bounded follow-up under the existing
USD8 cap; an external ChatGPT review informs test design, never authorization.
No live advisor, retry, warm-up, following hybrid, tuning or holdout access.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw

from bjlab.api_access_policy import MATRIX
from bjlab.controlled_http import resolve_scope
from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_state import LiveObservation
from bjlab.numeric_provenance import normalize_number, semantic_gate
from bjlab.offline_response_collector import OfflineResponseCollector
from bjlab.paired_persistent_http import PersistentScopedTransport, canonical_digest
from bjlab.private_observation_store import PrivateObservationStore
from bjlab.rejected_output_diagnostics import OwnedOutputScope
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, ROOT, native_record, file_hash
from validation.tools.cloud_connection_diagnosis import exception_types
from validation.tools.gemini_five_diagnostics import FrozenRequestReader, evaluate_saved, load_key, PRICE_CHECK
from validation.tools.gemini_new_session_prepare import corpus_case, table_only, SOURCES as PREP_SOURCES
from validation.tools.gemini_request_ablation import request_payload, native_view_audit
from validation.tools.grounded_corpus import font, save
from validation.tools.paired_cloud_prepare import allowed_number_views
from validation.tools.paired_semantic_smoke import claim, set_policy
from validation.tools.state_reader_comparison import load_frame

OUTPUT=ROOT/'artifacts/gemini-paired-total-check-20261008'
EPOCH='2026-10-08-gemini-paired-total-check-four'
INITIAL_LEDGER_SHA='114067512e9cdfe954c0a8614fb4b4c5c3888c549b5cc665636bd2ab10efc966'
PAIRS=(('S1','C'),('S1','D'),('S2','D'),('S2','C'))
MAX_RESERVATION=Decimal('1.2685312')
SPECS=(('S1','labelled-totals',91008059,'candarab.ttf','#31463e','#fff9ec',True),
       ('S2','labelled-totals',91008061,'constanb.ttf','#504262','#fcf4fc',True))
GATE={'required_positive_correct_timely_r1':1,'required_negative_correct_content_abstention':1,
    'false_accepts':0,'relevant_totals_exact':2,'exact_card_inventory':2,'deadline_ms':3000,
    'p95':None,'scope':'Two functional checks per variant; not a champion or generalization/p95 claim.'}
SOURCES=tuple(dict.fromkeys(PREP_SOURCES+('validation/tools/gemini_paired_total_check.py',
    'validation/tools/gemini_five_diagnostics.py','tests/test_gemini_paired_total_check.py',
    'tests/test_gemini_new_session_prepare.py','bjlab/offline_response_collector.py',
    'bjlab/paired_persistent_http.py','bjlab/paired_deadline_reader.py',
    'bjlab/private_observation_store.py','bjlab/rejected_output_diagnostics.py','bjlab/controlled_http.py')))


def scene(spec):
    original,observed,truth,visibility,stage,family=corpus_case(spec)
    image=Image.open(BytesIO(original.table_png)).convert('RGB'); draw=ImageDraw.Draw(image)
    printed=font('C:/Windows/Fonts/arialbd.ttf',25)
    change=None
    if spec[0]=='S1':
        draw.text((910,130),'20',font=printed,fill='white',anchor='lt')
        x,y,r,b=draw.textbbox((910,130),'20',font=printed,anchor='lt')
        truth['numbers'].append({'value':20,'role':'unknown','label':None,'view':'table',
            'box':[x/1024,y/768,(r-x)/1024,(b-y)/768]})
    else:
        target=next(n for n in truth['numbers'] if n['role']=='player_total')
        before=target['value']; after=before+3; position=(690,555)
        old_text='PLAYER TOTAL '+str(before); new_text='PLAYER TOTAL '+str(after)
        old_box=draw.textbbox(position,old_text,font=printed,anchor='lt')
        new_box=draw.textbbox(position,new_text,font=printed,anchor='lt')
        erase=(min(old_box[0],new_box[0]),min(old_box[1],new_box[1]),
            max(old_box[2],new_box[2]),max(old_box[3],new_box[3]))
        natural=np.asarray(image).copy(); draw.rectangle(erase,fill=spec[4])
        draw.text(position,new_text,font=printed,fill='white',anchor='lt')
        difference=np.any(natural != np.asarray(image),axis=2); yy,xx=np.where(difference)
        number_start=position[0]+int(printed.getlength('PLAYER TOTAL '))-2
        if not len(xx) or xx.min()<number_start or yy.min()<old_box[1] or yy.max()>erase[3]:
            raise ValueError('Counterfactual must alter only printed total digits.')
        target.update(value=after,box=[new_box[0]/1024,new_box[1]/768,
            (new_box[2]-new_box[0])/1024,(new_box[3]-new_box[1])/768])
        change={'kind':'synthetic_counterfactual_display_only','role':'player_total',
            'natural_visible_card_total':before,'printed_total':after,
            'changed_pixel_bbox':[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)],
            'changed_pixels':int(difference.sum()),'cards_controls_labels_unchanged':True}
    from validation.tools.paired_cloud_prepare import live_truth
    observed=live_truth(truth); frame=table_only(image); native_view_audit(frame)
    expected_usable=spec[0]=='S1'
    if semantic_gate(observed,available_views={'table'})['usable'] != expected_usable:
        raise ValueError('The pixel/reference decision outcome differs from predeclared test.')
    return frame,observed,truth,visibility,stage,change,original


def ledger_snapshot():
    digest=file_hash(CANONICAL_LEDGER); raw=json.loads(CANONICAL_LEDGER.read_text())
    if raw['max_requests'] not in (111,115): raise PermissionError('Unexpected canonical ceiling.')
    budget=PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,
        max_requests=raw['max_requests'],max_usd='8')
    result={'sha256':digest,'receipt':budget.receipt()}
    if file_hash(CANONICAL_LEDGER)!=digest: raise PermissionError('Ledger read raced.')
    return result


def prepare():
    before=ledger_snapshot()
    if before['sha256']!=INITIAL_LEDGER_SHA or before['receipt']['stopped'] or (
            Decimal(before['receipt']['accounted_upper_usd'])+MAX_RESERVATION>8):
        raise PermissionError('Canonical historical margin does not admit four controls.')
    OUTPUT.mkdir(parents=True,exist_ok=False); directory=OUTPUT/'inputs'; directory.mkdir()
    rows,truths,audits=[],{},{}
    for spec in SPECS:
        frame,observed,truth,visibility,stage,change,original=scene(spec)
        record=native_record(directory,spec[0],frame,split='new_validation',seed=spec[2],
            independent_session='paired-total-'+str(spec[2]),condition='usable' if spec[0]=='S1' else 'counterfactual-contradiction',
            family=spec[3],evidence_kind='owned new-session rendering; not provider transfer',
            expected_usable_r1=spec[0]=='S1')
        record['payloads']={}
        for variant,mode in (('C','structured-card-limit-local'),('D','json-mode')):
            value=request_payload(frame,mode); path=directory/spec[0]/(variant+'.request.json'); save(path,value)
            record['payloads'][variant]={'file':spec[0]+'/'+path.name,'sha256':file_hash(path),
                'canonical_sha256':canonical_digest(value),'mode':mode}
        if change: (directory/spec[0]/'natural-coherent.png').write_bytes(original.table_png)
        rows.append(record); truths[spec[0]]={**observed.model_dump(),
            'number_views':allowed_number_views(truth,frame.layout)}
        audits[spec[0]]={'visibility':visibility,'counterfactual':change,
            'reference_outcome':semantic_gate(observed,available_views={'table'}),
            'annotation_scope':'Owned mask evidence and assistant original-pixel audit; no independent human/provider annotation.'}
    save(directory/'frames.json',rows); save(directory/'oracle.json',truths); save(directory/'pixel-audit.json',audits)
    frozen={'experiment':'VISION-030','epoch':EPOCH,'pairs':PAIRS,'gate':GATE,
        'maximum_inferences':4,'request_count_amendment':[111,115],'money_cap_unchanged_usd':'8',
        'batch_maximum_reservation_usd':str(MAX_RESERVATION),'ledger_before':before,'price_check':PRICE_CHECK,
        'sources':{p:file_hash(ROOT/p) for p in SOURCES},
        'files':{str(p.relative_to(OUTPUT)):file_hash(p) for p in directory.rglob('*') if p.is_file()},
        'available_views':['table'],'diagnostic_ms':10000,'original_live_ms':3000,
        'advisor_connected':False,'following_hybrid':False,'retry':0,'paid_warmup':0,
        'final_holdout':'not_opened','human_scope':'2026-10-08 explicit autonomous continuation, unchanged lifetime USD8 cap',
        'technical_review':'Existing ChatGPT Blackjack review recommends paired C/D usable/contradictory controls; not authorization.'}
    save(OUTPUT/'freeze.json',frozen)
    return frozen


def checked(external_hash):
    if file_hash(OUTPUT/'freeze.json')!=external_hash: raise PermissionError('External paired freeze changed.')
    frozen=json.loads((OUTPUT/'freeze.json').read_text())
    if frozen['pairs'] != [list(p) for p in PAIRS] or frozen['gate']!=GATE or frozen['price_check']!=PRICE_CHECK:
        raise PermissionError('Paired order/gates/prices changed.')
    for name,digest in frozen['sources'].items():
        if file_hash(ROOT/name)!=digest: raise PermissionError('Frozen execution source changed: '+name)
    for name,digest in frozen['files'].items():
        path=(OUTPUT/name).resolve()
        if not path.is_relative_to(OUTPUT.resolve()) or file_hash(path)!=digest:
            raise PermissionError('Frozen pixel/payload/reference changed.')
    rows=json.loads((OUTPUT/'inputs/frames.json').read_text()); frames={r['id']:(r,load_frame(OUTPUT/'inputs',r)) for r in rows}
    if list(frames)!=['S1','S2'] or len({r['seed'] for r in rows})!=2:
        raise PermissionError('Exactly two distinct predeclared owned sessions are required.')
    for record,frame in frames.values():
        if frame.details: raise PermissionError('Unexpected extra view.')
        native_view_audit(frame)
    return frozen,frames,json.loads((OUTPUT/'inputs/oracle.json').read_text())


def relevant_totals_exact(observation,truth):
    expected=LiveObservation.model_validate({k:v for k,v in truth.items() if k!='number_views'})
    def tuples(value):
        result=[]
        for number in value.numbers if value else []:
            if number.role in ('player_total','dealer_total'):
                normalized=normalize_number(number,available_views={'table'})
                result.append((number.role,number.value,normalized.normalized_label,number.view,normalized.blocks_r1))
        return Counter(result)
    return bool(tuples(expected)) and tuples(expected)==tuples(observation)


def run(external_hash):
    frozen,frames,truths=checked(external_hash); before=ledger_snapshot()
    if before!=frozen['ledger_before'] or before['sha256']!=INITIAL_LEDGER_SHA or (
            datetime.now(timezone.utc).date().isoformat()!=PRICE_CHECK['verified_utc_date']):
        raise PermissionError('Historical/current-price prerequisite changed.')
    original=MATRIX.read_bytes(); policy=json.loads(original)['api_access_policy']
    if policy['inference_authorized'] or policy['max_requests']!=0 or Decimal(policy['max_usd'])!=0:
        raise PermissionError('Runtime must start disarmed.')
    old_entries=deepcopy(json.loads(CANONICAL_LEDGER.read_text())['entries'])
    claim(OUTPUT/'execution.claim.json',{'freeze_sha256':external_hash,'pairs':PAIRS,'max_reserved_usd':str(MAX_RESERVATION)})
    rows,transports,access=[],[],None; stop=None; initialization={}
    try:
        store=PrivateObservationStore(ROOT); probe={'output_text':'{}','provenance':{'experiment':'VISION-030-preflight'},'diagnosis':{}}
        protected=store.write(probe)
        if store.read(protected['record_id'])!=probe: raise PermissionError('Protected retention failed.')
        key=load_key(); began=time.monotonic_ns(); dns=resolve_scope()
        initialization['dns_ms']=(time.monotonic_ns()-began)/1e6
        budget=PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,max_requests=111,max_usd='8')
        metadata_client=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
        transports.append(metadata_client); metadata=metadata_client.metadata()
        exact=(metadata.get('name')=='models/'+GeminiConfig().model and 'generateContent' in metadata.get('supportedGenerationMethods',[]) and
            metadata.get('inputTokenLimit')==GeminiConfig().context_token_limit and metadata.get('outputTokenLimit',0)>=1024)
        access={'exact_model_and_limits':exact,'http_status':200,'timing':dict(metadata_client.timings)}
        metadata_client.close()
        if not exact or ledger_snapshot()!=before or MATRIX.read_bytes()!=original:
            raise PermissionError('Read-only access prerequisite failed or state changed.')
        if 4*GeminiConfig().reserve_usd!=MAX_RESERVATION: raise PermissionError('Reservation price changed.')
        budget=budget.extend_request_ceiling(max_requests=115,authorization_epoch=EPOCH,
            authorization_note='Human autonomous continuation 2026-10-08: four C/D diagnostics on two new owned usable/contradictory states, no retry/hybrid; unchanged USD8 and all prior charges.')
        set_policy({**policy,'inference_authorized':True,'authorization_epoch':EPOCH,'max_requests':4,
            'max_usd':str(MAX_RESERVATION),'scope':'VISION-030 exactly S1-C,S1-D,S2-D,S2-C, diagnostic only.'})
        for case,variant in PAIRS:
            if any(time.monotonic()+10>=entry['expires_at'] for entry in dns.values()):
                raise PermissionError('Original DNS scope cannot admit next diagnostic deadline.')
            record,frame=frames[case]; request=record['payloads'][variant]
            payload=json.loads((OUTPUT/'inputs'/request['file']).read_text())
            transport=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
            transports.append(transport); transport.bind(request['canonical_sha256'],OUTPUT/(case+'-'+variant+'.submission.claim.json'))
            reader=FrozenRequestReader(frame,payload,request['canonical_sha256'],budget,transport)
            scope=OwnedOutputScope('VISION-030',case+'-'+variant,'gemini',reader.config.model,
                request['canonical_sha256'],tuple(sha256(p).hexdigest() for _,p in frame.images()),True)
            result=OfflineResponseCollector(reader,store,scope).collect(frame)
            result.update(case=case,variant=variant,available_views=['table'])
            save(OUTPUT/(case+'-'+variant+'.collector.json'),result)
            result.update(evaluation=None,relevant_totals_exact=False,correct_content_abstention=False)
            rows.append(result); save(OUTPUT/'results.json',rows)
            try:
                if result['retention']['retained']:
                    text=store.read(result['retention']['record_id'])['output_text']
                    try: observed=LiveObservation.model_validate_json(text)
                    except ValueError: observed=None
                else: observed=None
                result['evaluation']=evaluate_saved(result,truths[case],frame,store)
                result['relevant_totals_exact']=relevant_totals_exact(observed,truths[case])
                evaluation=result['evaluation']
                result['correct_content_abstention']=bool(case=='S2' and observed is not None and
                    not evaluation['semantic_usable_r1'] and not evaluation['semantic_false_accept'] and
                    evaluation['exact_card_inventory'] and evaluation['phase_correct'] and evaluation['controls_correct'] and
                    result['relevant_totals_exact'])
            except Exception as exc:
                result.update(evaluation_error_type=type(exc).__name__,stop_before_next_request=True)
            save(OUTPUT/'results.json',rows)
            metrics=result['evaluation'] or {}
            print(json.dumps({'case':case,'variant':variant,'ms':result['total_through_validation_ms'],
                'correct_timely_r1':metrics.get('semantic_timely_correct_usable_r1'),
                'false_accept':metrics.get('semantic_false_accept'),'relevant_totals_exact':result['relevant_totals_exact'],
                'content_abstention':result['correct_content_abstention'],'advisor':False}),flush=True)
            if result['stop_before_next_request']: raise PermissionError('Access/accounting/protected-retention failure; stop remaining lot.')
    except Exception as exc: stop={'exception_types':exception_types(exc),'raw_message_saved':False}
    finally:
        MATRIX.write_bytes(original)
        for transport in transports: transport.close()
        after=ledger_snapshot(); attempted=after['receipt']['requests_attempted']-111
        save(OUTPUT/'summary.json',{'experiment':'VISION-030','freeze_sha256':external_hash,'rows':rows,'access':access,
            'initialization':initialization,'attempted_diagnostics':len(rows),'new_reservations':attempted,'maximum_inferences':4,
            'unused_slots_closed':4-attempted,'ledger_before':before,'ledger_after':after,
            'all_111_historical_entries_unchanged':json.loads(CANONICAL_LEDGER.read_text())['entries'][:111]==old_entries,
            'runtime_disarmed':MATRIX.read_bytes()==original,'pools_closed':all(t._closed for t in transports),
            'advisor_connected':False,'hybrid_requests':0,'retry':0,'paid_warmup':0,'p95':None,'stop':stop})
    return json.loads((OUTPUT/'summary.json').read_text())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--run',action='store_true'); parser.add_argument('--freeze-sha256'); args=parser.parse_args()
    if args.prepare:
        if args.run: parser.error('Prepare and run are separate.')
        prepare(); print(json.dumps({'prepared':4,'provider_calls':0,'freeze_sha256':file_hash(OUTPUT/'freeze.json')}))
    else:
        if not args.freeze_sha256: parser.error('External freeze hash required.')
        result=run(args.freeze_sha256) if args.run else checked(args.freeze_sha256)[0]
        print(json.dumps({k:result.get(k) for k in ('attempted_diagnostics','runtime_disarmed','stop')}))
