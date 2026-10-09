# Vision learning and card-presence follow-up

This source candidate extends `620e6a0dd7f929a116645c53181b4df360b8edbd`
(external-advisor branch). The installed/published **1.1.1** remains frozen at
`4f074efd53066a95d64ca1ed53de03479a8adcba`. No merge, replacement binary, new
Poker strategy or production model promotion is included. Detector:
`calibrated-corners-2-presence`.

## What changed in the running-source path

Card evidence now distinguishes readable rank, covered card and unreadable
face-up card. Empty role regions report **none observed**, which is not proof
that no physical card exists. Unknown rank no longer turns a face-up state
correction into a card back. Unknown player cards and light card surfaces
touching calibrated role edges block advice even when two other ranks are read.

The blue-back regression uses current pixels, a bright border, texture and
bounded upright geometry inside a declared role region. A broader red/blue
variant was rejected: face artwork/chips yielded six extra objects and only
8/9 ranks. Those failed receipts remain preserved. The retained blue-only rule
does not support every back, rotated card or tiny card. Small dark artifacts
at rounded white boundaries are recorded separately from rejected interior
glyphs. Current rank/suit evidence appears in the advisor's advanced details.

Calibration still requires manual regions and player-turn confirmation. A
clipped-card regression with unchanged source dimensions now blocks advice
and asks for recalibration. The same-size translation probe permits a 60-pixel
move that remains inside the zones, and blocks a 480-pixel move outside them.
This does not detect every scroll, layout change or same-sized replacement.

## Diagnose learning before claiming generalization

The historical eight-epoch scratch pilot is retained. An audit checked all 160
own synthetic images, 960 labels, hashes, class indices, bounds and nonempty
ink crops. The 16-image contact sheet was inspected: 96 upper-corner glyphs
cover all thirteen ranks. Lower decorative ranks remain hard negatives.
These images are deliberately reused for **memorization**, not independent
validation. The original 128/32 split and final holdout were not modified.

Configuration: Ultralytics 8.4.7, torch 2.9.1 CPU, four torch threads, image size
416, batch 8, deterministic seed 483107, AdamW lr .002, no augmentation.
The preregistered operating gate uses confidence .50 and matching IoU .50:
90% localization, 80% correct class including misses, at most 10% extra boxes.
For the one-class localizer, class correctness means geometry, not card rank.

| Initialization / task | Epochs | Wall seconds | Memorized-train mAP50 | Localized at fixed .50 |
| --- | ---: | ---: | ---: | ---: |
| Scratch / 13 ranks | 60 | 314.6 | 0.000 | 0/96 |
| Official pretrained / 13 ranks | 60 | 323.3 | 0.232 | 0/96 |
| Official pretrained / one corner class | 60 | 325.6 | 0.930 | 0/96 |
| Own localizer refinement | +30 | 135.5 | 0.930 | 0/96 |

The three 60-epoch budgets were 360 seconds each; refinement was bounded at
180 seconds, checked at epoch boundaries. More epochs retained the same best
metrics. No fixed .50 gate passed. mAP averages score thresholds and does not
imply a usable result at .50. Raw predictions expose this discrepancy.

A separate **development-only** score/NMS diagnostic then tested the fixed grid
`.01/.025/.05/.10/.15/.20/.30/.40/.50`, geometric IoU .50 and NMS .50. Its rule
selects the largest threshold with both precision and recall >=90% on those
memorized examples. At **.025: 92/96 localized, four missed, one extra**;
precision .989, recall .958. At .01 there were 104 extras; at .05 eight misses.
This receipt was frozen before the private-ROI comparison. The failed .50
result remains unchanged. This selection permits a development experiment,
not promotion or a generalization claim.

The external adapter composes learned corner localization with the same OCR,
silhouette suits and bounded back rule. Neither the one-class model nor the
historical rank pilot implements a learned suit classifier. PIL RGB input also
fixes the old adapter's RGB-array/BGR mismatch; that bug does not explain the
historical zero synthetic-file validation result.

## Same input and calibration: measured outcome

Three consumed development stills represent **two moments in two graphic
families**; one is a clipped preview of the other. There are nine face-rank
observations and one blue back, not independent sessions. Monitor photos remain
diagnostic cases outside this aggregate. Challengers receive the same manual
dealer/player ROIs and turn confirmation. Automatic baselines retain their
original geometry contract; their comparison also includes a native table crop.

| Profile | Matched correct ranks | Suits correct/wrong/unknown/missed | Objects missed/extra | Correctly usable stills | Offline p95 |
| --- | ---: | --- | --- | ---: | ---: |
| Automatic baseline | 3/9 | 0/0/3/6 | 7/0 | 0/3 | 1967 ms |
| Automatic + native table ROI | 3/9 | 0/0/3/6 | 7/0 | 0/3 | 1840 ms |
| Calibrated OCR + presence v2 | 9/9 | 4/0/5/0 | 0/0 | 1/3 | 257 ms |
| Historical rank-only YOLO | 0/9 | Not supported | 10/0 | 0/3 | 181 ms |
| Learned corners + OCR | 5/9 | 1/0/4/4 | 4/29 | 0/3 | 1043 ms |

The calibrated path now finds all ten annotated objects, including the blue
back, but Freegames artwork still creates unresolved glyphs and closes the
integrity gate. BrainPlay is usable in this bounded still probe. Good rank
inventory is not enough: the learned adapter's inventory intersection is 8/9,
but only 5/9 match the approximated object geometry. Do not advertise 8/9 as
full-object accuracy. Approximate card bodies inferred from corner dimensions
make full-card IoU .30 a diagnostic proxy, **not corner detection AP**.

Timing uses one excluded warm-up and three cache-cleared repeats per still,
AMD64 Windows CPU, with training/build workloads completed and Clef idle.
Nine timing samples per profile are not throughput or capture-to-display p95.
Usability feeds the existing state gates five repeated still observations with
manual turn: its simulated first-advice clock is not measured video latency.
No challenger was promoted; the learned adapter performs worse on this sample.

## Fresh own-renderer sequences: perception versus inventory

Three deterministic development sessions use seeds 4100401/4100402/4100403,
two decks, four rounds each, overlapping cards, visible backs and one unchanged
720x500 calibration. Native truth remains outside the pixel detector; manual
turn is simulated from the engine phase. This is **own synthetic rendering**,
not new recordings from providers or an unseen graphical family.

With six observations per native state: 29 states, all **117 repeated face
observations** read correctly, 53 suits correct and 64 unknown, none wrong;
15/15 player-decision states have advice with exact observed state. These are
not 117 unique physical cards. No false actionable state occurred in this
small assisted sample; no zero-risk guarantee follows.

| Seed | Final inventory L1 error | Observed RC error | Count certified |
| --- | ---: | ---: | --- |
| 4100401 | 0 | 0 | No |
| 4100402 | 4 | +3 | No |
| 4100403 | 4 | -2 | No |

The receipts isolate the remaining four-exposure losses. Seed 4100402's first
round settles immediately: all four face ranks are detected, but visible phase
is unknown, no player turn was confirmed, `seen_round=false`, and no events
are committed. Seed 4100403's fourth round likewise settles without an observed
phase/boundary: it remains round 3 and emits corrections/lost-track events
instead of four new physical exposures. The renderer supplies no controls or
settlement label, and this profile cannot establish that boundary from the
declared input. Do not fix this by inventing a phase or silently forcing IDs.

A separate three-observations-per-state sensitivity run lost inventory
**17/18/19** while current ranks stayed correct; its RC errors were 0/+5/-5.
The zero RC can conceal 17 inventory errors. Six observations reduced losses
but is not an acceptance result or final-test tuning. Complete shoe counts
remain disabled for the research profile.

## Provenance, isolation and reproduction

Official pretrained asset:
[Ultralytics v8.4.0 assets](https://github.com/ultralytics/assets/releases/tag/v8.4.0),
`yolo26n.pt`, 5,544,453 bytes, SHA256
`9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
The digest matches the GitHub asset metadata. Archive paths and pickle globals
were inspected before loading; pretrained/refinement initialization uses
`torch.load(weights_only=True)` with explicitly reviewed globals and fails on
unknown globals. Static checks are not proof of absolute safety. Research
adapters read only our local training outputs. No private pixels were uploaded.

The isolated research venv is separate from the app, uses audited dependencies,
disables telemetry/integrations and blocks networking during experiments.
The asset is generic COCO pretrained initialization, not a 52-card reader.
Ultralytics AGPL/Enterprise conditions still apply; no weights/dependency are
distributed in the app. Paid services, purchases and changed distribution
conditions remain subject to explicit cost/condition approval.

```powershell
# After the documented isolated environment and local official asset audit:
artifacts/vision-research/venv/Scripts/python.exe validation/tools/yolo_learning_check.py --source artifacts/vision-research/yolo-pilot/data --root artifacts/vision-research/new-corner-check --initialization pretrained --task corner --pretrained artifacts/vision-research/yolo26n-official.pt --epochs 60 --budget-seconds 360
artifacts/vision-research/venv/Scripts/python.exe validation/tools/learning_operating_points.py artifacts/vision-research/new-corner-check/learning.json --output artifacts/vision-research/new-corner-check/operating-points.json
# Local private manifest intentionally not distributed; use matching checkpoint/receipt.
artifacts/vision-research/venv/Scripts/python.exe validation/tools/vision_comparison.py artifacts/vision-research/private-cases.json --localizer-checkpoint artifacts/vision-research/new-corner-check/runs/pretrained/weights/best.pt --operating-points artifacts/vision-research/new-corner-check/operating-points.json --output artifacts/vision-research/new-comparison.json
.venv/Scripts/python.exe validation/tools/calibration_sessions.py --output artifacts/vision-research/new-calibration-sessions --stable-observations 6
.venv/Scripts/python.exe -m pytest -q
cd ui
npm test
npm run build
```

Public sanitized receipts contain measured aggregates, manifests/checkpoint
hashes, budgets, counterexamples and the no-promotion decision:
[summary.json](../validation/results/vision-learning-check/summary.json).
The application reads [VISION_EXPERIMENTS.json](VISION_EXPERIMENTS.json),
including historical and current tables. Detailed private cases remain ignored.

Next bounded work needs annotated provider corners and hard negatives with
compatible rights, a measured suit classifier, and new authorized full-session
recordings grouped by engine/graphic family. Count acceptance needs observable
round/settlement evidence, identity and every per-rank endpoint. No final
holdout has been consumed here. Advisor physical multi-monitor/DPI tests and
real sharing while minimized remain unexecuted; HTTP simulator submission is
kept distinct. Use the native candidate's own backend URL, not old `:8767`.

Verification: **431 Python tests + 10 subtests, 46 UI tests, TypeScript/Vite build**
passed. This is source verification, not a newly tested Windows binary.
