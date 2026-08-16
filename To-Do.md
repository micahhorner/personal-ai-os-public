---
id: note-to-do
type: note
status: active
created: 2026-07-25
updated: 2026-07-25
summary: "The routed to-do list. Sessions maintain it through the manage-todo capability; every item carries its own context — what, why it matters, what it blocks, and a path that resolves."
---

# To-Do

**The contract** (kept by the `manage-todo` capability — the `manage-todo` router row loads it):

- **Sessions update this file; it never updates itself.** Adding, completing, and
  reprioritizing go through `manage-todo`, which is what keeps the list alive —
  a list nothing routes to is a list nothing re-reads.
- **An item carries its context**: *what* to do, *why it matters*, what it
  *blocks or is blocked by*, and *a path that resolves* (a file, a note id, or a
  named next step). A bare file reference is not an item.
- **Paths are link-checked.** Any path an item references is verified whenever the
  capability touches the list; dead paths are flagged in place with `⚠`, never
  silently kept or silently deleted.
- **Counts come from scripts.** Statements about this vault (file counts, versions,
  coverage) are extracted live, never copied from this file's prose.

## Items

- [ ] **Read the Quick Start** — why: the fastest way to see the whole system work
  once, end to end · blocks: confident daily use of the routes below it · path:
  `System/Documentation/Quick Start.md`

## Done

<!-- completed items move here with their completion date; prune during the weekly pass -->
