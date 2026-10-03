"""Frozen new synthetic sessions: pixels only, no round/shoe label shortcuts.

Generate once, then run unchanged against two source roots. This is not an
independent provider dataset or a browser capture latency measurement.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

parser=argparse.ArgumentParser()
parser.add_argument('command',choices=['generate','run'])
parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[2])
parser.add_argument('--dataset',type=Path,required=True)
parser.add_argument('--output',type=Path)
args=parser.parse_args()
sys.path.insert(0,str(args.source.resolve()))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests'))

from bjlab import __version__
from bjlab.engine import Rules
from bjlab.live import LiveObserver
from bjlab.simulator import BlackjackSession
from bjlab.advice import recommend
from side_fixture import side_table
import numpy as np
from PIL import Image

rules=Rules(decks=4,double_rule='none',max_split_hands=1,resplit=False,surrender='none')

if args.command=='generate':
    if (args.dataset/'manifest.json').exists():
        raise RuntimeError('Dataset is frozen; choose a new directory instead of overwriting it.')
    args.dataset.mkdir(parents=True,exist_ok=True)
    sessions=[]
    for seed,locale,scale in ((12983,'en',1.),(77271,'it',.8),(61073,'en',.6)):
        game=BlackjackSession(rules,seed=seed,bankroll=100000)
        stages=[]
        def record(blank=False):
            player=game.hands[0].ranks
            dealer=[c.rank for c in game.dealer] if game.hole_revealed else [game.dealer[0].rank]
            stage=len(stages)
            image=side_table(player,dealer,locale=locale,scale=scale,settled=game.phase=='settled',
                             hidden=not game.hole_revealed,blank=blank)
            name=f'{seed}/{stage:04}.png';path=args.dataset/name;path.parent.mkdir(exist_ok=True)
            image.save(path)
            action=(recommend(player,dealer[0],rules,allowed=game.available_actions(),peeked=game.peek_resolved)['best_action']
                    if game.phase=='player' and not blank else None)
            stages.append({'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'round':game.round_id,'phase':'blank' if blank else game.phase,
                'player':player,'dealer':dealer,'basic_action':action,
                'seen':len(game.seen),'running_count':game.running_count,'remaining':len(game.shoe.cards)})
        for _ in range(10):
            game.deal()
            if game.phase=='insurance':game.action('decline_insurance')
            record()
            while game.phase=='player':
                action=recommend(game.hands[0].ranks,game.dealer[0].rank,rules,
                                 allowed=game.available_actions(),peeked=game.peek_resolved)['best_action']
                game.action(action);record()
            record(blank=True)
        sessions.append({'seed':seed,'locale':locale,'scale':scale,'rounds':10,'stages':stages})
    document={'schema':1,'scope':'new synthetic sequences, existing development renderer; not held-out provider footage',
        'rules':asdict(rules),'repetitions':6,'interval_ms':350,'decision_window_ms':2200,
        'thresholds_frozen_before_run':{'useful_coverage':.95,'false_confident_decisions':0},'sessions':sessions}
    (args.dataset/'manifest.json').write_text(json.dumps(document,indent=2),encoding='utf-8')
    print(json.dumps({'sessions':len(sessions),'rounds':30,'stages':sum(len(s['stages']) for s in sessions),
                      'manifest_sha256':hashlib.sha256((args.dataset/'manifest.json').read_bytes()).hexdigest()}))
else:
    manifest=args.dataset/'manifest.json';data=json.loads(manifest.read_text())
    outcomes=[]
    for source in data['sessions']:
        observer=LiveObserver(Rules(**data['rules']),samples=100,fresh_shoe=True)
        sequence=0;stages=[];latencies=[]
        for truth in source['stages']:
            image_path=args.dataset/truth['file']
            assert hashlib.sha256(image_path.read_bytes()).hexdigest()==truth['sha256']
            image=Image.open(image_path).convert('RGB');reports=[];first_correct=None;false=0
            for index in range(data['repetitions']):
                started=time.perf_counter()
                # The observer only receives pixels, monotone timestamps and
                # declared configuration. Truth stays in this evaluation code.
                result=observer.process(image,sequence,1+sequence*data['interval_ms']/1000)
                elapsed=(time.perf_counter()-started)*1000;latencies.append(elapsed);sequence+=1
                advice=result.get('advice')
                if advice:
                    correct=(result['player']==truth['player'] and result['dealer']==truth['dealer'][:1]
                             and advice.get('basic_action')==truth['basic_action'] and truth['phase']=='player')
                    if not correct:false+=1
                    elif first_correct is None:first_correct=index*data['interval_ms']+elapsed
                reports.append(result)
            last=reports[-1]
            stages.append({'round':truth['round'],'phase':truth['phase'],'expected_player':truth['player'],
                'recognized_player':last['player'],'expected_action':truth['basic_action'],
                'action':last.get('advice',{}).get('basic_action') if last.get('advice') else None,
                'first_correct_ms':first_correct,'false_confident_frames':false,
                'timely':first_correct is not None and first_correct<=data['decision_window_ms'] if truth['basic_action'] else None,
                'expected_seen':truth['seen'],'observed_cards':last['observed_cards'],
                'expected_rc':truth['running_count'],'running_count':last['running_count'],
                'count_reliable':last.get('count_reliable'),'count_history':last.get('count_history'),
                'reasons':last['gate']['reasons']})
        opportunities=[s for s in stages if s['expected_action']]
        final=stages[-1]
        outcomes.append({'seed':source['seed'],'rounds':source['rounds'],'frames':sequence,
            'decision_opportunities':len(opportunities),'timely_correct':sum(s['timely'] for s in opportunities),
            'false_confident_frames':sum(s['false_confident_frames'] for s in stages),
            'final_observed_minus_expected':final['observed_cards']-final['expected_seen'],
            'final_rc_error':None if final['running_count'] is None else final['running_count']-final['expected_rc'],
            'frame_processing_ms':{f'p{p}':float(np.percentile(latencies,p)) for p in (50,95,99)},'stages':stages})
    opportunities=sum(s['decision_opportunities'] for s in outcomes);timely=sum(s['timely_correct'] for s in outcomes)
    report={'version':__version__,'source':str(args.source.resolve()),'dataset_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'scope':data['scope'],'latency_scope':'offline observer processing and nominal stabilization; excludes browser, encoding, transport and display',
        'clef_enabled':False,'samples_per_action':100,'decision_window_ms':data['decision_window_ms'],
        'thresholds':data['thresholds_frozen_before_run'],'sessions':outcomes,
        'summary':{'rounds':sum(s['rounds'] for s in outcomes),'frames':sum(s['frames'] for s in outcomes),
          'decision_opportunities':opportunities,'timely_correct':timely,'useful_coverage':timely/opportunities,
          'false_confident_frames':sum(s['false_confident_frames'] for s in outcomes)}}
    report['acceptance_passed']=(report['summary']['useful_coverage']>=data['thresholds_frozen_before_run']['useful_coverage']
                               and report['summary']['false_confident_frames']==0)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key not in ('sessions','source')}))
