"""Bounded pixel-only overlap comparison. Truth is evaluator-only.

Development and verification manifests are distinct. A separately extracted
Git reference can be imported in a subprocess; no installed app is changed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def sources(root):
    return {str(p.relative_to(root)).replace('\\','/'):digest(p)
            for p in sorted((root/'bjlab').rglob('*')) if p.is_file() and p.suffix in ('.py','.onnx','.txt')}


def anchors(expected, detected):
    """One-to-one left/top anchor assignment, no rank/suit in matching.

    Visible row strips retain their left index; detector body widths are
    approximate and cannot be compared as full-card centers during overlap.
    This evaluator is bounded to upright rows, not general physical identity.
    """
    pairs=[]; missing=[]; extras=[]
    for zone in sorted({c['zone'] for c in expected}|{d['zone'] for d in detected}):
        a=[c for c in expected if c['zone']==zone]
        b=[d for d in detected if d['zone']==zone]
        cells={(0,0):(0.,())}
        # Exhaustive subset assignment, small single-hand scenes only.
        if len(b)>15: return [],list(expected),list(detected)
        for i,c in enumerate(a):
            next_cells={}
            for (_,mask),(cost,pairs_here) in cells.items():
                options=[(mask,cost+2,pairs_here)]
                for j,d in enumerate(b):
                    if mask&(1<<j): continue
                    dx=abs(c['bbox'][0]-d['bbox'][0]); dy=abs(c['bbox'][1]-d['bbox'][1])
                    radius=max(10,c['bbox'][3]*.18)
                    if dx<radius and dy<radius:
                        options.append((mask|(1<<j),cost+(dx+dy)/radius,pairs_here+((i,j),)))
                for m,v,p in options:
                    key=(i+1,m)
                    if key not in next_cells or v<next_cells[key][0]: next_cells[key]=(v,p)
            cells=next_cells
        _,choice=min((cost+2*(len(b)-mask.bit_count()),p)
                     for (_,mask),(cost,p) in cells.items())
        ia={i for i,j in choice}; ib={j for i,j in choice}
        pairs.extend((a[i],b[j]) for i,j in choice)
        missing.extend(c for i,c in enumerate(a) if i not in ia)
        extras.extend(d for j,d in enumerate(b) if j not in ib)
    return pairs,missing,extras


def generate(output):
    from validation.tools.stress_lab import timeline, render, rules, PROFILES, LAYOUT, SIZE, FPS
    from bjlab.datasets import card_font
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    # Predeclared before candidate verification. Paired graphics are not
    # independent hands. No seeds chosen for favorable cards/results.
    plan={'schema':1,'partition':'verification','kind':'own-synthetic-continuous-video',
          'seeds':[4100521,4100522], 'rounds':3,'fps':FPS,'source_size':list(SIZE),
          'rules':asdict(rules()),'api_requests':0,'sessions':[],
          'generator_sha256':digest(__file__), 'development_reference_seed':4100410,
          'timely_budget_ms':1500,'sampling_ms':350,
          'groups':{'new_seed':'original graphic family; different cards and stage durations',
                    'graphic_variation':'same new hands; 0.94 scale, x+23/y+9, diagonal blue back, moved controls'},
          'scope':'New synthetic sessions only. No external-site or universal claim.'}
    for seed in plan['seeds']:
        stages=timeline(seed,3)
        # Deterministic duration variations set before any result is measured.
        for n,stage in enumerate(stages):
            if stage['phase']=='player': stage['duration']=(2.25,1.75,2.5)[n%3]
            elif stage['phase']=='dealer': stage['duration']=(.5,.75)[n%2]
            elif stage['phase']=='waiting': stage['duration']=1.
        for group in plan['groups']:
            scale,tx,ty=(1.,0,0) if group=='new_seed' else (.94,23,9)
            layout={k:[x*scale+tx/SIZE[0],y*scale+ty/SIZE[1],w*scale,h*scale] for k,(x,y,w,h) in LAYOUT.items()}
            for profile in ('clean','overlap'):
                name=f'{seed}-{group}-{profile}'; video=output/f'{name}.webm'
                writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'VP80'),FPS,SIZE)
                if not writer.isOpened(): raise RuntimeError('VP8 unavailable')
                rows=[]; seen={}; frame=0
                try:
                    for stage in stages:
                        for tick in range(round(stage['duration']*FPS)):
                            image,truth=render(stage,PROFILES[profile],tick)
                            if group=='graphic_variation':
                                draw=ImageDraw.Draw(image)
                                for c in truth:
                                    if c['presence']=='covered':
                                        x,y,w,h=c['bbox']; draw.rounded_rectangle((x+5,y+5,x+w-6,y+h-6),5,fill='#2765a5')
                                        for offset in range(-h,w,9):
                                            # Clip diagonal strokes to the blue interior.
                                            x1=max(x+7,x+offset); x2=min(x+w-8,x+offset+h-14)
                                            if x2>x1: draw.line((x1,y+7+x1-x-offset,x2,y+7+x2-x-offset),fill='#b0c8e0',width=1)
                                draw.rectangle((0,650,1024,768),fill='#125e42' if profile=='clean' else '#075960')
                                captions={'player':['HIT','STAND'],'waiting':['DEAL'],'settled':['NEW HAND'],
                                          'dealer':['DEALER TURN'],'dealing':['DEALING'],'unknown':['INSURANCE']}[stage['phase']]
                                for i,caption in enumerate(captions):
                                    x=325+i*225
                                    draw.rounded_rectangle((x,669,x+190,714),9,fill='#162b29',outline='#e0b75e',width=2)
                                    draw.text((x+95,691),caption,font=card_font(22),fill='#f5e6bd',anchor='mm')
                                image=image.transform(SIZE,Image.Transform.AFFINE,(1/scale,0,-tx/scale,0,1/scale,-ty/scale),Image.Resampling.BICUBIC,fillcolor='#111e25')
                                for c in truth:
                                    if c['bbox']:
                                        x,y,w,h=c['bbox']; c['bbox']=[round(x*scale+tx),round(y*scale+ty),round(w*scale),round(h*scale)]
                            writer.write(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR))
                            for c in truth:
                                if c['presence']!='absent_from_pixels' and c['physical_rank']: seen[c['card_id']]=c['physical_rank']
                            rows.append({'frame':frame,'timestamp_ms':frame*1000/FPS,'round':stage['round'],
                                         'phase':stage['phase'],'cards':truth,'seen':dict(seen)})
                            frame+=1
                finally: writer.release()
                truth_path=output/f'{name}.truth.json'; save(truth_path,rows)
                plan['sessions'].append({'profile':profile,'name':name,'seed':seed,'group':group,'layout':layout,
                    'frames':frame,'video':video.name,'video_sha256':digest(video),'truth':truth_path.name,'truth_sha256':digest(truth_path)})
    save(output/'manifest.json',plan)


def replay(manifest_path, output, code_root, candidate, profiles=None):
    # Use a separate process for each code root. Imports precede no truth input.
    evaluator_hash=digest(__file__)
    code_root=Path(code_root).resolve(); sys.path.insert(0,str(code_root))
    from bjlab.live import LiveObserver
    from bjlab.engine import Rules
    from bjlab.advice import recommend
    import bjlab.live
    if Path(bjlab.live.__file__).resolve()!=code_root/'bjlab/live.py': raise RuntimeError('Wrong inference source root')
    before=sources(code_root)
    path=Path(manifest_path); manifest=json.loads(path.read_text(encoding='utf-8'))
    if manifest['partition'] not in ('development','verification'): raise ValueError('Unknown partition')
    reports=[]
    for session in manifest['sessions']:
        if profiles and session['profile'] not in profiles: continue
        name=session.get('name',session['profile']); video=path.parent/session['video']; truth_path=path.parent/session['truth']
        if digest(video)!=session['video_sha256'] or digest(truth_path)!=session['truth_sha256']: raise ValueError('Input hash mismatch')
        truth=json.loads(truth_path.read_text(encoding='utf-8'))
        kwargs={'context_challenger':True}
        if candidate: kwargs['overlap_challenger']=True
        observer=LiveObserver(Rules(**manifest['rules']),layout=session.get('layout',manifest.get('layout')),
                              fresh_shoe=True,manual_turn=False,samples=100,**kwargs)
        cap=cv2.VideoCapture(str(video)); index=0; next_ms=0; sampled=0
        counts=Counter(); exposures=Counter(); bindings={}; switches=[]; events=[]; traces=[]; times=[]; opportunities={}
        starts=Counter(); closures=Counter()
        first_seen={}; first_committed={}; drift_max=0; rc_max=0; final_drift={}
        # Opportunity onset is measured from ALL source frames, not just samples.
        for label in truth:
            if label['phase']=='player':
                key=(label['round'],tuple(c['card_id'] for c in label['cards'] if c['zone']=='player:0'))
                opportunities.setdefault(key,{'start_ms':label['timestamp_ms'],'r1_ms':None,'table_ms':None})
            for cid in label['seen']: first_seen.setdefault(cid,label['timestamp_ms'])
        try:
            while True:
                ok,pixels=cap.read()
                if not ok: break
                timestamp=index*1000/manifest['fps']; truth_index=index; index+=1
                if timestamp+1e-6<next_ms: continue
                next_ms+=350
                start=time.perf_counter()
                result=observer.process(Image.fromarray(cv2.cvtColor(pixels,cv2.COLOR_BGR2RGB)),sampled,1+timestamp/1000)
                elapsed=(time.perf_counter()-start)*1000; times.append(elapsed); sampled+=1
                # No annotations cross this recognition call.
                label=truth[truth_index]; expected=[c for c in label['cards'] if c['bbox']]
                pairs,missed,extra=anchors(expected,result['detections'])
                frame=Counter(missing_objects=len(missed),extra_objects=len(extra),
                              expected_backs=sum(c['presence']=='covered' for c in expected))
                frame['rank_missed']=sum(c['presence']=='readable' for c in missed)
                frame['missing_backs']=sum(c['presence']=='covered' for c in missed)
                for c,d in pairs:
                    if c['presence']=='covered': frame['correct_backs' if d['face_down'] else 'wrong_back_state']+=1
                    elif c['presence']=='readable':
                        frame['rank_correct' if d['rank']==c['rank'] else 'rank_unknown' if d['rank'] is None else 'rank_wrong']+=1
                        frame['suit_correct' if d['suit']==c['suit'] else 'suit_unknown' if d['suit'] is None else 'suit_wrong']+=1
                table_exact=not missed and not extra and all(d['face_down'] if c['presence']=='covered'
                    else d['rank']==c['rank'] if c['presence']=='readable' else d['rank'] is None for c,d in pairs)
                frame['complete_visible_table']=int(table_exact)
                frame['nonempty_table_observations']=int(bool(expected))
                frame['complete_nonempty_visible_table']=int(table_exact and bool(expected))
                active_tracks=[t for t in result['state']['tracks'] if t['missed']==0]
                track_pairs,_,_=anchors(expected,active_tracks)
                for c,t in track_pairs:
                    tid=t['card_id']; cid=c['card_id']
                    if tid in bindings and bindings[tid]!=cid:
                        switches.append({'timestamp_ms':timestamp,'track':tid,'before':bindings[tid],'after':cid})
                    bindings[tid]=cid
                for event in result['events']:
                    p=event['payload']; kind=event['kind']
                    if kind=='ROUND_STARTED': frame['round_starts' if expected else 'false_round_starts']+=1
                    if kind=='ROUND_STARTED' and expected: starts[label['round']]+=1
                    if kind=='ROUND_ENDED':
                        if not expected and label['phase']=='waiting': closures[label['round']]+=1
                        else: frame['false_round_closures']+=1
                    if kind not in ('CARD_CONFIRMED','CARD_REVEALED') or p.get('rank') is None: continue
                    cid=bindings.get(p['card_id']); correct=cid in label['seen'] and label['seen'].get(cid)==p['rank']
                    events.append({'timestamp_ms':timestamp,'track':p['card_id'],'physical_id':cid,'rank':p['rank'],'correct':correct})
                    if correct:
                        exposures[cid]+=1; first_committed.setdefault(cid,timestamp)
                    else: frame['wrong_or_unmatched_exposures']+=1
                expected_inventory=Counter(label['seen'].values()); actual=result['state']['known_rank_counts']
                final_drift={r:actual.get(r,0)-expected_inventory[r] for r in actual}
                drift=sum(abs(v) for v in final_drift.values()); drift_max=max(drift_max,drift)
                def hilo(r): return 1 if r in ('2','3','4','5','6') else -1 if r in ('A','10','J','Q','K') else 0
                rc_max=max(rc_max,abs(result['observed_running_count']-sum(hilo(r)*n for r,n in expected_inventory.items())))
                if result['count_reliable']: frame['certified_count_observations']+=1
                if result['temporal_evidence']['tracker_pending']: frame['provisional_observations']+=1
                player=[c['rank'] for c in expected if c['zone']=='player:0' and c['presence']=='readable']
                dealer=[c['rank'] for c in expected if c['zone']=='dealer' and c['presence']=='readable']
                expected_action=recommend(player,dealer[0],Rules(**manifest['rules']))['basic_action'] if label['phase']=='player' and len(player)>=2 and len(dealer)==1 else None
                r1=bool(result['advice'] and expected_action and result['phase']=='player'
                    and result['player']==player and result['dealer']==dealer and result['advice']['basic_action']==expected_action)
                if result['advice'] and not r1: frame['wrong_or_stale_basic_advice']+=1
                if label['phase']=='player':
                    key=(label['round'],tuple(c['card_id'] for c in label['cards'] if c['zone']=='player:0'))
                    o=opportunities[key]
                    if r1 and o['r1_ms'] is None: o['r1_ms']=timestamp+elapsed
                    if r1 and table_exact and o['table_ms'] is None: o['table_ms']=timestamp+elapsed
                counts.update(frame)
                traces.append({'timestamp_ms':timestamp,'truth_phase':label['phase'],'inventory_l1':drift,'metrics':dict(frame),'report':result})
        finally: cap.release(); observer.stop()
        if index!=len(truth) or index!=session['frames']: raise ValueError('Incomplete video decode')
        target=Path(output); save(target.parent/f'{name}.trace.json',traces)
        delays={field:[o[field]-o['start_ms'] if o[field] is not None else None for o in opportunities.values()] for field in ('r1_ms','table_ms')}
        report={'name':name,'profile':session['profile'],'group':session.get('group','development'),
            'seed':session.get('seed',manifest.get('seed')),'decoded_frames':index,'sampled_frames':sampled,
            'opportunities':len(opportunities),'r1_timely':sum(d is not None and d<=1500 for d in delays['r1_ms']),
            'table_timely':sum(d is not None and d<=1500 for d in delays['table_ms']),
            'first_basic_delay_ms':delays['r1_ms'],'first_full_table_delay_ms':delays['table_ms'],'metrics':dict(counts),
            'exposures':{'expected':len(truth[-1]['seen']),'matched_unique':len(exposures),
                'missing':len(set(truth[-1]['seen'])-set(exposures)), 'duplicate':sum(max(0,n-1) for n in exposures.values()),
                'wrong_or_unmatched':counts['wrong_or_unmatched_exposures'],'id_switches':len(switches)},
            'inventory_final_l1':sum(abs(v) for v in final_drift.values()),'inventory_final_drift':final_drift,
            'inventory_interim_max_l1':drift_max,'observed_rc_max_abs_error':rc_max,
            'confirmation_delay_ms':{'p50':float(np.percentile([first_committed[c]-first_seen[c] for c in first_committed],50)) if first_committed else None,
                'p95':float(np.percentile([first_committed[c]-first_seen[c] for c in first_committed],95)) if first_committed else None},
            'offline_processing_ms':{'p50':float(np.percentile(times,50)),'p95':float(np.percentile(times,95))},
            'rounds':{'expected':len({r['round'] for r in truth if r['cards']}),'starts':len(starts),
                'duplicate_starts':sum(max(0,n-1) for n in starts.values()),'observed_empty_closures':len(closures)},
            'event_audit':events,'id_switch_audit':switches}
        reports.append(report); print(json.dumps({k:report[k] for k in ('name','opportunities','r1_timely','table_timely','exposures','inventory_final_l1')}),flush=True)
    if before!=sources(code_root) or evaluator_hash!=digest(__file__): raise RuntimeError('Inference/evaluator changed during evaluation')
    save(output,{'schema':1,'partition':manifest['partition'],'candidate':candidate,'source_hashes':before,
        'evaluator_sha256':digest(__file__),'manifest_sha256':digest(path),'results':reports,'api_requests':0,
        'identity_scope':'One-to-one upright left/top anchors with diagnostic track bindings; no rank matching.',
        'runtime':{'python':platform.python_version(),'platform':platform.system(), 'processor':platform.processor(),
                   'opencv':cv2.__version__,'numpy':np.__version__},
        'timing_scope':'Offline processing plus source-timeline confirmation; not capture-to-display.',
        'limits':['No independent provider video','No certified TC','No poker/suit promotion','Graphic variants share hands']})


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['generate','run'])
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--manifest',type=Path)
    parser.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--candidate',action='store_true'); parser.add_argument('--profiles')
    args=parser.parse_args()
    if args.command=='generate': generate(args.output)
    else: replay(args.manifest,args.output,args.code_root,args.candidate,args.profiles.split(',') if args.profiles else None)


if __name__=='__main__': main()
