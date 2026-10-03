"""Bounded, non-queuing live work. Monte Carlo never owns the video lock."""
from concurrent.futures import ThreadPoolExecutor
import copy
import threading
import time

from . import live


class LiveAnalysisPool:
    def __init__(self, workers=2, timeout_ms=1200):
        self.workers = workers
        self.timeout_ms = timeout_ms
        self.slots = threading.BoundedSemaphore(workers)
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='live-estimate')
        self.metrics_lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.rejected = 0

    def submit(self, observer):
        with observer.lock:
            if observer.stopped or observer.analysis_input is None or observer.analysis_status not in ('ready', 'busy'):
                return False
            if not self.slots.acquire(blocking=False):
                observer.analysis_status = 'busy'
                observer.last_report['analysis']['status'] = 'busy'
                with self.metrics_lock:
                    self.rejected += 1
                return False
            snapshot = copy.deepcopy(observer.analysis_input)
            cancel = observer.analysis_cancel
            observer.analysis_status = 'pending'
            observer.last_report['analysis']['status'] = 'pending'
            with self.metrics_lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            try:
                self.executor.submit(self._run, observer, snapshot, cancel)
            except RuntimeError:
                self._release()
                observer.analysis_status = 'unavailable'
                observer.last_report['analysis']['status'] = 'unavailable'
                return False
            return True

    def _release(self):
        with self.metrics_lock:
            self.active -= 1
        self.slots.release()

    def _run(self, observer, snapshot, cancel):
        started = time.monotonic()
        decision, status = None, 'complete'
        try:
            live.check_analysis_budget(None, cancel)
            arguments = {key: value for key, value in snapshot.items() if key not in ('state_id', 'base_advice')}
            decision = live.estimate_actions(**arguments, timeout_ms=self.timeout_ms, cancel_event=cancel)
        except live.AnalysisStopped as exc:
            status = str(exc)
        except Exception:
            # An estimate failure must not take down valid basic advice.
            status = 'error'
        try:
            elapsed = (time.monotonic() - started) * 1000
            with observer.lock:
                if observer.stopped or cancel.is_set() or observer.state_id != snapshot['state_id']:
                    return
                observer.analysis_status, observer.analysis_ms = status, elapsed
                observer.decision = decision
                report = observer.last_report
                report['analysis'] = {'state_id': snapshot['state_id'], 'status': status, 'elapsed_ms': elapsed,
                                      'budget_ms': self.timeout_ms}
                report['decision'] = decision
                if decision:
                    advice = copy.deepcopy(snapshot['base_advice'])
                    selected = decision.get('best_action')
                    advice['composition_action'] = selected
                    if selected in advice['legal_actions'] and decision.get('ranking_resolved'):
                        advice['best_action'], advice['basis'] = selected, 'observed-composition'
                        advice['explanation'][-1] = f'Use the resolved observed-composition estimate: {selected}.'
                    report['advice'] = advice
        finally:
            self._release()

    def metrics(self):
        with self.metrics_lock:
            return {'workers': self.workers, 'active': self.active, 'peak': self.peak,
                    'rejected': self.rejected, 'queue_capacity': 0, 'budget_ms': self.timeout_ms}

    def shutdown(self):
        self.executor.shutdown(wait=True)


class LiveFramePool:
    """Reserve before reading the body; release only when real work ends."""
    def __init__(self, workers=5):
        self.workers = workers
        self.slots = threading.BoundedSemaphore(workers)
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='live-frame')

    def reserve(self, observer):
        if not observer.frame_slot.acquire(blocking=False):
            return False
        if not self.slots.acquire(blocking=False):
            observer.frame_slot.release()
            return False
        return True

    def release(self, observer):
        observer.frame_slot.release()
        self.slots.release()

    def submit_reserved(self, observer, function):
        def work():
            try:
                return function()
            finally:
                self.release(observer)
        return self.executor.submit(work)
