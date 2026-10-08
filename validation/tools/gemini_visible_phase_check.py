"""Three new visible-phase controls, then one conditional headless hybrid.

Explicit human continuation 2026-10-08: keep USD8, every old charge and result.
No retry, paid warm-up, hidden turn, training, holdout or native game control.
"""
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
from bjlab.controlled_http import resolve_scope
from bjlab.grounded_cloud import GeminiConfig
from bjlab.hybrid_evidence import CurrentEvidence, FrozenGroundedLocal
from bjlab.live_state import LiveObservation
from bjlab.offline_response_collector import OfflineResponseCollector
from bjlab.paired_deadline_reader import local_first_attempt
from bjlab.paired_persistent_http import PersistentScopedTransport, canonical_digest
from bjlab.private_observation_store import PrivateObservationStore, DIRECTORY, MAX_RECORDS
from bjlab.rejected_output_diagnostics import OwnedOutputScope, _OutputTap, inspect_output
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from bjlab.visible_phase_deadline_reader import VisiblePhaseDeadlineReader, REQUEST_PROFILE, PHASE_RULES
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, ROOT, FrozenLocalObservation, native_record, file_hash
from validation.tools.cloud_connection_diagnosis import exception_types
from validation.tools.gemini_bound_session_hybrid import checked as prior_checked, SOURCES as PRIOR_SOURCES, total_provenance_exact
from validation.tools.gemini_five_diagnostics import FrozenRequestReader, evaluate_saved, load_key, PRICE_CHECK
from validation.tools.gemini_new_session_prepare import corpus_case, table_only
from validation.tools.grounded_corpus import save, SYMBOL_FONT
from validation.tools.numeric_semantic_score import semantic_score
from validation.tools.paired_cloud_prepare import allowed_number_views, render_case, live_truth, local_snapshot, OfflineOnly
from validation.tools.paired_semantic_smoke import claim, set_policy
from validation.tools.state_reader_comparison import load_frame
from validation.tools.stress_lab import timeline

OUTPUT = ROOT/'artifacts/gemini-visible-phase-20261008'
PRIOR = ROOT/'artifacts/gemini-bound-session-hybrid-20261008'
PRIOR_FREEZE = '57cdefc57c2a3b014caa48a1372efb5454331fe58271cb161cfa94e7e660bd7f'
INITIAL_LEDGER_SHA = '62968d1e6c7ad515d133dffc3631539d930d966572b7978ef3ab2421366a65f8'
EPOCH = '2026-10-08-gemini-visible-phase-three-plus-one'
MAX_RESERVATION = Decimal('1.2685312')
SPECS = (
    ('phase-player','labelled-totals',91008201,'candarab.ttf','#234b53','#fff7ea',True),
    ('phase-ended','disabled-controls',91008209,'constanb.ttf','#544a35','#fcf7ef',False),
    ('phase-waiting','transition-clear',91008217,'corbelb.ttf','#373c57','#fbf6fc',False),
    ('phase-hybrid','overlap',91008223,'tahomabd.ttf','#485a3c','#fffef2',True),
)
ORDER = tuple(s[0] for s in SPECS[:3])
HYBRID_CASE = SPECS[3][0]
GATE = {'correct_timely_positive':1,'correct_complete_negatives':2,
    'exact_card_inventory':3,'complete_semantic_transcription':3,'phase_and_controls':3,
    'relevant_total_provenance_exact':3,'false_accepts':0,'max_complete_ms':3000,
    'max_following_hybrid':1,'deadline_comparison':'complete_ms < 3000','p95':None,
    'scope':'New request profile, three sampled owned states; no retrospective repair or promotion.'}
SOURCES = tuple(dict.fromkeys(PRIOR_SOURCES+('bjlab/visible_phase_deadline_reader.py',
    'validation/tools/gemini_visible_phase_check.py','tests/test_visible_phase_deadline_reader.py',
    'tests/test_gemini_visible_phase_check.py')))


def ledger_snapshot():
    digest = file_hash(CANONICAL_LEDGER)
    raw = json.loads(CANONICAL_LEDGER.read_text())
    if raw['max_requests'] not in (121,124):
        raise PermissionError('Unexpected canonical ceiling.')
    receipt = PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,
        max_requests=raw['max_requests'],max_usd='8').receipt()
    if file_hash(CANONICAL_LEDGER) != digest:
        raise PermissionError('Canonical read raced.')
    return {'sha256':digest,'receipt':receipt}


def payload_for(frame):
    guard = OfflineOnly()
    reader = VisiblePhaseDeadlineReader(GeminiConfig(),guard,
        [sha256(p).hexdigest() for _,p in frame.images()],transport=guard)
    return reader.payload(frame)


def phase_case(spec):
    if spec[1] != 'transition-clear':
        return corpus_case(spec)
    name,condition,seed,basename,felt,paper,usable = spec
    stages = timeline(seed,12)
    terminal = next(i for i,s in enumerate(stages) if s['phase']=='settled')
    stage = stages[terminal+1]
    if stage['phase'] != 'waiting' or stage['cards']:
        raise ValueError('Next natural stage must be the empty waiting table.')
    family = (seed,'owned-new-'+name+'-'+basename,'C:/Windows/Fonts/'+basename,felt,paper)
    image,truth,visibility = render_case(stage,condition,family)
    frame = table_only(image)
    observed = live_truth(truth)
    if observed.phase != 'waiting' or observed.cards or usable:
        raise ValueError('Declared waiting reference does not match the renderer.')
    return frame,observed,truth,visibility,stage,family


def qualifies_for_hybrid(rows):
    if [r.get('case') for r in rows] != list(ORDER):
        return False
    positive = negative = 0
    for row in rows:
        e = row.get('evaluation') or {}
        elapsed = row.get('total_through_validation_ms')
        if (row.get('status') != 'completed' or not row.get('within_unchanged_live_boundary') or
                type(elapsed) not in (int,float) or not math.isfinite(elapsed) or not 0<=elapsed<3000 or
                row.get('stop_before_next_request') is not False or row.get('usage_settled') is not True or
                not (row.get('retention') or {}).get('retained') or row.get('evaluation_error_type') is not None or
                not e.get('strict_wire_validated') or not e.get('exact_card_inventory') or
                not e.get('semantic_complete_transcription') or not e.get('phase_correct') or
                not e.get('controls_correct') or e.get('semantic_false_accept') or
                not row.get('relevant_totals_exact')):
            return False
        if e.get('expected_usable_r1'):
            if not e.get('semantic_timely_correct_usable_r1'):
                return False
            positive += 1
        else:
            if e.get('semantic_usable_r1'):
                return False
            negative += 1
    return positive==1 and negative==2


def frozen_local():
    original = json.loads((ROOT/'artifacts/paired-semantic-hybrid-20261006/freeze.json').read_text())
    return local_snapshot(original['frozen_local']['manifest'])


def prepare():
    prior_checked(PRIOR_FREEZE)
    past = json.loads((PRIOR/'summary.json').read_text())
    before = ledger_snapshot()
    if (past['attempted_still_diagnostics'] != 3 or past['hybrid']['executed'] or
            not past['runtime_disarmed'] or not past['pools_closed'] or past['stop'] is not None or
            before['sha256'] != INITIAL_LEDGER_SHA or past['ledger_after'] != before or
            before['receipt']['requests_attempted'] != 120 or before['receipt']['stopped'] or
            Decimal(before['receipt']['accounted_upper_usd'])+MAX_RESERVATION>8 or
            4*GeminiConfig().reserve_usd != MAX_RESERVATION):
        raise PermissionError('Prior closed lot/current canonical margin not intact.')
    protected_count = len(list((ROOT/DIRECTORY).glob('*.r1diag')))
    if protected_count+5>MAX_RECORDS:
        raise PermissionError('No protected capacity; never delete evidence to fit.')
    OUTPUT.mkdir(parents=True,exist_ok=False)
    directory = OUTPUT/'inputs'; directory.mkdir()
    records,truths,masks = [],{},{}
    for spec in SPECS:
        frame,observation,truth,visibility,stage,family = phase_case(spec)
        expected = {**observation.model_dump(),'number_views':allowed_number_views(truth,frame.layout)}
        case,condition,seed,basename,_,_,usable = spec
        record = native_record(directory,case,frame,split='new_validation',seed=seed,
            independent_session='visible-phase-'+str(seed),family=family[1],condition=condition,
            evidence_kind='new owned sampled state; shared renderer/controls/suits, not full-session/provider proof',
            expected_usable_r1=usable)
        payload = payload_for(frame)
        path = directory/case/'phase.request.json'; save(path,payload)
        record['payload'] = {'file':case+'/'+path.name,'sha256':file_hash(path),
            'canonical_sha256':canonical_digest(payload),'request_profile':REQUEST_PROFILE}
        records.append(record);truths[case]=expected;masks[case]=visibility
    save(directory/'frames.json',records);save(directory/'oracle.json',truths);save(directory/'visibility-evidence.json',masks)
    frozen = {'experiment':'VISION-033','parent_commit':'da57e74377be612b9dd39ba22fe687063aec10cd',
        'epoch':EPOCH,'order':list(ORDER),'hybrid_case':HYBRID_CASE,'specs':[list(s) for s in SPECS],
        'gate':GATE,'request_profile':REQUEST_PROFILE,'phase_rule_sha256':sha256(PHASE_RULES.encode()).hexdigest(),
        'maximum_inferences':4,'validation_requests':3,'maximum_conditional_hybrid_requests':1,
        'batch_maximum_reservation_usd':str(MAX_RESERVATION),'request_count_amendment':[121,124],
        'lifetime_attempts_before':120,'money_cap_unchanged_usd':'8','ledger_before':before,
        'price_check':PRICE_CHECK,'prior_freeze_sha256':PRIOR_FREEZE,
        'prior_result_sha256':file_hash(PRIOR/'summary.json'),'frozen_local':frozen_local(),
        'sources':{name:file_hash(ROOT/name) for name in SOURCES},
        'files':{str(p.relative_to(OUTPUT)):file_hash(p) for p in sorted(directory.rglob('*')) if p.is_file()},
        'fonts_sha256':{s[3]:file_hash('C:/Windows/Fonts/'+s[3]) for s in SPECS},
        'symbol_font_sha256':file_hash(SYMBOL_FONT),'controls_font_sha256':file_hash('C:/Windows/Fonts/arialbd.ttf'),
        'protected_capacity_preparation':{'records':protected_count,'maximum_new_records':5,'max':MAX_RECORDS},
        'diagnostic_ms':10000,'original_capture_deadline_ms':3000,'producer_hz':12,
        'human_scope':'Explicit human Ok vai after PR26 delivery, 2026-10-08; bounded next 3+1 under unchanged USD8',
        'changed':'Opt-in visible phase vocabulary appended to bound D request only',
        'unchanged':'Wire schema, gates, evaluator, local weights, engine, old outputs/requests/scores',
        'hybrid_local':'FrozenGroundedLocal(FrozenLocalObservation()), naturally unknown phase/empty controls',
        'presentation':'held owned pixels to headless JSON; not native capture or paint',
        'retry':0,'paid_warmup':0,'following_hybrid':False,'training':False,'final_holdout':'not_opened',
        'truth_scope':'Owned renderer plus assistant original-pixel audit, not independent provider/human truth'}
    save(OUTPUT/'freeze.json',frozen)
    return frozen


def checked(external_hash):
    if file_hash(OUTPUT/'freeze.json') != external_hash:
        raise PermissionError('External phase freeze changed.')
    f = json.loads((OUTPUT/'freeze.json').read_text())
    if (f['order'] != list(ORDER) or f['gate'] != GATE or f['specs'] != [list(s) for s in SPECS] or
            f['request_profile'] != REQUEST_PROFILE or f['price_check'] != PRICE_CHECK or
            f['phase_rule_sha256'] != sha256(PHASE_RULES.encode()).hexdigest()):
        raise PermissionError('Frozen phase scope/contract/gates changed.')
    prior_checked(PRIOR_FREEZE)
    if file_hash(PRIOR/'summary.json') != f['prior_result_sha256'] or frozen_local() != f['frozen_local']:
        raise PermissionError('Historical results/local weights changed.')
    for name,digest in f['sources'].items():
        if file_hash(ROOT/name) != digest:
            raise PermissionError('Frozen phase source changed: '+name)
    for name,digest in f['files'].items():
        p = (OUTPUT/name).resolve()
        if not p.is_relative_to(OUTPUT.resolve()) or file_hash(p) != digest:
            raise PermissionError('Frozen phase input/reference/request changed.')
    for basename,digest in f['fonts_sha256'].items():
        if file_hash('C:/Windows/Fonts/'+basename) != digest:
            raise PermissionError('Owned font changed.')
    if file_hash(SYMBOL_FONT) != f['symbol_font_sha256'] or file_hash('C:/Windows/Fonts/arialbd.ttf') != f['controls_font_sha256']:
        raise PermissionError('Shared artwork changed.')
    records = json.loads((OUTPUT/'inputs/frames.json').read_text())
    frames = {r['id']:(r,load_frame(OUTPUT/'inputs',r)) for r in records}
    if list(frames) != list(ORDER)+[HYBRID_CASE]:
        raise PermissionError('Unexpected phase case set/order.')
    for record,frame in frames.values():
        if frame.details or canonical_digest(payload_for(frame)) != record['payload']['canonical_sha256']:
            raise PermissionError('Phase request not reproducible from actual packet.')
    return f,frames,json.loads((OUTPUT/'inputs/oracle.json').read_text())


def run_headless(record,frame,truth,budget,transport,store):
    initialized = time.monotonic_ns()
    request = record['payload']; tap = _OutputTap(transport)
    cloud = VisiblePhaseDeadlineReader(GeminiConfig(),budget,
        [sha256(p).hexdigest() for _,p in frame.images()],transport=tap)
    scope = OwnedOutputScope('VISION-033',HYBRID_CASE,'gemini',cloud.config.model,
        request['canonical_sha256'],tuple(sha256(p).hexdigest() for _,p in frame.images()),True)
    scope.verify(cloud,frame)
    local = FrozenGroundedLocal(FrozenLocalObservation()); evidence = CurrentEvidence()
    done,ready = Event(),Event(); captures=[];lock=Lock();errors=[]
    initialization_ms = (time.monotonic_ns()-initialized)/1e6
    def producer():
        try:
            while not done.is_set():
                stamp=evidence.capture(frame,source='owned-held-phase-producer',table=record['independent_session'])
                with lock:captures.append(stamp.capture_ns)
                ready.set();done.wait(1/12)
        except Exception as exc:
            errors.append(type(exc).__name__);evidence.disconnect();done.set();ready.set()
    worker = Thread(target=producer,daemon=True,name='vision033-owned-pixel-producer');worker.start()
    if not ready.wait(2):
        done.set();worker.join(2);transport.close()
        return {'executed':False,'reason':'producer_not_ready'}
    before = budget.receipt()
    try:
        value=local_first_attempt(evidence,local,cloud)
        boundary=value['timing']['presentation_ns'];latest=value['revalidation'].get('latest_capture_ns')
        with lock:observed=[n for n in captures if n<=boundary]
        value.update(executed=True,cloud_reserved_attempts=budget.receipt()['requests_attempted']-before['requests_attempted'],
            http_post_transport_attempts=transport._request_count,physical_capture_or_window=False,
            oracle_supplied_to_path=False,forced_fallback=False,pre_capture_initialization_ms=initialization_ms,
            http_pool_initialization_ms=transport.initialization_ms,
            local_implementation='FrozenGroundedLocal(FrozenLocalObservation()); unknown phase/empty controls by construction',
            producer={'nominal_hz':12,'captures_through_presentation':len(observed),
                'maximum_observed_gap_ms':max(((b-a)/1e6 for a,b in zip(observed,observed[1:])),default=None),
                'latest_capture_age_at_boundary_ms':(boundary-latest)/1e6 if latest is not None else None,
                'error_types':list(errors)})
        observed=value.get('observation')
        if value['route']=='local' and observed:
            from bjlab.grounded_state import GroundedObservation
            legacy=GroundedObservation.model_validate(observed)
            observed=LiveObservation(cards=[c.model_dump() for c in legacy.cards],table_state=legacy.table_state,
                phase=legacy.phase,controls=legacy.controls,numbers=[],blockers=[])
        evaluation=semantic_score(observed,truth,status=value['status'],
            elapsed_ms=value['timing']['capture_to_headless_presentation_ms'],available_views={'table'})
        value.update(evaluation=evaluation,
            correct_presented_state=bool(value['presented'] and evaluation['semantic_timely_correct_usable_r1']),
            false_presented_state=bool(value['presented'] and not evaluation['semantic_timely_correct_usable_r1']))
        if tap.text is not None:
            public,private=inspect_output(tap.text,available_views={'table'})
            retained=store.write({'output_text':tap.text,'provenance':{**scope.__dict__,
                'research_only':True,'scope':'single held-frame headless integration; no native advisor',
                'timing':value['timing'],'usage':value['diagnostics'].get('usage')},
                'diagnosis':{'public':public,'private':private}})
            if sha256(store.read(retained['record_id'])['output_text'].encode()).hexdigest()!=sha256(tap.text.encode()).hexdigest():
                raise PermissionError('Hybrid protected text recovery failed.')
            value['retention']=retained
        else:
            value['retention']={'retained':False,'reason':'no_selected_cloud_output'}
        save(OUTPUT/'hybrid.json',value)
        return value
    finally:
        tap.text=None;done.set();worker.join(2);transport.close()


def run(external_hash):
    frozen,frames,truths=checked(external_hash);before=ledger_snapshot()
    if before!=frozen['ledger_before'] or datetime.now(timezone.utc).date().isoformat()!=PRICE_CHECK['verified_utc_date']:
        raise PermissionError('Canonical history/current-price prerequisite changed.')
    original=MATRIX.read_bytes();policy=json.loads(original)['api_access_policy']
    if policy['inference_authorized'] or policy['max_requests']!=0 or Decimal(policy['max_usd'])!=0:
        raise PermissionError('Runtime must start disarmed.')
    if len(list((ROOT/DIRECTORY).glob('*.r1diag')))+5>MAX_RECORDS:
        raise PermissionError('Protected capacity changed; stop before inference.')
    old_entries=deepcopy(json.loads(CANONICAL_LEDGER.read_text())['entries'])
    claim(OUTPUT/'execution.claim.json',{'freeze_sha256':external_hash,'maximum_inferences':4,'gate':GATE})
    rows,transports,access=[],[],None;stop=None;initialization={}
    hybrid={'executed':False,'reason':'validation_not_complete'}
    try:
        store=PrivateObservationStore(ROOT)
        probe={'output_text':'{}','provenance':{'experiment':'VISION-033-preflight'},'diagnosis':{}}
        protected=store.write(probe)
        if store.read(protected['record_id'])!=probe:
            raise PermissionError('Protected retention failed.')
        key=load_key();started=time.monotonic_ns();dns=resolve_scope()
        initialization['dns_ms']=(time.monotonic_ns()-started)/1e6
        budget=PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,max_requests=121,max_usd='8')
        metadata_client=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
        transports.append(metadata_client);metadata=metadata_client.metadata();metadata_client.close()
        exact=(metadata.get('name')=='models/'+GeminiConfig().model and 'generateContent' in metadata.get('supportedGenerationMethods',[]) and
            metadata.get('inputTokenLimit')==GeminiConfig().context_token_limit and metadata.get('outputTokenLimit',0)>=1024)
        access={'exact_model_and_limits':exact,'http_status':200}
        if not exact or ledger_snapshot()!=before or MATRIX.read_bytes()!=original:
            raise PermissionError('Read-only access prerequisite failed.')
        if 4*GeminiConfig().reserve_usd!=MAX_RESERVATION:
            raise PermissionError('Reservation price changed.')
        budget=budget.extend_request_ceiling(max_requests=124,authorization_epoch=EPOCH,
            authorization_note='Human Ok vai 2026-10-08 after PR26: three NEW visible-phase controls then at most one gated new held-frame hybrid. Old conditional slot remains closed; USD8 and all120 historical charges retained. No retry.')
        set_policy({**policy,'inference_authorized':True,'authorization_epoch':EPOCH,'max_requests':4,
            'max_usd':str(MAX_RESERVATION),'scope':'VISION-033 exactly three phase controls then at most one conditional headless hybrid.'})
        for case in ORDER:
            if any(time.monotonic()+10>=e['expires_at'] for e in dns.values()):
                raise PermissionError('Original DNS scope cannot admit next diagnostic.')
            record,frame=frames[case];request=record['payload']
            payload=json.loads((OUTPUT/'inputs'/request['file']).read_text())
            transport=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
            transports.append(transport);transport.bind(request['canonical_sha256'],OUTPUT/(case+'.submission.claim.json'))
            reader=FrozenRequestReader(frame,payload,request['canonical_sha256'],budget,transport)
            scope=OwnedOutputScope('VISION-033',case,'gemini',reader.config.model,request['canonical_sha256'],
                tuple(sha256(p).hexdigest() for _,p in frame.images()),True)
            row=OfflineResponseCollector(reader,store,scope).collect(frame)
            row.update(case=case,available_views=['table'],evaluation=None,relevant_totals_exact=False)
            rows.append(row);save(OUTPUT/'results.json',rows)
            try:
                observed=None
                if row['retention']['retained']:
                    text=store.read(row['retention']['record_id'])['output_text']
                    try:observed=LiveObservation.model_validate_json(text)
                    except ValueError:pass
                row['evaluation']=evaluate_saved(row,truths[case],frame,store)
                row['relevant_totals_exact']=total_provenance_exact(observed,truths[case])
            except Exception as exc:
                row.update(evaluation_error_type=type(exc).__name__,stop_before_next_request=True)
            save(OUTPUT/'results.json',rows)
            print(json.dumps({'case':case,'ms':row['total_through_validation_ms'],
                'phase_correct':(row['evaluation'] or {}).get('phase_correct'),
                'complete':(row['evaluation'] or {}).get('semantic_complete_transcription'),'advisor':False}),flush=True)
            if row['stop_before_next_request']:
                raise PermissionError('Storage/access/accounting/evaluator fault; stop remaining lot.')
        if qualifies_for_hybrid(rows):
            if any(time.monotonic()+3>=e['expires_at'] for e in dns.values()):
                raise PermissionError('Original DNS scope cannot admit capture deadline.')
            record,frame=frames[HYBRID_CASE];request=record['payload']
            transport=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
            transports.append(transport);transport.bind(request['canonical_sha256'],OUTPUT/(HYBRID_CASE+'.submission.claim.json'))
            hybrid=run_headless(record,frame,truths[HYBRID_CASE],budget,transport,store)
        else:
            hybrid={'executed':False,'reason':'frozen_visible_phase_quality_or_timing_gate_failed'}
        print(json.dumps({'hybrid_executed':hybrid['executed'],'presented':hybrid.get('presented'),
            'capture_to_headless_ms':hybrid.get('timing',{}).get('capture_to_headless_presentation_ms')}),flush=True)
    except Exception as exc:
        stop={'exception_types':exception_types(exc),'raw_message_saved':False}
    finally:
        MATRIX.write_bytes(original)
        for transport in transports:transport.close()
        after=ledger_snapshot();attempted=after['receipt']['requests_attempted']-120
        save(OUTPUT/'summary.json',{'experiment':'VISION-033','request_profile':REQUEST_PROFILE,'freeze_sha256':external_hash,
            'rows':rows,'access':access,'initialization':initialization,'gate':GATE,'gate_passed':qualifies_for_hybrid(rows),
            'hybrid':hybrid,'attempted_still_diagnostics':len(rows),'new_reservations':attempted,'maximum_inferences':4,
            'unused_slots_closed':4-attempted,'ledger_before':before,'ledger_after':after,
            'all_120_historical_entries_unchanged':json.loads(CANONICAL_LEDGER.read_text())['entries'][:120]==old_entries,
            'runtime_disarmed':MATRIX.read_bytes()==original,'pools_closed':all(t._closed for t in transports),
            'native_advisor_connected':False,'retry':0,'paid_warmup':0,'following_hybrid':False,'p95':None,'stop':stop})
    return json.loads((OUTPUT/'summary.json').read_text())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--run',action='store_true')
    parser.add_argument('--freeze-sha256');args=parser.parse_args()
    if args.prepare:
        if args.run:parser.error('Prepare and run are separate.')
        prepare();print(json.dumps({'prepared_stills':3,'conditional_hybrid_inputs':1,'provider_calls':0,'freeze_sha256':file_hash(OUTPUT/'freeze.json')}))
    else:
        if not args.freeze_sha256:parser.error('External freeze hash required.')
        value=run(args.freeze_sha256) if args.run else checked(args.freeze_sha256)[0]
        print(json.dumps({k:value.get(k) for k in ('attempted_still_diagnostics','gate_passed','runtime_disarmed','stop')}))
