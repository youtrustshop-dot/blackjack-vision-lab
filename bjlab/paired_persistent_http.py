"""Opt-in VISION-025 transport: one scoped persistent pool per official origin.

No default transport is replaced. DNS answers are fresh and expire even when a
connection is pooled. Each POST consumes a frozen slot and durable canonical
reservation exactly once. No retry, proxy discovery, redirects or late reuse.
"""
from hashlib import sha256
import json
import ipaddress
import math
import os
from pathlib import Path
from threading import Event, Lock, Thread
import time

import httpx

from .api_access_policy import require_inference_authorization
from .controlled_http import EVENTS, ScopedDnsHTTPTransport
from .openai_reader import ProviderHTTPError
from .research_budget import CANONICAL_LEDGER, PersistentRequestBudget

ORIGINS = {
    'openai': ('api.openai.com', 'https://api.openai.com/v1', '/models/gpt-6-luna', '/responses'),
    'gemini': ('generativelanguage.googleapis.com', 'https://generativelanguage.googleapis.com/v1beta',
               '/models/gemini-3.5-flash-lite', '/models/gemini-3.5-flash-lite:generateContent'),
}


def ensure_deadline(deadline_ns):
    if type(deadline_ns) is not int or deadline_ns <= time.monotonic_ns():
        raise TimeoutError('Original absolute deadline expired.')


def canonical_digest(payload):
    return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class PersistentScopedTransport:
    def __init__(self, *, provider, authorization_epoch, budget, dns_scope, api_key=None):
        if provider not in ORIGINS:
            raise ValueError('Only the two frozen provider origins are allowed.')
        self.provider, self.epoch, self.budget, self.dns_scope = provider, authorization_epoch, budget, dns_scope
        self._key = api_key or os.environ.get('OPENAI_API_KEY' if provider == 'openai' else 'GEMINI_API_KEY')
        if not self._key:
            raise PermissionError('Existing provider credential is unavailable.')
        self._closed = False; self._bound = None; self._request_count = 0
        self._lock = Lock(); self.timings = {}; self._active = False
        began = time.monotonic_ns()
        # Single connection, and a lifetime shorter than the scoped DNS lease.
        network = ScopedDnsHTTPTransport(dns_scope)
        # Pinned httpcore pool settings: limits on Client would not apply when
        # supplying an already constructed transport.
        network._pool._max_connections = 1
        network._pool._max_keepalive_connections = 1
        network._pool._keepalive_expiry = 60
        self.client = httpx.Client(transport=network, trust_env=False, follow_redirects=False)
        self.initialization_ms = (time.monotonic_ns()-began)/1e6

    def _scope(self, deadline_ns):
        try:
            ensure_deadline(deadline_ns)
        except TimeoutError:
            self.close(); raise
        host = ORIGINS[self.provider][0]
        entry = self.dns_scope.get(host)
        if (self._closed or not entry or type(entry['expires_at']) not in (int, float) or
                not math.isfinite(entry['expires_at']) or time.monotonic() >= entry['expires_at']):
            self.close()
            raise PermissionError('Pool closed or original DNS scope expired.')
        address = ipaddress.ip_address(entry['address'])
        if address.version != 4 or not address.is_global:
            self.close(); raise PermissionError('Invalid official DNS scope.')

    def bind(self, payload_sha256, attempt_path):
        if self._closed or self._bound is not None:
            raise PermissionError('No fresh one-shot payload slot.')
        self._bound = (payload_sha256, Path(attempt_path))

    def close(self):
        self._closed = True; self._bound = None
        self.client.close()

    def metadata(self):
        return self.request('GET', ORIGINS[self.provider][2], time.monotonic_ns()+10_000_000_000)

    def post(self, payload, *, deadline_ns, reservation_id):
        started = time.monotonic_ns(); claim_ms = None
        self.timings = {}
        try:
            self._scope(deadline_ns)
            if require_inference_authorization(self.epoch) != self.epoch:
                raise PermissionError('Spending authorization changed.')
            if (not isinstance(self.budget, PersistentRequestBudget) or
                self.budget.path.resolve() != CANONICAL_LEDGER.resolve()):
                raise PermissionError('Canonical persistent allowance required.')
            bound, self._bound = self._bound, None
            if bound is None or canonical_digest(payload) != bound[0]:
                raise PermissionError('Unbound or modified payload; no submission.')
            ensure_deadline(deadline_ns)
            with bound[1].open('x', encoding='utf-8') as handle:
                json.dump({'epoch': self.epoch, 'payload_sha256': bound[0], 'retry': 0}, handle)
                handle.flush(); os.fsync(handle.fileno())
            self.budget.claim_submission(reservation_id, sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
            claim_ms = (time.monotonic_ns()-started)/1e6
            ensure_deadline(deadline_ns)  # Claim time never grants a new timeout.
            raw = self.request('POST', ORIGINS[self.provider][3], deadline_ns, payload)
            if self.provider == 'openai':
                return raw
            # Same conversion as the frozen Gemini adapter, including thinking.
            usage = raw.get('usageMetadata') or {}; candidates = raw.get('candidates', [])
            counts = [usage.get(k, 0) for k in ('candidatesTokenCount', 'thoughtsTokenCount')]
            output = sum(counts) if all(type(n) is int and n >= 0 for n in counts) else None
            texts = []
            for candidate in candidates:
                for part in candidate.get('content', {}).get('parts', []):
                    if set(part)-{'text', 'thought', 'thoughtSignature'}:
                        raise ValueError('Unexpected Gemini tool or media.')
                    if not part.get('thought') and 'text' in part:
                        texts.append({'type': 'output_text', 'text': part['text']})
            complete = len(candidates) == 1 and candidates[0].get('finishReason') == 'STOP'
            return {'id': raw.get('responseId'), 'model': raw.get('modelVersion'),
                'status': 'completed' if complete else 'incomplete', 'output': [{'type': 'message', 'content': texts}],
                'usage': {'input_tokens': usage.get('promptTokenCount'), 'output_tokens': output},
                'provider_usage': usage, 'service_tier': 'default'}
        except Exception:
            self.close(); raise
        finally:
            self.timings = {**self.timings, 'submission_claim_ms': claim_ms,
                            'post_including_claim_ms': (time.monotonic_ns()-started)/1e6}

    def request(self, method, endpoint, deadline_ns, payload=None):
        expected = ORIGINS[self.provider][2 if method == 'GET' else 3]
        if (method not in ('GET', 'POST') or endpoint != expected or
                (method == 'GET' and payload is not None) or (method == 'POST' and not isinstance(payload, dict))):
            raise PermissionError('Only exact declared metadata/inference endpoints are allowed.')
        self._scope(deadline_ns)
        remaining = (deadline_ns-time.monotonic_ns())/1e9
        if not math.isfinite(remaining) or not 0 < remaining <= 10:
            raise ValueError('Bounded absolute request deadline required.')
        with self._lock:
            if self._active:
                raise PermissionError('Parallel or late pool reuse is prohibited.')
            self._active = True
        started = time.monotonic_ns(); done, cancelled = Event(), Event()
        result = {}; trace_rows = []; starts = {}; prior = self._request_count
        self._request_count += 1
        def work():
            def trace(name, info):
                stem, _, action = name.rpartition('.'); category = stem.rsplit('.', 1)[-1]
                if category not in EVENTS:
                    return
                self._scope(deadline_ns)
                if cancelled.is_set():
                    raise TimeoutError('Cancelled worker cannot start a late stage.')
                now = time.monotonic_ns()
                if action == 'started':
                    starts[stem] = now
                with self._lock:
                    trace_rows.append({'stage': category, 'action': action,
                        'at_ms': (now-started)/1e6,
                        'duration_ms': (now-starts[stem])/1e6 if action != 'started' and stem in starts else None})
            try:
                self._scope(deadline_ns)
                headers = {'Authorization': 'Bearer '+self._key} if self.provider == 'openai' else {'x-goog-api-key': self._key}
                body = {'json': payload} if payload is not None else {}
                with self.client.stream(method, ORIGINS[self.provider][1]+endpoint, headers=headers,
                    timeout=max(.001, (deadline_ns-time.monotonic_ns())/1e9), extensions={'trace': trace}, **body) as reply:
                    result['http_status'] = reply.status_code
                    result['headers_received_ms'] = (time.monotonic_ns()-started)/1e6
                    chunks = bytearray()
                    for chunk in reply.iter_bytes():
                        ensure_deadline(deadline_ns)
                        if cancelled.is_set():
                            raise TimeoutError('Cancelled response.')
                        chunks.extend(chunk)
                        if len(chunks) > (2_000_000 if reply.status_code == 200 else 32_000):
                            raise ValueError('Bounded response exceeded.')
                    result['body_complete_ms'] = (time.monotonic_ns()-started)/1e6
                    if reply.status_code != 200:
                        raise ProviderHTTPError(reply.status_code)
                    began = time.monotonic_ns(); value = json.loads(chunks)
                    result['provider_json_parse_ms'] = (time.monotonic_ns()-began)/1e6
                    ensure_deadline(deadline_ns); result['value'] = value
            except Exception as exc:
                result['exception'] = exc
            finally:
                done.set()
        Thread(target=work, daemon=True, name='vision025-persistent-http').start()
        try:
            if not done.wait(max(0., (deadline_ns-time.monotonic_ns())/1e9)) or time.monotonic_ns() >= deadline_ns:
                cancelled.set(); self.close()
                raise TimeoutError('Original complete-response deadline expired.')
            if 'exception' in result:
                self.close(); raise result['exception']
            return result['value']
        finally:
            with self._lock:
                rows = list(trace_rows); self._active = False
            self.timings = {k: result[k] for k in ('http_status', 'headers_received_ms', 'body_complete_ms', 'provider_json_parse_ms') if k in result}
            connects = sum(r['stage'] == 'connect_tcp' and r['action'] == 'started' for r in rows)
            self.timings.update(transport_total_ms=(time.monotonic_ns()-started)/1e6, trace=rows,
                connect_tcp_attempts=connects, pool_prior_requests=prior,
                reused_connection_observed=bool(prior and connects == 0 and 'value' in result and not cancelled.is_set()),
                worker_completed=done.is_set(), pool_closed=self._closed,
                dns_resolution_outside_request=True)
