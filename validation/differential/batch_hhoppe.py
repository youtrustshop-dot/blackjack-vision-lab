"""Pinned, measured finite-shoe comparisons; no external runtime dependency.

The reference is loaded once in this development-only process. Its effort
pruning is declared; agreement does not turn it into a proven exact oracle.
All inputs are selected and saved before any result is inspected.
"""
from __future__ import annotations

import argparse
import contextlib
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import io
import itertools
import json
from pathlib import Path
import random
import socket
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation" / "reference_engines"))
from bjlab.engine import Rules, hand_value, initial_counts, legal_actions
from bjlab.references import _checkout_provenance, _pin, compare_action_values, hhoppe_rule_mapping
from bjlab.solver import Solver
from hhoppe_worker import deny_network, load_core


def make_states(number: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    hands = [list(cards) for length in (2, 3, 4)
             for cards in itertools.combinations_with_replacement(range(1, 11), length)
             if 15 <= hand_value(cards)[0] <= 21
             and not (length == 2 and (cards[0] == cards[1] or cards == (1, 10)))]
    groups = []
    for decks in (1, 2, 4, 6, 8):
        for h17 in (False, True):
            rules = Rules(decks=decks, hit_soft17=h17)
            candidates = []
            for player in hands:
                for dealer in range(1, 11):
                    counts = list(initial_counts(decks))
                    for rank in (*player, dealer):
                        counts[rank - 1] -= 1
                    if min(counts) >= 0:
                        candidates.append({"rules": asdict(rules), "player": player,
                                           "dealer": dealer, "counts": counts,
                                           "peek_resolved": True,
                                           "legal_actions": legal_actions(player, rules)})
            rng.shuffle(candidates)
            groups.append(candidates)
    per_group, extra = divmod(number, len(groups))
    if any(len(group) < per_group + bool(extra) for group in groups):
        raise ValueError("Too many unique states requested")
    states = []
    for index, group in enumerate(groups):
        states.extend(group[:per_group + (index < extra)])
    for state in states:
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        state["state_id"] = hashlib.sha256(encoded).hexdigest()[:20]
    return states


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261003)
    parser.add_argument("--effort", type=int, default=3)
    parser.add_argument("--tolerance", type=float, default=1e-7)
    args = parser.parse_args()
    if args.cases < 1 or args.tolerance < 0 or not 0 <= args.effort <= 4:
        raise ValueError("Invalid experiment configuration")
    pin = _pin("hhoppe/blackjack")
    provenance = _checkout_provenance(args.checkout, pin)
    states = make_states(args.cases, args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    inputs_path = args.output / "inputs.json"
    inputs_path.write_text(json.dumps({"seed": args.seed, "states": states}, indent=2), encoding="utf-8")
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    urllib.request.urlopen = deny_network
    with contextlib.redirect_stdout(io.StringIO()):
        module, source_hash = load_core(args.checkout, args.effort)
    provenance["source_sha256"] = source_hash
    results, failures = [], []
    start = time.perf_counter()
    previous_rules = None
    for index, state in enumerate(states):
        rules = Rules(**state["rules"])
        if rules != previous_rules:
            for value in module.__dict__.values():
                if callable(value) and hasattr(value, "cache_clear"):
                    value.cache_clear()
            previous_rules = rules
        native = Solver(rules).analyze(state["player"], state["dealer"], state["counts"],
                    peek_resolved=True, timeout_ms=15000, max_nodes=2000000)
        mapping = hhoppe_rule_mapping(rules)
        reference_rules = module.Rules(**mapping)
        strategy = module.Strategy(attention=module.Attention.HAND_AND_INITIAL_CARDS_IN_PRIOR_SPLITS)
        player = state["player"]
        reference_state = (*sorted(player[:2]), *sorted(player[2:])), state["dealer"], ()
        ref_start = time.perf_counter()
        values = {action: float(module.reward_for_action(reference_state, reference_rules,
                                 strategy, module.Action[action.upper()]))
                  for action in state["legal_actions"]}
        reference = {"status": "executed", "actions": values,
                     "best_action": max(values, key=values.get), "exact": False,
                     "latency_ms": (time.perf_counter() - ref_start) * 1000}
        comparison = compare_action_values(native, reference, tolerance=args.tolerance, equivalent_model=True)
        best = native.get("best_action")
        # Equal-valued actions within the preset tolerance are not discrepancies.
        best_agrees = best in values and max(values.values()) - values[best] <= args.tolerance
        passed = bool(native.get("exact") and comparison["passed"] and best_agrees)
        result = {"state_id": state["state_id"], "native": native, "reference": reference,
                  "effective_reference_rules": mapping, "comparison": comparison,
                  "best_action_agrees_with_tolerance": best_agrees, "passed": passed}
        results.append(result)
        if not passed:
            failures.append({**state, "our_ev": native.get("actions"), "our_action": best,
                             "reference_ev": values, "reference_action": reference["best_action"],
                             "comparison": comparison, "native_exact": native.get("exact"),
                             "investigation_status": "unexplained"})
        if (index + 1) % 100 == 0:
            print(json.dumps({"completed": index + 1, "failures": len(failures),
                              "elapsed_seconds": round(time.perf_counter() - start, 2)}), flush=True)
    report = {"schema_version": 1, "status": "failed" if failures else "passed",
              "comparison_executed": True, "cases": len(results), "seed": args.seed,
              "rule_configurations": 10, "tolerance": args.tolerance, "effort": args.effort,
              "exact_reference": False, "provenance": provenance,
              "native_source_sha256": hashlib.sha256((ROOT / "bjlab" / "solver.py").read_bytes()).hexdigest(),
              "input_sha256": hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
              "elapsed_seconds": time.perf_counter() - start, "failures": len(failures),
              "scope": "Unique fresh-shoe nonsplit 2/3/4-card hands with totals 15..21; five deck counts and S17/H17; negative peek; no arbitrary depleted shoe or split validation.",
              "limitations": ["Upstream effort pruning has no proven error bound.",
                              "High totals selected to bound exhaustive computation; not uniform gameplay states."],
              "executed_at": datetime.now(timezone.utc).isoformat(), "results": results}
    (args.output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    (args.output / "DifferentialFailure.json").write_text(json.dumps({"schema_version": 1, "failures": failures}, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
