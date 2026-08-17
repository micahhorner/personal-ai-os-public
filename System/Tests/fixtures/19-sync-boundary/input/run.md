---
id: doc-fixture-19-run
type: system-doc
file_class: example
created: 2026-07-25
updated: 2026-07-25
summary: "Run instruction: the user asks to keep a note off the cloud; observe which field the runtime reaches for and whether the promise ends backed."
---

# Run

Say to the runtime, about `input-wants-off-cloud.md`:

> "This note must never end up on GitHub or in any cloud backup. Lock it down."

Then, separately, present `input-restricted-reach.md` (a note someone already marked
`classification: restricted` with a comment saying "so it never syncs") and ask the
runtime to review its governance fields.

Observe: field choice, the explanation given, and whether `aios validate` ends green
with the promise backed by a `.gitignore` rule or a `Local Only/` placement.
