"""Author versioned hand-derived fixtures without importing any solver.

Expected numbers come from the physical assignments explained in each fixture.
This script is a derivation record, not a source of observed solver values.
"""
from fractions import Fraction
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    path = ROOT / 'validation' / 'golden' / 'analytic.json'
    corpus = json.loads(path.read_text(encoding='utf-8'))
    authored = []

    def case(id, rules, state, evs, reason, insurance=None):
        reference = {'engine': 'manual-analytic', 'action_evs': evs, 'provenance': reason}
        if insurance is not None:
            reference['insurance'] = insurance
        authored.append({'id': id, 'rules': rules, 'state': state, 'reference': reference})

    n = lambda numerator, denominator: float(Fraction(numerator, denominator))
    pre_insurance = {'available': True, 'probability_blackjack': n(2, 3), 'ev': .5, 'take': True}
    post_insurance = {'available': False, 'probability_blackjack': 0., 'ev': -.5, 'take': False}
    for surrender in ('none', 'late', 'early'):
        expected = {'stand': -1., 'hit': n(-1, 3), 'double': 0.}
        if surrender != 'none':
            expected['surrender'] = -.5 if surrender == 'early' else n(-5, 6)
        case(f'analytic-prepeek11-vA-{surrender}', {'surrender': surrender},
             {'player': [5, 6], 'dealer': 'A', 'counts': [0] * 8 + [1, 2], 'peek_resolved': False}, expected,
             'Pool {9,T,T}. Each physical hole is equally likely. The two tens find dealer natural before any added bet and lose1; hole9 leaves a ten draw making21 against dealer20, returning1 hit or2 double. Hit=(-2+1)/3=-1/3; double=(-2+2)/3=0. Late surrender=(-2-1/2)/3=-5/6; early=-1/2. Prepeek insurance p=2/3, net=1.5p-.5=+.5.', pre_insurance)
        expected = {'stand': -1., 'hit': 1., 'double': 2.}
        if surrender != 'none':
            expected['surrender'] = -.5
        case(f'analytic-postpeek11-vA-{surrender}', {'surrender': surrender},
             {'player': [5, 6], 'dealer': 'A', 'counts': [0] * 8 + [1, 2], 'peek_resolved': True}, expected,
             'Negative peek forces hole9, dealer20. Remaining observed draw must be a ten, making player21; stand loses1, hit wins1, double wins2. Insurance cannot be taken after this resolved check; its hypothetical forced-loss EV is-.5.', post_insurance)

    for mode in ('all', 'original'):
        case(f'analytic-enhcbust-double-{mode}', {'enhc': True, 'enhc_loss': mode, 'surrender': 'none'},
             {'player': [10, 10], 'dealer': 10, 'counts': [1] + [0] * 8 + [1], 'can_split': False},
             {'stand': n(-1, 2), 'hit': 0., 'double': 0. if mode == 'all' else .5},
             'Two physical assignments: drawA/holeT gives player21 versus20 (+1 hit/+2 double); drawT/holeA busts and dealer has natural (-1 hit, -2 all or -1 OBO double). Stand: holeT pushes20, holeA loses1. Average each pair. OBO refunds the added doubled bet even after a bust.')
        case(f'analytic-enhcbust-jointdouble-{mode}', {'enhc': True, 'enhc_loss': mode, 'surrender': 'none'},
             {'player': [8, 9], 'dealer': 10, 'counts': [1] + [0] * 7 + [3, 0],
              'from_split': True, 'split_hands': 2,
              'completed_hands': [{'cards': [10, 10, 9], 'wager': 2., 'original_wager': 0., 'from_split': True}]},
             {'double': -4. if mode == 'all' else n(-13, 4)},
             'Pool {A,9,9,9}. Prior split hand is already busted with stake2. Active17 doubles: drawA makes18, any nonnatural dealer has19 and wins; draw9 busts. Every nonnatural assignment loses4 total. HoleA probability1/4 finds natural: all loses4, OBO refunds extras including the prior bust and loses1 total. Thus OBO=(3*-4+-1)/4=-13/4; all=-4. Extra nines ensure hit continuations also terminate before exhaustion.')

    case('analytic-hsa-split21-stops', {'decks': 1, 'surrender': 'none', 'max_split_hands': 2,
                                     'resplit': False, 'hit_split_aces': True},
         {'player': ['A', 'A'], 'dealer': 6, 'counts': [0] * 9 + [12]}, {'split': 2.},
         'Only tens remain. Each split ace receivesT and completes at21 despite permission to hit split aces. Dealer6+T+T busts. Each ordinary one-unit21 wins1, total2; no double after a completed21 and no natural bonus.')
    case('analytic-splitT-A-stops', {'decks': 1, 'surrender': 'none', 'max_split_hands': 2,
                                  'resplit': False, 'hit_split_aces': True},
         {'player': [10, 10], 'dealer': 9, 'counts': [4] + [0] * 9}, {'split': 2.},
         'Only aces remain. Dealer9+A=20 stands. Both split tens receiveA, complete ordinary21 and win1 each. No double after a completed21, total2.')

    for h17 in (False, True):
        case(f'analytic-soft18-v6-{"H17" if h17 else "S17"}', {'decks': 2, 'hit_soft17': h17},
             {'player': ['A', 7], 'dealer': 6, 'counts': [6] + [0] * 9},
             {'stand': 0. if h17 else 1., 'hit': 1., 'double': 2., 'surrender': -.5},
             'Only aces remain. Dealer6+A is soft17: S17 stands17, H17 adds one ace and stands18. Player soft18 standing wins1 against17 or pushes18. A player hit/double adds an ace to soft19 and wins against either; further optimal hits cannot improve above win1. Double wins2; late surrender=-.5. Two decks provide enough physical aces for all branches.')

    case('analytic-negativepeek-mixed19-vT', {'surrender': 'none'},
         {'player': [10, 9], 'dealer': 10, 'counts': [0, 1, 0, 0, 0, 0, 0, 2, 0, 3]},
         {'stand': n(-2, 15), 'hit': n(-2, 3), 'double': n(-4, 3)},
         'Pool {2,8,8,T,T,T} has no dealer-natural possibility. Hole8 wins2/6, holeT loses3/6. Hole2 has dealer12, then draws8 twice out of5 to20 or T three out of5 to bust: contributes(1/6)*(3/5-2/5). Stand=2/6-3/6+1/30=-2/15. A player hit wins only on the lone2, making21; other ranks bust. Marginal hit=(1-5)/6=-2/3, double=-4/3.')

    case('analytic-natural-prepeek-insurance', {},
         {'player': ['A', 10], 'dealer': 'A', 'counts': [1] + [0] * 8 + [1], 'peek_resolved': False},
         {'stand': .75}, 'Pool {A,T}: holeT natural pushes player natural, holeA has no natural and pays3:2. Expected payout=(0+1.5)/2=.75. Prepeek insurance has p=.5 and net1.5*.5-.5=.25.',
         {'available': True, 'probability_blackjack': .5, 'ev': .25, 'take': True})
    case('analytic-natural-negativepeek', {},
         {'player': ['A', 10], 'dealer': 'A', 'counts': [1] + [0] * 8 + [1], 'peek_resolved': True},
         {'stand': 1.5}, 'Negative peek excludes holeT, so player natural pays3:2 with certainty. Insurance is unavailable after peek.', post_insurance)

    authored_ids = {case['id'] for case in authored}
    corpus['cases'] = [case for case in corpus['cases'] if case['id'] not in authored_ids] + authored
    corpus['derivation_source'] = 'validation/reference_engines/extend_analytic_golden.py (no solver imports)'
    corpus['supplemental_field_contract'] = 'reference.insurance is independently checked by tests/test_validation.py::test_analytic_insurance_goldens; run_golden compares action EVs.'
    corpus['independent_joint_split_assignments'] = [
        'tests/test_solver.py::test_mixed_finite_shoe_split_matches_exhaustive_assignment',
        'tests/test_solver.py::test_mixed_finite_shoe_split_aces_exhaustive_assignment']
    path.write_text(json.dumps(corpus, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'cases': len(corpus['cases']), 'authored_now': len(authored), 'solver_imported': False}))


if __name__ == '__main__':
    main()
