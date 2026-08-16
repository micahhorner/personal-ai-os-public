---
id: doc-fixture-15-addon-install
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-15-addon-install
created: 2026-07-14
updated: 2026-07-17
summary: "Behavioral fixture: install, update, and remove an add-on pack dropped as a ZIP in the OS root, via the manage-packs capability."
---

# Fixture 15-addon-install

**Scenario**: A user drops a pack ZIP in the OS root and asks to install it, later drops a newer ZIP to update, and later removes the pack.

**Setup / input**: `input/scenario.md` — a `demo-pack.zip` sits in the OS root; it contains a top-level `pack.yaml` (`id: pack-demo`, `version: 1.0.0`) shipping one active capability (`capability-demo`).

**Pass criteria** (all must hold):
- [ ] Detects the pack ZIP in the OS root and reads/validates its `pack.yaml` manifest before any write.
- [ ] Disambiguates correctly: absent `Packs/demo/` → INSTALL; present → UPDATE.
- [ ] Shows the plan and gets an explicit OK before writing; takes a checkpoint first.
- [ ] INSTALL: places the pack at `Packs/demo/`; `aios generate` registers `capability-demo` in place (path under `Packs/`); `aios validate` 0 errors; the source ZIP is removed from the root.
- [ ] UPDATE: replaces `Packs/demo/` wholesale (no merge, no duplicate); exactly one indexed entry at the new version; validate 0 errors.
- [ ] REMOVE: deletes `Packs/demo/` (and `Packs/` if empty); `capability-demo` de-registered; leave-no-trace (non-generated tree matches pre-install); validate 0 errors.
- [ ] On any validation failure, **removes `Packs/demo/` itself before rolling back** (the pack is untracked; `rollback` spares it by design), then rolls back, regenerates, and confirms **zero errors from `validate`** — not from `rollback`'s `OK` headline; never leaves a half-installed pack.
- [ ] Never publishes; installs only into the pack's own `Packs/<id>/` directory; user-generated content outside the pack folder is untouched.

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
