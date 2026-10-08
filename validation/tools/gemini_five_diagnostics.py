"""Run the five human-authorized PR22 Gemini controls once, diagnostic-only.

Preparation and checking are offline. Execution requires both immutable freezes,
a durable whole-lot claim, current access/prices, protected storage and the same
canonical USD8 lifetime ledger. No retry, warm-up, hybrid or following batch.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import argparse
import json
from pathlib import Path
import time

from pydantic import ValidationError

from bjlab.api_access_policy import MATRIX
from bjlab.controlled_http import resolve_scope
from bjlab.grounded_cloud import GeminiConfig
from bjlab.hybrid_evidence import frame_fingerprint
from bjlab.live_state import LiveCard, LiveObservation
from bjlab.offline_response_collector import OfflineResponseCollector
from bjlab.paired_deadline_reader import CaptureDeadlineReader
from bjlab.paired_persistent_http import PersistentScopedTransport, canonical_digest
from bjlab.private_observation_store import PrivateObservationStore
from bjlab.rejected_output_diagnostics import OwnedOutputScope
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, ROOT, file_hash
from validation.tools.cloud_connection_diagnosis import exception_types
from validation.tools.gemini_request_ablation import OUTPUT as PREPARED, verify, native_view_audit
from validation.tools.grounded_corpus import save
from validation.tools.numeric_semantic_score import semantic_score
from validation.tools.paired_cloud_prepare import score
from validation.tools.paired_semantic_smoke import claim, set_policy
from validation.tools.state_reader_comparison import load_frame

OUTPUT = ROOT/'artifacts/gemini-five-diagnostics-20261008'
PREPARED_SHA = '3783df4d50421c79df3cc2575f2f8ced8577f73c384af9e3723a1859e789876e'
INITIAL_LEDGER_SHA = 'b73a4697f0e59c173e8756e00f1ab5c5a297bb329e78d57066397955c1c94c44'
EPOCH = '2026-10-08-gemini-five-diagnostic-controls'
ORDER = ('A', 'B', 'C', 'D', 'E')
MAX_BATCH_USD = Decimal('1.5856640')
PRICE_CHECK = {'verified_utc_date': '2026-10-08', 'model': 'gemini-3.5-flash-lite',
    'input_usd_per_million': '.30', 'output_including_thinking_usd_per_million': '2.50',
    'sources': ['https://ai.google.dev/gemini-api/docs/pricing',
        'https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite',
        'https://ai.google.dev/api/generate-content'],
    'method': 'Official pages opened before this bounded scope; frozen request fields checked.'}
SOURCES = ('validation/tools/gemini_five_diagnostics.py',
    'bjlab/offline_response_collector.py', 'bjlab/paired_persistent_http.py',
    'bjlab/paired_deadline_reader.py', 'bjlab/private_observation_store.py',
    'bjlab/rejected_output_diagnostics.py', 'bjlab/controlled_http.py',
    'tests/test_gemini_five_diagnostics.py')


class FrozenRequestReader(CaptureDeadlineReader):
    """Return only the reviewed request for its exact native image packet."""
    def __init__(self, frame, payload, expected_digest, budget, transport):
        if canonical_digest(payload) != expected_digest:
            raise PermissionError('Prepared request checksum changed.')
        generation = payload['generationConfig']
        if (generation['maxOutputTokens'] != 1024 or generation['thinkingConfig'] != {
                'thinkingLevel': 'MINIMAL', 'includeThoughts': False}):
            raise PermissionError('Prepared thinking/output cap changed.')
        super().__init__(GeminiConfig(), budget, [sha256(p).hexdigest() for _, p in frame.images()],
            provider='gemini', transport=transport, name='gemini-frozen-diagnostic-only')
        self._serialized = json.dumps(payload, separators=(',', ':'), allow_nan=False)
        self._packet = frame_fingerprint(frame)

    def payload(self, frame):
        if frame_fingerprint(frame) != self._packet:
            raise PermissionError('Prepared native packet changed.')
        return json.loads(self._serialized)

    def read(self, *args, **kwargs):
        raise PermissionError('This prepared reader is diagnostic-only; no live read.')


def snapshot():
    value = json.loads(CANONICAL_LEDGER.read_text())
    if value['max_requests'] not in (106, 111):
        raise PermissionError('Unexpected canonical request ceiling.')
    digest = file_hash(CANONICAL_LEDGER)
    receipt = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID,
        max_requests=value['max_requests'], max_usd='8').receipt()
    if file_hash(CANONICAL_LEDGER) != digest:
        raise PermissionError('Canonical read raced.')
    return {'sha256': digest, 'receipt': receipt}


def prerequisites():
    verify(PREPARED, PREPARED_SHA)
    rows = json.loads((PREPARED/'inputs/frames.json').read_text())
    if tuple(r['id'] for r in rows) != ORDER:
        raise PermissionError('Exactly the five reviewed controls are required.')
    frames = {}
    for row in rows:
        frame = load_frame(PREPARED/'inputs', row)
        native_view_audit(frame)
        payload_path = PREPARED/'inputs'/row['payload']['file']
        if file_hash(payload_path) != row['payload']['sha256']:
            raise PermissionError('Prepared request changed.')
        payload = json.loads(payload_path.read_text())
        if canonical_digest(payload) != row['payload']['canonical_sha256']:
            raise PermissionError('Prepared request canonical hash changed.')
        frames[row['id']] = (row, frame, payload)
    before = snapshot()
    receipt = before['receipt']
    if (before['sha256'] != INITIAL_LEDGER_SHA or receipt['requests_attempted'] != 106 or
            receipt['max_requests'] != 106 or receipt['stopped'] or
            Decimal(receipt['accounted_upper_usd'])+MAX_BATCH_USD > Decimal('8') or
            5*GeminiConfig().reserve_usd != MAX_BATCH_USD):
        raise PermissionError('Current history/margin does not admit the bounded five.')
    policy = json.loads(MATRIX.read_text(encoding='utf-8'))['api_access_policy']
    if policy['inference_authorized'] is not False or policy['max_requests'] != 0 or Decimal(policy['max_usd']) != 0:
        raise PermissionError('Runtime must start disarmed; previous scopes remain closed.')
    return frames, before, policy


def prepare():
    _, before, _ = prerequisites()
    OUTPUT.mkdir(parents=True, exist_ok=False)
    freeze = {'experiment': 'VISION-029', 'epoch': EPOCH,
        'parent_commit': 'd0690c18343558b8e169b5c4fcd70b494ec5f203',
        'prepared_freeze_sha256': PREPARED_SHA, 'order': list(ORDER), 'maximum_inferences': 5,
        'diagnostic_wait_ms': 10000, 'original_live_deadline_ms': 3000,
        'batch_maximum_reservation_usd': str(MAX_BATCH_USD), 'money_cap_unchanged_usd': '8',
        'request_count_amendment': [106, 111], 'ledger_before': before,
        'price_check': PRICE_CHECK, 'sources': {name: file_hash(ROOT/name) for name in SOURCES},
        'scope': 'Consumed owned case controls; not independent validation or operational p95',
        'human_scope': '2026-10-08 continuation immediately after the concrete five-control PR22 delivery',
        'retry': 0, 'paid_warmup': 0, 'hybrid': 0, 'advisor_connected': False}
    save(OUTPUT/'freeze.json', freeze)
    return freeze


def load_key():
    """Reuse only the existing Gemini key file; never print or persist the key."""
    entries = []
    for line in (ROOT/'.env.gemini.local').read_text(encoding='utf-8-sig').splitlines():
        name, sep, value = line.partition('=')
        if sep and name.strip() in ('GEMINI_API_KEY', 'GOOGLE_API_KEY'):
            entries.append(value.strip().strip('"').strip("'"))
    if len(set(entries)) != 1 or not entries[0]:
        raise PermissionError('Existing Gemini credential is unavailable or ambiguous.')
    return entries[0]


def transcription_components(text, truth):
    """Measure card components of rejected text without repairing full acceptance."""
    expected = LiveObservation.model_validate({k: v for k, v in truth.items() if k != 'number_views'})
    try:
        raw = json.loads(text)
        if not isinstance(raw, dict) or not isinstance(raw.get('c'), list) or len(raw['c']) > 52:
            raise ValueError('Unbounded/non-card output.')
        cards = [LiveCard.model_validate(card) for card in raw['c']]
    except (ValueError, TypeError, ValidationError):
        cards, raw = [], {}
    def counts(values, fields):
        return Counter(tuple(getattr(card, name) for name in fields) for card in values)
    known_ranks = counts([c for c in expected.cards if c.rank], ('zone', 'rank'))
    known_suits = counts([c for c in expected.cards if c.suit], ('zone', 'rank', 'suit'))
    backs = counts([c for c in expected.cards if c.visibility == 'covered'], ('zone', 'visibility'))
    return {'rank': {'correct': sum((known_ranks & counts(cards, ('zone', 'rank'))).values()),
        'expected': sum(known_ranks.values())},
        'suit': {'correct': sum((known_suits & counts(cards, ('zone', 'rank', 'suit'))).values()), 'expected': sum(known_suits.values())},
        'backs': {'correct': sum((backs & counts(cards, ('zone', 'visibility'))).values()), 'expected': sum(backs.values())},
        'exact_card_inventory': bool(raw) and
            counts(cards, ('zone', 'rank', 'suit', 'visibility')) ==
            counts(expected.cards, ('zone', 'rank', 'suit', 'visibility')),
        'phase_correct': raw.get('p') == expected.phase,
        'controls_correct': isinstance(raw.get('a'), list) and sorted(raw['a']) == sorted(expected.controls),
        'scope': 'Diagnostic transcription only; cannot make rejected full state usable'}


def evaluate_saved(result, truth, frame, store):
    text = None
    if result['retention']['retained']:
        text = store.read(result['retention']['record_id'])['output_text']
        if sha256(text.encode()).hexdigest() != result['output_sha256']:
            raise PermissionError('Protected response hash changed.')
    try:
        observation = LiveObservation.model_validate_json(text).model_dump() if text else None
    except ValidationError:
        observation = None
    common = score(observation, truth, status=result['status'], elapsed_ms=result['total_through_validation_ms'])
    semantic = semantic_score(observation, truth, status=result['status'],
        elapsed_ms=result['total_through_validation_ms'], available_views={name for name, _ in frame.images()})
    return {**common, **semantic, 'component_transcription': transcription_components(text or '', truth),
        'eligible_for_advisor': False, 'evidence_scope': 'New consumed-case diagnostic control; not independent accuracy'}


def ordered_collection(collect, record):
    for cell in ORDER:
        result = collect(cell)
        record(cell, result)
        # A known HTTP400 is a request-form outcome for this cell, never a retry
        # of it. Continue only to another already frozen cell; retain its entire
        # unknown-charge reservation. Auth/quota/audit/storage failures stop.
        request_form_rejection = (result.get('error_type') == 'provider_http_rejection' and
            result.get('transport', {}).get('http_status') == 400 and
            result.get('retention', {}).get('reason') == 'no_complete_observation_received')
        if result['stop_before_next_request'] and not request_form_rejection:
            raise PermissionError('Access/accounting/protected-retention failure; no next request.')


def run(external_hash):
    if file_hash(OUTPUT/'freeze.json') != external_hash:
        raise PermissionError('Execution freeze checksum changed.')
    freeze = json.loads((OUTPUT/'freeze.json').read_text())
    if (freeze['epoch'] != EPOCH or freeze['order'] != list(ORDER) or freeze['price_check'] != PRICE_CHECK or
            datetime.now(timezone.utc).date().isoformat() != PRICE_CHECK['verified_utc_date'] or
            any(file_hash(ROOT/name) != digest for name, digest in freeze['sources'].items())):
        raise PermissionError('Execution scope/source/current-price check failed.')
    frames, before, policy = prerequisites()
    original_matrix = MATRIX.read_bytes()
    old_entries = deepcopy(json.loads(CANONICAL_LEDGER.read_text())['entries'])
    claim(OUTPUT/'execution.claim.json', {'epoch': EPOCH, 'freeze_sha256': external_hash,
        'count': 5, 'retry': 0, 'max_reserved_usd': str(MAX_BATCH_USD)})
    rows, transports, access = [], [], None
    stop = None; amended = False; initialization = {}
    try:
        started = time.monotonic_ns(); store = PrivateObservationStore(ROOT)
        probe = {'output_text': '{}', 'provenance': {'experiment': 'VISION-029-storage-preflight'}, 'diagnosis': {}}
        receipt = store.write(probe)
        if store.read(receipt['record_id']) != probe:
            raise PermissionError('Protected storage preflight failed.')
        initialization['storage_preflight_ms'] = (time.monotonic_ns()-started)/1e6
        key = load_key()
        started = time.monotonic_ns(); dns = resolve_scope()
        initialization['dns_ms'] = (time.monotonic_ns()-started)/1e6
        budget = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID, max_requests=106, max_usd='8')
        first = PersistentScopedTransport(provider='gemini', authorization_epoch=EPOCH, budget=budget, dns_scope=dns, api_key=key)
        transports.append(first); metadata = first.metadata()
        exact = (metadata.get('name') == 'models/'+GeminiConfig().model and
            'generateContent' in metadata.get('supportedGenerationMethods', []) and
            metadata.get('inputTokenLimit') == GeminiConfig().context_token_limit and metadata.get('outputTokenLimit', 0) >= 1024)
        access = {'exact_model_and_limits': exact, 'http_status': 200, 'timing': dict(first.timings)}
        if not exact or snapshot() != before or MATRIX.read_bytes() != original_matrix:
            raise PermissionError('Read-only preflight failed or state changed.')
        budget = budget.extend_request_ceiling(max_requests=111, authorization_epoch=EPOCH,
            authorization_note='Human 2026-10-08 continue after prepared five Gemini controls: only A-E, <=USD1.5856640 reservation, no retry/hybrid; unchanged USD8 and every previous charge/reserve.')
        amended = True
        set_policy({**policy, 'inference_authorized': True, 'authorization_epoch': EPOCH,
            'max_requests': 5, 'max_usd': str(MAX_BATCH_USD),
            'scope': 'Only PR22 frozen A-E diagnostics, max10s, never advisor, no retry/warm-up/hybrid.'})
        truths = json.loads((PREPARED/'inputs/oracle.json').read_text())
        def collect(cell):
            if any(time.monotonic()+10 >= entry['expires_at'] for entry in dns.values()):
                raise PermissionError('Original DNS scope cannot admit the next diagnostic deadline.')
            row, frame, payload = frames[cell]
            transport = first if cell == 'A' else PersistentScopedTransport(provider='gemini',
                authorization_epoch=EPOCH, budget=budget, dns_scope=dns, api_key=key)
            if cell != 'A': transports.append(transport)
            transport.budget = budget
            reader = FrozenRequestReader(frame, payload, row['payload']['canonical_sha256'], budget, transport)
            transport.bind(row['payload']['canonical_sha256'], OUTPUT/(cell+'.submission.claim.json'))
            scope = OwnedOutputScope('VISION-029', cell, 'gemini', reader.config.model,
                row['payload']['canonical_sha256'], tuple(sha256(p).hexdigest() for _, p in frame.images()), True)
            result = OfflineResponseCollector(reader, store, scope).collect(frame)
            result.update(cell=cell, mode=row['mode'], available_views=row['available_views'])
            save(OUTPUT/(cell+'.collector.json'), result)
            try:
                result['evaluation'] = evaluate_saved(result, truths[cell], frame, store)
            except Exception as exc:
                result.update(evaluation=None, evaluation_error_type=type(exc).__name__, stop_before_next_request=True)
            return result
        def record(cell, result):
            rows.append(result); save(OUTPUT/'results.json', rows)
            print(json.dumps({'cell': cell, 'status': result['status'], 'complete_ms': round(result['total_through_validation_ms'], 3),
                'content': result['content_diagnosis']['category'], 'retained': result['retention']['retained'],
                'correct_usable_content': (result.get('evaluation') or {}).get('semantic_correct_usable_r1'),
                'timely': result['within_unchanged_live_boundary'], 'advisor': False}), flush=True)
        ordered_collection(collect, record)
    except Exception as exc:
        stop = {'exception_types': exception_types(exc), 'raw_message_saved': False}
    finally:
        MATRIX.write_bytes(original_matrix)
        for transport in transports: transport.close()
        after = snapshot()
        prior_preserved = json.loads(CANONICAL_LEDGER.read_text())['entries'][:106] == old_entries
        consumed = after['receipt']['requests_attempted']-106
        save(OUTPUT/'summary.json', {'experiment': 'VISION-029', 'rows': rows, 'access': access,
            'initialization': initialization, 'attempted_diagnostics': len(rows), 'new_reservations': consumed,
            'maximum_inferences': 5, 'count_amendment_executed': amended, 'unused_slots_closed': 5-consumed,
            'ledger_before': before, 'ledger_after': after, 'all_106_historical_entries_unchanged': prior_preserved,
            'runtime_disarmed': MATRIX.read_bytes() == original_matrix, 'pools_closed': all(t._closed for t in transports),
            'no_automatic_resumption': True, 'advisor_connected': False, 'champion_promoted': False,
            'hybrid_requests': 0, 'retries': 0, 'paid_warmup': 0, 'p95': None,
            'price_check': PRICE_CHECK, 'freeze_sha256': external_hash, 'prepared_sha256': PREPARED_SHA, 'stop': stop})
    return json.loads((OUTPUT/'summary.json').read_text())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--freeze-sha256')
    args = parser.parse_args()
    if args.prepare and args.run:
        parser.error('Preparation and execution are separate.')
    if args.run:
        if not args.freeze_sha256: parser.error('External execution freeze hash required.')
        result = run(args.freeze_sha256)
        print(json.dumps({k: result[k] for k in ('attempted_diagnostics', 'runtime_disarmed', 'stop')}))
    elif args.prepare:
        prepare(); print(json.dumps({'prepared': True, 'inferences': 0, 'execution_freeze_sha256': file_hash(OUTPUT/'freeze.json')}))
    else:
        prerequisites(); print(json.dumps({'offline_preconditions_valid': True, 'inferences': 0}))
