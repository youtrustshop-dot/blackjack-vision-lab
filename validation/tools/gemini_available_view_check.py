"""Two one-shot JSON-MIME controls of available image names; never live.

Reuses now-consumed owned S1/S2 pixels to test a corrected request contract,
not new generalization. USD8 and all previous unknown charges stay intact.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import argparse
import json
import shutil
import time

from bjlab.api_access_policy import MATRIX
from bjlab.available_image_views import bind_available_numeric_views, REQUEST_PROFILE
from bjlab.controlled_http import resolve_scope
from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_state import LiveObservation
from bjlab.offline_response_collector import OfflineResponseCollector
from bjlab.paired_persistent_http import PersistentScopedTransport, canonical_digest
from bjlab.private_observation_store import PrivateObservationStore
from bjlab.rejected_output_diagnostics import OwnedOutputScope
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, ROOT, file_hash
from validation.tools.cloud_connection_diagnosis import exception_types
from validation.tools.gemini_five_diagnostics import FrozenRequestReader, evaluate_saved, load_key, PRICE_CHECK
from validation.tools.gemini_paired_total_check import checked as old_checked, relevant_totals_exact, SOURCES as OLD_SOURCES
from validation.tools.gemini_request_ablation import request_payload, native_view_audit
from validation.tools.grounded_corpus import save
from validation.tools.paired_semantic_smoke import claim, set_policy
from validation.tools.state_reader_comparison import load_frame

SOURCE = ROOT/'artifacts/gemini-paired-total-check-20261008'
SOURCE_FREEZE = 'a068fce367d04434c28637df2e75d0e337bd8fe54c2f42dddf19674c8fcfb1a7'
OUTPUT = ROOT/'artifacts/gemini-available-view-json-check-20261008'
INITIAL_LEDGER_SHA = 'cb7e607e7dbbf00565accdd1ed86f6f6162f3f031b202a19f5a32eda85129521'
EPOCH = '2026-10-08-gemini-available-view-two'
ORDER = ('S1','S2')
MODE = 'json-mode'
MAX_RESERVATION = Decimal('0.6342656')
GATE = {'positive_timely_usable':1,'negative_grounded_content_abstention':1,
    'relevant_total_provenance_exact':2,'false_accepts':0,'original_live_ms':3000,
    'scope':'Two consumed-case functional controls, no champion/full-transcription/generalization/p95 claim.'}
SOURCES = tuple(dict.fromkeys(OLD_SOURCES+('bjlab/available_image_views.py',
    'validation/tools/gemini_available_view_check.py','tests/test_available_image_views.py',
    'tests/test_gemini_available_view_check.py')))


def ledger_snapshot():
    digest = file_hash(CANONICAL_LEDGER); value = json.loads(CANONICAL_LEDGER.read_text())
    if value['max_requests'] not in (115,117): raise PermissionError('Unexpected request ceiling.')
    receipt = PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,
        max_requests=value['max_requests'],max_usd='8').receipt()
    if file_hash(CANONICAL_LEDGER) != digest: raise PermissionError('Canonical read raced.')
    return {'sha256':digest,'receipt':receipt}


def prepare():
    prior,old_frames,truths = old_checked(SOURCE_FREEZE)
    before = ledger_snapshot(); old_result = json.loads((SOURCE/'summary.json').read_text())
    if (old_result['attempted_diagnostics'] != 4 or not old_result['runtime_disarmed'] or
            old_result['stop'] is not None or before['sha256'] != INITIAL_LEDGER_SHA or
            old_result['ledger_after'] != before or before['receipt']['stopped'] or
            before['receipt']['requests_attempted'] != 115 or
            Decimal(before['receipt']['accounted_upper_usd'])+MAX_RESERVATION > 8 or
            2*GeminiConfig().reserve_usd != MAX_RESERVATION):
        raise PermissionError('Closed prior scope and unchanged margin are required.')
    OUTPUT.mkdir(parents=True,exist_ok=False)
    shutil.copytree(SOURCE/'inputs',OUTPUT/'inputs')
    records = []
    for case in ORDER:
        old_record,frame = old_frames[case]; native_view_audit(frame)
        if frame.details: raise PermissionError('Only consumed table-only controls are admitted.')
        base = request_payload(frame,MODE)
        if canonical_digest(base) != old_record['payloads']['D']['canonical_sha256']:
            raise PermissionError('Old baseline payload no longer reproducible.')
        corrected = bind_available_numeric_views(base,frame,mode=MODE)
        path = OUTPUT/'inputs'/case/'D-bound.request.json'; save(path,corrected)
        record = deepcopy(old_record)
        record['corrected_payload']={'file':case+'/'+path.name,'canonical_sha256':canonical_digest(corrected),
            'sha256':file_hash(path),'mode':MODE,'request_profile':REQUEST_PROFILE}
        record['evidence_kind']='Consumed owned PR24 functional control; not new validation'
        records.append(record)
    save(OUTPUT/'inputs/frames.json',records)
    save(OUTPUT/'inputs/oracle.json',truths)
    freeze = {'experiment':'VISION-031','request_profile':REQUEST_PROFILE,'epoch':EPOCH,'order':list(ORDER),
        'mode':MODE,'gate':GATE,'maximum_inferences':2,'source_freeze_sha256':SOURCE_FREEZE,
        'source_result_sha256':file_hash(SOURCE/'summary.json'),'request_count_amendment':[115,117],
        'batch_maximum_reservation_usd':str(MAX_RESERVATION),'money_cap_unchanged_usd':'8',
        'ledger_before':before,'price_check':PRICE_CHECK,
        'sources':{name:file_hash(ROOT/name) for name in SOURCES},
        'files':{str(p.relative_to(OUTPUT)):file_hash(p) for p in sorted((OUTPUT/'inputs').rglob('*')) if p.is_file()},
        'diagnostic_ms':10000,'original_live_ms':3000,'advisor_connected':False,'hybrid':0,
        'retry':0,'paid_warmup':0,'final_holdout':'not_opened',
        'human_scope':'2026-10-08 autonomous continuation under the unchanged USD8 lifetime cap',
        'changed_request_fields':['systemInstruction.parts[0].text','systemInstruction.parts[1].text logical schema.$defs.LiveNumber.properties.w.enum'],
        'unchanged':'Consumed pixels/reference, model, thinking/output caps, local schema/gates/evaluator, all historical scores'}
    save(OUTPUT/'freeze.json',freeze)
    return freeze


def checked(external_hash):
    if file_hash(OUTPUT/'freeze.json') != external_hash: raise PermissionError('External corrected freeze changed.')
    frozen = json.loads((OUTPUT/'freeze.json').read_text())
    if (frozen['order'] != list(ORDER) or frozen['mode'] != MODE or frozen['gate'] != GATE or
            frozen['price_check'] != PRICE_CHECK or frozen['request_profile'] != REQUEST_PROFILE):
        raise PermissionError('Corrected order/contract/gates changed.')
    old_checked(SOURCE_FREEZE)
    if file_hash(SOURCE/'summary.json') != frozen['source_result_sha256']:
        raise PermissionError('Historical negative result changed.')
    for name,digest in frozen['sources'].items():
        if file_hash(ROOT/name) != digest: raise PermissionError('Frozen corrected source changed: '+name)
    for name,digest in frozen['files'].items():
        path=(OUTPUT/name).resolve()
        if not path.is_relative_to(OUTPUT.resolve()) or file_hash(path) != digest:
            raise PermissionError('Corrected pixels/payload/reference changed.')
    records = json.loads((OUTPUT/'inputs/frames.json').read_text())
    frames = {r['id']:(r,load_frame(OUTPUT/'inputs',r)) for r in records}
    if list(frames) != list(ORDER): raise PermissionError('Exactly the two consumed controls are required.')
    for record,frame in frames.values():
        native_view_audit(frame)
        payload=json.loads((OUTPUT/'inputs'/record['corrected_payload']['file']).read_text())
        rebound=bind_available_numeric_views(request_payload(frame,MODE),frame,mode=MODE)
        if canonical_digest(payload) != canonical_digest(rebound):
            raise PermissionError('Corrected request no longer reproducible.')
    return frozen,frames,json.loads((OUTPUT/'inputs/oracle.json').read_text())


def run(external_hash):
    frozen,frames,truths=checked(external_hash); before=ledger_snapshot()
    if before != frozen['ledger_before'] or datetime.now(timezone.utc).date().isoformat() != PRICE_CHECK['verified_utc_date']:
        raise PermissionError('Canonical history/current-price prerequisite changed.')
    original=MATRIX.read_bytes(); policy=json.loads(original)['api_access_policy']
    if policy['inference_authorized'] or policy['max_requests'] != 0 or Decimal(policy['max_usd']) != 0:
        raise PermissionError('Runtime must start disarmed.')
    old_entries=deepcopy(json.loads(CANONICAL_LEDGER.read_text())['entries'])
    claim(OUTPUT/'execution.claim.json',{'freeze_sha256':external_hash,'order':ORDER,'maximum_inferences':2})
    rows,transports,access=[],[],None; stop=None; initialization={}
    try:
        store=PrivateObservationStore(ROOT); probe={'output_text':'{}','provenance':{'experiment':'VISION-031-preflight'},'diagnosis':{}}
        protected=store.write(probe)
        if store.read(protected['record_id']) != probe: raise PermissionError('Protected retention failed.')
        key=load_key(); started=time.monotonic_ns(); dns=resolve_scope()
        initialization['dns_ms']=(time.monotonic_ns()-started)/1e6
        budget=PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,max_requests=115,max_usd='8')
        metadata_client=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
        transports.append(metadata_client); metadata=metadata_client.metadata()
        exact=(metadata.get('name') == 'models/'+GeminiConfig().model and 'generateContent' in metadata.get('supportedGenerationMethods',[]) and
            metadata.get('inputTokenLimit') == GeminiConfig().context_token_limit and metadata.get('outputTokenLimit',0) >= 1024)
        access={'exact_model_and_limits':exact,'http_status':200}; metadata_client.close()
        if not exact or ledger_snapshot() != before or MATRIX.read_bytes() != original:
            raise PermissionError('Read-only access prerequisite failed or state changed.')
        if 2*GeminiConfig().reserve_usd != MAX_RESERVATION: raise PermissionError('Reservation price changed.')
        budget=budget.extend_request_ceiling(max_requests=117,authorization_epoch=EPOCH,
            authorization_note='Human autonomous continuation 2026-10-08: exactly two corrected available-image-name diagnostics on consumed S1/S2; no retry/hybrid, unchanged USD8/all prior charges.')
        set_policy({**policy,'inference_authorized':True,'authorization_epoch':EPOCH,'max_requests':2,
            'max_usd':str(MAX_RESERVATION),'scope':'VISION-031 exactly two corrected source-view controls; never advisor.'})
        for case in ORDER:
            if any(time.monotonic()+10 >= entry['expires_at'] for entry in dns.values()):
                raise PermissionError('Original DNS scope cannot admit next diagnostic deadline.')
            record,frame=frames[case]; request=record['corrected_payload']
            payload=json.loads((OUTPUT/'inputs'/request['file']).read_text())
            transport=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=budget,dns_scope=dns,api_key=key)
            transports.append(transport); transport.bind(request['canonical_sha256'],OUTPUT/(case+'.submission.claim.json'))
            reader=FrozenRequestReader(frame,payload,request['canonical_sha256'],budget,transport)
            scope=OwnedOutputScope('VISION-031',case+'-D-bound','gemini',reader.config.model,
                request['canonical_sha256'],tuple(sha256(p).hexdigest() for _,p in frame.images()),True)
            row=OfflineResponseCollector(reader,store,scope).collect(frame)
            row.update(case=case,variant='D-bound',available_views=['table'])
            save(OUTPUT/(case+'.collector.json'),row)
            row.update(evaluation=None,relevant_totals_exact=False,correct_content_abstention=False)
            rows.append(row); save(OUTPUT/'results.json',rows)
            try:
                if row['retention']['retained']:
                    text=store.read(row['retention']['record_id'])['output_text']
                    try: observed=LiveObservation.model_validate_json(text)
                    except ValueError: observed=None
                else: observed=None
                row['evaluation']=evaluate_saved(row,truths[case],frame,store)
                row['relevant_totals_exact']=relevant_totals_exact(observed,truths[case])
                evaluation=row['evaluation']
                row['correct_content_abstention']=bool(case=='S2' and observed is not None and
                    not evaluation['semantic_usable_r1'] and not evaluation['semantic_false_accept'] and
                    evaluation['exact_card_inventory'] and evaluation['phase_correct'] and evaluation['controls_correct'] and row['relevant_totals_exact'])
            except Exception as exc:
                row.update(evaluation_error_type=type(exc).__name__,stop_before_next_request=True)
            save(OUTPUT/'results.json',rows)
            print(json.dumps({'case':case,'ms':row['total_through_validation_ms'],
                'correct_timely_r1':(row['evaluation'] or {}).get('semantic_timely_correct_usable_r1'),
                'relevant_totals_exact':row['relevant_totals_exact'],'content_abstention':row['correct_content_abstention'],'advisor':False}),flush=True)
            if row['stop_before_next_request']: raise PermissionError('Storage/access/accounting/evaluation fault; stop remaining lot.')
    except Exception as exc: stop={'exception_types':exception_types(exc),'raw_message_saved':False}
    finally:
        MATRIX.write_bytes(original)
        for transport in transports: transport.close()
        after=ledger_snapshot(); attempted=after['receipt']['requests_attempted']-115
        save(OUTPUT/'summary.json',{'experiment':'VISION-031','request_profile':REQUEST_PROFILE,'freeze_sha256':external_hash,
            'rows':rows,'access':access,'initialization':initialization,'attempted_diagnostics':len(rows),
            'new_reservations':attempted,'maximum_inferences':2,'unused_slots_closed':2-attempted,
            'ledger_before':before,'ledger_after':after,
            'all_115_historical_entries_unchanged':json.loads(CANONICAL_LEDGER.read_text())['entries'][:115]==old_entries,
            'runtime_disarmed':MATRIX.read_bytes()==original,'pools_closed':all(t._closed for t in transports),
            'advisor_connected':False,'hybrid_requests':0,'retry':0,'paid_warmup':0,'p95':None,'stop':stop})
    return json.loads((OUTPUT/'summary.json').read_text())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--run',action='store_true'); parser.add_argument('--freeze-sha256'); args=parser.parse_args()
    if args.prepare:
        if args.run: parser.error('Prepare and run are separate.')
        prepare(); print(json.dumps({'prepared':2,'provider_calls':0,'freeze_sha256':file_hash(OUTPUT/'freeze.json')}))
    else:
        if not args.freeze_sha256: parser.error('External freeze hash required.')
        value=run(args.freeze_sha256) if args.run else checked(args.freeze_sha256)[0]
        print(json.dumps({k:value.get(k) for k in ('attempted_diagnostics','runtime_disarmed','stop')}))
