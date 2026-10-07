"""Offline packet/candidate controls, never Gemini model quality claims."""
from dataclasses import replace
from io import BytesIO

from PIL import Image, ImageDraw
import pytest

from bjlab.state_reader import png_bytes, prepare_frame
from tests.test_r1_readers import frame
from validation.tools.gemini_request_ablation import bet_control, native_view_audit, request_payload
from validation.tools.grounded_corpus import font
from validation.tools.stress_lab import LAYOUT


def test_native_producer_details_match_table_crops():
    result = native_view_audit(frame())
    assert result['status'] == 'passed' and result['checked_details']


def test_initial_incoherent_detail_is_rejected_offline_even_without_motion():
    original = frame()
    name, encoded = original.details[0]
    with Image.open(BytesIO(encoded)) as image:
        wrong = Image.new('RGB', image.size, '#ab24df')
    changed = replace(original, details=((name, png_bytes(wrong)),) + original.details[1:])
    with pytest.raises(ValueError, match='differs from its same-table crop'):
        native_view_audit(changed)


@pytest.mark.parametrize('change', ['duplicate', 'no_geometry', 'wrong_source'])
def test_native_audit_rejects_ambiguous_names_and_geometry(change):
    original = frame()
    if change == 'duplicate':
        changed = replace(original, details=original.details+original.details[:1])
    elif change == 'no_geometry':
        changed = replace(original, details=(('unmapped', original.details[0][1]),))
    else:
        changed = replace(original, source_size=(1, 1))
    with pytest.raises(ValueError):
        native_view_audit(changed)


def test_json_mode_has_same_thinking_and_output_cap_without_reader_edit(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline payload preparation must never use network or credentials.')
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr('bjlab.grounded_cloud.GeminiTransport.__init__', forbidden)
    original = frame()
    structured = request_payload(original, 'structured-card-limit-local')
    mime = request_payload(original, 'json-mode')
    assert structured['contents'] == mime['contents']
    for key in ('maxOutputTokens', 'thinkingConfig'):
        assert structured['generationConfig'][key] == mime['generationConfig'][key]
    assert mime['generationConfig']['thinkingConfig'] == {'thinkingLevel': 'MINIMAL', 'includeThoughts': False}
    assert structured['systemInstruction']['parts'][0] == mime['systemInstruction']['parts'][0]
    assert 'responseFormat' not in mime['generationConfig']
    assert 'matching this JSON schema' in mime['systemInstruction']['parts'][1]['text']


def test_table_only_payload_does_not_claim_detail_images_were_sent():
    original = replace(frame(), details=())
    assert native_view_audit(original)['checked_details'] == []
    payload = request_payload(original, 'structured-card-limit-local')
    parts = payload['contents'][0]['parts']
    assert len([p for p in parts if 'inlineData' in p]) == 1
    assert [p['text'] for p in parts if p.get('text', '').startswith('View: ')] == ['View: table']


def test_bet_control_changes_only_visible_label_and_keeps_request_text_blind():
    image = Image.new('RGB', (1024, 768), '#28365c')
    ImageDraw.Draw(image).text((910, 130), '20', fill='white', anchor='lt',
        font=font('C:/Windows/Fonts/arialbd.ttf', 25))
    original = prepare_frame(image, LAYOUT)
    truth = {'numbers': [{'value': 20, 'role': 'unknown', 'label': None, 'view': 'table'}],
        'number_views': [{'value': 20, 'role': 'unknown', 'label': None, 'allowed_views': ['table']}]}
    labelled, expected, audit = bet_control(original, truth)
    assert truth['numbers'][0]['role'] == 'unknown' and truth['numbers'][0]['label'] is None
    assert expected['numbers'][0] == {'value': 20, 'role': 'ui', 'label': 'BET', 'view': 'table'}
    assert expected['number_views'][0]['allowed_views'] == ['table']
    assert audit['all_other_table_pixels_unchanged']
    native_view_audit(labelled)
    a = request_payload(original, 'structured-card-limit-local')
    e = request_payload(labelled, 'structured-card-limit-local')
    assert a['systemInstruction'] == e['systemInstruction']
    assert a['generationConfig'] == e['generationConfig']
    text = lambda p: [i['text'] for i in p['contents'][0]['parts'] if 'text' in i]
    assert text(a) == text(e)
    with Image.open(BytesIO(labelled.table_png)) as raw:
        assert raw.crop((910, 130, 970, 165)).tobytes() == image.crop((910, 130, 970, 165)).tobytes()
