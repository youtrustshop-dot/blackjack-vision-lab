import copy

import pytest

from bjlab.poker_engine import HeadsUpHand, pot_layers

HOLE = (('AS', 'AH'), ('KS', 'KH'))
BOARD = ('2S', '3H', '4D', '8C', '9S')


def hand(stacks=(100, 100), **kwargs):
    return HeadsUpHand(stacks, HOLE, BOARD, **kwargs)


def test_blind_option_position_and_showdown_chip_conservation():
    game = hand()
    assert game.actor == 0 and game.to_call == 1 and game.min_raise_to == 4
    game.act('call')
    assert game.actor == 1 and game.legal_actions() == ('check', 'fold', 'raise_to')
    game.act('check')
    assert game.street == 'flop' and game.actor == 1 and game.pot == 4
    for _ in range(6):
        game.act('check')
    assert game.settled and game.stacks == [102, 98]
    assert game.observe()['payoffs'] == [2, -2]
    assert HeadsUpHand.replay(game.export_history()).observe() == game.observe()


def test_uncalled_all_in_is_refunded_and_cannot_create_a_heads_up_side_pot():
    game = hand((100, 20))
    game.act('raise_to', 100)
    assert game.legal_actions() == ('call', 'fold')
    game.act('call')
    assert game.stacks == [120, 0]
    assert [(p.amount, p.refund) for p in game.pots] == [(40, False), (80, True)]
    assert game.pot == 0


def test_short_raise_all_in_and_fold_preserve_every_chip():
    game = hand((7, 100))
    game.act('raise_to', 5)
    game.act('raise_to', 8)
    assert game.to_call == 2 and game.min_raise_to is None
    game.act('call')
    assert game.settled and sum(game.stacks) == 107
    folded = hand()
    folded.act('raise_to', 17)
    folded.act('fold')
    assert folded.stacks == [102, 98]


def test_split_board_and_swapped_button():
    game = HeadsUpHand((100, 100), HOLE, ('2C', '3C', '4C', '5C', '6C'), button=1)
    assert game.actor == 1
    game.act('call'); game.act('check')
    assert game.actor == 0
    for _ in range(6): game.act('check')
    assert game.stacks == [100, 100]


def test_multiseat_accounting_utility_side_pots_dead_money_and_refund():
    pots = pot_layers((100, 60, 20), folded=(1,))
    assert [(p.amount, p.eligible, p.refund) for p in pots] == [
        (60, (0, 2), False), (80, (0,), False), (40, (0,), True)]
    assert sum(p.amount for p in pots) == 180


@pytest.mark.parametrize('action,amount,seat', [
    ('check', None, None), ('raise_to', 3, None), ('raise_to', 101, None),
    ('raise_to', True, None), ('raise_to', 4.5, None), ('call', 1, None),
    ('call', None, 1), ('dance', None, None)])
def test_invalid_action_is_atomic(action, amount, seat):
    game = hand()
    before = game.export_history()
    with pytest.raises(ValueError): game.act(action, amount, seat=seat)
    assert game.export_history() == before


def test_private_observations_and_history_tampering():
    game = hand()
    observed = game.observe(viewer=0)
    assert observed['hole'] == [list(HOLE[0]), None] and observed['board'] == []
    observed['stacks'][0] = 0
    assert game.stacks[0] == 99
    history = game.export_history()
    history['events'][0]['amount'] = 2
    with pytest.raises(ValueError): HeadsUpHand.replay(history)


@pytest.mark.parametrize('stacks,hole,board', [
    ((1, 100), HOLE, BOARD), ((True, 100), HOLE, BOARD),
    ((100, 100), (('AS', 'AH'), ('AS', 'KH')), BOARD),
    ((100, 100), HOLE, BOARD[:-1])])
def test_scope_and_physical_cards_are_enforced(stacks, hole, board):
    with pytest.raises(ValueError): HeadsUpHand(stacks, hole, board)
