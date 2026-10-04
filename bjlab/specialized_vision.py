"""Optional research-only ONNX card/index perception; not a production default.

Models are supplied explicitly and verified against a completed local receipt.
This module does not train, download weights, import Ultralytics or call APIs.
Bounding rectangles below represent observed extents; the four index points are
a conditional plane estimate, not evidence of invisible whole-card corners.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from .events import RANKS, SUITS
from .vision import CardDetection, _rgb


def ordered_rectification(pixels, quad):
    points=np.asarray(quad,np.float32)
    if points.shape!=(4,2) or not np.isfinite(points).all(): raise ValueError("Invalid index points")
    if cv2.contourArea(points,oriented=True)<=8 or not cv2.isContourConvex(points):
        raise ValueError("Reflected/degenerate index plane")
    target=np.float32([[0,0],[47,0],[47,71],[0,71]])
    return cv2.warpPerspective(pixels,cv2.getPerspectiveTransform(points,target),(48,72),
        flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(127,127,127))


def softmax(values):
    shifted=values-values.max(axis=1,keepdims=True)
    exp=np.exp(shifted); return exp/exp.sum(axis=1,keepdims=True)


def decoded_label(scores,labels,threshold,margin):
    order=np.argsort(scores); best=int(order[-1]); score=float(scores[best])
    gap=score-float(scores[order[-2]])
    label=labels[best] if score>=threshold and gap>=margin else None
    return label,score,gap


def intersection_over_union(a,b):
    ax,ay,aw,ah=a; bx,by,bw,bh=b
    area=max(0,min(ax+aw,bx+bw)-max(ax,bx))*max(0,min(ay+ah,by+bh)-max(ay,by))
    return area/max(1,aw*ah+bw*bh-area)


def spatial_suppression(proposals,threshold=.75):
    """Suppress coincident geometry only. Equal faces in a multideck shoe survive."""
    kept=[]
    for item in sorted(proposals,key=lambda x:x["score"],reverse=True):
        if any(item["class"]==other["class"] and intersection_over_union(item["bbox"],other["bbox"])>threshold for other in kept): continue
        kept.append(item)
    return kept


class SpecializedCardDetector:
    def __init__(self,manifest_path,layout=None,*,threads=4):
        import onnxruntime as ort
        path=Path(manifest_path).resolve(); self.root=path.parent
        self.manifest=json.loads(path.read_text(encoding="utf-8"))
        if self.manifest.get("schema")!=1 or self.manifest.get("model_family")!="YOLO26n-pose": raise ValueError("Unsupported research receipt")
        self.version=self.manifest["reader_version"]; self.layout=layout
        self.thresholds=self.manifest["thresholds"]
        if set(self.thresholds)!={"proposal","rank","suit","margin"} or any(not 0<v<1 for v in self.thresholds.values()): raise ValueError("Invalid thresholds")
        self.tracking_minimum_score=self.thresholds["proposal"]
        options=ort.SessionOptions(); options.intra_op_num_threads=threads; options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        sessions=[]
        for name in ("pose_model","classifier_model"):
            filename=self.manifest[name]; target=(self.root/filename).resolve()
            if not target.is_relative_to(self.root): raise ValueError("Model path escapes receipt")
            expected=self.manifest["exports"][filename]["sha256"]
            if hashlib.sha256(target.read_bytes()).hexdigest()!=expected: raise ValueError("Model hash mismatch")
            sessions.append(ort.InferenceSession(str(target),sess_options=options,providers=["CPUExecutionProvider"]))
        self.pose,self.classifier=sessions
        self.context={}; self.last_diagnostics={"rejected_card_candidates":0}
        self.debug_images={}; self.raw_proposals=[]

    def _zone(self,box,width,height):
        if not self.layout: return "unknown"
        x,y,w,h=box; cx,cy=(x+w/2)/width,(y+h/2)/height
        for name,(lx,ly,lw,lh) in self.layout.items():
            if name in ("dealer","player:0") and lx<=cx<=lx+lw and ly<=cy<=ly+lh: return name
        return None

    def detect(self,image):
        began=time.perf_counter(); pixels=_rgb(image); height,width=pixels.shape[:2]
        side=self.manifest["imgsz"]; ratio=min(side/width,side/height)
        rw,rh=round(width*ratio),round(height*ratio); ox,oy=(side-rw)//2,(side-rh)//2
        square=np.full((side,side,3),114,np.uint8)
        square[oy:oy+rh,ox:ox+rw]=cv2.resize(pixels,(rw,rh),interpolation=cv2.INTER_LINEAR)
        tensor=np.ascontiguousarray(square.transpose(2,0,1)[None],dtype=np.float32)/255.
        rows=self.pose.run(None,{self.pose.get_inputs()[0].name:tensor})[0]
        if rows.ndim!=3 or rows.shape[0]!=1 or rows.shape[2]!=19 or not np.isfinite(rows).all(): raise ValueError("Unexpected pose export output")
        proposed=[]
        for row in rows[0]:
            cls=int(np.argmax(row[4:7])); score=float(row[4+cls])
            if score<self.thresholds["proposal"] or cls not in (0,1,2): continue
            left,top,right,bottom=(row[:4]-np.asarray([ox,oy,ox,oy]))/ratio
            left,top=max(0,float(left)),max(0,float(top)); right,bottom=min(width,float(right)),min(height,float(bottom))
            if right-left<2 or bottom-top<2: continue
            box=(round(left),round(top),max(1,round(right-left)),max(1,round(bottom-top)))
            zone=self._zone(box,width,height)
            if zone is None: continue
            points=row[7:].reshape(4,3).copy(); points[:,:2]=(points[:,:2]-[ox,oy])/ratio
            proposed.append({"class":cls,"score":score,"bbox":box,"quad":points[:,:2].tolist(),
                             "keypoint_scores":points[:,2].tolist(),"zone":zone})
        proposed=spatial_suppression(proposed)
        patches=[]; indices=[]; issues=[]
        for item in proposed:
            if item["class"]!=0: continue
            try: patch=ordered_rectification(pixels,item["quad"])
            except ValueError:
                item.update(rank=None,suit=None,geometry="invalid_plane"); issues.append("Index geometry is unresolved")
                continue
            patches.append(patch.transpose(2,0,1)); indices.append(item)
        if patches:
            inputs=np.ascontiguousarray(np.stack(patches),dtype=np.float32)/255.
            rank,suit=self.classifier.run(None,{self.classifier.get_inputs()[0].name:inputs})
            if rank.shape!=(len(patches),14) or suit.shape!=(len(patches),5) or not np.isfinite(rank).all() or not np.isfinite(suit).all(): raise ValueError("Classifier export output invalid")
            rank,suit=softmax(rank),softmax(suit)
            for i,item in enumerate(indices):
                r,rs,rm=decoded_label(rank[i],[*RANKS,None],self.thresholds["rank"],self.thresholds["margin"])
                s,ss,sm=decoded_label(suit[i],[*SUITS,None],self.thresholds["suit"],self.thresholds["margin"])
                item.update(rank=r,suit=s,rank_score=rs,suit_score=ss,rank_margin=rm,suit_margin=sm,geometry="rectified_index_plane")
        bodies=[p for p in proposed if p["class"] in (1,2)]
        used=set(); detections=[]; reconciled=[]
        for item in [p for p in proposed if p["class"]==0]:
            # One physical body may own one upper index. No face-label dedup.
            cx,cy=np.asarray(item["quad"]).mean(axis=0)
            choices=[]
            for i,body in enumerate(bodies):
                if i in used or body["class"]==2 or body["zone"]!=item["zone"]: continue
                x,y,w,h=body["bbox"]
                if x-4<=cx<=x+w+4 and y-4<=cy<=y+h+4:
                    distance=float(np.linalg.norm(np.asarray(body["quad"])[0]-np.asarray(item["quad"])[0]))
                    choices.append((distance,i))
            body_id=min(choices)[1] if choices else None
            if body_id is not None: used.add(body_id)
            box=bodies[body_id]["bbox"] if body_id is not None else item["bbox"]
            rank=item.get("rank"); suit=item.get("suit")
            # Score represents presence/recognition acceptance, never a calibrated
            # chance of correctness. The observer applies its own temporal gate.
            detections.append(CardDetection(rank,suit,box,item["score"],zone=item["zone"],score_type="learned_index_detection_score"))
            reconciled.append({"index":item,"body":bodies[body_id] if body_id is not None else None})
        for i,body in enumerate(bodies):
            if i in used: continue
            detections.append(CardDetection(None,None,body["bbox"],body["score"],face_down=body["class"]==2,
                                           zone=body["zone"],score_type="learned_presence_uncalibrated"))
        self.context={"profile":self.version,"phase":"unknown","controls":[],"player_totals":{},"reasons":issues,
                      "provenance":"Explicit card zones; current-pixel keypoint localization and learned rank/suit. Phase remains a separate visible-context reader."}
        self.raw_proposals=proposed
        self.last_diagnostics={"profile":self.version,"detector_version":self.version,"input_size":[width,height],
            "proposal_count":len(proposed),"proposals":proposed,"reconciled":reconciled,"detections":len(detections),
            "unmatched_surface_count":len(bodies)-len(used),
            "unreadable_index_count":sum(p.get('rank') is None for p in proposed if p['class']==0),
            "rejected_card_candidates":len(issues),"thresholds":dict(self.thresholds),
            "score_semantics":self.manifest["score_type"],"latency_ms":(time.perf_counter()-began)*1000,
            "index_quad_scope":"Conditional index plane estimate; not observed hidden body corners"}
        self.debug_images={"letterbox":square}
        return sorted(detections,key=lambda d:(d.zone,d.bbox[0]))
