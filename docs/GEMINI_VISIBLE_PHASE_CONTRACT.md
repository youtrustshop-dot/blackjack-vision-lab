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

**Prepared; zero new provider inference requests at this documentation checkpoint.** Initial canonical ledger 120/121, USD6.176516500 upper, USD1.823483500 prudential margin under the unchanged **USD8** cap. All 120 entries and 15 unknown charges/reserves remain intact. The new scope allows at most four requests with aggregate worst-case reservation **USD1.2685312**; audited request ceiling 121 → 124 is applied only after all preflight checks, with a fresh epoch. PR26's unused conditional request remains closed. No key, credits, purchase, billing or auto-recharge change.

Current [official pricing](https://ai.google.dev/gemini-api/docs/pricing) was rechecked: USD0.30 per million input tokens and USD2.50 output tokens including thinking for this model. Actual usage/cost, failure, fourth-request execution and gate outcomes remain unmeasured here. An uncertain charge is retained, not declared free. The runtime is disarmed outside the one-shot experiment and closed afterward.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_visible_phase_deadline_reader.py tests/test_gemini_visible_phase_check.py -q
.venv/Scripts/python.exe -m validation.tools.gemini_visible_phase_check --prepare
.venv/Scripts/python.exe -m validation.tools.gemini_visible_phase_check --freeze-sha256 b2a5d53f9e854e83c6a4e861232f86d8d49e74f12dbeaecf027b091d09ed0f13
# Historical one-shot execution command, only within this human-authorized frozen scope:
.venv/Scripts/python.exe -m validation.tools.gemini_visible_phase_check --run --freeze-sha256 b2a5d53f9e854e83c6a4e861232f86d8d49e74f12dbeaecf027b091d09ed0f13
```

The ignored freeze/inputs are required. Preparation is single-use; execution uses durable whole-lot and per-request claims. Future runs cannot reuse consumed claims. Installed 1.1.1 remains frozen; no default reader promotion, release replacement, training, holdout, R2 or Poker expansion.
