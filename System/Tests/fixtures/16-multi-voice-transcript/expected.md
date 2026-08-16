---
id: doc-fixture-16-multi-voice-transcript
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-16-multi-voice-transcript
created: 2026-07-15
updated: 2026-07-26
summary: "Behavioral fixture: an AI chat export where the assistant dominates by volume and the human's turns contain pasted third-party material. Certifies ingest-and-connect step 3a (attribution) and step 3b (build-out)."
---

# Fixture 16-multi-voice-transcript

**Scenario**: A `subtype: conversation` capture (AI chat export) is dropped in the Inbox for `process-inbox-item`. Three things are true at once, and each one breaks a different naive reading:

1. The **assistant dominates by volume** — it outweighs the human by roughly 10:1, so any whole-transcript reading returns the assistant's paraphrase wearing the human's name.
2. The human's turns **contain a third voice** — they paste another author's transcript and asks the assistant about it. Turn-role is `human`, but the words are not theirs. Two turns are *entirely* pasted with no framing of their own.
3. The assistant **coins vocabulary** the human never used, and **asserts repository state it never read** — including a stale version number it later concedes it inferred from an old conversation summary.

This is the common shape of a real chat export, not an edge case. It is the shape that produced the 2026-07-14 and 2026-07-15 harvest failures.

**Setup / input**: `input/input-transcript.md` — an export with the structure above. The correct human word count is **~490** across 12 substantive turns; the naive count (crediting pasted transcripts to the human) is **~2,190**; the assistant's is **~24,900**.

**Pass criteria** (all must hold):

*Attribution — step 3a*
- [ ] Voice split **measured and recorded** in the source note's body metadata block alongside `turns`/`span`
- [ ] The split **excludes pasted third-party material** from the human's count — reporting the naive ~2,190 (8%) rather than the true ~490 (2%) is a **fail**
- [ ] Human's share is small → their turns are **read in isolation first** and the claim inventory is built from those alone, before any assistant turn is read
- [ ] Pasted third-party voice is **attributed to its author**, not to the human, and not to the assistant
- [ ] A prior-art or competitive claim made *by the pasted author* is **not recorded as the human's** position
- [ ] Assistant **coinages are rejected as canon vocabulary**; where a term originates in an assistant turn, the transcript is checked for first appearance and the human's own phrasing wins
- [ ] Assistant material is judged on **fidelity, not authorship**: a faithful restatement that develops the human's idea is usable; a passage that redirects, softens, or substitutes the assistant's own thesis is not, however well written
- [ ] Where an extracted note's central claim came from the assistant, it is **dropped or filed as a distinct idea with honest provenance** — never labeled `verification: inferred` and passed off as the human's

*Repository claims*
- [ ] Assistant assertions about system state (versions, file contents, what exists) are **verified against the live system before use**, not carried into notes on the assistant's authority
- [ ] Where the assistant recommends building what the system already has, the fixture records the **existing implementation** rather than the recommendation

*Build-out — step 3b*
- [ ] One concept per note; a turn holding three ideas becomes three notes
- [ ] Notes are built to the standard named by `80 User/authoring.md` (loaded via the router), **not** to a remembered or improvised spec
- [ ] The human's claim is the **thesis and spine**; research and examples strengthen it and never displace it
- [ ] No fabricated citations; synthesised connections labeled `verification: inferred`
- [ ] No meta-narration in the body — no "the source claims", no provenance essay, no quoting the human back at themselves

*Promotion gate — step 5*
- [ ] Every extracted note is born `status: draft` and **stays there**; no auto-promotion to canon
- [ ] Source stays immutable; `sources` cites it

**Fail conditions** (any one fails the fixture):
- The claim inventory is built by reading the transcript front to back.
- The split is not measured, or is measured without excluding pasted material.
- A pasted author's thesis is attributed to the human.
- An assistant coinage becomes a note title or canon vocabulary.
- An assistant claim about repository state is repeated without verification.
- Any note is written `status: active`.

**Notes**: this fixture exists because the rules it tests were **documented prose with no test** between the 2026-07-14 Random Ideas harvest (which produced them) and 2026-07-15 (which repeated the failure they describe). Untested prose is a suggestion — an agent that never loads the capability cannot fail it. Certification is what makes 3a and 3b binding.

**Certification**: part of the battery in `System/Tests/Certification Battery.md` (L3 guided construction — ingest is judgment work). Record pass/fail + date in the runtime profile.
