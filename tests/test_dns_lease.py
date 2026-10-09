from threading import Event
import time

import pytest

from bjlab.controlled_http import HOSTS
from bjlab.dns_lease import PreparedDnsLease


def answers(expiry=60):
    return {host: {'address': '8.8.8.8', 'expires_at': expiry} for host in HOSTS}


def test_snapshot_never_resolves_and_expiry_or_close_cannot_extend_capture_deadline():
    now = [0.]
    def fail():
        raise AssertionError('Critical path must never resolve DNS.')
    lease = PreparedDnsLease(answers(), resolver=fail, clock=lambda: now[0])
    value = lease.snapshot(); value[HOSTS[0]]['expires_at'] = 10000
    now[0] = 57.
    with pytest.raises(PermissionError): lease.snapshot()
    now[0] = 0.
    assert lease.snapshot()[HOSTS[0]]['expires_at'] == 60
    lease.close()
    with pytest.raises(PermissionError): lease.snapshot()


def test_late_background_resolver_does_not_reopen_a_closed_lease_or_start_http():
    began, release = Event(), Event()
    def delayed():
        began.set(); release.wait(1.); return answers(100.)
    lease = PreparedDnsLease(answers(6.), resolver=delayed, clock=lambda: 2.).start()
    assert began.wait(1.)
    closed = lease.close(); release.set()
    lease.thread.join(1.)
    assert closed['inference_requests'] == 0 and lease.refreshes == 0
    with pytest.raises(PermissionError): lease.snapshot()


def test_private_addresses_and_insufficient_lease_are_rejected_before_any_inference():
    bad = answers(); bad[HOSTS[0]]['address'] = '127.0.0.1'
    with pytest.raises(PermissionError): PreparedDnsLease(bad, clock=lambda: 0.)
    with pytest.raises(PermissionError): PreparedDnsLease(answers(2.), clock=lambda: 0.)
