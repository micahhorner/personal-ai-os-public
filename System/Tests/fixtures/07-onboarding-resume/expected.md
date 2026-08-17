---
id: doc-fixture-07-onboarding-resume
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-07-onboarding-resume
created: 2026-07-10
updated: 2026-07-10
summary: "Behavioral fixture: Onboarding interrupted mid-stage must resume losslessly."
---

# Fixture 07-onboarding-resume

**Scenario**: Onboarding interrupted mid-stage must resume losslessly.

**Setup / input**: Input: onboarding-progress.yaml with stages 1-3 complete, stage 4 in-progress (split state model, DEC-014; answers live separately in onboarding-answers.yaml).

**Pass criteria** (all must hold):
- [ ] Runtime reads the progress file, confirms position in one sentence
- [ ] Resumes at stage 4 without re-asking completed stages
- [ ] Stage validations still enforced
- [ ] Progress file updated after each step; answers written only to the answers file

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
