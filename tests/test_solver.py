import unittest
from itertools import permutations

from bjlab.engine import Rules, initial_counts
from bjlab.solver import Solver, insurance_ev, player_draw_probabilities


class SolverTests(unittest.TestCase):
    def test_six_deck_low_hand_fits_default_node_budget_and_reference(self):
        # Independently executed hhoppe pinned effort3 sample; artifact records
        # source hash/rules at validation/reference_engines/results/hhoppe-lowhand.json.
        from bjlab.engine import initial_counts
        counts = list(initial_counts(6))
        for rank in (2, 8, 4):
            counts[rank - 1] -= 1
        result = Solver(Rules()).analyze([2, 8], 4, counts, timeout_ms=5000, max_nodes=60000)
        self.assertTrue(result["exact"], result)
        self.assertEqual(result["best_action"], "double")
        expected = {"stand": -.2095616208421225, "hit": .23414060369412001,
                    "double": .46828120738824003, "surrender": -.5}
        for action, value in expected.items():
            self.assertAlmostEqual(result["actions"][action], value, delta=1e-9)

    def test_unresolved_hidden_card_has_unbiased_marginal(self):
        counts = (1, 1, 0, 0, 0, 0, 0, 0, 0, 2)
        probabilities = player_draw_probabilities(counts, "A")
        self.assertEqual(probabilities, tuple(n / 4 for n in counts))

    def test_negative_peek_changes_player_draw_posterior(self):
        counts = (1, 1, 0, 0, 0, 0, 0, 0, 0, 2)
        probabilities = player_draw_probabilities(counts, "A", peek_resolved=True)
        self.assertAlmostEqual(probabilities[9], 2 / 3)
        self.assertAlmostEqual(probabilities[0], 1 / 6)
        self.assertAlmostEqual(sum(probabilities), 1)
        next_counts = (1, 0, 0, 0, 0, 0, 0, 0, 0, 2)
        self.assertEqual(player_draw_probabilities(next_counts, "A", peek_resolved=True)[9], 1)

    def test_finite_shoe_hand_calculated_returns(self):
        # Pool {2,8,8,T,T,T}; dealer T. With stand on 19:
        # H=8: win (2/6), H=T: lose (3/6), H=2: dealer busts 3/5,
        # reaches 20 in 2/5. Thus stand = -2/15. A hit wins only on 2.
        counts = (0, 1, 0, 0, 0, 0, 0, 2, 0, 3)
        result = Solver(Rules(surrender="none")).analyze([10, 9], 10, counts)
        self.assertTrue(result["exact"], result)
        self.assertAlmostEqual(result["actions"]["stand"], -2 / 15)
        self.assertAlmostEqual(result["actions"]["hit"], -2 / 3)
        self.assertAlmostEqual(result["actions"]["double"], -4 / 3)
        self.assertEqual(result["best_action"], "stand")

    def test_stand_conditioned_on_negative_peek(self):
        counts = (2, 0, 0, 0, 0, 0, 1, 0, 0, 1)
        solver = Solver(Rules(surrender="none"))
        before = solver.analyze([10, 10], 10, counts, peek_resolved=False, can_split=False)
        after = solver.analyze([10, 10], 10, counts, peek_resolved=True, can_split=False)
        self.assertAlmostEqual(before["actions"]["stand"], -.25)
        self.assertAlmostEqual(after["actions"]["stand"], .5)

    def test_natural_and_insurance_use_prepeek_probabilities(self):
        counts = (1, 0, 0, 0, 0, 0, 0, 0, 0, 1)
        solver = Solver(Rules())
        before = solver.analyze(["A", 10], "A", counts, peek_resolved=False)
        after = solver.analyze(["A", 10], "A", counts, peek_resolved=True)
        self.assertAlmostEqual(before["actions"]["stand"], .75)
        self.assertAlmostEqual(after["actions"]["stand"], 1.5)
        self.assertAlmostEqual(insurance_ev(counts)["ev"], .25)
        self.assertFalse(insurance_ev(counts, peek_resolved=True)["available"])

    def test_enhc_double_loss_all_versus_original(self):
        # Draw A -> dealer T, win double; draw T -> dealer A, natural.
        counts = (1, 0, 0, 0, 0, 0, 0, 0, 0, 1)
        all_bets = Solver(Rules(enhc=True, surrender="none")).analyze([10, 10], 10, counts, can_split=False)
        obo = Solver(Rules(enhc=True, enhc_loss="original", surrender="none")).analyze([10, 10], 10, counts, can_split=False)
        self.assertAlmostEqual(all_bets["actions"]["double"], 0)
        self.assertAlmostEqual(obo["actions"]["double"], .5)

    def test_exact_joint_split_resplit_and_split_ace_payout(self):
        counts = (0,) * 9 + (12,)
        result = Solver(Rules(decks=1, surrender="none")).analyze([10, 10], 6, counts)
        self.assertTrue(result["exact"], result)
        self.assertEqual(result["actions"]["split"], 4)
        self.assertEqual(result["best_action"], "split")
        aces = Solver(Rules(decks=1, surrender="none")).analyze(["A", "A"], 6, counts)
        self.assertEqual(aces["actions"]["split"], 2)
        self.assertTrue(aces["exact"], aces)

    def test_split_twenty_one_cannot_be_doubled(self):
        rules = Rules(decks=1, surrender="none", max_split_hands=2,
                      resplit=False, hit_split_aces=True)
        # Every split ace receives a ten. Both hands have 21 and stop;
        # dealer 6+T must draw another ten and busts. Two +1 bets = +2.
        # Doubling an already completed 21 would incorrectly produce +4.
        result = Solver(rules).analyze(["A", "A"], 6, (0,) * 9 + (12,))
        self.assertTrue(result["action_details"]["split"]["exact"], result)
        self.assertEqual(result["actions"]["split"], 2)
        # Symmetric anchor: split tens that receive aces also stop at 21.
        # Up T and a pool of aces require a negative peek to be disabled:
        # use up 9 instead. Dealer 9+A=20 stands and both split21 hands win.
        result = Solver(rules).analyze([10, 10], 9, (4,) + (0,) * 9)
        self.assertTrue(result["action_details"]["split"]["exact"], result)
        self.assertEqual(result["actions"]["split"], 2)

    def test_real_six_deck_surrender_case(self):
        counts = list(initial_counts(6))
        counts[9] -= 2  # player ten and dealer ten
        counts[5] -= 1
        result = Solver(Rules()).analyze([10, 6], 10, counts, timeout_ms=2000)
        self.assertTrue(result["exact"], result)
        self.assertEqual(result["best_action"], "surrender")
        self.assertAlmostEqual(result["actions"]["surrender"], -.5)
        self.assertLess(result["actions"]["stand"], result["actions"]["hit"])

    def test_limits_and_shoe_exhaustion_do_not_claim_exactness(self):
        counts = list(initial_counts(6))
        counts[7] -= 2
        counts[9] -= 1
        result = Solver().analyze([8, 8], 10, counts, max_nodes=1)
        self.assertFalse(result["exact"])
        self.assertIsNone(result["best_action"])
        self.assertEqual(result["status"], "partial")
        tiny = Solver(Rules(surrender="none")).analyze([10, 6], 6, (0,) * 9 + (1,))
        self.assertFalse(tiny["exact"])
        self.assertIsNone(tiny["best_action"])

    def test_invalid_peek_and_missing_split_context_are_explicit(self):
        result = Solver().analyze([10, 6], "A", (0,) * 9 + (4,))
        self.assertEqual(result["status"], "error")
        self.assertIn("peek", result["error"])
        result = Solver().analyze([8, 10], 6, (0,) * 9 + (8,), from_split=True, split_hands=2)
        self.assertFalse(result["exact"])
        self.assertIsNone(result["best_action"])
        self.assertTrue(result["warnings"])

    def test_early_surrender_is_evaluated_before_peek(self):
        result = Solver(Rules(surrender="early")).analyze([10, 6], 10, (2, 0, 0, 0, 0, 0, 1, 0, 0, 1))
        self.assertFalse(result["peek_resolved"])
        self.assertEqual(result["actions"]["surrender"], -.5)

    def test_declining_early_surrender_does_not_add_bets_before_peek(self):
        result = Solver(Rules(surrender="early")).analyze([8, 8], 10, (4,) + (0,) * 9)
        self.assertTrue(result["exact"], result)
        self.assertEqual(result["actions"]["double"], -1)
        self.assertEqual(result["actions"]["split"], -1)
        self.assertEqual(result["best_action"], "surrender")
        self.assertTrue(result["future_peek_integrated"])

    def test_prepeek_double_only_occurs_after_a_negative_check(self):
        # Independently enumerate the three possible hole cards: two tens end
        # the round at -1 BEFORE a double. Hole 9 leaves only tens to draw:
        # player 11 becomes 21 and beats dealer A+9=20, for +2 when doubled.
        # Hence double = (2 * -1 + 1 * 2) / 3 = 0, versus hit = -1/3.
        counts = (0, 0, 0, 0, 0, 0, 0, 0, 1, 2)
        for surrender in ("none", "late", "early"):
            with self.subTest(surrender=surrender):
                solver = Solver(Rules(surrender=surrender))
                result = solver.analyze([5, 6], "A", counts, peek_resolved=False)
                self.assertTrue(result["exact"], result)
                self.assertAlmostEqual(result["actions"]["double"], 0)
                self.assertAlmostEqual(result["actions"]["hit"], -1 / 3)
                self.assertEqual(result["best_action"], "double")
                self.assertTrue(result["future_peek_integrated"])
                if surrender == "late":
                    self.assertAlmostEqual(result["actions"]["surrender"], -5 / 6)
                elif surrender == "early":
                    self.assertEqual(result["actions"]["surrender"], -.5)
                self.assertEqual(result["insurance"]["ev"], .5)
                self.assertTrue(result["insurance"]["available"])
                self.assertTrue(result["insurance"]["take"])
                after = solver.analyze([5, 6], "A", counts, peek_resolved=True)
                self.assertEqual(after["actions"]["double"], 2)
                self.assertFalse(after["insurance"]["available"])

    def test_certain_dealer_blackjack_prevents_split_and_late_surrender(self):
        # Every possible hole is an ace; dealer T will stop the round before
        # splitting or a late surrender can be exercised.
        for surrender in ("none", "late", "early"):
            with self.subTest(surrender=surrender):
                result = Solver(Rules(surrender=surrender)).analyze(
                    [8, 8], 10, (4,) + (0,) * 9, peek_resolved=False)
                self.assertTrue(result["exact"], result)
                self.assertEqual(result["actions"]["double"], -1)
                self.assertEqual(result["actions"]["split"], -1)
                if surrender != "none":
                    self.assertEqual(result["actions"]["surrender"], -.5 if surrender == "early" else -1)

    def test_early_surrender_default_peek_is_resolved_after_initial_phase(self):
        counts = (0, 0, 0, 0, 0, 0, 0, 0, 1, 2)
        solver = Solver(Rules(surrender="early"))
        # Three cards imply that player play already began after the check.
        result = solver.analyze([2, 3, 6], "A", counts)
        self.assertTrue(result["exact"], result)
        self.assertTrue(result["peek_resolved"])
        self.assertEqual(result["actions"]["hit"], 1)
        # A split round also necessarily passed the check. The completed20
        # pushes dealerA+9; active11 drawsT for21, winning1 hit or2 double.
        context = {"from_split": True, "split_hands": 2,
                   "completed_hands": [{"cards": [10, 10], "wager": 1,
                                        "original_wager": 0, "from_split": True}]}
        result = solver.analyze([5, 6], "A", counts, **context)
        self.assertTrue(result["exact"], result)
        self.assertTrue(result["peek_resolved"])
        self.assertEqual(result["actions"]["double"], 2)
        # Explicit prepeek remains available for a valid initial quote.
        result = solver.analyze([5, 6], "A", counts, can_surrender=False)
        self.assertTrue(result["peek_resolved"])
        self.assertEqual(result["actions"]["double"], 2)

    def test_impossible_inventory_is_rejected(self):
        result = Solver().analyze([8, 8], 10, initial_counts(6))
        self.assertEqual(result["status"], "error")
        self.assertIn("inventory", result["error"])

    def test_mixed_finite_shoe_split_matches_exhaustive_assignment(self):
        # Six distinguishable physical cards. Enumerate hole and two replacement
        # cards independently of solver recursion. Dealer 10+8/9/10 always stands;
        # split 8+8 hands reach 16/17/18, and every extra hit would bust.
        physical = (8, 8, 9, 9, 10, 10)
        outcomes = []
        for assignment in permutations(range(6), 3):
            hole, first, second = (physical[index] for index in assignment)
            dealer_total = 10 + hole
            score = 0
            for replacement in (first, second):
                total = 8 + replacement
                score += 1 if total > dealer_total else 0 if total == dealer_total else -1
            outcomes.append(score)
        expected = sum(outcomes) / len(outcomes)
        self.assertAlmostEqual(expected, -26 / 15)
        counts = (0, 0, 0, 0, 0, 0, 0, 2, 2, 2)
        result = Solver(Rules(decks=1, max_split_hands=2, resplit=False, double_rule="none", surrender="none")).analyze([8, 8], 10, counts)
        self.assertTrue(result["exact"], result)
        self.assertAlmostEqual(result["actions"]["split"], expected)

    def test_mixed_finite_shoe_split_aces_exhaustive_assignment(self):
        physical = (8, 8, 9, 9, 10, 10)
        outcomes = []
        for assignment in permutations(range(6), 3):
            hole, first, second = (physical[index] for index in assignment)
            dealer_total = 10 + hole
            outcomes.append(sum(1 if 11 + replacement > dealer_total else 0 if 11 + replacement == dealer_total else -1
                                for replacement in (first, second)))
        expected = sum(outcomes) / len(outcomes)
        # H=8: total EV +2. H=9: only 3/5 replacements beat 19, EV +6/5.
        # H=10: replacements have EV -1/5 each, total -2/5.
        self.assertAlmostEqual(expected, 14 / 15)
        counts = (0, 0, 0, 0, 0, 0, 0, 2, 2, 2)
        result = Solver(Rules(decks=1, double_rule="none", surrender="none")).analyze(["A", "A"], 10, counts)
        self.assertTrue(result["action_details"]["split"]["exact"], result)
        self.assertAlmostEqual(result["actions"]["split"], expected)


if __name__ == "__main__":
    unittest.main()
