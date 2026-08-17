---
id: capability-manage-todo
name: manage-todo
component_type: capability
status: active
version: 0.1.1
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-manage-todo
summary: "Add, complete, and reprioritize items in the root To-Do.md; every item carries its context (what · why · blocks · resolving path) and every path an item references is link-checked on load."
description: "Maintain the routed to-do list in To-Do.md — add, complete, reprioritize. Use when the user says 'add X to my to-do list', asks what's on the list, marks something done, or reorders priorities. Enforces the item-carries-context rule with at most one clarifying question, and flags dead paths in the items it touches."
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
x_runtime_evaluations:
- System/Tests/fixtures/20-todo-routing
documentation: self
created: '2026-07-25'
updated: '2026-08-09'
---

# Capability — manage-todo

The to-do list is routed, never remembered. `To-Do.md` at the vault root is the one
list; this capability is the only procedure that maintains it. The structural reason
to-do items rot is that nothing routes to the file — so nothing re-reads it, and it
drifts into asserting things that are no longer true. This capability is the route,
and the link-check below is the rot detector.

## When

The user adds to, asks about, completes, or reorders their to-do list. Trigger
phrases: "add X to my to-do list", "what's on my list?", "mark that done",
"make X the top priority". Bounded multi-session work is a *project* — route it
through the project-start row ("let's start a project") instead; a to-do item is
one actionable thing.

## The item contract (the four parts)

An item states, on one entry:

1. **What** — the action, concrete enough to start.
2. **Why it matters** — one clause; if no one can say why, question the item.
3. **Blocks / blocked by** — what this unblocks, or what must happen first ("nothing" is a valid answer, stated).
4. **A path that resolves** — a real file path, a note id, or a named next step.

**A bare file reference is not an item.** "Look at X.md" carries no why, blocks
nothing stated, and rots the moment its context is forgotten.

## Adding — capture stays light (one question max)

1. Read `To-Do.md`. If it is missing, recreate it first: frontmatter
   (`id: note-to-do`, `type: note`, `status: active`, dates, summary) plus the
   contract header, `## Items`, and `## Done` — ordinary lane, validate after.
2. **Draft all four parts yourself from the conversation's context.** Most adds
   arrive with the why and the blocks already said or plainly inferable — use them.
   Mark genuinely inferred parts per the kernel (inference is labeled) only where
   the inference is a stretch; plain restatement of what the user just said is not
   an inference.
3. **Ask at most ONE clarifying question**, and only for a part you genuinely
   cannot infer. Never interrogate through the contract part by part — friction
   here kills the capture habit the list depends on. If the user declines to
   answer, write the item anyway with the missing part marked
   `(unstated — flag at next touch)`: a flagged capture beats a lost one.
   What is forbidden is the silent bare write, not the imperfect item.
4. **Link-check** every path the new item references (step: does the file/id
   resolve? — same check as the rot detector below).
5. Write the item under `## Items` (top = highest priority unless the user says
   otherwise), bump `updated:`, run `aios validate`. Report in one line.

## Completing and reprioritizing

- **Complete**: move the item to `## Done` with the completion date. Don't delete —
  `## Done` is pruned during the weekly pass, not at completion time.
- **Reprioritize**: reorder under `## Items` (order *is* priority); content of the
  items themselves is untouched.
- Both end with `updated:` bumped and `aios validate`.

## The rot detector (every load)

Whenever this capability touches the list, **link-check the paths in every item it
reads or writes**: each referenced vault path or note id must resolve (check
existence directly, or `aios resolve --query <id>` for ids). A dead path is flagged
in place — prefix the reference with `⚠ path does not resolve:` and tell the user —
never silently kept and never silently deleted; the fix (repoint, rewrite, or drop
the item) is the user's call. Counting or asserting anything about the vault goes
through scripts (kernel §4), never through this file's prose.

## Fences

- One list, at the root. Per-project to-do files and a generated cross-project
  rollup are explicitly future scope — do not improvise them.
- No PM-tool integration; the list is a plain routed note.
- This capability edits `To-Do.md` only (plus recreating it when missing). Anything
  else the conversation asks for routes normally.
