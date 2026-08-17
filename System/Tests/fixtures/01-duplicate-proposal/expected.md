---
id: doc-fixture-01-duplicate-proposal
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-01-duplicate-proposal
created: 2026-07-10
updated: 2026-07-10
summary: "Behavioral fixture: A user asks to create a note that already exists under a different title."
---

# Fixture 01-duplicate-proposal

**Scenario**: A user asks to create a note that already exists under a different title.

**Setup / input**: Input: request 'create a note about weekly review habits'. The vault contains note-lesson-capture-before-organizing and procedure-weekly-review.

**Pass criteria** (all must hold):
- [ ] Runtime runs safe-write resolve-first before creating
- [ ] Detects procedure-weekly-review as covering the topic
- [ ] Proposes updating/extending it instead of creating a duplicate
- [ ] No new note is created without the user insisting

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
