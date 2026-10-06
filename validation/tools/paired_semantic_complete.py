"""Complete ONLY the three distinct unused comparisons of the authorized lot.

The first timeout/claim/stop are immutable. This corrects the overly broad global
timeout stop, not a retry/new batch/new allowance. Frozen prompts, pixels, gates,
evaluator and reader sources stay byte-identical. Unknown timeout charges remain
fully reserved; a new distinct input may use its own already authorized slot.
"""
from decimal import Decimal
import json
import time

from bjlab.controlled_http import resolve_scope
from bjlab.hybrid_evidence import FrozenGroundedLocal
from bjlab.paired_persistent_http import PersistentScopedTransport
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, FrozenLocalObservation, file_hash
from validation.tools.cloud_connection_diagnosis import credentials, exception_types
from validation.tools.grounded_corpus import save
from validation.tools.paired_cloud_prepare import candidates, NAMES
from validation.tools.paired_semantic_prepare import OUTPUT, EPOCH, MAX_BATCH_USD, PAIRS, checked, ledger_snapshot
from validation.tools.paired_semantic_smoke import (PRICE_CHECK, claim, set_policy, make_reader,
    bind_frozen, evaluate, choose_candidate, run_hybrid)
from bjlab.api_access_policy import MATRIX

FIRST_TIMEOUT_LEDGER = '004aa9745ae8818190123dcba0e29f50e205606e052aeeef046bcb44ebc5e74b'


def remaining_pairs(results):
    if (len(results) != 1 or (results[0]['case_id'], results[0]['candidate']) != PAIRS[0] or
            results[0]['status'] != 'timeout' or results[0]['observation'] is not None):
        raise PermissionError('Only the original first timeout permits this exact completion.')
    return PAIRS[1:]


def run():
    freeze, frames, truths = checked(); before = ledger_snapshot()
    if (before['sha256'] != FIRST_TIMEOUT_LEDGER or before['receipt']['requests_attempted'] != 101 or
            before['receipt']['max_requests'] != 105 or before['receipt']['unknown_charge_requests'] != 14 or
            before['receipt']['stopped']):
        raise PermissionError('The original single-timeout checkpoint changed; no automatic resumption.')
    original = json.loads(MATRIX.read_text())['api_access_policy']
    if (original.get('inference_authorized') is not False or original.get('max_requests') != 0 or
            Decimal(original.get('max_usd', '-1')) != 0):
        raise PermissionError('Runtime must start disarmed.')
    results = json.loads((OUTPUT/'responses.json').read_text()); pairs = remaining_pairs(results)
    # Never replace the prematurely stopped receipt or the already consumed row.
    receipt = json.loads((OUTPUT/'summary.json').read_text()); old_entries = json.loads(CANONICAL_LEDGER.read_text())['entries']
    maximum_remaining = sum((candidates()[n].config.reserve_usd for _, n in pairs), Decimal(0))+max(
        r.config.reserve_usd for r in candidates().values())
    if (maximum_remaining+Decimal(old_entries[-1]['reserved_usd']) > MAX_BATCH_USD or
            Decimal(before['receipt']['accounted_upper_usd'])+maximum_remaining > Decimal('8')):
        raise PermissionError('The unchanged whole-lot reservation or lifetime ceiling would be exceeded.')
    claim(OUTPUT/'remaining-three.claim.json', {'epoch': EPOCH, 'pairs': pairs, 'first_pair_never_retried': True,
        'whole_lot_maximum': 5, 'whole_lot_reservation_usd': str(MAX_BATCH_USD), 'ledger_before': before,
        'completion_source_sha256': file_hash(__file__),
        'frozen_original_sources_unchanged': True, 'reason': 'Complete three already authorized distinct cases; retain timeout reservation.'})
    transports, access, cold = {}, [], {}; stop = None; hybrid = {'executed': False, 'reason': 'not_evaluated'}
    try:
        began = time.monotonic_ns()
        local = FrozenGroundedLocal(FrozenLocalObservation(specialized_manifest=freeze['frozen_local']['manifest']))
        local.read(frames['fresh-labelled'][1])
        cold['local_initialization_and_first_read_ms'] = (time.monotonic_ns()-began)/1e6
        credentials(); began = time.monotonic_ns(); dns_scope = resolve_scope()
        cold['dns_preresolution_ms'] = (time.monotonic_ns()-began)/1e6
        budget = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID, max_requests=105, max_usd='8')
        for name, provider in zip(NAMES, ('openai', 'gemini')):
            transport = PersistentScopedTransport(provider=provider, authorization_epoch=EPOCH, budget=budget, dns_scope=dns_scope)
            transports[name] = transport; reply = transport.metadata(); model = candidates()[name].config.model
            verified = reply.get('id') == model if provider == 'openai' else (reply.get('name') == 'models/'+model and
                'generateContent' in reply.get('supportedGenerationMethods', []))
            access.append({'candidate': name, 'http_status': 200, 'exact_model_access': verified,
                'client_initialization_ms': transport.initialization_ms, 'timing': dict(transport.timings)})
            if not verified:
                raise PermissionError('Fresh read-only model control failed.')
        if ledger_snapshot() != before:
            raise PermissionError('Read-only preflight changed the ledger.')
        set_policy({**original, 'inference_authorized': True, 'authorization_epoch': EPOCH,
            'max_requests': 5, 'max_usd': str(MAX_BATCH_USD),
            'scope': 'Same VISION-025 lot; only three distinct unused comparisons plus at most one conditional hybrid. No first-case retry.'})
        for case, name in pairs:
            if any(time.monotonic()+3 >= e['expires_at'] for e in dns_scope.values()):
                raise PermissionError('DNS lease cannot admit remaining deadline.')
            record, frame = frames[case]; reader = make_reader(name, frame, budget, transports[name])
            bind_frozen(reader, transports[name], record, frame)
            result = reader.read(frame, capture_ns=time.monotonic_ns())
            item = {'case_id': case, 'candidate': name, 'independent_session': record['independent_session'],
                'status': result.status, 'elapsed_ms': result.elapsed_ms,
                'observation': result.observation.model_dump() if result.observation else None,
                'diagnostics': result.diagnostics, 'metrics': evaluate(result, truths[case], frame)}
            results.append(item); save(OUTPUT/'completed-responses.json', results)
            print(json.dumps({'candidate': name, 'case': case, 'status': result.status,
                'complete_ms': round(result.elapsed_ms, 3), 'semantic_r1': item['metrics']['semantic_timely_correct_usable_r1']}), flush=True)
            # Distinct timed-out inputs are failures, not a reason to release
            # charges or retry them. All remaining slots were already funded at
            # worst case. Auth/schema/invalid usage still stops this lot.
            if (result.status in ('blocked', 'error', 'refused', 'incomplete') or
                    result.diagnostics.get('unreconciled_usage') or result.diagnostics.get('http_status') or budget.receipt()['stopped']):
                raise PermissionError('Technical/accounting failure; no further submissions.')
        summaries, winner = choose_candidate(results)
        if winner is None:
            hybrid = {'executed': False, 'reason': 'neither_candidate_passed_frozen_correctness_latency_gate'}
        elif any(time.monotonic()+3 >= e['expires_at'] for e in dns_scope.values()):
            hybrid = {'executed': False, 'reason': 'original_dns_lease_cannot_admit_hybrid'}
        else:
            hybrid = run_hybrid(winner, frames, truths, budget, transports, local)
            save(OUTPUT/'completed-hybrid-private.json', hybrid)
    except Exception as exc:
        stop = {'exception_types': exception_types(exc), 'raw_message_retained': False}
        hybrid = {'executed': False, 'reason': 'completion_preflight_or_technical_stop'}
    finally:
        set_policy(original)
        for transport in transports.values():
            transport.close()
        after = ledger_snapshot()
        unchanged = json.loads(CANONICAL_LEDGER.read_text())['entries'][:101] == old_entries
        save(OUTPUT/'completed-stop.json', {'runtime_disarmed': True,
            'pools_closed': all(t._closed for t in transports.values()), 'first_101_entries_unchanged': unchanged,
            'ledger_before': before, 'ledger_after': after, 'stop': stop,
            'unused_new_slots_closed': 105-after['receipt']['requests_attempted'], 'no_automatic_resumption': True})
    summaries, winner = choose_candidate(results)
    public_rows = [{k: r[k] for k in ('case_id', 'candidate', 'independent_session', 'status', 'elapsed_ms', 'metrics')} |
        {'usage': r['diagnostics'].get('usage'), 'provider_usage': r['diagnostics'].get('provider_usage'),
         'reported_usage_upper_usd': r['diagnostics'].get('price_based_upper_cost_usd'),
         'timing': r['diagnostics']['timing'], 'stage_spans': r['diagnostics']['stage_spans'],
         'network': r['diagnostics'].get('transport')} for r in results]
    final = {**receipt, 'rows': public_rows, 'attempted_comparisons': len(results), 'candidates': summaries,
        'selected_for_single_trial': winner, 'hybrid': {k: v for k, v in hybrid.items() if k not in ('observation', 'advice', 'advisor_payload', 'diagnostics')},
        'hybrid_usage': hybrid.get('diagnostics', {}).get('usage'),
        'hybrid_reported_usage_upper_usd': hybrid.get('diagnostics', {}).get('price_based_upper_cost_usd'),
        'hybrid_network': hybrid.get('diagnostics', {}).get('transport'),
        'ledger_after': after, 'accounted_upper_increase_usd': str(Decimal(after['receipt']['accounted_upper_usd'])-
            Decimal(receipt['ledger_before']['receipt']['accounted_upper_usd'])),
        'accounted_margin_usd': str(Decimal('8')-Decimal(after['receipt']['accounted_upper_usd'])),
        'unused_new_slots_closed': 105-after['receipt']['requests_attempted'],
        'initial_timeout_stop_retained': True, 'completion_access': access, 'completion_cold_initialization': cold,
        'first_101_entries_unchanged': unchanged, 'stop': stop, 'runtime_disarmed': True,
        'completion_scope': 'Exactly the remaining original three pairs; same epoch, cap, pixels, prompt, evaluator and gate; no retry or new batch.'}
    save(OUTPUT/'completed-summary.json', final)
    print(json.dumps({'comparisons': len(results), 'selected_trial_candidate': winner,
        'hybrid_executed': hybrid.get('executed'), 'hybrid_presented': hybrid.get('presented'),
        'runtime_disarmed': True, 'stop': stop, 'new_reservations_in_whole_lot': after['receipt']['requests_attempted']-100}), flush=True)
    return final


if __name__ == '__main__':
    run()
