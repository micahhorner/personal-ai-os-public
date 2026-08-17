---
id: doc-flow-grow-the-system
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-grow-the-system
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: "User walkthrough for the grow the system flow."
---

# Flow 9 — Grow the System

**Want a new kind of note, a repeatable workflow, or an automation? Tell the Extension Builder what you're trying to accomplish. It designs the smallest thing that works, tests it, documents it — and never lets you hand-edit the machinery.**

Visual: `System/Documentation/Diagrams/svg/33-flow-grow-the-system.svg`.

---

## Your goal

Extend what the system can do without being an engineer — safely, with everything registered, tested, documented, and recoverable.

## What you say

> "I want a repeatable way to prep for client calls."
> "Add an automation that summarizes new reviews."

## What happens

1. The **Extension Builder** clarifies the outcome and checks whether something already covers it (extend before invent).
2. It picks the **least powerful component** that works (a script before a workflow before a capability).
3. It writes a **one-page design → your sign-off** → scaffolds → implements → tests → **documents** → activates.
4. Activation is **gated**: a component cannot go live without passing tests *and* being documented (a diagram + description), with your approval.

## What you get

- A new capability or workflow that is registered, tested, documented, and recoverable.
- No schema design on your part — the guided process handles it.

## If it goes wrong

- **Recommends against building it?** That's a valid, common outcome — often an existing flow already does the job.
- **Never hand-edit `System/`** to add things — that bypasses the guardrails; always go through the guided process.

## Related

- The component lifecycle and its gates — `Diagrams/svg/08-knowledge-model-lifecycle.svg`.
- The agent that runs it — `Diagrams/svg/13-agent-model.svg`.
