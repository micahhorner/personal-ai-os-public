---
id: doc-flow-add-spoken-context
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-add-spoken-context
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: "User walkthrough for the add spoken / tacit context flow."
---

# Flow 5 — Add Spoken / Tacit Context

**Tell the system something that isn't written down anywhere. It is preserved as a first-class source, clearly labeled as coming from you, so tacit knowledge stops living only in your head.**

Visual: `System/Documentation/Diagrams/svg/29-flow-add-spoken-context.svg`.

---

## Your goal

Capture the unwritten know-how — the things you just *know* — so the system can use it and it survives beyond your memory.

## What you say

> "Something that isn't written anywhere: the client hates surprises — always preview changes with them first."

## What happens

1. It captures your words as a first-class **Source** (spoken context is not second-class here).
2. It labels the source as **coming from you** (`provided_by`) with a confidence level, and marks it as recollection, not documented fact.
3. It connects the context to the relevant people, projects, and notes.
4. Later, it can act on this context and will show *where the claim came from* — never dressing up your recollection as hard evidence.

## What you get

- Tacit knowledge preserved and usable across every future conversation.
- Clear provenance: it is marked as your recollection, with a confidence level.

## If it goes wrong

- **Got a detail wrong?** Correct it; the update is journaled.
- **Sensitive?** Apply your privacy settings — spoken sources follow the same rules as any record.

## Related

- The ingest pipeline that files it — `Diagrams/svg/14-inbox-canonical-pipeline.svg`.
- Provenance and confidence fields — `Diagrams/svg/18-metadata-relationship-model.svg`.
