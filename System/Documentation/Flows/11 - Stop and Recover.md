---
id: doc-flow-stop-and-recover
type: system-doc
file_class: canonical
authority: canonical
canonical_for: flow-stop-and-recover
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: "User walkthrough for the stop & recover flow."
---

# Flow 11 — Stop & Recover

**If anything looks wrong, one line stops all AI writing instantly. The journal shows what happened, and checkpoints let you restore any earlier state. Your notes are always just files — nothing can hold your knowledge hostage.**

Visual: `System/Documentation/Diagrams/svg/35-flow-stop-and-recover.svg`.

---

## Your goal

Feel safe. Be able to halt the AI and undo anything, at any time, with no technical assumptions.

## What you say

> "Stop."
> (or set `ai_writes_enabled: false` in `SYSTEM-MANIFEST.yaml`)
> "Restore the checkpoint from before that change."

## What happens

1. The **kill switch** (`ai_writes_enabled: false`) makes every compliant runtime and script refuse all writes — immediately.
2. The **journal** shows what happened and when.
3. A **checkpoint** (a git commit or a zip snapshot) lets you restore an exact earlier state — your explicit `--confirm` is the authorization, so recovery works even while writes are off.
4. If all else fails, your notes are **plain files** — any text editor opens them; the Recovery Guide starts from symptoms and assumes nothing works but a text editor.

## What you get

- All AI writing stopped instantly; your files stay yours.
- Any earlier state restorable, with a plain-language guide.

## If it goes wrong

- **Not sure what broke?** Read the journal first; it names what changed.
- **Restore feels risky?** The system proposes the target and what's kept/lost before you confirm.

## Related

- The recover flow and backup model — `Diagrams/svg/21-recovery-backup.svg`.
- The kill switch and change control — `Diagrams/svg/12-three-write-lanes.svg`.
- `System/Documentation/Maintenance and Recovery Guide.md` — symptom-first, no assumptions.
