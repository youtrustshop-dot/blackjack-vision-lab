"""One local geometric challenger on hash-bound native development stills.

Not a provider-session runner. No API, hidden phase, repeated-frame replay or
automatic promotion. Truth is used only after pixel inference. Raw results stay
in the requested local output; publish the aggregate separately.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bjlab.state_reader import LocalVisionReader, prepare_frame, image_analysis
from bjlab.engine import Rules
from bjlab.ocr import _read_cached, MODEL_SHA256
from bjlab.vision_diagnostics import candidate_revision
from validation.tools.state_reader_comparison import score_state


def evaluate(manifest, output):
    source = Path(manifest).read_bytes()
    document = json.loads(source)
    if document['evidence_kind'] != 'sparse-browser-screenshots-not-continuous-video':
        raise ValueError('This probe evaluates sparse native browser stills only.')
    cases = document['cases']
    if not cases or any(c['split'] != 'development' for c in cases):
        raise ValueError('Development cases required; this is not a final holdout runner.')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Case IDs must be unique.')
    rows = []
    for case in cases:
        path = Path(case['source_file'])
        if sha256(path.read_bytes()).hexdigest() != case['sha256']:
            raise ValueError('Source pixels changed.')
        frame = prepare_frame(Image.open(path), case['layout'])
        for profile in ('legacy', 'neutral'):
            reader = LocalVisionReader(surface_profile=profile)
            _read_cached.cache_clear()
            began = time.perf_counter()
            result = reader.read(frame)
            analysis = image_analysis(result.observation, Rules())
            elapsed = (time.perf_counter() - began) * 1000
            # Oracle fields cannot enter either reader or mathematical analysis.
            truth = case['truth']
            metrics = score_state(result.observation, truth)
            rank_useful = (metrics['rank_presence_state_correct'] and analysis['gate']['usable'])
            rows.append({'case_id': case['id'], 'profile': profile, 'frame_id': frame.frame_id,
                'source_sha256': case['sha256'], 'source_size': frame.source_size,
                'metrics': metrics, 'correct_conditional_rank_study': rank_useful,
                'decision_opportunity': truth['phase'] == 'player',
                'gate': analysis['gate'], 'observation': result.observation.model_dump(),
                'analysis': analysis, 'diagnostics': result.diagnostics, 'offline_ms': elapsed})
    aggregates = {}
    for profile in ('legacy', 'neutral'):
        selected = [r for r in rows if r['profile'] == profile]
        opportunities = [r for r in selected if r['decision_opportunity']]
        aggregates[profile] = {
            'stills': len(selected), 'rank_presence_states_correct': sum(r['metrics']['rank_presence_state_correct'] for r in selected),
            'full_card_states_correct': sum(r['metrics']['full_card_state_correct'] for r in selected),
            'decision_opportunities': len(opportunities),
            'correct_conditional_rank_study_opportunities': sum(r['correct_conditional_rank_study'] for r in opportunities),
            'false_rank_state_acceptances': sum(r['gate']['usable'] and not r['metrics']['rank_presence_state_correct'] for r in selected),
            'complete_state_correct': sum(r['metrics']['complete_state_correct'] is True for r in selected),
            'phase_unknown_states': sum(r['observation']['phase'] == 'unknown' for r in selected),
            'known_suits_correct': sum(r['metrics']['known_suits_correct'] for r in selected),
            'known_suits_expected': sum(r['metrics']['known_suits_expected'] for r in selected),
            'readable_suits_unknown': sum(r['metrics']['readable_suits_unknown'] for r in selected),
            'processing_p50_ms': float(np.percentile([r['offline_ms'] for r in selected], 50)),
            'processing_p95_ms': float(np.percentile([r['offline_ms'] for r in selected], 95)),
            'gate_reasons': dict(Counter(reason for r in selected for reason in r['gate']['reasons']))}
    root = Path(__file__).resolve().parents[2]
    result = {'schema': 1, 'candidate': candidate_revision(root),
        'manifest_sha256': sha256(source).hexdigest(), 'ocr_checkpoint_sha256': MODEL_SHA256,
        'source_hashes': {p: sha256((root/p).read_bytes()).hexdigest() for p in
            ('bjlab/corner_vision.py', 'bjlab/state_reader.py', 'validation/tools/surface_profile_comparison.py')},
        'hardware': {'platform': platform.platform(), 'processor': platform.processor(), 'device': 'CPU'},
        'scope': document['evidence_kind'], 'assistance': 'one initial ROI; phase truth only in evaluator',
        'annotation_origin': document['annotation_origin'], 'independent_sessions': 0,
        'original_provider_videos': 0, 'api_requests': 0,
        'timing_scope': 'single cold-glyph read plus conditional analysis; excludes capture, preparation, display; no warm-up',
        'decision': 'research-only; no promotion without independent complete sessions',
        'aggregates': aggregates, 'rows': rows}
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.manifest, args.output)['aggregates'], indent=2))
