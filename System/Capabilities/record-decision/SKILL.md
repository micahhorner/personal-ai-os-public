---
id: capability-record-decision
name: record-decision
component_type: capability
status: active
version: 0.1.1
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-record-decision
summary: "Capture the moment a choice settles: a schema-valid decision record (what, why, alternatives, evidence, tacit context) in the top-level Decisions/ folder, with a dated slug id — never a claimed number — surfaced by the generated register."
description: "Record a settled decision as a durable dated record in Decisions/. Use when the user settles a choice that closes alternatives or changes scope — 'let's go with option B', 'approved', 'we're not doing X', 'record a decision'. Not every preference is a decision; one clarifying question max; ids are dated slugs and numbering is derived by the generated register, never claimed."
reads:
- vault
writes:
- per-procedure
permissions:
- uses-vault-operations-only
dependencies:
- doc-runtime-kernel
- capability-safe-write
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
- System/Tests/scripts/test_decisions.py
x_runtime_evaluations:
- System/Tests/fixtures/22-decisions-space
documentation: self
created: '2026-07-25'
updated: '2026-08-09'
---

# Capability — record-decision

A decision that lives only in the conversation is a decision the next session
re-litigates. This capability captures the moment a choice settles — as one dated,
schema-valid record in the top-level `Decisions/` folder (registry id `decisions`),
where it outranks old discussion when the vault answers "what did we decide, and
why?". The folder is at eye level on purpose: a space nested inside another folder
is a space you have to be told about, and a space nothing routes to becomes the
next forgotten convention. This route is what keeps it alive.

## When — the bar

**A decision is a choice that closes alternatives or changes scope.** Trigger
language: "let's go with option B", "approved", "we're going with X", "we're NOT
doing Y", "skip that", "record a decision", a waiver, an override, a scope change.

**Not every preference is a decision.** A passing taste ("I prefer dark mode"), a
mood, or a thought still in motion is not one — nothing closed, nothing changed
scope. When it isn't a decision, don't record one; the normal note lanes exist.
When genuinely unsure whether the choice settled, asking "is that decided?" is the
one question (below), not a reason to write a record on spec.

## Procedure

1. **Resolve first** (safe-write law): `aios resolve --query "<topic>"`. An
   existing decision on the same question means this is a **supersession** (step
   5), a duplicate record never. A related project found here fills `project:`.
2. **Draft the whole record from the conversation**: the Decision in one sentence;
   the Why; the Alternatives it closed (what was NOT chosen, and why not); the
   Evidence available at the time; the Tacit context (what a reader years later
   won't know); `decision_makers:` — the humans who decided, **never the AI**;
   `decided_at:` today unless the user says otherwise; `review_condition:` if one
   was stated or is plainly implied; `project:` and `related:` linking the
   affected project and notes.
3. **Ask at most ONE clarifying question**, only for what you genuinely cannot
   infer — usually the why or the alternatives. Never walk the record section by
   section; friction kills the capture habit. A declined answer still produces the
   record, with the gap marked `(unstated — flag at review)`: a flagged record
   beats a lost decision.
4. **Mint the id and write**: `decision-YYYY-MM-DD-<slug>` (the profile's dated
   slug form), from `System/Templates/decision.md`, into `Decisions/`, per
   safe-write. **Never assign a number** — no `DEC-`, no `D-001`, no counter of
   any kind. The id is the only stable handle; positions in the register are
   derived on every rebuild, which is exactly why parallel sessions cannot
   collide. Records are born `status: active` — recording is what the user just
   asked for; the settled choice *is* the approval.
5. **Superseding**: the new record carries `supersedes: <old-id>`; the old record
   gets `status: superseded` + `superseded_by: <new-id>` (consequential lane —
   one journal line). Never delete, never edit the old decision's content: the
   history stays honest.
6. **Register and validate**: `aios generate` (the register view
   `System/Generated/index-decision.md` rebuilds — newest first, grouped by
   project) then `aios validate`.
7. **Report in one line**: id, home, project scope if any, what it superseded if
   anything.

## The register is derived — never cite a position

`System/Generated/index-decision.md` is the human-readable register: generated
from frontmatter, newest first, grouped by `project:`, rebuilt on every
`aios generate`, never hand-edited. Cite decisions **by id**. A position in the
register ("the third decision") is a display artifact that can shift on rebuild;
treating it as a name is how registers collide.

## Fences

- **`System/Governance/Active Decisions.md` is the product's register, not the
  user's** — it records how this system itself is built and is overwritten by
  product updates. Never write a user decision there; cross-reference at most.
- One consolidated space. Project decisions live here too, scoped by `project:` —
  per-project decision files would recreate the scatter this space ends.
- No approval workflows and no decision-*making* machinery — this capability
  records choices after they settle; it does not weigh them.
- Pre-existing decision records elsewhere (e.g. `20 Knowledge/`) are tolerated by
  the schema and are not migrated unprompted — moving them is the user's call.
