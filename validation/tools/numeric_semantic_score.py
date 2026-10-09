"""New offline evaluator, sharing the application's opt-in numeric policy.

Reinterpreting saved responses is contract evaluation, not new model evidence.
The frozen PR16/17 evaluator and literal transcription metrics are untouched.
"""
from collections import Counter

from bjlab.live_state import LiveNumber, LiveObservation
from bjlab.numeric_provenance import POLICY_VERSION, VIEWS, normalize_number, semantic_gate
from validation.tools.paired_cloud_prepare import score as frozen_score


def semantic_score(observation, truth, *, status='completed', elapsed_ms=None, available_views=VIEWS):
    available_views = frozenset(available_views)
    literal = frozen_score(observation, truth, status=status, elapsed_ms=elapsed_ms)
    expected = LiveObservation.model_validate({k: v for k, v in truth.items() if k != 'number_views'})
    actual = LiveObservation.model_validate(observation) if observation is not None and status == 'completed' else None
    expected_gate = semantic_gate(expected, available_views=available_views)
    actual_gate = semantic_gate(actual, available_views=available_views) if actual is not None else None

    def tuples(obs):
        values = []
        for raw in obs.numbers if obs else []:
            number = normalize_number(raw, available_views=available_views)
            if number.blocks_r1 and obs is expected:
                raise ValueError('Reference number violates the declared semantic profile.')
            label = ('normalized', number.normalized_label) if number.normalized_label is not None else ('ambiguous', number.observed_text)
            view = number.source_view
            # The oracle, not the model, determines whether this exact label
            # and value is contained in a detail crop. No widening of its views.
            for entry in truth.get('number_views', []):
                reference = normalize_number(LiveNumber(value=entry['value'], role=entry['role'],
                    label=entry['label'], view='table'))
                if (not number.blocks_r1 and number.status == 'normalized' and
                    (number.declared_role, number.value, number.normalized_label) ==
                    (reference.declared_role, reference.value, reference.normalized_label) and
                    view in entry['allowed_views']):
                    view = 'table'
                    break
            values.append((number.declared_role, number.value, label, view, number.status))
        return Counter(values)

    numbers_e, numbers_a = tuples(expected), tuples(actual)
    unsafe_totals = any(role in ('player_total', 'dealer_total') for role, *_ in numbers_a-numbers_e)
    exact_ranks = actual is not None and Counter((c.zone, c.rank, c.visibility) for c in actual.cards) == Counter(
        (c.zone, c.rank, c.visibility) for c in expected.cards)
    usable = actual_gate is not None and actual_gate['usable']
    coherent = actual_gate is not None and not any(n['blocks_r1'] for n in actual_gate['normalized_numbers'])
    r1_correct = (exact_ranks and literal['phase_correct'] and literal['controls_correct'] and
        set(actual.blockers) == set(expected.blockers) and actual.table_state == expected.table_state and
        not unsafe_totals and coherent and literal['unsupported_known_suit_tuples'] == 0)
    timely = actual is not None and elapsed_ms is not None and 0 <= elapsed_ms <= 3000
    numbers_exact = actual is not None and coherent and numbers_e == numbers_a
    complete = (literal['exact_card_inventory'] and literal['phase_correct'] and literal['controls_correct'] and
        set(actual.blockers) == set(expected.blockers) and actual.table_state == expected.table_state and numbers_exact)
    return {'policy': POLICY_VERSION, 'status': status, 'elapsed_ms': elapsed_ms,
        'strict_wire_validated': actual is not None,
        'expected_usable_r1': expected_gate['usable'], 'semantic_usable_r1': usable,
        'semantic_correct_usable_r1': expected_gate['usable'] and usable and r1_correct,
        'semantic_timely_correct_usable_r1': expected_gate['usable'] and usable and r1_correct and timely,
        'semantic_false_accept': usable and (not expected_gate['usable'] or not r1_correct),
        'semantic_complete_transcription': complete,
        'semantic_numeric_provenance_exact': numbers_exact,
        'semantic_numeric_provenance': {'matched': sum((numbers_e & numbers_a).values()),
            'expected': sum(numbers_e.values()), 'extra_or_wrong': sum((numbers_a-numbers_e).values())},
        'literal_complete_transcription': literal['complete_state_correct'],
        'literal_numeric_provenance_exact': literal['numeric_provenance_exact'],
        'unsafe_semantic_total': unsafe_totals,
        'normalized_numbers': actual_gate['normalized_numbers'] if actual_gate else [],
        'gate_reasons': actual_gate['reasons'] if actual_gate else ['No completed observation.'],
        'evidence_scope': 'offline contract re-evaluation; not new accuracy or generalization'}
