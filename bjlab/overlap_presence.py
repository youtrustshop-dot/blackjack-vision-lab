"""Research-only upright patterned blue backs in explicit card regions.

Rank reading is untouched. A merged white row is not a single card: separate
blue patterned interiors with bright rims can establish covered-card presence.
No hidden rank, simulator label or temporal card identity enters this rule.
"""
import cv2
import numpy as np

from .calibration import NormalizedROI
from .vision import CardDetection


def patterned_backs(image, layout):
    rgb=np.asarray(image.convert('RGB')); found=[]; evidence=[]
    for zone in ('dealer','player:0'):
        x,y,w,h=NormalizedROI(*layout[zone]).to_pixels(image.width,image.height)
        pixels=rgb[y:y+h,x:x+w]; hsv=cv2.cvtColor(pixels,cv2.COLOR_RGB2HSV)
        blue=((hsv[:,:,0]>=90)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>70)&(hsv[:,:,2]>115)).astype(np.uint8)*255
        joined=cv2.morphologyEx(blue,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
        for contour in cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
            bx,by,bw,bh=cv2.boundingRect(contour)
            if not (max(40,h*.45)<=bh<h*.96 and 8<=bw and .10<=bw/bh<=.85): continue
            rims=[]
            # Compression can spread chroma onto the rim. Check the bounded
            # 0..5 pixel band rather than assume a fixed six-pixel white gap.
            for pad in range(6):
                a,b,c,d=max(0,bx-pad),max(0,by-pad),min(w,bx+bw+pad),min(h,by+bh+pad)
                patch=hsv[b:d,a:c]; bright=(patch[:,:,1]<70)&(patch[:,:,2]>175)
                rim=bright.copy(); rim[3:-3,3:-3]=False
                rims.append((float(rim.sum()/max(1,bright.size-max(0,d-b-6)*max(0,c-a-6))),a,b,c,d))
            rim_fraction,a,b,c,d=max(rims)
            values=hsv[by:by+bh,bx:bx+bw,2].astype(float)
            texture_range=float(np.percentile(values,90)-np.percentile(values,10))
            variation=float(values.std())
            blue_fraction=float((blue[by:by+bh,bx:bx+bw]>0).mean())
            accepted=rim_fraction>.30 and texture_range>35 and variation>8 and blue_fraction>.40
            bbox=(x+a,y+b,c-a,d-b)
            evidence.append({'zone':zone,'bbox':list(bbox),'covered':accepted,
                'rim_fraction':rim_fraction,'texture_range':texture_range,
                'pixel_variation':variation,'blue_fraction':blue_fraction,
                'provenance':'current pixels; separate patterned blue surface with bright rim'})
            if accepted:
                found.append(CardDetection(None,None,bbox,1.,face_down=True,zone=zone,
                    score_type='bounded_patterned_back_presence_not_probability'))
    return found,evidence
