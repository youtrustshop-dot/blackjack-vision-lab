"""No-provider replay/timing/budget proposal tests, with an untouched ledger."""
from copy import deepcopy
import socket
import subprocess

import pytest

from validation.tools.numeric_contract_replay import analyze_timeout, assert_runtime_disarmed, minimum_proposal, offline_guard


def retained_trace():
    return {'status': 'timeout', 'observation': None, 'candidate': 'luna-fast-live-v3',
        'case_id': 'labelled-totals', 'elapsed_ms': 3048.838,
        'diagnostics': {'timing': {'payload_ms': 2.2522, 'reservation_ms': 7.2456,
            'transport_total_ms': 2984.7271, 'observation_parse_validate_ms': 7.4094,
            'headers_received_ms': 2970.1861, 'body_complete_ms': 2984.2514,
            'receive_response_headers_ms': 2771.1879, 'provider_json_parse_ms': .1328}}}


def test_nonoverlapping_intervals_and_unknown_costs_not_invented():
    trace = retained_trace(); original = deepcopy(trace)
    result = analyze_timeout(trace)
    assert result['measured_sum_ms'] == pytest.approx(3001.6343)
    assert result['derived_untimed_residual_ms'] == pytest.approx(47.2037)
    assert result['within_transport_cumulative_ms']['body_complete_ms'] == 2984.2514
    assert result['within_transport_stage_ms']['provider_json_parse_ms'] == .1328
    assert all(n is None for n in result['unobserved_ms'].values())
    assert trace == original
    # The transport's nested header/body/parser times must not be summed again.
    assert result['measured_sum_ms'] < result['total_reader_ms']
    assert result['measured_sum_ms'] > result['live_deadline_ms']


def test_timeout_analysis_cannot_recover_a_discarded_observation():
    for changes in ({'observation': {}}, {'status': 'completed'}, {'elapsed_ms': 1}):
        with pytest.raises(ValueError): analyze_timeout({**retained_trace(), **changes})


def test_five_request_proposal_retains_caps_and_unknown_reservations():
    receipt = {'max_usd': '8', 'accounted_upper_usd': '5.095785750', 'requests_attempted': 100,
        'max_requests': 102, 'unknown_charge_requests': 13, 'unknown_charge_reserved_usd': '4.9064744'}
    original = deepcopy(receipt)
    plan = minimum_proposal(receipt)
    assert plan['maximum_requests'] == 5 and plan['paired_requests'] == 4
    assert plan['conditional_stable_hybrid_requests'] == 1
    assert plan['combined_worst_case_usd'] == '2.2138736' and plan['fits_existing_money_margin_at_frozen_prices']
    assert plan['minimum_future_lifetime_ceiling_if_authorized'] == 105
    assert plan['status'] == 'PROPOSAL_ONLY_NOT_AUTHORIZED' and plan['new_requests_executed'] == 0
    assert receipt == original
    assert not minimum_proposal({**receipt, 'accounted_upper_usd': '7'})['fits_existing_money_margin_at_frozen_prices']


def test_offline_guard_rejects_network_and_resolver_subprocess_before_execution():
    with offline_guard():
        with pytest.raises(PermissionError): socket.getaddrinfo('api.openai.com', 443)
        with pytest.raises(PermissionError): socket.create_connection(('api.openai.com', 443))
        with pytest.raises(PermissionError): subprocess.run(['pwsh', '-Command', 'Resolve-DnsName api.openai.com'])
        with socket.socket() as sock:
            with pytest.raises(PermissionError): sock.connect(('127.0.0.1', 443))


@pytest.mark.parametrize('change', [dict(inference_authorized=True), dict(inference_authorized=0),
    dict(max_requests=2), dict(max_requests=False), dict(max_usd='1'), dict(max_usd='NaN'), dict(max_usd='bad')])
def test_replay_cannot_disarm_or_amend_a_runtime_as_a_side_effect(change):
    valid = dict(inference_authorized=False, max_requests=0, max_usd='0')
    assert_runtime_disarmed(valid)
    policy = {**valid, **change}; original = deepcopy(policy)
    with pytest.raises(PermissionError): assert_runtime_disarmed(policy)
    assert policy == original
