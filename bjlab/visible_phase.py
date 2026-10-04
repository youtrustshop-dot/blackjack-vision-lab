"""Opt-in development context challenger: visible controls, never simulator truth.

The calibrated control ROI is required. Scores are raw OCR scores, not phase
probabilities. Missing controls do not imply a player turn or a cleared table.
"""
from collections import Counter
from dataclasses import replace
import re

import cv2
import numpy as np

from .calibration import NormalizedROI
from .ocr import read_text, read_light_text

VERSION = 'visible-controls-temporal-v1'
WORDS = {'HIT':'hit', 'STAND':'stand', 'DOUBLE':'double', 'SPLIT':'split',
         'SURRENDER':'surrender', 'DEAL':'deal', 'NEWHAND':'new_hand',
         'DEALERTURN':'dealer', 'DEALING':'dealing', 'INSURANCE':'insurance'}


class VisiblePhaseContext:
    def __init__(self, layout):
        if 'controls' not in layout:
            raise ValueError('The phase challenger requires a calibrated controls region.')
        self.roi = NormalizedROI(*layout['controls'])
        self.previous_phase = 'unknown'
        self.previous_dealer = ()

    def read(self, image, detections):
        rgb = np.asarray(image.convert('RGB'))
        x,y,w,h = self.roi.to_pixels(image.width,image.height)
        pixels = rgb[y:y+h,x:x+w]
        hsv = cv2.cvtColor(pixels,cv2.COLOR_RGB2HSV)
        ink = ((hsv[:,:,1]<130)&(hsv[:,:,2]>155)).astype(np.uint8)*255
        # Remove panel edges; group neighboring glyphs into text lines.
        _,components,stats,_ = cv2.connectedComponentsWithStats(ink,8)
        ids = [i for i,(_,_,cw,ch,area) in enumerate(stats)
               if i and 4<=ch<=h*.35 and 2<=cw<=w*.25 and area>=5]
        ink = np.isin(components,ids).astype(np.uint8)*255
        joined = cv2.morphologyEx(ink,cv2.MORPH_CLOSE,np.ones((3,21),np.uint8))
        proposals=[]; controls=[]
        for contour in cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
            bx,by,bw,bh=cv2.boundingRect(contour)
            if not (5<=bh<=h*.55 and 8<=bw<=w*.65): continue
            crop=255-ink[by:by+bh,bx:bx+bw]
            crop=cv2.copyMakeBorder(crop,4,4,4,4,cv2.BORDER_CONSTANT,value=255)
            text,score=read_text(np.repeat(crop[:,:,None],3,axis=2))
            if score<.80:
                alternative,alternative_score=read_light_text(pixels[by:by+bh,bx:bx+bw])
                if alternative_score>score: text,score=alternative,alternative_score
            word=re.sub('[^A-Z]','',text.upper())
            accepted=word in WORDS and score>=.80
            proposals.append({'text':text,'score':score,'accepted':accepted,
                              'bbox':[x+bx,y+by,bw,bh]})
            if accepted: controls.append(WORDS[word])
        controls=set(controls)
        player=[d for d in detections if d.zone=='player:0']
        dealer=tuple(d.rank for d in detections if d.zone=='dealer' and d.rank)
        reasons=[]; rule='no unambiguous visible phase signal'; phase='unknown'
        signals=set()
        if {'hit','stand'}<=controls: signals.add('player')
        if 'new_hand' in controls: signals.add('settled')
        if 'dealer' in controls: signals.add('dealer')
        if 'dealing' in controls: signals.add('dealing')
        if 'insurance' in controls: signals.add('unknown')
        if 'deal' in controls and not detections: signals.add('waiting')
        if len(signals)==1:
            phase=next(iter(signals)); rule='current-pixel explicit control text'
        elif len(signals)>1:
            reasons.append('Conflicting visible phase controls.')
        elif self.previous_phase in ('player','dealer') and dealer and dealer!=self.previous_dealer and not ({'hit','stand'}&controls):
            phase='dealer'; rule='dealer face changed after player controls disappeared'
        if phase=='player' and (len(player)<2 or len(dealer)!=1):
            reasons.append('Player controls visible but card presence is incomplete.')
        self.previous_phase=phase
        self.previous_dealer=dealer
        return {'phase':phase,'controls':sorted(controls), 'reasons':reasons,
                'phase_rule':rule,'control_proposals':proposals,
                'turn_provenance':'current-pixel controls; temporal transition',
                'context_version':VERSION}

    def covered_presence(self,image,detections):
        """Classify only existing unknown bodies, not ranks or new card objects.

        Blue patterned body plus bright rim is positive current-pixel evidence.
        Unknown bodies without this evidence retain the original blocking gate.
        The default rank detector and its raw diagnostics remain unchanged.
        """
        rgb=np.asarray(image.convert('RGB')); result=[]; evidence=[]
        for d in detections:
            if d.rank is not None or d.face_down:
                result.append(d); continue
            x,y,w,h=map(round,d.bbox); pixels=rgb[max(0,y):y+h,max(0,x):x+w]
            if pixels.size==0 or not .12<=w/h<=.85 or min(w,h)<20:
                result.append(d); continue
            hsv=cv2.cvtColor(pixels,cv2.COLOR_RGB2HSV)
            blue=(hsv[:,:,0]>=90)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>70)&(hsv[:,:,2]>70)
            bright=(hsv[:,:,1]<70)&(hsv[:,:,2]>175)
            rim=bright.copy(); rim[3:-3,3:-3]=False
            interior=hsv[6:-6,6:-6]
            values=interior[:,:,2].astype(float) if interior.size else np.zeros((1,1))
            texture_range=float(np.percentile(values,90)-np.percentile(values,10))
            stripe_variation=float(values.mean(axis=1).std())
            rim_fraction=rim.sum()/max(1,bright.size-(max(0,h-6)*max(0,w-6)))
            accepted=blue.mean()>.45 and texture_range>35 and stripe_variation>8 and rim_fraction>.30
            evidence.append({'bbox':list(d.bbox),'zone':d.zone,'covered':bool(accepted),
                'blue_fraction':float(blue.mean()),'texture_range':texture_range,'stripe_variation':stripe_variation,
                'rim_fraction':float(rim_fraction),'provenance':'current pixels; bounded patterned-back context rule'})
            result.append(replace(d,face_down=True,visibility='covered') if accepted else d)
        return result,evidence


class VisibleRoundLifecycle:
    """Witness clear before a deal; card stability and event stability run together.

Unlike the baseline's serial lifecycle/tracker waits, a witnessed new deal
opens identity once, then lets the unchanged tracker confirm its observations.
Unwitnessed replacement remains ambiguous and cannot manufacture a new round.
"""
    def __init__(self):
        self.required=3; self.hits=0; self.candidate=None
        self.empty_hits=0; self.seen_round=False; self.round_open=False
        self.clear_witnessed=False; self.ambiguous_boundary=False
        self.previous=None

    def observe(self,detections,phase,*,clear_evidence=False):
        player=tuple(d.rank for d in detections if d.zone=='player:0' and d.rank)
        dealer=tuple(d.rank for d in detections if d.zone=='dealer' and d.rank)
        token=(player,dealer,phase,tuple((d.zone,d.face_down,d.rank) for d in detections))
        self.hits=self.hits+1 if token==self.candidate else 1
        self.candidate=token
        self.empty_hits=self.empty_hits+1 if clear_evidence and not detections else 0
        result={'stable':self.hits>=self.required,'new_round':False,'round_ended':False,
                'history_gap':False,'ambiguous_boundary':self.ambiguous_boundary,
                'commit_allowed':self.round_open and not self.ambiguous_boundary}
        if self.empty_hits>=2:
            result['round_ended']=self.round_open
            self.round_open=False; self.clear_witnessed=True
            self.ambiguous_boundary=False; self.previous=None
            result.update(commit_allowed=False,ambiguous_boundary=False)
        elif detections and self.clear_witnessed:
            self.clear_witnessed=False; self.round_open=True; self.seen_round=True
            result.update(new_round=True,commit_allowed=True)
        elif detections and not self.seen_round and phase in ('player','settled'):
            # Joining a visible hand permits advice, but does not repair history.
            self.round_open=True; self.seen_round=True
            result.update(new_round=True,history_gap=True,commit_allowed=True)
        elif self.previous and self.hits>=self.required and phase in ('player','unknown','dealing'):
            old_player,old_dealer=self.previous
            if (phase=='player' and old_dealer and dealer!=old_dealer) or bool(Counter(old_player)-Counter(player)):
                self.ambiguous_boundary=True
                result.update(history_gap=True,ambiguous_boundary=True,commit_allowed=False)
        if result['stable'] and phase in ('player','dealer','settled') and not self.ambiguous_boundary:
            self.previous=(player,dealer)
        return result
