"""Reconcile executed nonsplit fresh-shoe reference artifacts with native EVs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules, initial_counts, card_rank
from bjlab.references import compare_action_values, _sha256
from bjlab.solver import Solver


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hhoppe", help="Executed 10,6 versus 10 default-rules artifact")
    parser.add_argument("--freebj", help="Executed stand 10,6 versus 10 fresh-shoe artifact")
    parser.add_argument("--output", required=True)
    parser.add_argument("--player", default="10,6")
    parser.add_argument("--dealer", default="10")
    parser.add_argument("--tolerance", type=float, default=1e-10)
    args = parser.parse_args()
    rules = Rules()
    player = [card_rank(c) for c in args.player.split(",")]
    up = card_rank(args.dealer)
    counts = list(initial_counts(rules.decks))
    for rank in (*player, up):
        counts[rank - 1] -= 1
    native = Solver(rules).analyze(player, up, tuple(counts), peek_resolved=True,
                                  timeout_ms=15000, max_nodes=2000000)
    comparisons = []
    for name, path in (("hhoppe", args.hhoppe), ("freebj", args.freebj)):
        if not path:
            continue
        reference = json.loads(Path(path).read_text(encoding="utf-8"))
        if reference.get("status") != "executed" or not reference.get("comparison_executed"):
            comparisons.append({"engine": name, "status": "not_executed", "passed": False})
            continue
        # This harness intentionally supports one fully specified sample only.
        from dataclasses import asdict
        if reference.get("requested_rules") != asdict(rules):
            raise ValueError("sample reference rules differ from native default rules")
        if name == "hhoppe":
            if reference.get("conditioning") != "negative-peek" or reference.get("method") != "external-finite-fresh-shoe-pruned-dp":
                raise ValueError("incompatible hhoppe sample model")
            expected_state = {"player": player, "dealer": up, "counts": counts,
                              "peek_resolved": True, "from_split": False}
            if reference.get("state") != expected_state:
                raise ValueError("reference state differs or is missing; regenerate with current adapter")
            # This hand's hit continuation needs no splits/resplits or noninitial doubles.
            comparison = compare_action_values(native, reference, tolerance=args.tolerance, equivalent_model=True)
            comparisons.append(dict(comparison, engine=name, reference_sha256=_sha256(path),
                                    reference_exact=False, scope=f"nonsplit {player} versus {up} fresh six-deck S17"))
        else:
            comparisons.append({"engine": name, "status": "unsupported", "passed": False,
                "reference_sha256": _sha256(path),
                "reason": "Pinned forced-card shoe is not exchangeable conditioned on shown cards; use unconditional_stand.py instead."})
    result = {"status": "passed" if comparisons and all(c["passed"] for c in comparisons) else "failed",
              "comparisons": comparisons, "native": native, "executed_at": datetime.now(timezone.utc).isoformat(),
              "scope": "One nonsplit hand only; no general split, resplit, OBO, depleted-shoe or table validation."}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
