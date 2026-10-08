"""Opt-in owned-layout R1 integration, using the existing readers and solver.

Acquisition and inference are independent. One authoritative session serves
both the main page and compact advisor. Evaluator truth is never accepted here.
The source is a browser canvas, not certified Windows desktop capture or R2.
"""
from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
import copy
import math
import secrets
from threading import Lock
import time

from PIL import Image

from .hybrid_evidence import CurrentEvidence, EvidenceStamp
from .paired_deadline_reader import local_first_attempt
from .state_reader import prepare_frame

PROFILE = 'owned-canvas-r1-v1'
MAX_BYTES = 2_000_000
MAX_PIXELS = 1_000_000


def pixel_digest(image):
    return sha256(image.convert('RGB').tobytes()).hexdigest()


class NoCloud:
    name = 'cloud-disabled'

    def read(self, frame, *, capture_ns):
        from .grounded_state import GroundedResult
        return GroundedResult(frame.frame_id, self.name, 'blocked', None, 0,
                              {'reason': 'No inference is authorized for this session.'})


class IntegratedR1Session:
    """Independent bounded pixel ingestion; no annotation/phase/manual-turn API."""
    def __init__(self, local, *, layout, approved_pixels, cloud=None, clock=time.monotonic_ns):
        self.id = secrets.token_urlsafe(18)
        self.source = 'owned-canvas-' + self.id
        self.table = 'Declared owned table'
        self.local, self.cloud = local, cloud or NoCloud()
        self.layout = copy.deepcopy(layout)
        self.approved_pixels = frozenset(approved_pixels)
        if not self.approved_pixels:
            raise ValueError('An explicit owned pixel allowlist is required.')
        self.clock = clock
        self.evidence = CurrentEvidence()
        self.lock, self.inference_lock = Lock(), Lock()
        self.sequence = -1
        self.closed = False
        self.attempt = None
        self.analysis_count = 0
        self.capture_count = 0
        self.captures = []
        self.attempts = []
        self.displays = []

    def display(self, *, evidence_capture_ns, capture_to_dom_ms, action, boundary):
        """Audit a client DOM boundary against the original authoritative state.

        A client duration is reported separately from the server clock. It is
        never permission to renew evidence or proof of physical monitor paint.
        """
        if (type(evidence_capture_ns) is not int or
                type(capture_to_dom_ms) not in (int, float) or
                not math.isfinite(capture_to_dom_ms) or not 0 <= capture_to_dom_ms <= 10_000 or
                boundary != 'browser-dom-two-raf'):
            raise ValueError('A bounded original-capture DOM receipt is required.')
        with self.lock:
            attempt = self.attempt or {}
            original = attempt.get('original_evidence')
            if not original or original['capture_ns'] != evidence_capture_ns:
                raise ValueError('DOM receipt is not bound to the completed observation.')
            expected = (attempt.get('advice') or {}).get('best_action')
            if not expected or action != expected:
                raise ValueError('DOM action differs from the authoritative advice.')
            validity = self.evidence.revalidate(EvidenceStamp(**original), now_ns=self.clock())
            # Even a client claiming a short duration cannot certify a stale
            # server state. Keep rejected receipts for the timing audit.
            eligible = bool(attempt.get('presented') and validity['valid'] and capture_to_dom_ms < 3000)
            row = {'evidence_capture_ns': evidence_capture_ns, 'action': action,
                   'capture_to_dom_ms': capture_to_dom_ms, 'boundary': boundary,
                   'eligible_at_receipt': eligible, 'revalidation': validity,
                   'physical_scanout_measured': False}
            if any(r['evidence_capture_ns'] == evidence_capture_ns for r in self.displays):
                raise ValueError('This original DOM boundary was already recorded.')
            self.displays.append(row)
            self.displays = self.displays[-128:]
            return copy.deepcopy(row)

    def capture(self, content, *, sequence, capture_age_ms=0):
        if type(sequence) is not int or sequence < 0:
            raise ValueError('Nonnegative sequence required.')
        if type(capture_age_ms) not in (int, float) or not 0 <= capture_age_ms <= 1000:
            raise ValueError('Bounded measured acquisition age required.')
        if not 0 < len(content) <= MAX_BYTES:
            raise ValueError('Owned capture exceeds its byte budget.')
        with Image.open(BytesIO(content)) as opened:
            if opened.width * opened.height > MAX_PIXELS:
                raise ValueError('Owned capture exceeds its pixel budget.')
            image = opened.convert('RGB')
        digest = pixel_digest(image)
        if digest not in self.approved_pixels:
            raise PermissionError('Capture is outside the frozen owned pixel corpus.')
        frame = prepare_frame(image, self.layout)
        # The cloud profile is the preserved table-only available-view request.
        from dataclasses import replace
        frame = replace(frame, details=())
        now = self.clock()
        with self.lock:
            if self.closed:
                raise ValueError('Source is closed.')
            if sequence <= self.sequence:
                raise ValueError('Out-of-order capture must not renew evidence.')
            stamp = self.evidence.capture(frame, source=self.source, table=self.table,
                                          capture_ns=now-int(capture_age_ms*1_000_000))
            self.sequence = sequence
            self.capture_count += 1
            self.captures.append({'sequence': sequence, 'capture_ns': stamp.capture_ns,
                                  'received_ns': now, 'pixel_sha256': digest,
                                  'source_epoch': stamp.source_epoch, 'motion_epoch': stamp.motion_epoch})
            self.captures = self.captures[-2048:]
        return {'sequence': sequence, 'frame_id': frame.frame_id,
                'capture_count': self.capture_count, 'received_ns': now,
                'capture_ns': stamp.capture_ns, 'source_id': self.source}

    def analyze(self):
        if not self.inference_lock.acquire(blocking=False):
            raise ValueError('An observation is already in flight.')
        try:
            with self.lock:
                if self.closed:
                    raise ValueError('Source is closed.')
                self.analysis_count += 1
            value = local_first_attempt(self.evidence, self.local, self.cloud)
            with self.lock:
                self.attempt = value
                self.attempts.append(copy.deepcopy(value))
                self.attempts = self.attempts[-128:]
            return self.snapshot()
        finally:
            self.inference_lock.release()

    def disconnect(self):
        # A late response cannot reestablish this source. A new session is explicit.
        with self.lock:
            self.closed = True
            self.evidence.disconnect()

    def snapshot(self):
        with self.lock:
            attempt = copy.deepcopy(self.attempt)
            counts = {'capture_count': self.capture_count, 'analysis_count': self.analysis_count,
                      'cloud_pending': bool(getattr(self.cloud, 'pending', False)),
                      'inflight': self.inference_lock.locked(), 'closed': self.closed}
        now = self.clock()
        original = (attempt or {}).get('original_evidence')
        validity = (self.evidence.revalidate(EvidenceStamp(**original), now_ns=now)
                    if original else {'valid': False, 'reasons': ['No completed current observation.']})
        observation = (attempt or {}).get('observation') or {}
        cards = observation.get('cards', [])
        player = [c['rank'] for c in cards if c['zone'] == 'player:0' and c['rank']]
        dealer = [c['rank'] for c in cards if c['zone'] == 'dealer' and c['rank']]
        actionable = bool(attempt and attempt.get('presented') and validity['valid'])
        observed_current = bool(original and validity['valid'])
        gate = (attempt or {}).get('gate') or {}
        reasons = gate.get('reasons') or [(attempt or {}).get('reason') or 'Waiting for a readable hand.']
        if not validity['valid']:
            reasons = validity['reasons']
        report = {'source_id': self.source,
                  'state_id': self.source + ':' + (original['frame_id'] if original else 'none'),
                  'player': player if observed_current else [], 'dealer': dealer if observed_current else [],
                  'phase': observation.get('phase', 'unknown') if observed_current else 'unknown',
                  'gate': {'solver_allowed': actionable, 'reasons': reasons},
                  'advice': attempt.get('advice') if actionable else None,
                  'count_reliable': False, 'true_count': None, 'r2_certified': False}
        remaining = max(0, 3000-(now-original['capture_ns'])/1e6) if observed_current else 0
        return {'report': report, 'source_id': self.source, 'session_id': self.id,
                'stale': not observed_current, 'evidence_ttl_ms': remaining,
                'evidence_capture_ns': original['capture_ns'] if original else None,
                'evidence_age_ms': (now-original['capture_ns'])/1e6 if original else None,
                'profile': PROFILE, 'counts': counts,
                'route': (attempt or {}).get('route'),
                'timing': (attempt or {}).get('timing'),
                'revalidation': validity,
                'scope': 'Owned browser canvas to local backend and compact view; R2 unverified.'}

    def receipt(self):
        with self.lock:
            return {'profile': PROFILE, 'session_id': self.id, 'source_id': self.source,
                    'captures': copy.deepcopy(self.captures), 'attempts': copy.deepcopy(self.attempts),
                    'displays': copy.deepcopy(self.displays),
                    'capture_count': self.capture_count, 'analysis_count': self.analysis_count,
                    'closed': self.closed, 'r2_certified': False}
