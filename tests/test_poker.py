import math
import pytest
from fastapi.testclient import TestClient
from bjlab.api import app
from bjlab.poker import equity,rank_hand


@pytest.mark.parametrize('cards,expected',[
 ('AS KS QS JS TS 2H 3C',(8,14)),
 ('AH 2H 3H 4H 5H 8S 9C',(8,5)),
 ('AS AH AD AC KS QH 2C',(7,14,13)),
 ('AS AH AD KS KH KD 2C',(6,14,13)),
 ('AS JS 8S 6S 2S KD QH',(5,14,11,8,6,2)),
 ('AS 2H 3D 4S 5C KH QD',(4,5)),
 ('AS AH AD KS QH 2D 3C',(3,14,13,12)),
 ('AS AH KS KH QS QH 2D',(2,14,13,12)),
 ('AS AH KS QS JC 3D 2S',(1,14,13,12,11)),
 ('AS KH QD JS 8H 6S 2C',(0,14,13,12,11,8))])
def test_hand_categories_wheel_full_house_and_kickers(cards,expected):
    assert rank_hand(cards.split())==expected


def test_river_nuts_and_split_pot_share_are_not_win_probability():
    nuts=equity(['AS','KS'],['QS','JS','TS','2H','3C'],opponents=3,samples=100)
    assert nuts['equity']==nuts['win']==1 and nuts['loss']==0
    board=['AS','KS','QS','JS','TS']
    split=equity(['2H','3D'],board,opponents=3,samples=100,pot=90,call_cost=10)
    assert split['equity']==.25 and split['tie']==1 and split['win']==0
    assert split['pot_odds']==.1 and split['showdown_call_ev']==15


def test_explicit_ranges_block_known_cards_and_seed_is_reproducible():
    args=dict(hole=['AS','AH'],board=['2S','3H','4D','8C','9S'],samples=200,opponent_ranges=[[['AS','KS'],['KS','KH']]])
    result=equity(**args)
    assert result['win']==1
    assert result==equity(**args)


@pytest.mark.parametrize('args',[
 {'hole':['AS','AS']},{'hole':['AS','KH'],'board':['2S']},
 {'hole':['AS','KH'],'opponents':0},{'hole':['AS','KH'],'pot':math.nan},
 {'hole':['AS','KH'],'opponent_ranges':[[['AS','KS']]]},
 {'hole':['AS','KH'],'opponents':2,'opponent_ranges':[[['QS','QH']],[['QS','QH']]]}
])
def test_invalid_and_incompatible_joint_deals_are_rejected(args):
    with pytest.raises(ValueError):equity(**args,samples=100)


def test_api_rank_and_suit_input_contract():
    with TestClient(app) as client:
        ok=client.post('/api/poker/equity',json={'hole':['A♠','K♠'],'board':['Q♠','J♠','10♠','2H','3D'],'samples':100})
        assert ok.status_code==200 and ok.json()['equity']==1
        assert client.post('/api/poker/equity',json={'hole':['A','K']}).status_code==422
        assert client.post('/api/poker/equity',json={'hole':['AS','KH'],'board':['2S','3C']}).status_code==422
