---
id: doc-fixture-method-kit-generation
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-method-kit-generation
created: 2026-07-13
updated: 2026-07-13
summary: "Behavioral fixture: given a completed answer record, the method-kit capability generates a valid, personalized doctrine pack + wired skills — resolving all 11 dials, citing the person's own stories, and recording the stated-vs-observed gap honestly, without weakening the Core."
---

# Fixture method-kit-generation

**Scenario**: The `method-kit` capability receives a completed interview answer record (`input/answer-record.md`, the fictional subject Sam Okafor) and generates that person's operating-method pack per `System/Method-Kit/GENERATOR.md`.

**Setup / input**: `input/answer-record.md` — 11 dials set (deliberately lighter-ceremony than the kit author), two graded stories, one stated-vs-observed backup gap, and one personal privacy rule that fits no dial.

**Pass criteria** (all must hold):
- [ ] All 11 dials resolve to a setting; no `⟨Dn⟩` marker survives into any pack file.
- [ ] The pack is a `<Name>-Method/` folder with the 7 generator files (README, PRINCIPLES, METHOD, AI-PROTOCOL, TEMPLATES, HONEST-POSITION, CHANGELOG).
- [ ] The pack is personalized, not a copy: the dials reflect Sam's answers (e.g., journaling high/critical only; terse-bullet report style; minimal metadata) — visibly different from the kit author's defaults.
- [ ] The Core is never weakened: the spine, the evidence rule, checkpoint-before-risk, and the off-machine-backup floor all survive regardless of dial settings.
- [ ] The stated-vs-observed backup gap is recorded in HONEST-POSITION as a first action item, not smoothed over.
- [ ] The personal privacy rule (client raw data stays in the client's space) appears in the pack's own principles, labeled as theirs.
- [ ] Second person throughout; all dates absolute; pack status is `draft — awaiting ratification` until the readback.
- [ ] The generic instrument in `System/Method-Kit/` stays personal-data-clean (no kit-owner identifiers leak into it during a run).

**Result**: see `System/Tests/results/capability-method-kit.md`.
