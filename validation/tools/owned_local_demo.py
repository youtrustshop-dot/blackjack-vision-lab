"""Networkless preparation and opt-in browser demo of the supported owned UI.

This is a development demonstration, not a newly independent accuracy test.
No cloud factory, credential loading, simulator phase or identity reaches the
runtime. The evaluator reference is a separate file and is never served.
"""
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread
import argparse
import json

from PIL import Image

from bjlab.api_access_policy import MATRIX
from bjlab.hybrid_evidence import FrozenGroundedLocal
from bjlab.integrated_r1 import pixel_digest
from bjlab.state_reader import prepare_frame
from validation.tools.api_reader_tournament import ROOT, FrozenLocalObservation, file_hash
from validation.tools.grounded_corpus import save
from validation.tools.stress_lab import LAYOUT, PROFILES, render, timeline

OUTPUT = ROOT/'artifacts/integrated-r1-session-20261008/local-demo'
SOURCES = ('validation/tools/owned_local_demo.py', 'bjlab/integrated_r1.py',
    'bjlab/integration_api.py', 'bjlab/hybrid_evidence.py', 'bjlab/paired_deadline_reader.py',
    'bjlab/visible_phase.py', 'bjlab/corner_vision.py', 'bjlab/ocr.py', 'bjlab/advice.py',
    'ui/src/IntegrationLab.tsx', 'ui/src/CompactAdvisor.tsx', 'ui/src/compact-advisor.ts')


def prepare():
    if json.loads(MATRIX.read_text())['api_access_policy']['inference_authorized']:
        raise PermissionError('Close the cloud scope first.')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    stages=timeline(91008453,2)
    player=next(s for s in stages if s['phase']=='player')
    clear=next(s for s in stages if s['phase']=='waiting')
    sources={};references={}
    for name, stage, profile in (
        ('supported-classic',player,PROFILES['clean']),
        ('occluded-classic',player,{**PROFILES['clean'],'cover':True}),
        ('empty-classic',clear,PROFILES['clean'])):
        image,truth=render(stage,profile)
        path=OUTPUT/(name+'.png');image.save(path)
        sources[name]={'file':path.name,'sha256':file_hash(path),'pixel_sha256':pixel_digest(image)}
        references[name]={'phase':stage['phase'],'cards':truth,
            'scope':'owned renderer development reference; already consumed session seed; no independent validation claim'}
    save(OUTPUT/'references.json',references)
    save(OUTPUT/'freeze.json',{'schema':1,'sources':sources,'layout':LAYOUT,'cloud_requests':0,
        'reader':'unchanged frozen local; explicitly supported outlined-controls owned layout',
        'scope':'development demo; no provider transfer, R2, desktop capture or independent accuracy proof',
        'code_sha256':{p:file_hash(ROOT/p) for p in SOURCES}})
    return file_hash(OUTPUT/'freeze.json')


def checked(digest):
    if file_hash(OUTPUT/'freeze.json')!=digest:raise PermissionError('Demo freeze changed.')
    doc=json.loads((OUTPUT/'freeze.json').read_text())
    if doc['cloud_requests']!=0:raise PermissionError('This demo never enables cloud.')
    for name,entry in doc['sources'].items():
        if file_hash(OUTPUT/entry['file'])!=entry['sha256']:raise PermissionError('Owned input changed.')
    for name,expected in doc['code_sha256'].items():
        if file_hash(ROOT/name)!=expected:raise PermissionError('Demo implementation changed.')
    return doc


def serve(digest,port):
    doc=checked(digest)
    if json.loads(MATRIX.read_text())['api_access_policy']['inference_authorized']:
        raise PermissionError('Default cloud must remain disarmed.')
    from bjlab.integration_api import configure,sessions
    from bjlab.api import app,mount_ui
    import uvicorn
    titles={'supported-classic':'Locale · Tavolo con controlli supportati',
        'occluded-classic':'Locale · Carta coperta dal popup', 'empty-classic':'Locale · Tavolo svuotato'}
    configure(layout=doc['layout'],sources={name:{'title':titles[name],
        'path':OUTPUT/entry['file'],'pixel_sha256':entry['pixel_sha256']}
        for name,entry in doc['sources'].items()},
        local_factory=lambda:FrozenGroundedLocal(FrozenLocalObservation()))
    mount_ui()
    stop=Event();stop_file=OUTPUT/'server.stop'
    if stop_file.exists():raise PermissionError('Prior stop flag must be reviewed first.')
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning'))
    def watch():
        while not stop.wait(.2):
            if stop_file.exists():server.should_exit=True;break
    Thread(target=watch,daemon=True,name='owned-local-demo-stop').start()
    print(json.dumps({'url':f'http://127.0.0.1:{port}/?integration=1','cloud':False,'freeze_sha256':digest}),flush=True)
    try:server.run()
    finally:
        stop.set()
        for identity,session in sessions.items():
            session.disconnect();save(OUTPUT/('browser-'+identity+'.json'),session.receipt())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--serve',action='store_true')
    parser.add_argument('--freeze-sha256');parser.add_argument('--port',type=int,default=8788)
    parser.add_argument('--output',type=Path,default=OUTPUT,
        help='A fresh local artifact directory; preparation never overwrites a consumed freeze.')
    args=parser.parse_args()
    OUTPUT=args.output.resolve()
    if args.prepare and not args.serve:print(json.dumps({'freeze_sha256':prepare(),'provider_calls':0}))
    elif args.serve and args.freeze_sha256:serve(args.freeze_sha256,args.port)
    else:parser.error('Separate offline preparation and explicit frozen local serve are required.')
