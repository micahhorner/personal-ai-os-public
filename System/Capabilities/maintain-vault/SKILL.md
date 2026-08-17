---
id: capability-maintain-vault
name: maintain-vault
component_type: capability
status: active
version: 0.3.1
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-maintain-vault
summary: The periodic health pass — mechanical checks, freshness triage, cache refresh.
description: "Run the periodic health pass — mechanical checks, freshness triage, cache refresh. Use for scheduled maintenance, after bulk changes, or when the vault's health state is unknown."
consolidates:
- skill-review-freshness
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
- System/Tests/scripts/test_freshness.py
- System/Tests/scripts/test_health_riders.py
- System/Tests/scripts/test_flat_folders.py
x_runtime_evaluations:
- System/Tests/fixtures/03-stale-canonical
- System/Tests/fixtures/17-knowledge-freshness
- System/Tests/fixtures/30-folder-rules
documentation: self
created: '2026-07-10'
updated: 2026-08-09
---

# Capability — maintain-vault

1. `aios health` — triage its findings.
2. **Inbox — count it, offer, and stop. Never drain it unasked.** Report how many items are waiting and how old the oldest is. Work them through `ingest-and-connect` **only** if the user says yes to that specifically; otherwise leave every item where it is and carry the count into the human queue (step 6). Processing the Inbox is manual and user-directed — a maintenance pass may surface the Inbox, never empty it, and this step is not the exception just because the user asked for maintenance (DEC-101, executing the owner's ruling of 2026-07-15). Past ~20 items say so plainly: it is a prompt, not a trigger. (Two-phase when the Steward runs this: the Steward inventories and queues — the ordinary L2 runtime executes any ingestion the user approves; the Steward never creates canonical content.)
3. Freshness triage per item surfaced: still correct → bump `review_due` · upstream changed → re-derive if deterministic, else `stale` + queue · contradicted → contradiction handling · obsolete → propose supersede/archive (human approves). Historical records are never "stale." **A project proposed for archive follows `safe-write`'s closure order**: its durable lessons are promoted to `20 Knowledge/` and listed for the user *before* anything moves to `90 Archive/`; proposing the move without naming that step is an incomplete proposal.
3a. **Ripple triage — the judgment leaves mechanical evidence** (SPEC-knowledge-freshness). `aios ripple` lists each changed note's connected neighbors. For every pair, judge the effect (the ingest step-4 nine) and record it: `aios ripple --ack <neighbor> --from <changed> --effect <effect>` — `no-impact` for the common case (`--all` batches it), `makes-stale` marks the neighbor (status only; rewriting it is a queued human-approved edit, never part of the ack). When a changed note's neighbors are all dispositioned, accept it: `aios ripple --baseline <id>`. Never baseline first — that discards the triage obligation unjudged. Then `aios review-due --set-missing` stamps horizons on newly promoted notes (deterministic; grandfathered notes are never stamped).
4. **Now** refresh caches: `aios generate` (the one scheduled place it runs; it also baselines never-seen notes and stamps the enforcement epoch on first run).
5. `aios checkpoint --zip -m "maintenance"` — the --zip keeps a fresh human-restorable snapshot at all times.
6. Human queue: one line per judgment call, ordered by consequence, short. >10 items = the cadence needs retuning — say so.
7. Close the loop: `aios workflow --ran workflow-weekly-maintenance` — the run that skips this line looks like a run that never happened, which is exactly the invisibility this record exists to end.
Steward agent runs this in maintenance mode; its recommend-only contract applies.
