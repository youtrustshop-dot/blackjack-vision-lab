"""Visible suit silhouettes with an explicit low-resolution abstention."""
from functools import lru_cache
import cv2
import numpy as np
from PIL import Image,ImageDraw
from .datasets import card_font


def silhouette(ink):
    yy,xx=np.where(ink)
    if not len(xx):return None
    return cv2.resize(ink[yy.min():yy.max()+1,xx.min():xx.max()+1],(32,32),interpolation=cv2.INTER_NEAREST)>0


@lru_cache(maxsize=1)
def templates():
    result={}
    for suit,symbol in zip('SHDC','♠♥♦♣'):
        result[suit]=[]
        for size in (16,20,24,32,48,64):
            image=Image.new('L',(96,96),255)
            ImageDraw.Draw(image).text((48,48),symbol,font=card_font(size),fill=0,anchor='mm')
            result[suit].append(silhouette(selected_ink((np.asarray(image)<150).astype(np.uint8)*255)))
    return result


def selected_ink(ink):
    contours=cv2.findContours(ink,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]
    if not contours:return np.zeros_like(ink)
    body=max(contours,key=cv2.contourArea)
    x,y,w,h=cv2.boundingRect(body)
    selected=np.zeros_like(ink)
    cv2.drawContours(selected,[body],-1,1,-1)
    # A spade/club stem can be disconnected by font hinting. Preserve it.
    for contour in contours:
        cx,cy,cw,ch=cv2.boundingRect(contour)
        if x<=cx+cw/2<=x+w and y+h*.65<=cy<=y+h*1.3 and cw<=w*.7 and ch<=h*.5 and cv2.contourArea(contour)>=2:
            cv2.drawContours(selected,[contour],-1,1,-1)
    return selected


def read_suit(rgb):
    if not rgb.size:return None
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    ink=(gray<150).astype(np.uint8)*255
    selected=selected_ink(ink)
    yy,xx=np.where(selected)
    if not len(xx) or xx.max()-xx.min()<5 or yy.max()-yy.min()<7 or len(xx)<30:return None
    foreground=rgb[ink>0]
    red=float(np.median(foreground[:,0])-np.median(foreground[:,1]))>40
    options='HD' if red else 'SC'
    observed=silhouette(selected)
    scores=[]
    for suit in options:
        similarity=max(np.logical_and(observed,prototype).sum()/max(1,np.logical_or(observed,prototype).sum()) for prototype in templates()[suit])
        scores.append((similarity,suit))
    scores.sort(reverse=True)
    # Low resolution or artwork outside the template family stays unknown.
    return scores[0][1] if scores[0][0]>=.72 and scores[0][0]-scores[1][0]>=.06 else None
