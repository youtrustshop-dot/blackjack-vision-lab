"""Start the real source server with no provider credentials; localhost checks."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, type=Path,
    help='New local output directory; existing evidence is never overwritten.')
OUT = parser.parse_args().output.resolve()
if not OUT.is_relative_to((ROOT/'artifacts').resolve()):
    parser.error('Smoke outputs must stay in the ignored project artifacts directory.')
OUT.mkdir(parents=True, exist_ok=False)
with socket.socket() as reservation:
    reservation.bind(('127.0.0.1', 0))
    port = reservation.getsockname()[1]
base = f'http://127.0.0.1:{port}'
environment = {key: value for key, value in os.environ.items()
    if not key.startswith(('OPENAI_', 'GEMINI_', 'GOOGLE_', 'BJLAB_NATIVE_'))}
checks = []

def request(path, *, method='GET', body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base+path, data=data, method=method,
        headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read(), response.headers['Content-Type']

with (OUT/'source-server.log').open('wb') as log:
    process = subprocess.Popen([sys.executable, '-m', 'bjlab.cli', 'serve', '--port', str(port)],
        cwd=ROOT, env=environment, stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        deadline = time.monotonic()+30
        while True:
            try:
                health = json.loads(request('/api/health')[0]); break
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Source server did not start.')
                time.sleep(.1)
        assert health['status'] == 'ok' and health['local_only'] is True
        checks.append('real source server boots on loopback without provider credentials')
        page, mime = request('/')
        assert 'text/html' in mime and b'<div id="root"' in page
        checks.append('built frontend is served by the real backend')
        experiments = json.loads(request('/api/vision/experiments')[0])
        assert experiments['api_access_policy']['inference_authorized'] is False
        checks.append('experiment matrix keeps inference disarmed')
        try:
            request('/api/research/r1/configuration')
            raise AssertionError('Default backend must not enable the owned cloud experiment.')
        except urllib.error.HTTPError as error:
            assert error.code == 503
        checks.append('owned integration needs explicit configuration; no default cloud factory')
        native = json.loads(request('/api/native/advisor/status')[0])
        assert native['available'] is False
        checks.append('browser server does not pretend to supply the native always-on-top host')
        created = json.loads(request('/api/sessions', method='POST', body={'seed': 42})[0])
        identity = created['session_id']
        request('/api/sessions/'+identity+'/deal', method='POST', body={'bet': 1})
        pixels, mime = request('/api/sessions/'+identity+'/frame')
        assert 'image/png' in mime and pixels.startswith(b'\x89PNG')
        request('/api/sessions/'+identity, method='DELETE')
        checks.append('seeded local simulation deals, serves actual pixels and closes without a provider')
        value = {'status': 'passed', 'checks': checks,
            'scope': 'default source startup and loopback HTTP; not physical capture/vision accuracy',
            'provider_credentials_in_child': False, 'inference_requests': 0,
            'installed_release_changed': False}
        (OUT/'source-smoke.json').write_text(json.dumps(value, indent=2)+'\n')
        print(json.dumps(value))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)
