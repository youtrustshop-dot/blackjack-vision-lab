"""Local-only video stream API; pixels and explicit user configuration only."""
import io
import asyncio
import math
import secrets
import threading
import time

from fastapi import APIRouter, Body, HTTPException, Query, Request
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from .engine import Rules
from .live import LiveObserver
from .live_work import LiveAnalysisPool, LiveFramePool

router = APIRouter(prefix="/api/live")
observers: dict[str, LiveObserver] = {}
registry_lock = threading.Lock()
analysis_pool = LiveAnalysisPool()
frame_pool = LiveFramePool()


class LiveConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: dict = Field(default_factory=dict)
    samples: int = Field(default=1500, ge=100, le=8000)
    corners: list[list[float]] | None = None
    zones: dict[str, tuple[int, int, int, int]] | None = None
    fresh_shoe: bool = False
    manual_turn: bool = False
    output_height: int = Field(default=600, ge=300, le=1600)


@router.post("")
def create_observer(body: LiveConfig):
    try:
        rules = Rules(**body.rules)
        if body.corners is not None:
            from .calibration import validate_corners
            validate_corners(body.corners, 960, 600, normalized=True)
        if body.zones:
            for name, (x, y, width, height) in body.zones.items():
                if not (name == "dealer" or name.startswith("player")) or min(x, y) < 0 or min(width, height) < 1:
                    raise ValueError("Invalid card zone.")
                if x + width > 960 or y + height > body.output_height:
                    raise ValueError("Card zone is outside the normalized table.")
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    with registry_lock:
        now = time.monotonic()
        for key, observer in list(observers.items()):
            if now - observer.last_access > 180:
                observers.pop(key, None)
                observer.stop()
        if len(observers) >= 8:
            raise HTTPException(429, "Eight live streams are already active. Stop an existing stream first.")
        identity = secrets.token_urlsafe(18)
        observers[identity] = LiveObserver(rules, samples=body.samples, corners=body.corners,
                                          zones=body.zones, fresh_shoe=body.fresh_shoe,
                                          manual_turn=body.manual_turn, output_height=body.output_height)
    return {"stream_id": identity, "source": "live-video-pixels", "stable_frames": 3}


@router.delete("/{stream_id}")
def stop_observer(stream_id: str):
    with registry_lock:
        observer = observers.pop(stream_id, None)
        if observer:
            observer.stop()
    return {"stopped": True}


@router.post("/browser")
def open_browser(request: Request, body: dict = Body(...)):
    """User-triggered browser handoff for desktop WebViews without capture."""
    import webbrowser
    if request.url.hostname not in ("127.0.0.1", "localhost"):
        raise HTTPException(403, "Browser handoff is only available on localhost.")
    if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
        raise HTTPException(403, "Browser handoff requires a same-origin request.")
    port = request.url.port or 80
    address = f"http://127.0.0.1:{port}/"
    if not webbrowser.open(address):
        raise HTTPException(503, f"Open {address} in Chrome or Edge manually.")
    return {"opened": True, "url": address}


@router.get("/{stream_id}/events")
def live_events(stream_id: str):
    observer = observers.get(stream_id)
    if observer is None:
        raise HTTPException(404, "Live stream no longer exists. Restart observation.")
    with observer.lock:
        return observer.tracker.log.to_dict()


@router.post("/{stream_id}/frame")
async def video_frame(stream_id: str, request: Request, sequence: int = Query(ge=0),
                      timestamp: float = Query(gt=0)):
    observer = observers.get(stream_id)
    if observer is None:
        raise HTTPException(404, "Live stream no longer exists. Restart observation.")
    if not math.isfinite(timestamp):
        raise HTTPException(422, "Video timestamp must be finite.")
    if not frame_pool.reserve(observer):
        raise HTTPException(429, 'Live frame workers are busy. Retry with the next video observation.')
    submitted = False
    try:
        content = bytearray()
        async with asyncio.timeout(5):
            async for chunk in request.stream():
                content.extend(chunk)
                if len(content) > 8 * 1024 * 1024:
                    raise HTTPException(413, "Video image exceeds 8 MiB.")
        def work():
            with Image.open(io.BytesIO(content)) as source:
                if source.width * source.height > 5_000_000:
                    raise ValueError("Video image exceeds five megapixels.")
                image = source.convert("RGB")
            result = observer.process(image, sequence, timestamp)
            scheduled = analysis_pool.submit(observer)
            # The basic response remains the captured immutable result even
            # if the worker finishes before HTTP serialization.
            with observer.lock:
                if result['state_id'] == observer.state_id:
                    result['analysis'] = (dict(status='pending', state_id=observer.state_id,
                                               budget_ms=analysis_pool.timeout_ms)
                                          if scheduled or (result['decision'] is None and observer.last_report['decision'] is not None)
                                          else dict(observer.last_report['analysis']))
            return result
        future = frame_pool.submit_reserved(observer, work)
        submitted = True
        return await asyncio.shield(asyncio.wrap_future(future))
    except TimeoutError as exc:
        raise HTTPException(408, 'Video upload timed out.') from exc
    except (ValueError, UnidentifiedImageError) as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        if not submitted:
            frame_pool.release(observer)


@router.get('/{stream_id}/analysis')
def live_analysis(stream_id: str, state_id: str):
    observer = observers.get(stream_id)
    if observer is None:
        raise HTTPException(404, 'Live stream no longer exists. Restart observation.')
    try:
        return observer.analysis_result(state_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
