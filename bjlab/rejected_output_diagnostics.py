"""Opt-in offline failure diagnosis around the unchanged three-second reader.

The transport tap retains ONLY output_text in memory before strict validation.
After the frozen reader has finished, selected text is encrypted outside the live
clock. This module never extends a deadline, creates advice or authorizes calls.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from threading import Lock
import time

from pydantic import ValidationError

from .live_state import CONTRACT_VERSION, LiveObservation
from .numeric_provenance import POLICY_VERSION, normalize_number, semantic_gate
from .paired_deadline_reader import CaptureDeadlineReader
from .paired_persistent_http import canonical_digest
from .private_observation_store import MAX_OUTPUT_BYTES

DIAGNOSTIC_VERSION = 'rejected-output-diagnostic-v1'
KNOWN_PATHS = frozenset(('c', 'cards', 'z', 'zone', 'r', 'rank', 's', 'suit', 'v',
    'visibility', 't', 'table_state', 'p', 'phase', 'a', 'controls', 'n', 'numbers',
    'value', 'role', 'l', 'label', 'w', 'view', 'b', 'blockers'))
INVARIANT_RULES = {
    'Value error, Explicit associated PLAYER/DEALER TOTAL label required.': 'explicit_total_label_required',
    'Value error, Covered/unreadable objects disclose no face information.': 'hidden_face_information',
    'Value error, Readable faces require a rank.': 'readable_rank_required',
    'Value error, Partial means some face information is legible.': 'partial_face_information_required',
    'Value error, Card presence and table state disagree.': 'table_presence_conflict',
    'Value error, Duplicate control/blocker.': 'duplicate_control_or_blocker',
}
R1_RULES = {
    'Table presence is not established.': 'table_presence_unknown',
    'Need at least two readable player cards.': 'player_cards_missing',
    'Need exactly one readable dealer upcard.': 'dealer_upcard_missing',
    'Player hand has already busted.': 'player_busted',
    'Observed player total disagrees with the cards.': 'player_total_card_mismatch',
    'Observed dealer total disagrees with the upcard.': 'dealer_total_card_mismatch',
    'Player turn is not established.': 'player_turn_unknown',
    'No enabled player decision control is observed.': 'enabled_control_missing',
}


def _issue_records(error):
    private = error.errors(include_input=False, include_context=False, include_url=False)
    public = []
    for item in private:
        rule = INVARIANT_RULES.get(item['msg'])
        public.append({'location': [part if type(part) is int or part in KNOWN_PATHS else 'other_field'
            for part in item['loc']], 'type': item['type'] if re.fullmatch(r'[a-z_]+', item['type']) else 'validation_error',
            'rule': rule or 'strict_field_constraint'})
    return public, private


def inspect_output(text, *, available_views=('table', 'dealer', 'player:0', 'controls')):
    """Re-run the same contract/policy in isolation; never return an observation.

    Structural fields and pre-normalization invariants belong to the SAME strict
    Pydantic operation. Error types identify which failed; no bypass model exists.
    Raw text/normalized values occur only in private_details, never public_summary.
    """
    if not isinstance(text, str) or len(text.encode()) > MAX_OUTPUT_BYTES:
        raise ValueError('Bounded observation text required.')
    public = {'diagnostic_version': DIAGNOSTIC_VERSION, 'contract': CONTRACT_VERSION,
        'semantic_policy': POLICY_VERSION, 'category': None, 'stages': [], 'issues': [],
        'semantic_issue_codes': [], 'r1_issue_codes': [], 'eligible_for_live': False,
        'scope': 'offline contract inspection; not fresh model accuracy or advisor delivery'}
    private = {'normalized_numbers': [], 'strict_validation_issues': [], 'r1_reasons': []}
    def stage(name, outcome):
        public['stages'].append({'stage': name, 'outcome': outcome})
    try:
        # Informational syntax stage; acceptance still uses the original JSON API.
        json.loads(text)
    except (ValueError, RecursionError):
        stage('json_syntax', 'rejected'); public['category'] = 'json_format_rejection'
        return public, private
    stage('json_syntax', 'passed')
    try:
        observation = LiveObservation.model_validate_json(text)
    except ValidationError as error:
        public['issues'], private['strict_validation_issues'] = _issue_records(error)
        stage('strict_contract_fields_and_invariants', 'rejected')
        public['category'] = ('pre_normalization_invariant_rejection' if any(
            issue['rule'] in INVARIANT_RULES.values() for issue in public['issues']) else 'structural_validation_rejection')
        # Do not normalize, repair a label or call R1 after failed validation.
        return public, private
    stage('strict_contract_fields_and_invariants', 'passed')
    normalized = [normalize_number(n, available_views=available_views) for n in observation.numbers]
    private['normalized_numbers'] = [n.record() for n in normalized]
    public['semantic_issue_codes'] = sorted({issue for n in normalized for issue in n.issues})
    stage('number_semantic_normalization', 'rejected' if public['semantic_issue_codes'] else 'passed')
    # This exact shared gate includes the original arithmetic/phase/card checks.
    gate = semantic_gate(observation, available_views=available_views)
    private['r1_reasons'] = list(gate['reasons'])
    public['r1_issue_codes'] = sorted({R1_RULES.get(reason, 'other_r1_blocker') for reason in gate['reasons']
        if not reason.startswith('Numeric provenance [')})
    stage('shared_r1_gate', 'passed' if gate['usable'] else 'rejected')
    public['category'] = ('semantic_provenance_rejection' if public['semantic_issue_codes'] else
        'r1_integrity_rejection' if not gate['usable'] else 'valid_usable_content')
    return public, private


def delivery_category(*, status, elapsed_ms, content_category=None, evidence_current=True,
                      http_status=None, unreconciled_usage=False):
    """Delivery failures take precedence; inspecting text cannot revive a reply."""
    if not isinstance(elapsed_ms, (int, float)) or not math.isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError('A measured finite nonnegative elapsed time is required.')
    if status == 'timeout' or elapsed_ms >= 3000:
        return 'timeout'
    if not evidence_current:
        return 'stale_response'
    if http_status is not None and http_status != 200:
        return 'provider_http_rejection'
    if unreconciled_usage:
        return 'usage_audit_rejection'
    if status in ('blocked', 'refused', 'incomplete'):
        return status
    if status != 'completed' and content_category == 'valid_usable_content':
        return 'reader_error'
    if content_category:
        return content_category
    return 'missing_observation_output' if status == 'completed' else 'reader_error'


@dataclass(frozen=True)
class OwnedOutputScope:
    """Caller-reviewed synthetic-only scope; storage permission, never API scope."""
    experiment: str
    case: str
    provider: str
    model: str
    payload_sha256: str
    image_sha256: tuple[str, ...]
    owned_synthetic: bool

    def verify(self, reader, frame):
        if (self.owned_synthetic is not True or self.provider not in ('openai', 'gemini') or
                self.provider != reader.payload_reader.provider or self.model != reader.config.model or
                not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}', self.experiment) or
                not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}', self.case)):
            raise PermissionError('Explicit reviewed owned synthetic scope required.')
        actual = tuple(sha256(p).hexdigest() for _, p in frame.images())
        if actual != self.image_sha256 or canonical_digest(reader.payload(frame)) != self.payload_sha256:
            raise PermissionError('Output scope differs from reviewed pixels/payload.')


class _OutputTap:
    """No envelope/body/header persistence; no retry; one original post delegate."""
    def __init__(self, transport):
        self.transport = transport; self.text = None; self.shape = 'no_output_received'

    @property
    def timings(self):
        return self.transport.timings

    def post(self, payload, *, deadline_ns, reservation_id):
        response = self.transport.post(payload, deadline_ns=deadline_ns, reservation_id=reservation_id)
        try:
            # Never persist reasoning, thoughts, auth/error headers or full JSON.
            texts = [part['text'] for item in response.get('output', []) if item.get('type') == 'message'
                for part in item.get('content', []) if part.get('type') == 'output_text']
            if len(texts) == 1 and isinstance(texts[0], str) and len(texts[0].encode()) <= MAX_OUTPUT_BYTES:
                self.text = texts[0]; self.shape = 'one_bounded_output_text'
            else:
                self.shape = 'unsupported_output_shape'
        except (KeyError, TypeError, AttributeError, UnicodeError):
            self.shape = 'unsupported_output_shape'
        return response  # Identical object for the frozen reader/usage validator.


class RetainingStillDiagnostic:
    """Explicit future opt-in: unchanged deadline reader plus post-read storage.

    Not wired into the application or any paid controller. A passed output is
    never made current here; public results are diagnostic-only metadata.
    The original transport retains its canonical authorization/claim guards.
    """
    def __init__(self, reader, store, scope):
        if not isinstance(reader, CaptureDeadlineReader):
            raise TypeError('The unchanged capture-deadline reader is required.')
        self.original, self.store, self.scope = reader, store, scope
        self._consumed = False; self._lock = Lock()

    def run(self, frame, *, capture_ns, evidence_current=True):
        with self._lock:
            if self._consumed:
                raise PermissionError('One-shot diagnostic already consumed; no retry.')
            self.scope.verify(self.original, frame)
            self._consumed = True
        tap = _OutputTap(self.original.transport)
        reader = CaptureDeadlineReader(self.original.config, self.original.budget,
            self.original.payload_reader.hashes, provider=self.scope.provider, transport=tap, name=self.original.name)
        result = reader.read(frame, capture_ns=capture_ns)
        after_read = time.monotonic_ns()
        public, private = (inspect_output(tap.text, available_views={n for n, _ in frame.images()})
            if tap.text is not None else ({'category': None, 'eligible_for_live': False}, {}))
        category = delivery_category(status=result.status, elapsed_ms=result.elapsed_ms,
            content_category=public['category'], evidence_current=evidence_current,
            http_status=result.diagnostics.get('http_status'),
            unreconciled_usage=result.diagnostics.get('unreconciled_usage', False))
        receipt = {'diagnostic_version': DIAGNOSTIC_VERSION, 'reader_status': result.status,
            'reader_elapsed_ms': result.elapsed_ms, 'category': category, 'content_diagnosis': public,
            'output_shape': tap.shape, 'eligible_for_live': False, 'advice': None,
            'output_sha256': sha256(tap.text.encode()).hexdigest() if tap.text is not None else None,
            'output_bytes': len(tap.text.encode()) if tap.text is not None else None,
            'retention': {'retained': False, 'reason': 'no_bounded_output_received'},
            'retry_count': 0, 'clock_scope': 'original reader clock unchanged; diagnostic write follows it'}
        if tap.text is not None:
            provenance = {'experiment': self.scope.experiment, 'case': self.scope.case,
                'provider': self.scope.provider, 'requested_model': self.scope.model,
                'payload_sha256': self.scope.payload_sha256, 'image_sha256': list(self.scope.image_sha256),
                'contract': CONTRACT_VERSION, 'semantic_policy': POLICY_VERSION,
                'reader_status': result.status, 'reader_elapsed_ms': result.elapsed_ms,
                'output_sha256': sha256(tap.text.encode()).hexdigest(), 'evidence_current': evidence_current,
                'category': category, 'owned_synthetic': True}
            try:
                receipt['retention'] = self.store.write({'output_text': tap.text,
                    'provenance': provenance, 'diagnosis': {'public': public, 'private': private}})
            except Exception as error:
                # Storage failure never triggers another request or relaxes R1.
                receipt['retention'] = {'retained': False, 'reason': 'protected_storage_failed',
                                        'error_type': type(error).__name__}
        tap.text = None
        receipt['post_read_diagnostic_ms'] = (time.monotonic_ns()-after_read)/1e6
        return receipt  # No observation/advisor object is exposed by this API.
