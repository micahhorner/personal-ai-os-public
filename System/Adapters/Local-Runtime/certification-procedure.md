---
id: adapter-local-runtime-certification
x_reviewed_against: ["adapter-local-runtime-spec:1.0.0"]
type: adapter
file_class: canonical
authority: derived
derived_from: [adapter-local-runtime-spec]
created: 2026-07-10
updated: 2026-07-16
summary: Step-by-step procedure for certifying any new runtime against the fixture battery.
---

# Runtime Certification Procedure

1. Copy `System/Runtime Profiles/_template.yaml` → `<runtime-id>.yaml`; fill identity + hosted/local.
2. Grant L0. Run the read fixtures (retrieval, privacy exclusion, abstention). Pass → L0 certified.
3. Run propose fixtures (drafts land in Inbox, correctly formed). Pass → L1.
4. Run write fixtures (low-risk auto change; high-risk correctly blocked; duplicate correctly refused; validation run after writes). Pass → L2.
5. Run guided-construction fixtures (onboarding resume; extension request end-to-end with human gates honored). Pass → L3.
6. L4 (migrations/structural) requires all of the above plus a supervised real migration on a copy of the vault.
7. Record each result with date in the profile. Any regression re-runs from the failed level. The manifest's `active_profile` switches only on human decision.
