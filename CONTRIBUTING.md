# Contributing

The Personal AI OS core and the already-open packs in this repository are MIT-licensed, and contributions to them are welcome. Separately licensed packs or vertical products are outside that grant; their attached license controls. This is also a system that governs its own changes, and that governance applies to contributors too — reading this first will save you a round trip.

## Before you write code

**Open an issue first for anything beyond a typo.** This project has a strong point of view about what belongs in it, and the fastest way to have a pull request declined is to build something that was deliberately left out. Several capabilities are absent on purpose, recorded in `System/Governance/Active Decisions.md`. Check there before proposing a feature; if a decision looks wrong, argue with the decision rather than working around it.

## The local gate

Create the isolated environment once, then run the exact script CI runs:

```
python3 System/Scripts/setup.py
bash System/Scripts/gate.sh
```

The setup command installs the pinned PyYAML range in the vault's isolated sibling environment; Python ≥3.9 is the only host prerequisite. `gate.sh` uses that environment when present and otherwise uses `AIOS_PYTHON` or `python3`, exactly as CI does.

**If you change a root product file** (`README.md`, `START-HERE.md`, `CLAUDE.md`, `pyproject.toml`), the shipped integrity baseline goes stale and a test will tell you so. Refresh it and commit the result alongside your change:

```
python3 System/Scripts/aios.py upgrade --make-baseline --confirm
```

## What a good pull request looks like

- **One concern per PR.** Mixed changes are hard to reason about and harder to revert.
- **Evidence, not assertion.** State what you ran and what it printed. If you fixed a bug, the ideal PR contains a test that fails against the old code — the repository's own convention is a seeded-failure test, and the decision register is full of examples.
- **Prose changes count as changes.** Much of this system's behavior is written in documentation that an AI runtime reads and obeys. Editing that documentation edits the behavior, so it gets the same scrutiny as code.
- **Do not edit dated records to match a later decision.** The CHANGELOG, `System/Journal/`, and the decision register are true as of their dates. Add a new entry; never rewrite history to be retroactively correct.

## Protected areas

Governance rules, schemas, and the AI runtime's own permissions change only with explicit owner instruction. A PR touching those will be asked for a decision record before it is considered, not merged and documented later.

## Claims and runtime evidence

Keep public claims narrower than the evidence. A shipped runtime profile is not a certification, direct filesystem access is not a sandbox, and the runtime-neutral architecture is not proof that every AI works with the product. Preserve the distinction between the 14 core capabilities and the additional capability delivered by the preinstalled open pack. If a claim depends on a benchmark, qualification run, or certification battery, cite evidence bound to the exact candidate rather than copying an older result.

## Style

Match the surrounding files. This system is read by both people and AI runtimes, so clarity beats cleverness, and a paragraph that a competent reader follows once without rereading is the target.

## Licensing of contributions

By submitting a pull request to the MIT-licensed core or an MIT-licensed pack,
you agree that your contribution is licensed under MIT. Do not include code or
content from a separately licensed pack or vertical product unless its license
expressly permits that contribution.
