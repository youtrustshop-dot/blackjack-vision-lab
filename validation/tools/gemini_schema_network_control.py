"""Resolve a diagnosed local DNS delay without changing host/TLS or the PC.

Supply an IPv4 just obtained from the host's DNS answer, verify ordinary HTTPS
with a read-only unauthenticated GET first, then resume distinct causal probes.
Never retry the consumed probe. All timed-out charge reservations remain held.
"""
import argparse
import asyncio
from contextlib import contextmanager
from hashlib import sha256
from ipaddress import IPv4Address
import json
from pathlib import Path
import socket
from types import SimpleNamespace

from bjlab.live_cloud import DiagnosticHTTPError, measured_request
from validation.tools.gemini_request_diagnosis import write
from validation.tools.gemini_schema_cause import PROBES, execute

HOST='generativelanguage.googleapis.com'


@contextmanager
def verified_address(ipv4):
    address=IPv4Address(ipv4)
    if not address.is_global: raise PermissionError('Only a public address from the observed Google DNS answer is allowed.')
    original=socket.getaddrinfo
    def resolve(host,port,*args,**kwargs):
        if host in (HOST,HOST.encode()):
            return original(str(address),port,socket.AF_INET,socket.SOCK_STREAM)
        return original(host,port,*args,**kwargs)
    socket.getaddrinfo=resolve
    try: yield
    finally: socket.getaddrinfo=original


async def check():
    transport=SimpleNamespace(_key='')
    try:
        await measured_request(transport,'GET','models/gemini-3.5-flash-lite',10.,gemini=True)
        status=200
    except DiagnosticHTTPError as exc:
        status=exc.status_code
    if status not in (200,400,401,403):
        raise PermissionError('Google HTTPS reachability control did not pass.')
    return {'read_only':True,'api_key_sent':False,'http_status':status,'timing':transport.timings,
        'tls_verification':True,'hostname_and_sni':HOST,'dns_override_scope':'this Python process only'}


def run(ipv4,probe,output):
    output=Path(output)
    with verified_address(ipv4):
        receipt=asyncio.run(check())
        receipt.update(ipv4_from_observed_dns_answer=ipv4,
            wrapper_source_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
        with (output/(probe+'-network-control.json')).open('x',encoding='utf-8') as handle:
            json.dump(receipt,handle,indent=2)
        if (output/'STOP.json').exists():
            stop=json.loads((output/'STOP.json').read_text())
            previous=json.loads((output/(stop['probe']+'.json')).read_text())
            timing=previous.get('network_timing',{})
            if (previous.get('status')!='timeout' or 'http_status' in previous or
                    any(k in timing for k in ('send_request_headers_ms','send_request_body_ms','headers_received_ms'))):
                raise PermissionError('Only a pre-submission DNS/connectivity stop may resume after verified read-only recovery.')
            if probe==stop['probe']: raise PermissionError('Do not retry the consumed probe.')
            # Preserve the stop rather than deleting its history; no ledger reset.
            (output/'STOP.json').replace(output/(stop['probe']+'-network-stop.json'))
            write(output/'network-recovery.json',{'stopped_probe':stop['probe'],
                'next_distinct_probe':probe,'reason':'DNS resolution timed out; observed DNS IPv4 verified with ordinary hostname/TLS GET.',
                'old_charge_reservation_retained':True,'money_and_request_caps_unchanged':True})
        return execute(probe,output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe',choices=PROBES)
    parser.add_argument('--ipv4',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.ipv4,args.probe,args.output),indent=2))
