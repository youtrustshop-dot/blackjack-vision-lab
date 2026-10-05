# Fresh paired cloud comparison: offline preparation

VISION-021, 2026-10-05. Parent PR15 / `a5ea454`. **No provider requests,
credential loading, authorization amendment, budget reservation or inference.**
PR13–15 reports and execution sources remain historical. Desktop 1.1.1, local
weights, production readers, Poker and every sealed final holdout are preserved.

## Deliverable

The offline generator prepares **32 new owned stills**, 16 development and 16
validation, from **six naturally shuffled physical simulator sessions**. It
does not reuse the old rigged diagnostic hand sequence. Seeds, physical hand
groups and font/palette families do not cross partitions. Six distinct card
fonts are used: Corbel, Bahnschrift, Candara, Franklin Gothic Medium, Impact and
Segoe Print. Layout, rectangular artwork renderer, control font and suit glyphs
remain shared. This is fresh evidence within our renderer, **not proof of
external-provider transfer**. Six source sessions are not 32 independent trials.

Both partitions cover clean cards, labelled totals, unlabelled/decorative
numbers, backs, overlap, miniature-card negatives outside the table zones,
rotation, clipping with a visible opposite index, a rank-only partial index,
popup occlusion, fading/blur, disabled controls, terminal state, table clear,
distribution and the next decision. The last four form an observable transition
from consecutive natural rounds, with no simulator phase/ID entering a request.
They are sampled stills, not a full continuous-session or R2 benchmark.

| Prepared partition | Inputs | Source sessions | R1 decision opportunities | Annotated objects |
| --- | ---: | ---: | ---: | ---: |
| Development | 16 | 3 | 11 | 61 |
| Validation | 16 | 3 | 11 | 60 |

Development visibility: 47 readable, 12 backs, one partial, one unreadable.
Validation: 46 readable, 12 backs, one partial, one unreadable. These are
**annotations, not detector scores**. The truth combines engine-driven evidence
masks and assistant inspection of both contact sheets plus native difficult
crops. It is a geometric visibility proxy, not independent human annotation.
The covered card retains presence with null face data; a partial index retains
its visible rank and null suit. A popup hiding every index closes R1.

Sixty-four request bodies are serialized locally: two candidates for each input.
All four native PNG views are byte-identical across providers, without upscaling.
Only calibration and pixels enter the payload. Card IDs, source session/hand,
oracle labels, expected actions and annotations stay in evaluator files.

| Candidate | Prepared wire contract | Local contract |
| --- | --- | --- |
| Luna Fast | Compact `grounded-r1-live-v3`, `reasoning=none`, max output 1024 | Strict `LiveObservation` and existing semantic gates |
| Gemini Flash Lite | `structured-card-limit-local`; remove only `/properties/c/maxItems` | Identical strict validation; max 52 cards, reject extra fields, provenance/visibility/integrity gates |

PR14 JSON mode is a retained reference, not an additional candidate. The Gemini
schema difference is already established; no further bound probes are planned.
No quality, latency or hybrid result is invented for the new inputs.

## Freeze and common evaluator

Private artifacts: `artifacts/paired-cloud-preparation-20261005-frozen/`.
Images, masks, oracle, raw requests and local model paths remain ignored. The
public [summary](../validation/results/paired-cloud-preparation/summary.json)
contains aggregate counts, file hashes and the proposed plan only.

`freeze.json` SHA256:
`d6fe0f0b41f624a717719ebccb3d35222d1fb4b534e1426b329d500ab4dbcbfe`.

The freeze binds sources, prompt, both schemas/configs, font files, native crops,
annotations, requests, plan and the unchanged local manifest/ONNX weights.
The checker rejects altered pixels, annotations, payloads, source or weights.
An external reviewed freeze hash detects replacement of the manifest itself.
The CLI has no final-holdout option and no submit/authorize operation.

The common evaluator measures strict validated/attempted, complete state,
exact card inventory, ranks, suits, backs, phase, controls, numeric provenance,
correct abstention, usable/timely R1, semantic false accepts and accepted inexact
card inventory. Failures retain their expected card denominators. Unknowns are
distinct from wrong reads; known unsupported suit tuples count as errors.
Blackjack rank-only usability remains distinct from complete card recognition.

Inventory errors are multiset **semantic tuple** mismatches; a wrong read creates
a missing and extra tuple. They are not a measurement of spatial localization or
physical identity. Suit matching includes rank/role because the compact contract
has no spatial identifier. These limits prevent exaggerated detector claims.

Numbers match value, role, copied label and actual containing native view. The
same number may legitimately be observed in table and dealer/player detail; only
views containing the complete annotated number/label box are accepted. A
mathematically plausible invented total still fails provenance. Omission of an
irrelevant session badge reduces full transcription, not automatically R1.

Reports retain planned, attempted and unexecuted counts, failures and timeouts.
Latency p50/p95/max uses **complete validated observations**, not first token;
censored failures are reported beside it. There are separate condition/session
groups. No interval treating correlated frames as independent is claimed; only
three validation source sessions cannot certify broad generalization.
Contract fixtures are explicitly marked as not model-quality evidence.

## Exact proposed counts and worst-case budget

The canonical ledger is unchanged at **94/102 reserved lifetime attempts**,
USD8 aggregate ceiling, USD5.0871906 upper accounting, including thirteen uncertain
charges. The unused eight diagnostic slots are **closed**, not permission to
infer. Remaining accounting margin: **USD2.9128094**; this is not a credit balance.

The unchanged audited per-attempt reservations are Luna Fast **USD0.526536** and
Gemini **USD0.3171328**, based on whole model context/max output and upper price
multipliers. These are conservative reservations, **not expected charges**.
Prices/model access must be reverified before future execution. No assumption
that a timeout/HTTP400 is free, and no uncertain reservation is released here.

| Proposed stage | Maximum new requests | All-uncertain reservation upper | Fits current money margin? |
| --- | ---: | ---: | --- |
| Initial paired smoke | 6 | USD2.5310064 | Yes; still needs fresh authorization |
| All 16 validation stills, both candidates | 32 | USD13.4987008 | No |
| Conditional winner hybrid | 5 | USD2.63268 | Only if preceding measured results and remaining ledger permit |
| Initial six + conditional hybrid | 11 | USD5.1636864 | Not guaranteed |
| Full validation + conditional hybrid | 37 | USD16.1313808 | No |

The initial three inputs are `labelled-totals`, `rotation`, `transition-after`,
one from each validation session. Both providers receive each input once.
Zero retries, paid warm-ups or development submissions are proposed. This smoke
is useful for a paired diagnostic, not full R1 acceptance. Future execution may
settle **audited reported usage** after success and admit later reservations, but
the plan does not promise the complete experiment within the current margin.
If a reservation cannot fit, stop; no ledger reset, cap increase or purchase.

## Conditional actual hybrid experiment

This is a frozen **plan, not an executed hybrid**. The winning cloud candidate
must first pass paired correctness, zero semantic false accepts/unsupported
suits, deadline/failure checks and the budget gate. Warm the frozen local model
and owned capture path without truth injection. Use a scoped persistent HTTPS
session, verify connection reuse, and count the cold first attempt. Existing
historical transport opens a new client per call; it is not rewritten here.

Five proposed trials: three stable warm inputs from separate sessions, then one
table-change and one source-disconnection during an actual pending response.
Use a genuinely measured local fallback trigger; if local succeeds, record that
route rather than force a cloud call using oracle knowledge.

Measure capture, local, routing/reservation, DNS, TCP, TLS, upload, response
headers/body, parse, strict/semantic validation, current-state revalidation,
solver and advisor serialization. Unobservable DNS/TCP subdivisions remain null;
response wait includes server and network time, not pure provider computation.

Preserve **capture-to-advisor <=3s**, sample target p95 <=2.5s, and <=250ms current
capture gap. Each API timeout uses the remaining original monotonic deadline;
local work does not buy another three seconds. Independently advancing capture
continues while cloud is pending. Pixel/source/table change, disconnection,
expiry or freshness loss rejects presentation; drawing again cannot refresh
evidence. Revalidate before and after deterministic solver serialization.

The measured advisor boundary would be **headless serialization**. Physical
desktop capture, native paint, minimizing/monitor/DPI checks remain separate
unexecuted tests. Three warm successes could demonstrate this bounded path,
not universal stable live behavior or a profitable strategy.

Select by false accepts, correctness, useful coverage, complete end-to-end
latency, failure rate, cost, then complexity. Conclude local-only, Luna fallback,
Gemini fallback, scoped hybrid demonstrated, cloud offline/replay, or R1 still
unverified. R2/ByteTrack/BoT-SORT/AMADEUS/SAM and Poker stay outside this increment.

## Offline reproduction

Verify the retained workstation artifacts (no network/credentials):

```powershell
.venv/Scripts/python.exe -m validation.tools.paired_cloud_prepare check --output artifacts/paired-cloud-preparation-20261005-frozen --expected-freeze-sha256 d6fe0f0b41f624a717719ebccb3d35222d1fb4b534e1426b329d500ab4dbcbfe
.venv/Scripts/python.exe -m pytest -q tests/test_paired_cloud_prepare.py
```

Create a separate private reproduction, requiring the declared Windows fonts
and retained local model receipt; never overwrite a freeze:

```powershell
.venv/Scripts/python.exe -m validation.tools.paired_cloud_prepare prepare --output artifacts/paired-cloud-reproduction --reader-manifest D:/CodexResearch/blackjack-vision-lab/specialized-card-reader-20261004/learning-full/reader.json
```

Future retained responses can be scored offline with `evaluate --output ...
--split validation --results ...`. The result envelope binds the freeze hash,
candidate, case, exact payload-file hash, status, duration and observation.
Wrong bindings/duplicate attempts fail; malformed observations remain failures.
`actual-provider-responses` and `contract-fixture` must be explicitly separated.
This evaluator does not authenticate a billing receipt or authorize inference.

Current delivery stops at offline readiness. No model is promoted and no new
API batch starts without the user's next explicit bounded authorization.
