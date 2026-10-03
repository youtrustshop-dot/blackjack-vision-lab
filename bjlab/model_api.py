"""Bounded loopback bridge to the optional, separately installed Clef runtime."""
import json
from typing import Literal
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from pydantic import Field

from .advisor_api import ImageRequest

router = APIRouter(prefix='/api/models/clef')
ENDPOINT = 'http://127.0.0.1:9051'

class VisualVerifyRequest(ImageRequest):
    task: Literal['table','card','scene'] = 'table'
    output_height:int=Field(default=600,ge=300,le=1600)


def verification_pixels(body):
    import base64,io
    from PIL import Image
    from .calibration import normalize_table
    raw=base64.b64decode(body.image_base64,validate=True)
    if len(raw)>8*1024*1024:raise ValueError('Image exceeds 8 MiB.')
    with Image.open(io.BytesIO(raw)) as source:
        if source.width*source.height>5_000_000:raise ValueError('Image exceeds five megapixels.')
        image=source.convert('RGB')
    if body.corners:
        image=Image.fromarray(normalize_table(image,body.corners,(960,body.output_height),corners_normalized=True).image_rgb)
    image.thumbnail((1024,1024))
    output=io.BytesIO();image.save(output,format='PNG')
    return base64.b64encode(output.getvalue()).decode()


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


@router.post('/verify')
async def verify(body: VisualVerifyRequest):
    from PIL import UnidentifiedImageError, Image
    try:
        pixels=await run_in_threadpool(verification_pixels,body)
    except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError) as error:
        raise HTTPException(422,'Provide a valid image below 8 MiB and five megapixels with valid table corners.') from error
    try:
        return await run_in_threadpool(call, '/verify', {'image_base64':pixels,'task':body.task},60)
    except HTTPError as error:
        raise HTTPException(502,'Clef visual verification failed. Update the optional runtime and inspect its log.') from error
    except ValueError as error:
        raise HTTPException(422,str(error)) from error
    except (URLError,OSError) as error:
        raise HTTPException(503,'Clef visual verification is unavailable or timed out. Card recognition remains separate.') from error
