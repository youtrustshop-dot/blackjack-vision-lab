import unittest

from bjlab.engine import (Rules, card_rank, hand_value, is_blackjack, initial_counts,
                          legal_actions, dealer_should_hit, settle, insurance_settle)


class EngineTests(unittest.TestCase):
    def test_multiple_aces_and_unicode_cards(self):
        self.assertEqual(hand_value(["A♠", "Ah", "9♦"]), (21, True))
        self.assertEqual(hand_value(["A", "A", "10", "9"]), (21, False))
        self.assertEqual(hand_value(["A", "9", "5"]), (15, False))
        self.assertEqual(card_rank("Q♣"), 10)
        for invalid in ("joker", "0", 14, True):
            with self.assertRaises(ValueError):
                card_rank(invalid)

    def test_decks_conserve_full_shoe(self):
        for decks in (1, 2, 4, 6, 8):
            counts = initial_counts(decks)
            self.assertEqual(sum(counts), 52 * decks)
            self.assertEqual(counts[9], 16 * decks)

    def test_soft_seventeen_policy(self):
        self.assertFalse(dealer_should_hit(["A", "6"], Rules()))
        self.assertTrue(dealer_should_hit(["A", "6"], Rules(hit_soft17=True)))
        self.assertFalse(dealer_should_hit(["10", "7"], Rules(hit_soft17=True)))

    def test_double_and_split_permissions(self):
        self.assertNotIn("double", legal_actions(["5", "3"], Rules(double_rule="9-11")))
        self.assertIn("double", legal_actions(["5", "4"], Rules(double_rule="9-11")))
        self.assertNotIn("double", legal_actions(["5", "6"], Rules(double_after_split=False), from_split=True))
        self.assertNotIn("split", legal_actions(["8", "8"], Rules(resplit=False), from_split=True, split_hands=2))
        self.assertNotIn("split", legal_actions(["8", "8"], Rules(), split_hands=4))
        self.assertIn("split", legal_actions(["K", "10"], Rules()))
        self.assertNotIn("double", legal_actions(["5", "6"], Rules(), can_double=False))

    def test_split_aces_frozen_but_resplittable(self):
        rules = Rules(resplit_aces=True)
        actions = legal_actions(["A", "A"], rules, from_split=True, split_aces=True, split_hands=2)
        self.assertEqual(set(actions), {"stand", "split"})
        self.assertIn("hit", legal_actions(["8", "A"], rules, from_split=True, split_aces=False))
        self.assertNotIn("surrender", legal_actions(["10", "6"], rules, from_split=True))

    def test_split_twenty_one_completes_without_doubling(self):
        rules = Rules(hit_split_aces=True, max_split_hands=2)
        for cards, split_aces in ((["A", 10], True), ([10, "A"], False)):
            with self.subTest(cards=cards):
                self.assertEqual(legal_actions(cards, rules, from_split=True,
                                               split_aces=split_aces, split_hands=2), ["stand"])

    def test_naturals_pushes_and_split_twenty_one(self):
        rules = Rules()
        self.assertEqual(settle(["A", "K"], ["10", "9"], rules), 1.5)
        self.assertEqual(settle(["A", "K"], ["A", "Q"], rules), 0)
        self.assertEqual(settle(["A", "K"], ["10", "9"], rules, from_split=True), 1)
        self.assertEqual(settle(["10", "8"], ["9", "9"], rules), 0)
        self.assertEqual(settle(["10", "8", "5"], ["10", "6", "10"], rules), -1)
        self.assertFalse(is_blackjack(["A", "10"], from_split=True))

    def test_enhc_obo_total_original_bet_only(self):
        dealer = ["A", "10"]
        rules = Rules(enhc=True, enhc_loss="original")
        one = settle(["10", "6", "10"], dealer, rules, wager=2, from_split=True, original_wager=1)
        two = settle(["8", "10"], dealer, rules, from_split=True, original_wager=0)
        self.assertEqual(one + two, -1)
        self.assertEqual(settle(["10", "6", "10"], dealer, Rules(enhc=True), wager=2), -2)

    def test_surrender_timing_and_insurance(self):
        self.assertEqual(settle(["10", "6"], ["A", "10"], Rules(surrender="early"), surrendered=True), -.5)
        self.assertEqual(settle(["10", "6"], ["A", "10"], Rules(), surrendered=True), -1)
        self.assertEqual(insurance_settle(["A", "10"]), 1)
        self.assertEqual(insurance_settle(["A", "9"]), -.5)

    def test_rule_validation(self):
        for kwargs in ({"decks": 3}, {"penetration": 1}, {"max_split_hands": 0},
                       {"double_rule": "magic"}, {"blackjack_payout": float("nan")},
                       {"decks": 6.0}, {"decks": True}, {"hit_soft17": "false"},
                       {"enhc": 1}, {"dealer_peek": "yes"}, {"resplit": None},
                       {"blackjack_payout": True}, {"blackjack_payout": "1.5"},
                       {"penetration": True}, {"penetration": ".75"}, {"max_split_hands": 4.0}):
            with self.assertRaises(ValueError):
                Rules(**kwargs)
        with self.assertRaises(ValueError):
            initial_counts(6.0)


if __name__ == "__main__":
    unittest.main()
