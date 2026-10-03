"""Rule-generated blackjack benchmark using independent draws (replacement).

This is a genuine dynamic-programming policy, not a lookup chart. It deliberately
does NOT claim finite-shoe/composition exactness. Within the declared replacement
model, totals and softness are sufficient statistics for continuation decisions.
Bounded splits/resplits are evaluated with pending-hand and total-hand states.
"""
from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
import math
from time import perf_counter
from typing import Iterable

from .engine import Rules, card_rank, hand_value, initial_counts, is_blackjack, legal_actions


PROBABILITIES = (1 / 13,) * 9 + (4 / 13,)
RANK_NAMES = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10")


def _add(total: int, soft: bool, rank: int) -> tuple[int, bool]:
    hard = total - 10 if soft else total
    hard += rank
    new_soft = (soft or rank == 1) and hard + 10 <= 21
    return hard + 10 if new_soft else hard, new_soft


class GeneratedStrategy:
    """Optimal policy in the specified replacement model and observable phase.

    All caches include the rules through this immutable instance. No finite shoe,
    hidden simulator state, external chart, or trained model is consulted.
    """
    def __init__(self, rules: Rules | None = None):
        self._rules = rules or Rules()
        # Instance-owned caches do not retain every historical strategy object
        # in a global method decorator. Registry eviction can reclaim the instance.
        self._dealer = lru_cache(maxsize=256)(self._dealer)
        self.dealer_distribution = lru_cache(maxsize=128)(self.dealer_distribution)
        self._continuation = lru_cache(maxsize=2048)(self._continuation)
        self._pending = lru_cache(maxsize=8192)(self._pending)
        self.generate_table = lru_cache(maxsize=1)(self.generate_table)

    @property
    def rules(self) -> Rules:
        return self._rules

    def _dealer(self, total: int, soft: bool) -> tuple[float, ...]:
        # Outcomes: bust,17,18,19,20,21 (naturals are handled at the hole draw).
        if total > 21:
            return (1., 0., 0., 0., 0., 0.)
        if total >= 17 and not (total == 17 and soft and self.rules.hit_soft17):
            return tuple(float(index == total - 16) for index in range(6))
        result = [0.] * 6
        for rank, probability in enumerate(PROBABILITIES, 1):
            next_total, next_soft = _add(total, soft, rank)
            for index, outcome in enumerate(self._dealer(next_total, next_soft)):
                result[index] += probability * outcome
        return tuple(result)

    def dealer_distribution(self, up: int | str, exclude_blackjack: bool = False) -> tuple[float, ...]:
        up = card_rank(up)
        forbidden = 10 if up == 1 else 1 if up == 10 else 0
        denominator = 1 - PROBABILITIES[forbidden - 1] if exclude_blackjack and forbidden else 1.
        result = [0.] * 7
        for hole, probability in enumerate(PROBABILITIES, 1):
            if exclude_blackjack and hole == forbidden:
                continue
            probability /= denominator
            if up + hole == 11 and 1 in (up, hole):
                result[6] += probability
            else:
                total, soft = hand_value([up, hole])
                for index, value in enumerate(self._dealer(total, soft)):
                    result[index] += probability * value
        return tuple(result)

    def _stand(self, total: int, up: int, excluded: bool, *, natural: bool = False) -> float:
        distribution = self.dealer_distribution(up, excluded)
        if natural:
            return self.rules.blackjack_payout * (1 - distribution[6])
        if total > 21:
            return -1.
        value = distribution[0] - distribution[6]
        for bank_total, probability in enumerate(distribution[1:6], 17):
            value += probability * (1 if total > bank_total else 0 if total == bank_total else -1)
        return value

    def _continuation(self, total: int, soft: bool, up: int, excluded: bool) -> float:
        stand = self._stand(total, up, excluded)
        if total >= 21:
            return stand
        hit = sum(probability * self._continuation(*_add(total, soft, rank), up, excluded)
                  for rank, probability in enumerate(PROBABILITIES, 1))
        return max(stand, hit)

    def _ordinary(self, cards: tuple[int, ...], up: int, excluded: bool, *, from_split: bool,
                  split_aces: bool = False, allowed: Iterable[str] | None = None) -> dict[str, float]:
        total, soft = hand_value(cards)
        if total > 21:
            return {"stand": -1.}
        permitted = set(legal_actions(cards, self.rules, from_split=from_split, split_aces=split_aces))
        if allowed is not None:
            permitted &= set(allowed)
        result = {}
        if "stand" in permitted:
            result["stand"] = self._stand(total, up, excluded, natural=is_blackjack(cards, from_split=from_split))
        if "hit" in permitted:
            result["hit"] = sum(probability * self._continuation(*_add(total, soft, rank), up, excluded)
                                for rank, probability in enumerate(PROBABILITIES, 1))
        if "double" in permitted:
            result["double"] = 2 * sum(probability * self._stand(_add(total, soft, rank)[0], up, excluded)
                                       for rank, probability in enumerate(PROBABILITIES, 1))
        if "surrender" in permitted:
            p_bj = self.dealer_distribution(up, excluded)[6]
            result["surrender"] = -.5 if self.rules.surrender == "early" else -.5 * (1 - p_bj) - p_bj
        return result

    def _pending(self, rank: int, up: int, excluded: bool, pending: int, hands: int) -> float:
        """Optimal sum of EV for one-card pending split hands (same split rank).

        A non-split decision completes one pending hand. A resplit replaces it
        with two pending hands and increments total hands, so the recurrence is
        acyclic even when every replacement is the split rank.
        """
        if pending == 0:
            return 0.
        future = self._pending(rank, up, excluded, pending - 1, hands)
        result = 0.
        for replacement, probability in enumerate(PROBABILITIES, 1):
            cards = (rank, replacement)
            options = self._ordinary(cards, up, excluded, from_split=True, split_aces=rank == 1)
            normal = max(options.values()) + future
            resplit_ok = (replacement == rank and self.rules.resplit and hands < self.rules.max_split_hands
                          and (rank != 1 or self.rules.resplit_aces))
            if resplit_ok:
                normal = max(normal, self._pending(rank, up, excluded, pending + 1, hands + 1))
            result += probability * normal
        return result

    def analyze(
        self, player: Iterable[str | int], dealer: str | int, *, from_split: bool = False,
        peek_resolved: bool | None = None, peeked: bool | None = None, split_hands: int = 1,
        split_aces: bool | None = None, pending_count: int | None = None,
        allowed_actions: Iterable[str] | None = None, can_double: bool | None = None,
        can_split: bool | None = None, can_surrender: bool | None = None,
    ) -> dict:
        started = perf_counter()
        result = {"method": "infinite-shoe-dp", "exactWithinModel": False,
                  "exact_within_model": False, "finite_shoe_exact": False,
                  "best_action": None, "actions": {}, "ev": {}, "error": None,
                  "assumptions": ["Independent card draws with replacement: A..9 each 1/13, tens 4/13.",
                                  "Dealer hidden card and negative peek are marginalized.",
                                  "Continuation after a hit optimizes total and softness, with no double or surrender.",
                                  "Split hands receive replacements sequentially; bounded resplits are optimized."],
                  "ev_units": "net profit per original initial wager", "scope": "initial round"}
        try:
            cards = tuple(card_rank(card) for card in player)
            up = card_rank(dealer)
            if len(cards) < 2 or hand_value(cards)[0] > 21:
                raise ValueError("player must be a live hand with at least two cards")
            if isinstance(split_hands, bool) or not isinstance(split_hands, int) or not 1 <= split_hands <= self.rules.max_split_hands:
                raise ValueError("split_hands exceeds the configured limit")
            if pending_count is not None and (isinstance(pending_count, bool) or not isinstance(pending_count, int)
                                              or not 0 <= pending_count < split_hands):
                raise ValueError("pending_count must be an integer in [0,split_hands)")
            if peeked is not None:
                if peek_resolved is not None and peek_resolved != peeked:
                    raise ValueError("peeked and peek_resolved disagree")
                peek_resolved = peeked
            early_prepeek = (self.rules.surrender == "early" and not from_split
                             and len(cards) == 2 and can_surrender is not False)
            if peek_resolved is None:
                peek_resolved = self.rules.dealer_peek and not self.rules.enhc and up in (1, 10) and not early_prepeek
            if peek_resolved and (self.rules.enhc or not self.rules.dealer_peek):
                raise ValueError("negative peek requires a supported hole-card game")
            if split_aces is None:
                split_aces = from_split and cards[0] == 1
            permitted = legal_actions(cards, self.rules, from_split=from_split, split_hands=split_hands,
                                      split_aces=split_aces, peek_resolved=bool(peek_resolved),
                                      can_double=can_double, can_split=can_split, can_surrender=can_surrender)
            restricted = {x.lower() for x in allowed_actions} if allowed_actions is not None else None
            early_continue = restricted is not None and "continue" in restricted
            if early_continue:
                if not early_prepeek or peek_resolved:
                    raise ValueError("continue is only an early-surrender decision before the peek")
                # Continue means permit future ordinary actions only after the
                # check. Compare their optimal conditional continuation EV.
                permitted = [a for a in permitted if a != "surrender" or "surrender" in restricted]
            elif restricted is not None:
                permitted = [a for a in permitted if a in restricted]
            if not permitted:
                raise ValueError("no legal actions remain after restrictions")
            raw_bj = self.dealer_distribution(up, False)[6]
            integrate_peek = self.rules.dealer_peek and not self.rules.enhc and not peek_resolved and up in (1, 10)
            # For OBO, optimize on no-BJ outcomes and apply the single original
            # loss once, after summing split hands and added double wagers.
            integrate_obo = self.rules.enhc and self.rules.enhc_loss == "original" and not peek_resolved
            excluded = bool(peek_resolved or integrate_peek or integrate_obo)
            values = self._ordinary(cards, up, excluded, from_split=from_split,
                                    split_aces=split_aces, allowed=permitted)
            pending = pending_count or 0
            if from_split and pending:
                future = self._pending(cards[0], up, excluded, pending, split_hands)
                values = {action: value + future for action, value in values.items()}
            if "split" in permitted:
                values["split"] = self._pending(cards[0], up, excluded, pending + 2, split_hands + 1)
            if integrate_peek or integrate_obo:
                for action in values:
                    if action == "surrender" and self.rules.surrender == "early":
                        continue
                    check_loss = 0. if is_blackjack(cards, from_split=from_split) else -1.
                    values[action] = raw_bj * check_loss + (1 - raw_bj) * values[action]
            if "surrender" in values and self.rules.surrender == "early":
                values["surrender"] = -.5
            if early_continue:
                continuation_value = max(value for action, value in values.items() if action != "surrender")
                values = {action: value for action, value in values.items() if action == "surrender"}
                values["continue"] = continuation_value
            precise = not (from_split and split_hands > 1 and pending_count is None)
            if from_split:
                result["scope"] = "active and pending split hands; completed-hand EV is an action-independent constant"
            if not precise:
                result["assumptions"].append("Other pending split hands were not supplied; available split slots are assigned locally.")
            best = max(values, key=values.get)
            ordered = sorted(values.values(), reverse=True)
            result.update(actions=values, ev=values, best_action=best,
                          exactWithinModel=precise, exact_within_model=precise,
                          status="ok" if precise else "local-split-policy",
                          peek_resolved=bool(peek_resolved), future_peek_integrated=integrate_peek,
                          obo_integrated=integrate_obo, split_precision="exact replacement-model bounded resplits" if precise else
                          "local policy; pending split context unspecified",
                          ev_gap=ordered[0] - ordered[1] if len(ordered) > 1 else None,
                          insurance={"available": up == 1 and not peek_resolved,
                                     "probability_blackjack": 0. if peek_resolved else raw_bj,
                                     "prepeek_probability_blackjack": raw_bj,
                                     "ev": 1.5 * raw_bj - .5 if up == 1 and not peek_resolved else None,
                                     "take": False})
        except (ValueError, TypeError) as error:
            result["error"] = str(error)
            result["status"] = "error"
        result["latency_ms"] = (perf_counter() - started) * 1000
        return result

    def generate_table(self) -> dict:
        """Generate hard/soft rows and pairs; aggregate initial composition weights.

        Hard/soft rows disable splitting and condition on total/softness. Pair
        rows include splitting. Natural A+T remains a separate natural row.
        Replacement makes total/softness sufficient for subsequent decisions,
        so this continuation is a true total-dependent policy in this model.
        """
        buckets: dict[tuple[str, int], list[tuple[tuple[int, int], float]]] = {}
        for a in range(1, 11):
            for b in range(a, 11):
                cards = (a, b)
                total, soft = hand_value(cards)
                group = "natural" if is_blackjack(cards) else "soft" if soft else "hard"
                weight = PROBABILITIES[a - 1] * PROBABILITIES[b - 1] * (1 if a == b else 2)
                buckets.setdefault((group, total), []).append((cards, weight))
        table = {"method": "infinite-shoe-dp", "rules": asdict(self.rules),
                 "finite_shoe_exact": False, "exactWithinModel": True,
                 "continuation_policy": "optimal total-dependent hit/stand after the initial decision",
                 "aggregation": "conditional weights of unordered initial rank pairs; split excluded from hard/soft rows",
                 "assumptions": self.analyze([10, 6], 10)["assumptions"],
                 "hard": {}, "soft": {}, "pairs": {}, "natural": {}}
        for (group, total), hands in sorted(buckets.items()):
            columns = {}
            denominator = sum(weight for cards, weight in hands)
            for up, label in enumerate(RANK_NAMES, 1):
                accumulated: dict[str, float] = {}
                for cards, weight in hands:
                    analysis = self.analyze(cards, up, can_split=False)
                    if analysis["error"]:
                        raise ValueError(analysis["error"])
                    for action, value in analysis["actions"].items():
                        accumulated[action] = accumulated.get(action, 0.) + weight / denominator * value
                best = max(accumulated, key=accumulated.get)
                columns[label] = {"action": best, "best_action": best, "actions": accumulated,
                                  "ev": accumulated, "exactWithinModel": True,
                                  "initial_state_probability": denominator}
            table[group][str(total)] = columns
        for rank, label in enumerate(RANK_NAMES, 1):
            table["pairs"][label] = {}
            for up, up_label in enumerate(RANK_NAMES, 1):
                analysis = self.analyze([rank, rank], up)
                table["pairs"][label][up_label] = {"action": analysis["best_action"],
                    "best_action": analysis["best_action"], "actions": analysis["actions"],
                    "ev": analysis["actions"], "exactWithinModel": analysis["exactWithinModel"]}
        return table


@lru_cache(maxsize=64)
def _strategy(rules: Rules) -> GeneratedStrategy:
    return GeneratedStrategy(rules)


def get_generated_strategy(rules: Rules | None = None) -> GeneratedStrategy:
    """Reuse a bounded, rules-keyed registry of instances with bounded caches."""
    return _strategy(rules or Rules())


def generated_basic_strategy(
    player: Iterable[str | int], dealer: str | int, rules: Rules | None = None,
    legal: Iterable[str] | None = None, *, from_split: bool = False, split_hands: int = 1,
    split_aces: bool | None = None, pending_count: int | None = None,
    peek_resolved: bool | None = None,
) -> str:
    result = _strategy(rules or Rules()).analyze(player, dealer, allowed_actions=legal,
        from_split=from_split, split_hands=split_hands, split_aces=split_aces,
        pending_count=pending_count, peek_resolved=peek_resolved)
    return result["best_action"] or "none"


class FiniteGeneratedStrategy:
    """Lazy fresh finite-shoe initial-cell analysis, distinct from basic policy.

    Initial hard/soft action values are averaged over finite physical rank-pair
    probabilities. Future decisions maximize EV with full observed composition.
    Consequently this is NOT a total-only finite-deck basic strategy generator.
    Budgets are per entire cell; unfinished action aggregates remain null.
    """
    def __init__(self, rules: Rules | None = None, *, timeout_ms: int = 1000,
                 max_nodes: int = 250_000):
        self.rules = rules or Rules()
        for name, value in (("timeout_ms", timeout_ms), ("max_nodes", max_nodes)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self.timeout_ms, self.max_nodes = timeout_ms, max_nodes
        self._cells: dict[tuple[str, int, int, bool], dict] = {}
        self._initial_hands = {}
        for a in range(1, 11):
            for b in range(a, 11):
                total, soft = hand_value((a, b))
                group = "natural" if is_blackjack((a, b)) else "soft" if soft else "hard"
                self._initial_hands.setdefault((group, total), []).append((a, b))

    def analyze(self, player: Iterable[str | int], dealer: str | int, *,
                counts: Iterable[int] | None = None, **kwargs) -> dict:
        from .solver import Solver
        cards, up = tuple(card_rank(c) for c in player), card_rank(dealer)
        if counts is None:
            pool = list(initial_counts(self.rules.decks))
            for rank in (*cards, up):
                pool[rank - 1] -= 1
            counts = tuple(pool)
        kwargs.setdefault("timeout_ms", self.timeout_ms)
        kwargs.setdefault("max_nodes", self.max_nodes)
        return Solver(self.rules).analyze(cards, up, tuple(counts), **kwargs)

    def _combinations(self, group: str, value: int, up: int, peek: bool) -> list[dict]:
        if group == "pairs":
            candidates = [(value, value)]
        else:
            candidates = self._initial_hands.get((group, value), [])
        if not candidates:
            raise ValueError("no two-card initial compositions for requested row")
        shoe = list(initial_counts(self.rules.decks))
        shoe[up - 1] -= 1
        total = sum(shoe)
        combinations = []
        for a, b in candidates:
            weight = shoe[a - 1] / total * (shoe[b - 1] - (a == b)) / (total - 1) * (1 if a == b else 2)
            counts = shoe.copy()
            counts[a - 1] -= 1
            counts[b - 1] -= 1
            if min(counts) < 0 or weight <= 0:
                continue
            if peek and up in (1, 10):
                # Condition distribution of initial rank combinations on the
                # same negative-peek event used in each composition's solver.
                natural_hole = 10 if up == 1 else 1
                weight *= 1 - counts[natural_hole - 1] / sum(counts)
            combinations.append({"cards": (a, b), "counts": tuple(counts), "weight": weight})
        normalizer = sum(c["weight"] for c in combinations)
        if normalizer <= 0:
            raise ValueError("initial row impossible under selected conditioning")
        for combination in combinations:
            combination["probability"] = combination["weight"] / normalizer
        return combinations

    def generate_cell(self, group: str, value: str | int, dealer: str | int, *,
                      peek_resolved: bool | None = None, refresh: bool = False) -> dict:
        from .solver import Solver
        if group not in ("hard", "soft", "pairs", "natural"):
            raise ValueError("group must be hard, soft, pairs or natural")
        value = card_rank(value) if group == "pairs" else int(value)
        up = card_rank(dealer)
        if peek_resolved is None:
            peek_resolved = (self.rules.dealer_peek and not self.rules.enhc and
                             up in (1, 10) and self.rules.surrender != "early")
        if not isinstance(peek_resolved, bool):
            raise ValueError("peek_resolved must be boolean")
        if peek_resolved and (not self.rules.dealer_peek or self.rules.enhc):
            raise ValueError("negative peek unavailable under selected rules")
        key = group, value, up, peek_resolved
        if key in self._cells and not refresh:
            return self._cells[key]
        combinations = self._combinations(group, value, up, peek_resolved)
        started, nodes = perf_counter(), 0
        action_names = set()
        for combo in combinations:
            action_names.update(legal_actions(combo["cards"], self.rules, can_split=group == "pairs"))
        accumulated = {action: 0. for action in action_names}
        complete = {action: True for action in action_names}
        reports = []
        for combo in combinations:
            remaining_ms = self.timeout_ms - (perf_counter() - started) * 1000
            remaining_nodes = self.max_nodes - nodes
            if remaining_ms <= 0 or remaining_nodes <= 0:
                report = {"actions": {a: None for a in action_names}, "exact": False,
                          "action_details": {}, "status": "not_computed", "nodes": 0,
                          "error": "cell computation budget exhausted"}
            else:
                report = Solver(self.rules).analyze(combo["cards"], up, combo["counts"],
                    can_split=group == "pairs", peek_resolved=peek_resolved,
                    timeout_ms=max(1, int(remaining_ms)), max_nodes=remaining_nodes)
            nodes += report.get("nodes", 0)
            for action in action_names:
                ev = report["actions"].get(action)
                detail = report.get("action_details", {}).get(action, {})
                if ev is None or not detail.get("exact", report.get("exact", False)):
                    complete[action] = False
                else:
                    accumulated[action] += combo["probability"] * ev
            reports.append({"player": list(combo["cards"]), "probability": combo["probability"],
                            "status": report.get("status"), "exact": report.get("exact", False),
                            "actions": report["actions"], "error": report.get("error")})
        actions = {a: accumulated[a] if complete[a] else None for a in sorted(action_names)}
        exact = all(complete.values()) and bool(actions)
        valid = {a: v for a, v in actions.items() if v is not None}
        best = max(valid, key=valid.get) if exact else None
        result = {"method": "finite-shoe-initial-composition-aggregation", "status": "ok" if exact else "partial",
                  "group": group, "value": value, "dealer": RANK_NAMES[up - 1],
                  "actions": actions, "ev": actions, "action": best, "best_action": best,
                  "best_evaluated_action": max(valid, key=valid.get) if valid else None,
                  "exact": exact, "finite_shoe_exact": exact, "total_only_basic_strategy_exact": False,
                  "action_details": {a: {"exact": complete[a], "initial_combinations": len(combinations)} for a in actions},
                  "conditioning": "negative-peek" if peek_resolved and up in (1, 10) else "pre-peek",
                  "continuation_policy": "full observed composition optimal; not constrained to total-only choices",
                  "aggregation": "finite initial rank pairs conditioned on dealer upcard and negative peek when selected",
                  "initial_combinations": reports, "nodes": nodes,
                  "latency_ms": (perf_counter() - started) * 1000,
                  "budget": {"timeout_ms": self.timeout_ms, "max_nodes": self.max_nodes},
                  "ev_units": "net profit per original bet", "rules": asdict(self.rules)}
        self._cells[key] = result
        return result

    def generate_table(self, *, cells: Iterable[tuple[str, str | int, str | int]] = ()) -> dict:
        """Cheap manifest by default; compute only explicitly requested cells."""
        for group, value, up in cells:
            self.generate_cell(group, value, up)
        table = {"method": "finite-shoe-initial-composition-aggregation", "rules": asdict(self.rules),
                 "complete": False, "finite_shoe_exact": False, "total_only_basic_strategy_exact": False,
                 "continuation_policy": "full observed composition optimal; not a total-only basic policy",
                 "lazy": True, "budget_per_cell": {"timeout_ms": self.timeout_ms, "max_nodes": self.max_nodes},
                 "hard": {}, "soft": {}, "pairs": {}, "natural": {}}
        rows = list(self._initial_hands) + [("pairs", rank) for rank in range(1, 11)]
        status_counts = {"ok": 0, "partial": 0, "not_computed": 0}
        for group, value in rows:
            row_label = RANK_NAMES[value - 1] if group == "pairs" else str(value)
            table[group][row_label] = {}
            for up, label in enumerate(RANK_NAMES, 1):
                peek = self.rules.dealer_peek and not self.rules.enhc and up in (1, 10) and self.rules.surrender != "early"
                result = self._cells.get((group, value, up, peek))
                if result is None:
                    result = {"status": "not_computed", "actions": {}, "ev": {}, "best_action": None,
                              "action": None, "exact": False, "finite_shoe_exact": False}
                table[group][row_label][label] = result
                status_counts[result["status"]] += 1
        table["cell_status_counts"] = status_counts
        table["complete"] = status_counts["partial"] == status_counts["not_computed"] == 0
        table["finite_shoe_exact"] = table["complete"]
        return table


@lru_cache(maxsize=8)
def get_finite_generated_strategy(rules: Rules | None = None, *, timeout_ms: int = 1000,
                                 max_nodes: int = 250_000) -> FiniteGeneratedStrategy:
    """Small rules-and-budget keyed registry; table computations are lazy."""
    return FiniteGeneratedStrategy(rules or Rules(), timeout_ms=timeout_ms, max_nodes=max_nodes)
