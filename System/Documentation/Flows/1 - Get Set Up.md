---
id: doc-flow-get-set-up
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-get-set-up
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: "User walkthrough for the get set up flow."
---

# Flow 1 — Get Set Up

**Make the folder yours and set your privacy defaults in a short guided conversation. You are productive after the first two stages; the rest can wait.**

Visual: `System/Documentation/Diagrams/svg/26-flow-get-set-up.svg`.

---

## Your goal

Go from a fresh copy of the folder to a system that is yours, private by your rules, and ready to use — without editing anything by hand.

## What you say

> "Read START-HERE.md and set this system up for me."

## What happens

1. The AI reads its own rules first (by design), then starts onboarding — a friendly conversation, one question at a time, everything skippable.
2. **Stage 1, Orientation:** it explains what it may and may not do, and shows you the off switch. You say "go."
3. **Stage 2, Privacy:** before collecting anything, it sets what counts as private for you, whether work and personal stay separate, and any off-limits topics.
4. It flips one line (`instance_role`) with your permission — that is what makes the generic master *your* instance.
5. Progress is saved continuously, so you can stop and it resumes exactly where you left off.

## What you get

- A vault that is yours, private by your own rules, ready for daily use.
- Only stages 1 and 2 are needed to start — roles, goals, and preferences can happen any other day.

## Recommended: use Obsidian

The folder **ships pre-configured as an Obsidian vault** — dark mode, navigator, backup plugin, sensible settings — and Obsidian is the recommended way to use it: free, fast, and far nicer than clicking through `.md` files in your file manager. Point Obsidian at the folder, answer the one trust prompt on first open ("trust and enable community plugins?" → yes), and you have a clean way to read and navigate everything. Details: `System/Documentation/Obsidian Setup Tips.md`.

Because it is all plain files, you are never *locked into* Obsidian — any editor opens them and the system does not depend on it. That is your insurance, not a reason to skip it: for almost everyone, Obsidian is simply how you use your vault.

## If it goes wrong

- **Overwhelmed?** Every question is skippable, forever. The simplest rule: anything you would not share with your AI, just skip.
- **Stopped partway?** Say "resume onboarding" — it picks up at the saved stage.
- **Changed your mind on privacy?** Adjust anytime; the settings are yours.

## Related

- The eight stages in full — `Diagrams/svg/09-onboarding-journey.svg`.
- Next: `Flows/2 - Capture and File.md` — feed it something real.
