---
id: doc-fixture-20-todo-routing
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-20-todo-routing
created: 2026-07-25
updated: 2026-07-25
summary: "Behavioral fixture: 'add to my to-do list' routes to manage-todo and produces an item carrying all four context parts; a context-free add triggers exactly one clarifying question, never a bare write; a dead path in the list is flagged in place on load."
---

# Fixture 20-todo-routing

**Scenario**: The user adds, completes, and reprioritizes to-do items through conversation. The runtime must route to `manage-todo` (the list is routed, never remembered), enforce the item-carries-context rule without making capture heavy, and flag rot (dead paths) in the items it touches.

**Setup / input**: A scratch copy whose `To-Do.md` is seeded with one item referencing a deliberately dead path, plus `input/run.md` probes.

**Pass criteria** (all must hold):
- [ ] A context-rich add produces one item under `## Items` with all four parts — what, why it matters, blocks/blocked-by, a resolving path — with **no** clarifying question, `updated:` bumped, and `aios validate` run
- [ ] A context-free add ("fix the thing") triggers **exactly one** clarifying question before writing — a bare one-line write fails the fixture, and so does a part-by-part interrogation (more than one question)
- [ ] If the user declines to answer, the item is still written with the gap visibly marked — the capture is never lost to the contract
- [ ] The seeded dead path is flagged in place (`⚠ path does not resolve:`) and surfaced to the user on the first manage-todo load that touches the list — never silently kept, never silently deleted
- [ ] Completing moves the item to `## Done` with the date (not deletion); reprioritizing only reorders `## Items`
- [ ] Any count or claim about the vault in the runtime's answers comes from scripts, not from the list's prose

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
