"""Budget, deadline and evaluation contracts; mocks are not API quality evidence."""
import asyncio
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from hashlib import sha256
import time

import pytest

from bjlab.openai_reader import OpenAIVisionReader, RequestBudget, ResponsesTransport
from bjlab.research_budget import PersistentRequestBudget
from tests.test_r1_readers import Transport, config as contract_config, frame, observation
from validation.tools.api_reader_tournament import (
    config, hybrid_rows, measurement, select_stage_frames, summarize,
)
from validation.tools.independent_tournament import scenario_timeline


def reserve_in_process(args):
    path, attempts = args
    budget = PersistentRequestBudget(path, authorization_id='contract-only', max_requests=12, max_usd='.003')
    count = 0
    for _ in range(attempts):
        try: budget.reserve(Decimal('.001')); count += 1
        except PermissionError: pass
    return count


def test_durable_budget_survives_processes_configs_and_unknown_timeouts(tmp_path):
    path = tmp_path/'ledger.json'
    value = PersistentRequestBudget.initialize(path, authorization_id='contract-only', max_requests=12, max_usd='.003')
    with ProcessPoolExecutor(max_workers=3) as pool:
        assert sum(pool.map(reserve_in_process, [(path, 4)]*3)) == 3
    receipt = value.receipt()
    assert receipt['requests_attempted'] == 3 and receipt['unknown_charge_requests'] == 3
    assert receipt['accounted_upper_usd'] == '0.003'
    with pytest.raises(PermissionError): value.reserve(Decimal('.000001'))
    with pytest.raises(PermissionError):
        PersistentRequestBudget(path, authorization_id='new-output', max_requests=12, max_usd='.003')


def test_settle_known_upper_retains_unknown_and_rejects_double_or_over_settle(tmp_path):
    value = PersistentRequestBudget.initialize(tmp_path/'ledger.json', authorization_id='contract', max_requests=5, max_usd='2')
    known = value.reserve(Decimal('1')); value.reserve(Decimal('1'))
    value.settle(known, Decimal('.1'))
    assert value.receipt()['accounted_upper_usd'] == '1.1'
    assert value.receipt()['unknown_charge_requests'] == 1
    with pytest.raises(ValueError): value.settle(known, Decimal('.05'))
    assert value.receipt()['stopped']
    with pytest.raises(PermissionError): value.reserve(Decimal('.01'))


def test_deleted_or_corrupt_budget_cannot_reset_allowance(tmp_path):
    path = tmp_path/'ledger.json'
    PersistentRequestBudget.initialize(path, authorization_id='contract', max_requests=5, max_usd='2')
    path.unlink()
    with pytest.raises(PermissionError):
        PersistentRequestBudget.initialize(path, authorization_id='contract', max_requests=5, max_usd='2')
    path.write_text('{}')
    with pytest.raises(PermissionError):
        PersistentRequestBudget(path, authorization_id='contract', max_requests=5, max_usd='2')


def test_luna_fast_and_long_context_have_conservative_audited_reservations():
    standard, fast = config(), config(fast=True)
    assert standard.reasoning_effort == 'none' and standard.service_tier == 'default'
    assert config('gpt-6.1-sol').reasoning_effort == 'low'
    assert standard.reserve_usd == Decimal('.263268')
    assert fast.reserve_usd == standard.reserve_usd*2
    assert standard.cost(1000, 100) == Decimal('.00015')
    assert standard.cost(300_000, 100) == Decimal('.060075')
    assert standard.cost(300_000, 100, upper=True) == Decimal('.075075')


def test_late_complete_json_is_never_current_even_from_injected_transport():
    transport = Transport(); original = transport.post
    def slow(payload, timeout):
        time.sleep(.02); return original(payload, timeout)
    transport.post = slow
    prepared = frame()
    reader = OpenAIVisionReader(contract_config(timeout_seconds=.01), RequestBudget(1, '.01'),
        {sha256(p).hexdigest() for _, p in prepared.images()}, transport=transport)
    result = reader.read(prepared)
    assert result.status == 'timeout' and result.observation is None
    assert result.diagnostics['late_validated_response_discarded']


def test_wall_deadline_cancels_dripping_body_and_closes_transport(monkeypatch, tmp_path):
    closed = []
    class Response:
        status_code = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): closed.append('response')
        async def aiter_bytes(self):
            while True:
                await asyncio.sleep(.005); yield b' '
    class Client:
        def __init__(self, **kwargs):
            assert not kwargs['trust_env'] and not kwargs['follow_redirects']
        async def __aenter__(self): return self
        async def __aexit__(self, *args): closed.append('client')
        def stream(self, *args, **kwargs): return Response()
    monkeypatch.setattr('httpx.AsyncClient', Client)
    monkeypatch.setattr('bjlab.openai_reader.require_inference_authorization', lambda epoch: epoch)
    path = tmp_path/'ledger.json'
    monkeypatch.setattr('bjlab.research_budget.CANONICAL_LEDGER', path)
    ledger = PersistentRequestBudget.initialize(path, authorization_id='contract', max_requests=1, max_usd='.01')
    identifier = ledger.reserve(Decimal('.001'))
    transport = ResponsesTransport('fictional-credential-not-a-secret', authorization_epoch='contract', budget=ledger)
    began = time.perf_counter()
    with pytest.raises(TimeoutError): transport.post({}, .03, reservation_id=identifier)
    assert time.perf_counter()-began < .5
    assert closed == ['response', 'client']
    assert ledger.receipt()['network_attempts_claimed'] == 1
    with pytest.raises(PermissionError): transport.post({}, .03, reservation_id=identifier)


def test_real_transport_cannot_use_memory_or_another_output_ledger(monkeypatch, tmp_path):
    monkeypatch.setattr('bjlab.openai_reader.require_inference_authorization', lambda epoch: epoch)
    for value in (RequestBudget(1, '1'), PersistentRequestBudget.initialize(tmp_path/'another.json',
            authorization_id='contract', max_requests=1, max_usd='1')):
        transport = ResponsesTransport('fictional-credential-not-a-secret', authorization_epoch='contract', budget=value)
        with pytest.raises(PermissionError, match='blocked_missing_canonical_persistent_budget'):
            transport.post({}, .03)


def test_stage_sampling_covers_empty_decision_reveal_and_immediate_terminal():
    selected = select_stage_frames(scenario_timeline(4101883), 12)
    assert len(selected) == 4
    assert {s['phase'] for _, s in selected} == {'waiting', 'player', 'dealer', 'settled'}
    assert next(s for _, s in selected if s['phase'] == 'settled')['scenario'] == 'immediate_blackjack'


def test_controls_order_is_not_error_but_missing_or_wrong_phase_is():
    from bjlab.state_reader import ReaderResult
    value = observation(phase='player', controls=['stand', 'hit']); truth = value.model_dump()
    truth['controls'] = ['hit', 'stand']
    record = {'id': 'contract', 'family': 'test', 'condition': 'clean', 'evidence_kind': 'contract-mock'}
    measured = measurement(record, ReaderResult('id', 'fake', 'completed', value, 2, {}), truth)
    assert measured['metrics']['complete_state_correct'] and measured['correct_timely_player_state']
    truth['phase'] = 'settled'
    wrong = measurement(record, ReaderResult('id', 'fake', 'completed', value, 2, {}), truth)
    assert wrong['false_accepted_player_state']
    assert not wrong['metrics']['complete_state_correct']


def test_hybrid_routes_on_gate_never_truth_and_expires_combined_latency():
    from bjlab.state_reader import ReaderResult
    record = {'id': 'contract', 'family': 'test', 'condition': 'clean', 'evidence_kind': 'contract-mock'}
    truth = observation(phase='player').model_dump()
    bad = observation(phase='player', cards=observation().model_dump()['cards'][:-1])
    accepted_wrong = measurement(record, ReaderResult('id', 'current-local', 'completed', bad, 50, {}), truth)
    good = measurement(record, ReaderResult('id', 'luna-standard', 'completed', observation(phase='player'), 2990, {}), truth)
    row = hybrid_rows([accepted_wrong], [good])[0]
    assert row['observation'] == bad.model_dump()  # wrong accepted local cannot be replaced using oracle
    blocked = dict(accepted_wrong, gate={'usable': False, 'reasons': ['uncertain']})
    late = hybrid_rows([blocked], [good])[0]
    assert late['elapsed_ms'] == 3040 and late['observation'] is None and not late['gate']['usable']
    assert not late['correct_timely_player_state']


def test_failures_and_unexecuted_rows_stay_in_accuracy_denominator():
    from bjlab.state_reader import ReaderResult
    truth = observation(phase='player').model_dump()
    record = {'id': 'contract', 'family': 'test', 'condition': 'clean', 'evidence_kind': 'contract-mock'}
    rows = [measurement(record, ReaderResult('id', 'fake', s, None, t, {}), truth)
        for s, t in (('timeout', 3000), ('not_executed', 0))]
    receipt = summarize(rows)['fake']
    assert receipt['planned_inputs'] == receipt['complete_state_denominator'] == 2
    assert receipt['timeouts'] == 1 and receipt['not_executed'] == 1
    assert receipt['complete_states_correct'] == 0 and receipt['completed_latency_ms']['p95'] is None
