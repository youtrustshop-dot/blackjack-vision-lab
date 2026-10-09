# Native view consistency and Gemini request controls

Changing a detail crop while keeping the main table image unchanged used to leave a pending hybrid response eligible for the solver. `CurrentEvidence` now binds every named image, its layout and source geometry. The reproduced fixture is rejected after the change. This is a packet-consistency fix in the controlled research path, not evidence that this fault occurred in a provider session.

Five Gemini request controls are prepared and hash-verified offline. No provider inference, model-access check, credential read, budget amendment or automatic next batch ran. PR21's paid diagnostics and installed desktop 1.1.1 remain unchanged.

## Pending responses bind all views

Previously, the fingerprint contained only the table PNG and layout. A detail could change without advancing the motion epoch. The new fingerprint also includes each detail's name, order and bytes, source dimensions and table rectangle. Removing, adding or renaming a view invalidates a pending response. Returning to the old crop does not restore its eligibility.

Revalidation also recomputes the current packet fingerprint. Mutating a captured layout dictionary without another capture fails closed. Stable subsequent frames can preserve continuity, but neither a new frame ID nor another capture renews the original three-second deadline. The existing 250 ms continuity limit and source/table epoch checks are retained.

| Controlled fixture | Before | After |
| --- | --- | --- |
| Same table/layout, changed detail bytes | Pending result valid; motion epoch 0 | Rejected; motion epoch 1 |
| Crop changes during mocked cloud fallback | Previously unbound detail | No solver call and no advisor payload |
| Mutable layout changes after capture | Not covered by the old fingerprint recheck | Rejected as captured_packet_mutated |

These checks establish packet identity, not the origin of an arbitrary initial crop. The usual `prepare_frame` producer derives all views from one acquisition. The new preparation tool separately compares decoded detail pixels with their declared table crop; an initially mixed packet is rejected in that offline preparation. This audit is not newly wired into every runtime input path.

## Five Gemini controls

The original case is the consumed, owned `fresh-rotated-unknown` hand from PR19. It has an unlabelled 20 near the dealer region and a separate SESSION 20. Repeating it diagnoses a failure; it is not new independent validation.

| Cell | Image input | Output serialization | Pixel change |
| --- | --- | --- | --- |
| A | Original table plus three native details | Existing structured-card-limit-local | None; reproduces the consumed request |
| B | Same four views | JSON MIME, logical schema in instructions | None |
| C | Original table only | Existing structured-card-limit-local | None |
| D | Original table only | JSON MIME, logical schema in instructions | None |
| E | Table plus three details regenerated together | Existing structured-card-limit-local | BET added beside the unlabelled 20 |

All five keep the same Gemini model, MINIMAL thinking with thoughts excluded, 1,024 output-token cap, local wire contract and numeric policy. Only the isolated preparation aligns the JSON MIME variants' explicit thinking setting with the structured variants; the frozen live reader is unchanged.

The Gemini documentation defines JSON MIME output and the thinking configuration fields. The new JSON-plus-MINIMAL combination has not been submitted, so field compatibility is not an empirical success claim. [Generation configuration](https://ai.google.dev/api/generate-content), [thinking levels](https://ai.google.dev/gemini-api/docs/thinking).

A/B and C/D compare serialization. A/C and B/D jointly change image load and the evidence views, so a faster response would not isolate server computation. A/E changes only visible label pixels, without telling the model the expected answer. The original 20, cards and controls stay in place. Assistant inspection confirms the table-only source is legible and BET does not cover the number; this is not independent human annotation.

Each cell declares only views actually sent. BET plus 20 is fully visible in the table, but clipped in the dealer detail, so E's label attribution allows only the table view. BET is not added to the frozen finite normalization grammar: literal label differences remain measurable.

## Acceptance and accounting

Any future collection must report three separate outcomes: gate acceptance, agreement with the pixel/reference annotation, and completion within the unchanged three-second live limit. Use the common semantic evaluator alongside literal transcription. A structurally accepted invented label remains a false attribution; gate acceptance alone is not correctness.

The proposed diagnostic collector can wait at most ten seconds, but no cell is advisor eligible, including a response below three seconds. One response per cell cannot establish operational p95, generalization, a champion, or the internal cause of latency. No retry, paid warm-up or following hybrid is proposed.

The canonical ledger remains byte-identical at 106/106 requests, USD 6.156175900 accounted upper under the existing USD 8 cap, with all 15 unknown-charge reserves retained. Its prudential monetary margin is USD 1.843824100; it is not an account balance. Five historical Gemini reservations total USD 1.5856640 and would leave USD 0.258160100. The current request ceiling is exhausted and unchanged. A new bounded human scope, current access/prices and protected-storage preflight are prerequisites to submission.

The authoritative local preparation freeze is:

`3783df4d50421c79df3cc2575f2f8ced8577f73c384af9e3723a1859e789876e`

Private pixel inputs, reference annotations, request bodies and the external review transcript stay in ignored local artifacts. The public summary contains hashes, controls and offline outcomes.

## Reproduction

Run the packet and preparation regressions without credentials or provider access:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_native_view_identity.py tests/test_gemini_ablation_preparation.py -q
```

The full suite is `.venv/Scripts/python.exe -m pytest -q`; current executed counts are recorded in [verification.json](../validation/results/frame-view-consistency/verification.json).

With the retained private PR19 inputs and ledger present, prepare into a new, unused directory:

```powershell
.venv/Scripts/python.exe -m validation.tools.gemini_request_ablation --output artifacts/gemini-request-controls-reproduction
```

That command prints its own freeze hash. Verify that directory using the printed hash:

```powershell
.venv/Scripts/python.exe -m validation.tools.gemini_request_ablation --output artifacts/gemini-request-ablation-preparation-20261007-final --verify-freeze-sha256 3783df4d50421c79df3cc2575f2f8ced8577f73c384af9e3723a1859e789876e
```

The tool exposes preparation and verification only; it has no submission command. The authoritative preparation and verification completed with socket creation and DNS denied, while the ledger bytes stayed identical.

## Delivery scope

The external ChatGPT review was received in the existing Blackjack conversation and its concrete packet-consistency concern was independently reproduced before implementation. The conversation's current settings were retained; Pro and reasoning effort were not overridden or verified.

Source changes cover packet identity and offline experiment preparation. They do not promote a reader, retrain weights, change thresholds, open final holdouts, expand R2/Poker, replace the installed release, or establish physical Windows capture/advisor/session reliability. Historical model outcomes remain in [PR21's diagnostic report](TWO_PROVIDER_DIAGNOSTICS.md).
