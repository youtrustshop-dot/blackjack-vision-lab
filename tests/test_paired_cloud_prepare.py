"""Offline contracts/fixtures only. These tests are not cloud-quality evidence."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import socket

import pytest

from validation.tools import paired_cloud_prepare as prep


def state(**changes):
    value = {'cards': [
        {'zone': 'player:0', 'rank': 'A', 'suit': 'H', 'visibility': 'readable'},
        {'zone': 'player:0', 'rank': '5', 'suit': 'D', 'visibility': 'readable'},
        {'zone': 'dealer', 'rank': '2', 'suit': 'C', 'visibility': 'readable'},
        {'zone': 'dealer', 'rank': None, 'suit': None, 'visibility': 'covered'}],
        'table_state': 'cards_present', 'phase': 'player', 'controls': ['hit', 'stand'],
        'numbers': [], 'blockers': []}
    value.update(changes)
    return value


@pytest.fixture(scope='module')
def corpus(tmp_path_factory):
    required = {family[2] for values in prep.FAMILIES.values() for family in values} | {'arialbd.ttf', 'seguisym.ttf'}
    if any(not Path('C:/Windows/Fonts', name).is_file() for name in required):
        pytest.skip('Rendering fixture requires the declared Windows artwork fonts; no silent substitution.')
    directory = tmp_path_factory.mktemp('paired-offline')
    model = directory/'weights'; model.mkdir()
    exports = {}
    for name in ('pose.onnx', 'classifier.onnx'):
        pixels = ('fixture only '+name).encode(); (model/name).write_bytes(pixels)
        exports[name] = {'sha256': sha256(pixels).hexdigest()}
    prep.save(model/'reader.json', {'pose_model': 'pose.onnx', 'classifier_model': 'classifier.onnx',
                                  'exports': exports, 'reader_version': 'contract-fixture'})
    snapshot = {'sha256': 'fixture', 'receipt': {'requests_attempted': 94, 'max_requests': 102,
        'max_usd': '8', 'accounted_upper_usd': '5.087190600'}}
    with pytest.MonkeyPatch.context() as m:
        def forbidden(*args, **kwargs): raise AssertionError('Offline preparation tried to access the network or infer.')
        m.setattr(socket, 'getaddrinfo', forbidden)
        m.setattr(socket, 'create_connection', forbidden)
        m.setattr(prep.DiagnosticReader, 'read', forbidden)
        m.setattr(prep, 'ledger_snapshot', lambda: deepcopy(snapshot))
        m.setenv('OPENAI_API_KEY', 'never-read-contract-fixture')
        m.setenv('GEMINI_API_KEY', 'never-read-contract-fixture')
        output = directory/'corpus'
        freeze = prep.prepare(output, model/'reader.json')
    return output, freeze


def test_fresh_corpus_grouping_and_no_oracle_in_provider_inputs(corpus):
    output, freeze = corpus
    for key in ('sessions', 'seeds', 'families', 'hand_groups'):
        assert not set(freeze['partitions']['development'][key]) & set(freeze['partitions']['validation'][key])
    assert freeze['provider_calls'] == 0 and freeze['final_holdout'].startswith('not_created')
    assert not (output/'final_holdout').exists()
    assert freeze['frozen_local']['inference_executed'] is False
    for split in ('development', 'validation'):
        _, inputs, truths = prep.checked(output, split)
        assert len(inputs) == 16 and len({r['independent_session'] for r, _ in inputs}) == 3
        assert len({r['independent_session'] for r, _ in inputs if r['id'] in prep.SMOKE}) == 3
        assert all(prep.score(prep.live_truth(truths[r['id']]), truths[r['id']])['complete_state_correct'] for r, _ in inputs)
        details = json.loads((output/split/'visibility-evidence.json').read_text())
        for record, frame in inputs:
            a, b = [json.loads((output/split/record['payloads'][n]['file']).read_text()) for n in prep.NAMES]
            assert prep.payload_images(a, prep.NAMES[0]) == prep.payload_images(b, prep.NAMES[1]) == [p for _, p in frame.images()]
            schema = deepcopy(a['text']['format']['schema']); schema['properties']['c'].pop('maxItems')
            assert schema == b['generationConfig']['responseFormat']['text']['schema']
            text = json.dumps([a, b])
            assert record['independent_session'] not in text and record['hand_group'] not in text
            assert all(d['physical_instance'] not in text for d in details[record['id']])
            assert 'never-read-contract-fixture' not in text


def test_partial_covered_unreadable_and_disabled_states_remain_distinct(corpus):
    output, _ = corpus
    _, _, truths = prep.checked(output, 'validation')
    partial = next(c for c in truths['partial-index']['cards'] if c['zone'] == 'player:0')
    assert partial['rank'] is not None and partial['suit'] is None and partial['visibility'] == 'partial'
    assert prep.score(prep.live_truth(truths['partial-index']), truths['partial-index'])['correct_usable_r1']
    assert any(c['visibility'] == 'covered' for c in truths['backs']['cards'])
    assert any(c['visibility'] == 'unreadable' for c in truths['popup-unreadable']['cards'])
    assert not truths['disabled-controls']['controls'] and truths['disabled-controls']['phase'] == 'settled'
    assert truths['transition-clear']['table_state'] == 'empty'
    assert truths['transition-dealing']['phase'] == 'unknown'


def test_final_holdout_rejected_before_any_files_are_read(tmp_path):
    with pytest.raises(PermissionError): prep.checked(tmp_path/'absent', 'final_holdout')


@pytest.mark.parametrize('filename', ('clean-ui/table.png', 'clean-ui/luna-fast-live-v3.request.json', 'oracle.json'))
def test_freeze_rejects_pixel_payload_and_annotation_tampering(corpus, filename):
    output, _ = corpus
    path = output/'validation'/filename; original = path.read_bytes()
    try:
        path.write_bytes(original+b' ')
        with pytest.raises(ValueError): prep.checked(output, 'validation')
    finally: path.write_bytes(original)


def test_freeze_rejects_weight_changes_without_loading_a_model(corpus):
    output, freeze = corpus
    path = Path(freeze['frozen_local']['manifest']).parent/'pose.onnx'; original = path.read_bytes()
    try:
        path.write_bytes(b'changed')
        with pytest.raises(ValueError): prep.checked(output, 'validation')
    finally: path.write_bytes(original)


def test_missing_and_duplicate_cards_stay_in_inventory_denominator():
    truth = state(); missing = state(); missing['cards'].pop()
    row = prep.score(missing, truth)
    assert row['backs'] == {'correct': 0, 'expected': 1}
    assert row['inventory_mismatches']['missing_tuples'] == 1 and row['false_accept']
    duplicate = state(); duplicate['cards'].append(deepcopy(duplicate['cards'][0]))
    row = prep.score(duplicate, truth)
    assert row['inventory_mismatches']['extra_tuples'] == 1 and row['false_accept']
    fail = prep.score(None, truth, status='timeout', elapsed_ms=3000)
    assert fail['rank'] == {'correct': 0, 'expected': 3} and fail['suit'] == {'correct': 0, 'expected': 3}


def test_provenance_checks_legitimate_views_and_detects_invented_attribution():
    number = {'role': 'dealer_total', 'value': 2, 'label': 'DEALER TOTAL', 'view': 'table'}
    truth = state(numbers=[number]); truth['number_views'] = [{**{k: number[k] for k in ('role', 'value', 'label')},
                                                              'allowed_views': ['table', 'dealer']}]
    seen = state(numbers=[{**number, 'view': 'dealer'}])
    assert prep.score(seen, truth)['numeric_provenance_exact']
    seen['numbers'][0]['view'] = 'controls'
    row = prep.score(seen, truth)
    assert row['false_accept'] and row['unsafe_attributed_total']
    # Even a mathematically matching total must have evidence in this image.
    assert prep.score(state(numbers=[number]), state())['false_accept']


def test_terminal_cannot_be_silently_reinterpreted_as_a_player_turn():
    row = prep.score(state(), state(phase='settled', controls=[]))
    assert row['false_accept'] and not row['correct_abstention']
    row = prep.score(state(phase='settled', controls=[]), state(phase='settled', controls=[]))
    assert row['correct_abstention'] and not row['correct_usable_r1']


def test_budget_plan_separates_affordable_initial_from_full_batch():
    receipt = {'max_usd': '8', 'accounted_upper_usd': '5.087190600'}
    plan = prep.budget_plan(receipt, 16)
    assert plan['initial_proposal']['paired_requests'] == 6
    assert plan['initial_proposal']['worst_case_usd'] == '2.5310064'
    assert plan['initial_proposal']['fits_existing_money_margin']
    assert plan['full_still_plus_hybrid']['maximum_requests'] == 37
    assert not plan['full_still_plus_hybrid']['fits_existing_money_margin']
    assert plan['new_requests_executed'] == plan['warmup_provider_requests'] == plan['retries'] == 0
    assert plan['authorization_status'] == 'NOT_AUTHORIZED_OFFLINE_ONLY'
    with pytest.raises(PermissionError): prep.OfflineOnly().reserve
    with pytest.raises(PermissionError): prep.OfflineOnly().post


def test_summary_keeps_failures_separate_from_latency_and_unexecuted():
    good = prep.score(state(), state(), elapsed_ms=1000)
    timeout = prep.score(None, state(), status='timeout', elapsed_ms=3000)
    summary = prep.summarize([good, timeout], planned=16, independent_sessions=3)
    assert summary['not_executed'] == 14 and summary['strict_validated'] == {'numerator': 1, 'denominator': 2}
    assert summary['timeouts'] == 1 and summary['failures'] == 1
    assert summary['timely_correct_usable_r1'] == {'numerator': 1, 'denominator': 2}
    assert summary['latency_complete_validated_only_ms']['p95'] == 1000
    assert prep.summarize([], planned=16, independent_sessions=3)['latency_complete_validated_only_ms']['p95'] is None


def test_evaluator_rejects_unbound_results_and_counts_invalid_output_as_failure(corpus, tmp_path):
    output, _ = corpus
    _, inputs, truths = prep.checked(output, 'validation'); record = inputs[0][0]; name = prep.NAMES[0]
    item = {'candidate': name, 'case_id': record['id'], 'payload_sha256': record['payloads'][name]['sha256'],
            'status': 'completed', 'elapsed_ms': 1234, 'observation': {**prep.live_truth(truths[record['id']]).model_dump(), 'invented_confidence': .99}}
    results = {'freeze_sha256': prep.file_hash(output/'freeze.json'), 'split': 'validation',
               'evidence_kind': 'contract-fixture', 'results': [item]}
    path = tmp_path/'results.json'; prep.save(path, results)
    scored = prep.evaluate(output, 'validation', path)
    assert not scored['model_quality_evidence'] and scored['candidates'][name]['failures'] == 1
    assert scored['candidates'][name]['strict_validated']['numerator'] == 0
    results['results'][0]['payload_sha256'] = 'wrong'; prep.save(path, results)
    with pytest.raises(ValueError): prep.evaluate(output, 'validation', path)
