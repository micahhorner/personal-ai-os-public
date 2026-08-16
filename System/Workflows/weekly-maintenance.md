---
id: workflow-weekly-maintenance
type: workflow
file_class: canonical
component_type: workflow
status: active
authority: canonical
canonical_for: workflow-weekly-maintenance
version: 1.2.1
cadence_days: 7
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
- System/Tests/scripts/test_freshness.py
- System/Tests/scripts/test_health_riders.py
- System/Tests/scripts/test_flat_folders.py
x_runtime_evaluations:
- System/Tests/fixtures/03-stale-canonical
- System/Tests/fixtures/30-folder-rules
created: 2026-07-10
updated: 2026-08-09
summary: The weekly pass that keeps the vault healthy without burdening the user — run by the Steward or on request.
---

# Workflow — weekly maintenance

Run by the Steward agent (or any L2+ runtime) on the user's chosen day.

1. `aios health` — full report (validate, links, dupes, the doc gates, vocab, review-due, inbox, unverified-in-knowledge — the Principle 26 signal: notes filed as canon but never verified).
2. **Report the Inbox — do not drain it.** The Steward inventories and prioritizes; the count, the age of the oldest item, and anything unclassifiable go to the human list. Items are worked through `ingest-and-connect` **only** if the user says yes to the Inbox specifically — asking for the weekly pass is not that yes. A cadenced run may surface the Inbox; **no scheduled task may empty it** (DEC-101, executing the owner's ruling of 2026-07-15). Past ~20 items, say so and offer the `inbox-processing` workflow. (Recommend-only also means the Steward itself never creates canonical content: the ordinary runtime executes whatever the user approves.)
3. freshness triage per `maintain-vault` (capability).
4. Steward drift checks: adapters, generated-file hashes, component-index-vs-reality, doc authority, and **documentation coverage** (`aios doc-check` — every component mapped to a described diagram; already rolled into the step-1 `aios health` report, surfaced here as the drift it guards, DEC-051).
5. `aios generate` — rebuild indexes and views.
6. `aios checkpoint --zip -m "weekly maintenance"` (the --zip keeps a fresh human-restorable snapshot at all times).
7. Deliver the human review queue: one line per judgment call, ordered by consequence, **short**. If it exceeds ~10 items, include a recommendation for retuning decay classes or cadence.
