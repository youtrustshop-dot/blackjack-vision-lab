# Verified status — 0.2.0

The source includes the original mathematical/research laboratory plus continuous video observation, a floating advisor, a standalone simulator and English-first UI with optional Italian. Laya is deferred. Clef/Jev are not required or promoted to measured production models.

## Current verification

- **259 Python tests + 10 subtests passed** in 30.87 seconds. The existing Starlette/httpx deprecation warning is preserved. Thirteen tests exercise the new live path.
- **16 frontend tests passed**: API outage/recovery, display-stream ownership/late grants, video scheduling/backpressure/stale callbacks and language translation. TypeScript/Vite production build passed.
- Real lossless video decoding across multiple actions/hands, persistent exposed counts, reveals, shoe changes, four-corner normalization, context OCR, action probabilities and occlusion gates are checked.
- Actual browser video demo recognized multiple hands and produced action/EV/win/push/loss, persistent RC/TC and fresh-observation metrics. Personal display-picker selection and arbitrary card artwork are not claimed as automated end-to-end tests.
- **Windows 0.2.0 built and exercised**: frozen backend, hidden native WebView creation, independent HTTP/solver/live-pixel flow, graceful owned-backend shutdown and a fresh current-user installer install/launch/uninstall. The frozen payload verifier checked 20 Python modules and 943 data files in the first build; metadata refreshes rerun the exact payload check. Versioned reports under `release/v0.2.0/` record final binary digests; original v0.1.0 evidence remains unchanged under `release/`. Personal screen capture and a separate always-on-top window are not certified by the hidden executable smoke.

[Live vision](LIVE_VISION.md) defines probability scope, timing, tracking and screen-sharing behavior. Live estimates are Monte Carlo, not certified exact optimization. There is no universal 30-FPS-analysis or sub-100-ms guarantee.

## Retained mathematical evidence

The original engine/solver audit covered 2,000 finite-shoe states across five deck counts and S17/H17: optimal actions agreed. 279 approximate-reference EV discrepancies were retained as failed originals and resolved separately at greater precision, with maximum diagnostic error 1.82e-10. BJSS supplied six states/24 EVs agreeing within 1e-9. FreeBJ and mhluska comparisons ran 120,000 rounds per engine with explicit policies and intervals; the failed conditioned FreeBJ comparison remains non-equivalent. Three real core defects found during that audit have independent regression cases.

These historical studies are documented in the existing raw validation/research reports. They are not rerun measurements of every new UI release. [Original status report](history/v0.1-STATUS.md) preserves the full earlier record and original language.

## Perception evidence and limitations

The original controlled held-out benchmark used 360 test images: 1,632 geometrically correct detections, 1,452 rank/suit readings and 180 card backs, with no FP/FN in that dataset. Detection p95 was 14.68 ms. Three-frame tracking ended 59/60 sessions exact, with one provisional reveal retained. These historical offline timings are not live capture FPS.

Temporal confirmation produced real delays and count errors per intermediate image; the ablations and gate exclusions remain in [PERCEPTION_EXPERIMENTS.md](PERCEPTION_EXPERIMENTS.md). External photos, unknown card designs and discard-tray inference had failures or abstentions; see [EXTERNAL_BENCHMARKS.md](EXTERNAL_BENCHMARKS.md). Adding live acquisition does not erase these limits.

The live detector reads the lab artwork and visible lab context. Other footage needs a trained, separately evaluated detector. Counts cover exposed cards actually observed; starting mid-shoe leaves earlier composition unknown. Sampling confidence does not certify perception accuracy or session integrity.
