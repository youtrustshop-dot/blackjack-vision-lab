# Rejected observation diagnostics, offline only

VISION-026, 2026-10-07, based on PR19 at 1770c32. **The diagnostic gap is
addressed for future opt-in owned synthetic trials. Zero new provider requests,
no repaired historical response and no live candidate promotion.** This change
does not establish Gemini correctness or Luna latency.

The four-request lot remains closed: Luna timed out twice while awaiting
response headers on established connections; Gemini delivered one valid R1 and
one HTTP200 output rejected at n[0]. The missing 566-byte output is still missing.
Its hash cannot reveal its number or label, and it is not attributed to the 20
badge. Connection reuse was already exercised in PR19; no new reuse fix or
causal speedup is claimed.

## What changes and what stays frozen

New opt-in modules:

- bjlab/rejected_output_diagnostics.py taps one bounded assistant output_text in
  memory BEFORE the unchanged reader validates it, then records the diagnosis
  after that reader has finished. It delegates exactly once with the same
  payload, reservation and original three-second deadline.
- bjlab/private_observation_store.py stores selected text, contract/policy,
  payload/image hashes, and the local rejection record in current-user Windows
  DPAPI ciphertext under the ignored artifacts/rejected-observation-diagnostics
  directory. Only the current user and SYSTEM have directory grants.
- validation/tools/rejected_output_offline.py exercises fabricated contract
  examples and an actual Windows encryption/decryption round trip, with sockets
  and DNS disabled. It is an offline command, not a paid execution controller.

These modules are not wired into the default reader, app, advisor or old paid
controllers. Frozen live_state, numeric_provenance, paired_deadline_reader,
paired_persistent_http, prompts, schemas, reader weights, engine, old receipts,
scores and holdouts are unchanged. The wrapper returns diagnostic metadata only:
no observation/advice/advisor payload and eligible_for_live=false.

The tap excludes full provider envelopes, authentication/error headers,
reasoning/thoughts and images. It supports exactly one output_text of at most
65,536 UTF-8 bytes. Missing, multiple or oversized texts are recorded as
unsupported/no output and are not partly saved. Storage failure is explicit,
retains the text hash/length, and never causes a retry. A future controller must
stop on failed retention before making another paid diagnostic request.

Retention is bounded to 32 encrypted records and seven days of permitted
access. Expired ciphertext is removed on the next store open/write, or by an
explicit local expiry purge; no background deletion service is installed.
Record paths reject traversal, symbolic links, junctions and hard-linked files.
There is no plaintext or non-Windows fallback. Text containing recognizable
credential markers is refused. The trusted caller must declare reviewed owned
synthetic scope; a boolean cannot independently establish pixel ownership.
Same-account compromise or administrator takeover is outside this protection.

DPAPI binds protection to the user credential by default and provides a keyed
integrity check; LOCAL_MACHINE scope is deliberately absent.
[Microsoft CryptProtectData documentation](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

## Actual validation order

The original application path is:

| Stage | Existing operation | Failure remains |
| --- | --- | --- |
| JSON syntax, strict fields and pre-normalization invariants | LiveObservation.model_validate_json | Rejected; no normalization or R1 advice |
| Numeric label normalization | normalize_number inside semantic_gate | Contradictory label/value/role/view blocks R1 |
| R1 integrity | Existing shared live/grounded gate | Card arithmetic, phase, presence and controls can still block |
| Timeliness/current evidence | Original capture deadline and evidence checks | Timeout/stale output never becomes current |

Strict field validation and nested/root model invariants occur in the SAME
Pydantic operation; the diagnostic does not insert a weaker structural model.
An informational JSON syntax check and fixed error categories explain that
operation offline. Raw error input/context never reaches the public report.
Locations, fixed rule codes and hashes do; selected raw text and detailed
normalization stay encrypted.

At n[0], LiveNumber.observed_label_required requires PLAYER or DEALER AND TOTAL
words for an attributed hand total. That runs before numeric normalization:

| Fabricated output | Diagnostic finding |
| --- | --- |
| role=dealer_total, label=DEALER 6 | pre_normalization_invariant_rejection, explicit_total_label_required at n[0] |
| role=dealer_total, label=DEALER TOTAL 6, value=6 | Valid content, provided its view exists and cards agree |
| role=dealer_total, label=DEALER TOTAL 16, value=6 | semantic_provenance_rejection, label_value_mismatch |
| role=player_total, label=PLAYER TOTAL 17, cards=10+6 | r1_integrity_rejection, player_total_card_mismatch |
| role=unknown, unlabelled number=20 | Stays unknown; never becomes a hand total |

The 15 executed contract examples include valid whitespace, unknown UI, missing
TOTAL, ambiguous actor, wrong view, hidden face claims, duplicate controls,
strict type failure, extra fields and malformed JSON. They are fabricated
regressions, **not reconstructions of Gemini's missing output**.

Google recommends validating values even with schema-conforming JSON and
handling semantically incorrect output.
[Google structured output documentation](https://ai.google.dev/gemini-api/docs/structured-output)
OpenAI also notes that structured outputs can contain mistakes.
[Official OpenAI structured output documentation](https://developers.openai.com/api/docs/guides/structured-outputs)

## Executed evidence and practical limit

Public diagnostic categories:
[summary.json](../validation/results/rejected-output-diagnostics/summary.json).
Verification and unchanged-history checks:
[verification.json](../validation/results/rejected-output-diagnostics/verification.json).

Local Python verification passed 782 tests and 10 subtests in 89.71 s, with
two existing warnings. The focused diagnostic/numeric/deadline run passed
111 tests, including 42 new networkless diagnostic cases. These tests verify
contract and storage behavior; they do not measure fresh model accuracy.

An actual fabricated Gemini-envelope fixture traversed the unchanged reader,
failed the numeric invariant, was encrypted locally, and was recovered exactly.
Its unrelated provider envelope/header fields were excluded. Windows DACL
inspection confirmed two allowed principals, protected inheritance, and no
inherited grants. DPAPI round-trip and tampering rejection also ran on Windows.
A wrong-account failure is simulated; cross-account login was not performed.

Offline deadline fixtures cover expired capture, a valid body arriving at
4.5 seconds, stale evidence, usage audit failure, storage failure, exact payload
preservation, unchanged three-second transport deadline and one-shot no-retry
behavior. All diagnostic results remain ineligible for live advice, even if
their content is otherwise valid. The protected write happens after the reader
clock and is timed separately; this is not app capture/paint evidence.

The future wrapper does not itself collect beyond three seconds. **The longer
network experiment below is proposed, not implemented or run in this scope.**
There is no evidence of how late Luna's two PR19 responses would have arrived.

PR19's final Windows CI reran 52 frontend tests and the TypeScript/Vite build,
rather than only inheriting a local parent count.
[PR19 CI](https://github.com/youtrustshop-dot/blackjack-vision-lab/actions/runs/37533835121)
That remains unit/build evidence, not a physical capture/minimized-popup test.
No new UI changes or physical advisor checks occurred here.

## Minimum future diagnostic proposal — not authorized

Two requests maximum, sequential, one per provider, no retry or paid warm-up.
Use only the consumed owned fresh-rotated-unknown pixels/payloads already frozen
in PR19, once for Gemini and once for Luna. Repetition is deliberate failure
diagnosis, not independent generalization or validation accuracy. A new answer
may differ; it cannot recover the old discarded answer.

| Request | Question | Diagnostic wait cap | Historical worst-case reservation |
| --- | --- | ---: | ---: |
| Gemini structured-card-limit-local | Which exact newly returned text passes/fails which unchanged validator? | 10 s | USD0.3171328 |
| Luna Fast compact | Does a complete output arrive after 3 s but before 10 s, and is its content valid? | 10 s | USD0.5265360 |
| Total | Two distinct diagnostic observations only | 20 s sequential inference wait maximum | USD0.8436688 |

Numbers use the preserved PR19 config price snapshot, not new price/access
verification. There have been no model GETs, DNS/provider controls, billing
lookups, reservations or ledger writes in VISION-026. Existing accounted margin
is USD1.846720150, so the proposal fits numerically and would leave
USD1.003051350 worst-case margin, provided access/prices/accounting still match.
Those are reservations, not an invoice or balance.

Approval would have to expressly authorize these two diagnostic submissions and
an audited request-count change from 105 to 106 with 104 consumed attempts.
The old unused slot stays closed; the new bounded scope must not implicitly
reuse it. Every existing unknown-charge reservation and the lifetime USD8 cap
remain. No such change or new authorization epoch has been made.

Before execution, bind reviewed hashes and exact unchanged request bodies to
the new bounded scope; check current access/prices/margin and private retention.
Use a separate offline collector with no app/evidence/advisor/solver connection:
3 s is the unchanged live usability boundary; 10 s is only its diagnostic
collection ceiling. A late result, including one arriving at 3.01 s, is never
delivered as current advice. Retain incomplete/HTTP failures and unknown charges,
stop on failed storage/access/accounting, close the pool on deadline, disarm
after the two authorized attempts, and do not fall through to hybrid or tuning.
If no complete body arrives by 10 s, record latency as censored >10 s.
Two observations cannot certify p95, reliability or a champion.

## Offline reproduction

From the repository root:

~~~powershell
.venv/Scripts/python.exe -m validation.tools.rejected_output_offline
.venv/Scripts/python.exe -m validation.tools.rejected_output_offline --protected-roundtrip
.venv/Scripts/python.exe -m pytest -q tests/test_rejected_output_diagnostics.py tests/test_numeric_provenance.py tests/test_paired_semantic_path.py
.venv/Scripts/python.exe -m validation.tools.paired_semantic_audit
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
~~~

Protected round-trip requires Windows and creates one encrypted fabricated
record. No CLI prints decrypted output. Historical audit additionally needs
local ignored PR19 receipts. Explicit expired-record cleanup is local only:

~~~powershell
.venv/Scripts/python.exe -m validation.tools.rejected_output_offline --purge-expired
~~~

Runtime is disarmed. Installed 1.1.1, previous PRs, final holdout and their
scores remain unchanged. This delivery stops after the offline diagnostic fix
and the bounded proposal.
