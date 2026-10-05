# Gemini HTTP400: isolated single-constraint trigger

VISION-020, 2026-10-05. Parent: PR14 / `48d227f`. Frozen diagnostic
preparation: `9ad3cea`. PR11–14 evidence remains unchanged.

The causal trigger in the current `grounded-r1-live-v3` GenerateContent request
is **`/properties/c/maxItems: 52`**, the maximum size of the cards array.
An actual one-change A/B/A comparison establishes this result:

| Controlled request | HTTP | Complete response | Elapsed |
| --- | --- | --- | --- |
| Original full schema, including `c.maxItems=52` | 400 | Generic `INVALID_ARGUMENT` | 1,335.9 ms |
| Exactly the same request, omitting only `c.maxItems` | 200 | Strictly validated full observation | 2,271.8 ms |
| Exact original request reintroduced | 400 | Same error/body digest | 1,527.1 ms |

The full request pointer is
`/generationConfig/responseFormat/text/schema/properties/c/maxItems`.
Native images, prompt, model, endpoint, token budget, thinking, nullable fields,
enums, numeric bounds, other array bounds and required fields are identical.
The first and third payload hashes match exactly. Free replay asserts that the
successful opt-in reader's payload matches the executed successful request.

This is a demonstrated trigger **in this full schema with
`gemini-3.5-flash-lite` on `v1beta:generateContent`**. Google returns only a generic
message; its internal parser/compiler reason remains undisclosed. We have not
proved that `maxItems=52` is universally unsupported, identified a maximum
acceptable alternative value, or isolated the older legacy `responseSchema`
failure. Google's [GenerateContent reference](https://ai.google.dev/api/generate-content)
documents `maxItems` and the JSON Schema output fields. The observed failure is
not evidence that the documented keyword is invalid in every schema.

## Scoped correction

`DiagnosticReader(..., provider='gemini', variant='live',
gemini_output='structured-card-limit-local')` uses
`gemini_structured_schema()`, omitting only that provider-side constraint.
`LiveObservation.cards` still has `max_length=52`; local strict parsing rejects
53 cards before anything can reach an advisor. All numeric/provenance,
visibility, extra-field, integrity and stale-response checks remain intact.
The original structured variant and PR14 JSON-mode variant remain reproducible.
This is opt-in research; there is no default-reader or installed-release change.

The successful reply on one **reused owned development still** has exact
inventory, ranks, phase, controls and numeric roles, with a usable R1 state and
no falsely accepted state. This is request diagnosis, not session-disjoint
generalization, a latency distribution, actual hybrid execution or desktop
capture-to-paint evidence. The live deadline remains 3 seconds; the diagnostic
transport allowed 10 seconds and never presented advice.

## Separate DNS failure and recovery

The initial tiny-schema attempt times out before TLS/request headers/body.
It is not a schema failure and has no HTTP status. Read-only checks distinguish
a DNS resolution delay from provider rejection. An IPv4 returned by the host's
DNS answer is verified with ordinary HTTPS hostname/certificate validation.
All three A/B/A submissions use the same process-only DNS resolution control;
the hostname/SNI remains `generativelanguage.googleapis.com`. No system hosts,
proxy, firewall, certificate verification, key, billing or recharge setting is
changed. The timeout, stop and read-only recovery receipts remain private.
The consumed tiny probe is not retried.

## Allowance and evidence

The latest user request explicitly authorizes exact causal diagnosis. The
operational request ceiling is audited from 90 to 102, at most 12 new attempts,
with the **unchanged USD8 aggregate money cap** and every old ledger entry and
unknown charge retained. Four new attempts are reserved: one pre-submission
timeout, two HTTP400s and one success. Three send an HTTP request body. The
remaining eight slots are closed; runtime inference is disarmed.

Reported successful usage: 4,816 input / 357 output tokens; price-based upper
USD0.0023373, **not an invoice**. All three uncertain attempts retain their full
reservations. Lifetime upper accounting is USD5.0871906, including thirteen
unknown charges, across 94 reserved attempts / 93 claimed network attempts.
No purchases or additional monetary authorization occurred.

Public aggregate: [`summary.json`](../validation/results/gemini-schema-cause/summary.json).
Private inputs, exact schemas, one-shot claims, timings and observations remain
under ignored `artifacts/gemini-schema-cause-20261005-authorized/`. The final
holdout is not opened; no user/provider private screenshots are uploaded or
published. No model training, Poker, UI/framework or release work occurs.

## Reproduction

Free local contract checks (no credentials or network):

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_gemini_schema_cause.py tests/test_gemini_schema_network_control.py tests/test_api_tournament.py tests/test_gemini_request_diagnosis.py
```

Free replay for the original workstation, with its retained ignored receipts:

```powershell
.venv/Scripts/python.exe -m validation.tools.gemini_schema_replay --output artifacts/gemini-schema-cause-20261005-authorized --summary validation/results/gemini-schema-cause/summary.json
```

The replay verifies frozen execution sources against `9ad3cea`, rechecks owned
pixel hashes, proves the whole-payload single-pointer difference and exact
reintroduction, validates the stored successful observation, and scores it only
after inference. It never submits or opens the final holdout. The generation
runner is one-shot/source-frozen and the diagnostic scope is closed; these
commands do not authorize another paid batch.
