# Numeric provenance alignment and retained latency analysis

VISION-024, started 2026-10-05 and completed 2026-10-06, based on PR17 commit
`a73d53a`. **The new opt-in R1 gate
and evaluator agree on explicit label normalization. The original PR17 scores
remain unchanged. Zero provider requests, zero hybrid trials, no promotion.**

This is a contract correction and re-evaluation of consumed responses, not new
vision accuracy, external-provider generalization or session reliability. The
wire contract, prompts, readers, transport, weights, popup, engine, frozen inputs
and installed 1.1.1 remain unchanged. No credential loading, new epoch or billing.

## One shared, versioned semantic policy

`bjlab/numeric_provenance.py` exports `numeric-provenance-r1-v1` and
`semantic_gate`. The new evaluator `validation/tools/numeric_semantic_score.py`
calls that same application-side gate. This is **opt-in**, not replacement of the
frozen/default `live_gate`; the deployed runtime remains disarmed.

Each number retains these distinct fields:

| Field | Example |
| --- | --- |
| Original observed text | `DEALER TOTAL 2` |
| Normalized label | `DEALER TOTAL` |
| Numeric value | `2` |
| Declared role | `dealer_total` |
| Named source view | `dealer` |
| Semantic status | `normalized`, `ambiguous` or `incoherent` |

Only three finite English labels are recognized: `DEALER TOTAL`, `PLAYER TOTAL`
and `SESSION`. Case/whitespace normalization and an optional separated unsigned
decimal suffix are explicit. A colon separator and leading zeroes are supported;
the original text is always retained. A suffix must equal the declared value.
No generic digit removal, arbitrary substring matching, role reassignment or
inferred view. This owned English profile does not normalize arbitrary site labels.

- `DEALER TOTAL 12` with value `2`: incoherent; blocked even when `2` matches
  the visible dealer rank.
- `SESSION 20`: UI only; never a hand total. A label/role conflict is blocked.
- `PLAYER DEALER TOTAL 2`: ambiguous; cannot authorize an attributed total.
- Dealer totals: `table` or `dealer`; player totals: `table` or `player:0`.
  `SESSION` is restricted to `table` in this owned profile. A missing native view
  or inappropriate source view blocks R1.
- UI/unknown numbers with unrecognized labels retain ambiguity; they never gain
  a hand role. Their omissions/mismatches remain in complete-transcription metrics.

Existing card integrity, enabled-control, phase and total-arithmetic gates remain.
The evaluator separately checks the oracle's allowed views. A model's plausible
label/view declaration is **not proof that the text exists in the pixels**: the
application can check role/view compatibility, while an independent reference
can reject a correctly named view that does not actually contain that number.
Tests preserve this limitation rather than feeding an oracle into the application.
Normalization retains the original view; evaluator equivalence across table/detail
views is allowed only when the frozen independent annotation contains that label
and value in that crop. Duplicates are not collapsed out of the denominator.

## Saved-response replay, with historical scores preserved

Same three owned PR16 validation stills and same six PR17 responses. Five contain
completed observations; Luna's discarded timeout contains **no observation** and
is never resurrected. Re-evaluation is on already-consumed data, not independent
verification. The original evaluator reproduces the public PR17 rows exactly.

| Metric / attempted | PR17 Luna | New semantic Luna | PR17 Gemini | New semantic Gemini |
| --- | ---: | ---: | ---: | ---: |
| Strict completed observations | 2/3 | 2/3 | 3/3 | 3/3 |
| Correct timely usable R1 | 2/3 | 2/3 | 2/3 | 3/3 |
| False accepted states | 0/3 | 0/3 | 1/3 | 0/3 |
| Complete literal transcription | 0/3 | 0/3 | 0/3 | 0/3 |
| Complete semantic transcription | Not scored | 1/3 | Not scored | 3/3 |
| Exact semantic numeric provenance | Not scored | 1/3 | Not scored | 3/3 |
| Semantic numeric tuples / expected | Not scored | 1/5 | Not scored | 5/5 |
| Timeout | 1/3 | 1/3 | 0/3 | 0/3 |

Here "literal" preserves the original exact JSON-field contract: its reference
stores labels and values separately. It is not an additional character-level
score against full combined text in the pixels, which was not independently
annotated. Raw observed strings are retained; no new literal OCR accuracy is claimed.

Cards, ranks, suits, backs, phase and controls are not re-read or improved.
Gemini's apparent false accept is removed **under the new semantic contract**
because its label suffix agrees with the correct value and declared role/view.
Luna still omits the SESSION badge on rotation; it has only one complete semantic
transcription. The historical scores, latency distributions and failed timeout stay.
Neither reader is promoted on a three-case replay.

## What the saved Luna timeout proves

| Clock / stage | Saved duration |
| --- | ---: |
| Reader total | 3048.838 ms |
| Payload construction | 2.252 ms |
| Durable worst-case reservation | 7.246 ms |
| Entire transport | 2984.727 ms |
| Observation extraction, hashing, strict parse/validation | 7.409 ms |
| Sum of those four nonoverlapping spans | 3001.634 ms |
| Derived remaining untimed work | 47.204 ms |
| TCP / TLS, nested within transport | 30.330 / 62.222 ms |
| Request body send, nested | 70.333 ms |
| Response-header wait, nested | 2771.188 ms |
| Body read / provider JSON parse, nested | 13.816 / 0.133 ms |
| Body-complete timestamp, cumulative from transport start | 2984.251 ms |

Nested/cumulative timers are **not added again** to transport. The header wait
contains server and network time; model-generation time was not measured.
Submission claim, model/tier/usage audit, durable settlement, receipt, scheduler
and other overhead were not individually timed. Their aggregate residual is
47.204 ms; it is not a measured budget-settlement duration.

The body's timestamp is relative to **transport** start. No absolute reader-clock
body receipt was saved. The submission claim occurs before that transport timer,
and the request's remaining timeout was calculated before the claim. Consequently
the trace does not establish exactly where the original reader deadline was first
crossed. The four measured sequential spans already exceed 3 seconds, so deferring
settlement alone is not demonstrated sufficient to save this response. The original
timeout, audited charge and discarded observation remain correct historical facts.

Future measurement must pass one absolute capture deadline through payload,
reservation, durable claim, transport and presentation, and explicitly time the
untimed work. The following are design conclusions, **not changes implemented here**:

- Durable worst-case reservation and one-attempt payload claim stay before send.
- Model/tier/usage bounds, strict parse, semantic integrity, original evidence
  expiry and current source/table/state checks stay before presenting advice.
- Full diagnostic receipts/serialization can be investigated outside that path.
  Durable settlement may move after an audited in-memory usage check only if the
  full durable worst-case reservation remains charged until successful settlement;
  a crash must retain it. No unaudited response or late state becomes presentable.

No accounting order, deadline or reader implementation changed in this increment.

## Persistent HTTP lifecycle: offline proof only

`validation/tools/persistent_http_fixture.py` supplies a **socketless scripted
backend** to the real pinned HTTPX 0.28.1 / httpcore 1.0.9 pool. It is not a provider
transport, has no keys, cannot accept a real network backend and is not integrated
with any runtime. It makes three local fixture transactions:

1. First origin: one scripted connection and one configured verified-TLS context.
2. Same origin again: zero new scripted connections; pool reuse is demonstrated.
3. Other origin: its own connection, with original Host and TLS server name.

Closing is idempotent and closes both streams. Expired scope, original deadline,
late result or request failure closes/blocks the fixture without retry. Scope expiry
is checked **before every transaction**, even when a connection already exists.
The test covers sequential lifecycle only. It does not demonstrate real TLS,
server keep-alive, concurrent/cancellable workers, DNS repair or API latency gain.

No DNS lookup was run. PR17's retained cold DNS preparation is approximately
9.031 s + 9.109 s = **18.140 s**, outside the subsequent inference clocks. A future
live test must report full cold initialization and warm requests separately. No
global resolver, DNS, proxy, hosts, firewall or certificate setting changed.

## Minimum future verification proposal — not executed

**At most five future requests:** two fresh owned cases paired across both
providers (four requests), followed by at most one stable-table hybrid request
for a passing candidate. No automatic continuation and zero requests when a
prerequisite fails. This is a functional smoke, not a statistical champion test.

Freeze a labelled-totals plus independent SESSION case, and a partial/rotated
card plus back/ambiguous-UI case before evaluation. Use new source sessions,
seeds, hand groups and artwork families disjoint from the consumed cases. Identical
native pixels for both candidates; new semantic and literal metrics side by side.
Positive/negative schema contracts are already tested offline, not paid probes.

The hybrid is conditional on correct full required R1 states, zero semantic false
accepts and complete required validation within the original 3 s budget, with the
provisional sample p95 <= 2.5 s and every timeout retained. The local reader must
route without an oracle; if it succeeds, no cloud call is forced. Measure advancing
capture -> local -> route -> API -> parse -> semantic gate -> state revalidation
-> solver -> headless advisor on a new stable owned table. One trial cannot prove
continuous/session reliability or physical desktop capture/native paint.

Frozen-price conservative reservations, subject to access/price recheck:

| Proposed part | Maximum reservation USD |
| --- | ---: |
| Two paired cases, four requests | 1.6873376 |
| One hybrid, worst candidate's reservation | 0.5265360 |
| Combined maximum | **2.2138736** |
| Existing accounted monetary margin | **2.904214250** |

Current ledger is **100/102**, USD5.095785750 accounted upper, including thirteen
unknown charges/USD4.9064744. It is byte-identical before/after this work.
The residual two slots remain **closed**. Five new attempts would require fresh
explicit scope and a lifetime ceiling of at least 105; **no amendment or new epoch
was made**. Unknown reservations stay charged. Prices are historical audited
configurations for a proposal, not a new current-price check or account balance.
No retries, paid warm-ups, final holdout, new models or billing actions.

## Reproduce

From the repository, offline:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_numeric_provenance.py tests/test_numeric_contract_replay.py tests/test_persistent_http_fixture.py
.venv/Scripts/python.exe -m validation.tools.persistent_http_fixture
.venv/Scripts/python.exe -m validation.tools.numeric_contract_replay
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
```

The replay requires the original private PR16 corpus, private PR17 response receipt
and canonical ledger. It checks the original hashes and reproduces historical rows,
with network/DNS/subprocess guards. It writes only its dedicated new aggregate
and private replay artifacts; it opens only consumed validation data. No network
execution command exists in the new tools. Never re-run the consumed paid smoke.

Public [aggregate and trace analysis](../validation/results/numeric-provenance-alignment/summary.json).
Detailed normalized rows and protected hashes remain ignored private artifacts.
Executed checks and limits are in
[verification](../validation/results/numeric-provenance-alignment/verification.json).
