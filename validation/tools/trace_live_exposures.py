"""Trace every pixel-derived exposure against a development session manifest."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PIL import Image
from bjlab.engine import Rules
from bjlab.live import LiveObserver


def run(dataset, output):
    manifest = dataset / 'manifest.json'
    data = json.loads(manifest.read_text(encoding='utf-8'))
    sessions = []
    for session in data['sessions']:
        observer = LiveObserver(Rules(**data['rules']), samples=100, fresh_shoe=True)
        frames = []
        sequence = 0
        for index, truth in enumerate(session['stages']):
            path = dataset / truth['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != truth['sha256']:
                raise ValueError('Frozen frame digest mismatch: ' + truth['file'])
            with Image.open(path) as source:
                image = source.convert('RGB')
            for repeat in range(data['repetitions']):
                report = observer.process(image, sequence, 1 + sequence * data['interval_ms'] / 1000)
                sequence += 1
                frames.append({
                    'stage': index, 'repeat': repeat, 'truth': truth,
                    'round': report['round'], 'phase': report['phase'],
                    'observed_cards': report['observed_cards'],
                    'observed_rc': report['observed_running_count'],
                    'count_reliable': report['count_reliable'],
                    'count_reasons': report['count_reasons'],
                    'detections': report['detections'], 'events': report['events'],
                    'tracks': report['state']['tracks'],
                    'known_rank_counts': report['state']['known_rank_counts'],
                })
        sessions.append({'seed': session['seed'], 'frames': frames})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                                 'sessions': sessions}, indent=2) + '\n', encoding='utf-8')
    for session in sessions:
        previous_deficit = 0
        for frame in session['frames']:
            if frame['repeat'] != data['repetitions'] - 1:
                continue
            deficit = frame['observed_cards'] - frame['truth']['seen']
            if deficit != previous_deficit:
                print(json.dumps({'seed': session['seed'], 'stage': frame['stage'],
                                  'truth': frame['truth'], 'observed': frame['observed_cards'],
                                  'round': frame['round'], 'deficit': deficit,
                                  'count_reasons': frame['count_reasons']}))
            previous_deficit = deficit


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.dataset, args.output)
