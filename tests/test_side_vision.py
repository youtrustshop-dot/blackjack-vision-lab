import pytest
from bjlab.external_vision import AdaptiveCardDetector
from bjlab.live import LiveObserver
from bjlab.engine import Rules
from bjlab.table_labels import caption
from side_fixture import side_table


@pytest.mark.parametrize('rank',('A','2','3','4','5','6','7','8','9','10','J','Q','K'))
def test_every_printed_rank_survives_overlap(rank):
    detector=AdaptiveCardDetector();found=detector.detect(side_table((rank,'5')))
    assert [d.rank for d in found if d.zone=='player:0' and d.rank]==[rank,'5']
    assert not detector.context['reasons']


@pytest.mark.parametrize('player,locale,scale',[
 (('A','5'),'it',1),(('9','8'),'en',1),(('5','3','3','K'),'it',1),
 (('A','7'),'en',.65),(('A','5'),'it',.5)])
def test_overlapping_printed_cards_side_totals_and_enabled_controls(player,locale,scale):
    detector=AdaptiveCardDetector();found=detector.detect(side_table(player,locale=locale,scale=scale))
    assert [d.rank for d in found if d.zone=='player:0' and d.rank]==list(player)
    assert detector.context['phase']=='player'
    assert set(detector.context['controls'])=={'hit','stand'}
    assert not detector.context['reasons']


def test_missed_card_total_and_intervening_animation_never_create_guidance():
    observer=LiveObserver(Rules(decks=4,surrender='none'),samples=100)
    image=side_table(('A','5'),total=19)
    for i in range(6):report=observer.process(image,i,i+1.)
    assert report['advice'] is None
    assert any('total' in reason for reason in report['gate']['reasons'])


def test_repeated_identical_deals_and_revealed_back_are_counted_once():
    observer=LiveObserver(Rules(decks=4,surrender='none'),samples=100)
    sequence=0
    def observe(image):
        nonlocal sequence
        for _ in range(6):report=observer.process(image,sequence,sequence+1.);sequence+=1
        return report
    first=observe(side_table())
    assert first['player']==['A','5'] and first['advice']['hand']['total']==16
    assert first['advice']['best_action']=='hit'
    initial=first['observed_cards']
    assert observe(side_table())['observed_cards']==initial
    settled=observe(side_table(('A','5','3'),('2','10','7'),settled=True,hidden=False))
    assert settled['advice'] is None
    next_round=observe(side_table())
    assert next_round['round']==2 and next_round['player']==['A','5']
    assert next_round['count_reliable'] and not next_round['count_reasons']
    assert next_round['running_count']==2
    assert next_round['observed_cards']==9


def test_caption_correction_is_closed_and_unambiguous():
    assert caption('STA')=='STAI'
    assert caption('DOBLE')=='DOUBLE'
    assert caption('17')=='17'
    assert caption('???')==''
    assert caption('BET 500')=='BET500'


def test_unseen_settlement_and_large_video_gap_disable_count_without_phantom_hand():
    observer=LiveObserver(Rules(decks=4,surrender='none'),samples=100,fresh_shoe=True)
    for i in range(6):first=observer.process(side_table(),i,i+1.)
    assert first['count_reliable']
    for i in range(6,12):result=observer.process(side_table(('9','8'),('7',)),i,20+i)
    assert result['player']==['9','8'] and result['advice']['best_action']=='stand'
    assert result['running_count'] is None and result['true_count'] is None
    assert not result['count_reliable'] and result['decision'] is None


def test_initial_unclassified_deal_is_not_counted_again_when_turn_starts():
    observer=LiveObserver(Rules(decks=4,surrender='none'),samples=100,fresh_shoe=True)
    image=side_table()
    observer.process(image,0,1.)
    external=observer.pixel_evidence[3]
    external['phase']='waiting'
    for i in range(1,7):waiting=observer.process(image,i,i+1.)
    assert waiting['observed_cards']==0 and waiting['advice'] is None
    external['phase']='player'
    for i in range(7,14):current=observer.process(image,i,i+1.)
    assert current['round']==1 and current['observed_cards']==3
    assert current['running_count']==1 and current['advice']['best_action']=='hit'
