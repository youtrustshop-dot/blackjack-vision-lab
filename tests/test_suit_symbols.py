import numpy as np
import pytest
from PIL import Image,ImageDraw
from bjlab.datasets import card_font
from bjlab.suit_symbols import read_suit


@pytest.mark.parametrize('suit,symbol',tuple(zip('SHDC','♠♥♦♣')))
@pytest.mark.parametrize('size',(20,32,48))
def test_original_clear_symbol_family(suit,symbol,size):
    image=Image.new('RGB',(80,80),'white')
    ImageDraw.Draw(image).text((40,40),symbol,font=card_font(size),fill=(190,0,0) if suit in 'HD' else (0,0,0),anchor='mm')
    assert read_suit(np.asarray(image))==suit


def test_blank_and_too_small_symbols_stay_unknown():
    assert read_suit(np.full((40,40,3),255,np.uint8)) is None
    image=Image.new('RGB',(20,20),'white');ImageDraw.Draw(image).text((10,10),'♣',font=card_font(5),fill='black',anchor='mm')
    assert read_suit(np.asarray(image)) is None
