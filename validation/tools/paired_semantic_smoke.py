"""Execute the human-authorized VISION-025 four-plus-one lot, once only.

Default is an offline freeze/budget check. --run requires the externally recorded
freeze checksum and consumes a crash-safe batch claim. No follow-on batch exists.
"""
import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from threading import Event, Thread
import time

import numpy as np

from bjlab.api_access_policy import MATRIX
from bjlab.controlled_http import resolve_scope
from bjlab.hybrid_evidence import CurrentEvidence, FrozenGroundedLocal
from bjlab.paired_deadline_reader import CaptureDeadlineReader, local_first_attempt
from bjlab.paired_persistent_http import PersistentScopedTransport, canonical_digest
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget, atomic_json
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, FrozenLocalObservation, file_hash, ROOT
from validation.tools.cloud_connection_diagnosis import credentials, exception_types
from validation.tools.grounded_corpus import save
from validation.tools.numeric_semantic_score import semantic_score
from validation.tools.paired_cloud_prepare import candidates, NAMES, score
from validation.tools.paired_semantic_prepare import (OUTPUT, EPOCH, INITIAL_LEDGER_SHA256,
    MAX_BATCH_USD, PAIRS, GATE, checked, ledger_snapshot)

PRICE_CHECK = {'verified_utc_date': '2026-10-06',
    'sources': ['https://developers.openai.com/api/docs/models/gpt-6-luna',
                'https://developers.openai.com/api/docs/pricing', 'https://ai.google.dev/gemini-api/docs/pricing'],
    'luna_input': '.10', 'luna_output': '.50', 'luna_cache_write_upper': '.125',
    'luna_fast_multiplier': '2', 'luna_long_input_multiplier': '2', 'luna_long_output_multiplier': '1.5',
    'gemini_input': '.30', 'gemini_output_including_thinking': '2.50',
    'method': 'Official pricing pages opened and checked before freezing this one-shot lot.'}


def claim(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False); handle.write('\n')
        handle.flush()
        import os
        os.fsync(handle.fileno())


def set_policy(value):
    matrix = json.loads(MATRIX.read_text(encoding='utf-8')); matrix['api_access_policy'] = value
    atomic_json(MATRIX, matrix)


def evaluate(result, truth, frame):
    observation = result.observation.model_dump() if result.observation else None
    return {**score(observation, truth, status=result.status, elapsed_ms=result.elapsed_ms),
        **semantic_score(observation, truth, status=result.status, elapsed_ms=result.elapsed_ms,
                         available_views={n for n, _ in frame.images()}),
        'evidence_scope': 'NEW owned sampled still response, not contract replay or provider generalization'}


def choose_candidate(rows):
    """Frozen before calls; never lower gates after seeing a slow reply."""
    summaries = {}; eligible = []
    for name in NAMES:
        part = [r for r in rows if r['candidate'] == name]; metrics = [r['metrics'] for r in part]
        times = [r['elapsed_ms'] for r in part if r['status'] == 'completed']
        p95 = float(np.percentile(times, 95)) if times else None
        passed = (len(part) == 2 and len(times) == 2 and
            sum(m['semantic_timely_correct_usable_r1'] for m in metrics) == 2 and
            not any(m['semantic_false_accept'] or m['unsupported_known_suit_tuples'] for m in metrics) and
            all(m['exact_card_inventory'] for m in metrics) and max(times) <= GATE['max_ms'] and p95 <= GATE['sample_p95_ms'])
        amount = sum((Decimal(r['diagnostics'].get('price_based_upper_cost_usd', '0')) for r in part), Decimal(0))
        count = sum(m['semantic_complete_transcription'] for m in metrics)
        summaries[name] = {'attempted': len(part), 'planned': 2, 'gate_passed': passed,
            'validated': sum(m['strict_wire_validated'] for m in metrics),
            'correct_timely_semantic_r1': sum(m['semantic_timely_correct_usable_r1'] for m in metrics),
            'semantic_false_accepts': sum(m['semantic_false_accept'] for m in metrics),
            'semantic_complete_transcriptions': count, 'literal_exact_json_fields': sum(m['literal_complete_transcription'] for m in metrics),
            'complete_ms_individual': [r['elapsed_ms'] for r in part],
            'validated_latency_ms': {'n': len(times), 'p50': float(np.percentile(times, 50)) if times else None,
                'p95_sample_only': p95, 'max': max(times) if times else None,
                'scope': 'n <= 2, completed only; not an operational p95, censored failures retained separately'},
            'failures': len(part)-len(times), 'timeouts': sum(r['status'] == 'timeout' for r in part),
            'reported_usage_upper_usd': str(amount),
            **{k: {'correct': sum(m[k]['correct'] for m in metrics), 'expected': sum(m[k]['expected'] for m in metrics)}
               for k in ('rank', 'suit', 'backs')},
            **{k: sum(m[k] for m in metrics) for k in ('exact_card_inventory', 'phase_correct', 'controls_correct', 'semantic_numeric_provenance_exact')},
            'semantic_numeric_tuples': {k: sum(m['semantic_numeric_provenance'][k] for m in metrics)
                for k in ('matched', 'expected', 'extra_or_wrong')}}
        if passed:
            eligible.append((-count, p95, amount, name))
    return summaries, min(eligible)[3] if eligible else None


def prerequisites(freeze_sha256):
    if file_hash(OUTPUT/'freeze.json') != freeze_sha256:
        raise PermissionError('External freeze checksum differs.')
    freeze, frames, truths = checked()
    before = ledger_snapshot(); receipt = before['receipt']
    if (before['sha256'] != INITIAL_LEDGER_SHA256 or receipt['requests_attempted'] != 100 or
            receipt['max_requests'] != 102 or receipt['unknown_charge_requests'] != 13 or receipt['stopped'] or
            Decimal(receipt['accounted_upper_usd'])+MAX_BATCH_USD > Decimal(receipt['max_usd'])):
        raise PermissionError('Canonical margin/history no longer admits this authorized lot.')
    configs = candidates()
    if 2*sum((r.config.reserve_usd for r in configs.values()), Decimal(0))+max(r.config.reserve_usd for r in configs.values()) != MAX_BATCH_USD:
        raise PermissionError('Audited reservation changed; do not expand money.')
    from datetime import datetime, timezone
    if datetime.now(timezone.utc).date().isoformat() != PRICE_CHECK['verified_utc_date']:
        raise PermissionError('Reverify prices; no automatic future replay.')
    original = json.loads(MATRIX.read_text())['api_access_policy']
    if (original.get('inference_authorized') is not False or original.get('max_requests') != 0 or
            Decimal(original.get('max_usd', '-1')) != 0):
        raise PermissionError('Runtime must start disarmed.')
    return freeze, frames, truths, before, original


def make_reader(name, frame, budget, transport):
    config = candidates()[name].config
    return CaptureDeadlineReader(config, budget, [sha256(p).hexdigest() for _, p in frame.images()],
        provider='openai' if name == NAMES[0] else 'gemini', transport=transport, name=name)


def bind_frozen(reader, transport, record, frame, suffix=''):
    saved = record['payloads'][reader.name]
    if canonical_digest(reader.payload(frame)) != saved['canonical_sha256']:
        raise PermissionError('Payload no longer matches frozen native pixels.')
    transport.bind(saved['canonical_sha256'], OUTPUT/(record['id']+'-'+reader.name+suffix+'.claim.json'))


def run_hybrid(winner, frames, truths, budget, transports, local):
    record, frame = frames['fresh-stable-hybrid']; transport = transports[winner]
    reader = make_reader(winner, frame, budget, transport)
    # Binding is not a reservation/submission. Local-only closes this unused slot.
    bind_frozen(reader, transport, record, frame, '-hybrid')
    evidence = CurrentEvidence(); done, ready = Event(), Event()
    def producer():
        while not done.is_set():
            evidence.capture(frame, source='owned-vision025-producer', table=record['independent_session'])
            ready.set(); done.wait(1/12)
    thread = Thread(target=producer, daemon=True, name='vision025-owned-capture'); thread.start()
    if not ready.wait(2):
        done.set(); thread.join(2)
        return {'executed': False, 'reason': 'producer_not_ready'}
    start_receipt = budget.receipt()
    try:
        value = local_first_attempt(evidence, local, reader)
        latest, _ = evidence.snapshot(); value['capture_updates'] = latest.sequence if latest else 0
        value['candidate'] = winner; value['executed'] = True
        observed = value.get('observation'); elapsed = value.get('timing', {}).get('capture_to_headless_presentation_ms')
        if value['route'] == 'fallback':
            semantic = semantic_score(observed, truths[record['id']], status=value['status'], elapsed_ms=elapsed,
                available_views={n for n, _ in frame.images()})
            value['metrics'] = semantic
            value['correct_presented_state'] = bool(value['presented'] and semantic['semantic_timely_correct_usable_r1'])
            value['false_presented_state'] = bool(value['presented'] and not semantic['semantic_timely_correct_usable_r1'])
        else:
            # Legacy local reads are not retrofitted with invented numeric labels.
            from bjlab.live_state import LiveObservation
            from bjlab.grounded_state import GroundedObservation
            projected = None
            if observed:
                legacy = GroundedObservation.model_validate(observed)
                projected = LiveObservation(cards=[c.model_dump() for c in legacy.cards], table_state=legacy.table_state,
                    phase=legacy.phase, controls=legacy.controls, numbers=[], blockers=[])
            semantic = semantic_score(projected, truths[record['id']], status=value['status'], elapsed_ms=elapsed,
                available_views={n for n, _ in frame.images()})
            value['local_r1_evaluation_without_numeric_invention'] = semantic
            value['correct_presented_state'] = bool(value['presented'] and semantic['semantic_timely_correct_usable_r1'])
            value['false_presented_state'] = bool(value['presented'] and not value['correct_presented_state'])
        value['new_reservations'] = budget.receipt()['requests_attempted']-start_receipt['requests_attempted']
        return value
    finally:
        done.set(); thread.join(2); evidence.disconnect()


def run(freeze_sha256):
    freeze, frames, truths, before, original = prerequisites(freeze_sha256)
    claim(OUTPUT/'execution-claim.json', {'epoch': EPOCH, 'external_freeze_sha256': freeze_sha256,
        'pairs': PAIRS, 'gate': GATE, 'ledger_before': before, 'pricing': PRICE_CHECK,
        'maximum_new_inferences': 5, 'maximum_reservation_usd': str(MAX_BATCH_USD)})
    old_entries = json.loads(CANONICAL_LEDGER.read_text())['entries']
    results, transports, access = [], {}, []; stop = None; amendment = None
    hybrid = {'executed': False, 'reason': 'paired_gate_not_yet_evaluated'}; cold = {}
    try:
        started = time.monotonic_ns()
        local = FrozenGroundedLocal(FrozenLocalObservation(specialized_manifest=freeze['frozen_local']['manifest']))
        local.read(frames['fresh-labelled'][1])  # Owned local initialization, no API/oracle.
        cold['local_initialization_and_first_read_ms'] = (time.monotonic_ns()-started)/1e6
        # No solver warm-up is hidden: math remains inside the measured hybrid path.
        credentials(); started = time.monotonic_ns(); dns_scope = resolve_scope()
        cold['dns_preresolution_ms'] = (time.monotonic_ns()-started)/1e6
        cold['dns_hosts'] = {h: {'resolution_ms': e['resolution_ms']} for h, e in dns_scope.items()}
        budget = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID, max_requests=102, max_usd='8')
        for name, provider in zip(NAMES, ('openai', 'gemini')):
            transport = PersistentScopedTransport(provider=provider, authorization_epoch=EPOCH, budget=budget, dns_scope=dns_scope)
            transports[name] = transport; reply = transport.metadata()
            model = candidates()[name].config.model
            verified = reply.get('id') == model if provider == 'openai' else (reply.get('name') == 'models/'+model and
                'generateContent' in reply.get('supportedGenerationMethods', []))
            access.append({'candidate': name, 'http_status': 200, 'exact_model_access': verified,
                'client_initialization_ms': transport.initialization_ms, 'timing': dict(transport.timings)})
            if not verified:
                raise PermissionError('Exact model access prerequisite failed.')
        if ledger_snapshot() != before:
            raise PermissionError('Read-only access control changed canonical history.')
        # Amend only the count after all prerequisites pass; every old cost stays.
        budget = budget.extend_request_ceiling(max_requests=105, authorization_epoch=EPOCH,
            authorization_note='Explicit human VISION-025 attachment: 100 consumed + exactly four comparisons and at most one conditional hybrid, USD8 unchanged.')
        amendment = ledger_snapshot()
        for transport in transports.values():
            transport.budget = budget
        save(OUTPUT/'preflight.json', {'freeze_sha256': freeze_sha256, 'access': access, 'cold': cold,
            'prices': PRICE_CHECK, 'ledger_before': before, 'count_amendment_after': amendment,
            'old_entries_unchanged': json.loads(CANONICAL_LEDGER.read_text())['entries'] == old_entries})
        set_policy({**original, 'inference_authorized': True, 'authorization_epoch': EPOCH,
            'max_requests': 5, 'max_usd': str(MAX_BATCH_USD), 'scope': 'VISION-025: exactly four frozen comparisons plus at most one conditional hybrid.'})
        for case, name in PAIRS:
            if any(time.monotonic()+3 >= e['expires_at'] for e in dns_scope.values()):
                raise PermissionError('Original DNS scope cannot admit a full request; no renewal/retry.')
            record, frame = frames[case]; reader = make_reader(name, frame, budget, transports[name])
            bind_frozen(reader, transports[name], record, frame)
            result = reader.read(frame, capture_ns=time.monotonic_ns())
            item = {'case_id': case, 'candidate': name, 'independent_session': record['independent_session'],
                'status': result.status, 'elapsed_ms': result.elapsed_ms,
                'observation': result.observation.model_dump() if result.observation else None,
                'diagnostics': result.diagnostics, 'metrics': evaluate(result, truths[case], frame)}
            results.append(item); save(OUTPUT/'responses.json', results)
            print(json.dumps({'candidate': name, 'case': case, 'status': result.status,
                'complete_ms': round(result.elapsed_ms, 3), 'semantic_r1': item['metrics']['semantic_timely_correct_usable_r1']}), flush=True)
            if (result.status in ('blocked', 'error', 'refused', 'incomplete') or
                result.diagnostics.get('unreconciled_usage') or result.diagnostics.get('http_status') or
                'price_based_upper_cost_usd' not in result.diagnostics or budget.receipt()['stopped']):
                raise PermissionError('Technical/unknown-charge stop; no remaining blind requests.')
        summaries, winner = choose_candidate(results)
        if winner is None:
            hybrid = {'executed': False, 'reason': 'neither_candidate_passed_frozen_correctness_latency_gate'}
        else:
            if any(time.monotonic()+3 >= e['expires_at'] for e in dns_scope.values()):
                hybrid = {'executed': False, 'reason': 'original_dns_scope_expired_before_hybrid'}
            else:
                hybrid = run_hybrid(winner, frames, truths, budget, transports, local)
                save(OUTPUT/'hybrid-private.json', hybrid)
    except Exception as exc:
        stop = {'exception_types': exception_types(exc), 'raw_message_retained': False}
        hybrid = {'executed': False, 'reason': 'preflight_or_comparative_stop'}
    finally:
        set_policy(original)
        for transport in transports.values():
            transport.close()
        after = ledger_snapshot()
        prior_preserved = json.loads(CANONICAL_LEDGER.read_text())['entries'][:100] == old_entries
        save(OUTPUT/'stop.json', {'runtime_disarmed': True, 'pools_closed': all(t._closed for t in transports.values()),
            'old_entries_unchanged': prior_preserved, 'ledger_before': before, 'ledger_after': after,
            'stop': stop, 'unused_new_slots_closed': 5-(after['receipt']['requests_attempted']-100),
            'no_automatic_resumption': True})
    summaries, winner = choose_candidate(results)
    public_rows = [{k: r[k] for k in ('case_id', 'candidate', 'independent_session', 'status', 'elapsed_ms', 'metrics')} |
        {'usage': r['diagnostics'].get('usage'), 'provider_usage': r['diagnostics'].get('provider_usage'),
         'reported_usage_upper_usd': r['diagnostics'].get('price_based_upper_cost_usd'),
         'timing': r['diagnostics']['timing'], 'stage_spans': r['diagnostics']['stage_spans'],
         'network': r['diagnostics'].get('transport')} for r in results]
    summary = {'experiment': 'VISION-025', 'freeze_sha256': freeze_sha256, 'gate': GATE,
        'attempted_comparisons': len(results), 'planned_comparisons': 4, 'maximum_new_inferences': 5,
        'rows': public_rows, 'candidates': summaries, 'selected_for_single_trial': winner,
        'hybrid': {k: v for k, v in hybrid.items() if k not in ('observation', 'advice', 'advisor_payload', 'diagnostics')},
        'hybrid_usage': hybrid.get('diagnostics', {}).get('usage'),
        'hybrid_reported_usage_upper_usd': hybrid.get('diagnostics', {}).get('price_based_upper_cost_usd'),
        'hybrid_network': hybrid.get('diagnostics', {}).get('transport'),
        'access': access, 'cold_initialization': cold, 'pricing': PRICE_CHECK,
        'ledger_before': before, 'count_amendment': amendment, 'ledger_after': after,
        'accounted_upper_increase_usd': str(Decimal(after['receipt']['accounted_upper_usd'])-Decimal(before['receipt']['accounted_upper_usd'])),
        'accounted_margin_usd': str(Decimal('8')-Decimal(after['receipt']['accounted_upper_usd'])),
        'old_entries_unchanged': prior_preserved, 'old_unknowns_preserved': True, 'stop': stop,
        'runtime_disarmed': True, 'unused_new_slots_closed': 5-(after['receipt']['requests_attempted']-100),
        'final_holdout_opened': False, 'reader_promoted': False, 'release_replaced': False,
        'claim_limit': 'Two fresh sampled owned stills/provider and at most one headless hybrid, not a statistical champion, Windows capture/paint, provider transfer, R2 or profit.'}
    save(OUTPUT/'summary.json', summary)
    print(json.dumps({'comparisons': len(results), 'selected_trial_candidate': winner,
        'hybrid_executed': hybrid.get('executed'), 'hybrid_presented': hybrid.get('presented'),
        'runtime_disarmed': True, 'stop': stop, 'new_reservations': after['receipt']['requests_attempted']-100}), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run', action='store_true')
    parser.add_argument('--freeze-sha256', required=True)
    args = parser.parse_args()
    if args.run:
        run(args.freeze_sha256)
    else:
        _, _, _, before, _ = prerequisites(args.freeze_sha256)
        print(json.dumps({'mode': 'offline_check_only', 'provider_calls': 0, 'ledger': before,
            'max_new_inferences': 5, 'max_reservation_usd': str(MAX_BATCH_USD)}))
