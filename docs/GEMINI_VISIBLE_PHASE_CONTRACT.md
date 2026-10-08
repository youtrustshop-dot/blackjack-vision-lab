# Visible phase vocabulary; bounded new 3+1 check

PR26 preserved a terminal `waiting`/`settled` mismatch and did not run its conditional hybrid. Its offline audit found distinct visible terminal and empty-table controls, while the actual request did not define the phase names. VISION-033 adds an **opt-in request instruction** defining those names before any new inference. It does not repair old answers or change the wire schema, numeric policy, integrity gate, evaluator, solver, local weights or installed desktop.

## Observable convention

| Phase | Required visible evidence in this research profile |
| --- | --- |
| `settled` | Cards remain; NEW HAND enabled; player decision buttons disabled. This takes precedence over the informal idea of awaiting another hand. |
| `waiting` | Empty card area and enabled DEAL. |
| `player` | Visibly enabled player decision controls. Unreadable cards remain unreadable and cannot bypass R1. |
| `dealer` | Explicit visible active dealer-turn indication. |
| `unknown` | Missing, obscured, conflicting or ambiguous signals. |

NEW HAND/DEAL inform phase only; they are not added to the supported decision-action enum. Internal round IDs, oracle phases and card-derived totals never enter the request. All returned fields still undergo unchanged strict and semantic validation. No response alias or post-response mapping is introduced.

## Frozen lot

Three new owned sampled states cover a labelled player decision, a completed hand with disabled controls and the naturally following empty waiting stage from another timeline. A fourth independent owned seed supplies an overlapped-card **conditional** local-first input. Seeds, fonts and palettes change; renderer, layout, control font and suit glyphs remain shared. These are sampled states, not complete independent sessions or external provider transfer.

Freeze: `b2a5d53f9e854e83c6a4e861232f86d8d49e74f12dbeaecf027b091d09ed0f13`. Model: `gemini-3.5-flash-lite`; bound table-only D request plus the visible-phase instruction, MINIMAL thinking, no thoughts, max output 1,024. Original 1,024 × 768 inputs were inspected before inference. Only reviewed owned images are eligible for submission; final holdout stays closed.

Before a fourth request, **all three** fixed observations must have exact cards, phase, controls, relevant-total provenance and complete semantic transcription, valid retained receipts and settled usage, one correct usable player state, two correct abstentions and no false accepted R1 state. Complete validated observations must arrive **strictly before 3,000 ms**. The diagnostic collection ceiling of ten seconds never extends the live deadline. Failed quality closes the fourth slot; storage/access/accounting failure stops the lot. No retry, replacement input or paid warm-up.

The new deadline adapter inherits the actual absolute capture deadline and current-evidence checks. It adds only the phase instruction to the validated bound request. Offline fixtures verify the request at the actual post, isolated phase rejection before solver, numeric/source rejection, changing/reappearing evidence, zero-cloud sufficient local routing and expiry during local reading, gate, solver and serialization. Conditional selector fixtures reject incomplete/unsafe receipts and the 3,000 ms boundary.

If opened, the single functional hybrid uses `FrozenGroundedLocal(FrozenLocalObservation())`, natural routing, a held-pixel producer at nominal 12 Hz and the unchanged three-second capture-through-headless-JSON boundary. Capture count/gaps/age, original stamp, routing, local/cloud/gate/solver/serialization timing and correctness against the fourth reference will be recorded. This local implementation has unknown phase and empty controls by construction; the test cannot measure API savings. The held producer is not Windows capture, native popup paint, minimized sharing, tracking or shoe reconstruction.

## Accounting and current execution status

**Executed and closed: three provider requests; fourth hybrid not executed.** Initial canonical ledger 120/121, USD6.176516500 upper, USD1.823483500 prudential margin under the unchanged **USD8** cap. Read-only exact model/access, current prices, frozen source/pixels and protected retention checks passed before inference. Request ceiling 121 → 124 was audited for this fresh epoch; all 120 old entries and 15 unknown charges/reserves remain intact. The original maximum four-request reservation was **USD1.2685312**. Both PR26's unused request and this lot's unconsumed conditional fourth remain closed. No key, credits, purchase, billing or auto-recharge change.

Current [official pricing](https://ai.google.dev/gemini-api/docs/pricing) was rechecked: USD0.30 per million input tokens and USD2.50 output tokens including thinking for this model. Reported usage for the three calls totals input6,786/output500 tokens; upper charge **USD0.0032858**. This is usage accounting, not an independently verified invoice. Final canonical ledger **123/124**, upper **USD6.179802300**, prudential margin **USD1.820197700**; all 15 unknown reservations **USD5.9595464** unchanged. Runtime is disarmed with zero request/spend scope, all transport pools closed, no automatic next lot. Protected storage grows25→29: one preflight and three selected outputs; none deleted.

## Observed result

| New owned sampled state | Complete validated observation | Cards/phase/controls exact | Usable player R1 / safe abstention | Complete semantic transcription |
| --- | ---: | --- | --- | --- |
| Labelled player | 1,656 ms | Yes | Correct timely R1 | Yes |
| Completed hand | 1,547 ms | Yes | Safely abstained | **No: SESSION label missing** |
| Empty waiting table | 1,390 ms | Yes | Safely abstained | Yes |

All three are HTTP200 and strict JSON. Ranks **10/10**, suits **10/10**, backs **1/1**, exact card inventories **3/3**, phases and controls **3/3**. The empty case contributes no rank/suit/back examples. Timely positive **1/1**, safe negatives **2/2**, false accepted R1 **0/3**. The labelled positive contains two decision totals with correct printed values, labels, roles and source; the other two cases have no decision totals. Relevant-total checks **3/3** include that exact absence, not six positive total reads.

The completed hand returns20 with correct `ui` role and `table` view, but `label=null` despite visible SESSION. This omits one **non-decision** label: semantic numeric provenance matches **4/5**, and complete semantic/literal transcription is **2/3**. It does not fabricate a player/dealer total or permit a false R1 state. Nevertheless, the predeclared gate requires all three complete transcriptions; it fails. **No fourth request, actual hybrid, held-frame producer, solver timing or headless presentation was executed.** The gate was not weakened or rewritten after seeing the results.

Observed offline latency min1,390/median1,547/max1,656ms; timeout/failure **0/3**. This includes request collection, usage settlement and unchanged validation, with protected storage separate. DNS/model-access preparation is recorded separately. These are three sampled offline observations, not operational capture-to-display p95 or a reliability estimate.

PR26 had phase2/3/full transcription1/3; this new lot has phase3/3/full transcription2/3. **Both the instruction and input states changed**, so this comparison is not a paired causal estimate or proof that every previous phase error was caused by missing vocabulary. The prior scores, sources, request pixels and closed fourth remain preserved. The current improvement in phase is useful within these new cases; it does not promote the reader or hybrid.

**Decision:** retain the opt-in phase contract and the measured progress, retain the missing-label failure, close the scope. The next paid experiment is not automatically authorized. Forward registry entries VISION-028–032 point to already published reports; their results were not rerun or overwritten.

Verification: **45** new networkless tests; full **961 passed +10 subtests** in101.83s (two existing warnings). Frontend **52** passed locally and TypeScript/Vite build passed after registry reconciliation. [Sanitized result](../validation/results/gemini-visible-phase/summary.json) and [source verification](../validation/results/gemini-visible-phase/verification.json). Original input PNGs, complete selected texts and record identifiers stay private; selected text hashes were recovered and verified.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_visible_phase_deadline_reader.py tests/test_gemini_visible_phase_check.py -q
.venv/Scripts/python.exe -m validation.tools.gemini_visible_phase_check --prepare
.venv/Scripts/python.exe -m validation.tools.gemini_visible_phase_check --freeze-sha256 b2a5d53f9e854e83c6a4e861232f86d8d49e74f12dbeaecf027b091d09ed0f13
# Historical one-shot execution command, only within this human-authorized frozen scope:
.venv/Scripts/python.exe -m validation.tools.gemini_visible_phase_check --run --freeze-sha256 b2a5d53f9e854e83c6a4e861232f86d8d49e74f12dbeaecf027b091d09ed0f13
```

The ignored freeze/inputs are required. Preparation is single-use; execution uses durable whole-lot and per-request claims. Future runs cannot reuse consumed claims. Installed 1.1.1 remains frozen; no default reader promotion, release replacement, training, holdout, R2 or Poker expansion.
