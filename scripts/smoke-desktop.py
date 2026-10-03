"""Exercise a fresh frozen/native release without automating desktop windows."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import tempfile
import threading
import time
from urllib.request import Request, urlopen


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def smoke_directory(work):
    temporary=tempfile.TemporaryDirectory(prefix='bjlab-smoke-',dir=work)
    target=Path(temporary.name).resolve()
    assert target.is_relative_to(work)
    try:yield target
    finally:
        # WebView2 can release an owned temporary file shortly after the
        # native parent and backend exit. Retry that scoped cleanup only.
        deadline=time.monotonic()+20
        while True:
            try:temporary.cleanup();break
            except PermissionError:
                if time.monotonic()>=deadline:raise
                time.sleep(.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    release, work = args.release.resolve(), args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    binary = args.binary.resolve() if args.binary else release / ('Blackjack Vision Lab.exe' if args.native else 'bjlab-backend.exe')
    environment = dict(os.environ)
    for variable in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','CARGO_HOME','RUSTUP_HOME'):
        environment.pop(variable,None)
    environment['PATH'] = str(Path(os.environ['SystemRoot'])/'System32')
    environment['BJLAB_FONT_PATH'] = 'invalid-external-font'
    report = {'version':'0.2.0','binary':binary.name,'sha256':digest(binary),
              'mode':'native-hidden' if args.native else 'frozen-backend',
              'runtime_path':'Windows System32 only; no Python/Node/Rust paths',
              'personal_display_picker_selected':False}
    with smoke_directory(work) as directory:
        temporary=Path(directory).resolve()
        assert temporary.is_relative_to(work)
        environment.update(TEMP=str(temporary),TMP=str(temporary))
        native_ready=temporary/'native-ready.json'
        if args.native:
            environment.update(BJLAB_DESKTOP_SMOKE='1',BJLAB_NATIVE_READY_FILE=str(native_ready),
                               BJLAB_NATIVE_SMOKE_EXIT_AFTER_MS='25000')
            command=[str(binary)]
        else:
            selftest=subprocess.run([str(binary),'--self-test'],cwd=temporary,env=environment,
                capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            assert selftest.returncode==0,selftest.stderr
            checked=json.loads(selftest.stdout)
            assert checked['frozen'] and checked['status']=='ok'
            assert checked['build_provenance']['version']=='0.2.0'
            for name,expected in checked['build_provenance']['source_sha256'].items():
                assert digest(project/name)==expected,'Stale recorded source: '+name
            report['self_test']=checked
            command=[str(binary),'--port','0','--parent-pid',str(os.getpid())]
        process=subprocess.Popen(command,cwd=temporary,env=environment,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        lines=queue.Queue()
        def read_output():
            for line in process.stdout:lines.put(line)
        threading.Thread(target=read_output,daemon=True).start()
        backend_handle=None
        try:
            ready=None
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('Executable exited before readiness')
                if args.native:
                    try:ready=json.loads(native_ready.read_text());break
                    except (OSError,ValueError):time.sleep(.1)
                else:
                    try:line=lines.get(timeout=.1)
                    except queue.Empty:continue
                    try:message=json.loads(line)
                    except ValueError:continue
                    if message.get('event')=='backend_ready':ready=message;break
            assert ready,'Executable readiness timed out'
            base=ready['url']
            if args.native:
                assert ready['pid']==process.pid and ready['window']=='main' and ready['hidden']
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
                kernel.OpenProcess.restype=wintypes.HANDLE
                kernel.WaitForSingleObject.argtypes=(wintypes.HANDLE,wintypes.DWORD)
                kernel.WaitForSingleObject.restype=wintypes.DWORD
                kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
                backend_handle=kernel.OpenProcess(0x100000,False,ready['backend_pid'])
                assert backend_handle
                report['native_window_created']=True
            def request(path,body=None,*,data=None):
                if body is not None:data=json.dumps(body).encode()
                with urlopen(Request(base+path,data=data,headers={'Content-Type':'image/png' if data is not None and body is None else 'application/json'}),timeout=30) as response:
                    payload=response.read()
                    return json.loads(payload) if response.headers.get_content_type()=='application/json' else payload
            health=request('/api/health')
            assert health['status']=='ok' and health['version']=='0.2.0'
            assert request('/api/roadmap')==json.loads((project/'docs/REQUIREMENTS.json').read_text(encoding='utf-8'))
            html=request('/')
            assert html==(project/'ui/dist/index.html').read_bytes()
            asset=re.search(rb'src="([^"]+\.js)"',html).group(1).decode()
            javascript=request(asset)
            assert javascript==(project/'ui/dist'/asset.lstrip('/')).read_bytes()
            assert b'Share screen' in javascript and b'Floating advisor' in javascript
            session=request('/api/sessions',{'seed':42})
            sid=session['session_id']
            session=request('/api/sessions/'+sid+'/deal',{})
            analysis=request('/api/sessions/'+sid+'/analyze',{'timeout_ms':1500,'max_nodes':60000})
            assert analysis['status']=='ok' and analysis['result']['exact']
            assert analysis['result']['best_action']=='double'
            live=request('/api/live',{'samples':500,'fresh_shoe':True})
            identity=live['stream_id']
            sequence=0
            stages=[]
            for stage in range(3):
                pixels=request('/api/sessions/'+sid+'/frame?live_context=true')
                assert pixels.startswith(b'\x89PNG')
                for _ in range(5):
                    result=request('/api/live/'+identity+'/frame?sequence='+str(sequence)+'&timestamp='+str(sequence+1),data=pixels)
                    sequence+=1
                assert result['source']=='live-video-pixels'
                assert result['observed_cards']==session['shoe']['seen']
                assert result['running_count']==session['shoe']['running_count']
                if stage==0:
                    assert result['decision']['best_action']=='double'
                    row=result['decision']['actions']['double']
                    assert abs(row['win']+row['push']+row['loss']-1)<1e-12
                    assert not result['decision']['exact'] and len(row['win_ci95'])==2
                    report['initial_live_probability']=row
                elif stage==1:assert result['decision'] is None
                stages.append({'round':session['round_id'],'phase':session['phase'],
                               'observed_cards':result['observed_cards'],'running_count':result['running_count'],
                               'best_action':result['decision']['best_action'] if result['decision'] else None})
                if stage<2:session=request('/api/sessions/'+sid+'/bot-step',{})
            report.update(status='pass',health=health,ui_matches_build=True,
                ui_javascript_sha256=hashlib.sha256(javascript).hexdigest(),
                exact_solver_best_action='double',live_pixel_stages=stages,
                live_counts_match_public_exposures=True,live_processed_observations=sequence,
                bundled_roadmap_matches_source=True,source_independent_launch=True)
            if args.native:
                code=process.wait(timeout=55)
                assert code==0 and kernel.WaitForSingleObject(backend_handle,20000)==0
                report['native_exit']='bounded hidden smoke used normal AppHandle Exit path'
                report['owned_backend_exited']=True
            else:
                process.stdin.write('shutdown\n');process.stdin.flush()
                code=process.wait(timeout=20)
            host,port=base.removeprefix('http://').split(':')
            with socket.socket() as connection:
                connection.settimeout(1)
                assert connection.connect_ex((host,int(port)))!=0
            deadline=time.monotonic()+15
            while list(temporary.glob('_MEI*')) and time.monotonic()<deadline:time.sleep(.1)
            assert not list(temporary.glob('_MEI*')),'One-file runtime assets leaked'
            report.update(graceful_exit_code=code,local_port_closed=True,new_mei_leaks=0)
        finally:
            if process.poll() is None:
                if not args.native:
                    try:process.stdin.write('shutdown\n');process.stdin.flush();process.wait(timeout=20)
                    except (OSError,subprocess.TimeoutExpired):process.terminate();process.wait(timeout=10)
                else:process.terminate();process.wait(timeout=10)
            if backend_handle:kernel.CloseHandle(backend_handle)
    path=args.evidence.resolve() if args.evidence else release/('native-smoke.json' if args.native else 'backend-smoke.json')
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'evidence':str(path),'sha256':report['sha256'],
                      'live_pixel_stages':report['live_pixel_stages'],'new_mei_leaks':report['new_mei_leaks']}))


if __name__=='__main__':main()
