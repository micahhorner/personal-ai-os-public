---
id: capability-safe-write
name: safe-write
component_type: capability
status: active
version: 0.8.2
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-safe-write
summary: Create or change any note correctly — the complete write procedure.
description: "Create or change any note in the vault correctly — the complete write procedure with preflight, placement, and validation. Use whenever creating, editing, renaming, moving, merging, or archiving any vault content."
consolidates:
- skill-preflight
- skill-create-note-safely
- skill-update-note-safely
- skill-find-canonical
reads:
- vault
writes:
- per-procedure
permissions:
- uses-vault-operations-only
dependencies:
- doc-runtime-kernel
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
- System/Tests/scripts/test_protected_writes.py
- System/Tests/scripts/test_flat_folders.py
- System/Tests/scripts/test_sync_boundary.py
x_runtime_evaluations:
- System/Tests/fixtures/01-duplicate-proposal
- System/Tests/fixtures/05-low-risk-auto
- System/Tests/fixtures/06-high-risk-blocked
- System/Tests/fixtures/11-workstyle-adaptation
- System/Tests/fixtures/19-sync-boundary
- System/Tests/fixtures/30-folder-rules
documentation: self
created: '2026-07-10'
updated: '2026-08-09'
---

# Capability — safe-write

Lane first (Kernel §2): ordinary / consequential / system. System lane → STOP, developer mode.

## Creating
1. **Resolve first — computed**: `aios resolve --query "<title or phrase>"` runs the ladder (id → title → aliases → body phrases) and follows every `superseded_by` chain to the end, the same way every time. Exists? → switch to *Changing* against the canonical record it names. Duplicates are corruption. (Kernel §4: never hand-perform this lookup.)
2. Copy the class template; fill required metadata (`id` = `<type>-<slug>`, immutable); omit empty keys; set governance fields for sensitive content per `80 User/privacy-rules.md`. **Setting `classification: restricted` is almost never right** — a compliant runtime must not retrieve or open the note, but direct-file mode is not physical confinement. If the intent is "never leaves this machine", the correct pair is `sync: local-only` (storage — must be backed by a `.gitignore` rule, or use a `Local Only/` folder; `aios validate` cross-checks both ways) plus `ai_use: local-only` (excluded from compliant hosted retrieval); `classification` records sensitivity only (DEC-092). Say this to the user before writing `restricted`, and keep material the runtime must not technically access outside its filesystem reach; `validate` warns on every restricted record. **Mint by machine**: `aios resolve --query "<title>" --mint --type <type>` returns the id and the F-6-sanitized filename (forbidden characters and trailing dots/spaces stripped at birth) and errors on an id collision — use what it prints. **Consult `80 User/workstyle.md` if present**: use the user's own terms in names, summaries, and filing reports, and apply their tags verbatim alongside the standard fields the map translates them to; its `keep` and `machinery` lists are absolute — proposing a change to anything they name is a defect, same class as a protected-object violation.
3. Ground it: `sources` for claims; `entities` for who/what; `related` sparingly.
4. **Place it — the folder decision.** Write to the folder the registry names (`System/Registries/folder-registry.yaml`; never a hard-coded path). Unprocessed material belongs in Inbox first. A new knowledge note is born `status: draft` (staging) and earns `active` (canon) only through the promotion gate (Principle 26) — never create knowledge pre-promoted.

   **`20 Knowledge/` and `40 Outputs/` stay flat. Do not create a subfolder in either, and do not propose one.** Meaning lives in metadata and links — `type`, `tags`, the relation fields, and the generated per-type views in `System/Generated/` — because a folder tree is a *second* taxonomy competing with the first and it carries exactly one axis: the note that belongs under two headings has to pick one, and the pick is invisible afterwards. That is the whole reason the metadata exists. **Project affiliation is carried by tags plus the project note as its own index** — tag the note, link it from the project note, and let the reverse view generate from the frontmatter relations. Do **not** create an index note, a MOC, or a second register to carry the affiliation: a second index is a second thing to drift (DEC-101).

   *When the user has deliberately diverged.* This is their vault, and the rule binds the runtime, not the human. `aios validate` reports subfolders in these two directories as **one rolled-up warning, never an error** (DEC-082: a lived-in vault never goes red on the user's own content). **The user declares a subfolder deliberate by putting an `_ABOUT.md` in it** — one paragraph saying what the folder is for, no frontmatter required — and `validate` goes quiet about that folder permanently. Say so when the warning surfaces; never flatten a folder on your own initiative, and never re-propose flattening one that already carries an `_ABOUT.md`. (A `Local Only/` folder is a privacy fence rather than a taxonomy and never warns — DEC-065.)

   **Every `output` records `derived_from`** — its provenance chain back to the knowledge and evidence it was built from. Without it a deliverable cannot be traced back, and a changed source cannot be traced forward to the outputs it affects; the trace is the reason the folder is separate from Knowledge at all. The same discipline applies to a project note: it **links** the knowledge, sources, decisions, and outputs it involves and never duplicates them.

## Writing a knowledge note (quality, not mechanics)

The steps above mint a **valid** note. These make it a **useful** one. They apply to every note in the knowledge layer, however it got created.

### The rule everything else follows from

**A knowledge note is an input, not an output.**

It is raw material. Its whole job is to be found, quoted, and combined later — by the user, by a future model, by whatever gets built next. So it is written for precision and accurate reuse, not for reading pleasure.

Anything built *from* the note can be stylised. The note cannot.

That one rule settles most authoring arguments. When a sentence reads better but states the claim less exactly, it is **wrong in a note and right in a post**.

### How a knowledge note reads

A knowledge note reads **more academic than the same author's other writing, and plainer than either**. It is serious, unhurried, and cited. It is also explanatory: written so that a competent reader who does not already hold the framework can follow it once, without rereading.

Defaults, until the user's own corpus says otherwise:

- **Write in developed paragraphs. This rule governs the others.** A knowledge note is a comprehensive explanatory overview, and it argues in paragraphs of roughly four to six sentences: a claim, its grounds, its qualification, its consequence, carried through together. One-sentence paragraphs are rare — under about one in ten, and only for a genuine turn in the argument. Clarity is produced *inside* the paragraph, never by chopping the argument into fragments. A run of short declaratives is not clearer than a well-built paragraph; it is the same content with the connective reasoning deleted, and the reader now has to supply it. **A draft averaging two or three sentences per paragraph has been written in the author's outward register and must be rebuilt.**
- **Break the sentence, keep the paragraph.** Unstacking one overloaded sentence into three clear ones is the work. Putting those three into three separate paragraphs undoes it — the reader gets short sentences and loses the connective reasoning that made them an argument. Split pieces stay in the paragraph they came from, and that paragraph usually gets *longer*. **A rewrite that lowers sentences-per-paragraph has gone wrong, however clear the individual sentences read.** Measure it before saving; this is the most common way a clarity pass fails.
- **Unstack sentences carrying several claims — this is not a rule against long sentences.** The target is the sentence that fuses three or four independent claims with commas and semicolons until no single assertion can be located. A thirty-word sentence making one well-qualified point is in-register; splitting it buys nothing and costs rhythm.
- **State it plainly, then qualify.** The clean version of the claim comes before anything complicates it — usually as the paragraph's opening sentence, with the qualification following in the same paragraph rather than in one of its own. Qualifying inside the first statement means the reader never receives an uncomplicated version of the idea and has to reconstruct one.
- **Sequence it so each part is understandable when it arrives.** A note is read start to finish the first time, and an argument that depends on something explained four hundred words later forces a reread that a clear ordering would have saved. Where a forward reference genuinely cannot be avoided, name it as one rather than leaving the reader to discover the gap.
- **Define coined or repurposed terms on first use, in their own sentence.** A term introduced inside a subordinate clause has not been defined.
- **A concrete within two sentences of every abstraction** — a named case, a date, a number, a worked instance. An abstraction explained only in terms of other abstractions is not yet explained.
- **Vary sentence length, around the register's centre rather than below it.** Short sentences belong in the mix, *inside* paragraphs, where a long sentence has just asked a lot of the reader — not as standalone paragraphs. Any sentence past roughly forty-five words gets read again and usually split; past sixty it always splits. Below forty-five, judge it on whether one claim is locatable, not on length. **Do not drive the mean down**: a note that comes out markedly shorter-sentenced than the author's own corpus has been flattened, not clarified.
- **Restating for comprehension is allowed; restating for length is not.** A second pass at a *different altitude* — the plain version after the technical one, the example after the principle — is teaching, and it is most of what makes a hard note learnable. A second pass at the same altitude is padding. Test: does it hand the reader a grip the first pass did not?
- **The user's outward voice rules stop at the knowledge layer — but their clarity rules do not.** If they have a voice standard (`80 User/voice.md`) it governs posts, essays, and client work, and its *attention* machinery (hooks, cliffhangers, openers built to stop a scroll) is wrong in a note. Its *craft* rules are not: cutting clutter, refusing padding, varying rhythm, reading the draft aloud. Those are about comprehension and they hold in both registers. This is the most common way a runtime's note comes out wrong: it holds both rulebooks, discards the whole voice card to protect the note register, and throws out the clarity with the marketing. Check which of their voice rules survive into the knowledge layer rather than assuming none do; the user's authoring standard should say, and if it does not, ask.
- **Almost no bold.** If a point needs bolding to land, the prose is not doing its job. Bolding every important sentence is self-labeling in different clothes.
- **Headers carry claims, not labels** — and state the claim in plain words. "The Abstraction of Consequence", never "The claim", "Overview", or "Background"; equally, "The test governs armor, not bonds" rather than "The scope, which is narrow and matters enormously". A header is an argument and a retrieval handle at once, and a header that comments on its section is neither.
- **A header roughly every 300 words.** Long prose is allowed to run inside a section — that is the register — but a thousand unbroken words is a wall, and the reader loses the thread before its turn arrives. Err toward fewer: over-heading fragments an argument that should have been carried through, and it is the same overcorrection as the two-sentence paragraph.
- **Objections woven into the prose** where they arise, so the reader cannot skip the hard part. A compact summary of the strongest may close the note.
- **Citations dense and precise**: named author, named work, year.
- **Complete, not padded.** Comprehensive means the note stands alone, not that it is long. Clarity is not brevity — a clear note may still run 1,600 words.
- **Read it aloud.** The most reliable density detector there is. Anything you stumble over is the sentence to rewrite, whether or not you can name what is wrong with it.

These defaults are a design decision of the system. **Treat them as direction, not law** — with one exception. Everything above about *how much a reader has to work* is not a default and does not bend: a note is written to be learned from. What genuinely varies by user is convention — how they cite, how they title, how they handle objections, which vocabulary is theirs. Once the user's own corpus exists, measure it for those.

### The standard always exists. Refine it; never replace it with your own defaults.

The section above **is** the knowledge-note standard. It ships with the system, it applies from the first note a user ever writes, and there is no case where a runtime has to invent one.

Two things refine it, in this order:

- **The user's authoring standard** (`80 User/authoring.md`) — if present, it governs where it conflicts. Read the file; never work from memory of it.
- **The user's existing notes** — once a body of them exists, that corpus is the more precise specification for *convention*. Measure it (citation density, headers per note, how objections are handled, titling, the user's own vocabulary) and let the measurements override the defaults above. Read two or three neighbours before drafting and write to what they actually do. **Measure paragraph shape first — sentences per paragraph, and the share of one-sentence paragraphs.** It is the single most reliable signal of whether a draft is in the user's knowledge register or has drifted into their outward one, and it is the measurement a runtime is most likely to skip.

A remembered spec drifts. A measured one does not. **The model's own house style is never the fallback** — the shipped defaults are.

**Measure conventions, not defects.** A corpus is evidence of what the user writes, not proof that it is what they want. Sentence length is the case that matters: measure it to know where the corpus stands, never to set a target. A runtime that reads "mean 25 words, a third of sentences past thirty" as an instruction will write thirty-word sentences deliberately, hit the numbers, and report compliance — reproducing the density rather than the intent. This has happened in a real vault, and the density had been growing for months before anyone named it, because every note passed every check.

The distinction is simple. **Where the corpus shows a choice, follow it. Where it shows a habit the user has never examined, do not promote it to a rule.** If the measurements pull against the clarity rules above, that is a finding worth raising with the user, not a licence to write notes they will struggle to read.

### One concept per note

A finding containing three ideas is three notes.

Concepts sharing a file cannot be linked, retrieved, or superseded independently, which is what notes are for.

### Write the note. Do not narrate writing it.

Cut anything that talks *about* the note instead of making its argument:

- "the source claims…" / "this is the key insight" / "the interesting part is…"
- quoting the user back at themselves inside their own framework
- any provenance essay in the body — the `sources` field records origin

**Headers carry claims, not labels.** "The Abstraction of Consequence", never "The claim", "Overview", or "Background".

### Four properties that make a note reusable, not merely correct

**1. A lift-ready summary.** The `summary` must be quotable word-for-word, on its own, with nothing in it the reader has to look up. It is the definition downstream work will pull, and it is how the note gets found at all.

**2. Scope conditions.** Say where the claim holds and where it does not. An unscoped claim cannot be applied or refused, so it cannot be used. This is the cure for "proves too much".

**3. A falsification condition.** Say what would make the claim wrong — the evidence, the case, the counterexample. *A claim with no failure condition is an opinion with citations.*

**4. Counterarguments.** Engage objections in the prose, where they arise, so a reader cannot skip the hard part. A short summary of the strongest ones may close the note for anyone retrieving it later. Never a disclaimer bolted on the end.

### Citations

Named author, named work, year. Never "research suggests". Never invent one.

Where a connection is your own synthesis rather than something sourced, **say so** and label it `verification: inferred`.

Research is recruited to strengthen the user's claim. It never replaces it. **Test:** if a reader would attribute the note's thesis to the cited scholar rather than to the user, the note has been overwritten — rewrite it.

**Say what the thinker actually argued, and mark the extension.** The recurring failure is recruiting a descriptive theorist for a normative claim they declined to make, or citing someone for the position they spent a career rejecting. Cite the thinker for their argument; where the note extends past it, say so in the same sentence rather than letting the borrowed authority do the work. A citation that would make its author object is worse than no citation, because it looks like support.

**If you are using someone's framework, name them.** The failure here is not misattribution but non-attribution: deploying a named thinker's concepts, in that thinker's own vocabulary, without ever mentioning them. It matters for three reasons and only one is credit. An unattributed framework cannot be checked, it cannot be followed back to the literature that qualifies it, and it makes the note look either ignorant of its field or quietly acquisitive. Where a rule or distinction is adopted from a live scholarly argument, say that it is contested and that the note is taking a side.

**A source's weight must be visible.** A systematic review, a single unblinded trial, a clinical idiom and an essayist's aphorism are not interchangeable, and listing them together implies a parity that does not exist. Where a note rests on both established and contested material, separate them and let the established part carry the argument.

**Test that a borrowed analogy transfers.** A metaphor imported from another discipline brings that discipline's assumptions with it, and those assumptions frequently do not hold in the new setting. Before keeping a cross-domain analogy, state the mechanism that makes it true at home and check that a counterpart exists here. Where none does, find the model that fits — it is usually available and usually stronger than the borrowed one.

**Distinguish what a study measured from what the claim needs.** A finding supports a claim only along the dimension it actually tested. Research showing that a framing increases clicks measures *attention*; a claim about what a culture rewards is about *reward*. The step between them is the load-bearing one, and citing the first for the second looks like evidence while supplying none. Name the gap in the note rather than letting the citation cover it.

**Effect sizes belong in the sentence.** "X drives Y" and "each additional unit of X raised Y by 2.3 per cent" are different claims, and only the second lets a reader judge whether the mechanism can carry the weight the argument puts on it. Where a figure is small, say so. A small well-established effect honestly reported is worth more than a large one implied.

### Claims that have failed replication

**Keep a list, and check it.** A standard that records which claims are disqualified or require qualification governs nothing unless something sweeps the existing corpus for them. Adding a claim to the list is not the fix; finding its existing uses is. Run the sweep when the list changes and before any publication pass.

Where such a claim previously appeared, **record its removal rather than deleting silently**, so it is not reintroduced later by someone who reads the gap as an oversight. A note that says "this argument previously rested on X, which has since been dismantled" is doing work that a clean deletion cannot.

**The tell for a claim with no source.** A suspiciously round figure, attributed to "studies" with no named author, quoted most often by parties who sell the remedy it justifies. These survive because they are repeated rather than because they were measured, and they are the citations most likely to destroy a piece on contact. Trace one to a primary source or replace it with the weaker statement that holds.

### Registers of claim

Not every claim in a note is the same kind of claim, and treating them alike produces two opposite failures: flattening a genuine insight into hedged mush, and dressing a reading up as a finding.

**Empirical claims** assert something checkable — a study found X, a rate is Y. These are held to the evidence standards above, and getting one wrong is an error to correct.

**Interpretive claims** offer a way of seeing: a lens, judged by what it lets a person notice and whether it holds across the cases it is applied to. An interpretive claim does not become weaker for lacking a citation, because it was never making that kind of promise. **Do not hedge one into vagueness** — that is what flattening looks like in practice, and it preserves neither honesty nor the insight.

**Category confusion is the only real defect**: an interpretive claim wearing empirical clothing. "Studies show", "universally documented", "the most replicated finding in the field", attached to what is actually a reading. The correction is never to delete the insight. It is to let the claim stand in its own register, which also insulates it from a replication dispute that was never about it.

### Explanation standards

**Do not explain an arrangement by the interests it serves without naming the mechanism.** Saying a system "requires" some condition, or that something "is not a bug but a feature", asserts a purpose the evidence rarely supports and personifies a system with no agent. This is functional explanation, and it is legitimate only when the selection mechanism is specified — what causes the beneficial version to persist and the alternatives to disappear. Where the mechanism can be named, name it. Where it cannot, use the weaker and defensible construction: the arrangement *has the effect of* producing that outcome, and nothing corrects it because nobody is measuring what is lost.

**Confidence must match evidence in the sentence, not in a caveat further down.** The characteristic failure is being most certain where least supported. Absolutes require a source that establishes the absolute.

**A note that classifies people or positions states what a legitimate disagreement looks like.** Any note describing someone as captured, unaware, or in denial carries a standing risk of absorbing every response: agreement confirms it and disagreement becomes evidence of the condition. Such a note must specify what an objection that is *none of those things* would look like. A taxonomy in which the author's own position is the only unlisted one has stopped making claims.


## Changing
1. Identify what it is: **source → annotate below the line, never alter captured content** · generated → fix the canonical input instead · approved → edit resets approval to `pending`, tell the human.
2. Smallest valid change; update `updated`; reassess `summary`/`confidence` if meaning moved.
3. Superseding? Set `supersedes`; old record gets `status: superseded`, never deleted.
4. **Consequential lane**: read the target's relations both ways; every dependent ends in exactly one of: auto-updated · marked `stale` · queued for human · confirmed unaffected. One journal line.

## Archiving — and closing a project

Archiving is a move, so it runs through this capability (consequential lane). **It is also where project *closure* actually happens**: the system has no separate close-project capability, and this is the procedure that runs when a project ends. Do the steps in this order — the order is the rule.

1. **Promote the durable lessons first — before anything moves.** Read the finished work for what outlived it: what was learned, what would be done differently next time, the procedure that turned out to be right, the claim the work established. Each becomes an ordinary knowledge note in `20 Knowledge/` through *Creating* above — born `status: draft`, citing the project note and its working material in `sources`. Working material (`type: working` — plans, logs, captures) is project *state* and never graduates as-is; what graduates is the knowledge the project produced, written as notes that stand on their own once the project's context is gone. **Say what you promoted, as a list, before you move anything.**
2. **Then move it** to `90 Archive/`. Archived records keep their metadata and stay searchable on request, but default retrieval excludes them. Archiving is **reversible** — it is a move, not a deletion — and deletion itself follows `System/Governance/Change Control and Preflight.md`, never this step.
3. **A closure that skips step 1 is incomplete — flag it and stop.** "There was nothing durable to promote" is a legitimate outcome, but it is a finding the *human confirms*, never an assumption you make on the way to moving a folder. If you are told to "just archive it", name the step you are being asked to skip, offer the short version (a single lessons note), and move only once they decline explicitly. The reason is asymmetry: the folder can be un-archived any time, but the lesson nobody wrote down is gone once the context is, and closing a project is the last moment anyone remembers it.

## Always
`aios validate` ends the session (plus `links` if references changed). Do **not** run `generate` — indexes refresh at maintenance. Report in one line unless something needs the human.
