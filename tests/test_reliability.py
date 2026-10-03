from types import SimpleNamespace
from bjlab.clef_contract import parse_visual_result,visual_request
from bjlab.round_lifecycle import RoundLifecycle
from bjlab.external_vision import integrity_reasons

def cards(player,dealer):
    return [SimpleNamespace(rank=r,zone='player:0') for r in player]+[SimpleNamespace(rank=r,zone='dealer') for r in dealer]

def stable(lifecycle,player,dealer,phase):
    for _ in range(3):result=lifecycle.observe(cards(player,dealer),phase)
    return result

def test_round_boundary_identical_redeal_and_missed_settlement():
    lifecycle=RoundLifecycle()
    assert stable(lifecycle,['A','5'],['2'],'player')['new_round']
    assert not stable(lifecycle,['A','5','3'],['2'],'player')['new_round']
    stable(lifecycle,['A','5','3'],['2','K','8'],'settled')
    next_round=stable(lifecycle,['A','5'],['2'],'player')
    assert next_round['new_round'] and not next_round['history_gap']
    abrupt=stable(lifecycle,['9','8'],['7'],'player')
    assert abrupt['new_round'] and abrupt['history_gap']

def test_animation_cannot_create_round_before_stability():
    lifecycle=RoundLifecycle()
    stable(lifecycle,['A','5'],['2'],'player')
    for player in (['3','5'],['A','5','7'],['8','9']):
        assert not lifecycle.observe(cards(player,['2']),'player')['stable']

def test_rescaling_context_still_verifies_total_and_active_hand():
    ds=[SimpleNamespace(rank=r,zone='player:0',face_down=False) for r in ['A','5']]
    context={'phase':'player','player_totals':{'player:0':[19]},'active_hand_ambiguous':True}
    assert len(integrity_reasons(context,ds))==2
    context['player_totals']={'player:0':[16]};context['active_hand_ambiguous']=False
    assert integrity_reasons(context,ds)==[]

def test_clef_fixed_contract_never_accepts_malformed_or_uncertain_answers():
    assert len(visual_request('table')['questions'])==8
    for result in (None,[],{'answers':[]},{'answers':{'rank':[]}},
                   {'answers':{'rank':{'choice':'A','probabilities':{'A':True}}}},
                   {'answers':{'rank':{'choice':'A','probabilities':{'A':float('nan')}}}}):
        assert not parse_visual_result(result,'card')['answers']['rank']['accepted']
    result={'answers':{'rank':{'choice':'A','probabilities':{'A':.99}},'suit':{'choice':'unknown','probabilities':{'unknown':1}}}}
    parsed=parse_visual_result(result,'card')
    assert parsed['answers']['rank']['accepted'] and not parsed['answers']['suit']['accepted']
