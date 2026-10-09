"""Frozen new-state gate prevents premature API follow-up; no network."""
from copy import deepcopy
import socket

import pytest

from tests.test_numeric_provenance import state, truth, number
from validation.tools.gemini_bound_session_hybrid import ORDER, HYBRID_CASE, SPECS, qualifies_for_hybrid, total_provenance_exact


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):raise AssertionError('No sockets or DNS in gate tests.')
    monkeypatch.setattr(socket,'socket',fail);monkeypatch.setattr(socket,'getaddrinfo',fail)


def valid_rows():
    return [{'case':case,'status':'completed','within_unchanged_live_boundary':True,'total_through_validation_ms':2400,
        'relevant_totals_exact':True,'stop_before_next_request':False,'usage_settled':True,'retention':{'retained':True},
        'evaluation':{'strict_wire_validated':True,'exact_card_inventory':True,'phase_correct':True,'controls_correct':True,
            'semantic_false_accept':False,'expected_usable_r1':i<2,'semantic_timely_correct_usable_r1':i<2,
            'semantic_usable_r1':i<2,'semantic_complete_transcription':True}}
        for i,case in enumerate(ORDER)]


def test_all_three_new_still_checks_are_required_before_a_single_conditional_hybrid():
    rows=valid_rows();assert qualifies_for_hybrid(rows)
    assert not qualifies_for_hybrid(rows[:2]) and not qualifies_for_hybrid(rows[::-1])
    assert HYBRID_CASE not in ORDER and len(SPECS)==4
    assert len({s[2] for s in SPECS})==4 and all(s[2]>91008061 for s in SPECS)


@pytest.mark.parametrize('failure',['late','false_accept','cards','controls','phase','total','negative_incomplete','negative_accepted','positive_not_usable'])
def test_safety_or_quality_failure_closes_hybrid_slot(failure):
    rows=valid_rows()
    if failure=='late':rows[0]['within_unchanged_live_boundary']=False
    elif failure=='total':rows[0]['relevant_totals_exact']=False
    elif failure=='negative_incomplete':rows[2]['evaluation']['semantic_complete_transcription']=False
    elif failure=='negative_accepted':rows[2]['evaluation']['semantic_usable_r1']=True
    elif failure=='positive_not_usable':rows[0]['evaluation']['semantic_timely_correct_usable_r1']=False
    else:
        field={'false_accept':'semantic_false_accept','cards':'exact_card_inventory','controls':'controls_correct','phase':'phase_correct'}[failure]
        rows[0]['evaluation'][field]=(failure=='false_accept')
    assert not qualifies_for_hybrid(rows)


def test_ui_transcription_residual_is_recorded_without_becoming_a_false_decision_total():
    rows=valid_rows();rows[1]['evaluation']['semantic_complete_transcription']=False
    assert qualifies_for_hybrid(rows)
    expected=truth([number('SESSION',20,'ui')]);observed=state([number(None,20,'unknown')])
    assert total_provenance_exact(observed,expected)
    assert not total_provenance_exact(state([number('DEALER TOTAL 2')]),expected)


def test_relevant_totals_require_observed_role_value_label_and_actual_table_view():
    expected=truth([number('PLAYER TOTAL',18,'player_total')])
    assert total_provenance_exact(state([number('PLAYER TOTAL 18',18,'player_total')]),expected)
    assert not total_provenance_exact(state(),expected)
    assert not total_provenance_exact(state([number('PLAYER TOTAL 18',18,'player_total','player:0')]),expected)


@pytest.mark.parametrize('failure',['missing_receipt','unsettled_usage','storage','evaluator','exact_deadline','invalid_time'])
def test_missing_receipts_or_boundary_result_close_the_conditional_slot(failure):
    rows=valid_rows()
    if failure=='missing_receipt':rows[0].pop('stop_before_next_request')
    elif failure=='unsettled_usage':rows[0]['usage_settled']=False
    elif failure=='storage':rows[0]['retention']['retained']=False
    elif failure=='evaluator':rows[0]['evaluation_error_type']='ValueError'
    elif failure=='exact_deadline':rows[0]['total_through_validation_ms']=3000
    else:rows[0]['total_through_validation_ms']=float('nan')
    assert not qualifies_for_hybrid(rows)
