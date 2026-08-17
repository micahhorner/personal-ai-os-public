# Personal AI OS

**A user-owned operating environment for long-lived work with AI. The AI can change; your memory, methods, rules, and recovery history stay with you.**

Personal AI OS turns an ordinary folder into a durable working system for a filesystem-capable AI. It keeps your notes, sources, decisions, preferences, projects, procedures, and operating rules together as readable Markdown and YAML. The model supplies reasoning for the current task; the folder supplies continuity across tasks, sessions, machines, and supported AI runtimes.

It is not a new model, chatbot, cloud account, database, or proprietary memory service. It is the **governed layer between you, your files, and a replaceable AI runtime**.

## The problem it solves

Most AI products are excellent at a conversation and weak at continuity. Important context is scattered across chats, silently summarized, tied to one vendor, or lost when the model changes. Giving an agent unrestricted access to a large folder creates the opposite problem: it may have plenty of context, but no stable rules for what to read, what to trust, what it may change, or how to recover from a mistake.

Personal AI OS addresses both problems:

- **Continuity without lock-in:** knowledge and operating context live in files you control rather than inside one model's memory.
- **Context without loading everything:** the AI follows a deterministic entry chain and opens only the rules and records relevant to the current job.
- **Action without unconstrained agency:** routine, consequential, and system-level writes receive different levels of review and recovery control.
- **Change without losing provenance:** sources remain distinct from derived notes; decisions, dependencies, validation results, and supported recovery artifacts remain inspectable.
- **Upgrades without starting over:** direct versioned migrations, checkpoints, validation, and rollback paths carry supported installations forward.

## The central design

The AI is replaceable. The folder is the lasting asset.

Every compatible runtime begins at one operator entry point. From there it reads a compact always-on rulebook, the task router, and its runtime profile. The router classifies the request and loads the specific procedure for that job instead of giving every task the entire manual. The profile defines the runtime's privacy and autonomy ceiling; the manifest contains the owner-controlled write switch and identifies protected parts of the system.

That creates a six-part operating flow:

1. **Connect a filesystem-capable AI.** Claude Code and Codex profiles ship today. The architecture is runtime-neutral, but other tools must be checked before being represented as supported.
2. **Load the house rules.** The runtime learns the non-negotiable privacy, source-integrity, instruction-trust, protected-file, and no-secrets rules.
3. **Route the request.** A deterministic router decides whether the job is retrieval, writing, ingestion, maintenance, recovery, onboarding, or system development.
4. **Follow a tested procedure.** The selected capability provides the step-by-step method, required inputs, boundaries, validation, and escalation points.
5. **Use separate read and write disciplines.** Retrieval filters before relevance and names the records used. Writes receive controls proportional to their consequences.
6. **Leave the durable result in your folder.** Knowledge, decisions, sources, preferences, activity records, and recovery history remain ordinary files that can be inspected without the AI.

[![Full Personal AI OS architecture](System/Documentation/Public%20Release/Architecture/ai-os-architecture-full.png)](System/Documentation/Public%20Release/Architecture/ai-os-architecture-full.md)

*Open the [plain-language architecture companion](System/Documentation/Public%20Release/Architecture/ai-os-architecture-full.md) for an accessible walkthrough of the diagram.*

## What it can do

The delivered system includes 15 active capabilities—14 in the core plus one in the preinstalled open Obsidian Bases pack—along with three specialist agents, two recurring workflows, and 36 documented commands. Together they support work such as:

- finding relevant records while enforcing the built-in retrieval eligibility rules;
- creating and updating structured notes without silently duplicating existing material;
- capturing and processing new material while keeping unreviewed input distinct from trusted knowledge;
- importing an existing collection through a reviewed, staged process;
- recording decisions, managing projects and to-dos, and preserving session handoffs;
- checking freshness, links, schemas, component evidence, and the health of the installation;
- installing or removing governed add-ons without treating their contents as authority;
- designing a new capability through adversarial review, tests, and explicit approval;
- checkpointing, upgrading, recovering, and validating the system with or without Git.

The deterministic command layer handles work that should not depend on model judgment. The AI handles interpretation, synthesis, and guided execution. The written procedures connect the two.

## How reading and writing are governed

### Retrieval

Supported retrieval applies privacy classification, AI-use policy, domain, lifecycle status, and trust rules before relevance. It starts from summaries, opens only the records likely to help, treats instructions found inside content as untrusted data, and reports which records it used—or that none qualified. This makes the retrieval path inspectable; it does not promise that every free-form answer from every model will cite perfectly or never hallucinate.

### Writes

Writes are divided by consequence:

- **Ordinary changes**—such as a new leaf note or a corrected link—use the appropriate schema, search before creating, write, and validate.
- **Consequential changes**—such as edits to canonical knowledge, merges, or renames—also inspect declared relationships, resolve or surface ripple effects, and record what changed.
- **System changes**—rules, schemas, components, runtime behavior, and protected objects—require the developer procedure, checkpoint, impact review, explicit approval, and tests.

Declared mutating commands use safe-path checks, scoped concurrent-edit detection, atomic publication or rollback for their own write sets, and post-write validation where the command contract requires it. Direct edits made by another program or person outside those transactions are not coordinated by the system.

## What you own

Your installation contains the knowledge layer and the machinery needed to operate it:

- an Inbox for material awaiting review;
- projects, knowledge, decisions, and a routed to-do list;
- immutable captured sources plus linked derived records;
- outputs and an archive;
- your preferences, voice, privacy choices, and working style;
- optional packs that add capabilities without rewriting the core;
- the manifest, rules, procedures, schemas, tools, tests, documentation, and recovery records.

The knowledge layer follows Google's open [OKF v0.2 specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) and can be checked locally with `python3 System/Scripts/aios.py okf-check`. The entire product remains inspectable as files; Obsidian and Git are useful but optional.

## Who it is for

Personal AI OS is for people whose work with AI extends beyond a disposable chat: researchers, writers, strategists, operators, consultants, builders, and anyone maintaining a body of knowledge or a repeatable way of working. It is especially useful when you want to change AI vendors without rebuilding your context, understand why the system behaved a certain way, or keep important work accessible independently of an AI service.

The tradeoff is intentional structure. This system asks the user and the AI to follow visible procedures, maintain metadata, and distinguish raw input from reviewed knowledge. Someone who wants a zero-setup chatbot or invisible automatic memory may find it heavier than necessary.

## Honest boundaries

- **It is not a security sandbox.** Direct-file mode is not an OS sandbox: a runtime with filesystem access is technically able to read or alter anything its OS account can reach. Privacy switches, protected paths, and the off switch are compliance rules that the runtime must obey. The current product does not ship a mechanically isolated brokered mode.
- **It does not make model judgment infallible.** It adds structure, provenance, deterministic checks, and recovery mechanics; it cannot guarantee that an AI's interpretation is correct.
- **It is not certified for every AI tool.** Claude Code and Codex profiles ship at the conservative uncertified L2 default. Higher autonomy and runtime certification must be earned in an individual installation.
- **It does not coordinate every possible editor.** Transaction and rollback guarantees apply to the declared commands and write sets that implement them, not arbitrary simultaneous edits made outside those workflows.
- **It is not a hosted backup service.** The folder is portable and includes backup/recovery procedures, but you remain responsible for maintaining copies on storage you control.

Those boundaries are part of the design, not fine print. The goal is not to claim perfect agency; it is to make useful AI-assisted work more durable, inspectable, portable, and recoverable.

For the canonical privacy model and operational implications, read [`Privacy and Boundaries.md`](System/Governance/Privacy%20and%20Boundaries.md). For the complete high-level flow, open [`How the System Works.md`](System/Documentation/How%20the%20System%20Works.md).

## Start here

| You want to… | Read |
|---|---|
| Decide if this is for you (5 min) | [`System/Documentation/Product Overview.md`](System/Documentation/Product%20Overview.md) |
| See it work (10 min) | [`System/Documentation/Quick Start.md`](System/Documentation/Quick%20Start.md) |
| Actually understand it | [`System/Documentation/How the System Works.md`](System/Documentation/How%20the%20System%20Works.md) |
| Use it day to day | [`System/Documentation/Human User Manual.md`](System/Documentation/Human%20User%20Manual.md) |
| Set it up for someone | [`System/Documentation/Implementation and Admin Guide.md`](System/Documentation/Implementation%20and%20Admin%20Guide.md) |
| Fix something | [`System/Documentation/Maintenance and Recovery Guide.md`](System/Documentation/Maintenance%20and%20Recovery%20Guide.md) |

Or simply open [`START-HERE.md`](START-HERE.md) — the folder explains itself; that's the design.

## Getting started with your copy

Personal AI OS is free and open source under the MIT license — download it, clone it, or have an implementer set it up with you in one session (see the Implementation and Admin Guide). However you got here:

1. Put the folder anywhere on your computer — **the folder is the entire product.** No database or service is required. Your knowledge remains ordinary files, readable with any text editor.
2. From the folder, run `python3 System/Scripts/setup.py`. It creates an isolated sibling environment named `.<folder-name>.aios-venv` (outside the vault so snapshots stay exact), installs the pinned PyYAML range there, generates required state, and runs the first instance-health check.
3. Open it with a filesystem-capable AI runtime. Vendor-neutral runtimes begin at `AGENTS.md`; Claude also has the thin `CLAUDE.md` adapter pointer. Say: *"Read the root operator entry point and set this system up for me."*
4. Optional: open the same folder in [Obsidian](https://obsidian.md) as a vault — it arrives pre-configured; one trust-click and you're in.

*Use it, change it, back it up, run it on as many machines as you like, and share it — MIT asks only that the copyright notice travels with it (see `LICENSE.md`). The knowledge you put inside your copy is yours alone; the license covers the system, not your notes.*

**Requirements:** Python ≥ 3.9 with PyYAML (for the built-in check/backup/search tools) · Git optional (zip snapshots work without it) · everything is plain Markdown + YAML, readable forever with any text editor. Tooling is CI-tested on macOS and Linux; Windows tooling is untested in v1 — the vault's *files* are plain text and work everywhere.

## What's in the box

```
00 Inbox … 90 Archive   your knowledge, in plain Markdown
Decisions/              one dated record per settled choice
To-Do.md                the routed to-do list
80 User/                your profile, preferences, privacy rules
System/                 the rules, playbooks, tools, tests, and docs
SYSTEM-MANIFEST.yaml    the machine entry point — and the off switch
START-HERE.md           the human entry point
```

<!-- docgen:note-class-count -->8<!-- /docgen:note-class-count --> record types · <!-- docgen:capability-count -->14<!-- /docgen:capability-count --> core AI playbooks, with another supplied by the preinstalled open pack (15 active delivered) · <!-- docgen:agent-count -->3<!-- /docgen:agent-count --> specialist AI roles · 2 core workflows · 1 deterministic command tool · a compact always-on AI rulebook. All 36 CLI commands are documented. The current version is the one in `SYSTEM-MANIFEST.yaml` (`system_version`); what changed in each release: [`CHANGELOG.md`](CHANGELOG.md). The one-line "why" behind every standing rule: [`System/Governance/Active Decisions.md`](System/Governance/Active%20Decisions.md).

## Development

Changes to this system follow its own governance (that's the point):

- Every change is proven in a crash-test copy first, with evidence.
- Local gate before any push: `bash System/Scripts/gate.sh`. CI runs that exact script.
- PRs merge only on green CI. Protected areas (rules, schemas, the AI's own permissions) change only with explicit owner instruction.
- History and rationale: the in-vault change journal, `Active Decisions.md`, and the architecture spec's amendment log.

- One add-on already ships pre-installed, in the Packs folder: Obsidian Bases Authoring, which teaches the AI to build Obsidian table and board views over your notes. Ask for it by name. Use the governed remove command when uninstalling so workspace archival, rollback, index refresh, and validation stay intact.

## License

The Personal AI OS core and the already-open packs shipped in this repository are MIT-licensed. See [`LICENSE.md`](LICENSE.md), which is the standard MIT text and nothing else, so automated tooling identifies it correctly.

Packs and vertical products may carry their own license file. Their `pack.yaml` must name that attached file explicitly; a pack never inherits the root MIT license by implication. PMM Engine is a separate `pmm-engine` distribution and retains its existing proprietary personal-use license, including for copies used in paid consulting. That is not a new commercial grant: any broader sale, redistribution, sublicensing, or service term requires owner/counsel wording.

**Your content is yours.** The knowledge you place inside your own installation belongs to you. The license covers the system, not the notes you put in it, and nothing here gives anyone a claim over them.

*Licensing history: an all-rights-reserved license (DEC-010, 2026-07-10) with a per-person grant added 2026-07-12 was replaced with MIT on 2026-07-28. MIT was chosen over Apache-2.0 so the core matches the add-on packs. An MIT grant on a released version is irrevocable for that version — later versions may be licensed differently, but what has shipped stays shipped.*

## Contributing and security

Bug reports and pull requests are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md) for how changes are governed here (this system is maintained under its own rules, which is the point). To report a security issue privately rather than in a public issue, see [`SECURITY.md`](SECURITY.md).
