---
id: doc-product-overview
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture]
canonical_for: product-overview
version: 1.3.3
created: 2026-07-10
updated: '2026-08-16'
summary: One page — what Personal AI OS is, who it's for, and why it exists. The first thing a new person should read.
---

# Personal AI OS — Product Overview

**Who this is for:** anyone deciding whether this system is worth their time. Five minutes, no technical background needed.

## The problem

You explain yourself to AI tools over and over. The context you build up in one chat is gone in the next. Decisions, sources, and hard-won lessons are scattered across conversations, apps, and vendors — and none of it accumulates into anything you own. If you cancel the subscription, the "memory" goes with it.

## What this is

**Personal AI OS is a private, portable folder that stores what you know — and a rulebook that lets a compatible AI use it, add to it, and keep it organized under explicit controls.**

Another way to say it: **the AI supplies replaceable reasoning; the folder supplies continuity.** The durable layer is not a model's memory. It is the knowledge, preferences, operating rules, procedures, provenance, and recovery history that you can inspect and keep when the model changes.

The step past a second brain: a second brain stores what you know; this stores what you know, how it connects, and how the work actually gets done on it.

Everything is ordinary files on your computer: your notes, your decisions, your sources, your preferences, and the rules the AI must follow. The shipped profiles support **Claude Code and Codex**; another filesystem-capable runtime needs its own adapter and evidence before it should be described as supported. The runtime reads the vault's rules and can file new material, connect it to what's already there, and retrieve from qualifying records while naming the records used. Writes receive controls proportional to their impact. New, uncertified runtime instances start at **L2**: validated low-risk writes are allowed, while guided multi-file and structural work requires higher earned certification and the applicable approval gates.

With today's direct-file runtimes, those privacy and write rules are compliance controls, not a physical sandbox: the runtime can technically open any file its OS account can reach. The current release does not ship a mechanically isolated brokered mode. That limitation matters when deciding what material to place within the runtime's filesystem reach.

## The job it does

Without a durable layer, every AI session begins by reconstructing the same context: who you are, what you are working on, which sources matter, what was decided, how you prefer to work, and what the AI may change. Personal AI OS turns that repeated explanation into a maintained asset.

It coordinates five things that normally live in separate products:

1. **Memory you control** — ordinary files holding knowledge, sources, decisions, and preferences.
2. **Task procedures** — a compact rulebook and job-specific playbooks, loaded only when relevant.
3. **Selective context** — privacy- and domain-aware retrieval that names the records it used.
4. **Controlled action** — validated writes with stronger review and recovery as consequences increase.
5. **Long-term continuity** — backups, migrations, generated indexes, and tested recovery that let the folder survive model and version changes.

It is designed for long-lived work with filesystem-capable AI: research, projects, decisions, writing, and personal knowledge that should compound over time. It deliberately favors transparent structure over invisible convenience. A person seeking only a zero-configuration chat assistant may not need it; a person who wants an AI working repeatedly on an owned body of knowledge is the intended user.

## Why it's different

- **You own it.** Plain files in a folder you control. No database, no lock-in, readable with any text editor forever.
- **Open format, verifiable — not just promised.** Your knowledge folders are a conformant bundle under Google Cloud's **Open Knowledge Format** (OKF v0.2, July 2026 — the current spec; v0.1 was June): Markdown plus a small metadata block, the format Google specified for giving AI curated context. Not a private format with an export button — the open one, as stored. `aios okf-check` verifies it against Google's own rules on demand and tells you which spec version it checked — and how many notes it read, across your own folders and the content of every add-on pack installed — so you can confirm your knowledge is portable instead of taking anyone's word for it, and see exactly what the verdict covered. AI OS goes further than the spec where a real system must — **which document wins when two disagree** (authority), what supersedes or contradicts what, privacy classes, and an audit history — which the format explicitly allows. Where the format has caught up, we say so rather than keep the old sales line: v0.2 makes provenance and freshness first-class, so those are no longer ours alone.
- **The AI stops forgetting.** Context you record once is there for every future conversation.
- **Answers name their basis.** Retrieval answers identify the vault records used so you can inspect them. When those records cite original sources, the source trail is preserved; the system does not promise that every record or answer has an external citation.
- **Knowledge compounds.** New information is checked against what you already know — what it confirms, contradicts, or makes outdated.
- **Knowledge problems stay visible.** For supported consequential changes, declared relationships and pending ripple effects are surfaced for judgment; promoted knowledge carries a review date suited to its type; recurring routines report when they've quietly stalled. The system reports review work instead of claiming it made every connected note correct.
- **A vetted core, not a landfill.** What you capture is only *staging* until it's checked; only verified, connected knowledge is treated as fact. Your vault is the size of what you've vetted — not everything you ever dumped in.
- **Your ideas stay yours.** Feed it your AI conversations and it keeps the voices straight: it measures who said what, builds your notes from *your* claims, and keeps the assistant's contributions only where they're faithful to your meaning — its own theses and vocabulary are attributed or dropped, never quietly filed as your beliefs.
- **It reads your documents, and proves it read them.** Drop a Word document in and its *contents* enter the vault, not just the file: headings, lists, tables and images preserved — and then the conversion is checked back against the original, paragraph by paragraph. If anything failed to survive, you get told and the original is kept, rather than a tidy-looking file with a page missing. And when material arrives as a folder of overlapping exports, the system tells you how much each file repeats the others *before* anything is harvested — so the same idea, copied into three files, is never counted as three independent sources.
- **Proportional safeguards.** Every write gets preflight and validation. Consequential changes add dependency checks and a journal entry; system changes require a checkpoint, impact review, tests, and approval. Ordinary leaf edits deliberately avoid journal and checkpoint ceremony. The AI can be shut off with one line, and setup walks you through choosing a backup (`Backup and Recovery Options.md`, same folder as the manuals).
- **It learns your system — you don't learn its.** If you already organize notes your own way (PARA, Zettelkasten, anything), the AI maps your method and speaks your language; supported import uses a reviewed plan, isolated staging, validation, and recovery, or your existing vault can stay where it is.
- **It can learn your whole way of working.** An optional guided step — the **Method Kit** — turns how you actually work (your rituals, rules, and vocabulary) into your own operating-method pack the AI then follows.
- **Change vendors, keep the system.** The AI is a guest. Swap it and the folder — your asset — comes with you.

## What it is not

Not a new AI model. Not a note-taking app (Obsidian is the recommended viewer, and it ships ready to go). Not a cloud service. Not a security sandbox. Not software that silently runs your life. It's the durable, user-owned layer *between* you and whatever compatible AI you use.

## Where to go next

- **Try it in ten minutes** → `Quick Start.md` (same folder as this file)
- **Understand how it works** → `How the System Works.md`
- **Day-to-day use** → `Human User Manual.md`
