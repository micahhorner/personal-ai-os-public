---
id: doc-flow-weekly-maintenance
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-weekly-maintenance
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: "User walkthrough for the weekly maintenance flow."
---

# Flow 7 — Weekly Maintenance

**Once a week, say the word. The system checks health, flags what's gone stale, tells you what's waiting in your Inbox, and hands you a short list of judgment calls — handling everything else itself. It never empties the Inbox without asking you first.**

Visual: `System/Documentation/Diagrams/svg/31-flow-weekly-maintenance.svg`.

---

## Your goal

Keep your knowledge trustworthy over the years without doing upkeep by hand — so it compounds instead of decaying into a pile you can't rely on.

## What you say

> "Run weekly maintenance."

## What happens

1. It runs a full **health check** — validation, broken links, duplicates, review-due items, Inbox age.
2. It **reports the Inbox** — how many items, how old the oldest — and **offers** to run them through the normal filing pipeline. It waits for your answer; a yes to "run maintenance" is not a yes to this.
3. It does **freshness triage** — bumping, re-deriving, flagging stale, or proposing archival for items whose sources changed.
4. It rebuilds the indexes and takes a **fresh restore point** (a zip snapshot).
5. It hands you a **short list of judgment calls**, ordered by consequence — usually a few lines.

## What you get

- Consistent links, up-to-date knowledge, and an honest count of what is still waiting in the Inbox (drained too, if you said yes).
- A short human review queue — your judgment, not filing.
- A fresh, human-restorable snapshot.

## If it goes wrong

- **List too long (>10 items)?** The system says so — that means the cadence or settings need retuning, not more effort.
- **Maintenance feels heavy?** Simplify (fewer fields, fewer reviews). If it's a burden, it's misconfigured.

## Related

- The full weekly pass under the hood — `Diagrams/svg/17-weekly-maintenance-workflow.svg`.
- The no-invisible-maintenance rule — `Diagrams/svg/05-change-control-tiers.svg`.
