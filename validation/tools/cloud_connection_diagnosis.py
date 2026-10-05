"""Bounded read-only A/B model-access diagnosis; never generates or uploads.

Trace events and exception TYPES only: headers, bodies and exception messages
are not retained. Both clients use verified TLS, direct official HTTPS, no
environment proxies, no redirects and no retries. A result cannot arm inference.
"""
import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import ssl
import sys
from threading import Event, Lock, Thread
import time
from unittest.mock import patch

import httpx

from bjlab.api_access_policy import MATRIX
from bjlab.live_cloud import MeasuredGeminiTransport, MeasuredResponsesTransport
from validation.tools.api_reader_tournament import ROOT
from validation.tools.paired_cloud_prepare import ledger_snapshot

ENDPOINTS = {
    'openai': ('api.openai.com', '/v1/models/gpt-6-luna'),
    'gemini': ('generativelanguage.googleapis.com', '/v1beta/models/gemini-3.5-flash-lite'),
}
TIMEOUT = 10.


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def credentials():
    # Prior user choice is reuse-existing; load only the already approved files.
    for filename, names in (('.env.local', ('OPENAI_API_KEY',)),
                            ('.env.gemini.local', ('GEMINI_API_KEY', 'GOOGLE_API_KEY'))):
        for line in (ROOT/filename).read_text(encoding='utf-8-sig').splitlines():
            name, sep, value = line.partition('=')
            if sep and name.strip() in names:
                key = 'GEMINI_API_KEY' if name.strip() == 'GOOGLE_API_KEY' else name.strip()
                os.environ[key] = value.strip().strip('\"\'')
    if not all(os.environ.get(k) for k in ('OPENAI_API_KEY', 'GEMINI_API_KEY')):
        raise PermissionError('Existing credentials unavailable; do not provision or disclose.')


def exception_types(exc):
    values, seen = [], set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc)); values.append(type(exc).__name__)
        exc = exc.__cause__ or exc.__context__
    return values


def bounded(function, timeout=TIMEOUT):
    done = Event(); value = {}
    def call():
        try: value['result'] = function()
        except Exception as exc: value['exceptions'] = exception_types(exc)
        finally: done.set()
    Thread(target=call, daemon=True, name='read-only-independent-control').start()
    if not done.wait(timeout):
        return {'exceptions': ['ReadOnlyWallDeadline'], 'worker_completed': False}
    return {**value, 'worker_completed': True}


class Recorder:
    def __init__(self):
        self.origin = time.perf_counter(); self.rows = []; self.lock = Lock()

    def event(self, stage, action, **safe):
        with self.lock:
            self.rows.append({'stage': stage, 'action': action,
                             'at_ms': (time.perf_counter()-self.origin)*1000, **safe})

    def snapshot(self):
        with self.lock: return list(self.rows)

    def trace(self, name, info):
        stem, _, action = name.rpartition('.')
        stage = stem.rsplit('.', 1)[-1]
        if stage in ('connect_tcp', 'start_tls', 'send_request_headers', 'send_request_body',
                     'receive_response_headers', 'receive_response_body'):
            self.event(stage, action, **({'exception_type': type(info['exception']).__name__}
                                       if action == 'failed' and 'exception' in info else {}))


def stage_at_stop(events):
    pending = {}
    for event in events:
        stage, action = event['stage'], event['action']
        if action == 'started': pending[stage] = True
        elif action in ('complete', 'failed'): pending.pop(stage, None)
    if 'dns' in pending: return 'dns_resolution_pending'
    for stage in ('receive_response_body', 'receive_response_headers', 'send_request_body',
                  'send_request_headers', 'start_tls', 'connect_tcp'):
        if stage in pending: return stage+'_pending'
    return 'completed_or_unobserved'


@contextmanager
def instrumentation(host, recorder):
    original_dns = socket.getaddrinfo
    original_client = httpx.AsyncClient
    def dns(name, port, family=0, type=0, proto=0, flags=0):
        decoded = name.decode() if isinstance(name, bytes) else name
        relevant = decoded == host
        if relevant: recorder.event('dns', 'started', family=int(family))
        try:
            values = original_dns(name, port, family, type, proto, flags)
            if relevant: recorder.event('dns', 'complete', address_count=len(values),
                                        families=sorted({int(v[0]) for v in values}))
            return values
        except Exception as exc:
            if relevant: recorder.event('dns', 'failed', exception_type=type(exc).__name__)
            raise
    class TracedAsyncClient(original_client):
        def stream(self, *args, **kwargs):
            extensions = dict(kwargs.get('extensions') or {})
            existing = extensions.get('trace')
            async def trace(name, info):
                recorder.trace(name, info)
                if existing is not None: await existing(name, info)
            extensions['trace'] = trace; kwargs['extensions'] = extensions
            return super().stream(*args, **kwargs)
    with patch('socket.getaddrinfo', dns), patch('bjlab.live_cloud.httpx.AsyncClient', TracedAsyncClient):
        yield


def model_access(provider, response):
    if provider == 'openai': return response.get('id') == 'gpt-6-luna'
    return response.get('name') == 'models/gemini-3.5-flash-lite' and \
        'generateContent' in response.get('supportedGenerationMethods', [])


def compare(provider, kind):
    host, path = ENDPOINTS[provider]; recorder = Recorder(); started = time.perf_counter()
    def request():
        if kind == 'project':
            transport = MeasuredResponsesTransport() if provider == 'openai' else \
                MeasuredGeminiTransport(authorization_epoch=None, budget=None)
            endpoint = '/models/gpt-6-luna' if provider == 'openai' else 'models/gemini-3.5-flash-lite'
            result = asyncio.run(transport._request('GET', endpoint, TIMEOUT))
            return {'http_status': 200, 'model_access_verified': model_access(provider, result)}
        headers = {'Authorization': 'Bearer '+os.environ['OPENAI_API_KEY']} if provider == 'openai' else \
            {'x-goog-api-key': os.environ['GEMINI_API_KEY']}
        with httpx.Client(transport=httpx.HTTPTransport(retries=0, verify=True, trust_env=False),
                          trust_env=False, follow_redirects=False, timeout=TIMEOUT) as client:
            with client.stream('GET', 'https://'+host+path, headers=headers,
                               extensions={'trace': recorder.trace}) as response:
                recorder.event('http', 'headers', status=response.status_code)
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000: raise ValueError('Bounded metadata response exceeded.')
                result = json.loads(body) if response.status_code == 200 else {}
                return {'http_status': response.status_code,
                        'model_access_verified': response.status_code == 200 and model_access(provider, result)}
    with instrumentation(host, recorder):
        result = bounded(request, TIMEOUT+.5)
    events = recorder.snapshot()
    return {'provider': provider, 'client': kind, 'method': 'GET', 'official_host': host,
            'endpoint': path, 'elapsed_ms': (time.perf_counter()-started)*1000,
            'stage_at_stop': stage_at_stop(events), 'events': events,
            'retry_count': 0, 'tls_verified': True, 'trust_env': False,
            'redirects': False, 'body_and_headers_saved': False, **result}


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    before = ledger_snapshot()
    if json.loads(MATRIX.read_text(encoding='utf-8'))['api_access_policy']['inference_authorized'] is not False:
        raise PermissionError('Diagnosis requires disarmed inference.')
    # One immutable invocation claim: no unattended loop or repeated diagnosis.
    with (output/'diagnosis-claim.json').open('x', encoding='utf-8') as handle:
        json.dump({'created_utc': datetime.now(timezone.utc).isoformat(),
                   'max_model_gets': 4, 'max_inference_calls': 0, 'budget_before': before}, handle, indent=2)
    presence = {k: bool(os.environ.get(k)) for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
               'NO_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'OPENAI_BASE_URL')}
    credentials()
    report = {'python': platform.python_version(), 'python_executable': sys.executable,
              'platform': platform.system(), 'tls': ssl.OPENSSL_VERSION,
              'packages': {p: importlib.metadata.version(p) for p in ('httpx', 'httpcore', 'anyio', 'certifi')},
              'environment_presence_only': presence, 'proxy_policy': 'trust_env=False, direct HTTPS',
              'permission_profile': 'danger-full-access with network enabled; no explicit sandbox rejection observed',
              'inference_calls': 0, 'image_uploads': 0, 'rows': [], 'budget_before': before}
    for provider in ENDPOINTS:
        for kind in ('project', 'independent'):
            row = compare(provider, kind); report['rows'].append(row)
            save(output/'diagnosis.json', report)
            print(json.dumps({k: row.get(k) for k in ('provider', 'client', 'elapsed_ms',
                             'stage_at_stop', 'result', 'exceptions')}), flush=True)
    report['budget_after'] = ledger_snapshot()
    report['ledger_unchanged'] = report['budget_after'] == before
    report['runtime_disarmed_after'] = json.loads(MATRIX.read_text(encoding='utf-8'))['api_access_policy']['inference_authorized'] is False
    report['all_access_verified'] = all(r.get('result', {}).get('model_access_verified') for r in report['rows'])
    save(output/'diagnosis.json', report)
    if not report['ledger_unchanged'] or not report['runtime_disarmed_after']:
        raise PermissionError('Unexpected accounting/runtime change during read-only diagnosis.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
