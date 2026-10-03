"""Validated immutable event streams and deterministic shoe reconstruction.

Only append operations change the journal. Corrections are new events; historic
records never change. Unknown cards are physical cards, not guessed ranks.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
from pathlib import Path
import time
from threading import RLock
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS = ("S", "H", "D", "C")
SUIT_ALIASES = {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}
KINDS = frozenset({"NEW_SHOE", "ROUND_STARTED", "ROUND_ENDED", "CARD_CONFIRMED",
                   "CARD_REVEALED", "STATE_CORRECTION", "CARD_MOVED", "TRACK_LOST",
                   "TRACK_REACQUIRED", "RULES_CHANGED", "ACTION_TAKEN", "ROUND_RESULT",
                   "SHUFFLE_OBSERVED", "MANUAL_ANNOTATION", "STATE_UNCERTAIN", "STATE_REVIEWED"})


class EventValidationError(ValueError):
    """An event would violate the public state or physical card conservation."""


def normalize_rank(rank: Any) -> str | None:
    if rank is None or rank in ("?", "UNKNOWN", "BACK"):
        return None
    value = str(rank).upper().strip()
    if value == "T":
        value = "10"
    if value not in RANKS:
        raise EventValidationError(f"Invalid card rank: {rank!r}")
    return value


def normalize_suit(suit: Any) -> str | None:
    if suit is None or suit in ("?", "UNKNOWN"):
        return None
    value = SUIT_ALIASES.get(str(suit), str(suit).upper().strip())
    if value not in SUITS:
        raise EventValidationError(f"Invalid card suit: {suit!r}")
    return value


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise EventValidationError("Payload must be finite JSON data") from exc


@dataclass(frozen=True)
class Event:
    index: int
    kind: str
    timestamp: float
    payload_json: str
    previous_hash: str
    digest: str
    version: int = SCHEMA_VERSION

    @property
    def payload(self) -> dict[str, Any]:
        # Fresh values prevent callers from mutating a journal entry in place.
        return json.loads(self.payload_json)

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "index": self.index, "kind": self.kind,
                "timestamp": self.timestamp, "payload": self.payload,
                "previous_hash": self.previous_hash, "digest": self.digest}


def _digest(index: int, kind: str, timestamp: float, payload: Mapping[str, Any],
            previous_hash: str) -> str:
    body = {"version": SCHEMA_VERSION, "index": index, "kind": kind,
            "timestamp": timestamp, "payload": payload, "previous_hash": previous_hash}
    return sha256(_canonical(body).encode("utf-8")).hexdigest()


@dataclass
class ReplayState:
    shoe_id: str | None = None
    decks: int | None = None
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)
    round_id: str | None = None
    rules: dict[str, Any] = field(default_factory=dict)
    integrity_issues: dict[str, str] = field(default_factory=dict)
    event_index: int = -1
    annotations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def counted_ids(self) -> set[str]:
        return {cid for cid, card in self.cards.items() if card.get("rank") is not None}

    @property
    def known_rank_counts(self) -> dict[str, int]:
        counts = Counter(card["rank"] for card in self.cards.values() if card.get("rank"))
        return {rank: counts[rank] for rank in RANKS}

    @property
    def ranks(self) -> dict[str, int]:
        """Observed 13-rank counts; face cards remain distinct for suit integrity."""
        return self.known_rank_counts

    @property
    def hidden_count(self) -> int:
        return sum(card.get("rank") is None for card in self.cards.values())

    @property
    def composition_remaining(self) -> list[int] | None:
        """Ten-value informational pool, including unknown dealt/hidden cards.

        This is NOT the exact physical draw pile while hidden cards exist. A
        solver must condition on those hidden draws and dealer peek evidence.
        """
        if self.decks is None:
            return None
        counts = self.known_rank_counts
        return [4 * self.decks - counts[r] for r in RANKS[:9]] + [
            16 * self.decks - sum(counts[r] for r in ("10", "J", "Q", "K"))]

    @property
    def physical_remaining(self) -> int | None:
        return None if self.decks is None else 52 * self.decks - len(self.cards)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "event_index": self.event_index,
                "shoe_id": self.shoe_id, "decks": self.decks, "round_id": self.round_id,
                "cards": json.loads(_canonical(self.cards)),
                "counted_ids": sorted(self.counted_ids),
                "known_rank_counts": self.known_rank_counts,
                "composition_remaining": self.composition_remaining,
                "physical_remaining": self.physical_remaining,
                "hidden_count": self.hidden_count,
                "composition_semantics": "informational_pool_includes_hidden_cards",
                "integrity_issues": dict(self.integrity_issues), "rules": dict(self.rules)}


def _validate_conservation(state: ReplayState) -> None:
    if state.decks is None:
        return
    if len(state.cards) > 52 * state.decks:
        raise EventValidationError("More physical cards than the configured shoe")
    counts = state.known_rank_counts
    if any(count > 4 * state.decks for count in counts.values()):
        raise EventValidationError("Known rank multiplicity exceeds shoe capacity")
    suits = Counter((card.get("rank"), card.get("suit")) for card in state.cards.values()
                    if card.get("rank") and card.get("suit"))
    if any(count > state.decks for count in suits.values()):
        raise EventValidationError("Known rank/suit multiplicity exceeds shoe capacity")


def _apply(state: ReplayState, event: Event) -> None:
    p = event.payload
    kind = event.kind
    if kind == "NEW_SHOE":
        decks = p.get("decks")
        if decks is not None and (type(decks) is not int or not 1 <= decks <= 16):
            raise EventValidationError("decks must be an integer from 1 to 16, or null")
        state.shoe_id = str(p.get("shoe_id") or f"shoe-{event.index}")
        state.decks = decks
        state.cards = {}
        state.integrity_issues = {}
        state.round_id = None
    elif kind == "ROUND_STARTED":
        if state.shoe_id is None:
            raise EventValidationError("Start a shoe before a round")
        if not p.get("round_id"):
            raise EventValidationError("ROUND_STARTED requires round_id")
        state.round_id = str(p["round_id"])
        for card in state.cards.values():
            card["on_table"] = False
    elif kind == "ROUND_ENDED":
        rid = str(p.get("round_id") or state.round_id)
        for card in state.cards.values():
            if str(card.get("round_id")) == rid:
                card["on_table"] = False
    elif kind == "CARD_CONFIRMED":
        if state.shoe_id is None:
            raise EventValidationError("Start a shoe before confirming cards")
        cid = str(p.get("card_id") or "")
        if not cid:
            raise EventValidationError("CARD_CONFIRMED requires card_id")
        if cid in state.cards:
            raise EventValidationError(f"Card {cid} was already dealt; use a correction")
        rank, suit = normalize_rank(p.get("rank")), normalize_suit(p.get("suit"))
        if rank is None and suit is not None:
            raise EventValidationError("An unknown card cannot have a confirmed suit")
        state.cards[cid] = {**p, "card_id": cid, "rank": rank, "suit": suit,
                            "round_id": p.get("round_id", state.round_id), "on_table": True,
                            "first_event": event.index, "last_event": event.index}
    elif kind in {"CARD_REVEALED", "STATE_CORRECTION", "CARD_MOVED"}:
        cid = str(p.get("card_id") or "")
        if cid not in state.cards:
            raise EventValidationError(f"Cannot change unknown logical card {cid}")
        card = state.cards[cid]
        if kind == "STATE_CORRECTION":
            if not str(p.get("reason") or "").strip():
                raise EventValidationError("A correction requires an audit reason")
            if p.get("retract"):
                del state.cards[cid]
                state.integrity_issues.pop(cid, None)
                state.annotations.append(event.to_dict())
                state.event_index = event.index
                _validate_conservation(state)
                return
        if kind == "CARD_REVEALED" and card.get("rank") is not None:
            raise EventValidationError("Only a previously hidden card can be revealed")
        if "rank" in p:
            card["rank"] = normalize_rank(p["rank"])
        if "suit" in p:
            card["suit"] = normalize_suit(p["suit"])
        if kind == "CARD_REVEALED" and card.get("rank") is None:
            raise EventValidationError("A reveal requires a known rank")
        if card.get("rank") is None and card.get("suit") is not None:
            raise EventValidationError("An unknown card cannot have a confirmed suit")
        card["face_down"] = card.get("rank") is None
        for key in ("zone", "bbox", "score", "round_id"):
            if key in p:
                card[key] = p[key]
        card["last_event"] = event.index
        if kind == "STATE_CORRECTION":
            state.annotations.append(event.to_dict())
            state.integrity_issues.pop(cid, None)
    elif kind == "TRACK_LOST":
        cid = str(p.get("card_id") or "")
        if cid not in state.cards:
            raise EventValidationError("TRACK_LOST requires an existing card")
        state.integrity_issues[cid] = str(p.get("reason") or "observation gap")
    elif kind == "TRACK_REACQUIRED":
        state.integrity_issues.pop(str(p.get("card_id")), None)
    elif kind == "STATE_UNCERTAIN":
        issue_id = str(p.get("issue_id") or "uncertain")
        state.integrity_issues[issue_id] = str(p.get("reason") or "unresolved state uncertainty")
    elif kind == "STATE_REVIEWED":
        if not p.get("reason"):
            raise EventValidationError("A reviewed issue requires an audit reason")
        state.integrity_issues.pop(str(p.get("issue_id")), None)
    elif kind == "RULES_CHANGED":
        state.rules = dict(p.get("rules", p))
    else:
        state.annotations.append(event.to_dict())
    state.event_index = event.index
    _validate_conservation(state)


class EventLog:
    """Append-only journal with hash chain, schema checks and atomic validation."""
    def __init__(self, events: Iterable[Event] = ()) -> None:
        self._lock = RLock()
        self._events: list[Event] = []
        self._state = ReplayState()
        for event in events:
            self._accept(event)

    @property
    def events(self) -> tuple[Event, ...]:
        with self._lock:
            return tuple(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def _accept(self, event: Event) -> None:
        if event.version != SCHEMA_VERSION or event.kind not in KINDS:
            raise EventValidationError("Unsupported event schema version or kind")
        previous = self._events[-1].digest if self._events else "0" * 64
        if event.index != len(self._events) or event.previous_hash != previous:
            raise EventValidationError("Event indices or hash chain are discontinuous")
        if not math.isfinite(event.timestamp) or event.timestamp < 0:
            raise EventValidationError("Timestamp must be finite and nonnegative")
        if self._events and event.timestamp < self._events[-1].timestamp:
            raise EventValidationError("Event time must be monotonic")
        if not isinstance(event.payload, dict):
            raise EventValidationError("Event payload must be an object")
        if _digest(event.index, event.kind, event.timestamp, event.payload, previous) != event.digest:
            raise EventValidationError("Event digest does not match its content")
        state = deepcopy(self._state)
        _apply(state, event)  # Validate candidate before changing authoritative data.
        self._events.append(event)
        self._state = state

    def append(self, kind: str, payload: Mapping[str, Any] | None = None,
               timestamp: float | None = None) -> Event:
        with self._lock:
            stamp = time.time() if timestamp is None else float(timestamp)
            p = dict(payload or {})
            previous = self._events[-1].digest if self._events else "0" * 64
            event = Event(len(self._events), str(kind), stamp, _canonical(p), previous,
                          _digest(len(self._events), str(kind), stamp, p, previous))
            self._accept(event)
            return event

    def replay(self, to_index: int | None = None) -> ReplayState:
        """Replay through inclusive index; -1 is empty and None is latest."""
        with self._lock:
            if to_index is None:
                return deepcopy(self._state)
            events = tuple(self._events)
        if to_index < -1 or to_index >= len(events):
            raise IndexError("Replay index is outside the journal")
        state = ReplayState()
        for event in events:
            if to_index is not None and event.index > to_index:
                break
            _apply(state, event)
        return state

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "events": [e.to_dict() for e in self.events]}

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text("\n".join(_canonical(e.to_dict()) for e in self.events) + "\n",
                             encoding="utf-8")
        temporary.replace(target)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EventLog":
        if data.get("schema_version") != SCHEMA_VERSION:
            raise EventValidationError("Unsupported journal schema")
        log = cls()
        for record in data.get("events", []):
            try:
                event = Event(int(record["index"]), record["kind"], float(record["timestamp"]),
                              _canonical(record["payload"]), record["previous_hash"],
                              record["digest"], int(record["version"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise EventValidationError("Malformed event record") from exc
            log._accept(event)
        return log

    @classmethod
    def load(cls, path: str | Path) -> "EventLog":
        records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        return cls.from_dict({"schema_version": SCHEMA_VERSION, "events": records})
