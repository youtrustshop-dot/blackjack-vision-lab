"""Explicit native-pixel card regions; rank reading has no site/color contract.

This is a research profile, not a universal detector. Candidate corners come
from light card surfaces; unknown/cropped glyphs remain rejected evidence.
"""
from pathlib import Path
import time

import cv2
import numpy as np

from .calibration import NormalizedROI
from .ocr import read_text
from .suit_symbols import read_suit
from .vision import CardDetection, _rgb

VERSION = 'calibrated-corners-1'
RANKS = ('A','2','3','4','5','6','7','8','9','10','J','Q','K')


def validate_layout(layout):
    if set(layout)-{'table','dealer','player:0','controls'} or not {'table','dealer','player:0'} <= set(layout):
        raise ValueError('Select table, dealer and player:0 native-pixel regions.')
    regions={name:NormalizedROI(*box) for name,box in layout.items()}
    table=regions['table']
    for name,region in regions.items():
        if name!='table' and not (table.x<=region.x and table.y<=region.y and
            region.x+region.width<=table.x+table.width+1e-9 and
            region.y+region.height<=table.y+table.height+1e-9):
            raise ValueError('Card/control regions must be inside the selected table.')
    a,b=regions['dealer'],regions['player:0']
    if min(a.x+a.width,b.x+b.width)>max(a.x,b.x) and min(a.y+a.height,b.y+b.height)>max(a.y,b.y):
        raise ValueError('Dealer and player card regions must not overlap.')
    return regions


def contours(mask):
    return cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]


class CornerCardDetector:
    def __init__(self,layout,*,minimum_score=.80):
        self.regions=validate_layout(layout)
        self.minimum_score=minimum_score
        self.last_diagnostics={}
        self.context={}
        self.debug_images={}

    def detect(self,image):
        began=time.perf_counter(); rgb=_rgb(image); height,width=rgb.shape[:2]
        self.debug_images={}; candidates=[]; detections=[]; rejected=0
        boxes={name:region.to_pixels(width,height) for name,region in self.regions.items()}
        for zone in ('dealer','player:0'):
            zx,zy,zw,zh=boxes[zone]; pixels=rgb[zy:zy+zh,zx:zx+zw]
            self.debug_images[zone.replace(':','-')]=pixels.copy()
            hsv=cv2.cvtColor(pixels,cv2.COLOR_RGB2HSV)
            light=cv2.inRange(hsv,np.array([0,0,145],np.uint8),np.array([179,145,255],np.uint8))
            light=cv2.morphologyEx(light,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
            self.debug_images[zone.replace(':','-')+'-surface-mask']=light
            for body in contours(light):
                bx,by,bw,bh=cv2.boundingRect(body)
                if bh<22 or bw<7 or bw*bh<220 or bw/bh>5 or bh>zh*.99:
                    continue
                # A merged body can contain several top-left corners. Do not
                # require a full card-width rectangle for an exposed sliver.
                top_height=max(10,round(bh*.28))
                top=pixels[by:by+top_height,bx:bx+bw]
                channels=top.astype(np.int16)
                ink=((channels.max(2)<155)|((channels[:,:,0]-channels[:,:,1]>45)&
                    (channels[:,:,0]-channels[:,:,2]>35))).astype(np.uint8)*255
                glyphs=[]
                for glyph in contours(ink):
                    gx,gy,gw,gh=cv2.boundingRect(glyph)
                    if 5<=gh<=max(9,bh*.24) and 2<=gw<=bh*.25 and gy<=max(4,bh*.13):
                        glyphs.append([gx,gy,gw,gh])
                glyphs.sort()
                groups=[]
                for box in glyphs:
                    gx,gy,gw,gh=box
                    if groups:
                        px,py,pw,ph=groups[-1]
                        if 0<=gx-px-pw<=max(2,gh*.25) and abs(gy+gh-py-ph)<=max(2,gh*.20):
                            groups[-1]=[px,min(py,gy),gx+gw-px,max(py+ph,gy+gh)-min(py,gy)]
                            continue
                    groups.append(box)
                for gx,gy,gw,gh in groups:
                    # A corner should have a light surface just above/along it.
                    absolute=[zx+bx+gx,zy+by+gy,gw,gh]
                    crop=top[max(0,gy-2):min(top_height,gy+gh+2),max(0,gx-2):min(bw,gx+gw+2)]
                    padded=cv2.copyMakeBorder(crop,4,4,4,4,cv2.BORDER_CONSTANT,value=(255,255,255))
                    token,score=read_text(padded); rank=token.strip().upper()
                    accepted=rank in RANKS and score>=self.minimum_score
                    key=f'candidate-{len(candidates):03}'
                    self.debug_images[key+'-rank']=crop.copy()
                    record={'zone':zone,'body_bbox':[zx+bx,zy+by,bw,bh],
                        'rank_bbox':absolute,'raw_token':token,'score':score,
                        'threshold':self.minimum_score,'accepted':accepted,
                        'reason':None if accepted else 'rank vocabulary or OCR score rejected',
                        'crop':key+'-rank.png','provenance':'current-pixel-ocr'}
                    candidates.append(record)
                    if not accepted:
                        rejected+=1;continue
                    # Locate the small symbol immediately below this rank.
                    sx=max(0,bx+gx-2); sy=by+gy+gh+1
                    suit_pixels=pixels[sy:min(zh,sy+max(8,round(gh*1.5))),sx:min(zw,sx+max(gw+4,round(gh*1.2)))]
                    self.debug_images[key+'-suit']=suit_pixels.copy()
                    suit=read_suit(suit_pixels)
                    left=max(zx,zx+bx+gx-max(2,round(bh*.04)))
                    bbox=(left,zy+by,min(round(bh*.74),width-left),bh)
                    if any(d.zone==zone and abs(d.bbox[0]-left)<max(4,bh*.13) and abs(d.bbox[1]-(zy+by))<bh*.2 for d in detections):
                        record['reason']='second corner candidate of the same surface';continue
                    detections.append(CardDetection(rank,suit,bbox,score,zone=zone,score_type='ocr_token_score'))
        self.context={'profile':VERSION,'table_bounds':list(boxes['table']),'phase':'unknown',
            'controls':[],'player_totals':{},'reasons':[],
            'provenance':'explicit user regions; current-pixel rank OCR; turn requires confirmation'}
        self.last_diagnostics={'profile':VERSION,'detector_version':VERSION,'input_size':[width,height],
            'regions':{name:list(box) for name,box in boxes.items()},'candidates':candidates,
            'rejected_card_candidates':rejected,'detections':len(detections),
            'threshold':self.minimum_score,'score_semantics':'OCR score, not recognition probability',
            'latency_ms':(time.perf_counter()-began)*1000,
            'scope':'explicit card regions, visible upright corner glyphs; rotation/backs not yet supported'}
        return sorted(detections,key=lambda d:(d.zone,d.bbox[0]))

    def export_debug(self,directory):
        from PIL import Image
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        for name,pixels in self.debug_images.items():
            if pixels.size:Image.fromarray(pixels).save(directory/(name+'.png'))
