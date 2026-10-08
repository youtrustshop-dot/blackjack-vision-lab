"""Opt-in owned browser-canvas integration. Three frozen Gemini slots maximum.

Prepare and local comparison are networkless. Serve is local-only by default.
--cloud-lot spends only a newly frozen explicit 3-slot scope, never prior slots.
Runtime receives pixels/layout; references stay in a separate offline evaluator.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Lock
import argparse
import json
import time

from PIL import Image, ImageDraw

from bjlab.api_access_policy import MATRIX
from bjlab.controlled_http import resolve_scope
from bjlab.grounded_cloud import GeminiConfig
from bjlab.grounded_state import GroundedResult
from bjlab.hybrid_evidence import FrozenGroundedLocal
from bjlab.integrated_r1 import pixel_digest
from bjlab.live_state import LiveObservation
from bjlab.paired_persistent_http import PersistentScopedTransport, canonical_digest
from bjlab.private_observation_store import PrivateObservationStore, DIRECTORY, MAX_RECORDS
from bjlab.rejected_output_diagnostics import OwnedOutputScope, _OutputTap, inspect_output
from bjlab.research_budget import CANONICAL_LEDGER, PersistentRequestBudget
from bjlab.state_reader import prepare_frame
from bjlab.visible_phase_deadline_reader import VisiblePhaseDeadlineReader, REQUEST_PROFILE
from validation.tools.api_reader_tournament import ROOT, AUTHORIZATION_ID, FrozenLocalObservation, file_hash, native_record
from validation.tools.gemini_five_diagnostics import load_key, PRICE_CHECK
from validation.tools.gemini_visible_phase_check import payload_for
from validation.tools.grounded_corpus import save, font, SYMBOL_FONT
from validation.tools.numeric_semantic_score import semantic_score
from validation.tools.paired_cloud_prepare import render_case, live_truth, allowed_number_views, local_snapshot
from validation.tools.paired_semantic_smoke import claim, set_policy
from validation.tools.state_reader_comparison import load_frame
from validation.tools.stress_lab import LAYOUT, timeline

OUTPUT = ROOT/'artifacts/integrated-r1-session-20261008'
EPOCH = '2026-10-08-owned-browser-integration-three'
INITIAL_LEDGER_SHA = 'be7e585038b53fe2364f67e09482973074679a180b6b7d3dde808f0e29d41b87'
MAX_RESERVATION = Decimal('0.9513984')
SPECS = (
    ('stable-overlap', 'overlap', 91008411, 'tahomabd.ttf', '#385643', '#fffaf2', True),
    ('changing-rotation', 'rotation', 91008419, 'constanb.ttf', '#4a445e', '#fff7fc', True),
    ('contradictory-total', 'labelled-totals', 91008427, 'candarab.ttf', '#285462', '#fffdf4', False),
)
ORDER = tuple(s[0] for s in SPECS)
GATES = {'current_hand_r1': 'Same semantic_score/semantic gate; sufficient current-hand content, phase, controls and relevant numeric provenance. Zero false accepted advice.',
    'full_transcription': 'Report semantic_complete_transcription separately; irrelevant UI omissions never repair historical gates or override semantic safety.',
    'capture_to_dom_deadline_ms': 3000, 'target_p95_ms': 2500, 'capture_gap_ms': 250,
    'changing_case': 'No current advice after actual pixels change, even if cloud transcription is correct.',
    'negative_case': 'Explicit printed player total disagrees with cards: abstain.',
    'promotion': False, 'r2_certification': False, 'physical_windows_capture': False}
SOURCES = ('bjlab/integrated_r1.py','bjlab/integration_api.py','bjlab/paired_deadline_reader.py',
    'bjlab/hybrid_evidence.py','bjlab/visible_phase_deadline_reader.py','bjlab/available_image_views.py',
    'bjlab/numeric_provenance.py','bjlab/live_state.py','bjlab/grounded_state.py','bjlab/state_reader.py',
    'bjlab/paired_persistent_http.py','bjlab/private_observation_store.py','bjlab/research_budget.py',
    'bjlab/controlled_http.py','bjlab/advice.py','bjlab/engine.py',
    'validation/tools/integrated_r1_session.py','validation/tools/numeric_semantic_score.py',
    'validation/tools/api_reader_tournament.py','validation/tools/paired_cloud_prepare.py',
    'validation/tools/grounded_corpus.py','validation/tools/stress_lab.py',
    'ui/src/IntegrationLab.tsx','ui/src/CompactAdvisor.tsx','ui/src/compact-advisor.ts','ui/src/main.tsx')


def ledger_snapshot():
    digest = file_hash(CANONICAL_LEDGER)
    raw = json.loads(CANONICAL_LEDGER.read_text())
    receipt = PersistentRequestBudget(CANONICAL_LEDGER, authorization_id=AUTHORIZATION_ID,
        max_requests=raw['max_requests'], max_usd='8').receipt()
    if file_hash(CANONICAL_LEDGER) != digest: raise PermissionError('Ledger read raced.')
    return {'sha256': digest, 'receipt': receipt}


def prepare():
    before = ledger_snapshot()
    if before['sha256'] != INITIAL_LEDGER_SHA or before['receipt']['requests_attempted'] != 123:
        raise PermissionError('Prior closed 123-entry scope changed.')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    directory = OUTPUT/'inputs'; directory.mkdir()
    records, truths, visible = [], {}, {}
    for spec in SPECS:
        name, condition, seed, basename, felt, paper, usable = spec
        stage = next(s for s in timeline(seed, 4) if s['phase'] == 'player')
        family = (seed, 'owned-integration-'+basename, 'C:/Windows/Fonts/'+basename, felt, paper)
        image, truth, visibility = render_case(stage, condition, family)
        if name == 'contradictory-total':
            # Explicitly a diagnostic counterfactual, not an accurate game total.
            original = next(n for n in truth['numbers'] if n['role'] == 'player_total')
            draw = ImageDraw.Draw(image); draw.rectangle((680, 540, 1023, 595), fill=felt)
            wrong = original['value']+3
            draw.text((690, 555), 'PLAYER TOTAL '+str(wrong), font=font('C:/Windows/Fonts/arialbd.ttf',25), fill='white', anchor='lt')
            original['value'] = wrong
        frame = replace(prepare_frame(image, LAYOUT), details=())
        reference = live_truth(truth)
        from bjlab.numeric_provenance import semantic_gate
        if semantic_gate(reference, available_views={'table'})['usable'] != usable:
            raise ValueError('Predeclared R1 case does not match rendered evidence.')
        record = native_record(directory, name, frame, seed=seed, family=family[1], condition=condition,
            split='owned_new_sampled_validation', expected_usable_r1=usable,
            evidence_kind='new seed; shared owned renderer; not independent provider/session certification')
        record['pixel_sha256'] = pixel_digest(image)
        payload = payload_for(frame); payload_path = directory/name/'request.json'; save(payload_path, payload)
        record['payload'] = {'file':name+'/request.json','sha256':file_hash(payload_path),
            'canonical_sha256':canonical_digest(payload)}
        records.append(record); truths[name] = {**reference.model_dump(), 'number_views':allowed_number_views(truth,LAYOUT)}
        visible[name] = visibility
    # Clearing really changes the acquired pixels. No phase flag is sent to inference.
    clear_stage = next(s for s in timeline(SPECS[1][2],4) if s['phase']=='waiting')
    _,_,seed,basename,felt,paper,_=SPECS[1]
    family=(seed,'owned-integration-'+basename,'C:/Windows/Fonts/'+basename,felt,paper)
    image, truth, visibility = render_case(clear_stage,'transition-clear',family)
    frame = replace(prepare_frame(image,LAYOUT),details=())
    clear = native_record(directory,'clear',frame,split='development_transition',seed=SPECS[1][2],
        family=family[1],condition='actual-table-clear',evidence_kind='owned transition; not separate session')
    clear['pixel_sha256']=pixel_digest(image);records.append(clear)
    truths['clear']={**live_truth(truth).model_dump(),'number_views':allowed_number_views(truth,LAYOUT)}
    visible['clear']=visibility
    save(directory/'frames.json',records);save(directory/'references.json',truths);save(directory/'visibility.json',visible)
    previous=json.loads((ROOT/'artifacts/paired-semantic-hybrid-20261006/freeze.json').read_text())
    frozen={'experiment':'VISION-034','epoch':EPOCH,'parent_commit':'3c23ea3c7c65f4ea06af651a9ca8cc7e3c99d535',
        'order':list(ORDER),'specs':[list(s) for s in SPECS],'gates':GATES,'request_profile':REQUEST_PROFILE,
        'maximum_cloud_inferences':3,'maximum_reservation_usd':str(MAX_RESERVATION),
        'unchanged_lifetime_cap_usd':'8','request_count_amendment':[124,126],
        'human_scope':'Latest explicit human ok vai fai tutto tu goal after proposed bounded integrated increment; existing paid budget and key reuse persist.',
        'ledger_before':before,'price_check':PRICE_CHECK,'frozen_local':local_snapshot(previous['frozen_local']['manifest']),
        'files':{str(p.relative_to(OUTPUT)):file_hash(p) for p in directory.rglob('*') if p.is_file()},
        'sources':{p:file_hash(ROOT/p) for p in SOURCES},
        'fonts':{s[3]:file_hash('C:/Windows/Fonts/'+s[3]) for s in SPECS},
        'symbol_font_sha256':file_hash(SYMBOL_FONT),
        'old_conditional_slot':'closed, never reopened','retry':0,'paid_warmup':0,'final_holdout':'not_opened',
        'runtime_input':'Actual browser canvas PNG bytes, native dimensions, timestamp, declared geometry. No references/phase/turn/round IDs.',
        'primary_local':'FrozenGroundedLocal(FrozenLocalObservation()) unchanged; routing measured, never forced from reference.',
        'presentation':'Main/browser-popup compact DOM. Two RAF acknowledgement; no physical scanout/native capture claim.',
        'truth_scope':'Renderer masks and assistant original-pixel review; not independent human/provider truth.'}
    save(OUTPUT/'freeze.json',frozen)
    if ledger_snapshot()!=before:raise PermissionError('Offline preparation changed ledger.')
    return frozen


def checked(external_hash):
    if file_hash(OUTPUT/'freeze.json')!=external_hash:raise PermissionError('External freeze changed.')
    f=json.loads((OUTPUT/'freeze.json').read_text())
    if f['gates']!=GATES or f['order']!=list(ORDER) or f['specs']!=[list(s) for s in SPECS]:raise PermissionError('Scope changed.')
    for mapping in ('files','sources'):
        for name,digest in f[mapping].items():
            path=(OUTPUT if mapping=='files' else ROOT)/name
            if file_hash(path)!=digest:raise PermissionError('Frozen input/source changed: '+name)
    if local_snapshot(f['frozen_local']['manifest'])!=f['frozen_local']:raise PermissionError('Weights changed.')
    if file_hash(SYMBOL_FONT)!=f['symbol_font_sha256']:raise PermissionError('Suit font changed.')
    for name,digest in f['fonts'].items():
        if file_hash('C:/Windows/Fonts/'+name)!=digest:raise PermissionError('Font changed.')
    records=json.loads((OUTPUT/'inputs/frames.json').read_text())
    return f,{r['id']:(r,load_frame(OUTPUT/'inputs',r)) for r in records}


def evaluate_local(external_hash):
    frozen,frames=checked(external_hash)
    references=json.loads((OUTPUT/'inputs/references.json').read_text())
    rows=[]
    for manifest in (None,frozen['frozen_local']['manifest']):
        reader=FrozenLocalObservation(specialized_manifest=manifest)
        for name,(record,frame) in frames.items():
            result=reader.read(frame)
            legacy=result.observation
            observed=LiveObservation(cards=[c.model_dump() for c in legacy.cards], table_state=legacy.table_state,
                phase=legacy.phase,controls=legacy.controls,numbers=[],blockers=[]) if legacy else None
            score=semantic_score(observed,references[name],status=result.status,elapsed_ms=result.elapsed_ms,available_views={'table'})
            from bjlab.state_reader import analysis_gate
            score['runtime_legacy_gate']=analysis_gate(legacy,require_turn=True) if legacy else {'usable':False}
            rows.append({'case':name,'reader':reader.name,'elapsed_ms':result.elapsed_ms,'evaluation':score,
                'observation':legacy.model_dump() if legacy else None,'scope':'offline isolated reader; no capture/display measurement'})
    save(OUTPUT/'local-comparison.json',rows)
    return rows


class OwnedCloudLot:
    """Shared one-shot lot across views/sessions. No anonymous/generic API proxy."""
    name='gemini-owned-integration'
    def __init__(self, external_hash):
        self.hash=external_hash;self.frozen,self.frames=checked(external_hash)
        self.original=MATRIX.read_bytes();policy=json.loads(self.original)['api_access_policy']
        before=ledger_snapshot()
        if (before!=self.frozen['ledger_before'] or policy['inference_authorized'] or policy['max_requests']!=0 or
            Decimal(policy['max_usd'])!=0 or before['receipt']['stopped'] or
            datetime.now(timezone.utc).date().isoformat()!=PRICE_CHECK['verified_utc_date'] or
            before['receipt']['requests_attempted']!=123 or 3*GeminiConfig().reserve_usd!=MAX_RESERVATION or
            Decimal(before['receipt']['accounted_upper_usd'])+MAX_RESERVATION>8):
            raise PermissionError('Budget/date/policy prerequisites failed before inference.')
        if len(list((ROOT/DIRECTORY).glob('*.r1diag')))+3>MAX_RECORDS:
            raise PermissionError('No protected output capacity; no deletion to fit.')
        self.store=PrivateObservationStore(ROOT)
        # Verify an existing retained output, without consuming a fourth record.
        previous=json.loads((ROOT/'artifacts/gemini-visible-phase-20261008/results.json').read_text())[-1]
        recovery=self.store.read(previous['retention']['record_id'])
        if sha256(recovery['output_text'].encode()).hexdigest()!=previous['retention']['output_sha256']:
            raise PermissionError('Protected recovery preflight failed.')
        recovery=None
        self.key=load_key();self.transports=[];self.rows=[];self.used=set();self.lock=Lock();self.pending=False;self.closed=False
        self.old_entries=deepcopy(json.loads(CANONICAL_LEDGER.read_text())['entries'])
        self.budget=PersistentRequestBudget(CANONICAL_LEDGER,authorization_id=AUTHORIZATION_ID,max_requests=124,max_usd='8')
        dns=resolve_scope()
        probe=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=self.budget,dns_scope=dns,api_key=self.key)
        try:metadata=probe.metadata()
        finally:probe.close()
        if (metadata.get('name')!='models/'+GeminiConfig().model or
                'generateContent' not in metadata.get('supportedGenerationMethods',[]) or
                metadata.get('inputTokenLimit')!=GeminiConfig().context_token_limit or metadata.get('outputTokenLimit',0)<1024):
            raise PermissionError('Read-only exact-model access prerequisite failed.')
        if ledger_snapshot()!=before or MATRIX.read_bytes()!=self.original:raise PermissionError('Preflight raced.')
        claim(OUTPUT/'cloud.execution.claim.json',{'freeze_sha256':external_hash,'maximum_inferences':3,'epoch':EPOCH})
        self.budget=self.budget.extend_request_ceiling(max_requests=126,authorization_epoch=EPOCH,
            authorization_note='Human explicit goal continuation: up to three newly frozen owned browser-canvas local-first trials. Prior fourth slot closed, all123 entries/unknowns and USD8 preserved. No retry/warm-up/release.')
        set_policy({**policy,'inference_authorized':True,'authorization_epoch':EPOCH,'max_requests':3,
            'max_usd':str(MAX_RESERVATION),'scope':'VISION-034 exactly three frozen owned browser integration cases; no following lot.'})

    def read(self,frame,*,capture_ns):
        with self.lock:
            matching=[name for name in ORDER if self.frames[name][1].frame_id==frame.frame_id]
            if self.closed or self.pending or len(matching)!=1 or matching[0] in self.used:
                return GroundedResult(frame.frame_id,self.name,'blocked',None,0,{'reason':'Frozen one-shot cloud slot unavailable.'})
            case=matching[0];checked(self.hash);self.used.add(case);self.pending=True
        record,approved=self.frames[case]; request=record['payload'];tap=None;transport=None;stop=False
        try:
            # Fresh read-only DNS lease before this one POST; no provider warm-up.
            dns=resolve_scope()
            transport=PersistentScopedTransport(provider='gemini',authorization_epoch=EPOCH,budget=self.budget,dns_scope=dns,api_key=self.key)
            self.transports.append(transport);transport.bind(request['canonical_sha256'],OUTPUT/(case+'.submission.claim.json'))
            tap=_OutputTap(transport)
            reader=VisiblePhaseDeadlineReader(GeminiConfig(),self.budget,
                [sha256(p).hexdigest() for _,p in frame.images()],transport=tap)
            scope=OwnedOutputScope('VISION-034',case,'gemini',reader.config.model,request['canonical_sha256'],
                tuple(sha256(p).hexdigest() for _,p in approved.images()),True)
            scope.verify(reader,frame)
            result=reader.read(frame,capture_ns=capture_ns)
            retention={'retained':False,'reason':'no_selected_output'}
            if tap.text is not None:
                public,private=inspect_output(tap.text,available_views={'table'})
                retention=self.store.write({'output_text':tap.text,'provenance':{**scope.__dict__,
                    'capture_ns':capture_ns,'scope':'owned browser integration; original deadline preserved',
                    'usage':result.diagnostics.get('usage')},'diagnosis':{'public':public,'private':private}})
                if sha256(self.store.read(retention['record_id'])['output_text'].encode()).hexdigest()!=retention['output_sha256']:
                    raise PermissionError('Protected recovery failed; no advice.')
            if result.diagnostics.get('unreconciled_usage') or (tap.text is not None and not retention['retained']):stop=True
            row={'case':case,'status':result.status,'elapsed_ms':result.elapsed_ms,'retention':retention,
                'diagnostics':result.diagnostics,'http_post_attempts':transport._request_count}
            self.rows.append(row);save(OUTPUT/'cloud-results.json',self.rows)
            return replace(result,diagnostics={**result.diagnostics,'retention':retention,'owned_integration_case':case})
        except Exception as exc:
            stop=True
            self.rows.append({'case':case,'status':'blocked','error_type':type(exc).__name__,'raw_error_saved':False})
            save(OUTPUT/'cloud-results.json',self.rows)
            return GroundedResult(frame.frame_id,self.name,'blocked',None,0,{'error_type':type(exc).__name__})
        finally:
            if tap is not None:tap.text=None
            if transport is not None:transport.close()
            with self.lock:self.pending=False
            if stop or len(self.used)==3:self.close()

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True
        MATRIX.write_bytes(self.original)
        for transport in self.transports:transport.close()
        after=ledger_snapshot()
        save(OUTPUT/'cloud-summary.json',{'experiment':'VISION-034','freeze_sha256':self.hash,'rows':self.rows,
            'used_cases':sorted(self.used),'new_reservations':after['receipt']['requests_attempted']-123,
            'unused_new_slots_closed':3-len(self.used),'ledger_before':self.frozen['ledger_before'],'ledger_after':after,
            'all_123_prior_entries_unchanged':json.loads(CANONICAL_LEDGER.read_text())['entries'][:123]==self.old_entries,
            'runtime_disarmed':MATRIX.read_bytes()==self.original,'pools_closed':all(t._closed for t in self.transports),
            'following_lot':False,'retry':0,'paid_warmup':0,'invoice_and_balance_verified':False})
        self.key=None


def serve(external_hash,*,port,cloud_lot=False):
    frozen,frames=checked(external_hash)
    from bjlab.integration_api import configure,sessions
    from bjlab.api import app,mount_ui
    import uvicorn
    lot=None
    try:
        if cloud_lot:lot=OwnedCloudLot(external_hash)
        titles={'stable-overlap':'1 · Carte sovrapposte — lettura stabile',
            'changing-rotation':'2 · Carte ruotate — cambia durante il cloud',
            'contradictory-total':'3 · Totale stampato incoerente — astensione',
            'clear':'Tavolo svuotato'}
        sources={name:{'title':titles[name],'path':OUTPUT/'inputs'/r['images'][0]['file'],
            'pixel_sha256':r['pixel_sha256'],
            'scenario':'change_while_pending' if name=='changing-rotation' else None,
            'switch_to':'clear' if name=='changing-rotation' else None} for name,(r,_) in frames.items()}
        configure(layout=LAYOUT,sources=sources,
            local_factory=lambda:FrozenGroundedLocal(FrozenLocalObservation()),
            cloud_factory=(lambda:lot) if lot else None)
        mount_ui()
        print(json.dumps({'url':'http://127.0.0.1:'+str(port)+'/?integration=1','cloud_slots':3 if lot else 0,
            'scope':'Owned browser canvas; existing desktop release untouched.'}),flush=True)
        uvicorn.run(app,host='127.0.0.1',port=port,log_level='warning')
    finally:
        if lot:lot.close()
        for identity,session in sessions.items():
            session.disconnect();save(OUTPUT/('browser-'+identity+'.json'),session.receipt())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--local',action='store_true')
    parser.add_argument('--serve',action='store_true');parser.add_argument('--cloud-lot',action='store_true')
    parser.add_argument('--freeze-sha256');parser.add_argument('--port',type=int,default=8788);args=parser.parse_args()
    if args.prepare:
        if args.local or args.serve or args.cloud_lot:parser.error('Preparation is a separate offline action.')
        prepare();print(json.dumps({'freeze_sha256':file_hash(OUTPUT/'freeze.json'),'provider_calls':0}))
    elif args.freeze_sha256:
        if args.local:
            if args.cloud_lot:parser.error('Local comparison cannot enable cloud.')
            rows=evaluate_local(args.freeze_sha256);print(json.dumps({'rows':len(rows),'provider_calls':0}))
        elif args.serve:serve(args.freeze_sha256,port=args.port,cloud_lot=args.cloud_lot)
        else:checked(args.freeze_sha256);print(json.dumps({'checked':True,'provider_calls':0}))
    else:parser.error('Explicit offline preparation or an external freeze hash is required.')
