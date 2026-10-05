"""Offline process-only DNS control; no reachability/provider evidence."""
import socket

import pytest

from validation.tools.gemini_schema_network_control import HOST, verified_address


def test_dns_control_changes_only_exact_google_host_and_always_restores(monkeypatch):
    calls=[]
    def original(*args,**kwargs): calls.append((args,kwargs));return ['offline-sentinel']
    monkeypatch.setattr(socket,'getaddrinfo',original)
    with pytest.raises(RuntimeError):
        with verified_address('8.8.8.8'):
            assert socket.getaddrinfo(HOST,443)==['offline-sentinel']
            assert calls[-1][0]==('8.8.8.8',443,socket.AF_INET,socket.SOCK_STREAM)
            socket.getaddrinfo('unrelated.example',443)
            assert calls[-1][0]==('unrelated.example',443)
            raise RuntimeError('Even interruption restores the process resolver.')
    assert socket.getaddrinfo is original


@pytest.mark.parametrize('address',['127.0.0.1','192.168.1.1','10.0.0.1','::1'])
def test_dns_control_rejects_private_or_non_ipv4_addresses(address):
    with pytest.raises((PermissionError,ValueError)):
        with verified_address(address): pytest.fail('Must not enter resolver override.')
