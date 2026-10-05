# Card Lab project instructions

- Read `docs/MASTER_PLAN.md` for the one active priority order (accepted v1.1,
  with the latest user-authorized specialized local challenger addendum).
  Earlier training deferrals are history; the user now explicitly authorizes
  one serious local card model alongside the existing reader tournament.
- Current milestone: M1, frozen local baseline and specialized YOLO26/keypoint
  plus learned rank/suit challenger versus available Gemini Flash/Lite,
  GPT-6 Luna Standard/Fast, and GPT-6.1 Sol only on residual hard cases. Preserve
  Poker Phase 0; prepare the existing native advisor's compact view independently.
- R1 image observation, R2 session reconstruction and R3 poker strategy are separate
  capabilities. Rank-only blackjack may tolerate an unknown suit; poker may not.
- API readers return observations only. Existing math owns advice. No oracle phase,
  card annotations or hidden simulator state may enter the reader.
- Current user authorization (2026-10-05): reuse the existing OpenAI key; up to
  EUR10 equivalent TOTAL R&D API spend across providers/configurations, reviewed
  native owned synthetic and historical provider-development crops. The user
  explicitly requested OpenAI first and has no Gemini credential. It supersedes
  the historical zero budget, but does not provision credentials or authorize
  purchases/recharge/payment changes. Credential reuse is resolved; establish available account
  access and a persistent worst-case ledger before enabling inference; the legacy
  runtime gate remains disarmed until these are satisfied. Unknown balance is not
  zero. Keep failures/timeouts reserved when their charges cannot be established.
- Future inference/upload requires reviewed native crops, account access and an
  explicit request/spend limit bound to the current spending authorization epoch.
  Secrets remain in the backend environment, never chat,
  source, committed approval files or logs. See `docs/R1_READER_COMPARISON.md`.
- Use `validation/tools/api_reader_tournament.py` and the canonical ignored
  `artifacts/api-budget/eur10-total-20261004.json` ledger for this authorization.
  All real Responses requests now require a durable one-attempt reservation;
  the historical memory-budget runner cannot spend this allowance. Do not reset
  the ledger or create another key. Existing key is in ignored .env.local, loaded
  only into the backend subprocess. Preserve the initial HTTP429 receipt. After
  the user reported a EUR10 top-up and explicitly requested another attempt,
  VISION-016 completed 69 new submissions (51 Standard / 15 Fast / 3 Sol), 70
  lifetime attempts under the unchanged cap. Luna Fast returned all 15 within
  2.5s, with 39/39 annotated rank/suit tuples, but 0/12 usable synthetic player
  states. The renderer's unlabelled decorative 20 is interpreted as a dealer
  total; visibility-proxy disagreements also remain. No reader promotion.
  USD0.035521 is the conservative upper charge for reported usage only;
  USD7.386864 of unknown-charge reservations is retained. Neither is an invoice
  or verified balance. Runtime is disarmed. No more submissions, automatic
  retries, billing changes or local training/tuning in this increment.
  See `docs/OPENAI_READER_TOURNAMENT.md`.
- Extend `docs/VISION_EXPERIMENTS.json`; keep failed checkpoints and consumed
  regressions. Do not call contract mocks or repeated screenshots independent evidence.
- Keep private evidence/approvals under ignored `artifacts/`. Publish aggregates only.
- Do not replace the frozen desktop 1.1.1, merge the candidate chain or expand poker
  strategy while this comparison remains undecided. No new framework or installer.
- Training stays in a separate research environment. Freeze session/seed/artwork
  partitions before running; never train or tune on the sealed final holdout.
  Keep official checkpoint provenance, restricted deserialization, failed runs,
  actual learning curves and end-to-end results. No generic-weight claim of
  52-card recognition. Do not distribute research weights/dependencies silently.
- Validate relevant source changes with `.venv/Scripts/python.exe -m pytest -q` and
  `.venv/Scripts/python.exe scripts/check-evidence.py`. UI checks apply if UI changes.
- Explain progress and limits to the user in Italian; public implementation docs are English.
