"""VISION-024 offline-only replay/trace analysis; no inference or authorization.

Reads the consumed PR16 validation inputs and exact PR17 receipts. Never reads
credentials, development/final holdouts or changes a ledger/runtime/old artifact.
"""
from contextlib import contextmanager
from decimal import Decimal
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

from bjlab.api_access_policy import MATRIX
from bjlab.numeric_provenance import POLICY_VERSION, VIEWS
from validation.tools import paired_cloud_prepare as frozen
from validation.tools.numeric_semantic_score import semantic_score
from validation.tools.persistent_http_fixture import lifecycle_report

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT/'artifacts/paired-cloud-preparation-20261005-frozen'
RESPONSES = ROOT/'artifacts/paired-cloud-smoke-20261005-six/responses.json'
FREEZE_SHA256 = 'd6fe0f0b41f624a717719ebccb3d35222d1fb4b534e1426b329d500ab4dbcbfe'
RESPONSES_SHA256 = '9e14d7200b93531371af2c39ecc8d7c9fd9c359576d15cd0d3c1afae5b5fbf5e'
PR17 = ROOT/'validation/results/cloud-connection-paired-smoke/summary.json'
PRIVATE = ROOT/'artifacts/numeric-provenance-offline-20261005'
PUBLIC = ROOT/'validation/results/numeric-provenance-alignment'


@contextmanager
def offline_guard():
    def forbidden(*args, **kwargs):
        raise PermissionError('Offline contract evaluation prohibits network/DNS/subprocess execution.')
    with patch.object(socket, 'getaddrinfo', forbidden), patch.object(socket, 'create_connection', forbidden), \
         patch.object(socket.socket, 'connect', forbidden), patch.object(socket.socket, 'connect_ex', forbidden), \
         patch.object(subprocess, 'run', forbidden):
        yield


def analyze_timeout(item):
    """Retained measurements only. Nested clocks are never summed twice."""
    if item['status'] != 'timeout' or item['observation'] is not None:
        raise ValueError('Analysis requires the discarded original timeout receipt.')
    clock = item['diagnostics']['timing']
    exclusive = {key: clock[key] for key in
        ('payload_ms', 'reservation_ms', 'transport_total_ms', 'observation_parse_validate_ms')}
    measured_sum = sum(exclusive.values())
    residual = item['elapsed_ms']-measured_sum
    if residual < 0:
        raise ValueError('Retained timers overlap or exceed the total.')
    return {'evidence_kind': 'retained-pr17-timeout-trace', 'candidate': item['candidate'], 'case_id': item['case_id'],
        'total_reader_ms': item['elapsed_ms'], 'live_deadline_ms': 3000,
        'exclusive_measured_spans_ms': exclusive, 'measured_sum_ms': measured_sum,
        'derived_untimed_residual_ms': residual,
        'within_transport_cumulative_ms': {key: clock[key] for key in ('headers_received_ms', 'body_complete_ms')},
        'within_transport_stage_ms': {key: clock.get(key) for key in
            ('connect_tcp_ms', 'start_tls_ms', 'send_request_headers_ms', 'send_request_body_ms',
             'receive_response_headers_ms', 'receive_response_body_ms', 'provider_json_parse_ms', 'dns_separate_ms')},
        'unobserved_ms': {key: None for key in ('absolute_reader_body_receipt', 'claim_submission',
            'model_tier_usage_audit', 'durable_settlement', 'budget_receipt', 'provider_compute', 'state_revalidation', 'advisor')},
        'untimed_code_paths': ['schema/hash serialization', 'durable one-attempt submission claim',
            'event-loop/worker scheduling', 'model/tier/usage audit', 'durable budget settlement',
            'diagnostic receipt and final return overhead'],
        'conclusions': [
            'Complete response body arrived at 2984.251ms on the TRANSPORT clock; no reader-clock body timestamp was saved.',
            'Even the four nonoverlapping measured spans total more than 3000ms. Deferring settlement alone is not shown sufficient.',
            'The 47ms residual is aggregate unmeasured work, not a measured settlement duration.',
            'Response-header wait includes server and network; it is not an isolated model-generation time.',
            'The timeout remains discarded; parsing/contract changes cannot revive it.'],
        'future_critical_path': {
            'must_remain_before_send': ['durable worst-case reservation', 'durable one-attempt payload claim', 'authorization and reviewed-pixel checks'],
            'must_remain_before_presentation': ['auditable returned model/tier/usage and reserve upper bound',
                'strict JSON/schema and numeric semantics', 'original capture deadline', 'current source/table/state revalidation'],
            'candidate_noncritical_work': ['full diagnostic receipt/serialization',
                'durable settlement after auditable in-memory usage check ONLY while full worst-case reservation stays durable and charged until settlement'],
            'not_implemented': 'No accounting order, reader, transport or deadline changed. A future lifecycle must pass one absolute deadline through claim/transport/presentation.'}}


def minimum_proposal(receipt):
    configs = frozen.candidates()
    reserves = {name: r.config.reserve_usd for name, r in configs.items()}
    still = 2*sum(reserves.values())
    hybrid = max(reserves.values())
    margin = Decimal(receipt['max_usd'])-Decimal(receipt['accounted_upper_usd'])
    return {'status': 'PROPOSAL_ONLY_NOT_AUTHORIZED', 'new_requests_executed': 0,
        'fresh_paired_cases': 2, 'paired_requests': 4, 'conditional_stable_hybrid_requests': 1,
        'maximum_requests': 5, 'per_request_reserve_usd': {k: str(v) for k, v in reserves.items()},
        'paired_worst_case_usd': str(still), 'hybrid_worst_case_usd': str(hybrid),
        'combined_worst_case_usd': str(still+hybrid), 'accounted_margin_usd': str(margin),
        'fits_existing_money_margin_at_frozen_prices': still+hybrid <= margin,
        'current_lifetime_requests': receipt['requests_attempted'], 'current_ceiling': receipt['max_requests'],
        'minimum_future_lifetime_ceiling_if_authorized': receipt['requests_attempted']+5,
        'closed_residual_slots': 'Both remain closed; no inferred permission from balance or reservation margin.',
        'case_specification': ['fresh owned player decision with two labelled totals and independent SESSION badge',
            'fresh owned player decision with partial/rotated card, back and an ambiguous UI number that must remain unknown'],
        'freeze_before_execution': ['new sessions/seeds/hand groups/artwork families, disjoint from consumed PR16 cases',
            'same native pixels and frozen payloads for both providers', 'common semantic and literal evaluator, no oracle in app inputs',
            'no final holdout, retries, paid warm-ups or new models'],
        'conditional_hybrid': ['at least one candidate passes both new cases with zero semantic false accepts',
            'full required state within original 3s deadline and provisional sample p95 <= 2.5s, with timeouts retained',
            'local routing must request the fallback without oracle forcing; zero calls if local succeeds',
            'one fresh owned stable-table capture, advancing timestamps and no per-frame phase assistance',
            'freshness/source checks through local -> cloud -> parse -> semantic gate -> revalidation -> solver -> headless advisor',
            'transport lifecycle/absolute deadline implementation tested offline before any live request',
            'explicit bounded scope/ledger admission and current model access/prices checked again'],
        'cold_warm_reporting': 'Include cold initialization separately and full cold capture-to-advisor time; no request-count-free inference warm-up.',
        'limits': 'This five-request maximum is a functional smoke, not a reliable p95, statistical winner, provider transfer or session certification.',
        'authorization_policy': 'Do not amend ceiling/epoch, reserve, load keys or submit as part of this offline proposal.'}


def protected_snapshot():
    paths = {ROOT/p for p in frozen.SOURCES}
    model = json.loads((CORPUS/'freeze.json').read_text())['frozen_local']
    manifest = Path(model['manifest'])
    paths.add(manifest)
    paths.update(manifest.parent/name for name in model['weights'])
    paths.add(MATRIX)
    paths.update(ROOT/p for p in ('bjlab/controlled_http.py', 'validation/tools/paired_cloud_smoke.py',
        'validation/tools/cloud_connection_diagnosis.py', 'docs/CLOUD_CONNECTION_PAIRED_SMOKE.md'))
    for directory in (CORPUS, RESPONSES.parent, PR17.parent):
        paths.update(p for p in directory.rglob('*') if p.is_file())
    return {str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p): frozen.file_hash(p) for p in sorted(paths)}


def assert_runtime_disarmed(policy):
    """Read-only precondition; do not silently disarm or amend a live scope."""
    try:
        disarmed = (policy['inference_authorized'] is False and type(policy['max_requests']) is int and
            policy['max_requests'] == 0 and Decimal(policy['max_usd']).is_finite() and Decimal(policy['max_usd']) == 0)
    except (KeyError, TypeError, ValueError, ArithmeticError):
        disarmed = False
    if not disarmed:
        raise PermissionError('Expected the existing runtime to remain disarmed; do not change its authorization.')


def replay():
    """Dedicated new outputs only. Compare old rows and every protected hash."""
    with offline_guard():
        before = frozen.ledger_snapshot(); protected = protected_snapshot()
        runtime = json.loads(MATRIX.read_text())['api_access_policy']
        assert_runtime_disarmed(runtime)
        if frozen.file_hash(RESPONSES) != RESPONSES_SHA256:
            raise ValueError('Original response receipt changed.')
        _, inputs, truths = frozen.checked(CORPUS, 'validation', expected_freeze_sha256=FREEZE_SHA256)
        old = frozen.evaluate(CORPUS, 'validation', RESPONSES)
        published = json.loads(PR17.read_text())
        if old['rows'] != published['rows']:
            raise ValueError('Frozen evaluation does not reproduce the original public rows.')
        source = json.loads(RESPONSES.read_text())
        records = {r['id']: (r, frame) for r, frame in inputs}
        rows = {name: [] for name in frozen.NAMES}
        for result in source['results']:
            record, frame = records[result['case_id']]
            row = semantic_score(result['observation'], truths[record['id']], status=result['status'],
                elapsed_ms=result['elapsed_ms'], available_views={'table', *frame.layout})
            rows[result['candidate']].append({**row, 'case_id': record['id']})
        summaries = {}
        keys = ('strict_wire_validated', 'semantic_usable_r1', 'semantic_correct_usable_r1',
            'semantic_timely_correct_usable_r1', 'semantic_false_accept', 'semantic_complete_transcription',
            'semantic_numeric_provenance_exact', 'literal_complete_transcription', 'literal_numeric_provenance_exact')
        for name, values in rows.items():
            summaries[name] = {'attempted': len(values),
                **{key: {'numerator': sum(bool(r[key]) for r in values), 'denominator': len(values)} for key in keys},
                'semantic_numeric_tuples': {'matched': sum(r['semantic_numeric_provenance']['matched'] for r in values),
                    'expected': sum(r['semantic_numeric_provenance']['expected'] for r in values)},
                'timeout_count': sum(r['status'] == 'timeout' for r in values)}
        timeout = analyze_timeout(next(r for r in source['results'] if r['status'] == 'timeout'))
        http = lifecycle_report()
        proposal = minimum_proposal(before['receipt'])
        after = frozen.ledger_snapshot()
        if before != after or protected_snapshot() != protected:
            raise ValueError('Offline work changed protected evidence or the canonical ledger.')
        summary = {'experiment_id': 'VISION-024', 'report_date': '2026-10-06', 'started_date': '2026-10-05',
            'policy': POLICY_VERSION,
            'evidence_kind': 'offline-contract-re-evaluation-of-consumed-pr17-responses',
            'new_model_quality_evidence': False, 'provider_calls': 0, 'hybrid_calls': 0, 'credential_loading': False,
            'new_policy_source_hashes': {p: frozen.file_hash(ROOT/p) for p in
                ('bjlab/numeric_provenance.py', 'validation/tools/numeric_semantic_score.py',
                 'validation/tools/numeric_contract_replay.py', 'validation/tools/persistent_http_fixture.py')},
            'freeze_sha256': FREEZE_SHA256, 'responses_sha256': RESPONSES_SHA256,
            'original_public_scores': published['candidates'], 'semantic_re_evaluation': summaries,
            'historical_rows_reproduced': True, 'original_scores_and_sources_unchanged': True,
            'protected_file_count': len(protected), 'protected_manifest_sha256': frozen.digest(protected),
            'ledger_before': before, 'ledger_after': after, 'runtime_disarmed': True,
            'final_holdout_opened': False, 'timeout_analysis': timeout, 'persistent_client_fixture': http,
            'historical_dns_initialization': published['dns_preresolution'],
            'minimum_future_proposal': proposal,
            'application_integration': 'Opt-in semantic_gate only; frozen live-v3 reader/default gate and deployed runtime unchanged.',
            'promotion': 'none; future independent requests require a new bounded authorization'}
        PRIVATE.mkdir(parents=True, exist_ok=True); PUBLIC.mkdir(parents=True, exist_ok=True)
        frozen.save(PRIVATE/'normalized-replay.json', rows)
        frozen.save(PRIVATE/'protected-manifest.json', protected)
        frozen.save(PUBLIC/'summary.json', summary)
        print(json.dumps({'status': 'offline_complete', 'provider_calls': 0, 'ledger_unchanged': True,
            'semantic_re_evaluation': summaries, 'proposal_worst_case_usd': proposal['combined_worst_case_usd']}))
        return summary


if __name__ == '__main__':
    replay()
