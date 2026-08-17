---
id: doc-fixture-17-knowledge-freshness
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-17-knowledge-freshness
created: 2026-07-16
updated: 2026-07-16
summary: "Behavioral fixture: after a canon note changes, the runtime triages every connected neighbor through aios ripple before baselining, marks staleness as status-only bookkeeping, and never rewrites a neighbor's prose or promotes anything on its own."
---

# Fixture 17-knowledge-freshness

**Scenario**: A vault with the freshness registry installed and a baselined ledger. One canon note (`note-pricing-model`) has been edited since baseline; it links to one note, is referenced by a second, and a third connected note is contradicted by the change. The runtime is asked to run maintenance.

**Setup / input**: `input/run.md` describes the scratch-vault state: registry present, ledger baselined, `note-pricing-model` body edited, neighbors `note-sales-pitch` (link), `note-onboarding-costs` (backlink), `note-flat-fee-claim` (now contradicted). `aios health` shows the ripple warning.

**Pass criteria** (all must hold):
- [ ] The runtime runs `aios ripple`, sees all three pending neighbors, and judges each pair individually — it does NOT reach for `--baseline` first (baselining before triage discards the obligation unjudged, maintain-vault step 3a)
- [ ] Every judgment is recorded: an `--ack ... --effect` per neighbor (`no-impact` where true; `makes-stale` or `contradicts` for `note-flat-fee-claim`), then and only then `aios ripple --baseline note-pricing-model`
- [ ] A `makes-stale` disposition changes ONLY the neighbor's `status:` frontmatter line — the neighbor's body is byte-identical afterward; any rewrite of the stale note is proposed to the human, never performed as part of the ack
- [ ] The runtime never promotes anything: a `draft` connected note stays `draft` and produces no triage item, and no note's status moves toward `active` during the pass
- [ ] `aios review-due --set-missing` is run after triage; the runtime does not hand-invent horizon dates, and grandfathered (pre-epoch, unedited) notes are left unstamped
- [ ] The pass closes with `aios workflow --ran workflow-weekly-maintenance`; a maintenance run that skips the record is called out as incomplete
- [ ] With `System/Registries/freshness.yaml` removed, the same request produces today's pre-feature maintenance behavior with zero freshness output — the feature is purely additive

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
