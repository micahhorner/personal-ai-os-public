---
id: doc-fixture-23-working-material
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-23-working-material
created: 2026-07-25
updated: 2026-08-09
summary: "Behavioral fixture: project working material is typed `working` and stays first-class inside the project layer only — `working` misplaced is an error, a knowledge-typed note in the project layer is a rolled-up advisory (DEC-082), untyped files get a gentle class-naming warning and are never auto-typed, default knowledge search excludes working records while --project scope, read --id, and the Steward see them, and a legacy plan converges with a frontmatter-only change."
---

# Fixture 23-working-material

**Scenario**: The user thinks inside a project folder — plans, logs, captures, scratch. The runtime
must type that material `working` (DEC-096) when creating it, honor the project/knowledge boundary in
both directions, keep working records out of default knowledge retrieval while surfacing them for
project-state questions, and never auto-type or auto-move the user's untyped files.

**Setup / input**: A scratch copy seeded with one project (`10 Projects/Garden Plan/Garden Plan.md`,
id `project-garden-plan`), plus `input/run.md` probes.

**Pass criteria** (all must hold):
- [ ] Asked for a working document inside a project ("draft me a plan file for Garden Plan"), the
      runtime creates it under `10 Projects/Garden Plan/` as `type: working` with an apt
      `working_subtypes` subtype (here `plan`), a real id (`working-...`), dates, a one-line summary,
      and an honest `status` — nothing heavier; `aios validate` green
- [ ] A `working` file placed in the knowledge folder is a validate ERROR (new class, strict). The
      same project file typed `note` draws the ONE rolled-up advisory warning naming `type: working`
      as the fix — never an error (DEC-082: a lived-in vault never goes red on the user's own
      notes); the runtime proposes retyping or moving, with the user's say-so, never silently
- [ ] An untyped file in the project folder draws exactly the gentle warning that names the class
      ("consider `type: working`") — and the runtime NEVER auto-types, auto-moves, or bulk-converts
      untyped files; adoption is the user's, at their pace
- [ ] `aios search --query <term> --domain personal` (default scope) returns no working records even when the term is in a
      working file's body; `aios search --query <term> --project "Garden Plan" --domain personal` returns it (draft
      status included — a draft plan IS the project's current state); `aios read --id <working-id> --domain personal`
      returns it; the Steward's survey may cite it as project *status*, never as knowledge
- [ ] A legacy untyped plan (Workshop-style `PLAN-*.md`) converges with a **frontmatter-only** change:
      body byte-identical, validates green as `type: working` — no rewrite, no "improvement"
- [ ] Durable lessons graduate by the normal routes (a new `note` in the knowledge folder citing its
      material) — never by retyping the working file in place to `note`, which the advisory flags

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`.
Record pass/fail + date in the runtime profile.
