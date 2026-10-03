"""Offline strategy library and explicit single-image/manual advice."""
from __future__ import annotations

import base64
import io
from collections import Counter
from dataclasses import asdict
from itertools import combinations_with_replacement

from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .advice import recommend
from .engine import Rules, card_rank, initial_counts, legal_actions
from .strategy import get_generated_strategy

router = APIRouter(prefix="/api/advisor")


class StrategyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: dict = Field(default_factory=dict)


class ManualRequest(StrategyRequest):
    player: list[str] = Field(min_length=2, max_length=24)
    dealer: str
    observed: list[str] = Field(default_factory=list, max_length=416)
    from_split: bool = False
    split_hands: int = Field(default=1, ge=1, le=8)
    estimate: bool = True


class ImageRequest(StrategyRequest):
    image_base64: str = Field(max_length=12_000_000)
    corners: list[list[float]] | None = None
    player_turn: bool = True


def _manual(body: ManualRequest):
    rules = Rules(**body.rules)
    counts = list(initial_counts(rules.decks))
    exposed = body.observed or [*body.player, body.dealer]
    current = Counter(card_rank(r) for r in [*body.player, body.dealer])
    evidence = Counter(card_rank(r) for r in exposed)
    if current - evidence:
        raise ValueError("The observed list must include every current player card and the dealer upcard.")
    for rank in exposed:
        index = card_rank(rank) - 1
        counts[index] -= 1
        if counts[index] < 0:
            raise ValueError("Observed ranks exceed the configured inventory.")
    # The list describes observed evidence; it is never an implicit complete shoe.
    running = sum(1 if 2 <= card_rank(r) <= 6 else -1 if card_rank(r) in (1, 10) else 0 for r in exposed)
    remaining = sum(counts)
    count = running / (remaining / 52) if remaining else 0.
    peeked = rules.dealer_peek and not rules.enhc and card_rank(body.dealer) in (1, 10)
    permitted = legal_actions(body.player, rules, from_split=body.from_split,
        split_hands=body.split_hands, peek_resolved=peeked)
    from .live import estimate_actions
    # A finite pool with unknown earlier history is explicitly a conditional model.
    decision = estimate_actions(body.player, body.dealer, counts, rules, permitted,
        samples=1500, peeked=peeked, from_split=body.from_split,
        split_hands=body.split_hands) if body.estimate and remaining >= 16 else None
    advice = recommend(body.player, body.dealer, rules, allowed=permitted,
        from_split=body.from_split, split_hands=body.split_hands,
        split_aces=body.from_split and card_rank(body.player[0]) == 1,
        peeked=peeked, true_count=count, estimate=decision)
    return {"source": "user-confirmed-cards", "advice": advice, "decision": decision,
        "player": body.player, "dealer": [body.dealer], "phase": "player",
        "observed_cards": len(exposed), "running_count": running, "true_count": count,
        "count_scope": "single image or explicit list only; earlier history unknown",
        "physical_remaining": remaining, "gate": {"solver_allowed": True, "reasons": []}}


@router.post("/manual")
async def manual_advice(body: ManualRequest):
    try:
        return await run_in_threadpool(_manual, body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/strategy")
async def strategy_library(body: StrategyRequest):
    def generate():
        rules = Rules(**body.rules)
        strategy = get_generated_strategy(rules)
        table = strategy.generate_table()
        combinations = []
        names = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10")
        for a, b in combinations_with_replacement(names, 2):
            for dealer in names:
                result = strategy.analyze([a, b], dealer)
                combinations.append({"player": [a, b], "dealer": dealer,
                                     "action": result["best_action"]})
        return {"table": table, "combinations": combinations, "rules": asdict(rules),
                "combination_count": len(combinations),
                "scope": "All 550 unordered two-card rank/dealer combinations; tens, J, Q and K share value 10.",
                "precision": "Rule-generated independent-draw reference. Finite deck composition is evaluated separately."}
    try:
        return await run_in_threadpool(generate)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/image")
async def image_advice(body: ImageRequest):
    def inspect():
        from .calibration import normalize_table
        from .vision import TemplateCardDetector
        raw = base64.b64decode(body.image_base64, validate=True)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Image exceeds 8 MiB.")
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > 5_000_000:
                raise ValueError("Image exceeds five megapixels.")
            image = source.convert("RGB")
        if body.corners:
            image = Image.fromarray(normalize_table(image, body.corners, (960, 600), corners_normalized=True).image_rgb)
        detector = TemplateCardDetector(zones={"dealer": (0, 0, 960, 250), "player:0": (0, 290, 960, 310)})
        detections = detector.detect(image)
        player = [d.rank for d in sorted(detections, key=lambda d: d.bbox[0]) if d.zone == "player:0" and not d.face_down and d.rank]
        dealer = [d.rank for d in detections if d.zone == "dealer" and not d.face_down and d.rank]
        reasons = []
        if not body.player_turn:
            reasons.append("Confirm that this image shows your player decision.")
        if len(player) < 2 or len(dealer) != 1:
            reasons.append("Confirm the player cards and dealer upcard, or calibrate/crop the table.")
        if detector.last_diagnostics["rejected_card_candidates"]:
            reasons.append("A card-shaped region could not be read. Confirm cards before using advice.")
        report = {"source": "single-image-pixels", "player": player, "dealer": dealer,
            "detections": [d.to_dict() for d in detections], "decision": None, "advice": None,
            "gate": {"solver_allowed": not reasons, "reasons": reasons},
            "count_scope": "single image only; earlier history unknown"}
        if not reasons:
            observed = [d.rank for d in detections if d.rank and not d.face_down]
            report.update(_manual(ManualRequest(player=player, dealer=dealer[0], observed=observed, rules=body.rules)))
            report["source"] = "single-image-pixels"
        return report
    try:
        return await run_in_threadpool(inspect)
    except (ValueError, TypeError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, str(exc)) from exc
