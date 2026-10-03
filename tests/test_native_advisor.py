import copy
import time

from fastapi.testclient import TestClient
from bjlab.api import app
from bjlab.engine import Rules
from bjlab.live import LiveObserver
from bjlab.native_advisor import NativeHost,snapshot


def observer():
    item=LiveObserver(Rules(),samples=100)
    item.last_report={'source_id':item.source_id,'state_id':'s1','player':['7','2'],'dealer':['6'],
        'advice':{'best_action':'double'},'decision':None,'gate':{'solver_allowed':True}}
    item.native_evidence={'at':100.,'epoch':2,'captured_epoch_ms':1234}
    item.native_view={'epoch':2,'stale':False,'verification':'disabled'}
    return item


def test_view_refresh_cannot_renew_expired_evidence_or_mutate_authoritative_report():
    item=observer()
    assert snapshot(item,now=101.)['report']['advice']['best_action']=='double'
    for now in (103.,104.,200.):
        result=snapshot(item,now=now)
        assert result['stale'] and result['report']['advice'] is None
    assert item.last_report['advice']['best_action']=='double'


def test_new_motion_epoch_blocks_late_old_frame_and_verifier_needs_current_state():
    item=observer();item.native_view={'epoch':3,'stale':False,'verification':'disabled'}
    assert snapshot(item,now=100.5)['stale']
    item.native_evidence['epoch']=3
    item.native_view.update(verification='disagreement',state_id='s1')
    assert snapshot(item,now=100.5)['stale']
    item.native_view.update(verification='agreement',state_id='old-state')
    assert snapshot(item,now=100.5)['stale']
    item.native_view['state_id']='s1';assert not snapshot(item,now=100.5)['stale']
    item.stop();assert snapshot(item,now=100.5)['stale']


def test_native_acknowledgements_are_bound_to_latest_request_and_selected_table():
    messages=[];host=NativeHost(True,messages.append)
    old=host.control('open','one','Table 1');new=host.control('open','two','Table 2')
    host.acknowledge({'event':'native_advisor_ack','request_id':old,'stream_id':'one','visible':True})
    assert host.status()['pending']
    host.acknowledge({'event':'native_advisor_ack','request_id':new,'stream_id':'two','visible':True})
    assert host.status()['visible'] and not host.status()['pending']
    host.acknowledge({'event':'native_advisor_ack','request_id':None,'stream_id':'two','visible':False})
    assert not host.status()['visible'] and host.status()['stream_id']=='two'
    assert len(messages)==2


def test_native_writes_refuse_foreign_origins_and_do_not_create_an_observer():
    from bjlab.live_api import observers
    before=set(observers)
    with TestClient(app,base_url='http://127.0.0.1:8000') as client:
        assert client.post('/api/native/advisor/control',json={'operation':'open','stream_id':'missing'},
                           headers={'origin':'https://elsewhere.invalid','x-bjlab-local':'1'}).status_code==403
        assert client.post('/api/native/advisor/control',json={'operation':'open','stream_id':'missing'},
                           headers={'origin':'http://127.0.0.1:8000','x-bjlab-local':'1'}).status_code==404
    assert set(observers)==before


def test_old_table_view_cannot_close_or_pin_the_new_selected_advisor(monkeypatch):
    import bjlab.native_advisor as module
    messages=[]
    host=NativeHost(True,messages.append)
    host.selected='current-table';host.visible=True
    monkeypatch.setattr(module,'host',host)
    with TestClient(app,base_url='http://127.0.0.1:8000') as client:
        for operation in ('hide','topmost'):
            response=client.post('/api/native/advisor/control',
                json={'operation':operation,'stream_id':'previous-table','topmost':True},
                headers={'origin':'http://127.0.0.1:8000','x-bjlab-local':'1'})
            assert response.status_code==409
    assert not messages and host.status()['visible'] and host.selected=='current-table'
