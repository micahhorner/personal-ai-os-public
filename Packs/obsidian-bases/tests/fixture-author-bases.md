---
id: doc-fixture-pack-author-bases
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-pack-author-bases
created: 2026-07-16
updated: 2026-07-16
summary: "Behavioral fixture: author a valid .base view via the author-bases pack capability, under AI OS plugin policy."
---

# Fixture — pack-author-bases

**Scenario**: With `pack-obsidian-bases` installed, the user asks for "a table view of my active projects."

**Pass criteria** (all must hold):
- [ ] Reads `resources/kepano/SKILL.md` before authoring — does not write Bases YAML from memory.
- [ ] Produces a `.base` file that is valid YAML; every `formula.X` used in `order`/`properties` is defined in `formulas`.
- [ ] Guards null properties with `if()`; accesses `.days` before rounding a Duration (never divides a Duration).
- [ ] Uses **this vault's** metadata keys — does not adopt the vendored examples' vocabulary (`status: done`, `priority`) as schema.
- [ ] Does NOT author a `map` view (requires the Maps community plugin; adopted plugins: none).
- [ ] Stores no fact only in the Base — the view surfaces data that exists in frontmatter (plugin-policy §1).
- [ ] Never writes frontmatter to satisfy the view (plugin-policy §3).
- [ ] `aios validate` 0 errors after the write.
