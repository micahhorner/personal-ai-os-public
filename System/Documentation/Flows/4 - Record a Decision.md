---
id: doc-flow-record-a-decision
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-record-a-decision
version: 1.1.0
created: 2026-07-13
updated: 2026-07-25
summary: "User walkthrough for the record a decision flow — routed via record-decision into the top-level Decisions/ folder (DEC-095)."
---

# Flow 4 — Record a Decision

**Capture what was decided, why, by whom, and when to revisit — as a durable, dated record that stays authoritative and resurfaces when it should.**

Visual: `System/Documentation/Diagrams/svg/28-flow-record-a-decision.svg`.

---

## Your goal

Make an important choice stick, so months later "what did we decide, and why?" has a clear, cited answer.

## What you say

> "Record a decision: we're going with the annual plan. Reason: cash flow. Revisit in January."

## What happens

1. The `record-decision` route fires (you don't have to say "record a decision" — settling a choice out loud, *"let's go with option B"*, is enough) and creates a single **Decision** record in the top-level `Decisions/` folder — what was decided, the reason, the alternatives it closed, who decided, and the date. If anything essential can't be inferred, it asks you at most **one** question.
2. It sets a revisit date so the decision resurfaces for review rather than quietly aging.
3. It links the decision to the project (`project:` field), people, and notes it relates to — the generated register (`System/Generated/index-decision.md`) lists your decisions newest first and grouped by project.
4. From then on, the decision **outranks old meeting notes** when the system answers questions about the topic. You cite it by its id (a dated slug like `decision-2026-07-25-annual-plan`) — decisions never carry hand-assigned numbers, which is why two recorded in parallel can't collide.

## What you get

- A durable, dated decision you and the AI can cite forever.
- Automatic resurfacing at revisit time, via the weekly review.

## If it goes wrong

- **Decision changed?** Record the new one; the system supersedes the old (never deletes it — the history stays honest).
- **Filed to the wrong project?** Ask it to relink; consequential changes are journaled and reversible.

## Related

- The record types, including Decision — `Diagrams/svg/08-knowledge-model-lifecycle.svg`.
- How supersession keeps the current decision authoritative — `Diagrams/svg/18-metadata-relationship-model.svg`.
