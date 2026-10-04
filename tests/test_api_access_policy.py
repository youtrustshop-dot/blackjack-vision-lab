"""No account/credential access: deny paid transport before its network client."""
import json

import pytest

from bjlab import api_access_policy
from bjlab.openai_reader import ResponsesTransport


def install_policy(tmp_path, monkeypatch, **changes):
    policy = dict(inference_authorized=False, authorization_epoch='new-explicit-consent',
                  max_requests=0, max_usd='0')
    policy.update(changes)
    path = tmp_path/'matrix.json'
    path.write_text(json.dumps({'api_access_policy': policy}), encoding='utf-8')
    monkeypatch.setattr(api_access_policy, 'MATRIX', path)
    return path


def test_zero_budget_blocks_before_network_even_with_a_key_and_old_epoch(tmp_path, monkeypatch):
    install_policy(tmp_path, monkeypatch)
    def forbidden(*a, **k):
        raise AssertionError('No network may be reached')
    monkeypatch.setattr('httpx.AsyncClient', forbidden)
    with pytest.raises(PermissionError, match='blocked_zero_api_budget'):
        ResponsesTransport(api_key='unit-test-not-a-key', authorization_epoch='old-consent').post({}, 1)


@pytest.mark.parametrize('change', [
    {'inference_authorized': True},
    {'inference_authorized': 'true', 'max_requests': 1, 'max_usd': '1'},
    {'inference_authorized': True, 'max_requests': 1, 'max_usd': 'NaN'},
    {'inference_authorized': True, 'max_requests': True, 'max_usd': '1'},
])
def test_zero_or_invalid_allowance_cannot_enable_inference(tmp_path, monkeypatch, change):
    install_policy(tmp_path, monkeypatch, **change)
    with pytest.raises(PermissionError):
        api_access_policy.require_inference_authorization()


def test_credit_balance_alone_is_never_permission(tmp_path, monkeypatch):
    install_policy(tmp_path, monkeypatch, credit_check={'free_credit_balance': 100})
    with pytest.raises(PermissionError, match='blocked_zero_api_budget'):
        api_access_policy.require_inference_authorization()


def test_new_positive_approval_still_rejects_an_old_epoch(tmp_path, monkeypatch):
    install_policy(tmp_path, monkeypatch, inference_authorized=True, max_requests=1, max_usd='1')
    with pytest.raises(PermissionError, match='blocked_stale_spending_authorization'):
        api_access_policy.require_inference_authorization('old-consent')
    assert api_access_policy.require_inference_authorization('new-explicit-consent') == 'new-explicit-consent'


@pytest.mark.parametrize('contents', [None, '{}', 'not-json', '{"api_access_policy": null}'])
def test_missing_or_corrupt_policy_fails_closed(tmp_path, monkeypatch, contents):
    path = tmp_path/'missing.json'
    monkeypatch.setattr(api_access_policy, 'MATRIX', path)
    if contents is not None:
        path.write_text(contents)
    with pytest.raises(PermissionError):
        api_access_policy.require_inference_authorization()


def test_transport_requires_explicit_current_epoch_even_after_future_approval(tmp_path, monkeypatch):
    install_policy(tmp_path, monkeypatch, inference_authorized=True, max_requests=1, max_usd='1')
    def forbidden(*a, **k):
        raise AssertionError('No network may be reached')
    monkeypatch.setattr('httpx.AsyncClient', forbidden)
    with pytest.raises(PermissionError, match='blocked_missing_spending_authorization'):
        ResponsesTransport(api_key='unit-test-not-a-key').post({}, 1)
