"""New original synthetic sessions for the local/VLM reader tournament.

Generation and local evaluation only: no network, API adapter or cloud runner.
The frozen 77a036a observer receives decoded pixels and declared ROIs, never
simulator phase, IDs, ranks, annotations or future frames. Final holdout is
generated and hashed but this tool refuses to evaluate it.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import random
import subprocess
import sys
import time
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from validation.tools.overlap_session import digest, save, sources

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "77a036ac34893fda201959a55f1033d9c106308c"
SPLITS = {
    "development": {"seed": 4100713, "family": "original-lab-amber", "font": "C:/Windows/Fonts/arialbd.ttf", "paper": "#fffdf5", "back": "#2765a5", "stripe": "#b0c8e0", "accent": "#c3aa78"},
    "validation": {"seed": 4100829, "family": "original-lab-slate", "font": "C:/Windows/Fonts/seguisb.ttf", "paper": "#f4f7fb", "back": "#685483", "stripe": "#c3b3d8", "accent": "#bfb398"},
    "final_holdout": {"seed": 4100961, "family": "original-lab-cobalt", "font": "C:/Windows/Fonts/georgiab.ttf", "paper": "#f7f1e8", "back": "#23425b", "stripe": "#a1c6de", "accent": "#dec07d"},
}


def game_rules():
    from bjlab.engine import Rules
    return Rules(decks=8, double_rule="any", max_split_hands=1, surrender="none")


def scenario_timeline(seed):
    """Legal engine games from one physical shoe; renderer alone sees truth.

    Reordering an owned synthetic shoe sets up diagnostic scenarios. Every
    dealt instance retains a distinct real engine card ID. The last two rounds
    have identical faces but distinct physical instances and visible clears.
    """
    from bjlab.simulator import BlackjackSession
    rng = random.Random(seed)
    up = rng.choice(["4", "5", "6"])
    scenarios = [
        {"kind": "immediate_blackjack", "draws": ["A", up, rng.choice(["J", "Q", "K"]), "9"], "actions": []},
        {"kind": "hit_bust", "draws": [rng.choice(["J", "Q", "K"]), "7", "6", "9", "10"], "actions": ["hit"]},
        {"kind": "stand_dealer_draw", "draws": ["10", "6", "8", "5", "6"], "actions": ["stand"]},
        {"kind": "double_dealer_draw", "draws": ["5", "5", "6", "9", rng.choice(["9", "10", "J"]), "3"], "actions": ["double"]},
        {"kind": "identical_first", "draws": ["9", "4", "8", "6", "7"], "actions": ["stand"]},
        {"kind": "identical_new_round", "draws": ["9", "4", "8", "6", "7"], "actions": ["stand"]},
    ]
    game = BlackjackSession(game_rules(), seed=seed, session_id=f"tournament-{seed}", bankroll=100000)
    available = list(game.shoe.cards)
    ordered = []
    same_faces = None
    for spec in scenarios:
        selected = []
        for index, rank in enumerate(spec["draws"]):
            suit = same_faces[index]["suit"] if spec["kind"] == "identical_new_round" else None
            options = [c for c in available if c.rank == rank and (suit is None or c.suit == suit)]
            card = rng.choice(options)
            available.remove(card)
            selected.append(card)
        if spec["kind"] == "identical_first": same_faces = [c.public() for c in selected]
        ordered.extend(selected)
    game.shoe.cards = available + list(reversed(ordered))
    stages = []

    def add(snapshot, phase, duration, spec, cards=None):
        cards = cards if cards is not None else [dict(c, zone=zone) for zone, values in
            [("dealer", snapshot["dealer"]["cards"]), ("player:0", snapshot["hands"][0]["cards"])] for c in values]
        stages.append({"round": game.round_id, "phase": phase, "duration": duration,
                       "cards": cards, "controls": snapshot["available_actions"] if snapshot and phase == "player" else [], "scenario": spec["kind"]})

    for number, spec in enumerate(scenarios):
        add(None, "waiting", 1.0, spec, [])
        snapshot = game.deal()
        player = [dict(c, zone="player:0") for c in snapshot["hands"][0]["cards"]]
        dealer = [dict(c, zone="dealer") for c in snapshot["dealer"]["cards"]]
        dealt = [player[0], dealer[0], player[1], {"id": dealer[1]["id"], "face_down": True, "zone": "dealer"}]
        for index in range(4): add(snapshot, "dealing", .25, spec, dealt[:index+1])
        for action in spec["actions"]:
            if game.phase != "player": raise ValueError("Scenario does not have the intended legal decision")
            add(snapshot, "player", (1.75, 2.0, 2.25)[(number + seed) % 3], spec)
            snapshot = game.action(action)
        if game.phase != "settled": raise ValueError("Scenario did not settle")
        player = [dict(c, zone="player:0") for c in snapshot["hands"][0]["cards"]]
        dealer = [dict(c, zone="dealer") for c in snapshot["dealer"]["cards"]]
        for index in range(1, len(dealer)+1): add(snapshot, "dealer", .5, spec, player+dealer[:index])
        add(snapshot, "settled", 1.5, spec)
        add(None, "waiting", 1.0, spec, [])
    return stages


def original_tile(card, profile, index, family):
    """Original artwork, using locally installed fonts without redistributing them."""
    from bjlab.datasets import card_font
    from validation.tools.stress_lab import SUITS
    image = Image.new("RGBA", (112, 156))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 111, 155), 8, fill=family["paper"], outline="#888888", width=1)
    corner = Image.new("L", image.size)
    if card.get("face_down"):
        draw.rounded_rectangle((5, 5, 106, 150), 5, fill=family["back"])
        for y in range(10, 151, 7): draw.line((7, y, 105, y), fill=family["stripe"], width=1)
    else:
        color = "#c42a38" if card["suit"] in "HD" else "#172028"
        rank_font = card_font(29, family["font"])
        suit_font = card_font(25)
        for target, ink in ((draw, color), (ImageDraw.Draw(corner), 255)):
            target.text((8, 8), card["rank"], font=rank_font, fill=ink, anchor="lt")
            target.text((9, 42), SUITS[card["suit"]], font=suit_font, fill=ink, anchor="lt")
        draw.text((57, 89), SUITS[card["suit"]], font=card_font(48), fill=color, anchor="mm")
        draw.text((102, 143), card["rank"], font=card_font(18, family["font"]), fill=color, anchor="rb")
    angle = profile["angle"] * (1 if index % 2 == 0 else -1)
    if angle:
        image = image.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        corner = corner.rotate(angle, Image.Resampling.NEAREST, expand=True)
    return image, corner


def render(stage, profile, family, tick):
    from bjlab.datasets import card_font
    from validation.tools import stress_lab
    # Reuse the existing visibility-mask renderer. Modification is limited to
    # owned original artwork and displayed legal controls in this generator.
    previous = stress_lab.tile
    stress_lab.tile = lambda card, p, i: original_tile(card, p, i, family)
    try:
        image, truth = stress_lab.render(stage, dict(profile, contrast=1., blur=0), tick)
    finally:
        stress_lab.tile = previous
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 650, 1024, 768), fill=stress_lab.COLORS[profile["theme"]])
    controls = [c.upper() for c in stage["controls"]] if stage["phase"] == "player" else {
        "waiting": ["DEAL"], "settled": ["NEW HAND"], "dealer": ["DEALER TURN"], "dealing": ["DEALING"]}[stage["phase"]]
    for index, label in enumerate(controls):
        x = 160 + index * 220
        draw.rounded_rectangle((x, 664, x+200, 710), 10, fill="#203229", outline=family["accent"])
        draw.text((x+100, 686), label, font=card_font(22), fill="#f0dcad", anchor="mm")
    if profile["contrast"] != 1: image = ImageEnhance.Contrast(image).enhance(profile["contrast"])
    if profile["blur"]: image = image.filter(ImageFilter.GaussianBlur(profile["blur"]))
    return image, truth


def generate(output):
    from validation.tools.stress_lab import PROFILES, LAYOUT, FPS, SIZE
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    archive = output / "baseline-77a036a.zip"
    subprocess.run(["git", "archive", "--format=zip", "--output", str(archive), BASELINE], cwd=ROOT, check=True)
    baseline = output / "baseline-77a036a"
    # This archive is produced above from our own immutable Git commit.
    with zipfile.ZipFile(archive) as saved: saved.extractall(baseline)
    freeze = {"schema": 1, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "baseline_commit": BASELINE, "baseline_archive_sha256": digest(archive),
              "source_hashes": sources(baseline), "generator_sha256": digest(__file__),
              "historical_results_modified": False, "rules": asdict(game_rules()),
              "timely_budget_ms": 1500, "sampling_ms": 350, "api_requests": 0,
              "split_policy": "Session, seed and graphic-family disjoint. Difficulty variants share the same hands within each split; never count paired variants as independent hands.",
              "scope": "Original owned synthetic graphics only; no external provider assets or pixels.",
              "split_not_tested": "Single player ROI and evaluator do not support multi-hand split vision. Split remains engine-only historical evidence.",
              "manifests": {}}
    save(output / "pre_generation_freeze.json", freeze)
    for split, family in SPLITS.items():
        if not Path(family["font"]).is_file(): raise FileNotFoundError(family["font"])
        target = output / split
        target.mkdir()
        stages = scenario_timeline(family["seed"])
        manifest = {"schema": 1, "kind": "own-synthetic-continuous-video", "partition": split,
                    "seed": family["seed"], "family": family["family"], "source_size": list(SIZE), "fps": FPS,
                    "rounds": 6, "rules": asdict(game_rules()), "layout": LAYOUT,
                    "generator_sha256": digest(__file__), "font_sha256": digest(family["font"]),
                    "sessions": [], "provider_assets": False, "api_requests": 0,
                    "holdout_status": "sealed_not_evaluated" if split == "final_holdout" else "available",
                    "scenarios": ["immediate_blackjack", "hit_bust", "stand_dealer_draw", "double_dealer_draw", "identical_first", "identical_new_round"],
                    "limits": ["One session/seed/family per partition; small diagnostic corpus, not a population accuracy estimate.", "Clipped/popup truth can be unreadable; neither reader nor evaluator may invent hidden ranks.", "Shared layout and renderer mechanics mean this tests graphic transfer, not universal independent engines."]}
        for profile, parameters in PROFILES.items():
            name = f"{family['seed']}-{family['family']}-{profile}"
            video = target / f"{name}.webm"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"VP80"), FPS, SIZE)
            if not writer.isOpened(): raise RuntimeError("VP8 unavailable")
            rows = []; frame = 0; seen = {}; cached = None
            try:
                for stage in stages:
                    cached = None
                    for tick in range(round(stage["duration"] * FPS)):
                        if cached is None or stage["phase"] == "dealing": cached = render(stage, parameters, family, tick)
                        image, truth = cached
                        writer.write(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR))
                        for card in truth:
                            if card["presence"] != "absent_from_pixels" and card["physical_rank"]: seen[card["card_id"]] = card["physical_rank"]
                        rows.append({"frame": frame, "timestamp_ms": frame*1000/FPS,
                                     "round": stage["round"], "phase": stage["phase"], "scenario": stage["scenario"],
                                     "controls": stage["controls"], "cards": truth, "seen": dict(seen)})
                        frame += 1
            finally: writer.release()
            truth_path = target / f"{name}.truth.json"
            save(truth_path, rows)
            manifest["sessions"].append({"name": name, "profile": profile, "seed": family["seed"], "group": family["family"],
                "frames": frame, "video": video.name, "video_sha256": digest(video),
                "truth": truth_path.name, "truth_sha256": digest(truth_path), "parameters": parameters})
        save(target / "manifest.json", manifest)
        freeze["manifests"][split] = {"path": f"{split}/manifest.json", "sha256": digest(target / "manifest.json"), "seed": family["seed"], "family": family["family"]}
        print(json.dumps({"split": split, "sessions": len(manifest["sessions"]), "seed": family["seed"], "family": family["family"], "status": manifest["holdout_status"]}), flush=True)
    save(output / "freeze.json", freeze)


def run(output, split, profiles=None):
    from validation.tools.overlap_session import replay, anchors
    output = Path(output).resolve()
    freeze = json.loads((output / "freeze.json").read_text(encoding="utf-8"))
    if split not in ("development", "validation"): raise ValueError("Final holdout is sealed; this runner accepts development/validation only")
    manifest_path = output / freeze["manifests"][split]["path"]
    if digest(manifest_path) != freeze["manifests"][split]["sha256"]: raise ValueError("Frozen manifest changed")
    if sources(output / "baseline-77a036a") != freeze["source_hashes"]: raise ValueError("Frozen baseline changed")
    original = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = output / "results" / split
    results.mkdir(parents=True, exist_ok=True)
    # Existing evaluator accepts 'verification'. Preserve validation provenance
    # explicitly and retain the exact original manifest/hash in the result.
    evaluator_manifest = dict(original, partition="development" if split == "development" else "verification", original_partition=split)
    save(results / "evaluator-manifest.json", evaluator_manifest)
    for session in evaluator_manifest["sessions"]:
        # Paths remain relative to the manifest consumed by the existing runner.
        session["video"] = str((manifest_path.parent / session["video"]).resolve())
        session["truth"] = str((manifest_path.parent / session["truth"]).resolve())
    save(results / "evaluator-manifest.json", evaluator_manifest)
    replay(results / "evaluator-manifest.json", results / "local.json", output / "baseline-77a036a", True, profiles)
    local = json.loads((results / "local.json").read_text(encoding="utf-8"))
    local["partition"] = split
    local["original_manifest_sha256"] = digest(manifest_path)
    local["baseline_commit"] = BASELINE
    local["physical_id_scope"] = "Left/top geometry matching inherited from overlap evaluator; approximate for rotated bodies, not a rigorous rotated-box detector metric."
    for report in local["results"]:
        session = next(s for s in original["sessions"] if s["name"] == report["name"])
        truth = json.loads((manifest_path.parent / session["truth"]).read_text(encoding="utf-8"))
        traces = json.loads((results / f"{report['name']}.trace.json").read_text(encoding="utf-8"))
        totals = Counter(); timings = []; safe_actions = 0; actionable_expected = 0
        first_exact = None; first_rank = None
        lookup = {r["frame"]: r for r in truth}
        for trace in traces:
            label = lookup[round(trace["timestamp_ms"] * original["fps"] / 1000)]
            predicted = trace["report"]
            timings.append(predicted["processing_ms"])
            expected = [c for c in label["cards"] if c["bbox"]]
            pairs, missed, extra = anchors(expected, predicted["detections"])
            totals["expected_objects"] += len(expected)
            totals["expected_readable"] += sum(c["presence"] == "readable" for c in expected)
            totals["expected_unreadable"] += sum(c["presence"] == "unreadable" for c in expected)
            totals["sampled_frames"] += 1
            totals["phase_correct"] += int(predicted["phase"] == label["phase"])
            totals["phase_unknown"] += int(predicted["phase"] == "unknown")
            totals["phase_wrong_nonunknown"] += int(predicted["phase"] != label["phase"] and predicted["phase"] != "unknown")
            totals["orientation_not_measured"] += len(expected)
            exact_suit = not missed and not extra and all(d["face_down"] if c["presence"] == "covered" else
                d["rank"] == c["rank"] and d["suit"] == c["suit"] if c["presence"] == "readable" else d["rank"] is None for c, d in pairs)
            totals["complete_suit_visible_table"] += int(exact_suit and bool(expected))
            totals["unreadable_presence_matched"] += sum(c["presence"] == "unreadable" for c,d in pairs)
            totals["unreadable_as_absent"] += sum(c["presence"] == "unreadable" for c in missed)
            totals["inferred_rank_on_unreadable"] += sum(c["presence"] == "unreadable" and d["rank"] is not None for c,d in pairs)
            if trace["metrics"].get("complete_nonempty_visible_table") and first_rank is None: first_rank = trace["timestamp_ms"]
            if exact_suit and expected and first_exact is None: first_exact = trace["timestamp_ms"]
            player = [c for c in expected if c["zone"] == "player:0"]
            dealer = [c for c in expected if c["zone"] == "dealer" and c["presence"] != "covered"]
            sufficiently_readable = bool(label["phase"] == "player" and len(player) >= 2 and len(dealer) == 1 and
                                         all(c["presence"] == "readable" for c in player + dealer))
            actionable_expected += int(sufficiently_readable)
            if predicted["advice"]:
                safe = bool(sufficiently_readable and predicted["phase"] == "player" and
                            predicted["player"] == [c["rank"] for c in player] and predicted["dealer"] == [c["rank"] for c in dealer])
                safe_actions += int(safe)
                totals["false_accepted_current_state"] += int(not safe)
        report["extended_metrics"] = dict(totals)
        report["extended_metrics"].update({"rank_only_safe_action_samples": safe_actions, "sufficiently_readable_player_samples": actionable_expected})
        report["first_nonempty_rank_exact_source_ms"] = first_rank
        report["first_nonempty_suit_exact_source_ms"] = first_exact
        report["observer_internal_processing_ms"] = {
            "p50": float(np.percentile(timings, 50)), "p95": float(np.percentile(timings, 95)),
            "max": max(timings), "scope": "Observer internal body timer, before response deep-copy. Offline; not capture-to-display or cloud-request latency."}
        report["capability_limits"] = ["No orientation output from current reader; not measured, never scored as correct.", "No actual capture/display or stale-response transport in this offline baseline.", "No multi-hand split vision evaluated.", "Immediate blackjack has no player action opportunity but its exposed cards/round events remain scored."]
    save(results / "local.json", local)
    print(json.dumps({"split": split, "local_result": str(results / "local.json"), "final_holdout": "sealed_not_evaluated"}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "run"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "validation"])
    parser.add_argument("--profiles")
    args = parser.parse_args()
    if args.command == "generate": generate(args.output)
    else: run(args.output, args.split, args.profiles.split(",") if args.profiles else None)


if __name__ == "__main__": main()
