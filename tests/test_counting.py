import unittest

from bjlab.counting import (SYSTEMS, CountingEngine, custom_system, round_true_count,
                            basic_strategy, hilo_strategy)
from bjlab.engine import Rules


class CountingTests(unittest.TestCase):
    def test_balanced_systems_return_to_zero_on_full_deck(self):
        for system in SYSTEMS.values():
            counter = CountingEngine(decks=1, system=system)
            for index, rank in enumerate([r for r in range(1, 10) for _ in range(4)] + [10] * 16):
                counter.observe(rank, f"card:{index}")
            if system.balanced:
                self.assertEqual(counter.running_count, 0, system.name)
            else:
                self.assertEqual(counter.running_count, 4)
                self.assertIsNone(counter.true_count())
            self.assertEqual(sum(counter.remaining_counts), 0)

    def test_event_dedup_and_correction_are_inventory_preserving(self):
        counter = CountingEngine()
        self.assertTrue(counter.observe("5♣", "physical:1"))
        for _ in range(100):
            self.assertFalse(counter.observe("5♣", "physical:1"))
        self.assertEqual(counter.running_count, 1)
        self.assertEqual(sum(counter.remaining_counts), 311)
        counter.correct_event("physical:1", "K")
        self.assertEqual(counter.running_count, -1)
        self.assertEqual(counter.remaining_counts[4], 24)
        self.assertEqual(counter.remaining_counts[9], 95)
        counter.remove_event("physical:1")
        self.assertEqual(counter.running_count, 0)
        self.assertEqual(sum(counter.remaining_counts), 312)

    def test_hilo_example_and_true_count_denominator(self):
        counter = CountingEngine()
        for rank in [3, 5, "K", 7, "Q", "A", 8, 5, 4, 2]:
            counter.observe(rank)
        self.assertEqual(counter.running_count, 2)
        self.assertAlmostEqual(counter.true_count(104), 1)
        self.assertIsNone(counter.true_count(0))

    def test_ko_initial_count_and_rounding_conventions(self):
        self.assertEqual(CountingEngine(6, "KO").running_count, -20)
        self.assertEqual(round_true_count(-1.7, "truncate"), -1)
        self.assertEqual(round_true_count(-1.7, "floor"), -2)
        self.assertEqual(round_true_count(-1.5, "nearest"), -2)

    def test_inventory_errors_and_reset(self):
        counter = CountingEngine(1)
        for n in range(4):
            counter.observe("A", n)
        with self.assertRaises(ValueError):
            counter.observe("A", "extra")
        with self.assertRaises(ValueError):
            counter.observe("K", 0)
        counter.reset()
        self.assertEqual(counter.running_count, 0)
        self.assertEqual(counter.shoe_id, 2)

    def test_custom_balanced_tags_validated(self):
        with self.assertRaises(ValueError):
            custom_system("bad", [1] * 10)
        system = custom_system("my-hilo", SYSTEMS["Hi-Lo"].tags)
        self.assertEqual(system.tag("A"), -1)

    def test_baseline_comparison_respects_surrender_and_legal_actions(self):
        self.assertEqual(basic_strategy([10, 6], 10, Rules()), "surrender")
        self.assertEqual(basic_strategy([8, 8], 10, Rules()), "split")
        self.assertEqual(basic_strategy(["A", 7], 6, Rules()), "double")
        self.assertEqual(basic_strategy(["A", 7], 6, Rules(double_rule="none")), "stand")
        self.assertEqual(hilo_strategy([10, 6], 10, Rules(surrender="none"), -1), "hit")
        self.assertEqual(hilo_strategy([10, 6], 10, Rules(surrender="none"), 0), "stand")
        self.assertEqual(hilo_strategy([10, 5], 9, Rules(), 2), "surrender")


if __name__ == "__main__":
    unittest.main()
