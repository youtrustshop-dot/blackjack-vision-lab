"""Offline audit of the consumed terminal scene; never invokes a provider.

Adjacent stages come from the unchanged owned timeline. Gate fixtures are
explicitly fabricated contract tests, not new model or physical-history truth.
"""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from bjlab.live_cloud import PROMPT
from bjlab.live_state import LiveObservation
from bjlab.numeric_provenance import semantic_gate
from bjlab import paired_deadline_reader as path
from validation.tools.api_reader_tournament import ROOT, file_hash
from validation.tools.gemini_bound_session_hybrid import OUTPUT, SPECS, checked
from validation.tools.paired_cloud_prepare import render_case
from validation.tools.stress_lab import timeline
from tests.test_available_view_deadline_reader import setup, Local
from tests.test_numeric_provenance import state


def audit(external_hash):
    frozen,frames,truths=checked(external_hash)
    record,frame=frames['new-ended']; spec=next(s for s in SPECS if s[0]=='new-ended')
    stages=timeline(spec[2],12); index=next(i for i,s in enumerate(stages) if s['phase']=='settled')
    selected=[('terminal',index,'disabled-controls'),('next-waiting',index+1,'transition-clear')]
    family=(spec[2],record['family'],'C:/Windows/Fonts/'+spec[3],spec[4],spec[5])
    decoded=Image.open(BytesIO(frame.table_png)).convert('RGB'); output=OUTPUT/'phase-observability';output.mkdir(exist_ok=False)
    rows=[]
    for name,i,condition in selected:
        stage=stages[i];image,truth,visibility=render_case(stage,condition,family)
        image.save(output/(name+'.png'))
        native=image.convert('RGB');pixels=np.asarray(native)
        if name=='terminal':
            assert native.tobytes()==decoded.tobytes(), 'Frozen terminal pixels no longer reproduce.'
        assert (truth['phase'],len(truth['cards']))==(('settled',5) if name=='terminal' else ('waiting',0))
        rows.append({'name':name,'timeline_index':i,'render_condition':condition,'stage_phase':stage['phase'],
            'observed_truth_phase':truth['phase'],'cards_in_pixels':len(truth['cards']),
            'decoded_pixels_sha256':sha256(native.tobytes()).hexdigest(),'native_views':['table'],
            'source_size':list(frame.source_size),'layout':deepcopy(frame.layout),'table_box':list(frame.table_box)})
    different=int(np.any(np.asarray(Image.open(output/'terminal.png')) !=
        np.asarray(Image.open(output/'next-waiting.png')),axis=2).sum())
    assert different>0
    request=json.loads((OUTPUT/'inputs'/record['payload']['file']).read_text())
    parts=request['systemInstruction']['parts']
    prefix='Return exactly one object matching this JSON schema: '
    assert parts[0]['text'].startswith(PROMPT) and parts[1]['text'].startswith(prefix)
    logical=json.loads(parts[1]['text'][len(prefix):]); phase_schema=logical['properties']['p']
    assert phase_schema['enum']==['player','dealer','waiting','settled','unknown']
    assert 'description' not in phase_schema
    matrix=[]
    terminal={k:v for k,v in truths['new-ended'].items() if k!='number_views'}
    def no_network(*args,**kwargs):raise AssertionError('Offline audit cannot use DNS or sockets.')
    with patch('socket.socket',no_network),patch('socket.getaddrinfo',no_network):
        for family_name,base in [('consumed-ended-reference',terminal),('otherwise-valid-r1-fixture',state().model_dump())]:
            for phase in ('waiting','settled','unknown','player'):
                value=LiveObservation.model_validate({**base,'phase':phase})
                expected=family_name=='otherwise-valid-r1-fixture' and phase=='player'
                gate=semantic_gate(value,available_views={'table'})
                native,evidence,stamp,budget,transport,cloud=setup(value)
                with patch.object(path,'recommend',wraps=path.recommend) as solver:
                    result=path.local_first_attempt(evidence,Local(False),cloud)
                assert gate['usable']==expected and result['presented']==expected
                assert solver.call_count==int(expected) and len(transport.calls)==1
                assert bool(result['advisor_payload'])==expected
                matrix.append({'fabricated_fixture':family_name,'phase':phase,'strict_wire_validated':True,
                    'r1_usable':gate['usable'],'gate_reasons':gate['reasons'],'mock_posts':len(transport.calls),
                    'solver_calls':solver.call_count,'headless_payload_presentable':result['presented']})
    result={'experiment':'VISION-032','kind':'Post-hoc OFFLINE bounded observability and gate audit',
        'frozen_execution_hash':external_hash,'provider_requests':0,'ledger_changed':False,
        'source_sha256':{p:file_hash(ROOT/p) for p in ('validation/tools/terminal_phase_audit.py',
            'validation/tools/stress_lab.py','validation/tools/grounded_corpus.py','validation/tools/paired_cloud_prepare.py',
            'bjlab/live_cloud.py','bjlab/live_state.py','bjlab/numeric_provenance.py','bjlab/state_reader.py')},
        'actual_serialized_request_sha256':record['payload']['canonical_sha256'],
        'actual_phase_schema':phase_schema,
        'phase_instruction_excerpt':'p visible phase; Unknown phase stays unknown',
        'explicit_waiting_settled_discriminating_rule_in_request':False,
        'reference_assignment_sites':['stress_lab.timeline adds settled after dealer progression',
            'grounded_corpus.render uses stage phase; disabled-controls forces settled',
            'waiting selects DEAL; settled selects NEW HAND'],
        'legitimate_adjacent_stages':rows,'decoded_changed_pixels':different,
        'visual_discriminant_in_this_replay':'Terminal has final cards, NEW HAND and disabled HIT/STAND/DOUBLE; next waiting is empty with DEAL.',
        'observability_result':'These two legitimate replay inputs differ; no single-frame collision demonstrated. Request does not specify the phase naming convention.',
        'fabricated_gate_matrix':matrix,'historical_scores_changed':False,'hybrid_executed':False,
        'claim_limit':'A two-stage source/pixel audit and eight fabricated safety fixtures; not exhaustive observability, model reclassification, new inference, full-session tracking or promotion.'}
    (output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze-sha256',required=True)
    args=parser.parse_args()
    ledger=ROOT/'artifacts/api-budget/eur10-total-20261004.json';before=file_hash(ledger)
    result=audit(args.freeze_sha256);assert file_hash(ledger)==before
    print(json.dumps({'actual_adjacent_stages':2,'decoded_changed_pixels':result['decoded_changed_pixels'],
        'fabricated_gate_cases':len(result['fabricated_gate_matrix']),'provider_requests':0,'ledger_unchanged':True}))
