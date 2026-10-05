"""Opt-in semantic R1 policy. Frozen live-v3 wire/reader/defaults stay unchanged.

Recognize a finite English label grammar, never delete arbitrary digits or
reassign a role/view. This checks declared provenance; pixel grounding still
requires independent evidence. Both application gate and new evaluator use it.
"""
from dataclasses import asdict, dataclass
import re
from typing import Iterable

from .live_state import LiveNumber, LiveObservation, live_gate

POLICY_VERSION = 'numeric-provenance-r1-v1'
VIEWS = frozenset(('table', 'dealer', 'player:0', 'controls'))
LABEL_RULES = {
    'DEALER TOTAL': ('dealer_total', frozenset(('table', 'dealer'))),
    'PLAYER TOTAL': ('player_total', frozenset(('table', 'player:0'))),
    'SESSION': ('ui', frozenset(('table',))),
}
# Only an optional, separated unsigned decimal value is permitted. Case and
# whitespace are canonicalized after retaining the original observed text.
LABEL_PATTERN = re.compile(
    r'(?P<label>DEALER TOTAL|PLAYER TOTAL|SESSION)(?:(?: +| *: *)(?P<number>[0-9]+))?'
)


@dataclass(frozen=True)
class NormalizedNumber:
    observed_text: str | None
    normalized_label: str | None
    value: int
    declared_role: str
    source_view: str
    status: str
    issues: tuple[str, ...]
    blocks_r1: bool

    def record(self):
        return asdict(self)


def normalize_number(number: LiveNumber | dict, *, available_views: Iterable[str] = VIEWS):
    """Do not invent labels for unknowns; malformed totals fail closed.

    available_views is capture metadata, not an oracle. An appropriate named
    view cannot prove that text exists at the claimed position within its pixels.
    """
    number = LiveNumber.model_validate(number)
    available = frozenset(available_views)
    if not available <= VIEWS:
        raise ValueError('Unknown native view in capture metadata.')
    text = ' '.join((number.label or '').upper().split())
    matched = LABEL_PATTERN.fullmatch(text)
    label = matched['label'] if matched else None
    issues = []
    if number.view not in available:
        issues.append('source_view_not_available')
    if matched:
        role, allowed = LABEL_RULES[label]
        if matched['number'] is not None and int(matched['number']) != number.value:
            issues.append('label_value_mismatch')
        if role != number.role:
            issues.append('label_role_mismatch')
        if number.view not in allowed:
            issues.append('label_source_view_mismatch')
    elif number.role in ('player_total', 'dealer_total'):
        issues.append('ambiguous_total_label')
    status = 'incoherent' if issues else 'normalized' if matched else 'ambiguous'
    return NormalizedNumber(number.label, label, number.value, number.role,
                            number.view, status, tuple(issues), bool(issues))


def semantic_gate(observation: LiveObservation | dict, *, available_views: Iterable[str] = VIEWS, **kwargs):
    """Application-side opt-in gate; no mutation of observations or old gates.

    UI/unknown numbers with unrecognized labels stay ambiguous. They are not
    converted to hand totals; missing/ambiguous UI transcription is measured
    separately. Existing card, total arithmetic, phase and turn checks remain.
    """
    observation = LiveObservation.model_validate(observation)
    available = frozenset(available_views)
    normalized = [normalize_number(n, available_views=available) for n in observation.numbers]
    gate = live_gate(observation, **kwargs)
    reasons = list(gate['reasons'])
    for index, number in enumerate(normalized):
        reasons.extend(f'Numeric provenance [{index}]: {issue}.' for issue in number.issues)
    return {**gate, 'usable': gate['usable'] and not any(n.blocks_r1 for n in normalized),
            'reasons': reasons, 'semantic_policy': POLICY_VERSION,
            'normalized_numbers': [n.record() for n in normalized],
            'numeric_pixel_grounding': 'declared_only; requires independent pixel evidence'}
