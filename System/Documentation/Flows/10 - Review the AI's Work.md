---
id: doc-flow-review-the-ai-work
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-review-the-ai-work
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: "User walkthrough for the review the ai's work flow."
---

# Flow 10 — Review the AI's Work

**See exactly what the AI did, in plain terms. The journal is your audit trail; stale flags and approvals surface what needs your judgment. Trust you can verify, not trust you have to assume.**

Visual: `System/Documentation/Diagrams/svg/34-flow-review-the-ai-work.svg`.

---

## Your goal

Stay in control and confident — know what changed, catch anything that needs you, and never wonder what the AI did behind your back.

## What you say

> "Show me what you changed today."
> "What's due for review?"

## What happens

1. Every **consequential or structural** change was written to the change journal as it happened (ordinary leaf edits stay out, so the journal is worth reading).
2. When something a note depends on changes, the note is marked **stale** rather than silently rewritten.
3. Anything meant for outside use carries an **approval** state; if anyone (including the AI) edits an approved item, it drops back to pending.
4. Stale items and judgment calls **surface in the weekly review** so nothing waits silently.

## What you get

- A plain-language audit trail you can skim weekly.
- A clear queue of what needs your judgment — stale items, approvals, conflicts.

## If it goes wrong

- **Something looks off?** Stop writes (one line) and read the journal — then restore a checkpoint if needed (`Flows/11 - Stop and Recover.md`).
- **Too much to review?** That signals the cadence needs retuning; the system will say so.

## Related

- The change-control tiers and the four-outcome rule — `Diagrams/svg/05-change-control-tiers.svg`.
- What runs automatically to protect you — `Flows/Automations Reference.md`.
