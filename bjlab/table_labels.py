"""Visible text contract for green tables with side totals and EN/IT buttons."""
import re
import cv2
import numpy as np
from .ocr import read_text

ALIASES = {'CARTA': 'hit', 'HIT': 'hit', 'STAI': 'stand', 'STAND': 'stand',
           'RADDOPPIA': 'double', 'DOUBLE': 'double', 'DIVIDI': 'split', 'SPLIT': 'split'}
NEXT = {'NUOVAMANO', 'NEWHAND', 'RIPETIPUNTATA', 'REPEATBET', 'NEXTROUND'}


def caption(text):
    """Recover a single OCR edit only when it has one possible button meaning."""
    text=re.sub('[^A-Z0-9]','',text.upper())
    text={'RRDDOPPIR':'RADDOPPIA','STA1':'STAI'}.get(text,text)
    if text in ALIASES or text in NEXT or len(text)<3:return text
    candidates=[]
    for word in (*ALIASES,*NEXT):
        previous=list(range(len(word)+1))
        for i,a in enumerate(text,1):
            current=[i]
            for j,b in enumerate(word,1):
                current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(a!=b)))
            previous=current
        if previous[-1]<=1:candidates.append(word)
    meanings={ALIASES.get(word,'next-hand') for word in candidates}
    return candidates[0] if len(meanings)==1 else text


def labels(image, mask, bounds):
    x, y, w, h = bounds
    local = mask[y:y+h, x:x+w]
    joined = cv2.morphologyEx(local, cv2.MORPH_CLOSE, np.ones((3, max(3, w // 45)), np.uint8))
    result = []
    for contour in cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        bx, by, bw, bh = cv2.boundingRect(contour)
        if not (4 <= bh <= h*.07 and 3 <= bw <= w*.65):
            continue
        ink = local[by:by+bh, bx:bx+bw]
        if np.count_nonzero(ink)/ink.size > .72:
            continue
        tile = cv2.copyMakeBorder(255-ink, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=255)
        text, score = read_text(np.repeat(tile[:,:,None], 3, axis=2))
        original=image[y+by:y+by+bh,x+bx:x+bx+bw]
        other,other_score=read_text(cv2.copyMakeBorder(original,3,3,3,3,cv2.BORDER_REPLICATE))
        other=re.sub('[^A-Z0-9]','',other.upper())
        if other_score>=.80 and (other in ALIASES or other in NEXT or other.isdigit()) and other_score>score:
            text,score=other,other_score
        if bx>w*.75 and not text.isdigit():
            digits=[]
            components=sorted([cv2.boundingRect(c) for c in cv2.findContours(ink,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]])
            for dx,dy,dw,dh in components:
                if dh<bh*.65 or dw<2:
                    continue
                part=cv2.copyMakeBorder(255-ink[dy:dy+dh,dx:dx+dw],3,3,3,3,cv2.BORDER_CONSTANT,value=255)
                digit,certainty=read_text(np.repeat(part[:,:,None],3,axis=2))
                if not re.fullmatch(r'\d',digit) or certainty<.80:
                    digits=[];break
                digits.append((digit,certainty))
            if 1<=len(digits)<=2:
                text=''.join(d for d,_ in digits);score=min(s for _,s in digits)
            elif bw/bh>1.1:
                projection=np.count_nonzero(ink,axis=0)
                lo,hi=max(1,int(bw*.25)),min(bw-1,int(bw*.65))
                cut=lo+int(np.argmin(projection[lo:hi]))
                parts=[]
                for part in (ink[:,:cut],ink[:,cut:]):
                    yy,xx=np.where(part)
                    if not len(xx):
                        break
                    part=part[yy.min():yy.max()+1,xx.min():xx.max()+1]
                    padded=cv2.copyMakeBorder(255-part,3,3,3,3,cv2.BORDER_CONSTANT,value=255)
                    digit,certainty=read_text(np.repeat(padded[:,:,None],3,axis=2))
                    if not re.fullmatch(r'\d',digit) or certainty<.80:
                        break
                    parts.append((digit,certainty))
                if len(parts)==2:
                    text=''.join(d for d,_ in parts);score=min(s for _,s in parts)
        if score >= .80:
            result.append((re.sub('[^A-Z0-9]', '', text.upper()), score, (bx,by,bw,bh)))
    return result


def read_side_total_context(rgb, bounds):
    x, y, w, h = bounds
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gold = cv2.inRange(hsv, np.array([12,50,145],np.uint8), np.array([44,255,255],np.uint8))
    tokens = labels(rgb, gold, bounds)
    for contour in cv2.findContours(gold[y:y+h,x:x+w],cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
        bx,by,bw,bh = cv2.boundingRect(contour)
        if not (by > h*.72 and w*.06 < bw < w*.35 and h*.025 < bh < h*.13):
            continue
        if cv2.contourArea(contour) < bw*bh*.65:
            continue
        patch=rgb[y+by+int(bh*.20):y+by+int(bh*.80),x+bx+int(bw*.06):x+bx+int(bw*.94)]
        if patch.size:
            text,score=read_text(patch)
            if score>=.80:
                tokens.append((re.sub('[^A-Z0-9]','',text.upper()),score,
                    (bx+int(bw*.06),by+int(bh*.20),int(bw*.94)-int(bw*.06),int(bh*.80)-int(bh*.20))))
    dark = ((hsv[:,:,2] < 95).astype(np.uint8)*255)
    dark[:y+int(h*.75)] = 0
    tokens += labels(rgb, dark, bounds)
    tokens=[(caption(text),score,box) for text,score,box in tokens]
    known = any(t in ALIASES or t in NEXT or t in ('BANCO','GIOCATORE','DEALER','PLAYER') for t,_,_ in tokens)
    if not known:
        return {}
    controls = []
    caption_colors=cv2.inRange(hsv,np.array([12,50,90],np.uint8),np.array([44,255,255],np.uint8))
    totals = []
    next_hand = False
    for text, score, (bx,by,bw,bh) in tokens:
        if by > h*.72:
            inset=min(4,max(1,bh//6))
            values=hsv[y+by+inset:y+by+bh-inset,x+bx+inset:x+bx+bw-inset,2]
            text_gold=caption_colors[y+by+inset:y+by+bh-inset,x+bx+inset:x+bx+bw-inset]>0
            foreground=values[text_gold]
            # Tiny antialiased captions contain dim edges; inspect the upper quartile.
            bright=bool(foreground.size and np.percentile(foreground,75)>=190)
            if text in ALIASES and bright:
                controls.append(ALIASES[text])
            if text in NEXT:
                next_hand = True
        if bx > w*.75 and h*.40 < by < h*.78 and re.fullmatch(r'\d{1,2}',text) and 2 <= int(text) <= 31:
            totals.append(int(text))
    controls = list(dict.fromkeys(controls))
    phase = 'settled' if next_hand else 'player' if 'hit' in controls and 'stand' in controls else 'waiting'
    return {'profile':'side-total-ocr', 'phase':phase, 'controls':controls,
            'player_totals':{'player:0':list(dict.fromkeys(totals))} if totals else {},
            'messages':[t for t,_,_ in tokens], 'next_hand_visible':next_hand}
