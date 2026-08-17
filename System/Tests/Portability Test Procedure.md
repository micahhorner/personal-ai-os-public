---
id: doc-portability-test-procedure
type: system-doc
file_class: canonical
authority: canonical
canonical_for: portability-testing
created: 2026-07-10
updated: 2026-07-10
summary: The release-gate tests proving the vault survives without Obsidian, without generated state, on any path, and without AI.
---

# Portability Test Procedure

Run on a **copy** of the vault. All must pass for a release.

1. **Obsidian-independence**: delete `.obsidian/` → `aios validate && aios links` green → open three notes in a plain editor and confirm full meaning.
2. **Generated-state independence**: delete `System/Generated/` → `aios generate` → identical file list on a second run → `aios validate` green.
3. **Path move**: move the vault folder elsewhere → full suite green (nothing depends on absolute paths).
4. **Case/character probe**: `aios validate` reports any case-collisions or forbidden characters (it always checks; confirm zero).
5. **The 13-step acceptance test** (Project Source 07, adopted verbatim): copy folder → remove .obsidian → remove generated → disconnect runtime → open with text editor → identify entry points via START-HERE → recreate documented dependencies (Python + PyYAML) → run validation → connect another supported runtime → rebuild generated → retrieve knowledge correctly → propose & apply a controlled test change → roll it back.
6. **Human-only recovery walkthrough**: a person with no AI and no Python follows the recovery chapter — locate authority, edit a note, flip the kill switch, restore a snapshot, export. Executed at least once by the owner.
