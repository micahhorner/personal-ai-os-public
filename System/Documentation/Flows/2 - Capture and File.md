---
id: doc-flow-capture-and-file
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-capture-and-file
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: User walkthrough for the capture-and-file flow — drop something in the Inbox and turn it into connected, cited knowledge.
---

# Flow 2 — Capture & File

**Get anything worth keeping into your knowledge without doing the filing yourself. You drop it in the Inbox and say the word; the system preserves the original, extracts what matters, and links it to everything related — cited back to the source.**

Visual: `System/Documentation/Diagrams/svg/25-flow-capture-and-file.svg`.

---

## Your goal

Turn a raw thing — a meeting note, a document, a pasted email — into knowledge you can search and trust later, without stopping to organize it.

## What you say

Drop the file into `00 Inbox/`, then, in plain language:

> "Process my inbox."

That's it. There's no format to follow and nothing to tag. You can drop several things and process them together.

## What happens

1. **Your original is preserved** as a **Source** and never rewritten — only annotated. Your evidence stays exactly as it arrived.
2. **The useful content becomes notes** — claims, findings, and open questions are pulled out as their own records.
3. **Decisions get their own record** — anything that reads as "we decided X" becomes a Decision, dated and connected.
4. **Everything is deduped and linked** — the system checks what already exists so you don't get duplicates, and connects the new material to the projects, people, and notes it relates to.
5. **It narrates what it did**, in one line per item, so you can see the filing rather than trust it blindly.

You don't choose note types, folders, or tags — the system classifies during filing (and, if you gave it your own method during setup, it uses *your* names and tags).

## What you get

- **Connected notes you can search**, each **cited back to the original** so you can always trace a claim to its evidence.
- **An empty Inbox** — the goal is zero; quarantine is temporary by design.
- **Your originals kept safe** in `30 Sources/`, untouched.

## If it goes wrong

- **Something was filed wrong?** Say "show me what you changed" (the journal) and ask it to fix or reclassify — consequential changes are reversible and journaled.
- **It couldn't classify something?** Unclassifiable items are surfaced to you with a one-line description rather than guessed at.
- **You want to undo a batch?** Every processing run leaves the vault restorable; see `Flows/11 - Stop and Recover.md`.

## Related

- **How it works under the hood:** the ingest pipeline and its nine effects — `Diagrams/svg/14-inbox-canonical-pipeline.svg`.
- **The safe-write discipline** every new record follows — `Diagrams/svg/15-safe-write-flow.svg`.
- **Adjacent flows:** `Flows/3 - Ask and Get Answers.md` (use what you filed), `Flows/5 - Add Spoken Context.md` (capture what isn't written down).
