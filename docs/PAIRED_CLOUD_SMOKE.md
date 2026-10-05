# Paired cloud smoke: stopped at model-access preflight

VISION-022, 2026-10-05. Parent: PR16, commit
`097cbba877fe694f542850c550d8854cf6d12b0c`.

The user authorized **only six** frozen submissions: `labelled-totals`,
`rotation`, `transition-after`, once each for Luna Fast live-v3 and Gemini
structured-card-limit-local. No retries, paid warm-up, development inference,
holdout, hybrid, local tuning, R2/Poker or installed-release changes.
The authorization explicitly requires stopping without inference if a
pre-submission check fails. This check failed; **0/6 inference calls ran**.

## Checks actually performed

- Both existing backend credential files contain the required keys. No key was
  printed, committed, replaced or used in a generation request.
- The PR16 freeze checksum
  `d6fe0f0b41f624a717719ebccb3d35222d1fb4b534e1426b329d500ab4dbcbfe`
  and its source, font, local-model, validation, pixel and request hashes pass
  the existing offline checker. No development inference or final holdout.
- Current [Luna model prices](https://developers.openai.com/api/docs/models/gpt-6-luna),
  [OpenAI Fast/context prices](https://developers.openai.com/api/docs/pricing)
  and [Gemini prices](https://ai.google.dev/gemini-api/docs/pricing) match the
  frozen configurations. Luna Fast short-context input/cache-write/output are
  USD0.20/0.25/1.00 per million tokens; long-context rates 0.40/0.50/1.50.
  Gemini Standard input/output are USD0.30/2.50, including thinking output.
- The unchanged canonical ledger allows USD2.9128094 remaining under its USD8
  lifetime cap. The six worst-case reservations total USD2.5310064 and would fit.
- One authenticated **GET model metadata** per provider was attempted:
  `/v1/models/gpt-6-luna` and
  `/v1beta/models/gemini-3.5-flash-lite`. Both reached the existing 10-second
  read-only deadline with `TimeoutError`; neither returned an HTTP status/body.
- No retry, generation POST, upload, request reservation, spending epoch,
  runtime arming or following hybrid trial was performed.

The precise network stage was not isolated: these failures do **not** establish
invalid credentials, exhausted credit, missing models, schema rejection or model
quality. Earlier successful access is historical evidence, not today's check.
Web documentation access is also not authenticated API model access.

## Results

| Metric | Luna Fast | Gemini structured |
| --- | --- | --- |
| Planned / attempted inference | 3 / 0 | 3 / 0 |
| Complete validated responses / attempted | 0 / 0 | 0 / 0 |
| Correct usable R1 / evaluated opportunities | not measured | not measured |
| False accepted states | not measured | not measured |
| Exact relevant inventory | not measured | not measured |
| Rank / suit / backs | not measured | not measured |
| Phase / controls / numeric provenance | not measured | not measured |
| Complete grounded transcription | not measured | not measured |
| Complete-response p50 / p95 / max | unavailable | unavailable |
| Inference timeouts / failures | 0 / 0 (not attempted) | 0 / 0 (not attempted) |
| Read-only model-access timeouts / attempted GET | 1 / 1 | 1 / 1 |
| New inference usage / charge | no inference | no inference |

Missing smoke results are **not** scored as recognition errors or successful
zero-error trials. Read-only timeouts are **not** included in inference latency.
There is no new candidate comparison or champion decision.

## Accounting and stop

Before and after ledger SHA256:
`6b94bbbfb5872ab8c1e64cec9a48140e9d5669eb57ae47dfe4e492422676ae4f`.
It remains 94/102 lifetime reservations, 93 claimed network attempts,
USD5.087190600 accounted upper, including **all 13** unknown charges reserved
at USD4.9064744. Remaining accounting margin: **USD2.912809400**.
These are research reservations, not an invoice or verified current balance.
The six authorized inference slots remain unconsumed; they were not armed.
No automatic resumption is scheduled. Runtime remains disarmed and the batch
stops here, as required by the authorization's failed-preflight rule.

Private sanitized preflight receipt:
`artifacts/paired-cloud-smoke-20261005/preflight.json`.
Public receipt: `validation/results/paired-cloud-smoke/preflight.json`.
PR13-16 source/results and the installed desktop 1.1.1 remain unchanged.

## Offline verification

```powershell
.venv/Scripts/python.exe -m validation.tools.paired_cloud_prepare check --output artifacts/paired-cloud-preparation-20261005-frozen --expected-freeze-sha256 d6fe0f0b41f624a717719ebccb3d35222d1fb4b534e1426b329d500ab4dbcbfe
.venv/Scripts/python.exe -m pytest -q tests/test_paired_cloud_prepare.py
.venv/Scripts/python.exe scripts/check-evidence.py
```

No product source or test was changed. Targeted offline freeze/evaluator tests
and evidence consistency checks apply; full backend/UI suites are inherited
from PR16 rather than represented as newly executed. One next step, if resumed:
diagnose read-only API connectivity before reconsidering this same six-request
smoke. No inference retry or paid diagnostic is part of this delivery.

Executed offline checks: **13 tests passed in 7.12s**, evidence checker reports
no inconsistencies, validation freeze rechecked, and unchanged ledger/runtime
policy and historical experiment preservation asserted. No inference followed.
