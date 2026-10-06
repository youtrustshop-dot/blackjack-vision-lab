"""Consume ONLY the fourth unused comparison of the original VISION-025 lot.

The first three rows, their sources and stop receipts are immutable. Gemini's
HTTP200/local-validation rejection is a candidate quality failure, not an HTTP
schema/access/accounting failure. Completing the distinct final Luna case does
not retry Gemini or change any reader/evaluator contract. Both candidates have
already failed the frozen two-of-two gate, so this script has no hybrid path.
Default is an offline preflight; --run requires the original freeze checksum.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import time

from bjlab.api_access_policy import MATRIX
from bjlab.controlled_http import resolve_scope
from bjlab.paired_persistent_http import PersistentScopedTransport
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, file_hash
from validation.tools.cloud_connection_diagnosis import credentials, exception_types
from validation.tools.grounded_corpus import save
from validation.tools.paired_cloud_prepare import candidates, NAMES
from validation.tools.paired_semantic_prepare import OUTPUT, EPOCH, MAX_BATCH_USD, PAIRS, checked, ledger_snapshot
from validation.tools.paired_semantic_smoke import PRICE_CHECK, claim, set_policy, make_reader, bind_frozen, evaluate, choose_candidate

THREE_ROW_LEDGER = 'e4d30852a9962aaa84582ae044d04dd944141420f6ba0b4e4d791912769f322b'
THREE_ROW_RESPONSES = 'fe362519d4882df1f7359caabf6ce17b25ad26b331ad38c7c3fc64b5c3a2f0cd'


def last_pair(rows):
    if (len(rows) != 3 or [(r['case_id'], r['candidate']) for r in rows] != list(PAIRS[:3]) or
            rows[0]['status'] != 'timeout' or rows[0]['observation'] is not None or
            rows[1]['status'] != 'completed' or not rows[1]['metrics']['semantic_timely_correct_usable_r1']):
        raise PermissionError('Only the exact three consumed rows permit the remaining distinct pair.')
    rejected = rows[2]; diagnostics = rejected['diagnostics']
    if (rejected['status'] != 'error' or rejected['observation'] is not None or
            diagnostics.get('error_type') != 'ValidationError' or
            diagnostics.get('validation_issues') != [{'location': ['n', 0], 'type': 'value_error'}] or
            diagnostics.get('transport', {}).get('http_status') != 200 or
            diagnostics.get('unreconciled_usage') or 'price_based_upper_cost_usd' not in diagnostics):
        raise PermissionError('Not the audited HTTP200/local-quality rejection; do not resume.')
    if choose_candidate(rows)[1] is not None:
        raise PermissionError('The frozen gate outcome changed.')
    return PAIRS[3]


def prerequisites(freeze_sha256):
    if file_hash(OUTPUT/'freeze.json') != freeze_sha256:
        raise PermissionError('Original external freeze checksum differs.')
    freeze, frames, truths = checked(); before = ledger_snapshot()
    if (before['sha256'] != THREE_ROW_LEDGER or before['receipt']['requests_attempted'] != 103 or
            before['receipt']['max_requests'] != 105 or before['receipt']['unknown_charge_requests'] != 14 or
            before['receipt']['stopped'] or file_hash(OUTPUT/'completed-responses.json') != THREE_ROW_RESPONSES):
        raise PermissionError('The unused fourth-pair checkpoint changed; no automatic replay.')
    rows = json.loads((OUTPUT/'completed-responses.json').read_text()); pair = last_pair(rows)
    original = json.loads(MATRIX.read_text())['api_access_policy']
    if (original.get('inference_authorized') is not False or original.get('max_requests') != 0 or
            Decimal(original.get('max_usd', '-1')) != 0):
        raise PermissionError('Runtime must start disarmed.')
    if datetime.now(timezone.utc).date().isoformat() != PRICE_CHECK['verified_utc_date']:
        raise PermissionError('Pricing verification expired; no automatic future run.')
    configs = candidates(); reserve = configs[pair[1]].config.reserve_usd
    worst = 2*sum((r.config.reserve_usd for r in configs.values()), Decimal(0))+max(
        r.config.reserve_usd for r in configs.values())
    entries = json.loads(CANONICAL_LEDGER.read_text())['entries']
    if (worst != MAX_BATCH_USD or len(entries) != 103 or
            sum((Decimal(e['reserved_usd']) for e in entries[100:]), Decimal(0))+reserve > MAX_BATCH_USD or
            Decimal(before['receipt']['accounted_upper_usd'])+reserve > Decimal('8')):
        raise PermissionError('Unchanged whole-lot or lifetime allowance would be exceeded.')
    return freeze, frames, truths, before, original, rows, pair, reserve, entries


def run(freeze_sha256):
    freeze, frames, truths, before, original, rows, pair, reserve, old_entries = prerequisites(freeze_sha256)
    prior = json.loads((OUTPUT/'completed-summary.json').read_text())
    claim(OUTPUT/'last-pair.claim.json', {'epoch': EPOCH, 'pair': pair, 'remaining_inferences': 1,
        'hybrid_permitted': False, 'no_retries': True, 'ledger_before': before,
        'original_freeze_sha256': freeze_sha256, 'consumed_responses_sha256': THREE_ROW_RESPONSES,
        'completion_source_sha256': file_hash(__file__), 'reason': 'Complete only the distinct fourth frozen comparison.'})
    transport = None; access = None; cold = {}; stop = None
    try:
        credentials(); start = time.monotonic_ns(); scope = resolve_scope()
        cold['fresh_dns_preresolution_ms'] = (time.monotonic_ns()-start)/1e6
        budget = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID, max_requests=105, max_usd='8')
        transport = PersistentScopedTransport(provider='openai', authorization_epoch=EPOCH, budget=budget, dns_scope=scope)
        reply = transport.metadata(); verified = reply.get('id') == candidates()[NAMES[0]].config.model
        access = {'candidate': NAMES[0], 'http_status': 200, 'exact_model_access': verified,
            'client_initialization_ms': transport.initialization_ms, 'timing': dict(transport.timings)}
        if not verified or ledger_snapshot() != before:
            raise PermissionError('Fresh read-only model access or canonical history failed.')
        if time.monotonic()+3 >= scope['api.openai.com']['expires_at']:
            raise PermissionError('Fresh DNS lease cannot admit the whole deadline.')
        set_policy({**original, 'inference_authorized': True, 'authorization_epoch': EPOCH,
            'max_requests': 1, 'max_usd': str(reserve), 'scope': 'VISION-025: ONLY the fourth unused pair; no hybrid or retry.'})
        case, name = pair; record, frame = frames[case]
        reader = make_reader(name, frame, budget, transport); bind_frozen(reader, transport, record, frame, '-last-pair')
        result = reader.read(frame, capture_ns=time.monotonic_ns())
        rows.append({'case_id': case, 'candidate': name, 'independent_session': record['independent_session'],
            'status': result.status, 'elapsed_ms': result.elapsed_ms,
            'observation': result.observation.model_dump() if result.observation else None,
            'diagnostics': result.diagnostics, 'metrics': evaluate(result, truths[case], frame)})
        save(OUTPUT/'final-responses.json', rows)
        print(json.dumps({'candidate': name, 'case': case, 'status': result.status,
            'complete_ms': result.elapsed_ms, 'semantic_r1': rows[-1]['metrics']['semantic_timely_correct_usable_r1']}), flush=True)
    except Exception as exc:
        stop = {'exception_types': exception_types(exc), 'raw_message_retained': False}
    finally:
        set_policy(original)
        if transport is not None:
            transport.close()
        after = ledger_snapshot()
        preserved = json.loads(CANONICAL_LEDGER.read_text())['entries'][:103] == old_entries
        disarmed = json.loads(MATRIX.read_text())['api_access_policy'] == original
        save(OUTPUT/'final-stop.json', {'runtime_disarmed': disarmed, 'pool_closed': transport is None or transport._closed,
            'first_103_entries_unchanged': preserved, 'consumed_responses_unchanged': file_hash(OUTPUT/'completed-responses.json') == THREE_ROW_RESPONSES,
            'ledger_before': before, 'ledger_after': after, 'unused_new_slots_closed': 105-after['receipt']['requests_attempted'],
            'no_automatic_resumption': True, 'stop': stop})
    summaries, winner = choose_candidate(rows)
    if winner is not None:
        raise PermissionError('Impossible promotion: consumed timeout/rejection cannot be erased.')
    public_rows = [{k: r[k] for k in ('case_id', 'candidate', 'independent_session', 'status', 'elapsed_ms', 'metrics')} |
        {'usage': r['diagnostics'].get('usage'), 'provider_usage': r['diagnostics'].get('provider_usage'),
         'reported_usage_upper_usd': r['diagnostics'].get('price_based_upper_cost_usd'),
         'timing': r['diagnostics']['timing'], 'stage_spans': r['diagnostics']['stage_spans'],
         'network': r['diagnostics'].get('transport'), 'error_type': r['diagnostics'].get('error_type'),
         'validation_issues': r['diagnostics'].get('validation_issues'),
         'output_json_sha256': r['diagnostics'].get('output_json_sha256')} for r in rows]
    final = {**prior, 'rows': public_rows, 'attempted_comparisons': len(rows), 'candidates': summaries,
        'selected_for_single_trial': None, 'hybrid': {'executed': False,
            'reason': 'neither_candidate_passed_frozen_correctness_latency_gate'},
        'ledger_after': after, 'accounted_upper_increase_usd': str(Decimal(after['receipt']['accounted_upper_usd'])-
            Decimal(freeze['ledger_before']['receipt']['accounted_upper_usd'])),
        'accounted_margin_usd': str(Decimal('8')-Decimal(after['receipt']['accounted_upper_usd'])),
        'unused_new_slots_closed': 105-after['receipt']['requests_attempted'], 'last_pair_access': access,
        'last_pair_cold': cold, 'first_103_entries_unchanged': preserved, 'runtime_disarmed': disarmed,
        'stop': stop, 'original_stops_retained': True,
        'execution_segments': ['initial first pair stopped on timeout',
            'two distinct Gemini pairs stopped on local validation rejection',
            'only the fourth distinct Luna pair; all contracts unchanged'],
        'completion_scope': 'Original four comparisons exactly once; no hybrid, new allowance, retry or follow-on batch.'}
    save(OUTPUT/'final-summary.json', final)
    print(json.dumps({'comparisons': len(rows), 'hybrid_executed': False, 'runtime_disarmed': disarmed,
        'new_reservations_in_whole_lot': after['receipt']['requests_attempted']-100, 'stop': stop}), flush=True)
    return final


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run', action='store_true')
    parser.add_argument('--freeze-sha256', required=True); args = parser.parse_args()
    if args.run:
        run(args.freeze_sha256)
    else:
        values = prerequisites(args.freeze_sha256)
        print(json.dumps({'mode': 'offline_only', 'provider_calls': 0, 'remaining_pair': values[6],
            'reservation_usd': str(values[7]), 'hybrid_permitted': False, 'ledger': values[3]}))
