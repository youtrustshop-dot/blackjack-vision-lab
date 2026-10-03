# Blackjack reliability and progressive response â€” 1.1.1

This increment preserves 1.1 functionality and addresses the three reproduced
audit findings on `f4f757909dccb7db62a5d2fa39118e7426a9ed2f`. It does not change the
recognition model or extend the experimental Texas Hold'em engine.

## What changed

Validated current-hand pixels and declared rules produce basic strategy without
running Monte Carlo in `LiveObserver.process()`. A separate analysis endpoint can
later supply outcome estimates or a resolved composition action. Unresolved
estimates, timeout and worker saturation retain the usable basic action.

Every estimate belongs to a source and state generation. A changed hand, source
stop or video discontinuity cancels the old computation. The server rejects an
obsolete state with HTTP 409; the browser also rejects results from an old
source/state/motion generation. Fetching estimates does not refresh video age.

The server admits at most five frame jobs, one per stream, and two live estimate
jobs, with no waiting queue. Slots remain occupied until the real worker finishes,
including after HTTP cancellation. Live estimates use a **1,200 ms cooperative
budget**. This is not a hard process kill or a guaranteed browser response time:
native OCR and scheduler delays can exceed it. Frame upload has a five-second
budget; image size and pixel limits remain enforced.

The response distinguishes three histories:

| History | What is known | Displayed count and inventory |
| --- | --- | --- |
| Complete | A declared/witnessed fresh shoe and intact observed history | RC, TC and physical remaining cards can be available |
| Partial | Intact observations since connecting; earlier shoe history unknown | Observed RC only; TC and physical remaining cards are `null` |
| Compromised | A gap, unknown removal or ambiguous tracking | Reliable counts withheld; reasons preserved |

`observed_running_count` records the observed tally without certifying complete
history. `conditional_inventory` is a separately labelled assumption-based model;
it is not a physical inventory claim. The nested state also withholds unknown
physical remaining cards. Hi-Lo composition comparisons and insurance estimates
require complete reliable history. A visible missed lab round or an observation
gap invalidates history; only a known new shoe restores it.

Current version and test counts are checked automatically by
`scripts/check-evidence.py`, including in CI. The original inconsistent 1.1
summary remains under a clearly named historical field rather than being erased.
The visible application version is imported from the frontend package, avoiding
another stale hard-coded footer version.

## Reproduced before, checked after

| Case | Unmodified 1.1.0 | 1.1.1 |
| --- | --- | --- |
| Start mid-shoe without declaring a new shoe | TC displayed as 0.25490196078431376 | TC and physical inventory withheld; base action remains |
| Slow live estimate | Estimate called before base response | Blocked estimate cannot delay the base response |
| Observation gap | Physical remaining cards displayed as 204 | Physical inventory and reliable count withheld |
| Current evidence metadata | Version 1.0.0 and 23 frontend tests conflicted with 1.1 evidence | Version 1.1.1, 382 Python tests + 10 subtests, 40 frontend tests |

The four initial regressions fail on the unchanged baseline. The expanded
12-case progressive suite passes, including outdated work, stop/cancellation,
capacity limits and cooperative deadlines. See the retained XML and JSON in
`experiments/live_reliability/` and the machine-readable
[verification record](LIVE_RELIABILITY_VERIFICATION.json).

## Executed verification

- **382 Python tests + 10 subtests passed** in 59.53 seconds; the existing
  Starlette/httpx deprecation warning is retained. Pytest JUnit counts 392 cases
  because it includes subtests.
- **40 frontend tests passed**; TypeScript and Vite production build passed.
- Actual headless Chrome with the real local API and owned canvas video verified
  base advice before estimates, independent estimate polling, the inline floating
  advisor, unknown mid-shoe count and five simultaneous isolated sources.
- The first Chrome run exposed a timer receiver error missed by Node tests.
  `browser-failed-timer.json` retains that failure; a receiver regression test was
  added and the final `browser.json` passes with zero page errors.
- Captured five-table processing readings were 59â€“120 ms at the sampled points.
  They are individual observations, not a p95 latency guarantee.
- Frozen backend, native launch/shutdown, installer and portable-package results
  belong to the versioned `release/v1.1.1/` records, each bound to artifact hashes.
  The source test record does not substitute for these executable checks.
- A preliminary native test ran concurrently with an installer/native test and
  failed temporary-file cleanup after WebView2 kept a file locked. The failure
  remains in `desktop-concurrent-cleanup-failure.json`. Final Windows tests run
  sequentially; no unrelated browser processes are terminated.

## New complete synthetic sessions

Three new fixed-seed sessions contain 30 complete rounds, 104 stages and 624
observations. English/Italian artwork and scales 1.0, 0.8 and 0.6 are included.
Rules are four decks and hit/stand-only. The observer receives pixels, declared
rules and monotone timestamps, without shoe/round identity labels or truth hints.
The unchanged baseline and candidate process the same immutable manifest.
Thresholds were set before evaluation: useful coverage at least 95%, zero falsely
confident advice and a 2,200 ms simulated decision window.

The public `experiments/live_reliability/session-manifest.json` records the fixed
truth labels and image digests. To reproduce, generate the same fixtures into a
new directory with `validation/tools/live_session_benchmark.py generate`, then
use its `run` command for each source checkout and
`validation/tools/assess_live_sessions.py` for the retained count assessment.
Private screenshots are not part of this dataset.

| Metric | 1.1.0 baseline | 1.1.1 candidate |
| --- | --- | --- |
| Timely correct basic decisions | 44 / 44 | 44 / 44 |
| Useful decision coverage | 100% | 100% |
| Falsely confident action frames | 0 | 0 |
| Final observed-card deficit, by session | 1, 4, 4 | 1, 4, 4 |
| Final reliable running count | Withheld in all three | Withheld in all three |
| Complete count accuracy accepted | **No** | **No** |

This is a new sequence from an existing development renderer, **not held-out
external provider footage**. Its oracle reuses the core basic strategy, so it
tests visual/state integration rather than independently proving the mathematics.
The useful-coverage acceptance covers basic actions only. Missing exposures,
ambiguous tracking and end-stage count abstentions remain in the reports. Zero
falsely confident end-stage counts is a sampled check, not an all-frame count
certification. These results do not show improved visual accuracy.

The report's offline frame-processing measurements exclude capture, network and
browser presentation. Simulated decision time includes scheduled frame intervals;
it is separate from wall-clock browser latency. These measurements establish
neither universal real-time performance nor profitability.

## Not executed or not certified in this increment

- Authorized independent full sessions from external providers, arbitrary artwork,
  every-frame event recovery and perfect shoe reconstruction.
- The user's display picker, detached OS advisor dragging, mixed monitor DPI or
  sustained five-provider capture on this computer.
- A new Clef ablation, new detector training or any new model installation.
  Existing Clef evidence remains separate and unchanged.
- A new economic/rake experiment, guaranteed betting edge or Poker strategy
  expansion. Existing finite-shoe and reference tests were rerun in the suite.

The release improves response ordering, history honesty, obsolete-result rejection
and bounded work. It does not certify a universal "10/10" vision system.
