"""Opt-in bounded HTTP with an expiring DNS scope for the research smoke only.

Both plain clients intermittently stalled in native DNS. Switching to a
synchronous client alone did not fix the problem. Pre-resolve official domains
through the configured OS resolver and use its fresh answers only in this pool.
Keep official origins, verified TLS, the same credentials and request bodies;
change neither system DNS/proxies nor frozen/default readers. A daemon worker
keeps uncancellable native DNS outside the caller deadline. Late DNS completion
cannot start a subsequent HTTP stage, and late results have no callback.
"""
import json
import ipaddress
import math
import subprocess
from threading import Event, Lock, Thread
import time

import httpx
import httpcore

from .grounded_cloud import GeminiTransport
from .openai_reader import API_ROOT, ProviderHTTPError, ResponsesTransport

EVENTS = ('connect_tcp', 'start_tls', 'send_request_headers', 'send_request_body',
          'receive_response_headers', 'receive_response_body')
HOSTS = ('api.openai.com', 'generativelanguage.googleapis.com')


def resolve_scope():
    """Fresh OS-configured DNS answers; no fixed addresses or OS setting change."""
    answers = {}
    for host in HOSTS:
        command = "Resolve-DnsName -Name '"+host+"' -Type A -DnsOnly -QuickTimeout -ErrorAction Stop | " \
                  "Where-Object { $_.IPAddress } | Select-Object IPAddress,TTL | ConvertTo-Json -Compress"
        began = time.monotonic()
        process = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', command],
                                 capture_output=True, text=True, timeout=10)
        if process.returncode != 0: raise PermissionError('Read-only DNS control failed.')
        values = json.loads(process.stdout.lstrip('\ufeff'))
        if isinstance(values, dict): values = [values]
        if not values: raise PermissionError('No current DNS A answer.')
        entry = values[0]; address = ipaddress.ip_address(entry['IPAddress']); ttl = entry['TTL']
        if not address.is_global or address.version != 4 or type(ttl) is not int or ttl <= 0:
            raise PermissionError('Nonpublic or invalid official DNS answer.')
        answers[host] = {'address': str(address), 'expires_at': began+min(ttl, 60),
                         'resolution_ms': (time.monotonic()-began)*1000}
    return answers


class ScopedDnsBackend(httpcore.SyncBackend):
    def __init__(self, answers): self.answers = answers

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if isinstance(host, bytes): host = host.decode('ascii')
        entry = self.answers.get(host)
        if host not in HOSTS or port != 443 or not entry or time.monotonic() >= entry['expires_at']:
            raise PermissionError('Official DNS scope absent or expired; no request.')
        address = ipaddress.ip_address(entry['address'])
        if address.version != 4 or not address.is_global: raise PermissionError('Invalid DNS scope.')
        # Only TCP resolution changes. HTTP origin/Host and TLS SNI remain the
        # original domain; certificate verification is still enforced by core.
        return super().connect_tcp(str(address), port, timeout, local_address, socket_options)


class ScopedDnsHTTPTransport(httpx.HTTPTransport):
    def __init__(self, answers):
        super().__init__(verify=True, trust_env=False, retries=0)
        # This is a pinned HTTPX 0.28.1/core 1.0.9 adapter. No global resolver
        # monkeypatch; the public core NetworkBackend applies to this pool only.
        self._pool._network_backend = ScopedDnsBackend(answers)


def bounded_call(function, timeout):
    """Worker exceptions are propagated by type; never log their messages."""
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 10:
        raise ValueError('A finite existing request deadline is required.')
    done, cancelled = Event(), Event(); box = {}; deadline = time.monotonic()+timeout
    def work():
        try: box['value'] = function(deadline, cancelled)
        except Exception as exc: box['exception'] = exc
        finally: done.set()
    Thread(target=work, daemon=True, name='bounded-http-control').start()
    if not done.wait(max(0., deadline-time.monotonic())) or time.monotonic() > deadline:
        cancelled.set()
        raise TimeoutError('Complete-response deadline expired; no result accepted.')
    if 'exception' in box: raise box['exception']
    return box['value']


class SynchronousControl:
    def __init__(self, *args, dns_scope=None, **kwargs):
        super().__init__(*args, **kwargs); self.dns_scope = dns_scope

    async def _request(self, method, endpoint, timeout, payload=None):
        gemini = isinstance(self, GeminiTransport)
        allowed = ('models/gemini-3.5-flash-lite', 'models/gemini-3.5-flash-lite:generateContent') if gemini else \
            ('/models/gpt-6-luna', '/responses')
        if (method not in ('GET', 'POST') or endpoint != allowed[method == 'POST'] or
                (method == 'GET' and payload is not None) or (method == 'POST' and not isinstance(payload, dict))):
            raise PermissionError('Only the declared official model metadata and inference endpoints are allowed.')
        timings, starts, lock = {}, {}, Lock(); begun = time.perf_counter()
        def work(deadline, cancelled):
            def trace(name, info):
                stem, _, action = name.rpartition('.'); category = stem.rsplit('.', 1)[-1]
                if category not in EVENTS: return
                if cancelled.is_set() or time.monotonic() >= deadline:
                    raise TimeoutError('Expired stage; do not begin a late HTTP request.')
                with lock:
                    if action == 'started': starts[stem] = time.perf_counter()
                    elif action in ('complete', 'failed') and stem in starts:
                        timings[category+'_ms'] = (time.perf_counter()-starts[stem])*1000
            headers = {'x-goog-api-key': self._key} if gemini else {'Authorization': 'Bearer '+self._key}
            root = 'https://generativelanguage.googleapis.com/v1beta/' if gemini else API_ROOT
            remaining = max(.001, deadline-time.monotonic())
            network_transport = ScopedDnsHTTPTransport(self.dns_scope) if self.dns_scope is not None else \
                httpx.HTTPTransport(verify=True, trust_env=False, retries=0)
            with httpx.Client(transport=network_transport,
                              trust_env=False, follow_redirects=False, timeout=remaining) as client:
                body = {'json': payload} if payload is not None else {}
                with client.stream(method, root+endpoint, headers=headers, extensions={'trace': trace}, **body) as response:
                    with lock: timings['headers_received_ms'] = (time.perf_counter()-begun)*1000
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        if cancelled.is_set() or time.monotonic() >= deadline: raise TimeoutError('Expired response.')
                        chunks.extend(chunk)
                        if len(chunks) > (2_000_000 if response.status_code == 200 else 32_000):
                            raise ValueError('Bounded provider response exceeded.')
                    with lock: timings['body_complete_ms'] = (time.perf_counter()-begun)*1000
                    if response.status_code != 200: raise ProviderHTTPError(response.status_code)
                    started = time.perf_counter(); result = json.loads(chunks)
                    with lock: timings['provider_json_parse_ms'] = (time.perf_counter()-started)*1000
                    return result
        try: return bounded_call(work, timeout)
        finally:
            with lock:
                # Copy rather than retain worker state: late work cannot refresh
                # the result, its timestamp or a published diagnostics record.
                self.timings = {**timings, 'transport_total_ms': (time.perf_counter()-begun)*1000,
                                'dns_separate_ms': None}


class ControlledResponsesTransport(SynchronousControl, ResponsesTransport):
    pass


class ControlledGeminiTransport(SynchronousControl, GeminiTransport):
    pass
