---
id: doc-release-evidence
type: system-doc
file_class: canonical
authority: canonical
canonical_for: release-evidence
version: 1.0.0
created: 2026-07-10
updated: 2026-07-10
summary: "Dated, commit-bound evidence for the v1.0.0 release gates. Gates 1-5 executed and passing; gate 6 (owner-only recovery) and observed runtime certification recorded here when complete."
---

# Release evidence — v1.0.0 candidate

```yaml
frozen_commit: 4af4791b1  (tag: release-candidate-freeze)
executed: 2026-07-10
executed_by: Claude (Fable 5), owner-instructed
method: fresh `git archive` extraction per gate; no source vault touched
```

## Portability Test Procedure results

| Gate | Result | Evidence |
|---|---|---|
| 1 — Obsidian independence | **PASS** | `.obsidian/` deleted → validate + links green; notes fully readable in plain text |
| 2 — Generated-state independence | **PASS** | `System/Generated/` deleted → rebuilt; identical file list on second run; validate green |
| 3 — Path move | **PASS** | vault moved to a different path → validate, links, dupes, full unit suite green |
| 4 — Case/character probe | **PASS** | zero collisions or forbidden names (validator always checks) |
| 5 — 13-step acceptance | **PASS** | all steps, incl. second-runtime simulation (local L0 discovery: manifest → kernel → profile [L2 uncertified, no certifications] → 15-operation contract), deterministic retrieval via `aios search/read`, controlled change applied + validated + rolled back via the no-git zip path |
| 6 — Owner-only human recovery | **WAIVED (DEC-029)** | owner declined; mechanical recovery paths proven (zip-only restore, rollback-while-off, exact-tree) — standing offer to run the 4-step drill remains |

## Supporting evidence (same day, this session)

- **CI**: green on ubuntu/py3.9, ubuntu/py3.11, macos/py3.11 for every merged PR incl. the freeze head.
- **Pressure test**: clean instance driven through 2 simulated weeks (onboarding, 12-item intake with traps, contradiction/stale/supersession/approval lifecycles, all privacy classes, domain isolation, maintenance, kill-switch drill, rollback-while-off, zip-only restore, extension e2e, migration e2e). Two defects found (P-1, P-2), fixed, merged before freeze.
- **Extended pressure**: 1,632-file scale (~1s/command) · hostile input (YAML colon, forbidden filename, placeholder id caught; unicode/emoji + 5MB accepted) · git-less lifecycle (zip checkpoints, migration fallback, manual-restore guidance) · crash-mid-generate healed by rerun.

## Completion record

1. Gate 6: **waived by owner** (DEC-029, 2026-07-10).
2. Certification battery: **ALL 10 FIXTURES PASS** (2026-07-10, owner-present observer; detailed per-fixture results in the workshop record `Fable Outputs/12`). L0–L3 certified for the reference runtime on the frozen state. Results deliberately not shipped as a profile grant (DEC-025 — the seed stays uncertified).
3. Owner docs read-through: **completed, approved** ("docs are good", 2026-07-10).
4. Released: manifest + package at 1.0.0; tag `v1.0.0` on the release commit.
