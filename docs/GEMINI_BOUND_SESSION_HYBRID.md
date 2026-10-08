# Three new Gemini states; conditional hybrid remains closed

The corrected table-only Gemini request reads all cards in three new owned scenes. Both player-decision states are correct and usable within three seconds. The ended hand is safely rejected, but its returned phase is `waiting` rather than the frozen reference `settled`. That fails the predeclared gate, so the fourth local-first hybrid was **not executed**. The result is useful new evidence and an integration check, not promotion of a live reader.

## Frozen experiment and observed results

This lot keeps PR25's model, D JSON-MIME payload profile, thinking/output caps, global schema, semantic gate, evaluator and local reader unchanged. Three distinct seeds change card states, rank fonts and palettes. They still share the owned renderer, layout, control font and suit glyphs. These are **three sampled states**, not three complete sessions or external-provider validation. The fourth input was also frozen before any request and remains unconsumed.

Original 1,024 × 768 pixels were inspected against the isolated renderer references before submission. No phase, expected card, turn-confirmation flag or oracle is supplied to the reader. Each diagnostic gets one request and a separate ten-second collection ceiling; timeliness remains strictly **less than 3,000 ms**. A diagnostic never emits an advisor payload, even when timely.

| New state | Complete validated observation | Exact cards | R1 result | Residual |
| --- | ---: | --- | --- | --- |
| Labelled totals: player 9 / dealer 10 | 1,828 ms | Yes | Correct usable positive | Complete semantic and literal transcription |
| Rotated hearts and unlabelled 20 | 1,563 ms | Yes | Correct usable positive | Unlabelled 20 declared `ui`, reference `unknown` |
| Ended hand, disabled decision buttons | 1,734 ms | Yes | Safe abstention | Phase `waiting`, reference `settled` |

All **3/3 HTTP200** and strict JSON responses arrived inside the unchanged live boundary. Combined: **11/11 ranks, 11/11 suits, 2/2 backs**, exact card inventory **3/3**, enabled controls **3/3**, exact phase **2/3**, correct timely usable positives **2/2**, safe negative abstention **1/1**, false accepted R1 states **0/3**. Complete semantic and literal transcription are each **1/3**. Correct *complete* negative transcription is **0/1**, despite the safe abstention.

Relevant decision-total provenance is exact in **3/3 cases**, including absence of fabricated totals. Only the first scene contains explicit player/dealer totals: **2/2 numbers in 1/1 scene**. This is not six independent total readings. All numeric source names are `table`; no absent image is credited. The rotation's `ui`/`unknown` error remains in full numeric metrics and is not silently repaired.

The three-observation sample median is **1,734 ms**, range **1,563–1,828 ms**. No operational p95, capture-to-display latency, speed improvement or champion is inferred from this sample.

## Why the fourth attempt stayed closed

Before inference, the selector required two exact timely positives, one correctly transcribed and rejected terminal state, exact cards/phase/controls/relevant totals, zero false accepts, valid retained receipts and settled usage. The negative phase mismatch fails that conjunction. A safe rejection or three HTTP200 replies cannot open the conditional slot. No replacement scene, repeat request or relaxed criterion followed.

The ended pixels contain player Q♥, 5♦, 10♠ (25), dealer 10♠, 9♦ (19), enabled **NEW HAND** and disabled **HIT/STAND/DOUBLE**. The model preserves those cards and enabled decision controls `[]`. Its blockers and table-presence fields also match. The exact difference is `waiting` versus `settled`, not missed cards, false enabled buttons or a missing-image rejection.

The unchanged request enumerates these phase names without a visible rule distinguishing them. A single post-hand image does not itself establish how that taxonomy should separate a completed hand from waiting for the next one. Therefore the evidence establishes a **mismatch with the frozen phase reference**; attributing it exclusively to a perception defect would go beyond the test. The renderer reference, historical score and failed gate remain unchanged.

A [post-hoc offline contract audit](../validation/results/gemini-bound-session-hybrid/phase-contract-audit.json) changes only the phase field of the known reference to each of the two names. Both fabricated projections validate under the unchanged strict contract and both block R1. This checks legal representations and the safety gate; it is **not** a pair of independently rendered histories, proof that both physical phases are correct, a new model result or a reason to reopen the failed slot.

The subsequent [bounded offline observability audit](../validation/results/gemini-bound-session-hybrid/phase-observability-audit.json) instead renders **two legitimate adjacent stages** from the unchanged timeline. The terminal image reproduces the consumed pixels exactly; the next waiting stage has an empty table and **DEAL**. Both use the same layout, native table view, source size, font and palette. Original-resolution inspection confirms the terminal's final cards, **NEW HAND** and disabled decision controls. The images differ in **119,430 decoded pixels**. These two stages are visibly distinguishable: this audit demonstrates no single-frame collision and does not establish an impossible perception task.

The audit also inspects the actual serialized request and reference assignment sites. The phase field enumerates `player/dealer/waiting/settled/unknown` without a description; the prompt asks for visible phase and uncertainty, but does not define a rule separating `waiting` from `settled`. The internal renderer assigns the terminal phase and different buttons explicitly. This isolates a **missing phase naming rule in the request**, while the model's exact reason for returning `waiting` remains unknown. It does not make that answer correct under the frozen benchmark.

Eight fabricated, networkless fixtures exercise the unchanged integrated reader, gate and solver. The actual ended reference remains blocked for all four tested phase values, with zero solver calls; it has several independent blockers, so it cannot isolate the phase gate. An otherwise valid player-decision fixture does isolate it: `waiting`, `settled` and `unknown` each block presentation and call no solver; only `player` presents a payload and calls the solver once. These are contract assertions, **not eight model observations or additional pytest tests**. No provider requests, ledger changes or historical score changes occurred.

Future phase clarification must be versioned before new inference and keep this batch as a consumed regression. A distinction without an observable signal belongs to a temporal state layer or explicit uncertainty; no such collision was demonstrated here. This audit does not add a phase alias, weaken R1, reopen the fourth slot or recalculate the batch as a success.

## Opt-in adapter and integrated offline proof

`AvailableViewDeadlineReader` builds the same byte-checked D request tested in PR25 while inheriting `CaptureDeadlineReader.read()` and its absolute capture deadline. It is separate from production defaults. `FrozenRequestReader.read()` remains diagnostic-only and is not reused as a live reader.

**37 new networkless tests** exercise the real adapter and `local_first_attempt` with a controlled transport. They intercept the actual posted request and verify identical D payload, supplied image bytes, one post at most and `capture timestamp + 3 s`. A completed but semantically forbidden response calls no solver and emits no advisor payload. Fixtures cover absent source views, contradictory totals and a correctly formed settled state with disabled controls. A sufficient local result uses zero cloud requests.

A controlled monotonic clock covers time consumed by local reading, semantic checking, solver and serialization. Repeated fresh identical captures cannot renew the original deadline. Pixel, geometry, table and source changes reject pending results; returning to the old pixels or reconnecting does not revive them. The selector rejects missing/storage/evaluation/accounting failures and the exact 3,000 ms boundary.

The prepared headless helper would use the frozen current local reader, natural routing and a 12 Hz held-pixel producer. It records initialization before capture separately, observed capture count/gaps/latest age and the original stamp. Its post-read protected storage lies outside the presentation clock. **None of those producer, solver or hybrid timings was measured here**, because the selector failed. Nominal 12 Hz is configuration, not an observed runtime result.

The concrete local path is `FrozenGroundedLocal(FrozenLocalObservation())`, backed by `LocalVisionReader`, which supplies unknown phase and empty controls by construction. A later functional fallback test with it could validate integration; it would not measure API savings or an autonomous local success rate. No expected outcome or forced-fallback flag enters that path.

The pre-inference suite passed **916 Python tests and 10 subtests**, with two existing warnings, in **103.94 s**; the 37 targeted tests passed in **1.41 s**. Both PR25 CI checks passed, including 52 frontend tests and TypeScript/Vite. UI source is unchanged and was not rerun locally for this increment. The directly received technical review in **Progetto Blackjack visivo** informed the integration checks; it inspected PR25 publicly, not this unpublished runner or private receipts. No Pro/effort setting is claimed as verified.

## Accounting and reproducibility

| State | Reported input/output tokens | Usage-based USD upper |
| --- | --- | ---: |
| Labelled totals | 2,072 / 342 | 0.0014766 |
| Rotation | 2,072 / 187 | 0.0010891 |
| Ended hand | 2,072 / 288 | 0.0013416 |

The new usage upper is **USD0.0039073**. Canonical ledger **120/121**, accounted upper **USD6.176516500**, prudential margin **USD1.823483500**. Aggregate monetary cap remains **USD8**. All 117 old entries and 15 uncertain charges/reserves, totaling USD5.9595464, remain intact. Durable network claims are 119 across the lifetime; a claim alone does not prove an HTTP body was sent. These figures are not an invoice or verified account balance.

The exact model and limits were verified by read-only metadata before inference; same-day official price verification is retained. [Official pricing](https://ai.google.dev/gemini-api/docs/pricing), [model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite). Each diagnostic used a fresh scoped pool. No retry, paid warm-up, new key, credit purchase or billing change. Selected response text was encrypted with current-user Windows DPAPI, recovered and hash-verified. Keys, headers, full envelopes, selected texts, private pixels and encrypted-record identifiers are excluded from public artifacts.

The runtime is **disarmed**, every pool is closed and the single unused conditional slot is closed. Installed desktop **1.1.1 at `4f074ef`** remains unchanged. Machine-readable evidence: [summary.json](../validation/results/gemini-bound-session-hybrid/summary.json), [verification.json](../validation/results/gemini-bound-session-hybrid/verification.json).

Historical commands:

```powershell
.venv/Scripts/python.exe -m validation.tools.gemini_bound_session_hybrid --prepare
.venv/Scripts/python.exe -m validation.tools.gemini_bound_session_hybrid --run --freeze-sha256 57cdefc57c2a3b014caa48a1372efb5454331fe58271cb161cfa94e7e660bd7f
.venv/Scripts/python.exe -m pytest tests/test_available_view_deadline_reader.py tests/test_gemini_bound_session_hybrid.py -q
.venv/Scripts/python.exe -m validation.tools.terminal_phase_audit --freeze-sha256 57cdefc57c2a3b014caa48a1372efb5454331fe58271cb161cfa94e7e660bd7f
.venv/Scripts/python.exe scripts/check-evidence.py
```

The execution claim and three request claims are consumed. The run cannot reopen the closed scope; rerunnable offline tests do not authorize new inference. The audit requires the original ignored freeze/inputs and writes a new private output directory only once; the published receipt contains hashes and assertions, not those private pixels. Final holdout, training, R2/session identity/shoe reconstruction and new Poker strategy were not opened. Physical Windows screen capture, popup rendering, multi-monitor/DPI and minimized capture remain unverified. External generalization and end-to-end session reliability remain work to demonstrate.
