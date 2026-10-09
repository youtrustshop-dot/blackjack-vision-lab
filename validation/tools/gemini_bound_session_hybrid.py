"""Three new owned R1 checks, then at most one gated headless hybrid.

Same human autonomous continuation, USD8, model and request profile as PR25.
No retry, warm-up, hidden turn/phase, training, holdout or real game control.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import argparse
import json
import math
from threading import Event, Lock, Thread
import time

from bjlab.api_access_policy import MATRIX
from bjlab.available_image_views import bind_available_numeric_views, REQUEST_PROFILE
from bjlab.available_view_deadline_reader import AvailableViewDeadlineReader
from bjlab.controlled_http import resolve_scope
from bjlab.grounded_cloud import GeminiConfig
from bjlab.hybrid_evidence import CurrentEvidence, FrozenGroundedLocal
from bjlab.live_state import LiveObservation
from bjlab.numeric_provenance import normalize_number
from bjlab.offline_response_collector import OfflineResponseCollector
from bjlab.paired_deadline_reader import local_first_attempt
from bjlab.paired_persistent_http import PersistentScopedTransport, canonical_digest
from bjlab.private_observation_store import PrivateObservationStore, DIRECTORY, MAX_RECORDS
from bjlab.rejected_output_diagnostics import OwnedOutputScope, _OutputTap, inspect_output
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, ROOT, FrozenLocalObservation, native_record, file_hash
from validation.tools.cloud_connection_diagnosis import exception_types
from validation.tools.gemini_available_view_check import checked as prior_checked, SOURCES as PRIOR_SOURCES
from validation.tools.gemini_five_diagnostics import FrozenRequestReader, evaluate_saved, load_key, PRICE_CHECK
from validation.tools.gemini_new_session_prepare import corpus_case
from validation.tools.gemini_request_ablation import request_payload, native_view_audit
from validation.tools.grounded_corpus import save, SYMBOL_FONT
from validation.tools.numeric_semantic_score import semantic_score
from validation.tools.paired_cloud_prepare import allowed_number_views
from validation.tools.paired_semantic_smoke import claim, set_policy
from validation.tools.state_reader_comparison import load_frame

OUTPUT=ROOT/'artifacts/gemini-bound-session-hybrid-20261008'
PRIOR=ROOT/'artifacts/gemini-available-view-json-check-20261008'
PRIOR_FREEZE='a1bd1a4b49037a41942fe8ba3044ed3c8fd368c64c84bcf3f069f558a63c0af3'
INITIAL_LEDGER_SHA='1d3c5870331ac79f7f15bdb7bda91dd22b9a277fb5313a7e01f14b6c1c21a7ea'
EPOCH='2026-10-08-gemini-bound-three-plus-one'
MAX_RESERVATION=Decimal('1.2685312')
SPECS=(('new-total','labelled-totals',91008103,'georgiab.ttf','#293f4f','#fffbef',True),
       ('new-rotation','rotation',91008111,'verdanab.ttf','#594544','#f7f5fc',True),
       ('new-ended','disabled-controls',91008117,'trebucbd.ttf','#414b37','#fff8ec',False),
       ('new-hybrid','labelled-totals',91008123,'georgiab.ttf','#3d3552','#fcfcf7',True))
ORDER=tuple(s[0] for s in SPECS[:3]); HYBRID_CASE=SPECS[3][0]
GATE={'correct_timely_positives':2,'correct_complete_negative':1,'exact_card_inventory':3,
    'phase_and_controls':3,'relevant_total_provenance_exact':3,'false_accepts':0,
    'max_complete_ms':3000,'max_following_hybrid':1,'p95':None,
    'deadline_comparison':'complete_ms < 3000',
    'scope':'Tiny new-seed owned still gate; shared renderer, not provider/full-session/champion proof.'}
SOURCES=tuple(dict.fromkeys(PRIOR_SOURCES+('bjlab/available_view_deadline_reader.py',
    'validation/tools/gemini_bound_session_hybrid.py','tests/test_available_view_deadline_reader.py',
    'tests/test_gemini_bound_session_hybrid.py','bjlab/advice.py','bjlab/engine.py')))


def ledger_snapshot():
    digest=file_hash(CANONICAL_LEDGER); raw=json.loads(CANONICAL_LEDGER.read_text())
    if raw['max_requests'] not in (117,121): raise PermissionError('Unexpected canonical ceiling.')
    receipt=PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,
        max_requests=raw['max_requests'],max_usd='8').receipt()
    if file_hash(CANONICAL_LEDGER)!=digest: raise PermissionError('Canonical read raced.')
    return {'sha256':digest,'receipt':receipt}


def total_provenance_exact(observation,truth):
    expected=LiveObservation.model_validate({k:v for k,v in truth.items() if k!='number_views'})
    def items(value):
        if value is None: return None
        return Counter((n.role,n.value,normalize_number(n,available_views={'table'}).normalized_label,
            n.view,normalize_number(n,available_views={'table'}).blocks_r1)
            for n in value.numbers if n.role in ('player_total','dealer_total'))
    return observation is not None and items(observation)==items(expected)


def qualifies_for_hybrid(rows):
    if [r.get('case') for r in rows]!=list(ORDER): return False
    positives=negatives=0
    for row in rows:
        e=row.get('evaluation') or {}
        elapsed=row.get('total_through_validation_ms')
        if (row.get('status')!='completed' or not row.get('within_unchanged_live_boundary') or
                type(elapsed) not in (int,float) or not math.isfinite(elapsed) or not 0<=elapsed<3000 or
                row.get('stop_before_next_request') is not False or row.get('usage_settled') is not True or
                not (row.get('retention') or {}).get('retained') or row.get('evaluation_error_type') is not None or
                not e.get('strict_wire_validated') or not e.get('exact_card_inventory') or
                not e.get('phase_correct') or not e.get('controls_correct') or
                e.get('semantic_false_accept') or not row.get('relevant_totals_exact')):
            return False
        if e.get('expected_usable_r1'):
            if not e.get('semantic_timely_correct_usable_r1'): return False
            positives+=1
        else:
            if e.get('semantic_usable_r1') or not e.get('semantic_complete_transcription'): return False
            negatives+=1
    return positives==2 and negatives==1


def prepare():
    prior_checked(PRIOR_FREEZE)
    past=json.loads((PRIOR/'summary.json').read_text()); before=ledger_snapshot()
    if (past['stop'] is not None or past['attempted_diagnostics']!=2 or
            not past['rows'][0]['evaluation']['semantic_timely_correct_usable_r1'] or
            not past['rows'][1]['correct_content_abstention'] or before['sha256']!=INITIAL_LEDGER_SHA or
            past['ledger_after']!=before or before['receipt']['stopped'] or
            before['receipt']['requests_attempted']!=117 or
            Decimal(before['receipt']['accounted_upper_usd'])+MAX_RESERVATION>8 or
            4*GeminiConfig().reserve_usd!=MAX_RESERVATION):
        raise PermissionError('Closed repair controls/current canonical margin do not admit this lot.')
    protected_count=len(list((ROOT/DIRECTORY).glob('*.r1diag')))
    if protected_count+5>MAX_RECORDS: raise PermissionError('No protected-record capacity; never delete evidence to fit.')
    OUTPUT.mkdir(parents=True,exist_ok=False); directory=OUTPUT/'inputs'; directory.mkdir()
    records,truths,masks=[],{},{}; hands=set()
    prior_truth=json.loads((PRIOR/'inputs/oracle.json').read_text())
    signature=lambda t:tuple(sorted((c['zone'],c['rank'] or '',c['suit'] or '',c['visibility']) for c in t['cards']))
    old_signatures={signature(t) for t in prior_truth.values()}
    for spec in SPECS:
        frame,observation,truth,visibility,stage,family=corpus_case(spec)
        expected={**observation.model_dump(),'number_views':allowed_number_views(truth,frame.layout)}
        hand=signature(expected)
        if hand in hands or hand in old_signatures: raise ValueError('Predeclared new hand duplicates another control.')
        hands.add(hand); case,condition,seed,basename,_,_,usable=spec
        record=native_record(directory,case,frame,split='new_validation',seed=seed,
            independent_session='bound-state-'+str(seed),family=family[1],condition=condition,
            evidence_kind='new owned sampled state; shared renderer/controls/symbols, not provider transfer',
            expected_usable_r1=usable)
        payload=bind_available_numeric_views(request_payload(frame,'json-mode'),frame,mode='json-mode')
        path=directory/case/'D-bound.request.json'; save(path,payload)
        record['payload']={'file':case+'/'+path.name,'sha256':file_hash(path),
            'canonical_sha256':canonical_digest(payload),'mode':'json-mode','request_profile':REQUEST_PROFILE}
        records.append(record);truths[case]=expected;masks[case]=visibility
    save(directory/'frames.json',records);save(directory/'oracle.json',truths);save(directory/'visibility-evidence.json',masks)
    frozen={'experiment':'VISION-032','epoch':EPOCH,'order':list(ORDER),'hybrid_case':HYBRID_CASE,
        'gate':GATE,'specs':[list(s) for s in SPECS],'request_profile':REQUEST_PROFILE,
        'maximum_inferences':4,'validation_requests':3,'maximum_conditional_hybrid_requests':1,
        'batch_maximum_reservation_usd':str(MAX_RESERVATION),'request_count_amendment':[117,121],
        'money_cap_unchanged_usd':'8','ledger_before':before,'price_check':PRICE_CHECK,
        'prior_freeze_sha256':PRIOR_FREEZE,'prior_result_sha256':file_hash(PRIOR/'summary.json'),
        'sources':{name:file_hash(ROOT/name) for name in SOURCES},
        'files':{str(p.relative_to(OUTPUT)):file_hash(p) for p in sorted(directory.rglob('*')) if p.is_file()},
        'fonts_sha256':{s[3]:file_hash('C:/Windows/Fonts/'+s[3]) for s in SPECS},
        'symbol_font_sha256':file_hash(SYMBOL_FONT),'controls_font_sha256':file_hash('C:/Windows/Fonts/arialbd.ttf'),
        'protected_capacity_preparation':{'records':protected_count,'max':MAX_RECORDS,'maximum_new_records':5},
        'diagnostic_ms':10000,'original_capture_deadline_ms':3000,'producer_hz':12,
        'hybrid_local':'FrozenGroundedLocal(FrozenLocalObservation()), no forced fallback or turn confirmation',
        'hybrid_presentation':'owned held-frame producer to headless JSON, no physical screen/Windows paint',
        'retry':0,'paid_warmup':0,'following_hybrid':False,'real_advisor_connected':False,
        'training':False,'final_holdout':'not_opened','r2_certified':False,
        'human_scope':'Explicit 2026-10-08 autonomous continuation under unchanged lifetime USD8',
        'truth_scope':'Owned renderer masks and assistant original-pixel audit; not independent human/provider truth'}
    save(OUTPUT/'freeze.json',frozen);return frozen


def checked(external_hash):
    if file_hash(OUTPUT/'freeze.json')!=external_hash: raise PermissionError('External new-state freeze changed.')
    f=json.loads((OUTPUT/'freeze.json').read_text())
    if f['order']!=list(ORDER) or f['gate']!=GATE or f['specs']!=[list(s) for s in SPECS] or f['price_check']!=PRICE_CHECK:
        raise PermissionError('Frozen scope/gate/specification changed.')
    prior_checked(PRIOR_FREEZE)
    if file_hash(PRIOR/'summary.json')!=f['prior_result_sha256']: raise PermissionError('Historical repair result changed.')
    for name,digest in f['sources'].items():
        if file_hash(ROOT/name)!=digest: raise PermissionError('Frozen new-state source changed: '+name)
    for name,digest in f['files'].items():
        path=(OUTPUT/name).resolve()
        if not path.is_relative_to(OUTPUT.resolve()) or file_hash(path)!=digest:
            raise PermissionError('Frozen new pixels/reference/request changed.')
    for basename,digest in f['fonts_sha256'].items():
        if file_hash('C:/Windows/Fonts/'+basename)!=digest: raise PermissionError('Owned artwork font changed.')
    if file_hash(SYMBOL_FONT)!=f['symbol_font_sha256'] or file_hash('C:/Windows/Fonts/arialbd.ttf')!=f['controls_font_sha256']:
        raise PermissionError('Shared controls/symbol font changed.')
    rows=json.loads((OUTPUT/'inputs/frames.json').read_text());frames={r['id']:(r,load_frame(OUTPUT/'inputs',r)) for r in rows}
    if list(frames)!=list(ORDER)+[HYBRID_CASE]: raise PermissionError('Unexpected case set/order.')
    for record,frame in frames.values():
        native_view_audit(frame)
        if frame.details or canonical_digest(bind_available_numeric_views(request_payload(frame,'json-mode'),frame,
                mode='json-mode'))!=record['payload']['canonical_sha256']:
            raise PermissionError('Bound table-only request not reproducible.')
    return f,frames,json.loads((OUTPUT/'inputs/oracle.json').read_text())


def run_headless(record,frame,truth,budget,transport,store):
    initialized=time.monotonic_ns()
    saved=record['payload'];tap=_OutputTap(transport)
    cloud=AvailableViewDeadlineReader(GeminiConfig(),budget,[sha256(p).hexdigest() for _,p in frame.images()],transport=tap)
    scope=OwnedOutputScope('VISION-032',HYBRID_CASE,'gemini',cloud.config.model,saved['canonical_sha256'],
        tuple(sha256(p).hexdigest() for _,p in frame.images()),True);scope.verify(cloud,frame)
    local=FrozenGroundedLocal(FrozenLocalObservation());evidence=CurrentEvidence();done,ready=Event(),Event()
    captures=[];capture_lock=Lock();producer_errors=[]
    initialization_ms=(time.monotonic_ns()-initialized)/1e6
    def producer():
        try:
            while not done.is_set():
                stamp=evidence.capture(frame,source='owned-held-frame-producer',table=record['independent_session'])
                with capture_lock: captures.append(stamp.capture_ns)
                ready.set();done.wait(1/12)
        except Exception as exc:
            producer_errors.append(type(exc).__name__);evidence.disconnect();done.set();ready.set()
    producer_thread=Thread(target=producer,daemon=True,name='vision032-owned-pixel-producer');producer_thread.start()
    if not ready.wait(2):
        done.set();producer_thread.join(2);return {'executed':False,'reason':'producer_not_ready'}
    before=budget.receipt();value=None
    try:
        value=local_first_attempt(evidence,local,cloud)
        stamp,_=evidence.snapshot();value.update(executed=True,capture_updates=stamp.sequence if stamp else 0,
            cloud_reserved_attempts=budget.receipt()['requests_attempted']-before['requests_attempted'],
            http_post_transport_attempts=transport._request_count,
            physical_capture_or_window=False,oracle_supplied_to_path=False,forced_fallback=False)
        boundary=value.get('timing',{}).get('presentation_ns')
        with capture_lock: observed_captures=[n for n in captures if boundary is not None and n<=boundary]
        latest=value.get('revalidation',{}).get('latest_capture_ns')
        value.update(producer={'nominal_hz':12,'captures_through_presentation':len(observed_captures),
            'maximum_observed_gap_ms':max(((b-a)/1e6 for a,b in zip(observed_captures,observed_captures[1:])),default=None),
            'latest_capture_age_at_boundary_ms':(boundary-latest)/1e6 if boundary is not None and latest is not None else None,
            'error_types':list(producer_errors)},pre_capture_initialization_ms=initialization_ms,
            http_pool_initialization_ms=transport.initialization_ms,
            local_implementation='FrozenGroundedLocal(FrozenLocalObservation()); underlying LocalVisionReader has unknown phase/empty controls')
        save(OUTPUT/'hybrid.raw.json',value)
        observed=value.get('observation');elapsed=value.get('timing',{}).get('capture_to_headless_presentation_ms')
        if value['route']=='fallback':
            evaluation=semantic_score(observed,truth,status=value['status'],elapsed_ms=elapsed,available_views={'table'})
        else:
            # Frozen legacy local route has no numeric-label provenance.
            from bjlab.grounded_state import GroundedObservation
            projected=None
            if observed:
                legacy=GroundedObservation.model_validate(observed)
                projected=LiveObservation(cards=[c.model_dump() for c in legacy.cards],table_state=legacy.table_state,
                    phase=legacy.phase,controls=legacy.controls,numbers=[],blockers=[])
            evaluation=semantic_score(projected,truth,status=value['status'],elapsed_ms=elapsed,available_views={'table'})
        value.update(evaluation=evaluation,correct_presented_state=bool(value['presented'] and evaluation['semantic_timely_correct_usable_r1']),
            false_presented_state=bool(value['presented'] and not evaluation['semantic_timely_correct_usable_r1']))
        if tap.text is not None:
            public,private=inspect_output(tap.text,available_views={'table'})
            retained=store.write({'output_text':tap.text,'provenance':{**scope.__dict__,
                'diagnostic_only':False,'research_only':True,'scope':'single headless held-frame experiment, no native advisor',
                'timing':value['timing'],'usage':value['diagnostics'].get('usage')},'diagnosis':{'public':public,'private':private}})
            if sha256(store.read(retained['record_id'])['output_text'].encode()).hexdigest()!=sha256(tap.text.encode()).hexdigest():
                raise PermissionError('Hybrid selected text recovery failed.')
            value['retention']=retained
        else:value['retention']={'retained':False,'reason':'no_selected_cloud_output'}
        save(OUTPUT/'hybrid.json',value)
        return value
    finally:
        tap.text=None;done.set();producer_thread.join(2);transport.close()


def run(external_hash):
    frozen,frames,truths=checked(external_hash);before=ledger_snapshot()
    if before!=frozen['ledger_before'] or datetime.now(timezone.utc).date().isoformat()!=PRICE_CHECK['verified_utc_date']:
        raise PermissionError('Canonical history/current-price prerequisite changed.')
    original=MATRIX.read_bytes();policy=json.loads(original)['api_access_policy']
    if policy['inference_authorized'] or policy['max_requests']!=0 or Decimal(policy['max_usd'])!=0:
        raise PermissionError('Runtime must start disarmed.')
    if len(list((ROOT/DIRECTORY).glob('*.r1diag')))+5>MAX_RECORDS:
        raise PermissionError('Protected capacity changed; stop before any inference.')
    old_entries=deepcopy(json.loads(CANONICAL_LEDGER.read_text())['entries'])
    claim(OUTPUT/'execution.claim.json',{'freeze_sha256':external_hash,'maximum_inferences':4,'gate':GATE})
    rows,transports,access=[],[],None;stop=None;initialization={};hybrid={'executed':False,'reason':'validation_not_complete'}
    try:
        store=PrivateObservationStore(ROOT);probe={'output_text':'{}','provenance':{'experiment':'VISION-032-preflight'},'diagnosis':{}}
        protected=store.write(probe)
        if store.read(protected['record_id'])!=probe:raise PermissionError('Protected retention failed.')
        key=load_key();started=time.monotonic_ns();dns=resolve_scope();initialization['dns_ms']=(time.monotonic_ns()-started)/1e6
        budget=PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,max_requests=117,max_usd='8')
        metadata_client=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
        transports.append(metadata_client);metadata=metadata_client.metadata();metadata_client.close()
        exact=(metadata.get('name')=='models/'+GeminiConfig().model and 'generateContent' in metadata.get('supportedGenerationMethods',[]) and
            metadata.get('inputTokenLimit')==GeminiConfig().context_token_limit and metadata.get('outputTokenLimit',0)>=1024)
        access={'exact_model_and_limits':exact,'http_status':200}
        if not exact or ledger_snapshot()!=before or MATRIX.read_bytes()!=original:raise PermissionError('Read-only access prerequisite failed.')
        budget=budget.extend_request_ceiling(max_requests=121,authorization_epoch=EPOCH,
            authorization_note='Explicit human autonomous continuation 2026-10-08: three new owned bound-D validation states and at most one frozen gated headless local-first request; unchangedUSD8/all historical charges, no retry.')
        set_policy({**policy,'inference_authorized':True,'authorization_epoch':EPOCH,'max_requests':4,'max_usd':str(MAX_RESERVATION),
            'scope':'VISION-032 three fixed new states then at most one gated held-frame headless hybrid; no native advisor.'})
        for case in ORDER:
            if any(time.monotonic()+10>=e['expires_at'] for e in dns.values()):raise PermissionError('Original DNS scope cannot admit next diagnostic.')
            record,frame=frames[case];request=record['payload'];payload=json.loads((OUTPUT/'inputs'/request['file']).read_text())
            transport=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
            transports.append(transport);transport.bind(request['canonical_sha256'],OUTPUT/(case+'.submission.claim.json'))
            reader=FrozenRequestReader(frame,payload,request['canonical_sha256'],budget,transport)
            scope=OwnedOutputScope('VISION-032',case,'gemini',reader.config.model,request['canonical_sha256'],
                tuple(sha256(p).hexdigest() for _,p in frame.images()),True)
            row=OfflineResponseCollector(reader,store,scope).collect(frame);row.update(case=case,available_views=['table'])
            save(OUTPUT/(case+'.collector.json'),row);row.update(evaluation=None,relevant_totals_exact=False)
            rows.append(row);save(OUTPUT/'results.json',rows)
            try:
                observed=None
                if row['retention']['retained']:
                    text=store.read(row['retention']['record_id'])['output_text']
                    try:observed=LiveObservation.model_validate_json(text)
                    except ValueError:pass
                row['evaluation']=evaluate_saved(row,truths[case],frame,store)
                row['relevant_totals_exact']=total_provenance_exact(observed,truths[case])
            except Exception as exc:row.update(evaluation_error_type=type(exc).__name__,stop_before_next_request=True)
            save(OUTPUT/'results.json',rows)
            print(json.dumps({'case':case,'ms':row['total_through_validation_ms'],
                'timely_positive':(row['evaluation'] or {}).get('semantic_timely_correct_usable_r1'),
                'complete':(row['evaluation'] or {}).get('semantic_complete_transcription'),'advisor':False}),flush=True)
            if row['stop_before_next_request']:raise PermissionError('Storage/access/accounting/evaluator fault; stop remaining lot.')
        if qualifies_for_hybrid(rows):
            if any(time.monotonic()+3>=e['expires_at'] for e in dns.values()):raise PermissionError('Original DNS scope cannot admit capture deadline.')
            record,frame=frames[HYBRID_CASE];request=record['payload']
            transport=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
            transports.append(transport);transport.bind(request['canonical_sha256'],OUTPUT/(HYBRID_CASE+'.submission.claim.json'))
            hybrid=run_headless(record,frame,truths[HYBRID_CASE],budget,transport,store)
        else:hybrid={'executed':False,'reason':'frozen_new_state_quality_or_timing_gate_failed'}
        print(json.dumps({'hybrid_executed':hybrid['executed'],'presented':hybrid.get('presented'),
            'capture_to_headless_ms':hybrid.get('timing',{}).get('capture_to_headless_presentation_ms')}),flush=True)
    except Exception as exc:stop={'exception_types':exception_types(exc),'raw_message_saved':False}
    finally:
        MATRIX.write_bytes(original)
        for transport in transports:transport.close()
        after=ledger_snapshot();attempted=after['receipt']['requests_attempted']-117
        save(OUTPUT/'summary.json',{'experiment':'VISION-032','request_profile':REQUEST_PROFILE,'freeze_sha256':external_hash,
            'rows':rows,'access':access,'initialization':initialization,'gate':GATE,'gate_passed':qualifies_for_hybrid(rows),
            'hybrid':hybrid,'attempted_still_diagnostics':len(rows),'new_reservations':attempted,'maximum_inferences':4,
            'unused_slots_closed':4-attempted,'ledger_before':before,'ledger_after':after,
            'all_117_historical_entries_unchanged':json.loads(CANONICAL_LEDGER.read_text())['entries'][:117]==old_entries,
            'runtime_disarmed':MATRIX.read_bytes()==original,'pools_closed':all(t._closed for t in transports),
            'native_advisor_connected':False,'retry':0,'paid_warmup':0,'following_hybrid':False,'p95':None,'stop':stop})
    return json.loads((OUTPUT/'summary.json').read_text())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--run',action='store_true');parser.add_argument('--freeze-sha256');args=parser.parse_args()
    if args.prepare:
        if args.run:parser.error('Prepare and run are separate.')
        prepare();print(json.dumps({'prepared_stills':3,'conditional_hybrid_inputs':1,'provider_calls':0,'freeze_sha256':file_hash(OUTPUT/'freeze.json')}))
    else:
        if not args.freeze_sha256:parser.error('External freeze hash required.')
        value=run(args.freeze_sha256) if args.run else checked(args.freeze_sha256)[0]
        print(json.dumps({k:value.get(k) for k in ('attempted_still_diagnostics','gate_passed','runtime_disarmed','stop')}))
