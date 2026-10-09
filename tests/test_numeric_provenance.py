"""Offline semantic contracts, not fresh cloud quality/generalization evidence."""
from copy import deepcopy

import pytest

from bjlab.live_state import LiveObservation, live_gate
from bjlab.numeric_provenance import POLICY_VERSION, normalize_number, semantic_gate
from validation.tools.numeric_semantic_score import semantic_score
from validation.tools.paired_cloud_prepare import score as frozen_score


def state(numbers=None):
    return LiveObservation.model_validate({'cards': [
        {'zone': 'player:0', 'rank': '8', 'suit': 'C', 'visibility': 'readable'},
        {'zone': 'player:0', 'rank': 'J', 'suit': 'S', 'visibility': 'readable'},
        {'zone': 'dealer', 'rank': '2', 'suit': 'S', 'visibility': 'readable'},
        {'zone': 'dealer', 'rank': None, 'suit': None, 'visibility': 'covered'}],
        'table_state': 'cards_present', 'phase': 'player', 'controls': ['hit', 'stand'],
        'numbers': numbers or [], 'blockers': []})


def number(label='DEALER TOTAL', value=2, role='dealer_total', view='table'):
    return dict(label=label, value=value, role=role, view=view)


def truth(numbers=None):
    value = state(numbers).model_dump()
    value['number_views'] = [{**{k: n[k] for k in ('role', 'value', 'label')},
        'allowed_views': ['table', 'dealer'] if n['role'] == 'dealer_total' else
            ['table', 'player:0'] if n['role'] == 'player_total' else ['table']}
        for n in value['numbers']]
    return value


@pytest.mark.parametrize('text', ['DEALER TOTAL', 'DEALER TOTAL 2', 'DEALER TOTAL:2',
    ' dealer  total : 2 ', 'DEALER TOTAL 02'])
def test_explicit_label_grammar_preserves_raw_text_and_equivalent_meaning(text):
    observed = state([number(text, view='dealer')]); before = observed.model_dump()
    gate = semantic_gate(observed)
    normalized = gate['normalized_numbers'][0]
    assert gate['usable'] and gate['semantic_policy'] == POLICY_VERSION
    assert normalized['observed_text'] == text
    assert normalized['normalized_label'] == 'DEALER TOTAL'
    assert (normalized['value'], normalized['declared_role'], normalized['source_view']) == (2, 'dealer_total', 'dealer')
    assert observed.model_dump() == before
    scored = semantic_score(observed, truth([number()]), elapsed_ms=1000)
    assert scored['semantic_timely_correct_usable_r1'] and scored['semantic_complete_transcription']


def test_format_difference_is_semantic_success_and_still_literal_failure():
    original = truth([number(), number('PLAYER TOTAL', 18, 'player_total'), number('SESSION', 20, 'ui')])
    seen = state([number('DEALER TOTAL 2', view='dealer'),
        number('PLAYER TOTAL 18', 18, 'player_total', 'player:0'), number('SESSION 20', 20, 'ui')])
    historical = frozen_score(seen, original, elapsed_ms=1000)
    assert historical['false_accept'] and not historical['complete_state_correct']
    new = semantic_score(seen, original, elapsed_ms=1000)
    assert new['semantic_complete_transcription'] and not new['semantic_false_accept']
    assert not new['literal_complete_transcription'] and not new['literal_numeric_provenance_exact']
    assert frozen_score(seen, original, elapsed_ms=1000) == historical


@pytest.mark.parametrize('bad,reason', [
    (number('DEALER TOTAL 12'), 'label_value_mismatch'),
    (number('SESSION 20', 20, 'unknown'), 'label_role_mismatch'),
    (number('SESSION 20 DEALER TOTAL', 20), 'ambiguous_total_label'),
    (number('PLAYER DEALER TOTAL 2'), 'ambiguous_total_label'),
    (number('DEALER TOTAL 2.0'), 'ambiguous_total_label'),
    (number('DEALER TOTAL 2 12'), 'ambiguous_total_label'),
    (number('DEALER TOTAL -2'), 'ambiguous_total_label'),
    (number('DEALER TOTAL 2', view='player:0'), 'label_source_view_mismatch'),
    (number('DEALER TOTAL 2', view='controls'), 'label_source_view_mismatch'),
    (number('PLAYER TOTAL 18', 18, 'player_total', 'dealer'), 'label_source_view_mismatch'),
    (number('SESSION 20', 20, 'ui', 'dealer'), 'label_source_view_mismatch'),
    (number('DEALER TOTAL 2', 2, 'ui'), 'label_role_mismatch'),
])
def test_incoherent_number_blocks_application_and_evaluator(bad, reason):
    observed = state([bad]); gate = semantic_gate(observed)
    assert reason in gate['normalized_numbers'][0]['issues'] and not gate['usable']
    new = semantic_score(observed, truth([number()]), elapsed_ms=1000)
    assert not new['semantic_usable_r1'] and not new['semantic_complete_transcription']
    assert not new['semantic_false_accept']


def test_session_cannot_become_total_even_before_semantic_adapter():
    with pytest.raises(ValueError): state([number('SESSION 20', 20)])
    normalized = normalize_number(number('SESSION 20', 20, 'ui'))
    assert normalized.declared_role == 'ui' and normalized.value == 20
    assert state([number('SESSION 20', 20, 'ui')]).totals()[0] == {}


@pytest.mark.parametrize('label', [None, '20', 'PLAYER OR DEALER TOTAL 20', 'TOTAL 20'])
def test_ambiguous_unknowns_never_gain_a_label_or_role(label):
    observed = state([number(label, 20, 'unknown')]); before = observed.model_dump()
    normalized = semantic_gate(observed)['normalized_numbers'][0]
    assert normalized['status'] == 'ambiguous' and normalized['normalized_label'] is None
    assert normalized['observed_text'] == label and normalized['declared_role'] == 'unknown'
    assert observed.totals()[0] == {} and observed.model_dump() == before
    assert not semantic_score(observed, truth([number('SESSION', 20, 'ui')]), elapsed_ms=1000)['semantic_complete_transcription']


def test_nonexistent_source_view_and_oracle_restricted_view_are_not_repaired():
    observed = state([number('DEALER TOTAL 2', view='dealer')])
    gate = semantic_gate(observed, available_views={'table', 'player:0', 'controls'})
    assert not gate['usable'] and 'source_view_not_available' in gate['normalized_numbers'][0]['issues']
    original = truth([number()]); original['number_views'][0]['allowed_views'] = ['table']
    # The application cannot see the oracle: it can check role/view compatibility,
    # not prove actual text presence. The independent evaluator catches this.
    scored = semantic_score(observed, original, elapsed_ms=1000)
    assert scored['semantic_false_accept'] and not scored['semantic_numeric_provenance_exact']


def test_mathematical_consistency_cannot_replace_evidence_and_omissions_stay_visible():
    observed = state([number()])
    assert live_gate(observed)['usable']
    assert semantic_score(observed, truth(), elapsed_ms=1000)['semantic_false_accept']
    row = semantic_score(state(), truth([number('SESSION', 20, 'ui')]), elapsed_ms=1000)
    assert row['semantic_timely_correct_usable_r1'] and not row['semantic_complete_transcription']
    assert row['semantic_numeric_provenance'] == {'matched': 0, 'expected': 1, 'extra_or_wrong': 0}


def test_timeout_cannot_be_resurrected_by_contract_re_evaluation():
    row = semantic_score(state([number('DEALER TOTAL 2')]), truth([number()]), status='timeout', elapsed_ms=3049)
    assert not row['strict_wire_validated'] and not row['semantic_usable_r1']
    assert not row['semantic_complete_transcription'] and row['normalized_numbers'] == []
    row = semantic_score(state(), truth(), elapsed_ms=3001)
    assert row['semantic_correct_usable_r1'] and not row['semantic_timely_correct_usable_r1']


def test_existing_arithmetic_phase_and_card_integrity_checks_still_apply():
    observed = state([number('PLAYER TOTAL 17', 17, 'player_total')])
    assert not semantic_gate(observed)['usable']
    unknown_phase = state().model_copy(update={'phase': 'unknown'})
    assert not semantic_gate(unknown_phase)['usable']
    missing = state().model_dump(); missing['cards'].pop()
    assert semantic_score(missing, truth(), elapsed_ms=1000)['semantic_false_accept']
    duplicate = state().model_dump(); duplicate['numbers'] = [number(), deepcopy(number())]
    row = semantic_score(duplicate, truth([number()]), elapsed_ms=1000)
    assert row['unsafe_semantic_total'] and row['semantic_numeric_provenance']['extra_or_wrong'] == 1
