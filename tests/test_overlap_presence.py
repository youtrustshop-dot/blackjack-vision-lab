from dataclasses import replace

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from bjlab.corner_vision import CornerCardDetector
from bjlab.engine import Rules
from bjlab.live import LiveObserver
from bjlab.overlap_presence import patterned_backs
from bjlab.visible_phase import VisiblePhaseContext
from bjlab.vision import CardDetection, TemporalTracker
from validation.tools.stress_lab import LAYOUT, PROFILES, render


def scene(profile='overlap'):
    return render({'phase':'player','cards':[
        {'id':'p1','rank':'6','suit':'H','zone':'player:0'},
        {'id':'p2','rank':'5','suit':'D','zone':'player:0'},
        {'id':'up','rank':'Q','suit':'S','zone':'dealer'},
        {'id':'hole','face_down':True,'zone':'dealer'}]},PROFILES[profile])[0]


@pytest.mark.parametrize('profile',['clean','overlap'])
def test_separate_back_presence_has_no_hidden_rank_and_no_duplicate(profile):
    image=scene(profile)
    raw=CornerCardDetector(LAYOUT).detect(image)
    context=VisiblePhaseContext(LAYOUT,overlap_challenger=True)
    detected,evidence=context.covered_presence(image,raw)
    assert len(detected)==4
    backs=[d for d in detected if d.face_down]
    assert len(backs)==1 and backs[0].rank is None and backs[0].suit is None
    assert context.covered_presence(image,detected)[0]==detected
    assert any(e['covered'] for e in context.back_proposals)


def test_back_evidence_requires_texture_and_rim_not_blue_table_or_plain_card():
    blank=Image.new('RGB',(1024,768),'#075960')
    assert patterned_backs(blank,LAYOUT)[0]==[]
    draw=ImageDraw.Draw(blank)
    draw.rectangle((450,142,561,297),fill='white')
    draw.rectangle((455,147,556,292),fill='#2765a5')
    assert patterned_backs(blank,LAYOUT)[0]==[]
    # Texture without a bright card rim must also abstain.
    draw.rectangle((450,142,561,297),fill='#2765a5')
    for y in range(142,298,7): draw.line((450,y,561,y),fill='#b0c8e0')
    assert patterned_backs(blank,LAYOUT)[0]==[]


def test_readable_disabled_controls_do_not_authorize_a_turn():
    image=scene(); detections=CornerCardDetector(LAYOUT).detect(image)
    context=VisiblePhaseContext(LAYOUT,overlap_challenger=True)
    assert context.read(image,detections)['phase']=='player'
    # Keep the same legible caption pixels; replace only enabled panel borders.
    disabled=image.copy(); draw=ImageDraw.Draw(disabled)
    for x in (250,470):
        draw.rounded_rectangle((x,664,x+200,710),10,outline='#6a6a6a',width=2)
    result=context.read(disabled,detections)
    assert result['phase']=='unknown' and result['controls']==[]
    assert len([p for p in result['control_proposals'] if p['accepted']])==2
    assert 'enabled-style' in result['reasons'][0]
    # Supported panel appearance remains usable at a different position.
    shifted=Image.new('RGB',image.size,'#075960')
    shifted.paste(image.crop((240,660,690,720)),(330,667))
    assert context.read(shifted,detections)['phase']=='player'


def test_overlap_is_opt_in_and_cannot_certify_shoe():
    with pytest.raises(ValueError): LiveObserver(Rules(),layout=LAYOUT,overlap_challenger=True)
    observer=LiveObserver(Rules(),layout=LAYOUT,context_challenger=True,overlap_challenger=True,fresh_shoe=True)
    blank,_=render({'phase':'waiting','cards':[]},PROFILES['overlap'])
    observer.process(blank,0,1); observer.process(blank,1,1.35)
    for i in range(5): result=observer.process(scene(),i+2,1.7+i*.35)
    assert result['advice']['basic_action']=='hit'
    assert not result['count_reliable'] and result['true_count'] is None
    assert len(result['detections'])==4


def test_compressed_overlap_keeps_back_and_enabled_controls(tmp_path):
    video=tmp_path/'overlap.webm'
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'VP80'),12,(1024,768))
    assert writer.isOpened()
    for _ in range(12): writer.write(cv2.cvtColor(np.asarray(scene()),cv2.COLOR_RGB2BGR))
    writer.release(); cap=cv2.VideoCapture(str(video)); ok,pixels=cap.read(); cap.release()
    assert ok
    image=Image.fromarray(cv2.cvtColor(pixels,cv2.COLOR_BGR2RGB))
    context=VisiblePhaseContext(LAYOUT,overlap_challenger=True)
    detections,_=context.covered_presence(image,CornerCardDetector(LAYOUT).detect(image))
    assert sum(d.face_down for d in detections)==1
    assert context.read(image,detections)['phase']=='player'


def test_row_alignment_preserves_upcard_and_hole_through_equal_rank_reveal():
    tracker=TemporalTracker(stable_frames=3,association_mode='ordered_row')
    up=CardDetection('4',None,(439,143,114,154),1.,zone='dealer')
    hole=CardDetection(None,None,(480,143,107,154),1.,face_down=True,zone='dealer')
    for i in range(3): tracker.update([up,hole],i+1,round_id='1')
    identities={t.face_down:t.card_id for t in tracker.tracks.values()}
    # The renderer temporarily shows the single upcard centered.
    tracker.update([replace(up,bbox=(458,143,114,154))],4)
    left=replace(up,bbox=(419,143,114,154))
    right=replace(up,bbox=(458,143,114,154))
    for i in range(3): tracker.update([left,right],5+i)
    assert tracker.tracks[identities[False]].bbox==left.bbox
    assert tracker.tracks[identities[True]].bbox==right.bbox
    revealed=[e for e in tracker.log.events if e.kind=='CARD_REVEALED']
    assert len(revealed)==1 and revealed[0].payload['card_id']==identities[True]
    assert len([e for e in tracker.log.events if e.kind=='CARD_CONFIRMED'])==2
    assert tracker.log.replay().known_rank_counts['4']==2
    assert sum(tracker.log.replay().known_rank_counts.values())==2

