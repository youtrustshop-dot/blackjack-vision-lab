# Bind numeric provenance to supplied image names

The corrected table-only Gemini JSON request passes the two diagnostic controls: the coherent hand becomes usable in 1,828 ms, while the contradictory printed total is read and rejected in 2,110 ms for arithmetic alone. Both cite only the supplied `table` image. This repairs the request mismatch on the consumed cases without changing the local gate or rewriting previous failures.

## Request correction

The previous table-only requests allowed `table`, `dealer`, `player:0` and `controls` in `n[].w`, even though only `table` was sent. The calibrated layout also described dealer/player regions. Four PR24 responses cited absent detail images and were correctly rejected. This proves the request exposed a broader domain than the packet allowed; it does not identify the model's internal reasoning or separate the effects of the enum and instructions.

The new **opt-in** `gemini-available-image-views-v1` builder derives numeric image names from the immutable `frame.images()` packet, verifies every serialized image name and byte sequence, and copies the existing schema independently. For table-only input the effective `LiveNumber.w` enum is `["table"]`. `c[].z` remains the card role; `n[].r` remains the numeric role. Layout keys, oracle annotations and expected outcomes do not determine image names.

The instruction distinguishes regions from supplied images and asks the model to retain visible numbers, associated labels and contradictions. For C, the restriction reaches the schema referenced by `n.items` in the provider grammar; the earlier omission of `c.maxItems` remains. For D, the restriction is in the logical schema inside the JSON-MIME prompt. **D is still enforced locally; putting a schema in its prompt does not add provider grammar enforcement.**

Only request instructions and the request-specific numeric-view enum change. Image pixels, model, thinking/output caps, global wire schema, local card-count/numeric/math validators, semantic evaluator, deadline and production defaults remain intact. No returned view is remapped. This is one declared functional intervention with two request changes, not a causal ablation of each change separately.

The directly received review in `Progetto Blackjack visivo` supports the fix and recommends two D controls. It inspected PR23 publicly; PR24 private outcomes were relayed facts, not independently executed by that reviewer. The initial C-only preparation was superseded before any submission or ledger mutation. Its freeze remains private and marked unexecuted. C has offline payload coverage but no new API result in this increment.

## Before and after on identical consumed pixels

| Case | Original D | Corrected D | Diagnostic outcome |
| --- | --- | --- | --- |
| S1: coherent player 13 / dealer 9 | 1,829 ms; cites absent views, blocked | 1,828 ms; all views `table`, usable | Correct timely positive **1/1**; both relevant totals retained |
| S2: cards 15 / printed player 18 | 2,656 ms; wrong views plus arithmetic rejection | 2,110 ms; all views `table`, arithmetic rejection only | Grounded correct-content abstention **1/1**; printed 18 retained |

Each corrected response has exact cards: **6/6 ranks, 6/6 suits and 2/2 backs** combined; phase and enabled controls are correct **2/2**. Strict JSON **2/2**, relevant player/dealer total provenance **2/2**, false accepted R1 states **0/2**. S2's only rejection is `Observed player total disagrees with the cards.` No missing image or malformed JSON supplies the negative rejection.

Complete semantic transcription is **1/2**, not 2/2. S1 still declares the unlabelled 20 as `ui` rather than reference `unknown`; this is nonblocking for R1 but a real numeric-role error. Literal exact transcription is **0/2**, with label formatting retained separately from semantic equivalence. Do not hide these residuals behind card accuracy.

These are two now-consumed owned scenes shared with PR24, not new independent validation or provider transfer. Single before/after observations do not establish speed improvement, operational p50/p95, universal grounding or a champion. Restricting source names guarantees that the named channel was supplied; it does not prove an invented label appears in that channel's pixels.

## Verification and accounting

The final source suite passed **879 Python tests and 10 subtests**, with two existing warnings, in **102.72 seconds** before inference. **29** new networkless checks cover actual packet derivation and bytes, duplicate/unsupported names, effective schema references, role preservation, independent schema copies across table/control requests, unchanged global contract, a coherent positive, arithmetic-only negative, omission as false accept, and permanent diagnostic exclusion. Both PR24 CI checks passed; unchanged frontend tests/TypeScript/Vite were verified there, without a new local UI run.

Exactly two D requests ran, once each, with ten seconds allowed for diagnostic collection and the unchanged three-second measure of timeliness. All HTTP200. Both requests used fresh pools after the read-only exact-model access GET. No retry, paid warm-up, hybrid, automatic deployment or advisor delivery. All selected texts were encrypted with current-user Windows DPAPI, recovered and hash-verified; keys, headers, raw envelopes, pixels and encrypted-record IDs stay private.

| Case | Reported input/output tokens | Usage-based USD upper |
| --- | --- | ---: |
| S1 | 2,072 / 240 | 0.0012216 |
| S2 | 2,072 / 224 | 0.0011816 |

New usage upper **USD0.0024032**; canonical ledger **117/117**, accounted upper **USD6.172609200**, prudential margin **USD1.827390800**. All 115 old entries and 15 uncertain reserves, totaling USD5.9595464, remain intact. Aggregate monetary cap remains **USD8**. These receipts are not an invoice or verified account balance. The exact `gemini-3.5-flash-lite` access/limits and current prices were checked before this bounded lot. [Official pricing](https://ai.google.dev/gemini-api/docs/pricing), [model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

The runtime is disarmed and every transport closed. Full machine-readable outcomes and source receipts: [summary.json](../validation/results/gemini-available-image-views/summary.json), [verification.json](../validation/results/gemini-available-image-views/verification.json).

## Historical commands and remaining evidence

```powershell
.venv/Scripts/python.exe -m validation.tools.gemini_available_view_check --prepare
.venv/Scripts/python.exe -m validation.tools.gemini_available_view_check --run --freeze-sha256 a1bd1a4b49037a41942fe8ba3044ed3c8fd368c64c84bcf3f069f558a63c0af3
.venv/Scripts/python.exe -m pytest tests/test_available_image_views.py tests/test_gemini_available_view_check.py -q
.venv/Scripts/python.exe scripts/check-evidence.py
```

The run and per-request claims are consumed; the historical commands cannot reopen them. Offline tests remain rerunnable. Preparation material stays ignored and owned, with the final holdout closed. Installed desktop 1.1.1 and historical PRs are preserved.

New session cases, an actual local-first hybrid, physical capture-to-display, native monitor/DPI/minimized capture, session identity/shoe reconstruction, training and R2/Poker were not performed in this increment. The next useful evidence is new scene/session validation of this frozen request profile, then a separately bounded headless hybrid if its correctness and timing gates pass.
