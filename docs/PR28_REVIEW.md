# PR #28 review — preserve the acquisition clock

Reviewed 9 October 2026 against PR #27 (`3c23ea3`), with initial
candidate `c0763226148aad511a4643641ef7d9fe356c08b6`. This is a source
review and a networkless corrective increment, not another vision experiment.

## Finding and repair

**P2, corrected:** the HTTP capture handler calculated browser acquisition age
before dispatching to the worker, but `IntegratedR1Session.capture` subtracted
that age from the clock **after** image decoding and frame preparation. Worker
queue and image-processing delays therefore moved the apparent capture forward.
This could keep old evidence within the original three-second budget incorrectly.

The handler now supplies its own monotonic receipt before threadpool dispatch.
Direct callers also anchor their receipt before image decoding. The original
capture is derived once from that receipt and the measured browser age;
`received_ns` and `ingested_ns` are kept separately. Decoding, queuing, local
reading and cloud work all consume the original evidence lifetime. No longer
timeout, gate relaxation, clock override or current-state renewal was added.

The retained [clock reproduction](../validation/results/pr28-review/capture-clock.json)
executes the old source from the reviewed Git commit and the corrected source
with fabricated four-second clock advances on an owned white PNG:

| Controlled case | Before | After |
| --- | --- | --- |
| Decode / preparation delay | Capture shifted forward 4,000 ms; accepted as current | No shift; rejected as stale and expired |
| Worker queue with 90 ms browser age | Capture shifted forward 4,000 ms; accepted as current | Original browser age retained; rejected as stale and expired |
| Actual capture endpoint, fabricated dispatch delay | Missing boundary propagation | Original server receipt reaches the capture worker; expired |

These are deterministic clock/endpoint regressions, not real latency, independent
model-quality observations or provider calls. The three new tests exercise
processing time, queue time and the HTTP boundary. No empirical performance
improvement is inferred.

The full Python suite passes **984 tests + 10 subtests**, with two existing
warnings, in 122.55 seconds. The unchanged frontend's 52 tests/build from
VISION-034 remain separate prior evidence; GitHub checks must pass again on
the corrected commit before any merge. No native build or provider inference.

## Scope and merge destination

PR #28 is stacked on `research/gemini-visible-phase-contract`, not `main`.
At the start of review GitHub reported it mergeable, with both Windows checks
passing, still in draft, no reviews, and 27 preceding stacked PRs open.
A merge into its existing base would only update that research branch.
This review does not grant blanket approval to integrate all previous PRs into
`main`; that broader destination must be explicit and its full diff reviewed.

The opt-in route/configuration, frozen owned-pixel boundary, original deadline,
source invalidation, single shared advisor state, private-output policy and
closed cloud scope were examined. No second unresolved blocking issue was found
in this PR's incremental diff. Review/testing cannot certify universal vision,
complete inventory, physical popup behavior or the entire preceding chain.

The original VISION-034 receipts, performance observations, 981-test verification,
source hashes and consumed source snapshots are preserved. Their recorded results
are not regraded as if this corrected implementation had produced them.
Forward verification lives in
`validation/results/pr28-review/verification.json`; the installed 1.1.1,
frozen holdouts, local weights, accounting and closed inference slots are unchanged.
No new API request, billing action, release build or installation is part of review.

