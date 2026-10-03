"""Finite-shoe expected values with an explicit hidden dealer-card posterior.

No secret card is supplied to this module. ``counts`` excludes observed cards
but includes the unknown dealer hole card (and explicitly declared unknown
removed cards). Negative peek information is integrated before each player
draw. We never optimize a policy after revealing the hidden card to the solver.

Splits use joint round states and sequential dealing: play the first split hand
before dealing a replacement to the next. A time/node limit returns a partial
result, with no definitive best action, rather than labelling an approximation
as an exact calculation.
"""
from __future__ import annotations

from functools import lru_cache
import math
from time import perf_counter
from typing import Iterable

from .engine import Rules, card_rank, hand_value, is_blackjack, legal_actions, initial_counts


_BANK_BUST = (1., 0., 0., 0., 0., 0.)
_BANK_TERMINAL = {total: tuple(float(index == total - 16) for index in range(6))
                  for total in range(17, 22)}


class SolverLimit(RuntimeError):
    pass


class ShoeExhausted(ValueError):
    pass


def _counts(values: Iterable[int]) -> tuple[int, ...]:
    result = tuple(values)
    if len(result) != 10 or any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in result):
        raise ValueError("counts must contain ten nonnegative integers in A,2,..,10 order")
    if sum(result) == 0:
        raise ValueError("the unobserved-card pool is empty")
    return result


def _remove(counts: tuple[int, ...], rank: int) -> tuple[int, ...]:
    return counts[:rank - 1] + (counts[rank - 1] - 1,) + counts[rank:]


def insurance_ev(counts: Iterable[int], dealer: str | int = "A", *, peek_resolved: bool = False) -> dict:
    """Insurance is quoted per original bet (insurance stake = half a bet).

    This is a PRE-PEEK side bet. Supplying a negative resolved peek makes its
    win probability zero, but insurance is then no longer an available action.
    """
    pool = _counts(counts)
    up = card_rank(dealer)
    if up != 1:
        return {"available": False, "probability_blackjack": 0.0, "ev": None, "take": False}
    probability = 0.0 if peek_resolved else pool[9] / sum(pool)
    value = 1.5 * probability - .5
    return {"available": not peek_resolved, "probability_blackjack": probability,
            "ev": value, "ev_per_insurance_unit": 3 * probability - 1,
            "take": not peek_resolved and value > 0, "exact": True}


def player_draw_probabilities(
    counts: Iterable[int], dealer: str | int, *, peek_resolved: bool = False,
) -> tuple[float, ...]:
    """Public helper used by validation: marginal next draw, with hidden hole."""
    pool = _counts(counts)
    total = sum(pool)
    if total <= 1:
        raise ShoeExhausted("no drawable card remains after reserving the hidden dealer card")
    up = card_rank(dealer)
    excluded = 10 if peek_resolved and up == 1 else 1 if peek_resolved and up == 10 else 0
    allowed_count = total - (pool[excluded - 1] if excluded else 0)
    if allowed_count <= 0:
        raise ValueError("negative peek is inconsistent with the unobserved-card pool")
    return tuple((n - (n / allowed_count if rank != excluded else 0)) / (total - 1)
                 for rank, n in enumerate(pool, 1))


class Solver:
    def __init__(self, rules: Rules | None = None):
        self.rules = rules or Rules()

    def insurance(self, counts: Iterable[int], dealer: str | int = "A", **kwargs) -> dict:
        return insurance_ev(counts, dealer, **kwargs)

    def analyze(
        self, player: Iterable[str | int], dealer: str | int, counts: Iterable[int], *,
        peek_resolved: bool | None = None, peeked: bool | None = None,
        from_split: bool = False, split_hands: int = 1, split_aces: bool | None = None,
        can_double: bool | None = None, can_split: bool | None = None,
        can_surrender: bool | None = None, timeout_ms: float = 1000,
        max_nodes: int = 250_000, unknown_removed: int = 0,
        completed_hands: list[dict] | None = None,
        pending_hands: list[list[str | int]] | None = None,
    ) -> dict:
        started = perf_counter()
        actions: dict[str, float | None] = {}
        details: dict[str, dict] = {}
        warnings: list[str] = []
        cleanup = None
        base = {"actions": actions, "best_action": None, "method": "finite-shoe-enumeration",
                "exact": False, "error": None, "status": "error", "warnings": warnings,
                "action_details": details, "ev_units": "net profit per original bet",
                "split_dealing": "sequential", "hidden_information": "marginalized"}
        try:
            input_cards = tuple(card_rank(card) for card in player)
            # For split hands the first card identifies the split rank. Preserve
            # it even when the replacement happens to be an ace.
            cards = ((input_cards[0],) + tuple(sorted(input_cards[1:]))) if from_split and input_cards else tuple(sorted(input_cards))
            up = card_rank(dealer)
            pool = _counts(counts)
            if len(cards) < 2 or hand_value(cards)[0] > 21:
                raise ValueError("analyze requires a live player hand with at least two cards")
            configured = initial_counts(self.rules.decks)
            visible = cards + (up,)
            if any(n + visible.count(rank) > configured[rank - 1] for rank, n in enumerate(pool, 1)):
                raise ValueError("pool plus observed hand/upcard exceeds the configured shoe inventory")
            if peeked is not None:
                if peek_resolved is not None and peek_resolved != peeked:
                    raise ValueError("peeked and peek_resolved disagree")
                peek_resolved = peeked
            if peek_resolved is None:
                early_initial_phase = (self.rules.surrender == "early" and not from_split
                                       and len(cards) == 2 and can_surrender is not False)
                peek_resolved = (self.rules.dealer_peek and not self.rules.enhc and up in (1, 10)
                                 and not early_initial_phase)
            if peek_resolved and (not self.rules.dealer_peek or self.rules.enhc):
                raise ValueError("a resolved negative peek requires dealer_peek and a hole-card game")
            if not isinstance(split_hands, int) or not 1 <= split_hands <= self.rules.max_split_hands:
                raise ValueError("split_hands is outside the configured limit")
            if not isinstance(unknown_removed, int) or unknown_removed < 0 or unknown_removed >= sum(pool):
                raise ValueError("unknown_removed must be a nonnegative integer smaller than the pool")
            if not math.isfinite(timeout_ms) or timeout_ms <= 0 or max_nodes <= 0:
                raise ValueError("timeout_ms and max_nodes must be positive")
            if split_aces is None:
                split_aces = from_split and cards[0] == 1
            legal = legal_actions(cards, self.rules, from_split=from_split, split_hands=split_hands,
                                  split_aces=split_aces, peek_resolved=bool(peek_resolved),
                                  can_double=can_double, can_split=can_split, can_surrender=can_surrender)
            actions.update({action: None for action in legal})
            # In a peek game all player actions follow the dealer check, except
            # early surrender. A pre-check quote integrates the check outcome;
            # it never charges added double/split wagers on the blackjack branch.
            # Late surrender describes the option after a negative check and
            # therefore still loses the original bet when that check finds BJ.
            future_peek = (self.rules.dealer_peek and not self.rules.enhc
                           and up in (1, 10) and not peek_resolved)
            complementary = 10 if up == 1 else 1 if up == 10 else 0
            prepeek_bj = pool[complementary - 1] / sum(pool) if future_peek else 0.
            condition_hole = bool(peek_resolved or future_peek)
            excluded = 10 if condition_hole and up == 1 else 1 if condition_hole and up == 10 else 0
            allowed = tuple(rank for rank in range(1, 11) if rank != excluded)
            if sum(pool[rank - 1] for rank in allowed) == 0 and prepeek_bj < 1:
                raise ValueError("negative peek is inconsistent with all possible hole cards")
            deadline = started + timeout_ms / 1000
            nodes = 0
            limit_name = ""

            def check() -> None:
                nonlocal nodes, limit_name
                nodes += 1
                if nodes > max_nodes:
                    limit_name = "node limit"
                    raise SolverLimit(f"node limit ({max_nodes}) reached")
                if perf_counter() >= deadline:
                    limit_name = "timeout"
                    raise SolverLimit(f"time budget ({timeout_ms:g} ms) exceeded")

            def draws(c: tuple[int, ...]) -> tuple[tuple[int, float], ...]:
                total = sum(c)
                if total <= 1 + unknown_removed:
                    raise ShoeExhausted("shoe cannot supply the next card; mid-round reshuffle is unsupported")
                hole_count = sum(c[r - 1] for r in allowed)
                if hole_count <= 0:
                    raise ValueError("state has no valid hidden dealer card")
                return tuple((rank, (n - (n / hole_count if rank in allowed else 0)) / (total - 1))
                             for rank, n in enumerate(c, 1) if n and
                             (n - (n / hole_count if rank in allowed else 0)) > 0)

            def bank(hard: int, aces: int, c: tuple[int, ...]) -> tuple[float, ...]:
                soft = aces > 0 and hard + 10 <= 21
                total = hard + 10 if soft else hard
                if total > 21:
                    return _BANK_BUST
                if total >= 17 and not (total == 17 and soft and self.rules.hit_soft17):
                    return _BANK_TERMINAL[total]
                return bank_draw(hard, aces, c)

            @lru_cache(maxsize=None)
            def bank_draw(hard: int, aces: int, c: tuple[int, ...]) -> tuple[float, ...]:
                # Terminal dealer vectors are constants and require neither a
                # count-specific memo entry nor another expanded recursion node.
                check()
                size = sum(c)
                if size <= unknown_removed:
                    raise ShoeExhausted("dealer must hit but the drawable shoe is empty")
                value = [0.] * 6
                # Unseen burn cards are exchangeable: integrate their identities.
                for rank, n in enumerate(c, 1):
                    if n:
                        outcome = bank(hard + rank, aces + (rank == 1), _remove(c, rank))
                        for index, probability in enumerate(outcome):
                            value[index] += n / size * probability
                return tuple(value)

            # Completed hand = (total, stake, natural, original-bet allocation, surrender).
            def completed(hand, wager=1., split=False, original=1., surrendered=False):
                return (hand_value(hand)[0], float(wager), is_blackjack(hand, from_split=split),
                        float(original), bool(surrendered))

            prior = tuple(completed(item["cards"], item.get("wager", 1),
                                    item.get("from_split", True), item.get("original_wager", 0),
                                    item.get("surrendered", False)) for item in (completed_hands or []))
            pending = tuple(tuple(card_rank(card) for card in hand) for hand in (pending_hands or []))
            if any(len(hand) not in (1, 2) for hand in pending):
                raise ValueError("pending split hands must contain one or two observed cards")
            if len(prior) + len(pending) + 1 > split_hands:
                raise ValueError("completed/pending hands exceed split_hands")
            joint_context = bool(prior or pending)
            full_split_context = not from_split or split_hands == 1 or len(prior) + len(pending) + 1 == split_hands
            if not full_split_context:
                warnings.append("Not all split hands were supplied; EV excludes missing split hands.")
            if sum(hand[3] for hand in prior) > 1:
                raise ValueError("split round has more than one original-bet allocation")

            @lru_cache(maxsize=None)
            def finish(done: tuple, c: tuple[int, ...]) -> float:
                check()
                hole_count = sum(c[r - 1] for r in allowed)
                if not hole_count:
                    raise ValueError("no possible dealer hole card")
                result = 0.
                needs_play = any(total <= 21 and not natural and not surrendered
                                 for total, wager, natural, original, surrendered in done)
                for hole in allowed:
                    n = c[hole - 1]
                    if not n:
                        continue
                    probability = n / hole_count
                    natural_bank = up + hole == 11 and 1 in (up, hole)
                    if natural_bank:
                        reward = sum(0. if natural else -original if self.rules.enhc and
                                     self.rules.enhc_loss == "original" else -wager
                                     for total, wager, natural, original, surrendered in done)
                    else:
                        if needs_play:
                            outcomes = bank(up + hole, int(up == 1) + int(hole == 1), _remove(c, hole))
                        else:
                            outcomes = (1., 0., 0., 0., 0., 0.)  # no dealer play is needed
                        reward = 0.
                        for total, wager, natural, original, surrendered in done:
                            if surrendered:
                                reward -= .5 * wager
                            elif natural:
                                reward += self.rules.blackjack_payout * wager
                            elif total > 21:
                                reward -= wager
                            else:
                                value = outcomes[0]
                                for index, p in enumerate(outcomes[1:], 17):
                                    value += p * (1 if total > index else 0 if total == index else -1)
                                reward += wager * value
                    result += probability * reward
                return result

            @lru_cache(maxsize=None)
            def single(hand: tuple[int, ...], c: tuple[int, ...]) -> float:
                check()
                total = hand_value(hand)[0]
                if total > 21:
                    # Single undoubled wager loses one whether or not dealer
                    # has BJ, including OBO. No dealer draw is needed for bust.
                    return -1.
                value = finish((completed(hand, split=from_split),), c)
                if total < 21:
                    hit = sum(p * single(tuple(sorted(hand + (rank,))), _remove(c, rank))
                              for rank, p in draws(c))
                    value = max(value, hit)
                return value

            @lru_cache(maxsize=None)
            def next_split(todo: tuple, done: tuple, c: tuple[int, ...], hands: int) -> float:
                check()
                if not todo:
                    return finish(done, c)
                hand, remaining = todo[0], todo[1:]
                if len(hand) == 1:
                    return sum(p * joint(hand + (rank,), remaining, done,
                                         _remove(c, rank), hands)
                               for rank, p in draws(c))
                return joint(hand, remaining, done, c, hands)

            @lru_cache(maxsize=None)
            def joint(hand: tuple, todo: tuple, done: tuple, c: tuple[int, ...], hands: int) -> float:
                check()
                options = legal_actions(hand, self.rules, from_split=True, split_hands=hands,
                                        split_aces=hand[0] == 1)
                if hand_value(hand)[0] > 21:
                    return next_split(todo, done + (completed(hand, split=True, original=0),), c, hands)
                values = []
                for action in options:
                    values.append(joint_action(action, hand, todo, done, c, hands))
                return max(values)

            def joint_action(action, hand, todo, done, c, hands, original=0.):
                if action == "stand":
                    return next_split(todo, done + (completed(hand, split=True, original=original),), c, hands)
                if action == "hit":
                    return sum(p * joint((hand[0],) + tuple(sorted(hand[1:] + (rank,))), todo, done, _remove(c, rank), hands)
                               for rank, p in draws(c))
                if action == "double":
                    return sum(p * next_split(todo, done + (completed(hand + (rank,), wager=2,
                                                                     split=True, original=original),),
                                              _remove(c, rank), hands) for rank, p in draws(c))
                if action == "split":
                    return next_split(((hand[0],), (hand[0],)) + todo, done, c, hands + 1)
                raise ValueError(f"unsupported split action {action}")

            # OBO allocation is attached at round completion, independent of which
            # split hand happens to retain an original card. Mark one completed hand.
            original_finish = finish
            if self.rules.enhc and self.rules.enhc_loss == "original":
                def finish(done, c):
                    if any(original for total, wager, natural, original, surrendered in done):
                        return original_finish(done, c)
                    if done:
                        first = done[0]
                        done = ((first[0], first[1], first[2], 1., first[4]),) + done[1:]
                    return original_finish(done, c)

            def cleanup():
                # Each analysis owns its caches. Clear them before returning so
                # timed-out calls do not retain huge state graphs until GC.
                for cached in (bank_draw, original_finish, single, next_split, joint):
                    cached.cache_clear()

            def evaluate(action):
                if action == "surrender" and self.rules.surrender == "early":
                    return -.5
                if joint_context:
                    if action == "surrender":
                        raise ValueError("surrender cannot apply to an existing split round")
                    return joint_action(action, cards, pending, prior, pool, split_hands)
                if action == "stand":
                    return finish((completed(cards, split=from_split),), pool)
                if action == "surrender":
                    return finish((completed(cards, surrendered=True),), pool)
                if action == "hit":
                    return sum(p * single(tuple(sorted(cards + (rank,))), _remove(pool, rank))
                               for rank, p in draws(pool))
                if action == "double":
                    return sum(p * finish((completed(cards + (rank,), wager=2, split=from_split),),
                                          _remove(pool, rank)) for rank, p in draws(pool))
                if action == "split":
                    return next_split(((cards[0],), (cards[0],)), (), pool, split_hands + 1)
                raise ValueError(f"unsupported action: {action}")

            for action in ("surrender", "stand", "double", "hit", "split"):
                if action not in actions:
                    continue
                action_start = perf_counter()
                try:
                    check()
                    early_surrender = action == "surrender" and self.rules.surrender == "early"
                    if prepeek_bj == 1 and not early_surrender:
                        # The dealer check ends the round before any added bet.
                        actions[action] = 0. if is_blackjack(cards, from_split=from_split) else -1.
                    else:
                        actions[action] = evaluate(action)
                        if future_peek and not early_surrender:
                            check_payoff = 0. if is_blackjack(cards, from_split=from_split) else -1.
                            actions[action] = prepeek_bj * check_payoff + (1 - prepeek_bj) * actions[action]
                    details[action] = {"exact": True, "method": "finite-shoe-enumeration",
                                       "latency_ms": (perf_counter() - action_start) * 1000}
                except SolverLimit as error:
                    details[action] = {"exact": False, "status": limit_name, "error": str(error)}
                except ShoeExhausted as error:
                    details[action] = {"exact": False, "status": "shoe-exhausted", "error": str(error)}
            missing = [action for action, value in actions.items() if value is None]
            best = max((a for a in actions if actions[a] is not None),
                       key=lambda a: actions[a], default=None)
            full_context = full_split_context
            complete = not missing and full_context
            base.update(exact=complete, status="ok" if complete else "partial",
                        best_action=best if complete else None, best_evaluated_action=best,
                        missing_actions=missing, nodes=nodes,
                        peek_resolved=bool(peek_resolved),
                        future_peek_integrated=future_peek,
                        insurance=insurance_ev(pool, up, peek_resolved=bool(peek_resolved)))
            if missing:
                base["error"] = "Some legal actions could not be evaluated within the budget or available shoe."
            if not full_context:
                base["error"] = "Full split-round context is required for a definitive round-optimal action."
            values = sorted((value for value in actions.values() if value is not None), reverse=True)
            base["ev_gap"] = values[0] - values[1] if len(values) > 1 else None
        except (ValueError, TypeError, OverflowError) as error:
            base["error"] = str(error)
        if cleanup is not None:
            cleanup()
        base["latency_ms"] = (perf_counter() - started) * 1000
        base["latency"] = base["latency_ms"]
        return base
