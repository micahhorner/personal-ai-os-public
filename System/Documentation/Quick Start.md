---
id: doc-quick-start
type: system-doc
file_class: canonical
authority: derived
x_reviewed_against: ["doc-onboarding-specification:1.10.0", "doc-human-onboarding-guide:1.10.0"]
derived_from: [doc-onboarding-specification, doc-human-onboarding-guide]
canonical_for: quick-start
version: 1.2.1
created: 2026-07-10
updated: 2026-08-14
summary: From a copied folder through deterministic setup, a proven AI connection, and your first grounded answer.
---

# Ten-Minute Quick Start

**Who this is for:** you just received this folder and want to see it work before reading anything else. **You will:** run the deterministic setup, prove your AI is connected to the real folder, feed it one real thing, and get an answer grounded in your own material.

## Before you start: choose a supported AI

Your OS is a folder on your computer; to operate it your AI must be able to read *and write* that folder. This release ships profiles for two hosted, filesystem-capable runtimes: **Claude Code and Codex**. Other runtimes need their own adapter and evidence before they should be described as supported. A plain chat session without filesystem tools may help you reason about files you provide, but it cannot operate the folder.

## What you need

- This folder, copied anywhere on your computer you like.
- One of the two runtimes profiled in this release — **Claude Code or Codex** — opened with access to this folder.
- **Recommended: Obsidian**, pointed at this folder as a vault — free, and far nicer than clicking through files in your file manager. It arrives **pre-configured** — dark mode, navigator, backup plugin, sensible settings. First open asks one question ("trust and enable community plugins?") — click yes, done. Details: `Obsidian Setup Tips.md`, same folder as this file. (It's plain files underneath, so you're never locked in — but Obsidian is how you'll actually use your vault.)

## Step 1 — Run the deterministic setup

From this folder, run:

```bash
python3 System/Scripts/setup.py
```

The script creates an isolated Python environment beside the folder, installs the pinned dependency, generates required state, and runs the first instance-health check. If it reports an error, stop there rather than working around it.

## Step 2 — Connect your AI to the real folder

Open `System/Onboarding/Connect Your AI.md` and complete both proofs: your runtime must read the token in `CONNECT-CHECK.md`, then create and remove the temporary test file that you confirm on disk. Do not continue with onboarding if only the read proof passes.

## Step 3 — Start from the operator entry point

Open your AI runtime in this folder and say:

> "Read AGENTS.md and set this system up for me."

`AGENTS.md` sends the runtime through `SYSTEM-MANIFEST.yaml`, the manifest's AI reading order, the Task Router, and the active runtime profile before onboarding begins. Claude's `CLAUDE.md` is only a thin adapter pointer into that same root chain. `START-HERE.md` is the human entry point, not a substitute for the AI operator entry chain.

During onboarding, the generic master becomes your personal instance: the AI asks for your explicit permission before changing the protected `instance_role` setting. You do not need to edit it yourself.

## Step 4 — The two onboarding stages that matter first

Full onboarding has eight stages, but only the first two are needed to start:

1. **Orientation** — the AI explains what it may and may not do, and shows you the off switch. You say "go."
2. **Privacy defaults** — before it collects anything: what counts as private for you, whether work and personal stay separated, any topics that are completely off the table, and — a separate question — whether anything must never leave this computer (no cloud sync, no hosted backup; that's the `sync: local-only` switch, or just a folder named `Local Only/`). **Simplest rule: anything you're not comfortable sharing with your AI, just skip.** Skipping is always allowed, forever.

Everything else (your roles, goals, preferences) can happen now or any other day — progress is saved and the AI resumes exactly where you left off.

**Already have a way of organizing notes** — PARA, Zettelkasten, daily notes, your own invention? Later in setup the AI asks once, reads how your existing notes are organized (with your permission, read-only), and drafts a one-page map of your method for you to correct. From then on it speaks your language. Your old notes can move in too — offered once, never pushed.

## Step 5 — Feed it something real

Drop one real file into the `00 Inbox/` folder — meeting notes, a document, an email you pasted into a text file. Then say:

> "Process my inbox."

Watch what it narrates: the original is preserved as a **source**, the useful content becomes connected **notes**, any decisions get their own record, and everything links back to where it came from.

## Step 6 — Ask it something

Ask a question your file can answer:

> "What did we decide about X?"

Supported retrieval names the qualifying records it used, so you can inspect the basis for the answer. That is not a promise that every conversational sentence receives a formal citation. Ask something the vault cannot support — a good answer is "your vault has nothing on that." Honest emptiness is a feature; this system never pads.

## That's the product

Eight things to remember — this is the entire user's job:

1. **Put new things in the Inbox.** The AI does the filing.
2. **Ask questions normally.** For supported vault retrieval, the AI names the qualifying records it used and abstains when the vault lacks support. Same for your to-do list — *"add X to my to-do list"* keeps `To-Do.md` (at the root) alive and honest — and for new work: *"let's start a project"* gives it a real home in `10 Projects/`.
3. **Say "record this decision"** (or just settle one — *"let's go with option B"*) when something important gets settled: one dated record lands in the top-level `Decisions/` folder, and the generated register keeps them findable — newest first, by project.
4. **Approve anything meant for outside use** before it goes out.
5. **Once a week, say "run maintenance."** You get a short list of judgment calls; the AI handles the rest.
6. **Keep one copy off this machine.** Onboarding helps you pick how (a private GitHub remote, an encrypted drive, more) — every option with honest tradeoffs lives in `System/Documentation/Backup and Recovery Options.md`, and the health check reminds you when content that never leaves this machine has no recorded copy.
7. **The off switch**: open `SYSTEM-MANIFEST.yaml`, set `ai_writes_enabled: false`. All AI writing stops; your files stay yours. (`START-HERE.md` shows this too.)
8. **When a new version ships**, updating is one command that keeps your notes and customizations untouched: `System/Documentation/Upgrading.md` walks you through it.

## If anything looks wrong

Say "stop" (or flip the off switch), then open `System/Documentation/Maintenance and Recovery Guide.md` — it starts from symptoms, not theory, and assumes nothing works except a text editor.
