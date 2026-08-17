# Fixture 30 — setup (the retrodiction test)

A seeded-flaw eval only proves the pass can find flaws someone planted for it. This
one proves something harder: that it finds a flaw **nobody planted** — a real defect
that a real shipped plan carried, and that a human later caught by re-reading it
honestly. The correction is on the record and is not in the input.

1. Copy the vault to a scratch location (fixtures never run against the live vault).
2. Copy `spec-aios-measure-original.md` into the scratch vault's `00 Inbox/`.
3. **Run the pass blind.** The runtime must not be shown `expected.md`, must not be
   told a flaw exists, and must not be told how the item actually shipped. Say only:

   > "Red-team this before I build it."

   **Keep the answer out of reach.** The correction is recorded in this product's
   own history, so the runtime must not read, while the pass is open: the
   CHANGELOG, the change journal, `System/Governance/Active Decisions.md`, the
   constitution's amendment log (§5.19 and the v2.10.0 entry name this case), or
   git history. The capability's own `SKILL.md` is deliberately free of worked
   examples for the same reason — if an illustration of this case ever appears in
   it, this fixture has been quietly disarmed and the fix is to remove the
   illustration, not to lower the bar.

4. Score the report against `expected.md` **after** the pass is complete.
5. Discard the scratch copy.

## Why this artifact

`aios measure` was filed as **one command doing three jobs** — a transcript
measurement, a note-check, and a register baseline. It shipped as **one job**: the
transcript measurement. The other two were explicitly demoted before any code was
written, once someone re-read the item and asked which of the three had ever
actually been needed.

The correction of record, in the estate's own words: *"Scope: the transcript job
only — the note-check and register-baseline halves were explicitly demoted."* Only
the transcript job had a triggering incident behind it (the eleven-of-eighteen
coinage finding, which is cited in the filing itself and belongs to job 1 alone).
The other two jobs shared a *word* — "measure" — and nothing else: not an input,
not a consumer, not an incident.

**The input above is a restatement of the original filing**, written for this
fixture from that record. It is not a verbatim historical document, and the fixture
does not claim to be one; what it faithfully preserves is the three-job scope, the
"why one command" reasoning, and the fact that only job 1 carries evidence of
demand. That is the whole surface the pass is scored on.

## The bar

The pass must reach the correction **on its own**, from the text alone. A report
that praises the bundling, or that lists only cosmetic objections while treating
all three jobs as equally warranted, is a FAIL — and it is the more informative
failure, because it says the capability finds flaws only when they are planted.
