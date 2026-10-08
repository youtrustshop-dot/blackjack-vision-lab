"""Networkless aggregate export of consumed VISION-034 receipts.

Never loads credentials, creates a reader/transport, modifies accounting, or
exposes private screenshots and raw browser/session identifiers in the export.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT/'artifacts/integrated-r1-session-20261008'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def collect():
    freeze = read(ARTIFACTS/'freeze.json')
    cloud = read(ARTIFACTS/'cloud-summary.json')
    ledger_path = ROOT/'artifacts/api-budget/eur10-total-20261004.json'
    ledger = read(ledger_path)
    if (digest(ledger_path) != cloud['ledger_after']['sha256'] or
            cloud['new_reservations'] or not cloud['all_123_prior_entries_unchanged'] or
            not cloud['runtime_disarmed'] or not cloud['pools_closed']):
        raise PermissionError('Closed accounting/evidence changed; do not regenerate a success claim.')
    amendment = next(a for a in ledger['request_limit_amendments']
        if a['authorization_epoch'] == freeze['epoch'])
    if sha256(json.dumps(ledger['entries'], sort_keys=True).encode()).hexdigest() != amendment['prior_entries_sha256']:
        raise PermissionError('Historical reservations changed.')
    policy = read(ROOT/'docs/VISION_EXPERIMENTS.json')['api_access_policy']
    if policy['inference_authorized'] or policy['max_requests'] or float(policy['max_usd']):
        raise PermissionError('This export requires a disarmed runtime.')
    demo = ARTIFACTS/'local-demo'
    receipts = [read(p) for p in demo.glob('browser-*.json')]
    populated = [r for r in receipts if r['analysis_count']]
    if len(populated) != 1 or not all(r['closed'] for r in receipts):
        raise PermissionError('Expected exactly one closed local demonstration engine with analysis.')
    receipt = populated[0]
    attempts, displays = receipt['attempts'], receipt['displays']
    positive = attempts[:4]
    negatives = attempts[4:]
    if (len(attempts) != 6 or sum(bool(a['presented']) for a in positive) != 3 or
            any(a['presented'] for a in negatives) or any(a.get('route') not in ('local','fallback') for a in attempts)):
        raise ValueError('Owned demonstration scope changed.')
    sessions = []
    for name, version_path in [('continuous-clean','v2-isolated'),('continuous-overlap','v2')]:
        folder = ARTIFACTS/name
        baseline = read(folder/'results.json')
        challenger = read(folder/version_path/'results.json')
        if baseline['manifest_sha256'] != challenger['manifest_sha256']:
            raise ValueError('Comparison must use exactly the same video/manifest.')
        sessions.append({'session':name, 'manifest_sha256':digest(folder/'manifest.json'),
            'baseline':deepcopy(baseline['results'][0]), 'existing_v2':deepcopy(challenger['results'][0]),
            'baseline_runner_sha256':baseline['runner_sha256'],
            'v2_source_hashes':challenger['source_hashes'],
            'baseline_receipt_sha256':digest(folder/'results.json'),
            'v2_receipt_sha256':digest(folder/version_path/'results.json'),
            'scope':'New owned development sessions; same renderer family; V2 is an existing implementation, not a new model.'})
    result = {'schema':1,'experiment':'VISION-034','executed_utc_date':'2026-10-08',
        'source_parent_commit':'3c23ea3c7c65f4ea06af651a9ca8cc7e3c99d535',
        'acquisition_commit':'a703ded52ffd7a712c004789456594320985274b',
        'installed_baseline':{'version':'1.1.1','commit':'4f074efd53066a95d64ca1ed53de03479a8adcba','replaced':False},
        'publication':'Unreleased opt-in source candidate; no native rebuild or deployment.',
        'gates':freeze['gates'],'original_freeze_sha256':digest(ARTIFACTS/'freeze.json'),
        'connection_repair_freeze_sha256':digest(ARTIFACTS/'connection-repair.json'),
        'local_demo_freeze_sha256':digest(demo/'freeze.json'),
        'source_snapshots':read(ARTIFACTS/'source-snapshot-receipt.json'),
        'historical_033':{'scores_unchanged':True,'full_transcription_correct':2,'attempted':3,
            'conditional_fourth':'closed; not executed or reopened','full_transcription_gate':'failed and preserved'},
        'local_browser':{'input':'Actual 1024x768 PNG acquired with canvas.toBlob in browser; only pixels, time and declared layout.',
            'reader':'Unchanged FrozenGroundedLocal(FrozenLocalObservation()); outlined controls owned development layout.',
            'manual_trigger':True,'manual_turn_confirmation':False,'oracle_input':False,
            'source_capture_count':receipt['capture_count'],'attempts':len(attempts),
            'usable_positive':{'accepted':3,'attempted':4,'first_cold_capture_gap_abstention':1},
            'safe_negatives':{'abstained':len(negatives),'attempted':len(negatives),'cases':['actual occlusion','actual empty table']},
            'backend_capture_to_output_ms':[a['timing']['capture_to_headless_presentation_ms'] for a in attempts],
            'dom_receipts':{'eligible':sum(bool(d['eligible_at_receipt']) for d in displays),'attempted':len(displays),
                'capture_to_dom_ms':[d['capture_to_dom_ms'] for d in displays],
                'boundary':'Two requestAnimationFrame acknowledgements in main browser view; physical scanout and external-window live paint not measured.'},
            'expired_original_advice_with_ongoing_capture':True,'actual_disconnect_removes_advice':True,
            'browser_popup':{'opened':True,'close_reopen':True,'reuses_existing_window':True,
                'same_authoritative_engine':True,'second_engine_analyses':0,
                'native_always_on_top_verified':False,'monitor_drag_dpi_minimized_capture_verified':False,
                'background_capture':'Chrome background timer/acquisition ages can exceed limits; stale/blocked, not operational success.'},
            'r2_certified':False,'independent_accuracy_or_p95':False,
            'proof_sha256':digest(demo/'browser-live-proof.png')},
        'cloud':{'planned_slots':3,'reached_local_cloud_wrapper':2,'provider_posts':0,'responses':0,
            'quality_numerator':None,'quality_denominator':0,'latency_p50_ms':None,'latency_p95_ms':None,
            'cases':[{'case':'stable-overlap','status':'timeout_before_post','elapsed_from_capture_ms':17151.816894,
                'diagnosis':'Synchronous official DNS resolution/preparation consumed deadline before reservation; no provider POST.'},
                {'case':'changing-rotation','status':'local_permission_guard_before_post',
                 'exact_guard':'unknown: original row saved exception type only; later stage tracing is offline-tested, not a reconstruction.'},
                {'case':'contradictory-total','status':'unused_closed'}],
            'actual_changed_while_cloud_pending_demonstrated':False,'actual_late_provider_reply_demonstrated':False,
            'dns_repair':'Expiring official OS DNS lease prepared outside capture path; no inference warm-up.',
            'repair_pools_closed':cloud['pools_closed'],'initial_process_internal_pool_finalization_observed':False,
            'runtime_disarmed':True,'following_lot':False,'retry':0,'paid_warmup':0},
        'accounting':{'before':cloud['ledger_before'],'after':cloud['ledger_after'],
            'all_123_previous_entries_unchanged':True,'new_reservations':0,'new_reported_usage_usd':'0',
            'unchanged_cap_usd':'8','remaining_accounted_margin_usd':'1.820197700',
            'unused_slots_closed':1,'invoice_and_current_balance_verified':False},
        'continuous_sessions':sessions,
        'strict_advice_diagnosis':read(ARTIFACTS/'session-failure-diagnosis.json'),
        'remaining_ten_failure':read(ARTIFACTS/'ten-rank-diagnosis.json'),
        'trace_retention':{'clean_v1_original_trace_overwritten_by_misnamed_v2_output':True,
            'original_v1_result_receipt_retained':True,'v2_trace_copied_to_separate_directory':True,
            'v1_reproduction_in_separate_directory':True,
            'reproduction_not_original_run_or_new_independent_evidence':True,
            'future_existing_result_or_trace_overwrite_rejected':True},
        'limitations':['Owned renderer references and geometric association are diagnostic, not independent human/physical identity truth.',
            'Offline video processing and media-plus-CPU opportunity times are not capture-to-display latency.',
            'Both final inventories remain one rank-10 short; zero certified complete session counts.',
            'No fresh provider screenshot/session generalization, operational p95, universal accuracy or profit evidence.',
            'Poker Phase0 and native advisor preserved, no strategy/tracker/model training expansion.',
            'Final holdout sealed; private images, browser identifiers and raw provider envelopes not published.']}
    return result


if __name__=='__main__':
    value=collect(); destination=ROOT/'validation/results/integrated-r1-session/summary.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'record':str(destination.relative_to(ROOT)),'provider_calls':0,
        'local_dom_receipts':value['local_browser']['dom_receipts'],'complete_certified_sessions':0}))
