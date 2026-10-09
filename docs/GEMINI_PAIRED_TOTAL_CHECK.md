# Gemini C/D check on two new owned scenes

Both table-only request variants read all cards and printed player/dealer totals, but claim numeric image views that were never supplied. The unchanged semantic gate correctly rejects all four responses. Neither variant passes the frozen functional gate; speed and card recognition alone do not make the state usable.

The existing ChatGPT conversation, `Progetto Blackjack visivo`, supplied a technical review directly under the human's explicit authorization. Its recommendation narrowed the preliminary five-case paid proposal to four requests: S1-C, S1-D, S2-D, S2-C. The human's autonomous continuation under the existing USD8 cap authorizes the work; the review is not financial authority. Existing chat settings were retained; Pro or a reasoning-effort selection was not verified.

## Inputs and unchanged conditions

S1 is a new owned scene: dealer 9♠ and a covered card, player 3♥ J♥, printed `DEALER TOTAL 9` and `PLAYER TOTAL 13`, `SESSION 20`, and an unlabelled 20. Hit/stand are visibly enabled and double disabled. Its reference R1 state is usable.

S2 is a separate new owned scene: dealer 9♦ and a covered card, player 5♦ J♠. Only the last digit of the printed player total changes from 15 to 18: 140 changed pixels in rectangle `[903,555,916,573]`. Cards, labels, controls and phase pixels are unchanged. The reference retains the printed contradiction; it does not substitute the engine total. This is an owned display counterfactual, not a naturally coherent game state. Its reference R1 state must abstain.

Each C/D pair receives byte-identical table PNG pixels. Only `table` is supplied, with no detail images. Both seeds are new, but scenes share the laboratory renderer and fonts with prior synthetic work. They are two functional scene checks, not full session videos, independent provider examples or a generalization estimate. Original-resolution pixels were inspected before inference; private annotation/pixels are not published.

C uses the existing structured card-limit-local configuration. D uses JSON MIME with the same logical schema in the request. Model, MINIMAL thinking, excluded thoughts, 1,024 output-token cap, local schema, numeric policy, evaluator and three-second live boundary remain unchanged. Diagnostic collection allows up to ten seconds; every collected answer is permanently excluded from the advisor, including answers below three seconds. All four pools are fresh after the read-only model-access pool is closed.

## Observed results

| Order | Variant/case | Complete response through accounting/validation | HTTP/strict JSON | Raw card inventory | Correct timely usable R1 | Grounded relevant totals |
| --- | --- | ---: | --- | --- | --- | --- |
| 1 | C / S1 | 2,766 ms | 200 / valid | Exact | No | No |
| 2 | D / S1 | 1,829 ms | 200 / valid | Exact | No | No |
| 3 | D / S2 | 2,656 ms | 200 / valid | Exact | Expected abstention | No |
| 4 | C / S2 | 2,625 ms | 200 / valid | Exact | Expected abstention | No |

Strict JSON: **4/4**. Exact card transcription: **4/4**, including **12/12 ranks, 12/12 suits and 4/4 backs**; phase and enabled controls match all four. Correct usable positive states: **0/2**, or **0/1 per variant**. Safe negative rejections: **2/2**, or **1/1 per variant**. Grounded correct-content negative rejections: **0/2**. False accepted R1 states: **0/4**. Exact relevant total provenance and complete semantic/literal transcriptions: **0/4**. No HTTP failure or ten-second diagnostic timeout occurs.

The inherited pre-semantic transcription evaluator and the authoritative semantic R1 gate are separate layers. Card/component correctness cannot bypass that final gate. The public summary explicitly publishes the semantic gate fields; original private collector/evaluator evidence remains intact.

Both variants report the correct dealer/player total values and labels but set their source images to `dealer` and `player:0`. D/S1 additionally places the unlabelled 20 in `controls`. None of these three images was supplied. `source_view_not_available` correctly blocks the states. S2 also produces the arithmetic rejection for printed 18 versus visible-card 15. These safe rejections do not demonstrate complete grounding, because wrong source views already independently reject them.

This repeats a concrete request ambiguity: the table-only payload retains a numeric-view enum containing four possible global names, while its layout describes dealer/player regions. The observations support fixing that contract. They do not establish the model's hidden reasoning or prove that one field alone caused every response. The next opt-in builder should derive allowed numeric image names from the actual image packet and explicitly distinguish card role from supplied image name. Do not remap returned views, relax the gate or retroactively repair these scores. Restricting source names still does not prove an invented label exists in pixels.

## Preliminary offline local comparison

Before the narrower review arrived, five owned exploratory scenes were prepared: labelled totals, rotation plus unlabelled UI, overlapping indices, an unreadable popup-covered face, and a settled hand. Current-local and specialized-local were both run without provider inference, manual turn confirmation or simulator phase/ID injection.

Each reader obtains **0/3 correctly usable positives, 2/2 safe negative rejections and 1/5 exact full-card states**. Even when positive cards are read, player phase is not established. Rotation adds missing/wrong cards; suits remain incomplete. The local readers do not implement the numeric wire contract; their projected numeric metrics are transcription diagnostics, not a new supported feature.

The proposed paid calls on those five inputs were superseded **before any submission**. None was sent to a provider. Keep this exploratory evidence separate from the four paired total checks and from the older trained-reader benchmark. No weight, threshold, model or training changes were made.

## Cost, retention and verification

Before the lot, the exact authenticated model GET verified `gemini-3.5-flash-lite` access and limits. Official Standard prices checked on 8 October 2026 are USD0.30 per million input tokens and USD2.50 per million output tokens including thinking. [Pricing](https://ai.google.dev/gemini-api/docs/pricing), [model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [generation configuration](https://ai.google.dev/api/generate-content).

| Case/variant | Reported input/output tokens | Usage-based USD upper |
| --- | --- | ---: |
| S1-C | 1,545 / 391 | 0.0014410 |
| S1-D | 1,976 / 250 | 0.0012178 |
| S2-D | 1,976 / 226 | 0.0011578 |
| S2-C | 1,545 / 352 | 0.0013435 |

New usage-based upper: **USD0.0051601**. Final canonical ledger: **115/115**, accounted upper **USD6.170206000**, prudential money margin **USD1.829794000**, unchanged aggregate cap **USD8**. All 111 previous entries and 15 uncertain-charge reserves remain intact; uncertain reserves still total **USD5.9595464**. This is not a verified invoice, current account balance or authorization to spend the whole remaining amount.

Existing Gemini credentials were reused without disclosure. Selected response text was encrypted with current-user Windows DPAPI, recovered and hash-verified. Raw envelopes, headers, keys and encrypted-record identifiers stay private. All pools closed and the runtime returned to disarmed after exactly four calls. No retry, warm-up, hybrid, following automatic batch or advisor delivery.

The full suite passed **850 tests and 10 subtests**, with two existing warnings, in **98.70 seconds** before inference. Twenty-five new networkless tests cover owned-corpus separation, counterfactual pixels/reference, strict negative cases, frozen ordering, payloads and execution limits. Frontend tests/TypeScript/Vite passed on the unchanged PR23 source in CI; no new local UI run. Current receipts: [verification.json](../validation/results/gemini-paired-total-check/verification.json). Results: [summary.json](../validation/results/gemini-paired-total-check/summary.json), [offline-local.json](../validation/results/gemini-paired-total-check/offline-local.json).

## Historical execution commands

```powershell
.venv/Scripts/python.exe -m validation.tools.gemini_new_session_prepare --prepare
.venv/Scripts/python.exe -m validation.tools.gemini_new_session_prepare --local --freeze-sha256 365b6ee2d0f973755c1de561aebe0b114fa46762fb01263be47989d7bd0f276f
.venv/Scripts/python.exe -m validation.tools.gemini_paired_total_check --prepare
.venv/Scripts/python.exe -m validation.tools.gemini_paired_total_check --run --freeze-sha256 a068fce367d04434c28637df2e75d0e337bd8fe54c2f42dddf19674c8fcfb1a7
```

Execution and per-request claims are consumed and cannot run twice. These commands document history, without reopening the scope. Networkless tests remain rerunnable:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_gemini_new_session_prepare.py tests/test_gemini_paired_total_check.py -q
.venv/Scripts/python.exe scripts/check-evidence.py
```

No latency p95, champion, provider transfer, actual capture-to-display, session identity, shoe count, physical monitor/DPI/minimized-screen check, new installed build, training, holdout or R2/Poker is established by this lot. Preserve the negative result and test the request-contract correction separately.
