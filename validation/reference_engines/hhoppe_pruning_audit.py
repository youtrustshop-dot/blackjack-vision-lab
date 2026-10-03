"""Diagnostic EFFORT4 recheck of frozen EFFORT3 failures; original results retained."""
from __future__ import annotations
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules
from bjlab.references import _checkout_provenance, _pin, _sha256, hhoppe_rule_mapping, compare_action_values
from hhoppe_worker import deny_network, load_core


def magnitude(case, action=None):
    differences = case['comparison']['differences']
    return abs(differences.get(action, 0)) if action else max(abs(v) for v in differences.values())


def select_sample(cases):
    ordered = sorted(cases, key=magnitude)
    sample = [cases[0], ordered[-1], max(cases, key=lambda c: magnitude(c, 'stand')),
              ordered[len(ordered)//2]]
    selected = []
    for case in sample:
        if case['state_id'] not in {c['state_id'] for c in selected}:
            selected.append(case)
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--failures', type=Path, required=True)
    parser.add_argument('--original-report', type=Path, required=True)
    parser.add_argument('--all', action='store_true', help='Recheck every frozen failure rather than diagnostic sample')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    failures = json.loads(args.failures.read_text(encoding='utf-8'))['failures']
    original = json.loads(args.original_report.read_text(encoding='utf-8'))
    tolerance = original['tolerance']
    if original['effort'] != 3 or tolerance != 1e-7:
        raise ValueError('This audit expects the original preregistered effort3/1e-7 experiment')
    if _sha256(ROOT/'bjlab/solver.py') != original['native_source_sha256']:
        raise ValueError('Native source changed after frozen original experiment')
    selected = failures if args.all else select_sample(failures)
    pin = _pin('hhoppe/blackjack')
    provenance = _checkout_provenance(args.checkout, pin)
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    urllib.request.urlopen = deny_network
    with contextlib.redirect_stdout(io.StringIO()):
        module, source_hash = load_core(args.checkout, 4)
    provenance['source_sha256'] = source_hash
    if source_hash != original['provenance']['source_sha256']:
        raise ValueError('Reference source changed after original experiment')
    results = []
    started = time.perf_counter()
    for index, case in enumerate(selected):
        # Independent per-case caches avoid retaining large effort4 dealer states.
        for value in module.__dict__.values():
            if callable(value) and hasattr(value, 'cache_clear'):
                value.cache_clear()
        rules = Rules(**case['rules'])
        reference_rules = module.Rules(**hhoppe_rule_mapping(rules))
        strategy = module.Strategy(attention=module.Attention.HAND_AND_INITIAL_CARDS_IN_PRIOR_SPLITS)
        cards = case['player']
        state = (*sorted(cards[:2]), *sorted(cards[2:])), case['dealer'], ()
        start = time.perf_counter()
        ev = {action: float(module.reward_for_action(state, reference_rules, strategy,
                           module.Action[action.upper()])) for action in case['legal_actions']}
        reference = {'status': 'executed', 'actions': ev, 'exact': False}
        comparison = compare_action_values({'actions': case['our_ev']}, reference,
                                           tolerance=tolerance, equivalent_model=True)
        delta3 = magnitude(case)
        delta4 = max(abs(value) for value in comparison['differences'].values())
        entry = {'state_id': case['state_id'], 'rules': case['rules'], 'player': cards,
                 'dealer': case['dealer'], 'counts': case['counts'], 'native_ev': case['our_ev'],
                 'original_effort3_ev': case['reference_ev'], 'effort4_ev': ev,
                 'original_comparison': case['comparison'], 'diagnostic_comparison': comparison,
                 'max_abs_diff_effort3': delta3, 'max_abs_diff_effort4': delta4,
                 'difference_reduction_factor': delta3/delta4 if delta4 else None,
                 'original_best_action': case['our_action'], 'effort4_best_action': max(ev, key=ev.get),
                 'original_failed': True, 'investigation_status': 'consistent_with_reference_card_tracking_truncation' if comparison['passed'] else 'unresolved',
                 'latency_ms': (time.perf_counter()-start)*1000}
        results.append(entry)
        print(json.dumps({'completed': index+1, 'total': len(selected), 'state_id': entry['state_id'],
                          'diff3': delta3, 'diff4': delta4, 'diagnostic_passed': comparison['passed'],
                          'elapsed_seconds': round(time.perf_counter()-started, 2)}), flush=True)
        # Persist partial diagnostics; completion is never inferred from missing rows.
        artifact = {'schema_version': 1, 'status': 'complete' if len(results) == len(selected) else 'partial',
                    'comparison_executed': True, 'exact_reference': False, 'diagnostic_only': True,
                    'original_report_status': original['status'], 'original_failure_count': len(failures),
                    'original_report_sha256': _sha256(args.original_report),
                    'original_failures_sha256': _sha256(args.failures),
                    'tolerance': tolerance, 'original_effort': 3, 'diagnostic_effort': 4,
                    'expected_cases': len(selected), 'completed_cases': len(results),
                    'selection': 'All original frozen failures' if args.all else 'First, maximum absolute EV difference, maximum stand difference, median failure; duplicates removed',
                    'diagnostic_failures': sum(not e['diagnostic_comparison']['passed'] for e in results),
                    'primary_mechanism': {'source_url': f"https://github.com/{pin['repository']}/blob/{pin['commit']}/blackjack.py#L1092",
                       'functions': ['make_recent', 'add_recent', 'reward_after_dealer_hits'],
                       'effort3_tracked_card_cap': 10, 'effort4_tracked_card_cap': 14,
                       'observed': 'At card cap add_recent returns the existing tuple, so subsequent dealer draws reuse probabilities without removing those drawn ranks.'},
                    'precision_note': 'Agreement at effort4 is evidence for truncation cause, not a proven global error bound or an exact reference. Original effort3 report remains failed; no tolerance/input/native-source change.',
                    'provenance': provenance, 'native_sha256': original['native_source_sha256'],
                    'elapsed_seconds': time.perf_counter()-started,
                    'executed_at': datetime.now(timezone.utc).isoformat(), 'results': results}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in artifact.items() if k not in ('results', 'provenance', 'primary_mechanism')}, indent=2))
    if artifact['diagnostic_failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
