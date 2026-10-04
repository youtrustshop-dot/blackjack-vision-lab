"""Bounded OpenAI R1 tournament on frozen, reviewed native development crops.

Reuses the existing corpus, observation contract, readers and evaluator. This is
not live integration, training, a fresh final test or R2 identity certification.
Credentials are read from the process environment, never from command arguments.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import platform
import sys
import time

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.api_access_policy import require_inference_authorization
from bjlab.corner_vision import CornerCardDetector
from bjlab.openai_reader import ModelConfig, OpenAIVisionReader, ResponsesTransport
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from bjlab.specialized_vision import SpecializedCardDetector
from bjlab.state_reader import HandObservation, ObservedCard, ReaderResult, analysis_gate, prepare_frame
from bjlab.visible_phase import VisiblePhaseContext
from validation.tools.independent_tournament import scenario_timeline
from validation.tools.state_reader_comparison import load_frame, prepare as prepare_provider, read_json, score_state, write_json

AUTHORIZATION_ID = 'card-lab-eur10-total-20261004'
EPOCH = '2026-10-05-openai-native-development-eur10'
LEDGER = CANONICAL_LEDGER
CAP_USD = '8'
MAX_REQUESTS = 90
DEADLINE_MS = 3000
FROZEN_SOURCE = '18bfd579c1913bfa902a096fb8a83477ce510edf'
PERCEPTION_FILES = ('bjlab/corner_vision.py', 'bjlab/ocr.py', 'bjlab/overlap_presence.py',
    'bjlab/suit_symbols.py', 'bjlab/specialized_vision.py', 'bjlab/visible_phase.py',
    'bjlab/state_reader.py', 'bjlab/vision.py', 'bjlab/calibration.py')
RUNNER_FILES = PERCEPTION_FILES + ('bjlab/openai_reader.py', 'bjlab/research_budget.py',
    'validation/tools/state_reader_comparison.py', 'validation/tools/api_reader_tournament.py')


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def config(model='gpt-6-luna', *, fast=False):
    sol = model == 'gpt-6.1-sol'
    if model not in ('gpt-6-luna', 'gpt-6.1-sol') or (sol and fast):
        raise ValueError('Only the declared Luna Standard/Fast and Sol residual comparison is prepared.')
    return ModelConfig(model=model, context_token_limit=1_050_000,
        input_usd_per_million='2' if sol else '.10', output_usd_per_million='10' if sol else '.50',
        cache_write_usd_per_million='2.50' if sol else '.125',
        long_context_threshold=272_000, long_input_multiplier='2', long_output_multiplier='1.5',
        max_output_tokens=2048 if sol else 1024, timeout_seconds=DEADLINE_MS/1000,
        detail='high', reasoning_effort='low' if sol else 'none', service_tier='fast' if fast else 'default',
        pricing_source='https://developers.openai.com/api/docs/models/'+model)


def budget(*, initialize=False):
    method = PersistentRequestBudget.initialize if initialize else PersistentRequestBudget
    return method(LEDGER, authorization_id=AUTHORIZATION_ID, max_requests=MAX_REQUESTS, max_usd=CAP_USD)


def native_record(target, identifier, frame, **metadata):
    directory = target/identifier; directory.mkdir()
    images = []
    for name, pixels in frame.images():
        filename = name.replace(':', '-')+'.png'
        (directory/filename).write_bytes(pixels)
        images.append({'name': name, 'file': identifier+'/'+filename, 'sha256': sha256(pixels).hexdigest()})
    return {'id': identifier, 'frame_id': frame.frame_id, 'layout': frame.layout,
        'source_size': frame.source_size, 'table_box': frame.table_box, 'images': images,
        'split': 'development', **metadata}


def select_stage_frames(stages, fps):
    """One midpoint in the first waiting/player/dealer/settled stage per clip.

    The rule is fixed before results. Labels used to select/score frames are never
    included in FrameInput or the API request. All variants share two sessions.
    """
    selected = {}; start = 0
    for stage in stages:
        length = round(stage['duration']*fps)
        if stage['phase'] in ('waiting', 'player', 'dealer', 'settled') and stage['phase'] not in selected:
            selected[stage['phase']] = (start+length//2, stage)
        start += length
    if set(selected) != {'waiting', 'player', 'dealer', 'settled'}:
        raise ValueError('Required predeclared stages are absent.')
    return list(selected.values())


def prepare(manifest_path, provider_manifest, reader_manifest, output):
    source = Path(manifest_path).resolve(); manifest = read_json(source)
    if manifest.get('partition') != 'validation' or manifest.get('kind') != 'own-synthetic-continuous-video':
        raise PermissionError('Only the consumed new-session validation corpus is eligible, never final holdout.')
    target = Path(output).resolve(); target.mkdir(parents=True, exist_ok=False)
    records, oracle = [], {}
    source_receipts = []
    for session in manifest['sessions']:
        paths = {}
        for field in ('video', 'truth'):
            path = (source.parent/session[field]).resolve()
            if not path.is_relative_to(source.parent) or file_hash(path) != session[field+'_sha256']:
                raise ValueError('Frozen source evidence changed or leaves its corpus.')
            paths[field] = path
        truth = read_json(paths['truth'])
        selections = select_stage_frames(scenario_timeline(session['seed']), manifest['fps'])
        capture = cv2.VideoCapture(str(paths['video']))
        try:
            for number, (index, stage) in enumerate(selections):
                row = truth[index]
                if row['frame'] != index or row['phase'] != stage['phase']:
                    raise ValueError('Timeline and frozen truth disagree.')
                capture.set(cv2.CAP_PROP_POS_FRAMES, index); ok, pixels = capture.read()
                if not ok:
                    raise ValueError('Frozen video frame could not be decoded.')
                image = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
                frame = prepare_frame(image, manifest['layout'])
                identifier = 'synthetic-'+session['name']+'-s'+str(number)
                records.append(native_record(target, identifier, frame,
                    evidence_kind='consumed-synthetic-development', family=session['group'],
                    physical_session=str(session['seed']), condition=session['profile'],
                    source_frame=index, timestamp_ms=row['timestamp_ms']))
                cards = [{'zone': c['zone'], 'visibility': c['presence'], 'rank': c['rank'], 'suit': c['suit']}
                    for c in row['cards'] if c['presence'] != 'absent_from_pixels']
                oracle[identifier] = {'cards': cards, 'table_state': 'cards_present' if cards else 'empty',
                    'phase': stage['phase'], 'controls': sorted(stage['controls']),
                    'player_total': None, 'dealer_total': None,
                    'annotation_review': 'Renderer top-index visibility-mask proxy; not independent human truth. No displayed card totals.',
                    'independent_session': False}
        finally:
            capture.release()
        source_receipts.append({k: session[k] for k in ('name', 'video_sha256', 'truth_sha256')})
    # Existing importer keeps private desktop surroundings out of native table
    # and role crops; historical phase/controls/totals remain unannotated.
    provider_root = target/'provider'; prepare_provider(provider_manifest, provider_root)
    provider_doc = read_json(provider_root/'frames.json'); provider_oracle = read_json(provider_root/'oracle.json')
    for record in provider_doc['frames']:
        original = record['id']; record['id'] = 'provider-'+original
        record.update(evidence_kind='consumed-provider-development', family='brainplay' if 'brainplay' in original else 'freegames',
            physical_session='historical-moment-brainplay' if 'brainplay' in original else 'historical-moment-freegames', condition='historical')
        for item in record['images']:
            item['file'] = 'provider/'+item['file']
        records.append(record); oracle[record['id']] = provider_oracle[original]
    write_json(target/'frames.json', {'schema': 1, 'scope': 'R1 development comparison; native crops only', 'frames': records})
    write_json(target/'oracle.json', oracle)
    model_configs = {'luna-standard': asdict(config()), 'luna-fast': asdict(config(fast=True)),
        'sol-residual': asdict(config('gpt-6.1-sol'))}
    write_json(target/'configuration.json', {'schema': 1, 'models': model_configs, 'deadline_ms': DEADLINE_MS,
        'fast_sample_rule': 'First player sample of each of 12 paired clips plus all 3 provider stills; Standard runs on every input first.',
        'sol_rule': 'At most three Standard failures, provider-first then manifest order; post-hoc diagnostic hard cases, not independent accuracy.',
        'hybrid_rule': 'Evaluate A->Luna and B->Luna separately; route only on the local player-turn integrity gate, never on oracle correctness.',
        'p95_target_ms': 2500, 'live_and_shoe_certified': False})
    write_json(target/'freeze.json', {'schema': 1, 'frozen_perception_commit': FROZEN_SOURCE,
        'prepared_sha256': file_hash(target/'frames.json'), 'oracle_sha256': file_hash(target/'oracle.json'),
        'configuration_sha256': file_hash(target/'configuration.json'),
        'reader_manifest': str(Path(reader_manifest).resolve()), 'reader_manifest_sha256': file_hash(reader_manifest),
        'source_session_manifest_sha256': file_hash(source), 'provider_manifest_sha256': file_hash(provider_manifest),
        'source_receipts': source_receipts, 'source_hashes': {p: file_hash(ROOT/p) for p in RUNNER_FILES},
        'physical_synthetic_sessions': 2, 'paired_renderings': 12, 'provider_moments': 2,
        'private_images': True, 'historical_final_holdout': 'sealed_untouched', 'new_training': False})
    write_json(target/'upload-review.json', {'approved': False,
        'prepared_manifest_sha256': file_hash(target/'frames.json'),
        'image_sha256': sorted({i['sha256'] for r in records for i in r['images']}),
        'notes': ['Agent must inspect every prepared table/detail crop before approval.',
            'User authorized reviewed synthetic/provider-development inputs; never raw desktops or monitor photographs.']})
    receipt = budget(initialize=True).receipt()
    return {'prepared_inputs': len(records), 'synthetic_inputs': len(records)-len(provider_doc['frames']),
        'provider_inputs': len(provider_doc['frames']), 'uploads': 0, 'budget': receipt}


def checked_inputs(directory):
    directory = Path(directory); freeze = read_json(directory/'freeze.json')
    for field, name in (('prepared_sha256', 'frames.json'), ('oracle_sha256', 'oracle.json'),
                        ('configuration_sha256', 'configuration.json')):
        if file_hash(directory/name) != freeze[field]:
            raise ValueError('Frozen input/configuration/evaluator truth changed.')
    if any(file_hash(ROOT/p) != expected for p, expected in freeze['source_hashes'].items()):
        raise ValueError('Frozen reader/evaluator source changed; no silent tuning.')
    if file_hash(freeze['reader_manifest']) != freeze['reader_manifest_sha256']:
        raise ValueError('Specialized reader changed after freeze.')
    records = read_json(directory/'frames.json')['frames']
    if len({r['id'] for r in records}) != len(records):
        raise ValueError('Repeated case identifiers.')
    return freeze, [(r, load_frame(directory, r)) for r in records], read_json(directory/'oracle.json')


class FrozenLocalObservation:
    def __init__(self, *, specialized_manifest=None):
        self.specialized_manifest = specialized_manifest
        self.name = 'specialized-local' if specialized_manifest else 'current-local'
        self.detector = SpecializedCardDetector(specialized_manifest) if specialized_manifest else None

    def read(self, frame):
        began = time.perf_counter(); image = Image.open(BytesIO(frame.table_png)).convert('RGB')
        detector = self.detector or CornerCardDetector(frame.layout)
        detector.layout = frame.layout
        detections = detector.detect(image); diagnostics = dict(detector.last_diagnostics)
        reasons = list(detector.context.get('reasons', [])); rejected = diagnostics.get('rejected_card_candidates', 0)
        phase, controls = 'unknown', []
        if 'controls' in frame.layout:
            context = VisiblePhaseContext(frame.layout, overlap_challenger=True)
            if not self.specialized_manifest:
                detections, evidence = context.covered_presence(image, detections)
                rejected = max(0, rejected-sum(e['covered'] and e.get('resolved_body_rejection', True) for e in evidence))
            visible = context.read(image, detections)
            reasons.extend(visible['reasons']); diagnostics['visible_context'] = visible
            phase = visible['phase'] if visible['phase'] != 'dealing' else 'unknown'
            controls = sorted(set(visible['controls']) & {'hit', 'stand', 'double', 'split', 'surrender'})
        if rejected:
            reasons.append('Unresolved local proposals; card presence is not established for each proposal.')
        observation = HandObservation(cards=[ObservedCard(zone=d.zone, rank=d.rank, suit=d.suit,
            visibility=d.visibility) for d in detections], table_state='cards_present' if detections else 'empty' if phase == 'waiting' else 'uncertain',
            phase=phase, controls=controls, player_total=None, dealer_total=None,
            unknown_fields=['displayed totals']+(['phase'] if phase == 'unknown' else []), blockers=reasons)
        return ReaderResult(frame.frame_id, self.name, 'completed', observation, (time.perf_counter()-began)*1000, diagnostics)


def measurement(record, result, truth):
    score = score_state(result.observation, truth)
    observation = result.observation
    # Enabled-control order carries no semantic meaning; the legacy still
    # evaluator compares lists. Normalize only in this tournament evaluation.
    if score['complete_state_annotated'] and observation:
        score['complete_state_correct'] = (score['full_card_state_correct'] and
            all(getattr(observation, k) == truth[k] for k in ('table_state', 'phase', 'player_total', 'dealer_total')) and
            set(observation.controls) == set(truth['controls']))
    expected_ranks = Counter((c['zone'], c['rank']) for c in truth['cards'] if c['rank'] is not None)
    predicted_ranks = Counter((c.zone, c.rank) for c in observation.cards if c.rank is not None) if observation else Counter()
    score.update(readable_ranks_expected=sum(expected_ranks.values()),
        readable_ranks_matched=sum((expected_ranks & predicted_ranks).values()),
        phase_correct=(observation is not None and observation.phase == truth['phase']) if truth.get('phase') is not None else None)
    gate = analysis_gate(observation, require_turn=True) if observation else {'usable': False, 'reasons': [result.status]}
    timely = result.status == 'completed' and result.elapsed_ms <= DEADLINE_MS
    correct_player = score['rank_presence_state_correct'] and truth.get('phase') == 'player'
    return {'case_id': record['id'], 'family': record['family'], 'condition': record['condition'],
        'evidence_kind': record['evidence_kind'], 'reader': result.reader, 'status': result.status,
        'annotated_player_opportunity': truth.get('phase') == 'player',
        'elapsed_ms': result.elapsed_ms, 'timely': timely, 'metrics': score, 'gate': gate,
        'correct_timely_player_state': bool(timely and gate['usable'] and correct_player),
        'false_accepted_player_state': bool(gate['usable'] and truth.get('phase') is not None and not correct_player),
        'accepted_provider_rank_error': bool('provider' in record['evidence_kind'] and gate['usable'] and not score['rank_presence_state_correct']),
        'unverifiable_provider_turn_acceptance': bool('provider' in record['evidence_kind'] and gate['usable'] and truth.get('phase') is None),
        'observation': observation.model_dump() if observation else None, 'diagnostics': result.diagnostics}


def summarize(rows):
    by_reader = {}
    for reader in sorted({r['reader'] for r in rows}):
        part = [r for r in rows if r['reader'] == reader]
        completed = [r for r in part if r['status'] == 'completed']
        annotated = [r for r in part if r['metrics']['complete_state_annotated']]
        billed = [r['diagnostics'].get('price_based_upper_cost_usd') for r in part]
        by_reader[reader] = {'planned_inputs': len(part), 'completed': len(completed),
            'timeouts': sum(r['status'] == 'timeout' for r in part),
            'not_executed': sum(r['status'] == 'not_executed' for r in part),
            'reader_failures': sum(r['status'] not in ('completed', 'not_executed') for r in part),
            'not_usable_as_player_advice': sum(r['status'] != 'completed' or not r['gate']['usable'] for r in part),
            'rank_presence_states_correct': sum(r['metrics']['rank_presence_state_correct'] for r in part),
            'complete_state_denominator': len(annotated),
            'complete_states_correct': sum(r['metrics']['complete_state_correct'] is True for r in annotated),
            'ranks_correct': sum(r['metrics']['readable_ranks_matched'] for r in part),
            'ranks_expected': sum(r['metrics']['readable_ranks_expected'] for r in part),
            'suits_correct': sum(r['metrics']['known_suits_correct'] for r in part),
            'suits_expected': sum(r['metrics']['known_suits_expected'] for r in part),
            'phase_correct': sum(r['metrics']['phase_correct'] is True for r in part),
            'phase_denominator': sum(r['metrics']['phase_correct'] is not None for r in part),
            'correct_timely_player_states': sum(r['correct_timely_player_state'] for r in part),
            'annotated_player_opportunity_denominator': sum(r['annotated_player_opportunity'] for r in part),
            'false_accepted_player_states': sum(r['false_accepted_player_state'] for r in part),
            'accepted_provider_rank_errors': sum(r['accepted_provider_rank_error'] for r in part),
            'unverifiable_provider_turn_acceptances': sum(r['unverifiable_provider_turn_acceptance'] for r in part),
            'completed_latency_ms': {q: float(np.percentile([r['elapsed_ms'] for r in completed], p)) if completed else None
                for q, p in (('p50', 50), ('p95', 95), ('max', 100))},
            'reported_usage_upper_cost_usd': str(sum((Decimal(v) for v in billed if v is not None), Decimal(0))) if any(v is not None for v in billed) else None,
            'latency_scope': 'prepared input to complete validated observation, including crop encoding; capture/display excluded',
            'censoring_note': 'Latency percentiles condition on completed results; timeouts/unexecuted stay in correctness denominators. No 2.5s claim from successful requests alone.'}
    return by_reader


def local(directory, output):
    freeze, inputs, oracle = checked_inputs(directory)
    readers = [FrozenLocalObservation(), FrozenLocalObservation(specialized_manifest=freeze['reader_manifest'])]
    rows = []
    for record, frame in inputs:
        for reader in readers:
            began = time.perf_counter()
            try:
                result = reader.read(frame)
            except Exception as exc:
                result = ReaderResult(frame.frame_id, reader.name, 'error', None,
                    (time.perf_counter()-began)*1000, {'error_type': type(exc).__name__})
            rows.append(measurement(record, result, oracle[record['id']]))
    write_json(output, {'schema': 1, 'prepared_manifest_sha256': freeze['prepared_sha256'],
        'source_hashes': freeze['source_hashes'], 'rows': rows, 'readers': summarize(rows),
        'assistance': 'Same initial role/control calibration; frozen current-pixel context, fresh context per still; no temporal truth.'})
    return {'readers': summarize(rows), 'api_requests': 0}


def approval_check(directory, freeze, inputs):
    review = read_json(Path(directory)/'upload-review.json')
    if review.get('approved') is not True or review.get('prepared_manifest_sha256') != freeze['prepared_sha256']:
        raise PermissionError('Exact native crops have not been reviewed.')
    if review.get('spending_authorization_epoch') != EPOCH or review.get('configuration_sha256') != freeze['configuration_sha256']:
        raise PermissionError('Crop/configuration spending scope changed.')
    expiry = datetime.fromisoformat(review['expires_utc'])
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise PermissionError('Reviewed-crop permission expired.')
    allowed = set(review['image_sha256'])
    if allowed != {i['sha256'] for r, _ in inputs for i in r['images']}:
        raise PermissionError('Reviewed hashes do not match every exact input.')
    return allowed


def hybrid_rows(local_rows, api_rows):
    api = {r['case_id']: r for r in api_rows}
    result = []
    for original in local_rows:
        if original['gate']['usable']:
            row = dict(original)
        else:
            row = dict(api[original['case_id']])
            row['elapsed_ms'] += original['elapsed_ms']
            row['timely'] = row['status'] == 'completed' and row['elapsed_ms'] <= DEADLINE_MS
            row['correct_timely_player_state'] = row['correct_timely_player_state'] and row['timely']
            row['diagnostics'] = {}  # API charges already reported once, not billed again by offline routing
        if not row['timely']:
            row['gate'] = {'usable': False, 'reasons': ['Combined local/API deadline expired or no current observation.']}
            row['observation'] = None
            row['correct_timely_player_state'] = False
            row['false_accepted_player_state'] = False
            row['accepted_provider_rank_error'] = False
            row['unverifiable_provider_turn_acceptance'] = False
        row['reader'] = original['reader']+'->luna-standard'
        result.append(row)
    return result


def run(directory, local_result, output):
    freeze, inputs, oracle = checked_inputs(directory)
    allowed = approval_check(directory, freeze, inputs)
    epoch = require_inference_authorization(EPOCH)
    ceiling = budget()
    transport = ResponsesTransport(authorization_epoch=epoch, budget=ceiling)
    available = set(transport.available_models())  # read-only, no inference or paid access probe
    local_doc = read_json(local_result)
    if local_doc['prepared_manifest_sha256'] != freeze['prepared_sha256'] or local_doc['source_hashes'] != freeze['source_hashes']:
        raise ValueError('Local comparison is not from these exact frozen inputs/readers.')
    models = read_json(Path(directory)/'configuration.json')['models']
    target = Path(output); target.mkdir(parents=True, exist_ok=False)
    # A second output path must not silently repeat a charged benchmark.
    with (Path(directory)/'execution-claim.json').open('x', encoding='utf-8') as handle:
        json.dump({'epoch': epoch, 'created_utc': datetime.now(timezone.utc).isoformat()}, handle)
    all_rows, standard_rows = [], []
    account_stop = None
    for label in ('luna-standard', 'luna-fast', 'sol-residual'):
        model = ModelConfig(**models[label])
        if label == 'luna-standard':
            selected = inputs
        elif label == 'luna-fast':
            selected = [(r, f) for r, f in inputs if r['evidence_kind'].startswith('consumed-provider') or
                (r['id'] in oracle and oracle[r['id']].get('phase') == 'player')]
        else:
            residual = {r['case_id'] for r in standard_rows if not r['metrics']['rank_presence_state_correct'] or
                (r['metrics']['complete_state_annotated'] and r['metrics']['complete_state_correct'] is not True)}
            selected = sorted([(r, f) for r, f in inputs if r['id'] in residual],
                key=lambda item: (not item[0]['evidence_kind'].startswith('consumed-provider'), item[0]['id']))[:3]
        reader = OpenAIVisionReader(model, ceiling, allowed, transport=transport)
        stage_stop = 'model_not_available' if model.model not in available else account_stop
        for record, frame in selected:
            if stage_stop:
                value = ReaderResult(frame.frame_id, label, 'not_executed', None, 0., {'reason': stage_stop})
            else:
                value = reader.read(frame); value.reader = label
                if value.status == 'blocked':
                    stage_stop = 'aggregate_budget_or_authorization_blocked'
                status_code = value.diagnostics.get('http_status')
                if status_code in (401, 403, 429):
                    account_stop = stage_stop = 'account_access_or_quota_blocked_http_'+str(status_code)
                elif status_code in (400, 404):
                    stage_stop = 'configuration_unavailable_http_'+str(status_code)
            row = measurement(record, value, oracle[record['id']]); all_rows.append(row)
            if label == 'luna-standard': standard_rows.append(row)
            write_json(target/'private-results.json', {'schema': 1, 'rows': all_rows, 'budget': ceiling.receipt()})
            print(json.dumps({'stage': label, 'completed_inputs': len([r for r in all_rows if r['reader'] == label]),
                'status': value.status, 'elapsed_ms': round(value.elapsed_ms), 'budget': ceiling.receipt()}), flush=True)
    hybrids = hybrid_rows(local_doc['rows'], standard_rows)
    paired = {}
    for label in ('luna-fast', 'sol-residual'):
        subset = [r for r in all_rows if r['reader'] == label]
        ids = {r['case_id'] for r in subset}
        paired[label] = {'inputs': len(ids),
            'readers': summarize([r for r in standard_rows if r['case_id'] in ids]+subset),
            'scope': 'Same exact sample, reused Standard measurements; not additional API requests.'}
    summary = {'schema': 1, 'scope': 'Consumed R1 development comparison; static observations, no provider/R2/live certification',
        'prepared_manifest_sha256': freeze['prepared_sha256'], 'oracle_sha256': freeze['oracle_sha256'],
        'configuration_sha256': freeze['configuration_sha256'], 'source_hashes': freeze['source_hashes'],
        'readers': summarize(local_doc['rows']+all_rows+hybrids), 'budget': ceiling.receipt(),
        'paired_api_comparisons': paired,
        'by_domain': {domain: summarize([r for r in local_doc['rows']+all_rows+hybrids if
            ('provider' in r['evidence_kind']) == (domain == 'provider')]) for domain in ('synthetic', 'provider')},
        'api_requests_executed': ceiling.receipt()['requests_attempted'],
        'gemini': 'not_executed_no_credential_user_requested_openai_first',
        'account_balance_and_invoice': 'unverified; no purchase/recharge/payment changes',
        'hybrid_evidence': 'Offline routing replay of separate attempts, not measured live hybrid latency or extra API calls. Conservative sum of local and API times; expire late evidence.',
        'sampling': {'synthetic_physical_sessions': 2, 'paired_renderings': 12, 'provider_moments': 2,
            'provider_inputs': 3, 'independent_provider_sessions': 0,
            'unique_frame_ids': len({f.frame_id for _, f in inputs}), 'planned_inputs': len(inputs),
            'repeated_exact_inputs': len(inputs)-len({f.frame_id for _, f in inputs})},
        'selection': 'No final holdout, local tuning, training or promotion during this comparison.',
        'hardware': {'os': platform.system(), 'processor': platform.processor(), 'local_device': 'CPU'},
        'decision': 'Research comparison only; independent validation required before promotion.'}
    write_json(target/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--sessions', required=True)
    p.add_argument('--providers', required=True); p.add_argument('--reader', required=True); p.add_argument('--output', required=True)
    p = commands.add_parser('local'); p.add_argument('--prepared', required=True); p.add_argument('--output', required=True)
    p = commands.add_parser('run'); p.add_argument('--prepared', required=True); p.add_argument('--local-result', required=True); p.add_argument('--output', required=True)
    commands.add_parser('access')
    args = parser.parse_args()
    try:
        if args.command == 'prepare': value = prepare(args.sessions, args.providers, args.reader, args.output)
        elif args.command == 'local': value = local(args.prepared, args.output)
        elif args.command == 'access':
            available = set(ResponsesTransport().available_models())
            value = {'openai_credential_usable': True, 'available_requested_models': sorted(available & {'gpt-6-luna', 'gpt-6.1-sol'}),
                'inference_requests': 0, 'balance_and_invoice': 'unverified'}
        else: value = run(args.prepared, args.local_result, args.output)
        print(json.dumps(value, indent=2, allow_nan=False))
    except Exception as exc:
        # Never echo provider bodies, environment values, private pixels or keys.
        print(json.dumps({'status': 'blocked', 'error_type': type(exc).__name__}))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
