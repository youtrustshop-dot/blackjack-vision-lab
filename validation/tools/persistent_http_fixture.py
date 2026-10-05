"""Socketless HTTPX/httpcore lifecycle experiment; NOT a provider transport.

The only injectable backend is this scripted fixture. No keys, DNS resolver,
sockets, inference, production integration or real latency evidence. HTTP/1.1
reuse is exercised in the actual pinned pool, not assumed from a mock client.
"""
import json
import ssl

import httpcore
import httpx

from bjlab.controlled_http import HOSTS


class FixtureStream:
    def __init__(self, backend):
        self.backend, self.buffer, self.closed = backend, bytearray(), False

    def read(self, max_bytes, timeout=None):
        if self.closed or not self.buffer:
            raise AssertionError('Unscripted fixture read; never open a socket.')
        result = bytes(self.buffer[:max_bytes]); del self.buffer[:max_bytes]
        return result

    def write(self, buffer, timeout=None):
        if self.closed:
            raise AssertionError('Write after stream closure.')
        if buffer.startswith(b'GET '):
            self.backend.writes.append(bytes(buffer))
            # Empty JSON object and keep-alive, deterministic and socketless.
            self.buffer.extend(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Type: application/json\r\n\r\n{}')

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED and ssl_context.check_hostname
        self.backend.tls_hosts.append(server_hostname)
        return self

    def get_extra_info(self, name):
        return False if name == 'is_readable' else None

    def close(self):
        self.closed = True


class FixtureBackend:
    """Implement the core network interface without inheriting a socket backend."""
    def __init__(self):
        self.streams, self.tls_hosts, self.writes, self.connects = [], [], [], []

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.connects.append((host, port))
        stream = FixtureStream(self); self.streams.append(stream)
        return stream

    def connect_unix_socket(self, *args, **kwargs):
        raise AssertionError('No Unix socket in this fixture.')

    def sleep(self, seconds):
        raise AssertionError('No retry in this fixture.')


class PersistentFixtureSession:
    """Scoped lifecycle prototype: caller supplies an already-resolved scope.

    Every request checks expiry, even when the pool already has a connection.
    An expired/closed session cannot renew DNS or continue. Separate origins
    remain separate connections. No real transport can be injected here.
    """
    def __init__(self, backend, *, clock, expires_at):
        if type(backend) is not FixtureBackend:
            raise PermissionError('Only a socketless scripted backend is permitted.')
        self.backend, self.clock, self.expires_at = backend, clock, expires_at
        self.closed, self.requests = False, 0
        transport = httpx.HTTPTransport(verify=True, trust_env=False, retries=0,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2, keepalive_expiry=60))
        # Same pinned pool hook as PR17, exclusively with a socketless backend.
        transport._pool._network_backend = backend
        self.client = httpx.Client(transport=transport, trust_env=False, follow_redirects=False)

    def get(self, host, *, deadline):
        if self.closed:
            raise PermissionError('Fixture session is closed.')
        if host not in HOSTS:
            raise PermissionError('Origin outside the declared scope.')
        if self.clock() >= min(self.expires_at, deadline):
            self.close()
            raise TimeoutError('Scope or original evidence deadline expired.')
        self.requests += 1
        # This endpoint is a contract fixture, never a model or inference URL.
        try:
            result = self.client.get('https://'+host+'/offline-contract-fixture',
                timeout=max(.001, deadline-self.clock())).json()
            if self.clock() >= min(self.expires_at, deadline):
                raise TimeoutError('Late fixture result discarded; do not reuse its pool.')
        except Exception:
            self.close()
            raise
        return result

    def close(self):
        if not self.closed:
            self.client.close(); self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def lifecycle_report():
    backend = FixtureBackend()
    with PersistentFixtureSession(backend, clock=lambda: 0., expires_at=60.) as session:
        session.get(HOSTS[0], deadline=3.)
        cold_connections = len(backend.connects)
        session.get(HOSTS[0], deadline=3.)
        warm_connections = len(backend.connects)-cold_connections
        session.get(HOSTS[1], deadline=3.)
        requests = session.requests
    return {'evidence_kind': 'socketless-httpcore-lifecycle-fixture', 'provider_calls': 0,
        'credential_loading': False, 'real_dns_queries': 0, 'real_tcp_connections': 0,
        'fixture_http_requests': requests, 'fixture_pool_connections': len(backend.connects),
        'first_origin_cold_connections': cold_connections, 'same_origin_warm_new_connections': warm_connections,
        'tls_hostnames_preserved': backend.tls_hosts == list(HOSTS),
        'verified_tls_context_configured': True, 'all_streams_closed': all(s.closed for s in backend.streams),
        'live_latency_gain_ms': None, 'production_integration': False,
        'limits': 'Sequential pool reuse/lifecycle only; no real TLS handshake, resolver repair, DNS speed, server keep-alive, cancellation or API latency proof.'}


if __name__ == '__main__':
    print(json.dumps(lifecycle_report()))
