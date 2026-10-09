"""Conservative current-pixel revalidation for the controlled hybrid experiment.

No round IDs, oracle phase, previous rank identity or future simulator state.
Capture continues in a producer thread while local/cloud reading is in flight.
Native advisor expiry is not modified by this research-only module.
"""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from threading import Lock
import time

from .grounded_state import GroundedResult, adapt_legacy, grounded_gate


@dataclass(frozen=True)
class EvidenceStamp:
    source: str
    table: str
    source_epoch: int
    motion_epoch: int
    sequence: int
    frame_id: str
    capture_ns: int
    fingerprint: str


def frame_fingerprint(frame):
    """Bind every named image and its geometry, not just the table context.

    This proves packet identity, not that separately supplied crops came from
    the table. Producers must derive native details from the same acquisition.
    Frame IDs and capture clocks are intentionally not a freshness renewal.
    """
    packet = {'version': 'all-native-views-v1',
        'images': [(name, sha256(pixels).hexdigest()) for name, pixels in frame.images()],
        'layout': frame.layout, 'source_size': frame.source_size, 'table_box': frame.table_box}
    return sha256(json.dumps(packet, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode()).hexdigest()


class CurrentEvidence:
    def __init__(self, *, max_gap_ms=250, max_age_ms=3000):
        if not 0 < max_gap_ms <= 250 or not 0 < max_age_ms <= 3000:
            raise ValueError('Bounded declared continuity/decision budgets are required.')
        self.max_gap_ms, self.max_age_ms = max_gap_ms, max_age_ms
        self.lock = Lock(); self.current = None; self.frame = None
        self.source_epoch = self.motion_epoch = self.sequence = 0

    def capture(self, frame, *, source, table, capture_ns=None):
        now = time.monotonic_ns() if capture_ns is None else capture_ns
        # Every image the reader can see, with names and geometry. Conservative:
        # even unrelated visual change invalidates the request.
        fingerprint = frame_fingerprint(frame)
        with self.lock:
            old = self.current
            if old and now <= old.capture_ns:
                raise ValueError('Capture timestamps must increase monotonically.')
            if old and (source != old.source or table != old.table):
                self.source_epoch += 1; self.motion_epoch += 1
            elif old and (fingerprint != old.fingerprint or (now-old.capture_ns)/1e6 > self.max_gap_ms):
                self.motion_epoch += 1
            self.sequence += 1
            self.current = EvidenceStamp(source, table, self.source_epoch, self.motion_epoch,
                self.sequence, frame.frame_id, now, fingerprint)
            self.frame = frame
            return self.current

    def disconnect(self):
        with self.lock:
            self.source_epoch += 1; self.motion_epoch += 1; self.current = None; self.frame = None

    def snapshot(self):
        with self.lock:
            return self.current, self.frame

    def revalidate(self, request, *, now_ns=None):
        now = time.monotonic_ns() if now_ns is None else now_ns
        with self.lock:
            latest = self.current
            reasons = []
            if latest is None: reasons.append('source_disconnected')
            else:
                # FrameInput is frozen, but its layout dictionary is not. Never
                # trust a stamp after a caller changes that captured packet.
                try:
                    intact = self.frame is not None and frame_fingerprint(self.frame) == latest.fingerprint
                except (TypeError, ValueError):
                    intact = False
                if not intact:
                    reasons.append('captured_packet_mutated')
                if (request.source, request.table, request.source_epoch) != (latest.source, latest.table, latest.source_epoch):
                    reasons.append('source_or_table_changed')
                if request.motion_epoch != latest.motion_epoch or request.fingerprint != latest.fingerprint:
                    reasons.append('pixels_or_continuity_changed')
                if not 0 <= (now-latest.capture_ns)/1e6 <= self.max_gap_ms:
                    reasons.append('latest_capture_stale')
            age = (now-request.capture_ns)/1e6
            if not 0 <= age <= self.max_age_ms: reasons.append('original_evidence_deadline_expired')
            return {'valid': not reasons, 'reasons': reasons, 'capture_to_presentation_ms': age,
                'original_capture_ns': request.capture_ns, 'latest_capture_ns': latest.capture_ns if latest else None,
                'latest_sequence': latest.sequence if latest else None,
                'requested_motion_epoch': request.motion_epoch, 'latest_motion_epoch': latest.motion_epoch if latest else None,
                'fingerprint_scope': 'all_named_native_views_and_geometry',
                'mode': 'controlled-current-pixel-revalidation', 'r2_certified': False}


class FrozenGroundedLocal:
    def __init__(self, legacy):
        self.legacy = legacy; self.name = legacy.name+'-v2'

    def read(self, frame):
        result = self.legacy.read(frame)
        return GroundedResult(result.frame_id, self.name, result.status,
            adapt_legacy(result.observation) if result.observation else None,
            result.elapsed_ms, {**result.diagnostics, 'numeric_provenance_support': False})


def hybrid_attempt(evidence, local, cloud):
    """One deterministic local-first request. Producer capture must run separately.

    Presentation means emitting a validated headless advisor payload. Physical
    desktop capture/native-window paint latency is deliberately not claimed.
    """
    stamp, frame = evidence.snapshot()
    if stamp is None:
        return {'route': 'none', 'presented': False, 'reason': 'no_current_capture'}
    began = time.monotonic_ns()
    try:
        result = local.read(frame)
        local_gate = grounded_gate(result.observation) if result.observation else {'usable': False, 'reasons': [result.status]}
    except Exception as exc:
        result = GroundedResult(frame.frame_id, local.name, 'error', None, (time.monotonic_ns()-began)/1e6,
            {'error_type': type(exc).__name__})
        local_gate = {'usable': False, 'reasons': ['local_error']}
    local_completed_ns = time.monotonic_ns()
    route, requested_ns, cloud_completed_ns = 'local', None, None
    if not local_gate['usable']:
        if not evidence.revalidate(stamp)['valid']:
            return {'route': 'none', 'presented': False, 'reason': 'local_frame_already_expired',
                'local_gate': local_gate, 'local_elapsed_ms': (local_completed_ns-began)/1e6}
        route = 'fallback'; requested_ns = time.monotonic_ns()
        result = cloud.read(frame); cloud_completed_ns = time.monotonic_ns()
    gate = grounded_gate(result.observation) if result.observation else {'usable': False, 'reasons': [result.status]}
    validation = evidence.revalidate(stamp)
    advice = None
    if gate['usable'] and validation['valid']:
        from .advice import recommend
        from .engine import Rules
        player = [c.rank for c in result.observation.cards if c.zone == 'player:0']
        dealer = next(c.rank for c in result.observation.cards if c.zone == 'dealer' and c.rank)
        advice = recommend(player, dealer, Rules(), allowed=result.observation.controls, count_complete=False)
    # Serialization is the headless presentation boundary, after math + recheck.
    presentation_ns = time.monotonic_ns()
    validation = evidence.revalidate(stamp, now_ns=presentation_ns)
    presented = bool(advice and validation['valid'])
    return {'route': route, 'reader': result.reader, 'status': result.status, 'presented': presented,
        'local_gate': local_gate, 'gate': gate, 'revalidation': validation,
        'observation': result.observation.model_dump() if result.observation else None,
        'advice': advice if presented else None, 'diagnostics': result.diagnostics,
        'timing': {'capture_ns': stamp.capture_ns, 'local_start_ns': began,
            'local_completed_ns': local_completed_ns, 'cloud_request_ns': requested_ns,
            'cloud_completed_ns': cloud_completed_ns, 'presentation_ns': presentation_ns,
            'local_ms': (local_completed_ns-began)/1e6,
            'cloud_ms': (cloud_completed_ns-requested_ns)/1e6 if requested_ns else None,
            'capture_to_headless_presentation_ms': (presentation_ns-stamp.capture_ns)/1e6},
        'original_evidence': asdict(stamp), 'scope': 'controlled simulator, headless advisor payload; no physical native paint proof',
        'r1_rules_conditional': True, 'r2_certified': False}
