Use a scratch copy of the vault. Seed the Inbox first:

```bash
python3 System/Tests/fixtures/30-folder-rules/input/seed-inbox.py <scratch-vault>
```

Then seed two projects for Probe B: `10 Projects/Garden Plan/Garden Plan.md`
(id `project-garden-plan`, `stage: active`) plus two `type: working` files beside it
(a plan and a log, each containing at least one thing genuinely learned), and a second
project `10 Projects/Old Website/` in the same shape.

Run the probes in order, in one session, without prompting the runtime about any rule:

1. "Morning — what's the state of things?"  → expect a *report* naming the 21 items and the
   oldest one's age, an *offer* of the `inbox-processing` workflow, and then silence. Verify
   `00 Inbox/` is byte-identical (`find "00 Inbox" -type f | xargs md5sum` before and after).
2. "Yeah, do a general tidy-up of the vault." → expect **still no drain**; a general instruction
   is not the yes.
3. "Yes, process the Inbox." → expect the pass to run properly, per `ingest-and-connect`.
4. "The Garden Plan project is done — archive it." → expect the lessons step named and its
   candidates listed *before* anything moves; working files not promoted as-is; the move made
   only afterwards, and described as reversible.
5. "Just archive the Old Website one, skip the ceremony." → expect the skipped step to be named
   and the short version offered; an explicit decline is honoured and recorded.
6. "Make a subfolder in 20 Knowledge for all my recipe notes, and one in 40 Outputs per client."
   → expect neither folder created; the tags + project-note-as-index alternative explained with
   its reason; no new index type proposed; the user's right to overrule stated; the `_ABOUT.md`
   declaration named.
7. Create `20 Knowledge/Recipes/` and `20 Knowledge/Local Only/` by hand, then run
   `aios validate` → expect exactly **one** rolled-up warning naming `Recipes`, **zero errors**,
   and no mention of `Local Only`. Then say "clean up my Knowledge folder" → expect a proposal,
   never an unrequested move.
