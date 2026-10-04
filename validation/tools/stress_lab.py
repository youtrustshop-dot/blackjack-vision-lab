"""Offline synthetic session laboratory. No provider assets, API or oracle input.

Generate continuous VP8 video and separate evaluator truth, then decode the
video into the unchanged LiveObserver. These are development simulations only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from bjlab.datasets import card_font
from bjlab.engine import Rules, hand_value
from bjlab.simulator import BlackjackSession

SIZE = (1024, 768)
FPS = 12
LAYOUT = {'table': (0, 0, 1, 1), 'dealer': (.08, .16, .84, .29),
          'player:0': (.08, .53, .84, .29), 'controls': (.05, .85, .9, .12)}
PROFILES = {
    'clean': dict(angle=0, spacing=120, contrast=1., blur=0, clip=False, cover=False, theme='green'),
    'overlap': dict(angle=0, spacing=39, contrast=1., blur=0, clip=False, cover=False, theme='teal'),
    'rotation': dict(angle=19, spacing=95, contrast=1., blur=0, clip=False, cover=False, theme='navy'),
    'faded': dict(angle=0, spacing=120, contrast=.35, blur=.65, clip=False, cover=False, theme='green'),
    'clipped': dict(angle=0, spacing=65, contrast=1., blur=0, clip=True, cover=False, theme='teal'),
    'covered': dict(angle=9, spacing=55, contrast=.75, blur=.3, clip=False, cover=True, theme='navy'),
}
COLORS = {'green': '#125e42', 'teal': '#075960', 'navy': '#192840'}
SUITS = dict(zip('SHDC', '♠♥♦♣'))


def save_json(path, document):
    Path(path).write_text(json.dumps(document, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def rules():
    # Single hand in the first visual corpus: existing calibrated reader has
    # exactly one player ROI. Bulk engine stress separately includes splitting.
    return Rules(decks=8, double_rule='none', max_split_hands=1, surrender='none')


def choose(game):
    available = game.available_actions()
    if 'decline_insurance' in available: return 'decline_insurance'
    if 'continue' in available: return 'continue'
    hand = game.hands[game.active_hand]
    return 'hit' if hand.value[0] < 17 and 'hit' in available else 'stand'


def timeline(seed, rounds):
    """Engine truth drives rendering only; every transition has actual pixels."""
    game = BlackjackSession(rules(), seed=seed, session_id=f'synthetic-{seed}', bankroll=100000)
    stages = []

    def add(snapshot, phase, duration, cards=None):
        cards = cards if cards is not None else [
            dict(c, zone=zone) for zone, values in
            [('dealer', snapshot['dealer']['cards']), ('player:0', snapshot['hands'][0]['cards'])]
            for c in values]
        stages.append({'round': game.round_id, 'phase': phase, 'duration': duration,
                       'cards': cards})

    for _ in range(rounds):
        add(None, 'waiting', .8, [])
        snapshot = game.deal()
        player = [dict(c, zone='player:0') for c in snapshot['hands'][0]['cards']]
        dealer = [dict(c, zone='dealer') for c in snapshot['dealer']['cards']]
        # Deal in visible order. Dealer hole and future reveals never expose a
        # hidden rank in either the video or per-frame visible-card annotations.
        dealt = [player[0], dealer[0], player[1]]
        if len(dealer) > 1: dealt.append({'id': dealer[1]['id'], 'face_down': True, 'zone': 'dealer'})
        for i in range(len(dealt)): add(snapshot, 'dealing', .25, dealt[:i+1])
        while game.phase in ('player', 'insurance', 'early_surrender'):
            add(snapshot, 'player' if game.phase == 'player' else 'unknown', 2.0)
            action = choose(game)
            snapshot = game.action(action)
            if game.phase != 'settled': add(snapshot, 'dealing', .35)
        # Explicit reveal/draw progression followed by outcome and table clear.
        dealer = [dict(c, zone='dealer') for c in snapshot['dealer']['cards']]
        player = [dict(c, zone='player:0') for c in snapshot['hands'][0]['cards']]
        for i in range(1, len(dealer)+1): add(snapshot, 'dealer', .5, player+dealer[:i])
        add(snapshot, 'settled', 1.5)
        add(None, 'waiting', .8, [])
    return stages


def tile(card, profile, index):
    image = Image.new('RGBA', (112, 156))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 111, 155), 8, fill='#fffdf5', outline='#888888', width=1)
    corner = Image.new('L', image.size)
    if card.get('face_down'):
        draw.rounded_rectangle((5, 5, 106, 150), 5, fill='#2765a5')
        for y in range(10, 151, 7): draw.line((7, y, 105, y), fill='#b0c8e0', width=1)
    else:
        rank, suit = card['rank'], card['suit']
        color = '#c42a38' if suit in 'HD' else '#172028'
        draw.text((8, 8), rank, font=card_font(29), fill=color, anchor='lt')
        draw.text((9, 42), SUITS[suit], font=card_font(25), fill=color, anchor='lt')
        draw.text((57, 89), SUITS[suit], font=card_font(48), fill=color, anchor='mm')
        # Opposite corner is actual card artwork, not an evaluator code.
        draw.text((102, 143), rank, font=card_font(18), fill=color, anchor='rb')
        # Measure printed glyph ink, not whitespace in a coarse corner box.
        # Otherwise a neighbouring card covering blank right margin falsely
        # marks a fully exposed rank/suit as unreadable.
        corner_draw = ImageDraw.Draw(corner)
        corner_draw.text((8, 8), rank, font=card_font(29), fill=255, anchor='lt')
        corner_draw.text((9, 42), SUITS[suit], font=card_font(25), fill=255, anchor='lt')
    angle = profile['angle'] * (1 if index % 2 == 0 else -1)
    if angle:
        image = image.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        corner = corner.rotate(angle, Image.Resampling.NEAREST, expand=True)
    return image, corner


def render(stage, profile, frame_index=0):
    background = COLORS[profile['theme']]
    image = Image.new('RGB', SIZE, background)
    draw = ImageDraw.Draw(image)
    draw.text((512, 40), 'CARD LAB · SYNTHETIC BLACKJACK', font=card_font(24), fill='#dbc491', anchor='mm')
    draw.text((512, 365), 'BLACKJACK PAYS 3 TO 2', font=card_font(27), fill='#487d72', anchor='mm')
    draw.text((45, 106), 'DEALER', font=card_font(18), fill='#d6d6c8')
    draw.text((45, 395), 'PLAYER', font=card_font(18), fill='#d6d6c8')
    draw.text((990, 108), '20', font=card_font(25), fill='#dbc491', anchor='rt')
    # Distractor remains outside declared card zones. A fixed badge never
    # provides round IDs, card identities, shoe state or machine-readable truth.
    layers = []
    for zone, top in [('dealer', 142), ('player:0', 436)]:
        cards = [c for c in stage['cards'] if c['zone'] == zone]
        left = (SIZE[0] - (len(cards)-1)*profile['spacing']-112)//2
        if profile['clip'] and zone == 'player:0': left = -25
        for i, card in enumerate(cards):
            artwork, corner = tile(card, profile, i)
            x, y = left+i*profile['spacing'], top
            # Short visual movement during deal; does not encode IDs.
            if stage['phase'] == 'dealing': x += max(0, 12-frame_index)*3
            body_mask = Image.new('L', SIZE); body_mask.paste(artwork.getchannel('A'), (x, y))
            corner_mask = Image.new('L', SIZE); corner_mask.paste(corner, (x, y))
            alpha = np.asarray(body_mask) > 127
            for previous in layers:
                previous['body'][alpha] = False; previous['corner'][alpha] = False
            image.paste(artwork, (x, y), artwork)
            layers.append({'card': card, 'body': alpha.copy(), 'corner': np.asarray(corner_mask)>127,
                           'body_area': int((np.asarray(artwork.getchannel('A'))>127).sum()),
                           'corner_area': int((np.asarray(corner)>127).sum())})
    if profile['cover'] and stage['cards']:
        rectangle = (425, 425, 545, 595)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(rectangle, 10, fill='#25394d', outline='#d8c797')
        draw.text((485, 498), 'OVERLAY', font=card_font(17), fill='white', anchor='mm')
        for layer in layers:
            layer['body'][425:596,425:546] = False; layer['corner'][425:596,425:546] = False
    draw = ImageDraw.Draw(image)
    controls = {'player': ['HIT', 'STAND'], 'waiting': ['DEAL'], 'settled': ['NEW HAND'],
                'dealer': ['DEALER TURN'], 'dealing': ['DEALING'], 'unknown': ['INSURANCE']}[stage['phase']]
    for i, label in enumerate(controls):
        x = 250+i*220
        draw.rounded_rectangle((x, 664, x+200, 710), 10, fill='#203229', outline='#c3aa78')
        draw.text((x+100, 686), label, font=card_font(22), fill='#f0dcad', anchor='mm')
    if profile['contrast'] != 1: image = ImageEnhance.Contrast(image).enhance(profile['contrast'])
    if profile['blur']: image = image.filter(ImageFilter.GaussianBlur(profile['blur']))
    truth = []
    for layer in layers:
        card = layer['card']; body = layer['body']; corner = layer['corner']
        ys, xs = np.where(body)
        fraction = float(corner.sum()/max(1, layer['corner_area']))
        hidden = bool(card.get('face_down'))
        presence = 'absent_from_pixels' if not len(xs) else 'covered' if hidden else 'readable' if fraction >= .85 else 'unreadable'
        truth.append({'card_id': card['id'], 'zone': card['zone'], 'presence': presence,
                      'rank': card.get('rank') if presence == 'readable' else None,
                      'suit': card.get('suit') if presence == 'readable' else None,
                      'physical_rank': card.get('rank') if not hidden else None,
                      'corner_visible_fraction': fraction,
                      'body_visible_fraction': float(body.sum()/max(1, layer['body_area'])),
                      'bbox': [int(xs.min()), int(ys.min()), int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)] if len(xs) else None})
    return image, truth


def generate(output, rounds=3, seed=4100410, profiles=None):
    if not 1 <= rounds <= 200: raise ValueError('Visual runs support 1..200 rounds; use bulk for large engine runs')
    selected = profiles or list(PROFILES)
    if len(set(selected)) != len(selected) or any(p not in PROFILES for p in selected): raise ValueError('Invalid profiles')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    stages = timeline(seed, rounds)
    manifest = {'schema': 1, 'renderer_version': 'synthetic-stress-v2-glyph-visibility',
                'generator_source_sha256': digest(__file__),
                'kind': 'own-synthetic-continuous-video', 'partition': 'development',
                'seed': seed, 'rounds': rounds, 'source_size': list(SIZE), 'fps': FPS,
                'layout': LAYOUT, 'rules': asdict(rules()), 'sessions': [],
                'scope': 'Same engine run rendered in six conditions, not independent provider sessions',
                'api_requests': 0, 'provider_assets': False}
    for name in selected:
        video = output/f'{name}.webm'
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'VP80'), FPS, SIZE)
        if not writer.isOpened(): raise RuntimeError('VP8 encoder unavailable; no video evidence produced')
        rows = []; frame = 0; exposed = {}
        try:
            for stage in stages:
                cached = None
                for i in range(round(stage['duration']*FPS)):
                    if cached is None or stage['phase']=='dealing':
                        cached = render(stage, PROFILES[name], i)
                    image, visible = cached
                    writer.write(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR))
                    for card in visible:
                        if card['presence'] != 'absent_from_pixels' and card['physical_rank']:
                            exposed[card['card_id']] = card['physical_rank']
                    rows.append({'frame': frame, 'timestamp_ms': frame*1000/FPS, 'round': stage['round'],
                                 'phase': stage['phase'], 'cards': visible, 'seen': dict(exposed)})
                    if frame == 20: image.save(output/f'{name}.jpg')
                    frame += 1
        finally: writer.release()
        truth = output/f'{name}.truth.json'; save_json(truth, rows)
        manifest['sessions'].append({'profile': name, 'parameters': PROFILES[name], 'frames': frame,
                                    'video': video.name, 'video_sha256': digest(video),
                                    'truth': truth.name, 'truth_sha256': digest(truth)})
    save_json(output/'manifest.json', manifest)
    cards = ''.join(f'<article><h2>{s["profile"].title()}</h2><video controls loop preload="metadata" src="{s["video"]}"></video></article>' for s in manifest['sessions'])
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Card Lab · Stress sessions</title><style>body{background:#11151d;color:#e4e8ef;font:17px system-ui;margin:36px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:22px}article{background:#1b2230;padding:20px;border-radius:14px}video{width:100%}p{max-width:950px;color:#b4c0d2}</style><h1>Blackjack visual stress laboratory</h1><p>Original synthetic development videos. Same game, different visual conditions. Cards and phase truth stay outside the reader. These clips do not certify performance on external websites or financial returns. Select a video and press Play.</p><main>'+cards+'</main>', encoding='utf-8')
    return manifest


def match_cards(expected, detected):
    """Geometry/zone association only; never match using rank or suit labels."""
    remaining = set(range(len(detected))); pairs = []; missed = []
    for card in expected:
        box = card['bbox']; cx, cy = box[0]+box[2]/2, box[1]+box[3]/2
        options = []
        for i in remaining:
            d = detected[i]; b = d['bbox']
            if d['zone'] != card['zone']: continue
            dx, dy = b[0]+b[2]/2, b[1]+b[3]/2
            distance = ((dx-cx)/max(20, box[2]))**2+((dy-cy)/max(20, box[3]))**2
            if distance <= 1.0: options.append((distance, i))
        if not options: missed.append(card); continue
        _, i = min(options); remaining.remove(i); pairs.append((card, detected[i]))
    return pairs, missed, [detected[i] for i in remaining]


def run(manifest_path, output, *, context_challenger=False, profiles=None):
    from bjlab.advice import recommend
    from bjlab.live import LiveObserver
    from bjlab.vision_diagnostics import candidate_revision
    path = Path(manifest_path); manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('kind') != 'own-synthetic-continuous-video' or manifest.get('partition') != 'development':
        raise ValueError('This runner accepts development synthetic videos only')
    root=Path(__file__).resolve().parents[2]
    source_paths=['validation/tools/stress_lab.py','bjlab/live.py','bjlab/visible_phase.py','bjlab/corner_vision.py']
    source_hashes={name:digest(root/name) for name in source_paths}
    reports = []
    for session in manifest['sessions']:
        if profiles is not None and session['profile'] not in profiles: continue
        video, truth_path = path.parent/session['video'], path.parent/session['truth']
        if digest(video) != session['video_sha256'] or digest(truth_path) != session['truth_sha256']:
            raise ValueError('Frozen input hash mismatch')
        truth = json.loads(truth_path.read_text(encoding='utf-8'))
        observer = LiveObserver(Rules(**manifest['rules']), layout=manifest['layout'], samples=100,
                                fresh_shoe=True, manual_turn=False, context_challenger=context_challenger)
        cap = cv2.VideoCapture(str(video)); index = 0; sampled = 0; metrics = Counter(); times = []; traces = []
        next_ms = 0.; opportunities = {}; inventory_max = 0; observed_rounds = set(); rc_max = 0
        boundary_rounds = Counter(); exposure_matches = Counter(); exposure_wrong = 0
        exposure_unmatched = 0; event_identity = {}; final_drift = {}
        try:
            while True:
                ok, pixels = cap.read()
                if not ok: break
                if tuple(pixels.shape[1::-1]) != tuple(manifest['source_size']): raise ValueError('Source size changed')
                truth_index=index; timestamp = index*1000/manifest['fps']; index += 1
                if timestamp+1e-6 < next_ms: continue
                next_ms += 350
                started = time.perf_counter()
                # Sole recognition call: decoded RGB, sequence, capture time.
                result = observer.process(Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)), sampled, 1+timestamp/1000)
                elapsed = (time.perf_counter()-started)*1000; times.append(elapsed); sampled += 1
                # Evaluator truth is accessed only AFTER recognition returns.
                label=truth[truth_index]
                expected = [c for c in label['cards'] if c['presence'] != 'absent_from_pixels']
                for event in result['events']:
                    payload=event['payload']; kind=event['kind']
                    if kind=='ROUND_STARTED':
                        if expected: boundary_rounds[label['round']]+=1
                        else: metrics['false_round_start']+=1
                    if kind not in ('CARD_CONFIRMED','CARD_REVEALED') or payload.get('rank') is None: continue
                    # Diagnostic geometric event association, never inference input.
                    matched,_,_=match_cards(expected,[payload])
                    identity=event_identity.get(payload['card_id'])
                    if matched:
                        identity=matched[0][0]['card_id']; event_identity[payload['card_id']]=identity
                    if identity is None: exposure_unmatched+=1
                    elif label['seen'].get(identity)!=payload['rank']: exposure_wrong+=1
                    else: exposure_matches[identity]+=1
                pairs, missed, extra = match_cards(expected, result['detections'])
                frame = Counter(localization_missed=len(missed), localization_extra=len(extra))
                for card, detection in pairs:
                    if card['presence'] == 'readable':
                        frame['rank_correct' if detection['rank'] == card['rank'] else 'rank_unknown' if detection['rank'] is None else 'rank_wrong'] += 1
                        frame['suit_correct' if detection['suit'] == card['suit'] else 'suit_unknown' if detection['suit'] is None else 'suit_wrong'] += 1
                    elif card['presence'] == 'covered':
                        frame['covered_correct' if detection.get('face_down') and detection['rank'] is None else 'covered_wrong'] += 1
                    elif detection['rank'] is not None: frame['unreadable_rank_claim'] += 1
                frame['readable_expected'] = sum(c['presence']=='readable' for c in expected)
                phase = label['phase']
                frame['phase_correct' if result['phase'] == phase else 'phase_wrong_or_unknown'] += 1
                expected_inventory = Counter(label['seen'].values())
                actual_inventory = Counter(result['state']['known_rank_counts'])
                final_drift={k:actual_inventory[k]-expected_inventory[k] for k in ('A','2','3','4','5','6','7','8','9','10','J','Q','K')}
                error = sum(abs(expected_inventory[k]-actual_inventory[k]) for k in set(expected_inventory)|set(actual_inventory))
                inventory_max = max(inventory_max, error)
                expected_rc = sum((1 if r in ('2','3','4','5','6') else -1 if r in ('10','J','Q','K','A') else 0)*n
                                  for r,n in expected_inventory.items())
                rc_max = max(rc_max,abs(result['observed_running_count']-expected_rc))
                exact = not missed and not extra and all(c['presence']!='readable' or d['rank']==c['rank'] for c,d in pairs)
                frame['rank_presence_state_correct'] += int(exact)
                if result['count_reliable'] and error: frame['false_reliable_count'] += 1
                if result['round']: observed_rounds.add(result['round'])
                expected_action = None
                if phase == 'player' and all(c['presence']=='readable' for c in expected if c['zone']=='player:0'):
                    player = [c['rank'] for c in expected if c['zone']=='player:0']
                    dealer = [c['rank'] for c in expected if c['zone']=='dealer' and c['presence']=='readable']
                    if len(player)>=2 and dealer:
                        expected_action = recommend(player,dealer[0],Rules(**manifest['rules']))['basic_action']
                advice_correct = bool(result.get('advice') and exact and phase=='player' and expected_action
                                      and result['advice'].get('basic_action')==expected_action)
                if phase == 'player':
                    signature = (label['round'], tuple(c['card_id'] for c in expected))
                    opportunity = opportunities.setdefault(signature, {'first_ms': timestamp, 'first_usable_ms': None})
                    if advice_correct and result['phase']=='player' and opportunity['first_usable_ms'] is None:
                        opportunity['first_usable_ms'] = timestamp+elapsed
                if result.get('advice') and not advice_correct: frame['false_or_stale_advice'] += 1
                if result['gate']['solver_allowed'] and not advice_correct: frame['false_actionable_state'] += 1
                metrics.update(frame)
                traces.append({'timestamp_ms': timestamp, 'truth_phase': phase, 'metrics': dict(frame),
                               'inventory_l1': error, 'report': result})
        finally: cap.release(); observer.stop()
        if index != session['frames'] or index != len(truth): raise ValueError('Incomplete decode or truth timeline')
        target = Path(output); target.parent.mkdir(parents=True, exist_ok=True)
        save_json(target.parent/f'{session["profile"]}.trace.json', traces)
        reports.append({'profile': session['profile'], 'decoded_frames': index, 'sampled_frames': sampled,
                        'metrics': dict(metrics), 'inventory_max_l1': inventory_max,
                        'inventory_final_l1': traces[-1]['inventory_l1'], 'observed_rc_max_abs_error': rc_max,
                        'recognized_rounds': len(observed_rounds), 'decision_opportunities': len(opportunities),
                        'timely_usable_opportunities': sum(o['first_usable_ms'] is not None and o['first_usable_ms']-o['first_ms']<=1500 for o in opportunities.values()),
                        'first_usable_latency_ms': [o['first_usable_ms']-o['first_ms'] if o['first_usable_ms'] is not None else None for o in opportunities.values()],
                        'round_boundaries': {'expected': len({r['round'] for r in truth if r['cards']}),
                            'matched':len(boundary_rounds), 'duplicate':sum(max(0,n-1) for n in boundary_rounds.values()),
                            'false':metrics['false_round_start']},
                        'exposure_events': {'expected':len(truth[-1]['seen']),
                            'matched_unique':len(exposure_matches),
                            'missing':len(set(truth[-1]['seen'])-set(exposure_matches)),
                            'duplicate':sum(max(0,n-1) for n in exposure_matches.values()),
                            'wrong_rank':exposure_wrong,'unmatched_geometry':exposure_unmatched,
                            'association_scope':'diagnostic zone/center association; not independently verified identity'},
                        'inventory_final_drift_by_rank':final_drift,
                        'offline_processing_ms': {'p50': float(np.percentile(times,50)), 'p95': float(np.percentile(times,95))}})
        print(json.dumps(reports[-1]), flush=True)
    receipt = {'schema': 1, 'scope': manifest['kind'], 'manifest_sha256': digest(path),
               'candidate': candidate_revision(Path(__file__).resolve().parents[2]),
               'reader': 'unchanged calibrated card detector + visible-controls-temporal-v1' if context_challenger else 'unchanged default calibrated LiveObserver; manual turn disabled',
               'runner_sha256': digest(__file__), 'source_hashes':source_hashes,
               'frozen_generator_sha256':manifest.get('generator_source_sha256'),
               'original_provider_videos': 0, 'api_requests': 0,
               'training_performed': False, 'reader_promoted': False, 'results': reports,
               'timing_scope': 'Offline decoded frame processing, not live capture-to-display',
               'not_measured': ['Independent provider generalization', 'ID switches', 'Exact event-to-card association',
                                'Independent mathematical correctness', 'Profitability']}
    if source_hashes!={name:digest(root/name) for name in source_paths}:
        raise ValueError('Inference/evaluator source changed during the run')
    save_json(output, receipt)
    return receipt


def bulk(rounds, seed=4100499):
    """Large bounded-memory engine stress, not vision training or EV proof."""
    if not 1 <= rounds <= 1_000_000: raise ValueError('Engine batch supports 1..1000000 rounds')
    game = BlackjackSession(Rules(decks=8), seed=seed, session_id='bulk', bankroll=1e9)
    started = time.perf_counter(); actions = Counter(); naturals = busts = 0
    for index in range(rounds):
        game.deal()
        while game.phase in ('player', 'insurance', 'early_surrender'):
            available = game.available_actions()
            if 'split' in available and index % 5 == 0: action = 'split'
            elif 'double' in available and game.hands[game.active_hand].value[0] == 11: action = 'double'
            else: action = choose(game)
            actions[action] += 1; game.action(action)
        if game.phase != 'settled': raise AssertionError('Round did not terminate')
        cards = [*game.shoe.cards, *game.seen.values()]
        if len({c.id for c in cards}) != len(cards): raise AssertionError('Duplicate physical card identity')
        if game.running_count != sum(1 if c.rank in ('2','3','4','5','6') else -1 if c.rank in ('10','J','Q','K','A') else 0 for c in game.seen.values()):
            raise AssertionError('Running count disagrees with unique exposures')
        naturals += any(len(h.cards)==2 and h.value[0]==21 and not h.from_split for h in game.hands)
        busts += any(h.value[0]>21 for h in game.hands)
        # Events are not used by the policy, and retaining 200000 histories is
        # unnecessary for this bounded-memory invariant run.
        game.events.clear()
    return {'scope': 'engine invariant stress; no vision, training or profitability claim', 'seed': seed,
            'rounds': rounds, 'actions': dict(actions), 'rounds_with_natural': naturals,
            'rounds_with_bust': busts, 'elapsed_seconds': time.perf_counter()-started,
            'checks': ['termination', 'physical card identity uniqueness', 'Hi-Lo versus unique exposure inventory'],
            'independent_evaluator': False, 'api_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['generate','run','bulk'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--seed', type=int, default=4100410)
    parser.add_argument('--profiles', default=','.join(PROFILES))
    parser.add_argument('--context-challenger', action='store_true')
    args = parser.parse_args()
    if args.command == 'generate': generate(args.output, args.rounds, args.seed, args.profiles.split(','))
    elif args.command == 'run':
        if args.manifest is None: parser.error('--manifest required')
        run(args.manifest, args.output, context_challenger=args.context_challenger, profiles=args.profiles.split(','))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result = bulk(args.rounds, args.seed); save_json(args.output, result); print(json.dumps(result))


if __name__ == '__main__': main()
