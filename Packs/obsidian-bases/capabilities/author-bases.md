---
id: capability-author-bases
name: author-bases
component_type: capability
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-author-bases
status: active
version: 1.0.1
summary: Author or edit an Obsidian Bases file (.base) — a live view over notes' frontmatter — using the vendored kepano reference for syntax, under AI OS's plugin policy.
consolidates: []
reads: [vault]
writes: [per-procedure]
permissions: [uses-vault-operations-only]
dependencies: [doc-runtime-kernel]
tests: [tests/fixture-author-bases.md]
documentation: self
created: 2026-07-16
updated: 2026-07-16
---

# Capability — author-bases

A **Base** (`.base`) is a YAML file describing a live table/card/list view over notes' frontmatter. It is a **display surface, not knowledge**.

This capability does not restate the syntax. The syntax reference is vendored verbatim from `kepano/obsidian-skills` (MIT, Steph Ango) and is the authority for it:

- **Syntax, filters, formulas, views:** `resources/kepano/SKILL.md`
- **Complete function reference:** `resources/kepano/references/FUNCTIONS_REFERENCE.md`
- **License + attribution:** `resources/kepano/LICENSE`

## Procedure

1. **Read the vendored reference** above before writing any `.base` file. Do not write Bases YAML from memory — the Duration and quoting rules are the two that bite.
2. **Preflight as normal** (`System/Governance/Change Control and Preflight.md`). A `.base` file is a write like any other: search first, smallest valid change.
3. **Author the file**, then validate it as YAML and confirm every `formula.X` referenced in `order`/`properties` is defined in `formulas`.
4. **Run `aios validate`.** Zero errors is the pass bar.

## Boundaries — where AI OS overrides the vendored reference

These rules come from `System/Adapters/Obsidian/plugin-policy.md` and **win over anything in the vendored file**:

- **A Base holds no canonical meaning** (policy §1). It is a view. If every `.base` file were deleted, nothing may be lost. Never store a fact only in a Base.
- **Display only** (policy §2/§3). A Base reads frontmatter; it never writes it. It therefore cannot introduce unknown metadata keys.
- **A deterministic equivalent must exist** (policy §4). Anything a Base surfaces that *matters* must also be reachable via `aios search` / `aios health`. A Base is convenience over a truth that already exists elsewhere.
- **No map views.** The `map` view type in the vendored reference requires the Maps community plugin. Adopted plugins: none. Do not author map views without an explicit policy §5 entry.
- The vendored reference's examples use its own property vocabulary (`status: done`, `priority`). **These are illustrations, not this vault's schema.** Use this vault's metadata dictionary; never adopt an example's keys.
