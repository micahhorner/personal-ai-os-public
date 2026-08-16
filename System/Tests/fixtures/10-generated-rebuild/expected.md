---
id: doc-fixture-10-generated-rebuild
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-10-generated-rebuild
created: 2026-07-10
updated: 2026-07-10
summary: "Behavioral fixture: Generated state is deleted entirely."
---

# Fixture 10-generated-rebuild

**Scenario**: Generated state is deleted entirely.

**Setup / input**: Input: rm -r System/Generated/ then aios generate.

**Pass criteria** (all must hold):
- [ ] All indexes, reverse views, ops-registry, implementation-status rebuilt
- [ ] Second run produces identical file list (idempotent)
- [ ] aios validate green afterward
- [ ] Zero meaning lost

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
