"""Freeze precisely two fresh owned paired cases and one conditional hybrid.

Reuses the existing renderer/engine/native layout. No provider or ledger mutation,
holdout access or local tuning. This is a tiny new validation lot, not a dataset
or generalization study. Pixel truth is isolated from application reader inputs.
"""
import argparse
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from PIL import ImageDraw

from bjlab.live_cloud import PROMPT
from bjlab.live_state import wire_schema, gemini_structured_schema
from bjlab.numeric_provenance import POLICY_VERSION, semantic_gate
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from bjlab.state_reader import prepare_frame
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, ROOT, file_hash, native_record
from validation.tools.grounded_corpus import SYMBOL_FONT, font, save
from validation.tools.paired_cloud_prepare import (SOURCES, NAMES, candidates, digest,
    render_case, live_truth, allowed_number_views, local_snapshot, FAMILIES, SMOKE)
from validation.tools.state_reader_comparison import load_frame
from validation.tools.stress_lab import LAYOUT, timeline

OUTPUT = ROOT/'artifacts/paired-semantic-hybrid-20261006'
OLD = ROOT/'artifacts/paired-cloud-preparation-20261005-frozen'
EPOCH = '2026-10-06-paired-semantic-four-plus-one'
INITIAL_LEDGER_SHA256 = '6ed8ccd493956c544a25cf4c04c4530089c9a2e050c74e00734cc0ef5c62d90f'
MAX_BATCH_USD = Decimal('2.2138736')
CASES = (
    ('fresh-labelled', 'labelled-totals', (91006011, 'owned-new-copper-verdana', 'verdanab.ttf', '#5f422c', '#ffffe8')),
    ('fresh-rotated-unknown', 'rotation', (91006019, 'owned-new-indigo-trebuchet', 'trebucbd.ttf', '#28365c', '#fff7ee')),
    ('fresh-stable-hybrid', 'rotation', (91006023, 'owned-new-pine-georgia', 'georgiab.ttf', '#26503a', '#faffed')),
)
PAIRS = ((CASES[0][0], NAMES[0]), (CASES[0][0], NAMES[1]),
         (CASES[1][0], NAMES[1]), (CASES[1][0], NAMES[0]))
NEW_SOURCES = ('bjlab/numeric_provenance.py', 'bjlab/paired_persistent_http.py',
    'bjlab/paired_deadline_reader.py', 'validation/tools/numeric_semantic_score.py',
    'validation/tools/paired_semantic_prepare.py', 'validation/tools/paired_semantic_smoke.py')
GATE = {'required_cases_per_candidate': 2, 'correct_timely_semantic_r1': 2,
    'false_accepts': 0, 'unsupported_known_suits': 0, 'required_inventory_exact': 2,
    'max_ms': 3000, 'sample_p95_ms': 2500,
    'p95_scope': 'two observations only; not an operational/population latency claim',
    'selection': ['eligible only', 'semantic_complete_transcriptions descending',
                  'sample p95 ascending', 'reported usage upper cost ascending', 'candidate name ascending'],
    'hybrid_max_requests': 1, 'hybrid_route': 'actual local gate only; no oracle forcing',
    'capture_deadline_ms': 3000, 'latest_capture_gap_ms': 250}


def ledger_snapshot():
    before = file_hash(CANONICAL_LEDGER)
    value = json.loads(CANONICAL_LEDGER.read_text())
    if value['max_requests'] not in (102, 105):
        raise PermissionError('Only the bounded unchanged or amended ledger is supported.')
    receipt = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID,
        max_requests=value['max_requests'], max_usd='8').receipt()
    if file_hash(CANONICAL_LEDGER) != before:
        raise PermissionError('Read-only ledger inspection raced with another writer.')
    return {'sha256': before, 'receipt': receipt}


def prepare(output=OUTPUT):
    old_freeze = json.loads((OLD/'freeze.json').read_text())
    local = local_snapshot(old_freeze['frozen_local']['manifest'])
    before = ledger_snapshot()
    if before['sha256'] != INITIAL_LEDGER_SHA256:
        raise PermissionError('Initial canonical history differs from the authorized checkpoint.')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    directory = output/'inputs'; directory.mkdir()
    records, truths, visibility = [], {}, {}
    old_sessions = {str(f[0]) for values in FAMILIES.values() for f in values}
    old_fonts = set(old_freeze['font_hashes'])
    for case_id, condition, values in CASES:
        seed, name, basename, felt, paper = values
        if str(seed) in old_sessions or basename in old_fonts:
            raise ValueError('New families/sessions must be disjoint from consumed cases.')
        stage = next(s for s in timeline(seed, 12) if s['phase'] == 'player')
        family = (seed, name, 'C:/Windows/Fonts/'+basename, felt, paper)
        image, truth, evidence = render_case(stage, condition, family)
        if case_id == CASES[1][0]:
            # A deliberately unlabelled independent UI number. No attribution to
            # dealer/player totals is present in the pixels or expected result.
            draw = ImageDraw.Draw(image); ui_font = font('C:/Windows/Fonts/arialbd.ttf', 25)
            draw.text((910, 130), '20', font=ui_font, fill='white', anchor='lt')
            x, y, r, b = draw.textbbox((910, 130), '20', font=ui_font, anchor='lt')
            truth['numbers'].append({'value': 20, 'role': 'unknown', 'label': None, 'view': 'table',
                'box': [x/1024, y/768, (r-x)/1024, (b-y)/768]})
        frame = prepare_frame(image, LAYOUT); observation = live_truth(truth)
        if not semantic_gate(observation, available_views={n for n, _ in frame.images()})['usable']:
            raise ValueError('Predeclared case is not an R1 decision opportunity.')
        record = native_record(directory, case_id, frame, split='new_validation',
            independent_session='semantic-'+str(seed), seed=seed, family=name,
            condition=condition, hand_group=str(seed)+':'+str(stage['round']),
            evidence_kind='new-owned-natural-session; shared renderer, not external transfer')
        hashes = [sha256(p).hexdigest() for _, p in frame.images()]; record['payloads'] = {}
        for name, reader in candidates(hashes).items():
            payload = reader.payload(frame); path = directory/case_id/(name+'.request.json')
            save(path, payload)
            record['payloads'][name] = {'file': case_id+'/'+path.name,
                'sha256': file_hash(path), 'canonical_sha256': digest(payload)}
        records.append(record)
        truths[case_id] = {**observation.model_dump(), 'number_views': allowed_number_views(truth, frame.layout)}
        visibility[case_id] = evidence
    # Only consumed public/dev metadata is opened, never a sealed final split.
    old_truth = json.loads((OLD/'validation/oracle.json').read_text())
    signatures = lambda t: sorted((c['zone'], c['rank'] or '', c['suit'] or '', c['visibility']) for c in t['cards'])
    if any(signatures(truths[c[0]]) == signatures(old_truth[k]) for c in CASES for k in SMOKE):
        raise ValueError('New hands duplicate consumed smoke cards.')
    save(directory/'frames.json', records); save(directory/'oracle.json', truths)
    save(directory/'visibility-evidence.json', visibility)
    protected = {str(p.relative_to(ROOT)): file_hash(p) for folder in (
        OLD, ROOT/'artifacts/paired-cloud-smoke-20261005-six',
        ROOT/'validation/results/numeric-provenance-alignment', ROOT/'validation/results/cloud-connection-paired-smoke')
        for p in folder.rglob('*') if p.is_file()}
    protected.update({p: file_hash(ROOT/p) for p in SOURCES})
    save(output/'protected-before.json', protected)
    configs = candidates(); worst = 2*sum((r.config.reserve_usd for r in configs.values()), Decimal(0))+max(
        r.config.reserve_usd for r in configs.values())
    if worst != MAX_BATCH_USD:
        raise ValueError('Reservation differs from the explicit lot.')
    freeze = {'experiment': 'VISION-025', 'epoch': EPOCH, 'parent': 'a4eb763470dac5795518c4728fd16ad5da19b969',
        'cases': [c[0] for c in CASES], 'pairs': PAIRS, 'gate': GATE, 'ledger_before': before,
        'batch_max_reservation_usd': str(worst), 'new_inference_maximum': 5, 'lifetime_ceiling': 105,
        'semantic_policy': POLICY_VERSION, 'prompt_sha256': sha256(PROMPT.encode()).hexdigest(),
        'schemas': {NAMES[0]: digest(wire_schema()), NAMES[1]: digest(gemini_structured_schema())},
        'configs': {n: asdict(r.config) for n, r in configs.items()}, 'frozen_local': local,
        'sources': {p: file_hash(ROOT/p) for p in tuple(dict.fromkeys(SOURCES+NEW_SOURCES))},
        'files': {str(p.relative_to(output)): file_hash(p) for p in directory.rglob('*') if p.is_file()},
        'protected_before_sha256': file_hash(output/'protected-before.json'),
        'font_hashes': {v[2]: file_hash('C:/Windows/Fonts/'+v[2]) for _, _, v in CASES},
        'symbol_font_sha256': file_hash(SYMBOL_FONT), 'provider_calls': 0,
        'shared_components': ['owned renderer', 'native layout', 'Arial controls', 'Segoe UI Symbol suits'],
        'truth_scope': 'render masks plus pre-call visual audit; not independently collected provider truth',
        'final_holdout': 'not_opened', 'retry': 0, 'paid_warmup': 0}
    save(output/'freeze.json', freeze)
    return freeze


def checked(output=OUTPUT):
    output = Path(output); freeze = json.loads((output/'freeze.json').read_text())
    if freeze['gate'] != GATE or freeze['epoch'] != EPOCH or freeze['pairs'] != [list(p) for p in PAIRS]:
        raise PermissionError('Frozen gate, scope or pair order differs.')
    for p, expected in freeze['sources'].items():
        if file_hash(ROOT/p) != expected:
            raise PermissionError('Frozen execution source changed: '+p)
    for p, expected in freeze['files'].items():
        path = (output/p).resolve()
        if not path.is_relative_to(output.resolve()) or file_hash(path) != expected:
            raise PermissionError('Frozen pixels/payload/oracle changed.')
    for basename, expected in freeze['font_hashes'].items():
        if file_hash('C:/Windows/Fonts/'+basename) != expected:
            raise PermissionError('Frozen font changed.')
    if (file_hash(SYMBOL_FONT) != freeze['symbol_font_sha256'] or
            local_snapshot(freeze['frozen_local']['manifest']) != freeze['frozen_local']):
        raise PermissionError('Frozen symbol font or local weights changed.')
    protected = json.loads((output/'protected-before.json').read_text())
    if file_hash(output/'protected-before.json') != freeze['protected_before_sha256']:
        raise PermissionError('Protected history manifest changed.')
    if any(file_hash(ROOT/p) != expected for p, expected in protected.items()):
        raise PermissionError('Historical evidence changed.')
    records = json.loads((output/'inputs/frames.json').read_text())
    frames = {r['id']: (r, load_frame(output/'inputs', r)) for r in records}
    return freeze, frames, json.loads((output/'inputs/oracle.json').read_text())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    freeze = prepare() if args.prepare else checked()[0]
    print(json.dumps({'cases': freeze['cases'], 'provider_calls': 0,
        'freeze_sha256': file_hash(OUTPUT/'freeze.json'), 'reservation_usd': freeze['batch_max_reservation_usd']}))
