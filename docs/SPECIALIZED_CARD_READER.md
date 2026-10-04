# One specialized local card challenger

This is VISION-015 within the existing reader tournament, following the latest
explicit user authorization. It preserves VISION-014, the installed desktop
1.1.1, the compact advisor candidate, Poker Phase 0 and the sealed historical
final holdout. It does not add another roadmap or change the default reader.

## What was built

The optional research path is:

`pixels → YOLO26n card/index/back + four points → native-pixel index-plane warp → learned rank/suit → existing tracker/context/integrity`

The localizer uses the installed official `yolo26-pose.yaml`, nano scale, with
three classes (`index`, `face_surface`, `back`) and four ordered keypoints.
Compatible backbone tensors come from the verified official YOLO26n COCO
detection checkpoint. The card/keypoint head is newly trained: the downloaded
model was never itself a 52-card reader. The classifier has 13 ranks plus
unknown, and four suits plus unknown. OCR is not used for its rank/suit heads.

The same declared table ROI is cropped at native resolution before letterboxing
for detection; classification warps its native index pixels to 48×72. Source
coordinates are restored explicitly, and excluded-window pixels stay excluded
from the classifier. This normalization cannot restore pixels
cut out of the capture. An estimated index plane is not evidence that hidden
whole-card corners were observed. Proposal scores and softmax margins are
uncalibrated scores, not percentages of correctness.

Index/body reconciliation uses geometry, never equal face labels. Distinct
equal cards remain distinct. Unreadable surfaces and covered backs remain
presence observations rather than disappearing into a missing rank. The
observer still owns visible phase evidence, temporal confirmation and advice.

## Data and predeclared evaluation

10,000 original scenes: 8,000 training, 1,000 calibration, 1,000 verification.
Parent seeds and **rank-font** families are disjoint. The vector-pip artwork,
some pip font and renderer mechanics are shared; this is not three independent
provider engines. Every manifest, source, font and image is hashed. Fonts and
research weights are not redistributed.

Variation covers overlap, rotation, perspective, clipping, popup occlusion,
size, colored paper, blur, fading, noise, JPEG artifacts and printed hard
negatives. Rank/suit visibility is recorded separately. The geometric ≥90%
visible-ink convention is not an independent human legibility annotation.
Tiny, clipped, covered and unreadable bodies remain in the denominator.

Calibration chooses checkpoints/configuration. Verification is unlocked only
after the selected reader, inference sources, evaluator and paired jobs are
frozen. Each paired baseline/challenger job is consumed once in a persistent
ledger **before** its labels are read; interrupted runs remain consumed. A later
version needs fresh verification data. Historical evidence is retained as
regression, not reused as a new independent result.

Random scenes measure presence/rank/suit, not semantic roles or usable legal
advice. Pairing uses global one-to-one observed-box IoU ≥0.15 without rank/suit
labels; it is not precise pose/mask AP. Extra-cause categories are geometric
diagnostic proxies. Legal-video evaluation reuses the unchanged historical
evaluator, whose upright anchor correspondence is approximate on rotation.

Two new physical six-round sessions, with six paired difficulty renderings
each, verify R1/R2 after selection. They are **two sessions**, not twelve
independent sessions. The same declared card/control regions and source-timeline
sampling reach both readers. No per-turn confirmation, hidden phase or card IDs
reach inference. Learned presence replaces the baseline's geometric back
recovery; the common integrity gate remains active.

Promotion requires better same-input state correctness/coverage without added
false-current advice; R2 inventory and event errors are a separate decision.
No synthetic result proves arbitrary-provider vision, live capture latency,
poker strength or economic return.

## Isolated execution and provenance

The run uses RTX 2070 SUPER (8 GiB, sm_75), torch 2.9.1+cu126, torchvision
0.24.1+cu126, Ultralytics 8.4.7, ONNX 1.18.0 and ONNX Runtime 1.30.0.
Its environment lives under a unique D-drive research directory. An initial
C-drive install failed for insufficient space; the failed log was preserved,
then a separate D-drive environment was used. The application environment and
installed binary were not replaced.

The official Ultralytics wheel SHA256 is
`7438696c981cf58d17250b0e4c7e29886bda9cc3e91ffbbf9544c622f65da91c`.
Official checkpoint source:
[Ultralytics assets YOLO26n](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt),
SHA256 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
The existing audited restricted loader uses `weights_only=True`; own checkpoints
contain only state dictionaries. Training blocks sockets and disables telemetry,
uploads and integrations. No third-party card script or card checkpoint was run.

The pose budget was fixed at 2,400 seconds with an epoch-end stop and 40 requested
maximum epochs, not a promise of 40 completed epochs. The classifier has 24
requested epochs. Actual epochs, curves and failures are reported separately.
Export uses the trained one-to-one branch before TopK, avoiding tied-score output
reordering between runtimes. ONNX numeric parity on a random tensor is an export
check, not a card-recognition benchmark.

Ultralytics code/derived models carry AGPL/Enterprise obligations; isolation and
ONNX conversion do not remove them. This is private research, with no checkpoint
bundle, enterprise purchase or new distribution implied.

Reference implementations reviewed for design, without importing their card
assets: [printed-index detection](https://github.com/geaxgx/playing-card-detection)
and [four-corner rectification](https://github.com/EdjeElectronics/OpenCV-Playing-Card-Detector).
The [official pose task](https://docs.ultralytics.com/tasks/pose/) and
[YOLO26 architecture](https://docs.ultralytics.com/models/yolo26/) define the actual
localizer used. ByteTrack, BoT-SORT and SAM remain conditional challengers after
localization/classification residuals are measured.

## Reproduction

Run from the repository root in the separate research environment. Use new output
directories; generation/training refuses to overwrite an earlier run. The app's
normal dependencies do not acquire torch/Ultralytics/SciPy.

```powershell
$research = 'D:/CodexResearch/blackjack-vision-lab/specialized-card-reader-20261004'
$python = "$research/venv/Scripts/python.exe"
& $python -m validation.tools.specialized_card_data --output "$research/data"
& $python -m validation.tools.specialized_card_train --data "$research/data" --output "$research/learning-full" --official artifacts/vision-research/yolo26n-official.pt --epochs 40 --budget-seconds 2400
& $python -m validation.tools.specialized_card_compare perception --data "$research/data" --partition calibration --output "$research/results/current-local-calibration.json"
& $python -m validation.tools.specialized_card_compare perception --data "$research/data" --partition calibration --reader "$research/learning-full/reader.json" --output "$research/results/specialized-calibration.json"
& $python -m validation.tools.specialized_card_sessions --output "$research/new-sessions"
```

Selected-reader and consumption receipts are private local evidence, not API
approvals. Verification commands require that receipt and refuse changed sources,
an altered evaluator or a repeated job. See the published aggregate comparison
for actual executed commands and result hashes. `--export-only` can re-export
the **verified own** tensor checkpoints without retraining; old failures stay
on disk and export alone does not reopen verification.

After calibration, the `select` command binds both new corpora to one reader
without opening their labels. A second selection for the same corpora is refused.

```powershell
$baseline = 'artifacts/reader-tournament-r1-20261004/baseline-77a036a'
& $python -m validation.tools.specialized_card_compare select --data "$research/data" --reader "$research/learning-full/reader.json" --new-sessions "$research/new-sessions" --baseline-root $baseline --calibration-result "$research/results/specialized-calibration.json" --output "$research/selected-reader.json"
& $python -m validation.tools.specialized_card_compare perception --data "$research/data" --partition verification --selection "$research/selected-reader.json" --output "$research/results/current-local-verification.json"
& $python -m validation.tools.specialized_card_compare perception --data "$research/data" --partition verification --reader "$research/learning-full/reader.json" --selection "$research/selected-reader.json" --output "$research/results/specialized-verification.json"
& $python -m validation.tools.specialized_card_compare sessions --data "$research/new-sessions" --partition validation --baseline-root $baseline --selection "$research/selected-reader.json" --output "$research/results/current-local-new-sessions.json"
& $python -m validation.tools.specialized_card_compare sessions --data "$research/new-sessions" --partition validation --reader "$research/learning-full/reader.json" --selection "$research/selected-reader.json" --output "$research/results/specialized-new-sessions.json"
```

These commands run paired jobs once, in separate sequential processes; they are
not a script that may repeatedly tune on verification. Copying a result/receipt
does not constitute new evidence. Remaining API comparisons do not consume the
historical final holdout either.

## API boundary

The aggregate EUR10 synthetic-only allowance is retained. Credentials, billing
balance and recharge state are not inferred from that allowance. The required
existing-key/new-key choice is pending; observed environment credentials are
absent. Requests and costs remain zero, and API accuracy/latency are unmeasured.
No billing configuration or payment action was changed. The local challenger
continues independently of that prerequisite.

## Executed comparison

Results are added here and to `VISION_EXPERIMENTS.json` only after the bounded
training and frozen paired evaluations complete. An earlier 96-scene execution
smoke and its repaired exports are retained separately; they are not the serious
model's accuracy evidence.
