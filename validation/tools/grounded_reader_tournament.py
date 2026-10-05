"""One new v2 paired tournament. Never rewrites PR10/11 or evaluates holdout.

Commands separate free local checks, reviewed provider execution and real
controlled hybrid. Private rows contain pixels-derived observations; aggregates
only may be published. Keys are loaded by the caller, never command arguments.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import platform
import threading
import time

import numpy as np

from bjlab.api_access_policy import require_inference_authorization
from bjlab.grounded_cloud import GroundedCloudReader, GeminiConfig, GeminiTransport, PROMPT
from bjlab.grounded_state import CONTRACT_VERSION, GroundedObservation, GroundedResult, grounded_gate
from bjlab.hybrid_evidence import CurrentEvidence, FrozenGroundedLocal, hybrid_attempt
from bjlab.openai_reader import ResponsesTransport
from validation.tools.api_reader_tournament import budget, config, FrozenLocalObservation, RUNNER_FILES, file_hash
from validation.tools.grounded_corpus import generate, checked_inputs, save, API_CASES, ROOT

EPOCH = '2026-10-05-grounded-v2-eur10'
COMPONENTS = RUNNER_FILES+('bjlab/grounded_state.py', 'bjlab/grounded_cloud.py', 'bjlab/hybrid_evidence.py',
    'validation/tools/grounded_corpus.py', 'validation/tools/grounded_reader_tournament.py')


def freeze_configuration(output):
    output = Path(output)
    configuration = {'contract': CONTRACT_VERSION, 'prompt_sha256': sha256(PROMPT.encode()).hexdigest(),
        'models': {'luna-fast-v2': asdict(config(fast=True)), 'gemini-lite-v2': asdict(GeminiConfig())},
        'source_hashes': {p: file_hash(ROOT/p) for p in COMPONENTS}, 'api_cases': API_CASES,
        'spending_authorization_epoch': EPOCH, 'maximum_new_still_submissions': 12,
        'maximum_new_hybrid_submissions': 6, 'retry_count': 0,
        'acceptance': {'complete_json_deadline_ms': 3000, 'target_p95_ms': 2500, 'false_accepted_states': 0,
            'promotion_requires_independent_provider_sessions': True},
        'visibility_truth': 'all rendered indices/pips geometric proxy plus assistant development audit, not independent human labels',
        'private_provider_pixels': 'excluded_from_both_cloud_candidates', 'local_training_or_tuning': False,
        'routing': 'local integrity/turn/control failure only; never evaluator truth/confidence',
        'revalidation': 'same source/table/pixel-motion epoch, <=250ms capture gap, <=3000ms original capture age'}
    save(output/'configuration.json', configuration)
    return configuration


def checked_configuration(output):
    value = json.loads((Path(output)/'configuration.json').read_text())
    if value['source_hashes'] != {p: file_hash(ROOT/p) for p in COMPONENTS}:
        raise ValueError('Frozen source changed; create a new iteration, do not tune the evaluated candidate.')
    if value['prompt_sha256'] != sha256(PROMPT.encode()).hexdigest(): raise ValueError('Frozen prompt changed.')
    return value


def score(record, result, truth):
    observed = result.observation
    gate = grounded_gate(observed) if observed else {'usable': False, 'reasons': [result.status]}
    expected, predicted = truth['cards'], observed.cards if observed else []
    ranks_expected = Counter((c['zone'], c['rank']) for c in expected if c['rank'])
    ranks_predicted = Counter((c.zone, c.rank) for c in predicted if c.rank)
    suits_expected = Counter((c['zone'], c['rank'], c['suit']) for c in expected if c['suit'])
    suits_predicted = Counter((c.zone, c.rank, c.suit) for c in predicted if c.suit)
    def objects(cards):
        return Counter((c['zone'], c['rank'], c['suit'], c['visibility'] == 'covered') for c in cards)
    expected_objects = objects(expected)
    predicted_objects = objects([c.model_dump() for c in predicted])
    full = expected_objects == predicted_objects
    rank_state = Counter((c['zone'], c['rank'], c['visibility'] == 'covered') for c in expected) == Counter(
        (c.zone, c.rank, c.visibility == 'covered') for c in predicted)
    numbers_expected = Counter((n['role'], n['value']) for n in truth['numbers'])
    numbers_predicted = Counter((n.role, n.value) for n in observed.numbers) if observed else Counter()
    phase = bool(observed and observed.phase == truth['phase'])
    controls = bool(observed and set(observed.controls) == set(truth['controls']))
    expected_player = [c for c in expected if c['zone'] == 'player:0']
    upcards = [c for c in expected if c['zone'] == 'dealer' and c['visibility'] != 'covered']
    opportunity = bool(truth['phase'] == 'player' and len(expected_player) >= 2 and len(upcards) == 1 and
        all(c['rank'] for c in expected_player+upcards) and set(truth['controls']) & {'hit', 'stand'})
    correct_rank_decision = bool(opportunity and rank_state and phase and controls)
    complete = bool(observed and full and phase and controls and numbers_expected == numbers_predicted and
        observed.table_state == truth['table_state'])
    attributed = Counter((n.role,n.value) for n in observed.numbers if n.role.endswith('_total')) if observed else Counter()
    expected_totals = Counter((n['role'],n['value']) for n in truth['numbers'] if n['role'].endswith('_total'))
    false_attribution = bool(attributed-expected_totals)
    return {'case_id': record['id'], 'condition': record['condition'], 'split': record['split'],
        'reader': result.reader, 'status': result.status, 'elapsed_ms': result.elapsed_ms,
        'metrics': {'expected_objects': len(expected), 'predicted_objects': len(predicted),
            'object_inventory_exact': full, 'rank_presence_exact': rank_state,
            'ranks_expected': sum(ranks_expected.values()), 'ranks_correct': sum((ranks_expected & ranks_predicted).values()),
            'suits_expected': sum(suits_expected.values()), 'suits_correct': sum((suits_expected & suits_predicted).values()),
            'unreadable_objects_expected': sum(c['visibility'] == 'unreadable' for c in expected),
            'backs_expected': sum(c['visibility'] == 'covered' for c in expected),
            'backs_predicted': sum(c.visibility == 'covered' for c in predicted),
            'numeric_provenance_exact': numbers_expected == numbers_predicted, 'phase_correct': phase,
            'complete_state_correct': complete, 'player_opportunity': opportunity,
            'correct_usable_rank_state': bool(gate['usable'] and correct_rank_decision and result.elapsed_ms <= 3000),
            'false_total_attribution': false_attribution,
            'false_accepted_state': bool(gate['usable'] and (not correct_rank_decision or false_attribution))},
        'gate': gate, 'observation': observed.model_dump() if observed else None, 'diagnostics': result.diagnostics}


def summaries(rows):
    result = {}
    for name in sorted({r['reader'] for r in rows}):
        data = [r for r in rows if r['reader'] == name]; timing = [r['elapsed_ms'] for r in data if r['status'] == 'completed']
        fields = ('expected_objects','predicted_objects','object_inventory_exact','rank_presence_exact','ranks_expected',
            'ranks_correct','suits_expected','suits_correct','backs_expected','backs_predicted','unreadable_objects_expected',
            'numeric_provenance_exact','phase_correct','complete_state_correct','player_opportunity',
            'correct_usable_rank_state','false_total_attribution','false_accepted_state')
        result[name] = {'planned_inputs': len(data), 'attempted_inputs': sum(r['status'] != 'not_executed' for r in data),
            'statuses': dict(Counter(r['status'] for r in data)),
            'metrics': {f: sum(int(r['metrics'][f]) for r in data) for f in fields},
            'completed_latency_ms': {k: float(np.percentile(timing, p)) if timing else None for k,p in [('p50',50),('p95',95),('max',100)]},
            'reported_usage_upper_usd': str(sum((Decimal(r['diagnostics'].get('price_based_upper_cost_usd','0')) for r in data),Decimal(0))),
            'cost_scope': 'reported usage upper only, not invoice; failures may remain reserved',
            'sample_scope': 'one physical session per partition, correlated scenario variants, not population/provider transfer'}
    return result


def local_compare(output, split):
    checked_configuration(output)
    freeze, inputs, oracle = checked_inputs(output, split)
    rows=[]
    readers = [FrozenGroundedLocal(FrozenLocalObservation()),
        FrozenGroundedLocal(FrozenLocalObservation(specialized_manifest=freeze['reader_manifest']))]
    for record, frame in inputs:
        for reader in readers: rows.append(score(record, reader.read(frame), oracle[record['id']]))
    target = Path(output)/split/'local-results.json'; save(target, rows)
    return {'contract': CONTRACT_VERSION, 'split': split, 'readers': summaries(rows), 'final_holdout': 'sealed_not_evaluated'}


def approved_inputs(output):
    configuration = checked_configuration(output)
    review = json.loads((Path(output)/'upload-review.json').read_text())
    if (review.get('spending_authorization_epoch') != EPOCH or review.get('approved_owned_only') is not True or
        review.get('configuration_sha256') != file_hash(Path(output)/'configuration.json')):
        raise PermissionError('Exact experiment upload review is missing/stale.')
    freeze, inputs, oracle = checked_inputs(output, 'validation')
    hashes = {i['sha256'] for r,_ in inputs for i in r['images']}
    if any(r['evidence_kind'] != 'new-owned-synthetic-v2' or r['split'] != 'validation' for r,_ in inputs):
        raise PermissionError('Only this reviewed owned validation partition may be uploaded.')
    if hashes != set(review['image_sha256']): raise PermissionError('Native crop review does not match.')
    return freeze, inputs, oracle, hashes


def cloud_readers(ceiling, allowed, providers=('gemini-lite-v2','luna-fast-v2')):
    require_inference_authorization(EPOCH)
    if not providers or len(set(providers))!=len(providers) or set(providers)-{'luna-fast-v2','gemini-lite-v2'}:
        raise ValueError('Select only audited declared providers.')
    readers={}
    if 'luna-fast-v2' in providers:
        readers['luna-fast-v2']=GroundedCloudReader(config(fast=True),ceiling,allowed,provider='openai',
            transport=ResponsesTransport(authorization_epoch=EPOCH,budget=ceiling))
    if 'gemini-lite-v2' in providers:
        readers['gemini-lite-v2']=GroundedCloudReader(GeminiConfig(),ceiling,allowed,provider='gemini',
            transport=GeminiTransport(authorization_epoch=EPOCH,budget=ceiling))
    return readers


def cloud_compare(output, providers=('gemini-lite-v2','luna-fast-v2')):
    freeze, inputs, oracle, allowed = approved_inputs(output)
    ceiling=budget(); readers=cloud_readers(ceiling, allowed, providers); rows=[]; stop=None
    claimed=Path(output)/'cloud-execution-claim.json'
    with claimed.open('x',encoding='utf-8') as handle: json.dump({'epoch':EPOCH,'budget_before':ceiling.receipt()},handle)
    for case in API_CASES:
        record,frame=next((r,f) for r,f in inputs if r['id']==case)
        # Identical input and contract for both; alternate ordering to avoid a
        # systematic warm-up advantage. No retry/selection based on correctness.
        names=['gemini-lite-v2','luna-fast-v2'] if API_CASES.index(case)%2==0 else ['luna-fast-v2','gemini-lite-v2']
        names=[name for name in names if name in providers]
        for name in names:
            result = readers[name].read(frame) if stop is None else GroundedResult(frame.frame_id,name,'not_executed',None,0,{'reason':stop})
            rows.append(score(record,result,oracle[case])); save(Path(output)/'cloud-private-results.json',rows)
            if result.status in ('timeout','blocked') or result.diagnostics.get('http_status') or (
                    result.status != 'not_executed' and result.diagnostics.get('price_based_upper_cost_usd') is None):
                stop='uncertain_charge_or_budget_or_provider_failure; no automatic retry'
            print(json.dumps({'case':case,'reader':name,'status':result.status,'elapsed_ms':round(result.elapsed_ms), 'stop':stop}),flush=True)
    report={'contract':CONTRACT_VERSION,'scope':'new paired owned validation diagnostics; no universal/provider/live promotion',
        'readers':summaries(rows),'selected_providers':list(providers),'stop_reason':stop,
        'budget':ceiling.receipt(),'final_holdout':'sealed_not_evaluated'}
    save(Path(output)/'cloud-summary.json',report);return report


def controlled_hybrid(output, providers=('gemini-lite-v2','luna-fast-v2')):
    freeze,inputs,oracle,allowed=approved_inputs(output);ceiling=budget();cloud=cloud_readers(ceiling,allowed,providers)
    lookup={r['id']:(r,f) for r,f in inputs};rows=[];stopped=False
    with (Path(output)/'hybrid-execution-claim.json').open('x') as handle:json.dump({'epoch':EPOCH,'budget_before':ceiling.receipt()},handle)
    for name in providers:
        for local_kind,change in (('current-local',False),('specialized-local',False),('specialized-local',True)):
            if stopped: break
            record,frame=lookup['rotation'];empty=lookup['empty'][1]
            evidence=CurrentEvidence();done=threading.Event();ready=threading.Event();origin=time.monotonic()
            def producer():
                while not done.is_set():
                    pixels=empty if change and time.monotonic()-origin >= .65 else frame
                    evidence.capture(pixels,source='owned-simulator',table='validation')
                    ready.set();done.wait(1/12)
            thread=threading.Thread(target=producer,name='owned-pixel-capture',daemon=True);thread.start();ready.wait(2)
            try:
                local=FrozenGroundedLocal(FrozenLocalObservation(specialized_manifest=freeze['reader_manifest'] if local_kind == 'specialized-local' else None))
                row=hybrid_attempt(evidence,local,cloud[name]);latest,_=evidence.snapshot()
                row.update(candidate=name,local_candidate=local_kind,scenario='changed_during_request' if change else 'stable',
                    captures_during_read=latest.sequence if latest else 0)
                observed=row.get('observation')
                score_result=GroundedResult(frame.frame_id,name,row.get('status','not_executed'),
                    GroundedObservation.model_validate_json(json.dumps(observed)) if observed else None,
                    row.get('timing',{}).get('capture_to_headless_presentation_ms',0),{})
                measured=score(record,score_result,oracle['rotation'])
                row['correct_presented_state']=bool(row['presented'] and not change and measured['metrics']['correct_usable_rank_state'])
                row['false_presented_state']=bool(row['presented'] and (change or measured['metrics']['false_accepted_state']))
                rows.append(row);save(Path(output)/'hybrid-private-results.json',rows)
                if row.get('status') in ('timeout','blocked') or row.get('diagnostics',{}).get('http_status') or (
                    row['route'] == 'fallback' and row.get('diagnostics',{}).get('price_based_upper_cost_usd') is None): stopped=True
                print(json.dumps({'candidate':name,'scenario':row['scenario'],'route':row['route'],'presented':row['presented'],
                    'captures':row['captures_during_read'],'false_presented':row['false_presented_state']}),flush=True)
            finally:
                done.set();thread.join(2);evidence.disconnect()
    summary={'scope':'real API plus continuous generated native pixels to headless advisor payload; not physical desktop/native paint',
        'selected_providers':list(providers),'planned_trials':3*len(providers),'executed_trials':len(rows),
        'fallback_requests':sum(r['route']=='fallback' for r in rows),
        'correct_presented_states':sum(r['correct_presented_state'] for r in rows),
        'false_presented_states':sum(r['false_presented_state'] for r in rows),
        'expired_or_changed_states_withheld':sum(not r['presented'] and r.get('revalidation',{}).get('valid') is False for r in rows),
        'rows':[{k:r.get(k) for k in ('candidate','local_candidate','scenario','route','status','presented','correct_presented_state','false_presented_state','captures_during_read','revalidation','timing')} for r in rows],
        'budget':ceiling.receipt(),'r2_certified':False,'final_holdout':'sealed_not_evaluated'}
    save(Path(output)/'hybrid-summary.json',summary);return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['generate','local','cloud','hybrid'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reader-manifest',type=Path)
    parser.add_argument('--split',choices=['development','validation'],default='development')
    args=parser.parse_args()
    if args.command=='generate': report=generate(args.output,args.reader_manifest);freeze_configuration(args.output)
    elif args.command=='local': report=local_compare(args.output,args.split)
    elif args.command=='cloud': report=cloud_compare(args.output)
    else:report=controlled_hybrid(args.output)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
