# Connection diagnosis and the original six paired requests

VISION-023, 2026-10-05, on local preflight commit `ff6681a`. **The connection
block was localized to native DNS resolution before TCP/TLS. A scoped mitigation
passed both authenticated model GETs, and all six original PR16 inference calls
were then attempted exactly once. Runtime is disarmed. No hybrid or champion.**

This explicitly resumed scope supersedes VISION-022's preflight stop only for
those six calls. PR13–16 sources, requests, evaluator and results are preserved;
the old failed preflight remains a historical result. No new money, credentials,
model, prompt, dataset, tuning, default reader, desktop release, UI or Poker work.

## What actually blocked the connection

The same authenticated non-generative GET was sent by the project transport and
an independent minimal HTTPX client. Both used the same existing keys, official
origins, verified TLS, direct HTTPS (`trust_env=False`), no redirects and no
automatic retries. The project request runs on its background network loop;
the independent client is synchronous in a bounded worker.

| Model metadata GET | Project client A | Independent client B |
| --- | --- | --- |
| `api.openai.com/v1/models/gpt-6-luna` | 10.009 s timeout; DNS still pending | HTTP200, exact model, 2.340 s |
| `generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite` | HTTP200, exact model, 0.307 s | HTTP200, exact model, 0.236 s |

OpenAI A: `connect_tcp.started` at 316 ms, `socket.getaddrinfo` started at 320 ms,
no DNS completion, then cancellation at 10.008 s. Exception types are
`TimeoutError` / `CancelledError`; no TLS handshake or request-body send occurred.
The connect trace includes resolution, so it must not be interpreted as TCP
already established. B spends 1.370 s resolving the same host, then completes
TCP, TLS and HTTP. No exception messages, headers or provider error bodies are
published. Stage event names/timings and exact exception types are retained.

The A/B result alone does **not** prove an async-client bug. Bounded follow-ups:

- The project path stalls in OpenAI DNS again, while Gemini returns HTTP200.
- A plain synchronous replacement subsequently times out for **both** domains;
  switching clients alone is rejected as a fix.
- DNS-only controls on the project loop show successful `AF_UNSPEC` resolutions
  and timed-out `AF_INET` resolutions. This does not establish IPv6 as the cause
  and forcing IPv4 is not adopted as the explanation.
- Windows `Resolve-DnsName`, using the configured resolver without changing it,
  takes 7.840 / 7.034 s. Delay is also observable outside the Python client.

**Diagnosis limit:** native resolution is the demonstrated blocking stage;
the specific Windows resolver, router, network/security driver or upstream DNS
reason is not isolated. No firewall, certificate, sandbox or provider inference
failure is established by these timeouts. An OpenAI status snapshot reported
minor degradation; it is not evidence that an incident caused the local DNS wait.

Environment actually used: project `.venv/Scripts/python.exe`, Python 3.12.14 on
Windows, OpenSSL 3.5.8, HTTPX 0.28.1, httpcore 1.0.9, AnyIO 4.15.1 and certifi
2026.7.22. No proxy/certificate override variables were present. The execution
environment permits network access; no tool-approval rejection was observed.

## Narrow correction and its limits

`bjlab/controlled_http.py` is an **opt-in research transport**, not a new default.
It obtains fresh public A answers for the two whitelisted official domains using
the existing OS resolver. Answers stay in memory for at most their remaining
DNS TTL / 60 seconds, measured from query start. No old receipt's address is
reused, no fixed provider IP is embedded, and expired/private answers fail closed.

The pool substitutes the answer only at TCP connection time. HTTP origin/Host
and TLS SNI retain the official hostname; certificate verification remains on.
No system DNS, hosts file, proxy, firewall or TLS setting changes. This pinned
HTTPX/core adapter uses the pool's private backend hook and is not a general
unversioned transport abstraction. Bounded workers reject late stages/results;
they never update an advisor after the original deadline.

With the scoped transport, both exact authenticated GETs return HTTP200:
OpenAI 0.876 s, Gemini 0.210 s. The ledger is byte-identical across those controls.
A fresh scope and two fresh exact-model GETs are then checked in the execution
process before arming inference. DNS setup takes **9.031 / 9.109 s in that process**.
It is a one-time batch setup cost, reported separately, not hidden API speed.
Each inference still opens a new HTTP client/connection; TCP/TLS are included
in the reader's 3 s limit. No pooled or capture-to-advisor latency claim.

This demonstrates a bounded workaround for this batch, **not repair of the PC's
DNS or universal transport reliability**. Cold startup is slow; expired scopes
stop rather than silently renewing DNS or retrying a request.

## Frozen comparison actually executed

Only `labelled-totals`, `rotation`, `transition-after`, each from a different
owned validation source session. Exact PR16 native PNGs, calibration, payloads
and common evaluator; no development inference, paid warm-up, retry or holdout.

Freeze SHA256:
`d6fe0f0b41f624a717719ebccb3d35222d1fb4b534e1426b329d500ab4dbcbfe`.
The offline checker verifies every original source, font, pixel, local model,
oracle, request and plan. A guard compares the actual outgoing canonical payload
to the frozen hash. Exclusive batch/per-pair claims prevent replay after crashes.
All six durable reservations and payload claims use the existing canonical ledger.
The original evaluator independently re-scores the receipts with identical rows.

| Metric, common frozen evaluator | Luna Fast compact | Gemini structured-card-limit-local |
| --- | ---: | ---: |
| Attempted / planned | 3/3 | 3/3 |
| Strict validated within 3 s / attempted | 2/3 | 3/3 |
| Correct usable R1 / eligible cases | 2/3 | 2/3 |
| Correct usable R1 in time / eligible cases | 2/3 | 2/3 |
| False accepted states / attempted | 0/3 | 1/3 |
| Exact relevant card inventory / attempted | 2/3 | 3/3 |
| Correct rank tuples / expected | 6/9 | 9/9 |
| Correct rank+suit tuples / expected | 6/9 | 9/9 |
| Correct backs / expected | 2/3 | 3/3 |
| Phase / attempted | 2/3 | 3/3 |
| Controls / attempted | 2/3 | 3/3 |
| Exact numeric provenance / attempted | 0/3 | 0/3 |
| Matched numeric tuples / expected | 0/5 | 0/5 |
| Complete grounded transcription / attempted | 0/3 | 0/3 |
| Complete validated latency p50 / p95 / max | 1.947 / 2.115 / 2.133 s (n=2) | 2.455 / 2.815 / 2.855 s (n=3) |
| Timeout / attempted | 1/3 | 0/3 |
| Other transport/schema errors / attempted | 0/3 | 0/3 |

Luna's first response body arrives before its transport deadline, but usage
audit/settlement and full local validation push the reader past its 3 s limit;
it returns at 3.049 s, with `late_complete_json_discarded` and no observation.
This is a complete-observation timeout, **not another DNS failure**. Reported
usage is available and audited, so that charge is reconciled despite discarding
the observation. The timeout stays in all accuracy denominators and is excluded
only from complete-validated latency percentiles. Two successful observations
cannot establish a reliable operational p95.

### Why the provenance result must be read precisely

Gemini's three numeric **values and roles are correct** on `labelled-totals`.
It returns labels `SESSION 20`, `DEALER TOTAL 2`, `PLAYER TOTAL 18` rather than
the frozen labels `SESSION`, `DEALER TOTAL`, `PLAYER TOTAL`. The literal-label
evaluator therefore matches zero of three, including the two attributed totals,
and records one unsafe-total false accept. The current local gate accepts that
format, but the frozen evidence contract rejects it. This is not a wrong card,
wrong total value, or the previous badge-as-dealer error.

On the other two scenes Gemini similarly appends `20` to `SESSION`. Luna omits
SESSION on rotation and appends its value on transition-after. Neither candidate
has a complete exact numeric transcription. The evaluator and scores are **not
modified** to forgive this after viewing validation. Any future interpretation of
label normalization needs separate offline specification/regressions and fresh
verification; it is not silently counted as a success here.

## Accounting and stop

Current official [Luna model pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)
and [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) are checked before
the batch. Luna Fast/long-context/cache-write upper multipliers and Gemini thinking
output are retained. Whole-context reservations remain deliberately conservative.

| Ledger | Before | After |
| --- | ---: | ---: |
| Lifetime reserved attempts / ceiling | 94/102 | 100/102 |
| Lifetime claimed network attempts | 93 | 99 |
| Accounted upper USD | 5.087190600 | 5.095785750 |
| Unknown-charge reservations | 13 | 13 |
| Unknown-charge reserved USD | 4.9064744 | 4.9064744 |
| Accounted monetary margin USD | 2.912809400 | 2.904214250 |

Six-request worst-case reservation: **USD2.5310064**, within the original margin.
All new requests report auditable usage; new upper charges are **USD0.002080750
Luna + USD0.006514400 Gemini = USD0.008595150**. This is a token-price upper,
not invoice/tax or live account balance. All 94 old entries are unchanged, including
the thirteen unknown charges. No reset, budget increase, recharge or payment action.

Runtime is disarmed with zero live allowance. The two residual request slots are
closed; lower actual charges do not authorize another batch. **Zero hybrid trials**,
no local retraining, R2/Poker expansion, UI change or installed-release replacement.

## Source verification and reproducibility

- Python: **653 passed, 10 subtests passed, two existing warnings**, 138.43 s.
- Deadline, endpoint, expiring/public-DNS and one-attempt/payload guards: 23 targeted
  tests passed before execution. Mocks are not API quality evidence.
- UI: source unchanged; 52 parent frontend tests and parent build evidence inherited,
  not a new local browser/native/monitor test.
- Every original PR16 validation source/hash remains checked after execution.

Public aggregates: [connection](../validation/results/cloud-connection-paired-smoke/connection.json),
[six-call scores](../validation/results/cloud-connection-paired-smoke/summary.json).
Private native pixels, payloads, observations, metadata/claim receipts and the
canonical ledger stay under ignored `artifacts/`; neither key is published.

Offline reproduction, from the repository:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
```

With the original private corpus/receipt, unchanged `paired_cloud_prepare.evaluate`
can re-score `artifacts/paired-cloud-smoke-20261005-six/responses.json`; it calls
neither provider and does not open final holdouts. The historical execution command
was `python -m validation.tools.paired_cloud_smoke --run`. It is **consumed**:
the expected original ledger and exclusive claim prevent a new invocation from
spending again. Do not re-execute network diagnostics to reproduce an offline score.

Decision: retain the scoped transport and exact receipts as research evidence;
**neither candidate is promoted**. This is three paired owned stills, not external
provider generalization, continuous game-state reconstruction or actual hybrid advice.
