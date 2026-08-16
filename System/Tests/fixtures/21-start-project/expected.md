---
id: doc-fixture-21-start-project
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-21-start-project
created: 2026-07-25
updated: 2026-07-25
summary: "Behavioral fixture: 'start a project for Y' routes to start-project and produces the folder, a schema-valid registered project note, and a pointer to where actions go — the generic floor only, with a method pack consulted by mention when installed."
---

# Fixture 21-start-project

**Scenario**: The user starts a project by saying so. The runtime must route to `start-project`, produce the generic floor (folder + schema-valid project note + registration), refuse to duplicate an existing project, and defer everything above the floor to an installed method pack — by consult-line mention, never by silent scaffolding.

**Setup / input**: A scratch copy with no method pack installed (probe 3 adds a stub pack), plus `input/run.md` probes.

**Pass criteria** (all must hold):
- [ ] "Start a project for Y" creates `10 Projects/<Name>/<Name>.md` from the template: `type: project`, a minted `project-` id, `stage` from the `project_stage` vocabulary, required fields filled, `aios validate` green
- [ ] The project is registered: `aios generate` runs and the note appears in the generated index
- [ ] The runtime states where next actions go (the note's `## Next actions`, plus the root `To-Do.md` via `manage-todo` for anything that must surface outside the project)
- [ ] **No PLAN/HANDOFF/gate artifacts are created and no method is offered** when no pack is installed — the generic floor never rebuilds anyone's method
- [ ] Repeating the request resolves to the existing project (resume proposed) — no second folder, no duplicate note
- [ ] With a method pack installed, the runtime mentions the pack's project-start doctrine as governing what sits above the floor — a consult, not an unrequested execution of the pack's scaffolding

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
