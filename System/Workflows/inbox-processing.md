---
id: workflow-inbox-processing
type: workflow
file_class: canonical
component_type: workflow
status: active
authority: canonical
canonical_for: workflow-inbox-processing
version: 1.2.1
cadence_days: 7
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
- System/Tests/scripts/test_ingest_triage.py
- System/Tests/scripts/test_flat_folders.py
x_runtime_evaluations:
- System/Tests/fixtures/02-contradicting-source
- System/Tests/fixtures/30-folder-rules
created: 2026-07-10
updated: 2026-08-09
summary: "Turn Inbox material into connected knowledge — the capture-to-canonical pipeline; the user starts every run, and nothing is promoted to canon until it clears the gate (Principle 26)."
---

# Workflow — inbox processing

## 0. The user starts this. Always.

**This workflow never runs on its own.** Not on a schedule, not on a count, not as the tail
of another task. The user invokes it — in so many words — and until they do, every item in
`00 Inbox/` stays exactly where it is (DEC-101, executing the owner's ruling of 2026-07-15:
*"Inbox processing should never be automatic. It should be manual and user directed."*).

Three consequences, each stated because each is a way the rule gets lost:

- **`cadence_days: 7` above means this workflow reports itself as due — not that it runs.**
  `aios workflow` and the weekly pass may say "the Inbox has 31 items, oldest 26 days".
  That is the whole of what a cadence buys here. **No scheduled task may drain the Inbox.**
- **The ~20-item threshold produces a prompt, never a run.** Past roughly twenty items,
  report the count and *offer* this workflow. Then wait. A yes starts it; anything else
  leaves it alone. Do not re-ask every turn, and do not begin "just the first few".
- **A general instruction is not the yes.** "Tidy up my vault", "do the maintenance",
  "get me organised" authorise the *reporting*, not the drain. Ask about the Inbox
  specifically and get an answer. Draining it decides, on the user's behalf, what their
  raw material becomes — which is the judgment staging exists to keep in their hands.

## 1. The pass, once invoked

For each item in `00 Inbox/` (oldest first):

1. Classify: source material → `ingest-and-connect` · a thought/idea → `safe-write` (note) · a task for a project → link into the project note · unclassifiable → human list with a one-line description.
2. The capabilities handle the rest (dedupe, template, enrichment, connection, effects).
3. Empty is the goal **of an invoked run** — quarantine is temporary by design, but the user decides when temporary ends. Anything sitting >2 weeks gets surfaced to the human rather than silently aging: surfaced, not processed.
