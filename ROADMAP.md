# Blackjack Vision Lab roadmap

Current priorities are governed by [MASTER_PLAN.md](docs/MASTER_PLAN.md), accepted v1.1.
This document retains historical workstreams; its R1/R2 labels predate the master plan
and do not override the current locale/API comparison before additional training.

## Reliability programme: complete-session vision and Texas Hold'em

The target is measured correctness over complete games, not a subjective 10/10
or a promise that arbitrary pixels are always readable. The seven new private
reports invalidate the previous implication that passing one external screenshot
proved reliable multi-provider play. Private screenshots are never redistributed.

| Workstream | Implementation and acceptance contract | Status |
|---|---|---|
| R1: independent Clef verification | Fixed scene/table/card questions; test rank, suit, count and phase against annotations; record errors, abstentions, warm/cold latency and hardware. Model scores do not certify accuracy. | Implemented; 11 exploratory cases, held-out corpus pending |
| R2: overlapping printed cards | Preserve entire rank corners; all 13 ranks, four suits, partially overlapping bodies, scaling, compression, duplicate previews, unreadable corner abstention. | Implemented for tested artwork; broader suits/layouts pending |
| R3: provider profiles | Lab, Windows-style blue badges and web-style side totals; EN/IT actions; explicit compatibility metadata and user region selection. Broader graphics require a held-out corpus. | Lab + classic + EN/IT side totals implemented; broader profiles pending |
| R4: whole-game memory | Separate current visible hand from historical exposures; stable round lifecycle, repeated identical ranks, missed boundaries, dealer reveals and shuffle declarations; no phantom cards. | Implemented and regression-tested; held-out whole-shoe evaluation pending |
| R5: uncertainty UX | Hide unverified totals and count-derived estimates; show readable reasons and current visible evidence; never show stale advice as current. Always communicate a state. | Implemented; stale/uncertain evidence remains explicit |
| R6: continuous video | Observe every browser-delivered frame with a lightweight monitor; inspect changed/stable evidence with bounded model work; report received/analysed/skipped frames, latency and gaps. Dense neural processing needs a measured hardware budget. | Every-frame monitor and local recording implemented; dense neural inference deferred |
| R7: optional neural verifier | Asynchronous, bounded, local-only verification tied to an exact image/evidence ID. Disagreement clears actionable analysis; late answers cannot modify a newer hand. Offline model leaves the fast path available. | Implemented; one request, image identity and disagreement gate |
| R8: provider evaluation | Private reported fixtures + original varied artwork + licensed public simulators, disjoint development/test sessions. Measure exact-hand accuracy, false advice, duplicate/missed exposures, final count drift, phase errors and p95 latency per provider. | Private/original regressions complete; licensed held-out sessions pending |
| R9: Texas Hold'em analysis | Reuse capture/replay/UI; independent 52-card identity, seven-card ranking, explicit opponent ranges, pot odds and equity. No claim of optimal betting from equity alone. | Implemented; independent ranking and equity, 6,000 Treys pair comparisons |
| R10: poker visual sessions | Board/hole cards, seats, active player, street, stack/pot/action OCR; multi-hand replay and licensed footage. No automatic hidden-card inference. | Calibrated hole/board image/video implemented; seat/stack/pot/action OCR pending |
| R11: delivery | Full regression suite, source/frozen/native/installer checks, English/Italian guide, versioned public release, checksums and updated desktop shortcut. | 1.1.0 source, Windows and public delivery verification |

Each row closes only after its acceptance evidence exists. A screenshot sequence
does not prove continuous real-world capture, and a synthetic fixture does not
prove an unseen provider. The release report retains remaining limitations.

The original laboratory covers rules, an independent mathematical core, observed-state reconstruction, counting, replay, experiments, reference comparisons and Windows distribution. Version 1.0 adds immediate advice, multi-table observation, image/manual input, complete offline basic-policy combinations and the dark English-first product. [Requirements and evidence](docs/REQUIREMENTS.json) are authoritative; historical failures and unexecuted optional models remain explicit.

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
| V23: international distribution | English default UI, English GitHub imagery/docs, optional Italian selection, versioned Windows artifacts. |

| V24: every valid player turn | Immediate legal basic policy; finite/sampled results override only within their declared precision contract. No partial-analysis headline. |
| V25: aces and strategy library | Active ace 1/11 values, alternative hard total; hard/soft/pair/natural tables and all 550 starting combinations. |
| V26: five tables | Independent names, rules, observers, counts and per-table calibration. Shared display selected once. Tables are registered explicitly; no universal automatic table locator. |
| V27: image/manual input | Paste/drop/upload image, automatic lab-artwork recognition, confirmed cards and observed-history/split context. |
| V28: onboarding and modes | First setup, short guide, configurable reuse prompt, standard/simple/custom rules and five deck counts. |
| V29: design | Original black/graphite/gold identity, compact advisor, advanced details, smooth motion and reduced-motion support. |
| V30: optional extension | Scoped Chromium active-tab image capture, clipboard and loopback-only analysis. Source tests pass; unpacked browser installation remains a manual check. |
| V31: Clef | Separate pinned CUDA environment and offline-safe bridge; actual model results are recorded in docs/CLEF.md. Independent visual verification remains optional and cannot write cards/counts. |

## Next research

Validate a trained detector on licensed external card artwork and multi-session footage; evaluate count drift and never-detected-card failures before claiming broader support. Compare local phase/anomaly classifiers, including Clef/Laya, on actual hardware. A model announcement is not a benchmark. Optional pre-deal betting-edge analysis needs its own information/EV contract and tests; current live EV describes the active decision.

The full original planning text and acceptance history are retained in [the historical roadmap](docs/history/v0.1-ROADMAP.md). Historical artifacts keep their original languages and measurements; they are not silently translated into new numerical claims.

## Remaining acceptance gates

[Provider matrix and measured boundaries](docs/RELIABILITY.md) and
[Hold’em assumptions](docs/POKER.md) define the next work. Complete licensed
held-out sessions, provider-specific final count drift, multi-hand active-seat
recognition, trained detector validation and automatic poker betting-state OCR
remain open. Neither “10/10” nor a universal bulletproof claim is an acceptance
criterion. No unexecuted experiment is marked complete.
