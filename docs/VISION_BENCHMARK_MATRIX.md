# Vision benchmark: preserved first increment and learning follow-up

Latest executed gate: [INDEPENDENT_READER_DECISION.md](INDEPENDENT_READER_DECISION.md),
VISION-014. A new original validation family has 350/350 correct sampled ranks
but only 2/5 timely usable R1 opportunities. Development/validation are separate
physical sessions; six difficulty variants per session are paired renderings.
The final holdout is sealed. API candidates have no invented latency or accuracy:
credential choice/account access remains unresolved, with actual cost zero.
The compact native advisor is verified separately in a portable candidate;
installed 1.1.1, production reader and historical VISION-013 evidence are preserved.

The first-increment results below are historical. The current bounded presence,
learning, usable-state and own-session comparison is in
[VISION_LEARNING_CHECK.md](VISION_LEARNING_CHECK.md), with sanitized executed
receipts in [summary.json](../validation/results/vision-learning-check/summary.json).
No checkpoint was promoted and no desktop release was replaced.

The next increment is [PROVIDER_SESSION_READINESS.md](PROVIDER_SESSION_READINESS.md):
classified causes of all 29 learned-adapter extras, observable/ambiguous boundary
contracts, confirmation counters and an original-video runner. Its
[session protocol](PROVIDER_SESSION_PROTOCOL.md) has **zero executed provider
sessions**; this is not a replacement for the preserved 1/3 still result.

This candidate extends commit `20f0fc0aa1ae862ad0ddd20dea2b5d8128a63b1c`.
The frozen installed/public desktop reference remains **1.1.1** at
`4f074efd53066a95d64ca1ed53de03479a8adcba`. This change contains no replacement
desktop release and does not merge PR #1. Its historical 97/97 results are
stabilized count endpoints of synthetic sequences, not independent sessions.

## What failed and what was measured

Three private digital screenshots contain nine visible rank observations:
Freegames desktop and a smaller clipped preview of **the same frame**, plus
BrainPlay. There are two visual families and two distinct moments, not three
independent sessions. Four unique monitor photos are additional diagnostic
inputs, excluded from the digital aggregate. Private pixels, paths, diagnostic
bundles and per-case reports stay in ignored `artifacts/vision-research`.

| Historical profile | Correct zone/ranks | Missed | Suit outcomes | Localized objects | Offline p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current automatic baseline | 3/9 | 6 | 3 unknown, 6 missed | 3/10 | 1680 ms |
| Baseline, native table ROI | 3/9 | 6 | 3 unknown, 6 missed | 3/10 | 1622 ms |
| Explicit calibrated corner OCR v1 | 9/9 | 0 | 4 correct, 5 unknown | 9/10 | 275 ms |
| YOLO26n rank-corner pilot | 0/9 | 9 | Not supported | 0/10 | 190 ms |

The tenth object is a visible blue card back, missed by every historical profile.
The follow-up adds a bounded blue-back rule and an explicit regression; it does
not establish arbitrary-back support. The rank-only pilot returns `suit=None`:
there is no suit classifier to score at 0/9.
Localization uses manually approximated rectangles, role matching and IoU >= .30;
these are development diagnostics, **not detection AP or a generalization test**.
Rank inventory matching alone can hide wrong object assignments, so geometric
matching and missed objects are reported separately. Unknown suits remain unknown.
No wrong extra zone/ranks occurred in this tiny digital sample; that is not a
zero-error guarantee. Monitor photos still produce misses and wrong candidates.

Each timing has one excluded model/runtime warm-up, then three repeats per
case/profile. Glyph OCR memoization is cleared before each repeat. These are nine
offline samples per profile, not capture-to-display latency, throughput or a
latency service guarantee. CPU training had finished; the unrelated Clef runtime
remained idle. The complete timing protocol/hardware and aggregates are in
[VISION_EXPERIMENTS.json](VISION_EXPERIMENTS.json).

The baseline requires a sufficiently large green surface with aspect ratio
between 1.1 and 4 and particular card/role geometry. BrainPlay's upright layout
violates that contract. Native crop alone does not fix it. Covered card bodies and
weak red strokes can remove K before OCR. The alternate profile finds multiple
exposed corners on one light surface, includes red ink and keeps exact native
pixels in explicitly selected roles. It also proposes ornamental/back glyphs;
these unresolved candidates keep the integrity gate closed. It is a **research
profile**, never a silently promoted reliable count/advisor.

## The experiment funnel is in the app

**Tools & programs → Vision experiment funnel** reads the versioned JSON matrix.
It reports runtime content fingerprint, detector version, frozen reference,
candidate publication status, per-stage status and actual results. Package
version alone does not identify changed source. A frozen source fingerprint is
available without Git.

Stages include acquisition, ROI, localization, rank, suit, rotation/overlap,
tracking, temporal confirmation, context, integrity, display and independent
verification. Statuses distinguish proposed, available, executed, not executable,
rejected and promoted. RT-DETR, learned rank/suit corners, OBB/segmentation,
ByteTrack and BoT-SORT are alternatives, not measured winners. Clef is available
as an optional independent verifier; it was not measured in this first comparison.

## Native calibration and private evidence

In Live vision select **Calibrated corners · research**, drag Table, Dealer cards
and Player cards; optional Controls are diagnostic. Pixel previews show exactly
the selected regions (scaled only for display). Applying the layout uploads the
native useful table crop, capped at five megapixels, with explicit scale metadata.
The default automatic profile remains available. Letterbox bands do not map to
source pixels; overlay boxes map back out of the uploaded crop.

A change in source dimensions, selected crop or uploaded dimensions invalidates
native calibration and requires restart. Same-size scrolling/translation is not
automatically detected: recalibrate after moving content. Missing corners cannot
be recovered by enlarging pixels. Phase is unknown unless Player turn is manually
confirmed. Totals never manufacture unseen cards. Backs, arbitrary rotation,
split-hand selection and complete shoe inventory are not certified by this profile.
RC/TC remain unavailable even if a fresh shoe is declared.

**Save private vision diagnostic** explicitly requests the next processed
observation. Its local ZIP includes exact uploaded bytes/SHA, received pixels,
normalization, native regions, exact OCR/retry crops where instrumented,
raw/rejected candidates, thresholds, tracker/events, gate and source/state data.
It is not written/uploaded automatically. Current-pixel reads, manual turn
confirmation and unknowns have explicit provenance.

## Ultralytics pilot: safety and reproducibility

Audited official PyPI wheel `ultralytics==8.4.7`, SHA256
`7438696c981cf58d17250b0e4c7e29886bda9cc3e91ffbbf9544c622f65da91c`.
ZIP inspected for unsafe paths/native executables/.pth; reviewed import/settings
and tracking script. No safety guarantee is inferred from a static review.

Research-only venv, official CPU torch 2.9.1 and torchvision 0.24.1. It does not
change the app environment or stop Clef. The pilot prewrites opt-out settings,
disables HUB/integrations, blocks socket connections before import and uses
`yolo26n.yaml` with random weights: no third-party checkpoint or private image
upload. Generic COCO's 80 classes are not the 52 playing cards.

128 own synthetic train images + 32 validation images, six annotated upper rank
corners each, thirteen rank classes, fixed seeds, eight CPU epochs (~228 s).
Synthetic validation mAP50 = 0; private digital rank recall = 0 at the predeclared
confidence threshold .50. **Reject this checkpoint**. This insufficient scratch
pilot does not reject the architecture. A serious next trial needs diverse,
licensed annotated corners/suits/backs, learning checks and a declared training
budget. It must not tune against these consumed final-looking development cases.

Ultralytics code is AGPL-3.0 / Enterprise. Research isolation and ONNX conversion
do not remove license obligations. No Ultralytics dependency or weights are bundled
in the application/release. Any distribution requiring different conditions,
purchase or paid/cloud/private uploads needs explicit cost/condition approval.
Official references:
[model](https://docs.ultralytics.com/models/yolo26/),
[detection tasks](https://docs.ultralytics.com/tasks/detect/),
[licensing](https://www.ultralytics.com/license).

After auditing/installing into the isolated environment:
```powershell
# Generates a fresh, non-overwritten own dataset. Offline once dependencies exist.
artifacts/vision-research/venv/Scripts/python.exe validation/tools/yolo_corner_pilot.py --root artifacts/vision-research/new-pilot --epochs 8
# The private manifest is local and intentionally not distributed.
artifacts/vision-research/venv/Scripts/python.exe validation/tools/vision_comparison.py artifacts/vision-research/private-cases.json --checkpoint artifacts/vision-research/yolo-pilot/runs/rank-corners/weights/best.pt --output artifacts/vision-research/comparison.json
.venv/Scripts/python.exe -m pytest -q
cd ui
npm test
npm run build
```

## Next acceptance protocol (before new validation)

Freeze manifests, hashes, session groups and graphic-engine families for train,
validation and a new sealed final set. Near-identical frames/assets stay in one
partition. The private screenshots in this increment are **development/regressions
only**; historical final sets remain consumed. Acquisition gaps are reported,
not filled with synthetic video labelled real. Provider access/rights and local
consent determine permissible data collection.

Proposed gates for a bounded supported profile, to freeze before new sessions:
- At least 10 independent full sessions and 10,000 visible card exposures across
  multiple source scales; independent unseen-family results reported separately.
- Rank recall and precision >=99.5% with misses included; suit metrics separate;
  no advertised support for untested occlusion/rotation/scale buckets.
- No falsely confident advice in the evaluated sessions; report an upper confidence
  bound rather than call the risk zero. Safe abstention coverage and recovery time
  must be stated (target >=95% timely decisions on supported readable states).
- No duplicate/missed exposure, unexplained ID switch or false round boundary in
  those count-acceptance sessions; verify **per-rank inventory and every endpoint**,
  not final RC alone. Unknown hidden exposures prevent certified RC/TC.
- Capture-to-display p95 <=750 ms and recovery <=2 s on declared hardware/source,
  measured with shared capture/display timestamps; CPU/RAM/GPU use included.
- Same detection sequences for tracker comparisons, then full end-to-end replay.
  Reveal, split, moving equal cards, identical new rounds and lost/recovered tracks
  retain separate track IDs versus physical-card-instance IDs.

These gates are targets, not achieved results. Evidence can reject a candidate;
it must never remove hard cases from the denominator. Prior champion stays
available for rollback. Poker Phase 0 remains intact; new poker strategic features
are deferred while common vision is evaluated.
