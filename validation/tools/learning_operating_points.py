"""Development-only score/duplicate diagnostics for the one-class localizer.

This deliberately selects on memorized training examples, not a validation or
final holdout. It can permit a development ROI comparison, never deployment.
Preserve the failed .50 result separately; do not rewrite its acceptance gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from bjlab.datasets import bbox_iou

GRID=(.01,.025,.05,.10,.15,.20,.30,.40,.50)


def box(prediction):
    a,b,c,d=prediction['xyxy'];return (a,b,c-a,d-b)


def suppress(predictions,threshold,overlap=.50):
    kept=[]
    for p in sorted((p for p in predictions if p['confidence']>=threshold),key=lambda p:p['confidence'],reverse=True):
        if not any(bbox_iou(box(p),box(k))>overlap for k in kept):kept.append(p)
    return kept


def run(receipt,output):
    receipt=Path(receipt);report=json.loads(receipt.read_text(encoding='utf-8'))
    if report.get('task')!='corner':raise ValueError('Geometry-only diagnostics require one class')
    cases=[]
    for row in report['after']['rows']:
        labels=receipt.parent/'data/labels/memorization'/(Path(row['image']).stem+'.txt')
        truth=[]
        for line in labels.read_text().splitlines():
            _,x,y,w,h=map(float,line.split());truth.append(((x-w/2)*416,(y-h/2)*320,w*416,h*320))
        cases.append((truth,row['raw_predictions_at_001']))
    rows=[]
    for threshold in GRID:
        matched=missed=extra=0
        for truth,raw in cases:
            predictions=suppress(raw,threshold);used_t=set();used_p=set()
            for iou,i,j in sorted(((bbox_iou(t,box(p)),i,j) for i,t in enumerate(truth) for j,p in enumerate(predictions)),reverse=True):
                if iou>=.50 and i not in used_t and j not in used_p:used_t.add(i);used_p.add(j)
            matched+=len(used_t);missed+=len(truth)-len(used_t);extra+=len(predictions)-len(used_p)
        precision=matched/(matched+extra) if matched+extra else 0.;recall=matched/(matched+missed)
        rows.append({'threshold':threshold,'localized':matched,'missed':missed,'extra':extra,
                     'precision':precision,'recall':recall,'diagnostic_gate':precision>=.90 and recall>=.90})
    passing=[r for r in rows if r['diagnostic_gate']]
    selected=max(passing,key=lambda r:r['threshold']) if passing else None
    result={'schema':1,'scope':'train memorization score/NMS diagnostic, development selection, no independent validation',
            'parent_receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),
            'checkpoint_sha256':report['checkpoint_sha256'],'grid':list(GRID),'nms_iou':.50,'matching_iou':.50,
            'rule':'largest grid threshold with >=90% geometric recall and precision on development memorization data',
            'fixed_050_gate_preserved':report['after']['learning_gate'],'rows':rows,'selected':selected,
            'can_proceed_to_development_roi_comparison':selected is not None,
            'rank_and_suit_classifiers':'not part of this one-class localizer'}
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('receipt');parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.receipt,args.output)
