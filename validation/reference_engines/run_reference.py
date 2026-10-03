"""Offline optional reference CLI. Install/build reference dependencies separately."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules, initial_counts, card_rank
from bjlab.references import FreeBJAdapter, HhoppeAdapter, run_golden_validation, reference_catalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", choices=("catalog", "golden", "freebj", "hhoppe"))
    parser.add_argument("--checkout")
    parser.add_argument("--binary", default="freebj")
    parser.add_argument("--build-receipt")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--rules", help="Path to JSON object with native Rules fields")
    parser.add_argument("--player", default="10,6")
    parser.add_argument("--dealer", default="10")
    parser.add_argument("--actions", default="stand,hit,double,surrender")
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=100000)
    parser.add_argument("--effort", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output")
    args = parser.parse_args()
    rules = Rules(**json.loads(Path(args.rules).read_text(encoding="utf-8"))) if args.rules else Rules()
    if args.engine == "catalog":
        result = reference_catalog()
    elif args.engine == "golden":
        result = run_golden_validation()
    elif args.engine == "hhoppe":
        if not args.checkout:
            parser.error("hhoppe requires --checkout pinned external source directory")
        result = HhoppeAdapter(args.checkout, python=args.python).analyze(
            rules, args.player.split(","), args.dealer, actions=args.actions.split(","),
            effort=args.effort, timeout_seconds=args.timeout)
    else:
        selected = args.actions.split(",")
        if len(selected) != 1:
            parser.error("FreeBJ requires one forced action via --actions stand (or hit, double, split, surrender)")
        result = FreeBJAdapter(args.binary, checkout=args.checkout, build_receipt=args.build_receipt).run_batches(
            rules, batches=args.batches, rounds_per_batch=args.rounds, timeout_seconds=args.timeout,
            player=args.player.split(","), dealer=args.dealer, action=selected[0], fresh_shoe=True)
    encoded = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    if result.get("status") in ("failed", "unsupported", "skipped"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
