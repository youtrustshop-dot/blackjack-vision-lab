"""One-shot resumption of the six original PR16 requests; never a new batch.

No alternative inputs/providers, retries, warm-up, hybrid, holdout or training.
The read-only default verifies the freeze/ledger; --run consumes an immutable
batch claim. Historical execution sources and evaluator are imported unchanged.
Existing credentials are loaded only for an explicitly requested execution.
"""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import time

from bjlab.api_access_policy import MATRIX
from bjlab.controlled_http import ControlledGeminiTransport, ControlledResponsesTransport, resolve_scope
from bjlab.grounded_cloud import GeminiConfig
from bjlab.live_cloud import DiagnosticReader
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget, atomic_json
from validation.tools.api_reader_tournament import AUTHORIZATION_ID, ROOT, config, file_hash
from validation.tools.cloud_connection_diagnosis import credentials, exception_types, save
from validation.tools.paired_cloud_prepare import NAMES, SMOKE, checked, digest, ledger_snapshot, score, summarize

FROZEN = ROOT/'artifacts/paired-cloud-preparation-20261005-frozen'
FREEZE_SHA256 = 'd6fe0f0b41f624a717719ebccb3d35222d1fb4b534e1426b329d500ab4dbcbfe'
INITIAL_LEDGER_SHA256 = '6b94bbbfb5872ab8c1e64cec9a48140e9d5669eb57ae47dfe4e492422676ae4f'
OUTPUT = ROOT/'artifacts/paired-cloud-smoke-20261005-six'
EPOCH = '2026-10-05-pr16-original-six-resume'
PAIRS = tuple((case, candidate) for case in SMOKE for candidate in NAMES)
CONFIGS = {NAMES[0]: config(fast=True), NAMES[1]: GeminiConfig()}
PRICE_CHECK = {
    'verified_utc_date': '2026-10-05',
    'method': 'Read current official model/pricing pages before this execution; no price assumption from the key.',
    'sources': ['https://developers.openai.com/api/docs/models/gpt-6-luna',
                'https://ai.google.dev/gemini-api/docs/pricing'],
    'luna_standard_per_million': {'input': '.10', 'output': '.50', 'cache_write_upper': '.125'},
    'luna_fast_multiplier': '2', 'luna_long_input_multiplier': '2', 'luna_long_output_multiplier': '1.5',
    'gemini_standard_per_million': {'input': '.30', 'output_including_thinking': '2.50'},
}


def claim(path, value):
    """Crash/re-execution cannot silently authorize another attempt."""
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False); handle.write('\n')


class FrozenPayloadGuard:
    def bind(self, *, payload_sha256, attempt_claim):
        if getattr(self, '_bound', None) is not None:
            raise PermissionError('Previous frozen attempt was not consumed.')
        self._bound = (payload_sha256, attempt_claim)

    def post(self, payload, timeout, *, reservation_id=None):
        bound = getattr(self, '_bound', None); self._bound = None
        if bound is None or digest(payload) != bound[0]:
            raise PermissionError('Undeclared or altered PR16 payload; no submission.')
        claim(bound[1], {'payload_canonical_sha256': bound[0], 'epoch': EPOCH, 'retries': 0})
        return super().post(payload, timeout, reservation_id=reservation_id)


class FrozenResponsesTransport(FrozenPayloadGuard, ControlledResponsesTransport):
    pass


class FrozenGeminiTransport(FrozenPayloadGuard, ControlledGeminiTransport):
    pass


def prerequisites():
    freeze, inputs, truths = checked(FROZEN, 'validation', expected_freeze_sha256=FREEZE_SHA256)
    selected = {r['condition']: (r, frame) for r, frame in inputs if r['condition'] in SMOKE}
    if set(selected) != set(SMOKE) or len({r['independent_session'] for r, _ in selected.values()}) != 3:
        raise PermissionError('The original three independent-session cases are required.')
    before = ledger_snapshot(); receipt = before['receipt']
    worst = sum((CONFIGS[name].reserve_usd for _, name in PAIRS), Decimal(0))
    if (before['sha256'] != INITIAL_LEDGER_SHA256 or receipt['requests_attempted'] != 94 or
            receipt['unknown_charge_requests'] != 13 or receipt['stopped'] or
            receipt['requests_attempted']+len(PAIRS) > receipt['max_requests'] or
            Decimal(receipt['accounted_upper_usd'])+worst > Decimal(receipt['max_usd'])):
        raise PermissionError('Original reservations/allowance changed or cannot admit six; no new allowance.')
    matrix = json.loads(MATRIX.read_text(encoding='utf-8'))
    if matrix['api_access_policy'].get('inference_authorized') is not False:
        raise PermissionError('Runtime must start disarmed.')
    return freeze, selected, truths, before, worst, matrix['api_access_policy']


def set_policy(policy):
    value = json.loads(MATRIX.read_text(encoding='utf-8'))
    value['api_access_policy'] = policy
    atomic_json(MATRIX, value)


def run():
    freeze, selected, truths, before, worst, original_policy = prerequisites()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    claim(OUTPUT/'execution-claim.json', {
        'authorization': 'Latest human attachment explicitly resumes only the six original PR16 calls after connection passes.',
        'epoch': EPOCH, 'pairs': PAIRS, 'freeze_sha256': FREEZE_SHA256,
        'ledger_before': before, 'worst_case_usd': str(worst), 'pricing_check': PRICE_CHECK,
        'configs': {n: asdict(c) for n, c in CONFIGS.items()},
        'execution_sources': {p: file_hash(ROOT/p) for p in (
            'bjlab/controlled_http.py', 'validation/tools/paired_cloud_smoke.py')},
        'retries': 0, 'paid_warmups': 0, 'hybrid_requests': 0, 'final_holdout_opened': False,
        'created_utc': datetime.now(timezone.utc).isoformat(),
    })
    old_entries = json.loads(CANONICAL_LEDGER.read_text())['entries']
    results, access, rows = [], [], {name: [] for name in NAMES}
    stop = None; dns_receipt = None
    try:
        credentials()
        dns_scope = resolve_scope()  # Fresh answers, never IPs loaded from a previous receipt.
        dns_receipt = {host: {'resolution_ms': entry['resolution_ms']} for host, entry in dns_scope.items()}
        budget = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID,
                                         max_requests=102, max_usd='8')
        transports = {
            NAMES[0]: FrozenResponsesTransport(authorization_epoch=EPOCH, budget=budget, dns_scope=dns_scope),
            NAMES[1]: FrozenGeminiTransport(authorization_epoch=EPOCH, budget=budget, dns_scope=dns_scope),
        }
        for name, endpoint in zip(NAMES, ('/models/gpt-6-luna', 'models/gemini-3.5-flash-lite')):
            transport = transports[name]
            reply = asyncio.run(transport._request('GET', endpoint, 10.))
            verified = (reply.get('id') == CONFIGS[name].model if name == NAMES[0] else
                        reply.get('name') == 'models/'+CONFIGS[name].model and
                        'generateContent' in reply.get('supportedGenerationMethods', []))
            access.append({'candidate': name, 'http_status': 200, 'exact_model_access': verified,
                           'timings': transport.timings})
            if not verified: raise PermissionError('Exact model access not established.')
        if ledger_snapshot() != before: raise PermissionError('Read-only prerequisites changed the ledger.')
        save(OUTPUT/'access.json', {'access': access, 'dns_preresolution': dns_receipt,
                                   'ledger_unchanged': True, 'inference_calls': 0})
        set_policy({**original_policy, 'inference_authorized': True, 'authorization_epoch': EPOCH,
                    'max_requests': 6, 'max_usd': str(worst),
                    'scope': 'ONLY the original PR16 paired smoke: three frozen validation cases x two providers.'})
        for case, name in PAIRS:
            # Do not renew DNS within the batch or send after the original answer's TTL.
            if any(time.monotonic()+3 >= entry['expires_at'] for entry in dns_scope.values()):
                raise PermissionError('DNS scope cannot admit another full deadline; no new request.')
            record, frame = selected[case]; saved = record['payloads'][name]
            if file_hash(FROZEN/'validation'/saved['file']) != saved['sha256']:
                raise PermissionError('Frozen payload file changed.')
            hashes = [sha256(p).hexdigest() for _, p in frame.images()]
            reader = DiagnosticReader(CONFIGS[name], budget, hashes,
                provider='openai' if name == NAMES[0] else 'gemini', variant='live', transport=transports[name],
                gemini_output='structured' if name == NAMES[0] else 'structured-card-limit-local')
            if digest(reader.payload(frame)) != saved['canonical_sha256']:
                raise PermissionError('Frozen payload comparison failed; no reservation.')
            transports[name].bind(payload_sha256=saved['canonical_sha256'],
                                  attempt_claim=OUTPUT/(case+'-'+name+'.claim.json'))
            result = reader.read(frame)
            item = {'case_id': record['id'], 'condition': case, 'candidate': name,
                'independent_session': record['independent_session'], 'payload_sha256': saved['sha256'],
                'status': result.status, 'elapsed_ms': result.elapsed_ms,
                'observation': result.observation.model_dump() if result.observation is not None else None,
                'diagnostics': result.diagnostics}
            results.append(item); save(OUTPUT/'responses.json', {'freeze_sha256': FREEZE_SHA256,
                'split': 'validation', 'evidence_kind': 'actual-provider-responses', 'results': results})
            scored = score(item['observation'], truths[record['id']],
                           status=result.status, elapsed_ms=result.elapsed_ms)
            scored.update(case_id=record['id'], condition=case,
                          independent_session=record['independent_session'])
            rows[name].append(scored)
            print(json.dumps({'candidate': name, 'case': case, 'status': result.status,
                              'complete_ms': round(result.elapsed_ms, 2)}), flush=True)
            if (result.status == 'blocked' or result.diagnostics.get('http_status') or
                    result.diagnostics.get('unreconciled_usage') or budget.receipt()['stopped']):
                raise PermissionError('Technical/access/accounting failure; remaining pairs are not submitted.')
    except Exception as exc:
        stop = {'exception_types': exception_types(exc), 'raw_message_retained': False}
    finally:
        set_policy(original_policy)  # Restore the exact disarmed policy, even after failure.
        after = ledger_snapshot()
        unchanged = json.loads(CANONICAL_LEDGER.read_text())['entries'][:len(old_entries)] == old_entries
        save(OUTPUT/'stop.json', {'stop': stop, 'runtime_disarmed': True,
            'original_entries_unchanged': unchanged, 'ledger_before': before, 'ledger_after': after,
            'infer_attempts': len(results), 'no_automatic_resumption': True})
    summaries = {}
    for name, values in rows.items():
        own = [r for r in results if r['candidate'] == name]
        summaries[name] = {**summarize(values, planned=3, independent_sessions=3),
            'correct_usable_r1': {'numerator': sum(r['correct_usable_r1'] for r in values),
                                  'denominator': sum(r['expected_usable_r1'] for r in values)},
            'numeric_provenance': {k: sum(r['numeric_provenance'][k] for r in values)
                                   for k in ('matched', 'expected', 'extra_or_wrong')},
            'provider_reported_usage': [r['diagnostics'].get('usage') for r in own],
            'reported_usage_upper_cost_usd': str(sum((Decimal(r['diagnostics']['price_based_upper_cost_usd'])
                for r in own if 'price_based_upper_cost_usd' in r['diagnostics']), Decimal(0))),
            'uncertain_reserved_usd': str(sum((CONFIGS[name].reserve_usd for r in own
                if 'price_based_upper_cost_usd' not in r['diagnostics']), Decimal(0))),
        }
    summary = {'experiment_id': 'VISION-023', 'freeze_sha256': FREEZE_SHA256,
        'attempted': len(results), 'planned': 6, 'access': access, 'dns_preresolution': dns_receipt,
        'candidates': summaries, 'rows': rows, 'stop': stop, 'runtime_disarmed': True,
        'ledger_before': before, 'ledger_after': after, 'original_entries_unchanged': unchanged,
        'accounted_margin_usd': str(Decimal(after['receipt']['max_usd'])-Decimal(after['receipt']['accounted_upper_usd'])),
        'pricing_check': PRICE_CHECK, 'hybrid_attempts': 0, 'final_holdout_opened': False,
        'latency_scope': 'Reader submission through full strict JSON validation; includes new TCP/TLS. DNS setup is separate. Not capture-to-advisor or continuous-video evidence.',
        'promotion': 'None. Three owned sampled stills per candidate cannot establish a champion or provider transfer.',
    }
    save(OUTPUT/'summary.json', summary)
    print(json.dumps({'attempted': len(results), 'planned': 6, 'runtime_disarmed': True,
                      'stop': stop, 'accounted_margin_usd': summary['accounted_margin_usd']}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Consume the one-shot original-six authorization.')
    args = parser.parse_args()
    if args.run: run()
    else:
        _, _, _, before, worst, _ = prerequisites()
        print(json.dumps({'mode': 'offline_check_only', 'provider_calls': 0, 'freeze_sha256': FREEZE_SHA256,
                          'worst_case_usd': str(worst), 'ledger': before}))


if __name__ == '__main__': main()
