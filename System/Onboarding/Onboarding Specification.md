---
id: doc-onboarding-specification
type: system-doc
file_class: canonical
authority: canonical
canonical_for: onboarding
version: 1.10.0
created: 2026-07-10
updated: 2026-08-09
summary: The single authoritative onboarding definition — stages, questions, outputs, validation, and state model. The human guide and AI procedure derive from this document, section by section.
---

# Onboarding Specification v1.10.0

Onboarding turns the generic core into one person's system. It is a **stateful, resumable process**, not a questionnaire: privacy comes before data collection, personalization is progressive (only what's approved), and the process ends with demonstrated retrieval and safe-write behavior — not just filled-in files.

**Derivation rule**: `Human Onboarding Guide.md` and `AI Onboarding Procedure.md` derive from this document and cite its stage numbers. The three stage lists must match exactly (validated).

## State model

State is split across two files (DEC-014):

- **`80 User/onboarding-progress.yaml`** — stages, status, created files, validation results. Hosted-safe: `internal` / `ai_use: allowed`. This is what any runtime reads to resume.
- **`80 User/onboarding-answers.yaml`** — the user's answers, `private` / `ai_use: allowed`. There is no field-level secrecy inside this file (DEC-026): anything the user is not comfortable exposing to their AI runtime should simply be skipped — skips are recorded as `prefer-not-to-say` and can be revisited anytime. The vault filters whole records, not lines; what enters the vault is the user's choice.

Progress schema (`onboarding-progress.yaml`):

```yaml
onboarding:
  session_id:            # e.g. onboard-2026-07-10
  spec_version: 1.10.0       # this document's own `version:` — bump both together
  status: not-started | in-progress | complete
  current_stage: 1-8
  stages:                # per stage: {status: pending|in-progress|complete|deferred, completed_at, notes}
  consent:               # stage-1 outcomes
  created_files: []      # every file onboarding creates
  validation_results: {} # retrieval_test, safe_write_test
  unresolved: []         # open questions to revisit
  resume_instructions:   # one sentence: what happens next
```

Any capable runtime resumes by reading the progress file, confirming the last completed stage with the user, and continuing. Interruption at any point loses nothing.

## The eight stages

### Stage 1 — Orientation and consent
**Connection precondition (first action).** Before anything else, prove the runtime can actually read *and* write this vault: have it report the token from `CONNECT-CHECK.md` (read proof), then write and remove a scratch file under `System/Logs/` that the user confirms appears in Obsidian (write proof). If the write fails, the runtime is operating on an uploaded copy or a read-only mirror — stop and send the user to `System/Onboarding/Connect Your AI.md` (operator-vs-read-only tiers); onboarding writes to `80 User/` from this stage on and cannot proceed without write access.
Explain in plain terms: what the system is (their knowledge + rules + tools in one portable folder), what it is not (a cloud service; a mind-reader; irreversible), what the AI may do (preflighted writes) and may never do (protected objects; deletion without approval), the kill switch, and where everything lives. Give the one-line framing: a second brain stores what you know; this stores what you know, how it connects, and how the work gets done on it. Then route the documentation by depth rather than handing over a list: the **Get Started** set (Product Overview, Quick Start, Human User Manual) is the path; **How the System Works** is there when they want to understand it; the reference and architecture docs are there when they want to extend it. Reading is offered, never required, and no stage waits on it. Obtain explicit consent to proceed and to store answers in `80 User/`.
Confirm `system.instance_role` in `SYSTEM-MANIFEST.yaml` is `personal-instance` — on a fresh copy the user says so and the AI flips it (the manifest is protected, so this needs their explicit instruction; DEC-025).
**Output**: consent recorded in state; instance_role confirmed. **Validation**: user can name the kill switch location.

### Stage 2 — Privacy and boundaries *(precedes all data collection)*
Establish: default classification for new content; work/personal domain handling; whether a hosted model is in use (drives local-only guidance); topics that are off-limits entirely; people whose information deserves extra care.
**The storage question is asked separately from the sensitivity question (DEC-092).** "Should compliant AI retrieval exclude this?" and "must this never leave this machine — no cloud sync, no hosted backup?" are different questions with different fields: the first is `classification`/`ai_use`; the second is `sync: local-only` (or a `Local Only/` folder), which must be backed by a `.gitignore` rule — `aios validate` cross-checks the promise both ways. Never answer the storage question with `classification: restricted`: that removes content from compliant retrieval but is not a physical barrier against a runtime with native file access. Explain that direct-file mode is compliance, not confinement, and keep material the runtime must not technically access outside its filesystem reach.
**Output**: `80 User/privacy-rules.md` (the personal privacy defaults; protected object). **Validation**: rules file exists; user confirms defaults read back to them, including where never-leaves-this-machine content will live.

### Stage 3 — Identity, roles, and domains
Collect: name/handle; the roles that matter (professional and personal, e.g. "product marketer, parent, researcher"); active domains; preferred terminology where it differs from system defaults.
**Output**: `80 User/profile.md` (entity-like profile with roles and domains). **Validation**: profile validates; no employer-confidential detail collected.

### Stage 4 — Goals, expected uses, and information inventory
Collect: what they want the system to do first (3–5 concrete recurring jobs); what they repeatedly re-explain to AI today; where their existing information lives (folders, apps, notes) — an inventory, not an import.

**Workstyle block (v1.1.0)** — when the inventory reveals a prior note system (an existing vault, a folder method, a notes app, or a method in their head), capture how the user already works. **Observe first, confirm second**:
1. **Consent gate** (one question, mandatory before any scan): may the AI read through their existing notes to learn how they organize them — local, read-only? Declined, or nothing to scan → step 4 only.
2. **Scan read-only**: folder tree and naming patterns; tag census; daily-note pattern; editor config if present (daily-note settings, template folders, installed plugins — plugin dependencies mean their structure is load-bearing). The corpus is never modified.
3. **Draft, don't interrogate**: write a draft `80 User/workstyle.md` from `System/Templates/workstyle.md` and present it for correction — people correct a draft far better than they answer a questionnaire.
4. **Ask only what inspection cannot know** (this list is also the full fallback interview when there is no corpus or no consent): what they call things and how they group them; which tags matter and what each means; rituals never to disturb; anything mechanical that depends on names, paths, or metadata keys; the binding `keep` list — scan candidates stay proposals until the user confirms each one; and the coexistence posture: `gradual` (default) | `side-by-side` | `full-adoption-later`.

**Where the work itself goes (v1.8.0).** The first jobs the user just named are the first things they will want to *act* on, so name the place while they are looking at them: the root **`To-Do.md`** is the one routed home for work items — *"add that to my list"* routes there (`manage-todo`), every item carries what it is, why it matters, what it blocks, and a path that resolves it, and the file is re-read on every load so items cannot rot unseen. **Offer once** to capture one named job as a first item; a decline is fine and nothing is seeded silently. This is orientation, not configuration — the file already exists in the vault.

Rules: skipping the block means "no prior system" and the product behaves exactly as it does today; deleting `80 User/workstyle.md` restores that behavior at any time (the feature is purely additive). Migrating their existing corpus may be suggested once, here, and never again unprompted — the concrete paths are `aios okf-import` (a bundle in the Open Knowledge Format) or `aios import` for a full external vault, each plan-authored and reversible, and both land material as draft evidence for the ingest pipeline, never straight into knowledge.
**Output**: `80 User/goals-and-uses.md`; inventory list appended to it; `80 User/workstyle.md` when a prior system exists; a first `To-Do.md` item only if the user accepted the offer. **Validation**: at least one concrete first job named; the user can say where a task they mention will end up; if a workstyle map was created, it passes validate and the user has explicitly confirmed its `keep` list.

### Stage 5 — Structure and terminology configuration
Propose (never impose) personalization within approved bounds: which note subtypes they'll actually use; any renamed vocabulary (`x_` custom values if needed); review-cadence defaults (aggressive/relaxed). **Core schemas, folders, and governance are not personalized** — extensions come later via the Extension Builder.

**Voice and authoring standards (v1.7.0).** The Task Router already loads two user-owned standards files whenever they exist (`load_if_present`: `80 User/voice.md` per DEC-036, `80 User/authoring.md` per DEC-063) — but until now onboarding never asked, so a user who *had* standards got the shipped defaults anyway (exactly the silent-drift failure DEC-063 recorded: a standard nobody wires in is a standard nobody follows). Ask two questions, both skippable:
1. **Voice** — do they have rules for how their outward writing should sound (a voice guide, brand rules, "write like me" notes)?
2. **Authoring** — do they have a standard for how knowledge notes should be built (structure, depth, citation practice, when a claim needs a counterargument)?

If **yes** to either: write the corresponding file — the rules inline when they are short, or a **one-line pointer** to the canonical document when the standard lives elsewhere. If **no**: say plainly that the shipped defaults apply — `safe-write`'s generic knowledge-note doctrine for notes, and no voice constraint for drafting — and that creating either file later wires it in with no other change needed.

**Pointer discipline** (canonical here; the same rule governs `80 User/handoff.md`, DEC-085). If the real standard lives in a longer document, the file in `80 User/` points at it in one line and holds no rules of its own. **One canonical home per standard; every other location is a pointer. Two copies of a rule become two different rules** — and they diverge silently, because both keep looking correct.

**Why the ask exists at all.** A standard that exists but is not wired to a route never loads, so every write is authored against the model's recollection of it rather than the thing itself — and the drift is invisible, because the output still reads well. This happened in a live instance on 2026-07-14: an active authoring standard sat unread for four days because no route referenced it. Hence the questions here, and hence the pointer rather than the copy. **A rule the runtime never sees is not a rule.**
**Output**: configuration recorded in profile; approved vocabulary additions written to **`80 User/vocabulary-extensions.yaml`** (user-owned; merged read-only at validation — the protected `System/Schemas/vocabularies.yaml` is never modified by onboarding; M-08/DEC-018 boundary); `80 User/voice.md` and/or `80 User/authoring.md` when the user has standards. **Validation**: `aios validate` green after changes.

### Stage 6 — First real content: see the system work
Import 3–10 real items (documents, a meeting transcript, a few notes) through `00 Inbox/` using `ingest-and-connect`, with the runtime narrating what happens to each: classified, filed, connected to existing notes, origin recorded. If an item is an AI chat export or other conversation, the narration includes attribution: the voice split measured and recorded (`aios measure`), the user's claims extracted from the user's own turns, and any assistant-originated idea attributed or dropped — never filed as the user's (`ingest-and-connect` step 3a). The purpose is demonstration through real use — the user watches the capture→process→connect pipeline run on their own material. If the user volunteers context that isn't in any document, capture it via the spoken-context path of `ingest-and-connect` (offered once, never pressed — tacit capture is an everyday feature, not an onboarding hurdle).
**Output**: promoted notes with provenance; extracted decisions if the sample contains any. **Validation**: all created notes pass validate + links; every claim cites a source; user confirms they understood what happened to at least one item.

### Stage 7 — Retrieval test + safe-write demonstration
**Retrieval**: user asks three real questions answerable from the sample; the runtime must retrieve the right notes, cite them, and abstain where the vault lacks evidence. **Safe write**: user requests one small change; the runtime demonstrates the full loop — preflight, smallest change, validation (plus a journal entry when the change is consequential) — narrated so the user sees each step.
**Output**: both results recorded in state. **Validation**: user confirms the answers were grounded and the write behavior was visible and correct.

### Stage 8 — Maintenance preferences + completion
Set: weekly maintenance day; how much review they want surfaced (minimal / standard); what happens to onboarding answers (keep / prune sensitive ones).

**Freshness (awareness only).** Tell the user their knowledge now keeps itself honest: change a note and everything connected is listed until each effect is judged; promoted knowledge carries a review date suited to its type; recurring routines report when they've stalled. All of it surfaces in the weekly maintenance pass they are choosing a day for, everything they wrote before today is grandfathered, and nothing is ever rewritten without their approval. No setup required — it activates at the first `aios generate`.

**Backup setup (offer, do not force).** Before completion, help the user protect what they just built. Present `System/Documentation/Backup and Recovery Options.md` — the full menu (GitHub private remote, obsidian-git auto-push, encrypted external drives, built-in zip snapshots, cloud-synced folder, whole-disk backup) with its honest tradeoffs — and let the user **choose**; never prescribe one. Explain the two failure modes it guards (a bad change vs. a dead machine) and the one hard rule (sensitive content stays off any cloud). Offer to help set up the chosen option now (typically connecting a private GitHub remote); the user may pick one, several, or defer. Record the choice in the completion report. Tell the user protection stays **visible** afterwards: every copy is recorded in the `80 User/LAST-BACKUP.txt` marker — written automatically by `System/Scripts/backup-clone.sh`, or by one command after a manual copy (given verbatim in the options doc) — and `aios health` thereafter reports any content that exists only on this machine alongside the last *recorded* backup date (a finding, never an error; no marker means "never", and the report words a marker as evidence of that run only). Offer to run the first backup now if the chosen option is the clone script. **Output**: backup choice recorded (or deferred). **Validation**: the user can name where an off-machine copy of their vault lives, or has explicitly deferred.

**Decision review (offer, do not force).** Before completion, present `System/Governance/Active Decisions.md` — the standing decisions that determine how this vault behaves — so the user inherits nothing silently. Group them into **user-tunable** (privacy and sync boundaries, retrieval and review cadence, vocabulary and note kinds, voice, maintenance) and **structural invariants** (marked as such: the generic-master/personal-copy split, the privacy axes, checkpoint and journal rules, and anything a protected object depends on — changing one of these is a system change, not an onboarding toggle). Walk the user through the tunable set one at a time; for each they keep or amend. Every amendment is recorded as a **new dated decision that supersedes the prior one** (never a silent edit) and is journaled per the change-journal rule. **Amendments are written to the top-level `Decisions/` folder via `record-decision` (v1.8.0)** — the user's own decisions space, where "let's go with X" routes from here on, ids are dated slugs and no record ever claims a number. `System/Governance/Active Decisions.md` is the *product's* register and is overwritten by product updates: it is read here, cross-referenced, and never written to. Say this plainly while the user is looking at both, so the boundary is learned once. The user may amend one, several, none, or defer the whole review — it can be re-run at any time by asking, and re-onboarding surfaces it again. The point is that governance is visible and owned from day one.

**Method Kit (offer, do not force).** Offer the optional Method Kit module — an extended (~45 min) interview that turns how the user actually works into their own operating method: a personal rulebook plus skills any AI follows (the `method-kit` capability). Present it as optional and separable from core setup — do it now, defer it, or decline. If not completed, record it in the completion report's `unresolved` list so re-onboarding re-surfaces it; onboarding progress is saved throughout, so the user can return to it anytime. Skipping it changes nothing about the working system.

**Staying current (awareness).** Tell the user how the OS itself updates: when a newer product release ships, `aios upgrade` brings their `System/` current in one command — notes and customizations untouched, conflicts never merged silently (see `System/Documentation/Upgrading.md`). Pair it with the backup beat above: a checkpoint before upgrading turns a bad update into just another reversible change. Nothing to do now; this beat is awareness only. **Output**: none. **Validation**: none — informational.

**Add-ons (awareness, optional).** Let the user know their OS is extensible with add-on packs — new capabilities they can install anytime by dropping a pack's ZIP in the OS root (see `System/Documentation/Add-Ons and Packs.md`). Their OS already ships with one pack installed — `obsidian-bases`, the first third-party pack, present in `Packs/` as a working example. No *further* pack is installed during onboarding; this beat is awareness only, so the user knows a pack is already working, that the path exists, and where new packs come from (the free-updates newsletter). **Output**: none. **Validation**: none — informational.

Produce the **completion report**: what was configured, what was created, what remains open (`unresolved`), which decisions were reviewed or amended, the backup choice, how to resume or re-onboard later (role change, new runtime, migration).
**Output**: `80 User/onboarding-report.md`; state `status: complete`. **Validation**: `aios health` green; report lists every created file.

## Question style rules

One question at a time · plain language · every question skippable ("prefer not to say" is stored as such) · never collect employer-confidential material · never ask for secrets · voice answers are welcome everywhere.

## Re-onboarding triggers

Major role change · migration to a new machine or runtime · vault-profile major version bump · user request. Re-onboarding reuses this spec, pre-filled from existing state, touching only stages that changed.
