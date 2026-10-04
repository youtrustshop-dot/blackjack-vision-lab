# Synthetic Blackjack stress laboratory

This extension reuses the existing finite-shoe Blackjack engine. It generates
continuous original local VP8/WebM clips, a visual gallery, and separate frame
annotations. It does not change the installed desktop release or default reader.
No API, training, provider assets, extra dependency or external upload is used.

## What is executable

- Six rendering conditions: clean, overlap, rotation, faded/blurred, clipped,
  and overlay-covered cards; three original palette families.
- Complete seeded single-hand rounds with progressive deal, player actions,
  dealer reveal/draw, settlement, clear table and subsequent deal. Deal movement
  is rendered at 12 fps rather than assembled from sparse provider screenshots.
- Geometric body/corner visibility after rotation, frame clipping, overlap and
  overlays. Covered cards have no rank/suit in their visible annotation. A fully
  occluded object is absent from pixels; evaluator identity is retained separately.
- Visible controls for player/dealer/deal/result phases. No synthetic round IDs,
  shoe labels or tracker IDs are printed in the image.
- Video replay through the **unchanged** default calibrated `LiveObserver` with
  manual turn disabled. Only decoded RGB, sequence and timestamp cross into the
  observer. Truth is consulted afterwards in evaluation.
- A bounded-memory engine batch supporting 200,000 or more rounds, including
  splits and doubles, with termination, card-identity and Hi-Lo invariants.

Visual clips are restricted to one player hand because the current calibrated
reader supports one player ROI. This limitation is explicit; the engine batch
does exercise splits. The driver uses a simple hit-below-17 policy to produce
states, not an optimal play or profitability claim.

## Reproduce locally

From the repository root, using the existing environment:

```powershell
.venv/Scripts/python.exe -m validation.tools.stress_lab generate --output artifacts/stress-lab/new-development-run --rounds 3 --seed 4100410
.venv/Scripts/python.exe -m validation.tools.stress_lab run --manifest artifacts/stress-lab/new-development-run/manifest.json --output artifacts/stress-lab/new-development-run/baseline.json
.venv/Scripts/python.exe -m validation.tools.stress_lab bulk --rounds 200000 --output artifacts/stress-lab/engine-200000.json
```

Open the generated `index.html` gallery, choose a condition, and play its video.
Individual `.webm` files can also be used in the application's existing replay
workflow. `--profiles clean,rotation` limits rendering; visual runs accept
1â€“200 rounds, bulk engine runs 1â€“1,000,000. Existing output directories are never
overwritten by generation. The VP8 writer must succeed; missing codec support
is an error, never replaced by false video evidence.

## Evaluation boundaries

The same seed and underlying game are used across conditions. These are paired
development variants, **not six independent sessions or unseen provider tests**.
No train/validation/final-holdout claim is made. A future training corpus needs
separate game seeds and graphic families before fitting any model.

The baseline samples decoded video every 350 ms and verifies hashes and full
decode length. It reports geometric presence misses/extras, correct/wrong/unknown
ranks and suits, unknown phase, inventory L1 drift, observed RC error, recognized
rounds, timely usable opportunities, and false/stale advice. Advice is checked
against the existing basic-strategy implementation, not an independent strategy
oracle. Inventory truth grows only when a physical face is actually represented
in pixels, not when the engine has privately dealt a future card.

Presence association uses zone and bounded center distance; it is a diagnostic
association, not COCO AP or a rigorously calibrated detector benchmark. Index
visibility measures printed top-left glyph ink after occlusion, rather than a
coarse enclosing rectangle. Fading/blur do not establish human legibility. Repeated
frame observations are correlated. Counts refer to sampled observations, not
unique physical cards. Timings are offline processing, not capture-to-display.
ID switches and exact event-to-card matching are not yet scored.

The large engine batch is an invariant stress run against the existing engine,
not independent proof of every rule, ML training, 200,000 vision-tested hands,
or evidence of economic return. No detector is promoted by this experiment.

The current executed aggregates belong in the existing experiment matrix and
`validation/results/synthetic-stress-lab/`; raw clips and traces remain under
ignored `artifacts/`. External provider recordings still remain necessary to
measure transfer beyond these original graphics.

The initial v1 development run is retained under `artifacts/stress-lab/run-20261004`.
Its broad corner-box mask counted covered whitespace as unreadable index area.
The corrected v2 run uses glyph ink masks, under `run-v2-20261004`; v1 is not
silently overwritten, reclassified as a holdout, or counted as new independent data.

## Executed development run — 2026-10-04

Six 30.5-second VP8 clips at 1024×768/12 fps; 366 decoded frames and 87 sampled observations each. Same three rounds repeated across conditions, not 18 independent rounds. Unchanged calibrated reader, no manual turn.

| Condition | Correct ranks / geometrically readable observations | Presence misses | Correct phase | Timely usable opportunities |
| --- | ---: | ---: | ---: | ---: |
| clean | 310/310 | 0 | 0/87 | 0/6 |
| overlap | 310/310 | 39 | 0/87 | 0/6 |
| rotation | 104/310 | 227 | 0/87 | 0/6 |
| faded | 0/310 | 209 | 0/87 | 0/6 |
| clipped | 178/250 | 149 | 0/87 | 0/6 |
| covered | 117/141 | 170 | 0/87 | 0/6 |

Every variant ends with inventory L1 error 20 and maximum observed RC error 9; zero rounds recognized. This is a negative continuity result, not accepted counting. No advice was emitted, so zero observed false advice does not imply adequate decision coverage. Unknown phase is already a complete blocker on clean input. Rotation/fading additionally require improved perception. Partial glyph labels and geometry matching remain diagnostic; the 10 partial-index rank claims in the covered condition are not independently proven wrong readings.

The engine batch completed **200,000 rounds in 307.20 seconds**, with 8,841 split actions and 9,319 doubles. All three declared invariants held. This is not 200,000 vision-tested hands or model training.

Validation: **514 tests + 10 subtests passed**, two existing warnings; five focused stress tests also passed. The browser decoded all six clips at their native dimensions without media errors, and playback advanced. First v1 annotations are preserved; v2 fixes glyph visibility without changing the rendered videos or tuning the reader.

Next scoped experiment: one visible-control/temporal-context challenger against this frozen development corpus. Its supported-layout result must stay separate from external provider evidence.
