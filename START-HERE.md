---
id: doc-start-here
type: system-doc
file_class: canonical
authority: canonical
canonical_for: entry-and-authority-map
created: 2026-07-10
updated: 2026-08-09
summary: Human entry point to the Personal AI OS — what it is, where authority lives, and where to go next.
---

# Start Here — Personal AI OS

This folder is a complete, portable Personal AI Operating System. Everything that matters is inside it: your knowledge, the rules that govern it, the tools that maintain it, and the documentation to understand and recover it. It works as plain files — you can read and edit everything here with any text editor. Obsidian is the recommended way to use it (free, pre-configured, and much nicer than a file manager); a filesystem-capable AI runtime makes it powerful. This release ships Claude Code and Codex profiles, while its runtime-neutral operation model is designed to support additional adapters. Because the durable layer is plain files, neither the editor nor the AI vendor can hold your knowledge hostage.

## The one-minute model

- **Your knowledge** lives in the numbered folders (`00 Inbox` through `90 Archive`), plus two top-level homes the numbering has no room for: **`Decisions/`** (one dated record per settled choice, DEC-095) and **`To-Do.md`** (the routed to-do list, DEC-094). All of it is ordinary Markdown notes with a small block of metadata at the top. That's not a house format: those folders are a conformant bundle under Google Cloud's **Open Knowledge Format** (OKF v0.2, the current spec), verifiable any time with `aios okf-check` — which names the version it checked, covers the content of any installed add-on pack as well, and reports how many notes it read and where.
- **The system** lives in `System/` — rules, schemas, templates, capabilities, agents, scripts, tests, and documentation.
- **Your personal configuration** lives in `80 User/` — profile, preferences, privacy rules.
- **Extend in `Packs/`, configure in `80 User/` — don't edit the `System/` core directly.** Add-ons you install live in `Packs/`, your settings in `80 User/`; both are yours and are preserved when you update to a new version. Editing files inside `System/` fuses your changes into the product core and makes future version updates difficult or unsafe — so treat `System/` as the vendor's to update, and keep your customizations in the user and add-on layers.
- **`System/Generated/` is disposable; `System/Logs/` is not disposable as a folder.** Generated views can be rebuilt. Logs is mixed state: ordinary reports may be expendable, but its freshness event log is durable history and its ledger carries live obligations. Never bulk-delete Logs. (`System/Journal/` is your permanent audit history — never delete it either.)
- **AI is a guest here, not the owner.** Every compliant AI write follows the change rules in `System/Governance/`. You can turn all AI writes off in one line (below).
- **Direct file access is not a sandbox.** Claude Code, Codex, and any similar runtime can technically open files their OS account can reach. Privacy and write rules are compliance controls in that mode; this release does not ship a mechanically isolated brokered mode.
- **Shipped does not mean certified.** Claude Code and Codex profiles start at the conservative uncertified L2 default. Runtime certification is earned per installation by completing and recording the certification battery; no certification evidence ships in either profile.
- **Capture is staging; knowledge is earned.** New material lands in `00 Inbox` as unverified staging and becomes trusted knowledge only once it's been checked and connected — the system never treats a raw note as fact (Principle 26, the canonical core).

## Where authority lives

| Question | Authoritative file |
|---|---|
| What is this, in plain terms? | `System/Documentation/Product Overview.md` → `How the System Works.md` |
| How do I get started fast? | `System/Documentation/Quick Start.md` |
| How do I set this up for someone else? | `System/Documentation/Implementation and Admin Guide.md` |
| What is this system? How is it designed? | `System/Architecture/Canonical Architecture Specification.md` |
| What file/format/naming rules apply? | `System/Architecture/Portable Vault Profile.md` |
| What may the AI change, and how? | `System/Governance/Change Control and Preflight.md` |
| What's private, and what may the AI read or send? | `System/Governance/Privacy and Boundaries.md` |
| What do the metadata fields mean? | `System/Documentation/Metadata and Relationship Dictionary.md` |
| How do I use this day to day? | `System/Documentation/Human User Manual.md` |
| How do I update to a new version? | `System/Documentation/Upgrading.md` — keep an external backup and verify the tagged release's published qualification evidence before upgrading an irreplaceable or only copy |
| How should I set up Obsidian? | `System/Documentation/Obsidian Setup Tips.md` |
| How does an AI operate this? | `System/Documentation/AI Operator Manual.md` |
| How do I connect my AI to this folder? (do this first) | `System/Onboarding/Connect Your AI.md` |
| How do I set it up for me? | `System/Onboarding/Human Onboarding Guide.md` |
| I already have a note system / an existing vault — will it adapt? | `System/Documentation/How the System Works.md` §11; bringing the notes in: `System/Capabilities/import-vault/SKILL.md` |
| How do I back up my vault? | `System/Documentation/Backup and Recovery Options.md` |
| How do I add capabilities / install an add-on? | `System/Documentation/Add-Ons and Packs.md` |
| Something broke — now what? | `System/Documentation/Maintenance and Recovery Guide.md` |

The machine-readable index of all of this is `SYSTEM-MANIFEST.yaml`, sitting next to this file.

## Reading order

**If you're a person, new here** — ordered by depth, and it matches `reading_order.human` in `SYSTEM-MANIFEST.yaml` exactly:

- **Get Started** (the quick, plain path): this file → `System/Documentation/Product Overview.md` → `System/Documentation/Quick Start.md` → `System/Onboarding/Human Onboarding Guide.md` → `System/Documentation/Human User Manual.md`.
- **Understand it** (the bridge to the reference layer): `System/Documentation/How the System Works.md`.
- **Reference** (canonical and architecture docs): read on demand — the "Where authority lives" table above is the index.

None of it is required reading. Onboarding will point you at the first set and then get out of the way; no stage waits on your having read anything.

**If you're an AI runtime**: read `SYSTEM-MANIFEST.yaml` and follow its `reading_order.ai` — the Runtime Kernel (your standing rules), the Task Router (what to load for the task at hand), and your runtime profile. Load nothing else unless the router names it. Confirm `runtime.ai_writes_enabled` is true before any write; system-level work loads the full governance stack via the router's developer mode.

## The kill switch

Open `SYSTEM-MANIFEST.yaml` and set:

```yaml
runtime:
  ai_writes_enabled: false
```

Every script in this system that can change your content refuses to run while that is false (two deliberate exceptions: creating a backup snapshot, which preserves rather than changes — and restoring one with `rollback --confirm`, because the switch stops the AI, never you). Compliant AI runtimes also honor it; for a runtime with direct file access this is an obeyed rule rather than a physical barrier. Use validation, change records where required, and checkpoints for the supported workflows that create them to verify what happened. Your files stay exactly as they are; you can keep reading and editing them yourself.

## If you are recovering this system

Go directly to the recovery chapter of `System/Documentation/Maintenance and Recovery Guide.md`. It assumes nothing works except a file manager and a text editor.
