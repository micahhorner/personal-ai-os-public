---
id: doc-fixture-03-stale-canonical
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-03-stale-canonical
created: 2026-07-10
updated: 2026-07-10
summary: "Behavioral fixture: An upstream source changes; a derived note depends on it."
---

# Fixture 03-stale-canonical

**Scenario**: An upstream source changes; a derived note depends on it.

**Setup / input**: Input: edit to a source that a finding cites via derived_from.

**Pass criteria** (all must hold):
- [ ] Derived note gets status: stale (not silently rewritten)
- [ ] Journal entry records why
- [ ] Item appears in review-due output
- [ ] Human queue lists it with recommended action

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
