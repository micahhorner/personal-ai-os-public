---
id: doc-fixture-22-decisions-space
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-22-decisions-space
created: 2026-07-25
updated: 2026-07-25
summary: "Behavioral fixture: 'let's go with option B' routes to record-decision and produces a schema-valid dated record in Decisions/, surfaced by the generated register; a bare preference is not recorded; supersession marks, never deletes; no number is ever claimed."
---

# Fixture 22-decisions-space

**Scenario**: The user settles choices in conversation. The runtime must route to `record-decision` when — and only when — a choice closes alternatives or changes scope, produce a schema-valid record in the top-level `Decisions/` home with a dated slug id, keep numbering derived (the generated register orders; records never claim numbers), scope project decisions via `project:`, and supersede honestly.

**Setup / input**: A scratch copy seeded with one project note, plus `input/run.md` probes.

**Pass criteria** (all must hold):
- [ ] A settled choice ("let's go with option B…") produces one record in `Decisions/`: `type: decision`, dated slug id (`decision-YYYY-MM-DD-<slug>`), Decision/Why/Alternatives drafted from the conversation, `decision_makers` = the humans (never the AI), **no clarifying question** when everything was inferable, `aios generate` + `aios validate` run
- [ ] **No number is claimed anywhere** — no `DEC-`, no `D-NNN`, no counter in id, filename, or body; the record appears in the generated register (`System/Generated/index-decision.md`, newest first), and citation is by id
- [ ] A bare preference ("I think I prefer the dark theme") produces **no** decision record — the trigger bar (closes alternatives or changes scope) holds; over-capture fails this fixture like under-capture would
- [ ] A context-thin decision triggers **exactly one** clarifying question — never a section-by-section interrogation; a declined answer still yields the record with the gap visibly marked
- [ ] A project-scoped decision carries `project: <project-id>` and appears under that project's heading in the register's **By project** section after `aios generate`
- [ ] Superseding creates a new record with `supersedes:`; the old record is marked `status: superseded` + `superseded_by:` with its content untouched — never deleted, never edited — with one journal line
- [ ] `System/Governance/Active Decisions.md` (the product's register) is never written by any probe

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
