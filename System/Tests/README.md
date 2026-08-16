# System/Tests — how AI OS proves itself

This folder is the product's built-in quality-control kit. It is what lets you (or your AI) **verify that your copy of AI OS is healthy, correct, and untampered** — without trusting anyone's word for it. Governance you can run yourself is a core promise of this system, not an afterthought; this folder is where that promise is checkable.

## What's in here

**`scripts/` — the automated checks.** Small programs that confirm the system works:
- `test_aios.py`, `test_commands.py` — the `aios` toolkit and its commands behave correctly.
- `test_import.py` — importing an outside file lands it safely in the Inbox.
- `test_doc_staleness.py` — documentation hasn't drifted from what it describes.
- `test_certify.py` — the certification checks pass.

**`examples/` — reference specimens.** Sample notes that show what a good decision, briefing, lesson, or procedure looks like — used to check the system's output and to learn the formats.

**`fixtures/` — staged test scenarios.** Tiny fake vaults, each built to prove one behavior:
- `01-duplicate-proposal` — the system catches duplicates.
- `04-privacy-exclusion` — private/local-only content is never exposed.
- `06-high-risk-blocked` — a risky action is stopped, not silently done.
- `09-readonly-write-refused` — a write is refused when the kill-switch is on.
- …and more, one per guarantee.

**Procedures.** `Certification Battery.md` (the full pass/fail suite), `Portability Test Procedure.md` (prove your copy runs anywhere), `Fixture Runner Protocol.md` (how fixtures are executed). Results land in `results/`.

## How to run it

- **Quick health:** `python3 System/Scripts/aios.py health` — the everyday "is anything off?" check.
- **Full validation:** `python3 System/Scripts/aios.py validate` — schema, links, and integrity, must be green.
- **The test scripts:** run the files in `scripts/` (e.g. `python3 System/Tests/scripts/test_aios.py`).
- **Full certification:** follow `Certification Battery.md` end to end.

## What passing proves

That your copy enforces its own rules: privacy boundaries hold, risky actions are gated, generated files rebuild from source, imports quarantine correctly, and the documentation matches the system. In short — it is safe to turn an AI loose on your real work inside this vault, because the guardrails are real and you can check them yourself.
