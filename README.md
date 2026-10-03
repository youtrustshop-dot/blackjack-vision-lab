# Blackjack Vision Lab

An open-source, local blackjack simulation and live vision laboratory. Share a screen, window or tab once: the lab watches its video, tracks exposed cards across hands, maintains a Hi-Lo count and estimates the best action with win/push/loss probabilities and expected value.

**English is the default. Italiano is available in the language selector.** [Leggi in italiano](README.it.md).

![Live video, recognized cards and mathematical advice](docs/screenshots/live-vision.jpg)

## Start

Download the [Windows 0.2.0 installer or portable ZIP](https://github.com/youtrustshop-dot/blackjack-vision-lab/releases/tag/v0.2.0). Windows x64 and Microsoft WebView2 are required; Python and Node are included or unnecessary for the packaged app.

From source, use Python 3.12+ and Node.js 22+:

```powershell
git clone https://github.com/youtrustshop-dot/blackjack-vision-lab.git
cd blackjack-vision-lab
.\setup.ps1
.\run.ps1
```

Open http://127.0.0.1:8765 in Chrome or Edge. Keep the launcher running.

## Watch a simulation

1. Open **Live vision → Run lab demo** to test the complete video pipeline immediately. The bot plays its own simulation; the observer receives only its video pixels.
2. For your screen, press **Share screen**, then choose the screen/window/tab in the browser picker. Audio is not requested. No manual image-capture step is required.
3. For a separate playable table, select **Open simulator window**. Share that window and use **Table calibration** to select its four corners in order: top left, top right, bottom right, bottom left.
4. Start from a new shoe for a complete count. If sharing begins mid-shoe, the count covers the observed portion. Keep the table in its calibrated position.
5. Press **Floating advisor** for a compact probability/count panel. **Pop out advisor** opens a separate always-on-top window in supported Chromium browsers; other browsers keep the panel in the page.

The included detector is validated on **the lab's card artwork**. Other games, camera footage and card designs require their own detector and evaluation. The live demo and decoded multi-hand video are tested; automated verification did not select a personal desktop in the display picker.

The preview is a real `MediaStream`. Analysis samples it automatically with a video-frame clock, one request in flight, no upload backlog, persistent tracking and stale-advice expiry. See [live vision](docs/LIVE_VISION.md) for the measured scope and probability method.

## What it includes

- Seeded simulator, configurable rules, bot and manual play, independent settlement engine.
- Finite-shoe solver, generated basic strategy, exact-within-budget split analysis, declared approximations and uncertainty gates.
- Live video observation, multi-round/shoe tracking, exposed-card count, Monte Carlo action comparisons and floating advice.
- Counting systems, shoe composition, unknown-deck inference, calibrated image/video research, immutable corrections and prefix replay.
- Reproducible experiments, analytic/property/integration tests and independent mathematical comparisons.
- English UI/documentation, optional Italian UI, MIT source and packaged Windows distribution.

Win probability and EV are different quantities. Live win/push/loss describes net profit of the active hand and newly created splits; already existing other hands are excluded. Live EV uses finite-pool Monte Carlo with generated basic continuation. Confidence intervals measure sampling uncertainty, not vision accuracy. Unstable, unreadable or stale observations hide the recommendation.

## Documentation and validation

- [Verified status](docs/STATUS.md), [roadmap](ROADMAP.md), [requirements/evidence](docs/REQUIREMENTS.json).
- [Live video guide](docs/LIVE_VISION.md), [screen sharing and recovery](docs/SCREEN_SHARING.md), [vision contract](docs/VISION.md).
- [API](docs/API.md), [Windows build/distribution](docs/DESKTOP.md), [changelog](CHANGELOG.md).
- [Perception experiments](docs/PERCEPTION_EXPERIMENTS.md), [external photographic failures](docs/EXTERNAL_BENCHMARKS.md), [references/licensing](THIRD_PARTY_REFERENCES.md).

```powershell
.venv/Scripts/python.exe -m pytest -q
npm --prefix ui test
npm --prefix ui run build
```

The 0.2 source verification passed **259 tests + 10 subtests**, **16 frontend tests** and the production TypeScript/Vite build. Historical research reports preserve their original measurements and language; current product documentation is English. No universal 30-FPS-analysis or sub-100-ms guarantee is claimed.

## Architecture and boundaries

`engine.py` defines rules/settlement; `solver.py` computes EV; `simulator.py` owns the seeded shoe. `vision.py` reconstructs card observations. `live.py` owns the persistent video observer and sampled probability engine; `live_api.py` receives video observations. `ui/` contains the React/TypeScript interface and Tauri shell.

The live observer does not receive a simulator session ID, hidden card ranks or future shoe order. Its configuration declares rules/inventory; card and context evidence comes from visible pixels. Processing stays in the local backend. The scope is simulation and research.

Laya, Jev and Cloudflare Clef are optional research directions, not startup dependencies or measured production models. [Model assessment](docs/LIVE_VISION.md#model-options) explains their roles.

## License and contributions

Original code uses the [MIT license](LICENSE). Dependencies, fonts and Microsoft components retain their own terms, included in Windows packages and `ui/src-tauri/licenses/`. See [CONTRIBUTING.md](CONTRIBUTING.md) and [publication provenance](docs/PUBLICATION.md). Private conversations, credentials, generated executables and large datasets are excluded from the public source checkout.
