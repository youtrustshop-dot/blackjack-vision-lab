"""Presence is distinct from readability, and never supplies a hidden value."""
import numpy as np
import pytest
from PIL import Image,ImageDraw

from bjlab.corner_vision import colored_backs,CornerCardDetector
from bjlab.vision import CardDetection,TemporalTracker


def test_face_up_unknown_is_not_a_back_and_reveal_keeps_instance():
    tracker=TemporalTracker(stable_frames=1)
    tracker.new_shoe(1)
    unreadable=CardDetection(None,None,(100,100,70,100),1,zone='player:0')
    tracker.update([unreadable],1,'1')
    before=tracker.state_summary()
    cid=next(iter(before['cards']))
    assert before['cards'][cid]['visibility']=='unreadable'
    assert not before['cards'][cid]['face_down']
    tracker.update([CardDetection('A','H',(100,100,70,100),1,zone='player:0')],2,'1')
    after=tracker.state_summary()
    assert len(after['cards'])==1 and after['cards'][cid]['rank']=='A'
    assert after['cards'][cid]['visibility']=='readable'


def test_known_to_unreadable_correction_does_not_claim_face_down():
    tracker=TemporalTracker(stable_frames=1)
    tracker.update([CardDetection('5','S',(100,100,70,100),1,zone='player:0')],1,'1')
    tracker.update([CardDetection(None,None,(100,100,70,100),1,zone='player:0')],2,'1')
    card=next(iter(tracker.state_summary()['cards'].values()))
    assert card['visibility']=='unreadable' and not card['face_down']


def test_visibility_cannot_encode_absence_or_disclose_a_back():
    for kwargs in ({'visibility':'absent'}, {'visibility':'covered'}, {'face_down':True,'visibility':'readable'}):
        with pytest.raises(ValueError):CardDetection(None,None,(1,1,20,30),1,**kwargs)
    assert CardDetection(None,None,(1,1,20,30),1,face_down=True).visibility=='covered'


def patterned_back():
    image=Image.new('RGB',(180,200),'#075344');draw=ImageDraw.Draw(image)
    draw.rectangle((40,25,95,165),fill='white')
    draw.rectangle((44,29,91,161),fill='#386fa8')
    for y in range(33,158,8):
        for x in range(47,89,8):draw.rectangle((x,y,x+2,y+2),fill='white')
    return image


def test_partial_blue_back_presence_and_plain_blue_noncard():
    image=patterned_back()
    assert len(colored_backs(np.asarray(image)))==1
    plain=Image.new('RGB',image.size,'#386fa8')
    assert colored_backs(np.asarray(plain))==[]
    # Visible strip, body occluded: retain presence, never manufacture rank/suit.
    pixels=np.asarray(image).copy();pixels[:,70:]=(7,83,68)
    assert len(colored_backs(pixels))==1


def test_no_rank_and_empty_zone_remain_distinct():
    image=Image.new('RGB',(400,250),'#074939');draw=ImageDraw.Draw(image)
    draw.rectangle((220,40,280,150),fill='white')
    layout={'table':(0,0,1,1),'dealer':(.05,.05,.35,.80),'player:0':(.5,.05,.35,.80)}
    detector=CornerCardDetector(layout);found=detector.detect(image)
    assert len(found)==1 and found[0].visibility=='unreadable'
    assert detector.last_diagnostics['zone_presence']=={'dealer':'none_observed','player:0':'present'}


def test_metrics_do_not_confuse_abstentions_misses_errors_or_unsupported_suits():
    from validation.tools.vision_comparison import recognition_counts
    truth=[{'rank':'A','suit':'H'},{'rank':'5','suit':'D'},{'rank':'2','suit':'C'},
           {'rank':None,'suit':None,'face_down':True}]
    found=[CardDetection('A',None,(0,0,30,50),1),CardDetection('7','C',(50,0,30,50),1),
           CardDetection(None,None,(150,0,30,50),1,face_down=True)]
    pairs=[(0,0),(1,1),(3,2)]
    counts=recognition_counts(truth,found,pairs)
    assert counts['rank']=={'correct':1,'wrong':1,'unknown':0,'missed':1}
    assert counts['suit']=={'correct':0,'wrong':1,'unknown':1,'missed':1}
    assert counts['presence']['covered_correct']==1
    assert recognition_counts(truth,found,pairs,suits_supported=False)['suit'] is None


def test_same_size_crop_can_block_even_with_two_readable_cards():
    from bjlab.datasets import card_font
    from bjlab.live import LiveObserver
    from bjlab.engine import Rules
    image=Image.new('RGB',(720,500),'#243747');draw=ImageDraw.Draw(image)
    for x,y,rank in ((110,45,'6'),(110,285,'7'),(155,285,'2'),(200,285,'A')):
        draw.rounded_rectangle((x,y,x+80,y+110),radius=6,fill='white')
        draw.text((x+6,y+6),rank,font=card_font(22),fill='black',anchor='lt')
    # Keep source dimensions identical; clip the third card with the role ROI.
    layout={'table':(0,0,1,1),'dealer':(.12,.06,.70,.29),'player:0':(.12,.54,.20,.29)}
    observer=LiveObserver(Rules(),layout=layout,manual_turn=True,samples=100)
    for i in range(6):report=observer.process(image,i,1+i*.2)
    assert len(report['player'])>=2
    assert report['advice'] is None and report['count_reliable'] is False
    assert any('region edge' in reason for reason in report['gate']['reasons'])
