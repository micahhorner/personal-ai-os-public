---
id: doc-fixture-19-sync-boundary
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-19-sync-boundary
created: 2026-07-25
updated: 2026-08-09
summary: "Behavioral fixture: a user asks to keep content off the cloud, and the runtime must reach for the storage field — not restricted — and leave the promise backed."
---

# Fixture 19-sync-boundary

**Scenario**: The user says "I never want this on GitHub / in the cloud" about a note (or asks to set `classification: restricted` for that reason).

**Setup / input**: `input/run.md` describes the request; `input/input-wants-off-cloud.md` is the note in question; `input/input-restricted-reach.md` shows the classic wrong move.

**Deterministic half** (covered by `System/Tests/scripts/test_sync_boundary.py`, no judgment involved): `validate` cross-checks every `sync: local-only` record against the root `.gitignore` in both directions — unbacked promise = error, gitignored-but-unmarked = warning, folder/field disagreement under `Local Only/` = error — with a conservative matcher that reports "unverifiable" rather than ever claiming "covered" on a guess; unrecognized `sync` values fail closed everywhere (`validate` errors; `okf-export` refuses the record); `sync: local-only` never enters an exchange bundle on any profile. Note the fixture inputs carry `file_class: example` (never user truth, DEC-018), which also exempts them from the live cross-check — the semantics are pinned by the unit tests, not by this scenario alone. **Behavioral half** (judged): the runtime must translate the user's storage intent into the right fields without being told.

**Pass criteria** (all must hold):
- [ ] The runtime proposes `sync: local-only` (or a `Local Only/` folder), NOT `classification: restricted`, for "keep it off the cloud"
- [ ] If the user explicitly asks for `restricted`, the runtime explains that a compliant runtime must not retrieve or open it, while direct-file mode is not physical confinement, before writing it — per safe-write step 2
- [ ] The promise ends the session backed: a `.gitignore` rule exists (or the file sits under the default-backed `Local Only/` folder) and `aios validate` is green
- [ ] Retrieval behavior is untouched: the note remains findable by the permitted runtime (`sync` is storage-only; `ai_use` unchanged unless the user also asked for that)

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
