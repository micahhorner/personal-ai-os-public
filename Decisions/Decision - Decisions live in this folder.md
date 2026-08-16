---
id: decision-2026-07-25-decisions-live-here
type: decision
status: active
decided_at: 2026-07-25
decision_makers:
- the product (shipped default — your own decisions replace this line with your name)
project: 
supersedes: 
review_condition: "Revisit if the register view stops being consulted — a decisions space nothing reads is the failure this design exists to prevent."
related: []
sources: []
created: 2026-07-25
updated: 2026-07-25
summary: "Shipped example and true record: user decisions live in the top-level Decisions/ folder, routed by record-decision, with dated slug ids and a generated register — never hand-claimed numbers."
---

# Decisions live in this folder

*(This is the shipped example decision — it demonstrates the record form and it is a true record of the convention it describes. Your own decisions look like this.)*

## Decision

User decisions in this vault live in the top-level `Decisions/` folder — one consolidated space, reached through the `record-decision` route — with dated slug ids (`decision-YYYY-MM-DD-<slug>`) as their only stable handle and a register view generated from frontmatter on every `aios generate`.

## Why

A decisions space must be as obvious as the Inbox. A folder nested inside Knowledge is a folder you have to be told about, and a folder nothing routes to becomes a forgotten convention within hours of existing — both failures were observed in the field before this design shipped. Derived numbering exists because hand-claimed register numbers collided repeatedly: when the number is computed from the records, two decisions recorded in parallel cannot collide by construction.

## Alternatives considered

- `20 Knowledge/Decisions/` — rejected: not findable without being told; it was in fact forgotten by its own owner.
- Per-project decision files — rejected: two homes recreate the scatter one space exists to end; the `project:` field plus the generated per-project view covers the need.
- Hand-assigned register numbers (`D-001`, …) — rejected: "check the register first" empirically fails under parallel sessions; numbers are derived in the generated view, never claimed in records.

## Evidence available at the time

The estate this product grew from had at least five separate decision registers and four live numbering collisions before this convention was adopted (product register, DEC-095).

## Tacit context

The product's own governance register (`System/Governance/Active Decisions.md`) is a separate object owned by product updates — user decisions never go there.

## What this affects

Where every future decision record in this vault is written; how it is cited (by id, never by position).

## History

- 2026-07-25 — shipped with the product (v1.40.0, DEC-095; D1–D3 owner-ratified 2026-07-25).
