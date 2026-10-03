"""Seeded, finite-shoe blackjack with an auditable public information boundary."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import csv
import io
import json
import math
import random
import uuid
from typing import Any

from .engine import Rules, card_rank, hand_value, settle

RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS = ("S", "H", "D", "C")


def hilo(rank: str) -> int:
    value = card_rank(rank)
    return 1 if 2 <= value <= 6 else -1 if value in (1, 10) else 0


@dataclass(frozen=True)
class Card:
    id: str
    rank: str
    suit: str

    def public(self, exposed: bool = True) -> dict:
        return asdict(self) | {"face_down": False} if exposed else {"id": self.id, "face_down": True}


@dataclass
class Hand:
    cards: list[Card]
    bet: float
    original_wager: float
    status: str = "active"
    from_split: bool = False
    split_aces: bool = False
    profit: float | None = None

    @property
    def ranks(self) -> list[str]:
        return [card.rank for card in self.cards]

    @property
    def value(self) -> tuple[int, bool]:
        return hand_value(self.ranks)

    def public(self) -> dict:
        total, soft = self.value
        return {"cards": [card.public() for card in self.cards], "bet": self.bet,
                "status": self.status, "from_split": self.from_split,
                "split_aces": self.split_aces, "total": total, "soft": soft,
                "natural": len(self.cards) == 2 and total == 21 and not self.from_split,
                "profit": self.profit}


class Shoe:
    def __init__(self, decks: int, rng: random.Random):
        self.decks = decks
        self.rng = rng
        self.generation = 0
        self.cards: list[Card] = []
        self.initial_counts = (0,) * 10
        self.id = ""
        self.shuffle()

    def shuffle(self) -> None:
        self.generation += 1
        self.id = f"shoe-{self.generation}"
        self.cards = [Card(f"{self.id}-{uuid.UUID(int=self.rng.getrandbits(128)).hex}", rank, suit)
                      for deck in range(self.decks) for suit in SUITS for rank in RANKS]
        self.rng.shuffle(self.cards)
        self.initial_counts = (4 * self.decks,) * 9 + (16 * self.decks,)

    def load(self, ranks: list[str]) -> None:
        """Install an ordered fixture. The first item will be dealt first."""
        self.generation += 1
        self.id = f"fixture-{self.generation}"
        cards = [Card(f"{self.id}-{i}", rank, SUITS[i % 4]) for i, rank in enumerate(ranks)]
        self.cards = list(reversed(cards))
        counts = Counter(card_rank(card.rank) for card in cards)
        self.initial_counts = tuple(counts.get(i, 0) for i in range(1, 11))

    def draw(self) -> Card:
        if not self.cards:
            raise ValueError("The shoe is exhausted; start a new shoe before dealing another round.")
        return self.cards.pop()


class BlackjackSession:
    def __init__(self, rules: Rules | None = None, seed: int = 42, session_id: str | None = None,
                 bankroll: float = 1000.0):
        self.rules = rules or Rules()
        self.seed = seed
        self.id = session_id or str(uuid.uuid4())
        self.rng = random.Random(seed)
        self.shoe = Shoe(self.rules.decks, self.rng)
        self.bankroll = float(bankroll)
        self.initial_bankroll = self.bankroll
        self.events: list[dict] = []
        self.seen: dict[str, Card] = {}
        self.running_count = 0
        self.round_id = 0
        self.phase = "ready"
        self.hands: list[Hand] = []
        self.dealer: list[Card] = []
        self.hole_revealed = False
        self.peek_resolved = False
        self.active_hand: int | None = None
        self.insurance = {"offered": False, "taken": False, "bet": 0.0, "profit": 0.0}
        self.round_profit = 0.0
        self.total_profit = 0.0
        self._emit("session_created", {"rules": asdict(self.rules), "seed": seed,
                                       "bankroll": bankroll, "session_id": self.id})
        self._emit("shoe_started", {"shoe_id": self.shoe.id, "decks": self.rules.decks})

    def _emit(self, kind: str, payload: dict) -> dict:
        event = {"seq": len(self.events), "kind": kind, "round_id": self.round_id,
                 "payload": payload}
        self.events.append(event)
        return event

    def _decision_ready(self) -> None:
        if self.phase != "settled":
            self._emit("decision_ready", {"phase": self.phase, "active_hand": self.active_hand})

    def _expose(self, card: Card, zone: str, hand_index: int | None = None) -> None:
        if card.id in self.seen:
            return
        self.seen[card.id] = card
        self.running_count += hilo(card.rank)
        self._emit("card_exposed", {"card": card.public(), "zone": zone,
                                    "hand_index": hand_index, "running_count": self.running_count})

    def _draw(self, zone: str, hand_index: int | None = None, hidden: bool = False) -> Card:
        card = self.shoe.draw()
        if hidden:
            self._emit("card_hidden", {"card_id": card.id, "zone": zone})
        else:
            self._expose(card, zone, hand_index)
        return card

    def _reveal(self) -> None:
        self.hole_revealed = True
        for card in self.dealer:
            self._expose(card, "dealer")

    def new_shoe(self) -> dict:
        if self.phase in ("player", "insurance", "early_surrender"):
            raise ValueError("Finish the current round before shuffling.")
        self._emit("shuffle_requested", {})
        self.shoe.shuffle()
        self.seen.clear()
        self.running_count = 0
        self._emit("shoe_started", {"shoe_id": self.shoe.id, "decks": self.rules.decks})
        return self.snapshot()

    def set_shoe(self, ranks: list[str]) -> None:
        if self.phase in ("player", "insurance", "early_surrender"):
            raise ValueError("Cannot replace the shoe during a round.")
        for rank in ranks:
            card_rank(rank)
        self._emit("shoe_fixture", {"ranks": list(ranks)})
        self.shoe.load(ranks)
        self.seen.clear()
        self.running_count = 0

    def deal(self, bet: float = 1.0) -> dict:
        if self.phase in ("player", "insurance", "early_surrender"):
            raise ValueError("Finish the current round first.")
        if not math.isfinite(bet) or not 0 < bet <= self.bankroll:
            raise ValueError("Bet must be positive and within the bankroll.")
        total_cards = sum(self.shoe.initial_counts)
        if not self.shoe.id.startswith("fixture") and (
            len(self.shoe.cards) < 20 or 1 - len(self.shoe.cards) / total_cards >= self.rules.penetration
        ):
            self.new_shoe()
        required = 3 if self.rules.enhc else 4
        if len(self.shoe.cards) < required:
            raise ValueError("Insufficient cards to start the round.")
        self.round_id += 1
        self._emit("round_started", {"bet": float(bet)})
        self.round_profit = 0.0
        self.hole_revealed = False
        self.peek_resolved = False
        self.insurance = {"offered": False, "taken": False, "bet": 0.0, "profit": 0.0}
        self.hands = [Hand([], float(bet), float(bet))]
        self.dealer = []
        self.active_hand = 0
        self.phase = "player"
        self.hands[0].cards.append(self._draw("player", 0))
        self.dealer.append(self._draw("dealer"))
        self.hands[0].cards.append(self._draw("player", 0))
        if not self.rules.enhc:
            self.dealer.append(self._draw("dealer", hidden=True))
        if self.rules.surrender == "early" and self.hands[0].value[0] != 21:
            self.phase = "early_surrender"
        else:
            self._initial_decisions()
        self._decision_ready()
        return self.snapshot()

    def _initial_decisions(self) -> None:
        upcard = card_rank(self.dealer[0].rank)
        if upcard == 1:
            self.insurance["offered"] = True
            self.phase = "insurance"
        elif upcard == 10 and self.rules.dealer_peek and not self.rules.enhc:
            self._peek()
        elif self.hands[0].value[0] == 21:
            self.hands[0].status = "stood"
            self._finish_round()

    def _dealer_blackjack(self) -> bool:
        return len(self.dealer) == 2 and hand_value([c.rank for c in self.dealer])[0] == 21

    def _peek(self) -> None:
        self.peek_resolved = True
        blackjack = self._dealer_blackjack()
        self._emit("dealer_peek", {"blackjack": blackjack})
        if blackjack:
            self._finish_round()
        elif self.hands[0].value[0] == 21:
            self.hands[0].status = "stood"
            self._finish_round()

    def _can_split(self, hand: Hand) -> bool:
        if len(hand.cards) != 2 or card_rank(hand.cards[0].rank) != card_rank(hand.cards[1].rank):
            return False
        if len(self.hands) >= self.rules.max_split_hands:
            return False
        if hand.from_split and not self.rules.resplit:
            return False
        if hand.split_aces and not self.rules.resplit_aces:
            return False
        return self._committed() + hand.bet <= self.bankroll

    def _committed(self) -> float:
        return sum(hand.bet for hand in self.hands) + self.insurance["bet"]

    def available_actions(self) -> list[str]:
        if self.phase in ("dealing", "resolving"):
            return []
        if self.phase in ("ready", "settled"):
            return ["deal", "shuffle"]
        if self.phase == "insurance":
            actions = ["decline_insurance"]
            if self._committed() + self.hands[0].bet / 2 <= self.bankroll:
                actions.insert(0, "insurance")
            return actions
        if self.phase == "early_surrender":
            return ["surrender", "continue"]
        if self.active_hand is None:
            return []
        hand = self.hands[self.active_hand]
        total, _ = hand.value
        ace_locked = hand.split_aces and not self.rules.hit_split_aces
        actions = ["stand"]
        if total < 21 and not ace_locked:
            actions.insert(0, "hit")
        if len(hand.cards) == 2 and not ace_locked and total < 21:
            double_rule = self.rules.double_rule
            double_allowed = (double_rule == "any" or double_rule in ("9-11", "9_11") and 9 <= total <= 11
                              or double_rule in ("10-11", "10_11") and 10 <= total <= 11)
            if double_allowed and (not hand.from_split or self.rules.double_after_split):
                if self._committed() + hand.bet <= self.bankroll:
                    actions.append("double")
        if self._can_split(hand):
            actions.append("split")
        if len(hand.cards) == 2 and not hand.from_split and self.rules.surrender == "late":
            actions.append("surrender")
        return actions

    def action(self, action: str, amount: float | None = None) -> dict:
        if action == "deal":
            return self.deal(amount or 1.0)
        if action == "shuffle":
            return self.new_shoe()
        if action not in self.available_actions():
            raise ValueError(f"Action {action!r} is not legal in the current state.")
        self._emit("player_action", {"action": action, "amount": amount,
                                     "hand_index": self.active_hand})
        if self.phase == "early_surrender":
            if action == "surrender":
                self.hands[0].status = "surrendered"
                self._finish_round()
            else:
                self.phase = "player"
                self._initial_decisions()
            self._decision_ready()
            return self.snapshot()
        if action in ("insurance", "decline_insurance"):
            self.insurance["taken"] = action == "insurance"
            self.insurance["bet"] = self.hands[0].bet / 2 if action == "insurance" else 0.0
            self.phase = "player"
            if self.rules.dealer_peek and not self.rules.enhc:
                self._peek()
            elif self.hands[0].value[0] == 21:
                self.hands[0].status = "stood"
                self._finish_round()
            self._decision_ready()
            return self.snapshot()
        assert self.active_hand is not None
        hand_index = self.active_hand
        hand = self.hands[hand_index]
        if action == "stand":
            hand.status = "stood"
        elif action == "surrender":
            hand.status = "surrendered"
        elif action in ("hit", "double"):
            if action == "double":
                hand.bet *= 2
            hand.cards.append(self._draw("player", hand_index))
            total, _ = hand.value
            if total > 21:
                hand.status = "busted"
            elif total == 21 or action == "double":
                hand.status = "stood"
        elif action == "split":
            is_aces = card_rank(hand.cards[0].rank) == 1
            first = Hand([hand.cards[0]], hand.bet, hand.original_wager,
                         from_split=True, split_aces=is_aces)
            second = Hand([hand.cards[1]], hand.bet, 0.0, status="waiting", from_split=True, split_aces=is_aces)
            self.hands[hand_index:hand_index + 1] = [first, second]
            first.cards.append(self._draw("player", hand_index))
            for item in (first,):
                if item.value[0] == 21:
                    item.status = "stood"
                elif is_aces and not self.rules.hit_split_aces and not self._can_split(item):
                    item.status = "stood"
        self._advance()
        self._decision_ready()
        return self.snapshot()

    def _advance(self) -> None:
        self.active_hand = next((i for i, hand in enumerate(self.hands) if hand.status in ("active", "waiting")), None)
        if self.active_hand is not None:
            hand = self.hands[self.active_hand]
            if hand.status == "waiting":
                hand.cards.append(self._draw("player", self.active_hand))
                hand.status = "active"
                if hand.value[0] == 21 or hand.split_aces and not self.rules.hit_split_aces and not self._can_split(hand):
                    hand.status = "stood"
                    return self._advance()
        if self.active_hand is None:
            self._finish_round()

    def _finish_round(self) -> None:
        if self.phase == "settled":
            return
        if self.rules.enhc and len(self.dealer) == 1:
            self.dealer.append(self._draw("dealer"))
        self._reveal()
        blackjack = self._dealer_blackjack()
        needs_dealer = any(hand.status != "busted" and hand.status != "surrendered"
                           and not (len(hand.cards) == 2 and hand.value[0] == 21 and not hand.from_split)
                           for hand in self.hands)
        if not blackjack and needs_dealer:
            while True:
                total, soft = hand_value([c.rank for c in self.dealer])
                if total > 17 or total == 17 and not (soft and self.rules.hit_soft17):
                    break
                self.dealer.append(self._draw("dealer"))
        self.insurance["profit"] = self.insurance["bet"] * (2 if blackjack else -1)
        for hand in self.hands:
            hand.profit = settle(hand.ranks, [card.rank for card in self.dealer], self.rules,
                                 wager=hand.bet, from_split=hand.from_split,
                                 surrendered=hand.status == "surrendered",
                                 doubled=hand.bet > hand.original_wager and len(hand.cards) == 3,
                                 original_wager=hand.original_wager)
            if hand.status == "active":
                hand.status = "stood"
        self.round_profit = sum(hand.profit or 0.0 for hand in self.hands) + self.insurance["profit"]
        self.total_profit += self.round_profit
        self.bankroll += self.round_profit
        self.phase = "settled"
        self.active_hand = None
        self._emit("round_settled", {"profit": self.round_profit, "bankroll": self.bankroll,
                                     "hands": [hand.public() for hand in self.hands],
                                     "dealer": [card.public() for card in self.dealer],
                                     "insurance": dict(self.insurance)})

    def counts(self) -> tuple[int, ...]:
        removed = Counter(card_rank(card.rank) for card in self.seen.values())
        return tuple(count - removed.get(i, 0) for i, count in enumerate(self.shoe.initial_counts, 1))

    def decision_state(self) -> dict:
        if self.phase not in ("player", "early_surrender") or self.active_hand is None:
            raise ValueError("No player decision is active.")
        actions = self.available_actions()
        if self.phase == "early_surrender":
            from .engine import legal_actions
            actions = legal_actions(self.hands[self.active_hand].ranks, self.rules, peek_resolved=False)
        hand = self.hands[self.active_hand]
        base_wager = sum(item.original_wager for item in self.hands)
        completed = [{"cards": item.ranks, "wager": item.bet / base_wager,
                      "original_wager": item.original_wager / base_wager,
                      "from_split": item.from_split, "surrendered": item.status == "surrendered"}
                     for i, item in enumerate(self.hands) if i != self.active_hand and item.status != "waiting"]
        pending = [item.ranks for item in self.hands if item.status == "waiting"]
        return {"player": hand.ranks, "dealer": self.dealer[0].rank,
                "counts": list(self.counts()), "can_double": "double" in actions,
                "can_split": "split" in actions, "can_surrender": "surrender" in actions,
                "peeked": self.peek_resolved, "from_split": hand.from_split,
                "split_aces": hand.split_aces, "split_hands": len(self.hands),
                "completed_hands": completed, "pending_hands": pending,
                "information": "exposed cards only; pool includes unobserved hole card"}

    def snapshot(self) -> dict:
        counts = self.counts()
        unknown = sum(counts)
        decks_remaining = len(self.shoe.cards) / 52
        visible_dealer = self.hole_revealed or len(self.dealer) == 1
        dealer_value = hand_value([card.rank for card in self.dealer]) if visible_dealer else (None, None)
        return {"session_id": self.id, "seed": self.seed, "rules": asdict(self.rules), "phase": self.phase,
                "round_id": self.round_id, "active_hand": self.active_hand,
                "hands": [hand.public() for hand in self.hands],
                "dealer": {"cards": [card.public(i == 0 or self.hole_revealed)
                                       for i, card in enumerate(self.dealer)],
                           "total": dealer_value[0], "soft": dealer_value[1]},
                "shoe": {"id": self.shoe.id, "decks": self.rules.decks,
                         "total": sum(self.shoe.initial_counts), "remaining": len(self.shoe.cards),
                         "seen": len(self.seen), "counts": list(counts),
                         "unknown_cards": unknown, "running_count": self.running_count,
                         "true_count": self.running_count / decks_remaining if decks_remaining else 0.0,
                         "true_count_denominator": "physical_remaining_cards",
                         "true_count_denominator_cards": len(self.shoe.cards), "decks_remaining": decks_remaining,
                         "penetration": 1 - len(self.shoe.cards) / max(1, sum(self.shoe.initial_counts))},
                "insurance": dict(self.insurance), "available_actions": self.available_actions(),
                "round_profit": self.round_profit, "total_profit": self.total_profit,
                "bankroll": self.bankroll, "events_count": len(self.events),
                "peek_resolved": self.peek_resolved}

    def ground_truth(self) -> dict:
        """Explicit debugging endpoint. Never feed this payload into perception or analysis."""
        return {"debug_only": True, "session_id": self.id, "shoe_id": self.shoe.id,
                "remaining_cards": [asdict(card) for card in reversed(self.shoe.cards)],
                "dealer": [asdict(card) for card in self.dealer],
                "hands": [[asdict(card) for card in hand.cards] for hand in self.hands]}

    def export(self, format: str = "json") -> str:
        if format == "json":
            return json.dumps({"schema": "bjlab.events.v1", "events": self.events}, indent=2)
        if format != "csv":
            raise ValueError("Export format must be json or csv.")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=("seq", "kind", "round_id", "payload"))
        writer.writeheader()
        writer.writerows(dict(event, payload=json.dumps(event["payload"])) for event in self.events)
        return stream.getvalue()

    @classmethod
    def replay(cls, events: list[dict], to_index: int | None = None) -> "BlackjackSession":
        if not events or events[0].get("kind") != "session_created":
            raise ValueError("Replay requires a session_created event first.")
        source = events if to_index is None else events[:to_index + 1]
        payload = source[0]["payload"]
        canonical = cls(Rules(**payload["rules"]), payload["seed"], payload["session_id"], payload["bankroll"])
        for event in source[1:]:
            kind, data = event["kind"], event["payload"]
            if kind == "shoe_fixture":
                canonical.set_shoe(data["ranks"])
            elif kind == "shuffle_requested":
                canonical.new_shoe()
            elif kind == "round_started":
                canonical.deal(data["bet"])
            elif kind == "player_action":
                canonical.action(data["action"], data.get("amount"))
        if canonical.events[:len(source)] != source:
            raise ValueError("Replay audit failed: event prefix differs from deterministic reconstruction.")
        if len(canonical.events) == len(source):
            return canonical

        # Reduce the exact event prefix. Command execution above audits facts,
        # but its future facts are never copied into the returned state.
        session = cls(Rules(**payload["rules"]), payload["seed"], payload["session_id"], payload["bankroll"])
        pending_action = None
        for event in source[1:]:
            kind, data = event["kind"], event["payload"]
            session.round_id = event["round_id"]
            if kind == "shoe_fixture":
                session.shoe.load(data["ranks"])
                session.seen.clear(); session.running_count = 0
            elif kind == "shoe_started" and session.shoe.id != data["shoe_id"]:
                session.shoe.shuffle()
                session.seen.clear(); session.running_count = 0
            elif kind == "round_started":
                session.hands = [Hand([], data["bet"], data["bet"])]
                session.dealer = []
                session.hole_revealed = False
                session.peek_resolved = False
                session.active_hand = 0
                session.round_profit = 0
                session.insurance = {"offered": False, "taken": False, "bet": 0.0, "profit": 0.0}
                session.phase = "dealing"
            elif kind == "player_action":
                pending_action = data["action"]
                session.phase = "resolving"
                index = data.get("hand_index")
                hand = session.hands[index] if index is not None else session.hands[0]
                if pending_action == "split":
                    aces = card_rank(hand.cards[0].rank) == 1
                    session.hands[index:index + 1] = [
                        Hand([hand.cards[0]], hand.bet, hand.original_wager, from_split=True, split_aces=aces),
                        Hand([hand.cards[1]], hand.bet, 0, status="waiting", from_split=True, split_aces=aces)]
                elif pending_action == "double":
                    hand.bet *= 2
                elif pending_action == "stand":
                    hand.status = "stood"
                elif pending_action == "surrender":
                    hand.status = "surrendered"
                elif pending_action in ("insurance", "decline_insurance"):
                    session.insurance["offered"] = True
                    session.insurance["taken"] = pending_action == "insurance"
                    session.insurance["bet"] = hand.bet / 2 if pending_action == "insurance" else 0
            elif kind in ("card_hidden", "card_exposed"):
                identity = data["card_id"] if kind == "card_hidden" else data["card"]["id"]
                card = next((item for item in session.dealer if item.id == identity), None)
                existing = card is not None
                if card is None:
                    location = next(i for i, item in enumerate(session.shoe.cards) if item.id == identity)
                    card = session.shoe.cards.pop(location)
                if kind == "card_hidden":
                    session.dealer.append(card)
                else:
                    session.seen[card.id] = card
                    session.running_count = data["running_count"]
                    if data["zone"] == "dealer":
                        if existing:
                            session.hole_revealed = True
                        else:
                            session.dealer.append(card)
                            if len(session.dealer) >= 2:
                                session.hole_revealed = True
                    else:
                        hand = session.hands[data["hand_index"]]
                        hand.cards.append(card)
                        if hand.status == "waiting":
                            hand.status = "active"
                        total, _ = hand.value
                        if total > 21:
                            hand.status = "busted"
                        elif total == 21 or pending_action == "double":
                            hand.status = "stood"
                        elif hand.split_aces and not session.rules.hit_split_aces and len(hand.cards) >= 2 and not session._can_split(hand):
                            hand.status = "stood"
            elif kind == "dealer_peek":
                session.peek_resolved = True
            elif kind == "decision_ready":
                session.phase = data["phase"]
                session.active_hand = data["active_hand"]
                session.insurance["offered"] = session.phase == "insurance" or session.insurance["offered"]
                pending_action = None
            elif kind == "round_settled":
                session.phase = "settled"
                session.active_hand = None
                session.hole_revealed = True
                session.round_profit = data["profit"]
                session.total_profit += data["profit"]
                session.bankroll = data["bankroll"]
                session.insurance = dict(data["insurance"])
                for hand, settled in zip(session.hands, data["hands"]):
                    hand.profit = settled["profit"]
                    hand.status = settled["status"]
        session.events = source.copy()
        return session
