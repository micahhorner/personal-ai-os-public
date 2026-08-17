---
id: doc-implementation-admin-guide
type: system-doc
file_class: canonical
authority: derived
x_reviewed_against: ["doc-onboarding-specification:1.10.0", "doc-canonical-architecture:2.22.0", "doc-change-control-and-preflight:1.1.0"]
derived_from: [doc-onboarding-specification, doc-canonical-architecture, doc-change-control-and-preflight]
canonical_for: implementation-and-administration
version: 1.3.0
created: 2026-07-10
updated: '2026-08-13'
summary: How to take a person from the clean product to a working, validated, handed-off personal system — and how to administer it afterward. For implementers and administrators, not everyday users.
---

# Implementation and Admin Guide

**Who this is for:** the person setting this system up for someone else (or for themselves, thoroughly), and the person responsible for it afterward. **You will be able to:** create a personal instance, run a complete implementation in one session, hand it off, and administer permissions, backups, and upgrades. Everyday use is *not* this document — that's the `Human User Manual.md`.

## Part 1 — Implementation (one session, eight visible stages)

### Stage 1 · Prepare

1. Copy the clean product folder to the user's machine, named whatever they like.
2. Decide the backup posture with them: Git repository (recommended — private remote), or rely on zip snapshots (built in, no Git needed).
3. That's it. Everything else happens inside the folder, guided.

### Stage 2 · Connect

1. Open the folder in the AI runtime (today: Claude Code, started in the folder).
2. Optionally open the same folder in Obsidian as a vault — a pleasant viewer, never required. It arrives pre-configured (plugins included); the user clicks one trust prompt on first open, and `Obsidian Setup Tips.md` documents what was chosen. **Importing an existing Obsidian corpus?** Their old vault's plugin *settings* may still be worth carrying over selectively — but never copy an old `workspace.json` over the shipped one (stale window state is how plugins break; F-5).
3. Verify the ground state before anything else: say *"Confirm the kill switch is on and tell me your autonomy level."* Expect: writes enabled, autonomy **L2** (the shipped default — everyday validated writes; more is earned, see Part 2).

### Stage 3 · Onboard

Say *"Read START-HERE.md and set this system up for me."* The AI runs the eight-stage onboarding conversationally. As implementer, know what each stage produces:

| Stage | What happens | What gets created |
|---|---|---|
| 1 Orientation & consent | Explains itself, shows the kill switch, confirms this copy is a personal instance | consent + `instance_role` recorded |
| 2 Privacy defaults | Sensitivity defaults, work/personal separation, off-limits topics, and the separate storage question — must anything never leave this machine? (`sync: local-only`, DEC-092) — *before any data collection* | `80 User/privacy-rules.md` (protected from then on) |
| 3 Identity | Roles and domains | `80 User/profile.md` |
| 4 Goals & inventory | 3–5 concrete first jobs; where their stuff currently lives (list only, imports come later); if they have a prior note system, the workstyle capture runs here — consent, read-only scan, drafted map they correct | `80 User/goals-and-uses.md`; `80 User/workstyle.md` when a prior system exists |
| 5 Personalization | Note subtypes they'll use, vocabulary, review cadence — within approved bounds only; asks whether they have voice/authoring standards and wires them in (rules or a one-line pointer) | `80 User/vocabulary-extensions.yaml`; `80 User/voice.md` and/or `80 User/authoring.md` when they have standards |
| 6 First real content | 3–10 real items through the Inbox, narrated | real sources + notes with provenance |
| 7 Prove it | Three real questions (cited answers, honest abstention) + one narrated safe write | results recorded |
| 8 Wrap | Maintenance day, review appetite, backup choice (full menu, user picks, evidence marker explained), completion report | `80 User/onboarding-report.md` |

Every stage is skippable and resumable — progress lives in `80 User/onboarding-progress.yaml`. Answers live in `80 User/onboarding-answers.yaml`. **Tell the user plainly:** anything they're not comfortable having in the vault, they skip. There is no per-line secrecy inside files (DEC-026) — what enters the vault is their call.

### Stage 4 · Seed and Stage 5 · Prove

Stages 6–7 of onboarding *are* the seed-and-prove steps — don't skip them. The user must see the pipeline run on **their own material** and watch one safe write happen with narration. This is where trust is built; a user who watched it file their real meeting notes understands the product better than any document can teach.

### Stage 6 · Validate

Before handoff, run the mechanical checks (or ask the AI to):

```bash
python3 System/Scripts/aios.py validate   # every record follows the rules
python3 System/Scripts/aios.py links      # no broken references
python3 System/Scripts/aios.py health     # overall state
python3 System/Scripts/aios.py checkpoint --zip -m "implementation complete"   # --zip guarantees a human-restorable snapshot even on a Git install
```

All green + a named restore point = done.

### Stage 7 · Hand off

Give the user one page, verbally and literally — the short list from `Quick Start.md` ("That's the product"): Inbox, ask, record, approve, weekly maintenance, backup, off switch. Show them the off switch **live**: open `SYSTEM-MANIFEST.yaml`, point at `ai_writes_enabled`. A user who knows they can stop everything trusts the system; one who doesn't, won't.

### Stage 7b · Bring their existing vault in (only if they want it)

Before the plan, run **`aios dedupe-batch <their source tree>`** read-only and show them the result. An external corpus is the worst case for repetition — re-exports, backup copies, "final v2" siblings — and no id/title/alias check can see it: the proven case was four documents handed over together where one was 97% a paste-up of two others and shared no id, title, or alias with them. Overlaps become quarantine-or-merge conversations in the plan; never resolve them for the owner, because which copy is the fuller record is a judgment (there, the near-duplicate was the *superset*).

If the user has an existing note corpus and chose to move it in (their workstyle map records the posture — never push this): use **`aios import`**, not hand-copying. Author `import-plan.yaml` with them per `System/Capabilities/import-vault/SKILL.md` — mode `verbatim` when anything mechanical depends on their structure (templates, queries, scripts: nothing renames), `mapped` for full adoption (their metadata survives as `x_` extensions; anything unmapped is quarantined to the Inbox, never dropped). The pipeline enforces itself: dry-run first, their approval, checkpoint, validation, one-time marker; their original vault is opened read-only and never modified. Both modes were proven by replaying two real production migrations byte-for-byte before this feature shipped.

### Stage 8 · Pilot

Two to four weeks of real use before any extension or customization beyond onboarding. Have them note *repeated* friction (not one-off wishes). Extensions come from lived friction, never speculation — this rule is what keeps the system small.

## Part 2 — Administration

### Permissions: how much the AI may do

The AI's authority comes from its **runtime profile** (`System/Runtime Profiles/` — the manifest's `active_profile` names the live one). Autonomy levels, in plain terms:

- **L0** — read and search only.
- **L1** — may draft into the Inbox for review.
- **L2** — everyday validated safe writes. **This is the shipped default.**
- **L3** — guided multi-file work (still gated by approvals). **Earned**, not assumed: the runtime must pass the certification battery (`System/Tests/Certification Battery.md`) with results recorded in `System/Tests/results/`.
- **L4** — structural work; every instance individually human-approved regardless of certification.

Certification is an engineering control, not a user concept — users never see it; you administer it. To raise a runtime's level: run the battery, record the results honestly (who observed it matters), update the profile. The profile is a **protected object** — changing it requires explicit human instruction, and no AI may ever raise its own.

### Four assurance verdicts — never substitute one for another

- **`aios source-check`** checks the generic product source, documentation, schemas, generated state, and automated tests. The legacy `aios certify` name is temporarily retained as an explicit source-check alias; it does not certify a runtime or qualify a release.
- **`aios instance-health`** reports the integrity and advisories of one installed vault. `aios health` remains its compatibility surface.
- **`aios runtime-certify`** verifies evidence for one named runtime profile. An empty, incomplete, or legacy self-reported record returns **NOT CERTIFIED**. Source tests and shipped autonomy defaults are never runtime evidence.
- **Release qualification** is a separate historical lifecycle gate: supported release coverage, exact legal/product convergence, every declared fault boundary, and exact Git plus no-Git recovery. Only that gate may say a release is qualified.

The generic product intentionally ships with no earned runtime certification. Human testing and external live-model evaluation must be named when performed and must never be inferred from automated source tests.

### Protected objects

Listed in `SYSTEM-MANIFEST.yaml` under `protected_objects`: the manifest itself, architecture, governance, schemas, agents, the runtime's own rules and profiles, adapters, operations, certification records, and the user's privacy rules. The AI may not touch any of it without the human explicitly asking. If a user reports the AI proposing changes there uninvited, that's a defect — journal it and stop writes.

### Backups and recovery

- **Checkpoints**: `aios.py checkpoint -m "label"` — a Git commit when Git is present, a zip snapshot otherwise (zips land next to the vault folder). Add `--zip` to force a human-restorable snapshot even on a Git install — do this at handoff and before anything major, so nontechnical recovery never depends on Git. `--zip-only` writes just the snapshot with **no git commit** — the right tool when the tree carries work that isn't ready to commit. Cheap; make them before anything you're unsure about. A checkpoint commits the whole working tree by design (you can always save state), and its **commit message lists every path it contains**, so you can always see what went in; `--paths <files or folders>` narrows it to what you declare and reports the rest as left alone, and `--strict` makes it refuse rather than sweep when anything outside that scope has changed — useful when more than one person or session is working in the same folder.
- **Rollback**: use the exact `rollback_command` printed by `checkpoint`. It carries the full immutable Git commit or snapshot path plus its recorded SHA-256, restores the exact earlier tree, and validates the result. Git recovery preserves any bytes it will overwrite or clean in an external pre-restore archive first. No-Git recovery validates and stages the complete snapshot beside the vault before swapping it into place, keeps the prior live tree as a sibling, and automatically puts that prior tree back if installation or validation fails. Scoped `--paths` checkpoints print a scope-bound rollback command whose identity includes the requested paths; it restores and cleans only that scope while leaving unrelated work untouched.
- **Off-machine copies**: the full menu with honest tradeoffs is `System/Documentation/Backup and Recovery Options.md`. `System/Scripts/backup-clone.sh <destination>` requires `rsync`, creates an exact mirror, and records the evidence marker (`80 User/LAST-BACKUP.txt`) only after success. If exact mirroring is unavailable it refuses rather than label an additive copy current. No marker reads as **never**; the check cannot produce a false "covered."
- **The journal** (`System/Journal/change-journal.md`) is append-only history — never delete it; it's excluded from "disposable" by design.
- **Full-loss drill** worth doing once with every user: kill switch off → find one answer using only files → copy the folder elsewhere → switch back on. Ten minutes, permanent confidence.

### Upgrades

Structural changes to an existing vault (new required fields, moved folders) go through **migrations**: `aios.py migrate` applies a written, numbered procedure from `System/Migrations/` — always dry-run first, always after a checkpoint. Never hand-restructure a live vault.

**Product versions** are the other axis. Bare `aios.py upgrade <path-to-release>` is read-only: it classifies against the release's shipped `System/.baseline-manifest.json` (DEC-074), binds the exact live/release surfaces, distributions, baseline, accepted conflicts, migration inputs, and protected policy, then prints a semantic review hash without checkpointing or staging a candidate. Apply requires `--apply --confirm --review-sha256 <fresh-hash>`; reproof happens before the first write and at transaction boundaries. The review labels its limit honestly: migrations and generation materialize final candidate bytes later, and the journal pins the resulting trees for recovery. Instance customizations remain kept, both-sides changes are never merged (DEC-073), user content is verified byte-identical, and `system_version` advances only when every gate is green. Releases you ship must carry a fresh baseline: regenerate it on the master with `aios upgrade --make-baseline` (CI fails if stale). Instances predating baselines treat every difference as conflict unless `--base <old release tree or baseline json>` restores exact classification. Procedure: `System/Documentation/Upgrading.md`.

One upgrade behavior to know: the knowledge-freshness feature activates per instance, not per product. The shipped registry (`System/Registries/freshness.yaml`) carries `enforced_since: null`; the instance's first `aios generate` stamps that date and baselines existing notes silently. Nothing that predates the stamp accrues obligations — an upgrade never turns years of old notes into a to-do list.

### The rules of system change (what keeps this trustworthy)

Any change to `System/` follows the heavy lane, no exceptions — including changes you make as an administrator with an AI's help: checkpoint → impact report → explicit approval → change → validate → journal. New components come only through the extension process (`aios.py scaffold`), which refuses to activate anything without existing tests *and* a recorded passing result. If you remember one administrative rule: **nothing lands in System/ casually.**

### Where the truth lives (when documents seem to disagree)

Precedence: current human instructions → `SYSTEM-MANIFEST.yaml` + `System/Architecture/` + `System/Governance/` → other canonical docs → adapters → generated files. The one-line "why" for every standing rule: `System/Governance/Active Decisions.md`.
