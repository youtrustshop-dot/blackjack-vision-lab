"""Optional research adapter: YOLO localizes, OCR reads, silhouette reads suits.

Same manual role ROIs as the calibrated profile. No labels are passed to inference,
no model is distributed with the application and no universal card reader claimed.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image

from bjlab.corner_vision import validate_layout,colored_backs
from bjlab.ocr import read_text
from bjlab.suit_symbols import read_suit
from bjlab.vision import CardDetection,_rgb
from validation.tools.yolo_corner_pilot import offline_configuration,RANKS


class LearnedCornerDetector:
    def __init__(self,layout,checkpoint,operating_points=None):
        offline_configuration(Path(checkpoint).resolve().parents[3])
        from ultralytics import YOLO
        self.model=YOLO(str(checkpoint))  # Our own verified training output only.
        if self.model.names!={0:'rank-corner'}:
            raise ValueError('Expected the one-class learned localizer, not generic COCO or 13-rank weights')
        self.regions=validate_layout(layout);self.last_diagnostics={};self.context={}
        self.threshold=.50;self.nms_iou=.50
        if operating_points:
            receipt=json.loads(Path(operating_points).read_text(encoding='utf-8'))
            if (hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()!=receipt['checkpoint_sha256'] or
                not receipt['can_proceed_to_development_roi_comparison']):
                raise ValueError('Localizer checkpoint/learning selection mismatch')
            self.threshold=receipt['selected']['threshold'];self.nms_iou=receipt['nms_iou']

    def detect(self,image):
        rgb=_rgb(image);height,width=rgb.shape[:2];found=[];candidates=[];rejected=0
        for zone in ('dealer','player:0'):
            x,y,w,h=self.regions[zone].to_pixels(width,height);pixels=rgb[y:y+h,x:x+w]
            for back in colored_backs(pixels):
                bx,by,bw,bh=back['bbox']
                found.append(CardDetection(None,None,(x+bx,y+by,bw,bh),1,face_down=True,zone=zone,
                             score_type='bounded_back_geometry_not_probability'))
            prediction=self.model.predict(Image.fromarray(pixels),imgsz=416,conf=self.threshold,device='cpu',verbose=False)[0]
            from validation.tools.learning_operating_points import suppress
            kept=suppress([{'xyxy':b,'confidence':s} for b,s in zip(prediction.boxes.xyxy.tolist(),prediction.boxes.conf.tolist())],self.threshold,self.nms_iou)
            for item in kept:
                bounds,confidence=item['xyxy'],item['confidence']
                a,b,c,d=[int(round(v)) for v in bounds];a=max(0,a);b=max(0,b);c=min(w,c);d=min(h,d)
                if c<=a or d<=b:continue
                crop=pixels[max(0,b-2):min(h,d+2),max(0,a-2):min(w,c+2)]
                padded=np.pad(crop,((4,4),(4,4),(0,0)),constant_values=255)
                token,score=read_text(padded);rank=token.strip().upper()
                accepted=rank in RANKS and score>=.80
                gh=d-b;gw=c-a
                suit=read_suit(pixels[d+1:min(h,d+1+max(8,round(gh*1.5))),max(0,a-2):min(w,a+max(gw+4,round(gh*1.2)))]) if accepted else None
                bbox=(x+max(0,a-3),y+max(0,b-5),max(1,min(w-a,round(gh*5))),max(1,min(h-b,round(gh*7))))
                if any(o.zone==zone and abs(o.bbox[0]-bbox[0])<max(4,gh*.5) and abs(o.bbox[1]-bbox[1])<max(4,gh*.5) for o in found):
                    candidates.append({'reason':'overlapping localizer prediction','bbox':list(bbox)});continue
                candidates.append({'zone':zone,'glyph_bbox':[x+a,y+b,gw,gh],'localizer_score':confidence,
                    'ocr_score':score,'raw_token':token,'accepted':accepted,'reason':None if accepted else 'rank unknown'})
                if not accepted:rejected+=1
                found.append(CardDetection(rank if accepted else None,suit,bbox,score if accepted else 1.,zone=zone,
                             score_type='ocr_token_score' if accepted else 'localizer_presence_not_probability'))
        self.context={'profile':'learned-corners-research','phase':'unknown','controls':[],'reasons':[],'player_totals':{},
                      'provenance':'manual role calibration, YOLO location, current-pixel OCR/silhouette'}
        self.last_diagnostics={'rejected_card_candidates':rejected,'candidates':candidates,
                               'localizer_threshold':self.threshold,'nms_iou':self.nms_iou,
                               'scope':'optional one-class localizer with shared OCR, suit and back components'}
        return sorted(found,key=lambda d:(d.zone,d.bbox[0]))
