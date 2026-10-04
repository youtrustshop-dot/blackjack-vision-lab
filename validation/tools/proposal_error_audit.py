"""Audit reviewed failure causes from consumed development proposals.

This reads annotations only for evaluation, never for recognition. It does not
retrain, tune or claim detector AP from inferred full-card boxes. Raw records and
montages remain local; public output contains aggregate causes and receipt hashes.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

CAUSES=('non_rank_suit','face_artwork','ui_badge_text','capture_overlay_text',
        'reconstructed_box','duplicate_corner','real_corner_unreadable','unclassified')


def run(proposals,annotations,output):
    proposals,annotations=Path(proposals),Path(annotations)
    raw=json.loads(proposals.read_text(encoding='utf-8'))
    review=json.loads(annotations.read_text(encoding='utf-8'))
    if len({p['id'] for p in raw})!=len(raw):raise ValueError('Duplicate proposal ID')
    labels={p['id']:p for p in review['labels']}
    if len(labels)!=len(review['labels']) or set(labels)!={p['id'] for p in raw}:
        raise ValueError('Review must cover every unmatched emitted object exactly once')
    counts=Counter();secondary=Counter();recognized=unknown=0
    for proposal in raw:
        label=labels[proposal['id']]
        if label['cause'] not in CAUSES or not label.get('explanation'):
            raise ValueError('Use a declared cause and a review explanation')
        counts[label['cause']]+=1
        secondary['already_represented_physical_card']+=bool(label.get('already_represented_physical_card'))
        recognized+=proposal['prediction']['rank'] is not None
        unknown+=proposal['prediction']['rank'] is None
    result={'schema':1,'scope':'Consumed private development stills; three inputs, two moments. Manual diagnostic classification, not new data or AP.',
        'review_type':review['review_type'],'objects':len(raw),'primary_causes':{k:counts[k] for k in CAUSES},
        'secondary_flags':dict(secondary),'rank_resolved':recognized,'rank_unresolved':unknown,
        'proposals_sha256':hashlib.sha256(proposals.read_bytes()).hexdigest(),
        'annotations_sha256':hashlib.sha256(annotations.read_bytes()).hexdigest(),
        'decision':'Corner proposals require independent card-surface/position evidence before becoming physical-card detections. Unreadable true corners retain their gate. No model promoted.'}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('proposals');parser.add_argument('annotations')
    parser.add_argument('--output',required=True);args=parser.parse_args();run(args.proposals,args.annotations,args.output)
