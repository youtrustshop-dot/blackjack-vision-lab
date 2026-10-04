"""Publish only synthetic aggregate receipts after an unchanged frozen run."""
from collections import Counter
import csv
import io
import json
from pathlib import Path
import subprocess

from validation.tools.overlap_session import digest, save, sources


def main():
    root=Path.cwd(); private=root/'artifacts/stress-lab/overlap-final-20261004'
    freeze=json.loads((private/'freeze.json').read_text(encoding='utf-8'))
    if freeze['candidate_source_hashes']!=sources(root): raise ValueError('Candidate differs from pre-verification freeze')
    if freeze['evaluator_sha256']!=digest(root/'validation/tools/overlap_session.py'): raise ValueError('Evaluator changed')
    reference=freeze['baseline_commit']
    historical={}
    for file in (root/'validation/results/visible-phase').glob('*'):
        relative=file.relative_to(root).as_posix()
        if file.read_bytes()!=subprocess.check_output(['git','show',f'{reference}:{relative}']):
            raise ValueError('Historical phase evidence changed')
        historical[relative]=digest(file)
    records={}; flat=[]; groups=[]
    revisions={'baseline':reference,'candidate':'ef769f542c4a8c44ce6769096ca546425ce02398'}
    for partition in ('development','verification'):
        records[partition]={}
        for reader in ('baseline','candidate'):
            p=private/partition/reader/'result.json'; record=json.loads(p.read_text(encoding='utf-8'))
            if record['evaluator_sha256']!=freeze['evaluator_sha256']: raise ValueError('Executed evaluator not frozen')
            if reader=='candidate' and record['source_hashes']!=freeze['candidate_source_hashes']: raise ValueError('Wrong executed candidate')
            import hashlib
            for relative,value in record['source_hashes'].items():
                committed=subprocess.check_output(['git','show',f'{revisions[reader]}:{relative}'])
                if hashlib.sha256(committed).hexdigest()!=value: raise ValueError('Executed source does not match named Git revision')
            if record['api_requests']!=0: raise ValueError('API calls not authorized')
            records[partition][reader]=record
            selected={a['group'] for a in record['results']}
            for group in sorted(selected):
                for profile in ('clean','overlap'):
                    items=[a for a in record['results'] if a['group']==group and a['profile']==profile]
                    metrics=Counter(); [metrics.update(a['metrics']) for a in items]
                    exposures=Counter(); [exposures.update(a['exposures']) for a in items]
                    row={'partition':partition,'group':group,'reader':reader,'profile':profile,
                        'sessions':len(items),'opportunities':sum(a['opportunities'] for a in items),
                        'r1_timely':sum(a['r1_timely'] for a in items),'table_timely':sum(a['table_timely'] for a in items),
                        'backs_correct':metrics['correct_backs'],'backs_expected':metrics['expected_backs'],
                        'missing_exposures':exposures['missing'],'duplicate_exposures':exposures['duplicate'],
                        'wrong_exposures':exposures['wrong_or_unmatched'],'id_switches':exposures['id_switches'],
                        'inventory_final_max_l1':max(a['inventory_final_l1'] for a in items),
                        'wrong_basic_observations':metrics['wrong_or_stale_basic_advice'],
                        'certified_count_observations':metrics['certified_count_observations']}
                    flat.append(row)
                    groups.append({**row,'metrics':dict(metrics),'exposures':dict(exposures),
                        'source_confirmation_ms':[a['confirmation_delay_ms'] for a in items],
                        'offline_processing_ms':[a['offline_processing_ms'] for a in items]})
    target=root/'validation/results/overlap-session'
    receipt={'schema':1,'baseline_commit':reference,'inference_commit':'ef769f542c4a8c44ce6769096ca546425ce02398',
        'freeze':freeze,'historical_phase_evidence_unchanged':historical,'historical_qualified_coverage':'6/36',
        'records':records,'aggregates':groups,'tests':{'python_passed':529,'subtests_passed':10,
            'warnings':2,'seconds':88.33,'frontend_local':'not rerun; no UI changes','native':'not built/tested'},
        'decision':'Retain opt-in synthetic rank/presence challenger; reject default/desktop and certified R2 promotion.',
        'scope':'Two new three-round seeds, two paired profiles and two paired graphic groups. Six underlying hands, seven decision opportunities, not 28 independent opportunities.',
        'api_requests':0,'training':False,'desktop_replaced':False}
    save(target/'comparison.json',receipt)
    table=io.StringIO(newline=''); writer=csv.DictWriter(table,fieldnames=list(flat[0])); writer.writeheader(); writer.writerows(flat)
    (target/'comparison.csv').write_text(table.getvalue(),encoding='utf-8')
    save(target/'verification.json',{'baseline_commit':reference,'inference_commit':receipt['inference_commit'],
        'candidate_matches_pre_verification_freeze':True,'evaluator_matches_freeze':True,
        'historical_evidence_unchanged':True,'new_inputs_checked_by_sha256':True,
        'no_tuning_after_verification':True,'tests':receipt['tests'],'api_requests':0,
        'timing_scope':'Offline replay. Baseline and candidate ran concurrently on the same host; this is not a controlled hardware speed comparison.'})
    matrix_path=root/'docs/VISION_EXPERIMENTS.json'; matrix=json.loads(matrix_path.read_text(encoding='utf-8'))
    stage={'id':'overlap-presence-identity','stage':'Upright overlap presence, physical identity and disabled-control regression',
        'candidate':'unchanged ranks + patterned blue-back localization + ordered row association + enabled control evidence',
        'status':'executed','finding':'Development overlap 6/6 R1 and full-table opportunities, 20/20 exposure identities, no miss/duplicate. New original graphics 7/7 per profile; graphic variations 0/7 per profile despite complete rank/presence tables. Provisional identity switches remain; no R2/default promotion.',
        'evidence':'validation/results/overlap-session/comparison.json'}
    matrix['stages']=[s for s in matrix['stages'] if s['id']!=stage['id']]; matrix['stages'].insert(0,stage)
    iteration={'experiment_id':'VISION-013','parent_experiment_id':'VISION-012','status':'executed',
        'question':'Can separate patterned-back presence and row identity repair overlap without losing clean, then transfer without tuning?',
        'split':'development plus two new verification seeds; paired graphics, no provider/final holdout',
        'reader_id':'visible-overlap-temporal-v2; rank detector unchanged',
        'assistance':'initial card/control ROIs only; no per-turn confirmations; evaluator truth never enters observer',
        'budget':{'max_requests':0,'max_cost':0},'result':stage['evidence'],'report':'docs/OVERLAP_SESSION_COMPARISON.md',
        'decision':receipt['decision'],'what_was_not_tested':['Independent provider sessions','Live capture-to-display',
            'Native minimized capture and monitor/DPI checks','Poker/suit completeness','Rotation/fading/crop changes','Final holdout']}
    matrix['iterations']=[i for i in matrix['iterations'] if i['experiment_id']!='VISION-013']; matrix['iterations'].append(iteration)
    matrix['current_priority']='VISION-013 finished. Rank-only R1 is usable within original synthetic calibrated hit/stand graphics; graphic transfer and provisional identities fail. No default, certified R2 or installed-app promotion. Decide explicit app research integration separately.'
    save(matrix_path,matrix)
    print(json.dumps(flat,indent=2))


if __name__=='__main__': main()
