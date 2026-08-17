---
id: doc-versioning-and-migration
type: system-doc
file_class: canonical
authority: canonical
canonical_for: versioning-and-migration
version: 1.4.0
created: 2026-07-10
updated: 2026-08-09
summary: How versions work and how structural change happens safely — semver rules, migration format, read-only reviewed product upgrades, and pre-declared migration paths.
---

# Versioning and Migration

Future change is handled through versioned migration, not wishful permanence (Design Principle 25).

## 1. What is versioned

| Thing | Field | Where |
|---|---|---|
| The whole system | `system_version` | SYSTEM-MANIFEST.yaml |
| The portability contract | `vault_profile_version` | SYSTEM-MANIFEST.yaml |
| Each note-class schema | `schema_version` | System/Schemas/*.yaml |
| Each component (capability, agent, workflow, script, template, adapter) | `version` | its contract file |
| Canonical documents | `version` | frontmatter |

Ordinary knowledge notes are **not** semver-versioned; their history is Git/checkpoints and their supersession chain (`supersedes` / `superseded_by`).

## 2. Semver rules

`MAJOR.MINOR.PATCH` — **major**: breaking change, migration required; **minor**: compatible addition; **patch**: correction. Notes record the `schema_version` they were created under. Readers must tolerate one major version back; `aios.py validate` reports version stragglers.

## 3. Migration format

Each migration is a directory `System/Migrations/NNN-short-description/` containing:

- `migration.yaml` — strict and duplicate-key-rejecting: directory-bound id, target authority, canonical source identity, exact SemVer edge, prerequisites, selector, one declarative transform, mandatory full-vault validation, outer exact-recovery contract, idempotency key, and canonical manifest hash.
- `README.md` — human explanation: why, what changes, what to watch for.

Only hash-bound `replace_exact_files` is permitted. Executable scripts and
inferred field-level transforms are prohibited because they cannot prove exact
historical postconditions after a ledger record exists.

## 4. Runner behavior (`aios.py migrate`)

Public `aios migrate` is read-only preview. Direct live-vault apply is refused.
Upgrade is the only apply surface. It resolves one exact direct system edge
before checkpoint creation, then the owned candidate performs strict preflight,
transform, mirror audit, full-vault validation, and durable records.

**Partial failure rule**: stop immediately and discard the isolated candidate;
the upgrade transaction retains the outer checkpoint for live-swap recovery.
Missing/unsafe journals, malformed ledgers, parser ambiguity, symlinks, hash
drift, and failed validation are failures.

The ledger is append-only-by-tool and consistency-checked against manifests,
prerequisite partial order, exact checkpoint shape, ids, and idempotency keys.
It is not externally immutable without a Git or external anchor.

## 4a. Product upgrades (`aios.py upgrade`) — DEC-073/074

A **migration** transforms an instance's own content under a schema change. An **upgrade** is the
other axis: it applies a *new product release's* `System/` into an existing
instance. They compose only inside a structurally proven upgrade candidate
using captured pre-overlay identity and the outer checkpoint.

- **Surface**: `System/`, minus generated or runtime-managed state (`System/Generated/`, `System/Logs/`), the
  canonical journal (`System/Journal/`, DEC-016), and certification records
  (`System/Tests/results/`) — **plus four named root files** the product owns and ships with every
  release: `CLAUDE.md`, `pyproject.toml`, `README.md`, `START-HERE.md` (DEC-097; the list is
  `ROOT_PRODUCT_FILES` in `upgrade.py`, one deliberate call per file, never inferred). Deliberately
  outside it: `LICENSE.md`, `CHANGELOG.md`, `SYSTEM-MANIFEST.yaml` (only `system_version` is
  bumped), `CONNECT-CHECK.md`, the content directories, `80 User/`, `.obsidian/` and `Packs/`.
  **`To-Do.md` and `Decisions/` are seeded additively when an instance lacks them** and are never
  replaced, merged, or removed once they exist — from that moment they are user content.
  `System/Logs/` is excluded because it is live mixed state, not because the whole directory is
  disposable; upgrade preserves its durable freshness history and obligations under DEC-121.
- **Classification** is three-way — base vs release vs instance — where *base* is the file-hash
  record every release ships at `System/.baseline-manifest.json` (**DEC-074**; regenerate on the
  master with `aios upgrade --make-baseline`). Pristine files are replaced; instance-edited files
  are kept; files changed on both sides are **conflicts**, left untouched and reported. Without a
  baseline the command falls back to treating every difference as a conflict — it replaces nothing
  rather than risk a wrong "unchanged" call.
- **The Task Router is never merged** (**DEC-073**): divergence produces a per-row review list. A
  structured overlay (`Task Router.local.yaml`) is the designated fast-follow.
- **Discipline**: public `migrate` is preview-only. Bare `upgrade` is also read-only: it reports the classification and an exact semantic-input review hash without creating a checkpoint or candidate. Apply requires a fresh matching plan and the explicit triple gate `--apply --confirm --review-sha256 <hash>`. Migration execution inherits upgrade's checkpoint, candidate, validation, journal, and loud-failure gates; it never introduces live in-place apply.
- **The version bump is earned, not assumed**: `system_version` advances only when the gates are
  green, no protected path is in conflict, any required exact migration passed, and classification had a real
  baseline. Otherwise the old version stands — an instance must never claim a version it isn't at.
- **Authority**: upgrade writes into protected paths by design. The human approves the exact semantic plan printed by the bare command; `--confirm` without its fresh review hash is insufficient. Nothing else may invoke apply. Final candidate bytes do not exist at review time, so the plan binds the complete semantic inputs and labels that limitation; the transaction journal pins materialized tree identities for recovery.

Procedure and failure modes: `System/Documentation/Upgrading.md`.

## 5. Pre-declared migration paths

These likely future changes have their path defined in advance:

- **Renameable content folder (`10 Projects`, `20 Knowledge`, `30 Sources`, `40 Outputs`) rename/renumber** → update `folder-registry.yaml`; scripts resolve these through the registry (`vaultpaths.rel_folder`), so no script edits are needed; run link validation. The **reserved directories** (`System/`, `80 User/`, `00 Inbox/`, `90 Archive/`, Vault Profile §9) are fixed by contract and are referenced literally by design — they are not renameable.
- **ID grammar change** → applies to newly created IDs only. Existing IDs are immutable, permanently.
- **Status-vocabulary change** → migration provides an old→new value map; validator enforces the new vocabulary afterward.
- **Subtype promotion to full class** (e.g., `note/claim` → `claim`) → new schema + template, migration rewrites `type`/`subtype`, registry and index regeneration.
- **Relationship-type addition** → additive: dictionary entry + schema update; no migration needed. Removal requires a migration mapping old fields.

## 6. Amendment linkage

Changes to frozen architecture documents require a decision-register entry and follow the amendment process in the Canonical Architecture Specification's Amendments section. A migration that implements an amendment references its DEC number.
