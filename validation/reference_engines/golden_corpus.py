"""Executed independent nonsplit S17/H17 corpus; upstream remains approximate."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules, initial_counts, legal_actions
from bjlab.references import HhoppeAdapter, compare_action_values, _sha256
from bjlab.solver import Solver


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", required=True)
    parser.add_argument("--effort", type=int, default=3)
    parser.add_argument("--tolerance", type=float, default=1e-7)
    args = parser.parse_args()
    adapter = HhoppeAdapter(args.checkout, python=args.python)
    results = []
    for h17 in (False, True):
        rules = Rules(hit_soft17=h17)
        for label, player, dealer in (("hard10-v4", [2, 8], 4), ("hard12-v2", [10, 2], 2),
                                      ("hard16-v10", [10, 6], 10), ("soft18-v9", [1, 7], 9),
                                      ("soft19-v6", [1, 8], 6)):
            counts = list(initial_counts(rules.decks))
            for rank in (*player, dealer):
                counts[rank - 1] -= 1
            native = Solver(rules).analyze(player, dealer, counts, peek_resolved=True,
                                          timeout_ms=15000, max_nodes=2000000)
            reference = adapter.analyze(rules, player, dealer, counts=counts,
                       actions=legal_actions(player, rules), peek_resolved=True,
                       effort=args.effort, timeout_seconds=120)
            comparison = compare_action_values(native, reference, tolerance=args.tolerance, equivalent_model=True)
            best_agrees = native["best_action"] == reference.get("best_action") and native["exact"]
            entry = {"id": ("H17-" if h17 else "S17-") + label, "rules": asdict(rules),
                     "player": player, "dealer": dealer, "counts": counts, "native": native,
                     "reference": reference, "comparison": comparison, "best_action_agrees": best_agrees,
                     "passed": comparison["passed"] and best_agrees}
            results.append(entry)
            print(f"{entry['id']}: {'passed' if entry['passed'] else 'failed'} nodes={native.get('nodes')} native_ms={native['latency_ms']:.1f}", flush=True)
    unsupported = []
    for label, rules in (("double-none", Rules(double_rule="none")),
                        ("ENHC-all", Rules(enhc=True, dealer_peek=False, enhc_loss="all", surrender="none")),
                        ("ENHC-OBO", Rules(enhc=True, dealer_peek=False, enhc_loss="original", surrender="none")),
                        ("early-surrender", Rules(surrender="early"))):
        reference = adapter.analyze(rules, [10, 6], 10)
        unsupported.append({"id": label, "rules": asdict(rules), "status": reference["status"],
                            "reason": reference.get("reason"), "comparison_executed": False})
    all_passed = all(r["passed"] for r in results) and all(r["status"] == "unsupported" for r in unsupported)
    result = {"schema_version": 1, "status": "passed" if all_passed else "failed",
              "comparison_executed": True, "exact_reference": False, "cases": results,
              "unsupported_cases": unsupported, "tolerance": args.tolerance,
              "native_source_sha256": _sha256(ROOT / "bjlab" / "solver.py"),
              "precision_note": "Native complete enumerations compared to pinned effort-pruned reference; numerical agreement is sample validation, not a proven reference error bound.",
              "scope": "Fresh six-deck nonsplit initial hands, S17/H17, any-two doubling, DAS, late surrender; no arbitrary depleted shoe or split proof.",
              "executed_at": datetime.now(timezone.utc).isoformat()}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "cases": len(results), "unsupported": unsupported, "output": str(output)}, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
