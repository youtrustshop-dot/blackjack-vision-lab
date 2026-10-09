"""Prepare five new owned session states for the frozen table-only JSON variant.

Offline only: no credential, access, inference, ledger mutation or holdout read.
Natural engine state drives pixels; separate oracle is never given to readers.
"""
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import argparse
import json
from pathlib import Path

from PIL import ImageDraw

from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_cloud import PROMPT
from bjlab.live_state import CONTRACT_VERSION, LiveObservation
from bjlab.numeric_provenance import POLICY_VERSION, semantic_gate
from bjlab.research_budget import CANONICAL_LEDGER
from bjlab.state_reader import analysis_gate, prepare_frame
from validation.tools.api_reader_tournament import ROOT, FrozenLocalObservation, file_hash, native_record
from validation.tools.gemini_request_ablation import request_payload, native_view_audit
from validation.tools.grounded_corpus import SYMBOL_FONT, font, save
from validation.tools.numeric_semantic_score import semantic_score
from validation.tools.paired_cloud_prepare import render_case, live_truth, local_snapshot, allowed_number_views, digest
from validation.tools.paired_semantic_prepare import CASES as CONSUMED_CASES
from validation.tools.state_reader_comparison import load_frame, score_state
from validation.tools.stress_lab import LAYOUT, timeline

OUTPUT = ROOT/'artifacts/gemini-new-session-20261008-frozen'
PR23 = ROOT/'artifacts/gemini-five-diagnostics-20261008'
OLD = ROOT/'artifacts/paired-semantic-hybrid-20261006'
CASES = (
    ('new-labelled-total', 'labelled-totals', 91008011, 'candarab.ttf', '#31463e', '#fff9ec', True),
    ('new-rotated-ui', 'rotation', 91008019, 'constanb.ttf', '#504262', '#fcf4fc', True),
    ('new-overlap-index', 'overlap', 91008029, 'tahomabd.ttf', '#263b63', '#fffff4', True),
    ('new-unreadable', 'popup-unreadable', 91008037, 'comicbd.ttf', '#4a392f', '#fffbef', False),
    ('new-settled', 'disabled-controls', 91008047, 'corbelb.ttf', '#3b4850', '#f9f8fe', False),
)
ORDER = tuple(row[0] for row in CASES)
GATE = {'positive_cases': 3, 'negative_cases': 2, 'required_correct_timely_r1': 3,
    'required_correct_abstentions': 2, 'false_accepts': 0, 'exact_card_inventory': 5,
    'deadline_ms': 3000, 'p95': None,
    'scope': 'Tiny new-session owned validation gate; no champion, R2 or provider transfer certification.'}
SOURCES = ('validation/tools/gemini_new_session_prepare.py',
    'validation/tools/gemini_request_ablation.py', 'validation/tools/paired_cloud_prepare.py',
    'validation/tools/grounded_corpus.py', 'validation/tools/stress_lab.py',
    'validation/tools/api_reader_tournament.py', 'validation/tools/numeric_semantic_score.py',
    'bjlab/live_cloud.py', 'bjlab/live_state.py', 'bjlab/numeric_provenance.py',
    'bjlab/hybrid_evidence.py', 'bjlab/grounded_state.py', 'bjlab/state_reader.py')


def table_only(image):
    return replace(prepare_frame(image, LAYOUT), details=())


def corpus_case(spec):
    name, condition, seed, basename, felt, paper, usable = spec
    stages = timeline(seed, 12)
    phase = 'settled' if condition == 'disabled-controls' else 'player'
    stage = next(s for s in stages if s['phase'] == phase)
    family = (seed, 'owned-new-'+name+'-'+basename, 'C:/Windows/Fonts/'+basename, felt, paper)
    image, truth, visibility = render_case(stage, condition, family)
    if condition == 'rotation':
        draw = ImageDraw.Draw(image); printed = font('C:/Windows/Fonts/arialbd.ttf', 25)
        draw.text((910, 130), '20', font=printed, fill='white', anchor='lt')
        x, y, r, b = draw.textbbox((910, 130), '20', font=printed, anchor='lt')
        truth['numbers'].append({'value':20, 'role':'unknown', 'label':None, 'view':'table',
            'box':[x/1024,y/768,(r-x)/1024,(b-y)/768]})
    frame = table_only(image); native_view_audit(frame)
    observed = live_truth(truth)
    if semantic_gate(observed, available_views={'table'})['usable'] != usable:
        raise ValueError('Predeclared decision/abstention case differs; never rig cards to fit it.')
    return frame, observed, truth, visibility, stage, family


def prepare(output=OUTPUT):
    # Historical summaries and consumed developmental metadata only; no final split.
    previous = json.loads((PR23/'summary.json').read_text())
    if previous['attempted_diagnostics'] != 5 or previous['stop'] is not None:
        raise PermissionError('The five diagnostic controls have not completed.')
    ledger_before = file_hash(CANONICAL_LEDGER)
    old_freeze = json.loads((OLD/'freeze.json').read_text())
    local = local_snapshot(old_freeze['frozen_local']['manifest'])
    if set(s[2] for s in CASES) & set(s[2][0] for s in CONSUMED_CASES):
        raise ValueError('New sessions overlap consumed sessions.')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    directory = output/'inputs'; directory.mkdir()
    records, truths, masks = [], {}, {}
    consumed = json.loads((OLD/'inputs/oracle.json').read_text())
    signatures = lambda t: sorted((c['zone'],c['rank'] or '',c['suit'] or '',c['visibility']) for c in t['cards'])
    for spec in CASES:
        frame, observation, truth, visibility, stage, family = corpus_case(spec)
        name, condition, seed, basename, _, _, usable = spec
        expected = {**observation.model_dump(), 'number_views':allowed_number_views(truth, frame.layout)}
        if any(signatures(expected) == signatures(value) for value in consumed.values()):
            raise ValueError('New hand duplicates a consumed control.')
        record = native_record(directory, name, frame, split='new_validation',
            independent_session='gemini-new-'+str(seed), seed=seed, family=family[1],
            condition=condition, hand_group=str(seed)+':'+str(stage['round']),
            evidence_kind='new-owned-natural-session; shared renderer, not provider transfer',
            expected_usable_r1=usable)
        payload = request_payload(frame,'json-mode'); path=directory/name/'gemini.request.json'
        save(path,payload); record['payload']={'file':name+'/'+path.name,
            'sha256':file_hash(path), 'canonical_sha256':digest(payload)}
        if sum('inlineData' in part for part in payload['contents'][0]['parts']) != 1:
            raise ValueError('Only one table image is allowed.')
        records.append(record); truths[name]=expected; masks[name]=visibility
    save(directory/'frames.json',records); save(directory/'oracle.json',truths)
    save(directory/'visibility-evidence.json',masks)
    # Contact sheet is diagnostic only; individual original PNGs are reviewed.
    from PIL import Image
    sheet=Image.new('RGB',(3*512,2*414),'#111a22'); draw=ImageDraw.Draw(sheet)
    for i,record in enumerate(records):
        frame=load_frame(directory,record); image=Image.open(BytesIO(frame.table_png))
        x,y=(i%3)*512,(i//3)*414; sheet.paste(image.resize((512,384)),(x,y))
        draw.text((x+7,y+387),record['id'],font=font('C:/Windows/Fonts/arialbd.ttf',17),fill='white')
    sheet.save(directory/'contact-sheet.png')
    frozen={'experiment':'VISION-030','parent_commit':'d9216ba', 'order':list(ORDER),
        'gate':GATE,'candidate':'PR23 D table-only JSON MIME; frozen model/prompt/caps/gates',
        'contract':CONTRACT_VERSION,'policy':POLICY_VERSION,'prompt_sha256':sha256(PROMPT.encode()).hexdigest(),
        'batch_worst_reservation_usd':str(5*GeminiConfig().reserve_usd), 'maximum_inferences':5,
        'diagnostic_wait_ms':10000,'original_live_deadline_ms':3000,'advisor_connected':False,
        'frozen_local':local, 'source_sha256':{p:file_hash(ROOT/p) for p in SOURCES},
        'files':{str(p.relative_to(output)):file_hash(p) for p in directory.rglob('*') if p.is_file()},
        'font_sha256':{s[3]:file_hash('C:/Windows/Fonts/'+s[3]) for s in CASES},
        'symbol_font_sha256':file_hash(SYMBOL_FONT),'ledger_before_sha256':ledger_before,
        'sessions':5,'new_provider_calls':0,'new_training':False,'final_holdout':'not_opened',
        'truth_scope':'Owned renderer masks plus assistant original-pixel review; not independent human/provider truth.',
        'shared_components':['owned rectangular artwork renderer','layout','Arial controls','Segoe UI Symbol suits']}
    if file_hash(CANONICAL_LEDGER) != ledger_before:
        raise PermissionError('Offline preparation changed or raced with ledger.')
    save(output/'freeze.json',frozen)
    return frozen


def checked(output, external_hash):
    output=Path(output)
    if file_hash(output/'freeze.json') != external_hash:
        raise PermissionError('External preparation freeze changed.')
    frozen=json.loads((output/'freeze.json').read_text())
    if frozen['order'] != list(ORDER) or frozen['gate'] != GATE:
        raise PermissionError('Frozen cases/gates changed.')
    for name,digest_value in frozen['source_sha256'].items():
        if file_hash(ROOT/name) != digest_value: raise PermissionError('Frozen source changed: '+name)
    for name,digest_value in frozen['files'].items():
        path=(output/name).resolve()
        if not path.is_relative_to(output.resolve()) or file_hash(path) != digest_value:
            raise PermissionError('Frozen image/payload/reference changed.')
    if local_snapshot(frozen['frozen_local']['manifest']) != frozen['frozen_local']:
        raise PermissionError('Frozen local weights changed.')
    for name,digest_value in frozen['font_sha256'].items():
        if file_hash('C:/Windows/Fonts/'+name) != digest_value:
            raise PermissionError('Frozen artwork font changed.')
    if file_hash(SYMBOL_FONT) != frozen['symbol_font_sha256']:
        raise PermissionError('Frozen suit font changed.')
    rows=json.loads((output/'inputs/frames.json').read_text())
    if [r['id'] for r in rows] != list(ORDER) or len({r['independent_session'] for r in rows}) != 5:
        raise PermissionError('Five unique predeclared sessions are required.')
    frames={r['id']:(r,load_frame(output/'inputs',r)) for r in rows}
    for record,frame in frames.values():
        if frame.details or native_view_audit(frame)['checked_details']:
            raise PermissionError('Table-only candidate acquired extra views.')
    return frozen,frames,json.loads((output/'inputs/oracle.json').read_text())


def compare_local(output, external_hash):
    frozen,frames,truths=checked(output,external_hash)
    rows=[]
    for reader in (FrozenLocalObservation(),FrozenLocalObservation(specialized_manifest=frozen['frozen_local']['manifest'])):
        for name,(record,frame) in frames.items():
            result=reader.read(frame); actual=result.observation
            metrics=score_state(actual,truths[name]); gate=analysis_gate(actual,require_turn=True)
            # Preserve arbitrary local blockers and unsupported numeric provenance.
            # A projected compatible transcription cannot overrule the actual gate.
            value=actual.model_dump()
            try:
                projected=LiveObservation(cards=value['cards'],table_state=value['table_state'],
                    phase=value['phase'],controls=value['controls'],numbers=[],blockers=[])
                shared=semantic_score(projected,truths[name],elapsed_ms=result.elapsed_ms,available_views={'table'})
            except ValueError:
                shared=semantic_score(None,truths[name],status='error',elapsed_ms=result.elapsed_ms,available_views={'table'})
            correct=bool(gate['usable'] and shared['semantic_timely_correct_usable_r1'])
            rows.append({'case':name,'reader':reader.name,'elapsed_ms':result.elapsed_ms,
                'expected_usable_r1':record['expected_usable_r1'],'actual_local_gate':gate,
                'card_transcription':metrics,'projected_transcription_only':shared,
                'correct_timely_r1':correct,'correct_abstention':not record['expected_usable_r1'] and not gate['usable'],
                'false_accept':gate['usable'] and (not record['expected_usable_r1'] or not correct),
                'numeric_provenance_supported':False})
    target=Path(output)/'local-comparison.json'
    with target.open('x',encoding='utf-8') as handle: json.dump(rows,handle,indent=2)
    return rows


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--prepare',action='store_true'); parser.add_argument('--local',action='store_true')
    parser.add_argument('--freeze-sha256'); args=parser.parse_args()
    if args.prepare:
        if args.local: parser.error('Preparation and local comparison are separate.')
        result=prepare(args.output)
        print(json.dumps({'prepared':5,'provider_calls':0,'freeze_sha256':file_hash(args.output/'freeze.json')}))
    else:
        if not args.freeze_sha256: parser.error('External preparation hash required.')
        result=compare_local(args.output,args.freeze_sha256) if args.local else checked(args.output,args.freeze_sha256)[0]
        print(json.dumps({'offline_completed':True,'provider_calls':0}))
