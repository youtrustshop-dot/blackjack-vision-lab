"""Prepare private native crops, then compare R1 readers on identical pixels.

Outputs remain local. No image upload occurs without an exact crop/config
authorization file, an available model and a bounded request/spend reservation.
This CLI never changes the application's live timeouts or installed release.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time
import platform

from PIL import Image
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bjlab.state_reader import FrameInput, ReaderResult, LocalVisionReader, analysis_gate, image_analysis, prepare_frame
from bjlab.openai_reader import ModelConfig, OpenAIVisionReader, RequestBudget, ResponsesTransport
from bjlab.engine import Rules
from bjlab.vision_diagnostics import candidate_revision
from bjlab.api_access_policy import require_inference_authorization


def digest(data):
    return sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def prepare(manifest, output):
    """Geometry only to the reader; historical annotations stay in an oracle file."""
    cases = [c for c in read_json(manifest)['cases'] if c['input_kind'] == 'digital-screenshot']
    ids = [c['id'] for c in cases]
    if not cases or len(set(ids)) != len(ids) or any(not re.fullmatch(r'[a-zA-Z0-9_-]+', i) for i in ids):
        raise ValueError('Nonempty unique safe case IDs are required.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    frames, oracle, review = [], {}, []
    for case in cases:
        if case['split'] != 'development':
            raise ValueError('Historical screenshot import is development-only.')
        with Image.open(case['source_file']) as image:
            frame = prepare_frame(image, case['layout'])
        directory = output / case['id']
        directory.mkdir()
        images = []
        for name, encoded in frame.images():
            filename = name.replace(':', '-')+'.png'
            (directory/filename).write_bytes(encoded)
            images.append({'name': name, 'file': case['id']+'/'+filename, 'sha256': digest(encoded)})
        frames.append({'id': case['id'], 'frame_id': frame.frame_id, 'layout': frame.layout,
                       'source_size': frame.source_size, 'table_box': frame.table_box, 'images': images,
                       'split': 'development', 'evidence_kind': 'consumed-regression'})
        oracle[case['id']] = {'cards': [{'zone': c['zone'], 'rank': c['rank'], 'suit': c['suit'],
            'visibility': 'covered' if c.get('face_down') else 'readable' if c['rank'] else 'unreadable'}
            for c in case.get('cards', [])], 'phase': None,
            'annotation_review': 'historical assistant review, not independent human truth',
            'independent_session': False}
        review.append({'id': case['id'], 'source_size': frame.source_size, 'table_box': frame.table_box,
                       'images': images})
    write_json(output/'frames.json', {'schema': 1, 'scope': 'private R1 development regressions', 'frames': frames})
    write_json(output/'oracle.json', oracle)
    write_json(output/'upload-review.json', {'approved': False, 'frames': review,
        'notes': ['Review every prepared crop. No API upload has occurred.',
                  'Freegames original and preview are the same moment, not independent evidence.',
                  'Phase annotations are absent: complete-state accuracy cannot be claimed.']})
    return {'prepared': len(frames), 'uploads': 0, 'scope': 'consumed development regressions'}


def load_frame(directory, record):
    images = []
    root = Path(directory).resolve()
    for item in record['images']:
        path = (root/item['file']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Prepared image leaves its experiment directory.')
        data = path.read_bytes()
        if digest(data) != item['sha256']:
            raise ValueError('Prepared image hash changed.')
        images.append((item['name'], data))
    if not images or images[0][0] != 'table' or len(set(n for n, _ in images)) != len(images):
        raise ValueError('One table context and unique native details are required.')
    return FrameInput(record['frame_id'], images[0][1], tuple(images[1:]), record['layout'],
                      tuple(record['source_size']), tuple(record['table_box']))


def score_state(observation, truth):
    expected = Counter((c['zone'], c['visibility'], c['rank']) for c in truth['cards'])
    predicted = Counter((c.zone, c.visibility, c.rank) for c in observation.cards) if observation else Counter()
    missed, extra = sum((expected-predicted).values()), sum((predicted-expected).values())
    rank_correct = observation is not None and missed == 0 and extra == 0
    full_expected = Counter((c['zone'], c['visibility'], c['rank'], c['suit']) for c in truth['cards'])
    full_predicted = Counter((c.zone, c.visibility, c.rank, c.suit) for c in observation.cards) if observation else Counter()
    known_expected = Counter((c['zone'], c['visibility'], c['rank'], c['suit'])
        for c in truth['cards'] if c['suit'] is not None)
    correct_suits = sum((known_expected & full_predicted).values())
    unknown_suits = sum(c.suit is None and c.visibility == 'readable' for c in observation.cards) if observation else 0
    phase_known = truth.get('phase') is not None
    state_fields = ('table_state', 'phase', 'controls', 'player_total', 'dealer_total')
    complete_annotated = phase_known and all(field in truth for field in state_fields)
    complete = (full_expected == full_predicted and observation is not None and
                all(getattr(observation, field) == truth[field] for field in state_fields)) if complete_annotated else None
    return {'rank_presence_state_correct': rank_correct, 'missed_or_wrong_objects': missed,
            'extra_or_wrong_objects': extra, 'full_card_state_correct': observation is not None and full_expected == full_predicted,
            'known_suits_correct': correct_suits, 'known_suits_expected': sum(known_expected.values()),
            'readable_suits_unknown': unknown_suits,
            'complete_state_correct': complete, 'phase_annotated': phase_known,
            'complete_state_annotated': complete_annotated}


def authorize(approval, records, configs, config_hash, prepared_hash):
    if (approval.get('approved') is not True or approval.get('configuration_sha256') != config_hash
            or approval.get('prepared_manifest_sha256') != prepared_hash):
        raise PermissionError('Explicit authorization for this configuration is missing.')
    expiry = datetime.fromisoformat(approval['expires_utc'])
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise PermissionError('Upload authorization expired or has no timezone.')
    required = {i['sha256'] for record in records for i in record['images']}
    allowed = set(approval.get('image_sha256', []))
    if not required <= allowed or set(approval.get('models', [])) != {c.model for c in configs}:
        raise PermissionError('Authorization does not cover the exact crops/models.')
    budget = RequestBudget(approval['max_requests'], approval['max_usd'])
    reservations = sum((c.reserve_usd for c in configs), start=0)*len(records)
    if len(configs)*len(records) > budget.max_requests or reservations > budget.maximum:
        raise PermissionError('Full-context conservative reservations exceed the approved run budget.')
    return budget, allowed


def claim_authorization(directory, approval):
    """One-shot consent, retained after errors; another output path cannot reuse it."""
    authorization_id = approval.get('authorization_id', '')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}', authorization_id):
        raise PermissionError('An explicit unique authorization ID is required.')
    ledger = Path(directory)/'authorization-ledger'
    ledger.mkdir(exist_ok=True)
    try:
        with (ledger/(authorization_id+'.json')).open('x', encoding='utf-8') as handle:
            json.dump({'claimed_utc': datetime.now(timezone.utc).isoformat(),
                       'approval_sha256': digest(json.dumps(approval, sort_keys=True).encode())}, handle)
    except FileExistsError:
        raise PermissionError('This authorization has already been consumed.') from None


def compare(directory, output, *, configuration=None, approval=None):
    directory, output = Path(directory), Path(output)
    manifest_bytes = (directory/'frames.json').read_bytes()
    document = json.loads(manifest_bytes)
    records = document['frames']
    if not records or len({r['frame_id'] for r in records}) != len(records):
        raise ValueError('Empty or repeated exact inputs are not independent benchmark rows.')
    oracle_bytes = (directory/'oracle.json').read_bytes()
    oracle = json.loads(oracle_bytes)
    # Validate every input before network or expensive work; no lazy upload of a changed crop.
    frames = [(r, load_frame(directory, r)) for r in records]
    readers = [LocalVisionReader()]
    configs = []
    budget = None
    if configuration:
        authorization_epoch = require_inference_authorization()
        configuration_bytes = Path(configuration).read_bytes()
        configs = [ModelConfig(**c) for c in json.loads(configuration_bytes)['models']]
        if not 1 <= len(configs) <= 2 or len({c.model for c in configs}) != len(configs):
            raise ValueError('Choose one or two explicit distinct model configurations.')
        if not approval:
            raise PermissionError('The paid API comparison requires a reviewed authorization file.')
        consent = read_json(approval)
        if consent.get('spending_authorization_epoch') != authorization_epoch:
            raise PermissionError('blocked_stale_spending_authorization')
        budget, allowed = authorize(consent, records, configs, digest(configuration_bytes), digest(manifest_bytes))
        transport = ResponsesTransport(authorization_epoch=authorization_epoch)
        available = set(transport.available_models())
        if any(c.model not in available for c in configs):
            raise PermissionError('A configured model is not listed as available to this account.')
        readers.extend(OpenAIVisionReader(c, budget, allowed, transport=transport) for c in configs)
    output.mkdir(parents=True, exist_ok=False)
    if configs:
        claim_authorization(directory, consent)
    rows = []
    for record, frame in frames:
        for reader in readers:
            began = time.perf_counter()
            try:
                result = reader.read(frame)
            except Exception as exc:
                result = ReaderResult(frame.frame_id, reader.name, 'error', None,
                    (time.perf_counter()-began)*1000, {'error_type': type(exc).__name__})
            metrics = score_state(result.observation, oracle[record['id']])
            gate = analysis_gate(result.observation) if result.observation else {'usable': False, 'reasons': [result.status]}
            analysis = image_analysis(result.observation, Rules()) if result.observation else None
            if analysis:
                gate = analysis['gate']
            complete_elapsed_ms = (time.perf_counter()-began)*1000
            rows.append({'case_id': record['id'], 'frame_id': frame.frame_id, 'reader': result.reader,
                'status': result.status, 'elapsed_ms': complete_elapsed_ms, 'reader_elapsed_ms': result.elapsed_ms,
                'timing_scope': 'prepared-input to validated observation and conditional rank analysis; no capture/display',
                'metrics': metrics,
                'rank_study_gate': gate, 'image_analysis': analysis,
                'observation': result.observation.model_dump() if result.observation else None,
                'diagnostics': result.diagnostics, 'evidence_kind': record['evidence_kind']})
            write_json(output/'private-results.json', {'scope': document['scope'], 'rows': rows})
    summaries = {}
    for reader in readers:
        subset = [row for row in rows if row['reader'] == reader.name]
        annotated = [row for row in subset if row['metrics']['complete_state_correct'] is not None]
        useful = sum(row['rank_study_gate']['usable'] and row['metrics']['rank_presence_state_correct'] for row in subset)
        summaries[reader.name] = {'states': len(subset), 'complete_annotated_states': len(annotated),
            'complete_state_accuracy': sum(r['metrics']['complete_state_correct'] for r in annotated)/len(annotated) if annotated else None,
            'complete_correct_usable_states': sum(r['metrics']['complete_state_correct'] is True and r['rank_study_gate']['usable'] for r in subset),
            'rank_presence_states_correct': sum(r['metrics']['rank_presence_state_correct'] for r in subset),
            'correct_usable_rank_study_states': useful,
            'false_accepted_rank_states': sum(r['rank_study_gate']['usable'] and not r['metrics']['rank_presence_state_correct'] for r in subset),
            'full_card_states_correct': sum(r['metrics']['full_card_state_correct'] for r in subset),
            'known_suits_correct': sum(r['metrics']['known_suits_correct'] for r in subset),
            'known_suits_expected': sum(r['metrics']['known_suits_expected'] for r in subset),
            'readable_suits_unknown': sum(r['metrics']['readable_suits_unknown'] for r in subset),
            'states_within_5s': sum(r['status'] == 'completed' and r['elapsed_ms'] <= 5000 for r in subset),
            'failures': sum(r['status'] != 'completed' for r in subset),
            'processing_p50_ms': float(np.percentile([r['elapsed_ms'] for r in subset], 50)),
            'processing_p95_ms': float(np.percentile([r['elapsed_ms'] for r in subset], 95)),
            'sampling_note': 'One attempt per still; tiny consumed corpus, not a live/session latency estimate.',
            'cost_usd': str(sum(Decimal(r['diagnostics']['price_based_cost_usd']) for r in subset))
                        if configs and reader.name.startswith('openai:') and all(r['diagnostics'].get('price_based_cost_usd') is not None for r in subset) else None}
        cost = summaries[reader.name]['cost_usd']
        summaries[reader.name]['cost_per_correct_usable_rank_state_usd'] = str(Decimal(cost)/useful) if cost is not None and useful else None
    root = Path(__file__).resolve().parents[2]
    components = ['bjlab/state_reader.py', 'bjlab/openai_reader.py', 'bjlab/api_access_policy.py',
                  'validation/tools/state_reader_comparison.py', 'bjlab/corner_vision.py',
                  'bjlab/calibration.py', 'bjlab/ocr.py', 'bjlab/suit_symbols.py',
                  'bjlab/engine.py', 'bjlab/advice.py']
    source_hashes = {p: digest((root/p).read_bytes()) for p in components}
    from bjlab.ocr import MODEL_SHA256
    report = {'schema': 1, 'candidate': candidate_revision(Path(__file__).resolve().parents[2]),
              'source_hashes': source_hashes, 'local_ocr_checkpoint_sha256': MODEL_SHA256,
              'prepared_manifest_sha256': digest(manifest_bytes), 'oracle_sha256': digest(oracle_bytes),
              'hardware': {'os': platform.system(), 'machine': platform.machine(), 'processor': platform.processor(), 'local_device': 'CPU'},
              'assistance': 'initial role calibration only; no oracle phase; suits/history unknown remain unknown',
              'configured_rules_for_conditional_study': asdict(Rules()),
              'acceptance': {'scope': 'independent supported R1 verification, not this consumed pilot',
                             'correct_usable_state_fraction': .95, 'false_accepted_states': 0, 'p95_ms': 5000},
              'scope': 'R1 consumed screenshot regression; no independent generalization or live/session claim',
              'readers': summaries, 'api_comparison_executed': bool(configs),
              'api_blockers': [],
              'decision': 'inconclusive', 'original_provider_sessions': 0,
              'budget': budget.receipt() if budget else None}
    # A local report records the active denial, not a stale key-setup assumption.
    # Billing balances and secrets never belong in benchmark reports.
    if not configs:
        try:
            require_inference_authorization()
        except PermissionError as exc:
            report['api_blockers'].append(str(exc))
        report['api_blockers'].append('Account credits/access and exact-crop consent unverified')
    write_json(output/'summary.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--manifest', required=True); p.add_argument('--output', required=True)
    p = commands.add_parser('compare'); p.add_argument('--prepared', required=True); p.add_argument('--output', required=True)
    p.add_argument('--configuration'); p.add_argument('--approval')
    commands.add_parser('list-models')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            report = prepare(args.manifest, args.output)
        elif args.command == 'list-models':
            report = {'available_ids': ResponsesTransport().available_models(), 'vision_support': 'verify model documentation before selection'}
        else:
            report = compare(args.prepared, args.output, configuration=args.configuration, approval=args.approval)
        print(json.dumps(report, indent=2, allow_nan=False))
    except Exception as exc:
        # Validation errors are actionable; secret-bearing transport exceptions are not echoed.
        print(json.dumps({'status': 'blocked', 'error_type': type(exc).__name__}))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
