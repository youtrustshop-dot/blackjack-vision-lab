# Blackjack Vision Lab roadmap

The original laboratory covers rules, an independent mathematical core, observed-state reconstruction, counting, replay, experiments, reference comparisons and Windows distribution. Version 0.2 adds the requested live-video workflow and English-first product. [Requirements and evidence](docs/REQUIREMENTS.json) are authoritative; historical failures and unexecuted optional models remain explicit.

## Correctness contracts

1. Decisions see only exposed cards, declared rules and observed history; hidden ranks and future shoe order remain outside the decision boundary.
2. The unobserved informational pool includes hidden cards and differs from the physical draw pile. Missing exposures need uncertainty or a gate.
3. Exact, approximate and Monte Carlo results declare their methods and budgets. Missing actions cannot certify a global optimum.
4. EV is normalized to the original wager, with explicit double/split/surrender/insurance/ENHC settlement.
5. Reveals, motion and repeated video observations preserve card identity without duplicate counting.
6. Reference comparisons align rules, information, policy and normalization. Vision score, probability calibration and whole-shoe integrity are distinct.

## Delivery matrix

| Milestone | Current scope and evidence |
|---|---|
| M01–M04: rules, engine, solver, splits | Implemented; analytic/property tests, finite-shoe differential comparisons and precision gates. |
| M05–M07: counting, shoe, events/replay | Implemented; Hi-Lo and additional/custom systems, unknown inventory/posteriors, immutable corrections, prefix replay. |
| M08–M12: simulator, capture, perception, tracker, gates | Implemented for controlled lab artwork. Multi-round live video added in 0.2. External photographic generalization remains unsupported. |
| M13–M15: dashboard, experiments, validation | Implemented; English primary/Italian secondary, probability/EV distinction, measured intervals, preserved negative results. |
| M16: external mathematical references | hhoppe/FreeBJ/mhluska/BJSS executed with stated equivalence limits. CardSharp studied architecturally; MGP inspected without a supported numerical runtime. |
| M17: competing detectors and tray inference | Controlled benchmarks and external photographic failures/abstentions retained. Roboflow/ONNX trained weights are not validated locally. |
| M18: Jev/Laya/RLCard | Contract adapters and measured state-machine baseline retained. Laya deferred; actual model execution and RLCard remain future research. |
| M19: desktop packaging | Tauri/frozen backend/NSIS with source provenance, dependency terms and versioned release evidence. |
| M20: performance | Measured on this computer within each task's contract. Universal 30-FPS analysis or <100-ms feedback is not certified. |
| V21: continuous screen video | Share-once display stream, automatic video-clock observations, persistent count, stale expiry and no backlog. Tested canvas video plus multi-action lossless video. |
| V22: live probabilities and popup | Finite-pool sampled win/push/loss/EV per active-hand action, intervals, uncertainty gate, floating panel and Document PiP pop-out. |
| V23: international distribution | English default UI, English GitHub imagery/docs, optional Italian selection, Windows 0.2 artifacts. |

## Next research

Validate a trained detector on licensed external card artwork and multi-session footage; evaluate count drift and never-detected-card failures before claiming broader support. Compare local phase/anomaly classifiers, including Clef/Laya, on actual hardware. A model announcement is not a benchmark. Optional pre-deal betting-edge analysis needs its own information/EV contract and tests; current live EV describes the active decision.

The full original planning text and acceptance history are retained in [the historical roadmap](docs/history/v0.1-ROADMAP.md). Historical artifacts keep their original languages and measurements; they are not silently translated into new numerical claims.
