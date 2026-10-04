"""Bounded learning diagnostics, never a generalization or final-holdout test.

Use the isolated research venv. No uploads or automatic downloads. The pretrained
checkpoint must match an official digest and pass a restricted weights-only load.
The same sixteen development images are deliberately evaluated after training:
memorization is a necessary diagnostic, not an independent validation result.
"""
import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from validation.tools.yolo_corner_pilot import RANKS, offline_configuration

OFFICIAL_SHA256 = '9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef'
OFFICIAL_URL = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_dataset(source):
    from PIL import Image, ImageDraw
    import numpy as np
    source = Path(source)
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    counts, rows, errors = Counter(), [], []
    for item in manifest['files']:
        image_path = source / item['file']
        image = Image.open(image_path).convert('RGB')
        if digest(image_path) != item['sha256']:
            raise ValueError('Frozen development image hash mismatch')
        label_path = source / 'labels' / item['split'] / (image_path.stem + '.txt')
        labels = []
        for line in label_path.read_text().splitlines():
            fields = line.split()
            if len(fields) != 5:
                raise ValueError('Expected one class and four normalized coordinates')
            label = int(fields[0]); x, y, w, h = map(float, fields[1:])
            if not (0 <= label < len(RANKS) and w > 0 and h > 0 and
                    0 <= x-w/2 < x+w/2 <= 1 and 0 <= y-h/2 < y+h/2 <= 1):
                raise ValueError('Invalid annotation bounds/class')
            a, b, c, d = (round((x-w/2)*image.width), round((y-h/2)*image.height),
                          round((x+w/2)*image.width), round((y+h/2)*image.height))
            pixels = np.asarray(image.crop((a, b, c, d))).astype('int16')
            ink = (pixels.max(2) < 160) | ((pixels[:, :, 0]-pixels[:, :, 1] > 40) &
                                          (pixels[:, :, 0]-pixels[:, :, 2] > 30))
            if not ink.any():
                errors.append({'image': item['file'], 'class': label, 'problem': 'empty ink crop'})
            counts[f"{item['split']}:{RANKS[label]}"] += 1
            labels.append({'class': label, 'bbox': [a, b, c-a, d-b], 'ink_pixels': int(ink.sum())})
        rows.append({'file': item['file'], 'split': item['split'], 'labels': labels,
                     'image_sha256': digest(image_path), 'label_sha256': digest(label_path)})
    sizes = [r['bbox'][2:] for row in rows for r in row['labels']]
    return {'schema': 1, 'manifest_sha256': digest(source/'manifest.json'), 'images': len(rows),
            'class_counts': dict(counts), 'annotation_count': len(sizes), 'errors': errors,
            'glyph_width_range': [min(s[0] for s in sizes), max(s[0] for s in sizes)],
            'glyph_height_range': [min(s[1] for s in sizes), max(s[1] for s in sizes)],
            'limitations': ['Synthetic font glyphs, not provider card artwork',
                'Unlabelled lower-corner rank decorations remain hard negatives',
                'Geometric/ink audit does not independently prove every semantic class'],
            'rows': rows}


def prepare_subset(source, target, audit, task='rank'):
    import yaml
    from PIL import Image, ImageDraw
    source, target = Path(source), Path(target)
    if target.exists():
        raise ValueError('Do not overwrite diagnostic data')
    selected = [r for r in audit['rows'] if r['split'] == 'train'][:16]
    classes = {label['class'] for row in selected for label in row['labels']}
    if classes != set(range(len(RANKS))):
        raise ValueError('Diagnostic subset must cover all thirteen ranks')
    manifest = []
    sheet = Image.new('RGB', (416*4, 320*4), 'white')
    for index, row in enumerate(selected):
        path = source/row['file']; image = Image.open(path).convert('RGB')
        annotated = image.copy(); draw = ImageDraw.Draw(annotated)
        for label in row['labels']:
            x, y, w, h = label['bbox']
            draw.rectangle((x, y, x+w, y+h), outline='#00ff00', width=1)
        sheet.paste(annotated, (index % 4 * 416, index // 4 * 320))
        for split in ('train', 'memorization'):
            output = target/'images'/split/path.name; output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output)
            labels = target/'labels'/split/(path.stem+'.txt'); labels.parent.mkdir(parents=True, exist_ok=True)
            original=(source/'labels/train'/(path.stem+'.txt')).read_text()
            labels.write_text(original if task=='rank' else '\n'.join('0 '+line.split(' ',1)[1] for line in original.splitlines())+'\n')
            manifest.append({'file': output.relative_to(target).as_posix(), 'group': row['file'],
                             'image_sha256': digest(output), 'label_sha256': digest(labels)})
    sheet.save(target/'annotation-contact-sheet.png')
    document = {'schema': 1, 'scope': 'development memorization check; train == diagnostic evaluation by design',
                'classes': list(RANKS) if task=='rank' else ['rank-corner'], 'files': manifest, 'independent_validation': False}
    (target/'manifest.json').write_text(json.dumps(document, indent=2), encoding='utf-8')
    (target/'data.yaml').write_text(yaml.safe_dump({'path': str(target.resolve()), 'train': 'images/train',
                 'val': 'images/memorization', 'names': dict(enumerate(document['classes']))}, sort_keys=False))
    return target/'data.yaml'


def restricted_pretrained(path,*,expected_sha256=OFFICIAL_SHA256):
    """Fail closed before deserialization; never fall back to weights_only=False."""
    import torch
    if digest(path) != expected_sha256:
        raise ValueError('Official checkpoint SHA256 mismatch')
    # Exact audited model class families, not arbitrary names from the pickle.
    allowed = {
        'ultralytics.nn.tasks.DetectionModel', 'builtins.set',
        *('torch.nn.modules.'+name for name in (
            'container.Sequential', 'container.ModuleList', 'conv.Conv2d', 'batchnorm.BatchNorm2d',
            'activation.SiLU', 'activation.Softmax', 'pooling.MaxPool2d', 'upsampling.Upsample',
            'linear.Linear', 'linear.Identity', 'dropout.Dropout', 'container.ParameterList', 'activation.ReLU')),
        *('ultralytics.nn.modules.'+name for name in (
            'conv.Conv', 'conv.Concat', 'conv.DWConv', 'block.C3k2', 'block.C3k', 'block.C2PSA',
            'block.SPPF', 'block.Bottleneck', 'block.Attention', 'block.PSABlock', 'head.Detect',
            'block.DFL', 'block.C2f')),
    }
    globals_found = sorted(torch.serialization.get_unsafe_globals_in_checkpoint(path))
    unknown = set(globals_found) - allowed
    if unknown:
        raise ValueError(f'Unreviewed checkpoint globals: {sorted(unknown)}')
    objects = []
    for name in globals_found:
        module, attr = name.rsplit('.', 1)
        objects.append(getattr(importlib.import_module(module), attr))
    with torch.serialization.safe_globals(objects):
        checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    model = checkpoint.get('ema') or checkpoint.get('model')
    if not isinstance(model, torch.nn.Module):
        raise ValueError('Expected a model after restricted deserialization')
    return model, {'url': OFFICIAL_URL, 'sha256': digest(path), 'globals': globals_found,
                   'deserialization': 'torch.load(weights_only=True), explicit audited globals',
                   'license': 'Ultralytics AGPL-3.0 / Enterprise; research only, no distribution',
                   'source_classes': model.names}


def score_predictions(model, data, *, confidence=.50):
    """Geometry matching first; count misses, wrong classes and duplicate boxes."""
    from bjlab.datasets import bbox_iou
    from PIL import Image
    totals = Counter(); rows = []
    for path in sorted((Path(data)/'images/memorization').glob('*.png')):
        image = Image.open(path).convert('RGB'); truth = []
        for line in (Path(data)/'labels/memorization'/(path.stem+'.txt')).read_text().splitlines():
            label, x, y, w, h = map(float, line.split())
            truth.append((int(label), ((x-w/2)*image.width, (y-h/2)*image.height, w*image.width, h*image.height)))
        prediction = model.predict(image, imgsz=416, device='cpu', conf=.001, verbose=False)[0]
        raw = [{'class': int(c), 'confidence': float(s), 'xyxy': b}
               for b, s, c in zip(prediction.boxes.xyxy.tolist(), prediction.boxes.conf.tolist(), prediction.boxes.cls.tolist())]
        accepted = [r for r in raw if r['confidence'] >= confidence]; pairs = []; used_t = set(); used_p = set()
        possible = sorted(((bbox_iou(t[1], (p['xyxy'][0], p['xyxy'][1], p['xyxy'][2]-p['xyxy'][0], p['xyxy'][3]-p['xyxy'][1])), i, j)
                           for i, t in enumerate(truth) for j, p in enumerate(accepted)), reverse=True)
        for iou, i, j in possible:
            if iou >= .50 and i not in used_t and j not in used_p:
                used_t.add(i); used_p.add(j); pairs.append((i,j))
        correct = sum(truth[i][0] == accepted[j]['class'] for i,j in pairs)
        row = {'image': path.name, 'truth': len(truth), 'localized': len(pairs), 'rank_correct': correct,
               'rank_wrong': len(pairs)-correct, 'missed': len(truth)-len(pairs),
               'extra_boxes': len(accepted)-len(pairs), 'raw_predictions_at_001': raw}
        rows.append(row)
        totals.update({k: row[k] for k in ('truth','localized','rank_correct','rank_wrong','missed','extra_boxes')})
    rank_task=len(model.names)>1
    return {'confidence_threshold': confidence, 'iou_threshold': .50, **dict(totals),
            'classification_task':'13 ranks' if rank_task else 'one geometry class; no rank or suit classifier',
            'learning_gate': totals['localized']/totals['truth'] >= .90 and
                totals['rank_correct']/totals['truth'] >= .80 and totals['extra_boxes'] <= totals['truth']*.10,
            'gate_defined_before_run': '>=90% localization, >=80% correct rank including misses, <=10% extra boxes; train memorization only',
            'independent_validation': False, 'rows': rows}


def run(source, root, initialization, epochs, pretrained=None, budget_seconds=360, task='rank',parent_report=None):
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=False)
    audit = audit_dataset(source)
    if audit['errors']:
        raise ValueError('Annotation ink audit failed')
    (root/'annotation-audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    data = prepare_subset(source, root/'data', audit, task)
    offline_configuration(root)
    import torch
    from ultralytics import YOLO, __version__
    torch.set_num_threads(4)
    model = YOLO('yolo26n.yaml'); origin = None
    if initialization == 'pretrained':
        if not pretrained:
            raise ValueError('Pass a separately reviewed official local checkpoint')
        weights, origin = restricted_pretrained(pretrained)
        model.model.load(weights)
        # The trainer only transfers the in-memory weights when ckpt is truthy.
        # Keep the restricted object here; do not deserialize the file again.
        model.ckpt = {'model': weights}
    elif initialization=='refine':
        if not parent_report or not pretrained:
            raise ValueError('A refinement needs our completed experiment receipt and checkpoint')
        parent=json.loads(Path(parent_report).read_text(encoding='utf-8'))
        if parent.get('task')!=task or parent.get('uploads') is not False:
            raise ValueError('Own parent experiment/task mismatch')
        weights,origin=restricted_pretrained(pretrained,expected_sha256=parent['checkpoint_sha256'])
        origin['url']=None;origin['scope']='our local checkpoint, restricted load, parent receipt hash verified'
        origin['parent_report_sha256']=digest(parent_report)
        # Preserve the already learned one-class head, not an 80-class YAML head.
        model.model=weights.float();model.ckpt={'model':weights}
        model.overrides['model']='yolo26n.yaml'
    began = time.perf_counter()
    before = score_predictions(model, root/'data') if initialization == 'scratch' else None
    deadline = time.perf_counter()+budget_seconds
    def stop_at_budget(trainer):
        if time.perf_counter() >= deadline:
            trainer.stop = True
    model.add_callback('on_train_epoch_end', stop_at_budget)
    result = model.train(data=str(data), epochs=epochs, imgsz=416, batch=8, device='cpu', workers=0,
          amp=False, pretrained=False, plots=False, save=True, project=str(root/'runs'), name=initialization,
          exist_ok=False, seed=483107, deterministic=True, optimizer='AdamW', lr0=.002, warmup_epochs=0,
          mosaic=0, fliplr=0, flipud=0, degrees=0, translate=0, scale=0,
          hsv_h=0, hsv_s=0, hsv_v=0, erasing=0, patience=epochs, verbose=False)
    after = score_predictions(model, root/'data')
    report = {'schema': 1, 'scope': 'development training memorization; NO independent validation or promotion',
              'initialization': initialization, 'origin': origin, 'task':task,
              'classes': list(RANKS) if task=='rank' else ['rank-corner'],
              'train_images': 16, 'train_annotations': 96, 'ultralytics': __version__, 'torch': torch.__version__,
              'imgsz': 416, 'requested_epochs': epochs, 'actual_epochs': model.trainer.epoch+1,
              'budget_seconds': budget_seconds, 'wall_seconds': time.perf_counter()-began,
              'dataset_sha256': digest(root/'data/manifest.json'),
              'checkpoint_sha256': digest(model.trainer.best), 'validation_metrics': result.results_dict,
              'before': before, 'after': after, 'suits': 'not supported', 'telemetry': False, 'uploads': False,
              'next_step': 'same calibrated ROI comparison only if learning gate passes; keep final holdout untouched'}
    (root/'learning.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('before','after')}, indent=2))
    print(json.dumps({k:v for k,v in after.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--initialization', choices=('scratch','pretrained','refine'), required=True)
    parser.add_argument('--epochs', type=int, default=60)
    parser.add_argument('--pretrained', type=Path)
    parser.add_argument('--budget-seconds', type=int, default=360)
    parser.add_argument('--task', choices=('rank','corner'), default='rank')
    parser.add_argument('--parent-report',type=Path)
    args = parser.parse_args()
    run(args.source, args.root, args.initialization, args.epochs, args.pretrained, args.budget_seconds, args.task,args.parent_report)
