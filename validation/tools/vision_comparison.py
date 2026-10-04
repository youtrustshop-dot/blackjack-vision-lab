"""Compare pixel-only profiles on explicit development cases, never a holdout.

Private manifests may reference user images; reports omit paths and pixels.
Declared layouts are evaluator-independent manual geometry, not rank inputs.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from bjlab.corner_vision import CornerCardDetector
from bjlab.datasets import bbox_iou
from bjlab.vision import CardDetection
from bjlab.external_vision import AdaptiveCardDetector
from bjlab.vision_diagnostics import source_revision


def recognition_counts(truth, found, pairs, *, suits_supported=True):
    """Disjoint outcomes: localization misses are not OCR/classifier errors."""
    matched=dict(pairs); rank=Counter(); suit=Counter(); presence=Counter()
    for i,t in enumerate(truth):
        if i not in matched:
            presence['missed']+=1
            if not t.get('face_down'):
                rank['missed']+=1
                if suits_supported:suit['missed']+=1
            continue
        d=found[matched[i]]
        expected='covered' if t.get('face_down') else 'readable'
        presence['correct' if d.visibility==expected else 'wrong']+=1
        if expected=='covered':
            presence['covered_correct' if d.face_down else 'covered_wrong']+=1
            continue
        rank['unknown' if d.rank is None else 'correct' if d.rank==t['rank'] else 'wrong']+=1
        if suits_supported:
            suit['unknown' if d.suit is None else 'correct' if d.suit==t['suit'] else 'wrong']+=1
    presence['extra']=len(found)-len(pairs)
    keys=('correct','wrong','unknown','missed')
    return {'rank':{k:rank[k] for k in keys},
            'suit':{k:suit[k] for k in keys} if suits_supported else None,
            'suits_supported':suits_supported,
            'presence':{k:presence[k] for k in ('correct','wrong','missed','extra','covered_correct','covered_wrong')}}


def still_state_probe(image, found, diagnostics, context):
    """Probe actual state gates with repeated stills; never call it a video session."""
    from bjlab.live import LiveObserver
    from bjlab.engine import Rules
    class ReplayDetector:
        def __init__(self):
            self.context={**(context or {}),'phase':'player','controls':[],'player_totals':{},
                          'reasons':list((context or {}).get('reasons',[]))}
            self.last_diagnostics={'rejected_card_candidates':diagnostics.get('rejected_card_candidates',0)}
        def detect(self,_):return found
    observer=LiveObserver(Rules(),samples=100,manual_turn=True)
    observer.detector=ReplayDetector()
    first=None; reports=[]
    for i in range(5):
        report=observer.process(image,i,i*.2+1.)
        reports.append({'step':i,'has_advice':report['advice'] is not None,'reasons':report['gate']['reasons']})
        if report['advice'] is not None and first is None:first=i*.2
    return {'manual_player_turn':True,'repeated_still_not_video':True,'first_advice_after_simulated_seconds':first,
            'advice_available':report['advice'] is not None,'action':report['advice'],
            'reasons':report['gate']['reasons'],'states':reports}


def evaluate(manifest,output,checkpoint=None,*,localizer_checkpoint=None,operating_points=None,timing_environment='Concurrent workloads not monitored'):
    document=json.loads(Path(manifest).read_text(encoding='utf-8'))
    if any(c['split']!='development' for c in document['cases']):
        raise ValueError('This first comparison is development-only, not a final test runner.')
    modes=['baseline-full','baseline-native-roi','calibrated-corners']
    if checkpoint:modes.append('ultralytics-corners')
    if localizer_checkpoint:modes.append('learned-corners-ocr')
    rows=[]
    for case in document['cases']:
        path=Path(case['source_file']); image=Image.open(path).convert('RGB')
        for mode in modes:
            detector=AdaptiveCardDetector() if mode.startswith('baseline') else CornerCardDetector(case['layout'])
            if mode=='learned-corners-ocr':
                from validation.tools.learned_corners import LearnedCornerDetector
                detector=LearnedCornerDetector(case['layout'],localizer_checkpoint,operating_points)
            pixels=image
            if mode=='baseline-native-roi':
                from bjlab.calibration import NormalizedROI
                pixels=Image.fromarray(NormalizedROI(*case['layout']['table']).crop(image))
            def run():
                if mode=='ultralytics-corners':
                    from validation.tools.yolo_corner_pilot import detect
                    return detect(image,case['layout'],checkpoint)
                return detector.detect(pixels)
            run()  # One excluded warm-up per case/profile, including model load.
            times=[]
            for repeat in range(3):
                from bjlab.ocr import _read_cached
                _read_cached.cache_clear()  # Warm runtime, fresh glyph inference; repeated stills cannot win on OCR memoization.
                began=time.perf_counter(); found=run();times.append((time.perf_counter()-began)*1000)
            elapsed=float(np.median(times))
            if mode=='baseline-native-roi':
                x,y,_,_=NormalizedROI(*case['layout']['table']).to_pixels(*image.size)
                found=[CardDetection(d.rank,d.suit,(d.bbox[0]+x,d.bbox[1]+y,d.bbox[2],d.bbox[3]),d.score,
                    face_down=d.face_down,zone=d.zone,score_type=d.score_type) for d in found]
            truth=case.get('cards',[]); pairs=[]; used_truth=set();used_found=set()
            possibilities=sorted(((bbox_iou(t['bbox'],d.bbox),i,j) for i,t in enumerate(truth)
                for j,d in enumerate(found) if t['zone']==d.zone),reverse=True)
            for overlap,i,j in possibilities:
                if overlap>=.30 and i not in used_truth and j not in used_found:
                    used_truth.add(i);used_found.add(j);pairs.append((i,j))
            visible=[i for i,t in enumerate(truth) if not t.get('face_down')]
            rank_correct=sum(found[j].rank==truth[i].get('rank') for i,j in pairs if i in visible)
            suit_correct=sum(found[j].suit==truth[i].get('suit') for i,j in pairs if i in visible)
            expected=Counter((zone,rank) for zone,ranks in case['expected'].items() for rank in ranks)
            predicted=Counter((d.zone,d.rank) for d in found if d.rank)
            correct=sum((expected&predicted).values()); missed=sum((expected-predicted).values())
            wrong=sum((predicted-expected).values())
            outcomes=recognition_counts(truth,found,pairs,suits_supported=mode!='ultralytics-corners')
            diagnostic=detector.last_diagnostics if mode!='ultralytics-corners' else {}
            state=still_state_probe(image,found,diagnostic,detector.context if mode!='ultralytics-corners' else {})
            complete=(len(pairs)==len(truth) and len(found)==len(truth) and
                      all(found[j].rank==truth[i].get('rank') and found[j].face_down==truth[i].get('face_down',False) for i,j in pairs))
            state['correctly_usable']=state['advice_available'] and complete
            rows.append({'case_id':case['id'],'family':case['family'],'group':case['group'],'input_kind':case['input_kind'],
                'split':case['split'],'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'source_size':list(image.size),'analyzed_size':list(pixels.size),
                'profile':mode,'expected_visible_cards':sum(expected.values()),'correct_zone_ranks':correct,
                'missed_zone_ranks':missed,'extra_or_wrong_zone_ranks':wrong,
                'predictions':[d.to_dict() for d in found], 'detector_context':detector.context if mode!='ultralytics-corners' else {},
                'outcomes':outcomes,'state_usefulness':state,
                'localization':{'iou_threshold':.30,'truth_objects':len(truth),'matched':len(pairs),
                    'missed':len(truth)-len(pairs),'unmatched_predictions':len(found)-len(pairs),
                    'visible_faces':len(visible),'rank_correct_including_misses':rank_correct,
                    'suit_correct_including_misses':suit_correct},
                'offline_ms':elapsed,'offline_samples_ms':times,'diagnostics':detector.last_diagnostics if mode!='ultralytics-corners' else None})
    aggregates={}
    for mode in modes:
        subset=[r for r in rows if r['profile']==mode and r['input_kind']=='digital-screenshot']
        total=sum(r['expected_visible_cards'] for r in subset); correct=sum(r['correct_zone_ranks'] for r in subset)
        wrong=sum(r['extra_or_wrong_zone_ranks'] for r in subset)
        aggregates[mode]={'visible_cards':total,'correct_zone_ranks':correct,'missed_zone_ranks':total-correct,
            'extra_or_wrong_zone_ranks':wrong,'rank_inventory_recall':correct/total if total else None,
            'rank_inventory_precision':correct/(correct+wrong) if correct+wrong else None,
            'offline_ms_p50':float(np.percentile([t for r in subset for t in r['offline_samples_ms']],50)) if subset else None,
            'offline_ms_p95':float(np.percentile([t for r in subset for t in r['offline_samples_ms']],95)) if subset else None}
        localized=sum(r['localization']['matched'] for r in subset)
        objects=sum(r['localization']['truth_objects'] for r in subset)
        detected=sum(r['localization']['matched']+r['localization']['unmatched_predictions'] for r in subset)
        aggregates[mode]['localization_precision']=localized/detected if detected else None
        aggregates[mode]['localization_recall']=localized/objects if objects else None
        aggregates[mode]['rank_correct_including_misses']=sum(r['localization']['rank_correct_including_misses'] for r in subset)
        aggregates[mode]['suit_correct_including_misses']=sum(r['localization']['suit_correct_including_misses'] for r in subset)
        aggregates[mode]['suits_supported']=mode!='ultralytics-corners'
        if mode=='ultralytics-corners':aggregates[mode]['suit_correct_including_misses']=None
        aggregates[mode]['outcomes']={kind:({key:sum(r['outcomes'][kind][key] for r in subset)
            for key in ('correct','wrong','unknown','missed')} if kind=='rank' or mode!='ultralytics-corners' else None)
            for kind in ('rank','suit')}
        aggregates[mode]['presence_outcomes']={key:sum(r['outcomes']['presence'][key] for r in subset)
            for key in ('correct','wrong','missed','extra','covered_correct','covered_wrong')}
        aggregates[mode]['state_usefulness']={'stills':len(subset),'independent_moments':len({r['group'] for r in subset}),
            'advice_available':sum(r['state_usefulness']['advice_available'] for r in subset),
            'correctly_usable':sum(r['state_usefulness']['correctly_usable'] for r in subset),
            'scope':'same still replayed five times with manual turn; not first stable video latency or session integrity'}
    result={'schema':1,'source_fingerprint':source_revision(Path(__file__).resolve().parents[2]),
        'hardware':{'platform':platform.platform(),'processor':platform.processor()},
        'manifest_sha256':hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        'scope':'private development stills; repeated preview is same family/session, not independent data',
        'metrics_semantics':'manual full-card boxes matched at IoU .30 within role; still-image detection/zone rank and suit metrics, not calibrated certainty or detection AP',
        'selection':'no promotion; limited samples and no unseen external session evaluation',
        'localizer_checkpoint_sha256':hashlib.sha256(Path(localizer_checkpoint).read_bytes()).hexdigest() if localizer_checkpoint else None,
        'operating_points_sha256':hashlib.sha256(Path(operating_points).read_bytes()).hexdigest() if operating_points else None,
        'timing_protocol':'one excluded runtime warm-up then three repeats per case/profile; glyph OCR cache cleared before each repeat; offline detection only',
        'timing_environment':timing_environment,
        'not_measured':['tracking ID switches',
            'missed/duplicate video events','RC/TC session drift','capture-to-display latency','independent final generalization'],
        'aggregates':aggregates,'cases':rows}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(aggregates,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest');parser.add_argument('--output',required=True)
    parser.add_argument('--checkpoint');parser.add_argument('--localizer-checkpoint')
    parser.add_argument('--operating-points')
    parser.add_argument('--timing-environment',default='Concurrent workloads not monitored')
    args=parser.parse_args();evaluate(args.manifest,args.output,args.checkpoint,
        localizer_checkpoint=args.localizer_checkpoint,operating_points=args.operating_points,timing_environment=args.timing_environment)
