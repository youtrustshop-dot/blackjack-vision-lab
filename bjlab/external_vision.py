"""Pixel-only recognition for a classic green casino table and printed ranks.

Find the largest table in a shared window, read upper card corners independently
of font and ASCII suit labels, and use visible turn text/controls. Repeated small
previews outside that table do not become extra hands or counted cards.
"""
import re
import time

import cv2
import numpy as np

from .engine import hand_value
from .ocr import read_light_text, read_text
from .vision import CardDetection, TemplateCardDetector, _rgb

OCR_RANK_MIN_SCORE = .80


def integrity_reasons(context, detections):
    reasons = []
    totals_by_zone = context.get('player_totals', {})
    if context.get('phase') == 'player' and not totals_by_zone:
        reasons.append('The player total could not be verified. Enlarge the shared game window.')
    for zone, totals in totals_by_zone.items():
        ranks = [d.rank for d in detections if d.zone == zone and d.rank and not d.face_down]
        if not ranks or hand_value(ranks)[0] not in totals:
            reasons.append('The recognized cards do not match the visible hand total. Enlarge or recalibrate the table.')
    if context.get('active_hand_ambiguous'):
        reasons.append('Several player hands are visible. Confirm the active hand manually.')
    if context.get('phase') == 'player' and any(d.face_down for d in detections if d.zone.startswith('player')):
        reasons.append('A player card is face down or unreadable.')
    return reasons


def _contours(mask):
    return cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]


class ClassicCasinoDetector:
    def __init__(self):
        self.last_diagnostics = {}
        self.context = {}

    def detect(self, image):
        started = time.perf_counter()
        self.debug_images={}
        rgb = _rgb(image)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        green = cv2.inRange(hsv, np.array([35, 70, 25], np.uint8), np.array([95, 255, 240], np.uint8))
        kernel = max(3, min(15, rgb.shape[1] // 200)) | 1
        green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((kernel, kernel), np.uint8))
        self.debug_images['table-mask']=green
        fields = sorted(_contours(green), key=cv2.contourArea, reverse=True)
        fields = [c for c in fields if cv2.contourArea(c) > rgb.shape[0]*rgb.shape[1]*.035]
        self.context = {}
        self.last_diagnostics = {"rejected_card_candidates": 0, "detections": 0,
                                 "profile": "classic-casino-ocr", "scope": "printed ranks on a classic green table"}
        if not fields:
            self.last_diagnostics['localization_rejection']='No sufficiently large compatible green surface.'
            return []
        x, y, w, h = cv2.boundingRect(fields[0])
        if w < 180 or h < 100 or not 1.1 < w/h < 4:
            self.last_diagnostics['localization_rejection']='Largest green surface violates baseline size/aspect limits.'
            self.last_diagnostics['rejected_table_bounds']=[x,y,w,h]
            return []
        self.context = {"table_bounds": [x, y, w, h], "profile": "classic-casino-ocr",
                        "phase": "waiting", "controls": [], "player_totals": {}}
        # Color/geometry supplies candidate bodies; OCR supplies the ranks.
        white = cv2.inRange(hsv, np.array([0, 0, 165], np.uint8), np.array([179, 95, 255], np.uint8))
        white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        opening = max(3, min(11, w // 150)) | 1
        white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((opening, opening), np.uint8))
        marks, bodies = [], []
        for contour in _contours(white):
            bx, by, bw, bh = cv2.boundingRect(contour)
            if not (x+w*.12 < bx < x+w*.78 and y <= by < y+h*.82 and
                    h*.10 < bh < h*.42 and .3 < bw/bh < 5.5):
                continue
            # Ignore the chips/deck stack. Ink must sit on a bright card background.
            if by < y+h*.30:
                zone = "dealer"
            elif by > y+h*.40:
                zone = "player:0"
            else:
                continue
            bodies.append((bx, by, bw, bh, zone))
            top_height = max(14, round(bh*.30))
            local = rgb[by:by+top_height, bx:bx+bw]
            ink = (cv2.cvtColor(local, cv2.COLOR_RGB2GRAY) < 130).astype(np.uint8)*255
            boxes = []
            for cc in _contours(ink):
                ix, iy, iw, ih = cv2.boundingRect(cc)
                if max(5, bh*.045) <= ih <= bh*.23 and 2 <= iw <= bh*.25 and 1 <= iy <= bh*.16:
                    boxes.append((ix, iy, iw, ih))
            boxes.sort()
            groups = []
            for box in boxes:
                ix, iy, iw, ih = box
                if groups:
                    gx, gy, gw, gh = groups[-1]
                    if 0 <= ix-(gx+gw) <= max(2, ih*.35) and abs((iy+ih)-(gy+gh)) <= max(2, ih*.25):
                        top = min(gy, iy)
                        groups[-1] = (gx, top, ix+iw-gx, max(gy+gh, iy+ih)-top)
                        continue
                groups.append(box)
            for ix, iy, iw, ih in groups:
                crop = local[max(0,iy-2):min(top_height,iy+ih+2), max(0,ix-2):ix+iw+2]
                key='rank-'+str(len(self.last_diagnostics.setdefault('rank_candidates',[])))
                self.debug_images[key]=crop.copy()
                text, score = read_text(crop)
                rank = text.strip().upper()
                vocabulary=("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
                if rank not in vocabulary or score < OCR_RANK_MIN_SCORE:
                    # A tightly cropped single glyph can lose OCR confidence.
                    # Restore a white margin without lowering the acceptance
                    # threshold or changing the rank vocabulary.
                    padded=cv2.copyMakeBorder(crop,4,4,4,4,cv2.BORDER_CONSTANT,value=(255,255,255))
                    self.debug_images[key+'-retry']=padded.copy()
                    retry,retry_score=read_text(padded)
                    retry=retry.strip().upper()
                    if rank not in vocabulary or retry==rank:
                        rank,score=retry,retry_score
                # A generic text model scores narrow printed letters (notably J)
                # below long words. The rank vocabulary, independent total check
                # and temporal stability are additional integrity requirements.
                self.last_diagnostics['rank_candidates'].append({'zone':zone,'body_bbox':[bx,by,bw,bh],
                    'rank_bbox':[bx+ix,by+iy,iw,ih],'raw_token':text,'selected_rank':rank,'score':score,
                    'threshold':OCR_RANK_MIN_SCORE,'accepted':rank in vocabulary and score>=OCR_RANK_MIN_SCORE,'crop':key+'.png'})
                if rank not in vocabulary or score < OCR_RANK_MIN_SCORE:
                    self.last_diagnostics['rejected_card_candidates']+=1
                    continue
                # Locate a card from its upper corner, including overlapped bodies.
                left = max(bx, bx+ix-round(bh*.05))
                box = (left, by, min(round(bh*.80), rgb.shape[1]-left), bh)
                if all(abs(left-d.bbox[0]) > bh*.20 or zone != d.zone for d in marks):
                    from .suit_symbols import read_suit
                    sy=by+iy+ih+max(2,round(bh*.015))
                    sx=max(0,bx+ix-round(bh*.035))
                    symbol=rgb[sy:sy+round(bh*.18),sx:sx+round(bh*.23)]
                    marks.append(CardDetection(rank, read_suit(symbol), box, score, zone=zone, score_type="ocr_token_score"))

        # A patterned card back is a physical exposure with unknown rank.
        # It changes the draw-pile size, but never the Hi-Lo running count.
        red=cv2.inRange(hsv,np.array([0,100,100],np.uint8),np.array([9,255,255],np.uint8)) | cv2.inRange(hsv,np.array([170,100,100],np.uint8),np.array([179,255,255],np.uint8))
        red=cv2.morphologyEx(red,cv2.MORPH_CLOSE,np.ones((max(3,w//150)|1,max(3,w//150)|1),np.uint8))
        for contour in _contours(red):
            bx,by,bw,bh=cv2.boundingRect(contour)
            if not (x+w*.12<bx<x+w*.78 and y<=by<y+h*.82 and h*.10<bh<h*.42 and .4<bw/bh<.9):
                continue
            if cv2.contourArea(contour)<bw*bh*.65:
                continue
            zone='dealer' if by<y+h*.30 else 'player:0' if by>y+h*.40 else None
            if zone:
                marks=[d for d in marks if not (bx<=d.bbox[0]<bx+bw and d.zone==zone)]
                marks.append(CardDetection(None,None,(bx,by,bw,bh),1.,face_down=True,zone=zone,score_type='visible_card_back'))

        # Visible dark-blue message and total badges belong to this table only.
        blue = cv2.inRange(hsv, np.array([90,50,20],np.uint8), np.array([135,255,210],np.uint8))
        badges = []
        messages = []
        for c in _contours(blue):
            bx, by, bw, bh = cv2.boundingRect(c)
            if not (x <= bx <= x+w and y <= by <= y+h and w*.08 < bw < w*.35 and h*.02 < bh < h*.20):
                continue
            inset = max(2, round(bh*.10))
            patch = rgb[by+inset:by+bh-inset, bx+inset:bx+bw-inset]
            if not patch.size:
                continue
            if bx > x+w*.60 and by < y+h*.20:
                hh = cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
                light = (hh[:,:,1]<115)&(hh[:,:,2]>160)
                occupied = light.sum(1) > 3
                starts = np.where(np.r_[occupied[0], occupied[1:] & ~occupied[:-1]])[0]
                ends = np.where(np.r_[occupied[:-1] & ~occupied[1:], occupied[-1]])[0]+1
                for top, bottom in zip(starts, ends):
                    if bottom-top < 4:
                        continue
                    text, score = read_light_text(patch[max(0,top-2):bottom+2])
                    if score >= .85:
                        messages.append(text.lower())
            elif bw/bh > 3:
                text, score = read_light_text(patch)
                if score >= .90 and re.fullmatch(r"\d{1,2}(?:\s*[/,]\s*\d{1,2})?",text):
                    badges.append((bx,by,bw,bh,[int(t) for t in re.findall(r"\d+",text)]))

        player_badges = sorted((b for b in badges if b[1] > y+h*.35), key=lambda b:b[0])
        if len(player_badges) > 1:
            assigned=[]
            for d in marks:
                if d.zone.startswith("player"):
                    nearest=min(range(len(player_badges)),key=lambda i:abs(d.bbox[0]+d.bbox[2]/2-(player_badges[i][0]+player_badges[i][2]/2)))
                    d=CardDetection(d.rank,d.suit,d.bbox,d.score,zone=f"player:{nearest}",score_type=d.score_type)
                assigned.append(d)
            marks=assigned
            self.context["active_hand_ambiguous"] = True
        for i, b in enumerate(player_badges):
            self.context["player_totals"][f"player:{i}"] = b[4]

        # Enabled green control buttons: read their captions, never infer from a total.
        controls=[]
        for c in _contours(green):
            bx,by,bw,bh=cv2.boundingRect(c)
            if not (y+h*.95 <= by < y+h*1.40 and x+w*.15 < bx < x+w*.80 and
                    w*.025 < bw < w*.13 and .55 < bw/bh < 1.60):
                continue
            # Long labels such as DOUBLE can extend beyond the circular icon.
            # Preserve their complete strokes instead of clipping the final E.
            px=max(x,bx-round(bw*.08)); pw=round(bw*1.16)
            patch=rgb[min(rgb.shape[0],by+bh):min(rgb.shape[0],by+bh+round(bh*.60)), px:min(x+w,px+pw)]
            if patch.size:
                hh=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
                occupied=((hh[:,:,1]<115)&(hh[:,:,2]>160)).sum(1)>3
                starts=np.where(np.r_[occupied[0],occupied[1:]&~occupied[:-1]])[0]
                ends=np.where(np.r_[occupied[:-1]&~occupied[1:],occupied[-1]])[0]+1
                for top,bottom in zip(starts,ends):
                    if not 4<=bottom-top<=bh*.30:
                        continue
                    text,score=read_light_text(patch[max(0,top-2):bottom+2])
                    action=re.sub(r'[^a-z_]','',text.lower())
                    if action in ('hit','stand','double','split','surrender','insurance','decline') and score>=.75:
                        controls.append('decline_insurance' if action=='decline' else action)
        self.context["controls"]=list(dict.fromkeys(controls))
        self.context["messages"]=messages
        if any(any(word in t for word in ('win','lose','lost','push','bust','draw','blackjack')) for t in messages):
            self.context["phase"]="settled"
        elif any('your turn' in t for t in messages) or ('hit' in controls and 'stand' in controls):
            self.context["phase"]="player"

        from .table_labels import read_side_total_context
        side_context = read_side_total_context(rgb, (x,y,w,h))
        if side_context:
            self.context.update(side_context)
            self.last_diagnostics['profile'] = side_context['profile']

        # Totals are independent visible evidence: a missed card must not yield advice.
        reasons=integrity_reasons(self.context, marks)
        if len([d for d in marks if d.zone == 'dealer']) == 0 and any(b[4] == 'dealer' for b in bodies):
            reasons.append("The dealer upcard could not be read. Enlarge the shared game window.")
        self.context["reasons"]=reasons
        self.last_diagnostics.update(detections=len(marks), latency_ms=(time.perf_counter()-started)*1000,
            score_semantics="OCR token scores, not calibrated correctness probabilities", table_found=True)
        return sorted(marks,key=lambda d:(d.bbox[1],d.bbox[0]))


class AdaptiveCardDetector:
    """Keep the validated lab path and add a separately reported external path."""
    def __init__(self, **kwargs):
        self.lab=TemplateCardDetector(**kwargs)
        self.classic=ClassicCasinoDetector()
        self.last_diagnostics={}
        self.context={}

    def detect(self,image):
        self.debug_images={}
        lab=self.lab.detect(image)
        rgb=_rgb(image)
        scale=2 if rgb.shape[1]<800 else 1
        external=self.classic.detect(cv2.resize(rgb,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC) if scale!=1 else image)
        if scale!=1:
            external=[CardDetection(d.rank,d.suit,tuple(v/scale for v in d.bbox),d.score,
                face_down=d.face_down,zone=d.zone,score_type=d.score_type) for d in external]
            if self.classic.context.get('table_bounds'):
                self.classic.context['table_bounds']=[round(v/scale) for v in self.classic.context['table_bounds']]
                from .table_labels import read_side_total_context
                native_context=read_side_total_context(rgb,self.classic.context['table_bounds'])
                if native_context:
                    self.classic.context.update(native_context)
                    self.classic.context['reasons']=integrity_reasons(self.classic.context, external)
        strong_lab=[d for d in lab if d.rank and d.score>=.90]
        # A small lab preview must not hide a larger external table in a desktop share.
        bounds=self.classic.context.get('table_bounds')
        lab_is_main=not bounds or np.median([d.bbox[3] for d in strong_lab] or [0]) >= bounds[3]*.10
        if len(strong_lab)>=3 and lab_is_main:
            self.context={}
            self.last_diagnostics=self.lab.last_diagnostics
            return lab
        if self.classic.context:
            self.debug_images=self.classic.debug_images
            self.context=self.classic.context
            self.last_diagnostics=self.classic.last_diagnostics
            self.last_diagnostics['analysis_scale']=scale
            return external
        self.context={}
        self.last_diagnostics=self.lab.last_diagnostics
        self.last_diagnostics['classic_attempt']=self.classic.last_diagnostics
        self.debug_images=self.classic.debug_images
        return lab
