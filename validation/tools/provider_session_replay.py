"""Replay original local provider recordings, with truth isolated from inference.

No model fitting, repeated still frames, simulator metadata or external uploads.
Private traces contain per-observation evidence; public receipts contain aggregate
metrics and hashes only. This is an offline replay, not capture-to-display timing.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import platform
import time

RANKS=('A','2','3','4','5','6','7','8','9','10','J','Q','K')
SUITS=('S','H','D','C')
ACTIONS=('hit','stand','double','split','surrender','insurance','decline_insurance')
POLICY={'sample_interval_ms':350,'advice_deadline_ms':1500,
        'min_timely_decision_coverage':.95,'min_rounds_per_verification_session':20,
        'min_verification_sessions':2,'max_false_advice_frames':0,
        'max_inventory_l1_at_checkpoints':0,'max_unmatched_exposures':0,
        'max_false_reliable_count_frames':0,'max_manual_interventions':0}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def candidate_fingerprint():
    root=Path(__file__).resolve().parents[2]
    files=sorted((root/'bjlab').glob('*.py'))+[Path(__file__).resolve()]
    sources={str(f.relative_to(root)).replace('\\','/'):digest(f) for f in files}
    return hashlib.sha256(json.dumps({'sources':sources,'runtime':runtime_versions()},sort_keys=True).encode()).hexdigest()


def runtime_versions():
    from importlib.metadata import version,PackageNotFoundError
    result={'python':platform.python_version()}
    for name in ('numpy','Pillow','opencv-python-headless','onnxruntime'):
        try:result[name]=version(name)
        except PackageNotFoundError:result[name]=None
    return result


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


@dataclass(frozen=True)
class ReplayInput:
    """Only capture/configuration fields cross into the recognition path."""
    session_id:str
    video:Path
    source_size:tuple[int,int]
    layout:dict
    rules:dict
    sample_interval_ms:int=350


def validate_manifest(path):
    path=Path(path);doc=read_json(path)
    if doc.get('schema')!=1 or doc.get('layout_family')!='freegames-classic':
        raise ValueError('This increment is restricted to the declared Freegames classic layout')
    if doc.get('policy')!=POLICY:
        raise ValueError('Use the versioned, frozen session policy; do not tune on verification results')
    if not doc.get('sessions'):
        raise ValueError('No original provider recordings supplied; no session benchmark has been executed')
    if doc.get('candidate_fingerprint')!=candidate_fingerprint():
        raise ValueError('Candidate code changed since protocol freeze; do not silently reuse verification')
    from bjlab.corner_vision import validate_layout
    from bjlab.engine import Rules
    seen_ids=set();seen_hashes=set();seen_runs=set();prepared=[]
    for row in doc['sessions']:
        if row['partition'] not in ('development','verification'):
            raise ValueError('Consumed final holdouts cannot be reused by this runner')
        if row['session_id'] in seen_ids or row['capture_run_id'] in seen_runs:
            raise ValueError('One recording run per session; splitting one run cannot create independence')
        if row['video_sha256'] in seen_hashes:raise ValueError('Duplicate video in session partitions')
        if row.get('authorization')!={'local_analysis':True,'external_upload':False}:
            raise ValueError('Original recordings need explicit local-analysis authorization')
        if row.get('input_kind')!='original-provider-video' or not row.get('provenance'):
            raise ValueError('Original provider video and provenance required; rendered/still/photo inputs are excluded')
        if not row.get('rules_provenance') or not row.get('annotation_review'):
            raise ValueError('Declare rules assumptions and annotation reviewer/method')
        config=row['config']
        if set(config)!={'layout','rules'}:
            raise ValueError('Only initial layout and rules enter inference; turn/phase/round IDs are forbidden')
        regions=validate_layout(config['layout']);Rules(**config['rules'])
        table=regions['table']
        for name,region in regions.items():
            if name!='table' and not (region.x>=table.x and region.y>=table.y and
                    region.x+region.width<=table.x+table.width+1e-9 and
                    region.y+region.height<=table.y+table.height+1e-9):
                raise ValueError('All calibrated regions must be inside the native table crop')
        size=row['source_size']
        if len(size)!=2 or any(type(v)!=int or v<=0 for v in size):raise ValueError('Native source size required')
        video=(path.parent/row['video']).resolve();labels=(path.parent/row['annotations']).resolve()
        if not video.is_file() or not labels.is_file():raise ValueError('Original video or annotation file is missing')
        if digest(video)!=row['video_sha256'] or digest(labels)!=row['annotations_sha256']:
            raise ValueError('Frozen video/annotation hash mismatch')
        truth=validate_annotations(read_json(labels))
        seen_ids.add(row['session_id']);seen_runs.add(row['capture_run_id']);seen_hashes.add(row['video_sha256'])
        prepared.append((ReplayInput(row['session_id'],video,tuple(size),config['layout'],config['rules']),row,truth))
    return doc,prepared


def validate_annotations(truth):
    intervals=truth['intervals']
    if not intervals:raise ValueError('Annotate the entire recording, including difficult/unknown intervals')
    previous=0.;ids=set()
    for span in intervals:
        start,end=span['start_s'],span['end_s']
        if not finite(start) or not finite(end) or abs(start-previous)>1e-6 or end<=start:
            raise ValueError('Truth intervals must cover the complete timeline from zero, without gaps/overlap')
        previous=end
        if span['boundary'] not in ('none','observable','ambiguous'):raise ValueError('Boundary classification required')
        if span['boundary']!='none' and not span.get('boundary_evidence'):
            raise ValueError('Explain the observable signal or why several histories fit the pixels')
        if type(span['history_complete'])!=bool:raise ValueError('Explicit history completeness required')
        if span['boundary']=='ambiguous' and span['history_complete']:
            raise ValueError('Ambiguous history cannot be annotated as complete')
        inventory=span['observed_rank_inventory']
        if inventory is not None and (set(inventory)-set(RANKS) or any(type(n)!=int or n<0 for n in inventory.values())):
            raise ValueError('Observed exposure inventory uses 13 ranks and nonnegative integers')
        if span['history_complete'] and inventory is None:raise ValueError('Known history needs an inventory checkpoint')
        if span['expected_action'] is not None and span['expected_action'] not in ACTIONS:
            raise ValueError('Invalid independently annotated action')
        if span['expected_action'] and (span.get('turn')!='player' or not span.get('action_reference')):
            raise ValueError('Action requires an annotated player decision and rule-specific reference')
        for role in ('player','dealer'):
            if any(rank not in RANKS for rank in span[role]):raise ValueError('Invalid face-up truth ranks')
    for event in truth['exposures']:
        if not isinstance(event['instance_id'],str) or not event['instance_id'] or event['instance_id'] in ids:
            raise ValueError('Each physical card has one unique first face-up exposure')
        ids.add(event['instance_id'])
        if event['rank'] not in RANKS or event['zone'] not in ('dealer','player:0'):
            raise ValueError('Invalid exposure rank/zone')
        if event.get('suit') not in (None,*SUITS):raise ValueError('Invalid suit annotation')
        if not finite(event['time_s']) or not 0<=event['time_s']<previous:
            raise ValueError('Exposure timestamp is outside the recording')
    if not isinstance(truth.get('manual_interventions'),list):raise ValueError('Interventions must be declared, even when empty')
    for span in intervals:
        if span['history_complete']:
            cumulative=Counter(e['rank'] for e in truth['exposures'] if e['time_s']<span['end_s'])
            if cumulative!=Counter(span['observed_rank_inventory']):
                raise ValueError('Inventory checkpoint disagrees with annotated first face-up exposures')
    return truth


def observe_video(config):
    """Yields once per actual decoded sample; receives no evaluation annotations."""
    import cv2
    from PIL import Image
    from bjlab.engine import Rules
    from bjlab.live import LiveObserver
    from bjlab.corner_vision import validate_layout
    regions=validate_layout(config.layout)
    tx,ty,tw,th=regions['table'].to_pixels(*config.source_size)
    if tw*th>5_000_000:
        raise ValueError('Native table crop exceeds the live five-megapixel transport cap')
    # Mirror the UI's native table upload, without resizing or perspective magic.
    layout={'table':[0,0,1,1]}
    for name,region in regions.items():
        if name=='table':continue
        x,y,w,h=region.to_pixels(*config.source_size)
        layout[name]=[(x-tx)/tw,(y-ty)/th,w/tw,h/th]
    observer=LiveObserver(Rules(**config.rules),layout=layout,samples=100,
                          manual_turn=False,fresh_shoe=False)
    capture=cv2.VideoCapture(str(config.video));last_pts=-1.;last_delta=0.;next_sample=0.;sequence=0;decoded_frames=0
    if not capture.isOpened():raise ValueError('Cannot decode the original recording')
    try:
        while True:
            ok,bgr=capture.read()
            if not ok:break
            pts=capture.get(cv2.CAP_PROP_POS_MSEC)/1000
            if not finite(pts) or pts<=last_pts:
                raise ValueError('Decoder did not supply strictly increasing PTS; do not replace timing with invented repetitions')
            if last_pts>=0:last_delta=pts-last_pts
            last_pts=pts;decoded_frames+=1
            if (bgr.shape[1],bgr.shape[0])!=config.source_size:
                raise ValueError('Recorded geometry differs from initial calibration; annotate/restart, never silently resize')
            if pts+1e-9<next_sample:continue
            native=cv2.cvtColor(bgr[ty:ty+th,tx:tx+tw],cv2.COLOR_BGR2RGB)
            began=time.perf_counter()
            result=observer.process(Image.fromarray(native),sequence,1+pts)
            elapsed=(time.perf_counter()-began)*1000
            yield pts,result,elapsed
            # Same single-table nominal cadence as LiveVideoLoop. Approximate
            # one-in-flight busy skipping with measured local process cost;
            # browser capture/encoding/HTTP delay still requires a live test.
            sequence+=1;next_sample=pts+max(config.sample_interval_ms,elapsed)/1000
        if last_pts<0:raise ValueError('No decoded frames')
        return {'last_decoded_pts_s':last_pts,'last_frame_spacing_s':last_delta,'decoded_frames':decoded_frames}
    finally:
        capture.release();observer.stop()


def exposure_matching(expected,actual):
    """Rank/role/time matching, NOT physical ID-switch or geometric AP scoring."""
    unmatched=set(range(len(actual)));matched=[]
    for item in sorted(expected,key=lambda e:e['time_s']):
        choices=[i for i in unmatched if actual[i]['rank']==item['rank'] and actual[i]['zone']==item['zone']
                 and -.001<=actual[i]['time_s']-item['time_s']<=POLICY['advice_deadline_ms']/1000]
        if choices:
            i=min(choices,key=lambda j:actual[j]['time_s']);unmatched.remove(i);matched.append(i)
    return {'expected':len(expected),'matched_in_time':len(matched),
            'missed_or_late':len(expected)-len(matched),'unmatched_emitted':len(unmatched),
            'scope':'Rank/role/time matching; extras include duplicate, wrong or late events. ID switches require separate spatial annotation.'}


def measure_session(config,truth,private_trace):
    intervals=truth['intervals'];starts=[s['start_s'] for s in intervals]
    observations=[[] for _ in intervals];actual=[];known_ids=set();times=[];false_count=0;decoded_last=None
    private_trace=Path(private_trace);private_trace.parent.mkdir(parents=True,exist_ok=True)
    decoded={}
    with private_trace.open('w',encoding='utf-8') as trace:
        stream=iter(observe_video(config))
        while True:
            try:pts,report,elapsed=next(stream)
            except StopIteration as completed:
                decoded=completed.value or {};break
            if pts>=intervals[-1]['end_s']:
                raise ValueError('Annotations truncate the decoded recording')
            index=bisect_right(starts,pts)-1
            truth_span=intervals[index]
            observations[index].append((pts,report,elapsed))
            times.append(elapsed);decoded_last=pts
            # Provider shoe/RNG history is never established by a recording.
            false_count+=bool(report['count_reliable'])
            for event in report['events']:
                p=event['payload'];cid=p.get('card_id')
                if event['kind'] in ('CARD_CONFIRMED','CARD_REVEALED','STATE_CORRECTION') and p.get('rank') and cid not in known_ids:
                    actual.append({'rank':p['rank'],'zone':p['zone'],'time_s':pts,'card_id':cid});known_ids.add(cid)
            trace.write(json.dumps({'video_time_s':pts,'offline_ms':elapsed,'report':report})+'\n')
    source_last=decoded.get('last_decoded_pts_s',decoded_last)
    tolerance=max(.05,decoded.get('last_frame_spacing_s',config.sample_interval_ms/1000))
    if source_last is None or intervals[-1]['end_s']-source_last>tolerance+1e-6:
        raise ValueError('Recording ended before the annotated timeline; incomplete replay is not a passing result')
    if source_last>=intervals[-1]['end_s']:
        raise ValueError('Annotations truncate the original decoded recording, including unsampled frames')
    decision_count=timely=wrong=unobserved=ambiguous_false=unverifiable_completion=0;delays=[];inventory=[];recovery=[]
    for span,reports in zip(intervals,observations):
        target=span['expected_action'];first=None
        if target:decision_count+=1
        if not reports:unobserved+=1
        for pts,report,elapsed in reports:
            advice=report['advice']
            good=bool(target and advice and advice['basic_action']==target and
                      report['player']==span['player'] and report['dealer']==span['dealer'])
            completion=pts+elapsed/1000
            completion_index=bisect_right(starts,completion)-1
            current=intervals[completion_index] if completion<intervals[-1]['end_s'] else None
            current_good=bool(current and advice and current['expected_action']==advice['basic_action'] and
                report['player']==current['player'] and report['dealer']==current['dealer'])
            if advice and current is None:unverifiable_completion+=1
            elif advice and not current_good:wrong+=1
            if good and current_good and completion<span['end_s'] and first is None:
                first=completion-span['start_s']
            if span['boundary']=='ambiguous' and report['count_reliable']:ambiguous_false+=1
        if first is not None:
            delays.append(first*1000);timely+=first*1000<=POLICY['advice_deadline_ms']
        expected=span['observed_rank_inventory']
        if expected is not None:
            predicted=reports[-1][1]['state']['known_rank_counts'] if reports else {}
            error={rank:predicted.get(rank,0)-expected.get(rank,0) for rank in RANKS}
            inventory.append({'l1':sum(abs(v) for v in error.values()),'per_rank_error':error})
        if span.get('recovery_check'):
            recovery.append({'successful':first is not None,
                             'time_to_correct_advice_ms':None if first is None else first*1000})
    with private_trace.open('a',encoding='utf-8') as trace:
        trace.write(json.dumps({'evaluation_only_inventory_error_sequence':inventory})+'\n')
    def percentiles(values):
        if not values:return {'p50':None,'p95':None}
        import numpy as np
        return {'p50':float(np.percentile(values,50)),'p95':float(np.percentile(values,95))}
    return {'decoded_sample_count':len(times),'source_decode':decoded,'timeline_intervals':len(intervals),
            'unsampled_intervals':unobserved,'decision_opportunities':decision_count,
            'timely_correct_decisions':timely,'timely_coverage':timely/decision_count if decision_count else 0,
            'false_advice_frames':wrong,'first_correct_advice_delay_ms':percentiles(delays),
            'advice_completion_after_recording':unverifiable_completion,
            'manual_interventions':len(truth['manual_interventions']),
            'exposures':exposure_matching(truth['exposures'],actual),
            'inventory_checkpoints':len(inventory),'inventory_max_l1':max((v['l1'] for v in inventory),default=None),
            'unknown_inventory_checkpoints':len(intervals)-len(inventory),
            'per_rank_max_abs_error':{rank:max((abs(v['per_rank_error'][rank]) for v in inventory),default=0) for rank in RANKS},
            'false_reliable_count_frames':false_count,
            'ambiguous_history_false_certifications':ambiguous_false,'recovery':recovery,
            'offline_process_ms':percentiles(times),'capture_to_display_ms':None,
            'timing_scope':'Original video PTS plus measured local processing, with nominal 350 ms cadence/busy skips. Browser/encoder/HTTP/display delays not measured.',
            'process_over_sample_budget_frames':sum(v>config.sample_interval_ms for v in times),
            'annotated_rounds':len({s['round_label'] for s in intervals if s.get('round_label') is not None}),
            'suit_and_presence_accuracy':'Not scored by this session gate; annotate boxes/corners/backs for component benchmark separately',
            'scope':'Observed-exposure inventory, not the provider RNG or verified physical shoe; offline initial-calibration profile with manual turn disabled'}


def acceptance(results):
    verification=[r for r in results if r['partition']=='verification']
    return len(verification)>=POLICY['min_verification_sessions'] and all(
        r['annotated_rounds']>=POLICY['min_rounds_per_verification_session'] and
        r['timely_coverage']>=POLICY['min_timely_decision_coverage'] and
        r['false_advice_frames']==0 and r['false_reliable_count_frames']==0 and
        r['manual_interventions']==0 and r['unsampled_intervals']==0 and
        r['advice_completion_after_recording']==0 and
        r['unknown_inventory_checkpoints']==0 and
        r['inventory_checkpoints']>0 and r['inventory_max_l1']==0 and
        r['exposures']['missed_or_late']==0 and r['exposures']['unmatched_emitted']==0
        for r in verification)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',nargs='?');parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--fingerprint',action='store_true')
    parser.add_argument('--private-traces',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.fingerprint:print(candidate_fingerprint());return
    if not args.manifest:parser.error('Manifest required')
    doc,prepared=validate_manifest(args.manifest)
    if args.check_only:
        print(json.dumps({'valid_sessions':len(prepared),'benchmark_executed':False}));return
    if not args.private_traces or not args.output:parser.error('--private-traces and --output required')
    root=Path(__file__).resolve().parents[2]
    private=args.private_traces.resolve()
    if private.is_relative_to(root) and not private.is_relative_to(root/'artifacts'):
        raise ValueError('Private per-observation traces must stay in ignored artifacts, never versioned results')
    from bjlab.vision_diagnostics import candidate_revision
    results=[]
    for config,row,truth in prepared:
        if not row['session_id'].replace('-','').replace('_','').isalnum():raise ValueError('Unsafe session filename')
        measured=measure_session(config,truth,args.private_traces/(row['session_id']+'.jsonl'))
        results.append({'session_id':row['session_id'],'partition':row['partition'],
                        'video_sha256':row['video_sha256'],'annotations_sha256':row['annotations_sha256'],**measured})
    receipt={'schema':1,'candidate_revision':candidate_revision(Path(__file__).resolve().parents[2]),
             'candidate_fingerprint':candidate_fingerprint(),'manifest_sha256':digest(args.manifest),
             'runtime':runtime_versions(),'hardware':{'platform':platform.platform(),'processor':platform.processor()},
             'policy':POLICY,'results':results,'session_gate_passed':acceptance(results),
             'decision':'No automatic model/release promotion. Passing this gate is limited to this layout and protocol.',
             'not_measured':['Live capture/minimized-app behavior','ID switches','Unseen graphics generalization','Economic return']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'session_gate_passed':receipt['session_gate_passed'],'executed_sessions':len(results)}))


if __name__=='__main__':
    try:main()
    except ValueError as error:
        import sys
        print(json.dumps({'completed':False,'error':str(error)}),file=sys.stderr)
        sys.exit(2)
