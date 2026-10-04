# R1 reader comparison — runnable, API experiment blocked

The accepted [master plan](MASTER_PLAN.md) prioritizes a calibrated local/API
comparison before additional training. This increment implements the observation
contract, native input preparation, local baseline, Responses API adapter, and a
private comparison runner. It does not connect API responses to the live advisor.

## Current zero-budget policy (2026-10-04)

The user's latest instruction overrides the earlier paid-pilot next step.
Inference allowance is **zero requests / $0**. The user reports having saved a key;
key presence, old crop approvals, purchased balance or free credits are not permission.
No inference, model-list account call, image upload or billing modification was
performed in this follow-up.

Read-only [Billing overview](https://platform.openai.com/settings/organization/billing/overview)
redirected to login. Balance, free-credit balance and auto-recharge are **unknown**,
not zero or disabled. Record `blocked_credit_verification`; use
`blocked_no_free_credits` only after verified absence. Whether a test can consume
only existing free credits cannot currently be established. The inference block is
independently `blocked_zero_api_budget`.

The real transport reads the matrix's `api_access_policy` before every inference
network request and denies when missing, malformed, revoked or zero. A future
positive allowance must have fresh explicit consent and a new authorization epoch;
the runner binds the crop approval to that epoch, so previous approval files cannot
reactivate inference. Injected test transports have no billing capability and are
contract tests only. This local guard does not control other applications or
guarantee a provider billing cutoff.

No payment method, credit purchase or auto-recharge change is authorized.
[OpenAI prepaid billing documentation](https://help.openai.com/en/articles/8264644-setting-up-and-managing-prepaid-api-billing)
explains that credits fund billable use and cutoff/accounting can be delayed.
Continue native input preparation, schemas, local metrics, annotation protocols and
candidate source review; no new training or installation is required by this override.

## Actual result

The historical digital screenshots were prepared and read locally. Three inputs
represent **two game moments**; one is a repeated preview. They are consumed
development regressions, not new sessions or a holdout. The annotation review is
historical assistant review, not independently checked human truth.

| Measure | Local result | API result |
|---|---:|---|
| Exact rank/presence states | 3/3 | Not executed |
| Correct usable conditional rank-study states | 1/3 | Not executed |
| Known suits correct / unknown readable suits | 4/9; 5 unknown | Not executed |
| Complete card states, including suits | 0/3 | Not executed |
| Complete state accuracy, including phase | Not measurable: phase unannotated | Not executed |
| False accepted rank states in this finite sample | 0 | Not executed |
| Original complete provider sessions | 0 | Not executed |

Freegames remains blocked by touching ROI edges and unresolved proposals.
BrainPlay is usable only as **conditional rank study**, with configured rules and
unknown turn/history. This is not autonomous current-turn advice or count acceptance.
The reader was not tuned against these three images during this increment.

The three retained local runs are integration checks; the final run binds the
completed field accounting and full observation/conditional-math timing. It is not additional independent evidence
or evidence of a detector improvement. [Aggregate receipt](../validation/results/r1-reader-comparison/local-summary.json)
binds the exact input manifest, evaluator annotations, source hashes and OCR checkpoint.
Timings include cold initialization in the first state, prepared input to validated
observation and conditional analysis, excluding capture/display. Their sample size
is three. Do not compare their p95 directly to older warm/profile-only measurements.

## Contract and gates

`bjlab/state_reader.py` preserves readable, covered, unreadable, empty and uncertain
states. Native table/dealer/player crops share one source identity; no detector
pre-filters which cards reach the API. Both readers receive the same prepared
frame/calibration. Evaluator labels live in a separate oracle file.

API input is calibrated image context plus native details, with no tools, IDs,
strategy or ground-truth phase. The output is strict JSON observations; schema
validity is not truth. Refusal, timeout, invalid schema or incomplete output produces
an unavailable observation, never an empty hand. Equal card ranks remain separate
objects. An unknown suit does not block otherwise sufficient blackjack rank study;
it does block the suit-dependent card capability. This is not a full poker reader.

Conditional analysis reuses the existing mathematical engine, reports its configured
rules, and never applies a count deviation from unknown history. Unknown phase is
acceptable only for hypothetical image study; observed dealer/waiting/settled phases
block advice. Live and shoe-history certification are always false in this adapter.

The old live stale timeout, observer, replay and native advisor are unchanged.
Frame buffering and current-state revalidation remain R2 integration work. No new
installer, new dependency, model download or paid request was performed.

## Reproduce local preparation and baseline

Run from the repository root. Use fresh output directories; existing receipts are
preserved. The source screenshots and historical private manifest are local only.

```powershell
.venv/Scripts/python.exe validation/tools/state_reader_comparison.py prepare --manifest artifacts/vision-research/private-cases.json --output artifacts/vision-research/r1-api-comparison/prepared-new
.venv/Scripts/python.exe validation/tools/state_reader_comparison.py compare --prepared artifacts/vision-research/r1-api-comparison/prepared-new --output artifacts/vision-research/r1-api-comparison/local-new
.venv/Scripts/python.exe -m pytest -q tests/test_r1_readers.py
```

`prepare` imports historical development stills only. It writes native PNGs,
`frames.json` (reader input), `oracle.json` (evaluation only) and `upload-review.json`
(**not approved**). Original monitor photographs are excluded. The runner remains
a development pilot; a session-disjoint verification corpus with human-checked
phase/controls and graphics families is still required before choosing a reader.

## Future API prerequisites — disabled now

1. Obtain fresh explicit user authorization for the exact scope and positive budget.
   Verify account credits/access read-only; do not probe with inference. A key is not
   authorization and must never be pasted into chat.
2. After approval, verify the selected model IDs read-only. Listing is not proof
   of image/strict-schema capability: verify the selected snapshot's official docs.
3. Review the prepared table and every detail crop. The user must explicitly approve
   those exact crops, model configurations and a maximum request/spend budget.
   Do not turn `upload-review.json` into approval merely because preparation ran.
4. Store the reviewed configuration/approval locally under ignored `artifacts/`.
   Update the existing matrix policy only to the approved scope and a fresh
   `authorization_epoch`; bind the approval to that epoch. Do not enable it now.

The following commands document the future workflow, not authorization to execute it.
```powershell
.venv/Scripts/python.exe validation/tools/state_reader_comparison.py list-models
.venv/Scripts/python.exe validation/tools/state_reader_comparison.py compare --prepared artifacts/vision-research/r1-api-comparison/prepared --output artifacts/vision-research/r1-api-comparison/api-run-001 --configuration artifacts/vision-research/r1-api-comparison/configuration.json --approval artifacts/vision-research/r1-api-comparison/approval.json
```

Configuration contains `models`, one or two objects with explicit `model`,
`context_token_limit`, `input_usd_per_million`, `output_usd_per_million`,
`pricing_source`, `max_output_tokens`, `timeout_seconds` and `detail`. Prices and
the input/context ceiling must be audited against current official model docs
before authorization. No default model or placeholder rate is used remotely.

Approval contains `approved: true`, a unique `authorization_id` (8–80 safe letters,
digits, underscores or hyphens), `spending_authorization_epoch` matching the newly
approved matrix policy, `configuration_sha256`, `prepared_manifest_sha256`,
`expires_utc` with timezone, the complete `image_sha256` list, the exact `models`
list, `max_requests` and `max_usd`. Bind both images **and geometry metadata**.
The approval is one-shot in its prepared directory; a new output directory does
not reset permission. Do not copy an already consumed preparation to evade that
ledger. Failed attempts consume reservations; a new run requires new authorization.

Every request reserves full-context uncached input plus capped output at audited
rates. This conservative estimate may substantially exceed actual usage. It is a
client guard based on verified prices/ceilings, not an OpenAI billing hard cap.
No automatic retries or tools; possible failed charges are never refunded to this
run's reservation. Unexpected usage above the audited ceiling stops the budget.
The account/project spend controls must also be reviewed before paid work.
If the reservation covers long context, audit the higher long-context rates rather
than multiplying the full model context ceiling by short-context prices.

Model ID returned, token usage, retry count, full completion timing, price-based
cost and cost per correct useful state are recorded. Missing usage stays unknown.
`store=false` is sent; it is not a guarantee of zero retention of all kinds.
Responses, diagnostics, images and approvals remain private; publish aggregate
results only after review. Do not commit keys, data URLs or raw provider errors.

## Executed checks

Zero-budget follow-up: **504 tests and 10 subtests passed** (60.09 seconds),
including 12 new denial/epoch policy cases; two existing warnings remain.
Before the final local-report refinement, 52 targeted reader/policy tests passed.
No real network inference was used by these contracts.
[Current source receipt](../validation/results/r1-reader-comparison/zero-budget-policy-checks.json).

Historical initial M1 at `048c2c8`: **492 tests and 10 subtests** (55.86 seconds).
The evidence consistency check passed. Of those tests, 40 were the new reader and
runner contracts, using injected transports rather than paid API calls. Two existing
warnings were emitted by FastAPI/Starlette and PokerKit. No frontend or native
application changes were made. [Source-check receipt](../validation/results/r1-reader-comparison/source-checks.json).

## Acceptance and remaining work

Before independent verification, freeze input assistance, snapshots/prompts,
annotations, acceptance criteria and request budget. M1's initial target is >=95%
correct useful supported states, no visibly wrong accepted state in the observed
sample, and p95 complete validated request-to-result <=5 seconds for image/replay.
Report abstentions, failed requests, missed/extra objects and uncertainty, not only
successful rows. These three old stills cannot certify those targets; full-state
accuracy is unknown when required annotation fields are absent.

Current decision: **inconclusive, no reader promotion**. API inference is explicitly
blocked by zero budget. Credit/access verification, account model availability,
exact-crop consent and fresh explicit allowance remain prerequisites. Original
video is required for R2, not this M1 pilot. At most two targeted corrections after
the actual comparison, then an explicit local/API/hybrid/neither decision.

## Reference scan (no installation)

- [geaxgx/playing-card-detection](https://github.com/geaxgx/playing-card-detection):
  README describes labeled printed corners and dataset generation for YOLOv3.
  Relevant to future annotations; no code, dataset or checkpoint imported.
- [roboflow/blackjack-basic-strategy](https://github.com/roboflow/blackjack-basic-strategy):
  a visual basic-strategy demo. It is an implementation reference, not an evaluator
  or evidence that our session reconstruction works. No dependency imported.

API implementation follows [Images and vision](https://developers.openai.com/api/docs/guides/images-vision)
and [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Before actual requests also review [API data controls](https://developers.openai.com/api/docs/guides/your-data).
Other candidates remain conditional in the master plan and experiment matrix.

## Proposed API models and illustrative future cost — not executed

Documentation checked 2026-10-04. At most two candidates:
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) as a cost-focused
reader and [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
as a stronger comparator. Both document image input and structured output;
neither documents native video input. Account availability and actual card-reading
quality remain unverified; no runnable configuration or consent has been created.

| Proposed reader | Standard uncached input / 1M tokens | Output / 1M tokens | Hypothetical one request |
|---|---:|---:|---:|
| gpt-6-luna | $0.10 | $0.50 | $0.001 |
| gpt-6.1-sol | $2.00 | $10.00 | $0.020 |

Source: [official pricing](https://developers.openai.com/api/docs/pricing).
Example assumes **5,000 total billable input tokens (including images) and 1,000
total billable output tokens (including reasoning)** per request, Standard processing,
short context, no tools or regional premiums. Three requests per model would be
$0.063 under those assumptions. These token counts have **not** been measured on our
crops; this is arithmetic, not a guaranteed quote or spending cap. Image detail,
reasoning, failed requests, processing tier and context can change actual cost.
The current full-context client reservation is substantially higher; future
authorization must audit it, including applicable long-context prices, before any
request. Current authorized budget remains $0 regardless of this example.

Conditional source reviews added to the existing matrix:
[LocateAnything-3B](https://huggingface.co/nvidia/LocateAnything-3B) for grounding
(checkpoint card limits use to non-commercial academic/non-profit research), and
[Vision Agents](https://github.com/GetStream/Vision-Agents) for orchestration
(Apache-2.0 code; services/models may have separate costs/rights). Neither is a
tested card reader, an installed dependency or a reason to migrate frameworks.
