"""Pool/lifecycle evidence only; prohibit real DNS/sockets in every fixture."""
import socket
import subprocess

import httpcore
import pytest

from bjlab.controlled_http import HOSTS
from validation.tools.persistent_http_fixture import FixtureBackend, PersistentFixtureSession, lifecycle_report


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Offline fixture tried to access DNS, a socket or a subprocess.')
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)


def test_real_pool_reuses_same_origin_and_closes_streams():
    result = lifecycle_report()
    assert result['first_origin_cold_connections'] == 1
    assert result['same_origin_warm_new_connections'] == 0
    assert result['fixture_http_requests'] == 3 and result['fixture_pool_connections'] == 2
    assert result['tls_hostnames_preserved'] and result['all_streams_closed']
    assert result['provider_calls'] == result['real_dns_queries'] == result['real_tcp_connections'] == 0
    assert result['live_latency_gain_ms'] is None


def test_origin_host_and_tls_name_preserved_and_close_is_idempotent():
    backend = FixtureBackend(); session = PersistentFixtureSession(backend, clock=lambda: 0., expires_at=60.)
    session.get(HOSTS[0], deadline=3.)
    assert backend.connects == [(HOSTS[0], 443)] and backend.tls_hosts == [HOSTS[0]]
    assert b'Host: api.openai.com\r\n' in backend.writes[0]
    assert b'Authorization:' not in backend.writes[0] and b'x-goog-api-key:' not in backend.writes[0]
    session.close(); session.close()
    with pytest.raises(PermissionError): session.get(HOSTS[0], deadline=3.)
    assert len(backend.writes) == 1 and all(s.closed for s in backend.streams)


def test_expired_scope_blocks_even_an_existing_pooled_connection():
    now = [0.]; backend = FixtureBackend()
    with PersistentFixtureSession(backend, clock=lambda: now[0], expires_at=2.) as session:
        session.get(HOSTS[0], deadline=3.)
        now[0] = 2.
        with pytest.raises(TimeoutError): session.get(HOSTS[0], deadline=3.)
        assert session.closed and session.requests == 1 and len(backend.writes) == 1


def test_original_deadline_not_reset_for_second_request():
    now = [0.]; backend = FixtureBackend()
    with PersistentFixtureSession(backend, clock=lambda: now[0], expires_at=60.) as session:
        session.get(HOSTS[0], deadline=3.)
        now[0] = 3.
        with pytest.raises(TimeoutError): session.get(HOSTS[0], deadline=3.)
        assert session.requests == 1


def test_late_result_closes_pool_without_publishing_or_retrying():
    times = iter([0., 0., 4.]); backend = FixtureBackend()
    with PersistentFixtureSession(backend, clock=lambda: next(times), expires_at=60.) as session:
        with pytest.raises(TimeoutError): session.get(HOSTS[0], deadline=3.)
        assert session.closed and session.requests == 1 and len(backend.writes) == 1


def test_unknown_origin_and_real_backend_cannot_enter_socketless_experiment():
    backend = FixtureBackend()
    with PersistentFixtureSession(backend, clock=lambda: 0., expires_at=60.) as session:
        with pytest.raises(PermissionError): session.get('untrusted.example', deadline=3.)
        assert session.requests == 0 and not backend.connects
    with pytest.raises(PermissionError):
        PersistentFixtureSession(httpcore.SyncBackend(), clock=lambda: 0., expires_at=60.)


def test_failed_request_closes_pool_without_automatic_retry(monkeypatch):
    from validation.tools.persistent_http_fixture import FixtureStream
    def fail(*args, **kwargs):
        raise ValueError('Scripted failure, not a provider response.')
    monkeypatch.setattr(FixtureStream, 'read', fail)
    backend = FixtureBackend()
    session = PersistentFixtureSession(backend, clock=lambda: 0., expires_at=60.)
    with pytest.raises(ValueError): session.get(HOSTS[0], deadline=3.)
    assert session.closed and session.requests == 1 and len(backend.writes) == 1
    assert all(stream.closed for stream in backend.streams)
