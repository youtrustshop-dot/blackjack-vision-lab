"""Separate ten-second observation collector. Every result is diagnostic-only.

Reuses the frozen wire builder and strict policy, not its three-second read path.
No app, solver, evidence producer or advisor is imported/returned. Exactly one
post is delegated; the existing transport owns canonical authorization/claim.
"""
from hashlib import sha256
from threading import Lock
import time

from .paired_deadline_reader import CaptureDeadlineReader
from .openai_reader import ProviderHTTPError
from .rejected_output_diagnostics import _OutputTap, inspect_output

VERSION = 'offline-response-collector-v1'
DIAGNOSTIC_NS = 10_000_000_000
LIVE_BOUNDARY_MS = 3000


class OfflineResponseCollector:
    def __init__(self, reader, store, scope):
        if not isinstance(reader, CaptureDeadlineReader):
            raise TypeError('Frozen payload/config builder required.')
        self.reader, self.store, self.scope = reader, store, scope
        self._lock = Lock(); self._consumed = False

    def collect(self, frame):
        with self._lock:
            if self._consumed:
                raise PermissionError('One-shot diagnostic consumed; no retry.')
            self.scope.verify(self.reader, frame)
            self._consumed = True
        began = time.monotonic_ns(); deadline = began+DIAGNOSTIC_NS
        tap = _OutputTap(self.reader.transport)
        status = 'error'; issue = None; usage = None; cost = None; response = None; settled = False
        spans = []; post_offset = None
        def measured(name, function):
            start = time.monotonic_ns()
            try:
                return function()
            finally:
                spans.append({'stage': name, 'start_ms': (start-began)/1e6,
                    'end_ms': (time.monotonic_ns()-began)/1e6})
        public, private = {'category': None, 'eligible_for_live': False}, {}
        try:
            payload = measured('frozen_payload', lambda: self.reader.payload(frame))
            if time.monotonic_ns() >= deadline:
                raise TimeoutError('Diagnostic deadline expired before reservation.')
            reservation = measured('reservation', lambda: self.reader.budget.reserve(self.reader.config.reserve_usd))
            post_offset = (time.monotonic_ns()-began)/1e6
            response = measured('post', lambda: tap.post(payload, deadline_ns=deadline, reservation_id=reservation))
            def audit():
                nonlocal usage, cost, settled
                raw = response.get('usage') or {}
                inputs, outputs = raw.get('input_tokens'), raw.get('output_tokens')
                model = response.get('model', '')
                if not (type(inputs) is int and type(outputs) is int and
                        0 <= inputs <= self.reader.config.context_token_limit and
                        0 <= outputs <= self.reader.config.max_output_tokens and isinstance(model, str) and
                        (model == self.reader.config.model or model.startswith(self.reader.config.model+'-'))):
                    raise ValueError('Unverified usage/model; retain reservation.')
                usage = {'input_tokens': inputs, 'output_tokens': outputs}
                cost = self.reader.config.cost(inputs, outputs, upper=True, service_tier=response.get('service_tier'))
                if cost > self.reader.config.reserve_usd:
                    self.reader.budget.stop(); raise ValueError('Cost exceeds reservation.')
                self.reader.budget.settle(reservation, cost)
                settled = True
            measured('usage_audit_and_settlement', audit)
            if tap.text is not None:
                public, private = measured('unchanged_contract_normalization_r1', lambda: inspect_output(
                    tap.text, available_views={name for name, _ in frame.images()}))
            status = 'completed' if response.get('status') == 'completed' else 'incomplete'
            if time.monotonic_ns() >= deadline:
                status = 'timeout'
        except Exception as exc:
            issue = type(exc).__name__
            status = ('timeout' if isinstance(exc, TimeoutError) or 'timeout' in issue.lower() else
                'blocked' if isinstance(exc, PermissionError) else 'error')
            if isinstance(exc, ProviderHTTPError):
                issue = 'provider_http_rejection'
            if tap.text is not None:
                public, private = measured('unchanged_contract_normalization_r1', lambda: inspect_output(
                    tap.text, available_views={name for name, _ in frame.images()}))
        finished = time.monotonic_ns(); total_ms = (finished-began)/1e6
        network = dict(tap.timings)
        complete_body = network.get('body_complete_ms') is not None
        result = {'collector_version': VERSION, 'status': status, 'error_type': issue,
            'content_diagnosis': public, 'usage': usage,
            'reported_usage_upper_usd': str(cost) if settled else None, 'usage_settled': settled,
            'reserved_usd': str(self.reader.config.reserve_usd),
            'total_through_validation_ms': total_ms, 'stage_spans': spans,
            'request_post_start_ms': post_offset, 'transport': network,
            'http_complete_body_received': complete_body, 'complete_observation_received': tap.text is not None,
            'no_complete_response_within_10s': status == 'timeout' and not complete_body,
            'within_unchanged_live_boundary': status == 'completed' and total_ms < LIVE_BOUNDARY_MS,
            'eligible_for_live': False, 'advisor_connected': False, 'advice': None,
            'retry_count': 0, 'output_shape': tap.shape,
            'output_sha256': sha256(tap.text.encode()).hexdigest() if tap.text is not None else None,
            'output_bytes': len(tap.text.encode()) if tap.text is not None else None,
            'retention': {'retained': False, 'reason': 'no_complete_observation_received'},
            'stop_before_next_request': status in ('blocked', 'error') or
                (response is not None and usage is None),
            'clock_scope': 'diagnostic collect start through accounting and unchanged validation; storage separate'}
        after_collect = time.monotonic_ns()
        try:
            if tap.text is not None:
                result['retention'] = self.store.write({'output_text': tap.text,
                    'provenance': {'experiment': self.scope.experiment, 'case': self.scope.case,
                        'provider': self.scope.provider, 'requested_model': self.scope.model,
                        'contract': public.get('contract'), 'semantic_policy': public.get('semantic_policy'),
                        'payload_sha256': self.scope.payload_sha256, 'image_sha256': list(self.scope.image_sha256),
                        'owned_synthetic': True, 'diagnostic_only': True, 'collector_version': VERSION,
                        'timing': {'complete_ms': total_ms, 'stages': spans, 'transport': network},
                        'usage': usage, 'reported_usage_upper_usd': result['reported_usage_upper_usd']},
                    'diagnosis': {'public': public, 'private': private}})
        except Exception as exc:
            result['retention'] = {'retained': False, 'reason': 'protected_storage_failed', 'error_type': type(exc).__name__}
            result['stop_before_next_request'] = True
        finally:
            tap.text = None
            self.reader.transport.close()
        result['protected_storage_ms'] = (time.monotonic_ns()-after_collect)/1e6
        result['pool_closed'] = True
        return result
