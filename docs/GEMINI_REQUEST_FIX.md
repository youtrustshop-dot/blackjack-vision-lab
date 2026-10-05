# Gemini request diagnosis and JSON-mode workaround — VISION-019

Gemini generation and image reading now work in an **explicit research variant**.
The minimal text request completed in **0.962 s**. JSON MIME mode produced a
complete, locally validated hand in **1.993 s**, with three correct exposed
rank/suit pairs, one back, correct phase/actions and all three numeric roles.
The configured structured hand-schema path still returns generic HTTP400.

This is one reused owned development still, not independent verification,
session reconstruction, a latency percentile estimate or a promoted reader.
PR11/12/13 evidence, default readers and installed desktop 1.1.1 are preserved.
The [aggregate receipt](../validation/results/gemini-request-fix/summary.json)
contains all three new submissions, including the failed alternative.

## What was isolated

The user's billing screenshots show positive EUR5 prepaid credit, paid Tier 1,
the intended project and auto-recharge off. Billing/account identifiers and
screenshots remain private. A successful generation establishes usable access;
neither a model GET nor a delayed EUR0 spend chart alone would establish it.

| Probe | Configuration | Result | Complete response/validation time |
| --- | --- | --- | --- |
| Minimal text | Exact `gemini-3.5-flash-lite`; text, 64 output-token cap | Completed, expected response | 0.962 s |
| Compatibility image | Same four native views; legacy `responseSchema`, `responseMimeType`; no explicit thinking setting | HTTP400 `INVALID_ARGUMENT` | 1.532 s to error |
| JSON-mode image | Same views; `application/json`, same contract in system instructions, strict local validation | Complete, correct grounded development state | 1.993 s |

Images are the already reviewed table/dealer/player/controls views of the
`labelled-totals` owned development case from VISION-018. No provider asset,
private account screenshot, hidden simulator phase/card truth or final holdout
was uploaded. The scoring oracle is read only after inference.

The compatibility schema inlines acyclic references, represents unknown scalar
values with `nullable:true`, encodes int64 bounds as strings and omits the legacy
Schema's unsupported `additionalProperties`. Local extra-field rejection remains.
The discovery preflight also learned to validate dynamic property maps. Both
payloads passed local REST-shape checks; **that does not prove server acceptance**.

The earlier `responseFormat` failure and the new compatibility failure have the
same generic error-body hash and no offending-field details. Removing explicit
thinking was insufficient. The working configuration leaves images, model,
roles, recognition fields and local provenance checks in place, but moves shape
instructions from server schema compilation into the prompt.

The evidence localizes a working workaround to the request/output path. It
**does not identify one failing schema constraint**, prove that all structured
output is broken, or establish server schema complexity as the precise cause.
The format and schema encoding changed together across configurations. We did
not spend further requests to distinguish refs, enums, nullability, cardinality,
backend/model support or other constraints.

Google documents JSON MIME output separately from structured schema generation,
and notes that structured schemas can be rejected for complexity. This explains
the diagnostic choice, not the undocumented reason for this particular 400.
[REST reference](https://ai.google.dev/api/generate-content#GenerationConfig),
[structured-output limitations](https://ai.google.dev/gemini-api/docs/generate-content/structured-output#limitations).

## Implementation and boundaries

`DiagnosticReader(..., provider='gemini', variant='live',
gemini_output='json-mode')` constructs the exact successful payload. Its hash
matches the executed request, including native pixels and prompt. The previous
structured serialization remains the default for reproducibility; the new
variant is named `gemini-lite-live-json-mode` and is **opt-in**.

The new wire mode does not guarantee schema adherence at the provider. Our
unchanged `LiveObservation` parser must still accept one complete JSON object:
extra fields, malformed JSON, unsupported labels, invented ranks for backs and
incoherent tables are rejected. Semantic checks are application checks, not
independent verification that a model's asserted label exists in the pixels.
Advice still belongs to the deterministic engine; the cloud supplies observation.

The offline diagnostic waited at most 10 s to distinguish errors from slow
responses. It never delivered advice. The reusable research reader retains its
**3 s complete-JSON deadline**, no automatic retry and current-evidence checks in
the existing hybrid layer. The successful diagnostic was under 3 s; we have not
rerun it through actual capture/local-routing/revalidation/native window paint.

## Budget and reproducibility

Exactly three generation submissions consumed the last three lifetime slots:
87 to **90/90 reserved attempts**, 86 to 89 claimed network attempts. No ledger
reset/increase, purchase, new key, payment change or recharge occurred.

The two successful calls report **USD0.0024709** combined under the audited token
prices. The HTTP400 has no usage receipt, so its **USD0.3171328** worst-case
reservation stays accounted. New accounted upper: USD0.3196037; lifetime upper:
**USD4.1334549**, including ten uncertain charges totaling USD3.9550760. These
are conservative accounting bounds, **not invoices or remaining account balance**.
The request ceiling, rather than money, now prevents additional generation.
Runtime inference is disarmed; another paid batch is not started automatically.

An initial local credential-loading preflight found no Gemini variable in the
OpenAI file, made **zero reservations/submissions**, and was preserved separately.
The existing ignored `.env.gemini.local` was then used without displaying its key.
It is not counted as a failed provider request or as a reason to regenerate keys.

Free checks and replay from the repository root, using the private artifacts
that remain on this PC:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
.venv/Scripts/python.exe -m validation.tools.gemini_request_diagnosis replay --output artifacts/gemini-request-fix-20261005-authorized
```

Replay requires no credential and makes no network call. Probe commands are
one-shot; the canonical lifetime ledger rejects further generation. Source and
payload hashes, receipts and private observations are kept separately from
published aggregates. Published results do not contain keys or private pixels.

## Decision

Retain the JSON-mode Gemini candidate for the next **explicitly bounded**
same-input comparison. Do not promote it after one development success. Next
evidence needed: new session-disjoint cases, failure/false-acceptance rates and
request-to-validated-state p50/p95, followed by a gated actual hybrid trial.
No new models, training, R2 expansion, Poker or framework are required to complete
this request diagnosis. Physical advisor verification remains separate.
