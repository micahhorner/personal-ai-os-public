---
id: doc-system-map
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture]
version: 1.1.0
created: 2026-07-10
updated: '2026-08-09'
summary: Where everything lives and how the layers fit together — the orientation diagram for humans and AI.
---

# System Map

## The five layers

```
1. DURABLE PORTABLE CORE           your knowledge (00-90 folders, Decisions/, To-Do.md) + System rules
2. PERSONAL CONFIGURATION          80 User/ — profile, preferences, privacy, onboarding state
   + ADD-ONS                        Packs/ — installed add-ons you own; removable without touching the core (v1.12.0)
3. GOVERNANCE & OPERATIONS         System/ — rules, schemas, operations, scripts, tests
4. ADAPTERS                        System/Adapters/ + CLAUDE.md + .obsidian/  (translate, never own rules; no copies — every runtime reads the masters)
5. GENERATED + RUNTIME STATE       System/Generated/ (disposable) + System/Logs/ (mixed; preserve freshness history/obligations)
```

## Directory purposes

| Path | Layer | What lives there |
|---|---|---|
| `00 Inbox/` | 1 | capture + quarantine (untrusted until promoted) |
| `10 Projects/` `20 Knowledge/` `30 Sources/` `40 Outputs/` | 1 | projects, canonical knowledge (notes, entities, procedures), immutable evidence, deliverables |
| `Decisions/` | 1 | settled choices, one dated record each — a registered content directory since v1.40.0 (DEC-095), top-level so it is as findable as the Inbox; the register in `System/Governance/Active Decisions.md` derives from it |
| `To-Do.md` (root) | 1 | the routed to-do list (DEC-094) — a file, not a folder, deliberately at the root where nothing has to remember it |
| `80 User/` | 2 | the person; removed and rebuilt when re-shipping the generic core |
| `90 Archive/` | 1 | inactive, excluded from default retrieval |
| `System/Architecture/` | 3 | frozen spec, vault profile, principles, this map |
| `System/Governance/` | 3 | change control, privacy, versioning — **protected** |
| `System/Schemas/` + `Templates/` | 3 | what notes are and how they're born — **protected (schemas)** |
| `System/Registries/` | 3 | folder registry (canonical); the component index is generated + disposable in `System/Generated/` (DEC-024) |
| `System/Operations/` | 3 | the 15-operation runtime-neutral contract |
| `System/Capabilities/` `Agents/` `Scripts/` `Workflows/` | 3 | task procedures, roles, deterministic tools, routines |
| `System/Onboarding/` `Documentation/` `Tests/` `Migrations/` | 3 | setup, manuals, fixtures, structural change |
| `System/Adapters/` `Runtime Profiles/` | 4 | per-runtime translation + certified capabilities |
| `System/Generated/` | 5 | disposable views; rebuild as one complete staged tree with `aios generate` |
| `.claude/skills/aios-*` | 5 | separately published tool-owned projections; foreign skills are preserved |
| `System/Logs/` | 5 | mixed runtime state: ordinary reports may be disposable; freshness history and live obligations are not bulk-deletable |

## How things flow

**In**: everything enters via `00 Inbox/` → `ingest-and-connect` (or `safe-write` for direct creation) → canonical folders, with enrichment connecting it to what exists.
**Through**: tasks pull the smallest complete context (`retrieve-context`) filtered by privacy and freshness.
**Out**: deliverables land in `40 Outputs/` with `derived_from` provenance.
**Around**: every write passes preflight; every consequential change is journaled and checkpointed; every generated view is disposable.
