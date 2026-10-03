"""Deterministic heads-up NLHE research engine, integer chips and zero rake.

This module does not import PokerKit or Treys. They are independent validation
references. A fixed complete deal isolates betting correctness from perception,
randomness and strategy. Public observations hide the other seat's hole cards.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable

from .poker import card, rank_hand

STREETS = ('preflop', 'flop', 'turn', 'river')


def chips(value, name, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer of at least {minimum}.')
    return value


@dataclass(frozen=True)
class PotLayer:
    amount: int
    eligible: tuple[int, ...]
    contributors: tuple[int, ...]
    refund: bool = False


def pot_layers(contributions: Iterable[int], folded: Iterable[int] = ()) -> tuple[PotLayer, ...]:
    """Partition matched pots and uncalled refunds; no money is discarded.

    This independent accounting utility supports multi-seat test fixtures. The
    betting engine itself supports exactly two seats. With two seats unequal
    contributions create an uncalled refund, not a contested side pot.
    """
    values = tuple(chips(v, 'Contribution') for v in contributions)
    if len(values) < 2:
        raise ValueError('At least two seats are required.')
    folded = frozenset(folded)
    if any(type(i) is not int or not 0 <= i < len(values) for i in folded):
        raise ValueError('Invalid folded seat.')
    previous = 0
    pots = []
    for level in sorted(set(values) - {0}):
        contributors = tuple(i for i, value in enumerate(values) if value >= level)
        amount = (level - previous) * len(contributors)
        refund = len(contributors) == 1
        eligible = contributors if refund else tuple(i for i in contributors if i not in folded)
        if not eligible:
            raise ValueError('A contested pot has no eligible player.')
        pots.append(PotLayer(amount, eligible, contributors, refund))
        previous = level
    return tuple(pots)


class HeadsUpHand:
    """One cash hand; seat ``button`` posts SB and acts first preflop.

    ``raise_to`` is the total street contribution, never an increment. The
    initial scope uses stacks >= BB, one runout, no antes/straddles/rake and
    unrestricted integer legal bet sizes. Strategy abstractions can restrict
    these actions later without changing the rules engine.
    """

    def __init__(self, stacks, hole, runout, *, small_blind=1, big_blind=2, button=0):
        chips(small_blind, 'Small blind', minimum=1)
        chips(big_blind, 'Big blind', minimum=2)
        if small_blind >= big_blind or type(button) is not int or button not in (0, 1):
            raise ValueError('Use SB < BB and a button seat of zero or one.')
        if len(stacks) != 2 or len(hole) != 2 or any(len(hand) != 2 for hand in hole):
            raise ValueError('Heads-up requires two stacks and two hole cards per seat.')
        self.starting_stacks = tuple(chips(v, 'Starting stack', minimum=big_blind) for v in stacks)
        self.hole = tuple(tuple(map(card, hand)) for hand in hole)
        self._runout = tuple(map(card, runout))
        all_cards = self.hole[0] + self.hole[1] + self._runout
        if len(self._runout) != 5 or len(set(all_cards)) != 9:
            raise ValueError('Provide five runout cards and nine distinct physical cards.')
        self.small_blind, self.big_blind, self.button = small_blind, big_blind, button
        self.stacks = list(self.starting_stacks)
        self.bets = [0, 0]
        self.contributions = [0, 0]
        self.folded = set()
        self.street_index = 0
        self.board = []
        self.last_full_raise = big_blind
        self.current_bet = big_blind
        self.pending = {0, 1}
        # _continue_betting selects the next pending seat after this one.
        self.actor = 1 - button
        self.settled = False
        self.payouts = [0, 0]
        self.pots = ()
        self.history = []
        for seat, amount in ((button, small_blind), (1 - button, big_blind)):
            self._pay(seat, amount)
            self._record('blind', seat=seat, amount=amount)
        self._continue_betting()
        self.assert_conservation()

    @property
    def pot(self):
        return 0 if self.settled else sum(self.contributions)

    @property
    def street(self):
        return 'settled' if self.settled else STREETS[self.street_index]

    @property
    def to_call(self):
        if self.actor is None:
            return 0
        return min(self.stacks[self.actor], self.current_bet - self.bets[self.actor])

    @property
    def max_raise_to(self):
        if self.actor is None or self.stacks[1 - self.actor] == 0:
            return None
        value = self.bets[self.actor] + self.stacks[self.actor]
        return value if value > self.current_bet else None

    @property
    def min_raise_to(self):
        maximum = self.max_raise_to
        if maximum is None:
            return None
        return min(maximum, self.current_bet + self.last_full_raise if self.current_bet else self.big_blind)

    def legal_actions(self):
        if self.actor is None:
            return ()
        result = ['call' if self.to_call else 'check', 'fold']
        if self.max_raise_to is not None:
            result.append('raise_to')
        return tuple(result)

    def _record(self, kind, **payload):
        self.history.append({'index': len(self.history), 'street': STREETS[self.street_index],
                             'kind': kind, **payload})

    def _pay(self, seat, amount):
        self.stacks[seat] -= amount
        self.bets[seat] += amount
        self.contributions[seat] += amount

    def act(self, action, amount=None, *, seat=None):
        """Reject invalid inputs before mutating any state or history."""
        if self.actor is None or self.settled:
            raise ValueError('This hand has no pending player action.')
        if seat is not None and (type(seat) is not int or seat != self.actor):
            raise ValueError('Only the current actor can act.')
        if action not in self.legal_actions():
            raise ValueError('Illegal action for the current state.')
        if action == 'raise_to':
            chips(amount, 'Raise-to amount', minimum=1)
            if not self.min_raise_to <= amount <= self.max_raise_to:
                raise ValueError('Raise violates the minimum raise or available stack.')
        elif amount is not None:
            raise ValueError('Only raise_to accepts an amount.')
        seat = self.actor
        self._record(action, seat=seat, amount=amount)
        if action == 'fold':
            self.folded.add(seat)
            self._settle()
        elif action == 'raise_to':
            increment = amount - self.current_bet
            self._pay(seat, amount - self.bets[seat])
            if increment >= self.last_full_raise:
                self.last_full_raise = increment
            self.current_bet = amount
            self.pending = {1 - seat}
            self._continue_betting()
        else:
            self._pay(seat, self.to_call)
            self.pending.discard(seat)
            self._continue_betting()
        self.assert_conservation()
        return self.observe()

    def _continue_betting(self):
        self.pending = {seat for seat in self.pending if self.stacks[seat] > 0}
        # A lone live stack may only respond to an unmatched all-in. There is
        # nobody left to contest a new bet or exercise a free BB option.
        live = [seat for seat in (0, 1) if self.stacks[seat] > 0]
        if len(live) == 1 and self.bets[live[0]] >= self.current_bet:
            self.pending.clear()
        if self.pending:
            self.actor = next(seat for seat in (1 - self.actor, self.actor) if seat in self.pending)
            return
        self.actor = None
        if any(stack == 0 for stack in self.stacks):
            self.board = list(self._runout)
            self._record('runout', cards=list(self.board))
            self._settle()
        elif self.street_index == 3:
            self._settle()
        else:
            self.street_index += 1
            self.board = list(self._runout[:(3, 4, 5)[self.street_index - 1]])
            self.bets = [0, 0]
            self.current_bet = 0
            self.last_full_raise = self.big_blind
            self.pending = {0, 1}
            self.actor = 1 - self.button
            self._record('board', cards=list(self.board))

    def _settle(self):
        self.pots = pot_layers(self.contributions, self.folded)
        for pot in self.pots:
            if pot.refund or len(pot.eligible) == 1:
                winners = list(pot.eligible)
            else:
                ranks = {seat: rank_hand(self.hole[seat] + tuple(self.board)) for seat in pot.eligible}
                best = max(ranks.values())
                winners = [seat for seat in pot.eligible if ranks[seat] == best]
            # Odd chips go to the first winning seat left of the button.
            winners.sort(key=lambda seat: (seat - self.button - 1) % 2)
            share, remainder = divmod(pot.amount, len(winners))
            for index, seat in enumerate(winners):
                value = share + (index < remainder)
                self.stacks[seat] += value
                self.payouts[seat] += value
            self._record('refund' if pot.refund else 'award', amount=pot.amount, winners=winners)
        self.settled = True
        self.bets = [0, 0]
        self.pending.clear()
        self.actor = None

    def assert_conservation(self):
        if any(type(value) is not int or value < 0 for value in self.stacks + self.bets + self.contributions):
            raise AssertionError('Invalid chip accounting.')
        if sum(self.stacks) + self.pot != sum(self.starting_stacks):
            raise AssertionError('Chip conservation failed.')

    def observe(self, viewer=None):
        """A fresh observation; perfect public state does not reveal hidden cards."""
        if viewer is not None and (type(viewer) is not int or viewer not in (0, 1)):
            raise ValueError('Invalid viewing seat.')
        return {'street': self.street, 'actor': self.actor, 'button': self.button,
                'stacks': list(self.stacks), 'bets': list(self.bets), 'pot': self.pot,
                'contributions': list(self.contributions), 'board': list(self.board),
                'hole': [list(hand) if (self.settled and not self.folded) or seat == viewer else None
                         for seat, hand in enumerate(self.hole)],
                'to_call': self.to_call, 'min_raise_to': self.min_raise_to,
                'max_raise_to': self.max_raise_to, 'legal_actions': list(self.legal_actions()),
                'settled': self.settled, 'rake': 0,
                'payoffs': [value - start for value, start in zip(self.stacks, self.starting_stacks)]
                           if self.settled else None}

    def export_history(self):
        return {'schema': 1, 'scope': 'offline perfect-deal research; audit contains private cards',
                'config': {'stacks': list(self.starting_stacks), 'hole': [list(h) for h in self.hole],
                           'runout': list(self._runout), 'small_blind': self.small_blind,
                           'big_blind': self.big_blind, 'button': self.button},
                'events': deepcopy(self.history), 'final': self.observe()}

    @classmethod
    def replay(cls, document):
        if document.get('schema') != 1:
            raise ValueError('Unsupported hand history schema.')
        hand = cls(**document['config'])
        for event in document['events']:
            if event['kind'] in ('check', 'call', 'fold', 'raise_to'):
                hand.act(event['kind'], event['amount'], seat=event['seat'])
        if hand.export_history() != document:
            raise ValueError('History differs from deterministic replay.')
        return hand
