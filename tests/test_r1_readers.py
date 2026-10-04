"""Reader/transport contracts with fakes, not evidence of API vision quality."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json

import pytest
from PIL import Image
from pydantic import ValidationError

from bjlab.engine import Rules
from bjlab.state_reader import HandObservation, analysis_gate, image_analysis, prepare_frame
from bjlab.openai_reader import ModelConfig, OpenAIVisionReader, RequestBudget
from validation.tools.state_reader_comparison import (
    authorize, claim_authorization, compare, digest, load_frame, prepare, score_state, write_json,
)


LAYOUT = {'table': [.1, .1, .8, .8], 'dealer': [.3, .15, .3, .2],
          'player:0': [.3, .55, .3, .2]}


def observation(**changes):
    value = dict(cards=[
        {'zone': 'player:0', 'rank': 'A', 'suit': None, 'visibility': 'readable'},
        {'zone': 'player:0', 'rank': '5', 'suit': None, 'visibility': 'readable'},
        {'zone': 'dealer', 'rank': '2', 'suit': 'C', 'visibility': 'readable'},
        {'zone': 'dealer', 'rank': None, 'suit': None, 'visibility': 'covered'}],
        table_state='cards_present', phase='unknown', controls=[], player_total=16,
        dealer_total=2, unknown_fields=['phase', 'player suits'], blockers=[])
    value.update(changes)
    return HandObservation(**value)


def frame():
    image = Image.new('RGB', (200, 100), 'red')
    image.paste('green', (20, 10, 180, 90))
    return prepare_frame(image, LAYOUT)


def config(**changes):
    # Fictional model/rates for transport contracts. Never call this ID remotely.
    value = dict(model='contract-test-only', context_token_limit=1000,
        input_usd_per_million='1', output_usd_per_million='2', max_output_tokens=200,
        pricing_source='https://developers.openai.com/api/docs/pricing')
    value.update(changes)
    return ModelConfig(**value)


class Transport:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response if response is not None else dict(status='completed',
            model='contract-test-only', usage={'input_tokens': 50, 'output_tokens': 80},
            output=[{'type': 'message', 'content': [{'type': 'output_text',
                'text': observation().model_dump_json()}]}])
        self.error = error

    def post(self, payload, timeout):
        self.calls.append(payload)
        if self.error:
            raise self.error
        return self.response


def reader(transport=None, approved=None, budget=None):
    approved = approved if approved is not None else {sha256(b).hexdigest() for _, b in frame().images()}
    return OpenAIVisionReader(config(), budget or RequestBudget(2, '.01'), approved,
                              transport=transport or Transport())


def test_native_inputs_exclude_surrounding_desktop_and_preserve_pixels():
    value = frame()
    assert value.source_size == (200, 100)
    assert value.table_box == (20, 10, 160, 80)
    for name, data in value.images():
        image = Image.open(BytesIO(data))
        assert image.getpixel((0, 0)) == (0, 128, 0)
    assert Image.open(BytesIO(value.details[0][1])).size == (60, 20)


def test_unknown_suits_allow_rank_study_but_not_poker_or_live():
    value = observation()
    assert analysis_gate(value)['usable']
    assert not analysis_gate(value, capability='poker-cards')['usable']
    assert not analysis_gate(value, require_turn=True)['usable']
    result = image_analysis(value, Rules())
    assert result['advice'] is not None
    assert result['conditional_on_configured_rules']
    assert not result['gate']['shoe_history_certified']
    assert not result['gate']['live_certified']


@pytest.mark.parametrize('phase', ['dealer', 'waiting', 'settled'])
def test_explicit_non_player_phase_blocks_advice(phase):
    assert image_analysis(observation(phase=phase), Rules())['advice'] is None


@pytest.mark.parametrize('change', [
    {'player_total': 3}, {'dealer_total': 9}, {'blockers': ['occluded unknown player card']},
    {'cards': [], 'table_state': 'uncertain'}, {'cards': [], 'table_state': 'empty'},
])
def test_observed_conflicts_and_missing_information_block(change):
    assert not analysis_gate(observation(**change))['usable']


@pytest.mark.parametrize('change', [
    {'cards': [], 'table_state': 'cards_present'},
    {'controls': ['hit', 'hit']}, {'player_total': True}, {'phase': 'assumed-player'},
    {'cards': [{'zone': 'dealer', 'rank': 'A', 'suit': None, 'visibility': 'covered'}]},
])
def test_invalid_observation_is_not_a_valid_empty_hand(change):
    with pytest.raises(ValidationError):
        observation(**change)


def test_equal_cards_remain_two_physical_objects():
    value = observation()
    value.cards[1] = value.cards[0].model_copy()
    value.player_total = 12
    assert len(value.cards) == 4
    assert analysis_gate(value)['usable']


def test_success_payload_has_no_oracle_tools_or_strategy():
    transport = Transport()
    result = reader(transport).read(frame())
    assert result.status == 'completed'
    payload = transport.calls[0]
    assert payload['store'] is False
    assert 'tools' not in payload
    assert payload['text']['format']['strict']
    assert payload['text']['format']['schema']['additionalProperties'] is False
    images = [c for c in payload['input'][0]['content'] if c['type'] == 'input_image']
    assert len(images) == 3
    assert base64.b64decode(images[0]['image_url'].split(',')[1]) == frame().table_png
    assert 'expected_cards' not in json.dumps(payload)
    assert result.diagnostics['retry_count'] == 0
    assert result.diagnostics['price_based_cost_usd'] == '0.00021'


def test_unapproved_crop_never_reaches_transport_or_budget():
    transport = Transport()
    value = reader(transport, approved=set())
    result = value.read(frame())
    assert result.status == 'blocked' and result.observation is None
    assert transport.calls == [] and value.budget.requests == 0


@pytest.mark.parametrize('response,status', [
    ({'status': 'incomplete', 'output': []}, 'incomplete'),
    ({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}, 'refused'),
    ({'status': 'completed', 'output': []}, 'error'),
    ({'status': 'completed', 'output': [{'type': 'function_call'}]}, 'error'),
    ({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{}'}]}]}, 'error'),
])
def test_unavailable_response_is_not_an_empty_observation(response, status):
    result = reader(Transport(response=response)).read(frame())
    assert result.status == status and result.observation is None


@pytest.mark.parametrize('error,status', [(TimeoutError('private-token'), 'timeout'),
                                        (RuntimeError('private-token'), 'error')])
def test_no_retry_no_secret_echo_and_failed_reservation_retained(error, status):
    transport = Transport(error=error)
    value = reader(transport, budget=RequestBudget(1, '.01'))
    result = value.read(frame())
    assert result.status == status
    assert 'private-token' not in json.dumps(result.diagnostics)
    assert value.read(frame()).status == 'blocked'
    assert len(transport.calls) == 1 and value.budget.requests == 1


def test_unexpected_usage_stops_future_requests():
    transport = Transport()
    transport.response['usage']['input_tokens'] = 1001
    value = reader(transport)
    assert value.read(frame()).status == 'error'
    assert value.budget.stopped
    assert value.read(frame()).status == 'blocked'
    assert len(transport.calls) == 1


def test_parallel_budget_cannot_overspend():
    budget = RequestBudget(100, '.003')
    def attempt(_):
        try:
            budget.reserve(Decimal('.001'))
            return True
        except PermissionError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(30))) == 3
    assert budget.requests == 3 and budget.reserved == Decimal('.003')


def test_absent_truth_phase_never_claims_complete_state_correctness():
    value = observation()
    assert score_state(value, {'cards': value.model_dump()['cards'], 'phase': None})['complete_state_correct'] is None
    assert not score_state(None, {'cards': [], 'phase': 'waiting'})['rank_presence_state_correct']


def test_complete_state_needs_control_and_total_annotations_and_checks_them():
    value = observation(phase='player')
    truth = value.model_dump()
    assert score_state(value, truth)['complete_state_correct'] is True
    truth['controls'] = ['hit']
    assert score_state(value, truth)['complete_state_correct'] is False
    del truth['controls']
    assert score_state(value, truth)['complete_state_correct'] is None


def approval(records):
    return dict(approved=True, authorization_id='unit-only-001', configuration_sha256='config-hash',
        prepared_manifest_sha256='frame-hash',
        expires_utc=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        image_sha256=[i['sha256'] for r in records for i in r['images']],
        models=['contract-test-only'], max_requests=2, max_usd='.01')


@pytest.mark.parametrize('mutation', [
    {'approved': False}, {'configuration_sha256': 'changed'},
    {'prepared_manifest_sha256': 'changed-geometry'}, {'image_sha256': []},
    {'models': ['another-model']}, {'max_usd': '.0001'},
    {'expires_utc': '2020-01-01T00:00:00+00:00'},
])
def test_authorization_binds_pixels_geometry_config_expiry_budget(mutation):
    records = [{'images': [{'sha256': 'pixels'}]}]
    consent = approval(records)
    consent.update(mutation)
    with pytest.raises(PermissionError):
        authorize(consent, records, [config()], 'config-hash', 'frame-hash')


def test_authorization_cannot_be_reused_for_another_output(tmp_path):
    consent = approval([])
    claim_authorization(tmp_path, consent)
    with pytest.raises(PermissionError):
        claim_authorization(tmp_path, consent)


def test_prepare_keeps_oracle_separate_and_refuses_changed_images(tmp_path):
    source = tmp_path/'source.png'
    Image.new('RGB', (200, 100), 'green').save(source)
    manifest = tmp_path/'manifest.json'
    write_json(manifest, {'cases': [dict(id='unit', input_kind='digital-screenshot',
        split='development', source_file=str(source), layout=LAYOUT, cards=[
            {'zone': 'dealer', 'rank': '2', 'suit': 'C'}])]})
    directory = tmp_path/'prepared'
    assert prepare(manifest, directory)['uploads'] == 0
    records = json.loads((directory/'frames.json').read_text())['frames']
    assert 'cards' not in records[0]
    assert 'oracle' not in json.dumps(records)
    (directory/records[0]['images'][0]['file']).write_bytes(b'changed')
    with pytest.raises(ValueError):
        load_frame(directory, records[0])


def test_paid_runner_missing_authorization_does_no_network(tmp_path, monkeypatch):
    source = tmp_path/'source.png'
    Image.new('RGB', (200, 100), 'green').save(source)
    manifest = tmp_path/'manifest.json'
    write_json(manifest, {'cases': [dict(id='unit', input_kind='digital-screenshot',
        split='development', source_file=str(source), layout=LAYOUT, cards=[])]})
    directory = tmp_path/'prepared'
    prepare(manifest, directory)
    configuration = tmp_path/'configuration.json'
    write_json(configuration, {'models': [config().__dict__]})
    def forbidden(*a, **k):
        raise AssertionError('Network is not authorized')
    monkeypatch.setattr('validation.tools.state_reader_comparison.ResponsesTransport', forbidden)
    with pytest.raises(PermissionError):
        compare(directory, tmp_path/'run', configuration=configuration)


def test_runner_records_reader_error_and_keeps_failed_state_in_denominator(tmp_path, monkeypatch):
    from bjlab.state_reader import ReaderResult
    policy = tmp_path/'policy.json'
    write_json(policy, {'api_access_policy': {'inference_authorized': False}})
    monkeypatch.setattr('bjlab.api_access_policy.MATRIX', policy)
    source = tmp_path/'source.png'
    Image.new('RGB', (200, 100), 'green').save(source)
    manifest = tmp_path/'manifest.json'
    write_json(manifest, {'cases': [dict(id='unit', input_kind='digital-screenshot',
        split='development', source_file=str(source), layout=LAYOUT, cards=[])]})
    directory = tmp_path/'prepared'
    prepare(manifest, directory)
    class FailedReader:
        name = 'failing-contract-only'
        def read(self, frame):
            raise RuntimeError('private-source-text')
    monkeypatch.setattr('validation.tools.state_reader_comparison.LocalVisionReader', FailedReader)
    report = compare(directory, tmp_path/'run')
    result = report['readers'][FailedReader.name]
    assert result['states'] == 1 and result['failures'] == 1
    assert result['rank_presence_states_correct'] == 0
    assert result['complete_state_accuracy'] is None
    assert not report['api_comparison_executed']
    assert 'blocked_zero_api_budget' in report['api_blockers']
    assert 'private-source-text' not in (tmp_path/'run/private-results.json').read_text()
