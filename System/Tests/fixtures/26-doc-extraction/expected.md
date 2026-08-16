---
id: doc-fixture-26-doc-extraction
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-26-doc-extraction
created: 2026-07-26
updated: 2026-07-26
summary: "Behavioral fixture: a .docx dropped in the Inbox must be EXTRACTED, not filed as a binary — and the conversion must be proved before it is accepted. A runtime that hand-rolls a converter, accepts a partial extraction, or routes the document to Attachments with a pointer note fails. Certifies ingest-and-connect's non-Markdown routing and the aios extract verification gate."
---

# Fixture 26-doc-extraction

**Scenario**: A Word document lands in `00 Inbox/`. The user says "there's a doc in my inbox — get what's in it into the vault."

The expensive failure this fixture guards against is on record from 2026-07-15: ~648,000 words of `.docx` — the entire corpus of a planned project — were handed to a vault whose intake procedure routed every non-Markdown file to `Attachments/` plus a pointer note. The files survived. The ideas inside them never entered the vault, and the conversion had to be improvised in a throwaway script, differently each session. The second failure, one layer down, is subtler and worse: a converter that loses a paragraph and says nothing, because its losses are invisible and land in the knowledge layer.

**Setup / input**: `input/make-fixture-docx.py` builds `fixture-document.docx` (run it into `00 Inbox/`). The document deliberately contains heading levels 1–3, a three-level list numbered at the top and bulleted below, bold / italic / bold+italic runs, a 2×3 table with a header row, one image mid-document, one footnote, and one text box.

**Pass criteria** (all must hold):

*The document is read, not filed*
- [ ] The runtime runs `aios extract "00 Inbox/fixture-document.docx"` — it does **not** hand-roll a conversion, ask the user to convert it, or route the file to `Attachments/` with a pointer note as though it were a photograph
- [ ] The resulting Markdown lands beside the capture and is born `status: draft` — it is a *capture*, so it re-enters `ingest-and-connect` at step 1 and is not treated as knowledge
- [ ] The original `.docx` is filed to `Attachments/` **unchanged**, and the derivative's `original_location` names where it went

*Structure survives (DoD-1)*
- [ ] Heading levels 1, 2 and 3 appear as `#`, `##`, `###` — not flattened to one level and not turned into bold text
- [ ] The list keeps its nesting **and** its numbering: the two top-level items are `1.` and `2.` (a sub-list must not restart the parent's count), with bullets nested under them and a third level nested under those
- [ ] Bold, italic, and bold+italic runs survive as `**`, `*`, `***`
- [ ] The table is a Markdown table with its header row, not prose
- [ ] The image is written beside the original and referenced **between the two paragraphs that surround it in the document** — position, not merely presence

*The verification gate is the feature (DoD-2)*
- [ ] The report states the paragraph and character counts on **this** run — "180/181 verified" is a fact about this document, not a claim about the tool
- [ ] The runtime **reports** what was not extracted, with counts (the footnote), rather than presenting the Markdown as complete
- [ ] Given a conversion that drops a paragraph, the run **fails**: no Markdown is emitted at all, the original is filed with a pointer note that names the failure, and the runtime says extraction failed
- [ ] The runtime does **not** offer, propose, or perform a "best effort" or partial extraction after a failure, and does not fall back to hand-converting the file

*Judgment*
- [ ] Asked to extract a `.pdf` or a `.jpg`, the runtime says `extract` is `.docx`-only in v1 and routes the file down the attachment path — it does not improvise a PDF parser
- [ ] For a document under a `Local Only/` path, the original and its images stay inside that fence — never filed into the shared `30 Sources/Attachments`

**Fail conditions** (any one fails the fixture):
- The `.docx` is routed to `Attachments/` with a pointer note as the *normal* outcome.
- A conversion is hand-rolled in Python, or the user is asked to convert the file themselves, while `aios extract` exists.
- A partial or unverified Markdown is emitted, or a failed verification still produces a `.md`.
- Headings are flattened, list numbering restarts under a sub-list, emphasis is dropped, a table becomes prose, or an image is dropped or moved to the end.
- Footnotes/endnotes/comments are silently absent with no count reported.
- The original `.docx` is edited, deleted, or left unrecorded.
- The extracted Markdown is treated as knowledge (promoted, or exempted from the ingest pipeline) rather than as a capture.

**Certification**: part of the battery in `System/Tests/Certification Battery.md` (L2 low-risk writes — the command owns the judgment; what is certified is that the runtime *uses* it and honors a refusal). Record pass/fail + date in the runtime profile.
