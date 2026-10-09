"""Publish explicitly selected aggregates, never private pixels/cases/paths.

Reads completed local experiments. Original receipts and failed experiments are
preserved. This does not retrain, select a model or evaluate a final holdout.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish(artifacts,session_receipt,comparison):
    artifacts=Path(artifacts);session_receipt=Path(session_receipt);comparison=Path(comparison)
    matrix=read(ROOT/'docs/VISION_EXPERIMENTS.json')
    history=matrix['comparison']
    history['detector_version']='calibrated-corners-1 (historical)'
    for name,result in history['aggregates'].items():
        supported=name!='ultralytics-corners';result['suits_supported']=supported
        if not supported:
            result['suit_correct_including_misses']=None
            suit=None
        elif name=='calibrated-corners':
            suit={'correct':4,'wrong':0,'unknown':5,'missed':0}
        else:
            suit={'correct':0,'wrong':0,'unknown':3,'missed':6}
        result['outcomes']={'suit':suit}
    current=read(comparison)
    matrix['latest_comparison']={k:current[k] for k in (
        'scope','hardware','source_fingerprint','manifest_sha256','metrics_semantics',
        'timing_protocol','timing_environment','selection','not_measured','aggregates',
        'localizer_checkpoint_sha256','operating_points_sha256')}
    matrix['latest_comparison'].update(detector_version='calibrated-corners-2-presence',
        raw_report_sha256=sha(comparison),
        assistance='All challengers use the same manual dealer/player regions and manual turn. Automatic baselines have their original contracts.',
        full_card_geometry_warning='Learned corners infer approximate card bodies from glyph boxes; IoU .30 is a diagnostic proxy, not corner detection AP.')
    checks=[]
    for name in ('learning-scratch','learning-pretrained','learning-corner','learning-corner-refine'):
        path=artifacts/name/'learning.json';r=read(path)
        checks.append({k:r[k] for k in ('initialization','classes','train_images','train_annotations',
            'ultralytics','torch','imgsz','requested_epochs','actual_epochs','budget_seconds',
            'wall_seconds','dataset_sha256','checkpoint_sha256','validation_metrics')})
        checks[-1].update(id=name,task=r.get('task','rank'),receipt_sha256=sha(path),
            fixed_gate={k:v for k,v in r['after'].items() if k!='rows'},
            learning_gate=r['after']['learning_gate'],
            finding=f"Memorized train mAP50 {r['validation_metrics']['metrics/mAP50(B)']:.3f}; at the fixed .50 threshold {r['after']['localized']}/96 localized. No independent validation.",
            decision='Not promoted; retain failed .50 gate and completed checkpoint.',
            suits_supported=False,
            origin_sha256=(r.get('origin') or {}).get('sha256'))
    points_path=artifacts/'learning-corner/operating-points.json';points=read(points_path)
    checks[2]['finding']+=' Development score/NMS diagnostic selects .025: 92/96 localized, four missed, one extra. This permits only a development comparison.'
    checks[2]['decision']='Compared on private development stills; 29 extra objects, 0/3 usable. Do not promote.'
    checks[3]['finding']+=' Thirty additional epochs retain the same best metrics; extra time did not improve this checkpoint.'
    matrix['learning_checks']=checks
    matrix['learning_operating_point']={k:points[k] for k in ('scope','checkpoint_sha256','rule',
        'grid','nms_iou','matching_iou','fixed_050_gate_preserved','rows','selected',
        'can_proceed_to_development_roi_comparison','rank_and_suit_classifiers')}
    sessions=read(session_receipt)
    matrix['own_development_sessions']={
        'scope':sessions['protocol']['scope'], 'protocol':sessions['protocol'],
        'dataset_manifest_sha256':sessions['dataset_manifest_sha256'],
        'receipt_sha256':sha(session_receipt),
        'sessions':[{k:v for k,v in s.items() if k!='rows'} for s in sessions['sessions']],
        'same_size_drift_probe':sessions['same_size_drift_probe'],
        'selection':sessions['selection'],
        'count_loss_diagnostics':[{
            'seed':s['seed'],'round':row['round'],'native_phase':row['phase'],
            'detected_phase':row['detected_phase'],'detected_round':row['detected_round'],
            'lifecycle':row['lifecycle'],'events':row['state_events'],
            'ranks_correct':row['ranks_correct'],'visible_faces':row['visible_faces'],
            'inventory_l1_error':row['inventory_l1_error'],
            'expected_inventory':row['expected_inventory'],'observed_inventory':row['observed_inventory'],
            'reasons':row['reasons']
        } for s in sessions['sessions'] for i,row in enumerate(s['rows'])
          if row['inventory_l1_error'] and (i==0 or row['inventory_l1_error']!=s['rows'][i-1]['inventory_l1_error'])]
    }
    brief=read(artifacts/'calibration-sessions-v2/result.json')
    matrix['brief_exposure_negative']={
        'scope':brief['protocol']['scope'],'stable_observations_per_state':3,
        'receipt_sha256':sha(artifacts/'calibration-sessions-v2/result.json'),
        'sessions':[{k:v for k,v in s.items() if k!='rows'} for s in brief['sessions']],
        'finding':'Final inventory L1 17/18/19 despite all current ranks read; RC errors 0/+5/-5 can hide inventory loss. Six observations were a separate development sensitivity check, not acceptance.'}
    rejected=read(artifacts/'comparison-presence.json')['aggregates']['calibrated-corners']
    matrix['rejected_presence_variant']={
        'scope':'development-only broader red/blue back geometry before refinement',
        'receipt_sha256':sha(artifacts/'comparison-presence.json'),
        'ranks_correct':rejected['correct_zone_ranks'],
        'presence_outcomes':rejected['presence_outcomes'],
        'decision':'Rejected: face artwork/chips produced extra objects and suppressed a rank. Current blue-only bounded rule is not universal back recognition.'}
    findings={
        'localization':'Calibrated presence v2: 10/10 objects on two development moments; learned-corner/OCR adapter: 6/10 matched, 29 extra. No promotion.',
        'ranks':'Calibrated 9/9; learned-corner/OCR 5/9 geometrically matched, inventory intersection 8/9 can hide assignment errors. Development only.',
        'suits':'Calibrated four correct, zero wrong, five unknown. Rank-only YOLO pilot does not support suits; learned adapter uses silhouette templates, not a learned suit classifier.',
        'temporal':'Own renderer: three observations/state lose inventory 17/18/19; six retain errors 0/4/4. This sensitivity check is not external-video validation.',
        'context':'Manual turn required. Direct-settlement hands with no observable phase/boundary account for four lost exposures in two own sequences. No strategy or count promotion.',
        'integrity':'Calibrated stills: only 1/3 correctly usable despite 9/9 ranks. Unreadable player cards/cropped surfaces block advice. Research RC/TC never certified.',
        'roi':'Source dimension/crop changes invalidate calibration. Touching a role edge blocks the tested cropped-card case. Same-size motion wholly inside ROI is not automatically recalibration; arbitrary scroll not certified.'}
    for stage in matrix['stages']:
        if stage['id'] in findings:
            stage['finding']=findings[stage['id']];stage['status']='executed'
    matrix['stages']=[s for s in matrix['stages'] if s['id']!='learning']
    matrix['stages'].append({'id':'learning','stage':'Learning diagnostic',
        'candidate':'scratch / official pretrained rank / pretrained geometry + shared OCR',
        'status':'executed','finding':'Audited 160 synthetic images/960 labels. Geometry learns memorized corners after development score/NMS selection; provider comparison still fails. No final holdout read.'})
    matrix['ultralytics_training']['suits_supported']=False
    matrix['parent_commit']='620e6a0dd7f929a116645c53181b4df360b8edbd'
    matrix['decision']='No detector promoted. Failed scratch pilot preserved; bounded geometry learning demonstrated only on memorized development examples. Calibrated profile remains research-only.'
    (ROOT/'docs/VISION_EXPERIMENTS.json').write_text(json.dumps(matrix,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    target=ROOT/'validation/results/vision-learning-check';target.mkdir(parents=True,exist_ok=True)
    summary={k:matrix[k] for k in ('schema','baseline','parent_commit','publication','latest_comparison',
        'learning_checks','learning_operating_point','own_development_sessions','brief_exposure_negative',
        'rejected_presence_variant','decision')}
    (target/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',required=True);parser.add_argument('--sessions',required=True)
    parser.add_argument('--comparison',required=True)
    args=parser.parse_args();publish(args.artifacts,args.sessions,args.comparison)
