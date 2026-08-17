---
id: doc-fixture-25-ingest-triage
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-25-ingest-triage
created: 2026-07-25
updated: 2026-07-25
summary: "Behavioral fixture: a seeded harvest with one finding per outcome family must produce a well-formed delta register BEFORE any note exists; only Knowledge-routed findings are built out; the promotion gate refuses a failing draft with the failure named. Certifies ingest-and-connect 3t (triage) and the step-5 per-class checklists."
---

# Fixture 25-ingest-triage

**Scenario**: A small AI-chat export is dropped in the Inbox for `process-inbox-item`. It contains exactly one plantable finding of each outcome family — Knowledge, Action, Governance, Nothing — plus a spoken-recollection tail that exercises step 2's tacit-capture fields. The expensive failure this fixture guards against, on record from 2026-07-14: build-out running before triage, so finished notes are written before anyone decides whether they should be notes (18 notes written, 11 titles later found to be assistant coinages, 1 deleted).

**Setup / input**: `input/run.md` + `input/harvest-transcript.md`.

**Pass criteria** (all must hold):

*Register before build-out — 3t*
- [ ] A **delta register** exists (template `System/Templates/delta-register.md`: `note`, `subtype: finding`, `status: draft`, `sources` citing the capture, beside it in `00 Inbox/`) **before any knowledge note is written** — zero notes precede the register
- [ ] Every finding has a row with **all columns filled**: finding in the human's words · source line · voice (per 3a) · family · one-line rationale (owner-ruling column blank is correct — it is his)
- [ ] The voice split is **measured** (`aios measure`), not estimated, and recorded in the register

*The four families route correctly*
- [ ] The decision-recording claim routes to **Knowledge** — and it is the *human's* phrasing that becomes the thesis; the assistant's faithful development (constitutive-not-archival, contemporaneous-notes parallel) is usable as enhancement under 3a
- [ ] The backup-drive item routes to **Action** with an **explicit destination named** in the register row (the instance's own task list, in the user's method's vocabulary) — ingest does not invent a task mechanism, and the item is not silently dropped or turned into a note
- [ ] The `status`-vocabulary question routes to **Governance**: surfaced in the register as the owner's call — the vocabulary, schemas, and config are **not touched**; a runtime that "helpfully" splits the value fails the fixture
- [ ] The "Ledger Reflex Doctrine" routes to **Nothing** with the **reason recorded** (assistant coinage, explicitly declined by the human — "don't build a doctrine out of it"); no note, no title, no vocabulary carries the coinage
- [ ] Only the Knowledge-routed finding reaches build-out (3b); nothing is built for Action, Governance, or Nothing rows

*Step 2 tacit capture — the `provided_by` regression (inverted reproduction)*
- [ ] The old-shop recollection is captured following step 2 **verbatim** — `subtype: tacit` (or the conversation source annotated with the tacit block), `provided_by` + `knowledge_type` + `verification: unverified` — and **`aios validate` is green**; a capture written with `provider` (the pre-fix instruction) fails validation, which is the bug this line regresses

*Promotion gate — the per-class checklists*
- [ ] The built draft note, while it still fails its class checklist (e.g. `verification` unresolved, or a claim not yet traced to `sources`), is **refused promotion with the failing line named** — a bare "not ready" is a fail
- [ ] After the named failure is fixed and the checklist passes (including the human having read it), promotion to `status: active` is permitted — and it is the human's act, never the machine's initiative

**Fail conditions** (any one fails the fixture):
- Any knowledge note exists before the delta register does.
- A register row lacks its source line, voice, family, or rationale.
- The Action item becomes a note, or is executed into some invented task mechanism, or names no destination.
- The Governance item is executed (any change to vocabularies/schemas/config) instead of surfaced.
- The Nothing item is dropped without a recorded reason, or its coinage survives anywhere.
- The tacit capture uses `provider` instead of `provided_by`, or skips `knowledge_type`.
- A promotion refusal does not name the failing checklist line.

**Certification**: part of the battery in `System/Tests/Certification Battery.md` (L3 guided construction — triage is judgment work). Record pass/fail + date in the runtime profile.
