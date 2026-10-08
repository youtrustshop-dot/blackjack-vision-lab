"""Read-only DNS preparation outside an original-capture decision deadline.

This cache performs no inference or paid warm-up. Official OS answers expire;
an unavailable lease fails closed immediately. A late resolver cannot trigger
HTTP, renew evidence or publish an answer after the cache has been closed.
"""
from copy import deepcopy
import ipaddress
from threading import Event, Lock, Thread
import time

from .controlled_http import HOSTS, resolve_scope


class DnsLeaseUnavailable(PermissionError):
    """Public guard code only; no credential, address or raw resolver error."""
    def __init__(self, code):
        self.code = code
        super().__init__('Official DNS lease unavailable: '+code)


class PreparedDnsLease:
    def __init__(self, answers, *, resolver=resolve_scope, clock=time.monotonic):
        self.resolver, self.clock = resolver, clock
        self.lock, self.stopped = Lock(), Event()
        self.answers = deepcopy(answers)
        self.thread = None
        self.refreshes = self.failures = 0
        self.snapshot()  # Never serve an invalid initial scope.

    def snapshot(self, *, required_seconds=3.1):
        """A bounded copy only; never perform DNS in the critical path."""
        with self.lock:
            if self.stopped.is_set():
                raise DnsLeaseUnavailable('preparation_closed')
            answers = deepcopy(self.answers)
        now = self.clock()
        for host in HOSTS:
            entry = answers.get(host)
            if not entry:
                raise DnsLeaseUnavailable('missing_host')
            if entry['expires_at'] <= now+required_seconds:
                raise DnsLeaseUnavailable('insufficient_remaining_lease')
            address = ipaddress.ip_address(entry['address'])
            if address.version != 4 or not address.is_global:
                raise DnsLeaseUnavailable('nonpublic_ipv4')
        return answers

    def start(self):
        if self.thread is not None or self.stopped.is_set():
            raise ValueError('One background DNS preparation worker only.')

        def refresh():
            while not self.stopped.is_set():
                with self.lock:
                    until = min(e['expires_at'] for e in self.answers.values())-self.clock()
                if self.stopped.wait(min(15., max(.1, until-5.))):
                    break
                try:
                    answers = self.resolver()
                    # Validation does not mutate the active lease.
                    check = PreparedDnsLease(answers, resolver=self.resolver, clock=self.clock)
                    check.snapshot()
                    with self.lock:
                        if self.stopped.is_set():
                            break
                        self.answers = deepcopy(answers)
                        self.refreshes += 1
                except Exception:
                    with self.lock:
                        self.failures += 1
                    # No inference retry. An expired previous lease stays expired.
                    if self.stopped.wait(1.):
                        break
        self.thread = Thread(target=refresh, daemon=True, name='owned-readonly-dns-preparation')
        self.thread.start()
        return self

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=.1)
        return {'closed': True, 'refreshes': self.refreshes, 'failures': self.failures,
                'inference_requests': 0, 'late_resolver_cannot_start_http': True}
