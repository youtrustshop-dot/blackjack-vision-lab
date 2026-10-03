import base64

import pytest
from fastapi.testclient import TestClient

from bjlab.advice import describe_hand, recommend
from bjlab.api import app, sessions
from bjlab.engine import Rules, legal_actions


@pytest.mark.parametrize('cards,total,soft,aces,alternative', [
    (['A', '7'], 18, True, [11], 8),
    (['A', '7', 'A'], 19, True, [11, 1], 9),
    (['A', 'A', '10'], 12, False, [1, 1], None),
    (['10', 'Q'], 20, False, [], None),
])
def test_ace_values(cards, total, soft, aces, alternative):
    hand = describe_hand(cards)
    assert (hand['total'], hand['soft'], hand['ace_values'], hand['alternative_total']) == (total, soft, aces, alternative)


@pytest.mark.parametrize('cards,dealer,expected', [
    (['10', '10'], '6', 'stand'), (['A', '7'], '9', 'hit'),
    (['8', '8'], '10', 'split'), (['10', '6'], '10', 'surrender'),
    (['5', '6'], '6', 'double'), (['A', '9'], 'A', 'stand'),
])
def test_immediate_rule_policy(cards, dealer, expected):
    result = recommend(cards, dealer, Rules(), peeked=True)
    assert result['best_action'] == expected
    assert result['best_action'] in result['legal_actions']


def test_overlapping_estimates_keep_a_legal_basic_answer():
    rules = Rules()
    result = recommend(['10', '10'], '6', rules,
        estimate={'best_action': 'hit', 'ranking_resolved': False})
    assert result['best_action'] == 'stand'
    assert result['basis'] == 'basic-strategy'
    resolved = recommend(['10', '6'], '10', rules, peeked=True,
        estimate={'best_action': 'stand', 'ranking_resolved': True})
    assert resolved['best_action'] == 'stand'
    assert resolved['basis'] == 'observed-composition'
    illegal = recommend(['10', '10'], '6', rules,
        estimate={'best_action': 'insurance', 'ranking_resolved': True})
    assert illegal['best_action'] == 'stand'


def test_simple_mode_never_recommends_disabled_actions():
    rules = Rules(double_rule='none', max_split_hands=1, surrender='none', resplit=False)
    for cards, dealer in [(['8', '8'], '6'), (['5', '6'], '6'), (['10', '6'], '10')]:
        assert recommend(cards, dealer, rules)['best_action'] in ('hit', 'stand')


def test_native_quick_advice_and_pixel_image_probabilities():
    with TestClient(app) as client:
        sid = client.post('/api/sessions', json={}).json()['session_id']
        try:
            sessions[sid].set_shoe(['10', '6', '10', '9'] + ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'A'] * 6)
            state = client.post(f'/api/sessions/{sid}/deal', json={}).json()
            assert state['advice']['best_action'] == 'stand'
            assert state['advice']['hand']['total'] == 20
            probability = client.post(f'/api/sessions/{sid}/outcomes', json={}).json()
            assert probability['events_count'] == state['events_count']
            assert probability['decision']['actions']['stand']['win'] > .5
            frame = client.get(f'/api/sessions/{sid}/frame?theme=black').content
            result = client.post('/api/advisor/image', json={'image_base64': base64.b64encode(frame).decode()})
            assert result.status_code == 200, result.text
            report = result.json()
            assert report['source'] == 'single-image-pixels'
            assert report['advice']['best_action'] == 'stand'
            assert report['observed_cards'] == 3
            row = report['decision']['actions']['stand']
            assert row['win'] + row['push'] + row['loss'] == pytest.approx(1)
            assert 'earlier history unknown' in report['count_scope']
            assert 'session_id' not in report
        finally:
            client.delete(f'/api/sessions/{sid}')


def test_manual_evidence_inventory_and_invalid_input():
    with TestClient(app) as client:
        body = {'player': ['10', '10'], 'dealer': '6', 'observed': ['6']}
        assert client.post('/api/advisor/manual', json=body).status_code == 422
        body['observed'] = ['10', '10', '6', '2', '5']
        quick = client.post('/api/advisor/manual', json={**body, 'estimate': False}).json()
        assert quick['advice']['best_action'] == 'stand'
        assert quick['decision'] is None
        report = client.post('/api/advisor/manual', json=body).json()
        assert report['observed_cards'] == 5
        assert report['running_count'] == 1
        assert report['physical_remaining'] == 312 - 5
        assert report['true_count'] == pytest.approx(52 / 307)
        body.update(rules={'decks': 1}, observed=['10'] * 17 + ['6'])
        assert client.post('/api/advisor/manual', json=body).status_code == 422
        assert client.post('/api/advisor/image', json={'image_base64': 'bad'}).status_code == 422
        assert client.post('/api/advisor/strategy', json={'rules': {'decks': 3}}).status_code == 422


@pytest.mark.parametrize('rules', [{}, {'decks': 1}, {'decks': 8, 'hit_soft17': True},
    {'double_rule': 'none', 'max_split_hands': 1, 'resplit': False, 'surrender': 'none'}])
def test_all_starting_combinations_have_legal_answers(rules):
    with TestClient(app) as client:
        response = client.post('/api/advisor/strategy', json={'rules': rules})
        assert response.status_code == 200, response.text
        library = response.json()
        assert library['combination_count'] == len(library['combinations']) == 550
        assert len({(tuple(row['player']), row['dealer']) for row in library['combinations']}) == 550
        for row in library['combinations']:
            assert row['action'] in legal_actions(row['player'], Rules(**rules))
