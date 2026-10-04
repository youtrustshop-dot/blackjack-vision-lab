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

VERSION = 'calibrated-corners-2-presence'
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


def colored_backs(pixels):
    """Bounded colored-back hypothesis in a declared card zone, not a generic detector.

    A narrow exposed strip can be sufficient. Require a bright border and texture;
    dark blue face ink, a plain blue tile and the table background are not backs.
    No rank, suit or probability is inferred from this geometric rule.
    """
    hsv=cv2.cvtColor(pixels,cv2.COLOR_RGB2HSV)
    light=(hsv[:,:,1]<65)&(hsv[:,:,2]>175)
    results=[]; height,width=pixels.shape[:2]
    # Red face artwork/chips caused extra objects in the first development run.
    # Retain that negative result; only the bounded blue rule proceeds here.
    for color,mask in (('blue',cv2.inRange(hsv,np.array([90,70,80],np.uint8),np.array([135,255,255],np.uint8))),):
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        for contour in contours(mask):
            x,y,w,h=cv2.boundingRect(contour)
            if h<max(25,height*.20) or w<8 or not .08<=w/h<=.80 or h>=height*.98 or cv2.contourArea(contour)/(w*h)<.45:
                continue
            a,b,c,d=max(0,x-3),max(0,y-3),min(width,x+w+3),min(height,y+h+3)
            rim=light[b:d,a:c].copy(); rim[max(0,y-b+2):min(d-b,y-b+h-2),max(0,x-a+2):min(c-a,x-a+w-2)]=False
            rim_pixels=(d-b)*(c-a)-max(0,h-4)*max(0,w-4)
            border=float(rim.sum()/max(1,rim_pixels))
            texture=float(light[y:y+h,x:x+w].mean())
            if border<.15 or not .04<=texture<=.80:
                continue
            results.append({'bbox':(x,y,w,h),'color':color,'border_fraction':border,'light_texture_fraction':texture})
    return results


class CornerCardDetector:
    def __init__(self,layout,*,minimum_score=.80,surface_profile='legacy'):
        if surface_profile not in ('legacy','neutral'):
            raise ValueError('Unknown surface profile.')
        self.regions=validate_layout(layout)
        self.minimum_score=minimum_score
        # Research challenger only. The default retains the frozen baseline.
        # Neutral bright surfaces exclude colored badges and faded table ink;
        # tinted card stock may require the baseline instead.
        self.surface_profile=surface_profile
        self.last_diagnostics={}
        self.context={}
        self.debug_images={}

    def detect(self,image):
        began=time.perf_counter(); rgb=_rgb(image); height,width=rgb.shape[:2]
        self.debug_images={}; candidates=[]; detections=[]; rejected=0; surfaces=[]; border_artifacts=[]; geometry_reasons=[]; non_index=[]
        boxes={name:region.to_pixels(width,height) for name,region in self.regions.items()}
        for zone in ('dealer','player:0'):
            zx,zy,zw,zh=boxes[zone]; pixels=rgb[zy:zy+zh,zx:zx+zw]
            self.debug_images[zone.replace(':','-')]=pixels.copy()
            hsv=cv2.cvtColor(pixels,cv2.COLOR_RGB2HSV)
            floor,saturation=(145,145) if self.surface_profile=='legacy' else (175,65)
            light=cv2.inRange(hsv,np.array([0,0,floor],np.uint8),np.array([179,saturation,255],np.uint8))
            light=cv2.morphologyEx(light,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
            self.debug_images[zone.replace(':','-')+'-surface-mask']=light
            backs=colored_backs(pixels)
            for back in backs:
                x,y,w,h=back['bbox']
                bbox=(zx+x,zy+y,w,h)
                detections.append(CardDetection(None,None,bbox,1.,face_down=True,zone=zone,
                                  score_type='bounded_back_geometry_not_probability'))
                surfaces.append({'zone':zone,'bbox':list(bbox),'visibility':'covered',
                    'provenance':'current-pixel colored border/texture rule',**{k:v for k,v in back.items() if k!='bbox'}})
            for body in contours(light):
                bx,by,bw,bh=cv2.boundingRect(body)
                if bh<max(22,zh*.20) or bw<7 or bw*bh<220 or bw/bh>5:
                    continue
                if bx<=1 or by<=1 or bx+bw>=zw-1 or by+bh>=zh-1:
                    geometry_reasons.append('A card surface touches a calibrated region edge; check crop/scroll and recalibrate.')
                if bh>zh*.99:
                    rejected+=1
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
                recognized_body=False
                for gx,gy,gw,gh in groups:
                    # A corner should have a light surface just above/along it.
                    absolute=[zx+bx+gx,zy+by+gy,gw,gh]
                    if self.surface_profile=='neutral':
                        # A merged row contains rounded seams between cards as
                        # well as its outer border. Do not let a seam read as 7
                        # suppress the actual, taller 2 a few pixels to its right.
                        # An otherwise unreadable body still fails presence/rank
                        # validation below; this does not make cropped cards safe.
                        if gy<=max(2,bh*.03) and gh<bh*.10:
                            border_artifacts.append({'zone':zone,'bbox':absolute,
                                'reason':'small component in the rounded top-edge band'})
                            continue
                        if gy>bh*.09 or gh>bh*.18:
                            non_index.append({'zone':zone,'bbox':absolute,
                                'reason':'outside bounded upright index row; not proof of another card'})
                            continue
                    if gy<=1 and (gx<=1 or gx+gw>=bw-1) and gh<bh*.10:
                        border_artifacts.append({'zone':zone,'bbox':absolute,
                            'reason':'small dark component at rounded surface boundary, not an interior corner glyph'})
                        continue
                    if any(x<=bx+gx+gw/2<=x+w and y<=by+gy+gh/2<=y+h for x,y,w,h in (b['bbox'] for b in backs)):
                        # Back artwork is evidence of presence, not failed face OCR.
                        continue
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
                    recognized_body=True
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
                if not recognized_body and .12<=bw/bh<=.95:
                    covered=any(x<=bx+bw/2<=x+w and y<=by+bh/2<=y+h for x,y,w,h in (b['bbox'] for b in backs))
                    if not covered:
                        bbox=(zx+bx,zy+by,bw,bh)
                        detections.append(CardDetection(None,None,bbox,1.,zone=zone,
                                          score_type='light_surface_geometry_not_probability'))
                        surfaces.append({'zone':zone,'bbox':list(bbox),'visibility':'unreadable',
                                         'provenance':'current-pixel light card surface; rank not read'})
                        rejected+=1
        self.context={'profile':VERSION,'table_bounds':list(boxes['table']),'phase':'unknown',
            'controls':[],'player_totals':{},'reasons':list(dict.fromkeys(geometry_reasons)),
            'provenance':'explicit user regions; current-pixel rank OCR; turn requires confirmation'}
        self.last_diagnostics={'profile':VERSION,'detector_version':VERSION,'input_size':[width,height],
            'regions':{name:list(box) for name,box in boxes.items()},'candidates':candidates,
            'rejected_card_candidates':rejected,'detections':len(detections),
            'presence':surfaces,
            'ignored_surface_border_artifacts':border_artifacts,
            'non_index_proposals':non_index,
            'zone_presence':{zone:('present' if any(d.zone==zone for d in detections) else 'none_observed')
                             for zone in ('dealer','player:0')},
            'surface_profile':self.surface_profile,
            'threshold':self.minimum_score,'score_semantics':'OCR score, not recognition probability',
            'latency_ms':(time.perf_counter()-began)*1000,
            'scope':'explicit card regions, upright corner glyphs and bounded colored backs; no universal presence/rotation guarantee'}
        return sorted(detections,key=lambda d:(d.zone,d.bbox[0]))

    def export_debug(self,directory):
        from PIL import Image
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        for name,pixels in self.debug_images.items():
            if pixels.size:Image.fromarray(pixels).save(directory/(name+'.png'))
