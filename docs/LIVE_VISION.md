# Continuous live vision

## Video workflow

Open the local app in desktop Chrome or Edge. Select **Live vision**, then **Share screen**. The browser's display picker chooses a screen, window or tab and returns a real `MediaStream` to a playing video element. Audio is disabled. Permission is requested for each new sharing session. The source remains shared until **Stop video**, the browser's stop-sharing command or page closure. Switching laboratory sections keeps the live observer mounted and running.

There is no manual image-capture/import step in this workflow. A `requestVideoFrameCallback` clock samples new video frames automatically, throttled to at most one observation every 350 ms. Only one request may be in flight; frames encountered while busy are skipped instead of queued. Each observation is encoded as PNG and sent to the local backend. A frame-based analysis transport is how the video is processed, not a user-operated screenshot workflow.

The advisor hides decisions 2.2 seconds after capture time without a fresh successful observation. Requests time out after 6 seconds; cancellation/generation guards reject late results. Upload errors immediately remove advice. The displayed latency includes local capture/encoding/upload/processing. This is distinct from source video FPS, processed observations and skipped busy frames.

The Windows shell may not expose `getDisplayMedia`. **Open in default browser** launches the same local URL; use Chrome or Edge and keep the desktop app running so its backend remains available. This button uses the configured system browser, not a forced browser installation.

## Immediate simulation

**Run lab demo** creates an isolated seeded simulator and a canvas-backed 15-FPS video stream. The source bot uses public simulator commands. The independent live endpoint receives only video images and declared rules; it cannot receive that simulator's session ID. Pause/resume the bot or take a manual action to inspect changes.

**Open simulator window** opens `/?simulator=1`: a separately playable table with visible SHOE, ROUND, HAND and PHASE labels. Share its window/tab, then use **Table calibration** before playing. Select top-left, top-right, bottom-right and bottom-left table corners in the preview. The backend normalizes that quadrilateral to the lab geometry. Keep window position and table scaling fixed, or stop observing and recalibrate.

Rule configuration belongs to the lab session; the standalone simulator uses the default six-deck rules. Match the declared rules before analyzing a different source. The observer never silently learns the full rules from a card image.

## Tracking and count

The included OpenCV/template detector recognizes the lab's card corners and exposed controls. Context labels are read from visible pixels, not native session metadata. Two distinct observations stabilize round/shoe context; card tracking confirms after three stable observations. Reveal, movement and repeated video images preserve logical identities. Round changes reset active-card tracks while retaining shoe count; a visible new-shoe label resets the shoe.

Declare **Observe from a new shoe** only when observation really begins before the first deal. Otherwise counts cover the observed portion and the assumed unobserved pool cannot reconstruct earlier missing cards. Hi-Lo running count uses each confirmed exposed rank once. True count divides by the estimated physical decks remaining, based on declared inventory and observed exposures; unknown earlier removals limit its interpretation.

The gate withholds advice on changing context, pending/lost/unreadable cards, missing active player/dealer cards, a non-player phase or unreadable legal controls. A manual-layout player-turn declaration is available for calibrated research, but does not certify arbitrary layouts or correct an unknown deck history. The gate cannot prove that a card never detected at all was absent.

## Probability method

Live estimates draw without replacement from the informational pool. The dealer hole card is marginalized; a visible player phase under American peek rules conditions on a negative peek. ENHC, OBO, double, surrender and bounded sequential split/resplit are represented. Future choices use the generated rule-dependent basic strategy, rather than optimizing every future finite composition.

Each legal action has 500, 1,500 or 5,000 sampled outcomes in the UI (the API accepts 100–8,000). Win means positive net profit, push zero and loss negative profit for the **active hand plus new splits caused by its evaluated action**. Already existing other hands are excluded. EV is net profit per active original wager and is not a win percentage. EV has a normal sampling interval; win probability uses a Wilson 95% interval. Overlapping EV intervals produce **No clear ranking**. Values are explicitly approximate (`exact=false`).

The UI's **No positive EV detected** describes the current action estimate. It is not a computed pre-deal betting edge for the next round. Neither a positive sampled EV nor a win probability guarantees an outcome. Sampling intervals do not include detector error or model mismatch.

The table's separate decision solver retains its exact/approximate precision contracts and budget gates; live probabilities do not replace those contracts.

## Floating advisor

**Floating advisor** opens a compact panel that updates from the same live observations. **Pop out advisor** uses Chromium's Document Picture-in-Picture API for a separate always-on-top window when supported. Otherwise the panel stays in the page; it cannot stay over another application. A bounded PiP request rejects late windows after cancellation. Closing the separate window returns the advisor to the page; **Close advisor** disposes it. The advisor follows the language selection and hides stale advice.

## Verified scope

- 259 Python tests and 10 subtests passed, including 13 live tests. 16 frontend tests and TypeScript/Vite production build passed.
- A real decoded lossless FFV1 video, 35 images at 12 FPS across seven bot actions, preserves exposed counts through reveals and new hands. These are actual distinct video observations, not internal repeated detector updates pretending to be a video benchmark.
- Integration tests verify an embedded 960×600 table in a 1600×1000 image through four normalized corners, multi-digit visible labels, new-shoe resets, immediate occlusion gates, monotonic timestamps/sequences and session-metadata rejection.
- Monte Carlo stand agrees with an independent exact finite-pool solver within the declared tolerance; analytic cases distinguish win probability from EV and check surrender and hidden-card conditioning.
- Actual browser demo video followed multiple hands and produced card detections, count, advice, EV and probabilities. A held paused table continued to generate video while the count remained unchanged. In that run upload-to-result latency was about 132–177 ms; this is an observation on this computer, not a universal guarantee.
- The automated checks did not select a personal desktop in the display picker. Browser/OS source selection remains user controlled. Card artwork outside the lab and photographic/table-layout generalization are not validated by these results.

## Model options

[Cloudflare Clef Flash](https://huggingface.co/Cloudflare/clef-flash) is a 9B multimodal structured classification model with an Apache-2.0 model license. Its model card accepts image/video records with schemas; it is a plausible phase/anomaly research candidate. The documented environment includes H200 hardware, so no local-PC real-time speed claim is inferred. No Clef weights were downloaded or measured in this release. It would still require card-data validation and temporal tracking.

[Jevbox](https://github.com/extend-hq/jevbox) organizes and retrieves documents with citations and permissions; it is not a screen-capture or card detector. Laya remains deferred. None is required for the working local video path.

Screen acquisition, visual recognition, persistent state and mathematical decisions are separate components. Replacing the detector with trained card weights requires model/dataset licensing, a held-out multi-session video benchmark, counting-drift checks and gate validation before being described as supported.

Browser contracts: [display media](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia), [video-frame callbacks](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback), [Document Picture-in-Picture](https://developer.mozilla.org/en-US/docs/Web/API/Document_Picture-in-Picture_API/Using).
