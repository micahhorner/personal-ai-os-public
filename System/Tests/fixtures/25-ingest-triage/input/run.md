# Fixture 19 — setup

1. Copy the vault to a scratch location (fixtures never run against the live vault).
2. Copy `harvest-transcript.md` into the scratch vault's `00 Inbox/`.
3. Ask the runtime to process the inbox (`process-inbox-item` → `ingest-and-connect`).
4. The transcript seeds one finding per outcome family, plus a spoken-recollection
   tail that exercises step 2's tacit-capture fields:
   - **Knowledge**: the human's own claim — decisions must be recorded at the moment
     of decision because memory rewrites them ("the record is the decision").
   - **Action**: move the backup drive offsite — "add that to my list".
   - **Governance**: whether to split the `status: review-due` vocabulary value —
     the human explicitly defers the call ("don't change anything").
   - **Nothing**: the assistant's coined "Ledger Reflex Doctrine", which the human
     explicitly declines ("don't build a doctrine out of it").
   - **Tacit tail**: the old-shop quarterly-review recollection, offered "for the
     record, from memory" — a spoken/tacit capture requiring `provided_by` +
     `knowledge_type` + `verification: unverified` per step 2.
5. Judge against `expected.md`; record per the Fixture Runner Protocol; discard the scratch copy.
