# Grounded R1 observations and continuous hybrid revalidation — VISION-017

The new numeric/visibility boundary and controlled hybrid runner are implemented.
The API comparison stopped on provider failures: two Gemini HTTP400 responses and
one Luna Fast complete-JSON timeout. No new reader is promoted. This is a research
increment on top of frozen PR11, not a desktop release or a completed live trial.

The [aggregate result](../validation/results/grounded-reader-v2/summary.json)
contains actual executions, unexecuted trials, denominators and corpus hashes.
PR10 perception source/weights and PR11's historical scores remain unchanged.

## Observation boundary

`grounded-r1-v2` separates card information from visible numbers. A number carries
its value, native view, normalized region, observed associated label, and role:
`player_total`, `dealer_total`, `ui` or `unknown`. An unlabelled `20` is not a hand
total. A `SESSION 20` badge remains UI evidence. Only attributed totals participate
in card-total consistency; all other numbers remain in the observation and score.
Nothing silently rewrites an old observation or derives a card from a total.

This particular owned trial requires explicit English `PLAYER TOTAL` / `DEALER
TOTAL` labels. It is not a universal provider layout profile. Labels/boxes are
model observations, not independently verified pixel facts. The evaluator checks
number roles/values; it does not establish precise numeric-box localization.

Cards distinguish readable faces, partial faces, visible backs, and present but
unreadable faces. Absence means no observed object. Any visible top/bottom index or
central suit pip can supply information. Unknown suits may still permit rank-only
blackjack R1; they cannot certify full-card perception or poker. Frozen locals
have no numeric provenance support, which is explicitly reported as unsupported.

## New data and preserved failures

Development, validation and final holdout each contain 12 scenes from separate
physical engine sessions/seeds and grouped rank-font/palette families. They share
the renderer, control font and Segoe UI Symbol suit glyphs. These are correlated
scenario renderings, not 12 independent provider sessions. Final holdout remains
sealed; the runner refuses to load it for evaluation.

Cases include labelled and unlabelled numbers, overlap, rotation, fading/blur,
top-index clipping with a readable opposite index, a popup obscuring a face,
disabled controls on an actual terminal hand, decorative card-like negatives,
empty table and repeated new-round appearances. The six predeclared cloud inputs
are clean UI, labelled totals, unlabelled number, overlap, rotation and popup.
Only owned native pixels are approved; no private provider screenshot was sent in
this increment. Both candidates receive the same views, prompt and logical schema.

Visibility truth examines all rendered index/pip ink masks, followed by an
assistant visual audit. It is still a geometric proxy, not independent human
annotation or proof of readability under blur. No oracle phase/ID is given to the
reader. The oracle is used after reading for scoring only.

Two preparations were rejected before API execution: one used an artificial
phase override instead of an actual terminal fixture; the next exposed missing
suit-font glyphs. The latter's development-only diagnostic is preserved, not used
as validation evidence. The corrected preparation checks four distinct suit
glyphs and was frozen before the reported local validation/API attempts.

## Executed local results

No local training, threshold adjustment or perception-source edit was made.
Offline CPU timings below come from single executions per case, not a latency
distribution measured from a running desktop capture loop.

| New validation, all 12 scenes | Frozen Local A | Specialized Local B |
|---|---:|---:|
| Correct rank observations | 28/34 | 33/34 |
| Correct rank/suit tuples | 12/34 | 4/34 |
| Exact full object inventories | 2/12 | 0/12 |
| Exact rank/presence inventories | 9/12 | 9/12 |
| Backs predicted / expected | 8/10 | 10/10 |
| Correct phases | 0/12 | 0/12 |
| Timely usable R1 opportunities | 0/9 | 0/9 |
| False accepted R1 states | 0 | 0 |
| Offline completed p95 | 149 ms | 67 ms |

Predicted/expected backs is a count, not an independently matched localization
recall. Local A predicts 42 of 45 objects; Local B predicts 45, but matching the
total object count does not imply the inventory is correct. Their complete v2
states are both 0/12: phase fails and numeric provenance is unsupported.

On exactly the six predeclared API inputs, Local A reads 15/17 ranks and 7/17
rank/suit tuples, with 1/6 exact inventories. Local B reads 17/17 ranks and 4/17
tuples, with 0/6 exact inventories. Both yield 0/5 timely usable opportunities.
These new scores do not replace PR10's earlier synthetic/provider results.

## Actual API attempts and remaining uncertainty

| Configuration | Executed result | Quality/latency conclusion |
|---|---|---|
| Gemini 3.5 Flash Lite, `responseFormat` | HTTP400, about 2014 ms | No observation; no quality score |
| Gemini, documented compatibility JSON fields | HTTP400, about 1696 ms | No observation; error category remains unspecified |
| GPT-6 Luna Fast, reasoning `none` | Complete-JSON deadline exceeded, about 3170 ms | No validated current state; remaining five cases not executed |

These are three new submissions, each with one durable network claim and no
automatic retry. The compatibility request is a separately frozen configuration,
not a rerun erased from the record. The first Gemini response body was discarded;
the second produces only a fixed diagnostic category. The HTTP400 cause has not
been proved. Read-only model metadata access succeeds; that does not prove the
generation request is accepted. HTTP400 is not a card-recognition accuracy score.

The hard deadline surrounds network upload, complete response and JSON decoding;
cancellation/connection cleanup can finish after 3000 ms. Timed-out evidence is
never accepted. There are no completed new cloud observations, so p50/p95 and
card-quality estimates are **not measured**, rather than zero or a model ranking.
The six intended real-API hybrid trials were not executed after these failures.
PR11's earlier Fast 15/15 latency observations remain historical evidence under a
different schema; they do not prove the larger grounded response meets the budget.

Gemini's REST structured-output compatibility fields and bounded configuration
are documented in the [GenerateContent reference](https://ai.google.dev/api/generate-content).
The [troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting)
does not recommend blindly retrying HTTP400 errors. Current model rates/context
were checked against [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
and the [official Luna page](https://developers.openai.com/api/docs/models/gpt-6-luna).

## Continuous-capture boundary

The research runner has one capture producer while local/cloud reading happens
separately. Requests bind original capture time, source, table, source epoch and
pixel/motion epoch. Any table/source change, any native table-pixel change, a
capture gap above 250 ms or disconnection invalidates the result. Returning to
old pixels does not restore the old epoch. Repeated identical captures do not
refresh the original evidence's maximum 3000 ms age.

Routing uses the local integrity/turn/control gate only. Oracle correctness does
not choose fallback. Advice uses existing deterministic math after a successful
observation, then revalidates before emitting a headless advisor payload. This
does not certify identities, shoe reconstruction or R2. Exact pixel equality is
deliberately conservative: animation/cursor changes can cause abstention.

Tests run a real producer thread during an injected slow cloud reader, proving
capture continues and changed-pixel replies are withheld. Those are contract
mocks, not real API quality or latency results. Actual desktop capture, native
window painting, mixed DPI, cross-monitor dragging and minimized-app capture were
not tested here. The installed advisor and its original 2200 ms expiry are
unchanged; the 3000 ms research budget is not a product expiry change.

## Cost reconciliation and runtime state

Both existing credentials were reused; no key value entered output or source.
Read-only authenticated billing pages show positive prepaid balances and
auto-recharge off for both providers. Exact account/payment details remain local.
No purchase, recharge, billing-setting change or new allowance was performed.

Read-only OpenAI exports cover all prior 51 Standard / 15 Fast / 3 Sol requests.
The reported period cost is USD0.04263181; it is a current report, not a final
invoice. Eight old funded timeout reservations were reconciled conservatively:
**each** timeout is charged all input tokens of its entire model/tier group plus
its maximum request output at the audited upper rates. This overcounts input and
does not rely on potentially delayed output costs being final. The export hashes
and settlement intent are saved privately before applying durable settlements.

The original authorization remains EUR10 total, with the same USD8 working cap
and 90 lifetime attempts. Current ledger: 73 attempts; USD1.5944261 upper accounting,
including USD1.4240696 retained for four uncertain attempts (initial HTTP429, two
Gemini HTTP400s and the new Luna timeout). This is neither actual spend nor a
provider balance. Google warns that cost reporting may take 24 hours or longer;
a zero current chart cannot release its reservations. Runtime is disarmed.

## Reproduction and decision

Validation completed: 585 Python tests and 10 subtests passed (two pre-existing
dependency/reference warnings), 52 frontend tests passed, frontend production
build passed, evidence-consistency and whitespace checks passed. These checks
verify implementation regressions; they do not replace missing real-API/native
session evidence. No new installer or release build was produced.

Free preparation/local checks on the same Windows font environment:

```powershell
.venv/Scripts/python.exe -m validation.tools.grounded_reader_tournament generate --output artifacts/new-owned-v2 --reader-manifest D:/CodexResearch/blackjack-vision-lab/specialized-card-reader-20261004/reader.json
.venv/Scripts/python.exe -m validation.tools.grounded_reader_tournament local --output artifacts/new-owned-v2 --split development
.venv/Scripts/python.exe -m validation.tools.grounded_reader_tournament local --output artifacts/new-owned-v2 --split validation
.venv/Scripts/python.exe -m pytest -q tests/test_grounded_reader.py
.venv/Scripts/python.exe scripts/check-evidence.py
```

The approved manifest and weights must already exist in the research environment.
No weights or dependencies are distributed by these commands. Cloud/hybrid commands
require a current reviewed input/configuration hash, approved epoch and canonical
ledger; a key's presence or another output directory cannot authorize a request.
Do not simply rerun paid attempts or consume final holdout to repair failures.

Next useful work is a bounded diagnosis of the Gemini request/account error and
measurement of complete grounded JSON latency. Then run the already implemented
controlled hybrid if a candidate passes, followed by new original provider
sessions and independent visibility annotation. No new local training, other
model framework, release replacement or poker strategy expansion is justified
by these incomplete API results. Installed desktop 1.1.1 and Poker Phase 0 remain
unchanged. No universal-vision, economic-return or completed-live claim is made.
