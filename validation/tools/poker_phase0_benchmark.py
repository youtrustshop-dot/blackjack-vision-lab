"""Freeze PokerKit trajectories, then differentially verify our NLHE engine.

The reference chooses legal actions and supplies each expected intermediate
state. Treys and PokerKit independently check hand ordering. No strategy
training, video input, rake or economic-performance claim is involved.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.poker import DECK, rank_hand
from bjlab.poker_engine import HeadsUpHand


def text(cards):
    return ''.join(c[0] + c[1].lower() for c in cards)


def reference(config):
    from pokerkit import Automation, Mode, NoLimitTexasHoldem
    button = config['button']
    order = (1 - button, button)  # PokerKit HU: BB seat 0, button/SB seat 1.
    auto = (Automation.ANTE_POSTING, Automation.BET_COLLECTION,
            Automation.BLIND_OR_STRADDLE_POSTING, Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
            Automation.HAND_KILLING, Automation.CHIPS_PUSHING, Automation.CHIPS_PULLING,
            Automation.RUNOUT_COUNT_SELECTION)
    state = NoLimitTexasHoldem.create_state(auto, True, 0,
        (config['small_blind'], config['big_blind']), config['big_blind'],
        tuple(config['stacks'][seat] for seat in order), 2, mode=Mode.CASH_GAME)
    for index, seat in enumerate(order):
        state.deal_hole(text(config['hole'][seat]), index)
    return state, order


def drain(state, runout):
    while state.status and state.actor_index is None:
        if state.can_burn_card():
            state.burn_card('??')  # Unknown burn: never randomly consume a planned runout.
        elif state.can_deal_board():
            offset = len(tuple(state.get_board_cards(0)))
            state.deal_board(text(runout[offset:offset + state.board_dealing_count]))
        else:
            raise RuntimeError('Unexpected manual PokerKit transition.')


def snapshot(state, order):
    raising = state.can_complete_bet_or_raise_to() if state.actor_index is not None else False
    call = state.checking_or_calling_amount if state.actor_index is not None else 0
    actions = []
    if state.actor_index is not None:
        if state.can_check_or_call(): actions.append('call' if call else 'check')
        if state.can_fold(): actions.append('fold')
        if raising: actions.append('raise_to')
    return {'actor': order[state.actor_index] if state.actor_index is not None else None,
        'street': ('preflop', 'flop', 'turn', 'river')[state.street_index] if state.status else 'settled',
        'stacks': [state.stacks[order.index(seat)] for seat in (0, 1)],
        'bets': [state.bets[order.index(seat)] for seat in (0, 1)],
        'pot': state.total_pot_amount, 'to_call': call,
        'min_raise_to': state.min_completion_betting_or_raising_to_amount if raising else None,
        'max_raise_to': state.max_completion_betting_or_raising_to_amount if raising else None,
        'legal_actions': actions, 'settled': not state.status,
        'board': [repr(c).upper() for c in state.get_board_cards(0)]}


def generate(path, *, seed, hands, evaluator_pairs):
    if path.exists(): raise ValueError('Corpus is frozen. Choose a new path.')
    rng = random.Random(seed)
    games = []
    for index in range(hands):
        deal = rng.sample(DECK, 9)
        # Include asymmetric short stacks and both button positions.
        stacks = [(2, 100), (100, 2), (7, 100), (100, 7), (100, 100)][index % 5]
        if index % 6 == 0: stacks = (rng.randint(2, 300), rng.randint(2, 300))
        config = {'stacks': stacks, 'hole': (deal[:2], deal[2:4]), 'runout': deal[4:],
                  'small_blind': 1, 'big_blind': 2, 'button': index % 2}
        state, order = reference(config)
        drain(state, config['runout'])
        initial = snapshot(state, order)
        steps = []
        while state.status:
            expected = snapshot(state, order)
            # Include full passive showdowns; random policies alone terminate
            # many hands preflop and give weak coverage of later streets.
            action = ('call' if expected['to_call'] else 'check') if index%7==0 else rng.choice(expected['legal_actions'])
            amount = None
            if action == 'raise_to':
                amount = rng.choice((expected['min_raise_to'], expected['max_raise_to'],
                    rng.randint(expected['min_raise_to'], expected['max_raise_to'])))
                state.complete_bet_or_raise_to(amount)
            elif action == 'fold': state.fold()
            else: state.check_or_call()
            drain(state, config['runout'])
            steps.append({'action': action, 'amount': amount, 'expected': snapshot(state, order)})
            if len(steps) > 100: raise RuntimeError('Reference hand failed to terminate.')
        games.append({'id': f'{seed}:{index}', 'config': config, 'initial': initial, 'steps': steps})
    pairs = []
    from pokerkit import StandardHighHand
    from treys import Card, Evaluator
    evaluator = Evaluator()
    for _ in range(evaluator_pairs):
        size = rng.choice((5, 6, 7))
        first = rng.sample(DECK, size); second = rng.sample(DECK, size)
        p1 = StandardHighHand.from_game(text(first)); p2 = StandardHighHand.from_game(text(second))
        pk = (p1 > p2) - (p1 < p2)
        t1 = evaluator.evaluate([], [Card.new(c[0] + c[1].lower()) for c in first])
        t2 = evaluator.evaluate([], [Card.new(c[0] + c[1].lower()) for c in second])
        treys = (t1 < t2) - (t1 > t2)
        if pk != treys: raise RuntimeError('Independent evaluator references disagree; investigate.')
        pairs.append({'first': first, 'second': second, 'ordering': pk})
    corpus = {'schema': 1, 'scope': 'heads-up cash, fixed deals, integer chips, stacks >= BB, one runout, zero rake',
        'seed': seed, 'references': {name: importlib.metadata.version(name) for name in ('pokerkit', 'treys')},
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'acceptance': {'state_divergences': 0, 'evaluator_divergences': 0, 'replay_divergences': 0},
        'games': games, 'evaluator_pairs': pairs}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as target:
        target.write(json.dumps(corpus, indent=2) + '\n')
    return corpus


def run(path, output):
    payload = path.read_bytes(); corpus = json.loads(payload)
    divergences = []; state_checks = 0; replay_failures = []
    fields = ('actor', 'street', 'stacks', 'bets', 'pot', 'to_call', 'min_raise_to',
              'max_raise_to', 'settled', 'board')
    for fixture in corpus['games']:
        game = HeadsUpHand(**fixture['config'])
        def check(expected, step):
            nonlocal state_checks
            actual = game.observe(); state_checks += 1
            differences = {name: {'actual': actual[name], 'expected': expected[name]}
                           for name in fields if actual[name] != expected[name]}
            if set(actual['legal_actions']) != set(expected['legal_actions']):
                differences['legal_actions'] = {'actual': actual['legal_actions'], 'expected': expected['legal_actions']}
            if differences: divergences.append({'id': fixture['id'], 'step': step, 'differences': differences})
            game.assert_conservation()
        check(fixture['initial'], -1)
        for index, step in enumerate(fixture['steps']):
            try: game.act(step['action'], step['amount'])
            except ValueError as exc:
                divergences.append({'id': fixture['id'], 'step': index, 'error': str(exc)})
                break
            check(step['expected'], index)
        try: HeadsUpHand.replay(game.export_history())
        except ValueError as exc: replay_failures.append({'id': fixture['id'], 'error': str(exc)})
    rank_failures = []
    for index, pair in enumerate(corpus['evaluator_pairs']):
        first = rank_hand(pair['first']); second = rank_hand(pair['second'])
        ordering = (first > second) - (first < second)
        if ordering != pair['ordering']: rank_failures.append({'index': index, **pair, 'actual': ordering})
    result = {'corpus_sha256': hashlib.sha256(payload).hexdigest(), 'scope': corpus['scope'],
        'references': corpus['references'], 'hands': len(corpus['games']), 'intermediate_state_checks': state_checks,
        'evaluator_pairs': len(corpus['evaluator_pairs']), 'state_divergences': divergences,
        'evaluator_divergences': rank_failures, 'replay_divergences': replay_failures,
        'passed': not (divergences or rank_failures or replay_failures),
        'strategy_quality_evaluated': False, 'economic_edge_evaluated': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: len(value) if key.endswith('divergences') else value for key, value in result.items()}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('generate', 'run'))
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seed', type=int, default=913107)
    parser.add_argument('--hands', type=int, default=1000)
    parser.add_argument('--evaluator-pairs', type=int, default=6000)
    args = parser.parse_args()
    if args.command == 'generate':
        data = generate(args.corpus, seed=args.seed, hands=args.hands, evaluator_pairs=args.evaluator_pairs)
        print(json.dumps({'hands': len(data['games']), 'evaluator_pairs': len(data['evaluator_pairs']),
                          'sha256': hashlib.sha256(args.corpus.read_bytes()).hexdigest()}))
    else:
        if args.output is None: parser.error('run requires --output')
        raise SystemExit(0 if run(args.corpus, args.output)['passed'] else 1)
