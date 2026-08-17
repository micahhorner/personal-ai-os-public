---
id: capability-method-kit
name: method-kit
component_type: capability
status: active
version: 0.1.1
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-method-kit
summary: Interview the user about how they run their work and generate their own operating method — a personal rulebook plus skills any AI follows.
description: "Interview the user about how they run their work and generate their own operating method — a personal rulebook plus procedures any AI follows. Use when the user wants their working method captured, updated, or exported."
reads:
- vault
- System/Method-Kit
writes:
- per-procedure
permissions:
- uses-vault-operations-only
dependencies:
- doc-runtime-kernel
- doc-method-kit-bundle
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
x_runtime_evaluations:
- System/Tests/fixtures/method-kit-generation
documentation: self
created: '2026-07-13'
updated: 2026-08-09
---

# Capability — method-kit

Build the user their own operating method: interview them about how they actually run their work, generate a personal doctrine pack (their rulebook), and install skills that make any AI follow it. Runs the vendored instrument in `System/Method-Kit/` — point at it, never restate it.

## When

The optional Method Kit module at the end of onboarding (Stage 8, deferrable and re-surfaced like any skipped stage), or on request ("build my method", "set up how I work").

## Procedure

1. **Interview** — administer `System/Method-Kit/INTERVIEW.md` (8 sections, ~45 min) one question at a time per its admin rules; log into the `ANSWER-RECORD.md` format as you go. Every question is skippable; grade evidence E1–E4 (observed behavior beats self-report).
2. **Resolve the dials** — set the 11 dials in `System/Method-Kit/DIALS.md` from the readback-confirmed answers. Missing or contradictory signal → the dial's conservative default, leaned by the stakes note; no setting may weaken the Core floors.
3. **Generate** — per `System/Method-Kit/GENERATOR.md`, produce the user's pack in their **user layer** (a named `<their>-Method/` home under `80 User/`), plus the pack-skills from `System/Method-Kit/Adapters/pack-skills/` pointed at that pack. The pack is the user's; core is never personalized.
4. **Ratify** — read the pack back; the user confirms or amends before it is active. Their doctrine, their sign-off.
5. **Record** — write the outcome to `onboarding-progress.yaml` when run from onboarding, or a journal line when standalone. The pack + wired skills are the deliverable.

## Boundaries

- The generated pack lives in the user layer and belongs to the user; the generic instrument in `System/Method-Kit/` is never personalized (grep-gated, no personal data enters it).
- Consult `80 User/workstyle.md` if present — the pack extends the user's existing preferences, never contradicts them silently.
- This capability produces a rulebook the user owns and can edit or delete at any time; it is purely additive to the system.
