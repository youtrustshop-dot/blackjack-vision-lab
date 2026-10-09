"""Fresh seeded OWN renderer sequences. No claim about new provider recordings.

The detector gets pixels and one fixed manual calibration. Evaluator truth and
the simulated manual turn confirmation stay outside the pixel detector. Native
session histories evaluate inventory errors separately from the final Hi-Lo sum.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
from bjlab.datasets import card_font
from bjlab.engine import Rules
from bjlab.simulator import BlackjackSession
from bjlab.live import LiveObserver
from bjlab.corner_vision import VERSION

LAYOUT={'table':(0,0,1,1),'dealer':(.12,.06,.70,.29),'player:0':(.12,.54,.70,.29)}
SEEDS=(4100401,4100402,4100403)


def render(snapshot,shift=0):
    image=Image.new('RGB',(720,500),(30,52,69));draw=ImageDraw.Draw(image)
    cards=[]
    for zone,items,y in [('dealer',snapshot.get('dealer',{}).get('cards',[]),45),
                         ('player:0',snapshot.get('hands',[{}])[0].get('cards',[]) if snapshot.get('hands') else [],285)]:
        for i,card in enumerate(items):
            x=110+45*i+shift;draw.rounded_rectangle((x,y,x+80,y+110),radius=6,fill='white')
            if card.get('face_down'):
                draw.rectangle((x+4,y+4,x+76,y+106),fill='#386fa8')
                for gy in range(y+9,y+105,8):
                    for gx in range(x+9,x+73,8):draw.rectangle((gx,gy,gx+2,gy+2),fill='white')
            else:
                rank=card['rank'];suit=card['suit'];color='#b82b35' if suit in 'HD' else '#181a1d'
                draw.text((x+6,y+6),rank,font=card_font(22),fill=color,anchor='lt')
                draw.text((x+6,y+31),dict(zip('SHDC','♠♥♦♣'))[suit],font=card_font(18),fill=color,anchor='lt')
                draw.text((x+40,y+62),dict(zip('SHDC','♠♥♦♣'))[suit],font=card_font(28),fill=color,anchor='lt')
            cards.append({'zone':zone,'rank':card.get('rank'),'suit':card.get('suit'),
                          'face_down':bool(card.get('face_down')),'bbox':[x,y,81,111]})
    return image,cards


def run(output,stable_observations=6):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    # Define cohort and scoring before reading any result. This is fresh
    # development data, not the final holdout or an unseen graphic family.
    protocol={'schema':1,'scope':'own synthetic full-round sequences, same renderer family, no external recordings',
              'seeds':list(SEEDS),'rounds_per_session':4,'layout':LAYOUT,'split':'development',
              'detector':VERSION,'manual_turn':'simulated confirmation at each game state',
              'suits':'correct/wrong/unknown including every visible face',
              'count_acceptance':'never certified by this research profile',
              'stable_observations_per_state':stable_observations,
              'geometry_drift':'same-size +60px (inside ROI) and +480px (clipped ROI); report gates, do not tune on them'}
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    reports=[];frames=[];first_player=None
    for seed in SEEDS:
        session=BlackjackSession(Rules(decks=2,dealer_peek=False,enhc=False),seed=seed)
        observer=LiveObserver(session.rules,layout=LAYOUT,manual_turn=True,fresh_shoe=True,samples=100)
        rows=[];sequence=0
        def observe(snapshot):
            nonlocal sequence,first_player
            if snapshot['phase']=='player' and first_player is None:
                first_player=json.loads(json.dumps(snapshot))
            image,truth=render(snapshot)
            path=output/f'{seed}-{sequence:04}.png';image.save(path)
            observer.manual_turn=snapshot['phase']=='player'
            state_events=[]
            for _ in range(stable_observations):
                report=observer.process(image,sequence,1+sequence*.2);sequence+=1
                state_events.extend(event['kind'] for event in report['events'])
            actual=Counter((d['zone'],d['rank']) for d in report['detections'] if d['rank'])
            expected=Counter((c['zone'],c['rank']) for c in truth if c['rank'])
            suit_correct=suit_wrong=suit_unknown=0
            # Greedy nearest corner geometry; no class labels in association.
            used=set()
            for card in [c for c in truth if c['rank']]:
                options=sorted((abs(d['bbox'][0]-card['bbox'][0]),i,d) for i,d in enumerate(report['detections'])
                               if i not in used and d['zone']==card['zone'] and abs(d['bbox'][0]-card['bbox'][0])<18)
                if not options:suit_unknown+=1;continue
                _,i,d=options[0];used.add(i)
                if d['suit'] is None:suit_unknown+=1
                elif d['suit']==card['suit']:suit_correct+=1
                else:suit_wrong+=1
            rank_inventory=Counter(c.rank for c in session.seen.values())
            reconstructed=Counter(report['state']['known_rank_counts'])
            inventory_error=sum(abs(rank_inventory[k]-reconstructed[k]) for k in rank_inventory.keys()|reconstructed.keys())
            complete=actual==expected and len(report['detections'])==len(truth)
            row={'session_seed':seed,'round':snapshot['round_id'],'phase':snapshot['phase'],
                 'frame':path.name,'frame_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                 'truth_objects':len(truth),'visible_faces':sum(bool(c['rank']) for c in truth),
                 'ranks_correct':sum((actual&expected).values()),'ranks_missed':sum((expected-actual).values()),
                 'ranks_extra_or_wrong':sum((actual-expected).values()),'state_exact':complete,
                 'suits_correct':suit_correct,'suits_wrong':suit_wrong,'suits_unknown_or_missed':suit_unknown,
                 'advice_available':report['advice'] is not None,
                 'incorrect_actionable_state':report['advice'] is not None and not complete,
                 'reasons':report['gate']['reasons'],'count_reliable':report['count_reliable'],
                 'detected_phase':report['phase'],'detected_round':report['round'],
                 'lifecycle':{'seen_round':observer.lifecycle.seen_round,
                     'stable_hits':observer.lifecycle.hits,'round_open':observer.lifecycle.round_open,
                     'pending_boundary':observer.lifecycle.pending_boundary},
                 'state_events':state_events,'expected_inventory':dict(rank_inventory),
                 'observed_inventory':dict(reconstructed),
                 'inventory_l1_error':inventory_error,'observed_rc_error':report['observed_running_count']-session.running_count}
            rows.append(row);frames.append({'session':seed,'frame':path.name,'sha256':row['frame_sha256'],'split':'development'})
        for _ in range(4):
            snapshot=session.deal(10);observe(snapshot)
            while session.phase!='settled':
                actions=session.available_actions()
                action='hit' if 'hit' in actions and session.hands[0].value[0]<15 else 'stand' if 'stand' in actions else actions[0]
                snapshot=session.action(action);observe(snapshot)
        decision_rows=[r for r in rows if r['phase']=='player']
        reports.append({'seed':seed,'states':len(rows),'decision_states':len(decision_rows),
            'correctly_usable_decision_states':sum(r['advice_available'] and r['state_exact'] for r in decision_rows),
            'incorrect_actionable_states':sum(r['incorrect_actionable_state'] for r in rows),
            'visible_faces':sum(r['visible_faces'] for r in rows),'ranks_correct':sum(r['ranks_correct'] for r in rows),
            'suits_correct':sum(r['suits_correct'] for r in rows),'suits_wrong':sum(r['suits_wrong'] for r in rows),
            'suits_unknown_or_missed':sum(r['suits_unknown_or_missed'] for r in rows),
            'final_inventory_l1_error':rows[-1]['inventory_l1_error'],'final_observed_rc_error':rows[-1]['observed_rc_error'],
            'count_ever_certified':any(r['count_reliable'] for r in rows),'rows':rows})
    drifts=[]
    for shift in (0,60,480):
        shifted,_=render(first_player,shift)
        drift=LiveObserver(session.rules,layout=LAYOUT,manual_turn=True,samples=100)
        for i in range(stable_observations):drift_report=drift.process(shifted,i,1+i*.2)
        drifts.append({'source_size_unchanged':True,'translation_px':shift,'advice_available':drift_report['advice'] is not None,
                      'reasons':drift_report['gate']['reasons']})
    result={'schema':1,'protocol':protocol,'sessions':reports,'dataset_manifest_sha256':hashlib.sha256(json.dumps(frames,sort_keys=True).encode()).hexdigest(),
        'same_size_drift_probe':drifts,
        'selection':'No promotion. New own-renderer development sessions, no new external provider session or count acceptance.'}
    (output/'manifest.json').write_text(json.dumps(frames,indent=2),encoding='utf-8')
    (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({**result,'sessions':[{k:v for k,v in s.items() if k!='rows'} for s in reports]},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--stable-observations',type=int,default=6)
    args=parser.parse_args();run(args.output,args.stable_observations)
