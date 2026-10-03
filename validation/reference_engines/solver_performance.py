"""Record concrete finite-solver timing; no general exactness inference."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules, initial_counts
from bjlab.solver import Solver
from bjlab.references import _sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--max-nodes", type=int, default=1000000)
    parser.add_argument("--label", default="current")
    args = parser.parse_args()
    rules = Rules()
    counts = list(initial_counts(rules.decks))
    for rank in (2, 8, 4):
        counts[rank - 1] -= 1
    result = Solver(rules).analyze([2, 8], 4, counts, peek_resolved=False,
                                 timeout_ms=args.timeout_ms, max_nodes=args.max_nodes)
    artifact = {"label": args.label, "scenario": "player2,8 dealer4 freshsixdecksS17",
                "solver_source_sha256": _sha256(ROOT / "bjlab" / "solver.py"),
                "budget": {"timeout_ms": args.timeout_ms, "max_nodes": args.max_nodes},
                "counts": counts, "result": result, "executed_at": datetime.now(timezone.utc).isoformat()}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
