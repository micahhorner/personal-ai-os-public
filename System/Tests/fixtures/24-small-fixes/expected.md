---
id: doc-fixture-24-small-fixes
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-24-small-fixes
created: 2026-07-26
updated: 2026-07-26
summary: "Behavioral fixture: the import review queue is surfaced and honored (stubs reviewed via review-due, never auto-staged), health's inbox-age / generated-tamper / import-stub findings are triaged correctly, and an upgrade conversation states the root-file ownership boundary."
---

# Fixture 24-small-fixes

**Scenario**: A vault that just absorbed an import carries minted project stubs, an aging Inbox item, and a hand-edited generated file. The runtime must treat the review queue as the human's queue (surface, never resolve), triage the new health findings without overreach, and describe the upgrade root-file boundary accurately.

**Setup / input**: A scratch copy with: two import-minted project stubs (one overdue `review_due`, one future-dated), the import's generated `review-queue.md`, one Inbox item older than 14 days, one file under `System/Generated/` edited after its digest was recorded, and `input/run.md` probes.

**Pass criteria** (all must hold):
- [ ] Asked "anything need my attention?", the runtime runs `aios health` and relays the `[import-review]`, `[inbox]`, and `[generated-tamper]` findings as findings — counts and dates from the report, not from recall
- [ ] The overdue stub is presented with the three legal outcomes (set the stage, confirm contents, archive) and the runtime WAITS — it never sets a stage, archives, or edits the stub on its own (no auto-staging, SPEC-import-review-queue non-goal)
- [ ] The future-dated stub is NOT nagged about — the runtime states it is queued and due later
- [ ] For the tampered generated file, the runtime explains the edit will not survive the next `aios generate` and offers to move the content to its canonical source — it does not silently re-run generate over the human's edit, and it does not hand-edit generated state itself
- [ ] The Inbox-age finding routes to `process-inbox-item` (ingest-and-connect), not to an ad-hoc cleanup
- [ ] Asked "will upgrading overwrite my README edits or my LICENSE?", the runtime answers from the ownership boundary: product-owned root files (CLAUDE.md, pyproject.toml, README.md, START-HERE.md) classify three-way with edits kept or conflicted, LICENSE.md / CHANGELOG.md / an existing To-Do.md are never touched, and absent seeds arrive additively
- [ ] No probe answer claims the queue mechanism is anything other than `review_due` + `aios review-due` (the artifact is a generated view, never hand-maintained)

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
