import json
import unittest
import gc
import weakref

from bjlab.engine import Rules
from bjlab.strategy import (GeneratedStrategy, generated_basic_strategy, get_generated_strategy,
                            FiniteGeneratedStrategy, get_finite_generated_strategy)


class GeneratedStrategyTests(unittest.TestCase):
    def test_published_replacement_ev_including_bounded_resplits(self):
        # Primary reference, S17/DAS/max4/noRSA/one card split aces:
        # https://wizardofodds.com/games/blackjack/expected-return-infinite-deck/
        result = GeneratedStrategy(Rules()).analyze([8, 8], 10)
        expected = {"stand": -.540430, "hit": -.539826, "double": -1.079653, "split": -.480686}
        for action, value in expected.items():
            self.assertAlmostEqual(result["actions"][action], value, delta=.0000006)
        self.assertEqual(result["best_action"], "split")
        self.assertTrue(result["exactWithinModel"])
        self.assertFalse(result["finite_shoe_exact"])

    def test_rule_generated_action_changes_h17(self):
        s17 = GeneratedStrategy(Rules())
        h17 = GeneratedStrategy(Rules(hit_soft17=True))
        self.assertEqual(s17.analyze([5, 6], "A")["best_action"], "hit")
        self.assertEqual(h17.analyze([5, 6], "A")["best_action"], "double")
        self.assertEqual(s17.analyze(["A", 8], 6)["best_action"], "stand")
        self.assertEqual(h17.analyze(["A", 8], 6)["best_action"], "double")
        self.assertEqual(h17.analyze([8, 8], "A")["best_action"], "surrender")

    def test_dealer_probability_distribution_and_peek(self):
        for h17 in (False, True):
            strategy = GeneratedStrategy(Rules(hit_soft17=h17))
            for up in range(1, 11):
                self.assertAlmostEqual(sum(strategy.dealer_distribution(up)), 1)
                self.assertAlmostEqual(sum(strategy.dealer_distribution(up, True)), 1)
            self.assertAlmostEqual(strategy.dealer_distribution(1)[6], 4 / 13)
            self.assertAlmostEqual(strategy.dealer_distribution(10)[6], 1 / 13)
            self.assertEqual(strategy.dealer_distribution(1, True)[6], 0)

    def test_legal_restrictions_and_three_card_continuation(self):
        strategy = GeneratedStrategy(Rules())
        result = strategy.analyze(["A", 7], 6, allowed_actions=["hit", "stand"])
        self.assertEqual(result["best_action"], "stand")
        self.assertNotIn("double", result["actions"])
        result = strategy.analyze([2, 3, 6], 6)
        self.assertEqual(result["best_action"], "hit")
        self.assertNotIn("double", result["actions"])
        self.assertNotIn("surrender", result["actions"])

    def test_das_and_resplit_budget_monotonicity(self):
        no_das = GeneratedStrategy(Rules(double_after_split=False)).analyze([2, 2], 6)["actions"]["split"]
        das = GeneratedStrategy(Rules()).analyze([2, 2], 6)["actions"]["split"]
        self.assertGreaterEqual(das, no_das)
        two = GeneratedStrategy(Rules(max_split_hands=2)).analyze([8, 8], 6)["actions"]["split"]
        four = GeneratedStrategy(Rules()).analyze([8, 8], 6)["actions"]["split"]
        self.assertGreaterEqual(four, two)
        disabled = GeneratedStrategy(Rules(resplit=False)).analyze([8, 8], 6)["actions"]["split"]
        self.assertAlmostEqual(disabled, two)

    def test_split_aces_do_not_receive_blackjack_bonus(self):
        low = GeneratedStrategy(Rules(blackjack_payout=1.2))
        high = GeneratedStrategy(Rules(blackjack_payout=1.5))
        self.assertAlmostEqual(low.analyze(["A", "A"], 6)["actions"]["split"],
                               high.analyze(["A", "A"], 6)["actions"]["split"])
        self.assertEqual(high.analyze(["A", 10], 6)["actions"], {"stand": 1.5})
        self.assertEqual(low.analyze(["A", 10], 6)["actions"], {"stand": 1.2})

    def test_replacement_split_twenty_one_is_terminal(self):
        strategy = GeneratedStrategy(Rules(hit_split_aces=True, max_split_hands=2))
        for cards, split_aces in ((["A", 10], True), ([10, "A"], False)):
            with self.subTest(cards=cards):
                result = strategy.analyze(cards, 6, from_split=True, split_aces=split_aces,
                                          split_hands=2, pending_count=0)
                self.assertTrue(result["exactWithinModel"], result)
                self.assertEqual(set(result["actions"]), {"stand"})

    def test_enhc_obo_refunds_added_double_and_split_bets(self):
        all_bets = GeneratedStrategy(Rules(enhc=True, dealer_peek=False)).analyze([8, 8], 10)
        original = GeneratedStrategy(Rules(enhc=True, dealer_peek=False, enhc_loss="original")).analyze([8, 8], 10)
        self.assertGreater(original["actions"]["split"], all_bets["actions"]["split"])
        self.assertAlmostEqual(original["actions"]["double"] - all_bets["actions"]["double"], 1 / 13)
        self.assertAlmostEqual(original["actions"]["stand"], all_bets["actions"]["stand"])

    def test_early_surrender_integrates_future_negative_peek(self):
        early = GeneratedStrategy(Rules(surrender="early")).analyze([8, 8], 10)
        after = GeneratedStrategy(Rules(surrender="none")).analyze([8, 8], 10, peek_resolved=True)
        for action in ("stand", "hit", "double", "split"):
            self.assertAlmostEqual(early["actions"][action], -1 / 13 + 12 / 13 * after["actions"][action])
        self.assertEqual(early["actions"]["surrender"], -.5)
        self.assertTrue(early["future_peek_integrated"])

    def test_early_surrender_three_card_default_is_after_peek(self):
        strategy = GeneratedStrategy(Rules(surrender="early"))
        inferred = strategy.analyze([2, 3, 6], "A")
        explicit = strategy.analyze([2, 3, 6], "A", peek_resolved=True)
        self.assertTrue(inferred["peek_resolved"])
        self.assertEqual(inferred["actions"], explicit["actions"])
        self.assertFalse(inferred["future_peek_integrated"])

    def test_generated_table_weighting_and_separate_naturals(self):
        strategy = GeneratedStrategy(Rules())
        table = strategy.generate_table()
        self.assertEqual(table["hard"]["16"]["10"]["action"], "surrender")
        self.assertEqual(table["pairs"]["8"]["10"]["action"], "split")
        self.assertEqual(table["soft"]["18"]["6"]["action"], "double")
        self.assertEqual(table["natural"]["21"]["6"]["action"], "stand")
        self.assertEqual(len(table["pairs"]), 10)
        for group in ("hard", "soft", "natural"):
            for row in table[group].values():
                self.assertEqual(len(row), 10)
                for cell in row.values():
                    self.assertNotIn("split", cell["actions"])
        state_probability = sum(row["A"]["initial_state_probability"] for group in ("hard", "soft", "natural")
                                for row in table[group].values())
        self.assertAlmostEqual(state_probability, 1)
        json.dumps(table, allow_nan=False)

    def test_no_finite_deck_claim_and_rule_cache_isolation(self):
        one = GeneratedStrategy(Rules(decks=1)).analyze([10, 6], 10)
        eight = GeneratedStrategy(Rules(decks=8)).analyze([10, 6], 10)
        self.assertEqual(one["actions"], eight["actions"])
        self.assertFalse(one["finite_shoe_exact"])
        self.assertEqual(generated_basic_strategy([10, 6], 10, Rules()), "surrender")
        self.assertEqual(generated_basic_strategy([10, 6], 10, Rules(surrender="none")), "hit")

    def test_split_pending_context_precision_is_declared(self):
        strategy = GeneratedStrategy(Rules())
        missing = strategy.analyze([8, 8], 6, from_split=True, split_hands=2)
        complete = strategy.analyze([8, 8], 6, from_split=True, split_hands=2, pending_count=1)
        self.assertFalse(missing["exactWithinModel"])
        self.assertTrue(complete["exactWithinModel"])
        self.assertGreater(complete["actions"]["stand"], missing["actions"]["stand"])

    def test_invalid_input_has_no_recommendation(self):
        strategy = GeneratedStrategy(Rules())
        for kwargs in ({"allowed_actions": []}, {"split_hands": 99}, {"pending_count": -1}):
            result = strategy.analyze([8, 8], 6, **kwargs)
            self.assertIsNone(result["best_action"])
            self.assertEqual(result["status"], "error")

    def test_cache_registry_and_unregistered_instance_collection(self):
        rules = Rules()
        self.assertIs(get_generated_strategy(rules), get_generated_strategy(rules))
        strategy = GeneratedStrategy(rules)
        strategy.analyze([8, 8], 10)
        reference = weakref.ref(strategy)
        del strategy
        gc.collect()
        self.assertIsNone(reference())

    def test_early_phase_continue_compares_future_actions(self):
        strategy = GeneratedStrategy(Rules(surrender="early"))
        positive = strategy.analyze([5, 6], 6, allowed_actions=["surrender", "continue"])
        self.assertEqual(set(positive["actions"]), {"surrender", "continue"})
        self.assertEqual(positive["best_action"], "continue")
        poor = strategy.analyze([10, 6], 10, allowed_actions=["surrender", "continue"])
        self.assertEqual(poor["best_action"], "surrender")

    def test_finite_cell_is_lazy_rule_dependent_and_distinct_from_basic(self):
        one = get_finite_generated_strategy(Rules(decks=1, surrender="none"), timeout_ms=1000)
        six = get_finite_generated_strategy(Rules(decks=6, surrender="none"), timeout_ms=1000)
        self.assertIsNot(one, six)
        self.assertIs(one, get_finite_generated_strategy(Rules(decks=1, surrender="none"), timeout_ms=1000))
        table = one.generate_table()
        self.assertFalse(table["complete"])
        self.assertGreater(table["cell_status_counts"]["not_computed"], 300)
        self.assertIsNone(table["hard"]["16"]["10"]["best_action"])
        a = one.generate_cell("hard", 16, 10)
        b = six.generate_cell("hard", 16, 10)
        self.assertTrue(a["finite_shoe_exact"], a)
        self.assertTrue(b["finite_shoe_exact"], b)
        self.assertNotAlmostEqual(a["actions"]["hit"], b["actions"]["hit"], places=5)
        self.assertFalse(a["total_only_basic_strategy_exact"])
        self.assertIs(one.generate_cell("hard", 16, 10), a)
        self.assertEqual(one.generate_table()["cell_status_counts"]["ok"], 1)
        self.assertNotIn("split", a["actions"])
        json.dumps(one.generate_table(), allow_nan=False)

    def test_finite_initial_weights_condition_on_dealer_and_negative_peek(self):
        strategy = FiniteGeneratedStrategy(Rules(decks=1, surrender="none"))
        combos = strategy._combinations("hard", 16, 10, True)
        self.assertEqual({tuple(c["cards"]) for c in combos}, {(6, 10), (7, 9), (8, 8)})
        weights = {}
        for a, b in ((6, 10), (7, 9), (8, 8)):
            ca, cb = (4, 15) if b == 10 else (4, 4)
            raw = ca * (cb - (a == b)) * (1 if a == b else 2)
            # All these non-ace hard16 combos leave four aces, so the negative
            # peek factor 45/49 is the same and cancels within this row.
            weights[(a, b)] = raw
        total = sum(weights.values())
        for combo in combos:
            self.assertAlmostEqual(combo["probability"], weights[combo["cards"]] / total)
        self.assertAlmostEqual(sum(c["probability"] for c in combos), 1)

    def test_finite_budget_reports_partial_without_recommendation(self):
        strategy = FiniteGeneratedStrategy(Rules(), timeout_ms=1, max_nodes=1)
        result = strategy.generate_cell("pairs", 8, 10)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["finite_shoe_exact"])
        self.assertIsNone(result["best_action"])
        self.assertTrue(any(v is None for v in result["actions"].values()))
        self.assertEqual(strategy.generate_table()["cell_status_counts"]["partial"], 1)


if __name__ == "__main__":
    unittest.main()
