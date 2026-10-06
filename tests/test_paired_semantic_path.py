"""Socketless VISION-025 lifecycle/deadline/selection tests; no API evidence."""
from hashlib import sha256
import json
from pathlib import Path
import socket
import time
from types import SimpleNamespace

import pytest

from bjlab.grounded_state import GroundedResult, adapt_legacy
from bjlab.hybrid_evidence import CurrentEvidence
from bjlab.live_state import LiveObservation
from bjlab.paired_deadline_reader import CaptureDeadlineReader, local_first_attempt
import bjlab.paired_persistent_http as http
from bjlab.research_budget import PersistentRequestBudget
from bjlab.state_reader import FrameInput
from validation.tools.api_reader_tournament import config
from validation.tools.paired_cloud_prepare import NAMES
from validation.tools.paired_semantic_smoke import choose_candidate
from validation.tools.persistent_http_fixture import FixtureBackend, FixtureStream


def observation():
    return LiveObservation.model_validate({'c': [
        {'z': 'player:0', 'r': '10', 's': 'S', 'v': 'readable'},
        {'z': 'player:0', 'r': '6', 's': 'H', 'v': 'readable'},
        {'z': 'dealer', 'r': '6', 's': 'C', 'v': 'readable'},
        {'z': 'dealer', 'r': None, 's': None, 'v': 'covered'}],
        't': 'cards_present', 'p': 'player', 'a': ['hit', 'stand'],
        'n': [{'v': 16, 'r': 'player_total', 'l': 'PLAYER TOTAL 16', 'w': 'table'}], 'b': []})


def response():
    return {'model': 'gpt-6-luna', 'service_tier': 'fast', 'status': 'completed',
        'usage': {'input_tokens': 500, 'output_tokens': 180},
        'output': [{'type': 'message', 'content': [{'type': 'output_text',
            'text': observation().model_dump_json(by_alias=True)}]}]}


class Budget:
    def __init__(self):
        self.reserves = self.settles = 0
    def reserve(self, cost):
        self.reserves += 1; return 'test'
    def settle(self, identifier, cost):
        self.settles += 1
    def receipt(self):
        return {'requests_attempted': self.reserves}
    def stop(self):
        raise AssertionError('Fixture must not exceed the reservation.')


class Transport:
    timings = {}
    def __init__(self):
        self.posts = 0; self.deadline_ns = None
    def post(self, payload, *, deadline_ns, reservation_id):
        self.posts += 1; self.deadline_ns = deadline_ns
        return response()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No real socket/DNS in these fixtures.')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)


@pytest.fixture
def frame():
    return FrameInput('owned-fixture', b'fixture-pixels', (), {'table': (0., 0., 1., 1.)}, (1, 1), (0, 0, 1, 1))


def reader(frame, budget=None, transport=None):
    return CaptureDeadlineReader(config(fast=True), budget or Budget(), [sha256(frame.table_png).hexdigest()],
        provider='openai', transport=transport or Transport(), name=NAMES[0])


def test_deadline_begins_at_capture_and_includes_receipt(frame):
    budget, transport = Budget(), Transport(); r = reader(frame, budget, transport)
    capture = time.monotonic_ns()-100_000_000
    result = r.read(frame, capture_ns=capture)
    assert result.status == 'completed' and result.observation is not None
    assert transport.deadline_ns == capture+3_000_000_000
    assert result.elapsed_ms >= 100
    assert budget.reserves == budget.settles == 1
    assert result.diagnostics['semantic_gate']['usable']
    assert {'payload_ms', 'reservation_ms', 'post_and_claim_ms', 'usage_audit_ms', 'settlement_ms',
            'strict_parse_ms', 'semantic_gate_ms', 'receipt_ms'} <= result.diagnostics['timing'].keys()


def test_expired_capture_cannot_reserve_or_call(frame):
    budget, transport = Budget(), Transport()
    result = reader(frame, budget, transport).read(frame, capture_ns=time.monotonic_ns()-3_100_000_000)
    assert result.status == 'timeout' and result.observation is None
    assert budget.reserves == transport.posts == 0


def test_payload_overrun_has_no_reservation(frame, monkeypatch):
    budget, transport = Budget(), Transport(); r = reader(frame, budget, transport)
    def slow(frame):
        time.sleep(.025); return {}
    monkeypatch.setattr(r, 'payload', slow)
    result = r.read(frame, capture_ns=time.monotonic_ns()-2_990_000_000)
    assert result.status == 'timeout' and budget.reserves == transport.posts == 0


@pytest.mark.parametrize('late_stage', ['settle', 'receipt'])
def test_audited_late_state_settles_but_never_becomes_current(frame, monkeypatch, late_stage):
    budget, transport = Budget(), Transport()
    original = getattr(budget, late_stage)
    def late(*args):
        result = original(*args)
        late_now = time.monotonic_ns()+3_100_000_000
        monkeypatch.setattr(time, 'monotonic_ns', lambda: late_now)
        return result
    monkeypatch.setattr(budget, late_stage, late)
    result = reader(frame, budget, transport).read(frame, capture_ns=time.monotonic_ns())
    assert result.status == 'timeout' and result.observation is None
    assert budget.reserves == budget.settles == transport.posts == 1
    assert 'price_based_upper_cost_usd' in result.diagnostics


def test_unverified_usage_preserves_reservation_and_rejects(frame, monkeypatch):
    budget, transport = Budget(), Transport()
    monkeypatch.setattr(transport, 'post', lambda *a, **k: {**response(), 'usage': {}})
    result = reader(frame, budget, transport).read(frame, capture_ns=time.monotonic_ns())
    assert result.status == 'error' and result.observation is None
    assert result.diagnostics['unreconciled_usage'] and budget.reserves == 1 and budget.settles == 0


class Local:
    name = 'frozen-local-contract'
    def __init__(self, usable):
        obs = observation().legacy_gate_view()
        obs.player_total = None  # Legacy adapter has no observed label/view.
        if not usable:
            obs.phase = 'unknown'; obs.controls = []
        self.observation = adapt_legacy(obs)
    def read(self, frame):
        return GroundedResult(frame.frame_id, self.name, 'completed', self.observation, 0., {})


def test_local_success_never_forces_cloud(frame):
    evidence = CurrentEvidence(); evidence.capture(frame, source='owned', table='one')
    cloud = reader(frame)
    result = local_first_attempt(evidence, Local(True), cloud)
    assert result['route'] == 'local' and result['presented']
    assert cloud.transport.posts == 0 and result['advisor_payload']['action'] in ('hit', 'stand')


def test_real_uncertainty_routes_once_and_keeps_capture_deadline(frame):
    evidence = CurrentEvidence(); stamp = evidence.capture(frame, source='owned', table='one')
    cloud = reader(frame)
    result = local_first_attempt(evidence, Local(False), cloud)
    assert result['route'] == 'fallback' and result['presented']
    assert cloud.transport.posts == 1
    assert cloud.transport.deadline_ns == stamp.capture_ns+3_000_000_000
    assert result['local_gate']['usable'] is False


@pytest.mark.parametrize('change', ['different_pixels', 'disconnect', 'different_source'])
def test_current_evidence_change_prevents_headless_delivery(frame, monkeypatch, change):
    evidence = CurrentEvidence(); evidence.capture(frame, source='owned', table='one')
    cloud = reader(frame); real = cloud.read
    def changed(frame, *, capture_ns):
        result = real(frame, capture_ns=capture_ns)
        if change == 'disconnect':
            evidence.disconnect()
        elif change == 'different_source':
            evidence.capture(frame, source='other', table='one')
        else:
            evidence.capture(FrameInput('new', b'changed', (), frame.layout, frame.source_size, frame.table_box), source='owned', table='one')
        return result
    monkeypatch.setattr(cloud, 'read', changed)
    result = local_first_attempt(evidence, Local(False), cloud)
    assert result['route'] == 'fallback' and result['presented'] is False
    assert result['advice'] is None and result['advisor_payload'] is None


def test_gate_and_solver_cannot_renew_original_deadline(frame, monkeypatch):
    import bjlab.paired_deadline_reader as module
    evidence = CurrentEvidence(); evidence.capture(frame, source='owned', table='one')
    cloud = reader(frame); original = module.recommend
    def late(*args, **kwargs):
        # Advance monotonic clock after math, avoiding a 3-second real sleep.
        result = original(*args, **kwargs)
        now = time.monotonic_ns()+3_100_000_000
        monkeypatch.setattr(time, 'monotonic_ns', lambda: now)
        return result
    monkeypatch.setattr(module, 'recommend', late)
    result = local_first_attempt(evidence, Local(False), cloud)
    assert result['presented'] is False and result['advisor_payload'] is None
    assert result['revalidation']['valid'] is False


def fixture_transport(monkeypatch, tmp_path):
    backend = FixtureBackend(); original = http.ScopedDnsHTTPTransport
    def socketless(scope):
        value = original(scope); value._pool._network_backend = backend
        return value
    monkeypatch.setattr(http, 'ScopedDnsHTTPTransport', socketless)
    scope = {h: {'address': '8.8.8.8', 'expires_at': time.monotonic()+60} for h, *_ in http.ORIGINS.values()}
    budget = PersistentRequestBudget.initialize(tmp_path/'ledger.json', authorization_id='fixture-only', max_requests=5, max_usd='8')
    transport = http.PersistentScopedTransport(provider='openai', authorization_epoch='fixture', budget=budget,
        dns_scope=scope, api_key='fixture-not-a-key')
    return transport, backend, budget


def test_actual_pinned_pool_reuse_and_verified_origin_configuration(monkeypatch, tmp_path):
    transport, backend, _ = fixture_transport(monkeypatch, tmp_path)
    try:
        assert transport.metadata() == {}
        assert transport.timings['connect_tcp_attempts'] == 1
        assert not transport.timings['reused_connection_observed']
        assert transport.metadata() == {}
        assert transport.timings['connect_tcp_attempts'] == 0
        assert transport.timings['reused_connection_observed']
        assert len(backend.connects) == 1 and backend.tls_hosts == ['api.openai.com']
        assert all(b'Host: api.openai.com' in w for w in backend.writes)
    finally:
        transport.close()
    assert all(s.closed for s in backend.streams)


@pytest.mark.parametrize('failure', ['expired_dns', 'expired_capture', 'private_ip', 'closed'])
def test_pooled_connection_cannot_bypass_scope_or_deadline(monkeypatch, tmp_path, failure):
    transport, backend, _ = fixture_transport(monkeypatch, tmp_path)
    transport.metadata(); writes = len(backend.writes)
    deadline = time.monotonic_ns()+3_000_000_000
    if failure == 'expired_dns':
        transport.dns_scope['api.openai.com']['expires_at'] = time.monotonic()-1
    elif failure == 'expired_capture':
        deadline = time.monotonic_ns()-1
    elif failure == 'private_ip':
        transport.dns_scope['api.openai.com']['address'] = '127.0.0.1'
    else:
        transport.close()
    with pytest.raises((TimeoutError, PermissionError)):
        transport.request('GET', '/models/gpt-6-luna', deadline)
    assert len(backend.writes) == writes and transport._closed


@pytest.mark.parametrize('endpoint', ['/models', '/responses-other', 'https://example.com'])
def test_endpoint_allowlist_cannot_call_other_origins(monkeypatch, tmp_path, endpoint):
    transport, backend, _ = fixture_transport(monkeypatch, tmp_path)
    try:
        with pytest.raises(PermissionError):
            transport.request('GET', endpoint, time.monotonic_ns()+3_000_000_000)
        assert not backend.writes
    finally:
        transport.close()


def test_late_worker_closes_pool_and_never_supplies_result(monkeypatch, tmp_path):
    transport, backend, _ = fixture_transport(monkeypatch, tmp_path)
    original = FixtureStream.read
    def slow(self, *args, **kwargs):
        time.sleep(.08); return original(self, *args, **kwargs)
    monkeypatch.setattr(FixtureStream, 'read', slow)
    with pytest.raises(TimeoutError):
        transport.request('GET', '/models/gpt-6-luna', time.monotonic_ns()+20_000_000)
    assert transport._closed and not transport.timings['reused_connection_observed']
    frozen = json.dumps(transport.timings, sort_keys=True)
    time.sleep(.09)
    assert json.dumps(transport.timings, sort_keys=True) == frozen
    with pytest.raises(PermissionError):
        transport.metadata()


@pytest.mark.parametrize('bad', ['missing_epoch', 'changed_payload', 'noncanonical_ledger', 'second_attempt'])
def test_post_durable_guard_rejects_replay_or_unauthorized_submission(monkeypatch, tmp_path, bad):
    transport, backend, budget = fixture_transport(monkeypatch, tmp_path)
    payload = {'reviewed': 'fixture'}; transport.bind(http.canonical_digest(payload), tmp_path/'attempt.json')
    reservation = budget.reserve('.01')
    monkeypatch.setattr(http, 'CANONICAL_LEDGER', budget.path if bad != 'noncanonical_ledger' else tmp_path/'other.json')
    def authorize(epoch):
        if bad == 'missing_epoch':
            raise PermissionError('Fixture authorization absent.')
        return epoch
    monkeypatch.setattr(http, 'require_inference_authorization', authorize)
    if bad == 'changed_payload':
        payload['extra'] = True
    if bad == 'second_attempt':
        budget.claim_submission(reservation, 'a'*64)
    try:
        with pytest.raises(PermissionError):
            transport.post(payload, deadline_ns=time.monotonic_ns()+3_000_000_000, reservation_id=reservation)
        assert not backend.writes
        assert budget.receipt()['requests_attempted'] == 1
    finally:
        transport.close()


def test_successful_post_uses_existing_pool_and_one_durable_claim(monkeypatch, tmp_path):
    transport, backend, budget = fixture_transport(monkeypatch, tmp_path)
    transport.metadata()
    original = FixtureStream.write
    body = json.dumps(response()).encode()
    def serve(self, buffer, timeout=None):
        if buffer.startswith(b'POST '):
            self.backend.writes.append(buffer)
            self.buffer.extend(b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
        else:
            original(self, buffer, timeout)
    monkeypatch.setattr(FixtureStream, 'write', serve)
    monkeypatch.setattr(http, 'CANONICAL_LEDGER', budget.path)
    monkeypatch.setattr(http, 'require_inference_authorization', lambda epoch: epoch)
    payload = {'reviewed': 'fixture'}; transport.bind(http.canonical_digest(payload), tmp_path/'attempt.json')
    reserved = budget.reserve('.01')
    try:
        assert transport.post(payload, deadline_ns=time.monotonic_ns()+3_000_000_000, reservation_id=reserved) == response()
        assert transport.timings['reused_connection_observed'] and len(backend.connects) == 1
        assert budget.receipt()['network_attempts_claimed'] == 1
        with pytest.raises(PermissionError):
            transport.post(payload, deadline_ns=time.monotonic_ns()+3_000_000_000, reservation_id=reserved)
        assert sum(w.startswith(b'POST ') for w in backend.writes) == 1
    finally:
        transport.close()


def test_claim_time_reduces_remaining_deadline_and_cannot_send_late(monkeypatch, tmp_path):
    transport, backend, budget = fixture_transport(monkeypatch, tmp_path)
    monkeypatch.setattr(http, 'CANONICAL_LEDGER', budget.path)
    monkeypatch.setattr(http, 'require_inference_authorization', lambda epoch: epoch)
    original = budget.claim_submission
    def delayed(*args):
        result = original(*args)
        late_now = time.monotonic_ns()+3_100_000_000
        monkeypatch.setattr(time, 'monotonic_ns', lambda: late_now)
        return result
    monkeypatch.setattr(budget, 'claim_submission', delayed)
    payload = {}; transport.bind(http.canonical_digest(payload), tmp_path/'attempt.json')
    reserved = budget.reserve('.01')
    with pytest.raises(TimeoutError):
        transport.post(payload, deadline_ns=time.monotonic_ns()+3_000_000_000, reservation_id=reserved)
    assert not backend.writes and transport._closed
    assert budget.receipt()['network_attempts_claimed'] == 1
    assert budget.receipt()['unknown_charge_requests'] == 1


def test_count_amendment_retains_all_prior_money_and_prevents_replay(tmp_path):
    budget = PersistentRequestBudget.initialize(tmp_path/'ledger.json', authorization_id='fixture-only', max_requests=2, max_usd='8')
    first = budget.reserve('.4'); budget.claim_submission(first, 'a'*64)
    second = budget.reserve('.3'); budget.settle(second, '.02')
    old = json.loads(budget.path.read_text())['entries']
    amended = budget.extend_request_ceiling(max_requests=5, authorization_epoch='new-human-scope', authorization_note='fixture approval')
    assert json.loads(amended.path.read_text())['entries'] == old
    assert amended.receipt()['accounted_upper_usd'] == '0.42'
    assert amended.receipt()['unknown_charge_requests'] == 1
    assert amended.receipt()['max_usd'] == '8'
    with pytest.raises(PermissionError):
        budget.receipt()  # The old handle cannot spend under a new scope.
    with pytest.raises(PermissionError):
        amended.extend_request_ceiling(max_requests=6, authorization_epoch='new-human-scope', authorization_note='replay')


def rows_for_selection():
    metric = {'semantic_timely_correct_usable_r1': True, 'semantic_false_accept': False,
        'unsupported_known_suit_tuples': 0, 'exact_card_inventory': True, 'strict_wire_validated': True,
        'semantic_complete_transcription': True, 'literal_complete_transcription': False,
        'phase_correct': True, 'controls_correct': True, 'semantic_numeric_provenance_exact': True,
        'semantic_numeric_provenance': {'matched': 1, 'expected': 1, 'extra_or_wrong': 0},
        **{k: {'correct': 3, 'expected': 3} for k in ('rank', 'suit', 'backs')}}
    return [{'candidate': name, 'status': 'completed', 'elapsed_ms': elapsed,
        'metrics': dict(metric), 'diagnostics': {'price_based_upper_cost_usd': '.001'}}
        for name, elapsed in ((NAMES[0], 1900), (NAMES[0], 2100), (NAMES[1], 2000), (NAMES[1], 2200))]


def test_selection_uses_frozen_gate_and_no_definitive_champion():
    rows = rows_for_selection(); _, winner = choose_candidate(rows)
    assert winner == NAMES[0]
    rows[1]['elapsed_ms'] = 2900  # Valid within 3s, but fails declared 2.5s sample gate.
    summaries, winner = choose_candidate(rows)
    assert winner == NAMES[1] and not summaries[NAMES[0]]['gate_passed']


@pytest.mark.parametrize('failure', ['false_accept', 'extra_suit', 'missed_back', 'timeout', 'one_case'])
def test_failures_cannot_be_hidden_for_fifth_call(failure):
    rows = rows_for_selection()
    if failure == 'false_accept':
        for r in rows:
            r['metrics']['semantic_false_accept'] = True
    elif failure == 'extra_suit':
        for r in rows:
            r['metrics']['unsupported_known_suit_tuples'] = 1
    elif failure == 'missed_back':
        for r in rows:
            r['metrics']['exact_card_inventory'] = False
    elif failure == 'timeout':
        for r in rows:
            r['status'] = 'timeout'; r['elapsed_ms'] = 3005
    else:
        rows = rows[:1]+rows[2:3]
    _, winner = choose_candidate(rows)
    assert winner is None


def test_completion_never_repeats_first_pair_or_expands_declared_lot():
    from validation.tools.paired_semantic_complete import remaining_pairs
    from validation.tools.paired_semantic_prepare import PAIRS
    results = [{'case_id': PAIRS[0][0], 'candidate': PAIRS[0][1], 'status': 'timeout', 'observation': None}]
    assert remaining_pairs(results) == PAIRS[1:]
    assert PAIRS[0] not in remaining_pairs(results)
    with pytest.raises(PermissionError):
        remaining_pairs(results*2)
    with pytest.raises(PermissionError):
        remaining_pairs([{**results[0], 'status': 'completed'}])


def last_pair_fixture():
    from validation.tools.paired_semantic_prepare import PAIRS
    rows = [rows_for_selection()[i] for i in (0, 2, 3)]
    for row, pair in zip(rows, PAIRS[:3]):
        row.update(case_id=pair[0], observation={})
    rows[0].update(status='timeout', observation=None)
    rows[2].update(status='error', observation=None)
    rows[2]['diagnostics'].update(error_type='ValidationError',
        validation_issues=[{'location': ['n', 0], 'type': 'value_error'}],
        transport={'http_status': 200})
    return rows


def test_final_completion_has_only_the_unused_fourth_pair_and_no_hybrid():
    from validation.tools.paired_semantic_last_pair import last_pair
    from validation.tools.paired_semantic_prepare import PAIRS
    rows = last_pair_fixture()
    assert last_pair(rows) == PAIRS[3]
    assert last_pair(rows) not in [(r['case_id'], r['candidate']) for r in rows]
    assert choose_candidate(rows)[1] is None


@pytest.mark.parametrize('changed', ['extra_row', 'reordered', 'non_timeout', 'http400', 'usage_unknown', 'other_parse_error'])
def test_final_completion_cannot_resume_a_different_or_unaudited_failure(changed):
    from validation.tools.paired_semantic_last_pair import last_pair
    rows = last_pair_fixture()
    if changed == 'extra_row':
        rows.append(rows[0])
    elif changed == 'reordered':
        rows[0], rows[1] = rows[1], rows[0]
    elif changed == 'non_timeout':
        rows[0]['status'] = 'completed'
    elif changed == 'http400':
        rows[2]['diagnostics']['transport']['http_status'] = 400
    elif changed == 'usage_unknown':
        rows[2]['diagnostics']['unreconciled_usage'] = True
    else:
        rows[2]['diagnostics']['validation_issues'][0]['location'] = ['c', 0]
    with pytest.raises(PermissionError):
        last_pair(rows)
