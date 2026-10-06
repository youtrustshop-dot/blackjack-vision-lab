# Four new paired semantic requests and the conditional hybrid gate

VISION-025, 2026-10-06, based on PR18 `a4eb763`. **All four authorized
comparisons ran exactly once. Luna delivered 0/2 valid states before the deadline;
Gemini delivered 1/2. Neither passes the frozen 2/2 gate, so the conditional
hybrid was not started. No reader promotion or installed-release change.**

The remaining limitation is timely, strictly valid R1 availability. Luna waited
for response headers until expiry; Gemini's second response violated an explicit
numeric-label rule. This lot does not establish a working local-to-cloud advisor.

Public [individual results, metrics, trace and accounting](../validation/results/paired-semantic-hybrid/summary.json)
and [executed verification](../validation/results/paired-semantic-hybrid/verification.json).

## Scope frozen before inference

The existing renderer, native layout, prompt, compact wire schema, evaluator,
semantic policy `numeric-provenance-r1-v1`, local weights and math remain unchanged.
Two fresh owned natural-session states were frozen with new seeds/hand groups and
font/felt families. They were not used for training or threshold selection:

| Case | Session seed / artwork | Evidence |
| --- | --- | --- |
| `fresh-labelled` | 91006011 / copper, Verdana | Exposed indexes, overlap, blue back; explicit PLAYER/DEALER TOTAL and SESSION labels |
| `fresh-rotated-unknown` | 91006019 / indigo, Trebuchet | Rotated overlapping cards, blue back; SESSION plus a separate unlabelled UI number |
| Conditional-only `fresh-stable-hybrid` | 91006023 / pine, Georgia | New stable owned table; frozen but not submitted because no candidate passed |

The sessions and new font families differ from the consumed PR16 cases. The
renderer/layout, Arial controls and Segoe UI Symbol suits are shared. These are
two sampled states from two owned sessions, **not independent external graphics
or complete session tests**. Render visibility masks plus pre-call visual review
provide the reference; no independently collected real-provider truth is claimed.

Both candidates receive the same native table/detail pixel bytes for each case.
Provider-specific request envelopes are frozen separately. Images, payloads,
oracle and failure receipts remain ignored under
`artifacts/paired-semantic-hybrid-20261006/`; no private screenshots or credentials
are published. Original freeze SHA256:

`f81df70de7c4a86d1adb274e0a0169ee72aed3bd888e46e75e411a011b927b58`.

The gate requires 2/2 strict, timely, correct semantic R1 states; exact required
card inventory including backs in both; zero false accepts or unsupported known
suits; every state within 3s and two-case sample p95 <=2.5s. Eligible candidates
are ordered by semantic complete transcriptions, sample p95, reported-usage
upper cost, then name. No prompt, threshold, validator or selection rule changed
after seeing the responses. The final holdout was not opened.

## Individual outcomes

| Order / case | Requested candidate | Outcome | Complete capture-to-reader ms | Reported input / output tokens | Price-based upper USD |
| --- | --- | --- | ---: | ---: | ---: |
| 1 / labelled | GPT-6 Luna Fast compact | Timeout; no response headers or observation retained | 3016 | Unknown | Unknown; 0.526536 reserved |
| 2 / labelled | Gemini 3.5 Flash Lite structured-card-limit-local | Strict valid, semantically complete and usable R1 | 2343 | 4816 / 353 | 0.0023273 |
| 3 / rotated + unknown UI | Same Gemini | HTTP200; local numeric validation rejection | 2219 | 4816 / 260 | 0.0020948 |
| 4 / rotated + unknown UI | Same Luna Fast compact | Timeout; no response headers or observation retained | 3016 | Unknown | Unknown; 0.526536 reserved |

Fast was requested in Luna's frozen payload. No returned tier, usage or model
body was available before its deadlines. Both exact model metadata GET controls
succeeded with verified TLS; they are read-only access checks, not paid warm-ups.

The Gemini failure is **not HTTP400**. `LiveObservation.model_validate_json`
rejects `n[0]` with `value_error`; the corresponding `LiveNumber` validator
requires associated PLAYER/DEALER TOTAL words for an attributed hand total. No
observation passes that rejection. The reader retained only the output hash
`033c4a50a5ad8b6522fe6f5bca8fcc2f2b515a30240dc25b1222618a6e0022de`,
length 566 bytes, location and type. Its exact offending number/label was **not
retained and cannot be reconstructed from that hash**. We do not attribute it
specifically to the unlabelled `20`, repair it, or retry the provider.

Counts describe what reaches the strictly validated application boundary:

| Metric / attempted | Luna | Gemini |
| --- | ---: | ---: |
| Strict validated | 0/2 | 1/2 |
| Correct timely usable semantic R1 | 0/2 | 1/2 |
| False accepted states | 0/2 | 0/2 |
| Exact relevant inventory including backs | 0/2 | 1/2 |
| Delivered correct ranks / expected | 0/6 | 3/6 |
| Delivered correct suits / expected | 0/6 | 3/6 |
| Delivered backs / expected | 0/2 | 1/2 |
| Correct phase | 0/2 | 1/2 |
| Correct enabled controls | 0/2 | 1/2 |
| Exact semantic numeric provenance | 0/2 | 1/2 |
| Matched semantic numeric tuples / expected | 0/5 | 3/5 |
| Complete grounded semantic transcription | 0/2 | 1/2 |
| Literal exact JSON-field transcription | 0/2 | 0/2 |
| Timeouts | 2/2 | 0/2 |
| Other validation failures | 0/2 | 1/2 |

Failed/time-out observations remain in every denominator. Their zero delivered
card counts **do not measure what the models visually recognized in discarded or
unavailable JSON**. Zero false accepts reflects one accepted state in this tiny
sample, not zero risk. Literal exact-field matching is the preserved contract
that stores labels separately from values; it is not a character-level OCR score.
Gemini's valid response preserves combined observed strings and is semantically
correct after the shared, pre-existing normalization.

Among validated responses only, Luna has n=0 and no p50/p95/max. Gemini has n=1:
p50/sample p95/max all 2343ms. Its rejected but returned response took 2219ms.
The four individual times above are the relevant evidence; no operational p95
or definitive champion follows from this sample.

## Actual connection reuse and one absolute deadline

`bjlab/paired_persistent_http.py` adds an opt-in pool per fixed official origin
using the existing scoped OS DNS transport. Original Host/SNI and certificate
verification remain; proxies, redirects and retries are disabled. Fresh public
DNS answers expire even when a socket is pooled. An expired scope or late worker
closes the pool. Each POST is bound to a frozen payload and durable one-use claim
on the canonical ledger. No global DNS/router/hosts/certificate setting changed.

`bjlab/paired_deadline_reader.py` passes the **original capture + 3s** deadline
through payload, reservation, durable claim, HTTP, usage/model audit, settlement,
strict parse, semantic gate and receipt. An observation that expires during those
steps is discarded. The optional local-first path also includes routing, current
source/table/pixel revalidation, existing math and headless serialization, with
checks before and after serialization. It has no oracle argument or forced API
route. That hybrid path was verified with offline fixtures, **not real API in
this lot**, because no candidate met its prerequisites.

| POST trace, nested within full reader time | Luna labelled | Gemini labelled | Gemini rotated | Luna rotated |
| --- | ---: | ---: | ---: | ---: |
| New TCP attempts / TLS starts | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Body upload ms | 109 | 94 | 62 | 203 |
| Completed response-header wait ms | Not completed | 2234 | 2125 | Not completed |
| Complete-response reuse flag | False: timeout | True | True | False: timeout |

All four transmitted after an existing model-GET connection, with no new TCP/TLS
stage traced. Gemini demonstrates actual completed pooled responses, including
one later rejected locally. Luna demonstrates transmission on the existing path,
but no completed response reuse: the diagnostic flag deliberately remains false
on failure. Pooling did not make these two Luna calls meet the deadline. There
is no matched nonpooled control, so **no causal speedup is claimed**.

Header wait combines server and network time; their contributions and model
generation time are not separately observed. The recorded Windows Python3.12
`monotonic_ns` clock resolution is **15.625ms**. A stage reported as 0ms is below
that resolution; it is not free. The 3016ms timeout receipts include finalization
after expiry at 3000ms. No late state was made valid. Original timers are retained,
not recalculated using a different clock.

Cold setup is outside the subsequent captured-still clocks and is recorded
separately: original local initialization/first read 1234ms, scoped DNS 3485ms;
completion segment local 656ms/DNS2594ms; last-pair segment fresh DNS5594ms. Exact
GET and client-initialization traces for each segment are in the aggregate. These
varying startup observations are not a startup latency distribution or repaired-DNS
claim. The last segment has no local initialization because hybrid was already
ineligible; it only completes the remaining paired still.

## Controller stops and immutable evidence

The initial controller was too broad: it stopped after the first timeout. Its
completion controller then stopped after Gemini's audited HTTP200/local-validation
quality failure. Both receipts and executed controller sources are retained.
Separate one-use completion scripts ran only the three then the one **distinct
unused original comparisons**, under the same epoch/105-attempt/USD8 allowance.
There are four submissions total, not retries, new cases or a new batch.

Reader, pixels, prompt, evaluator and gate hashes stayed unchanged across all
segments. The last-pair controller specifically admits only the recorded three-row
checkpoint and `n[0]` quality failure with audited usage/HTTP200; other schema,
access or unverified-usage failures cannot use that continuation. It contains no
hybrid execution path. Offline audit reproduces all four scores, checks response
prefixes, one-use payload claims, historical/source/weight hashes and the closed
runtime, without socket/DNS/subprocess access.

## Canonical accounting and final stop

Current official [OpenAI prices](https://developers.openai.com/api/docs/pricing)
and [Gemini prices](https://ai.google.dev/gemini-api/docs/pricing) were checked
2026-10-06 before inference. The whole authorized worst-case reservation remained
USD2.2138736, within the original USD2.904214250 margin. Only the request ceiling
was auditably amended **102 ->105 from 100 consumed attempts**; the lifetime
USD8 prudential cap within the existing EUR10 authorization did not change.

| Accounting item | USD |
| --- | ---: |
| Four initial per-request reservations actually allocated | 1.6873376 |
| New upper charge derived from two reported usage records | 0.0044221 |
| Two new unresolved Luna timeout reserves retained | 1.0530720 |
| New accounted-upper increase | 1.057494100 |
| Final lifetime accounted upper | 6.153279850 |
| Included lifetime unknown-charge reserves, 15 attempts | 5.9595464 |
| Residual prudential margin under USD8 | 1.846720150 |

All original 100 entries and thirteen uncertain reservations are retained; two
uncertain timeouts were added. Ledger: **104/105 reserved lifetime attempts,
103 claimed network submissions**, including its unchanged historical unclaimed
attempt. Two new known-usage records are settled to the audited upper; neither
timeout is released without billing evidence. These figures are **not an invoice,
verified current balance or free spending authorization**.

No hybrid request, retry, paid warm-up, new key, purchase or recharge. The runtime
is disarmed with zero active request/money allowance; all pools close and the one
unused numerical slot stays closed. Final ledger SHA256:

`7793ff458df87b0abf10eca59f71a73e2be242a29c0687a82ae5c692be385895`.

No automatic next lot, new training/model/tracker, R2/Poker expansion, popup work,
installer, merge or release replacement follows this delivery. Physical Windows
screen capture/paint and session reliability remain distinct, unexecuted proofs.

## Offline reproduction

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_paired_semantic_path.py tests/test_numeric_provenance.py
.venv/Scripts/python.exe -m validation.tools.paired_semantic_prepare
.venv/Scripts/python.exe -m validation.tools.paired_semantic_audit
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
```

The two audit commands require the retained private freeze/receipts/canonical
checkpoint. They verify consumed data and perform zero provider requests. No paid
replay command is provided: every original and completion execution claim is
consumed, and their exact ledger preconditions no longer hold. The preserved
controller files are an execution audit trail, not permission to run another lot.
