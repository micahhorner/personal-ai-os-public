---
id: doc-ai-support-guide
type: system-doc
file_class: canonical
authority: canonical
canonical_for: ai-support
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: How any AI answers "how does this product work" questions from the product's own documentation, with citations. The support harness — a map plus rules, not a service.
---

# AI Support Guide

**This is the product's built-in support layer. It points whatever AI a user is running at the product's own documentation so it can answer "how does this work?" questions accurately, with citations, and admit when the answer isn't documented. It is a map plus a small set of rules — not a running service, not a separate model.**

Load this when a user asks how the system works, what a component does, why it behaves a certain way, or where something lives. It applies identically to Personal AI OS and to any vertical built on this core (e.g. PMM Engine) — the core documentation is shared.

---

## The corpus

The answerable corpus is the **full product documentation set**, not any one artifact:

- The generated map is `System/Generated/support-index.json` (rebuilt by `aios generate`; regenerate if absent or stale). It enumerates every documentation file with its path and one-line summary, the reading order, and the diagram atlas.
- The docs themselves: `System/Documentation/` (product overview, how-it-works, manuals, glossary, metadata dictionary, this guide), `System/Architecture/`, `System/Governance/`, `System/Operations/`, `System/Onboarding/`, and every component's own file under `System/Capabilities/`, `System/Agents/`, `System/Workflows/`.
- The **diagram atlas** (`System/Documentation/Diagrams/`) — 44 diagrams with rich descriptions in `diagram-metadata.yaml` and a coverage map in `coverage.yaml`. Diagrams are one *slice* of the corpus: the part that visualizes core components. Use them to explain structure and flow, and offer the relevant diagram when a visual would help.
- The generated `System/Generated/system-reference.md` — a facts-only catalog of components, operations, schemas, and folders, always current by construction.

## The procedure

1. **Resolve the question to the corpus.** Read `support-index.json` first — scan its `docs` summaries and `diagrams` descriptions/`answers` to pick the few sources that actually bear on the question. Do not open the whole documentation set; orient from the index, then read the load-bearing few (this mirrors `retrieve-context`).
2. **Answer from source.** Ground the answer in what those documents say. Prefer the canonical doc over memory. If a diagram illustrates it, name and offer it (e.g. "see `System/Documentation/Diagrams/svg/05-change-control-tiers.svg`").
3. **Cite.** Reference the document(s) you used by path or id, so the user can verify. A support answer without a citation is a guess.
4. **Abstain honestly.** If the corpus does not cover the question, say so plainly rather than inventing an answer. Point to the nearest relevant doc and, if useful, suggest the question become a documentation gap to fill. Never present inference as documented fact.
5. **Respect privacy and scope.** Answer about how the *product* works from System documentation. Do not pull a user's personal content (`80 User/`, private notes) into a "how does it work" answer; those are governed by the privacy rules, not this guide.

## Honesty about enforcement

For a runtime with native file access, this guide is a **binding instruction, not a physical barrier** — the same honesty the product states about privacy enforcement. It works because a compliant AI follows it. The generated `support-index.json` makes following it cheap: the map is one small file, so answering from source is the path of least resistance.

## Keeping it current

The support index is generated — it never goes stale on its own, because `aios generate` rebuilds it from the live documentation on every maintenance pass. When documentation is added or changed, the index picks it up on the next generate; nothing here is hand-maintained. New components must be documented and diagrammed before they can activate (DEC-051), so the corpus stays complete by construction.
