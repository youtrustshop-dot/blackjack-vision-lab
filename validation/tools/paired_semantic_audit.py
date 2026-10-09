"""Audit the consumed VISION-025 lot offline; never replay a provider request.

Default is read-only. --export writes only the new public aggregate. Private
receipts, frames, payloads, failed rows, frozen sources and ledger stay unchanged.
"""
import argparse
from decimal import Decimal
import json
import socket
import subprocess
import time
from unittest.mock import patch

from bjlab.api_access_policy import MATRIX
from bjlab.grounded_state import GroundedResult
from bjlab.live_state import LiveObservation
from bjlab.research_budget import CANONICAL_LEDGER
from validation.tools.api_reader_tournament import ROOT, file_hash
from validation.tools.grounded_corpus import save
from validation.tools.paired_semantic_prepare import OUTPUT, PAIRS, checked, ledger_snapshot
from validation.tools.paired_semantic_smoke import evaluate, choose_candidate

PUBLIC = ROOT/'validation/results/paired-semantic-hybrid'


def denied(*args, **kwargs):
    raise AssertionError('Offline audit cannot use network, DNS or subprocesses.')


def audit():
    before = ledger_snapshot(); _, frames, truths = checked()
    first = json.loads((OUTPUT/'responses.json').read_text())
    middle = json.loads((OUTPUT/'completed-responses.json').read_text())
    rows = json.loads((OUTPUT/'final-responses.json').read_text())
    final = json.loads((OUTPUT/'final-summary.json').read_text())
    if (len(first) != 1 or len(middle) != 3 or len(rows) != 4 or
            rows[:1] != first or rows[:3] != middle or
            [(r['case_id'], r['candidate']) for r in rows] != list(PAIRS)):
        raise AssertionError('Consumed prefix/order/count changed.')
    for row in rows:
        frame = frames[row['case_id']][1]
        observation = LiveObservation.model_validate(row['observation']) if row['observation'] else None
        result = GroundedResult(frame.frame_id, row['candidate'], row['status'], observation,
            row['elapsed_ms'], row['diagnostics'])
        # Dataclass tuple fields serialize as lists in the immutable JSON receipt.
        replay = json.loads(json.dumps(evaluate(result, truths[row['case_id']], frame), allow_nan=False))
        if replay != row['metrics']:
            raise AssertionError('Frozen shared evaluator no longer reproduces a consumed row.')
    summaries, winner = choose_candidate(rows)
    if winner is not None or summaries != final['candidates'] or final['hybrid']['executed']:
        raise AssertionError('Conditional hybrid must remain skipped under the frozen gate.')
    claims = []
    for index, (case, name) in enumerate(PAIRS):
        suffix = '-last-pair' if index == 3 else ''
        claim_path = OUTPUT/(case+'-'+name+suffix+'.claim.json')
        claim = json.loads(claim_path.read_text())
        if claim['retry'] != 0 or claim['payload_sha256'] != frames[case][0]['payloads'][name]['canonical_sha256']:
            raise AssertionError('Consumed payload claim differs from its frozen input.')
        claims.append(file_hash(claim_path))
    stops = [json.loads((OUTPUT/name).read_text()) for name in ('stop.json', 'completed-stop.json', 'final-stop.json')]
    if not (stops[0]['old_entries_unchanged'] and stops[1]['first_101_entries_unchanged'] and
            stops[2]['first_103_entries_unchanged'] and stops[2]['consumed_responses_unchanged'] and
            all(s['runtime_disarmed'] for s in stops) and stops[2]['pool_closed']):
        raise AssertionError('Original history or final stop receipt changed.')
    policy = json.loads(MATRIX.read_text())['api_access_policy']
    if (policy['inference_authorized'] is not False or policy['max_requests'] != 0 or Decimal(policy['max_usd']) != 0 or
            before != final['ledger_after'] or before['receipt']['requests_attempted'] != 104):
        raise AssertionError('Runtime or the final canonical checkpoint changed.')
    entries = json.loads(CANONICAL_LEDGER.read_text())['entries']
    reported = sum((Decimal(r['diagnostics'].get('price_based_upper_cost_usd', '0')) for r in rows), Decimal(0))
    increase = Decimal(final['accounted_upper_increase_usd'])
    public = {**final, 'offline_audit': {'frozen_sources_pixels_models_history_verified': True,
        'old_response_prefixes_unchanged': True, 'all_four_metrics_reproduced': True,
        'four_unique_submission_claim_sha256': claims, 'provider_calls': 0,
        'audit_source_sha256': file_hash(__file__), 'ledger_sha256_unchanged': before['sha256']},
        'new_accounting': {'reported_usage_price_upper_usd': str(reported),
            'unreconciled_timeout_reservation_usd': str(increase-reported),
            'accounted_upper_increase_usd': str(increase),
            'total_new_reserved_usd': str(sum((Decimal(e['reserved_usd']) for e in entries[100:]), Decimal(0))),
            'initial_whole_lot_worst_case_usd': '2.2138736', 'new_inference_attempts': 4,
            'new_reported_usage_requests': 2, 'new_unreconciled_timeouts': 2,
            'invoice_or_current_balance_verified': False},
        'measurement_clock': {'api': 'time.monotonic_ns',
            'declared_resolution_ms': time.get_clock_info('monotonic').resolution*1000,
            'meaning': 'Zeros mean below clock resolution; timeout finalization may overshoot deadline. No late observation is accepted.'},
        'main_remaining_limit': 'Timely strictly valid R1 availability: Luna header waits and Gemini numeric-label validation; no passing candidate for hybrid.',
        'not_measured': ['native Windows capture or advisor paint', 'session/R2 reliability',
            'external-provider transfer', 'causal pooling speedup', 'server-versus-network header-wait split']}
    if ledger_snapshot() != before:
        raise AssertionError('Read-only audit mutated the canonical allowance.')
    return public


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    with patch.object(socket, 'socket', denied), patch.object(socket, 'getaddrinfo', denied), patch.object(subprocess, 'run', denied):
        public = audit()
    if args.export:
        PUBLIC.mkdir(parents=True, exist_ok=True)
        save(PUBLIC/'summary.json', public)
    print(json.dumps({'offline_audit_passed': True, 'provider_calls': 0, 'consumed_comparisons': 4,
        'hybrid_executed': False, 'runtime_disarmed': True, 'exported': args.export,
        'ledger_after': public['ledger_after']['receipt']}))
