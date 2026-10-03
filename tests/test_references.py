import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bjlab.engine import Rules
from bjlab.references import (
    FreeBJAdapter, HhoppeAdapter, UnsupportedReference, ReferenceExecutionError,
    freebj_rule_mapping, hhoppe_rule_mapping, load_manifest, parse_freebj_output,
    verify_freebj_rules, independent_batch_statistics, write_freebj_shoe,
    load_reference_output, compare_action_values, run_golden_validation,
)


class ReferenceTests(unittest.TestCase):
    def test_manifest_real_revisions_and_no_runtime_dependency(self):
        manifest = load_manifest()
        self.assertEqual(len(manifest["references"]), 11)
        self.assertTrue(all(len(e["commit"]) == 40 and e["commit"] != "0" * 40 for e in manifest["references"]))
        self.assertTrue(all(not e["production_dependency"] and not e["code_copied"] for e in manifest["references"]))

    def test_mapping_echo_has_explicit_rule_values(self):
        rules = Rules(decks=2, hit_soft17=True, double_after_split=False, double_rule="9-11",
                      surrender="early", max_split_hands=4, penetration=.7)
        mapped = freebj_rule_mapping(rules)
        self.assertIn("--db-hard-9-11", mapped["argv"])
        self.assertEqual(mapped["expected_rules"]["penetration_cards"], 72)
        self.assertEqual(mapped["expected_rules"]["max_splits"], 4)
        self.assertEqual(mapped["expected_rules"]["surrender"], "early_surrender")
        self.assertFalse(mapped["native_split_deal_order_matches"])
        single = freebj_rule_mapping(Rules(resplit=False, max_split_hands=8), fresh_shoe=True)
        self.assertEqual(single["expected_rules"]["max_splits"], 2)
        self.assertEqual(single["expected_rules"]["penetration_cards"], 1)

    def test_unsupported_rule_combinations_are_rejected(self):
        for rules in (Rules(blackjack_payout=1.2), Rules(dealer_peek=False),
                      Rules(enhc=True, enhc_loss="original", surrender="none"),
                      Rules(enhc=True, surrender="late"), Rules(resplit_aces=True, hit_split_aces=False)):
            with self.assertRaises(UnsupportedReference):
                freebj_rule_mapping(rules)
        for rules in (Rules(enhc=True), Rules(surrender="early"), Rules(double_rule="9-11")):
            with self.assertRaises(UnsupportedReference):
                hhoppe_rule_mapping(rules)

    def test_strict_json_and_echo_dont_accept_wrong_types(self):
        expected = freebj_rule_mapping(Rules())["expected_rules"]
        output = parse_freebj_output(json.dumps({"rules": expected, "rounds": 10, "ev": -.1, "stddev": 1.1}))
        verify_freebj_rules(output, expected)
        metadata = parse_freebj_output(json.dumps({"rules": expected, "rounds": 0, "ev": None, "stddev": None}), metadata_only=True)
        verify_freebj_rules(metadata, expected)
        output["rules"]["das"] = 1
        with self.assertRaises(ReferenceExecutionError):
            verify_freebj_rules(output, expected)
        for raw in ("log\n{}", '{"rules":{},"rounds":10,"ev":NaN,"stddev":1}', '{"rules":{},"rounds":true,"ev":0,"stddev":1}'):
            with self.assertRaises(ReferenceExecutionError):
                parse_freebj_output(raw)

    def test_batch_ci_uses_batch_variability(self):
        stats = independent_batch_statistics([-.1, 0, .1])
        self.assertAlmostEqual(stats["standard_error"], .1 / 3 ** .5)
        self.assertGreater(stats["critical_value"], 4)
        self.assertEqual(stats["method"], "independent-batch-means-student-t")
        with self.assertRaises(ValueError):
            independent_batch_statistics([0])

    def test_pinned_file_shoe_uses_source_verified_ascii(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_freebj_shoe(Path(folder) / "cards.dat", [1, 2, 10, "K"])
            self.assertEqual(path.read_bytes(), b"A 2 T T")

    def test_forced_cli_argv_and_missing_engine_skip(self):
        adapter = FreeBJAdapter("certainly-missing-freebj-reference.exe")
        command, mapping = adapter.build_command(Rules(), player=[10, 6], dealer=10, action="stand", fresh_shoe=True)
        self.assertEqual(command[-6:], ["-c", "10,6", "--dealer", "10", "-a", "="])
        unconditional, _ = adapter.build_command(Rules(), action="stand")
        self.assertEqual(unconditional[-2:], ["-a", "="])
        self.assertNotIn("-c", unconditional)
        self.assertEqual(adapter.run_batches(Rules())["status"], "skipped")
        self.assertEqual(adapter.run_batches(Rules(), shoe_file="fixed.dat")["status"], "unsupported")
        unavailable = HhoppeAdapter("nonexistent-reference-checkout").analyze(Rules(), [10, 6], 10)
        self.assertEqual(unavailable["status"], "skipped")
        self.assertFalse(unavailable["comparison_executed"])

    def test_hhoppe_refuses_unrepresented_state_before_execution(self):
        adapter = HhoppeAdapter("nonexistent-reference-checkout")
        self.assertEqual(adapter.analyze(Rules(), [10, 6], 10, counts=(1,) * 10)["status"], "unsupported")
        self.assertEqual(adapter.analyze(Rules(), [10, 6], 10, peek_resolved=False)["status"], "unsupported")
        self.assertEqual(adapter.analyze(Rules(), [1, 10], 10)["status"], "unsupported")

    def test_external_output_requires_complete_provenance_and_model(self):
        pin = next(e for e in load_manifest()["references"] if e["repository"] == "Neurobaby/MGPs-BJ-CA")
        artifact = {"schema_version": 1, "status": "executed", "rules": asdict(Rules()), "exact": False,
                    "actions": {"stand": -.4}, "model": {"shoe": "finite-fresh", "conditioning": "negative-peek",
                    "continuation": "stand", "split_deal_order": "none", "ev_units": "net-profit-per-original-unit"},
                    "provenance": {"repository": pin["repository"], "revision": pin["commit"],
                    "source_url": pin["url"], "executed_at": "2026-10-03T01:00:00+00:00", "producer": "manual-tool-export",
                    "raw_output_sha256": "a" * 64}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "artifact.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            result = load_reference_output(path)
            self.assertTrue(result["provenance_verified_against_manifest"])
            self.assertFalse(result["mathematical_equivalence_verified"])
            artifact["provenance"]["revision"] = "0" * 40
            path.write_text(json.dumps(artifact), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_reference_output(path)

    def test_no_comparison_pass_for_skipped_partial_or_different_model(self):
        reference = {"status": "executed", "actions": {"stand": -.4}}
        self.assertEqual(compare_action_values({"actions": {"stand": -.4}}, reference,
                         tolerance=1e-8)["status"], "unsupported")
        self.assertFalse(compare_action_values({"actions": {"stand": None}}, reference,
                         tolerance=1e-8, equivalent_model=True)["passed"])
        self.assertFalse(compare_action_values({"actions": {"stand": -.4}}, dict(reference, status="skipped"),
                         tolerance=1e-8, equivalent_model=True)["passed"])

    def test_primary_published_golden_values_match_replacement_dp(self):
        result = run_golden_validation()
        self.assertEqual(result["status"], "passed", result)
        self.assertTrue(result["comparison_executed"])
        self.assertTrue(all(not r["finite_shoe_validation"] for r in result["results"]))


if __name__ == "__main__":
    unittest.main()
