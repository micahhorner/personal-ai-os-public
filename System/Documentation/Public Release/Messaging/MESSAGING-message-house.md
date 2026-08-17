---
id: doc-public-message-house
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture]
canonical_for: public-message-house
version: 1.0.0
product: personal-ai-os
status: active
author: Claude (Fable 5), owner-requested framing work 2026-07-28
created: 2026-07-28
updated: 2026-08-13
summary: "The current AI OS message house for the v1.64.5 release, with historical evidence kept separate."
---

# AI OS — Message House

This is the approved messaging source for outward Personal AI OS copy. Use it with the claims ledger and require owner voice approval before publication.

## The house

**Villain: the start-over loop.** You chat, you upload files, maybe you've set up a Project. It does OK. Session ends; tomorrow you upload the same files and explain the same backstory, from the top. Concrete, no analogy — it's the reader's actual Tuesday. Name Projects explicitly ("Projects soften this; nothing ends it"); it earns trust with the people who've tried the best chat offers.

**Promise: one folder on your computer gives the work somewhere durable to accumulate.** Avoid “fixes it” as an absolute: a folder must still be maintained, reviewed, and backed up.

**Three pillars, in this order (the order is a ladder — each unlocks the next):**
1. **The memory** — your context, saved once, as plain files. Kills the loop. Yours forever.
2. **The rulebook** — what the AI can see and touch, restore points, one off switch. Makes write access sane.
3. **The procedures** — 14 core capabilities for recurring work, plus one active capability from the shipped open pack. Answers can become reviewable work instead of disappearing into chat.

**Two arguments, matching the two audiences:**
- **Argument 1 (everyday chat users):** the problems you already have with chatbots, solved. This is the hero, always.
- **Argument 2 (builders):** agents and automations need the same three things; this is the foundation, already built. One box, after argument 1, never before.

**The one allowed polished contrast (Voice Card law A budget):** "The AI is rented. The folder is yours." It lives on the architecture diagram and nowhere else in a given piece.

**The one-breath walkthrough (for narrating the diagram):** you ask at the top, the rules load first, the system sorts the job and hands the AI a procedure, questions come back with receipts, changes go through one door that stops to ask when they're big, and it all lands in one folder that still opens in TextEdit if every company on the page disappears.

**Standing kicker line:** "You own the folder. The AI is a guest."

## Vocabulary rulings (owner, in session, 2026-07-28)

- **Never "head"** in outward copy. "The AI" / "the AI you plug in." Owner: "sounds weird."
- **"Headless" is reserved for technical content.** The civilian bridge paragraph (shipped on the explainer, "More on the AI you plug in" section) is the approved way to introduce it: folder ships with no AI inside, on purpose; the intelligence is a plug-in.
- **Anchor on the chatbot experience.** Everybody knows chatbots; few know agents. Meet them there.
- **Rejected framings — do not resurrect as leads:** workplace/new-hire onboarding analogy ("no abstract analogies"); processor/OS/files computer-architecture lead ("too technical"); memory-as-filing-cabinet metaphors. Tech-concept relations may appear in *support* (restore points, permissions, version history) but never as the headline frame.
- Plain declarative headlines. No triads, no rhythmic parallelism, no em dashes anywhere (Voice Card law 1).
- **Explanations are literal, always** (owner ruling 2026-07-28, second confirmation): no analogies or metaphors when explaining what AI OS is — plain everyday words (folder, files, rules, instructions, knows you, asks permission, undo, yours). Source: `MESSAGING-plain-explanations.md`. The metaphor bank is PARKED.

## Claim guardrails

Every factual public claim runs [`CLAIMS-LEDGER.md`](CLAIMS-LEDGER.md). The knowledge layer is an OKF v0.2 bundle, never “the repo is a bundle.” No priority claims, certification claims, universal-runtime claims, behavioral absolutes, physical-sandbox implications, or v1.64.5 qualification totals without its definitive evidence. “Verify the stated scope” beats every superlative.

## Asset inventory (as of 2026-08-13)

- **[`../Architecture/ai-os-hero-v2.png`](../Architecture/ai-os-hero-v2.png)** — current text-free launch hero with negative space for copy and no security-wall metaphor.
- **[`../Architecture/ai-os-explainer.html`](../Architecture/ai-os-explainer.html)** — current responsive v1.64.5 explainer, grounded in the full architecture diagram and claims ledger.
- **[`../Architecture/ai-os-architecture-full.svg`](../Architecture/ai-os-architecture-full.svg)** — primary current v1.64.5 architecture explainer; its [Markdown companion](../Architecture/ai-os-architecture-full.md) is the accessible factual transcript.
- **[`../Architecture/ai-os-architecture.svg`](../Architecture/ai-os-architecture.svg)** — concise current v1.64.5 orientation graphic.
- **[`../Architecture/ai-os-proof-card-v1641.svg`](../Architecture/ai-os-proof-card-v1641.svg)** — historical v1.64.1 evidence only; do not present it as current v1.64.5 proof.

Superseded workshop graphics, PMM Engine material, thought-leadership drafts, and session-only artifacts are intentionally excluded from this public set.

## Companion stories

- **Your words stay yours** (`MESSAGING-story-your-words-stay-yours.md`, added 2026-07-25): the attribution differentiator — your AI's ideas never quietly become your notes. Supports pillar 1 (the memory is *yours*, down to who said what). Hooks live in hook-bank family 14; the literal explanation is in plain-explanations; the client-facing form is Leave-Behind point 4.

## Where this language applies

Use this language to keep the repository README, START-HERE path, onboarding, user manual, public explainers, and buyer collateral consistent. Product mechanics and canonical documentation remain authoritative over this messaging guide.
