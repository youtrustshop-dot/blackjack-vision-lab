"""One local authoritative live observer, viewed by one native advisor window.

Control messages use the inherited sidecar pipe; HTTP cannot choose a URL,
execute a process or create an observer. No cross-origin writes are allowed.
"""
import copy
import json
import os
import secrets
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal

from .live_api import observers, registry_lock

router=APIRouter(prefix='/api/native/advisor')


class NativeHost:
    def __init__(self,enabled=False,emit=None):
        self.enabled=enabled
        self.emit=emit or (lambda message:print(json.dumps(message),flush=True))
        self.lock=threading.RLock()
        self.selected=None;self.table_name='';self.visible=False;self.topmost=False
        self.pending=None;self.error=None
        self.proof={}

    def control(self,operation,stream_id=None,table_name='',topmost=None):
        with self.lock:
            if not self.enabled:raise ValueError('Native advisor host is unavailable in this browser/source server.')
            if operation=='open':
                self.selected=stream_id;self.table_name=table_name
            identity=secrets.token_hex(16)
            message={'event':'native_advisor','operation':operation,'request_id':identity,
                'stream_id':self.selected,'table_name':self.table_name,
                'topmost':self.topmost if topmost is None else topmost}
            self.pending={'request_id':identity,'at':time.monotonic()}
            self.error=None;self.emit(message)
            return identity

    def acknowledge(self,message):
        with self.lock:
            if not self.enabled or message.get('event')!='native_advisor_ack':return
            if message.get('stream_id')!=self.selected:return
            identity=message.get('request_id')
            if identity is not None and (not self.pending or identity!=self.pending['request_id']):return
            if identity is not None:self.pending=None
            self.visible=bool(message.get('visible',False));self.topmost=bool(message.get('topmost',False))
            self.error=message.get('error')
            self.proof={key:message.get(key) for key in ('window','main_minimized','monitor_count')}

    def status(self):
        with self.lock:
            if self.pending and time.monotonic()-self.pending['at']>4:
                self.pending=None;self.error='Native window did not acknowledge the request.'
            return {'available':self.enabled,'visible':self.visible,'stream_id':self.selected,
                'table_name':self.table_name,'topmost':self.topmost,'pending':bool(self.pending),'error':self.error,'native_proof':self.proof}


host=NativeHost(os.getenv('BJLAB_NATIVE_ADVISOR')=='1')


def same_origin(request):
    if request.url.hostname not in ('127.0.0.1','localhost') or request.headers.get('x-bjlab-local')!='1':
        raise HTTPException(403,'Native advisor writes require the local application.')
    if request.headers.get('origin') not in (None,str(request.base_url).rstrip('/')):
        raise HTTPException(403,'Cross-origin native advisor control is forbidden.')


class Control(BaseModel):
    operation:Literal['open','hide','topmost']
    stream_id:str|None=Field(default=None,max_length=80)
    table_name:str=Field(default='Table',max_length=80)
    topmost:bool|None=None


@router.get('/status')
def status():
    result=host.status()
    with registry_lock:
        result['tables']=[{'stream_id':identity,'source_id':observer.source_id,
                          'table_name':getattr(observer,'table_name','Observed table')}
                         for identity,observer in observers.items() if not observer.stopped]
    return result


@router.post('/control')
def control(request:Request,body:Control):
    same_origin(request)
    if body.operation=='open':
        observer=observers.get(body.stream_id)
        if observer is None:raise HTTPException(404,'Start observing the selected table first.')
    elif body.stream_id and body.stream_id!=host.status()['stream_id']:
        raise HTTPException(409,'This advisor belongs to another table.')
    try:
        identity=host.control(body.operation,body.stream_id,body.table_name,body.topmost)
    except ValueError as exc:raise HTTPException(503,str(exc)) from exc
    return {'request_id':identity,'pending':True}


class ViewStatus(BaseModel):
    epoch:int=Field(default=0,ge=0)
    stale:bool=False
    state_id:str|None=Field(default=None,max_length=150)
    verification:Literal['disabled','pending','agreement','disagreement','inconclusive']='disabled'


@router.post('/{stream_id}/view')
def update_view(stream_id:str,body:ViewStatus,request:Request):
    same_origin(request)
    observer=observers.get(stream_id)
    if observer is None:raise HTTPException(404,'Observation stopped.')
    with observer.lock:
        previous=getattr(observer,'native_view',{})
        if body.epoch<previous.get('epoch',0):raise HTTPException(409,'Obsolete capture view epoch.')
        observer.native_view=body.model_dump()
    return {'updated':True}


def snapshot(observer,*,now=None):
    now=time.monotonic() if now is None else now
    with observer.lock:
        report=copy.deepcopy(observer.last_report)
        evidence=getattr(observer,'native_evidence',None)
        view=getattr(observer,'native_view',{})
        age=now-evidence['at'] if evidence else float('inf')
        valid=bool(report and evidence and not observer.stopped and age<=2.2 and
            evidence['epoch']>=view.get('epoch',0) and not view.get('stale',False))
        verification=view.get('verification','disabled')
        if verification!='disabled' and (verification!='agreement' or not report or view.get('state_id')!=report.get('state_id')):
            valid=False
        if report and not valid:
            report['advice']=None;report['decision']=None
            report['gate']={'solver_allowed':False,'reasons':['Evidence expired, changed or independent verification is incomplete.']}
        return {'report':report,'stale':not valid,'evidence_ttl_ms':max(0,(2.2-age)*1000) if valid else 0,
                'source_id':observer.source_id,'evidence_timestamp':evidence.get('captured_epoch_ms') if evidence else None}


@router.get('/{stream_id}/state')
def advisor_state(stream_id:str):
    if host.status()['stream_id']!=stream_id:raise HTTPException(409,'Advisor is associated with another table.')
    observer=observers.get(stream_id)
    if observer is None:return {'report':None,'stale':True,'evidence_ttl_ms':0,'reason':'Observation stopped.'}
    return snapshot(observer)
