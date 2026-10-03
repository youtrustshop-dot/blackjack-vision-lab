# Verified status — 1.0.0

Version 1.0 adds immediate legal recommendations, ace values, a complete offline starting-hand library, separate observers for up to five tables, image/manual input, first-visit setup, rule presets, a dark visual identity and an optional Chromium image extension.

## Current verification

- **282 Python tests + 10 subtests passed** in 30.32 seconds. This includes the finite-pool, replay and independent reference checks plus the new recommendation, ace, image, count-isolation and model-bridge cases.
- **23 frontend tests passed**. TypeScript and the Vite production build passed.
- Actual browser checks recognized an uploaded A–7 versus 9 image as soft 18, showed the alternative total 8 and recommended Hit. Confirmed 20 versus 6 recommended Stand. English and secondary Italian flows, the offline strategy matrix, first setup and five distinct lab-video sources were exercised.
- Five observers preserve separate rules, ranks, histories and counts. The initial five-video browser run exposed delays; pixel reuse and an offscreen media-clock heartbeat were added. The browser still produced variable response latency and occasional stale expiry during concurrent work; no universal five-table latency is certified.
- Windows 1.0 frozen-backend, hidden native launch/shutdown and fresh current-user installer install/launch/uninstall checks passed, including pixel recognition, probabilities and exposed counts through a reveal and second hand. Versioned `release/v1.0.0/` reports bind these checks to artifact digests. Portable archive binary fingerprints and CRC are verified.
- **Clef actually ran locally** on an RTX 2070 SUPER (8 GB) with 16 GB RAM. The two controlled cases returned the expected scene labels. Loading took 1,099 seconds under concurrent work; the first text/image calls took 137.1 / 35.7 seconds. A warm request through the actual core loopback bridge classified the image in 3.8 seconds, with 8.2 seconds total roundtrip. Peak allocated model VRAM was 4,028 MiB. This is an occasional experimental classifier, not a real-time card detector. [Measured model evidence](CLEF_VERIFICATION.json) retains earlier failures and scope.
- During model loading, a preview health request timed out. A private diagnostic preview process with periodic stack dumps subsequently exited with an access violation in the Windows asyncio path; the cause is undetermined. The ordinary launcher was restarted and its health/controlled image path checked. This negative observation is retained rather than described as a passed stress test. The separate bounded frozen/native/installer checks do not certify resilience under every memory-pressure condition.

Basic strategy is available before a finite computation finishes. An unresolved Monte Carlo ranking keeps the configured basic policy as the primary recommendation. A valid recognized turn receives a legal action; unavailable, changing or stale evidence asks for a fresh view or manual confirmation. Unknown pixels never become an invented action.

The included detector is validated on the lab artwork. External card graphics need a separately trained and evaluated detector. Poker/other tables are visual monitors only. Counts cover observed exposures; joining a shoe midway leaves earlier composition unknown. The optional Clef scene classifier does not recognize ranks or compute blackjack decisions.

## Retained evidence

The prior studies below remain historical measurements, not new performance claims. Original v0.1 and v0.2 release artifacts and their evidence are preserved.

# Historical verification — 0.2.0

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
