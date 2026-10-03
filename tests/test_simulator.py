from dataclasses import replace
import csv
import io
import json

import pytest

from bjlab.engine import Rules, card_rank
from bjlab.simulator import BlackjackSession


def fixture(cards, **rules):
    session = BlackjackSession(Rules(**rules), seed=17)
    session.set_shoe(cards)
    return session


def finish(session):
    while session.phase != "settled":
        session.action("decline_insurance" if session.phase == "insurance" else
                       "continue" if session.phase == "early_surrender" else "stand")


def test_deterministic_seed_and_replay():
    first, second = BlackjackSession(seed=1), BlackjackSession(seed=1)
    first.deal(); second.deal()
    finish(first); finish(second)
    assert first.snapshot()["hands"] == second.snapshot()["hands"]
    assert first.snapshot()["dealer"] == second.snapshot()["dealer"]
    rebuilt = BlackjackSession.replay(first.events)
    assert rebuilt.snapshot() == first.snapshot()
    assert rebuilt.events == first.events


def test_hole_hidden_and_count_information_boundary():
    session = fixture(["2", "6", "8", "A", "10", "9", "3"])
    state = session.deal()
    hole = state["dealer"]["cards"][1]
    assert set(hole) == {"id", "face_down"}
    assert state["dealer"]["total"] is None
    assert sum(session.counts()) == 4  # Unseen hole plus three drawable cards.
    assert state["shoe"]["remaining"] == 3
    assert state["shoe"]["running_count"] == 2
    assert state["shoe"]["true_count"] == pytest.approx(2 / (3 / 52))
    assert state["shoe"]["true_count_denominator"] == "physical_remaining_cards"
    assert state["shoe"]["true_count_denominator_cards"] == 3
    assert state["seed"] == 17
    assert session.decision_state()["counts"][0] == 1
    before = len(session.events)
    session._expose(session.hands[0].cards[0], "player", 0)
    assert len(session.events) == before
    assert session.running_count == 2


def test_standard_hole_id_does_not_contain_rank():
    session = BlackjackSession(seed=9)
    state = session.deal()
    identity = state["dealer"]["cards"][1]["id"]
    assert len(identity.split("-")[-1]) == 32
    assert "rank" not in state["dealer"]["cards"][1]


def test_natural_payout_and_both_naturals():
    session = fixture(["A", "9", "K", "7"])
    assert session.deal()["round_profit"] == 1.5
    session = fixture(["A", "A", "K", "K"])
    assert session.deal()["phase"] == "insurance"
    assert session.action("decline_insurance")["round_profit"] == 0


def test_insurance_and_peek_settlement():
    session = fixture(["10", "A", "9", "K"])
    state = session.deal()
    assert state["phase"] == "insurance"
    assert session.action("insurance")["round_profit"] == 0
    assert session.insurance["profit"] == 1
    assert session.hands[0].profit == -1
    assert len(session.seen) == 4


def test_negative_peek_leaves_hole_hidden():
    session = fixture(["8", "10", "8", "7", "2"])
    state = session.deal()
    assert state["peek_resolved"] is True
    assert state["dealer"]["cards"][1]["face_down"]
    assert session.decision_state()["peeked"] is True


@pytest.mark.parametrize("loss, expected", [("all", -2), ("original", -1)])
def test_enhc_double_loss_rules(loss, expected):
    session = fixture(["5", "A", "6", "9", "K"], enhc=True, dealer_peek=False, enhc_loss=loss)
    session.deal(); session.action("decline_insurance")
    assert session.action("double")["round_profit"] == expected
    assert session.hands[0].bet == 2


@pytest.mark.parametrize("surrender, expected", [("late", -1), ("early", -.5)])
def test_surrender_with_unresolved_dealer_blackjack(surrender, expected):
    session = fixture(["10", "10", "6", "A"], enhc=True, dealer_peek=False, surrender=surrender)
    session.deal()
    assert session.action("surrender")["round_profit"] == expected


def test_early_surrender_before_peek_and_cannot_be_used_after_continue():
    session = fixture(["10", "10", "6", "A"], surrender="early")
    state = session.deal()
    assert state["phase"] == "early_surrender"
    assert state["peek_resolved"] is False
    assert session.action("surrender")["round_profit"] == -.5
    session = fixture(["10", "10", "6", "7"], surrender="early")
    session.deal(); session.action("continue")
    assert "surrender" not in session.available_actions()
    assert session.decision_state()["can_surrender"] is False


@pytest.mark.parametrize("hit_soft17, expected", [(False, 1), (True, -1)])
def test_soft_seventeen_rule(hit_soft17, expected):
    session = fixture(["10", "A", "8", "6", "4"], hit_soft17=hit_soft17)
    session.deal(); session.action("decline_insurance")
    assert session.action("stand")["round_profit"] == expected


def test_split_dealing_is_sequential_and_double_bets_settle():
    session = fixture(["8", "6", "8", "10", "3", "10", "10", "5"])
    session.deal()
    state = session.action("split")
    assert len(state["hands"]) == 2
    assert state["hands"][0]["total"] == 11
    assert len(state["hands"][1]["cards"]) == 1
    assert state["hands"][1]["status"] == "waiting"
    session.action("double")
    assert session.active_hand == 1
    assert session.hands[1].value[0] == 18
    state = session.action("stand")
    assert state["round_profit"] == -1
    assert [hand.bet for hand in session.hands] == [2, 1]
    assert sum(hand.original_wager for hand in session.hands) == 1


def test_split_aces_resplit_and_no_natural_bonus():
    session = fixture(["A", "6", "A", "10", "A", "10", "9", "8", "5"],
                      resplit_aces=True, max_split_hands=3)
    session.deal(); session.action("split")
    assert "split" in session.available_actions()
    assert "hit" not in session.available_actions()
    state = session.action("split")
    assert state["phase"] == "settled"
    assert len(session.hands) == 3
    assert not session.hands[0].public()["natural"]
    assert state["round_profit"] == -2


def test_ace_split_forced_stand_when_resplit_disallowed():
    session = fixture(["A", "6", "A", "10", "A", "10", "5"])
    session.deal()
    state = session.action("split")
    assert state["phase"] == "settled"
    assert [hand.status for hand in session.hands] == ["stood", "stood"]


def test_enhc_obo_split_round_loses_only_original_bet():
    session = fixture(["8", "10", "8", "10", "10", "A"], enhc=True,
                      dealer_peek=False, enhc_loss="original")
    session.deal(); session.action("split"); session.action("stand")
    state = session.action("stand")
    assert state["round_profit"] == -1
    assert [hand.profit for hand in session.hands] == [-1, 0]


def test_split_limit_das_and_double_restrictions():
    session = fixture(["8", "6", "8", "10", "3", "10", "10", "5"], double_after_split=False,
                      max_split_hands=2)
    session.deal(); session.action("split")
    assert "double" not in session.available_actions()
    assert "split" not in session.available_actions()
    session = fixture(["7", "6", "5", "10", "5"], double_rule="10-11")
    session.deal()
    assert "double" not in session.available_actions()


def test_bankroll_prevents_extra_exposure_and_invalid_actions_are_atomic():
    session = fixture(["8", "6", "8", "10", "5"])
    session.bankroll = 1
    session.deal()
    assert "double" not in session.available_actions()
    assert "split" not in session.available_actions()
    before = session.snapshot()
    with pytest.raises(ValueError):
        session.action("split")
    assert session.snapshot() == before
    with pytest.raises(ValueError):
        session.new_shoe()


def test_invalid_bets_and_insufficient_cards():
    session = fixture(["2", "6", "8"])
    for bet in (-1, 0, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            session.deal(bet)
    with pytest.raises(ValueError):
        session.deal()
    assert session.phase == "ready"


def test_shuffle_resets_counts_and_preserves_history():
    session = fixture(["10", "10", "9", "7"])
    session.deal(); session.action("stand")
    assert len(session.seen) == 4
    old_id = session.shoe.id
    state = session.new_shoe()
    assert state["shoe"]["seen"] == 0
    assert state["shoe"]["running_count"] == 0
    assert sum(state["shoe"]["counts"]) == 312
    assert state["shoe"]["id"] != old_id
    assert BlackjackSession.replay(session.events).snapshot() == state


def test_event_exports_contain_complete_auditable_log():
    session = fixture(["10", "10", "9", "7"])
    session.deal(); session.action("stand")
    parsed = json.loads(session.export("json"))
    assert parsed["events"] == session.events
    rows = list(csv.DictReader(io.StringIO(session.export("csv"))))
    assert len(rows) == len(session.events)
    assert json.loads(rows[-1]["payload"])["profit"] == 1
    assert BlackjackSession.replay(parsed["events"]).events == session.events


def test_counts_never_negative_across_seeded_play():
    for seed in range(4):
        session = BlackjackSession(Rules(decks=1, penetration=.35), seed=seed)
        for _ in range(25):
            session.deal(); finish(session)
            counts = session.counts()
            assert min(counts) >= 0
            assert sum(counts) == len(session.shoe.cards)
            assert len({card.id for card in session.seen.values()}) == len(session.seen)
        assert any(event["kind"] == "shuffle_requested" for event in session.events)


def test_replay_prefix_during_deal_excludes_future_exposure_and_hole():
    session = fixture(["2", "6", "8", "A", "10", "9", "3"])
    session.deal()
    exposures = [event for event in session.events if event["kind"] == "card_exposed"]
    cursor = exposures[0]["seq"]
    prefix = BlackjackSession.replay(session.events, cursor)
    assert len(prefix.events) == cursor + 1
    assert len(prefix.seen) == 1
    assert [card.rank for card in prefix.hands[0].cards] == ["2"]
    assert prefix.dealer == []
    assert prefix.phase == "dealing"
    assert prefix.available_actions() == []
    assert sum(prefix.counts()) == 6
    assert len(prefix.shoe.cards) == 6


def test_replay_mid_reveal_has_no_future_dealer_draw_or_profit():
    session = fixture(["10", "6", "8", "5", "10"])
    session.deal(); session.action("stand")
    hole_id = session.dealer[1].id
    cursor = next(event["seq"] for event in session.events
                  if event["kind"] == "card_exposed" and event["payload"]["card"]["id"] == hole_id)
    prefix = BlackjackSession.replay(session.events, cursor)
    assert len(prefix.dealer) == 2
    assert prefix.hole_revealed
    assert prefix.phase == "resolving"
    assert prefix.round_profit == 0
    assert prefix.total_profit == 0
    assert prefix.bankroll == 1000
    assert len(prefix.seen) == 4
    assert len(prefix.shoe.cards) == 1
    assert prefix.hands[0].profit is None


def test_replay_rejects_corrupted_fact_and_reduces_all_prefixes():
    session = fixture(["8", "6", "8", "10", "3", "10", "10", "5"])
    session.deal(); session.action("split"); session.action("double"); session.action("stand")
    for cursor in range(len(session.events)):
        prefix = BlackjackSession.replay(session.events, cursor)
        assert len(prefix.events) == cursor + 1
        exposed_ids = {event["payload"]["card"]["id"] for event in session.events[:cursor + 1]
                       if event["kind"] == "card_exposed"}
        assert set(prefix.seen) == exposed_ids
        assert min(prefix.counts()) >= 0
    damaged = json.loads(session.export())["events"]
    exposure = next(event for event in damaged if event["kind"] == "card_exposed")
    exposure["payload"]["card"]["rank"] = "K"
    with pytest.raises(ValueError, match="audit"):
        BlackjackSession.replay(damaged)
