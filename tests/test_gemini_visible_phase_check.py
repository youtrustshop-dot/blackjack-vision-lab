"""Offline conditional-lot gate; no model requests or hidden simulator state."""
import socket

import pytest

from validation.tools.gemini_visible_phase_check import ORDER, SPECS, phase_case, qualifies_for_hybrid


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*a,**k):raise AssertionError('No DNS or sockets in conditional selector tests.')
    monkeypatch.setattr(socket,'socket',fail);monkeypatch.setattr(socket,'getaddrinfo',fail)


def good_rows():
    rows=[]
    for i,case in enumerate(ORDER):
        positive=i==0
        rows.append({'case':case,'status':'completed','within_unchanged_live_boundary':True,
            'total_through_validation_ms':1700,'stop_before_next_request':False,'usage_settled':True,
            'retention':{'retained':True},'evaluation_error_type':None,'relevant_totals_exact':True,
            'evaluation':{'strict_wire_validated':True,'exact_card_inventory':True,'phase_correct':True,
                'controls_correct':True,'semantic_complete_transcription':True,'semantic_false_accept':False,
                'expected_usable_r1':positive,'semantic_timely_correct_usable_r1':positive,'semantic_usable_r1':positive}})
    return rows


def test_three_expected_complete_observations_allow_only_the_declared_hybrid():
    assert qualifies_for_hybrid(good_rows())
    assert not qualifies_for_hybrid(good_rows()[:-1])
    assert not qualifies_for_hybrid(good_rows()[::-1])


@pytest.mark.parametrize('key',[
    'strict_wire_validated','exact_card_inventory','phase_correct','controls_correct','semantic_complete_transcription',
])
def test_any_inexact_negative_closes_the_conditional_slot(key):
    rows=good_rows();rows[1]['evaluation'][key]=False
    assert not qualifies_for_hybrid(rows)


@pytest.mark.parametrize('reason',['false_accept','unsafe_negative','positive_not_usable','positive_incomplete',
    'missing_retention','unsettled_usage','stop','evaluation_error','wrong_order'])
def test_receipt_or_safety_failure_closes_the_conditional_slot(reason):
    rows=good_rows()
    if reason=='false_accept':rows[1]['evaluation']['semantic_false_accept']=True
    elif reason=='unsafe_negative':rows[2]['evaluation']['semantic_usable_r1']=True
    elif reason=='positive_not_usable':rows[0]['evaluation']['semantic_timely_correct_usable_r1']=False
    elif reason=='positive_incomplete':rows[0]['evaluation']['semantic_complete_transcription']=False
    elif reason=='missing_retention':rows[2]['retention']={'retained':False}
    elif reason=='unsettled_usage':rows[0]['usage_settled']=False
    elif reason=='stop':rows[0]['stop_before_next_request']=True
    elif reason=='evaluation_error':rows[2]['evaluation_error_type']='ValueError'
    else:rows[2]['case']=ORDER[1]
    assert not qualifies_for_hybrid(rows)


@pytest.mark.parametrize('elapsed',[3000,3001,-1,float('nan'),float('inf'),True,None,'1700'])
def test_invalid_or_boundary_time_closes_the_conditional_slot(elapsed):
    rows=good_rows();rows[0]['total_through_validation_ms']=elapsed
    assert not qualifies_for_hybrid(rows)


def test_waiting_is_a_reachable_empty_following_stage_not_a_relabelled_terminal():
    frame,observation,truth,visibility,stage,family=phase_case(SPECS[2])
    assert stage['phase']=='waiting' and not stage['cards']
    assert observation.phase=='waiting' and not observation.cards and not observation.controls
    assert not frame.details and [n for n,_ in frame.images()]==['table']
