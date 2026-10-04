"""Local perception, temporal identity, uncertainty and deck inference.

The baseline recognizes this lab's renderer. Its similarity scores are explicitly
not probabilities and no ground truth travels through the detector API.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, asdict
from io import BytesIO
import math
from pathlib import Path
import time
from typing import Any, Iterable, Mapping, Protocol

import cv2
import numpy as np
from PIL import Image

from .datasets import CARD_WIDTH, CARD_HEIGHT, card_image, bbox_iou
from .events import Event, EventLog, EventValidationError, RANKS, SUITS, normalize_rank, normalize_suit


@dataclass(frozen=True)
class CardDetection:
    rank: str | None
    suit: str | None
    bbox: tuple[int, int, int, int]
    score: float
    face_down: bool = False
    zone: str = "unknown"
    logical_hint: str | None = None
    calibrated_probability: float | None = None
    score_type: str = "template_similarity"
    visibility: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rank", normalize_rank(self.rank))
        object.__setattr__(self, "suit", normalize_suit(self.suit))
        if not math.isfinite(self.score) or not 0 <= self.score <= 1:
            raise ValueError("Detection score must be finite and in [0, 1]")
        if (len(self.bbox) != 4 or any(not math.isfinite(value) for value in self.bbox) or
                self.bbox[2] <= 0 or self.bbox[3] <= 0):
            raise ValueError("Bounding box must be x,y,width,height with positive size")
        if self.face_down and (self.rank is not None or self.suit is not None):
            raise ValueError("A hidden detection must not disclose its rank or suit")
        visibility = self.visibility or ("covered" if self.face_down else "readable" if self.rank else "unreadable")
        if visibility not in ("readable", "covered", "unreadable"):
            raise ValueError("A detection is a present object; absence is not a detection")
        if (visibility == "covered") != self.face_down or (visibility == "readable") != (self.rank is not None):
            raise ValueError("Visibility must agree with the observed rank and card orientation")
        object.__setattr__(self, "visibility", visibility)
        if self.calibrated_probability is not None and not 0 <= self.calibrated_probability <= 1:
            raise ValueError("Calibrated probability must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Detector(Protocol):
    def detect(self, image: Image.Image | np.ndarray | str | Path) -> list[CardDetection]: ...


def _rgb(image: Image.Image | np.ndarray | str | Path | bytes) -> np.ndarray:
    if isinstance(image, bytes):
        image = Image.open(BytesIO(image))
    if isinstance(image, (str, Path)):
        image = Image.open(image)
    if isinstance(image, Image.Image):
        result = np.asarray(image.convert("RGB"))
    else:
        result = np.asarray(image)
        if result.ndim != 3 or result.shape[2] not in (3, 4):
            raise ValueError("Detector requires an RGB/RGBA image")
        result = result[:, :, :3]
    if result.dtype != np.uint8:
        if np.any(~np.isfinite(result)):
            raise ValueError("Image must be finite")
        result = np.clip(result, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(result)


def _glyph(crop: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    # Adaptive threshold uses the bright local card background, supports red ink.
    threshold = max(50, min(200, (float(np.percentile(gray, 90)) + float(gray.min())) / 2))
    binary = gray < threshold
    ys, xs = np.nonzero(binary)
    if not len(xs) or len(xs) < 6:
        return None
    binary = binary[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
    return cv2.resize(binary, (32, 40), interpolation=cv2.INTER_AREA)


def _match(glyph: np.ndarray | None, templates: Mapping[str, np.ndarray]) -> tuple[str | None, float, float]:
    if glyph is None:
        return None, 0.0, 0.0
    scores = []
    for label, template in templates.items():
        norm = float(np.linalg.norm(glyph) * np.linalg.norm(template))
        cosine = float(np.sum(glyph * template) / norm) if norm else 0.0
        scores.append((max(0, min(1, cosine)), label))
    scores.sort(reverse=True)
    return scores[0][1], scores[0][0], scores[0][0] - scores[1][0] if len(scores) > 1 else 1.0


class TemplateCardDetector:
    """OpenCV rectangle detector plus rank/suit template recognizer.

    Supports the deterministic ivory card contract at several scales, local
    PNG/JPEG frames and moderate brightness/noise/blur. Overlapped corner marks,
    arbitrary casino themes and perspective require an independently trained
    detector; these unsupported cases become misses/low scores, never guessed truth.
    """
    def __init__(self, *, minimum_score: float = .68,
                 zones: Mapping[str, tuple[int, int, int, int]] | None = None,
                 font_path: str | None = None) -> None:
        # Small lab frames are faster and predictable without a native thread pool
        # per API worker. Also avoids oversubscription alongside mathematical jobs.
        cv2.setNumThreads(1)
        if not 0 <= minimum_score <= 1:
            raise ValueError("minimum_score must be in [0,1]")
        self.minimum_score = minimum_score
        self.zones = dict(zones or {})
        self.rank_templates: dict[str, np.ndarray] = {}
        self.suit_templates: dict[str, np.ndarray] = {}
        for rank in RANKS:
            arr = np.asarray(card_image(rank, "S", font_path=font_path))
            self.rank_templates[rank] = _glyph(arr[5:32, 7:62])
        for suit in SUITS:
            arr = np.asarray(card_image("A", suit, font_path=font_path))
            self.suit_templates[suit] = _glyph(arr[33:58, 7:35])
        self.last_diagnostics: dict[str, Any] = {}

    def _zone(self, box: tuple[int, int, int, int], height: int) -> str:
        x, y, w, h = box
        cx, cy = x + w / 2, y + h / 2
        for zone, (zx, zy, zw, zh) in self.zones.items():
            if zx <= cx <= zx + zw and zy <= cy <= zy + zh:
                return zone
        return "dealer" if cy < height * .48 else "player"

    def detect(self, image: Image.Image | np.ndarray | str | Path | bytes) -> list[CardDetection]:
        started = time.perf_counter()
        rgb = _rgb(image)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, np.array([0, 0, 165], dtype=np.uint8),
                           np.array([179, 95, 255], dtype=np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections, rejected = [], 0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if not (30 <= w <= 400 and 44 <= h <= 600 and .57 <= w / h <= .84):
                continue
            if cv2.contourArea(contour) / (w * h) < .78:
                continue
            # The border is dark and is not present in the white contour.
            x, y = max(0, x - 1), max(0, y - 1)
            w, h = min(rgb.shape[1] - x, w + 2), min(rgb.shape[0] - y, h + 2)
            tile = cv2.resize(rgb[y:y + h, x:x + w], (CARD_WIDTH, CARD_HEIGHT),
                              interpolation=cv2.INTER_AREA)
            tile_hsv = cv2.cvtColor(tile, cv2.COLOR_RGB2HSV)
            blue_fraction = float(np.mean((tile_hsv[8:-8, 8:-8, 0] > 90) &
                                          (tile_hsv[8:-8, 8:-8, 0] < 125) &
                                          (tile_hsv[8:-8, 8:-8, 1] > 80)))
            box = (x, y, w, h)
            if blue_fraction > .6:
                detections.append(CardDetection(None, None, box, min(1, blue_fraction),
                                                True, self._zone(box, rgb.shape[0]),
                                                score_type="back_pattern_similarity"))
                continue
            rank, rank_score, rank_margin = _match(_glyph(tile[5:32, 7:62]), self.rank_templates)
            suit, suit_score, suit_margin = _match(_glyph(tile[33:58, 7:35]), self.suit_templates)
            score = min(rank_score, suit_score)
            if rank is None or suit is None or score < self.minimum_score:
                rejected += 1
                continue
            detections.append(CardDetection(rank, suit, box, score, False,
                                            self._zone(box, rgb.shape[0])))
        detections.sort(key=lambda detection: (detection.bbox[1], detection.bbox[0]))
        self.last_diagnostics = {"latency_ms": (time.perf_counter() - started) * 1000,
                                 "rejected_card_candidates": rejected, "detections": len(detections),
                                 "score_semantics": "raw similarities; not calibrated probabilities",
                                 "input_shape": list(rgb.shape), "scope": "controlled lab renderer"}
        return detections


CardDetector = TemplateCardDetector


class ONNXCardDetector:
    """Optional real ONNX adapter for an explicit Nx6 card detection contract.

    Model input is [1,3,H,W] RGB float32 /255. Output rows are x1,y1,x2,y2,
    score,class_index in input-pixel coordinates. Class order is ranks x suits
    then BACK (53 labels). This does not pretend arbitrary ONNX models comply.
    """
    def __init__(self, model_path: str | Path, *, input_size: tuple[int, int] = (640, 640),
                 threshold: float = .5) -> None:
        if not Path(model_path).is_file():
            raise FileNotFoundError(model_path)
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("ONNX adapter requires optional onnxruntime and a trained model") from exc
        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.threshold = threshold
        self.labels = [(rank, suit) for rank in RANKS for suit in SUITS] + [(None, None)]

    def detect(self, image: Image.Image | np.ndarray | str | Path) -> list[CardDetection]:
        rgb = _rgb(image)
        iw, ih = self.input_size
        tensor = cv2.resize(rgb, (iw, ih)).astype(np.float32).transpose(2, 0, 1)[None] / 255
        result = np.asarray(self.session.run(None, {self.input_name: tensor})[0]).squeeze(axis=0)
        if result.ndim != 2 or result.shape[1] != 6:
            raise ValueError("Model output does not follow the documented Nx6 detection contract")
        detections = []
        for x1, y1, x2, y2, score, class_id in result:
            if score < self.threshold:
                continue
            cid = int(class_id)
            if cid != class_id or not 0 <= cid < len(self.labels):
                raise ValueError("Invalid ONNX class index")
            rank, suit = self.labels[cid]
            box = (round(x1 * rgb.shape[1] / iw), round(y1 * rgb.shape[0] / ih),
                   round((x2 - x1) * rgb.shape[1] / iw), round((y2 - y1) * rgb.shape[0] / ih))
            detections.append(CardDetection(rank, suit, box, float(score), cid == 52,
                                            score_type="onnx_model_score"))
        # Class-agnostic NMS suppresses repeated boxes; identities belong to the tracker.
        kept: list[CardDetection] = []
        for detection in sorted(detections, key=lambda d: d.score, reverse=True):
            if all(bbox_iou(detection.bbox, previous.bbox) < .5 for previous in kept):
                kept.append(detection)
        return kept


@dataclass
class _Track:
    card_id: str
    bbox: tuple[int, int, int, int]
    zone: str
    rank: str | None
    suit: str | None
    face_down: bool
    score: float
    hits: int = 1
    missed: int = 0
    confirmed: bool = False
    lost: bool = False
    candidate: tuple[str | None, str | None, bool] | None = None
    candidate_hits: int = 0
    logical_hint: str | None = None


class TemporalTracker:
    """Associate observations with logical deal events through movement/reveals.

    Tracks remain available throughout a round, including after occlusion. The
    caller must signal a round boundary: image-only observations cannot identify
    two identical cards removed and redealt between unseen frames with certainty.
    Ambiguous association is surfaced as an integrity gate, never a certainty.
    """
    def __init__(self, log: EventLog | None = None, *, stable_frames: int = 3,
                 minimum_score: float = .90, lost_after: int = 3,
                 association_radius: float = 190) -> None:
        if stable_frames < 1 or lost_after < 1 or association_radius <= 0:
            raise ValueError("Invalid temporal tracker thresholds")
        self.log = log if log is not None else EventLog()
        self.stable_frames, self.minimum_score = stable_frames, minimum_score
        self.lost_after, self.association_radius = lost_after, association_radius
        self.tracks: dict[str, _Track] = {}
        self.round_id: str | None = None
        self.sequence = 0
        self.ambiguities: list[str] = []
        self.last_timestamp = 0.0

    def new_shoe(self, decks: int | None, *, timestamp: float = 0,
                 shoe_id: str | None = None) -> Event:
        event = self.log.append("NEW_SHOE", {"decks": decks, "shoe_id": shoe_id or f"shoe-{len(self.log)}"},
                                timestamp=timestamp)
        self.tracks.clear()
        self.round_id = None
        self.sequence = 0
        self.ambiguities.clear()
        self.last_timestamp = timestamp
        return event

    def start_round(self, round_id: str, *, timestamp: float) -> Event:
        event = self.log.append("ROUND_STARTED", {"round_id": round_id}, timestamp=timestamp)
        self.tracks.clear()
        self.round_id = str(round_id)
        self.ambiguities.clear()
        self.last_timestamp = timestamp
        return event

    def end_round(self, *, timestamp: float) -> Event:
        event = self.log.append("ROUND_ENDED", {"round_id": self.round_id}, timestamp)
        self.tracks.clear()
        self.last_timestamp = timestamp
        return event

    @staticmethod
    def _distance(track: _Track, detection: CardDetection) -> float:
        x, y, w, h = track.bbox
        dx, dy, dw, dh = detection.bbox
        return math.hypot((x + w / 2) - (dx + dw / 2), (y + h / 2) - (dy + dh / 2))

    def _association_cost(self, track: _Track, detection: CardDetection) -> float | None:
        if track.logical_hint is not None and detection.logical_hint is not None:
            return 0 if track.logical_hint == detection.logical_hint else None
        distance = self._distance(track, detection)
        same_label = (track.rank, track.suit, track.face_down) == (detection.rank, detection.suit,
                                                                 detection.face_down)
        same_zone = track.zone == detection.zone or "unknown" in (track.zone, detection.zone)
        overlap = bbox_iou(track.bbox, detection.bbox)
        # A unique matching face may move farther than the local radius in one frame.
        if same_label and same_zone:
            return distance * .65 + (15 if track.missed else 0)
        # A reveal/correction is associated by location, not by its newly seen rank.
        if distance < self.association_radius and (same_zone or overlap > .3):
            return distance + 35 + (60 if not same_zone else 0)
        return None

    def _event_payload(self, track: _Track) -> dict[str, Any]:
        return {"card_id": track.card_id, "rank": track.rank, "suit": track.suit,
                "face_down": track.face_down, "bbox": list(track.bbox), "zone": track.zone,
                "visibility": "covered" if track.face_down else "readable" if track.rank else "unreadable",
                "round_id": self.round_id, "score": track.score,
                "score_semantics": "raw_similarity_not_probability"}

    def update(self, detections: Iterable[CardDetection | Mapping[str, Any]], timestamp: float,
               round_id: str | None = None) -> list[Event]:
        stamp = float(timestamp)
        if not math.isfinite(stamp) or stamp < self.last_timestamp:
            raise ValueError("Frame timestamps must be finite and monotonic")
        before = len(self.log)
        if self.log.replay().shoe_id is None:
            self.new_shoe(None, timestamp=stamp)
        if round_id is not None and str(round_id) != self.round_id:
            self.start_round(str(round_id), timestamp=stamp)
        observations = [d if isinstance(d, CardDetection) else CardDetection(**d) for d in detections]
        observations = [d for d in observations if d.score >= self.minimum_score]
        self.ambiguities = []
        candidates: list[tuple[float, str, int]] = []
        for cid, track in self.tracks.items():
            for i, detection in enumerate(observations):
                cost = self._association_cost(track, detection)
                if cost is not None:
                    candidates.append((cost, cid, i))
        candidates.sort()
        assignments: dict[int, str] = {}
        assigned_tracks: set[str] = set()
        for cost, cid, i in candidates:
            if i in assignments or cid in assigned_tracks:
                continue
            competing = [(other_cost, other_cid) for other_cost, other_cid, other_i in candidates
                         if other_i == i and other_cid != cid and other_cid not in assigned_tracks]
            if competing and abs(competing[0][0] - cost) < 10:
                reason = f"Observation {i} has ambiguous identity between {cid} and {competing[0][1]}"
                self.ambiguities.append(reason)
                issue_id = "identity:" + ":".join(sorted((cid, competing[0][1])))
                if issue_id not in self.log.replay().integrity_issues:
                    self.log.append("STATE_UNCERTAIN", {"issue_id": issue_id, "reason": reason}, stamp)
            assignments[i] = cid
            assigned_tracks.add(cid)
        for i, detection in enumerate(observations):
            if i not in assignments:
                self.sequence += 1
                shoe_id = self.log.replay().shoe_id
                cid = f"{shoe_id}:card-{self.sequence}"
                track = _Track(cid, detection.bbox, detection.zone, detection.rank, detection.suit,
                               detection.face_down, detection.score, logical_hint=detection.logical_hint)
                self.tracks[cid] = track
                assigned_tracks.add(cid)
                assignments[i] = cid
            else:
                track = self.tracks[assignments[i]]
                track.hits += 1
                if track.lost and track.confirmed:
                    self.log.append("TRACK_REACQUIRED", {"card_id": track.card_id}, stamp)
                track.lost = False
                track.missed = 0
                track.bbox, track.score = detection.bbox, detection.score
                if detection.zone != track.zone:
                    track.zone = detection.zone
                    if track.confirmed:
                        self.log.append("CARD_MOVED", {"card_id": track.card_id, "zone": track.zone,
                                                       "bbox": list(track.bbox)}, stamp)
                label = (detection.rank, detection.suit, detection.face_down)
                current = (track.rank, track.suit, track.face_down)
                if label != current:
                    if not track.confirmed:
                        track.hits = 0
                    track.candidate_hits = track.candidate_hits + 1 if track.candidate == label else 1
                    track.candidate = label
                    if track.candidate_hits >= self.stable_frames:
                        was_hidden = track.rank is None
                        track.rank, track.suit, track.face_down = label
                        track.candidate, track.candidate_hits = None, 0
                        if not track.confirmed:
                            track.hits = self.stable_frames
                        if track.confirmed:
                            kind = "CARD_REVEALED" if was_hidden and track.rank is not None else "STATE_CORRECTION"
                            payload = self._event_payload(track)
                            if kind == "STATE_CORRECTION":
                                payload["reason"] = "stable visual label correction"
                            try:
                                self.log.append(kind, payload, stamp)
                            except EventValidationError as exc:
                                track.rank, track.suit, track.face_down = current
                                self.ambiguities.append(f"Correction rejected by card conservation: {exc}")
                else:
                    if not track.confirmed and track.candidate is not None:
                        # A return to the original reading after a flicker starts
                        # a fresh consecutive stability window.
                        track.hits = 1
                    track.candidate, track.candidate_hits = None, 0
            if not track.confirmed and track.hits >= self.stable_frames and track.candidate is None:
                try:
                    self.log.append("CARD_CONFIRMED", self._event_payload(track), stamp)
                    track.confirmed = True
                except EventValidationError as exc:
                    self.ambiguities.append(f"Card conservation rejected {track.card_id}: {exc}")
        for cid, track in self.tracks.items():
            if cid not in assigned_tracks:
                track.missed += 1
                track.hits = 0 if not track.confirmed else track.hits
                if track.missed >= self.lost_after and not track.lost:
                    track.lost = True
                    if track.confirmed:
                        self.log.append("TRACK_LOST", {"card_id": cid,
                                                      "reason": "card occluded or removed without round boundary"}, stamp)
        self.last_timestamp = stamp
        return list(self.log.events[before:])

    def correct(self, card_id: str, *, rank: str | None, suit: str | None,
                reason: str, timestamp: float) -> Event:
        event = self.log.append("STATE_CORRECTION", {"card_id": card_id, "rank": rank,
                               "suit": suit, "reason": reason}, timestamp)
        if card_id in self.tracks:
            track = self.tracks[card_id]
            track.rank, track.suit = normalize_rank(rank), normalize_suit(suit)
            track.face_down = track.rank is None
            track.candidate, track.candidate_hits = None, 0
        self.last_timestamp = timestamp
        return event

    def state_summary(self) -> dict[str, Any]:
        state = self.log.replay()
        pending = [track.card_id for track in self.tracks.values()
                   if not track.confirmed or track.candidate is not None or track.missed > 0]
        reasons = list(self.ambiguities) + list(state.integrity_issues.values())
        if pending:
            reasons.append(f"{len(pending)} cards await stable visual evidence")
        status = "manual_review" if self.ambiguities or state.integrity_issues else "provisional" if pending else "stable"
        return {**state.to_dict(), "gate": {"status": status, "reasons": reasons,
                "solver_allowed": status == "stable" and bool(state.counted_ids),
                "probability_of_correct_state": None,
                "confidence_semantics": "deterministic integrity checks; no uncalibrated state probability"},
                "tracks": [{"card_id": t.card_id, "rank": t.rank, "suit": t.suit,
                            "bbox": list(t.bbox), "zone": t.zone, "score": t.score,
                            "confirmed": t.confirmed, "hits": t.hits, "missed": t.missed,
                            "label_pending": t.candidate is not None,
                            "candidate_hits": t.candidate_hits,
                            "lost": t.lost} for t in self.tracks.values()]}


class ScoreCalibrator:
    """Held-out empirical bin calibration with Laplace smoothing and support counts.

    Fit ONLY matched validation outcomes and false positives from calibration
    sessions. It estimates per-detection correctness, never whole-session integrity.
    Empty bins return None; probabilities have empirical support, not magic certainty.
    """
    def __init__(self, bins: int = 10) -> None:
        if bins < 2:
            raise ValueError("At least two calibration bins are required")
        self.bins = bins
        self.counts = [0] * bins
        self.correct = [0] * bins

    def fit(self, samples: Iterable[tuple[float, bool]]) -> "ScoreCalibrator":
        self.counts, self.correct = [0] * self.bins, [0] * self.bins
        for score, correct in samples:
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("Calibration scores must be finite in [0, 1]")
            index = min(self.bins - 1, int(score * self.bins))
            self.counts[index] += 1
            self.correct[index] += int(bool(correct))
        return self

    def predict(self, score: float) -> float | None:
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Calibration score must be in [0,1]")
        index = min(self.bins - 1, int(score * self.bins))
        return ((self.correct[index] + 1) / (self.counts[index] + 2)
                if self.counts[index] else None)

    def evaluate(self, samples: Iterable[tuple[float, bool]]) -> dict[str, Any]:
        outcomes = [(self.predict(score), bool(correct)) for score, correct in samples]
        supported = [(p, correct) for p, correct in outcomes if p is not None]
        if not supported:
            return {"supported": 0, "unsupported": len(outcomes), "brier_score": None, "ece": None}
        ece = 0.0
        for b in range(self.bins):
            group = [(p, c) for p, c in supported if min(self.bins - 1, int(p * self.bins)) == b]
            if group:
                ece += len(group) / len(supported) * abs(sum(p for p, _ in group) / len(group) -
                                                        sum(c for _, c in group) / len(group))
        return {"supported": len(supported), "unsupported": len(outcomes) - len(supported),
                "brier_score": sum((p - int(c)) ** 2 for p, c in supported) / len(supported),
                "ece": ece, "counts": list(self.counts)}

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "method": "empirical_bins_laplace",
                "bins": self.bins, "counts": list(self.counts), "correct": list(self.correct),
                "scope": "per-detection correctness, not session integrity"}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScoreCalibrator":
        if data.get("schema_version") != 1 or data.get("method") != "empirical_bins_laplace":
            raise ValueError("Unsupported calibration schema")
        obj = cls(int(data["bins"]))
        counts, correct = list(data["counts"]), list(data["correct"])
        if len(counts) != obj.bins or len(correct) != obj.bins or any(
                type(n) is not int or type(c) is not int or n < 0 or not 0 <= c <= n
                for n, c in zip(counts, correct)):
            raise ValueError("Invalid calibration support counts")
        obj.counts, obj.correct = counts, correct
        return obj


class DeckCountEstimator:
    """Bayesian deck posterior using confirmed rank/suit draws without replacement.

    Missing suits marginalize over rank-level multiplicities. Priors represent
    assumptions, not measurement; the result cannot identify unseen deck count
    with certainty. Reset on each new shoe, and never feed repeated frame detections.
    """
    def __init__(self, candidates: Iterable[int] = (1, 2, 4, 6, 8),
                 priors: Mapping[int, float] | None = None) -> None:
        self.candidates = tuple(candidates)
        if not self.candidates or any(type(n) is not int or n <= 0 for n in self.candidates):
            raise ValueError("Deck candidates must be positive integers")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError("Deck candidates must be unique")
        prior = {n: float(priors.get(n, 0)) if priors is not None else 1 for n in self.candidates}
        if any(not math.isfinite(v) or v < 0 for v in prior.values()) or sum(prior.values()) <= 0:
            raise ValueError("Invalid deck-count priors")
        total = sum(prior.values())
        self.priors = {n: prior[n] / total for n in self.candidates}
        self.observations: dict[str, tuple[str, str | None]] = {}

    def observe(self, card_id: str, rank: str, suit: str | None) -> None:
        normalized = (normalize_rank(rank), normalize_suit(suit))
        if normalized[0] is None:
            raise ValueError("Deck estimation requires a confirmed rank")
        # Corrections replace the logical observation instead of adding another draw.
        self.observations[str(card_id)] = normalized

    def reset(self) -> None:
        self.observations.clear()

    def estimate(self) -> dict[str, Any]:
        exact = Counter((r, s) for r, s in self.observations.values() if s is not None)
        unknown_suit = Counter(r for r, s in self.observations.values() if s is None)
        n = len(self.observations)
        likelihood: dict[int, float] = {}
        # unordered sample likelihood constants cancel between candidate shoe sizes.
        for decks in self.candidates:
            if self.priors[decks] == 0 or n > 52 * decks or any(v > decks for v in exact.values()):
                likelihood[decks] = -math.inf
                continue
            logp = math.log(self.priors[decks])
            feasible = True
            used_rank = Counter()
            for (rank, _), count in exact.items():
                logp += math.lgamma(decks + 1) - math.lgamma(decks - count + 1)
                used_rank[rank] += count
            for rank, count in unknown_suit.items():
                available = 4 * decks - used_rank[rank]
                if count > available:
                    feasible = False
                    break
                logp += math.lgamma(available + 1) - math.lgamma(available - count + 1)
            if feasible:
                logp -= math.lgamma(52 * decks + 1) - math.lgamma(52 * decks - n + 1)
                likelihood[decks] = logp
            else:
                likelihood[decks] = -math.inf
        finite = [value for value in likelihood.values() if math.isfinite(value)]
        if not finite:
            return {"status": "inconsistent", "probabilities": {str(n): 0 for n in self.candidates},
                    "observations": n, "reason": "Confirmed cards exceed every candidate shoe"}
        maximum = max(finite)
        weights = {d: math.exp(v - maximum) if math.isfinite(v) else 0 for d, v in likelihood.items()}
        total = sum(weights.values())
        probabilities = {d: weights[d] / total for d in self.candidates}
        best = max(probabilities, key=probabilities.get)
        return {"status": "estimated" if n else "prior_only",
                "probabilities": {str(d): probabilities[d] for d in self.candidates},
                "observations": n, "most_likely": best,
                "posterior_max": probabilities[best],
                "entropy_bits": -sum(p * math.log2(p) for p in probabilities.values() if p),
                "assumptions": "uniform shuffled shoe; confirmed draws; specified finite candidate set",
                "certainty": False}


def estimate_discard_tray(pixel_height: float, *, pixels_per_card: float,
                          measurement_error_pixels: float = 4, calibration_error: float = .1) -> dict[str, Any]:
    """Experimental visual height estimate, separate from deck posterior evidence."""
    if pixel_height < 0 or pixels_per_card <= 0 or measurement_error_pixels < 0 or not 0 <= calibration_error < 1:
        raise ValueError("Invalid discard tray calibration")
    estimate = pixel_height / pixels_per_card
    lower = max(0, pixel_height - measurement_error_pixels) / (pixels_per_card * (1 + calibration_error))
    upper = (pixel_height + measurement_error_pixels) / (pixels_per_card * (1 - calibration_error))
    return {"status": "experimental", "estimated_cards": estimate,
            "cards_interval": [lower, upper], "estimated_decks": estimate / 52,
            "decks_interval": [lower / 52, upper / 52],
            "probability": None, "requires_calibration": True}


class LocalVideoSource:
    """Read frames from a local file; no capture of unrelated windows."""
    def __init__(self, path: str | Path) -> None:
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        self.path = str(path)

    def frames(self) -> Iterable[tuple[float, np.ndarray]]:
        capture = cv2.VideoCapture(self.path)
        if not capture.isOpened():
            raise ValueError("OpenCV cannot decode this local video")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or not math.isfinite(fps):
            fps = 30
        index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                yield index / fps, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                index += 1
        finally:
            capture.release()


class LocalWindowCapture:
    """Optional mss adapter requiring an explicit simulator rectangle.

    It does not enumerate or choose third-party windows. User selects the local
    simulator region; a UI must request that rectangle before calling capture.
    """
    def __init__(self, region: Mapping[str, int]) -> None:
        required = {"left", "top", "width", "height"}
        if set(region) != required or region["width"] <= 0 or region["height"] <= 0:
            raise ValueError("Capture requires explicit left/top/width/height")
        self.region = {key: int(value) for key, value in region.items()}

    def capture(self) -> np.ndarray:
        try:
            import mss
        except ImportError as exc:
            raise RuntimeError("Window capture requires optional mss; use PNG/video without it") from exc
        with mss.mss() as screen:
            bgra = np.asarray(screen.grab(self.region))
        return cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGB)
