"""Blackjack rules and settlement, independent of vision and random-number sources.

Card values use A=1, 2..9, and 10 for all ten-valued ranks. Money returned
by settlement is NET profit in units of the original wager, not gross payout.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Rules:
    decks: int = 6
    hit_soft17: bool = False
    blackjack_payout: float = 1.5
    dealer_peek: bool = True
    enhc: bool = False
    enhc_loss: str = "all"
    double_rule: str = "any"
    double_after_split: bool = True
    resplit: bool = True
    max_split_hands: int = 4
    resplit_aces: bool = False
    hit_split_aces: bool = False
    surrender: str = "late"
    penetration: float = .75

    def __post_init__(self) -> None:
        if isinstance(self.decks, bool) or not isinstance(self.decks, int) or self.decks not in (1, 2, 4, 6, 8):
            raise ValueError("decks must be one of 1, 2, 4, 6, 8")
        for field in ("hit_soft17", "dealer_peek", "enhc", "double_after_split", "resplit",
                      "resplit_aces", "hit_split_aces"):
            if not isinstance(getattr(self, field), bool):
                raise ValueError(f"{field} must be a boolean")
        if (isinstance(self.blackjack_payout, bool) or not isinstance(self.blackjack_payout, (int, float))
                or not math.isfinite(self.blackjack_payout) or self.blackjack_payout <= 0):
            raise ValueError("blackjack_payout must be a finite positive net payout")
        if not isinstance(self.enhc_loss, str) or not isinstance(self.double_rule, str) or not isinstance(self.surrender, str):
            raise ValueError("enhc_loss, double_rule and surrender must be strings")
        if self.enhc_loss not in ("all", "original"):
            raise ValueError("enhc_loss must be 'all' or 'original' (OBO)")
        aliases = {"any two": "any", "any_two": "any", "9_11": "9-11", "10_11": "10-11"}
        object.__setattr__(self, "double_rule", aliases.get(self.double_rule, self.double_rule))
        if self.double_rule not in ("any", "9-11", "10-11", "none"):
            raise ValueError("double_rule must be any, 9-11, 10-11, or none")
        if self.surrender not in ("none", "early", "late"):
            raise ValueError("surrender must be none, early, or late")
        if (isinstance(self.max_split_hands, bool) or not isinstance(self.max_split_hands, int)
                or not 1 <= self.max_split_hands <= 8):
            raise ValueError("max_split_hands must be an integer from 1 to 8")
        if (isinstance(self.penetration, bool) or not isinstance(self.penetration, (int, float))
                or not math.isfinite(self.penetration) or not 0 < self.penetration < 1):
            raise ValueError("penetration must be strictly between 0 and 1")


def card_rank(card: str | int) -> int:
    """Accept A/2..10/J/Q/K, optional ASCII or Unicode suit, or rank 1..13."""
    if isinstance(card, bool):
        raise ValueError("a boolean is not a card")
    if isinstance(card, int):
        if 1 <= card <= 13:
            return min(card, 10)
        raise ValueError(f"invalid card rank: {card!r}")
    if not isinstance(card, str):
        raise ValueError(f"invalid card: {card!r}")
    value = card.strip().upper()
    for suffix in ("♠", "♥", "♦", "♣", "S", "H", "D", "C"):
        if value.endswith(suffix):
            value = value[:-1].strip()
            break
    if value in ("A", "ACE"):
        return 1
    if value in ("T", "J", "Q", "K", "JACK", "QUEEN", "KING"):
        return 10
    if value.isdigit() and 1 <= int(value) <= 13:
        return min(int(value), 10)
    raise ValueError(f"invalid card: {card!r}")


def hand_value(cards: Iterable[str | int]) -> tuple[int, bool]:
    ranks = tuple(card_rank(card) for card in cards)
    total = sum(ranks)
    soft = 1 in ranks and total + 10 <= 21
    return (total + 10 if soft else total), soft


def is_blackjack(cards: Iterable[str | int], *, from_split: bool = False) -> bool:
    ranks = tuple(card_rank(card) for card in cards)
    return not from_split and len(ranks) == 2 and sorted(ranks) == [1, 10]


def initial_counts(decks: int) -> tuple[int, ...]:
    if isinstance(decks, bool) or not isinstance(decks, int) or decks not in (1, 2, 4, 6, 8):
        raise ValueError("decks must be one of 1, 2, 4, 6, 8")
    return (4 * decks,) * 9 + (16 * decks,)


def dealer_should_hit(cards: Iterable[str | int], rules: Rules) -> bool:
    total, soft = hand_value(cards)
    return total < 17 or (total == 17 and soft and rules.hit_soft17)


def legal_actions(
    player: Iterable[str | int], rules: Rules, *, from_split: bool = False,
    split_hands: int = 1, split_aces: bool = False, peek_resolved: bool = False,
    can_double: bool | None = None, can_split: bool | None = None,
    can_surrender: bool | None = None,
) -> list[str]:
    """Legal actions in turn; external flags may REMOVE, never add, actions.

    Late surrender is a rules permission. Whether it is valid before a dealer
    blackjack check is represented in settlement/EV rather than silently treating
    it as an unconditional loss of half a bet.
    """
    cards = tuple(card_rank(card) for card in player)
    if len(cards) < 2:
        return []
    total, _ = hand_value(cards)
    if total > 21:
        return []
    if is_blackjack(cards, from_split=from_split):
        return ["stand"]
    actions = ["stand"]
    frozen_aces = from_split and split_aces and not rules.hit_split_aces
    if total < 21 and not frozen_aces:
        actions.append("hit")
    # Twenty-one completes the hand, including a non-natural split A+10.
    # This must match the simulator's automatic stand at twenty-one.
    double_ok = len(cards) == 2 and total < 21 and not frozen_aces and rules.double_rule != "none"
    double_ok &= not from_split or rules.double_after_split
    if rules.double_rule == "9-11":
        double_ok &= 9 <= total <= 11
    elif rules.double_rule == "10-11":
        double_ok &= 10 <= total <= 11
    if double_ok and can_double is not False:
        actions.append("double")
    split_ok = len(cards) == 2 and cards[0] == cards[1] and split_hands < rules.max_split_hands
    if from_split:
        split_ok &= rules.resplit
        if cards[0] == 1:
            split_ok &= rules.resplit_aces
    if split_ok and can_split is not False:
        actions.append("split")
    if not from_split and len(cards) == 2 and rules.surrender != "none" and can_surrender is not False:
        actions.append("surrender")
    return actions


def settle(
    player: Iterable[str | int], dealer: Iterable[str | int], rules: Rules, *,
    wager: float = 1, from_split: bool = False, surrendered: bool = False,
    doubled: bool = False, original_wager: float = 1,
) -> float:
    """Return net profit. OBO refunds added bets on dealer natural, even busts.

    For an OBO split round, allocate original_wager=1 to one hand and 0 to
    subsequent hands. The aggregate round loss on dealer blackjack is then -1.
    ``doubled`` is metadata only: pass wager=2 to represent a doubled wager.
    """
    if wager <= 0 or not math.isfinite(wager) or not 0 <= original_wager <= wager:
        raise ValueError("wager must be positive and original_wager within [0, wager]")
    cards, bank = tuple(player), tuple(dealer)
    player_bj = is_blackjack(cards, from_split=from_split)
    dealer_bj = is_blackjack(bank)
    if surrendered and rules.surrender == "early":
        return -.5 * wager
    if dealer_bj:
        if player_bj:
            return 0.0
        loss = original_wager if rules.enhc and rules.enhc_loss == "original" else wager
        return -float(loss)
    if surrendered:
        if rules.surrender == "none":
            raise ValueError("surrender is disabled")
        return -.5 * wager
    if player_bj:
        return rules.blackjack_payout * wager
    total, _ = hand_value(cards)
    bank_total, _ = hand_value(bank)
    if total > 21:
        return -float(wager)
    if bank_total > 21 or total > bank_total:
        return float(wager)
    if total == bank_total:
        return 0.0
    return -float(wager)


def insurance_settle(dealer: Iterable[str | int], *, insurance_wager: float = .5) -> float:
    if insurance_wager < 0 or not math.isfinite(insurance_wager):
        raise ValueError("insurance wager must be finite and nonnegative")
    return (2 if is_blackjack(dealer) else -1) * insurance_wager
