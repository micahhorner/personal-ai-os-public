---
id: doc-portable-vault-profile
type: system-doc
file_class: canonical
authority: canonical
canonical_for: file-format-and-naming-rules
version: 1.1.0
created: 2026-07-10
updated: 2026-08-09
summary: Normative rules for files, formats, identifiers, links, names, paths, and contained transactional publication. The contract that keeps this vault portable across editors, runtimes, and operating systems.
---

# Portable Vault Profile v1.1.0

This document defines the rules every file in this vault follows. It is the portability contract: any editor, script, or AI runtime that honors these rules can operate the vault. **This profile is valid without Obsidian** — deleting `.obsidian/` loses no meaning.

## 1. Encoding and text format

- **Encoding**: UTF-8, Unicode NFC normalization.
- **Line endings**: LF.
- **Markdown**: CommonMark subset plus pipe tables and YAML frontmatter. No essential meaning may live in formatting, HTML, plugin syntax, or canvas files.
- **YAML frontmatter**: fenced by `---` lines at the top of the file; YAML 1.2; scalar values and flat lists only — no nested maps deeper than one level.
- **Dates**: ISO 8601. Date-only (`2026-07-10`) where time is irrelevant; with UTC offset (`2026-07-10T14:30:00-05:00`) where time matters.

## 2. Stable identifiers (DEC-005)

- Every canonical file carries a frontmatter `id` of the form `<type>-<slug>`:
  - lowercase `a–z`, `0–9`, and hyphens only;
  - type prefix matches the file's `type` field (`note-`, `source-`, `entity-`, `project-`, `decision-`, `procedure-`, `output-`, `working-`, `doc-`, `capability-`, `agent-`, `script-`, `schema-`, `template-`, `workflow-`, `adapter-`, `op-`);
  - date-stamped where natural: `decision-2026-07-10-weekly-webinars`.
- **IDs are immutable once assigned.** Renaming a file never changes its `id`.
- Uniqueness is enforced by `aios.py validate`.
- Filenames are display artifacts; anything that must survive a rename references the `id`, not the path.

## 3. Links (DEC-007)

- Note **bodies** may use either wikilinks (`[[Note Title]]`) or relative Markdown links.
- **Canonical relationships must also appear in frontmatter** as stable IDs (see the Metadata and Relationship Dictionary). Frontmatter is the durable form; body links are for reading and navigation.
- The validator resolves both forms and reports broken targets.
- Wikilink values inside YAML must be quoted: `related: ["[[Some Note]]"]` — but plain IDs are preferred: `related: [note-some-note]`.

## 4. Names and paths

- No two paths may differ only by case (case-insensitive filesystems are assumed).
- Forbidden in file and folder names: `\ / : * ? " < > |`, trailing dots, trailing spaces.
- Keep full paths comfortably under 200 characters (legacy Windows tolerance).
- Scripts and components never hard-code content-folder paths; they resolve them through `System/Registries/folder-registry.yaml`. Renaming a folder is a migration, not a breakage.

## 5. Reserved directories and keys

- **Reserved directories**: `System/`, `80 User/`, `00 Inbox/`, `90 Archive/`.
- **Reserved metadata keys**: exactly those defined in `System/Documentation/Metadata and Relationship Dictionary.md`. Unknown keys fail validation unless prefixed `x_` (the experimentation escape hatch).
- **Controlled vocabularies** live in `System/Schemas/vocabularies.yaml` and nowhere else.

## 6. File classes and authority markings

Every important file is classifiable as one of:

| Class | Meaning | Marking |
|---|---|---|
| `canonical` | authoritative, durable | `file_class: canonical` (default for content notes) |
| `generated` | rebuildable from canonical state | `generated: true` + `generator` + timestamp, or residence in `System/Generated/`; residence in mixed `System/Logs/` is not sufficient |
| `runtime-specific` | used by one adapter | residence in `System/Adapters/` or `.obsidian/` |
| `temporary` | safe to delete after its lifecycle | residence in `00 Inbox/` pre-promotion |
| `example` | demonstration content shipped with the generic core; **never retrievable as user truth** (DEC-018) | `file_class: example` + residence in `System/Tests/examples/` |

Documentation additionally declares `authority: canonical | derived | generated` and, for canonical docs, `canonical_for: <rule-domain>`. Exactly one document owns each rule domain.

## 7. Versions

- `SYSTEM-MANIFEST.yaml` carries `system_version` and `vault_profile_version`.
- Schemas carry `schema_version`; components carry `version`. Semver throughout; a major bump requires a migration (see `System/Governance/Versioning and Migration.md`).

## 8. Import and export

- **Export** = copy the folder. Nothing else is required.
- **Import** = new material enters through `00 Inbox/` and is promoted by the `ingest-and-connect` capability. Bulk imports are staged in the Inbox, never written directly into content folders.

## 9. Exclusions

Never stored in the vault: secrets (API keys, passwords, tokens — reference environment-variable names instead), model weights, Python virtual environments, rebuildable third-party indexes.

## 10. Stated assumptions

- Single user. The mutating CLI protects each declared transaction against path substitution and concurrent changes to the files it has bound: it stages complete candidates, re-proves inputs, and publishes with no-clobber or compare-and-swap semantics. This is **not** a vault-wide multi-writer transaction manager. Unrelated commands, native editor writes, and manual filesystem changes still require coordination; a detected race refuses rather than guesses.
- Obsidian is an optional interface. Git is optional for reading and recovery (DEC-011).

## 11. Cross-platform acceptance

A vault conforms to this profile only if the portability tests in `System/Tests/Portability Test Procedure.md` pass, including: `.obsidian/` removal is lossless; `System/Generated/` deletion is fully rebuildable; the vault validates after being moved to a different path; no case-collision or forbidden-character violations exist.
