---
id: doc-human-user-manual
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture, doc-change-control-and-preflight, doc-privacy-and-boundaries]
version: 1.4.1
created: 2026-07-10
updated: '2026-08-14'
summary: How to live with this system day to day — as its owner, not its engineer. Plain language; no technical background assumed.
---

# Human User Manual

You own this system. The AI operates parts of it under rules you control. This manual covers daily use; the deeper rules it follows live in the documents it cites (see the authority table in `START-HERE.md`).

The release includes connection profiles for **Claude Code and Codex**. A fresh instance is uncertified **L2**: it may make validated low-risk writes, but guided multi-file or structural work needs the stronger evidence and approval gates described by the system. Another runtime is not automatically supported merely because it can open the folder.

## 1. The daily loop

The system earns its keep through a simple rhythm:

1. **Capture** — anything worth keeping goes into `00 Inbox/`: a quick note, a file, something you dictated on your phone. Don't organize it; just get it in.
2. **Work** — ask the AI for what you need. It retrieves the right context itself; you shouldn't have to re-explain your life each time. If you *do* keep re-explaining something, say so — that's a gap worth capturing.
3. **Record what mattered** — decisions, lessons, useful results. Say it out loud if that's easier ("add this context to the pricing decision…"). Spoken context is a first-class source here.
4. **Let the system tidy — when you say so** — ask for inbox processing or the weekly maintenance pass and it handles classification, linking, and freshness. Your job is judgment, not filing. Note the *when you say so*: the system will tell you the inbox is piling up, but it never empties it on its own, because deciding what your raw material becomes is the one job that stays yours.

One idea sits under all of this: **your inbox is a holding pen; your knowledge is what's been checked.** Anything you capture starts as *staging* — raw and unverified, and deliberately kept out of your trusted answers. It becomes part of your real knowledge only once it has earned it: cleaned up, sourced, and connected. The system never quietly promotes a rough note into fact, and never hands you an unverified note as though it were checked. That is why what you rely on stays trustworthy — your vault is the size of what you have *vetted*, not everything you have ever dropped in.

**Your words stay yours.** Drop an AI chat conversation into the Inbox and the system does not treat the whole transcript as you. It measures who actually said what first (`aios measure` computes the word split and flags phrases the AI coined rather than you), reads your side on its own, and builds your notes from *your* claims. Where the assistant restated your idea faithfully, that polish can be kept; where it steered toward a thesis of its own, that idea is filed separately under its real author or dropped — it never quietly becomes a note wearing your name. The full rule lives in the `ingest-and-connect` capability (step 3a). And before any note gets written at all, everything found in a capture is routed in a small table you can review — the **delta register**: each finding becomes a note, a task on *your* list, a question only you can decide, or is dropped with the reason recorded. Most findings are not notes, and the register is where that gets decided cheaply — not after a polished note already exists.

**Word documents are read, not just filed.** Drop a `.docx` in the Inbox and its *text* comes into the vault: `aios extract` converts it to Markdown — headings, nested lists, bold and italic, tables, and images kept where they sat — then **proves the conversion** before letting it in. Every paragraph of the original is checked, character for character, against the result. If even one did not survive, you get no Markdown at all: the original is filed to `Attachments/` with a note saying extraction failed, because a document that lost a paragraph quietly is worse than one you know you still have to read. Whatever the converter cannot take (footnotes, comments) is named with a count rather than dropped in silence. The original `.docx` is always kept, untouched, and the Markdown says where it went. If you explicitly select a document outside the vault, its original path is read-only: the tool copies the preserved original and derivative into contained vault folders and never writes beside or removes the external file.

**Files that arrive together are checked against each other.** When material shows up as a folder — chat exports, a re-download, three versions of the same document — run `aios dedupe-batch <folder>` before anything is harvested from it. It reports how much each file repeats the others: a pairwise overlap table and, per file, how much of it appears nowhere else. This exists because of a real case: of four documents handed over as one corpus, one was **97% a paste-up** of two of the others, and nothing in the system could see it — they shared no title, no id, no alias. The damage is not disk space, it is **manufactured corroboration**: the same claim, read out of three "independent" sources, gets promoted as triply-attested when it was written once and pasted twice. The command **reports and stops** — it never discards anything, because which copy is the fuller record is your call (in that real case the near-duplicate was the *bigger* file). Once you have decided, re-run it with `--annotate` and the overlap map is written into the files you kept, so the next harvest counts the shared material once. This is a different job from `aios dupes`, which checks whether a *new note collides with knowledge you already have*.

**A note that shares its source's title is not a duplicate.** Capture a source, write the note that develops it, cite the source — and the note ends up with the source's name, because that is what it is about. `aios dupes` reports that pair as a **warning**, not an error: the two records are of different kinds, they live in different folders, and one names the other in its `sources`, so there is nothing ambiguous about which is which. You still see the line, because it is worth knowing the pairing exists. What stays an **error** is a collision nothing explains — two notes of the same kind under one title, two records in the same folder, or two same-titled records with no declared link between them, which is exactly the case where you probably did mean one thing and now have two. When you get one of those, the fix is yours: link them if they really are related, rename or alias one, or archive the older. Muting it is not on the menu, and your AI is instructed not to offer it.

**Adding new abilities.** Your OS can be extended with add-on packs — install one by downloading its ZIP, dropping it in your OS folder, and asking your AI to install it (see `Add-Ons and Packs.md`). Updating or removing one is the same simple gesture. Add-ons live in `Packs/` and are yours; they survive version updates.

## 2. What to say — real examples

You talk to it in plain language. There are no commands to memorize; these are just typical phrasings:

- **Capture**: drop a file in `00 Inbox/`, then — *"Process my inbox."* The AI narrates: "team-sync.md → preserved as a source; extracted one decision (dropping the Q3 feature) and one open question; linked to Project Atlas and to Dana."
- **Ask**: *"What did we decide about pricing, and why?"* → an answer naming the decision record it used and, when that record links one, the meeting source behind it. If the vault has nothing: *"Your vault has nothing on that"* — honest emptiness, never padding.
- **Record**: *"Record a decision: we're going with the annual plan. Reason: cash flow. Revisit in January."* → one dated decision record in the top-level `Decisions/` folder, connected to the related project. Settling a choice out loud (*"let's go with option B"*) routes the same way. Decisions never get hand-assigned numbers — the register view in `System/Generated/index-decision.md` is generated (newest first, by project), so two decisions recorded in parallel can't collide, and you cite a decision by its id.
- **Spoken context**: *"Something that isn't written anywhere: the client hates surprises — always preview changes with them first."* → captured, labeled as coming from you, with a confidence level.
- **Produce**: *"Draft the kickoff memo from what we know about Atlas."* → lands in `40 Outputs/`, linked to every record it drew on.
- **Maintain**: *"Run weekly maintenance."* → health checked, stale items flagged, a 5-line list of judgment calls for you — including how much is waiting in the inbox. To actually empty it, say so: *"Process my inbox."*
- **When unsure what it did**: *"Show me what you changed today."* → the journal entries, in plain terms.
- **To-do**: *"Add to my to-do list: review the contract before Friday — the renewal decision is waiting on it."* → one item in `To-Do.md` (at the vault root) that keeps its own context: what, why, what it blocks, and a link that resolves. If you give it a bare "fix the thing," it asks you **one** question — never a quiz — and if a link in your list goes dead, it flags it instead of letting the list quietly rot.
- **Red-team a plan**: *"Poke holes in this before I build it."* → a written pass over your plan in fixed sections: the assumptions holding it up and how you'd know they're false, the failure modes it never names, the cheaper version a skeptic would build, the traps, and the one thing it can't survive — every point citing the line it attacks, and at least one thing your plan gets right. It ends by reminding you what it did *not* do: it tested whether the plan is sound, never whether anyone wants it. It advises; you decide.
- **Start a project**: *"Let's start a project for the garden redesign."* → a folder in `10 Projects/`, a proper project note, and registration so the system can find it. If you brought your own method (§8), your method's rituals govern everything beyond that floor.
- **Ending a work session**: *"Ok, wrap up — we're done for now."* → the AI saves a snapshot of the work and leaves an honest note of where things stopped and what's still open, so a future session (any AI, cold) picks up without you re-explaining. Next time: *"Pick the project back up"* → it reads that note first, double-checks it against reality, and tells you where you left off. Quick Q&A sessions skip the ceremony — no paperwork you don't need. If you brought your own method (§8), the note takes *your* format.

## 3. What the AI may and may not do

- It **always** checks before writing (the "preflight"): does this already exist? what does it affect? Ordinary small things (new notes, typo fixes, links) happen quietly; consequential changes get a journal line; anything structural comes to you first.
- It **may never touch** the protected areas (system rules, schemas, its own permissions, your privacy settings) without your explicit instruction.
- It **never treats its own inferences as facts** — anything it deduced is labeled as inference; anything you told it from memory is labeled with your name and a confidence level.
- Deleting real content is never automatic. The system archives or supersedes instead.
- Every consequential or structural change is written to the change journal (`System/Journal/change-journal.md`), and every risky change has a checkpoint you can restore. Ordinary leaf-level edits stay out of the journal so it remains worth reading.

## 4. Privacy in one minute

Every note can carry four switches: **classification** (public → restricted), **domain** (work / personal / shared), **ai_use** (allowed / local-only / prohibited), and **sync** (allowed / local-only). In compliant filtered retrieval, `restricted` or `prohibited` content is excluded; `ai_use: local-only` content is excluded for a hosted model; `sync: local-only` content stays out of cloud sync or a git push — it must be backed by a `.gitignore` rule, and the validator checks marking and rule agree in both directions (DEC-092). `private` content reaches a hosted model only if you've explicitly approved that model for private material; work and personal don't mix unless you ask. A folder named `Local Only/` applies the same retrieval and storage markings automatically (DEC-065/092), and a misspelled switch fails closed (DEC-066). One caution the validator will also give you: `restricted` removes the note from compliant AI retrieval. If what you actually mean is "keep it off the cloud," use `sync: local-only` (plus `ai_use: local-only` for hosted AI) — not `restricted`. With today's direct-file runtime, these are binding compliance rules, not a physical sandbox: the runtime can technically open any file its OS account can read. Set them during onboarding; adjust anytime. Details: `System/Governance/Privacy and Boundaries.md`.

Be clear about what these switches are: **filing rules your AI obeys, not security walls.** They work per note (whole file), not per line, and they depend on the AI following them. The real rule is simpler: only put into the vault what you're comfortable exposing to your AI. That responsibility is yours (DEC-026).

**Never put passwords, API keys, or other secrets in any note.** The validator scans notes (Markdown only — it does not scan attachments or other file types) and will complain, but it's a backstop, not a guarantee.

## 5. Reviewing the AI's work

- **The journal** is your audit trail — skim it weekly.
- **Stale flags**: when something a note depends on changes, the note is marked `stale` rather than silently rewritten. Stale items and anything needing your judgment surface in the weekly maintenance report.
- **Ripple checks**: edit one note and the system lists every note connected to it until each has been judged — fine, affected, or contradicted. You update one fact; the five notes that reference it don't get to rot silently. Nothing is ever rewritten for you: judged-stale notes are queued for your approval.
- **Review clocks**: a note promoted to real knowledge gets a review date suited to its type (claims sooner, how-tos later). Old notes are grandfathered — nothing you wrote before this feature nags you — and drafts and captures never accrue review debt. If you use a stale note, the system flags it *at the moment of use*.
- **Routines that report themselves**: recurring workflows (weekly maintenance, inbox processing, any you add) record when they last ran, and the health report says when one has quietly stopped. Nothing turns itself on — but now nothing stalls invisibly either.
- **Approvals**: material meant for use outside the vault needs your explicit `approved` mark. If anyone (including the AI) edits an approved item, it drops back to `pending`.

## 6. Maintenance without the burden

You do not need to keep metadata tidy by hand. Run (or ask the AI to run) the weekly maintenance workflow: it finds duplicates and broken links, lists what's due for review, reports what's waiting in the Inbox, and gives you a short list of judgment calls. It does not process the Inbox unless you ask it to — that is a separate word (*"process my inbox"*), on purpose. Ask for a checkup any time, too (`aios checkup`): in one line it tells you how much is still sitting in staging and whether anything was filed as knowledge without being verified — and it never nags, it only answers when you ask. The system's promise is **visible maintenance**: declared relationships, stale items, review obligations, and stalled routines are surfaced for judgment. It does not claim to discover every relationship or automatically keep every note correct. If maintenance ever feels heavy, the system is misconfigured — simplify (fewer fields, fewer reviews), don't push harder.

## 7. When something feels wrong

1. **Stop AI writes**: open `SYSTEM-MANIFEST.yaml`, set `ai_writes_enabled: false`. That's the whole procedure.
2. **Look at the journal** to see what happened.
3. **Restore a checkpoint** if needed — the Maintenance and Recovery Guide walks through it with no technical assumptions.
4. **Set up backup so a dead laptop can't erase your work** — `System/Documentation/Backup and Recovery Options.md` lays out every option (onboarding also walks you through choosing one). Backups you make get recorded (the clone script does it for you; a hand copy takes one command from that doc), and the health check will say plainly when content that never leaves this machine has no recorded copy — it reminds, never nags, and never claims you're covered when it can't know.
5. Your notes are always just files. Any editor opens them. Nothing about this system can hold your knowledge hostage — that's the point of it.

## 8. If you brought your own method

If you told the system how you already work (setup asks once), that lives in one file you own: `80 User/workstyle.md` — your names for things, your tags, your routines, and a binding "never touch" list. The AI reads it before filing or naming anything, speaks in *your* terms, and treats the never-touch list as absolutely off-limits. Edit the file anytime; delete it and the system behaves as if it never existed. Your old notes stay wherever they are unless you ask to bring them in — that gets offered exactly once, during setup, and never again unless you raise it.

### What lives in `80 User/`

Setup **always** creates six files there without you doing anything: `profile.md`,
`privacy-rules.md`, `goals-and-uses.md`, `onboarding-report.md`, and the two state files it uses to
resume if you stop halfway — `onboarding-progress.yaml` and `onboarding-answers.yaml`.

`workstyle.md` is created **only if you have a prior system to describe** — setup asks at stage 4,
and skipping the question means "no prior system"; nothing is created and nothing behaves
differently. Everything in that folder is private by default, and it is the only directory that gets
removed and rebuilt from scratch if this system is ever re-shipped to someone else.

Four more files are **optional hooks**. The system loads each one *if it exists* and does nothing at all if it doesn't — nothing breaks, the routes simply run on the shipped defaults:

- **`voice.md`** — how your outward writing should sound. Loaded whenever the AI drafts anything outward-facing: posts, newsletters, client copy.
- **`authoring.md`** — your standard for how knowledge notes are built: structure, depth, citation practice, when a claim needs a counterargument. Loaded whenever a note is created or updated.
- **`handoff.md`** — your rules for how a working session's stopping point gets recorded. Loaded when a session closes or resumes.
- **`transcript-voices.yaml`** — the speaker labels *your* chat exports use, so `aios measure` can tell your turns from the AI's. Two lines: `human: [your-name]` and, if you need it, `assistant: [whatever-yours-is-called]`. Without it the command still recognises the common labels (`## You`, `## Human`, `## ChatGPT`, `## Claude`); with it, an export headed with your own name is attributed to you instead of vanishing from the count. Every run prints which set it used, so a split is never computed with markers you thought you had replaced.

Setup asks about the first two and writes them for you if you say yes; you can also create any of them yourself, any day, and nothing else needs wiring. Each holds either the rules themselves or a **one-line pointer** to wherever the real standard already lives — never a second copy of it, because two copies of a rule quietly become two different rules. Without them, notes are still written to the system's own shipped standard — never to the AI model's house style — and the patterns in your existing notes refine that standard as your vault grows.

## 9. Growing the system

Want a new kind of note, a new repeatable workflow, a new automation? Tell the AI what you're trying to accomplish — the Extension Builder walks you through it, picks the right kind of component, tests it, and documents it. You never have to design schemas yourself. One rule: extensions are added through that guided process, not by hand-editing `System/` — that keeps everything registered, tested, and recoverable. There's also the optional **Method Kit**: a guided interview that turns how *you* work into your own rulebook the AI follows — offered at onboarding, or run it later whenever you like.

## 10. Checking that your knowledge is really portable

You were told this system doesn't lock you in. You can check that claim rather than trust it. Your knowledge folders are stored in the **Open Knowledge Format** — the open spec Google Cloud publishes for giving AI curated context, currently v0.2: Markdown files with a small metadata block on top. Run `aios okf-check` (or ask the AI to) and it reads your knowledge folders, checks them against Google's rules, and answers in one line, naming the spec version it checked against. A green result means any tool that speaks the format can read your knowledge — including tools that have nothing to do with this product, and tools that don't exist yet.

**It tells you what it read.** The verdict carries its own scope: how many notes were checked, and which folders and packs they came from. That matters because a "conformant" answer over nine notes on a vault holding hundreds is technically true and practically useless — so the count is in the answer, and you never have to wonder whether the check reached the material you care about.

**Installed add-ons are included.** If you've installed an add-on pack, the notes it brought are checked alongside your own — a pack that carries a whole working corpus is knowledge you'd want portable too. What isn't checked is the pack's machinery: its capabilities, agents, workflows and any third-party files it carries under someone else's licence. Those are the pack's equivalent of `System/`, and `System/` isn't checked either. The scope line names both halves, so nothing is silently omitted.

Nothing about this is a conversion step or a special export. Your notes are already in that format as they sit on your disk; the command just confirms it. Point it at any other folder to check that one instead: `aios okf-check <folder>` — an explicit folder is checked exactly as given, with no exclusions at all — and add `--okf-version 0.1` to check something against the older spec.

You may see a *v0.2 advisory* on your own folders. It is not a failure — the newer spec took two words this system already used, `status` and `sources`, and gave them its own meanings. Your folders are still conformant; the advisory just says a stranger's tool reading them raw would read both of them as its own. `aios okf-export` translates both on the way out, which is what that command is for.

## 11. Staying current

When a new version ships, run **that new release's** `upgrade-existing.py` with the absolute path to your existing vault. Never start a cross-version upgrade with the older installed vault's `System/Scripts/aios.py`. The launcher **only shows you the plan** unless you explicitly add the apply flags. It does not make a checkpoint or change a file. The plan prints a review hash—an exact fingerprint of the release, your current system, the baseline, conflicts, migration inputs, and the protected rules that apply. After you read it, run the same new-release launcher with `--apply --confirm --review-sha256 <printed-hash>`. If anything relevant changed after you looked, the hash no longer matches and the upgrade refuses rather than substituting a new plan. Your content, `80 User/`, and customizations are kept; conflicts are surfaced and never merged silently. The review binds exact inputs, while the final candidate bytes are built later inside the recovery-backed transaction—that limitation is shown, not hidden. The full commands are in `System/Documentation/Upgrading.md`.
