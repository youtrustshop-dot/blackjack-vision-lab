import json
from dataclasses import FrozenInstanceError

import pytest
from hypothesis import given, strategies as st

from bjlab.events import EventLog, EventValidationError, RANKS, SUITS


def shoe(decks=1):
    log = EventLog()
    log.append("NEW_SHOE", {"decks": decks, "shoe_id": "test"}, 0)
    return log


def test_hidden_reveal_correction_replay_are_physical_conservation():
    log = shoe()
    log.append("ROUND_STARTED", {"round_id": "r1"}, 1)
    hidden = log.append("CARD_CONFIRMED", {"card_id": "hole", "rank": None, "suit": None}, 2)
    log.append("CARD_CONFIRMED", {"card_id": "player", "rank": "8", "suit": "H"}, 3)
    state = log.replay(hidden.index)
    assert state.hidden_count == 1
    assert state.physical_remaining == 51
    assert sum(state.composition_remaining) == 52
    log.append("CARD_REVEALED", {"card_id": "hole", "rank": "K", "suit": "S"}, 4)
    log.append("STATE_CORRECTION", {"card_id": "player", "rank": "9", "suit": "H",
                                   "reason": "reviewed original frame"}, 5)
    state = log.replay()
    assert state.physical_remaining == 50
    assert state.hidden_count == 0
    assert state.known_rank_counts["8"] == 0
    assert state.known_rank_counts["9"] == 1
    assert state.known_rank_counts["K"] == 1
    assert len(state.counted_ids) == 2
    assert state.cards["hole"]["face_down"] is False
    assert log.replay(3).known_rank_counts["8"] == 1
    assert log.replay(-1).shoe_id is None


def test_events_are_immutable_and_payload_defensive():
    log = shoe()
    event = log.append("CARD_CONFIRMED", {"card_id": "a", "rank": "A", "suit": "S",
                                         "bbox": [1, 2, 3, 4]}, 1)
    original = event.digest
    event.payload["bbox"][0] = 900
    event.payload["rank"] = "K"
    assert event.payload["bbox"][0] == 1
    assert event.payload["rank"] == "A"
    assert event.digest == original
    with pytest.raises(FrozenInstanceError):
        event.kind = "NEW_SHOE"
    assert isinstance(log.events, tuple)


def test_duplicate_and_impossible_cards_are_rejected_atomically():
    log = shoe()
    log.append("CARD_CONFIRMED", {"card_id": "a", "rank": "A", "suit": "S"}, 1)
    before = log.to_dict()
    for payload in ({"card_id": "a", "rank": "A", "suit": "S"},
                    {"card_id": "b", "rank": "A", "suit": "S"}):
        with pytest.raises(EventValidationError):
            log.append("CARD_CONFIRMED", payload, 2)
    assert log.to_dict() == before
    for suit in ("H", "D", "C"):
        log.append("CARD_CONFIRMED", {"card_id": suit, "rank": "A", "suit": suit}, 2)
    with pytest.raises(EventValidationError):
        log.append("CARD_CONFIRMED", {"card_id": "fifth", "rank": "A", "suit": None}, 3)
    assert len(log.replay().cards) == 4


def test_journal_roundtrip_and_tamper_detection(tmp_path):
    log = shoe(2)
    log.append("CARD_CONFIRMED", {"card_id": "a", "rank": "A", "suit": "S"}, 1)
    target = tmp_path / "events.jsonl"
    log.save(target)
    restored = EventLog.load(target)
    assert restored.to_dict() == log.to_dict()
    records = log.to_dict()
    records["events"][1]["payload"]["rank"] = "K"
    with pytest.raises(EventValidationError, match="digest"):
        EventLog.from_dict(records)
    records = log.to_dict()
    records["events"][1]["version"] = 99
    with pytest.raises(EventValidationError, match="schema"):
        EventLog.from_dict(records)


def test_correction_retract_and_new_shoe_reset_preserve_history():
    log = shoe(2)
    log.append("CARD_CONFIRMED", {"card_id": "a", "rank": "A", "suit": "S"}, 1)
    log.append("TRACK_LOST", {"card_id": "a"}, 2)
    assert log.replay().integrity_issues
    log.append("STATE_CORRECTION", {"card_id": "a", "retract": True,
                                   "reason": "review shows duplicate perception"}, 3)
    assert not log.replay().cards
    assert not log.replay().integrity_issues
    log.append("NEW_SHOE", {"decks": 1, "shoe_id": "second"}, 4)
    assert log.replay().physical_remaining == 52
    assert log.replay(1).known_rank_counts["A"] == 1


def test_invalid_time_and_schema_do_not_append():
    log = shoe()
    with pytest.raises(EventValidationError):
        log.append("CARD_CONFIRMED", {"card_id": "a", "rank": "A"}, float("nan"))
    with pytest.raises(EventValidationError):
        log.append("FAKE_EVENT", {}, 1)
    with pytest.raises(IndexError):
        log.replay(5)


@given(st.lists(st.integers(min_value=0, max_value=51), max_size=30, unique=True))
def test_full_rank_suit_conservation_for_arbitrary_observed_subset(indices):
    log = shoe()
    for number, index in enumerate(indices):
        log.append("CARD_CONFIRMED", {"card_id": str(index), "rank": RANKS[index // 4],
                                     "suit": SUITS[index % 4]}, number + 1)
    state = log.replay()
    assert state.physical_remaining == 52 - len(indices)
    assert sum(state.composition_remaining) == state.physical_remaining
    assert sum(state.known_rank_counts.values()) == len(indices)
