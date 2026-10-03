"""Controlled pixel-only card fixtures, grouped datasets and perception metrics.

Ground-truth labels are written separately; detectors receive only RGB pixels.
The renderer is also the simulator's documented visual acquisition contract.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
from typing import Any, Iterable, Mapping

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .events import RANKS, SUITS, normalize_rank, normalize_suit

CARD_WIDTH, CARD_HEIGHT = 78, 110
CARD_COLOR = (250, 246, 234)
THEMES = {"green": (12, 77, 55), "navy": (20, 40, 66), "burgundy": (84, 30, 50)}
FONT_CANDIDATES = ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                   "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")


@lru_cache(maxsize=64)
def card_font(size: int, path: str | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path is None:
        path = os.environ.get("BJLAB_FONT_PATH") or None
    if path:
        return ImageFont.truetype(path, size)
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def card_image(rank: str | None, suit: str | None, *, face_down: bool = False,
               scale: float = 1.0, font_path: str | None = None,
               card_design: str = "classic") -> Image.Image:
    """Draw a card with machine-readable rank and suit corner marks.

    ASCII S/H/D/C suit marks make the reference portable across fonts. Decorative
    central suit symbols use vector paths, so they cannot leak a text label.
    """
    if not 0.4 <= scale <= 4:
        raise ValueError("Card scale must be between 0.4 and 4")
    if card_design not in {"classic", "minimal"}:
        raise ValueError("Card design must be classic or minimal")
    image = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, CARD_WIDTH - 1, CARD_HEIGHT - 1), radius=7,
                           fill=CARD_COLOR, outline=(55, 55, 50), width=1)
    if face_down or rank is None:
        draw.rounded_rectangle((5, 5, CARD_WIDTH - 6, CARD_HEIGHT - 6), radius=4,
                               fill=(43, 81, 144), outline=(205, 214, 237), width=2)
        for y in range(10, CARD_HEIGHT - 9, 8):
            for x in range(10, CARD_WIDTH - 9, 8):
                draw.line((x, y, x + 3, y + 3), fill=(107, 145, 192), width=1)
    else:
        rank, suit = normalize_rank(rank), normalize_suit(suit)
        color = (168, 32, 41) if suit in ("H", "D") else (24, 26, 29)
        draw.text((9, 7), rank, font=card_font(22, font_path), fill=color, anchor="lt")
        draw.text((9, 35), suit or "?", font=card_font(17, font_path), fill=color, anchor="lt")
        # Bottom/right duplicate corner allows future partial-occlusion adapters.
        draw.text((CARD_WIDTH - 8, CARD_HEIGHT - 10), rank,
                  font=card_font(16, font_path), fill=color, anchor="rb")
        x, y, a = 47, 67, 11
        if card_design == "minimal":
            # Corner rank/suit geometry remains byte-identical. Only this body
            # decoration changes, keeping the existing detector contract fixed.
            draw.line((39, 66, 55, 66), fill=color, width=2)
            draw.line((47, 58, 47, 74), fill=color, width=2)
        elif suit == "D":
            draw.polygon([(x, y - a), (x + a, y), (x, y + a), (x - a, y)], fill=color)
        elif suit == "H":
            draw.ellipse((x - a, y - a, x + 1, y + 2), fill=color)
            draw.ellipse((x - 1, y - a, x + a, y + 2), fill=color)
            draw.polygon([(x - a, y - 2), (x + a, y - 2), (x, y + a)], fill=color)
        elif suit == "S":
            draw.polygon([(x, y - a), (x - a, y + 2), (x + a, y + 2)], fill=color)
            draw.ellipse((x - a, y - 3, x + 1, y + 8), fill=color)
            draw.ellipse((x - 1, y - 3, x + a, y + 8), fill=color)
            draw.polygon([(x - 4, y + a), (x + 4, y + a), (x, y)], fill=color)
        elif suit == "C":
            draw.ellipse((x - 6, y - 12, x + 6, y), fill=color)
            draw.ellipse((x - 12, y - 3, x + 1, y + 10), fill=color)
            draw.ellipse((x - 1, y - 3, x + 12, y + 10), fill=color)
            draw.polygon([(x - 4, y + 13), (x + 4, y + 13), (x, y + 1)], fill=color)
    if scale != 1:
        image = image.resize((round(CARD_WIDTH * scale), round(CARD_HEIGHT * scale)),
                             Image.Resampling.LANCZOS)
    return image


def render_table(cards: Iterable[Mapping[str, Any]], *, width: int = 960, height: int = 600,
                 theme: str = "green", scale: float = 1.0, font_path: str | None = None,
                 blur: float = 0, brightness: float = 1, noise_std: float = 0,
                 seed: int = 0, rule_labels: Iterable[str] | None = None,
                 button_labels: Iterable[str] | None = None,
                 card_design: str = "classic") -> Image.Image:
    """Render visible cards. Arbitrary labels/card IDs are not encoded in pixels."""
    if theme not in THEMES:
        raise ValueError(f"Unknown table theme {theme!r}")
    if card_design not in {"classic", "minimal"}:
        raise ValueError("Card design must be classic or minimal")
    if not 160 <= width <= 4096 or not 160 <= height <= 2160:
        raise ValueError("Frame size must be between 160 and 4096 x 2160")
    if blur < 0 or noise_std < 0 or not 0.1 <= brightness <= 3:
        raise ValueError("Invalid pixel augmentation")
    image = Image.new("RGB", (width, height), THEMES[theme])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((30, 30, width - 30, height - 30), radius=80,
                           outline=tuple(min(255, c + 30) for c in THEMES[theme]), width=2)
    draw.text((width // 2, 70), "BLACKJACK VISION LAB", fill=(132, 144, 130),
              font=card_font(15, font_path), anchor="mt")
    label_font = card_font(16, font_path)
    if rule_labels:
        lx, ly = round(width * .26), round(height * .06)
        for label in rule_labels:
            label = str(label)
            draw.text((lx, ly), label, font=label_font, fill=(212, 220, 213), anchor="lt")
            lx += round(label_font.getlength(label)) + 18
    if button_labels:
        lx, ly = round(width * .04), round(height * .89)
        for label in button_labels:
            label = str(label)
            button_width = round(label_font.getlength(label)) + 24
            draw.rounded_rectangle((lx - 10, ly - 8, lx + button_width - 14, ly + 24), radius=5,
                                   outline=(147, 156, 144), width=1)
            draw.text((lx, ly), label, font=label_font, fill=(212, 220, 213), anchor="lt")
            lx += button_width + 14
    for number, card in enumerate(cards):
        if not card.get("visible", True):
            continue
        x = round(float(card.get("x", 160 + 95 * number)))
        y = round(float(card.get("y", 330)))
        local_scale = float(card.get("scale", scale))
        tile = card_image(card.get("rank"), card.get("suit"),
                          face_down=bool(card.get("face_down", False)),
                          scale=local_scale, font_path=font_path, card_design=card_design)
        image.paste(tile, (x, y))
        # Occlusion uses a table-colored rectangle; the label still records it.
        fraction = float(card.get("occlusion", 0))
        if fraction:
            if not 0 <= fraction <= 1:
                raise ValueError("Occlusion fraction must be in [0, 1]")
            ImageDraw.Draw(image).rectangle((x, y, x + round(tile.width * fraction), y + tile.height),
                                           fill=THEMES[theme])
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    if brightness != 1 or noise_std:
        arr = np.asarray(image).astype(np.float32) * brightness
        if noise_std:
            arr += np.random.default_rng(seed).normal(0, noise_std, arr.shape)
        image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return image


def _split_for_group(session_id: str, theme: str, seed: int) -> str:
    # Entire session/theme combination is held together: frames never straddle splits.
    digest = hashlib.sha256(f"{seed}:{theme}:{session_id}".encode()).digest()
    score = int.from_bytes(digest[:4], "big") / 2 ** 32
    return "train" if score < 0.6 else "calibration" if score < 0.8 else "test"


def generate_dataset(output: str | Path, *, sessions: int = 12, frames_per_session: int = 6,
                     seed: int = 13, themes: Iterable[str] = tuple(THEMES),
                     augment: bool = True, holdout_theme: str | None = "burgundy") -> dict[str, Any]:
    """Write deterministic PNGs and a manifest, grouping split by session AND theme.

    A held-out theme is test-only. Every remaining session is assigned once,
    independently of the theme, which prevents cross-theme session leakage.
    """
    if sessions < 1 or frames_per_session < 1:
        raise ValueError("Dataset needs positive sessions and frames")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    themes = tuple(themes)
    records: list[dict[str, Any]] = []
    for session in range(sessions):
        sid = f"session-{session:04d}"
        deck = [(rank, suit) for rank in RANKS for suit in SUITS]
        rng.shuffle(deck)
        selected = deck[:rng.randint(3, 7)]
        for theme in themes:
            if theme not in THEMES:
                raise ValueError(f"Unknown table theme {theme}")
            split = "test" if theme == holdout_theme else _split_for_group(sid, "all", seed)
            for frame_index in range(frames_per_session):
                positions: list[dict[str, Any]] = []
                for i, (rank, suit) in enumerate(selected):
                    positions.append({"card_id": f"{sid}-card-{i}", "rank": rank, "suit": suit,
                                      "x": 110 + 105 * i + frame_index * 2,
                                      "y": 180 if i < 2 else 350,
                                      "zone": "dealer" if i < 2 else "player",
                                      "face_down": i == 1 and frame_index < frames_per_session // 2,
                                      "visible": not (i == 2 and frame_index == 2)})
                # Keep low augmentations as a reproducible support boundary baseline.
                brightness = rng.uniform(.9, 1.1) if augment else 1
                blur = rng.choice((0, .2, .4)) if augment else 0
                noise = rng.choice((0, 1, 2)) if augment else 0
                image = render_table(positions, theme=theme, brightness=brightness,
                                     blur=blur, noise_std=noise, seed=seed + len(records))
                rel = f"{split}/{sid}-{theme}-{frame_index:04d}.png"
                destination = root / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                image.save(destination, compress_level=1)
                labels = []
                for card in positions:
                    if card["visible"]:
                        hidden = card["face_down"]
                        labels.append({**card, "rank": None if hidden else card["rank"],
                                       "suit": None if hidden else card["suit"],
                                       "bbox": [card["x"], card["y"], CARD_WIDTH, CARD_HEIGHT]})
                records.append({"image": rel, "session_id": sid, "theme": theme, "split": split,
                                "frame": frame_index, "timestamp": frame_index / 10,
                                "labels": labels,
                                "augmentation": {"brightness": brightness, "blur": blur,
                                                 "noise_std": noise}})
    # A session exposed by held-out-theme test cannot appear in train/calibration.
    # Strict session+theme evaluation uses distinct sessions for test themes.
    if holdout_theme is not None:
        heldout_sessions = {r["session_id"] for r in records
                            if _split_for_group(r["session_id"], "all", seed) == "test"}
        for record in list(records):
            if record["theme"] == holdout_theme and record["session_id"] not in heldout_sessions:
                (root / record["image"]).unlink()
                records.remove(record)
    manifest = {"schema_version": 1, "seed": seed, "sessions": sessions,
                "frames_per_session": frames_per_session, "render_contract": "ivory-78x110-ascii-v1",
                "split_policy": "entire session is disjoint; heldout theme is test-only",
                "heldout_theme": holdout_theme, "records": records}
    validate_splits(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def validate_splits(manifest: Mapping[str, Any]) -> None:
    seen: dict[str, str] = {}
    groups: dict[tuple[str, str], str] = {}
    for record in manifest.get("records", []):
        sid, theme, split = record["session_id"], record["theme"], record["split"]
        if split not in {"train", "calibration", "test"}:
            raise ValueError("Unknown data split")
        if sid in seen and seen[sid] != split:
            raise ValueError(f"Session leakage: {sid} occurs in several splits")
        if (sid, theme) in groups and groups[(sid, theme)] != split:
            raise ValueError("Theme/session leakage")
        seen[sid], groups[(sid, theme)] = split, split
        if theme == manifest.get("heldout_theme") and split != "test":
            raise ValueError("Heldout theme leaks into training/calibration")


def bbox_iou(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay, aw, ah = tuple(a)
    bx, by, bw, bh = tuple(b)
    overlap = max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(
        0, min(ay + ah, by + bh) - max(ay, by))
    return overlap / max(1e-12, aw * ah + bw * bh - overlap)


def detection_metrics(predictions: Iterable[Mapping[str, Any]], labels: Iterable[Mapping[str, Any]],
                      *, iou_threshold: float = .5) -> dict[str, Any]:
    predictions, labels = list(predictions), list(labels)
    candidates = sorted(((bbox_iou(p["bbox"], t["bbox"]), i, j)
                         for i, p in enumerate(predictions) for j, t in enumerate(labels)), reverse=True)
    used_pred: set[int] = set()
    used_truth: set[int] = set()
    matches = []
    for overlap, i, j in candidates:
        if overlap >= iou_threshold and i not in used_pred and j not in used_truth:
            used_pred.add(i)
            used_truth.add(j)
            matches.append((predictions[i], labels[j]))
    rank_matches = [(p, t) for p, t in matches if t.get("rank") is not None]
    suit_matches = [(p, t) for p, t in matches if t.get("suit") is not None]
    rank_correct = sum(p.get("rank") == t.get("rank") for p, t in rank_matches)
    suit_correct = sum(p.get("suit") == t.get("suit") for p, t in suit_matches)
    def is_back(card: Mapping[str, Any]) -> bool:
        return bool(card.get("face_down", card.get("rank") is None))
    back_tp = sum(is_back(p) and is_back(t) for p, t in matches)
    back_fp = sum(is_back(p) and not is_back(t) for p, t in matches) + sum(
        is_back(p) for i, p in enumerate(predictions) if i not in used_pred)
    back_fn = sum(not is_back(p) and is_back(t) for p, t in matches) + sum(
        is_back(t) for j, t in enumerate(labels) if j not in used_truth)
    return {"true_positives": len(matches), "false_positives": len(predictions) - len(matches),
            "false_negatives": len(labels) - len(matches),
            "precision": len(matches) / len(predictions) if predictions else None,
            "recall": len(matches) / len(labels) if labels else None,
            "rank_correct": rank_correct, "suit_correct": suit_correct,
            "visible_rank_matches": len(rank_matches), "visible_suit_matches": len(suit_matches),
            "rank_accuracy": rank_correct / len(rank_matches) if rank_matches else None,
            "suit_accuracy": suit_correct / len(suit_matches) if suit_matches else None,
            "back_true_positives": back_tp, "back_false_positives": back_fp,
            "back_false_negatives": back_fn,
            "back_precision": back_tp / (back_tp + back_fp) if back_tp + back_fp else None,
            "back_recall": back_tp / (back_tp + back_fn) if back_tp + back_fn else None,
            "matched_scores": [{"score": p.get("score"),
                                "correct": p.get("rank") == t.get("rank") and
                                p.get("suit") == t.get("suit") and
                                is_back(p) == is_back(t)} for p, t in matches] + [
                                    {"score": p.get("score"), "correct": False}
                                    for i, p in enumerate(predictions) if i not in used_pred]}


def event_metrics(predicted: Iterable[Mapping[str, Any]], expected: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Measure semantic card events by truth ID when an evaluator supplies matches.

    The evaluator may attach truth_card_id after geometrical matching. Track IDs
    alone cannot establish semantic correctness across an observation gap.
    """
    from collections import Counter
    def key(event: Mapping[str, Any]) -> tuple[Any, Any, Any]:
        payload = event.get("payload", event)
        return (event.get("kind", "CARD_CONFIRMED"),
                payload.get("truth_card_id", payload.get("card_id")), payload.get("rank"))
    p, t = Counter(key(e) for e in predicted), Counter(key(e) for e in expected)
    missed = sum((t - p).values())
    extra = sum((p - t).values())
    duplicates = sum(max(0, count - max(1, t[k])) for k, count in p.items())
    return {"expected_events": sum(t.values()), "predicted_events": sum(p.values()),
            "missed_events": missed, "extra_events": extra, "duplicate_events": duplicates,
            "event_recall": (sum(t.values()) - missed) / sum(t.values()) if t else None}


def benchmark_dataset(dataset: str | Path, detector: Any, *, split: str = "test") -> dict[str, Any]:
    root = Path(dataset)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    validate_splits(manifest)
    records = [r for r in manifest["records"] if r["split"] == split]
    totals = {"true_positives": 0, "false_positives": 0, "false_negatives": 0,
              "rank_correct": 0, "suit_correct": 0,
              "visible_rank_matches": 0, "visible_suit_matches": 0,
              "back_true_positives": 0, "back_false_positives": 0, "back_false_negatives": 0}
    latency, score_labels = [], []
    for record in records:
        image = Image.open(root / record["image"]).convert("RGB")
        start = time.perf_counter()
        detections = detector.detect(image)
        latency.append((time.perf_counter() - start) * 1000)
        preds = [d.to_dict() if hasattr(d, "to_dict") else asdict(d) if is_dataclass(d) else d
                 for d in detections]
        metrics = detection_metrics(preds, record["labels"])
        for key in totals:
            totals[key] += metrics[key]
        score_labels.extend(metrics["matched_scores"])
    tp, fp, fn = (totals[key] for key in ("true_positives", "false_positives", "false_negatives"))
    return {"schema_version": 1, "split": split, "frames": len(records), **totals,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "rank_accuracy": totals["rank_correct"] / totals["visible_rank_matches"] if totals["visible_rank_matches"] else None,
            "suit_accuracy": totals["suit_correct"] / totals["visible_suit_matches"] if totals["visible_suit_matches"] else None,
            "back_precision": totals["back_true_positives"] / (totals["back_true_positives"] + totals["back_false_positives"])
                              if totals["back_true_positives"] + totals["back_false_positives"] else None,
            "back_recall": totals["back_true_positives"] / (totals["back_true_positives"] + totals["back_false_negatives"])
                           if totals["back_true_positives"] + totals["back_false_negatives"] else None,
            "latency_ms_mean": float(np.mean(latency)) if latency else None,
            "latency_ms_p95": float(np.percentile(latency, 95)) if latency else None,
            "raw_score_labels": score_labels,
            "probability_calibration": "raw template scores are not probabilities",
            "scope": "controlled synthetic renderer; no external-casino generalization"}


def benchmark_tracking_dataset(dataset: str | Path, detector: Any, *, split: str = "test",
                               stable_frames: int = 3) -> dict[str, Any]:
    """Run pixels -> tracker -> events -> replay against separate session truth.

    Truth IDs are attached only by the evaluator after emitted event bboxes are
    matched. They never enter the detector or tracker. Eligibility uses consecutive
    ground-truth visibility, independently of recognition success.
    """
    from collections import defaultdict, Counter
    from .vision import TemporalTracker
    root = Path(dataset)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    validate_splits(manifest)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in manifest["records"]:
        if record["split"] == split:
            groups[(record["session_id"], record["theme"])].append(record)
    reports = []
    latencies = []
    for (sid, theme), frames in sorted(groups.items()):
        tracker = TemporalTracker(stable_frames=stable_frames, minimum_score=.90)
        tracker.new_shoe(1, timestamp=0, shoe_id=f"{sid}-{theme}")
        truth_last: dict[str, dict[str, Any]] = {}
        max_streak: dict[str, int] = defaultdict(int)
        current_streak: dict[str, int] = defaultdict(int)
        max_label_streak: dict[str, int] = defaultdict(int)
        label_streak: dict[str, int] = defaultdict(int)
        previous_label: dict[str, tuple[Any, Any]] = {}
        emitted_map: dict[str, str] = {}
        for frame in sorted(frames, key=lambda f: f["frame"]):
            visible = {label["card_id"]: label for label in frame["labels"]}
            for truth_id in set(truth_last) | set(visible):
                if truth_id in visible:
                    label = visible[truth_id]
                    current_streak[truth_id] += 1
                    max_streak[truth_id] = max(max_streak[truth_id], current_streak[truth_id])
                    pair = (label["rank"], label["suit"])
                    label_streak[truth_id] = label_streak[truth_id] + 1 if previous_label.get(truth_id) == pair else 1
                    previous_label[truth_id] = pair
                    max_label_streak[truth_id] = max(max_label_streak[truth_id], label_streak[truth_id])
                    truth_last[truth_id] = label
                else:
                    current_streak[truth_id], label_streak[truth_id] = 0, 0
            # Deliberately pass only image pixels and the public session boundary.
            image = Image.open(root / frame["image"]).convert("RGB")
            start = time.perf_counter()
            emitted = tracker.update(detector.detect(image), frame["timestamp"], round_id=sid)
            latencies.append((time.perf_counter() - start) * 1000)
            for event in emitted:
                if event.kind in {"CARD_CONFIRMED", "CARD_REVEALED", "STATE_CORRECTION"}:
                    p = event.payload
                    if p.get("bbox"):
                        matches = [(bbox_iou(p["bbox"], label["bbox"]), label["card_id"])
                                   for label in frame["labels"]]
                        if matches:
                            overlap, truth_id = max(matches)
                            if overlap >= .5:
                                emitted_map[p["card_id"]] = truth_id
        eligible = {cid for cid in truth_last if max_streak[cid] >= stable_frames}
        state = tracker.log.replay()
        matched_counts = Counter(emitted_map[cid] for cid in state.cards if cid in emitted_map)
        missed = len(eligible - set(matched_counts))
        duplicates = sum(max(0, count - 1) for count in matched_counts.values())
        extras = sum(cid not in emitted_map for cid in state.cards)
        expected_ranks = Counter(truth_last[cid]["rank"] for cid in eligible if truth_last[cid]["rank"] is not None)
        # Final label is evaluable only if it had enough stable ground-truth frames.
        truth_evaluable_ids = {cid for cid in eligible if label_streak[cid] >= stable_frames}
        expected_ranks = Counter(truth_last[cid]["rank"] for cid in truth_evaluable_ids
                                 if truth_last[cid]["rank"] is not None)
        actual_evaluable = Counter(card["rank"] for cid, card in state.cards.items()
                                   if emitted_map.get(cid) in truth_evaluable_ids and card.get("rank"))
        drift = sum(abs(expected_ranks[rank] - actual_evaluable[rank]) for rank in RANKS)
        rank_errors = sum(card.get("rank") != truth_last[emitted_map[cid]]["rank"]
                          for cid, card in state.cards.items() if emitted_map.get(cid) in truth_evaluable_ids)
        suit_errors = sum(card.get("suit") != truth_last[emitted_map[cid]]["suit"]
                          for cid, card in state.cards.items() if emitted_map.get(cid) in truth_evaluable_ids)
        reports.append({"session_id": sid, "theme": theme, "frames": len(frames),
                        "eligible_logical_cards": len(eligible), "missed_events": missed,
                        "duplicate_events": duplicates, "unmatched_events": extras,
                        "known_rank_l1_drift": drift, "rank_event_errors": rank_errors,
                        "suit_event_errors": suit_errors,
                        "observed_physical_cards": len(state.cards),
                        "integrity_gate": tracker.state_summary()["gate"]["status"],
                        "state_exact": bool(eligible) and len(truth_evaluable_ids) == len(eligible) and
                                       missed == duplicates == extras == drift == rank_errors == suit_errors == 0})
    evaluable = [r for r in reports if r["eligible_logical_cards"]]
    return {"schema_version": 1, "split": split, "stable_frames": stable_frames,
            "groups": reports, "evaluable_groups": len(evaluable),
            "missed_events": sum(r["missed_events"] for r in reports),
            "duplicate_events": sum(r["duplicate_events"] for r in reports),
            "unmatched_events": sum(r["unmatched_events"] for r in reports),
            "known_rank_l1_drift": sum(r["known_rank_l1_drift"] for r in reports),
            "rank_event_errors": sum(r["rank_event_errors"] for r in reports),
            "suit_event_errors": sum(r["suit_event_errors"] for r in reports),
            "exact_session_fraction": sum(r["state_exact"] for r in evaluable) / len(evaluable) if evaluable else None,
            "pipeline_latency_ms_mean": float(np.mean(latencies)) if latencies else None,
            "pipeline_latency_ms_p95": float(np.percentile(latencies, 95)) if latencies else None,
            "scope": "controlled renderer, separate truth, public session boundary; not external live play"}


def _counting_snapshot(cards: Mapping[str, Mapping[str, Any]], decks: int) -> dict[str, Any]:
    """Observed inventory only; hidden ranks never enter count/composition."""
    from collections import Counter
    known = Counter(card.get("rank") for card in cards.values() if card.get("rank"))
    rank_counts = {rank: known[rank] for rank in RANKS}
    running = sum(count if rank in {"2", "3", "4", "5", "6"} else -count
                  if rank in {"A", "10", "J", "Q", "K"} else 0
                  for rank, count in rank_counts.items())
    remaining = 52 * decks - len(cards)
    pool = [4 * decks] * 9 + [16 * decks]
    for rank, count in rank_counts.items():
        value = 1 if rank == "A" else 10 if rank in {"10", "J", "Q", "K"} else int(rank)
        pool[value - 1] -= count
    return {"known_rank_counts": rank_counts, "physical_observed": len(cards),
            "unknown_rank_observed": sum(card.get("rank") is None for card in cards.values()),
            "physical_remaining": remaining, "running_count": running,
            "true_count": running / (remaining / 52) if remaining > 0 else None,
            "informational_pool": pool}


def _normal_decision_context(cards: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    from .engine import hand_value
    ordered = sorted(cards.values(), key=lambda card: card.get("bbox", [0])[0])
    dealer = [card["rank"] for card in ordered if card.get("zone") == "dealer" and card.get("rank")]
    player = [card["rank"] for card in ordered if str(card.get("zone", "")).startswith("player") and card.get("rank")]
    if len(dealer) != 1 or len(player) < 2 or hand_value(player)[0] >= 21:
        return None
    return {"player": player, "dealer": dealer[0]}


def _summarize_counting_frames(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tc_errors = [row["true_count_error"] for row in rows if row["true_count_error"] is not None]
    decision_frames = [row for row in rows if row["native_decision_opportunity"]]
    native_times = [row["native_state_ms"] for row in rows]
    vision_times = [row["pixel_pipeline_ms"] for row in rows]
    return {"frames": len(rows),
            "running_count_exact_fraction": sum(row["running_count_error"] == 0 for row in rows) / len(rows) if rows else None,
            "running_count_mae": float(np.mean([abs(row["running_count_error"]) for row in rows])) if rows else None,
            "running_count_max_absolute_error": max((abs(row["running_count_error"]) for row in rows), default=None),
            "true_count_evaluable_frames": len(tc_errors),
            "true_count_mae": float(np.mean(np.abs(tc_errors))) if tc_errors else None,
            "true_count_rmse": float(np.sqrt(np.mean(np.square(tc_errors)))) if tc_errors else None,
            "true_count_max_absolute_error": max((abs(value) for value in tc_errors), default=None),
            "known_rank_l1_mean": float(np.mean([row["known_rank_l1"] for row in rows])) if rows else None,
            "state_exact_fraction": sum(row["state_exact"] for row in rows) / len(rows) if rows else None,
            "integrity_allowed_frames": sum(row["integrity_allowed"] for row in rows),
            "integrity_allowed_inexact_frames": sum(row["integrity_allowed"] and not row["state_exact"] for row in rows),
            "native_decision_opportunities": len(decision_frames),
            "normal_decision_allowed_frames": sum(row["normal_decision_allowed"] for row in decision_frames),
            "normal_decision_withheld_frames": sum(not row["normal_decision_allowed"] for row in decision_frames),
            "normal_decision_allowed_fraction": sum(row["normal_decision_allowed"] for row in decision_frames) / len(decision_frames) if decision_frames else None,
            "normal_decision_allowed_inexact_frames": sum(row["normal_decision_allowed"] and not row["state_exact"] for row in decision_frames),
            "native_state_p50_ms": float(np.percentile(native_times, 50)) if rows else None,
            "native_state_p95_ms": float(np.percentile(native_times, 95)) if rows else None,
            "pixel_pipeline_p50_ms": float(np.percentile(vision_times, 50)) if rows else None,
            "pixel_pipeline_p95_ms": float(np.percentile(vision_times, 95)) if rows else None,
            "decode_p95_ms": float(np.percentile([row["decode_ms"] for row in rows], 95)) if rows else None,
            "detection_p95_ms": float(np.percentile([row["detection_ms"] for row in rows], 95)) if rows else None,
            "tracking_and_replay_p95_ms": float(np.percentile([row["tracking_and_replay_ms"] for row in rows], 95)) if rows else None}


def benchmark_counting_ablation(dataset: str | Path, detector: Any, *, split: str = "test",
                               confirmations: tuple[int, ...] = (1, 3), regret_samples: int = 4,
                               solver_timeout_ms: float = 250, solver_max_nodes: int = 15000) -> dict[str, Any]:
    """Actual held-out pixel tracking versus observable native labels.

    Detector thresholds, data and track association are untouched. Both temporal
    modes receive the same independent detections. Ground truth and solver case
    selection stay in the evaluator; no label/ID is supplied to either tracker.
    The generated fixture is one round per group, with a public boundary.
    """
    from collections import Counter, defaultdict
    from .vision import TemporalTracker
    from .engine import Rules
    from .solver import Solver
    if not confirmations or any(not isinstance(n, int) or n < 1 for n in confirmations):
        raise ValueError("positive temporal confirmations required")
    if regret_samples < 0:
        raise ValueError("regret_samples must be nonnegative")
    root = Path(dataset)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_splits(manifest)
    groups = defaultdict(list)
    for record in manifest["records"]:
        if record["split"] == split:
            groups[(record["session_id"], record["theme"])].append(record)
    frame_rows = {n: [] for n in confirmations}
    group_rows = {n: [] for n in confirmations}
    regret_rows = []
    seen_solver_states = set()
    # These are explicit evaluation rules, not inferred rules or hidden truth.
    evaluation_rules = Rules(decks=1, dealer_peek=False, max_split_hands=2, resplit=False, surrender="late")
    attempted_solver_states = 0
    for (sid, theme), frames in sorted(groups.items()):
        trackers = {n: TemporalTracker(stable_frames=n, minimum_score=.90) for n in confirmations}
        for tracker in trackers.values():
            tracker.new_shoe(1, timestamp=0, shoe_id=f"{sid}-{theme}")
        associations = {n: {} for n in confirmations}
        native_history = {}
        for record in sorted(frames, key=lambda frame: frame["frame"]):
            native_started = time.perf_counter()
            for label in record["labels"]:
                native_history[label["card_id"]] = dict(label)
            native = _counting_snapshot(native_history, 1)
            native_context = _normal_decision_context(native_history)
            native_ms = 1000 * (time.perf_counter() - native_started)
            image_path = root / record["image"]
            decode_started = time.perf_counter()
            with Image.open(image_path) as source:
                pixels = source.convert("RGB")
            decode_ms = 1000 * (time.perf_counter() - decode_started)
            detector_started = time.perf_counter()
            detections = detector.detect(pixels)
            detection_ms = 1000 * (time.perf_counter() - detector_started)
            contexts = {}
            for n, tracker in trackers.items():
                track_started = time.perf_counter()
                emitted = tracker.update(detections, record["timestamp"], round_id=sid)
                state = tracker.log.replay()
                summary = tracker.state_summary()
                predicted = _counting_snapshot(state.cards, 1)
                tracking_ms = 1000 * (time.perf_counter() - track_started)
                for event in emitted:
                    if event.kind not in {"CARD_CONFIRMED", "CARD_REVEALED", "STATE_CORRECTION"}:
                        continue
                    payload = event.payload
                    if not payload.get("bbox"):
                        continue
                    possible = [(bbox_iou(payload["bbox"], label["bbox"]), label["card_id"]) for label in record["labels"]]
                    if possible:
                        overlap, truth_id = max(possible)
                        if overlap >= .5:
                            associations[n][payload["card_id"]] = truth_id
                l1 = sum(abs(predicted["known_rank_counts"][rank] - native["known_rank_counts"][rank]) for rank in RANKS)
                exact = l1 == 0 and predicted["physical_observed"] == native["physical_observed"] and predicted["unknown_rank_observed"] == native["unknown_rank_observed"]
                predicted_context = _normal_decision_context(state.cards)
                allowed = bool(summary["gate"]["solver_allowed"])
                normal_allowed = allowed and predicted_context is not None
                contexts[n] = (predicted_context, predicted, normal_allowed)
                row = {"session_id": sid, "theme": theme, "frame": record["frame"], "timestamp": record["timestamp"],
                       "image": record["image"], "confirmation_frames": n,
                       "native": native, "predicted": predicted, "running_count_error": predicted["running_count"] - native["running_count"],
                       "true_count_error": predicted["true_count"] - native["true_count"] if predicted["true_count"] is not None and native["true_count"] is not None else None,
                       "known_rank_l1": l1, "state_exact": exact,
                       "gate_status": summary["gate"]["status"], "gate_reasons": summary["gate"]["reasons"],
                       "integrity_allowed": allowed, "native_decision_opportunity": native_context is not None,
                       "normal_decision_allowed": normal_allowed, "native_state_ms": native_ms,
                       "decode_ms": decode_ms, "detection_ms": detection_ms, "tracking_and_replay_ms": tracking_ms,
                       "pixel_pipeline_ms": decode_ms + detection_ms + tracking_ms,
                       "state": state.to_dict()}
                frame_rows[n].append(row)
            if native_context is not None and attempted_solver_states < regret_samples:
                state_key = (tuple(native_context["player"]), native_context["dealer"], tuple(native["informational_pool"]))
                if state_key not in seen_solver_states:
                    seen_solver_states.add(state_key)
                    attempted_solver_states += 1
                    reference = Solver(evaluation_rules).analyze(native_context["player"], native_context["dealer"], native["informational_pool"], peek_resolved=False, timeout_ms=solver_timeout_ms, max_nodes=solver_max_nodes)
                    for n in confirmations:
                        context, predicted, allowed = contexts[n]
                        sample = {"session_id": sid, "theme": theme, "frame": record["frame"], "confirmation_frames": n,
                                  "native_context": native_context, "native_analysis": reference, "vision_context": context,
                                  "vision_analysis": None, "status": "withheld" if not allowed else "reference_incomplete",
                                  "ev_regret": None, "action_matches": None}
                        if allowed and reference.get("exact") and reference.get("best_action") is not None:
                            analysis = Solver(evaluation_rules).analyze(context["player"], context["dealer"], predicted["informational_pool"], peek_resolved=False, timeout_ms=solver_timeout_ms, max_nodes=solver_max_nodes)
                            sample["vision_analysis"] = analysis
                            best = analysis.get("best_action")
                            if analysis.get("exact") and best in reference["actions"]:
                                sample.update(status="compared", ev_regret=max(reference["actions"].values()) - reference["actions"][best], action_matches=best == reference["best_action"])
                            else:
                                sample["status"] = "vision_incomplete_or_illegal"
                        regret_rows.append(sample)
        for n, tracker in trackers.items():
            state = tracker.log.replay()
            matched = Counter(associations[n][cid] for cid in state.cards if cid in associations[n])
            group_rows[n].append({"session_id": sid, "theme": theme, "frames": len(frames), "confirmation_frames": n,
                                  "native_logical_cards": len(native_history), "predicted_logical_cards": len(state.cards),
                                  "missed_events": len(set(native_history) - set(matched)),
                                  "duplicate_events": sum(max(0, count - 1) for count in matched.values()),
                                  "unmatched_events": sum(cid not in associations[n] for cid in state.cards),
                                  "final_state_exact": frame_rows[n][-1]["state_exact"], "final_gate_status": tracker.state_summary()["gate"]["status"],
                                  "events": tracker.log.to_dict()})
    modes = {}
    for n in confirmations:
        evaluated = [row for row in regret_rows if row["confirmation_frames"] == n and row["status"] == "compared"]
        mode_samples = [row for row in regret_rows if row["confirmation_frames"] == n]
        modes[str(n)] = {**_summarize_counting_frames(frame_rows[n]), "groups": len(group_rows[n]),
                         "final_exact_groups": sum(row["final_state_exact"] for row in group_rows[n]),
                         "missed_events": sum(row["missed_events"] for row in group_rows[n]),
                         "duplicate_events": sum(row["duplicate_events"] for row in group_rows[n]),
                         "unmatched_events": sum(row["unmatched_events"] for row in group_rows[n]),
                         "regret_requested_unique_states": regret_samples, "regret_attempted_unique_states": attempted_solver_states,
                         "regret_compared_states": len(evaluated),
                         "regret_withheld_states": sum(row["status"] == "withheld" for row in mode_samples),
                         "regret_incomplete_states": sum(row["status"] not in {"compared", "withheld"} for row in mode_samples),
                         "mean_ev_regret": float(np.mean([row["ev_regret"] for row in evaluated])) if evaluated else None,
                         "action_match_fraction": sum(row["action_matches"] for row in evaluated) / len(evaluated) if evaluated else None}
    return {"schema_version": 1, "status": "completed", "split": split,
            "dataset_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "confirmations": list(confirmations), "tracker_minimum_score": .90, "modes": modes,
            "raw_frames": {str(n): frame_rows[n] for n in confirmations},
            "raw_groups": {str(n): group_rows[n] for n in confirmations}, "regret_samples": regret_rows,
            "evaluation_rules": asdict(evaluation_rules),
            "solver_budget": {"timeout_ms": solver_timeout_ms, "max_nodes": solver_max_nodes},
            "scope": "native labels are evaluator only; vision trackers receive pixels-derived detections and public one-round boundary",
            "latency_semantics": "native observable-state bookkeeping versus actual RGB decode + detection + tracker/replay; shared detection measured once per independent frame, no capture pacing or live FPS claim",
            "limitations": ["counts benchmark compares immediate native exposures against temporally confirmed vision, retaining confirmation delays", "one-round synthetic groups include movement, occlusion and reveal; no unseen round/shuffle inference", "normal-decision opportunity is one visible dealer rank and at least two nonterminal player ranks under explicitly fixed evaluation rules", "gate ablation measures eligibility and incorrect allowed states, not a calibrated probability", "null regret means withheld/incomplete, not zero; exact comparison only when both budgeted solver analyses complete", "per-frame snapshots within sessions are correlated; fractions are descriptive, not independent-binomial confidence intervals"]}
