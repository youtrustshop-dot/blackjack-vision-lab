# Freegames surface probe — 2026-10-04

The new neutral/index-row profile fixes a reproduced **2 → 7** substitution in
this small Freegames development sample. It is **not promoted**: BrainPlay
regresses, suits and automatic phase remain insufficient, and no original
continuous provider video was obtained. The installed 1.1.1 and default detector
are unchanged.

## Evidence acquired autonomously

Eight new, locally saved browser screenshots from Freegames classic: one empty
table, two completed play-money rounds and the opening of a third. The original
browser screenshot dimensions are 1280×1262. Files remain JPEG; native role
crops are not resized or enhanced. Capture start/end timestamps, hashes, initial
table/dealer/player/control rectangles, oracle annotations and exact crops are
retained under ignored `artifacts/provider-sessions/fg-sparse-dev-20261004/`.

These are **sparse development stills**, with unobserved gaps. They are not a
30-FPS recording, a complete session, eight independent trials or a final
holdout. The 29 annotated face occurrences repeat cards within a round. The
assistant reviewed pixels; there is no independent human validation. Deck
artwork outside the calibrated hand zones is excluded; no hidden dealer card
or physical shoe history is inferred.

Two acquisition routes were investigated: preparation of the existing Windows
Snipping Tool and an attempt through the application's existing local video
recorder. Native browser capture
previously stopped because the browser URL could not be verified. In this
follow-up, the known-URL browser tab is controllable, but its content does not
match the native window inventory. The application on a separate local port
reached the screen-sharing pending state; the source picker was not exposed to
the available browser controls. That attempt was cancelled/closed. No video
was saved, no entire desktop was silently recorded, and no browser protections
or permission controls were bypassed.

## Reproduced cause and one challenger

The baseline's permissive light-surface mask joins faded table lettering and
colored total badges to the white card row. Inside that merged row a tiny
rounded seam is recognized as **7** before the actual **2**. The real 2 is then
rejected as a second corner of the same surface. The OCR can read the 2: the
problem includes proposal geometry and deduplication order, not just OCR.

One geometric challenger uses the same OCR, suit reader, calibration, rules and
integrity gates. Its bright neutral surface mask uses HSV value ≥175 and
saturation ≤65. Its bounded upright index-row filter retains small top-seam
components and out-of-row artwork in diagnostics without treating each as a
new physical card. A body without an accepted rank still remains unreadable;
real region-edge clipping still blocks analysis.

An initial mask-only development attempt removed false edge warnings but still
read seams as 7. The index-row refinement followed crop inspection. Therefore
the final settings are **development-tuned**, not selected on unseen validation.
No OCR score threshold was lowered, no totals were converted into cards, and
no oracle phase or manual turn flag was supplied to inference.

## Same-input results

| Measure | Legacy baseline | Neutral/index challenger |
|---|---:|---:|
| Exact rank/presence inventories across all eight stills | 2/8 | 7/8 |
| Exact inventories on the seven nonempty stills | 1/7 | 6/7 |
| Correct conditional rank-study results at five annotated player opportunities | 0/5 | 4/5 |
| False acceptance of an incorrect rank inventory | 0 observed | 0 observed |
| Complete observed state, including phase and controls | 0/8 | 0/8 |
| Known suit occurrences correctly read | 1/29 | 1/29 |
| Readable detected faces with unknown suits | 27 | 27 |
| Stills with false region-edge warnings in this sample | 7 | 0 |

One expected face is absent in the challenger's bust/overlay still. This is not
an unknown suit: the card itself was missed. The correct inventory on a 21 hand
does not become useful because remaining unresolved artwork keeps its gate
closed. Thus correct ranks are still insufficient. The one exact full-card
inventory in each profile is the **empty** image, not a completely recognized
playing hand. No phase is read in any of the eight cases.

Single-attempt processing timings are in the receipt. They include observation
and conditional analysis, exclude capture/preparation/display, and clear the
glyph cache before each read. Profile order is fixed, with no runtime warm-up
exclusion; they are diagnostic timings, not a fair sustained latency or speed
promotion benchmark.

## Failure breakdown

| Stage | Finding | Status |
|---|---|---|
| Continuous acquisition | Original video/source picker unavailable to automation | Blocked; zero videos |
| Native ROI/coordinates | One static initial calibration; no scaling or perspective synthesis | Executed on stills only; scroll/DPI stability not tested |
| Surface proposals | Table artwork and badges merge with card mask | Reproduced; neutral mask separates the tested surfaces |
| Rank/association | Seam 7 suppresses real 2; overlay/figure still loses Q | Seam fixed in development; one missed face remains |
| Suits | One correct occurrence; 27 unknown detected suits and one missed face | Not ready for Poker card state |
| Phase/controls | Both profiles return unknown phase, no controls | Not solved; no autonomous live advice certification |
| Tracking/round boundary | Sparse snapshots omit transitions | Not measured; no new exposure/RC/TC result |
| Integrity | Challenger still blocks three stills for unresolved proposals | Retained; not indiscriminately disabled |
| Staleness/advisor | No continuous source connected | Not measured by this probe |

## Regression and decision

The three historical consumed stills were replayed separately, not counted as
new evidence. Legacy retains 3/3 rank inventories and 1/3 conditional usable
states. Neutral retains both Freegames rank inventories, makes the original
Freegames still conditionally usable, still blocks its cropped preview, and
**loses BrainPlay's cards**. This negative result prevents a global replacement.

Use `LocalVisionReader(surface_profile='neutral')` only as the explicit research
challenger. Default/local live recognition stays legacy. Do not replace the
release, certify counts or start broad training from these results. The original
session milestone remains blocked; a full automatic game state is not ready.

## Reproduction

With the local private manifest retained:

```powershell
.venv/Scripts/python.exe -m validation.tools.surface_profile_comparison artifacts/provider-sessions/fg-sparse-dev-20261004/manifest.json --output artifacts/provider-sessions/fg-sparse-dev-20261004/comparison-rerun.json
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
```

The public aggregate receipt omits raw screenshots, per-card crops and private
paths. Without the private pixels it is an inspectable report, not a public
dataset that someone else can independently rerun. No API calls, external
uploads, model downloads, new frameworks, Poker strategy changes or desktop
release replacement occurred.

Source validation: **509 Python tests and 10 subtests passed in 64.98 s**,
including five targeted seam/presence/crop/probe-contract tests. Two existing
dependency warnings remain. UI code is unchanged; no new frontend build,
native installer, physical monitor/advisor or minimized capture verification
is claimed. Evidence consistency is checked separately in the verification
receipt.
