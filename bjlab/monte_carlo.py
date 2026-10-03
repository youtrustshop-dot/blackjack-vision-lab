"""Reproducible policy experiments, with independent batches and honest intervals."""
from __future__ import annotations

from dataclasses import asdict
import math
import statistics
import time
from typing import Any

from .engine import Rules, card_rank, hand_value
from .simulator import BlackjackSession


def basic_action(session: BlackjackSession) -> str:
    """Rule-generated replacement-model baseline, restricted to legal actions."""
    available = session.available_actions()
    if session.phase == "insurance":
        return "decline_insurance"
    assert session.active_hand is not None
    from .strategy import generated_basic_strategy
    from .engine import legal_actions
    hand = session.hands[session.active_hand]
    legal = available if session.phase != "early_surrender" else legal_actions(hand.ranks, session.rules)
    generated = generated_basic_strategy(hand.ranks, session.dealer[0].rank, session.rules, legal,
                                        from_split=hand.from_split, split_hands=len(session.hands),
                                        split_aces=hand.split_aces,
                                        pending_count=sum(item.status == "waiting" for item in session.hands),
                                        peek_resolved=session.peek_resolved)
    if session.phase == "early_surrender":
        return "surrender" if generated == "surrender" else "continue"
    return generated


def chart_action(session: BlackjackSession) -> str:
    """Legacy published-style chart reference, separate from generated strategy."""
    available = session.available_actions()
    if session.phase == "insurance":
        return "decline_insurance"
    if session.phase == "early_surrender":
        return "continue"
    assert session.active_hand is not None
    try:
        from .counting import basic_strategy
    except ImportError:
        basic_strategy = None
    if basic_strategy is not None:
        hand = session.hands[session.active_hand]
        return basic_strategy(hand.ranks, session.dealer[0].rank, session.rules, legal=available,
                              from_split=hand.from_split, split_hands=len(session.hands),
                              split_aces=hand.split_aces)
    hand = session.hands[session.active_hand]
    ranks = [card_rank(rank) for rank in hand.ranks]
    total, soft = hand_value(ranks)
    dealer = card_rank(session.dealer[0].rank)
    if "surrender" in available and not soft and (total == 16 and dealer in (9, 10, 1)
                                                  or total == 15 and dealer == 10):
        return "surrender"
    if "split" in available:
        pair = ranks[0]
        should_split = (pair in (1, 8) or pair == 9 and dealer in (2, 3, 4, 5, 6, 8, 9)
                        or pair == 7 and 2 <= dealer <= 7
                        or pair == 6 and 2 <= dealer <= (6 if session.rules.double_after_split else 6)
                        or pair in (2, 3) and (2 <= dealer <= 7 if session.rules.double_after_split else 4 <= dealer <= 7)
                        or pair == 4 and session.rules.double_after_split and dealer in (5, 6))
        if should_split:
            return "split"
    preferred = "hit"
    if soft:
        if total >= 20:
            preferred = "stand"
        elif total == 19:
            preferred = "double" if session.rules.hit_soft17 and dealer == 6 else "stand"
        elif total == 18:
            preferred = "double" if 3 <= dealer <= 6 or session.rules.hit_soft17 and dealer == 2 else "stand" if dealer in (2, 7, 8) else "hit"
        elif total == 17 and 3 <= dealer <= 6 or total in (15, 16) and 4 <= dealer <= 6 or total in (13, 14) and dealer in (5, 6):
            preferred = "double"
    else:
        if total >= 17 or 13 <= total <= 16 and 2 <= dealer <= 6 or total == 12 and 4 <= dealer <= 6:
            preferred = "stand"
        elif total == 11 and (dealer != 1 or session.rules.hit_soft17):
            preferred = "double"
        elif total == 10 and 2 <= dealer <= 9 or total == 9 and 3 <= dealer <= 6:
            preferred = "double"
    if preferred in available:
        return preferred
    if preferred == "double" and soft and total >= 18 and "stand" in available:
        return "stand"
    return "hit" if "hit" in available else "stand"


def hilo_action(session: BlackjackSession) -> str:
    """A declared subset of familiar Hi-Lo index deviations, not all indices."""
    count = session.snapshot()["shoe"]["true_count"]
    available = session.available_actions()
    if session.phase == "insurance":
        return "insurance" if count >= 3 and "insurance" in available else "decline_insurance"
    if session.phase == "early_surrender":
        return basic_action(session)
    assert session.active_hand is not None
    try:
        from .counting import hilo_strategy
    except ImportError:
        hilo_strategy = None
    if hilo_strategy is not None:
        hand = session.hands[session.active_hand]
        return hilo_strategy(hand.ranks, session.dealer[0].rank, session.rules,
                             true_count=count, legal=available, from_split=hand.from_split,
                             split_hands=len(session.hands), split_aces=hand.split_aces)
    total, soft = session.hands[session.active_hand].value
    dealer = card_rank(session.dealer[0].rank)
    if not soft:
        deviations = {(16, 10): (0, "stand"), (15, 10): (4, "stand"),
                      (12, 3): (2, "stand"), (12, 2): (3, "stand"),
                      (10, 10): (4, "double"), (10, 1): (4, "double"),
                      (11, 1): (1, "double")}
        deviation = deviations.get((total, dealer))
        if deviation and count >= deviation[0] and deviation[1] in available:
            return deviation[1]
    return basic_action(session)


def _t95(df: int) -> float:
    table = (0, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306,
             2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110,
             2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060,
             2.056, 2.052, 2.048, 2.045, 2.042)
    return table[df] if df <= 30 else 1.96


def summarize(values: list[float], batches: list[list[float]] | None = None) -> dict:
    if not values:
        return {"rounds": 0, "mean": None, "std": None, "ci95": None, "standard_error": None}
    mean = statistics.fmean(values)
    grouped = batches or [[value] for value in values]
    grouped = [batch for batch in grouped if batch]
    clusters = len(grouped)
    residuals = [sum(batch) - mean * len(batch) for batch in grouped]
    error = math.sqrt(clusters / (clusters - 1) * sum(r * r for r in residuals)) / len(values) if clusters > 1 else None
    half = _t95(clusters - 1) * error if error is not None else None
    return {"rounds": len(values), "mean": mean,
            "std": statistics.stdev(values) if len(values) > 1 else None,
            "standard_error": error, "ci95": [mean - half, mean + half] if half is not None else None,
            "independent_batches": clusters, "interval_method": "Student t with independent batch clusters",
            "units": "net profit per initial unit wager", "total_profit": sum(values)}


def run_experiment(rounds: int = 200, seed: int = 42, rules: Rules | None = None,
                   policies: list[str] | None = None, max_seconds: float = 30,
                   solver_seconds: float = .05, regret_samples: int = 12) -> dict:
    if not isinstance(rounds, int) or not 1 <= rounds <= 100_000:
        raise ValueError("rounds must be an integer from 1 to 100000")
    policies = policies if policies is not None else ["basic", "hilo"]
    if not policies or len(set(policies)) != len(policies) or any(name not in ("basic", "hilo", "composition") for name in policies):
        raise ValueError("Policies must be basic, hilo, or composition.")
    rules = rules or Rules()
    from .solver import Solver
    started = time.perf_counter()
    batch_count = min(20, max(1, rounds // 20))
    sizes = [rounds // batch_count + (i < rounds % batch_count) for i in range(batch_count)]
    data = {name: [] for name in policies}
    batch_data = {name: [] for name in policies}
    regrets = {name: [] for name in policies}
    methods: dict[str, dict[str, int]] = {name: {} for name in policies}
    fallback_counts = {name: 0 for name in policies}
    interrupted = False
    for batch_index, size in enumerate(sizes):
        sessions = {name: BlackjackSession(rules, seed + batch_index * 1_000_003, bankroll=1_000_000)
                    for name in policies}
        current = {name: [] for name in policies}
        solvers = {name: Solver(rules) for name in policies}
        for _ in range(size):
            if time.perf_counter() - started >= max_seconds:
                interrupted = True
                break
            round_values: dict[str, float] = {}
            for name in policies:
                session = sessions[name]
                session.deal()
                while session.phase != "settled":
                    if session.phase == "insurance":
                        action = hilo_action(session) if name == "hilo" else basic_action(session)
                        if name == "composition":
                            pool = session.counts()
                            action = "insurance" if pool[9] * 3 > sum(pool) and "insurance" in session.available_actions() else "decline_insurance"
                    else:
                        action = hilo_action(session) if name == "hilo" else basic_action(session)
                        needs_analysis = name == "composition" or len(regrets[name]) < regret_samples
                        if needs_analysis:
                            state = session.decision_state()
                            arguments = {key: state[key] for key in ("can_double", "can_split", "can_surrender", "peeked", "from_split", "split_aces", "split_hands", "completed_hands", "pending_hands")}
                            analysis = solvers[name].analyze(state["player"], state["dealer"], tuple(state["counts"]),
                                                            timeout_ms=solver_seconds * 1000,
                                                            max_nodes=12_000, **arguments)
                            method = str(analysis.get("method", "unknown"))
                            methods[name][method] = methods[name].get(method, 0) + 1
                            evs = analysis.get("actions", {})
                            numeric = {key: value for key, value in evs.items() if isinstance(value, (float, int)) and math.isfinite(value)}
                            if session.phase == "early_surrender":
                                continuations = [ev for candidate, ev in numeric.items() if candidate != "surrender"]
                                numeric = {"surrender": numeric.get("surrender"),
                                           "continue": max(continuations) if continuations else None}
                                numeric = {key: value for key, value in numeric.items() if value is not None}
                            if name == "composition":
                                candidate = analysis.get("best_action")
                                if session.phase == "early_surrender" and candidate is not None:
                                    candidate = "surrender" if candidate == "surrender" else "continue"
                                if candidate in session.available_actions():
                                    action = candidate
                                else:
                                    fallback_counts[name] += 1
                            if action in numeric and len(regrets[name]) < regret_samples:
                                regrets[name].append({"loss": max(numeric.values()) - numeric[action],
                                                      "exact": bool(analysis.get("exact", False)),
                                                      "method": method})
                    session.action(action)
                round_values[name] = session.round_profit
            for name in policies:
                data[name].append(round_values[name])
                current[name].append(round_values[name])
        for name in policies:
            if current[name]:
                batch_data[name].append(current[name])
        if interrupted:
            break
    results = {}
    for name in policies:
        sampled = regrets[name]
        results[name] = summarize(data[name], batch_data[name]) | {
            "policy": name, "solver_methods": methods[name], "fallback_decisions": fallback_counts[name],
            "decision_loss": {"samples": len(sampled),
                              "mean": statistics.fmean(item["loss"] for item in sampled) if sampled else None,
                              "exact_samples": sum(item["exact"] for item in sampled),
                              "interpretation": "sampled solver action EV gap; approximate EV gaps are not certified regret"},
        }
    comparisons = []
    for first in policies:
        for second in policies:
            if policies.index(first) >= policies.index(second):
                continue
            differences = [a - b for a, b in zip(data[first], data[second])]
            grouped_differences = [[a - b for a, b in zip(batch_a, batch_b)]
                                  for batch_a, batch_b in zip(batch_data[first], batch_data[second])]
            comparisons.append({"first": first, "second": second,
                                "difference": summarize(differences, grouped_differences),
                                "coupling": "same shuffle seeds per independent batch; decision paths may diverge"})
    return {"seed": seed, "rules": asdict(rules), "requested_rounds": rounds,
            "completed_rounds": len(data[policies[0]]), "status": "time_budget" if interrupted else "complete",
            "results": results, "comparisons": comparisons,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "notes": ["Basic policy is generated from the configured rules in a replacement model; finite-shoe exactness is not claimed.",
                      "Hi-Lo uses published-style index deviations with raw true count and declared rules assumptions.",
                      "Composition decisions respect the solver budget and retain its precision labels.",
                      "Intervals describe simulation sampling uncertainty, not solver approximation error.",
                      "Small independent-batch counts yield uncertain intervals; no positive return is guaranteed."],
            "samples": data}
