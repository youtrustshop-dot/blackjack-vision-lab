"""Independent always-stand differential: random initial hands, fresh finite shoes.

No finite solver, generated policy, count strategy or forced cards are used.
Native audit/UI serialization is suppressed; card identities are deterministic
opaque values instead of UUIDs, leaving gameplay and uniform shuffle unchanged.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules
from bjlab.references import FreeBJAdapter, independent_batch_statistics, _sha256
from bjlab.simulator import BlackjackSession, Shoe, Card, RANKS, SUITS


class AuditlessSession(BlackjackSession):
    def _emit(self, kind, payload):
        return {"kind": kind, "payload": payload}

    def snapshot(self):
        return {}


class IdentityOnlyShoe(Shoe):
    def shuffle(self):
        self.generation += 1
        self.id = f"shoe-{self.generation}"
        self.cards = [Card(f"{self.id}-{deck}-{suit}-{rank}", rank, suit)
                      for deck in range(self.decks) for suit in SUITS for rank in RANKS]
        self.rng.shuffle(self.cards)
        self.initial_counts = (4 * self.decks,) * 9 + (16 * self.decks,)


def native_batch(rules, seed, rounds):
    session = AuditlessSession(rules, seed=seed, bankroll=1e9)
    session.shoe = IdentityOnlyShoe(rules.decks, session.rng)
    total = 0.
    for _ in range(rounds):
        session.deal(1)
        while session.phase != "settled":
            action = ("decline_insurance" if session.phase == "insurance" else
                      "continue" if session.phase == "early_surrender" else "stand")
            session.action(action)
        total += session.round_profit
    assert abs(total - session.total_profit) < 1e-10
    return {"seed": seed, "rounds": rounds, "ev": total / rounds}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--build-receipt", required=True)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=271828)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    # Native ratios are checked before the next round; FreeBJ cuts after the
    # current round. With threshold one card, both reshuffle every round, also
    # removing upstream dealer-draw differences after a player natural from the
    # next round's distribution.
    rules = Rules(penetration=1 / (6 * 52))
    reference = FreeBJAdapter(args.binary, checkout=args.checkout,
                             build_receipt=args.build_receipt).run_batches(
        rules, batches=args.batches, rounds_per_batch=args.rounds,
        action="stand", fresh_shoe=True, timeout_seconds=60)
    if reference.get("status") != "executed" or not reference.get("validation_eligible"):
        raise RuntimeError("FreeBJ unconditional experiment unavailable: " + json.dumps(reference))
    means, native_results = [], []
    started = time.perf_counter()
    for index in range(args.batches):
        batch = native_batch(rules, args.seed + index * 104729, args.rounds)
        native_results.append(batch)
        delta = batch["ev"] - reference["batch_results"][index]["ev"]
        means.append(delta)
        print(f"batch {index + 1}/{args.batches}: native={batch['ev']:.6f} FreeBJ={reference['batch_results'][index]['ev']:.6f}", flush=True)
    native_stats = independent_batch_statistics(r["ev"] for r in native_results)
    differences = independent_batch_statistics(means)
    passed = differences["interval95"][0] <= 0 <= differences["interval95"][1]
    result = {"schema_version": 1, "status": "passed" if passed else "failed", "passed": passed,
              "comparison_executed": True, "exact": False, "rules": asdict(rules),
              "policy": "always stand; decline insurance; continue early-surrender phase; fixed wager one",
              "conditioning": "unconditional initial deal", "shoe": "six decks freshly shuffled every round",
              "native": {"sampling": native_stats, "batch_results": native_results,
                         "gameplay_source_sha256": _sha256(ROOT / "bjlab" / "simulator.py"),
                         "settlement_source_sha256": _sha256(ROOT / "bjlab" / "engine.py")},
              "freebj": reference, "native_minus_reference": differences,
              "statistical_method": "Independent equal-size batch differences; t interval under approximately normal batch means.",
              "seed_note": "Native deterministic seed list; independent upstream FreeBJ entropy streams have no exposed seeds.",
              "native_wrapper": "Disable event storage/snapshot serialization; replace UUID identity generation only. Rank shuffle and gameplay production code unchanged.",
              "limitations": ["One fixed stand policy only; no optimal continuation, splits, count deviations or betting validation.",
                               "95% statistical consistency check can fail by chance; no repeat-until-pass procedure."],
              "latency_seconds": time.perf_counter() - started,
              "executed_at": datetime.now(timezone.utc).isoformat()}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "native": native_stats, "freebj": reference["sampling"],
                      "difference": differences, "output": str(target)}, indent=2), flush=True)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
