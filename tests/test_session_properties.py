"""Cross-rule state and replay properties, independent of strategy choices."""
import random
from hypothesis import given, settings, strategies as st
import pytest
from bjlab.engine import Rules
from bjlab.simulator import BlackjackSession


def check_public_inventory(session):
    state = session.snapshot()
    shoe = state["shoe"]
    assert all(count >= 0 for count in shoe["counts"])
    assert sum(shoe["counts"]) + shoe["seen"] == 52 * state["rules"]["decks"]
    assert shoe["unknown_cards"] == sum(shoe["counts"])
    # A physically removed, unrevealed hole is part of the unknown pool.
    hidden = sum(card.get("face_down", False) for card in state["dealer"]["cards"])
    assert shoe["unknown_cards"] == shoe["remaining"] + hidden
    for card in state["dealer"]["cards"]:
        if card.get("face_down"):
            assert "rank" not in card and "suit" not in card
    assert state["bankroll"] == pytest.approx(1000 + state["total_profit"])
    if state["phase"] == "settled":
        assert state["active_hand"] is None
        assert state["round_profit"] == pytest.approx(
            sum(hand["profit"] for hand in state["hands"]) + state["insurance"]["profit"]
        )
    return state


@settings(max_examples=32, deadline=None, derandomize=True)
@given(
    seed=st.integers(0, 2**31-1),
    decks=st.sampled_from([1, 2, 6]),
    h17=st.booleans(), enhc=st.booleans(), das=st.booleans(),
    resplit_aces=st.booleans(), hit_split_aces=st.booleans(),
    double=st.sampled_from(["any", "9-11", "10-11", "none"]),
    surrender=st.sampled_from(["none", "early", "late"]),
    loss=st.sampled_from(["all", "original"]),
)
def test_random_legal_sessions_preserve_inventory_money_and_replay(
    seed, decks, h17, enhc, das, resplit_aces, hit_split_aces, double, surrender, loss
):
    rules = Rules(
        decks=decks, hit_soft17=h17, enhc=enhc, dealer_peek=not enhc,
        double_after_split=das, double_rule=double, surrender=surrender,
        enhc_loss=loss, resplit_aces=resplit_aces, hit_split_aces=hit_split_aces,
        max_split_hands=4,
    )
    session = BlackjackSession(rules, seed, bankroll=1000)
    rng = random.Random(seed ^ 0xB1A)
    check_public_inventory(session)
    for _ in range(12):
        session.deal(1)
        check_public_inventory(session)
        for _ in range(100):
            if session.phase == "settled":
                break
            legal = session.available_actions()
            assert legal
            session.action(rng.choice(legal))
            check_public_inventory(session)
        else:
            pytest.fail("A legal round did not terminate after 100 actions")
    final = session.snapshot()
    reconstructed = BlackjackSession.replay(session.events).snapshot()
    assert reconstructed == final
    # Check a cursor inside an atomic deal/action, where future cards must be absent.
    cursor = rng.randrange(2, len(session.events))
    prefix = BlackjackSession.replay(session.events, cursor)
    assert prefix.events == session.events[:cursor+1]
    assert prefix.snapshot()["events_count"] == cursor+1
    check_public_inventory(prefix)
