"""Same-input research challenger evaluation, with independent truth boundaries.

Perception scores use geometry-only assignment. Historical sessions reuse the
existing unchanged replay evaluator, retaining its bounded anchor limitations.
No annotations, simulator phase or identities enter either reader.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import time

import numpy as np
from PIL import Image


def digest(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,document):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(document,indent=2,allow_nan=False)+"\n",encoding="utf-8")


def verification_claim(selection, job, corpus_sha256, reader_path, code_root):
    """Consume one predeclared paired job before exposing its verification truth.

    Interrupted runs stay consumed. Replaying one is historical regression,
    never a fresh independent result. The paired baseline/challenger jobs are
    allowed once each, against exactly the same frozen selection.
    """
    from validation.tools.overlap_session import sources
    if selection is None:
        raise ValueError("New verification requires a preselected reader receipt")
    selection=Path(selection).resolve()
    frozen=json.loads(selection.read_text(encoding="utf-8"))
    if frozen.get("evaluator_sha256")!=digest(__file__):
        raise ValueError("Evaluator changed after selection")
    plan=frozen.get("verification_jobs",{}).get(job)
    if not plan or plan["corpus_sha256"]!=corpus_sha256:
        raise ValueError("Verification job was not predeclared for this corpus")
    if frozen.get("verification_previously_used") is not False:
        raise ValueError("Consumed verification is historical regression only")
    if reader_path is not None and digest(reader_path)!=frozen["reader_sha256"]:
        raise ValueError("Reader changed after selection")
    if sources(Path(code_root))!=plan["source_hashes"]:
        raise ValueError("Inference source changed after selection")
    ledger_path=selection.with_suffix(".consumption.json")
    lock_path=selection.with_suffix(".consumption.lock")
    descriptor=os.open(lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.close(descriptor)
        ledger=json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {
            "schema":1,"selection_sha256":digest(selection),"jobs":{}}
        if ledger["selection_sha256"]!=digest(selection):
            raise ValueError("Selection changed after verification began")
        if job in ledger["jobs"]:
            raise ValueError("Verification job already consumed; retain it as historical evidence")
        ledger["jobs"][job]={"status":"started","corpus_sha256":corpus_sha256,
                              "started_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
        save(ledger_path,ledger)
    finally:
        lock_path.unlink()
    return ledger_path,job


def verification_complete(claim, output):
    if claim is None: return
    ledger_path,job=claim
    ledger=json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["jobs"][job].update(status="complete",result_sha256=digest(output))
    save(ledger_path,ledger)


def geometry_pairs(expected,detected):
    """Maximum global IoU assignment; labels/face values never affect pairing."""
    from scipy.optimize import linear_sum_assignment
    from bjlab.specialized_vision import intersection_over_union
    n,m=len(expected),len(detected)
    if not n or not m: return [],list(expected),list(detected)
    cost=np.zeros((n+m,n+m)); cost[:n,:m]=5; cost[:n,m:]=1.1; cost[n:,:m]=1.1
    for i,a in enumerate(expected):
        for j,b in enumerate(detected):
            iou=intersection_over_union(a["bbox"],b["bbox"])
            if iou>=.15: cost[i,j]=1-iou
    rows,cols=linear_sum_assignment(cost)
    pairs=[(int(i),int(j)) for i,j in zip(rows,cols) if i<n and j<m and cost[i,j]<=.85]
    ei={i for i,j in pairs}; di={j for i,j in pairs}
    return [(expected[i],detected[j]) for i,j in pairs], [a for i,a in enumerate(expected) if i not in ei], [b for j,b in enumerate(detected) if j not in di]


def load_corpus(data,partition,selection=None):
    data=Path(data).resolve(); manifest=json.loads((data/"manifest.json").read_text(encoding="utf-8"))
    if partition not in ("calibration","verification"): raise ValueError("Training/final holdout not accepted as independent evaluation")
    spec=manifest["partitions"][partition]
    if digest(data/f"{partition}.truth.json")!=spec["truth_sha256"]: raise ValueError("Frozen truth changed")
    if partition=="verification":
        if selection is None: raise ValueError("Verification requires preselected reader receipt")
        frozen=json.loads(Path(selection).read_text(encoding="utf-8"))
        if frozen["data_manifest_sha256"]!=digest(data/"manifest.json"): raise ValueError("Wrong selected corpus")
        if frozen.get("verification_previously_used") is not False: raise ValueError("Consumed verification is historical regression only")
    return manifest,json.loads((data/f"{partition}.truth.json").read_text(encoding="utf-8"))


def perception(data,partition,output,reader_path=None,selection=None,limit=None):
    # This is card perception, not a semantically legal random-table game.
    # Both readers receive the same two half-frame card zones.
    from bjlab.corner_vision import CornerCardDetector
    from bjlab.specialized_vision import SpecializedCardDetector
    from validation.tools.overlap_session import sources
    root=Path(__file__).resolve().parents[2]
    source_hashes=sources(root)
    data=Path(data).resolve()
    if partition=="verification" and limit is not None:
        raise ValueError("Verification must retain the full predeclared denominator")
    claim=verification_claim(selection,"perception-specialized" if reader_path else "perception-current",
                             digest(data/"manifest.json"),reader_path,root) if partition=="verification" else None
    manifest,truth=load_corpus(data,partition,selection)
    if selection is not None and reader_path is not None:
        frozen=json.loads(Path(selection).read_text(encoding="utf-8"))
        if digest(reader_path)!=frozen["reader_sha256"]: raise ValueError("Reader changed after selection")
    layout={"table":(0,0,1,1),"dealer":(0,0,1,.5),"player:0":(0,.5,1,.5)}
    reader=SpecializedCardDetector(reader_path,layout) if reader_path else CornerCardDetector(layout)
    totals=Counter(); by_condition={}; times=[]; rows=[]
    for label in truth[:limit]:
        image_path=data/label["image"]
        if digest(image_path)!=label["image_sha256"]: raise ValueError("Image changed")
        image=Image.open(image_path).convert("RGB")
        began=time.perf_counter(); result=reader.detect(image); elapsed=(time.perf_counter()-began)*1000; times.append(elapsed)
        detections=[d.to_dict() for d in result]
        expected=[c for c in label["objects"] if c["bbox"]]
        pairs,missing,extra=geometry_pairs(expected,detections)
        counts=Counter(frames=1,expected_objects=len(expected),matched_objects=len(pairs),
                       missing_objects=len(missing),extra_objects=len(extra),
                       expected_rank_readable=sum(c["rank"] is not None for c in expected),
                       expected_suit_readable=sum(c["suit"] is not None for c in expected),
                       expected_backs=sum(c["presence"]=="covered" for c in expected),
                       nonempty_frames=int(bool(expected)))
        for c in missing:
            if c["rank"] is not None: counts["rank_missed"]+=1
            if c["suit"] is not None: counts["suit_missed"]+=1
            if c["presence"]=="covered": counts["back_missed"]+=1
        exact=not missing and not extra
        for c,d in pairs:
            down=c["presence"]=="covered"
            correct_back=down==d["face_down"]
            counts["presence_correct" if correct_back else "presence_wrong"]+=1
            if down:
                counts["back_correct" if correct_back else "back_wrong"]+=1
                exact=exact and correct_back and d["rank"] is None and d["suit"] is None
                continue
            for field in ("rank","suit"):
                if c[field] is not None:
                    counts[field+"_correct" if d[field]==c[field] and not d["face_down"] else field+"_unknown" if d[field] is None else field+"_wrong"]+=1
                else:
                    counts[field+"_unknown_correct" if d[field] is None else field+"_inferred_on_unreadable"]+=1
            exact=exact and correct_back and d["rank"]==c["rank"] and d["suit"]==c["suit"]
        counts["exact_nonempty_face_state"]=int(bool(expected) and exact)
        counts["false_presence_on_empty"]=int(not expected and bool(detections))
        from bjlab.specialized_vision import intersection_over_union
        for candidate in extra:
            overlaps=[intersection_over_union(candidate['bbox'],card['bbox']) for card in expected]
            duplicate=any(intersection_over_union(candidate['bbox'],card['bbox'])>=.15 for card,_ in pairs)
            counts['extra_duplicate_geometry_proxy' if duplicate else 'extra_low_iou_body_proxy' if overlaps and max(overlaps)>0 else 'extra_outside_card_proxy']+=1
        totals.update(counts)
        rotated=any(abs(np.degrees(np.arctan2(c['index_quad'][1][1]-c['index_quad'][0][1],c['index_quad'][1][0]-c['index_quad'][0][0])))>10 for c in expected)
        for category,active in (("all",True),("overlap",label["overlap"]),("rotation",rotated),("popup",label["popup"]),
                                ("unknown_rank",any(c["presence"]=="unreadable" for c in expected)),
                                ("ink_visibility_loss",any(c["rank_visible_fraction"]<.9 for c in expected if c["presence"]!="covered"))):
            if active: by_condition.setdefault(category,Counter()).update(counts)
        rows.append({"index":label["index"],"image_sha256":label["image_sha256"],"elapsed_ms":elapsed,
                     "metrics":dict(counts),"detections":detections,
                     "diagnostics":reader.last_diagnostics})
        if len(rows)%100==0: print(json.dumps({"perception":partition,"reader":reader.version if reader_path else "current-local","frames":len(rows)}),flush=True)
    receipt={"schema":1,"kind":"owned-independent-perception","partition":partition,"reader":"specialized-card-v1" if reader_path else "current-local",
             "data_manifest_sha256":digest(data/"manifest.json"),"reader_manifest_sha256":digest(reader_path) if reader_path else None,
             "source_hashes":source_hashes,"selection_sha256":digest(selection) if selection else None,
             "evaluator_sha256":digest(__file__),"counts":dict(totals),"by_condition":{k:dict(v) for k,v in by_condition.items()},
             "offline_processing_ms":{"p50":float(np.percentile(times,50)),"p95":float(np.percentile(times,95)),"max":max(times)},
             "assistance":"Same predeclared two half-frame card zones; no manual turn, truth/phase/IDs passed to recognition.",
             "matching":"Global one-to-one observed-box IoU >=.15; labels never used. This is presence/classification, not precise mask/pose AP. Extra cause categories are geometric diagnostic proxies, not independently annotated causal diagnoses.",
             "limits":["Original synthetic artwork/shared renderer only, no independent provider capture.","Random card scenes are not full legal games; semantic roles are not scored here.","Visibility is separate renderer ink fractions, not independently judged human legibility."],
             "api_requests":0,"final_holdout":"sealed_untouched"}
    output=Path(output); save(output,receipt); save(output.with_suffix(".trace.json"),rows)
    if source_hashes!=sources(root): raise RuntimeError("Inference changed during evaluation")
    verification_complete(claim,output)
    print(json.dumps({"reader":receipt["reader"],"partition":partition,"counts":dict(totals),"latency":receipt["offline_processing_ms"]}),flush=True)


def sessions(corpus,partition,output,reader_path=None,profiles=None,selection=None,baseline_root=None):
    from validation.tools.overlap_session import replay,sources
    root=Path(__file__).resolve().parents[2]; corpus=Path(corpus).resolve()
    freeze=json.loads((corpus/"freeze.json").read_text(encoding="utf-8"))
    if partition not in ("development","validation"): raise ValueError("Historical final holdout remains sealed")
    manifest_path=corpus/freeze["manifests"][partition]["path"]
    if digest(manifest_path)!=freeze["manifests"][partition]["sha256"]: raise ValueError("Session manifest changed")
    code_root=Path(baseline_root).resolve() if baseline_root else root
    if freeze.get("verification_status") and profiles is not None:
        raise ValueError("New session verification must retain all predeclared profiles")
    if reader_path is None and baseline_root is None:
        raise ValueError("Baseline sessions require an explicit frozen code root")
    claim=verification_claim(selection,"sessions-specialized" if reader_path else "sessions-current",
                             digest(manifest_path),reader_path,code_root) if freeze.get("verification_status") else None
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(partition="development" if partition=="development" else "verification",original_partition=partition)
    for session in manifest["sessions"]:
        for field in ("video","truth"):
            target=manifest_path.parent/session[field]
            if digest(target)!=session[field+"_sha256"]: raise ValueError("Session evidence changed")
            session[field]=str(target.resolve())
    live=None
    if reader_path:
        from bjlab import live
        from bjlab.specialized_vision import SpecializedCardDetector
        observer_class=live.LiveObserver
        class ResearchObserver(observer_class):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs)
                self.detector=SpecializedCardDetector(reader_path,self.layout)
                self.tracker.minimum_score=self.detector.tracking_minimum_score
                # One authoritative presence reader; common lifecycle/phase.
                self.context_challenger.covered_presence=lambda image,detections:(detections,[])
                self.context_challenger.back_proposals=[]
        live.LiveObserver=ResearchObserver
    output=Path(output); path=output.parent/"session-evaluator-manifest.json"
    save(path,manifest)
    try: replay(path,output,code_root,True,profiles)
    finally:
        if live is not None: live.LiveObserver=observer_class
    result=json.loads(output.read_text(encoding="utf-8")); result.update(reader="specialized-card-v1" if reader_path else "current-local",original_partition=partition,
        reader_manifest_sha256=digest(reader_path) if reader_path else None,session_manifest_sha256=digest(manifest_path),
        frozen_baseline_commit=freeze["baseline_commit"],current_sources=sources(code_root),
        selection_sha256=digest(selection) if selection else None,
        assistance="Same declared table/card/control ROIs and source-timeline sampling. Shared visible phase and existing tracker; no per-turn confirmation.",
        presence_difference="Challenger's learned presence replaces geometric back recovery; integrity gate remains active." if reader_path else "Frozen baseline's geometric back recovery; integrity gate remains active.",
        final_holdout="sealed_untouched")
    save(output,result)
    verification_complete(claim,output)


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("command",choices=("perception","sessions"))
    parser.add_argument("--data",type=Path,required=True); parser.add_argument("--partition",required=True)
    parser.add_argument("--output",type=Path,required=True); parser.add_argument("--reader",type=Path)
    parser.add_argument("--selection",type=Path); parser.add_argument("--limit",type=int); parser.add_argument("--profiles")
    parser.add_argument("--baseline-root",type=Path)
    args=parser.parse_args()
    if args.command=="perception": perception(args.data,args.partition,args.output,args.reader,args.selection,args.limit)
    else: sessions(args.data,args.partition,args.output,args.reader,args.profiles.split(',') if args.profiles else None,args.selection,args.baseline_root)
