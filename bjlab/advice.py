"""Auditable recommendations: basic policy first, composition estimates second."""
from __future__ import annotations

from .counting import hilo_strategy
from .engine import Rules, card_rank, hand_value, legal_actions
from .strategy import get_generated_strategy


def describe_hand(player):
    ranks = [card_rank(card) for card in player]
    total, soft = hand_value(ranks)
    hard = sum(ranks)
    ace_values = [11 if soft and index == ranks.index(1) else 1
                  for index, rank in enumerate(ranks) if rank == 1]
    return {"total": total, "hard_total": hard, "soft": soft,
            "ace_values": ace_values, "alternative_total": hard if soft else None,
            "label": f"{'Soft' if soft else 'Hard'} {total}"}


def recommend(player, dealer, rules: Rules, *, allowed=None, phase="player",
              from_split=False, split_hands=1, split_aces=False, peeked=False,
              true_count=0., count_complete=False, estimate=None):
    """Always return a legal policy for a valid playable state, without inventing EV.

    A Monte Carlo action overrides the basic policy only with a separated ranking.
    Count indices remain a comparison, since they are not universally optimal.
    """
    cards = [card_rank(card) for card in player]
    up = card_rank(dealer)
    hand = describe_hand(cards)
    permitted = list(allowed if allowed is not None else legal_actions(
        cards, rules, from_split=from_split, split_hands=split_hands,
        split_aces=split_aces, peek_resolved=peeked))
    if len(cards) < 2 or hand["total"] > 21 or not permitted:
        raise ValueError("A recommendation needs a playable hand and legal actions.")
    if phase == "insurance":
        basic = "decline_insurance"
        basic_evs = {}
    else:
        normal = None if phase in ("early", "early_surrender") else permitted
        generated = get_generated_strategy(rules).analyze(
            cards, up, from_split=from_split, split_hands=split_hands,
            split_aces=split_aces, peek_resolved=peeked, allowed_actions=normal)
        if generated["error"] or not generated["best_action"]:
            raise ValueError(generated["error"] or "No legal basic-strategy action.")
        basic = generated["best_action"]
        if phase in ("early", "early_surrender"):
            basic = "surrender" if basic == "surrender" else "continue"
        basic_evs = generated["actions"]
    if basic not in permitted:
        raise ValueError("Basic recommendation conflicts with visible legal actions.")
    count_action = basic if count_complete else None
    if phase == "player" and count_complete:
        count_action = hilo_strategy(cards, up, rules, true_count, permitted,
            from_split=from_split, split_hands=split_hands, split_aces=split_aces)
    selected, basis = basic, "basic-strategy"
    estimated = estimate.get("best_action") if estimate else None
    if (estimated in permitted and
            (estimate.get("exact") or estimate.get("ranking_resolved"))):
        selected, basis = estimated, "observed-composition"
    return {"best_action": selected, "basic_action": basic,
            "count_action": count_action, "composition_action": estimated,
            "basis": basis, "hand": hand, "dealer_upcard": str(dealer),
            "legal_actions": permitted, "basic_model_evs": basic_evs,
            "count_comparison_reliable": bool(count_complete),
            "explanation": [
                f"Visible player total: {hand['label']}; dealer upcard: {dealer}.",
                "Apply the configured rules and currently available actions.",
                (f"Rule-generated basic policy: {basic}; Hi-Lo index comparison: {count_action}." if count_complete
                 else f"Rule-generated basic policy: {basic}; Hi-Lo comparison unavailable because shoe history is incomplete."),
                (f"Use the resolved observed-composition estimate: {selected}." if basis == "observed-composition"
                 else "Use basic strategy while the composition estimate is unavailable or its ranking overlaps."),
            ],
            "precision": "Basic policy uses independent draws; finite-pool estimates and sampling intervals are separate."}


def session_advice(session):
    snapshot = session.snapshot()
    if session.phase not in ("player", "insurance", "early_surrender"):
        return snapshot
    hand = session.hands[session.active_hand or 0]
    snapshot["advice"] = recommend(hand.ranks, session.dealer[0].rank, session.rules,
        allowed=session.available_actions(), phase=session.phase,
        from_split=hand.from_split, split_hands=len(session.hands), split_aces=hand.split_aces,
        peeked=session.peek_resolved, true_count=snapshot["shoe"]["true_count"], count_complete=True)
    return snapshot
