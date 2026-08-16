# Personal AI OS

**A portable folder that stores what you know — and a rulebook that lets a filesystem-capable AI use it, add to it, and keep it organized over time. You own it; the AI is a guest.**

Most AI tools forget your context or trap it inside one vendor. Personal AI OS keeps your knowledge, decisions, sources, and working methods as ordinary files you control. A compatible AI reads the rules in this folder and can file new material, connect it to what's already there, retrieve answers from your records, and maintain the collection under proportional write controls. Supported retrieval names the records it used. Consequential and system changes receive heavier preflight, reporting, and recovery controls than ordinary writes.

The runtime is replaceable by design. This release ships profiles for **Claude Code and Codex**, both at the conservative uncertified L2 default. Certification is earned by running the battery in an individual installation; the shipped profiles do not claim external or universal runtime certification.

**Security-boundary note:** with a runtime that can directly read and write this folder, privacy switches, protected paths, and the off switch are compliance rules the runtime must obey—not an OS sandbox. The current product does not ship a mechanically isolated brokered mode. Keep material you cannot expose to that runtime outside its filesystem reach; see [`Privacy and Boundaries.md`](System/Governance/Privacy%20and%20Boundaries.md).

**Your knowledge is stored in an open standard, and you can verify that yourself.** Google Cloud publishes the [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) — currently **OKF v0.2** (July 2026; v0.1 was June 2026): a folder of Markdown files with YAML frontmatter, one required field. Your knowledge folders (`00 Inbox` … `90 Archive`) are a conformant OKF bundle exactly as they sit on disk — not converted, not exported, using the spec's own bundle-as-subdirectory form. Run `python3 System/Scripts/aios.py okf-check` and it verifies them against Google's rules, **names the spec version it checked against**, and tells you plainly. It covers the content of every add-on pack you have installed too, and **reports how many notes it read and where they were**, so the verdict can't be broader than the reading behind it. Portability here is a command you run, not a promise you're asked to trust.

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
