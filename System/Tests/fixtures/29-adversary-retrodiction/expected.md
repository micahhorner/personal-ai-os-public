---
id: doc-fixture-29-adversary-retrodiction
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-29-adversary-retrodiction
created: 2026-07-26
updated: 2026-07-26
summary: "Behavioral fixture (eval): the adversary pass reads a real plan that shipped with a known post-hoc correction — aios measure, filed as three jobs and cut to one — with the correction withheld. If the pass finds flaws only when they are planted, this fixture is what says so."
---

# Fixture 29-adversary-retrodiction

**Scenario**: A plan is handed to the adversary pass cold, with no hint that anything is wrong with it. The plan is a restatement of a real roadmap item from this product's own history — `aios measure`, filed as one command doing three jobs — which was cut to a single job before any code was written, once a human re-read it and asked which of the three had ever actually been needed. The pass must reach that correction from the text alone.

This is the harder half of the anti-theater bar. Fixture 29 proves the pass finds flaws someone planted for it; only this one proves it finds a flaw nobody did.

**Setup / input**: `input/run.md` + `input/spec-aios-measure-original.md`. `expected.md` is not shown to the runtime before the pass.

**Pass criteria** (all must hold):

*The known correction is reached — DoD-2*
- [ ] The report identifies that the three jobs are **bundled by a word, not by a shared job**: they take different inputs, serve different consumers, and share only the name "measure". Naming any two of {different input, different consumer, no shared machinery} is sufficient; a vague "this feels broad" is not
- [ ] The report notices that **only job 1 carries evidence of demand** — the eleven-of-eighteen coinage incident is cited in the filing itself and belongs to the transcript job alone; jobs 2 and 3 have no triggering incident anywhere in the text
- [ ] The report's recommendation lands on the correction that actually shipped: **build the transcript job; demote the other two** (or the equivalent — split them, defer them, drop them). A recommendation to build all three as filed is a FAIL
- [ ] The reasoning is reconstructed, not asserted: the finding cites the lines that carry it (the "why one command" paragraph and the incident that names only job 1)

*The pass is a pass, not a lucky sentence*
- [ ] All five fixed sections are present, with the steelman first and the mandatory closing line last
- [ ] The scope finding states its **falsifier** — e.g. "show a single caller that needs two of these three jobs in the same run, and this finding is wrong"
- [ ] **At least one thing the plan gets right is named** — the read-only shape, or the compute-don't-eyeball principle that job 1 genuinely proves
- [ ] The verdict is **proceed-with-amendments** (build one job) or **redesign** (the item is three items); `proceed` fails

**Fail conditions** (any one fails the fixture, and each is worth recording as such):
- The report treats all three jobs as equally warranted.
- The report praises the bundling as good CLI economy — the filing's own argument, accepted uncritically.
- The report objects only to surface details (naming, flags, output format) while the scope defect goes unnamed.
- The correction is produced only after the scorer hints at it.

**On failure, record it plainly.** A failed retrodiction does not mean the plan under test was fine; it means the pass finds flaws only when they are planted, which is precisely the finding this fixture exists to surface. Record it, and treat the capability's verdicts as unproven until it passes.

**Certification**: part of the battery in `System/Tests/Certification Battery.md` (L3 guided construction). Record pass/fail + date in the runtime profile. Together with `28-adversary-seeded-flaw` this is the permanent falsifiable bar for `adversary`; neither may be dropped while the capability is active.
