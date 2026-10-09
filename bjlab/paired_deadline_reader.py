"""Opt-in compact observation and local-first R1 under one capture deadline.

The frozen wire/prompt, local models, default gate and advice engine are reused.
An oracle is never supplied here. Evaluators operate after the path has finished.
Presentation means headless JSON serialization, not native Windows paint.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import time

from pydantic import ValidationError

from .advice import recommend
from .engine import Rules
from .grounded_state import GroundedResult
from .live_cloud import DiagnosticReader
from .live_state import LiveObservation
from .numeric_provenance import semantic_gate
from .openai_reader import ProviderHTTPError
from .paired_persistent_http import ensure_deadline

DEADLINE_NS = 3_000_000_000


class CaptureDeadlineReader:
    def __init__(self, config, budget, hashes, *, provider, transport, name):
        self.config, self.budget, self.transport, self.name = config, budget, transport, name
        self.payload_reader = DiagnosticReader(config, budget, hashes, provider=provider,
            variant='live', transport=transport,
            gemini_output='structured-card-limit-local' if provider == 'gemini' else 'structured')

    def payload(self, frame):
        return self.payload_reader.payload(frame)

    def read(self, frame, *, capture_ns):
        deadline = capture_ns+DEADLINE_NS; began = time.monotonic_ns()
        diagnostics = {'retry_count': 0, 'provider': self.payload_reader.provider,
            'latency_scope': 'original capture through budget receipt and semantic gate',
            'timing': {}, 'stage_spans': [], 'original_capture_ns': capture_ns,
            'deadline_ns': deadline, 'raw_body_saved': False}
        observation = None; status = 'error'; clock = diagnostics['timing']
        def measured(name, fn):
            start = time.monotonic_ns()
            try:
                return fn()
            finally:
                stop = time.monotonic_ns(); clock[name+'_ms'] = (stop-start)/1e6
                diagnostics['stage_spans'].append({'stage': name,
                    'start_after_capture_ms': (start-capture_ns)/1e6, 'end_after_capture_ms': (stop-capture_ns)/1e6})
        try:
            ensure_deadline(deadline)
            payload = measured('payload', lambda: self.payload(frame))
            ensure_deadline(deadline)
            reservation = measured('reservation', lambda: self.budget.reserve(self.config.reserve_usd))
            ensure_deadline(deadline)
            response = measured('post_and_claim', lambda: self.transport.post(
                payload, deadline_ns=deadline, reservation_id=reservation))
            diagnostics.update(usage=response.get('usage'), provider_usage=response.get('provider_usage'),
                model_returned=response.get('model'), service_tier_returned=response.get('service_tier'))
            # Accounting is mandatory even if the reply becomes late during
            # audit/settlement; it never makes a late state usable again.
            def audit():
                usage = response.get('usage') or {}; inputs, outputs = usage.get('input_tokens'), usage.get('output_tokens')
                returned = response.get('model', '')
                if not (type(inputs) is int and type(outputs) is int and 0 <= inputs <= self.config.context_token_limit and
                        0 <= outputs <= self.config.max_output_tokens and isinstance(returned, str) and
                        (returned == self.config.model or returned.startswith(self.config.model+'-'))):
                    diagnostics['unreconciled_usage'] = True
                    raise ValueError('Unverified model or usage; retain reservation.')
                upper = self.config.cost(inputs, outputs, upper=True, service_tier=response.get('service_tier'))
                if upper > self.config.reserve_usd:
                    self.budget.stop(); raise ValueError('Returned charge exceeds audited reservation.')
                diagnostics['price_based_upper_cost_usd'] = str(upper)
                return upper
            upper = measured('usage_audit', audit)
            measured('settlement', lambda: self.budget.settle(reservation, upper))
            ensure_deadline(deadline)
            def parse():
                if any(item.get('type') not in ('message', 'reasoning') for item in response.get('output', [])):
                    raise ValueError('Unexpected tool output.')
                blocks = [p for item in response.get('output', []) if item.get('type') == 'message' for p in item.get('content', [])]
                if any(p.get('type') == 'refusal' for p in blocks):
                    return None, 'refused'
                if response.get('status') != 'completed':
                    return None, 'incomplete'
                texts = [p['text'] for p in blocks if p.get('type') == 'output_text']
                if len(texts) != 1:
                    raise ValueError('Exactly one complete JSON output required.')
                diagnostics['output_json_sha256'] = sha256(texts[0].encode()).hexdigest()
                diagnostics['output_json_bytes'] = len(texts[0].encode())
                return LiveObservation.model_validate_json(texts[0]), 'completed'
            observation, status = measured('strict_parse', parse)
            ensure_deadline(deadline)
            if observation is not None:
                diagnostics['semantic_gate'] = measured('semantic_gate', lambda: semantic_gate(
                    observation, available_views={n for n, _ in frame.images()}))
            ensure_deadline(deadline)
        except Exception as exc:
            observation = None
            status = 'blocked' if isinstance(exc, PermissionError) else 'timeout' if isinstance(exc, TimeoutError) or 'timeout' in type(exc).__name__.lower() else 'error'
            diagnostics['error_type'] = type(exc).__name__
            if isinstance(exc, ProviderHTTPError):
                diagnostics['http_status'] = exc.status_code
            if isinstance(exc, ValidationError):
                diagnostics['validation_issues'] = [{'location': e['loc'], 'type': e['type']}
                    for e in exc.errors(include_input=False, include_context=False, include_url=False)]
        diagnostics['transport'] = dict(self.transport.timings)
        diagnostics['budget'] = measured('receipt', self.budget.receipt)
        finished = time.monotonic_ns()
        if finished >= deadline:
            observation = None; status = 'timeout'; diagnostics['late_state_discarded'] = True
        diagnostics['cloud_path_ms'] = (finished-began)/1e6
        return GroundedResult(frame.frame_id, self.name, status, observation, (finished-capture_ns)/1e6, diagnostics)


def local_first_attempt(evidence, local, cloud, *, rules=None):
    """No oracle argument, no forced fallback, no renewal after local reading."""
    stamp, frame = evidence.snapshot()
    if stamp is None:
        return {'route': 'none', 'presented': False, 'reason': 'no_current_capture'}
    deadline = stamp.capture_ns+DEADLINE_NS; timing = {}; route = 'local'
    result = None; advice = None; gate = None; local_gate = None; reason = None
    def measured(name, fn):
        start = time.monotonic_ns()
        try:
            return fn()
        finally:
            timing[name+'_ms'] = (time.monotonic_ns()-start)/1e6
    try:
        ensure_deadline(deadline)
        result = measured('local', lambda: local.read(frame))
        # Frozen legacy local adapter cannot supply v3 labels. Its rank/phase
        # blockers are retained; never fabricate semantic numeric provenance.
        from .grounded_state import grounded_gate
        local_gate = measured('routing', lambda: grounded_gate(result.observation)
            if result.observation else {'usable': False, 'reasons': [result.status]})
        ensure_deadline(deadline)
        current = measured('pre_route_revalidation', lambda: evidence.revalidate(stamp))
        if not current['valid']:
            reason = 'local_frame_not_current'
        elif not local_gate['usable']:
            route = 'fallback'
            result = measured('cloud', lambda: cloud.read(frame, capture_ns=stamp.capture_ns))
        if reason is None:
            ensure_deadline(deadline)
            gate = measured('final_gate', lambda: (semantic_gate(result.observation,
                available_views={n for n, _ in frame.images()}) if route == 'fallback' else grounded_gate(result.observation))
                if result.observation else {'usable': False, 'reasons': [result.status]})
            current = measured('pre_solver_revalidation', lambda: evidence.revalidate(stamp))
            if gate['usable'] and current['valid']:
                player = [c.rank for c in result.observation.cards if c.zone == 'player:0']
                dealer = next(c.rank for c in result.observation.cards if c.zone == 'dealer' and c.rank)
                advice = measured('solver', lambda: recommend(player, dealer, rules or Rules(),
                    allowed=result.observation.controls, count_complete=False))
            else:
                reason = 'gate_or_current_evidence_rejected'
    except Exception as exc:
        reason = 'absolute_deadline_expired' if isinstance(exc, TimeoutError) else type(exc).__name__
    validation = measured('pre_serialize_revalidation', lambda: evidence.revalidate(stamp))
    payload = {'source': stamp.source, 'table': stamp.table, 'evidence_capture_ns': stamp.capture_ns,
        'action': advice['best_action'] if advice and validation['valid'] else None,
        'observation': result.observation.model_dump() if result and result.observation else None,
        'valid_until_ns': deadline, 'r2_certified': False}
    serialized = measured('serialization', lambda: json.dumps(payload, separators=(',', ':'), allow_nan=False).encode())
    # Check AGAIN after serialization, at the actual headless output boundary.
    validation = measured('post_serialize_revalidation', lambda: evidence.revalidate(stamp))
    finished = time.monotonic_ns()
    presented = bool(payload['action'] and validation['valid'] and finished < deadline and reason is None)
    if not presented:
        advice = None
    return {'route': route, 'reader': result.reader if result else None,
        'status': result.status if result else 'error', 'presented': presented, 'reason': reason,
        'local_gate': local_gate, 'gate': gate, 'revalidation': validation,
        'observation': result.observation.model_dump() if result and result.observation else None,
        'advice': advice, 'diagnostics': result.diagnostics if result else {},
        'serialized_bytes': len(serialized), 'advisor_payload': payload if presented else None,
        'original_evidence': asdict(stamp), 'timing': {**timing, 'capture_ns': stamp.capture_ns,
            'presentation_ns': finished, 'capture_to_headless_presentation_ms': (finished-stamp.capture_ns)/1e6},
        'scope': 'owned pixel producer to current headless advisor JSON; no Windows capture/paint/session proof'}
