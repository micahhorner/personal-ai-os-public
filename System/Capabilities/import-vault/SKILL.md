---
id: capability-import-vault
name: import-vault
component_type: capability
status: active
version: 0.3.1
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-import-vault
summary: Bring a user's existing vault in safely — plan authored with the owner, executed by the script, provable afterward.
description: "Bring a user's existing vault or note collection into AI OS safely — plan authored with the owner, executed by the import script, provable afterward. Use when migrating external content into the vault at scale."
reads:
- vault
- external-source-vault-readonly
writes:
- per-procedure
permissions:
- uses-vault-operations-only
dependencies:
- doc-runtime-kernel
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
- System/Tests/scripts/test_import.py
x_runtime_evaluations:
- System/Tests/fixtures/13-vault-import
- System/Tests/fixtures/24-small-fixes
- System/Tests/fixtures/27-intake-dedupe
documentation: self
created: '2026-07-11'
updated: '2026-08-09'
---

# Capability — import-vault

An import crosses a trust boundary: an ungoverned external tree enters a
governed vault. The `aios import` script owns every mechanical guarantee
(read-only source, dry-run default, checkpoint, one-time marker, validation);
this procedure owns the human side. **The plan is authored with the owner and
executed by the machine — never invent mappings.**

1. **Mode from the workstyle map** (`80 User/workstyle.md`, if present): any
   load-bearing machinery or a side-by-side posture → `verbatim` (no renames,
   no moves — their automations keep working; converge later in owner-gated
   waves). Full adoption with no machinery → `mapped`. No map → ask the two
   questions that decide it (machinery? posture?) before anything else.
1a. **Overlap check before the plan** (multi-file intake, always): run
   `aios dedupe-batch <the source tree>` read-only and put the result in front
   of the owner. An external tree is the worst case for repetition — re-exports,
   backup copies, and "final v2" siblings — and nothing else in the pipeline
   compares the incoming files to *each other* (`aios dupes` compares records to
   canon). Overlaps go into the survey and into the plan conversation as
   quarantine or merge candidates; **never auto-resolve them** — the owner
   decides which copy is the fuller record. Sibling command, different job: keep
   the distinction explicit when reporting.
2. **Survey the source read-only** and draft `import-plan.yaml` in a new
   `System/Migrations/NNN-<name>/` folder, walking the owner folder-by-folder
   ("these look like knowledge records — map or quarantine?"). Anything
   unmapped goes to the Inbox quarantine rule — nothing is ever dropped, and
   nothing is ever imported that the owner didn't see in the plan.
3. **Dry-run and present the report in the owner's vocabulary**: counts per
   rule, collisions, sanitized names, secret flags (each one is the owner's
   call), the source's own broken-link baseline (pre-existing breakage,
   recorded so the import is never blamed for it), and what will be
   quarantined.
4. **Owner approves → `--apply`**, then walk them through the result: what
   moved where, validation status, the quarantine count ("your Inbox has N
   items; they drain at your pace via ingest-and-connect"), and — if project
   stubs were minted — **the review queue**: every stub carries `review_due`
   (default +14 days; plan `review_after_days:` or `--review-days` tunes it)
   and a truthful "Contains:" line, and the generated
   `System/Migrations/NNN-<name>/review-queue.md` lists them all. Tell the
   owner what "review" means: set the stage, confirm the contents, or archive.
   `aios review-due` surfaces them when due; `aios health` reports any left
   unreviewed past their date — the system never forgets its own instruction.
5. **Offer once, never press**: a dedupe-integration session for any
   duplicate candidates, an Inbox processing plan they may accept or decline, and — verbatim imports only —
   the convergence conversation (each wave owner-gated; re-test their
   machinery after every wave; keys never rename while anything depends on
   them). Migration was the one allowed suggestion; after this, the topic
   waits for the owner to raise it.

Journal the import (the script writes its own line; add context if the owner
made notable calls). `aios validate` and `links` must be green before the
session ends — compare links against the recorded baseline, not against zero.
