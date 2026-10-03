"""Independent small-pool analytic checks; never an external-reference claim."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules
from bjlab.solver import Solver


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    cases = []

    def check(label, rules, player, up, counts, expected, **kwargs):
        actual = Solver(rules).analyze(player, up, counts, **kwargs)
        discrepancies = {action: actual['actions'].get(action) for action, value in expected.items()
                         if actual['actions'].get(action) is None or abs(actual['actions'][action] - value) > 1e-12}
        cases.append({'id': label, 'rules': asdict(rules), 'player': player, 'dealer': up,
                      'counts': list(counts), 'context': kwargs, 'analytic_expected': expected,
                      'result': actual, 'status': 'passed' if not discrepancies else 'failed',
                      'discrepancies': discrepancies})
        assert not discrepancies, cases[-1]
        return actual

    pool = (0, 0, 0, 0, 0, 0, 0, 0, 1, 2)
    for surrender in ('none', 'late', 'early'):
        expected = {'stand': -1., 'hit': -1 / 3, 'double': 0.}
        if surrender != 'none':
            expected['surrender'] = -.5 if surrender == 'early' else -5 / 6
        pre = check(f'prepeek-double-{surrender}', Rules(surrender=surrender), [5, 6], 'A', pool,
                    expected, peek_resolved=False)
        assert pre['exact'] and pre['best_action'] == 'double'
        assert pre['insurance']['ev'] == .5 and pre['insurance']['available']
        post = check(f'postpeek-double-{surrender}', Rules(surrender=surrender), [5, 6], 'A', pool,
                     {'stand': -1., 'hit': 1., 'double': 2.}, peek_resolved=True)
        assert post['exact'] and not post['insurance']['available']
        expected = {'stand': -1., 'hit': -1., 'double': -1., 'split': -1.}
        if surrender != 'none':
            expected['surrender'] = -.5 if surrender == 'early' else -1.
        check(f'certain-blackjack-{surrender}', Rules(surrender=surrender), [8, 8], 10,
              (4,) + (0,) * 9, expected, peek_resolved=False)

    for mode, double in (('all', 0.), ('original', .5)):
        # H=T, draw A: player 21 wins +1 hit/+2 double. H=A, draw T:
        # player busts, and natural dealer loses -1 hit or -2/-1 double.
        check(f'enhc-bust-{mode}', Rules(enhc=True, enhc_loss=mode, surrender='none'),
              [10, 10], 10, (1,) + (0,) * 8 + (1,), {'hit': 0., 'double': double}, can_split=False)
        # Prior split hand already busted for stake2. Active17 doubles:
        # draw A/H=9 loses -4 round total, draw9/H=A loses -4(all) or -1(OBO).
        # This path must retain the latent BJ refund, including the earlier bust.
        check(f'enhc-joint-bust-{mode}', Rules(enhc=True, enhc_loss=mode, surrender='none'),
              [8, 9], 10, (1,) + (0,) * 7 + (1, 0),
              {'double': -4. if mode == 'all' else -2.5}, from_split=True, split_hands=2,
              completed_hands=[{'cards': [10, 10, 9], 'wager': 2, 'original_wager': 0, 'from_split': True}])

    terminal_rules = Rules(decks=1, surrender='none', max_split_hands=2,
                           resplit=False, hit_split_aces=True)
    check('split-aces-receive-tens-stop21', terminal_rules, ['A', 'A'], 6,
          (0,) * 9 + (12,), {'split': 2.})
    check('split-tens-receive-aces-stop21', terminal_rules, [10, 10], 9,
          (4,) + (0,) * 9, {'split': 2.})

    artifacts = ROOT / 'validation' / 'differential' / 'results' / 'hhoppe-2000'
    original = {name: sha256(artifacts / name) for name in ('report.json', 'DifferentialFailure.json')}
    payload = {'status': 'passed', 'created_at': datetime.now(timezone.utc).isoformat(),
               'method': 'independent analytic physical-hole assignments', 'external_reference': False,
               'tolerance': 1e-12, 'cases': cases,
               'derivation': ['For pool 9,T,T and up A, two hole assignments find natural before actions.',
                              'The remaining hole9 assignment draws T: player11 becomes21 versus dealer20.',
                              'Late surrender applies only to the negative-peek branch; early is fixed -1/2.',
                              'OBO joint bust enumerates the two possible hole/draw assignments; original loss is allocated once.',
                              'A split21 stops without a double; two winning one-unit split hands return +2, not +4.'],
               'scope_of_fix': ['Explicit/unresolved future AHC peek; already negative-peek recursion unchanged.',
                                'Double unavailable at split21, matching simulator automatic completion.'],
               'original_corpus_scope_check': 'Corpus excludes initial natural and pair splitting. Nonnatural21 hands have3+cards and were already ineligible to double. Neither changed branch occurs in its states.',
               'original_corpus_artifact_sha256': original,
               'original_corpus_solver_sha256': 'ea14fa586a3e382a313a09753e21a277ed93258be790188cb8f186fae8a5a40c',
               'current_source_sha256': {name: sha256(ROOT / 'bjlab' / name)
                                         for name in ('solver.py', 'engine.py', 'strategy.py')},
               'runner_sha256': sha256(Path(__file__)),
               'corpus_not_rerun': True,
               'corpus_resolution': 'validation/reference_engines/results/hhoppe-resolution.json'}
    output = ROOT / 'validation' / 'reference_engines' / 'results' / 'prepeek-core-audit.json'
    output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'cases': len(cases), 'solver_sha256': payload['current_source_sha256']['solver.py'], 'output': str(output)}))


if __name__ == '__main__':
    main()
