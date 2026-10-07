"""Prepare five Gemini request ablations OFFLINE; there is no execution command.

Reuses one consumed owned development case and a pixel-only BET-label control.
No key loading, access checks, budget mutations, inference, tuning or holdouts.
The existing reader, schema, gates and collector remain frozen.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageDraw

from bjlab.calibration import NormalizedROI
from bjlab.grounded_cloud import GeminiConfig
from bjlab.hybrid_evidence import frame_fingerprint
from bjlab.live_cloud import DiagnosticReader
from bjlab.live_state import CONTRACT_VERSION
from bjlab.numeric_provenance import POLICY_VERSION, semantic_gate
from bjlab.state_reader import prepare_frame
from validation.tools.api_reader_tournament import native_record
from validation.tools.grounded_corpus import font, save
from validation.tools.paired_cloud_prepare import OfflineOnly, digest
from validation.tools.state_reader_comparison import load_frame

ROOT = Path(__file__).resolve().parents[2]
CASE = 'fresh-rotated-unknown'
SOURCE = ROOT/'artifacts/paired-semantic-hybrid-20261006'
OUTPUT = ROOT/'artifacts/gemini-request-ablation-preparation-20261007-final'
LEDGER = ROOT/'artifacts/api-budget/eur10-total-20261004.json'
PARENT_COMMIT = '6a5e071da76c76b22453d3a4808a209f0ad74bd8'
CELLS = (('A', 'structured-card-limit-local', False, False),
         ('B', 'json-mode', False, False),
         ('C', 'structured-card-limit-local', True, False),
         ('D', 'json-mode', True, False),
         ('E', 'structured-card-limit-local', False, True))
CODE_FILES = ('validation/tools/gemini_request_ablation.py', 'bjlab/hybrid_evidence.py',
    'bjlab/live_cloud.py', 'bjlab/live_state.py', 'bjlab/numeric_provenance.py',
    'bjlab/grounded_state.py', 'bjlab/offline_response_collector.py',
    'validation/tools/numeric_semantic_score.py')


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def native_view_audit(frame):
    """Check supplied native details against the table's decoded crop pixels.

    This is an offline producer/input audit, not inferred card truth, pose or
    a cross-acquisition proof from a fingerprint alone. Empty details are valid.
    """
    names = [name for name, _ in frame.images()]
    if len(names) != len(set(names)) or names[0] != 'table':
        raise ValueError('One table and unique named views are required.')
    with Image.open(BytesIO(frame.table_png)) as raw:
        if raw.width*raw.height > 16_000_000:
            raise ValueError('Native table exceeds the bounded image size.')
        table = raw.convert('RGB')
    x, y, width, height = frame.table_box
    if table.size != (width, height) or x < 0 or y < 0 or (
            x+width > frame.source_size[0] or y+height > frame.source_size[1]):
        raise ValueError('Native table dimensions and source geometry disagree.')
    checked = []
    for name, encoded in frame.details:
        if name not in frame.layout:
            raise ValueError('Detail has no declared native geometry.')
        rx, ry, rw, rh = NormalizedROI(*frame.layout[name]).to_pixels(*table.size)
        with Image.open(BytesIO(encoded)) as raw:
            if raw.width*raw.height > 16_000_000:
                raise ValueError('Native detail exceeds the bounded image size.')
            detail = raw.convert('RGB')
        expected = table.crop((rx, ry, rx+rw, ry+rh))
        if detail.size != expected.size or detail.tobytes() != expected.tobytes():
            raise ValueError('Native detail differs from its same-table crop: '+name)
        checked.append(name)
    return {'status': 'passed', 'checked_details': checked, 'table_size': list(table.size),
        'scope': 'native pixel equivalence, not independent card/label legibility'}


def request_payload(frame, mode):
    """Align thinking/output caps before comparing the two serialization modes."""
    guard = OfflineOnly()
    hashes = [sha256(p).hexdigest() for _, p in frame.images()]
    reader = DiagnosticReader(GeminiConfig(), guard, hashes, provider='gemini',
        variant='live', transport=guard, gemini_output=mode)
    payload = reader.payload(frame)
    if mode == 'json-mode':
        # Explicitly match the existing structured request. No frozen reader edit.
        payload['generationConfig']['thinkingConfig'] = {
            'thinkingLevel': 'MINIMAL', 'includeThoughts': False}
    return payload


def bet_control(frame, truth):
    """Add BET beside the existing unlabelled20 without moving the number."""
    with Image.open(BytesIO(frame.table_png)) as raw:
        image = raw.convert('RGB')
    if frame.table_box != (0, 0, 1024, 768) or frame.source_size != image.size:
        raise ValueError('The reviewed control requires the original full native table.')
    before = image.copy()
    draw = ImageDraw.Draw(image)
    ui_font = font('C:/Windows/Fonts/arialbd.ttf', 25)
    position = (847, 130)
    bounds = draw.textbbox(position, 'BET', font=ui_font, anchor='lt')
    if bounds[2] >= 910:
        raise ValueError('BET would overwrite the original number.')
    draw.text(position, 'BET', font=ui_font, fill='white', anchor='lt')
    # Prove every source pixel outside this new label's box remains identical.
    restored = image.copy(); restored.paste(before.crop(bounds), bounds)
    if restored.tobytes() != before.tobytes():
        raise ValueError('The label control changed unrelated source pixels.')
    changed = deepcopy(truth)
    indexes = [i for i, n in enumerate(changed['numbers'])
        if n['value'] == 20 and n['role'] == 'unknown' and n['label'] is None]
    if len(indexes) != 1:
        raise ValueError('Exactly one reviewed ambiguous number is required.')
    index = indexes[0]
    changed['numbers'][index].update(role='ui', label='BET', view='table')
    number_views = [n for n in changed['number_views']
        if n['value'] == 20 and n['role'] == 'unknown' and n['label'] is None]
    if len(number_views) != 1:
        raise ValueError('The existing number annotation is not unique.')
    # Complete BET+20 is not contained in the clipped dealer crop. Never widen it.
    number_views[0].update(role='ui', label='BET', allowed_views=['table'])
    return prepare_frame(image, frame.layout), changed, {
        'new_label': 'BET', 'label_box_native': list(bounds),
        'original_number_position_unchanged': [910, 130],
        'all_other_table_pixels_unchanged': True,
        'annotation_review': 'owned renderer plus assistant visual audit, not independent human truth'}


def payload_footprint(payload, frame, mode):
    generation = payload['generationConfig']
    system = [part['text'] for part in payload['systemInstruction']['parts']]
    user = [part['text'] for part in payload['contents'][0]['parts'] if 'text' in part]
    return {'views': [n for n, _ in frame.images()],
        'image_bytes': sum(len(p) for _, p in frame.images()),
        'canonical_payload_bytes': len(json.dumps(payload, separators=(',', ':')).encode()),
        'system_text_characters': sum(map(len, system)), 'user_text_characters': sum(map(len, user)),
        'provider_schema_bytes': len(json.dumps(generation['responseFormat']['text']['schema'],
            separators=(',', ':')).encode()) if mode != 'json-mode' else 0,
        'thinking': generation['thinkingConfig'], 'output_token_cap': generation['maxOutputTokens'],
        'tokens_and_provider_timings': 'unmeasured; no submission'}


def prepare(source=SOURCE, output=OUTPUT, ledger=LEDGER):
    source, output, ledger = Path(source), Path(output), Path(ledger)
    budget_bytes = ledger.read_bytes()
    budget = json.loads(budget_bytes)
    prior = json.loads((ROOT/'validation/results/two-provider-diagnostics/freeze.json').read_text())
    if file_hash(source/'freeze.json') != prior['prior_freeze_sha256']:
        raise ValueError('Consumed source freeze changed.')
    records = json.loads((source/'inputs/frames.json').read_text())
    record = next(r for r in records if r['id'] == CASE)
    original = load_frame(source/'inputs', record)
    native_view_audit(original)
    truth = json.loads((source/'inputs/oracle.json').read_text())[CASE]
    snapshot = prior['payloads']['gemini-structured-card-limit-local']
    saved_payload = source/'inputs'/snapshot['file']
    if file_hash(saved_payload) != snapshot['sha256'] or digest(request_payload(
            original, 'structured-card-limit-local')) != snapshot['canonical_sha256']:
        raise ValueError('Cell A must reproduce the unchanged consumed Gemini payload.')
    control, control_truth, control_audit = bet_control(original, truth)
    native_view_audit(control)
    output.mkdir(parents=True, exist_ok=False)
    directory = output/'inputs'; directory.mkdir()
    rows, oracle = [], {}
    for cell, mode, table_only, labelled in CELLS:
        frame = control if labelled else original
        if table_only:
            frame = replace(frame, details=())
        expected = deepcopy(control_truth if labelled else truth)
        available = {name for name, _ in frame.images()}
        observation = {k: v for k, v in expected.items() if k != 'number_views'}
        if not semantic_gate(observation, available_views=available)['usable']:
            raise ValueError('Reference violates unchanged R1 rules.')
        for number in expected['number_views']:
            number['allowed_views'] = [n for n in number['allowed_views'] if n in available]
        row = native_record(directory, cell, frame, split='consumed_development_diagnostic',
            evidence_kind='same consumed owned hand; E pixel-only counterfactual; not independent sessions')
        payload = request_payload(frame, mode)
        path = directory/cell/'gemini.request.json'; save(path, payload)
        row.update(mode=mode, packet_fingerprint=frame_fingerprint(frame),
            native_view_audit=native_view_audit(frame), available_views=sorted(available),
            payload={'file': cell+'/'+path.name, 'sha256': file_hash(path), 'canonical_sha256': digest(payload)},
            footprint=payload_footprint(payload, frame, mode))
        rows.append(row); oracle[cell] = expected
    save(directory/'frames.json', rows); save(directory/'oracle.json', oracle)
    save(output/'label-control.json', control_audit)
    proposed = 5*GeminiConfig().reserve_usd
    # Read the receipt, never initialize/reserve/amend the canonical ledger.
    from bjlab.research_budget import PersistentRequestBudget
    receipt = PersistentRequestBudget(ledger, authorization_id=budget['authorization_id'],
        max_requests=budget['max_requests'], max_usd=budget['max_usd']).receipt()
    margin = Decimal(receipt['max_usd'])-Decimal(receipt['accounted_upper_usd'])
    plan = {'status': 'OFFLINE_PREPARED_NOT_AUTHORIZED_NOT_EXECUTED',
        'parent_commit': PARENT_COMMIT, 'case': CASE, 'order': [c[0] for c in CELLS],
        'provider': asdict(GeminiConfig()), 'proposed_requests': 5, 'executed_requests': 0,
        'retry': 0, 'paid_warmup': 0, 'hybrid': 0, 'advisor_connected': False,
        'diagnostic_wait_ms': 10000, 'live_deadline_ms_unchanged': 3000,
        'per_attempt_historical_reservation_usd': str(GeminiConfig().reserve_usd),
        'batch_historical_reservation_usd': str(proposed), 'accounted_margin_usd': str(margin),
        'fits_snapshot_money_margin': proposed <= margin,
        'ledger_before_sha256': sha256(budget_bytes).hexdigest(), 'ledger_receipt': receipt,
        'request_ceiling_current': budget['max_requests'], 'request_ceiling_proposed_only': budget['max_requests']+5,
        'numeric_and_wire_policy': [CONTRACT_VERSION, POLICY_VERSION],
        'comparisons': {'A/B and C/D': 'serialization modes; logical local contract unchanged',
            'A/C and B/D': 'four views versus native table only; image content/load jointly change',
            'A/E': 'only BET label added to pixels; no answer injected into prompt'},
        'scoring': {'common': 'unchanged semantic_score plus literal transcription; available_views per cell',
            'separate': ['gate accepted', 'independent pixel/reference match', 'completed within 3s'],
            'E': 'ui20 with actually visible BET label, table view; never dealer_total',
            'label_format_limit': 'BET is not added to the frozen finite normalization grammar; raw label transcription differences stay visible'},
        'stop_before': ['fresh bounded human scope missing', 'prices/access not verified',
            'canonical ledger cannot reserve all five without releasing uncertainty',
            'same model/thinking/caps or protected storage not verified', 'freeze/input audit fails'],
        'stop_during': ['access/accounting/storage failure', 'frozen payload changed'],
        'stop_after': 'five one-shot cells; disarm; no automatic hybrid or promotion',
        'limits': ['diagnostic repeat, not new model reliability evidence',
            'one request/cell cannot isolate server queue/compute from network or measure operational p95',
            'table-only legibility needs declared assistant pixel review, not oracle injection',
            'new JSON+MINIMAL combination is offline constructed, not provider compatibility verified',
            'old scopes stay closed; this module has no run/submission/credential path']}
    save(output/'plan.json', plan)
    files = {str(p.relative_to(output)).replace('\\', '/'): file_hash(p)
        for p in sorted(output.rglob('*')) if p.is_file()}
    freeze = {'status': plan['status'], 'files': files,
        'code_sha256': {name: file_hash(ROOT/name) for name in CODE_FILES}, 'source_sha256': {
        'consumed-freeze': file_hash(source/'freeze.json'), 'consumed-request': file_hash(saved_payload),
        'preparation-tool': file_hash(__file__), 'current-evidence': file_hash(ROOT/'bjlab/hybrid_evidence.py'),
        'frozen-live-reader': file_hash(ROOT/'bjlab/live_cloud.py')},
        'new_requests': 0, 'credentials_loaded': False, 'ledger_unchanged': ledger.read_bytes() == budget_bytes}
    if not freeze['ledger_unchanged']:
        raise ValueError('Canonical budget changed during offline preparation.')
    save(output/'freeze.json', freeze)
    return {'output': str(output), 'freeze_sha256': file_hash(output/'freeze.json'),
        'cells_prepared': 5, 'provider_requests': 0, 'ledger_unchanged': True,
        'historical_batch_reserve_usd': str(proposed), 'fits_snapshot_money_margin': proposed <= margin}


def verify(output, expected_freeze_sha256):
    output = Path(output).resolve()
    if file_hash(output/'freeze.json') != expected_freeze_sha256:
        raise ValueError('Prepared freeze changed.')
    freeze = json.loads((output/'freeze.json').read_text())
    for name, expected in freeze['code_sha256'].items():
        if file_hash(ROOT/name) != expected:
            raise ValueError('Frozen preparation/reader/gate/evaluator code changed.')
    for name, expected in freeze['files'].items():
        path = (output/name).resolve()
        if not path.is_relative_to(output) or file_hash(path) != expected:
            raise ValueError('Prepared artifact changed or escaped its directory.')
    rows = json.loads((output/'inputs/frames.json').read_text())
    for row in rows:
        frame = load_frame(output/'inputs', row)
        native_view_audit(frame)
        if frame_fingerprint(frame) != row['packet_fingerprint']:
            raise ValueError('Named native packet changed.')
    return {'status': freeze['status'], 'cells_verified': len(rows), 'provider_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--verify-freeze-sha256')
    args = parser.parse_args()
    result = (verify(args.output, args.verify_freeze_sha256) if args.verify_freeze_sha256
        else prepare(output=args.output))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
