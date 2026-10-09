"""Local REST service. Public game state, pixel perception and debug truth are separate."""
from __future__ import annotations

import asyncio
import base64
from dataclasses import asdict
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import threading
import time
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .engine import Rules
from . import __version__
from itertools import count
from .advice import session_advice
from .monte_carlo import basic_action, hilo_action, run_experiment
from .simulator import BlackjackSession

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Blackjack Vision Lab", version=__version__)
sessions: dict[str, BlackjackSession] = {}
visual_sessions: dict[str, int] = {}
visual_session_numbers = count(1)
session_locks: dict[str, threading.RLock] = {}
perception_trackers: dict[str, Any] = {}
analysis_cache: dict[str, dict] = {}
analysis_lock = threading.Lock()
analysis_slots = threading.BoundedSemaphore(2)


class NewSession(BaseModel):
    rules: dict = Field(default_factory=dict)
    seed: int = 42
    bankroll: float = Field(default=1000, gt=0, allow_inf_nan=False)


class DealRequest(BaseModel):
    bet: float = Field(default=1, gt=0, allow_inf_nan=False)


class ActionRequest(BaseModel):
    action: str
    amount: float | None = Field(default=None, allow_inf_nan=False)


class AnalyzeRequest(BaseModel):
    timeout_ms: int = Field(default=1500, ge=50, le=15000)
    max_nodes: int = Field(default=60000, ge=100, le=150000)
    unknown_removed: int = Field(default=0, ge=0, le=208)


class ReplayRequest(BaseModel):
    events: list[dict]
    to_index: int | None = Field(default=None, ge=0)


class ExperimentRequest(BaseModel):
    rounds: int = Field(default=200, ge=1, le=100000)
    seed: int = 42
    rules: dict = Field(default_factory=dict)
    policies: list[str] = Field(default_factory=lambda: ["basic", "hilo"])
    max_seconds: float = Field(default=30, ge=.1, le=120)
    solver_seconds: float = Field(default=.05, ge=.001, le=.5)
    regret_samples: int = Field(default=12, ge=0, le=100)


class PerceptionRequest(BaseModel):
    frames: int = Field(default=3, ge=1, le=12)
    theme: str = "green"
    blur: float = Field(default=0, ge=0, le=10)
    overlap: float = Field(default=0, ge=0, le=.9)
    scale: float = Field(default=1, ge=.4, le=2)
    card_design: Literal["classic", "minimal"] = "classic"


class UploadRequest(BaseModel):
    image_base64: str
    session_id: str | None = None
    decks: int | None = Field(default=None, ge=1, le=8)
    frames: int = Field(default=3, ge=1, le=12)
    corners: list[list[float]] | None = None
    corners_normalized: bool = False
    output_width: int = Field(default=960, ge=160, le=4096)
    output_height: int = Field(default=600, ge=160, le=2160)
    zones: dict[str, tuple[int, int, int, int]] = Field(default_factory=dict)


class CorrectionRequest(BaseModel):
    card_id: str
    rank: str | None = None
    suit: str | None = None
    reason: str = Field(min_length=3)


class CountingRequest(BaseModel):
    cards: list[str] = Field(default_factory=list)
    decks: int = 6
    rounding: str = "truncate"
    cards_remaining: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class CustomCountingRequest(CountingRequest):
    name: str = Field(default="Custom", min_length=1, max_length=80)
    tags: list[float] = Field(min_length=10, max_length=10)
    balanced: bool = True


def _rules(data: dict) -> Rules:
    try:
        return Rules(**data)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


def _session(session_id: str) -> BlackjackSession:
    try:
        return sessions[session_id]
    except KeyError as exc:
        raise HTTPException(404, "Unknown session") from exc


def _guard_action(function, *args) -> Any:
    try:
        return function(*args)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "service": "Blackjack Vision Lab",
            "local_only": True, "truth_boundary": "debug endpoint excluded from solver inputs"}


@app.get('/api/vision/experiments')
def vision_experiments():
    from .vision_diagnostics import source_revision,candidate_revision
    from .corner_vision import VERSION
    data=json.loads((ROOT/'docs/VISION_EXPERIMENTS.json').read_text(encoding='utf-8'))
    data['runtime']={'package_version':__version__,'detector_version':VERSION,
        'source_fingerprint':source_revision(ROOT),'frozen':bool(getattr(__import__('sys'),'frozen',False)),
        'publication':'research candidate; no installed desktop replacement',**candidate_revision(ROOT)}
    return data


@app.get("/api/rules")
def default_rules() -> dict:
    return {"defaults": asdict(Rules()), "choices": {"decks": [1, 2, 4, 6, 8],
            "double_rule": ["any", "9-11", "10-11", "none"],
            "surrender": ["none", "early", "late"], "enhc_loss": ["all", "original"]}}


@app.get("/api/counting/systems")
def counting_systems() -> dict:
    from .counting import available_systems
    return {"systems": available_systems()}


@app.post("/api/counting/compare")
def counting_compare(body: CountingRequest) -> dict:
    from .counting import available_systems, CountingEngine
    results = {}
    try:
        for system in available_systems():
            engine = CountingEngine(body.decks, system["name"], body.rounding)
            for index, card in enumerate(body.cards):
                engine.observe(card, index)
            results[system["name"]] = engine.snapshot(body.cards_remaining)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"systems": results, "cards_observed": len(body.cards)}


@app.post("/api/counting/custom")
def counting_custom(body: CustomCountingRequest) -> dict:
    from .counting import custom_system, CountingEngine
    try:
        system = custom_system(body.name, body.tags, balanced=body.balanced)
        engine = CountingEngine(body.decks, system, body.rounding)
        for index, card in enumerate(body.cards):
            engine.observe(card, index)
        return {"definition": {"name": system.name, "tags": list(system.tags), "balanced": system.balanced},
                "counter": engine.snapshot(body.cards_remaining)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/roadmap")
def roadmap() -> dict:
    source = ROOT / "docs" / "REQUIREMENTS.json"
    if not source.exists():
        return {"status": "being_written", "requirements": []}
    return json.loads(source.read_text(encoding="utf-8"))


@app.post("/api/sessions")
def create_session(body: NewSession) -> dict:
    session = BlackjackSession(_rules(body.rules), body.seed, bankroll=body.bankroll)
    sessions[session.id] = session
    session_locks[session.id] = threading.RLock()
    return session_advice(session)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    session = _session(session_id)
    with session_locks[session_id]:
        return session_advice(session)


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    _session(session_id)
    with session_locks[session_id]:
        sessions.pop(session_id, None)
        perception_trackers.pop(session_id, None)
        visual_sessions.pop(session_id, None)
    return {"deleted": session_id}


@app.post("/api/sessions/{session_id}/deal")
def deal(session_id: str, body: DealRequest) -> dict:
    session = _session(session_id)
    with session_locks[session_id]:
        _guard_action(session.deal, body.bet)
        return session_advice(session)


@app.post("/api/sessions/{session_id}/action")
def action(session_id: str, body: ActionRequest) -> dict:
    session = _session(session_id)
    with session_locks[session_id]:
        result = _guard_action(session.action, body.action, body.amount)
        if body.action == "shuffle":
            perception_trackers.pop(session_id, None)
        return session_advice(session)


@app.post("/api/sessions/{session_id}/bot-step")
def simulator_bot_step(session_id: str) -> dict:
    """Drive the visible source; the independent video observer never calls this."""
    session = _session(session_id)
    with session_locks[session_id]:
        if session.phase in ("ready", "settled"):
            _guard_action(session.deal, 1.)
        else:
            _guard_action(session.action, basic_action(session))
        return session_advice(session)


def _solver_child(connection, rules: dict, state: dict, timeout_ms: int, max_nodes: int) -> None:
    try:
        from .solver import Solver
        arguments = {key: state[key] for key in ("can_double", "can_split", "can_surrender", "peeked",
                                                 "from_split", "split_aces", "split_hands", "completed_hands", "pending_hands")}
        arguments["unknown_removed"] = state.get("unknown_removed", 0)
        result = Solver(Rules(**rules)).analyze(state["player"], state["dealer"], tuple(state["counts"]),
                                              timeout_ms=timeout_ms, max_nodes=max_nodes, **arguments)
        connection.send({"status": "ok", "result": result})
    except Exception as exc:
        connection.send({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        connection.close()


def _analyze_process(rules: dict, state: dict, timeout_ms: int, max_nodes: int) -> dict:
    cache_key = hashlib.sha256(json.dumps([rules, state, timeout_ms, max_nodes], sort_keys=True).encode()).hexdigest()
    with analysis_lock:
        cached = analysis_cache.get(cache_key)
    if cached is not None:
        return dict(cached, cached=True)
    if not analysis_slots.acquire(blocking=False):
        return {"status": "busy", "result": None, "error": "Two solver jobs are already active; retry shortly."}
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_solver_child, args=(sender, rules, state, timeout_ms, max_nodes), daemon=True)
    start = time.perf_counter()
    try:
        process.start()
        sender.close()
        # Startup allowance is separate from the algorithm's budget. Terminate
        # the isolated worker if it overruns; it cannot occupy the web service.
        if receiver.poll(timeout_ms / 1000 + 5):
            try:
                result = receiver.recv()
            except EOFError:
                result = {"status": "error", "result": None, "error": "Solver worker exited without a result."}
        else:
            result = {"status": "timeout", "result": None, "error": "Solver exceeded its isolated worker deadline."}
        result["service_latency_ms"] = (time.perf_counter() - start) * 1000
        result["cached"] = False
        if result["status"] == "ok":
            with analysis_lock:
                if len(analysis_cache) >= 512:
                    analysis_cache.pop(next(iter(analysis_cache)))
                analysis_cache[cache_key] = result
        return result
    finally:
        if process.is_alive():
            process.terminate()
        if process.pid is not None:
            process.join(timeout=1)
        receiver.close()
        sender.close()
        analysis_slots.release()


@app.post("/api/sessions/{session_id}/outcomes")
async def session_outcomes(session_id: str):
    """Sample the public informational pool, never the hidden future shoe order."""
    from .live import estimate_actions
    session = _session(session_id)
    with session_locks[session_id]:
        if session.phase != 'player':
            raise HTTPException(409, 'Outcome estimates need an active player decision.')
        state = session.decision_state()
        rules = session.rules
        available = list(session.available_actions())
        revision = session.snapshot()['events_count']
    try:
        result = await run_in_threadpool(estimate_actions, state['player'], state['dealer'],
            list(state['counts']), rules, available, samples=1500, peeked=state['peeked'],
            from_split=state['from_split'], split_hands=state['split_hands'])
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {'decision': result, 'events_count': revision,
            'precision': 'Finite-pool Monte Carlo with generated continuation; separate from the finite exact solver.'}


@app.post("/api/sessions/{session_id}/analyze")
async def analyze(session_id: str, body: AnalyzeRequest = AnalyzeRequest()) -> dict:
    start = time.perf_counter()
    session = _session(session_id)
    with session_locks[session_id]:
        if session.phase == "insurance":
            pool = session.counts()
            probability = pool[9] / sum(pool) if sum(pool) else 0
            ev = 3 * probability - 1
            return {"status": "ok", "result": {"actions": {"insurance": ev * .5, "decline_insurance": 0},
                    "best_action": "insurance" if ev > 0 else "decline_insurance", "method": "finite_pool",
                    "exact": True, "latency_ms": (time.perf_counter() - start) * 1000, "warnings": []},
                    "state": {"counts": list(pool)}, "comparison": {"basic": "decline_insurance",
                    "hilo": hilo_action(session)}, "precision": "Exact conditional insurance EV per initial wager"}
        state = _guard_action(session.decision_state)
        state["unknown_removed"] = body.unknown_removed
        rules = asdict(session.rules)
        comparison = {"basic": basic_action(session), "hilo": hilo_action(session)}
        from .strategy import get_generated_strategy
        generated = get_generated_strategy(session.rules).analyze(state["player"], state["dealer"],
                    from_split=state["from_split"], split_hands=state["split_hands"],
                    split_aces=state["split_aces"], pending_count=len(state["pending_hands"]),
                    peek_resolved=state["peeked"], allowed_actions=session.available_actions())
        round_id = session.round_id
        early_surrender = session.phase == "early_surrender"
    response = await run_in_threadpool(_analyze_process, rules, state, body.timeout_ms, body.max_nodes)
    if early_surrender and response.get("result"):
        result = dict(response["result"])
        actions = result.get("actions", {})
        future = {action: ev for action, ev in actions.items() if action != "surrender"}
        continuation = [ev for ev in future.values() if isinstance(ev, (float, int))]
        complete = bool(future) and len(continuation) == len(future)
        result["continuation_actions"] = actions
        result["actions"] = {"surrender": actions.get("surrender"),
                             "continue": max(continuation) if complete else None}
        original_best = result.get("best_action")
        result["best_action"] = None if original_best is None else "surrender" if original_best == "surrender" else "continue"
        result["action_details"] = {"surrender": result.get("action_details", {}).get("surrender", {}),
                                    "continue": {"exact": complete and bool(result.get("exact")),
                                                 "method": result.get("method"), "evaluated_future_actions": len(continuation),
                                                 "required_future_actions": len(future)}}
        response = response | {"result": result}
    return response | {"state": state, "comparison": comparison, "round_id": round_id,
                       "generated_basic": generated,
                       "precision": "Read result.method, result.exact and result.warnings for the scope of each estimate."}


@app.get("/api/sessions/{session_id}/events")
def events(session_id: str) -> dict:
    session = _session(session_id)
    with session_locks[session_id]:
        return {"schema": "bjlab.events.v1", "events": list(session.events)}


@app.get("/api/sessions/{session_id}/export")
def export(session_id: str, format: str = Query(default="json", pattern="^(json|csv)$")) -> Response:
    session = _session(session_id)
    with session_locks[session_id]:
        content = session.export(format)
    media = "application/json" if format == "json" else "text/csv"
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{session_id}.{format}"'})


@app.get("/api/sessions/{session_id}/truth")
def truth(session_id: str, debug: bool = False) -> dict:
    if not debug:
        raise HTTPException(403, "Ground truth requires the explicit debug=true flag.")
    session = _session(session_id)
    with session_locks[session_id]:
        return session.ground_truth()


@app.post("/api/replay")
def replay(body: ReplayRequest) -> dict:
    try:
        session = BlackjackSession.replay(body.events, body.to_index)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    source = body.events if body.to_index is None else body.events[:body.to_index + 1]
    matches = session.events[:len(source)] == source
    if not matches:
        raise HTTPException(422, "Replay audit failed: supplied events differ from deterministic reconstruction.")
    return {"snapshot": session.snapshot(), "verified": True, "events_count": len(session.events),
            "granularity": "exact event prefix; future exposures excluded"}


@app.post("/api/experiments")
async def experiments(body: ExperimentRequest) -> dict:
    rules = _rules(body.rules)
    try:
        return await run_in_threadpool(run_experiment, body.rounds, body.seed, rules,
                                      body.policies, body.max_seconds, body.solver_seconds, body.regret_samples)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _render_session(session: BlackjackSession, *, theme: str = "green", blur: float = 0,
                    scale: float = 1, overlap: float = 0, card_design: str = "classic"):
    from PIL import ImageFilter
    from .datasets import render_table
    snapshot = session.snapshot()
    cards = []
    for index, card in enumerate(snapshot["dealer"]["cards"]):
        cards.append(card | {"x": 60 + index * 88 * (1 - overlap), "y": 60,
                             "card_id": card["id"], "zone": "dealer"})
    for hand_index, hand in enumerate(snapshot["hands"]):
        gap = min(88, 340 / max(1, len(hand["cards"]) - 1)) * (1 - overlap)
        for card_index, card in enumerate(hand["cards"]):
            cards.append(card | {"x": 60 + (hand_index % 2) * 440 + card_index * gap,
                                 "y": 310 + (hand_index // 2) * 190,
                                 "card_id": card["id"], "zone": f"player:{hand_index}"})
    height = max(600, 500 + (len(snapshot["hands"]) - 1) // 2 * 190)
    rules = session.rules
    rule_labels = ["H17" if rules.hit_soft17 else "S17", "ENHC" if rules.enhc else "AHC",
                   "DAS" if rules.double_after_split else "NDAS", "RSA" if rules.resplit_aces else "NRSA",
                   {"early": "ES", "late": "LS", "none": "NS"}[rules.surrender], f"D{rules.decks}"]
    if not rules.enhc:
        rule_labels.append("PEEK" if rules.dealer_peek else "NPEEK")
    if rules.blackjack_payout in (1.5, 1.2):
        rule_labels.append("BJ3:2" if rules.blackjack_payout == 1.5 else "BJ6:5")
    buttons = [{"shuffle": "NEW SHOE", "decline_insurance": "DECLINE INSURANCE"}.get(action, action.upper())
               for action in snapshot["available_actions"]]
    image = render_table(cards, width=960, height=height, theme=theme, scale=scale, card_design=card_design,
                         rule_labels=rule_labels, button_labels=buttons)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    return image


@app.get("/api/sessions/{session_id}/frame")
def frame(session_id: str, theme: str = "green", blur: float = Query(default=0, ge=0, le=10),
          scale: float = Query(default=1, ge=.4, le=2), overlap: float = Query(default=0, ge=0, le=.9),
          card_design: Literal["classic", "minimal"] = "classic", live_context: bool = False) -> Response:
    session = _session(session_id)
    try:
        with session_locks[session_id]:
            image = _render_session(session, theme=theme, blur=blur, scale=scale, overlap=overlap, card_design=card_design)
            if live_context:
                # Visible context, read from pixels by the independent observer.
                # These labels contain no hidden card or future deck information.
                from PIL import ImageDraw
                from .datasets import card_font
                draw = ImageDraw.Draw(image)
                font = card_font(16)
                color = (212, 220, 213)
                if session_id not in visual_sessions:
                    visual_sessions[session_id] = next(visual_session_numbers)
                context = [(60, "SHOE"), (120, str(session.shoe.generation)),
                           (225, "ROUND"), (305, str(session.round_id)),
                           (405, "HAND"), (470, str((session.active_hand or 0) + 1)),
                           (590, "EARLY" if session.phase == "early_surrender" else session.phase.upper()),
                           (760, "SESSION"), (860, str(visual_sessions[session_id]))]
                for x, text in context:
                    draw.text((x, 260), text, font=font, fill=color, anchor="lt")
        output = io.BytesIO()
        image.save(output, format="PNG")
        return Response(output.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


def _perception_summary(tracker) -> dict:
    summary = tracker.state_summary()
    if summary.get("decks") is None:
        gate = dict(summary["gate"])
        gate.update(status="manual_review", solver_allowed=False,
                    reasons=list(gate["reasons"]) + ["Deck inventory is unknown; declare decks or use a configured session."])
        summary["gate"] = gate
    return summary


def _deck_estimation(state: dict, source: str = "configured-session") -> dict:
    from .vision import DeckCountEstimator
    estimator = DeckCountEstimator()
    for card_id, card in state["cards"].items():
        if card.get("rank") is not None:
            estimator.observe(card_id, card["rank"], card.get("suit"))
    result = estimator.estimate()
    known = state.get("decks")
    return {"mode": "KNOWN" if known is not None else "INFERRED",
            "source": source if known is not None else "inferred-confirmed-cards",
            "decks": known, "posterior": result["probabilities"], "certain": known is not None,
            "observations": result["observations"], "most_likely": result.get("most_likely"),
            "posterior_max": result.get("posterior_max"), "entropy_bits": result.get("entropy_bits"),
            "status": result["status"], "assumptions": result.get("assumptions", result.get("reason", "")),
            "certainty_semantics": "Declared configuration, not pixel certification" if known is not None else
                "Finite candidate posterior under shuffled-shoe assumptions; inferred deck count is not certain"}


def _detect_and_track(image, tracker, frames: int, round_id: str | None = None, zones: dict | None = None) -> dict:
    start = time.perf_counter()
    import cv2
    cv2.setNumThreads(1)
    from .vision import TemplateCardDetector
    detector = TemplateCardDetector(zones=zones)
    detections = detector.detect(image)
    detection_ms = (time.perf_counter() - start) * 1000
    emitted = []
    timestamp = max(time.time(), tracker.last_timestamp + .001)
    for index in range(frames):
        batch = tracker.update(detections, timestamp=timestamp + index / 30, round_id=round_id)
        emitted.extend(item.to_dict() if hasattr(item, "to_dict") else item for item in batch)
    elapsed_ms = (time.perf_counter() - start) * 1000
    from .calibration import extract_controlled_metadata
    metadata_start = time.perf_counter()
    metadata = extract_controlled_metadata(image)
    metadata_ms = (time.perf_counter() - metadata_start) * 1000
    state = tracker.log.replay().to_dict()
    return {"detections": [item.to_dict() for item in detections], "events": emitted,
            "state": state, "summary": _perception_summary(tracker), "deck_estimation": _deck_estimation(state),
            "latency_ms": elapsed_ms, "detection_ms": detection_ms,
            "tracking_ms": elapsed_ms - detection_ms, "processed_frames": 1, "tracker_updates": frames,
            "frame_source": "still-repeat", "pipeline_fps": 1000 / elapsed_ms if elapsed_ms else None,
            "controlled_metadata": metadata, "metadata_ms": metadata_ms,
            "full_pixel_latency_ms": elapsed_ms + metadata_ms,
            "full_pixel_fps": 1000 / (elapsed_ms + metadata_ms) if elapsed_ms + metadata_ms else None,
            "throughput_semantics": "one independent still input per detection-and-stabilization wall time; excludes upload/calibration/control-label recognition",
            "stream_fps": None, "drop_count": None,
            "input": "rendered image pixels only", "temporal_note": "Repeated still frames stabilize recognition; this is not a video accuracy benchmark."}


def _tracker(session: BlackjackSession):
    from .vision import TemporalTracker
    tracker = perception_trackers.get(session.id)
    if tracker is None:
        tracker = TemporalTracker(stable_frames=3)
        tracker.new_shoe(session.rules.decks, shoe_id=session.shoe.id)
        tracker.simulator_shoe_id = session.shoe.id
        perception_trackers[session.id] = tracker
    elif tracker.simulator_shoe_id != session.shoe.id:
        tracker.new_shoe(session.rules.decks, shoe_id=session.shoe.id,
                         timestamp=max(time.time(), tracker.last_timestamp + .001))
        tracker.simulator_shoe_id = session.shoe.id
    return tracker


@app.post("/api/sessions/{session_id}/perception")
def perception(session_id: str, body: PerceptionRequest = PerceptionRequest()) -> dict:
    session = _session(session_id)
    try:
        with session_locks[session_id]:
            image = _render_session(session, theme=body.theme, blur=body.blur,
                                    scale=body.scale, overlap=body.overlap, card_design=body.card_design)
            zones = {"dealer": (0, 0, 960, 250)} | {
                f"player:{i}": (30 + i % 2 * 440, 290 + i // 2 * 190, 440, 190)
                for i in range(len(session.hands))}
            response = _detect_and_track(image, _tracker(session), body.frames, str(session.round_id), zones)
        return response | {"frame_url": f"/api/sessions/{session_id}/frame", "session_id": session_id}
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/sessions/{session_id}/perception/events")
def perception_events(session_id: str) -> dict:
    session = _session(session_id)
    with session_locks[session_id]:
        return _tracker(session).log.to_dict()


@app.post("/api/sessions/{session_id}/perception/correct")
def correct_perception(session_id: str, body: CorrectionRequest) -> dict:
    session = _session(session_id)
    with session_locks[session_id]:
        tracker = _tracker(session)
        try:
            event = tracker.correct(body.card_id, rank=body.rank, suit=body.suit, reason=body.reason,
                                    timestamp=max(time.time(), tracker.last_timestamp + .001))
            state = _perception_summary(tracker)
            return {"event": event.to_dict(), "state": state, "deck_estimation": _deck_estimation(state)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


@app.post("/api/sessions/{session_id}/perception/analyze")
async def analyze_perception(session_id: str, body: AnalyzeRequest = AnalyzeRequest()) -> dict:
    from .engine import legal_actions
    from .counting import hilo_strategy
    from .strategy import generated_basic_strategy, get_generated_strategy
    session = _session(session_id)
    with session_locks[session_id]:
        if session.phase != "player" or session.active_hand is None:
            raise HTTPException(409, "A normal player decision must be active.")
        tracker = _tracker(session)
        summary = tracker.state_summary()
        if not summary["gate"]["solver_allowed"]:
            return {"status": "gated", "result": None, "gate": summary["gate"], "source": "perception"}
        observed = summary["cards"].values()
        on_table = [card for card in observed if card.get("on_table") and card.get("rank")]
        def zone_cards(zone: str) -> list[str]:
            cards = [card for card in on_table if card.get("zone") == zone]
            cards.sort(key=lambda card: (card.get("bbox", [0])[0], card.get("first_event", 0)))
            return [card["rank"] for card in cards]
        dealer = zone_cards("dealer")
        player = zone_cards(f"player:{session.active_hand}")
        if not player and len(session.hands) == 1:
            player = zone_cards("player")
        if len(dealer) != 1 or len(player) < 2:
            return {"status": "gated", "result": None, "gate": {"status": "manual_review",
                    "reasons": ["Need exactly one visible dealer upcard and at least two player cards."],
                    "solver_allowed": False}, "source": "perception"}
        hand = session.hands[session.active_hand]
        actions = legal_actions(player, session.rules, from_split=hand.from_split, split_hands=len(session.hands),
                                split_aces=hand.split_aces, peek_resolved=session.peek_resolved,
                                can_surrender=session.rules.surrender == "late")
        base_wager = sum(item.original_wager for item in session.hands)
        completed, pending = [], []
        for index, item in enumerate(session.hands):
            if index == session.active_hand:
                continue
            cards = zone_cards(f"player:{index}")
            if not cards:
                return {"status": "gated", "result": None, "gate": {"status": "manual_review",
                        "reasons": ["Other split-hand cards are missing from perception."], "solver_allowed": False}}
            if item.status == "waiting":
                pending.append(cards)
            else:
                completed.append({"cards": cards, "wager": item.bet / base_wager,
                                  "original_wager": item.original_wager / base_wager,
                                  "from_split": item.from_split, "surrendered": item.status == "surrendered"})
        state = {"player": player, "dealer": dealer[0], "counts": summary["composition_remaining"],
                 "can_double": "double" in actions and session._committed() + hand.bet <= session.bankroll,
                 "can_split": "split" in actions and session._committed() + hand.bet <= session.bankroll,
                 "can_surrender": "surrender" in actions, "peeked": session.peek_resolved,
                 "from_split": hand.from_split, "split_aces": hand.split_aces, "split_hands": len(session.hands),
                 "completed_hands": completed, "pending_hands": pending,
                 "unknown_removed": body.unknown_removed,
                 "information": "rank and count inputs exclusively from replay of pixel perception"}
        rules = asdict(session.rules)
        running = sum(sum(1 if 2 <= int(rank) <= 6 else 0 for _ in range(count)) if rank.isdigit() and int(rank) < 10
                      else -count if rank in ("A", "10", "J", "Q", "K") else 0
                      for rank, count in summary["known_rank_counts"].items())
        physical_remaining = summary["physical_remaining"]
        count = running / (physical_remaining / 52) if physical_remaining else 0
        state["true_count_denominator"] = "perception_estimated_physical_remaining_cards"
        state["true_count_denominator_cards"] = physical_remaining
        policy_legal = [action for action in actions if (action != "double" or state["can_double"])
                        and (action != "split" or state["can_split"])]
        generated = get_generated_strategy(session.rules).analyze(player, dealer[0],
                    from_split=hand.from_split, split_hands=len(session.hands), split_aces=hand.split_aces,
                    pending_count=len(pending), peek_resolved=session.peek_resolved, allowed_actions=policy_legal)
        comparison = {"basic": generated["best_action"],
                      "hilo": hilo_strategy(player, dealer[0], session.rules, count, policy_legal,
                                             from_split=hand.from_split, split_hands=len(session.hands),
                                             split_aces=hand.split_aces)}
    response = await run_in_threadpool(_analyze_process, rules, state, body.timeout_ms, body.max_nodes)
    return response | {"state": state, "comparison": comparison, "gate": summary["gate"], "source": "perception",
                       "deck_estimation": _deck_estimation(summary),
                       "generated_basic": generated,
                       "precision": "Conditional on reconstructed state. Integrity gate cannot certify cards that were never detected."}


@app.post("/api/vision/upload")
def upload(body: UploadRequest) -> dict:
    from PIL import Image, UnidentifiedImageError
    from .vision import TemporalTracker
    encoded = body.image_base64.split(",", 1)[-1]
    if len(encoded) > 16 * 1024 * 1024:
        raise HTTPException(413, "Image payload exceeds the 12 MiB decoded limit.")
    try:
        content = base64.b64decode(encoded, validate=True)
        image = Image.open(io.BytesIO(content)).convert("RGB")
        if image.width * image.height > 20_000_000:
            raise ValueError("Image exceeds 20 megapixels.")
    except (ValueError, UnidentifiedImageError) as exc:
        raise HTTPException(422, f"Invalid image: {exc}") from exc
    calibration = None
    if body.corners is not None:
        from .calibration import normalize_table
        try:
            calibration = normalize_table(image, body.corners,
                          outputsize=(body.output_width, body.output_height),
                          corners_normalized=body.corners_normalized)
            image = Image.fromarray(calibration.image_rgb)
        except ValueError as exc:
            raise HTTPException(422, f"Invalid table calibration: {exc}") from exc
    from .vision import CardDetection
    if body.session_id:
        session = _session(body.session_id)
        with session_locks[session.id]:
            response = _detect_and_track(image, _tracker(session), body.frames, str(session.round_id), body.zones)
    else:
        tracker = TemporalTracker(stable_frames=3)
        tracker.new_shoe(body.decks, shoe_id="uploaded-image")
        response = _detect_and_track(image, tracker, body.frames, zones=body.zones)
    response["input"] = "uploaded image pixels only"
    response["frame_source"] = "uploaded-image"
    response["deck_provenance"] = "configured-session" if body.session_id else (
        "explicit-upload-parameter" if body.decks is not None else "unknown")
    if response["deck_estimation"]["mode"] == "KNOWN":
        response["deck_estimation"]["source"] = response["deck_provenance"]
    if calibration is not None:
        response["calibration"] = calibration.to_dict()
        response["source_detections"] = [calibration.map_detection_to_source(CardDetection(**detection)).to_dict()
                                         for detection in response["detections"]]
    return response


@app.post("/api/vision/upload-video")
async def upload_video(request: Request, stride: int = Query(default=10, ge=1, le=120),
                       max_frames: int = Query(default=120, ge=1, le=600),
                       decks: int | None = Query(default=None, ge=1, le=8),
                       thumbnails: bool = True, thumbnail_width: int = Query(default=480, ge=160, le=960)) -> dict:
    """Decode a raw video locally, never reading simulated ground truth."""
    content = await request.body()
    if len(content) > 64 * 1024 * 1024:
        raise HTTPException(413, "Video exceeds 64 MiB.")
    return await run_in_threadpool(_process_video, content, stride, max_frames, decks, thumbnails, thumbnail_width)


def _process_video(content: bytes, stride: int, max_frames: int, decks: int | None = None,
                   thumbnails: bool = True, thumbnail_width: int = 480) -> dict:
    started = time.perf_counter()
    import tempfile
    import math
    import cv2
    cv2.setNumThreads(1)
    from .vision import TemporalTracker, TemplateCardDetector
    tracker = TemporalTracker(stable_frames=3)
    tracker.new_shoe(decks, shoe_id="uploaded-video")
    detector = TemplateCardDetector()
    detections_per_frame = []
    timings = []
    with tempfile.TemporaryDirectory(prefix="bjlab-video-") as temporary:
        path = Path(temporary) / "clip.mp4"
        path.write_bytes(content)
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            raise HTTPException(422, "Video cannot be decoded by the local OpenCV backend.")
        reported_fps = capture.get(cv2.CAP_PROP_FPS)
        fps = reported_fps if math.isfinite(reported_fps) and reported_fps > 0 else 30
        index = 0
        try:
            while len(detections_per_frame) < max_frames:
                success, pixels = capture.read()
                if not success:
                    break
                if index % stride == 0:
                    frame_start = time.perf_counter()
                    detections = detector.detect(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
                    emitted = tracker.update(detections, timestamp=index / fps, round_id="video")
                    event_end = tracker.log.events[-1].index
                    height, width = pixels.shape[:2]
                    preview_width = min(width, thumbnail_width) if thumbnails else None
                    preview_height = max(1, round(height * preview_width / width)) if thumbnails else None
                    encoded_image = None
                    if thumbnails:
                        preview = cv2.resize(pixels, (preview_width, preview_height), interpolation=cv2.INTER_AREA)
                        success, encoded = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        if not success:
                            raise HTTPException(500, "The local JPEG encoder failed.")
                        encoded_image = base64.b64encode(encoded.tobytes()).decode("ascii")
                    replay = tracker.log.replay(to_index=event_end).to_dict()
                    detections_per_frame.append({"frame": index, "frame_index": index, "timestamp": index / fps,
                         "image_base64": encoded_image, "image_format": "image/jpeg" if thumbnails else None,
                         "frame_width": width, "frame_height": height,
                         "preview_width": preview_width, "preview_height": preview_height,
                         "detections": [item.to_dict() for item in detections],
                         "event_end_index": event_end, "events": [item.to_dict() for item in emitted],
                         "replay_state": replay})
                    timings.append((time.perf_counter() - frame_start) * 1000)
                index += 1
        finally:
            capture.release()
    elapsed_ms = (time.perf_counter() - started) * 1000
    ordered = sorted(timings)
    state = tracker.log.replay().to_dict()
    return {"frames": detections_per_frame, "state": state,
            "events": [item.to_dict() for item in tracker.log.events],
            "deck_estimation": _deck_estimation(state, "explicit-video-parameter"),
            "summary": _perception_summary(tracker), "input": "video pixels only",
            "frame_source": "local-video", "processed_frames": len(timings), "decoded_frames": index,
            "stride": stride, "sampled_out_frames": index - len(timings), "drop_count": None,
            "latency_ms": elapsed_ms, "mean_frame_ms": sum(timings) / len(timings) if timings else None,
            "p95_frame_ms": ordered[math.ceil(len(ordered) * .95) - 1] if ordered else None,
            "pipeline_fps": len(timings) * 1000 / elapsed_ms if elapsed_ms else None,
            "throughput_semantics": "offline sampled frame throughput including decode; not live stream FPS",
            "source_reported_fps": reported_fps if math.isfinite(reported_fps) and reported_fps > 0 else None,
            "timestamp_basis": "frame index / source FPS" if reported_fps == fps else "frame index / assumed 30 FPS",
            "stream_fps": None, "thumbnails": thumbnails,
            "deck_provenance": "explicit-video-parameter" if decks is not None else "unknown",
            "segmentation": "single-round clip; no automatic round or shoe transition detection",
            "limitation": "Template detector calibrated to lab card artwork; arbitrary camera cards need adaptation."}


def mount_ui() -> None:
    distribution = ROOT / "ui" / "dist"
    if distribution.exists():
        app.mount("/", StaticFiles(directory=distribution, html=True), name="ui")
    else:
        @app.get("/")
        def missing_ui() -> dict:
            return {"service": "Blackjack Vision Lab", "api_docs": "/docs", "ui": "Build ui/dist to enable the dashboard."}


from .live_api import router as live_router
app.include_router(live_router)
from .native_advisor import router as native_advisor_router
app.include_router(native_advisor_router)
from .advisor_api import router as advisor_router
app.include_router(advisor_router)
from .model_api import router as model_router
app.include_router(model_router)
from .poker_api import router as poker_router
app.include_router(poker_router)
from .integration_api import router as integration_router
app.include_router(integration_router)
mount_ui()
