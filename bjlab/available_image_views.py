"""Opt-in Gemini research request binding; no output repair or live wiring.

Card zone and numeric source image are different concepts. Restrict the latter
to names in the actual, byte-checked image packet, not the calibrated layout.
The global wire schema, local validators and semantic gate remain unchanged.
"""
import base64
from copy import deepcopy
import json

from .live_cloud import PROMPT
from .live_state import gemini_structured_schema, wire_schema

REQUEST_PROFILE = 'gemini-available-image-views-v1'
MODES = ('structured-card-limit-local', 'json-mode')
SCHEMA_PREFIX = 'Return exactly one object matching this JSON schema: '


def bind_available_numeric_views(payload, frame, *, mode):
    """Copy a frozen baseline request, changing only instruction/view enum.

    This checks packet identity, not crop origin or actual label/value presence.
    A dishonest prediction still has to pass the unchanged local semantic gate.
    No annotations, expected numbers or hidden engine state enter this builder.
    """
    if mode not in MODES:
        raise ValueError('Only the two declared Gemini research modes are supported.')
    images = tuple(frame.images())
    names = [name for name, _ in images]
    supported = wire_schema()['$defs']['LiveNumber']['properties']['w']['enum']
    if not names or names[0] != 'table' or len(set(names)) != len(names) or (
            any(type(name) is not str or name not in supported for name in names)):
        raise ValueError('One table and unique supported supplied image names are required.')
    contents = payload.get('contents', [])
    if len(contents) != 1 or contents[0].get('role') != 'user':
        raise ValueError('One frozen user image packet is required.')
    parts = contents[0].get('parts', [])
    if len(parts) != 1+2*len(images) or set(parts[0]) != {'text'}:
        raise ValueError('Frozen image packet structure changed.')
    for i, (name, pixels) in enumerate(images):
        label, image = parts[1+2*i:3+2*i]
        expected = {'mimeType': 'image/png', 'data': base64.b64encode(pixels).decode('ascii')}
        if label != {'text': 'View: '+name} or image != {'inlineData': expected}:
            raise ValueError('Supplied image names or bytes differ from the request packet.')
    system = payload.get('systemInstruction', {}).get('parts', [])
    expected_schema = wire_schema() if mode == 'json-mode' else gemini_structured_schema()
    if mode == 'json-mode':
        expected_system = [{'text': PROMPT}, {'text': SCHEMA_PREFIX+
            json.dumps(expected_schema, separators=(',', ':'))}]
        if system != expected_system or payload['generationConfig'].get('responseMimeType') != 'application/json':
            raise ValueError('Frozen JSON-mode contract changed.')
    elif system != [{'text': PROMPT}] or payload['generationConfig'].get('responseFormat', {}).get(
            'text') != {'mimeType': 'APPLICATION_JSON', 'schema': expected_schema}:
        raise ValueError('Frozen structured contract changed.')

    result = deepcopy(payload)
    expected_schema['$defs']['LiveNumber']['properties']['w']['enum'] = names
    supplied = json.dumps(names, separators=(',', ':'))
    instruction = (
        '\nActually supplied image names: '+supplied+'. '
        'c[].z is a card role/region; n[].w is the supplied image name where '
        'both the associated label (if any) and value are visible. Calibrated '
        'dealer/player regions inside table are not separately supplied images. '
        'Use only '+supplied+' for n[].w; never a role name unless that image '
        'was actually supplied. Retain all visible numbers and their observed '
        'labels, including contradictions; never change a printed total to '
        'make it agree with cards.')
    result['systemInstruction']['parts'][0]['text'] = PROMPT+instruction
    if mode == 'json-mode':
        result['systemInstruction']['parts'][1]['text'] = SCHEMA_PREFIX+json.dumps(
            expected_schema, separators=(',', ':'))
    else:
        result['generationConfig']['responseFormat']['text']['schema'] = expected_schema
    return result
