"""Independent rules reference and independent hand-evaluation references."""
from pokerkit import Automation, Mode, NoLimitTexasHoldem

from validation.tools.poker_phase0_benchmark import generate, run, drain
from bjlab.poker_engine import pot_layers


def test_frozen_reference_trajectories_all_intermediate_states_and_replay(tmp_path):
    path=tmp_path/'corpus.json'
    generate(path, seed=130907, hands=250, evaluator_pairs=500)
    result=run(path,tmp_path/'result.json')
    assert result['passed']
    assert result['hands']==250 and result['intermediate_state_checks']>500
    assert result['evaluator_pairs']==500


def test_multiplayer_pot_accounting_reference_does_not_extend_hu_betting_scope():
    auto=(Automation.ANTE_POSTING,Automation.BET_COLLECTION,Automation.BLIND_OR_STRADDLE_POSTING,
          Automation.HOLE_CARDS_SHOWING_OR_MUCKING,Automation.HAND_KILLING,
          Automation.CHIPS_PUSHING,Automation.CHIPS_PULLING,Automation.RUNOUT_COUNT_SELECTION)
    state=NoLimitTexasHoldem.create_state(auto,True,0,(1,2,0),2,(100,60,20),3,mode=Mode.CASH_GAME)
    for seat, cards in enumerate(('2h3h','KsKh','AsAh')): state.deal_hole(cards,seat)
    state.complete_bet_or_raise_to(20)
    state.complete_bet_or_raise_to(100)
    state.check_or_call()
    drain(state,('4S','5H','8D','9C','TS'))
    # AA wins the main pot, KK the contested side pot; the unmatched 40 returns.
    assert state.stacks==[40,80,60]
    pots=pot_layers((100,60,20))
    assert [(p.amount,p.eligible,p.refund) for p in pots]==[
        (60,(0,1,2),False),(80,(0,1),False),(40,(0,),True)]
