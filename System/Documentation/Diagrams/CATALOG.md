---
id: doc-diagrams-catalog
type: system-doc
file_class: canonical
authority: canonical
canonical_for: diagram-atlas-catalog
version: 1.1.0
created: 2026-07-13
updated: 2026-08-09
summary: "Registry of the diagram atlas: every visual diagram of the product, what it covers, the canonical source it is grounded in, and how to keep it current."
---

# AI OS Diagram Atlas — Catalog

**A documented, comprehensive set of 44 visual diagrams covering how the Personal AI OS product works — every layer, subsystem, capability, workflow, agent, and governance mechanism, plus the user-facing flows of work. Each diagram is a self-contained, theme-aware SVG grounded in a specific canonical source doc. This catalog records what exists, what each covers, what it is grounded in, and how to keep it current.**

- **Product covered:** Personal AI OS — this generic-master repository — version-independent; the manifest owns the current version
- **Built / expanded:** 2026-07-13 · counts reconciled 2026-07-16
- **Count:** 44 diagrams — 23 concept/system (01–23), 12 user-flow how-to (24–35), automations layer (36), portability contract (37), method-kit capability flow (38), add-on pack lifecycle (39), session-handoff loop (40), manage-todo loop (41), start-project flow (42), record-decision flow (43), adversary pre-build gate (44)
- **Format:** SVG (680px canvas, light/dark adaptive) in `svg/`, also rendered inline as chat widgets
- **Location:** `System/Documentation/Diagrams/`
- **Scope:** the AI OS core only. The PMM Engine vertical is a separate product and gets its own atlas; it is not documented here.

### The how-to layer (24–44)

Diagrams 01–23 explain how the *system* works (documented in detail below). Diagrams 24–44 are the *user-facing* layer, added with the how-to documentation:

- **24** Flows of Work (map) · **25–35** the eleven user-flow walkthroughs (Capture & File, Get Set Up, Ask, Record a Decision, Add Spoken Context, Produce, Weekly Maintenance, Bring Your Own Method, Grow, Review, Stop & Recover) — each drawn from the user's perspective (YOU DO → BEHIND THE SCENES → YOU GET) and paired with a walkthrough doc in `System/Documentation/Flows/`.
- **36** Automations & Checks — the always-on layer, grouped by when each fires (paired with `Flows/Automations Reference.md`).
- **37** Portable Vault Profile — the portability contract and what it guarantees (no lock-in).

`aios doc-check` enforces coverage for both components and every `Flows/*.md` walkthrough. Registrations live in `coverage.yaml`; descriptions in `diagram-metadata.yaml`.

---

## Completeness statement

Every functional element of the product surface is represented by at least one diagram. The set was assembled by sweeping the full `System/` tree (architecture, governance, operations, capabilities, agents, workflows, schemas, adapters, runtime, onboarding, tests, migrations, generated state, scripts) and mapping each area to a diagram. The coverage map below is the audit trail. The CLI-surface diagram (22) now draws **all 32 subcommands** — `upgrade`, the `okf-export`/`okf-import` round-trip, `measure`, `pack`, `resolve`, `ripple`, `dedupe-batch` and the five documentation gates included — so the coverage claim made here is one anyone can check by opening the file. It had previously named those commands as covered while the artwork drew thirteen and none of the four; promoting the OKF round-trip and the upgrade lifecycle to their own *flow* diagrams remains a tracked follow-up.

Three low-visual-value areas remain documented in prose only (not diagrammed), by choice: the 21-category full-preflight appendix taxonomy, the complete reserved-metadata-key list, and controlled vocabularies. Flag any of these if a diagram would help.

---

## Coverage map — product surface → diagram

| Product surface area | Source of record | Diagram(s) |
|---|---|---|
| Five architectural layers | `Architecture/System Map.md` | 01 |
| Directory taxonomy (00–90 + System) | `Architecture/System Map.md` | 01, 03 |
| Data flow (in / through / out) | `Architecture/System Map.md` | 02 |
| Safe-write governance loop | `Governance/Change Control and Preflight.md` | 02, 05 |
| Kill switch | `SYSTEM-MANIFEST.yaml` · Change Control §8 | 02, 05, 07, 11 |
| The 15 stable operations | `Operations/operations.yaml` | 04 |
| Approval modes | Change Control §3 · operations.yaml | 04, 05 |
| Risk tiers & proportional preflight | Change Control §2 | 05 |
| Four-outcome invariant | Change Control §6 | 05, 14 |
| Protected objects | Change Control §4 · manifest | 05, 12 |
| The three write lanes | `Runtime/Runtime Kernel.md` §2 | 12 |
| Privacy fields & routing | `Governance/Privacy and Boundaries.md` | 06 |
| Runtime kernel + task router (progressive disclosure) | `Runtime/Runtime Kernel.md` · `Runtime/Task Router.yaml` | 11 |
| Runtimes & adapters | `Adapters/**` · Runtime Profiles | 03, 19 |
| Adapter operation mapping | `Adapters/Claude/operation-mapping.yaml` | 19 |
| Autonomy levels L0–L4 | `Documentation/AI Operator Manual.md` · Architecture Spec §33 | 07 |
| Certification battery (fixtures → levels) | `Tests/Certification Battery.md` | 20 |
| Capabilities / agents / workflows inventory | `Generated/component-index.json` | 03 |
| Agent model (roles, guardrails, recommend-only) | `Agents/*/AGENT.md` | 13 |
| safe-write capability | `Capabilities/safe-write/SKILL.md` | 15 |
| retrieve-context capability | `Capabilities/retrieve-context/SKILL.md` | 16 |
| ingest-and-connect + nine effects | `Capabilities/ingest-and-connect/SKILL.md` · `Workflows/inbox-processing.md` | 14 |
| maintain-vault / weekly maintenance | `Workflows/weekly-maintenance.md` · `Capabilities/maintain-vault/SKILL.md` | 17 |
| recover capability + backup | `Capabilities/recover/SKILL.md` · `Documentation/Maintenance and Recovery Guide.md` | 21 |
| Note classes (8 schemas) | `Schemas/**` | 08 |
| Component lifecycle (draft→active) | `Capabilities/build-extension/SKILL.md` · operations.yaml | 08 |
| Metadata & relationship model | `Documentation/Metadata and Relationship Dictionary.md` | 18 |
| Onboarding (8 stages) | `Onboarding/Onboarding Specification.md` | 09 |
| Method Kit (capability + optional onboarding module) | `Capabilities/method-kit/SKILL.md` · `Onboarding/Onboarding Specification.md` | 38, 09 |
| Session handoff (close + resume) | `Capabilities/session-handoff/SKILL.md` | 40 |
| To-do routing (item contract + rot detector) | `Capabilities/manage-todo/SKILL.md` · `To-Do.md` | 41 |
| Project start (generic floor) | `Capabilities/start-project/SKILL.md` | 42 |
| Decision recording (the routed decisions space) | `Capabilities/record-decision/SKILL.md` · `Decisions/_ABOUT.md` | 43, 28 |
| Adversary pre-build gate (red-team a plan) | `Capabilities/adversary/SKILL.md` · `Capabilities/build-extension/SKILL.md` | 44, 08 |
| Import & migration | `Capabilities/import-vault/SKILL.md` · `Migrations/README.md` | 10 |
| Versioning & semver | `Governance/Versioning and Migration.md` | 23 |
| CLI surface (aios.py) | `Scripts/aios.py` · adapter mapping | 22 |
| Generated state (disposable, rebuildable) | `Generated/**` · System Map | 22 |

---

## The diagrams, by theme

### Foundations — orientation
- **01 — Five-Layer Architecture** (`svg/01-five-layer-architecture.svg`) — durable core → config → governance → adapters → generated and mixed runtime state; the "AI is a guest" portability claim. *Grounded in:* System Map, Product Overview.
- **02 — Data Flow & Governance** (`svg/02-data-flow-governance.svg`) — inbox→ingest→canonical→outputs spine + the governance lane every write passes through. *Grounded in:* System Map, Change Control.
- **03 — Component & Operations Map** (`svg/03-component-operations-map.svg`) — the hourglass: runtimes → adapters → 15-op waist → capabilities/agents/workflows → vault. *Grounded in:* component-index.json, operations.yaml, Architecture Spec.

### Governance & safety
- **04 — Operations Matrix** (`svg/04-operations-matrix.svg`) — all 15 operations by kind and approval mode. *Grounded in:* operations.yaml, Change Control §3.
- **05 — Change-Control Tiers** (`svg/05-change-control-tiers.svg`) — Low/Medium/High/Critical risk tiers, depth, approval; four-outcome invariant; protected objects. *Grounded in:* Change Control and Preflight.
- **06 — Privacy Routing Gate** (`svg/06-privacy-routing-gate.svg`) — classification/domain/ai_use → filtered-result inclusion/exclusion before ranking, with the direct-file compliance-not-confinement limit. *Grounded in:* Privacy and Boundaries.
- **12 — The Three Write Lanes** (`svg/12-three-write-lanes.svg`) — ordinary / consequential / system; pick the heavier lane when unsure. *Grounded in:* Runtime Kernel §2.

### Runtime & execution
- **11 — Runtime Kernel & Task Router** (`svg/11-runtime-kernel-router.svg`) — progressive disclosure: always-on kernel + intent routing across normal/maintenance/developer/onboarding modes. *Grounded in:* Runtime Kernel, Task Router.
- **07 — Autonomy Ladder** (`svg/07-autonomy-ladder.svg`) — L0–L4, shipped-default vs. earned-by-certification; kill-switch override. *Grounded in:* AI Operator Manual, Architecture Spec §33, Certification Battery.
- **19 — Adapter Translation** (`svg/19-adapter-translation.svg`) — the canonical operation contract mapped to a runtime's native abilities. *Grounded in:* Claude operation-mapping.yaml.
- **20 — Certification Battery** (`svg/20-certification-battery.svg`) — which fixtures certify which autonomy level; failed fixture caps the runtime. *Grounded in:* Certification Battery.

### Capabilities & workflows
- **14 — Inbox → Canonical Pipeline** (`svg/14-inbox-canonical-pipeline.svg`) — ingest-and-connect: dedupe→preserve→extract→triage (delta register, four outcome families)→build-out→connect, the nine effects. *Grounded in:* ingest-and-connect, inbox-processing.
- **15 — safe-write Flow** (`svg/15-safe-write-flow.svg`) — resolve-first, then create vs. change; supersession; always validate. *Grounded in:* safe-write.
- **16 — retrieve-context Flow** (`svg/16-retrieve-context-flow.svg`) — filter→orient via index→resolve→freshness→assemble→cite/abstain. *Grounded in:* retrieve-context.
- **17 — Weekly Maintenance Workflow** (`svg/17-weekly-maintenance-workflow.svg`) — the 7-step steward pass: health→inbox→freshness→drift→generate→checkpoint→review queue. *Grounded in:* weekly-maintenance, maintain-vault.

### Agents
- **13 — Agent Model** (`svg/13-agent-model.svg`) — steward, onboarding-guide, extension-builder: roles, capabilities used, guardrails; shared no-self-modification contract. *Grounded in:* the three AGENT.md contracts.

### Knowledge & data model
- **08 — Knowledge Model & Lifecycle** (`svg/08-knowledge-model-lifecycle.svg`) — the eight note classes (note · entity · decision · procedure · source · project · output · `working` — the last being project material: plans · logs · captures · drafts · scratch, DEC-096, project layer only and outside default retrieval), plus the ninth schema `component`, which is a contract for capabilities/agents/workflows and not a record class at all — plus the design→scaffold→validate→register lifecycle; guardrails. *Grounded in:* Schemas, build-extension.
- **18 — Metadata & Relationship Model** (`svg/18-metadata-relationship-model.svg`) — 9 relationship types, direction rule, provenance/epistemic fields, generated reverse views. *Grounded in:* Metadata and Relationship Dictionary.

### Lifecycle journeys
- **09 — Onboarding Journey** (`svg/09-onboarding-journey.svg`) — the 8 guided stages, privacy before data. *Grounded in:* Onboarding Specification.
- **10 — Import & Migration Flow** (`svg/10-import-migration-flow.svg`) — the shared dry-run→approve→apply(checkpoint)→validate rhythm; verbatim vs. mapped. *Grounded in:* import-vault, Migrations/README.

### Operations, recovery & change
- **21 — Recovery & Backup** (`svg/21-recovery-backup.svg`) — recover flow (stabilize→diagnose→restore→verify); two restore paths; checkpoint/zip. *Grounded in:* recover, Maintenance and Recovery Guide.
- **22 — Tooling & Generated State** (`svg/22-tooling-generated-state.svg`) — aios.py CLI surface + disposable artifacts + three separately atomic publication domains; mixed Logs state stays outside the disposal promise. *Grounded in:* Scripts/aios.py, Generated/**.
- **23 — Versioning & Migration** (`svg/23-versioning-migration.svg`) — what's semver'd, major/minor/patch, notes-vs-schema, amendment linkage. *Grounded in:* Versioning and Migration.

### User flows & how-to layer (24–38)

- **24 — Flows of Work (map)** (`svg/24-flows-of-work-map.svg`) — The eleven user flows grouped by when you use them; the map to every walkthrough.
- **25 — Capture & File (flow)** (`svg/25-flow-capture-and-file.svg`) — Capture & file, user's view: drop a file, say process my inbox, get connected cited notes.
- **26 — Get Set Up (flow)** (`svg/26-flow-get-set-up.svg`) — Get set up (onboarding), user's view: open your AI; it sets privacy first and makes the folder yours.
- **27 — Ask & Get Answers (flow)** (`svg/27-flow-ask-and-get-answers.svg`) — Ask & get cited answers: ask plainly; privacy-filtered retrieval returns a cited answer or honest emptiness.
- **28 — Record a Decision (flow)** (`svg/28-flow-record-a-decision.svg`) — Record a decision: state it; one dated Decision record is filed and linked, resurfacing at revisit time.
- **29 — Add Spoken Context (flow)** (`svg/29-flow-add-spoken-context.svg`) — Add spoken/tacit context: tell it something unwritten; captured as a source labeled as your recollection.
- **30 — Produce a Deliverable (flow)** (`svg/30-flow-produce-a-deliverable.svg`) — Produce a deliverable: ask it to draft from what's known; output lands in Outputs with lineage, awaiting approval.
- **31 — Weekly Maintenance (flow)** (`svg/31-flow-weekly-maintenance.svg`) — Weekly maintenance: say run maintenance; health, inbox reported (drained only on a separate yes), freshness triage, rebuild, checkpoint, short review list.
- **32 — Bring Your Own Method (flow)** (`svg/32-flow-bring-your-own-method.svg`) — Bring your own method & notes: it learns your organizing method and imports your existing notes safely.
- **33 — Grow the System (flow)** (`svg/33-flow-grow-the-system.svg`) — Grow the system: tell the Extension Builder a goal; it designs, tests, documents, and activates a new component.
- **34 — Review the AI's Work (flow)** (`svg/34-flow-review-the-ai-work.svg`) — Review the AI's work: the journal, stale flags, and approvals give you a verifiable audit trail.
- **35 — Stop & Recover (flow)** (`svg/35-flow-stop-and-recover.svg`) — Stop & recover: one line halts all AI writes; the journal and checkpoints restore any earlier state.
- **36 — Automations Always-On Layer** (`svg/36-automations-always-on-layer.svg`) — The always-on layer: every automatic check/automation grouped by when it fires (write, ask, ingest, weekly, on-demand certification, standing guards).
- **37 — Portable Vault Profile** (`svg/37-portable-vault-profile.svg`) — The portability contract: the rules every file follows (plain Markdown, stable immutable IDs, cross-platform-safe names, file classes, folder-registry indirection) and what they guarantee — operable by any editor or AI, runs on any OS, export = copy the folder, no vendor lock-in.
- **38 — method-kit Flow** (`svg/38-method-kit-flow.svg`) — The six-step method-kit procedure: interview the user across eight sections with evidence graded E1–E4, resolve the eleven personalization dials, generate their operating-method pack into their user layer, wire pack-skills to follow it, have them ratify it, and record it as theirs to keep.
- **39 — Add-On Pack Lifecycle** (`svg/39-addon-pack-lifecycle.svg`) — The manage-packs lifecycle: exact archive review and hash-bound apply, staged/live checks, activation receipt, index publication, and transactional archive/quarantine removal with explicit purge.
- **40 — Session Handoff Loop** (`svg/40-session-handoff-loop.svg`) — The session-handoff close/resume loop: journal sweep, checkpoint + validate, an honest stopping-point record; then the cold resume — record read first, claims re-verified against live state, frame restated before any write.
- **41 — manage-todo Loop** (`svg/41-manage-todo-loop.svg`) — The routed to-do loop: an add drafts the four-part item (what · why · blocks · resolving path) from context, asks at most one clarifying question, link-checks the paths it touches (dead ones flagged in place — the rot detector), then writes and validates. Done items move to `## Done`, dated; order is priority.
- **42 — start-project Flow** (`svg/42-start-project-flow.svg`) — The generic project floor: resolve the name first (resume, don't duplicate), folder under `10 Projects/`, schema-valid note from the template, register + validate, state where actions go. Plans, handoffs, and gates stay in the user's installed method pack — consulted by mention, never rebuilt.
- **43 — record-decision Flow** (`svg/43-record-decision-flow.svg`) — The routed decisions space: a settled choice (the bar: closes alternatives or changes scope) becomes one dated record in the top-level `Decisions/` folder — resolve first (supersede, never duplicate), the record drafted from context with one clarifying question max, a dated slug id and never a claimed number; the generated register (newest first, by project) derives ordering, so parallel decisions cannot collide.
- **44 — Adversary Pre-Build Gate** (`svg/44-adversary-gate.svg`) — The hostile read that happens before the build spends the money: on demand ("red-team this") or as `build-extension` step 3b on any High-tier build, before a single file exists. Steelman first, then five separate reads — load-bearing assumptions with how we'd know they're false, unnamed failure modes, the cheaper version, scope traps, and the plan-killer named. Every finding cites its line and states its falsifier; the report must name one thing the plan gets right; the verdict (proceed · proceed-with-amendments · redesign) advises and never blocks; the report is filed as working material and a skipped gate is recorded, never silent.

---

## Regeneration & maintenance

Hand-authored SVGs, not script-generated. When the product changes, update the affected diagram and this catalog together.

- **Highest drift risk** (update the diagram if the source doc's content changes): operations.yaml (04), Change Control (05, 12), Privacy (06), Runtime Kernel/Task Router (11, 12), autonomy levels (07, 20), component-index (03), the capability procedures (14–17), agent contracts (13), metadata dictionary (18), operation-mapping (19), versioning (23).
- **Design system:** each SVG uses the widget host's CSS-variable ramp classes (`c-blue`, `c-teal`, `c-amber`, `c-green`, `c-red`, `c-purple`, `c-gray`) and text classes (`t`/`ts`/`th`) so they render in both light and dark mode. Canvas is `viewBox="0 0 680 H"`; keep width at 680.
- **To re-render inline:** pass the SVG source to the visualization widget tool.

## Status

| # | Diagram | Theme | Status |
|---|---|---|---|
| 01 | Five-Layer Architecture | Foundations | complete |
| 02 | Data Flow & Governance | Foundations | complete |
| 03 | Component & Operations Map | Foundations | complete |
| 04 | Operations Matrix | Governance & safety | complete |
| 05 | Change-Control Tiers | Governance & safety | complete |
| 06 | Privacy Routing Gate | Governance & safety | complete |
| 07 | Autonomy Ladder | Runtime & execution | complete |
| 08 | Knowledge Model & Lifecycle | Knowledge & data model | complete |
| 09 | Onboarding Journey | Lifecycle journeys | complete |
| 10 | Import & Migration Flow | Lifecycle journeys | complete |
| 11 | Runtime Kernel & Task Router | Runtime & execution | complete |
| 12 | The Three Write Lanes | Governance & safety | complete |
| 13 | Agent Model | Agents | complete |
| 14 | Inbox → Canonical Pipeline | Capabilities & workflows | complete |
| 15 | safe-write Flow | Capabilities & workflows | complete |
| 16 | retrieve-context Flow | Capabilities & workflows | complete |
| 17 | Weekly Maintenance Workflow | Capabilities & workflows | complete |
| 18 | Metadata & Relationship Model | Knowledge & data model | complete |
| 19 | Adapter Translation | Runtime & execution | complete |
| 20 | Certification Battery | Runtime & execution | complete |
| 21 | Recovery & Backup | Operations, recovery & change | complete |
| 22 | Tooling & Generated State | Operations, recovery & change | complete |
| 23 | Versioning & Migration | Operations, recovery & change | complete |
| 24 | Flows of Work (map) | User flows | complete |
| 25 | Capture & File (flow) | User flows | complete |
| 26 | Get Set Up (flow) | User flows | complete |
| 27 | Ask & Get Answers (flow) | User flows | complete |
| 28 | Record a Decision (flow) | User flows | complete |
| 29 | Add Spoken Context (flow) | User flows | complete |
| 30 | Produce a Deliverable (flow) | User flows | complete |
| 31 | Weekly Maintenance (flow) | User flows | complete |
| 32 | Bring Your Own Method (flow) | User flows | complete |
| 33 | Grow the System (flow) | User flows | complete |
| 34 | Review the AI's Work (flow) | User flows | complete |
| 35 | Stop & Recover (flow) | User flows | complete |
| 36 | Automations Always-On Layer | User flows | complete |
| 37 | Portable Vault Profile | Runtime & execution | complete |
| 38 | method-kit Flow | Capabilities & workflows | complete |
| 39 | Add-On Pack Lifecycle | Capabilities & workflows | complete |
| 40 | Session Handoff Loop | Capabilities & workflows | complete |
| 41 | manage-todo Loop | Capabilities & workflows | complete |
| 42 | start-project Flow | Capabilities & workflows | complete |
| 43 | record-decision Flow | Capabilities & workflows | complete |
| 44 | Adversary Pre-Build Gate | Capabilities & workflows | complete |
