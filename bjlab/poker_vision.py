"""Calibrated Hold'em card regions. No hidden-card or betting-policy inference."""
import cv2
import numpy as np
from .vision import CardDetection,TemplateCardDetector,_rgb
from .ocr import read_text
from .suit_symbols import read_suit
from .clef_contract import RANKS


def read_region(image,roi,zone):
    rgb=_rgb(image);height,width=rgb.shape[:2]
    if len(roi)!=4 or any(type(v) not in (int,float) or not np.isfinite(v) for v in roi):
        raise ValueError('A card region needs four finite normalized values: x, y, width, height.')
    x,y,w,h=roi
    if min(x,y)<0 or min(w,h)<=0 or x+w>1 or y+h>1:raise ValueError('Card region is outside the image.')
    x,y,w,h=round(x*width),round(y*height),round(w*width),round(h*height)
    if min(w,h)<20:raise ValueError('Enlarge the card region to at least 20 pixels in each direction.')
    patch=rgb[y:y+h,x:x+w]
    detector=TemplateCardDetector()
    observations=detector.detect(patch)
    lab=[d for d in observations if d.rank and d.suit and d.score>=.90]
    if lab:
        reasons=['Some card-shaped regions are unreadable or face down.'] if len(lab)!=len(observations) or detector.last_diagnostics['rejected_card_candidates'] else []
        return [CardDetection(d.rank,d.suit,(x+d.bbox[0],y+d.bbox[1],d.bbox[2],d.bbox[3]),d.score,zone=zone) for d in lab],reasons
    hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
    white=cv2.inRange(hsv,np.array([0,0,165],np.uint8),np.array([179,95,255],np.uint8))
    white=cv2.morphologyEx(white,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    white=cv2.morphologyEx(white,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    result=[];reasons=[]
    for c in cv2.findContours(white,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
        bx,by,bw,bh=cv2.boundingRect(c)
        if bh<30 or bw<bh*.25 or bw>bh*8 or cv2.contourArea(c)<bw*bh*.60:continue
        top=patch[by:by+round(bh*.30),bx:bx+bw]
        ink=(cv2.cvtColor(top,cv2.COLOR_RGB2GRAY)<130).astype(np.uint8)*255
        glyphs=sorted([cv2.boundingRect(c) for c in cv2.findContours(ink,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]])
        groups=[]
        for ix,iy,iw,ih in glyphs:
            if not (max(5,bh*.045)<=ih<=bh*.23 and 2<=iw<=bh*.25 and 1<=iy<=bh*.16):continue
            if groups and 0<=ix-groups[-1][0]-groups[-1][2]<=max(2,ih*.35) and abs(iy+ih-groups[-1][1]-groups[-1][3])<=max(2,ih*.25):
                gx,gy,gw,gh=groups[-1];ny=min(iy,gy);groups[-1]=(gx,ny,ix+iw-gx,max(iy+ih,gy+gh)-ny)
            else:groups.append((ix,iy,iw,ih))
        if not groups:reasons.append('A card body has no readable printed corner.')
        for ix,iy,iw,ih in groups:
            tile=top[max(0,iy-2):iy+ih+2,max(0,ix-2):ix+iw+2];rank,score=read_text(tile)
            if rank not in RANKS or score<.80:
                reasons.append('A printed card rank is unreadable.');continue
            sy=by+iy+ih+max(2,round(bh*.015));sx=max(0,bx+ix-round(bh*.035))
            suit=read_suit(patch[sy:sy+round(bh*.18),sx:sx+round(bh*.23)])
            if not suit:reasons.append('A suit is unreadable. Enlarge the table or confirm the card.')
            left=bx+ix-round(bh*.05)
            result.append(CardDetection(rank,suit,(x+left,y+by,round(bh*.7),bh),score,zone=zone,score_type='ocr_token_score'))
    return sorted(result,key=lambda d:d.bbox[0]),list(dict.fromkeys(reasons))


def inspect(image,hole_roi,board_roi):
    hole,hole_reasons=read_region(image,hole_roi,'hole')
    board,board_reasons=read_region(image,board_roi,'board')
    reasons=hole_reasons+board_reasons
    if len(hole)!=2:reasons.append('Exactly two readable hole cards are required.')
    if len(board) not in (0,3,4,5):reasons.append('The board must contain zero, three, four or five cards.')
    all_cards=hole+board
    known=[d.rank.replace('10','T')+d.suit for d in all_cards if d.rank and d.suit]
    if len(set(known))!=len(known):reasons.append('A physical card appears in more than one position. Recalibrate the regions.')
    return {'source':'calibrated-poker-pixels','hole':[d.rank.replace('10','T')+(d.suit or '?') for d in hole],
        'board':[d.rank.replace('10','T')+(d.suit or '?') for d in board],
        'detections':[d.to_dict() for d in all_cards],'gate':{'solver_allowed':not reasons,'reasons':list(dict.fromkeys(reasons))},
        'scope':'Experimental calibrated hole/board regions. Empty board must be confirmed as preflop. No pot, turn, opponent cards or optimal action is inferred.'}
