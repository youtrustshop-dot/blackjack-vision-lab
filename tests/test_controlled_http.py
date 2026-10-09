"""Meaningful offline deadline and endpoint guards; no provider quality claim."""
import asyncio
from threading import Event
import time

import pytest

from bjlab.controlled_http import ControlledResponsesTransport, ScopedDnsBackend, bounded_call
from validation.tools.cloud_connection_diagnosis import exception_types, stage_at_stop


def test_late_result_is_not_accepted_and_worker_gets_cancellation():
    release, finished = Event(), Event(); seen = []
    def work(deadline, cancelled):
        release.wait(1); seen.append(cancelled.is_set()); finished.set(); return 'old state'
    began = time.monotonic()
    with pytest.raises(TimeoutError): bounded_call(work, .03)
    assert time.monotonic()-began < .5
    release.set(); assert finished.wait(1) and seen == [True]


def test_worker_called_once_and_error_is_not_retried():
    calls = []
    def fail(deadline, cancelled): calls.append(1); raise ValueError('private sentinel')
    with pytest.raises(ValueError): bounded_call(fail, .5)
    assert calls == [1]


@pytest.mark.parametrize('timeout', [0, -1, 11, float('inf'), float('nan'), True])
def test_invalid_deadline_never_starts_worker(timeout):
    with pytest.raises(ValueError): bounded_call(lambda *_: pytest.fail('Must not run'), timeout)


@pytest.mark.parametrize('method,endpoint', [('POST', '/models/gpt-6-luna'),
    ('GET', '/responses'), ('GET', 'https://untrusted.example/'), ('DELETE', '/models/gpt-6-luna')])
def test_unknown_endpoint_never_sends_key(method, endpoint):
    transport = ControlledResponsesTransport(api_key='offline sentinel')
    with pytest.raises(PermissionError): asyncio.run(transport._request(method, endpoint, 1.))


def test_dns_pending_is_distinguished_from_tls_and_http_wait():
    events = [{'stage': 'connect_tcp', 'action': 'started'}, {'stage': 'dns', 'action': 'started'},
              {'stage': 'connect_tcp', 'action': 'failed'}]
    assert stage_at_stop(events) == 'dns_resolution_pending'
    assert stage_at_stop([{'stage': 'start_tls', 'action': 'started'}]) == 'start_tls_pending'
    assert stage_at_stop([{'stage': 'receive_response_headers', 'action': 'started'}]) == 'receive_response_headers_pending'


def test_exception_trace_retains_types_only():
    try:
        try: raise ValueError('private sentinel')
        except ValueError as inner: raise TimeoutError('another private sentinel') from inner
    except TimeoutError as exc: assert exception_types(exc) == ['TimeoutError', 'ValueError']


@pytest.mark.parametrize('host,entry', [('untrusted.example', {'address': '8.8.8.8', 'expires_at': time.monotonic()+1}),
    ('api.openai.com', {'address': '8.8.8.8', 'expires_at': 0}),
    ('api.openai.com', {'address': '127.0.0.1', 'expires_at': time.monotonic()+1})])
def test_dns_scope_rejects_unapproved_expired_or_private_answers(host, entry):
    with pytest.raises(PermissionError): ScopedDnsBackend({host: entry}).connect_tcp(host, 443)


def test_dns_scope_affects_tcp_only(monkeypatch):
    import httpcore
    calls = []
    monkeypatch.setattr(httpcore.SyncBackend, 'connect_tcp', lambda self, *args: calls.append(args) or 'offline stream')
    backend = ScopedDnsBackend({'api.openai.com': {'address': '8.8.8.8', 'expires_at': time.monotonic()+1}})
    assert backend.connect_tcp('api.openai.com', 443, 1) == 'offline stream'
    assert calls[0][0:2] == ('8.8.8.8', 443)
