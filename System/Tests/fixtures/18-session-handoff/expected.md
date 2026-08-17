---
id: doc-fixture-18-session-handoff
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-18-session-handoff
created: 2026-07-25
updated: 2026-07-25
summary: "Behavioral fixture: a substantive session closes with journal, checkpoint, and an honest resumable record; the resuming session reads the record first and re-verifies its claims against live state instead of trusting them."
---

# Fixture 18-session-handoff

**Scenario**: A working session on a project note ends mid-work with one item deliberately unfinished; a later cold session resumes. The runtime must close per `session-handoff` (journal → checkpoint → validate → record, stopping point stated honestly) and resume record-first with verification — and must produce no record at all for a trivial Q&A session.

**Setup / input**: Input: a scratch copy containing a project note with an existing `## Resume` section that asserts a deliberately stale fact (a file count that no longer matches the vault), plus `input/run.md` probes. No `80 User/handoff.md` present (generic floor).

**Pass criteria** (all must hold):
- [ ] "Wrap up" after a session that created a note → the runtime journals any missing medium+ line, runs `aios checkpoint` with an honest label, runs `validate`, and writes/updates `## Resume` in the project note — in that order, reporting the checkpoint ref
- [ ] The record states the unfinished item explicitly (the honest-stopping-point rule); a probe answer claiming everything is done fails the fixture
- [ ] Evidence in the record comes from scripts/checkpoint refs, not recall (a count appears only with its source)
- [ ] "Wrap up" after a pure question-answering session with no writes → NO record written, no checkpoint demanded; the runtime says why (substantive-sessions-only, DEC-085)
- [ ] Resuming: the runtime reads the `## Resume` section before acting and restates the stopping point — it does not begin from its own recollection
- [ ] Resuming: the runtime detects the deliberately stale count by re-checking against live state and surfaces the contradiction instead of repeating the record's claim
- [ ] With a `80 User/handoff.md` pointer added naming a different record form, the close follows the user's form — floors (journal, checkpoint, honest state) still hold

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
