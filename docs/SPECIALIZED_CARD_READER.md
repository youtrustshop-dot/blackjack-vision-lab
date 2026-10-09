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
An index and its body may straddle a declared ROI boundary: reconciliation does
not duplicate the object merely because their centers have different zone labels.
The emitted role uses the index center when available, otherwise the surface
center; this is explicit geometric attribution, not learned universal role reading.

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
an altered evaluator or a repeated job. Commands below reproduce the paired
execution recipe; the published aggregate comparison records result hashes.
`--export-only` can re-export
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

Source frozen for verification: `94638a3`. Published aggregates:
[comparison JSON](../validation/results/specialized-card-reader/comparison.json)
and [per-session CSV](../validation/results/specialized-card-reader/sessions.csv).
Private pixels, traces, tensor checkpoints and ONNX weights remain local. An
earlier 96-scene execution smoke and its failed/repaired exports are retained
separately; they are not the serious model's accuracy evidence.

The actual localizer completed **9 epochs**, 2,593 seconds: the predeclared
2,400-second budget stops at the next epoch boundary, rather than interrupting
a batch. Forty was a maximum request, not the achieved count. The classifier
completed 24 epochs on **37,054 training crops / 4,650 calibration crops**; best
raw joint calibration accuracy was 96.84%. Those crops use annotated index
planes; that number does not measure whole-image or video recognition.
Numerical ONNX parity: max absolute differences 0.000275 in the pose export's
raw output units (mixed coordinates and scores) and 0.00000334 / 0.00000238 for
classifier logits, on a random tensor.

Calibration geometry diagnosis, same weights and thresholds:

| Stage on 1,000 calibration images | Complete nonempty states / 941 | Extra objects |
| --- | ---: | ---: |
| Current local | 15 | 97 |
| Initial specialized reconciliation | 481 | 187 |
| Geometry-only cross-zone reconciliation | 552 | 49 |

The preserved audit found 137 unreconciled indices whose containing face body
had a different declared zone label. Physical association was incorrectly using
that zone label to split one object into two. Removing that constraint fixes
this cause; no face-label deduplication, threshold reduction or integrity-gate
bypass was used. Remaining extras are not all attributed to the same cause.
Calibration workload contention differs between runs; it was not used to claim
comparative speed. Selection occurred before reading verification labels.

Frozen **1,000-image verification**, new parent seeds/rank-font families:

| Metric, including misses | Current local | Specialized |
| --- | ---: | ---: |
| Complete nonempty states | 26/941 | 480/941 |
| Observed objects matched | 1,421/3,847 | 3,704/3,847 |
| Missing / extra objects | 2,426 / 97 | 143 / 53 |
| Correct readable ranks | 694/2,740 | 2,343/2,740 |
| Wrong / unknown / missed readable ranks | 33 / 397 / 1,616 | 9 / 376 / 12 |
| Correct readable suits | 237/2,761 | 2,522/2,761 |
| Wrong / unknown / missed readable suits | 4 / 899 / 1,621 | 44 / 187 / 8 |
| Covered backs recognized | 72/682 | 625/682 |
| False presence on 59 empty scenes | 5 | 0 |
| Offline CPU processing p50 / p95 / max | 77.9 / 243.2 / 870.5 ms | 56.9 / 84.5 / 172.2 ms |

These are raw counts on clustered synthetic scenes, not a population confidence
interval or a provider generalization claim. Suit coverage improves considerably
but wrong suits increase: no poker perception approval follows from these scores.
The four paired verification jobs are complete in the consumption ledger. Frozen
pre-run manifests retain their original `verification_used=false` declaration;
the separate consumption ledger is authoritative for actual use.

Two new six-round physical sessions, each rendered in six paired conditions:

| Video outcome, 60 source decision opportunities | Current local | Specialized |
| --- | ---: | ---: |
| Correct rank-only R1 within 1,500 ms | 9/60 | 17/60 |
| Correct full-table state within 1,500 ms | 0/60 | 17/60 |
| Missed exposures across 360 paired expected exposures | 174 | 144 |
| Duplicate / wrong-or-unmatched exposures | 0 / 23 | 1 / 0 |
| Diagnostic identity switches | 8 | 119 |
| Wrong/stale basic-advice frames observed | 0 | 0 |
| Certified count frames | 0 | 0 |

Clean R1 improves from 0/5 to 4/5 for each new family. Overlap R1 remains 4/5
and 5/5; its exposure reconstruction actually worsens. Rotation obtains most
exposures but no timely R1. Fading, clipping and popup conditions retain zero
timely R1. All 60 source opportunities remain in the denominator, including
conditions that hide necessary glyphs; abstention on absent information is not
classified as invented certainty. The legacy anchor matcher approximates
rotated geometry, so 119 is a diagnostic switch count, not rigorous general
MOT accuracy. Even the clean/overlap failures reject R2 promotion. Zero observed
wrong/stale advice in this small paired corpus does not establish zero risk.

Historical private development regressions expose the transfer limit: on three
annotated digital screenshots (two moments plus a repeated preview), the current
reader has 9/9 ranks, four correct suits/five unknown and the covered back. The
specialized reader has **2/9 ranks**, five unknown/two missed, one correct suit/
one wrong/five unknown/two missed, and misclassifies the matched back. It also
has three extras. The same initial table/card ROIs reach both readers. Four
unannotated monitor-photo cases remain unscored, with no substitute labels.
This regression is retained; the model is not promoted on those providers.

**Decision:** keep one trained research challenger and the frozen comparison;
reject default/desktop, external-provider, poker and certified R2 promotion.
The measured follow-up needs are actual graphic-domain adaptation and stable
instance reconstruction. A tracker comparison would require fixed detection
replay and better geometry correspondence; it cannot repair unreadable ranks
by itself. No extra detector/framework was introduced after seeing verification.

Validation: **542 app tests, 10 subtests**, **19 isolated research contracts**,
and evidence consistency passed. One early attempt to run research geometry
tests in the app environment failed for missing optional SciPy; those tests were
then run successfully in their intended isolated environment. UI/native tests
were not repeated because this increment changes neither UI nor native code.
All four frozen release-file hashes match; no installed release was replaced.
API inference requests/cost remain zero, with credential/account prerequisites
unresolved. API accuracy and request-to-validated-JSON latency remain unmeasured.
