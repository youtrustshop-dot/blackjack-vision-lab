"""New owned v2 numeric/visibility development corpus, never a training set.

No provider assets. Distinct physical engine session, seed and font/palette per
partition. All indices/pips are rendered as evidence masks; they are geometric
visibility candidates, not a claim of independently measured human legibility.
The runner cannot evaluate final_holdout. Historical files are never rewritten.
"""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

from bjlab.engine import hand_value
from bjlab.state_reader import prepare_frame
from validation.tools.api_reader_tournament import native_record, PERCEPTION_FILES, file_hash
from validation.tools.independent_tournament import scenario_timeline
from validation.tools.stress_lab import LAYOUT, SIZE, SUITS

ROOT = Path(__file__).resolve().parents[2]
PARTITIONS = {
    'development': (5100503, 'owned-v2-verdant-arial', 'C:/Windows/Fonts/arialbd.ttf', '#106049', '#fffdf5'),
    'validation': (5100521, 'owned-v2-indigo-calibri', 'C:/Windows/Fonts/calibrib.ttf', '#253f61', '#f6f6fd'),
    'final_holdout': (5100599, 'owned-v2-plum-cambria', 'C:/Windows/Fonts/cambriab.ttf', '#493551', '#fff6ea'),
}
CASES = ('clean-ui', 'labelled-totals', 'unlabelled-number', 'overlap', 'rotation',
         'faded-blur', 'clipping-alt-index', 'popup-unreadable', 'disabled-controls',
         'hard-negatives', 'empty', 'identical-new-round')
API_CASES = ('clean-ui', 'labelled-totals', 'unlabelled-number', 'overlap', 'rotation', 'popup-unreadable')
SYMBOL_FONT = 'C:/Windows/Fonts/seguisym.ttf'


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def font(path, size):
    if not Path(path).is_file():
        raise FileNotFoundError('Declared artwork font unavailable; do not silently reuse a different family.')
    return ImageFont.truetype(path, size)


def card_tile(card, font_path, paper, angle=0, clip=False):
    image = Image.new('RGBA', (112, 156)); draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 111, 155), 7, fill=paper, outline='#9095a0')
    masks = {key: Image.new('L', image.size) for key in ('top_rank', 'bottom_rank', 'top_suit', 'bottom_suit', 'pip')}
    if card.get('face_down'):
        draw.rounded_rectangle((5, 5, 106, 150), 5, fill='#2765a5')
        for y in range(10, 150, 7): draw.line((8, y, 103, y), fill='#b0c8e0')
    else:
        color = '#c42a38' if card['suit'] in 'HD' else '#172028'
        specs = [('top_rank', card['rank'], (8, 8), 29, 'lt'),
                 ('top_suit', SUITS[card['suit']], (9, 42), 25, 'lt'),
                 ('bottom_rank', card['rank'], (102, 142), 19, 'rb'),
                 ('bottom_suit', SUITS[card['suit']], (100, 112), 18, 'rb'),
                 ('pip', SUITS[card['suit']], (57, 83), 43, 'mm')]
        for key, text, position, size, anchor in specs:
            printed_font = font(SYMBOL_FONT if key.endswith('suit') or key == 'pip' else font_path, size)
            draw.text(position, text, font=printed_font, fill=color, anchor=anchor)
            ImageDraw.Draw(masks[key]).text(position, text, font=printed_font, fill=255, anchor=anchor)
    original_ink = {k: int(np.count_nonzero(np.asarray(mask))) for k, mask in masks.items()}
    if clip:
        ImageDraw.Draw(image).rectangle((0, 0, 27, 155), fill=(0, 0, 0, 0))
        for mask in masks.values(): ImageDraw.Draw(mask).rectangle((0, 0, 27, 155), fill=0)
    if angle:
        image = image.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        masks = {k: v.rotate(angle, Image.Resampling.NEAREST, expand=True) for k, v in masks.items()}
        original_ink = {k: int(np.count_nonzero(np.asarray(mask))) for k, mask in masks.items()}
    return image, masks, original_ink


def render(stage, case, family):
    _, _, font_path, felt, paper = family
    image = Image.new('RGB', SIZE, felt); draw = ImageDraw.Draw(image)
    ui_font = font('C:/Windows/Fonts/arialbd.ttf', 25)
    draw.rectangle((0, 0, 1023, 76), fill='#141e2b')
    draw.text((35, 25), 'OWNED CARD RESEARCH TABLE', font=ui_font, fill='#dcc382')
    draw.text((44, 114), 'DEALER', font=ui_font, fill='#ffffff')
    draw.text((44, 397), 'PLAYER', font=ui_font, fill='#ffffff')
    layers = []
    for zone, y in [('dealer', 150), ('player:0', 440)]:
        cards = [c for c in stage['cards'] if c['zone'] == zone]
        spacing = 43 if case == 'overlap' else 123
        origin = 395-len(cards)*spacing//2
        for index, card in enumerate(cards):
            angle = (19 if index % 2 == 0 else -19) if case == 'rotation' else 0
            tile, masks, original_ink = card_tile(card, font_path, paper, angle, case == 'clipping-alt-index' and index == 0 and zone == 'player:0')
            x = origin+index*spacing
            alpha = np.asarray(tile.getchannel('A')) > 0
            ys, xs = np.where(alpha)
            for old in layers:
                for key, mask in list(old['masks'].items()):
                    arr = np.asarray(mask).copy(); section = arr[y:y+tile.height, x:x+tile.width]
                    section[alpha] = 0; old['masks'][key] = Image.fromarray(arr)
                body = np.asarray(old['body']).copy(); body[y:y+tile.height, x:x+tile.width][alpha] = 0
                old['body'] = Image.fromarray(body)
            image.paste(tile, (x, y), tile)
            body = Image.new('L', SIZE); body.paste(tile.getchannel('A'), (x, y))
            full = {k: Image.new('L', SIZE) for k in masks}
            for k, mask in masks.items():
                full[k].paste(mask, (x, y))
            layers.append({'card': card, 'body': body, 'masks': full, 'ink': original_ink,
                'original_body_pixels': len(xs), 'box': [x+int(xs.min()), y+int(ys.min()), int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)]})
    draw = ImageDraw.Draw(image)
    if case == 'popup-unreadable':
        rectangle = (278, 446, 377, 590)
        draw.rounded_rectangle(rectangle, 5, fill='#33383d', outline='#d0d5da')
        draw.text((277, 482), 'MENU', font=font('C:/Windows/Fonts/arialbd.ttf', 17), fill='#ffffff')
        for layer in layers:
            ImageDraw.Draw(layer['body']).rectangle(rectangle, fill=0)
            for mask in layer['masks'].values(): ImageDraw.Draw(mask).rectangle(rectangle, fill=0)
    if case == 'hard-negatives':
        # Real-looking preview cards outside the declared dealer/player ROIs.
        for i, (rank, suit) in enumerate([('A', 'H'), ('7', 'C')]):
            tile, _, _ = card_tile({'rank': rank, 'suit': suit}, font_path, paper)
            image.paste(tile.resize((40, 56)), (875+i*48, 675))
        draw.text((871, 645), 'OTHER GAMES', font=font('C:/Windows/Fonts/arialbd.ttf', 14), fill='#ffffff')
    numbers = []
    def number(value, role, label, position):
        text = f'{label} {value}' if label else str(value)
        draw.text(position, text, font=ui_font, fill='#ffffff', anchor='lt')
        bbox = draw.textbbox(position, text, font=ui_font, anchor='lt')
        numbers.append({'value': value, 'role': role, 'label': label, 'view': 'table',
            'box': [bbox[0]/1024, bbox[1]/768, (bbox[2]-bbox[0])/1024, (bbox[3]-bbox[1])/768]})
    number(20, 'ui', 'SESSION', (804, 84))
    if case == 'unlabelled-number': number(20, 'unknown', None, (910, 130))
    if case == 'labelled-totals':
        for zone, name, pos in [('dealer', 'DEALER TOTAL', (690, 265)), ('player:0', 'PLAYER TOTAL', (690, 555))]:
            visible = [c['rank'] for c in stage['cards'] if c['zone'] == zone and not c.get('face_down')]
            number(hand_value(visible)[0], 'dealer_total' if zone == 'dealer' else 'player_total', name, pos)
    phase = stage['phase']
    controls = sorted(set(stage.get('controls', [])) & {'hit', 'stand', 'double', 'split', 'surrender'}) if phase == 'player' else []
    if case == 'disabled-controls': phase, controls = 'settled', []
    labels = [('HIT', 'hit'), ('STAND', 'stand'), ('DOUBLE', 'double')]
    if phase == 'waiting': labels = [('DEAL', None)]
    elif phase == 'settled': labels = [('NEW HAND', None)] + (labels if case == 'disabled-controls' else [])
    elif phase == 'dealer': labels = [('DEALER TURN', None)]
    for i, (label, action) in enumerate(labels):
        x = 125+i*185
        enabled = action in controls if action else True
        draw.rounded_rectangle((x, 663, x+160, 726), 9, fill='#ead292' if enabled else '#617078')
        draw.text((x+80, 694), label, font=ui_font, fill='#151b25' if enabled else '#a9afb4', anchor='mm')
    if case == 'faded-blur': image = ImageEnhance.Contrast(image).enhance(.42).filter(ImageFilter.GaussianBlur(.9))
    observed, detail = [], []
    for layer in layers:
        card = layer['card']; body_pixels = int(np.count_nonzero(np.asarray(layer['body'])))
        fractions = {k: int(np.count_nonzero(np.asarray(mask)))/layer['ink'][k] if layer['ink'][k] else 0
                     for k, mask in layer['masks'].items()}
        rank_visible = max(fractions['top_rank'], fractions['bottom_rank']) >= .97
        suit_visible = max(fractions['top_suit'], fractions['bottom_suit'], fractions['pip']) >= .97
        if not body_pixels: visibility = 'absent_from_pixels'
        elif card.get('face_down'): visibility = 'covered'
        elif rank_visible and suit_visible: visibility = 'readable'
        elif rank_visible or suit_visible: visibility = 'partial'
        else: visibility = 'unreadable'
        if visibility != 'absent_from_pixels':
            observed.append({'zone': card['zone'], 'rank': card.get('rank') if rank_visible else None,
                'suit': card.get('suit') if suit_visible else None, 'visibility': visibility})
        detail.append({'physical_instance': card['id'], 'zone': card['zone'], 'presence': visibility,
            'box': layer['box'], 'body_fraction': body_pixels/layer['original_body_pixels'], 'glyph_fractions': fractions,
            'visibility_scope': 'all rendered index/pip ink; geometric proxy; development visual audit required'})
    truth = {'cards': observed, 'table_state': 'cards_present' if observed else 'empty',
        'phase': phase, 'controls': controls, 'numbers': numbers, 'unknown_fields': [], 'blockers': []}
    return image, truth, detail


def generate(output, reader_manifest):
    # Font fallback/tofu can make perfect masks certify nonexistent suit ink.
    # Reject a font lacking four distinct suit symbols before any data is saved.
    suit_masks = [card_tile({'rank':'7','suit':s},PARTITIONS['development'][2],'white')[1]['pip'].tobytes() for s in SUITS]
    if len(set(suit_masks)) != 4:
        raise ValueError('Symbol font does not render four distinct suits.')
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    reader_manifest = Path(reader_manifest).resolve()
    freeze = {'schema': 2, 'contract': 'grounded-r1-v2', 'baseline_commit': '4148a08218ec40c752a2d4f1fd215bc4f21c4b3d',
        'reader_manifest': str(reader_manifest), 'reader_manifest_sha256': file_hash(reader_manifest),
        'perception_hashes': {p: file_hash(ROOT/p) for p in PERCEPTION_FILES}, 'partitions': {},
        'split_rule': 'physical session, seed, artwork font/palette grouped before evaluation',
        'shared_renderer_components': ['layout','control font','audited Segoe UI Symbol suit glyphs'],
        'symbol_font': SYMBOL_FONT, 'symbol_font_sha256': file_hash(SYMBOL_FONT),
        'final_holdout': 'sealed_not_evaluated', 'historical_scores': 'frozen_never_rescored'}
    for split, family in PARTITIONS.items():
        directory = output/split; directory.mkdir()
        stages = scenario_timeline(family[0]); decisions = [s for s in stages if s['phase'] == 'player']
        records, oracle, evidence = [], {}, {}
        for index, case in enumerate(CASES):
            stage = decisions[index % len(decisions)]
            if case == 'identical-new-round': stage = next(s for s in decisions if s['scenario'] == 'identical_new_round')
            if case == 'empty': stage = next(s for s in stages if s['phase'] == 'waiting')
            if case == 'disabled-controls': stage = next(s for s in stages if s['phase'] == 'settled' and s['scenario'] == 'hit_bust')
            image, truth, detail = render(stage, case, family)
            record = native_record(directory, case, prepare_frame(image, LAYOUT), family=family[1], seed=family[0],
                condition=case, evidence_kind='new-owned-synthetic-v2', independent_session=family[0])
            record['split'] = split; records.append(record); oracle[case] = truth; evidence[case] = detail
        save(directory/'frames.json', records); save(directory/'oracle.json', oracle); save(directory/'visibility-evidence.json', evidence)
        freeze['partitions'][split] = {name: file_hash(directory/name) for name in ('frames.json', 'oracle.json', 'visibility-evidence.json')}
        freeze['partitions'][split].update(seed=family[0], family=family[1], inputs=len(records),
            status='sealed_not_evaluated' if split == 'final_holdout' else 'frozen_before_evaluation')
    save(output/'freeze.json', freeze)
    return freeze


def checked_inputs(output, split):
    from validation.tools.state_reader_comparison import load_frame
    if split not in ('development', 'validation'):
        raise PermissionError('Final holdout is sealed; this runner cannot evaluate it.')
    directory = Path(output)/split; freeze = json.loads((Path(output)/'freeze.json').read_text())
    if file_hash(freeze['reader_manifest']) != freeze['reader_manifest_sha256']:
        raise ValueError('Frozen reader manifest changed.')
    if {p: file_hash(ROOT/p) for p in PERCEPTION_FILES} != freeze['perception_hashes']:
        raise ValueError('Frozen perception source changed.')
    for name in ('frames.json', 'oracle.json', 'visibility-evidence.json'):
        if file_hash(directory/name) != freeze['partitions'][split][name]: raise ValueError('Frozen partition changed.')
    records = json.loads((directory/'frames.json').read_text()); frames = []
    for record in records:
        for image in record['images']:
            if file_hash(directory/image['file']) != image['sha256']: raise ValueError('Native pixels changed.')
        frames.append((record, load_frame(directory, record)))
    return freeze, frames, json.loads((directory/'oracle.json').read_text())
