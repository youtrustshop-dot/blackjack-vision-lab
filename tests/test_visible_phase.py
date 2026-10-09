from PIL import Image, ImageDraw
import pytest

from bjlab.engine import Rules
from bjlab.live import LiveObserver
from bjlab.visible_phase import VisiblePhaseContext, VisibleRoundLifecycle
from bjlab.vision import CardDetection
from validation.tools.stress_lab import LAYOUT, PROFILES, render


def cards(player=('6','5'),dealer=('Q',)):
    return [CardDetection(r,None,(100+i*120,440,112,156),1.,zone='player:0') for i,r in enumerate(player)]+[
        CardDetection(r,None,(100+i*120,142,112,156),1.,zone='dealer') for i,r in enumerate(dealer)]


def test_visible_controls_and_missing_controls_never_use_phase_as_input():
    context=VisiblePhaseContext(LAYOUT)
    image,_=render({'phase':'player','cards':[]},PROFILES['clean'])
    result=context.read(image,cards())
    assert result['phase']=='player' and {'hit','stand'}<=set(result['controls'])
    assert context.read(Image.new('RGB',image.size,'#125e42'),cards())['phase']=='unknown'
    # Presence alone, including a perfect player hand, cannot establish a turn.
    assert context.read(Image.new('RGB',image.size,'#125e42'),cards())['controls']==[]


def test_contradictory_controls_and_unknown_back_remain_blocking():
    context=VisiblePhaseContext(LAYOUT)
    player,_=render({'phase':'player','cards':[]},PROFILES['clean'])
    settled,_=render({'phase':'settled','cards':[]},PROFILES['clean'])
    player.paste(settled.crop((250,664,450,711)),(250,720))
    # Test the explicit signal conflict without relying on OCR failure.
    from unittest.mock import patch
    with patch('bjlab.visible_phase.read_text',side_effect=[('NEW HAND',.99),('STAND',.99),('HIT',.99)]):
        # Three separated captions inside the ROI.
        img=Image.new('RGB',(1024,768),'#125e42'); draw=ImageDraw.Draw(img)
        from bjlab.datasets import card_font
        for x,word in ((100,'NEW HAND'),(430,'STAND'),(730,'HIT')):
            draw.text((x,674),word,font=card_font(22),fill='white')
        assert context.read(img,cards())['reasons']==['Conflicting visible phase controls.']
    unknown=CardDetection(None,None,(450,142,112,156),1.,zone='dealer')
    blank=Image.new('RGB',(1024,768),'#125e42'); ImageDraw.Draw(blank).rectangle((450,142,561,297),fill='white')
    converted,evidence=context.covered_presence(blank,[unknown])
    assert converted==[unknown] and not evidence[0]['covered']
    ImageDraw.Draw(blank).rectangle((456,148,555,291),fill='#2765a5')
    converted,evidence=context.covered_presence(blank,[unknown])
    assert converted==[unknown] and not evidence[0]['covered']  # plain blue is not a patterned back


def test_witnessed_clear_allows_identical_new_round_without_serial_confirmation():
    life=VisibleRoundLifecycle()
    assert not life.observe([],'waiting',clear_evidence=True)['new_round']
    life.observe([],'waiting',clear_evidence=True)
    start=life.observe(cards(),'dealing')
    assert start['new_round'] and start['commit_allowed'] and not start['stable']
    for _ in range(3): stable=life.observe(cards(),'player')
    assert stable['stable'] and not stable['new_round']
    life.observe([],'waiting',clear_evidence=True)
    assert life.observe([],'waiting',clear_evidence=True)['round_ended']
    assert life.observe(cards(),'dealing')['new_round']


def test_disappearing_cards_without_clear_signal_does_not_certify_boundary():
    life=VisibleRoundLifecycle()
    for _ in range(3): life.observe(cards(),'player')
    for _ in range(4): result=life.observe([],'unknown',clear_evidence=False)
    assert not result['round_ended']
    for _ in range(3): result=life.observe(cards(('9','8'),('7',)),'player')
    assert result['ambiguous_boundary'] and result['history_gap'] and not result['commit_allowed']


def test_challenger_is_opt_in_pixel_only_and_keeps_shoe_uncertified():
    stage={'phase':'player','cards':[{'id':'a','rank':'6','suit':'H','zone':'player:0'},
        {'id':'b','rank':'5','suit':'D','zone':'player:0'},
        {'id':'c','rank':'Q','suit':'S','zone':'dealer'},
        {'id':'d','face_down':True,'zone':'dealer'}]}
    image,_=render(stage,PROFILES['clean'])
    baseline=LiveObserver(Rules(),layout=LAYOUT)
    challenger=LiveObserver(Rules(),layout=LAYOUT,context_challenger=True,fresh_shoe=True)
    blank,_=render({'phase':'waiting','cards':[]},PROFILES['clean'])
    challenger.process(blank,0,1); challenger.process(blank,1,1.35)
    for i in range(5): result=challenger.process(image,i+2,1.7+i*.35)
    assert result['phase']=='player'
    assert result['advice'] and result['advice']['basic_action']=='hit'
    assert not result['count_reliable'] and result['true_count'] is None
    assert baseline.process(image,0,1)['phase']=='unknown'
    assert any(d['face_down'] for d in result['detections'])
    unknown=CardDetection(None,None,(516,142,112,156),1.,zone='dealer')
    recovered,evidence=VisiblePhaseContext(LAYOUT).covered_presence(image,[unknown])
    assert recovered[0].face_down and evidence[0]['covered']
    # Obscuring the control band invalidates advice immediately; cached earlier
    # controls must not extend a turn or retain a stale recommendation.
    obscured=image.copy(); ImageDraw.Draw(obscured).rectangle((0,650,1024,768),fill='#125e42')
    after=challenger.process(obscured,7,4.0)
    assert after['advice'] is None and not after['gate']['solver_allowed']
    with pytest.raises(ValueError): LiveObserver(Rules(),context_challenger=True)
    with pytest.raises(ValueError): LiveObserver(Rules(),layout=LAYOUT,context_challenger=True,manual_turn=True)
