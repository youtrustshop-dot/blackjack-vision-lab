"""Real producer/error path, fake socket-free transport; no provider observations."""
from dataclasses import replace
from threading import Thread
import socket

import pytest

from bjlab import paired_deadline_reader as live_path
from bjlab.hybrid_evidence import CurrentEvidence
from bjlab.paired_persistent_http import canonical_digest
from tests.test_r1_readers import frame
from validation.tools import gemini_visible_phase_check as runner


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args,**kwargs):raise AssertionError('No socket/DNS in source-error regressions.')
    monkeypatch.setattr(socket,'socket',fail)
    monkeypatch.setattr(socket,'getaddrinfo',fail)


class Budget:
    def __init__(self):self.reserves=[]
    def receipt(self):return {'requests_attempted':len(self.reserves)}
    def reserve(self,cost):self.reserves.append(cost);raise AssertionError('No API reservation expected.')


class Transport:
    def __init__(self):
        self._request_count=0;self._closed=False;self.initialization_ms=0;self.timings={}
    def post(self,*args,**kwargs):
        self._request_count+=1;raise AssertionError('No model post expected.')
    def close(self):self._closed=True


class Local:
    name='source-failure-fixture'
    def __init__(self):self.calls=0
    def read(self,native):self.calls+=1;raise AssertionError('No local read without source.')


def exercise(monkeypatch,tmp_path,evidence_type):
    local=Local();budget=Budget();transport=Transport();solver=[];workers=[]
    monkeypatch.setattr(runner,'FrozenLocalObservation',lambda:local)
    monkeypatch.setattr(runner,'CurrentEvidence',evidence_type)
    monkeypatch.setattr(runner,'OUTPUT',tmp_path)
    monkeypatch.setattr(live_path,'recommend',lambda *a,**k:solver.append((a,k)))
    def tracked_worker(*args,**kwargs):
        thread=Thread(*args,**kwargs);workers.append(thread);return thread
    monkeypatch.setattr(runner,'Thread',tracked_worker)
    native=replace(frame(),details=())
    record={'payload':{'canonical_sha256':canonical_digest(runner.payload_for(native))},
        'independent_session':'owned-source-error-fixture'}
    value=runner.run_headless(record,native,{},budget,transport,None)
    assert not value['executed'] and not value['presented']
    assert value['advice'] is None and value['advisor_payload'] is None
    assert value['timing'] is None and value['revalidation'] is None and value['evaluation'] is None
    assert value['cloud_reserved_attempts']==0 and value['http_post_transport_attempts']==0
    assert not budget.reserves and transport._request_count==0 and transport._closed
    assert local.calls==0 and not solver
    assert workers and all(not worker.is_alive() for worker in workers)
    assert value['producer']['worker_stopped'] and value['transport_closed']
    assert value['retention']=={'retained':False,'reason':'source_not_available'}
    assert (tmp_path/'hybrid.json').exists()
    return value


def test_producer_failure_before_first_frame_retains_cause_and_closes_resources(monkeypatch,tmp_path):
    class FailedCapture(CurrentEvidence):
        def capture(self,*args,**kwargs):raise ValueError('Controlled first-capture failure.')
    value=exercise(monkeypatch,tmp_path,FailedCapture)
    assert value['reason']=='producer_failed_before_capture'
    assert value['producer']['error_types']==['ValueError']
    assert value['producer']['captures_before_source_failure']==0
    assert not value['local_first_invoked']


def test_source_disappearing_between_ready_and_internal_snapshot_keeps_early_return(monkeypatch,tmp_path):
    class DisappearingCapture(CurrentEvidence):
        def __init__(self):super().__init__();self.snapshots=0;self.disappeared=False
        def capture(self,*args,**kwargs):
            if self.disappeared:raise ConnectionError('Controlled source loss.')
            return super().capture(*args,**kwargs)
        def snapshot(self):
            self.snapshots+=1
            if self.snapshots==2:
                self.disappeared=True;self.disconnect()
            return super().snapshot()
    value=exercise(monkeypatch,tmp_path,DisappearingCapture)
    assert value['reason']=='no_current_capture' and value['route']=='none'
    assert value['producer']['captures_before_source_failure']>=1
    assert value['local_first_invoked']
