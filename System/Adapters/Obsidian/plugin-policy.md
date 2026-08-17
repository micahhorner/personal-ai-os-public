---
id: adapter-obsidian-plugin-policy
type: adapter
file_class: runtime-specific
authority: derived
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
derived_from: [doc-canonical-architecture]
created: 2026-07-10
updated: '2026-08-09'
summary: Community plugins are optional conveniences only — the rules.
---

# Obsidian Plugin Policy

1. No community plugin may hold canonical meaning — if a plugin database vanished, nothing may be lost.
2. Plugins that only *display* canonical data (query/table views) are fine.
3. Plugins that *write* frontmatter must be checked against the metadata dictionary before adoption (unknown keys fail validation).
4. Anything a plugin automates that matters should have a deterministic `aios` or skill equivalent documented.
5. Record adopted plugins here with their purpose and what would be lost if removed (correct answer: convenience only).

## Adopted plugins

Three ship pre-installed in the seed vault, so that a new copy opens usable rather than raw
(v1.0.4). Each is listed with the only thing that matters under rule 1 — what is lost if you
delete it.

| Plugin | Purpose | Lost if removed |
|---|---|---|
| `notebook-navigator` | A file-tree sidebar that makes the numbered folders navigable at a glance | Convenience only. Obsidian's built-in file explorer shows the same folders. |
| `obsidian-git` | Commits and pushes on a timer, which is what makes the GitHub backup option in `Backup and Recovery Options.md` automatic rather than a thing you must remember | Convenience only — but note the honest cost: backups become manual (`aios checkpoint`, or `git push` by hand). Nothing in the vault is lost; the *habit* is. |
| `dataview` | Renders query views over frontmatter | Convenience only. Every view it draws is derived from frontmatter that lives in the notes themselves; `aios generate` produces the same facts without it. |

This file previously read *"Adopted plugins: none."* while all three sat in the shipped
`.obsidian/` — and one of them was being sold as a headline backup option two documents away.
Rule 5 exists precisely so that cannot happen; it had simply never been executed.
