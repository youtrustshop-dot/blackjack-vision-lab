# Vision and state reconstruction

There are two workflows: **continuous live video** for the lab simulation and **offline image/video tools** for research and replay. Their metrics and context contracts differ.

## Live path

Browser display capture supplies a real screen/window/tab `MediaStream`; the automatic observation loop samples it using the video clock. `live.py` consumes only pixels and declared configuration. It reads lab rank/suit glyphs, exposed controls and visible shoe/round/hand/phase text; three-frame temporal tracking builds an immutable observed event log. The count persists across rounds and resets only on a new shoe. Unstable or stale inputs withhold advice.

Four normalized table corners allow an embedded lab table to be rectified. Geometry does not make an unsupported artwork detector universal. See [LIVE_VISION.md](LIVE_VISION.md) for UI steps, probability interpretation, actual tests and remaining limits.

## Offline path

The original renderer creates controlled themes, blur, overlap, scaling and two designs. OpenCV finds card regions and matches lab corner glyphs. Template scores are similarities, not calibrated probabilities. Detection, physical card, logical track and classification identities remain separate. A reveal or move should not count the card twice.

Independent image/video imports keep inventory unknown unless explicitly declared. Four-corner normalization and zone selection preserve geometry provenance. Offline video import treats the clip as one round and supports prefix replay with actual sampled thumbnails; it does not inherit the live context segmenter's multi-round behavior.

Unknown inventory, pending/lost tracks and corrections are explicit. Corrections append events with reasons and preserve original observations. A gate cannot certify never-detected cards. Card/artwork benchmarks, session-separated calibration, count drift and negative photographic results remain inspectable in [PERCEPTION_EXPERIMENTS.md](PERCEPTION_EXPERIMENTS.md) and [EXTERNAL_BENCHMARKS.md](EXTERNAL_BENCHMARKS.md).

## Information boundary

The simulator's debug truth requires an explicit debug endpoint and never feeds the live observer. Native session perception is a separate controlled comparison: it receives declared session rules/action context, while card ranks/counts come from pixels. Live APIs reject simulator session IDs. No rendered frame encodes hidden card ranks, physical IDs or future shoe order.

A known deck count is declared configuration, not an image certification. Inferred deck posteriors remain distributions and cannot silently open the finite-inventory solver gate. Live mid-shoe counting cannot recover earlier unobserved removals.

Retained historical implementation details: [original vision document](history/v0.1-VISION.md). Current API contracts are in [API.md](API.md).
