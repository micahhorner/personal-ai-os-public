---
id: doc-flow-ask-and-get-answers
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-ask-and-get-answers
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: "User walkthrough for the ask & get cited answers flow."
---

# Flow 3 — Ask & Get Cited Answers

**Ask anything in plain language and get an answer built from your own records, cited by name — or an honest "nothing on that" when your vault is empty on the topic.**

Visual: `System/Documentation/Diagrams/svg/27-flow-ask-and-get-answers.svg`.

---

## Your goal

Get a trustworthy answer from what you already know, without re-explaining your life or wondering where the answer came from.

## What you say

> "What did we decide about pricing, and why?"
> "What do we know about Project Atlas?"

## What happens

1. It filters by your privacy rules **first** — anything restricted, prohibited, or out-of-domain is invisible before ranking even starts.
2. It orients from a cheap index and pulls the smallest trustworthy set of *current* records (following supersession, preferring decisions and fresh notes).
3. It flags anything past its review date as "verify before relying," rather than presenting stale material as fact.
4. It answers, **citing your records by name** so you can trace every claim.

## What you get

- An answer grounded in your own material, with citations you can open.
- Or an honest "your vault has nothing on that" — never a padded guess.

## If it goes wrong

- **Answer seems stale?** It will flag verify-before-relying; ask it to re-check the source.
- **Expected something it didn't find?** The material may be filed under privacy/domain rules that exclude it, or may simply not be captured yet.
- **Keep re-explaining the same thing?** That is a gap worth capturing — say so, and record it.

## Related

- How retrieval works under the hood — `Diagrams/svg/16-retrieve-context-flow.svg`.
- Privacy filtering that runs first — `Diagrams/svg/06-privacy-routing-gate.svg`.
