"""Opt-in visible phase vocabulary; no relabelling of returned observations.

Only the request instruction changes. The wire schema, available-image binding,
local semantic gate, solver and original capture deadline are inherited intact.
The convention describes visible controls, never hidden round IDs or outcomes.
"""
from copy import deepcopy

from .available_view_deadline_reader import AvailableViewDeadlineReader
from .live_cloud import PROMPT

REQUEST_PROFILE = 'gemini-visible-phase-v1'
PHASE_RULES = '''
Visible phase convention for this research profile:
p=settled when cards remain on the table, NEW HAND is visibly enabled and all
player decision buttons are disabled. This name takes precedence over the
informal idea of waiting for another hand.
p=waiting when the card area is empty and DEAL is visibly enabled.
p=player when player decision buttons such as HIT or STAND are visibly enabled;
unreadable cards must still be reported and blocked, not invented.
p=dealer only with an explicit visible active-dealer-turn indication.
p=unknown when these signals are absent, obscured, ambiguous or conflicting.
Do not infer an internal phase from totals, card identities or a previous frame.
NEW HAND and DEAL are phase evidence, not additional entries in a; a still
contains only supported visibly enabled player decision actions.
Keep the actual printed numbers, labels, all cards and all blockers unchanged.'''


def add_visible_phase_vocabulary(bound_payload):
    """Append one rule to a previously byte-checked available-view request."""
    parts = bound_payload.get('systemInstruction', {}).get('parts', [])
    if (len(parts) != 2 or not parts[0].get('text', '').startswith(PROMPT) or
            'Actually supplied image names: ' not in parts[0]['text'] or
            PHASE_RULES in parts[0]['text'] or
            bound_payload.get('generationConfig', {}).get('responseMimeType') != 'application/json'):
        raise ValueError('One unchanged bound JSON-mode request is required.')
    result = deepcopy(bound_payload)
    result['systemInstruction']['parts'][0]['text'] += PHASE_RULES
    return result


class VisiblePhaseDeadlineReader(AvailableViewDeadlineReader):
    def __init__(self, config, budget, hashes, *, transport):
        super().__init__(config, budget, hashes, transport=transport)
        self.name = 'gemini-json-visible-phase-v1'

    def payload(self, frame):
        return add_visible_phase_vocabulary(super().payload(frame))
