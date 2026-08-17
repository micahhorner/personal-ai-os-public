---
id: capability-session-handoff
name: session-handoff
component_type: capability
status: active
version: 0.1.1
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-session-handoff
summary: Close a working session so any future session resumes cold with zero verbal context, and resume from such a record safely.
description: "Close a working session — journal current, work checkpointed, an honest resumable stopping point recorded — or resume from a prior session's record. Use when a substantive session ends ('wrap up', 'we're done for now', 'hand off') or picks prior multi-session work back up."
reads:
- vault
writes:
- per-procedure
permissions:
- uses-vault-operations-only
dependencies:
- doc-runtime-kernel
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
x_runtime_evaluations:
- System/Tests/fixtures/18-session-handoff
documentation: self
created: '2026-07-25'
updated: '2026-08-09'
---

# Capability — session-handoff

End a session so the next one — any runtime, any model, cold — resumes without a word of verbal context. Also the resume ritual when picking such work back up. The floors here are non-negotiable; the *form* of the record is the user's (see Personalization).

## When

A **substantive** session ends: it wrote medium+ changes, or it touched work that spans sittings (a project, a migration, a build). Trigger phrases: "wrap up", "we're done for now", "closing", "hand off". A session that only answered questions ends with the kernel's ordinary obligations — no record, no ceremony (paperwork nobody needs is its own kind of rot). During onboarding, this capability does not apply: onboarding owns its own resume state (`onboarding-progress.yaml`).

## Ending a session

1. **Journal sweep.** Any medium+ change not yet in `System/Journal/change-journal.md` gets its line now. Write-time journaling should make this a no-op; if it wasn't, note the gap itself.
2. **Checkpoint.** `aios checkpoint -m "<honest label>"` — a git commit or zip snapshot, same command either way. Uncommitted work is work that doesn't exist yet. Pushing or syncing beyond the checkpoint stays the human's call.
3. **Validate.** `aios validate` (plus `links` if references changed) — the kernel already requires this after write sessions; run it before the record so the record can state the result truthfully.
4. **Record the stopping point** where the next session will look first:
   - **Project-bound work** → a `## Resume` section in the project's primary note (update in place; history lives in checkpoints). A method may require its own artifact instead — e.g. a per-project `HANDOFF.md` — in which case that artifact *is* the record (see Personalization); never write both.
   - **Vault-wide work** (maintenance, migration, system change) → the change-record entry the journal already requires for high/critical work carries the stopping point; add one if the work stopped between journal-worthy events.
   - The record states: what was done **with evidence** (counts from scripts, checkpoint refs — never from recall), decisions made, open items in priority order (human-gated items marked), and the honest state — mid-wave, pending ratification, anything left broken. **A clean-looking record hiding a dirty state is worse than a dirty state.** The record is working material, never auto-promoted to canon.
5. **Report** in one line: what was journaled, the checkpoint ref, where the record lives.

## Resuming

1. **The record is canonical over recollection.** Read it before acting. Never begin from memory of a prior session when a record exists — the document wins.
2. **Verify before relying.** The record was true when written. Re-check any count, version, path, or status it asserts against the live vault — scripts, not recall — before building on it.
3. **Confirm the frame.** Restate the stopping point and the top open item to the human before writing anything. If the live state contradicts the record, say so first; the contradiction is the finding.

## Personalization (floor stays, form is the user's)

- An installed doctrine pack (Method Kit output) governs the record's form and depth — its skeleton, its artifact (e.g. `HANDOFF.md` per project, a recognized convention filename), its dials.
- `80 User/handoff.md`, when present, carries the user's own record rules or a one-line pointer to them (same pattern as `voice.md` / `authoring.md`, DEC-036). The router consults it; absent on a fresh seed, skipped silently.
- With neither, the generic form above applies. At every rung the floors hold: journal, checkpoint, validate, honest stopping point. Personalization changes depth and shape, never whether.
