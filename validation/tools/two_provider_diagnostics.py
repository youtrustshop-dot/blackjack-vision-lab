"""VISION-027: only the two explicitly authorized standalone diagnostics.

Default is offline checking. --prepare freezes; --run requires its external hash
and consumes a durable whole-lot claim before read-only access controls. No retry,
warm-up, hybrid, app/solver/advisor connection or following batch exists.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import time

from bjlab.api_access_policy import MATRIX
from bjlab.controlled_http import resolve_scope
from bjlab.offline_response_collector import OfflineResponseCollector
from bjlab.paired_persistent_http import PersistentScopedTransport, canonical_digest
from bjlab.private_observation_store import PrivateObservationStore
from bjlab.rejected_output_diagnostics import OwnedOutputScope
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, ROOT, file_hash
from validation.tools.cloud_connection_diagnosis import credentials, exception_types
from validation.tools.grounded_corpus import save
from validation.tools.paired_cloud_prepare import candidates, NAMES
from validation.tools.paired_semantic_prepare import OUTPUT as PRIOR, checked
from validation.tools.paired_semantic_smoke import claim, make_reader, set_policy

OUTPUT = ROOT/'artifacts/two-provider-diagnostics-20261007'
CASE = 'fresh-rotated-unknown'
ORDER = (NAMES[1], NAMES[0])
EPOCH = '2026-10-07-two-provider-offline-diagnostics'
MAX_BATCH_USD = Decimal('0.8436688')
BEFORE_LEDGER_SHA = '7793ff458df87b0abf10eca59f71a73e2be242a29c0687a82ae5c692be385895'
PRICE_CHECK = {'verified_utc_date': '2026-10-07',
    'sources': ['https://developers.openai.com/api/docs/models/gpt-6-luna',
        'https://developers.openai.com/api/docs/pricing', 'https://ai.google.dev/gemini-api/docs/pricing'],
    'luna_standard_input': '.10', 'luna_standard_output': '.50', 'luna_cache_write_upper': '.125',
    'luna_fast_multiplier': '2', 'luna_long_input_multiplier': '2', 'luna_long_output_multiplier': '1.5',
    'gemini_standard_input': '.30', 'gemini_output_including_thinking': '2.50',
    'method': 'Current exact-model official pages opened before this authorized scope; no substitution.'}
SOURCES = ('bjlab/offline_response_collector.py', 'validation/tools/two_provider_diagnostics.py',
    'tests/test_offline_response_collector.py', 'bjlab/private_observation_store.py',
    'bjlab/rejected_output_diagnostics.py')


def snapshot():
    value = json.loads(CANONICAL_LEDGER.read_text())
    if value['max_requests'] not in (105, 106):
        raise PermissionError('Unexpected canonical request ceiling.')
    before = file_hash(CANONICAL_LEDGER)
    receipt = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID,
        max_requests=value['max_requests'], max_usd='8').receipt()
    if file_hash(CANONICAL_LEDGER) != before:
        raise PermissionError('Canonical inspection raced.')
    return {'sha256': before, 'receipt': receipt}


def prerequisites():
    freeze, frames, _ = checked()
    proposal = json.loads((ROOT/'validation/results/rejected-output-diagnostics/proposal.json').read_text())
    record, frame = frames[CASE]
    if file_hash(PRIOR/'freeze.json') != proposal['prior_freeze_sha256']:
        raise PermissionError('Original reviewed freeze changed.')
    configs = candidates([sha256(p).hexdigest() for _, p in frame.images()])
    for name in ORDER:
        entry = record['payloads'][name]
        if (entry['sha256'] != proposal['request_payload_sha256'][name] or
                entry['canonical_sha256'] != proposal['request_canonical_sha256'][name] or
                canonical_digest(configs[name].payload(frame)) != entry['canonical_sha256']):
            raise PermissionError('Original pixels, prompt, schema or output cap changed.')
        if asdict(configs[name].config) != freeze['configs'][name]:
            raise PermissionError('Frozen model/config changed.')
    if sum((configs[name].config.reserve_usd for name in ORDER), Decimal(0)) != MAX_BATCH_USD:
        raise PermissionError('Worst-case reserve differs from exact authorization.')
    before = snapshot()
    if (before['sha256'] != BEFORE_LEDGER_SHA or before['receipt']['requests_attempted'] != 104 or
            before['receipt']['max_requests'] != 105 or before['receipt']['stopped'] or
            Decimal(before['receipt']['accounted_upper_usd'])+MAX_BATCH_USD > Decimal('8')):
        raise PermissionError('Current canonical history/margin does not permit this exact lot.')
    policy = json.loads(MATRIX.read_text())['api_access_policy']
    if policy['inference_authorized'] is not False or policy['max_requests'] != 0 or Decimal(policy['max_usd']) != 0:
        raise PermissionError('Start disarmed; no implicit scope reuse.')
    return record, frame, before, policy


def prepare():
    record, frame, before, _ = prerequisites()
    OUTPUT.mkdir(parents=True, exist_ok=False)
    freeze = {'experiment': 'VISION-027', 'epoch': EPOCH, 'parent_commit': '49d40036bef36fcf0658cf545946896d4d819f41',
        'case': CASE, 'order': list(ORDER), 'new_requests_maximum': 2,
        'diagnostic_deadline_ms': 10000, 'live_deadline_ms_unchanged': 3000,
        'scope': 'consumed owned case repeated for failure diagnosis, not independent accuracy',
        'advisor_connected': False, 'promote_candidate': False, 'retry': 0, 'paid_warmup': 0, 'hybrid': 0,
        'batch_maximum_reservation_usd': str(MAX_BATCH_USD), 'ledger_before': before,
        'price_check': PRICE_CHECK, 'sources': {p: file_hash(ROOT/p) for p in SOURCES},
        'prior_freeze_sha256': file_hash(PRIOR/'freeze.json'),
        'payloads': record['payloads'], 'image_sha256': [sha256(p).hexdigest() for _, p in frame.images()],
        'authorization_attachment_sha256': file_hash('C:/Users/User/.codex/attachments/a4ad7c52-d3fd-4325-8b3b-8f44833fad34/Testo incollato.txt')}
    save(OUTPUT/'freeze.json', freeze)
    return freeze


def frozen(external_hash):
    if file_hash(OUTPUT/'freeze.json') != external_hash:
        raise PermissionError('Externally reviewed freeze checksum differs.')
    value = json.loads((OUTPUT/'freeze.json').read_text())
    if (value['epoch'] != EPOCH or value['order'] != list(ORDER) or value['case'] != CASE or
            value['price_check'] != PRICE_CHECK or value['batch_maximum_reservation_usd'] != str(MAX_BATCH_USD)):
        raise PermissionError('Frozen bounded scope changed.')
    if any(file_hash(ROOT/p) != digest for p, digest in value['sources'].items()):
        raise PermissionError('Prepared diagnostic source changed.')
    return value, prerequisites()


def run(external_hash):
    freeze, (record, frame, before, policy) = frozen(external_hash)
    if datetime.now(timezone.utc).date().isoformat() != PRICE_CHECK['verified_utc_date']:
        raise PermissionError('Recheck current prices/access; no unattended future replay.')
    original_matrix = MATRIX.read_bytes()
    old_entries = json.loads(CANONICAL_LEDGER.read_text())['entries']
    claim(OUTPUT/'execution.claim.json', {'epoch': EPOCH, 'freeze_sha256': external_hash,
        'count': 2, 'no_retry': True, 'no_advisor': True, 'max_reserved_usd': str(MAX_BATCH_USD)})
    rows, access, transports, initialization = [], [], {}, {}
    stop = None; amended = False
    try:
        # Paid generation cannot start until actual private retention works.
        started = time.monotonic_ns(); store = PrivateObservationStore(ROOT)
        probe = {'output_text': '{}', 'provenance': {'experiment': 'VISION-027-offline-storage-preflight'}, 'diagnosis': {}}
        receipt = store.write(probe)
        if store.read(receipt['record_id']) != probe:
            raise PermissionError('Protected storage preflight failed.')
        initialization['private_storage_preflight_ms'] = (time.monotonic_ns()-started)/1e6
        credentials(); started = time.monotonic_ns(); dns = resolve_scope()
        initialization['dns_preresolution_ms'] = (time.monotonic_ns()-started)/1e6
        budget = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID, max_requests=105, max_usd='8')
        for name, provider in zip(ORDER, ('gemini', 'openai')):
            transport = PersistentScopedTransport(provider=provider, authorization_epoch=EPOCH, budget=budget, dns_scope=dns)
            transports[name] = transport; meta = transport.metadata(); model = candidates()[name].config.model
            valid = meta.get('id') == model if provider == 'openai' else (
                meta.get('name') == 'models/'+model and 'generateContent' in meta.get('supportedGenerationMethods', []))
            access.append({'candidate': name, 'exact_model_access': valid, 'http_status': 200,
                'client_initialization_ms': transport.initialization_ms, 'metadata_timing': dict(transport.timings)})
            if not valid:
                raise PermissionError('Exact model access failed.')
        if snapshot() != before or MATRIX.read_bytes() != original_matrix:
            raise PermissionError('Read-only access preflight changed canonical/runtime state.')
        budget = budget.extend_request_ceiling(max_requests=106, authorization_epoch=EPOCH,
            authorization_note='Explicit 2026-10-07 human attachment: exactly one Gemini and one Luna standalone diagnostic, <=USD0.8436688. Old unused scope closed; USD8 and every previous charge/reservation retained.')
        amended = True
        set_policy({**policy, 'inference_authorized': True, 'authorization_epoch': EPOCH,
            'max_requests': 2, 'max_usd': str(MAX_BATCH_USD),
            'scope': 'Only two standalone diagnostics on consumed owned PR19 input; 10s cap, never advisor, no retries/hybrid.'})
        for name, provider in zip(ORDER, ('gemini', 'openai')):
            if any(time.monotonic()+10 >= entry['expires_at'] for entry in dns.values()):
                raise PermissionError('Original DNS lease cannot admit this diagnostic deadline.')
            transport = transports[name]; transport.budget = budget
            reader = make_reader(name, frame, budget, transport)
            digest = record['payloads'][name]['canonical_sha256']
            transport.bind(digest, OUTPUT/(name+'.submission.claim.json'))
            scope = OwnedOutputScope('VISION-027', CASE, provider, reader.config.model,
                digest, tuple(freeze['image_sha256']), True)
            result = OfflineResponseCollector(reader, store, scope).collect(frame)
            result.update(case=CASE, candidate=name, evidence_scope=freeze['scope'])
            rows.append(result); save(OUTPUT/'results.json', rows)
            print(json.dumps({'candidate': name, 'status': result['status'],
                'complete_ms': round(result['total_through_validation_ms'], 3),
                'content_category': result['content_diagnosis']['category'],
                'text_retained': result['retention']['retained'], 'eligible_for_live': False}), flush=True)
            if result['stop_before_next_request'] or budget.receipt()['stopped']:
                raise PermissionError('Access/accounting/private-retention block; no next submission.')
    except Exception as exc:
        stop = {'exception_types': exception_types(exc), 'raw_message_saved': False}
    finally:
        MATRIX.write_bytes(original_matrix)
        for transport in transports.values():
            transport.close()
        after = snapshot()
        historical_entries_unchanged = json.loads(CANONICAL_LEDGER.read_text())['entries'][:104] == old_entries
        new_reserved = after['receipt']['requests_attempted']-104
        save(OUTPUT/'summary.json', {'experiment': 'VISION-027', 'rows': rows, 'access': access,
            'initialization_separate': initialization, 'attempted_diagnostics': len(rows),
            'new_reservations': new_reserved, 'maximum_inferences': 2, 'count_amendment_executed': amended,
            'new_scope_unused_slots_closed': 2-new_reserved, 'old_unused_scope_stays_closed': True,
            'ledger_before': before, 'ledger_after': after, 'all_104_historical_entries_unchanged': historical_entries_unchanged,
            'runtime_disarmed': MATRIX.read_bytes() == original_matrix, 'pools_closed': all(t._closed for t in transports.values()),
            'no_automatic_resumption': True, 'advisor_connected': False, 'champion_promoted': False,
            'hybrid_requests': 0, 'retries': 0, 'paid_warmup': 0, 'p95': None,
            'price_check': PRICE_CHECK, 'freeze_sha256': external_hash, 'stop': stop})
    return json.loads((OUTPUT/'summary.json').read_text())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--freeze-sha256')
    args = parser.parse_args()
    if args.prepare and args.run:
        parser.error('Preparation and execution are separate actions.')
    if args.run:
        if not args.freeze_sha256:
            parser.error('Explicit external freeze checksum required.')
        result = run(args.freeze_sha256)
        print(json.dumps({k: result[k] for k in ('attempted_diagnostics', 'runtime_disarmed', 'stop')}))
    elif args.prepare:
        prepare(); print(json.dumps({'prepared': True, 'provider_calls': 0, 'freeze_sha256': file_hash(OUTPUT/'freeze.json')}))
    else:
        prerequisites(); print(json.dumps({'offline_preconditions_valid': True, 'provider_calls': 0}))
