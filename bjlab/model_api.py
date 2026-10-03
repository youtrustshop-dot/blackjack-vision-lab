"""Bounded loopback bridge to the optional, separately installed Clef runtime."""
import json
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from .advisor_api import ImageRequest

router = APIRouter(prefix='/api/models/clef')
ENDPOINT = 'http://127.0.0.1:9051'


def call(path, body=None, timeout=3):
    request = Request(ENDPOINT + path, data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(1024 * 1024))


@router.get('/status')
async def status():
    try:
        return await run_in_threadpool(call, '/health')
    except (URLError, OSError, ValueError):
        return {'status': 'offline', 'model': 'Cloudflare/clef-flash',
                'message': 'The optional Clef runtime is not running. Core video advice remains available.'}


@router.post('/classify')
async def classify(body: ImageRequest):
    try:
        return await run_in_threadpool(call, '/classify', {'image_base64': body.image_base64}, 60)
    except HTTPError as error:
        raise HTTPException(502, 'Clef rejected the image. Check its local runtime log.') from error
    except (URLError, OSError, ValueError) as error:
        raise HTTPException(503, 'Clef is unavailable or timed out. Start the optional local runtime.') from error
