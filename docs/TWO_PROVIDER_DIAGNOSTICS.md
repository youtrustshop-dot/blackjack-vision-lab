# Two consumed-case diagnostics — closed

VISION-027, 2026-10-07, based on PR20 at `49d4003`. Exactly two authorized
diagnostic inferences ran, Gemini first and Luna second, on the already consumed
owned `fresh-rotated-unknown` PR19 pixels. Prompts, models, schemas, output caps,
numeric policy and three-second live deadline were unchanged. No retry, paid
warm-up, hybrid or subsequent batch ran. **This is failure diagnosis, not
independent validation or live-advisor evidence.**

## Individual outcomes

| Observation | Gemini structured-card-limit-local | Luna Fast compact |
| --- | --- | --- |
| Exact model | gemini-3.5-flash-lite | gpt-6-luna |
| Complete HTTP200 observation | 1/1 | 1/1 |
| Strict, semantically usable content | 0/1 | 1/1 |
| Diagnostic collect start through usage settlement and validation | 3,297 ms | 3,578 ms |
| Fits unchanged 3,000 ms boundary | 0/1 | 0/1 |
| Returned text encrypted and recovered with matching hash | 1/1, 655 bytes | 1/1, 351 bytes |
| Advisor eligibility | Always false in this separate collector | Always false in this separate collector |

These individual times are not p50/p95 estimates. Storage follows the collect
clock: 15 ms and 16 ms respectively. Both outputs were retained solely for local
diagnosis, including Luna's otherwise valid late content.

### Gemini: the newly returned rejection is explained

The preserved new text assigns the unlabelled number 20 to `dealer_total`, with
no associated label and the dealer view. `LiveNumber.observed_label_required`
in `bjlab/live_state.py:33` rejects `n[0]` with
`Explicit associated PLAYER/DEALER TOTAL label required.` The public rule is
`explicit_total_label_required`, category `pre_normalization_invariant_rejection`.
JSON syntax passes; strict validation fails before semantic normalization or R1.
Neither later stage was run for this response.

The reviewed pixels contain dealer 5 clubs and a blue back, player 9 clubs and
7 diamonds, enabled HIT/STAND, a labelled SESSION 20 and a separate unlabelled
20. They contain no associated DEALER TOTAL label for the unlabelled number.
The returned hand-total attribution has no pixel support. The strict control
correctly rejects it; merely moving normalization earlier would not justify
acceptance. The labelled SESSION number is separately reported as UI.

The error *class* recurred in this new call, and its new text now explains it.
The lost 566-byte PR19 answer is still unavailable: this does not recover that
answer or prove it contained the same number or label. Full new observation text
and detailed local errors remain in current-user DPAPI ciphertext, not Git or
the published aggregate report.

### Luna: valid content arrived outside the live deadline

Luna reports all three faces and the covered object, player phase and HIT/STAND
correctly in this consumed case. It leaves the unlabelled 20 as unknown and
reports SESSION as UI. Strict validation, the unchanged numeric policy and the
shared R1 gate all pass. This is a post-hoc pixel check of one reused owned state,
not new generalization evidence.

HTTP timing begins after the one-shot submission claim. Headers arrive at
3,516 ms; the full body at 3,563 ms. The claim consumes 15 ms, and the diagnostic
collect clock finishes at 3,578 ms including accounting and validation. Timed
subspans below the host monotonic timer resolution are reported as zero; zero
does not establish absence of work. Transport tracing shows a pooled connection
reused from the read-only model GET, with zero new TCP connects in generation.
Most measured request time is waiting for response headers (3,390 ms). This does
not separately measure server queueing, reasoning or network transit, or prove
a causal pooling speedup.

Preparation is separate: protected storage preflight 141 ms; OS DNS resolution
5,390 ms; Gemini/Luna client construction 47/31 ms; exact-model metadata GETs
250/1,016 ms. None is presented as part of a live capture-to-display measurement.
The two previous Luna timeouts remain censored observations; this new 3.578 s
response does not establish when those old requests would have completed.

## Collector and controls

`bjlab/offline_response_collector.py` calls the frozen payload builder and
transport once with a separate absolute ten-second diagnostic ceiling. It never
calls the default three-second reader path, solver, observer or advisor. All
results have `eligible_for_live=false` and no advice, including early results.
It settles auditable usage, retains unknown charges on failure, saves only
bounded selected observation text through the existing protected store, closes
the pool and tells the controller to stop on access/accounting/storage failure.

`validation/tools/two_provider_diagnostics.py` freezes this exact scope before
execution. An exclusive whole-lot claim prevents rerunning it; individual claims
bind the exact frozen payloads. Actual Windows encrypted write/read succeeds
before any paid request. Both authenticated exact-model GETs return HTTP200.
The runtime is armed only for this epoch and these two slots, then restored to
the original disarmed state. The documented completed-scope metadata is also
disarmed. Existing unused authorizations remain closed.

## Budget and history

Prices were checked against the current official
[OpenAI pricing](https://developers.openai.com/api/docs/pricing) and
[Gemini exact-model pricing](https://ai.google.dev/gemini-api/docs/pricing)
before submission. They match the frozen pricing reservation. The combined
worst-case reserve USD0.8436688 fits the initial prudential margin USD1.846720150.
This reserve is not an invoice or account balance.

| Accounting | Gemini | Luna | Total |
| --- | ---: | ---: | ---: |
| Input/output tokens reported | 4,816 / 300 | 2,237 / 142 | — |
| Reported-usage conservative charge | USD0.0021948 | USD0.00070125 | USD0.00289605 |
| Unresolved new reservations | 0 | 0 | 0 |

The audited count ceiling changed 105 → 106, with 104 attempts previously
consumed. Final receipt: **106/106**, USD6.156175900 accounted upper under the
unchanged USD8 lifetime cap; margin USD1.843824100. All 104 old entries and all
15 old unknown-charge reservations, totalling USD5.9595464, remain intact.
No invoice/balance lookup, purchase, recharge or billing change occurred.

Frozen sources, PR19 native pixel/payload hashes, fonts, local weights and prior
evidence pass the local audit. The final holdout was not opened. Default readers,
contracts, numeric policy, engine, UI, Poker and installed desktop 1.1.1 remain
unchanged. This branch is an unreleased research candidate.

## Verification and decision

The full local suite passed **794 tests + 10 subtests** in 91.99 s, with two
existing warnings. Twelve new networkless tests cover early/late/absent responses,
exact payloads, strict Gemini rejection, usage/storage failures and one-shot
execution. Windows protected output recovery and unchanged-history audits passed
for both real responses. Frontend/physical capture/paint/minimization tests were
not rerun locally; prior PR19 Windows CI includes 52 frontend tests and build.

Public evidence: [summary](../validation/results/two-provider-diagnostics/summary.json),
[frozen scope](../validation/results/two-provider-diagnostics/freeze.json),
[verification](../validation/results/two-provider-diagnostics/verification.json).
Historical PR13–20 reports and scores are not rewritten.

Offline reproduction from the repository root:

~~~powershell
.venv/Scripts/python.exe -m pytest -q tests/test_offline_response_collector.py
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
~~~

The paid execution command recorded locally was
`python -m validation.tools.two_provider_diagnostics --run --freeze-sha256
25a471f0aa3028d9d31e3d7a34d340a32c2a8f77b188baf4265d6a87437ef985`.
**Do not repeat it**: its lot claim, ledger precondition and count ceiling are
closed. The default command now rejects the consumed precondition rather than
opening another scope. Local protected records have the existing seven-day
access/expiry policy; raw text is not copied into a reproducibility bundle.

Decision: keep the strict provenance control; no permissive gate fix is justified
by an unsupported hand total. Luna can return usable content here, but this one
response misses the live deadline even on a reused connection. Neither model is
promoted, no hybrid starts and no new batch is proposed or launched automatically.
The authorized diagnostic question is answered; live reliability remains unproved.
