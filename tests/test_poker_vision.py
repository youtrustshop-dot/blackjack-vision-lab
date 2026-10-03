import base64,io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from bjlab.api import app
from bjlab.datasets import card_image
from bjlab.poker_vision import inspect,read_region


def poker_image(hole=('AS','KH'),board=('QS','JH','2D')):
    image=Image.new('RGB',(800,600),(14,37,62))
    for cards,y,left in ((hole,400,250),(board,150,120)):
        for i,c in enumerate(cards):image.paste(card_image(c[0],c[1]),(left+i*95,y))
    return image


def test_calibrated_original_cards_have_distinct_ranks_and_suits():
    report=inspect(poker_image(),[.25,.6,.5,.3],[.1,.2,.8,.3])
    assert report['hole']==['AS','KH'] and report['board']==['QS','JH','2D']
    assert report['gate']['solver_allowed']


def test_duplicate_physical_card_is_gated_and_no_hidden_rank_is_inferred():
    report=inspect(poker_image(board=('AS','JH','2D')),[.25,.6,.5,.3],[.1,.2,.8,.3])
    assert not report['gate']['solver_allowed']
    assert any('physical card' in r for r in report['gate']['reasons'])
    image=poker_image(hole=('AS',),board=())
    image.paste(card_image(None,None,face_down=True),(345,400))
    report=inspect(image,[.25,.6,.5,.3],[.1,.2,.8,.3])
    assert report['hole']==['AS'] and not report['gate']['solver_allowed']


@pytest.mark.parametrize('roi',[[0,0,2,1],[-.1,0,.5,.5],[0,0,0,.5],[0,0,float('nan'),.5]])
def test_regions_must_be_explicit_finite_and_inside_image(roi):
    with pytest.raises(ValueError):read_region(poker_image(),roi,'hole')


def test_actual_image_api_preserves_pixel_only_input_contract():
    image=poker_image();data=io.BytesIO();image.save(data,format='PNG')
    with TestClient(app) as client:
        response=client.post('/api/poker/image',json={'image_base64':base64.b64encode(data.getvalue()).decode(),'hole_roi':[.25,.6,.5,.3],'board_roi':[.1,.2,.8,.3]})
    assert response.status_code==200 and response.json()['hole']==['AS','KH']
