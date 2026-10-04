# Card Lab project instructions

- Read `docs/MASTER_PLAN.md` for the one active priority order (accepted v1.1).
  `ROADMAP.md` and earlier reports retain history; they do not reactivate immediate YOLO training.
- Current milestone: M1, calibrated local reader versus at most two available
  OpenAI image-reader configurations. Preserve Poker Phase 0 and the external advisor.
- R1 image observation, R2 session reconstruction and R3 poker strategy are separate
  capabilities. Rank-only blackjack may tolerate an unknown suit; poker may not.
- API readers return observations only. Existing math owns advice. No oracle phase,
  card annotations or hidden simulator state may enter the reader.
- Current API budget is zero. No inference, including credit-funded inference,
  without fresh explicit user approval. A saved key or old approval is not consent.
  Billing verification is read-only; do not buy credits, add payment methods or
  change auto-recharge. Unknown balance is not zero: use blocked_credit_verification;
  blocked_no_free_credits requires verified absence. Continue independent local work.
- Future inference/upload requires reviewed native crops, account access and an
  explicit request/spend limit bound to the current spending authorization epoch.
  Secrets remain in the backend environment, never chat,
  source, committed approval files or logs. See `docs/R1_READER_COMPARISON.md`.
- Extend `docs/VISION_EXPERIMENTS.json`; keep failed checkpoints and consumed
  regressions. Do not call contract mocks or repeated screenshots independent evidence.
- Keep private evidence/approvals under ignored `artifacts/`. Publish aggregates only.
- Do not replace the frozen desktop 1.1.1, merge the candidate chain or expand poker
  strategy while this comparison remains undecided. No new framework or installer.
- Validate relevant source changes with `.venv/Scripts/python.exe -m pytest -q` and
  `.venv/Scripts/python.exe scripts/check-evidence.py`. UI checks apply if UI changes.
- Explain progress and limits to the user in Italian; public implementation docs are English.
