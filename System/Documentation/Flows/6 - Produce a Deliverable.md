---
id: doc-flow-produce-a-deliverable
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-produce-a-deliverable
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: "User walkthrough for the produce a deliverable flow."
---

# Flow 6 — Produce a Deliverable

**Ask the system to draft something from what it already knows. The output lands in your deliverables folder, linked back to every record it drew on, and waits for your approval before it goes anywhere.**

Visual: `System/Documentation/Diagrams/svg/30-flow-produce-a-deliverable.svg`.

---

## Your goal

Turn your accumulated knowledge into a usable artifact — a memo, a summary, a brief — without starting from a blank page or losing track of your sources.

## What you say

> "Draft the kickoff memo from what we know about Atlas."

## What happens

1. It retrieves the relevant records (same privacy-and-freshness discipline as any question).
2. It drafts the deliverable from that material — grounded, not invented.
3. It files the result in `40 Outputs/` with its **lineage preserved** (`derived_from`) back to every source it used.
4. It leaves the output as **draft** — nothing is marked approved for outside use until you say so.

## What you get

- A deliverable in `40 Outputs/`, linked to everything it drew on.
- Full traceability from the artifact back to its evidence.

## If it goes wrong

- **Not quite right?** Iterate in place; the lineage updates with it.
- **Ready to send?** Mark it `approved` — and note that any later edit drops it back to `pending` (so "approved" always means the current version).

## Related

- The in-through-out data flow — `Diagrams/svg/02-data-flow-governance.svg`.
- The approval boundary — `Governance/Privacy and Boundaries.md`.
