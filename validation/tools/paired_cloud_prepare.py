"""VISION-021: owned inputs and paired request preparation, strictly OFFLINE.

No credential loading, inference, model warm-up or authorization path exists.
Natural engine sessions render evidence; oracle state is confined to scoring.
Historical corpora and all final holdouts are deliberately never opened.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_cloud import DiagnosticReader, PROMPT
from bjlab.live_state import CONTRACT_VERSION, LiveObservation, live_gate, wire_schema, gemini_structured_schema
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from bjlab.state_reader import prepare_frame
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, PERCEPTION_FILES, config, file_hash, native_record
from validation.tools.grounded_corpus import SYMBOL_FONT, card_tile, font, render, save
from validation.tools.state_reader_comparison import load_frame
from validation.tools.stress_lab import LAYOUT, SUITS, timeline

ROOT = Path(__file__).resolve().parents[2]
PARENT = 'a5ea45428b670d8a0ff10f5d6d495ad534fa9fde'
NAMES = ('luna-fast-live-v3', 'gemini-structured-card-limit-local')
FAMILIES = {
    'development': (
        (81005071, 'owned-paired-jade-corbel', 'corbelb.ttf', '#185247', '#fff9ed'),
        (81005073, 'owned-paired-slate-bahnschrift', 'bahnschrift.ttf', '#354c5c', '#f6f7fe'),
        (81005079, 'owned-paired-clay-candara', 'candarab.ttf', '#623c30', '#fff6f1')),
    'validation': (
        (81005181, 'owned-paired-berry-franklin', 'framd.ttf', '#533a56', '#f9f0ff'),
        (81005183, 'owned-paired-moss-impact', 'impact.ttf', '#424f2e', '#ffffec'),
        (81005187, 'owned-paired-ocean-segoe-print', 'segoeprb.ttf', '#205d75', '#f0ffff')),
}
GROUPS = (
    ('clean-ui', 'labelled-totals', 'unlabelled-number', 'backs', 'overlap', 'hard-negatives'),
    ('rotation', 'clipping-alt-index', 'partial-index', 'popup-unreadable', 'faded-blur'),
    ('disabled-controls', 'terminal', 'transition-clear', 'transition-dealing', 'transition-after'),
)
SMOKE = ('labelled-totals', 'rotation', 'transition-after')
SOURCES = tuple(dict.fromkeys(PERCEPTION_FILES + (
    'bjlab/live_cloud.py', 'bjlab/live_state.py', 'bjlab/grounded_cloud.py',
    'bjlab/grounded_state.py', 'bjlab/hybrid_evidence.py', 'bjlab/research_budget.py',
    'bjlab/openai_reader.py', 'bjlab/simulator.py', 'bjlab/engine.py',
    'validation/tools/paired_cloud_prepare.py', 'validation/tools/grounded_corpus.py',
    'validation/tools/stress_lab.py', 'validation/tools/api_reader_tournament.py',
    'validation/tools/state_reader_comparison.py')))


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class OfflineOnly:
    def __getattr__(self, name):
        raise PermissionError('Offline preparation cannot submit, reserve or enable inference: '+name)


def candidates(hashes=()):
    guard = OfflineOnly()
    return {
        NAMES[0]: DiagnosticReader(config(fast=True), guard, hashes, provider='openai', variant='live', transport=guard),
        NAMES[1]: DiagnosticReader(GeminiConfig(), guard, hashes, provider='gemini', variant='live', transport=guard,
                                  gemini_output='structured-card-limit-local'),
    }


def ledger_snapshot():
    """Read the existing canonical allowance, never initialize/reserve/amend it."""
    before = file_hash(CANONICAL_LEDGER)
    receipt = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID,
                                     max_requests=102, max_usd='8').receipt()
    if file_hash(CANONICAL_LEDGER) != before:
        raise ValueError('Read-only budget inspection changed the ledger.')
    return {'sha256': before, 'receipt': receipt}


def budget_plan(receipt, validation_inputs):
    luna, gemini = config(fast=True).reserve_usd, GeminiConfig().reserve_usd
    remaining = max(Decimal('0'), Decimal(receipt['max_usd'])-Decimal(receipt['accounted_upper_usd']))
    initial = 3*(luna+gemini)
    full = validation_inputs*(luna+gemini)
    hybrid = 5*max(luna, gemini)
    return {
        'authorization_status': 'NOT_AUTHORIZED_OFFLINE_ONLY', 'new_requests_executed': 0,
        'unused_diagnostic_slots': '8 CLOSED; not a new allowance',
        'currency': 'USD', 'pricing': 'Frozen PR13/15 audited config; reverify before future execution',
        'reservation_basis': 'Whole declared context plus max output, including Luna Fast/long/cache upper multipliers; not expected cost or invoice',
        'existing_ledger': receipt, 'remaining_accounted_margin_usd': str(remaining),
        'per_attempt_reserve_usd': {NAMES[0]: str(luna), NAMES[1]: str(gemini)},
        'initial_proposal': {'inputs': list(SMOKE), 'split': 'validation', 'paired_requests': 6,
            'worst_case_usd': str(initial), 'fits_existing_money_margin': initial <= remaining,
            'purpose': 'Small paired smoke; insufficient for full R1 or hybrid promotion'},
        'full_still_proposal': {'split': 'validation', 'inputs_per_candidate': validation_inputs,
            'paired_requests': 2*validation_inputs, 'worst_case_usd': str(full),
            'fits_existing_money_margin': full <= remaining},
        'conditional_hybrid_proposal': {'requests': 5, 'candidate': 'one measured winner only',
            'worst_case_usd': str(hybrid), 'conditions': ['paired gate passed', 'fresh explicit scope', 'ledger admits each reservation'],
            'scenarios': ['stable warm table: 3 independent inputs', 'table changes while cloud is pending: 1', 'source disconnects while cloud is pending: 1']},
        'full_still_plus_hybrid': {'maximum_requests': 2*validation_inputs+5, 'worst_case_usd': str(full+hybrid),
            'fits_existing_money_margin': full+hybrid <= remaining},
        'initial_plus_conditional_hybrid': {'maximum_requests': 11, 'worst_case_usd': str(initial+hybrid),
            'fits_existing_money_margin': initial+hybrid <= remaining,
            'policy': 'The initial six can be proposed within the current margin. Conditional requests require passing results AND new scope AND the ledger admitting each reservation. Completion is not guaranteed.'},
        'warmup_provider_requests': 0, 'retries': 0,
        'budget_policy': 'No automatic execution. Do not reset ledger, release uncertain charges, assume HTTP400 free, raise caps or purchase credit. Each future attempt needs a durable reservation. Paid warm-up would need a separate counted authorization.'}


def hybrid_plan():
    return {'status': 'planned_not_executed', 'new_provider_requests': 0, 'maximum_future_requests': 5,
        'prerequisites': ['fresh bounded explicit authorization', 'same-input paired measurements',
            'zero falsely accepted states and unsupported known suits',
            'all selected decision states correct and usable; nondecision inputs correctly abstained',
            'complete validated JSON within 3s, sample p95 <= 2.5s; all failures retained',
            'frozen local receipt verified; triggers measured rather than forced from oracle',
            'remaining budget admits each durable reservation'],
        'trial_order': ['stable warm: labelled-totals', 'stable warm: rotation', 'stable warm: transition-after',
            'owned table changes during actual cloud response', 'owned source disconnects during actual cloud response'],
        'local_and_capture_warmup': 'owned development input only, no annotation/phase injection into local reader',
        'persistent_https': 'future scoped pooled transport, same TLS hostname/certificate checks; no system DNS/proxy changes; current historical transport opens a client per request and is not rewritten here',
        'network_warmup': 'no paid warm-up; count cold first attempt; verify reuse from transport traces, never assume it',
        'source': 'controlled owned producer, advancing sequence/timestamp; keep current capture independent of a pending cloud request',
        'route': 'local -> semantic fallback trigger -> cloud observation -> strict parse -> semantic/provenance gate -> current-state revalidation -> deterministic solver -> revalidation -> advisor serialization',
        'deadline': {'capture_to_advisor_ms': 3000, 'target_p95_ms': 2500, 'maximum_current_capture_gap_ms': 250,
            'per_request_timeout': 'remaining monotonic capture deadline, capped at 3s; never grant a new 3s after local processing'},
        'stage_measurements': ['capture', 'local', 'routing/reservation', 'DNS', 'TCP', 'TLS', 'upload',
            'response headers/body', 'provider JSON parse', 'strict/semantic validation', 'current-state revalidation',
            'deterministic solver', 'headless advisor serialization'],
        'timing_limits': 'DNS/TCP separation needs explicit tracing; response wait includes provider/network, not measured server compute. Unobservable durations stay null. Report cold/warm separately.',
        'stale_policy': 'changed pixels/table/source, disconnected source, expired original capture or capture gap closes presentation; repaint does not renew evidence validity',
        'scoring': 'common still evaluator plus actual capture-to-advisor correctness/freshness; separate latency distributions and failure/timeout/late-discard denominators',
        'advisor_boundary': 'controlled headless serialization; native paint, physical screen sharing/minimization and external sessions remain separate unexecuted tests',
        'decision_order': ['false accepts', 'state correctness', 'useful coverage', 'capture-to-display latency', 'failure rate', 'cost', 'complexity'],
        'stop_outcomes': ['local-only', 'Luna fallback', 'Gemini fallback', 'hybrid demonstrated within declared owned scope', 'cloud offline/replay only', 'R1 still unverified'],
        'limits': 'Three warm successes would demonstrate a bounded path, not stable universal live behavior, R2/shoe history, provider transfer or profit. Small sample uncertainty remains explicit.'}


def live_truth(truth):
    """Remove coordinate-only evaluator metadata; preserve label and native view."""
    value = {key: truth[key] for key in ('cards', 'table_state', 'phase', 'controls', 'blockers')}
    value['numbers'] = [{k: n[k] for k in ('value', 'role', 'label', 'view')} for n in truth['numbers']]
    return LiveObservation.model_validate(value)


def selected_stages(seed, group):
    stages = timeline(seed, 16)
    rounds = sorted({s['round'] for s in stages if s['phase'] == 'player'})
    if len(rounds) < 6:
        raise ValueError('Natural session lacks enough distinct player rounds; never rig cards to fill it.')
    if group < 2:
        return [(case, next(s for s in stages if s['round'] == rounds[i] and s['phase'] == 'player'))
                for i, case in enumerate(GROUPS[group])]
    first = rounds[0]
    third = next(r for r in rounds[2:] if any(s['round'] == r-1 and s['phase'] == 'settled' for s in stages))
    second = third-1
    # One actual terminal -> cleared table -> next distribution -> next decision.
    settled = next(s for s in stages if s['round'] == second and s['phase'] == 'settled')
    index = stages.index(settled)
    clear = stages[index+1]
    dealing = next(s for s in stages[index+1:] if s['round'] == third and s['phase'] == 'dealing' and len(s['cards']) == 2)
    after = next(s for s in stages[index+1:] if s['round'] == third and s['phase'] == 'player')
    return [('disabled-controls', next(s for s in stages if s['round'] == first and s['phase'] == 'settled')),
            ('terminal', settled), ('transition-clear', clear), ('transition-dealing', dealing), ('transition-after', after)]


def render_case(stage, condition, family):
    stage = {**stage, 'phase': 'unknown' if stage['phase'] == 'dealing' else stage['phase'],
             'controls': ['hit', 'stand'] if stage['phase'] == 'player' else []}
    render_condition = condition if condition not in ('backs', 'terminal', 'transition-clear', 'transition-dealing', 'transition-after', 'partial-index') else 'clean-ui'
    image, truth, visibility = render(stage, render_condition, family)
    draw = ImageDraw.Draw(image)
    if condition == 'transition-dealing':
        draw.text((260, 608), 'DEALING', font=font('C:/Windows/Fonts/arialbd.ttf', 25), fill='white')
    if condition == 'partial-index':
        target = next(d for d in visibility if d['zone'] == 'player:0')
        x, y, w, h = target['box']
        # Leave only the complete top rank. Mask suit/pip and opposite index.
        rectangle = (x, y+35, x+w-1, y+h-1)
        draw.rectangle(rectangle, fill='#303d48')
        draw.text((x+8, y+67), 'OVERLAY', font=font('C:/Windows/Fonts/arialbd.ttf', 14), fill='white')
        card = next(c for c in truth['cards'] if c['zone'] == 'player:0')
        card.update(suit=None, visibility='partial')
        target.update(presence='partial', body_fraction=35/h, overlay=list(rectangle),
                      glyph_fractions={k: 1. if k == 'top_rank' else 0. for k in target['glyph_fractions']})
    return image, truth, visibility


def payload_images(payload, name):
    if name == NAMES[0]:
        return [base64.b64decode(c['image_url'].split(',', 1)[1], validate=True)
                for c in payload['input'][0]['content'] if c['type'] == 'input_image']
    return [base64.b64decode(p['inlineData']['data'], validate=True)
            for p in payload['contents'][0]['parts'] if 'inlineData' in p]


def write_contact_sheet(directory, records):
    sheet = Image.new('RGB', (4*384, 4*315), '#111a22')
    draw = ImageDraw.Draw(sheet)
    for i, record in enumerate(records):
        x, y = (i % 4)*384, (i // 4)*315
        with Image.open(directory/record['images'][0]['file']) as image:
            sheet.paste(image.resize((384, 288)), (x, y))
        draw.text((x+6, y+291), record['id'], font=font('C:/Windows/Fonts/arialbd.ttf', 14), fill='white')
    sheet.save(directory/'contact-sheet.png')


def local_snapshot(manifest):
    manifest = Path(manifest).resolve()
    value = json.loads(manifest.read_text())
    models = {}
    for key in ('pose_model', 'classifier_model'):
        name = value[key]; path = (manifest.parent/name).resolve()
        if not path.is_relative_to(manifest.parent): raise ValueError('Frozen model escapes its manifest.')
        actual = file_hash(path)
        if actual != value['exports'][name]['sha256']: raise ValueError('Frozen model checksum mismatch.')
        models[name] = actual
    return {'manifest': str(manifest), 'manifest_sha256': file_hash(manifest), 'weights': models,
            'reader_version': value['reader_version'], 'inference_executed': False}


def allowed_number_views(truth, layout):
    catalog = []
    for n in truth['numbers']:
        x, y, w, h = n['box']
        views = []
        for view, (lx, ly, lw, lh) in layout.items():
            if lx <= x and ly <= y and x+w <= lx+lw and y+h <= ly+lh:
                views.append(view)
        catalog.append({'role': n['role'], 'value': n['value'], 'label': n['label'], 'allowed_views': views})
    return catalog


def prepare(output, reader_manifest):
    output = Path(output).resolve()
    receipt = ledger_snapshot(); local = local_snapshot(reader_manifest)
    # Check all artwork before writing. Suit tofu must not pass a mask oracle.
    for values in FAMILIES.values():
        for family in values: font('C:/Windows/Fonts/'+family[2], 29)
    masks = [card_tile({'rank': '7', 'suit': s}, 'C:/Windows/Fonts/corbelb.ttf', 'white')[1]['pip'].tobytes() for s in SUITS]
    if len(set(masks)) != 4: raise ValueError('Four distinct suit glyphs required.')
    output.mkdir(parents=True, exist_ok=False)
    freeze = {'scope': 'VISION-021 offline owned synthetic preparation', 'parent': PARENT,
        'contract': CONTRACT_VERSION, 'sources': {p: file_hash(ROOT/p) for p in SOURCES}, 'frozen_local': local,
        'prompt_sha256': sha256(PROMPT.encode()).hexdigest(),
        'logical_schema_sha256': digest(wire_schema()),
        'provider_schema_sha256': {NAMES[0]: digest(wire_schema()), NAMES[1]: digest(gemini_structured_schema())},
        'configs': {name: asdict(reader.config) for name, reader in candidates().items()},
        'font_hashes': {f[2]: file_hash('C:/Windows/Fonts/'+f[2]) for values in FAMILIES.values() for f in values},
        'symbol_font_sha256': file_hash(SYMBOL_FONT), 'ledger_before': receipt,
        'partitions': {}, 'provider_calls': 0, 'final_holdout': 'not_created_not_opened_not_evaluated',
        'shared_components': ['owned rectangular artwork renderer', 'calibrated layout', 'Arial control font', 'Segoe UI Symbol suits'],
        'truth_scope': 'engine-rendered evidence masks plus visual audit; geometric visibility proxy, not independent human/provider truth',
        'claim_limit': 'fresh sessions/palettes/fonts within an owned renderer; NOT external-provider generalization or R2 certification',
        'authorization': 'offline only; payload readiness does not authorize upload or inference'}
    for split, values in FAMILIES.items():
        directory = output/split; directory.mkdir()
        records, truths, evidence = [], {}, {}
        for group, family_values in enumerate(values):
            seed, name, basename, felt, paper = family_values
            family = (seed, name, 'C:/Windows/Fonts/'+basename, felt, paper)
            for condition, stage in selected_stages(seed, group):
                image, truth, visibility = render_case(stage, condition, family)
                observation = live_truth(truth)
                frame = prepare_frame(image, LAYOUT)
                record = native_record(directory, condition, frame, split=split,
                    evidence_kind='new-owned-natural-session-live-v3', condition=condition,
                    independent_session='paired-'+str(seed), seed=seed, family=name,
                    hand_group=str(seed)+':'+str(stage['round']),
                    transition_group=str(seed)+':transition' if condition.startswith('transition-') or condition == 'terminal' else None,
                    expected_usable_r1=live_gate(observation)['usable'])
                record['payloads'] = {}
                hashes = [sha256(p).hexdigest() for _, p in frame.images()]
                for candidate, reader in candidates(hashes).items():
                    payload = reader.payload(frame)
                    if payload_images(payload, candidate) != [p for _, p in frame.images()]:
                        raise ValueError('Providers must receive the identical native pixels.')
                    path = directory/condition/(candidate+'.request.json')
                    save(path, payload)
                    record['payloads'][candidate] = {'file': condition+'/'+path.name, 'sha256': file_hash(path),
                        'canonical_sha256': digest(payload), 'bytes': path.stat().st_size}
                records.append(record)
                truths[condition] = {**observation.model_dump(), 'number_views': allowed_number_views(truth, frame.layout)}
                evidence[condition] = visibility
        save(directory/'frames.json', records); save(directory/'oracle.json', truths); save(directory/'visibility-evidence.json', evidence)
        write_contact_sheet(directory, records)
        freeze['partitions'][split] = {'files': {n: file_hash(directory/n) for n in ('frames.json', 'oracle.json', 'visibility-evidence.json', 'contact-sheet.png')},
            'sessions': [str(v[0]) for v in values], 'seeds': [v[0] for v in values], 'families': [v[1] for v in values],
            'hand_groups': sorted({r['hand_group'] for r in records}), 'inputs': len(records),
            'decision_opportunities': sum(r['expected_usable_r1'] for r in records)}
        if len({r['independent_session'] for r in records if r['id'] in SMOKE}) != 3:
            raise ValueError('Initial paired inputs must cover three independent source sessions.')
    for key in ('sessions', 'seeds', 'families', 'hand_groups'):
        if set(freeze['partitions']['development'][key]) & set(freeze['partitions']['validation'][key]):
            raise ValueError('Development and validation groups overlap: '+key)
    if ledger_snapshot() != receipt: raise ValueError('Offline preparation changed the ledger.')
    save(output/'plan.json', budget_plan(receipt['receipt'], freeze['partitions']['validation']['inputs']))
    freeze['plan_sha256'] = file_hash(output/'plan.json')
    save(output/'hybrid-plan.json', hybrid_plan())
    freeze['hybrid_plan_sha256'] = file_hash(output/'hybrid-plan.json')
    save(output/'freeze.json', freeze)
    return freeze


def checked(output, split, *, expected_freeze_sha256=None):
    if split not in ('development', 'validation'):
        raise PermissionError('This offline runner cannot open a final holdout.')
    output = Path(output).resolve(); directory = output/split
    if expected_freeze_sha256 is not None and file_hash(output/'freeze.json') != expected_freeze_sha256:
        raise ValueError('Freeze differs from the reviewed external checksum.')
    freeze = json.loads((output/'freeze.json').read_text())
    for p, expected in freeze['sources'].items():
        if file_hash(ROOT/p) != expected: raise ValueError('Frozen source changed: '+p)
    if local_snapshot(freeze['frozen_local']['manifest']) != freeze['frozen_local']:
        raise ValueError('Frozen local model changed.')
    for basename, expected in freeze['font_hashes'].items():
        if file_hash('C:/Windows/Fonts/'+basename) != expected: raise ValueError('Frozen artwork font changed.')
    if file_hash(SYMBOL_FONT) != freeze['symbol_font_sha256']: raise ValueError('Frozen suit glyph font changed.')
    if file_hash(output/'plan.json') != freeze['plan_sha256']: raise ValueError('Frozen plan changed.')
    if file_hash(output/'hybrid-plan.json') != freeze['hybrid_plan_sha256']: raise ValueError('Frozen hybrid plan changed.')
    for p, expected in freeze['partitions'][split]['files'].items():
        if file_hash(directory/p) != expected: raise ValueError('Frozen input/annotation changed: '+p)
    records = json.loads((directory/'frames.json').read_text()); inputs = []
    for record in records:
        if record['split'] != split: raise ValueError('Wrong partition.')
        frame = load_frame(directory, record)
        for name, saved in record['payloads'].items():
            path = (directory/saved['file']).resolve()
            if not path.is_relative_to(directory) or file_hash(path) != saved['sha256']:
                raise ValueError('Frozen payload changed or escaped its partition.')
            payload = json.loads(path.read_text())
            hashes = [sha256(p).hexdigest() for _, p in frame.images()]
            if digest(payload) != saved['canonical_sha256'] or digest(candidates(hashes)[name].payload(frame)) != saved['canonical_sha256']:
                raise ValueError('Payload is not the frozen pixel/configuration contract.')
        inputs.append((record, frame))
    return freeze, inputs, json.loads((directory/'oracle.json').read_text())


def score(observation, truth, *, status='completed', elapsed_ms=None):
    """Common strict evaluator; denominators include failed/missed observations."""
    expected = LiveObservation.model_validate({k: v for k, v in truth.items() if k != 'number_views'})
    if observation is not None:
        observation = LiveObservation.model_validate(observation)
    actual = observation if status == 'completed' else None
    def cards(obs, fields):
        return Counter(tuple(getattr(c, f) for f in fields) for c in obs.cards) if obs else Counter()
    fields = ('zone', 'rank', 'suit', 'visibility')
    full_e, full_a = cards(expected, fields), cards(actual, fields)
    ranks = ('zone', 'rank', 'visibility'); rank_e, rank_a = cards(expected, ranks), cards(actual, ranks)
    def numbers(obs):
        values = []
        for n in obs.numbers if obs else []:
            view = n.view
            # The same label can legitimately occur in both table and a native
            # detail crop. Permit only views containing its full observed box.
            for entry in truth.get('number_views', []):
                if (n.role, n.value, n.label) == (entry['role'], entry['value'], entry['label']) and view in entry['allowed_views']:
                    view = 'table'; break
            values.append((n.role, n.value, n.label, view))
        return Counter(values)
    exact_cards = actual is not None and full_e == full_a
    exact_ranks = actual is not None and rank_e == rank_a
    number_e, number_a = numbers(expected), numbers(actual)
    unsafe_totals = any(role in ('player_total', 'dealer_total') for role, *_ in (number_a-number_e))
    phase = actual is not None and actual.phase == expected.phase
    controls = actual is not None and set(actual.controls) == set(expected.controls)
    blockers = actual is not None and set(actual.blockers) == set(expected.blockers)
    presence = actual is not None and actual.table_state == expected.table_state
    expected_usable = live_gate(expected)['usable']
    usable = actual is not None and live_gate(actual)['usable']
    r1_correct = exact_ranks and phase and controls and blockers and presence and not unsafe_totals
    complete = exact_cards and phase and controls and blockers and presence and number_e == number_a
    timely = elapsed_ms is not None and 0 <= elapsed_ms <= 3000 and actual is not None
    known_ranks = Counter((c.zone, c.rank) for c in expected.cards if c.rank is not None)
    known_suits = Counter((c.zone, c.rank, c.suit) for c in expected.cards if c.suit is not None)
    pred_ranks = Counter((c.zone, c.rank) for c in actual.cards if c.rank is not None) if actual else Counter()
    pred_suits = Counter((c.zone, c.rank, c.suit) for c in actual.cards if c.suit is not None) if actual else Counter()
    unsupported_suits = sum((pred_suits-known_suits).values())
    r1_correct = r1_correct and unsupported_suits == 0
    return {'strict_validated': actual is not None, 'status': status, 'elapsed_ms': elapsed_ms,
        'expected_usable_r1': expected_usable, 'usable_r1': usable,
        'correct_usable_r1': expected_usable and usable and r1_correct,
        'timely_correct_usable_r1': expected_usable and usable and r1_correct and timely,
        'false_accept': usable and (not expected_usable or not r1_correct),
        'accepted_inexact_card_inventory': usable and not exact_cards,
        'correct_abstention': not expected_usable and actual is not None and not usable and r1_correct,
        'complete_state_correct': complete, 'exact_card_inventory': exact_cards,
        'inventory_mismatches': {'missing_tuples': sum((full_e-full_a).values()), 'extra_tuples': sum((full_a-full_e).values()),
            'scope': 'semantic tuples; wrong reads create missing+extra, not detector localization counts'},
        'rank': {'correct': sum((known_ranks & pred_ranks).values()), 'expected': sum(known_ranks.values())},
        'suit': {'correct': sum((known_suits & pred_suits).values()), 'expected': sum(known_suits.values())},
        'backs': {'correct': sum((full_e & full_a)[k] for k in full_e if k[3] == 'covered'),
            'expected': sum(full_e[k] for k in full_e if k[3] == 'covered')},
        'phase_correct': phase, 'controls_correct': controls, 'numeric_provenance_exact': actual is not None and number_e == number_a,
        'numeric_provenance': {'matched': sum((number_e & number_a).values()), 'expected': sum(number_e.values()),
            'extra_or_wrong': sum((number_a-number_e).values())}, 'unsafe_attributed_total': unsafe_totals,
        'unsupported_known_suit_tuples': unsupported_suits}


def summarize(rows, *, planned, independent_sessions):
    """No invented p95 for unexecuted requests, or for censored timeouts."""
    if planned < len(rows): raise ValueError('Attempted exceeds planned; retries require a separate plan.')
    elapsed = [r['elapsed_ms'] for r in rows if r['strict_validated'] and r['elapsed_ms'] is not None]
    return {'planned': planned, 'attempted': len(rows), 'not_executed': planned-len(rows),
        'independent_sessions': independent_sessions,
        **{key: {'numerator': sum(bool(r[key]) for r in rows), 'denominator': len(rows)} for key in
           ('strict_validated', 'complete_state_correct', 'exact_card_inventory', 'phase_correct', 'controls_correct',
            'numeric_provenance_exact', 'false_accept', 'accepted_inexact_card_inventory')},
        'timely_correct_usable_r1': {'numerator': sum(r['timely_correct_usable_r1'] for r in rows),
                                   'denominator': sum(r['expected_usable_r1'] for r in rows)},
        'timeouts': sum(r['status'] == 'timeout' for r in rows),
        'failures': sum(not r['strict_validated'] for r in rows),
        **{k: {'correct': sum(r[k]['correct'] for r in rows), 'expected': sum(r[k]['expected'] for r in rows)} for k in ('rank', 'suit', 'backs')},
        'latency_complete_validated_only_ms': {'count': len(elapsed),
            'p50': float(np.percentile(elapsed, 50)) if elapsed else None,
            'p95': float(np.percentile(elapsed, 95)) if elapsed else None, 'max': max(elapsed) if elapsed else None},
        'scope': 'R1 still observations only; latency excludes censored failures, whose counts remain visible; session-clustered uncertainty required before promotion'}


def evaluate(output, split, result_file):
    """Score retained responses offline, without a provider client or secrets."""
    freeze, inputs, truths = checked(output, split)
    results = json.loads(Path(result_file).read_text())
    if results['freeze_sha256'] != file_hash(Path(output)/'freeze.json') or results['split'] != split:
        raise ValueError('Responses belong to a different frozen experiment.')
    kind = results['evidence_kind']
    if kind not in ('actual-provider-responses', 'contract-fixture'):
        raise ValueError('Provider and mock evidence must be explicitly distinguished.')
    records = {r['id']: r for r, _ in inputs}; seen = set(); rows = {name: [] for name in NAMES}
    for item in results['results']:
        name, case = item['candidate'], item['case_id']; key = name, case
        if name not in rows or case not in records or key in seen:
            raise ValueError('Unknown candidate/input or duplicate attempt.')
        seen.add(key); record = records[case]
        if item['payload_sha256'] != record['payloads'][name]['sha256']:
            raise ValueError('Response is not bound to the prepared payload.')
        elapsed = item.get('elapsed_ms')
        if elapsed is not None and (type(elapsed) not in (int, float) or not np.isfinite(elapsed) or elapsed < 0):
            raise ValueError('Elapsed time must be a finite nonnegative duration.')
        status = item['status']
        if status not in ('completed', 'timeout', 'http_error', 'invalid', 'error'):
            raise ValueError('Unknown attempt status.')
        observation = item.get('observation')
        if status == 'completed':
            try: observation = LiveObservation.model_validate(observation)
            except ValueError: status, observation = 'invalid', None
        else: observation = None
        scored = score(observation, truths[case], status=status, elapsed_ms=elapsed)
        scored.update(case_id=case, independent_session=record['independent_session'], condition=record['condition'])
        rows[name].append(scored)
    summaries = {name: summarize(values, planned=len(inputs), independent_sessions=len(freeze['partitions'][split]['sessions']))
                 for name, values in rows.items()}
    grouped = {}
    for name, values in rows.items():
        grouped[name] = {}
        for group_key in ('condition', 'independent_session'):
            grouped[name][group_key] = {}
            for group in sorted({record[group_key] for record in records.values()}):
                planned = sum(record[group_key] == group for record in records.values())
                subset = [r for r in values if r[group_key] == group]
                grouped[name][group_key][group] = summarize(subset, planned=planned,
                    independent_sessions=len({r['independent_session'] for r in records.values() if r[group_key] == group}))
    return {'evidence_kind': kind, 'model_quality_evidence': kind == 'actual-provider-responses',
        'results_sha256': file_hash(result_file), 'freeze_sha256': results['freeze_sha256'],
        'provider_calls_by_evaluator': 0, 'promotion': 'none; this is a scoring tool, not authorization or a rollout',
        'candidates': summaries, 'groups': grouped, 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'check', 'evaluate'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--reader-manifest', type=Path)
    parser.add_argument('--split', choices=('development', 'validation'), default='validation')
    parser.add_argument('--results', type=Path)
    parser.add_argument('--expected-freeze-sha256')
    args = parser.parse_args()
    if args.operation == 'prepare':
        if args.reader_manifest is None: parser.error('prepare requires --reader-manifest')
        freeze = prepare(args.output, args.reader_manifest)
    elif args.operation == 'evaluate':
        if args.results is None: parser.error('evaluate requires --results')
        result = evaluate(args.output, args.split, args.results)
        save(args.output/('offline-evaluation-'+args.split+'.json'), result)
        print(json.dumps({k: v for k, v in result.items() if k != 'rows'})); return
    else:
        freeze, *_ = checked(args.output, 'development', expected_freeze_sha256=args.expected_freeze_sha256)
        checked(args.output, 'validation', expected_freeze_sha256=args.expected_freeze_sha256)
    print(json.dumps({'status': 'prepared_offline' if args.operation == 'prepare' else 'verified_offline',
                      'provider_calls': 0, 'partitions': freeze['partitions'], 'final_holdout': freeze['final_holdout']}))


if __name__ == '__main__': main()
