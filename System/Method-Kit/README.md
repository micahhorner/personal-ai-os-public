---
id: doc-method-kit-bundle
type: system-doc
file_class: canonical
authority: canonical
canonical_for: method-kit-vendored-instrument
status: active
version: 0.2.0
source_version: method-kit@0.2.0
created: 2026-07-13
updated: 2026-07-13
summary: "The Method Kit instrument vendored into AI OS — the generic interview + dials + generator that builds a user their own operating method. Copied verbatim from the Method-Kit master; re-sync by version; never edit personal data in (generic-master invariant)."
---

# Method Kit — vendored instrument

This folder is the generic Method Kit instrument, vendored into the product so AI OS stays self-contained (DEC-001: no cross-folder runtime reach). The `method-kit` capability runs it, and the optional Method Kit onboarding module invokes that capability.

**What it builds:** it interviews a user about how they run their work, sets 11 personalization dials, and generates *their own* operating method — a plain-text rulebook (plan template, gates, decision register, handoff, journal) plus working skills wired to follow it.

**The files:**
- `CORE.md` — the universal skeleton every disciplined operator shares (lifecycle, gates, tiers, records, backups).
- `DIALS.md` — the 11 personalization dials that make a pack personal.
- `INTERVIEW.md` — the 8-section instrument an AI administers (~45 min).
- `GENERATOR.md` — how a completed interview becomes the user's doctrine pack + installed skills.
- `ANSWER-RECORD.md` — the required format the interview logs into and the generator consumes.
- `Adapters/` — the `pack-skills` the generated pack installs (`pk-new-project`, `pk-plan`, `pk-handoff`) and the `method-interview` skill.

**Provenance and sync:** the maintainer-owned upstream Method Kit, currently v0.2.0, is the source for this shipping reference copy. Re-sync copies the upstream files, then applies one deterministic re-stamp so they validate as product reference docs rather than being mistaken for components: frontmatter `id` `mk-*` → `doc-method-kit-*`, `type` → `system-doc`, and any internal `derived_from` references to those ids (the bodies are untouched). The sync re-applies that transform each time. This is generic-master class — the personal-data grep gate runs on every sync and must stay clean (it scans for owner identifiers; those never belong in this bundle).
