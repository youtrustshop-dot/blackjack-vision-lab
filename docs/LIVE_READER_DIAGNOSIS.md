# Compact grounded R1 and measured hybrid failures — VISION-018

Luna Fast's compact grounded contract produced three correct, usable R1 states
within three seconds on three new owned development scenes. Its sample p50/p95
was **1.99/2.13 s**. This permits a bounded hybrid experiment, not adoption:
only **1/3** responses included every annotated visible number, and the actual
local-first hybrid produced **no current advisor output** in its three trials.
Gemini remains blocked by an unlocalized HTTP400. No reader is promoted.

The [aggregate receipt](../validation/results/live-reader-diagnosis/summary.json)
includes failures, attempted denominators, trace timings and frozen source hashes.
PR11 and PR12 remain unchanged stacked drafts. This branch starts from PR12
`b4b95168aa0cd290b47e4e780c7450d11764283f`; the installed desktop remains 1.1.1.

## Scope and comparison

The same four native PNG views (table, dealer, player and controls), calibrated
regions, model `gpt-6-luna`, Fast tier, reasoning `none`, and 1,024-token ceiling
were used for each Luna schema. The request deadline covers payload construction,
reservation, network, complete provider JSON and observation validation: 3 s.
The predeclared hybrid gate additionally requires all three usable/correct R1
states, sample p95 <=2.5 s and no falsely accepted state. It does not require
complete transcription of unrelated UI badges. That separate metric is retained.

Three development scenes use physical seeds 6100511, 6100528 and 6100545; an empty
scene, seed 6100562, changes the evidence during the hybrid trial. Conditions are
clean UI, explicitly labelled totals and rotation. They share our owned renderer,
Arial rank font and suit glyph family: **these are not provider-transfer tests,
complete sessions, or independent population samples**. Each player scene has
three visible faces and a blue back. Geometric ink visibility plus an assistant
visual audit provides the scoring reference, not independent human annotation.
No phase, round ID, future state or oracle card is supplied to either reader.

Only reviewed owned native pixels were uploaded. No private provider screenshot,
final holdout, local retraining, threshold adjustment, Poker expansion, new model,
framework, desktop build or release replacement occurred.

## Still results

| Candidate | Validated JSON <=3 s / attempted | Correct usable R1 | All grounded fields correct | p50 / p95 / max, valid responses | Failure rate |
| --- | --- | --- | --- | --- | --- |
| Frozen PR11 v1, Luna Fast | 2/3 | Unsupported by the new grounded contract | Unsupported numeric provenance | 2.119 / 2.181 / 2.188 s | 1/3 |
| Frozen PR12 v2, Luna Fast | 1/3 | 1/3 | 1/3 | 2.745 / 2.745 / 2.745 s | 2/3 |
| Compact live v3, Luna Fast | 3/3 | 3/3 | **1/3** | 1.993 / 2.131 / 2.146 s | 0/3 |
| Compact live v3, Gemini Lite | 0/2; third not executed | Not measured | Not measured | No validated response | 2/2 technical failures |

Latency percentiles use only complete validated responses; the adjacent failure
denominator prevents a timeout from improving the apparent performance. With
three scenes, these numbers do not estimate production tail latency. Zero observed
false acceptances does not establish zero risk.

All nine exposed rank/suit pairs and three backs were correct for compact Luna.
The labelled player/dealer totals, 16 and 7, were correctly attributed. However,
`SESSION 20` was omitted on clean UI and labelled totals, making full-grounded
correctness 1/3. An omission is preserved, not relabelled as a correct UI reading.
The old v1 accepts common card/phase/control information on its two responses but
lacks the new numeric provenance; it is ineligible for the new advisor experiment.
V2 has a clean success, a labelled-totals timeout, and a rotation response rejected
by the number-region validator at `numbers[0]`. Its rejected response was accounted
from reported usage and was not counted as validated JSON; invoicing is unverified.

## What changed in the live contract

`grounded-r1-live-v3` keeps cards and roles, readable/partial/covered/unreadable
visibility, table presence, phase, visibly enabled actions and fixed blocker codes.
Numbers retain value, role, observed associated label and named native view.
Explicit English `PLAYER TOTAL` / `DEALER TOTAL` labels are still required for
total attribution; this restricted profile does not support arbitrary providers.
Labels remain model observations, not independent verification of label pixels.

The compact wire has short keys and no prose explanations, confidence, tracking
IDs or number coordinates. It does **not** fabricate a rectangle to satisfy v2.
The gate declares `observed_label_and_named_native_view` provenance and coordinate
support absent. Unknown objects and conflicts still close the appropriate gate.
Both providers receive the identical live schema and prompt. Google's documented
schema subset omits `maxLength`; string length is enforced locally after parsing
and is removed from both wire schemas. This does not change frozen PR12.

## Latency diagnosis, rather than a causal claim

| Per clean request | PR11 v1 | PR12 v2 | Live v3 |
| --- | --- | --- | --- |
| Native images | Identical four views | Same | Same |
| Prompt UTF-8 bytes | 799 | 1,147 | 1,094 |
| Compact JSON-schema bytes | 1,582 | 2,031 | 1,424 |
| Request bytes including images | 58,715 | 59,528 | 58,867 |
| Reported input tokens | Timeout: unavailable | 2,327 | 2,237 |
| Reported output tokens | Timeout: unavailable | 156 | 111 |
| DNS/TCP + TLS trace | 737 ms | 434 ms | 116 ms |
| Wait for response headers | 2,211 ms, timeout | 2,198 ms | 1,735 ms |

The prompt/schema together become smaller; output also shrinks. Observation
parsing/validation takes about 0.07–0.27 ms and is not the dominant observed delay.
But network establishment, request order, prompt and output all differ, and there
are too few requests to isolate schema length causally. Response-header wait mixes
provider generation/service time with network time. No first-token result is used.
Returned reasoning tokens are zero; the receipt preserves input/cache-write/cache
read/output counts. Cache and tier effects are not erased from the comparison.

## Gemini: exact diagnostic boundary

Before inference, a read-only model GET confirmed `gemini-3.5-flash-lite` and
`generateContent` support. The REST body was checked against Google's current
discovery schema, including `generationConfig.responseFormat.text`, JSON MIME,
thinking `MINIMAL`, and the trimmed JSON-schema subset. Local checks found no
unknown fields or invalid enum/types. This is a preflight, not server acceptance.

The first smoke input timed out during connection establishment; a distinct
predeclared second input returned HTTP400 `INVALID_ARGUMENT`. The candidate
stopped immediately; its third input was not submitted. No identical request was
retried. The saved error-body SHA256 matches a fixed public error JSON template
containing **“Request contains an invalid argument.”** Recovery required zero
provider calls and did not retain or print an error body, key or prompt.

There is no field-specific diagnostic. PR12's `maxLength` mismatch was a hypothesis;
removing it did **not** resolve this new request. The exact incompatible argument
therefore remains **unresolved**, and there is no Gemini perception-quality score.
The new sanitizer labels this fixed message `generic_invalid_argument`; it never
echoes arbitrary provider text. No more Gemini retries were made.

## Actual local → Luna hybrid

The compact Luna still gate passed before either cloud fallback was submitted.
The existing specialized reader and weights stayed frozen. A separate producer
delivered owned native pixels at nominal 12 FPS while the real cloud call ran.
The existing source/table/evidence timestamp checks and math were used unchanged.
Presentation is headless advisor-payload emission, **not native window paint or
real screen sharing**. There is no physical Windows capture/DPI/minimization claim.

| Trial | Local | Real API | Capture → headless boundary | Result |
| --- | --- | --- | --- | --- |
| Stable, first initialization | 578 ms | Not submitted | Not retained by frozen early-return path | Evidence became invalid before routing; no output |
| Table changes after 650 ms | 94 ms | Complete in 2,812 ms | 2,937 ms | Pixel/motion epoch changed; correctly withheld |
| Stable, after explicit warm-up | 47 ms | Timeout at 3,031 ms | 3,078 ms | Evidence deadline expired; correctly withheld |

The first run retained 11 capture updates but its frozen early return does not
record the exact invalidation predicate; startup-induced capture discontinuity is
a hypothesis, not a fully diagnosed fact. In the changed trial, 32 updates and a
motion-epoch change prove that a real API answer cannot become the current advice.
The warm trial excludes a documented 360 ms initialization, retains 33 fresh
updates with unchanged pixels, and spends 2,875 ms in DNS/TCP establishment before
timeout. The rest of the warm batch stops; it is not repeatedly retried until green.

**Three trials, two actual hybrid API submissions, zero presented states.** There
is no successful stable hybrid demonstration and no measured hybrid p95. The
changed-trial stale rejection is positive evidence for the guard, not positive
evidence for hybrid availability or R2 identity tracking.

### Caller deadline repair and executed versions

The first Gemini timeout took 11.35 s at the synchronous reader despite a 3 s HTTP
timeout: `asyncio.run` waited for its DNS executor during shutdown. This violates
the desired caller deadline and is retained as a failure. A small persistent
background event loop now lets the caller cancel and stop waiting without joining
the outstanding lookup on the critical path. It does not retry or publish a late
response. Process shutdown may still wait for OS/executor work, and scheduling
jitter is not zero; the supplemental trial's caller took 3.031 s.

The initial comparison source freeze is
`44e1a8b047c92c2a6ccc14248c414e13e536be7c0dcf95db1acdf23ec742fe3f`.
Its observations/scores are preserved. A separate warm/transport supplement,
bound to the same pixels, prompt, schema and weights, has freeze
`9e3060f0dfd363dca3d194290adf57a7bbe1ab68d4c910361839cca263dd2f15`.
All supplemental executed sources have byte-exact private snapshots. Source
changes are not presented as if the original cloud comparison used the repair.
After inference, a local-only guard additionally rejects unaudited returned
model/token usage before observation parsing; injected tests cover that path.
No cloud scores were recomputed with that guard or the new error classification.

## Budget, privacy and reproducibility

Eleven still submissions and two hybrid submissions used the existing keys and
the same lifetime EUR10 authorization, conservatively implemented as USD8/90.
These count real network attempts, not confirmed provider receipt: connection
timeouts can precede transmission of the HTTP body. Their possible charge remains
reserved rather than assumed free.
One earlier local policy failure reserved a slot but submitted nothing; its
zero-network proof settled the charge to zero and kept the lifetime slot. Setup
failures and the unsubmitted third Gemini scene are not model-quality samples.

The final ledger has **87 lifetime reserved attempts, 86 claimed network attempts**,
USD **3.8138512** accounted upper including **3.6379432** retained for nine unknown
charges. This is not an invoice or actual spend. Eight new responses report usage
with a price-based upper of USD **0.0055515**, including the invalid v2 answer and
withheld changed-table answer. Five new timeouts/errors have no returned usage and
remain conservatively reserved. No assumption that errors are free is made.
Runtime inference is disarmed after the bounded increment; the ledger is not reset.
No purchases, payment or recharge changes occurred. Private manifests, pixels,
response IDs, billing receipts and diagnostics stay under ignored `artifacts/`.

Offline preparation and request audit:

```powershell
.venv/Scripts/python.exe -m validation.tools.live_reader_diagnosis prepare --output artifacts/new-live-development --reader-manifest D:/CodexResearch/blackjack-vision-lab/specialized-card-reader-20261004/learning-full/reader.json
# Place the read-only REST discovery and model metadata in the new output directory.
.venv/Scripts/python.exe -m validation.tools.live_reader_diagnosis audit --output artifacts/new-live-development
.venv/Scripts/python.exe -m pytest tests/test_live_reader.py tests/test_grounded_reader.py -q
npm --prefix ui test
npm --prefix ui run build
.venv/Scripts/python.exe scripts/check-evidence.py
```

The executed paths are `artifacts/live-reader-diagnosis-20261005-authorized` and
`artifacts/live-reader-diagnosis-20261005-warmed`. `compare`, `hybrid`, and
`hybrid-warm` require a fresh exact-pixel upload review, source/weight/input freeze,
documental preflight, active epoch and the existing non-reset budget. Exclusive
claim files prevent rerunning an already-consumed batch. The current delivered
policy is disabled; these commands do not silently reauthorize inference.

Validation: **596 Python tests + 10 subtests, 52 frontend tests, frontend production
build and source-evidence consistency check passed**. Two pre-existing Python
warnings concern Starlette/httpx and a PokerKit fixture fold. One parallel targeted run failed an existing
wall-clock producer assertion (2 observed updates instead of >=5); the isolated
13-test rerun passed. That scheduling-sensitive failure is retained, not removed
by changing PR12's tests. Mocks prove contracts/deadlines, not provider quality.

## Decision and one next step

Retain compact Luna as an R1 research candidate, the bounded transport repair and
the negative actual-hybrid evidence. Do not promote a reader, installed release,
provider generalization or tracking R2. Gemini stays `blocked_invalid_argument`.
The next useful increment is **a bounded stable-hybrid transport/availability
test after local initialization**, with capture continuing and both image-content
and evidence-age checks intact. It must demonstrate current advice in time before
opening ByteTrack/BoT-SORT or claiming an operational hybrid. No new paid batch is
started by this report.

Official sources consulted on 2026-10-05:
[Gemini REST](https://ai.google.dev/api/generate-content),
[Gemini structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[Gemini Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[Gemini troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting),
[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization).
