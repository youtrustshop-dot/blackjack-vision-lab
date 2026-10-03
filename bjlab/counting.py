"""Interpretable counting baselines, event deduplication, and chart policies.

The chart and published-style count indices are BENCHMARK POLICIES, not an
exact composition solver. Rule-specific EV generation belongs in solver.py.
KO is unbalanced and uses its running count; it is not a true-count system.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping

from .engine import Rules, card_rank, hand_value, initial_counts, legal_actions


@dataclass(frozen=True, slots=True)
class CountingSystem:
    name: str
    tags: tuple[float, ...]
    balanced: bool = True

    def __post_init__(self):
        if len(self.tags) != 10 or any(not math.isfinite(x) for x in self.tags):
            raise ValueError("counting tags must be ten finite values in A,2,..,10 order")
        actual_balance = sum(self.tags[:9]) + 4 * self.tags[9]
        if self.balanced and abs(actual_balance) > 1e-12:
            raise ValueError("a balanced system must sum to zero over a complete deck")

    def tag(self, card: str | int) -> float:
        return self.tags[card_rank(card) - 1]

    def initial_count(self, decks: int) -> float:
        # Standard KO initial running count gives a pivot of +4 for any shoe.
        return 4 - 4 * decks if self.name == "KO" else 0


SYSTEMS = {
    "Hi-Lo": CountingSystem("Hi-Lo", (-1, 1, 1, 1, 1, 1, 0, 0, 0, -1)),
    "KO": CountingSystem("KO", (-1, 1, 1, 1, 1, 1, 1, 0, 0, -1), False),
    "Hi-Opt I": CountingSystem("Hi-Opt I", (0, 0, 1, 1, 1, 1, 0, 0, 0, -1)),
    "Hi-Opt II": CountingSystem("Hi-Opt II", (0, 1, 1, 2, 2, 1, 1, 0, 0, -2)),
    "Omega II": CountingSystem("Omega II", (0, 1, 1, 2, 2, 2, 1, 0, -1, -2)),
    "Zen": CountingSystem("Zen", (-1, 1, 1, 2, 2, 2, 1, 0, 0, -2)),
    "Wong Halves": CountingSystem("Wong Halves", (-1, .5, 1, 1, 1.5, 1, .5, 0, -.5, -1)),
}


def get_system(name: str | CountingSystem = "Hi-Lo") -> CountingSystem:
    if isinstance(name, CountingSystem):
        return name
    key = name.lower().replace("-", "").replace(" ", "").replace("_", "")
    aliases = {"hilo": "Hi-Lo", "ko": "KO", "hiopt1": "Hi-Opt I", "hiopti": "Hi-Opt I",
               "hiopt2": "Hi-Opt II", "hioptii": "Hi-Opt II", "omega2": "Omega II",
               "omegaii": "Omega II", "zen": "Zen", "zencount": "Zen",
               "wonghalves": "Wong Halves", "halves": "Wong Halves"}
    if key not in aliases:
        raise ValueError(f"unknown counting system: {name}")
    return SYSTEMS[aliases[key]]


def custom_system(name: str, tags: Mapping[str | int, float] | Iterable[float], *, balanced=True) -> CountingSystem:
    if isinstance(tags, Mapping):
        values = [0.] * 10
        for rank, value in tags.items():
            values[card_rank(rank) - 1] = float(value)
    else:
        values = list(tags)
    return CountingSystem(name, tuple(values), balanced)


def round_true_count(value: float, method: str = "truncate") -> float | int:
    if method in ("raw", "none"):
        return value
    if method in ("truncate", "trunc"):
        return math.trunc(value)
    if method == "floor":
        return math.floor(value)
    if method == "ceil":
        return math.ceil(value)
    if method == "nearest":
        # Documented half-away-from-zero; avoid Python's ties-to-even round.
        return math.floor(value + .5) if value >= 0 else math.ceil(value - .5)
    raise ValueError("rounding must be raw, truncate, floor, ceil, or nearest")


class CountingEngine:
    def __init__(self, decks: int = 6, system: str | CountingSystem = "Hi-Lo", rounding: str = "truncate"):
        self.starting_counts = initial_counts(decks)
        self.decks = decks
        self.system = get_system(system)
        round_true_count(0., rounding)
        self.rounding = rounding
        self.events: dict[str, int] = {}
        self.history: list[dict] = []
        self.running_count = self.system.initial_count(decks)
        self._auto_id = 0
        self.shoe_id = 1

    def observe(self, card: str | int, event_id: str | int | None = None) -> bool:
        rank = card_rank(card)
        if event_id is None:
            self._auto_id += 1
            event_id = f"automatic:{self._auto_id}"
        identity = str(event_id)
        if identity in self.events:
            if self.events[identity] != rank:
                raise ValueError("an existing event has another rank; use correct_event")
            return False
        if list(self.events.values()).count(rank) >= self.starting_counts[rank - 1]:
            raise ValueError("observations exceed the configured shoe's rank inventory")
        self.events[identity] = rank
        self.running_count += self.system.tag(rank)
        self.history.append({"event": "CARD_CONFIRMED", "id": identity, "rank": rank,
                             "running_count": self.running_count})
        return True

    update = observe
    add = observe

    def correct_event(self, event_id: str | int, card: str | int) -> None:
        identity = str(event_id)
        if identity not in self.events:
            raise ValueError("cannot correct an unknown event")
        old, new = self.events[identity], card_rank(card)
        if old == new:
            return
        if list(self.events.values()).count(new) >= self.starting_counts[new - 1]:
            raise ValueError("correction exceeds the configured shoe's rank inventory")
        self.events[identity] = new
        self.running_count += self.system.tag(new) - self.system.tag(old)
        self.history.append({"event": "STATE_CORRECTION", "id": identity, "old_rank": old,
                             "rank": new, "running_count": self.running_count})

    def remove_event(self, event_id: str | int) -> None:
        identity = str(event_id)
        if identity not in self.events:
            raise ValueError("cannot remove an unknown event")
        old = self.events.pop(identity)
        self.running_count -= self.system.tag(old)
        self.history.append({"event": "EVENT_RETRACTED", "id": identity, "old_rank": old,
                             "running_count": self.running_count})

    def reset(self, *, shoe_id: int | None = None) -> None:
        self.shoe_id = self.shoe_id + 1 if shoe_id is None else shoe_id
        self.events.clear()
        self.running_count = self.system.initial_count(self.decks)
        self.history.append({"event": "NEW_SHOE", "shoe_id": self.shoe_id,
                             "running_count": self.running_count})

    @property
    def remaining_counts(self) -> tuple[int, ...]:
        observed = list(self.events.values())
        return tuple(n - observed.count(rank) for rank, n in enumerate(self.starting_counts, 1))

    def true_count(self, cards_remaining: float | None = None, *, rounded: bool = False) -> float | int | None:
        if not self.system.balanced:
            return None
        size = sum(self.remaining_counts) if cards_remaining is None else cards_remaining
        if not math.isfinite(size) or size < 0:
            raise ValueError("cards_remaining must be finite and nonnegative")
        if size == 0:
            return None
        value = self.running_count / (size / 52)
        return round_true_count(value, self.rounding) if rounded else value

    def snapshot(self, cards_remaining: float | None = None) -> dict:
        size = sum(self.remaining_counts) if cards_remaining is None else cards_remaining
        return {"system": self.system.name, "balanced": self.system.balanced,
                "running_count": self.running_count, "true_count": self.true_count(size),
                "rounded_true_count": self.true_count(size, rounded=True), "rounding": self.rounding,
                "cards_observed": len(self.events), "cards_remaining": size,
                "decks_remaining": size / 52, "shoe_id": self.shoe_id,
                "remaining_counts": list(self.remaining_counts),
                "note": "KO uses its running count without true-count normalization." if not self.system.balanced else
                        "True count uses the supplied remaining-card estimate; unknown removals must be accounted for."}


CardCounter = CountingEngine


def basic_strategy(
    player: Iterable[str | int], dealer: str | int, rules: Rules | None = None,
    legal: Iterable[str] | None = None, *, from_split: bool = False, split_hands: int = 1,
    split_aces: bool = False,
) -> str:
    """Standard total-dependent chart baseline with common rule variations.

    This deliberately does not claim exactness for every shoe or exotic ruleset.
    Exact generated decisions use Solver on an explicitly defined fresh shoe.
    """
    rules = rules or Rules()
    cards = tuple(card_rank(c) for c in player)
    up = card_rank(dealer)
    total, soft = hand_value(cards)
    allowed = set(a.lower() for a in legal) if legal is not None else set(legal_actions(
        cards, rules, from_split=from_split, split_hands=split_hands, split_aces=split_aces))
    if not allowed:
        return "none"
    pair = len(cards) == 2 and cards[0] == cards[1]
    nohole_all = rules.enhc and rules.enhc_loss == "all"
    # H17 late surrender adds 15/17 and pair 8 versus ace to the standard chart.
    surrender = not soft and len(cards) == 2 and ((total == 16 and up in (9, 10, 1) and not pair)
                   or total == 15 and up == 10 or rules.hit_soft17 and up == 1 and total in (15, 17)
                   or rules.hit_soft17 and up == 1 and pair and cards[0] == 8)
    if rules.surrender == "early" and up == 1 and not soft and total in (5, 6, 7, 12, 13, 14, 15, 16, 17):
        surrender = True
    if surrender and "surrender" in allowed:
        return "surrender"
    if pair and "split" in allowed:
        rank = cards[0]
        do_split = rank in (1, 8) or (rank == 9 and up in (2, 3, 4, 5, 6, 8, 9))
        do_split |= rank == 7 and up in range(2, 8)
        do_split |= rank == 6 and up in range(2 if rules.double_after_split else 3, 7)
        do_split |= rank == 4 and rules.double_after_split and up in (5, 6)
        do_split |= rank in (2, 3) and up in range(2 if rules.double_after_split else 4, 8)
        if nohole_all and (rank == 8 and up in (10, 1) or rank == 1 and up == 1):
            do_split = False
        if do_split:
            return "split"
    if soft:
        double = (total in (13, 14) and up in (5, 6) or total in (15, 16) and up in (4, 5, 6)
                  or total == 17 and up in (3, 4, 5, 6)
                  or total == 18 and up in (2, 3, 4, 5, 6) and (up != 2 or rules.hit_soft17)
                  or total == 19 and up == 6 and rules.hit_soft17)
        if double and "double" in allowed:
            return "double"
        preferred = "stand" if total >= 19 or total == 18 and up in (2, 3, 4, 5, 6, 7, 8) else "hit"
    else:
        double = (total == 9 and up in range(2 if rules.decks <= 2 else 3, 7)
                  or total == 10 and up in range(2, 10)
                  or total == 11 and (up != 1 or rules.hit_soft17 or rules.decks <= 2))
        if nohole_all and up in (10, 1):
            double = False
        if double and "double" in allowed:
            return "double"
        preferred = "stand" if total >= 17 or total >= 13 and up in range(2, 7) or total == 12 and up in (4, 5, 6) else "hit"
    if preferred in allowed:
        return preferred
    return "stand" if "stand" in allowed else sorted(allowed)[0]


def hilo_strategy(
    player: Iterable[str | int], dealer: str | int, rules: Rules | None = None,
    true_count: float = 0, legal: Iterable[str] | None = None, *, from_split=False,
    split_hands=1, split_aces=False,
) -> str:
    """Hi-Lo research index baseline (common I18/Fab4 indices).

    Indices vary by rules, deck estimation and rounding. This benchmark uses
    the caller's count value, defaults to common multi-deck indices, and is not
    advertised as an EV-optimal policy across arbitrary configurations.
    """
    rules = rules or Rules()
    cards = tuple(card_rank(c) for c in player)
    up = card_rank(dealer)
    total, soft = hand_value(cards)
    allowed = set(a.lower() for a in legal) if legal is not None else set(legal_actions(
        cards, rules, from_split=from_split, split_hands=split_hands, split_aces=split_aces))
    baseline = basic_strategy(cards, up, rules, allowed, from_split=from_split,
                              split_hands=split_hands, split_aces=split_aces)
    if soft or rules.enhc or not math.isfinite(true_count):
        return baseline
    # A count index must not override an allowed baseline surrender for 16.
    if baseline == "surrender" and total == 16:
        return baseline
    surrender_indices = {(15, 10): 0, (15, 9): 2, (15, 1): 1, (14, 10): 3}
    if "surrender" in allowed and len(cards) == 2 and (total, up) in surrender_indices:
        if true_count >= surrender_indices[total, up]:
            return "surrender"
        if baseline == "surrender":
            return "hit" if "hit" in allowed else baseline
    if len(cards) == 2 and cards == (10, 10) and "split" in allowed:
        if up == 5 and true_count >= 5 or up == 6 and true_count >= 4:
            return "split"
    if baseline == "split":
        return baseline
    stand_indices = {(16, 10): 0, (15, 10): 4, (12, 3): 2, (12, 2): 3, (16, 9): 5,
                     (13, 2): -1, (12, 4): 0, (12, 5): -2, (12, 6): -1, (13, 3): -2}
    if (total, up) in stand_indices:
        choice = "stand" if true_count >= stand_indices[total, up] else "hit"
        if choice in allowed:
            return choice
    double_indices = {(10, 10): 4, (11, 1): 1, (9, 2): 1, (10, 1): 4, (9, 7): 3}
    if (total, up) in double_indices and true_count >= double_indices[total, up] and "double" in allowed:
        return "double"
    return baseline


def available_systems() -> list[dict]:
    return [{"name": system.name, "tags": list(system.tags), "balanced": system.balanced}
            for system in SYSTEMS.values()]
