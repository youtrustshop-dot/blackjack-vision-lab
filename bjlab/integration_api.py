"""Opt-in local owned-canvas experiment. Never a default cloud live observer."""
import asyncio
from pathlib import Path
from threading import Lock
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .integrated_r1 import IntegratedR1Session, MAX_BYTES

router = APIRouter(prefix='/api/research/r1')
sessions = {}
registry_lock = Lock()
configuration = None


def configure(*, layout, sources, local_factory, cloud_factory=None):
    """Only an explicit experiment process supplies owned assets and readers."""
    global configuration
    configuration = {'layout': layout, 'sources': sources, 'local_factory': local_factory,
                     'cloud_factory': cloud_factory}


def configured():
    if configuration is None:
        raise HTTPException(503, 'Owned integration experiment is not configured in this backend.')
    return configuration


def session(identity):
    value = sessions.get(identity)
    if value is None:
        raise HTTPException(404, 'Integration source no longer exists.')
    return value


def local_write(request):
    if (request.url.hostname not in ('127.0.0.1', 'localhost') or
            request.headers.get('x-bjlab-local') != '1' or
            request.headers.get('origin') not in (None, str(request.base_url).rstrip('/'))):
        raise HTTPException(403, 'Same-origin local experiment request required.')


@router.get('/configuration')
def get_configuration():
    config = configured()
    return {'layout': config['layout'], 'sources': [{'id': name, 'title': value['title'],
             'scenario': value.get('scenario'), 'switch_to': value.get('switch_to'),
             'url': '/api/research/r1/source/'+name+'.png'} for name, value in config['sources'].items()],
            'cloud_configured': config['cloud_factory'] is not None,
            'scope': 'Owned simulator pixels; no external site or desktop capture certification.'}


@router.get('/source/{name}.png')
def source_image(name: str):
    value = configured()['sources'].get(name)
    if value is None:
        raise HTTPException(404, 'Unknown owned image.')
    return Response(Path(value['path']).read_bytes(), media_type='image/png',
                    headers={'Cache-Control': 'no-store'})


class Start(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cloud: bool = False


@router.post('/sessions')
def start(body: Start, request: Request):
    local_write(request)
    config = configured()
    if body.cloud and config['cloud_factory'] is None:
        raise HTTPException(403, 'No bounded cloud batch is configured.')
    with registry_lock:
        if sum(not s.closed for s in sessions.values()) >= 8 or len(sessions) >= 32:
            raise HTTPException(429, 'Close an existing owned source first.')
        value = IntegratedR1Session(config['local_factory'](), layout=config['layout'],
            approved_pixels=[v['pixel_sha256'] for v in config['sources'].values()],
            cloud=config['cloud_factory']() if body.cloud else None)
        sessions[value.id] = value
    return {'session_id': value.id, 'source_id': value.source, 'cloud': body.cloud}


@router.post('/sessions/{identity}/capture')
async def capture(identity: str, request: Request, sequence: int,
                  captured_epoch_ms: float):
    local_write(request)
    value = session(identity)
    content = bytearray()
    try:
        async with asyncio.timeout(3):
            async for chunk in request.stream():
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise HTTPException(413, 'Owned canvas capture exceeds its budget.')
        # Both clocks are on this local machine. Browser performance.now is used
        # separately for capture-to-DOM measurements; no server/client span sums.
        received_ns = value.clock()
        age = time.time()*1000-captured_epoch_ms
        if not 0 <= age <= 1000:
            raise ValueError('Browser acquisition age is invalid or expired.')
        ack = await run_in_threadpool(value.capture, bytes(content),
                                      sequence=sequence, capture_age_ms=age, received_ns=received_ns)
        ack['capture_ns'] = str(ack['capture_ns'])  # JS safe even after long machine uptime.
        return ack
    except (ValueError, PermissionError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/sessions/{identity}/analyze')
async def analyze(identity: str, request: Request):
    local_write(request)
    try:
        return await run_in_threadpool(session(identity).analyze)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/sessions/{identity}/state')
def state(identity: str):
    value = session(identity).snapshot()
    if value['evidence_capture_ns'] is not None:
        value['evidence_capture_ns'] = str(value['evidence_capture_ns'])
    return value


@router.get('/sessions/{identity}/receipt')
def receipt(identity: str):
    return session(identity).receipt()


class Display(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    evidence_capture_ns: str = Field(pattern=r'^\d{1,25}$')
    capture_to_dom_ms: float = Field(ge=0, le=10_000, allow_inf_nan=False)
    action: str = Field(max_length=20)
    boundary: str = Field(max_length=40)


@router.post('/sessions/{identity}/display')
def display(identity: str, body: Display, request: Request):
    local_write(request)
    try:
        value = body.model_dump()
        value['evidence_capture_ns'] = int(value['evidence_capture_ns'])
        return session(identity).display(**value)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete('/sessions/{identity}')
def stop(identity: str, request: Request):
    local_write(request)
    value = session(identity)
    value.disconnect()
    # Keep the bounded receipt for this experiment, allowing late-output audit.
    return {'stopped': True, 'session_id': identity}
