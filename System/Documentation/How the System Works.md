---
id: doc-how-the-system-works
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture, doc-system-map]
canonical_for: plain-english-orientation
version: 1.4.1
created: 2026-07-10
updated: '2026-08-14'
summary: The plain-English master explanation — the mental model, the parts, and the complete life of a piece of information. Read this to be able to explain the whole system to someone else.
---

# How the System Works

**Who this is for:** anyone who wants to genuinely understand this system — to use it confidently, explain it, or implement it for someone else. Plain language throughout; the technical term appears once in parentheses so you can find it in the reference docs. **You will be able to:** explain every part of the system and follow one piece of information through its entire life.

## 1. The mental model: a well-run personal library

Picture a private library with a very careful librarian:

- **The folder** (the *vault*) is the library building. Everything is inside it; it moves as one piece.
- **The numbered folders** are the rooms — new arrivals, active work, established knowledge, original evidence, finished deliverables, your personal settings, storage.
- **Notes** are the books: each one a single piece of knowledge with a small label on top saying what it is, how sensitive it is, and what it's connected to (the *metadata*, in a block called *frontmatter*).
- **The AI is the librarian** — it files, cross-references, fetches, and maintains. It doesn't own the library; you do.
- **The house rules** (the *Runtime Kernel*) are the short list of rules the librarian must always follow — about thirty lines, always in force.
- **The switchboard** (the *Task Router*) looks at each job and hands the librarian exactly the playbook that job needs — nothing more. This keeps everyday work fast and cheap.
- **The playbooks** (fourteen *capabilities*) are complete step-by-step procedures for the jobs that cover everything: write safely, find context, take in new material, maintain, recover, extend, bring an existing vault in, manage add-ons, build your own method, close or resume a working session, keep your to-do list alive, start a project, record a decision, and attack a plan before you build it.
- **Specialist staff** (three *agents*) handle three special roles with deliberately narrow permissions.
- **Reliable machines** (the *scripts*) handle everything that should never depend on AI judgment: checking rules, finding broken links, making backups, restoring them, rebuilding indexes.
- **The card catalog** (*generated files*) is rebuilt from the real books at any time — helpful, disposable, never the truth itself.
- **The logbook and the safes** (the *journal* and *checkpoints*) protect changes in proportion to risk: consequential work is journaled, and system/high-risk work gets a checkpoint. Ordinary leaf edits are validated but intentionally do not create paperwork every time.
- **The wall plugs** (*adapters and runtime profiles*) are how a particular AI connects. Claude Code and Codex profiles ship today; another runtime needs an adapter and its own evidence. Obsidian is a recommended viewer, not an AI runtime. The library's durable content does not depend on either.

At the start of a session, the runtime follows one chain: root `AGENTS.md` → `SYSTEM-MANIFEST.yaml` → the manifest's `reading_order.ai` (Runtime Kernel, Task Router, active runtime profile). The router then loads only the procedure for the current task. The larger developer stack loads only when a task changes `System/`, schemas, structure, or components. A fresh runtime instance is uncertified L2; it may do validated low-risk writes, while L3+ must be earned by certification.

## 2. The rooms

| Folder | What goes there |
|---|---|
| `00 Inbox/` | Everything new lands here first. The capture tray. |
| `10 Projects/` | Active, bounded work with goals and stages. |
| `20 Knowledge/` | The current knowledge the system relies on. |
| `Decisions/` | Your decisions — one dated record per settled choice, at eye level on purpose. |
| `30 Sources/` | Original evidence, kept exactly as captured. |
| `40 Outputs/` | Deliverables you produced, linked to what they came from. |
| `80 User/` | Your profile, preferences, privacy rules, setup state. |
| `90 Archive/` | Inactive material, out of the way by default. |
| `System/` | The rules, playbooks, tools, tests, and documentation. |

## 3. The eight kinds of record

User content uses eight record types — enough to distinguish the things that behave differently, few enough to hold in your head. System components have a separate ninth `component` contract; they are not user notes and are maintained through the developer lane:

1. **Note** — a claim, finding, lesson, concept, or question.
2. **Source** — original evidence: a document, webpage, meeting transcript, or something you said. Never rewritten, only annotated.
3. **Entity** — a person, organization, product, or place.
4. **Project** — bounded work with a goal and a stage.
5. **Decision** — what was decided, why, by whom, and when to reconsider.
6. **Procedure** — a repeatable method.
7. **Output** — a deliverable, with its lineage back to sources preserved.
8. **Working** — project working material: a plan, log, capture, draft, or scratch file inside a project's folder. Deliberately light to type, kept out of default knowledge search (it's project *state*, not knowledge), and bound to the project layer — the boundary is checked both ways.

You never pick these yourself unless you want to — the AI classifies during filing, using the blank form for each type (a *template*) and the rules for each type (a *schema*).

## 4. The four privacy switches

Every record can carry four independent settings:

- **How sensitive is it?** (`classification`: public → internal → private → restricted)
- **Whose life does it belong to?** (`domain`: work / personal / shared)
- **May AI use it?** (`ai_use`: allowed / local-only / prohibited)
- **May it leave this machine?** (`sync`: allowed / local-only — storage only: cloud sync, git push, hosted backup)

Practical effects in compliant filtered retrieval: `restricted` and `prohibited` content is excluded, and `ai_use: local-only` content is excluded for a hosted (cloud) AI. `sync: local-only` content stays off every git-based sync channel — the marking must be backed by a `.gitignore` rule, and `aios validate` checks that the two agree, both ways. Work and personal don't mix unless you ask. The two "local-only"s are different switches on purpose: one is about *AI routing*, one about *storage*. Reaching for `restricted` to keep something off the cloud is the classic mistake because it removes the note from compliant AI retrieval (DEC-092). With native file access, these routing rules remain obligations rather than physical confinement; the vault cannot stop that runtime opening another readable path.

**Be clear about what these are:** filing rules the AI obeys — not encryption, not security walls. They apply per file, and they depend on the AI following them (which is verified by tests, and auditable in the journal). The real rule is the simple one: **only put into the vault what you're comfortable exposing to your AI.** That choice is always yours (recorded as decision DEC-026).

## 5. The three sizes of change

Every AI write gets effort proportional to its risk:

- **Ordinary** (new note, typo fix, a link): check for duplicates, use the right form, write, validate. Quiet — no ceremony.
- **Consequential** (changing established knowledge, renaming, anything other records depend on): also check what depends on it downstream, and write one line in the journal.
- **System** (rules, structure, forms, permissions): full stop. The AI loads the full governance stack, creates a restore point, writes an impact report, and asks you first. Always.

The AI picks the lane; when unsure, it must pick the heavier one.

## 6. The fourteen playbooks

| Playbook (capability) | The job it covers |
|---|---|
| **safe-write** | Create or change a record correctly: find what exists first, smallest valid change, validate after. |
| **retrieve-context** | Find the smallest trustworthy set of current records for a question or task — filtered by privacy, freshness, and status. |
| **ingest-and-connect** | Turn raw inbox material into preserved sources and connected knowledge; also captures things you *say* that aren't written anywhere. Keeps the voices straight in conversation sources: your notes are built from your own claims, and an AI assistant's ideas are attributed or dropped — never filed as yours. And it decides cheap before building expensive: every finding is first routed in a small table you can review (the delta register) — note, task, your call, or dropped with a reason — and only what routed to "note" gets built out. |
| **maintain-vault** | The weekly pass: report what's waiting in the inbox, flag stale material, check integrity, rebuild indexes, and give you a short list of judgment calls. It never empties the inbox on its own — that is always your call. |
| **recover** | When something's wrong: stop writes, diagnose, restore a checkpoint, verify, document what happened. |
| **build-extension** | Add a new capability, template, or workflow safely — designed, approved, red-teamed, and tested before it activates. |
| **adversary** | Attack a plan, spec, or scope *before* it gets built — the assumptions holding it up and how you'd know they're false, the failure modes it doesn't name, the cheaper version, the traps, and the one thing it can't survive. Runs when you ask (*"red-team this"*) and automatically before any big build. It advises; you decide. |
| **import-vault** | Bring an existing vault in on an owner-approved plan — nothing dropped, nothing imported unseen. |
| **manage-packs** | Install/update only the exact reviewed ZIP, receipt activation, or transactionally archive and remove an add-on — checkpointed, validated, reversible. |
| **method-kit** | Interview you about how you actually work and generate your own operating method as a pack you own. |
| **session-handoff** | End a real working session with a saved snapshot and an honest "where we stopped" note — and resume it cold later, with the note read first and its claims re-checked against reality. |
| **manage-todo** | Keep the one to-do list (`To-Do.md` at the root) alive: every item carries its context — what, why, what it blocks, and a path that resolves — added with at most one clarifying question, and dead references get flagged instead of rotting. |
| **start-project** | Give bounded multi-session work a real home: a folder, a valid project note, and registration so the system can find it — while plans, handoffs, and gates stay with whatever method *you* use. |
| **record-decision** | Capture the moment a choice settles as one dated record in the top-level `Decisions/` folder — what, why, the alternatives it closed, who decided, when to revisit. Ids are dated slugs; the register view is generated, so decisions never collide over numbers. |

## 7. The three specialists

| Role (agent) | Responsibility | Deliberate limit |
|---|---|---|
| **Onboarding Guide** | Sets the system up for one person, privacy-first, resumable at any point. | Only runs onboarding. |
| **Steward** | Periodic health and freshness audits; produces the maintenance queue. | Recommends; may not destroy anything. |
| **Extension Builder** | Turns a recurring need into the smallest safe addition. | Can't touch core rules or forms without your approval. |

## 8. The reliable machines

The highest-risk machines separate review from apply. Bare `upgrade <release>` is read-only and
prints the semantic plan hash; apply requires `--apply --confirm --review-sha256 <fresh-hash>`.
Pack install follows the same exact-review rule and earns a hash-bound activation receipt. Generate
publishes three separately atomic domains—Generated, tool-owned skill projections, then freshness
registry+ledger CAS—and never treats all of mixed `System/Logs/` as disposable.

One command-line tool (`aios.py`) does everything mechanical, identically every time, no AI judgment involved: **validate** (do all records follow the rules?), **links / dupes** (broken references? duplicates?), **search / read** (privacy-filtered access), **health / review-due / checkup** (maintenance views — `checkup` gives a friendly one-line "state of your core"), **doc-check / doc-commands / doc-audit / doc-paths** (is every component drawn? every command documented? every documented number true? every cited file path real?), **okf-check** (is this folder of notes a valid bundle under Google's Open Knowledge Format? — defaults to your knowledge folders, which are one, **plus the content of any add-on pack you have installed** — and it reports how many notes it read and where, so the verdict never covers less than it sounds like; checks against v0.2 unless you ask for an older spec with `--okf-version`, and always names the version it answered; point it at any directory, including an export, to verify portability yourself), **okf-export / okf-import** (your knowledge travels both ways: export a folder as an OKF bundle anyone can read — the bundle declares which spec version it targets, private, local-only and draft material never leaves, *and neither do references to it*, and every bundle is self-verified by `okf-check` against its own declared version before it ships; import someone else's bundle and it lands as draft evidence for the ingest pipeline, never straight into your knowledge — including their claim that a concept was verified, which stays *their* claim), **measure** (who actually said what in a chat transcript — the word split between you and the AI, and which phrases were the AI's coinages rather than yours; the check you run before harvesting notes from an export, so its framing doesn't end up wearing your name), **import** (bring an existing vault in, by approved plan), **vocab** (banned-term guard), **certify** (one-command product-integrity certification — the mechanical checks plus governance/safety, idempotency, doc-truth, and regression, in one ranked record), **checkpoint / rollback** (make and restore recovery points), **generate** (rebuild the disposable indexes, and emit each capability as a spec-valid Agent Skill under `.claude/skills/` so any skills-compatible agent can read it), **upgrade** (bring this vault up to a newer product release — your notes and customizations untouched, conflicts never merged silently; see `Upgrading.md`), **scaffold / migrate** (create components; upgrade structure safely), **ripple** (a changed note's connected notes, listed until each judgment is recorded), **workflow** (which recurring routines are overdue; `--ran` records a run). Every write command refuses to run when the off switch is off.

## 9. The life of one piece of information

A meeting transcript, start to finish — watch how it enters as *staging* and only earns a place in your trusted knowledge once it has been checked and connected (context is staging; knowledge is canon):

1. **Capture** — you drop `team-sync.md` into `00 Inbox/`.
2. **Check** — the AI searches: do we already have this meeting? (No duplicates, ever.)
3. **Preserve** — the transcript becomes a **source** record in `30 Sources/`, never to be rewritten. If what you dropped in was a Word document rather than text, its *contents* come in too: `aios extract` converts it and then **proves the conversion**, paragraph by paragraph, against the original — and if a single paragraph did not survive, you get no Markdown at all and a note saying extraction failed, because a document that quietly lost a page is worse than one you know you still have to read. The original file is always kept. And if the material arrived as a *folder* of files, they are first compared **to each other** (`aios dedupe-batch`): when one file turns out to be largely a paste-up of its siblings, you are told the percentages and left to decide — nothing is discarded — so the same claim read out of three copies is never mistaken for three independent sources.
4. **Extract and triage** — the findings are listed and routed *before* anything is written: a small table (the delta register) says what each one becomes — a **decision** ("we're dropping the Q3 feature"), two **notes** (a finding and an open question), one new **entity** (the client who attended), an action item routed to your task list, and one aside dropped with the reason recorded. You can review the map; only what routed to "note" gets built out.
5. **Connect** — each new record links back to the transcript and to the related project and people already in the vault.
6. **Compare** — the AI checks what this changes: the decision *contradicts* an older note, so that note is marked stale — flagged, not silently deleted. Contradictions are preserved and linked, never erased.
7. **Label honestly** — what the client *said* is marked `reported` (someone saying X is not X being true). What the AI *deduced* is marked `inferred`. Facts, claims, and guesses never blur. And when the source is a conversation with an AI, the same honesty applies to *whose words are whose*: the word split is measured first (`aios measure`), your notes are built from your own claims, and an idea that originated with the assistant is credited to it or dropped — never filed as yours.
8. **Rest** — ordinary additions happened quietly; the stale-marking was consequential, so it got a journal line.
9. **Use** — weeks later you ask, "what did we commit to the client?" The AI retrieves the decision, names the record it used, and names the source too when the decision record links one.
10. **Produce** — you ask for a proposal draft; it lands in `40 Outputs/`, linked to every record it drew from.
11. **Maintain** — the weekly pass flags the stale note for your call, tells you what's piled up in the inbox (and offers to process it), rebuilds the catalog.
12. **Survive** — if anything ever goes wrong: off switch, restore point, and the journal that says exactly what happened when.

Everything else in `System/` — schemas, tests, adapters, migration tools, certification records — exists to make those twelve steps trustworthy, portable, and recoverable. You never need to touch it; the people who maintain or extend the system do (see the Implementation and Admin Guide).

## 10. Plain words ↔ technical words

The third column is the same idea in the words the AI field uses. It is there so you can place this system against tools and terms you may already have read about. You never need that column to use the system; it is for comparing, explaining, or evaluating.

| We say | The files say | In the field's terms |
|---|---|---|
| the folder / the vault | vault, instance | file-native knowledge base / owned context store |
| main record | canonical record | structured memory / knowledge-graph node |
| label / the block on top | metadata, frontmatter | structured metadata |
| how information compounds | knowledge-compounding | memory enrichment / write-time reconciliation |
| house rules | Runtime Kernel | system prompt / agent policy |
| switchboard | Task Router | context engineering / progressive disclosure |
| playbook | capability | skill / tool use |
| specialist role | agent | subagent / role |
| blank form / form rules | template / schema | schema / data contract |
| the card catalog / rebuildable indexes | generated state | derived index |
| check-before-change | preflight | write-time guardrail |
| restore point | checkpoint | snapshot / rollback point |
| off switch | kill switch (`ai_writes_enabled`) | governance kill switch |
| AI connection | runtime | model + harness (swappable) |
| upgrade procedure | migration | schema migration |
| how-you-work map | workstyle map (`80 User/workstyle.md`) | user preference profile |

Placed on the map the field is drawing, this system sits where three young categories overlap: a **memory layer** (knowledge an AI reuses across sessions), **context engineering** (controlling what enters the window for each task), and **AI governance** (rules for what the AI may read, change, or send). The word the others cannot say is **owned**. Your memory, your rules, and your playbooks are plain files you keep across vendors, not a feature rented inside one AI product.

## 11. If you already have a system

The library adapts to you, not the other way around. During setup — with your permission, read-only — the AI looks at how your existing notes are organized and drafts a one-page map of your method: your names for things, your groupings, your tags and what they mean, your rituals, plus a binding "never touch" list that only you can confirm. You correct the draft; from then on the AI speaks your language ("filed to your Resources") while the standard machinery does the real work underneath. Two rules keep it honest: your never-touch list is absolute, and moving your old notes in is offered exactly once — never pushed. Delete the map and the system behaves exactly as if it never existed.

**If you come from PARA**: Projects → the Projects room, one-to-one. Areas → a lens, not a folder — records get tagged to your Areas and assembled on demand, and the AI still says "your Health area." Resources → Knowledge + Sources (a split you never have to think about; it narrates in your terms). Archives → the Archive room, one-to-one. Zettelkasten, GTD, daily notes, Johnny Decimal, or a method you invented yourself all work the same way — the map records whatever you actually do; no method has to be "supported" by name to work.
