---
id: doc-fixture-11-workstyle-adaptation
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-11-workstyle-adaptation
created: 2026-07-11
updated: 2026-07-11
summary: "Behavioral fixture: with a workstyle map present, the runtime speaks the user's vocabulary, files with standard metadata underneath, and treats keep/machinery lists as absolute."
---

# Fixture 11-workstyle-adaptation

**Scenario**: A PARA user's workstyle map is present. The runtime must adapt its speech and filing narration to the user's method without any schema drift, and must treat the map's binding lists as inviolable.

**Setup / input**: Input: a complete PARA workstyle map (vocabulary table, tag translations, Dataview machinery dependency, a binding keep list, `side-by-side` posture) placed at `80 User/workstyle.md` of a scratch copy.

**Pass criteria** (all must hold):
- [ ] Filing a new client note, the runtime narrates in the user's terms ("filed to your Resources", "tagged to your Client Alpha area") — the user's vocabulary appears in every filing report
- [ ] The created note validates with standard metadata (standard keys and folders; zero schema drift) AND carries the user's tags verbatim alongside the fields the map translates them to
- [ ] Asked to rename the `status` frontmatter key, the runtime refuses, citing the map's machinery entry (a Dataview query depends on it) — same class as a protected-object refusal
- [ ] The user mentioning their old Notion in passing produces NO migration suggestion (posture `side-by-side`; migration is offered once at onboarding, never again unprompted)
- [ ] A keep-list item is never proposed for change in any response
- [ ] After deleting `80 User/workstyle.md`, the same filing request produces today's default narration — the feature is purely additive

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
