"""Publish aggregate local tournament evidence, with no private frame/trace data.

This reads development/validation evaluation only. The final holdout manifest
is checked by hash, never loaded or evaluated. No cloud/network implementation.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from validation.tools.overlap_session import anchors, digest, save, sources

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "validation/results/independent-tournament"


def read_verified_truth(manifest_directory, session):
    """Check actual dev/validation pixel and label bytes before consuming truth."""
    manifest_directory = Path(manifest_directory)
    for field in ("video", "truth"):
        path = manifest_directory / session[field]
        if digest(path) != session[f"{field}_sha256"]:
            raise ValueError(f"Frozen {field} changed: {session['name']}")
    return json.loads((manifest_directory / session["truth"]).read_text(encoding="utf-8"))


def exact_face_state(expected, detections):
    """Derived geometric table correctness with explicit face-up/down semantics.

    Unknown rank is allowed for a present unreadable face-up object, but it
    must not be described as a covered/back card. Empty tables are excluded.
    Geometry matching retains the bounded upright-anchor scope of the run.
    """
    pairs, missed, extra = anchors(expected, detections)

    def correct(card, detected, suit):
        face_down = bool(detected.get("face_down"))
        if card["presence"] == "covered":
            return face_down and detected.get("rank") is None and (not suit or detected.get("suit") is None)
        if card["presence"] == "readable":
            return not face_down and detected.get("rank") == card["rank"] and (not suit or detected.get("suit") == card["suit"])
        if card["presence"] == "unreadable":
            return not face_down and detected.get("rank") is None and (not suit or detected.get("suit") is None)
        return False

    return {"rank_exact": int(bool(expected) and not missed and not extra and all(correct(c,d,False) for c,d in pairs)),
            "suit_exact": int(bool(expected) and not missed and not extra and all(correct(c,d,True) for c,d in pairs)),
            "wrong_back_on_unreadable": sum(c["presence"] == "unreadable" and bool(d.get("face_down")) for c,d in pairs),
            "nonempty": int(bool(expected))}


def publish(artifact_root):
    artifact_root = Path(artifact_root).resolve()
    freeze = json.loads((artifact_root / "freeze.json").read_text(encoding="utf-8"))
    if digest(ROOT / "validation/tools/independent_tournament.py") != freeze["generator_sha256"]:
        raise ValueError("Generator changed after corpus freeze")
    if sources(artifact_root / "baseline-77a036a") != freeze["source_hashes"]:
        raise ValueError("Baseline changed")
    if len({v["seed"] for v in freeze["manifests"].values()}) != 3 or len({v["family"] for v in freeze["manifests"].values()}) != 3:
        raise ValueError("Split seed/family collision")
    for metadata in freeze["manifests"].values():
        if digest(artifact_root / metadata["path"]) != metadata["sha256"]:
            raise ValueError("Manifest changed")
    if (artifact_root / "results/final_holdout").exists():
        raise ValueError("Final holdout has already been opened for evaluation")
    public = {"schema": 1, "experiment": "Independent original synthetic local baseline",
              "baseline_commit": freeze["baseline_commit"], "baseline_archive_sha256": freeze["baseline_archive_sha256"],
              "generator_sha256": freeze["generator_sha256"], "freeze_sha256": digest(artifact_root / "freeze.json"),
              "publication_evaluator": {"version": "derived-face-state-exact-v2", "path": "validation/tools/publish_tournament_baseline.py",
                  "sha256": digest(__file__), "geometric_helper_path": "validation/tools/overlap_session.py",
                  "geometric_helper_sha256": digest(ROOT / "validation/tools/overlap_session.py"),
                  "correction": "Initial run's rank/suit exact metrics accepted unknown-rank unreadable objects even when face_down=True. Derived metrics below recompute explicit face state from the original traces without inference or edits to frozen run results."},
              "partitions": freeze["manifests"], "final_holdout": "sealed_not_evaluated",
              "independent_sessions_evaluated": 2, "distinct_physical_rounds_evaluated": 12,
              "difficulty_renderings_per_session": 6, "paired_renderings_are_not_independent_rounds": True,
              "api_requests": 0, "api_cost": 0,
              "timing_scope": "Offline replay on a contended Windows host: native build and the installed capture backend also ran. This is neither an isolated latency benchmark nor capture-to-display/cloud-request latency.",
              "reader_input_boundary": "Frozen observer receives RGB pixels, source timestamps and declared ROIs only. Truth, scenario, simulator phase/round/IDs and future frames are consumed only by renderer/evaluator.",
              "pipeline_config": {"context_challenger": True, "overlap_challenger": True,
                  "manual_turn": False, "fresh_shoe": True, "samples": 100,
                  "calibration": "declared synthetic table/dealer/player/control rectangles", "sampling_ms": 350},
              "installed_desktop_status": "Unchanged; this is the opt-in research profile from 77a036a, not a measured default desktop release.",
              "selection_limits": ["No reader promotion from this baseline alone.",
                  "One session/seed/family per partition is insufficient for population accuracy or tail latency claims.",
                  "Six difficulty variants share hands within a session. Family font/paper/back varies, but rendering/layout mechanics are shared.",
                  "Rotation matching uses approximate upright left/top anchors; detector precision and ID metrics there remain diagnostic.",
                  "Clipped combines partial source pixels with stale/narrow player ROI; it is not an isolated OCR test.",
                  "Clipped/covered can make player ranks fundamentally unobservable. Correct abstention is not a missed recommendation on a fully observable hand.",
                  "Suit/rank readability is the existing combined glyph-mask convention (85% ink visibility), not an independent human legibility label.",
                  "No orientation accuracy, provider generalization, live stale-response transport, multi-hand split vision or gray-disabled-control test is demonstrated."],
              "private_artifact_root": "artifacts/reader-tournament-r1-20261004",
              "results": []}
    rows = []
    for split in ("development", "validation"):
        result_path = artifact_root / "results" / split / "local.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        manifest_path = artifact_root / freeze["manifests"][split]["path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if result["source_hashes"] != freeze["source_hashes"] or result["original_manifest_sha256"] != digest(manifest_path):
            raise ValueError("Result provenance mismatch")
        for report in result["results"]:
            session = next(s for s in manifest["sessions"] if s["name"] == report["name"])
            truth = read_verified_truth(manifest_path.parent, session)
            trace_path = result_path.parent / f"{report['name']}.trace.json"
            trace_sha256 = digest(trace_path)
            traces = json.loads(trace_path.read_text(encoding="utf-8"))
            derived = {"rank_exact": 0, "suit_exact": 0, "wrong_back_on_unreadable": 0, "nonempty": 0}
            for trace in traces:
                frame = round(trace["timestamp_ms"] * manifest["fps"] / 1000)
                label = truth[frame]
                if abs(label["timestamp_ms"] - trace["timestamp_ms"]) > .01:
                    raise ValueError("Trace/truth source-time mismatch")
                expected = [c for c in label["cards"] if c["bbox"]]
                metrics = exact_face_state(expected, trace["report"]["detections"])
                for key, value in metrics.items(): derived[key] += value
            if len(traces) != report["sampled_frames"] or derived["nonempty"] != report["metrics"]["nonempty_table_observations"]:
                raise ValueError("Derived trace denominator mismatch")
            observable = set()
            for label in truth:
                if label["phase"] != "player": continue
                player = [c for c in label["cards"] if c["zone"] == "player:0" and c["bbox"]]
                dealer = [c for c in label["cards"] if c["zone"] == "dealer" and c["bbox"] and c["presence"] != "covered"]
                if len(player) >= 2 and len(dealer) == 1 and all(c["presence"] == "readable" for c in player + dealer):
                    observable.add((label["round"], tuple(c["card_id"] for c in player)))
            m = report["metrics"]; e = report["extended_metrics"]
            item = {"partition": split, "profile": report["profile"], "seed": manifest["seed"], "family": manifest["family"],
                "rounds": report["rounds"], "decoded_frames": report["decoded_frames"], "sampled_frames": report["sampled_frames"],
                "source_player_opportunities": report["opportunities"], "observable_rank_only_opportunities": len(observable),
                "r1_timely": {"correct": report["r1_timely"], "source_denominator": report["opportunities"], "observable_denominator": len(observable)},
                "rank_exact_table_timely": {"correct": report["table_timely"], "source_denominator": report["opportunities"]},
                "rank_exact_nonempty_frames": {"correct": m.get("complete_nonempty_visible_table", 0), "denominator": m["nonempty_table_observations"]},
                "suit_exact_nonempty_frames": {"correct": e.get("complete_suit_visible_table", 0), "denominator": m["nonempty_table_observations"]},
                "inherited_exact_metric_status": "Retained original frozen run metrics; use the derived face-state metrics for corrected correctness.",
                "derived_face_state_exact_nonempty_frames": {
                    "rank": {"correct": derived["rank_exact"], "denominator": derived["nonempty"]},
                    "suit": {"correct": derived["suit_exact"], "denominator": derived["nonempty"]},
                    "wrong_back_on_unreadable": derived["wrong_back_on_unreadable"],
                    "rank_delta_from_inherited": derived["rank_exact"] - m.get("complete_nonempty_visible_table", 0),
                    "suit_delta_from_inherited": derived["suit_exact"] - e.get("complete_suit_visible_table", 0)},
                "ranks": {"correct": m.get("rank_correct", 0), "wrong": m.get("rank_wrong", 0), "unknown": m.get("rank_unknown", 0), "missed": m.get("rank_missed", 0), "denominator": e["expected_readable"]},
                "suits": {"correct": m.get("suit_correct", 0), "wrong": m.get("suit_wrong", 0), "unknown": m.get("suit_unknown", 0), "missed": m.get("rank_missed", 0), "denominator": e["expected_readable"]},
                "presence": {"expected": e["expected_objects"], "missed": m.get("missing_objects", 0), "extra": m.get("extra_objects", 0),
                             "unreadable_expected": e["expected_unreadable"], "unreadable_matched": e.get("unreadable_presence_matched", 0), "unreadable_as_absent": e.get("unreadable_as_absent", 0)},
                "backs": {"correct": m.get("correct_backs", 0), "wrong": m.get("wrong_back_state", 0), "missed": m.get("missing_backs", 0), "denominator": m.get("expected_backs", 0)},
                "phase": {"correct": e["phase_correct"], "unknown": e["phase_unknown"], "wrong_nonunknown": e["phase_wrong_nonunknown"], "denominator": e["sampled_frames"]},
                "false_accepted_current_state": e.get("false_accepted_current_state", 0), "wrong_or_stale_basic_advice": m.get("wrong_or_stale_basic_advice", 0),
                "safe_rank_only_action_samples": e["rank_only_safe_action_samples"], "observable_player_samples": e["sufficiently_readable_player_samples"],
                "exposures": report["exposures"], "inventory_final_l1": report["inventory_final_l1"], "inventory_final_drift": report["inventory_final_drift"],
                "inventory_interim_max_l1": report["inventory_interim_max_l1"], "observed_rc_max_abs_error": report["observed_rc_max_abs_error"],
                "certified_count_samples": m.get("certified_count_observations", 0), "confirmation_delay_ms": report["confirmation_delay_ms"],
                "first_qualified_r1_delay_ms": report["first_basic_delay_ms"], "observer_internal_processing_ms": report["observer_internal_processing_ms"],
                "result_sha256": digest(result_path),
                "result_artifact": f"artifacts/reader-tournament-r1-20261004/results/{split}/local.json",
                "result_hash_scope": "One aggregate result JSON per split, shared by its six profile rows.",
                "trace_sha256": trace_sha256,
                "trace_artifact": f"artifacts/reader-tournament-r1-20261004/results/{split}/{report['name']}.trace.json",
                "input_video_sha256": session["video_sha256"], "input_truth_sha256": session["truth_sha256"]}
            if report["profile"] == "clipped":
                item["failure_classification"] = "partial source pixels + stale/narrow player ROI; card localization/OCR effects are confounded"
                item["same_input_cloud_contract"] = "Use the same declared card ROI availability. A full-table cloud reader that uses out-of-ROI cards has different geometric assistance and must be labeled separately."
            if report["profile"] == "covered": item["failure_classification"] = "popup/overlap/rotation/contrast composite; some player glyphs never observable"
            public["results"].append(item)
            rows.append({"partition": split, "profile": report["profile"], "rank_correct": item["ranks"]["correct"], "rank_denominator": item["ranks"]["denominator"],
                "suit_correct": item["suits"]["correct"], "suit_unknown": item["suits"]["unknown"], "phase_correct": item["phase"]["correct"], "phase_denominator": item["phase"]["denominator"],
                "r1_timely": report["r1_timely"], "source_opportunities": report["opportunities"], "observable_opportunities": len(observable),
                "false_accepted": item["false_accepted_current_state"], "missing_exposures": item["exposures"]["missing"], "duplicate_exposures": item["exposures"]["duplicate"],
                "id_switches": item["exposures"]["id_switches"], "inventory_final_l1": report["inventory_final_l1"],
                "derived_rank_exact_frames": derived["rank_exact"], "derived_suit_exact_frames": derived["suit_exact"],
                "derived_nonempty_frames": derived["nonempty"], "wrong_back_on_unreadable": derived["wrong_back_on_unreadable"],
                "offline_p50_ms": item["observer_internal_processing_ms"]["p50"], "offline_p95_ms": item["observer_internal_processing_ms"]["p95"], "offline_max_ms": item["observer_internal_processing_ms"]["max"]})
    public["aggregate_paired_observations"] = {
        "sampled_frames": sum(r["sampled_frames"] for r in public["results"]),
        "rank_exact_nonempty_frames": {"correct": sum(r["rank_exact_nonempty_frames"]["correct"] for r in public["results"]),
                                      "denominator": sum(r["rank_exact_nonempty_frames"]["denominator"] for r in public["results"])},
        "suit_exact_nonempty_frames": {"correct": sum(r["suit_exact_nonempty_frames"]["correct"] for r in public["results"]),
                                      "denominator": sum(r["suit_exact_nonempty_frames"]["denominator"] for r in public["results"])},
        "r1_timely": {"correct": sum(r["r1_timely"]["correct"] for r in public["results"]),
                      "source_denominator": sum(r["source_player_opportunities"] for r in public["results"]),
                      "observable_denominator": sum(r["observable_rank_only_opportunities"] for r in public["results"])},
        "false_accepted_current_state": sum(r["false_accepted_current_state"] for r in public["results"]),
        "certified_count_samples": sum(r["certified_count_samples"] for r in public["results"]),
        "derived_face_state_exact_nonempty_frames": {
            "rank": {"correct": sum(r["derived_face_state_exact_nonempty_frames"]["rank"]["correct"] for r in public["results"]),
                     "denominator": sum(r["derived_face_state_exact_nonempty_frames"]["rank"]["denominator"] for r in public["results"])},
            "suit": {"correct": sum(r["derived_face_state_exact_nonempty_frames"]["suit"]["correct"] for r in public["results"]),
                     "denominator": sum(r["derived_face_state_exact_nonempty_frames"]["suit"]["denominator"] for r in public["results"])},
            "wrong_back_on_unreadable": sum(r["derived_face_state_exact_nonempty_frames"]["wrong_back_on_unreadable"] for r in public["results"])},
        "denominator_warning": "Correlated frames and paired renderings. Do not call these independent hands/sessions or infer zero population risk from zero observed false acceptance."}
    if digest(__file__) != public["publication_evaluator"]["sha256"]:
        raise ValueError("Publication evaluator changed during derived scoring")
    PUBLIC.mkdir(parents=True, exist_ok=True)
    save(PUBLIC / "local-baseline.json", public)
    with (PUBLIC / "local-baseline.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"published": str(PUBLIC), "profiles_evaluated": len(rows), "holdout": public["final_holdout"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    publish(parser.parse_args().artifacts)
