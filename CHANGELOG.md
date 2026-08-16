---
id: doc-changelog
type: system-doc
file_class: canonical
authority: canonical
canonical_for: system-version-history
created: 2026-07-10
updated: 2026-08-16
summary: Version history of this Personal AI OS installation.
---

# Changelog

## [1.64.3] — 2026-08-16 (CI workflow correction)

This patch release corrects the GitHub Actions workflow structure so manual
dispatch is nested under the workflow trigger map instead of appearing as an
invalid top-level key. The release retains the v1.64.2 product behavior and
public-truth work while rebuilding every direct historical upgrade edge for
the new target and adding an exact v1.64.2-to-v1.64.3 bridge. The immutable
v1.64.2 tag and release assets are not moved or replaced.

## [1.64.2] — 2026-08-14 (public truth, onboarding, and release evidence)

The public release now explains the product at the same level of precision as
its implementation. The root entry points and onboarding path name the two
shipped profiles—Claude Code and Codex—without treating a shipped profile as
runtime certification. They distinguish filtered-retrieval enforcement from
the compliance rules followed by a runtime with native filesystem access, and
scope citations, journals, checkpoints, dependency review, and rollback to the
workflows that actually provide them.

The first-run path consistently begins with the isolated `setup.py` flow and
the root operator entry chain. Public architecture, messaging, buyer material,
and accessible text alternatives now ship in an explicitly inventoried
directory. Historical v1.64.1 machine evidence remains immutable and is labeled
as evidence for that release only; target-bound v1.64.2 qualification evidence
is published separately with the release so it cannot create a self-referential
candidate commit. No human testing or external runtime certification is
inferred or claimed.

The documentation generator now excludes the executable migration-manifest
schema from its user-record count, matching the documentation audit and the
eight user-content record contracts. Upgrade support remains direct and
identity-bound: the historical edges now target v1.64.2, and a new exact
v1.64.1-to-v1.64.2 edge preserves the qualified recovery source without
rewriting an already-correct license. The existing v1.64.1 tag is not moved.

## [1.64.1] — 2026-07-28 (recovery identity and legal boundary — DEC-120)

The core remains MIT, while PMM Engine remains a separately licensed product.
The previous documentation incorrectly implied that every add-on inherited the
root MIT license. Pack manifests must now name their own attached license.

Migrations gain an exact `source_distribution` precondition, read from
`system.distribution_id`: `personal-ai-os` for core and `pmm-engine` for PMM.
Missing, unknown, or different values refuse before any transform, and tests
prove the two distributions cannot take each other's edge. Exact-file
transforms may enumerate the known legacy hash and already-correct target hash;
all other bytes block.

The PMM transition is deliberately ordered: attach the existing proprietary
license inside `Packs/pmm/`, point that pack's manifest to it, and declare
`pmm-engine` before any root-license transition. No new commercial terms are
created here; broader commercial rights still require owner/counsel wording.

`SECURITY.md` now names 1.64.1 as the sole supported release and explicitly
marks 1.64.0 and earlier unsupported. Candidate version strings are not support
evidence; the tagged release must carry passing qualification results.

## [1.64.0] — 2026-07-28 (free and open source under MIT — DEC-119)

Personal AI OS is now MIT-licensed. The owner's ruling replaces the all-rights-reserved licence of DEC-010 and the per-person grant added on 2026-07-12.

### Why MIT rather than Apache-2.0

The product was already carrying two licences at once. `LICENSE.md` forbade redistribution while the add-on packs shipped MIT, so a reader of the root file and a reader of a pack got opposite answers about the same folder. MIT resolves that in the direction the packs already pointed. Apache-2.0 would have kept the split and added a patent grant nobody had asked for.

### What the stale wording was doing

The claims were load-bearing rather than cosmetic. §1.5 of the constitution read *"the pricing reflects it: the system is delivered by an implementer"*, and the constitution governs wherever another document disagrees — so that sentence outranked the corrected README and would have been the authority an AI runtime resolved against. The README separately told the reader their copy *"comes from your implementer"*.

The **Implementer role survives**; the exclusivity does not. Installing, migrating, onboarding and handing over remain real work someone may want done for them, and the audiences table is unchanged.

### Licence detection

`LICENSE.md` is now the canonical MIT text and nothing else. GitHub had reported the licence as `Other`: its detector matches the licence body within a small tolerance, and the *"your content is yours"* clause plus a history note more than doubled the file. A project whose entire pitch is that you can take it was showing no licence at all to every tool that looks. Both passages moved to the README's Licence section, where they are likelier to be read.

### Added

- `SECURITY.md` — private reporting. Scope deliberately includes the **governance prose itself**: in a system where an AI runtime obeys documented rules, a rule that can be read to permit what it should forbid is a vulnerability with no code in it. Runtime compliance with the kill switch is explicitly out of scope, being a documented convention rather than a barrier.
- `CONTRIBUTING.md` — the four-command local gate, the baseline-refresh step a contributor will otherwise trip over, and the rule that dated records are never rewritten.

### Deliberately not done

DEC-028's *"commercial legal packaging is out of v1 scope"* stays as written — moot, not retroactively wrong, and §4.8 forbids editing a dated entry to match a later ruling. **The repository stays private.** An MIT grant on a released version is irrevocable for that version, so publishing is a separate act reserved to the owner; branch protection, free once public and absent today, should be enabled the moment it is.

Documentation and licensing only: no schema change, no migration, no new command, no behaviour change. Constitution 2.21.2→2.21.3 with twenty derived documents re-stamped as confirmed unaffected.

## [1.63.0] — 2026-07-28 (citation and claim standards — DEC-118)

The citation rules required a named author, work and year, and forbade invention. All of that held while a live corpus accumulated defects of a completely different shape, found by auditing it against primary sources rather than against the rules.

### What the old standard could not catch

A thinker cited for the position he spent a career rejecting. A framework used in its originator's own vocabulary with his name never mentioned, so the claim could not be checked or traced. A metaphor borrowed from economics whose mechanism has no counterpart in the domain it was carried into. A study measuring attention cited for a claim about reward. And three figures with no primary source at all — round numbers attributed to "studies", quoted most often by whoever sells the remedy they justify.

### Added

- Say what the thinker actually argued, and mark the extension in the same sentence.
- Credit the framework you are using, and say when the rule is contested.
- Make a source's weight visible; a systematic review and an aphorism are not interchangeable.
- Test that a borrowed analogy transfers before keeping it.
- Distinguish what a study measured from what the claim needs.
- Put effect sizes in the sentence.

### Replication hygiene is a sweep, not a list

A standard recording disqualified claims governs nothing unless something checks the corpus for them. Adding to the list is not the fix; finding the existing uses is. A removed claim is recorded as removed, so the gap is not later read as an oversight and refilled.

### Registers of claim, and explanation standards

Empirical claims are held to evidence. Interpretive claims are lenses and do not weaken for lacking a citation — hedging one into vagueness preserves neither honesty nor insight. Category confusion, an interpretive claim in empirical clothing, is the only real defect, and the fix is to restore the register rather than delete the claim.

An arrangement may not be explained by the interests it serves unless the selection mechanism is named. And a note that classifies people states what a legitimate disagreement would look like, since a taxonomy in which the author's position is the only unlisted one has stopped making claims.

`safe-write` 0.7.0 → 0.8.0. Documentation-only.

## [1.62.0] — 2026-07-28 (knowledge notes are written to be learned from — DEC-117)

The shipped note register told every instance that notes are denser and longer-sentenced, that stacked clauses are in-register, and that once a user's corpus exists a runtime should measure it and let the measurements override the defaults. Nothing anywhere asked whether a reader could follow the result.

Those instructions compose into a loop with no exit. A runtime writes dense notes, measures them, reads the averages as a target, and writes to the target. The mean never moves, and every note passes every check. It ran for months in a live vault whose owner reported the notes as dense and difficult to understand, and a runtime rewriting that corpus under the same register reproduced the defect inside one session, hitting the measured averages exactly and reporting compliance.

### The register is rebuilt around one test

A competent reader who does not already hold the framework follows the note once, without rereading. Serious, unhurried and cited, and also explanatory.

Clarity rules added: developed paragraphs as the governing unit; break the sentence and keep the paragraph; unstack the sentence that fuses several claims, which is not a rule against long sentences; state plainly then qualify; define coined or repurposed terms on first use in their own sentence; a concrete within two sentences of every abstraction; sequence so each part is understandable when it arrives; restate at a different altitude but never the same one; a header roughly every 300 words carrying its claim in plain words; read it aloud.

### Measurement is scoped to convention, never to defect

A corpus is evidence of what a user writes, not proof of what they want. Measurement now scopes to convention — citation style, titling, how objections are handled, the user's own vocabulary — and explicitly never to sentence length as a target. Where the measurements pull against the clarity rules, that is a finding to raise with the user rather than a licence to write notes they will struggle to read.

### The outward-voice boundary is corrected

The prior text fenced off the whole voice card at the knowledge layer, which threw out the craft with the marketing. Attention machinery — hooks, cliffhangers, scroll-stopping openers — stays out of a note. Cutting clutter, refusing padding, varying rhythm and reading aloud are about comprehension and hold in both registers.

`safe-write` 0.6.0 → 0.7.0. Documentation-only: no schema change, no migration, no new command, and no behaviour change for any note already written.

## [1.60.0] — 2026-07-28 (the machinery stops failing on things that are not your work — DEC-115)

> **Numbering.** Cut from `mainline` at v1.59.0 / DEC-114 / constitution 2.21.0 with no queued changes
> ahead of it, so **1.60.0 / DEC-115** stands as taken.
> **`1.45.0` / `DEC-100` / `safe-write 0.7.0` remain reserved** for `parallel feature change` and
> were not taken.
> **The constitution stays at 2.21.0, deliberately.** This release adds no command, flag, schema,
> component or fixture and amends no normative section — it corrects what two existing checks
> *classify* as an error. The constitution's only edits here are its own `docgen` censuses, which it
> regenerates from source. Bumping it would have required re-stamping 20 derived documents against a
> version whose normative text is identical, and DEC-105 is explicit that a stamp re-applied without
> a re-read is the failure the stamp exists to prevent. If the owner wants an amendment entry for the
> record, it can be added on top; it is not being manufactured here.

**Two defects, one shape: a check judged something that was never the user's work, and refused a
version bump over it.** Both were found by measurement on live instances, not by a bug report, and
between them they were the only thing standing between three green vaults and their version labels.

### 1. An editor being open blocked every upgrade

`aios upgrade` runs `aios generate`, which writes index files into the vault. Obsidian — running,
watching the folder — reacts by re-saving its own `.obsidian/workspace.json` **inside the same run**.
The DEC-109 content-integrity check fingerprints the user's world before and after, saw that file
move, and reported `CONTENT INTEGRITY FAILURE — 1 user file(s) changed`. The bump was refused as
"gates red".

Measured on all three live instances, 2026-07-27: **no vault open in Obsidian could complete an
upgrade.** The obvious thing for a user to do — leave their notes app open — was the thing that broke
it, and the report told them to roll back a run that had done nothing wrong.

| | |
|---|---|
| Instances that received the v1.59.0 `System/` tree | **3** |
| Instances that recorded the version | **0** |
| Cause, all three | `.obsidian/workspace.json` rewritten mid-run |
| No script writes it (`grep` over `System/Scripts/`) | confirmed — only `import_vault.py`, which *skips* it |
| File stable while the vault sat idle | **36 s**, then changed across a bare `aios generate` |

**The guarantee is unweakened; the scope is corrected.** The check exists so an upgrade can never
silently alter a user's **notes**. `.obsidian/` is runtime application state that this command has
been declared never to touch since v1.0.4 — it is already outside the upgrade *surface*, and
including it in the *verdict* was the inconsistency. Three files are now named as the open editor's
own session state and excluded from the verdict: `workspace.json`, `workspace-mobile.json`,
`workspaces.json` — which panes are open, which file was last active. Nothing a human authored.

Deliberately narrow, and deliberately loud:

- **Everything else under `.obsidian/` is still verified byte for byte** — `app.json`, `hotkeys.json`,
  `appearance.json`, plugin settings. Those are user *configuration*; an upgrade that reset someone's
  hotkeys is still a hard failure. Pinned by test.
- **A real note changing mid-run still blocks**, names the file, and points at the checkpoint. Pinned
  by its own test, seeded to fail against the fix.
- **Excluded is not hidden.** If a session-state file does move, the report names it in its own field
  with the reason, and the headline claim counts it separately rather than folding it in with the
  regenerated skill projections. The scope sentence says what the check now declines to judge.

### 2. `pack-check` errored on the product's own templates

New in v1.58.0, and role-gated to `generic-master`, which is why it surfaced on a role-pack instance
and nowhere else: **31 errors, blocking that instance's version bump.**

Nineteen were `duplicate id 'note-<slug>'` and `'source-<slug>'` across a pack's 22 templates. Those
are placeholder ids — and **the product's own `System/Templates/` uses the identical convention**,
including `procedure-<slug>` **twice**, on which `aios dupes` is green. `aios validate` has exempted
template placeholders since the id rules were written. `pack-check` re-derived the id rules from
scratch and re-derived them without that, so the newest checker reported the oldest convention in the
product as a defect.

**A template's placeholder id is not a malformed id — it is a template.** The rule now has one
definition, `frontmatter.is_placeholder` / `in_template_space`, called by both readers, so it cannot
drift apart again. The recognition is the two things the product already knew: the `<…>` grammar (an
angle bracket is not legal in an id, so a value carrying one is unambiguously an unfilled slot) and
the `Templates` folder (factored out of `validate` **unchanged**, so nothing exempt yesterday becomes
an error today).

**The tolerance is not a blind spot — the check got stricter where it matters.** A placeholder id
*outside* a `Templates` folder is now an error `pack-check` did not make at all before: an unfilled id
in a shipped record is a note nobody finished. Real duplicate ids and real type-prefix violations are
untouched, each pinned by its own test. And a placeholder never enters the pack id index, so nothing
can cite `note-<slug>` and be told it resolved.

The remaining twelve errors were `unresolved wikilink [[]]` — a false description of a fill-in slot.
`[[ ]]` and `[[<the competitor>]]` name nothing; there is no note they could resolve to and nothing is
broken. The frontmatter relation fields have skipped `<…>` for exactly this reason since the command
shipped; the body now agrees with the frontmatter. They are reported as the empty slots they are,
advisory on every role — while a link promising a note that does not exist stays an error on
`generic-master`, pinned by test.

Verified read-only against the live role-pack instance that produced the 31: **31 errors → 0 errors,
22 warnings**, 272 files checked across two packs. Nothing was written to it.

### Census

No new commands, flags, schemas, components or fixtures. Unit tests **624 → 638** (+14).
`System/Scripts/lib/frontmatter.py` gains two shared predicates; `validate` now calls them instead of
its own inline copies, with identical behaviour.

**Additive; no migration.** Both changes can only move a finding from error to warning-or-silent, or
add an error in a place that had none — no vault green today can go red on upgrade.

## [1.59.0] — 2026-07-27 (following the documented path is not a duplicate — DEC-114)

> **Numbering.** Cut from the mainline at v1.55.0 / DEC-110 / constitution 2.17.0. Three previously
> queued release changes landed first, as planned, so **1.59.0 / DEC-114** stands. The
> constitution version did move: cut against 2.18.0, it takes **2.21.0** on top of the 2.20.0 those
> three merges left behind.
> **`1.45.0 / DEC-100 / safe-write 0.7.0` remain reserved** for `parallel feature change` and were
> not taken.

**The product tells you to capture a source, write the note that develops it, and cite the source by
id. Do that, and `aios dupes` called your vault ambiguous.**

The note keeps the source's title, because that *is* its title. Measured on a lived-in personal
instance before anything was changed:

| | |
|---|---|
| Title-collision **errors** reported | **25** |
| Of those, a `source` and the `note` citing it | **24** |
| Accidental duplicates among the 25 | **0** |

Every one of the 24 had distinct ids, distinct `type`, distinct folders, and bodies that differ, and
every note declared `sources: [<the source's id>]` pointing at its own pair. The check compared
basenames and looked at nothing else. `dupes.py` was **byte-identical from v1.30.4 through
v1.55.0**, so this was true of every version ever shipped: the one procedure the system most wants a
user to follow was also the one that reddened their vault.

**A title collision is no longer an error when the colliding records are one declared derivation
lineage** — every record typed, ids distinct, `type` distinct, folders distinct, and the group joined
into a single *connected* graph by its own `sources` / `derived_from` edges. Those are the two
lineage relations in the Metadata and Relationship Dictionary; `related` is association and
`depends_on` is operational coupling, and neither one earns a shared title. Connectivity is what
lets a source → note → output chain pass as one lineage while two unrelated pairs sharing a title do
not.

**It is a warning, deliberately, and not silence.** The pairing is worth seeing even when it is
correct, and DEC-084's convention carve-out already set that precedent: a collision that is
legitimate by design stays visible and never red.

**The citation is required, and that is the load-bearing choice.** The same live vault held one
cross-type collision that is *not* a derivation — a personal to-do list and an unrelated work capture
that both normalize to "To Do", neither citing the other. A downgrade keyed on differing `type` alone
would have silenced a real collision in order to improve a count. It stays an error, which is the
correct verdict on it; the remedy is one line in the owner's own vault, and it is his to make.

Everything the check exists for is still an error, and each one is probed by its own test rather than
asserted: same-type collisions, same-folder collisions, duplicate ids, groups containing an untyped
file, and any pair where nobody cited anybody.

Measured after the change, on a read-only copy of that same instance: **25 errors → 1**, the To-Do
collision, with no new error anywhere else.

Census: no new commands, flags, schemas or components; fixtures 31→32 (`31-derivation-titles`); unit
tests 620→624. Additive — the change can only move a collision from error to warning, never the
reverse, so no vault that is green today can go red on upgrade. No migration.
system_version 1.58.0→1.59.0; constitution 2.20.0→2.21.0.
## [1.58.0] — 2026-07-27 (pack content stops being a blind spot — DEC-113)

> **Numbering.** Cut from `mainline` at v1.55.0 / DEC-110 / constitution 2.17.0 (`53c69f8`),
> taking **1.58.0 / DEC-113 / constitution 2.20.0** and leaving 1.56.0 / DEC-111 to the
> version-bump-lockout branch and 1.57.0 / DEC-112 to the pack-workspace-split branch, both open
> ahead of it. **`1.45.0 / DEC-100 / safe-write 0.7.0` remain reserved** for
> `parallel feature change` and were not taken.

`Packs/` is in `frontmatter.SKIP_DIRS`. **That is correct and it stays** — a pack legitimately
ships its own `README.md` and `CHANGELOG.md`, which would collide with the vault's in `dupes`, and
its ids are its own (DEC-061, DEC-067).

The consequence on a pack-heavy instance was severe. Measured live, 2026-07-27:

| | Files |
|---|---|
| Markdown in the instance | **446** |
| Scanned by `validate` / `links` / `dupes` | **165** |
| Inside `Packs/` and never scanned | **260** |

**A green suite was evidence about the vault around the pack, not about the pack.** Found by hand
in that blind spot: 20 broken wikilinks live for a day, an invalid `type`, two invalid `subtype`s,
an id/type mismatch, 3 duplicate titles, 34 files with no frontmatter — and a **fabricated
attributed customer quote whose own remediation had concluded "exactly one file"**, because the
second copy was inside `Packs/`.

### `aios pack-check`

Reads every `Packs/*/` holding a `pack.yaml`, resolving each pack's ids, titles and links against
**itself plus the vault**, in a separate pass. `iter_markdown` gains an optional `skip_dirs`
parameter whose **default is unchanged**; nothing else passes it.

**DEC-067 is not regressed, and this is the crux.** Pack ids never enter the canon id space,
`dupes` still never collides a pack README with the vault's, and `validate` reports the same file
count. Guarded by test rather than asserted: two packs and the vault all carrying
`README.md`/`CHANGELOG.md` and a colliding id stay clean — plus a guard that **fails loudly if
anyone later removes `Packs` from the default skip set** to make this command simpler.

Severity is role-scoped per DEC-083: errors on `generic-master` (that role means "ships to
customers as it is"), warnings on a `personal-instance` (DEC-082 — the product must not redden a
user's own content forever). Five classes are **never** downgraded: parse failures, id grammar,
duplicate ids within a pack, a pack claiming governance `canonical_for`, and committed secrets. A
pack id that also exists in the vault is a **warning, never an error** — a pack is entitled to its
own namespace. Missing frontmatter is a warning too, or nobody would run the check.

Composed into `health` (so `certify` carries it) with warnings **rolled up as one line** rather
than flooding it.

**It found a real defect in this repo's own shipped pack on its first run.** `obsidian-bases`
vendors kepano's `SKILL.md`, which links to `references/FUNCTIONS_REFERENCE.md` — a path our
packaging had flattened, so both links were dead. Fixed by restoring the layout the vendored file
expects, leaving that file byte-identical.

### Citing across the pack boundary

A vault note declaring `sources: [source-example-…]` into an installed pack was a hard `links`
**error**. So a compliant note that declared its provenance turned the suite red, while a note that
stayed green could not declare it — and the packs instruct users to write exactly those notes.

Adopts the spec's recommended option (a): pack ids are a **secondary index**, consulted only by the
resolver. **Resolution is not membership** — nothing is merged, and `validate`/`dupes` are
untouched. Cross-boundary references are reported so the dependency is visible.

With the §6.3 hardening: **`aios pack --remove` now refuses** when a vault note cites an id that
*only* that pack defines, and names the citing notes. An id the vault or another pack also defines
still resolves after removal and is not a reason to refuse.

### Two separate items, handled separately

- **`links.py:42`** held every filename **with** its extension while the lookup used raw link text.
  Obsidian resolves `[[Guide]]` to `Guide.md`, so a link to a markdown file outside `titles` was
  reported broken while the same link written `[[Guide.md]]` silently passed — **two spellings, opposite
  verdicts, and the passing one bypassed the id/title check.** Its own fix, its own test.
- **`test_pack.py`'s comment** claimed its fixture fails on a duplicate id. It cannot: `Packs/` is
  pruned, so `validate` never sees the pack's copy. It fails on the **id/type-prefix** rule. The
  test and its subject were always correct; the comment described a mechanism DEC-067 makes
  impossible. Corrected.

Census: one new command (`pack-check`, 31→32); no new flags; no schema change; unit tests 570→592.
Additive; no migration. system_version 1.55.0→1.58.0; constitution 2.17.0→2.20.0.
## [1.57.0] — 2026-07-27 (a pack update stops destroying the client's own work — DEC-112)

> **Numbering.** Cut from `mainline` at v1.55.0 / DEC-110 / constitution 2.17.0 (`53c69f8`),
> taking **1.57.0 / DEC-112 / constitution 2.19.0** and leaving **1.56.0 / DEC-111** to the
> previously queued version-bump change. **`1.45.0 / DEC-100 / safe-write
> 0.7.0` remain reserved** for `parallel feature change` and were not taken.

DEC-061 states the pack contract: *"install places the folder; update replaces it wholesale (no
merge, no duplicate); delete removes it leave-no-trace."* That is **correct** for a pack that is
pure vendor scaffold — a capability and a vendored reference file.

It is **destructive** for a content-bearing role pack, which is now the commercial shape. Once a
client's vault is in use, `Packs/<name>/` holds:

| Path | What an update destroyed |
|---|---|
| `01 Messaging Hub/` | canonical positioning, messaging, vocabulary, personas |
| `02 Sales Enablement/` | battle cards, one-pagers, proof library, objection handling |
| `03 Intelligence Hub/` | competitor profiles, reviews, win/loss, market signals |
| `04 Published Assets/` | the record of what the company actually shipped |
| `About Me.md` | the owner's voice profile |
| `06 Claude/Config.md` | the company layer — ICP, vocabulary, connected tools |

**The failure was silent and total, and the command reported success.** Uninstall was worse framed:
"leave-no-trace" was written when a pack held nothing but vendor files, and it actively reassured
the person about to lose their entire corpus.

### `layout:` — three classes of path

| Class | Whose | Update | Uninstall |
|---|---|---|---|
| `scaffold` | vendor | replaced | deleted |
| `workspace` | **user** | **never touched** — not read, not diffed, not replaced | **archived** |
| `seed` | vendor starter content, user's once present | written only where the file is **absent** | **archived** |

**Longest declared prefix wins**, so a pack can carve a vendor-maintained folder out of a user
workspace or the reverse. A path declared in two classes is **refused** — the reading is
destructive and must not be guessed.

### Backward compatibility is the acceptance bar

**An undeclared path is scaffold, so a pack with no `layout:` block behaves bit-identically to
before**: wholesale replace on update, leave-no-trace deletion on uninstall, no scaffold baseline
written. This is asserted directly, and by `test_pack.py::test_update_replaces_never_merges`, which
was not modified.

But **silence must not read as safety**. The plan the user approves now states, in words, which
paths are protected — and when a pack declares none it says so outright: *"this pack declares no
workspace; everything under `Packs/<id>/` will be replaced."*

### An edited scaffold file is never auto-merged

Install fingerprints the vendor's scaffold into `Packs/<name>/.pack-scaffold-baseline.json` — the
DEC-074 mechanism, scoped to a pack. On update, a scaffold file whose hash no longer matches is
**kept**, the incoming version is written beside it as `<name>.incoming`, and it is reported. The
DEC-073 rule `aios upgrade` applies to the core, applied to packs.

The vendor also **never re-seeds**: seeding is decided by whether the *declared path* exists, so a
user who deleted the EXAMPLE files does not get them back.

### Uninstall evacuates

Workspace and seed content is **moved** to `90 Archive/packs/<name>-<date>/`, preserving relative
structure, and the report names what went where. The guarantee that mattered is untouched — no
vendor residue, the vault returns to a clean state — while an uninstall can no longer take the
user's own work with it.

`--purge` is the only route to the old destructive behaviour. It must be asked for by name, it
still requires `--confirm`, and it prints how many files it will take **and how many of those are
the user's** before taking them.

### The version floor is the protection

A manifest declaring `layout:` **must** also declare `min_system_version: '1.57.0'` or newer, and
is refused at the gate otherwise. An older core does not understand `layout:` and would replace the
folder wholesale — but every core has always enforced `min_system_version`, so the declaration is
what stops a workspace-bearing pack installing somewhere that would destroy it.

Census: no new commands; one new flag (`--purge`); `pack-manifest.yaml` gains the `layout` contract;
capability `manage-packs` 0.3.0→0.4.0; unit tests 570→588. Additive; no migration.
system_version 1.55.0→1.57.0; constitution 2.17.0→2.19.0.
## [1.56.0] — 2026-07-27 (a customized instance can record that it upgraded — DEC-111)

> **Numbering.** Cut from `mainline` at v1.55.0 / DEC-110 / constitution 2.17.0 (`53c69f8`),
> taking **1.56.0 / DEC-111 / constitution 2.18.0**. **`1.45.0 / DEC-100 / safe-write 0.7.0`
> remain reserved** for `parallel feature change` and were not taken.

**The product's headline feature failed closed on its best-behaved customer.** `aios upgrade`
refuses to advance `system_version` while any protected path is in conflict. That gate is right and
it stays: a vault must never claim a version whose files never arrived. But "conflict" was doing two
unrelated jobs, and only one of them is a reason to refuse.

Measured live on three real instances, 2026-07-27. All three received v1.55.0's `System/` tree
cleanly. **None could record that it had.**

| Instance | Gates after upgrade | Bumped? | Why not |
|---|---|---|---|
| Personal instance | 25 errors (pre-existing duplicate titles) | no | gates red — **correct** |
| Commercial-role instance | 3 errors (a stale composite census in `README.md`) | no | gates red — **correct** |
| Green customized work instance | **validate 0 · links 0 · dupes 0 · health 0** | **no** | **2 "unresolved conflicts in protected paths"** |

The green customized work instance is the proof, because nothing about it is broken. 318 of the 322 files the release
ships under `System/` are byte-identical. Its two divergences are:

- **`System/Runtime/Task Router.yaml`** — customized, which DEC-073 explicitly permits and DEC-083
  names as the normal condition of a lived-in instance. The router is *by contract* never
  auto-merged.
- **the constitution's `docgen` censuses** — regenerated against its own tree, which
  `aios docgen --check` **requires** it to do, and fails `health` if it does not.

Both are things the product asks the instance to do. Doing either locked it out of every future
version bump, permanently, with no path through the tool. The second is a closed loop: the gate
demanded the regeneration and then treated the result as a disagreement.

### What changed: the gate now asks *why*, not *whether*

A protected-path conflict still blocks — unless it is **accounted for**, by one of exactly three
routes. Each is a recorded reason, not a lowered threshold.

| Route | Meaning | Today |
|---|---|---|
| `sanctioned` | the product itself declares the path instance-owned and never auto-merged | `System/Runtime/Task Router.yaml` (DEC-073/DEC-083) |
| `derived` | the two copies differ **only inside `docgen` regions**, which the instance is required to regenerate from its own tree | any doc carrying a census block |
| `accepted` | a human reviewed the conflict and named it with `--accept` | the escape hatch for a genuine one |

Everything else blocks exactly as before.

The `derived` route is deliberately strict, because it grants a version bump. The file must contain
a real `docgen` region; everything **outside** the regions must be byte-identical; and an unreadable
file is never derived. **One edited sentence next to a census disqualifies the whole file** — which
is what stops this being a blanket exemption for any document that happens to carry a count. The
markers themselves are compared, so adding or removing a whole block is still a real difference.

### The version claim travels with its caveats

Nothing is merged, nothing is overwritten, and nothing is skipped quietly. An accounted divergence
is written into the upgrade report under its own heading, and the manifest's `system_version` line
carries the reason on itself:

```yaml
system_version: 1.56.0       # upgraded from 1.55.0 via aios upgrade — 2 declared divergence(s) kept: System/Runtime/Task Router.yaml, System/Architecture/Canonical Architecture Specification.md (see the upgrade report)
```

A reader who sees the version can see, without leaving the file, that two protected paths
deliberately differ from what that version shipped. **That is the honest form of the guarantee the
old gate was trying to keep** — the point was never that an instance must be identical, it was that
it must not claim something untrue.

### `--accept <path>`, repeatable

The "somebody chose" route. It does **not** merge, overwrite, or resolve the file — the instance's
copy is kept, exactly as today. It records that a human looked at the conflict and decided, so it
stops blocking the bump. Without it the gate had no exit at all, which is what made a legitimate
divergence permanent. An `--accept` naming a path that is not in conflict **warns**, rather than
being ignored, so a typo cannot read as a resolution.

Census: no new commands, schemas, components or fixtures; one new flag (`--accept`); unit tests
570→580. Additive; no migration. system_version 1.55.0→1.56.0; constitution 2.17.0→2.18.0.

## [1.55.0] — 2026-07-27 (the portability check reads the whole folder, and says how much of it — DEC-110)

> **Numbering.** Cut from `mainline` at v1.52.0 / DEC-107 / constitution 2.15.2, and originally
> claimed 1.54.0 / DEC-110, holding 1.53.0 / DEC-109 for `parallel feature change`. It landed
> **third** of the three queued changes that day: `parallel feature change` went first on severity as
> v1.53.0 / DEC-109, `parallel feature change` second as v1.55.0 / DEC-109, so this release
> shifted up one to **1.55.0 / DEC-110** and its back-references moved with it — the branch's own
> instruction, applied in the direction the merge order actually took. Its constitution bump is
> **2.16.0 → 2.17.0**, not 2.15.2 → 2.16.0: the release ahead of it had already amended the
> constitution to 2.16.0, so a second entry at that version would have been two amendments wearing
> one number. **`1.45.0 / DEC-100 / safe-write 0.7.0` remain reserved** for
> `parallel feature change` and were not taken.

**A verdict that does not say what it read is not evidence.** `aios okf-check` is the verifiable
half of the product's portability claim — *"run one command and check it yourself."* Its default
scope was the manifest's content directories, and nothing else. On a vault whose knowledge arrives
through an add-on pack, that is a conformance verdict over almost nothing.

Measured on a live role-pack instance, 2026-07-27, before the change:

| | Concepts |
|---|---|
| Reported by `okf-check` as CONFORMANT | **9** |
| Sitting in `Packs/` and never opened | **236** |

Nine files. The buyer's entire messaging, sales-enablement, intelligence, published-assets and
practice-wiki corpus — 236 notes, the whole reason they bought the thing — was outside the scope of
the portability guarantee it was sold under. The command was not wrong; it was answering a smaller
question than the one being asked of it, and nothing in its output said so.

### The default scope is now the whole knowledge surface

`okf-check` covers the manifest's content directories **and the content of every installed pack**.
The same instance now reports **245 concepts checked**, and reports where they came from.

The covered set is derived as a **complement**, the shape DEC-109's integrity fix used for the same
class of bug: `vaultpaths.PACK_MACHINERY_DIRS` names the pack's machinery — `capabilities`,
`agents`, `workflows`, `components`, `templates`, `schemas`, `migrations`, `tests`, `resources` —
and everything else under a pack is content, by construction. A content folder a pack author
invents tomorrow (`05 PMM Wiki`, `03 Intelligence Hub`) is in scope without anyone remembering to
add it. The trade-off runs one way on purpose: an unlisted *machinery* folder is over-covered and
gets checked as content, which can only make the check stricter. Under-coverage is what produced
the nine-file verdict.

Two things stay outside, each mirroring the vault around the pack: **machinery**, as the vault's own
`System/` is outside the knowledge layer; and the pack's **root files**, as the vault's root files
are. `--target <dir>` is unchanged — an explicit target is checked exactly as given, no pack
discovery, no exclusions, mirroring the spec, which defines none.

### The verdict carries its own scope

The defect DEC-109 named — a report that says *verified* without saying *what* — is the same defect
here, and gets the same answer. The report now states, before any verdict:

- `scope` — the content directories, the number of installed packs, **what each pack contributed**
  (a pack of pure machinery reports `0`, so the reader learns it was looked at rather than skipped),
  and what is excluded and why.
- `coverage_by_tree` — the concept count per folder and per pack tree.
- `verdict` — *"CONFORMANT — 245 concepts across the vault's knowledge layer and 2 installed packs
  (…), valid OKF v0.2"*. The number is in the sentence, so the claim cannot be quoted without it.

This is what makes the marketing claim safe to make. The prose says the command reports its coverage;
the count lives in the command, where it cannot go stale.

### DEC-061 / DEC-067 are untouched, and that is the crux

A pack ships its own `README.md` and `CHANGELOG.md` and its own note ids. Merging those into vault
canon is exactly what DEC-067 forbids, because it reddened `dupes` on every well-formed pack.
Nothing here merges anything: **`okf-check` builds no index at all.** It opens each file alone and
applies three rules to it, so there is no namespace to collide. `Packs/` remains pruned from
`frontmatter.SKIP_DIRS`, and `validate`, `links` and `dupes` see exactly what they saw before.
**Coverage is not canon** — reading a file is not admitting it.

Guarded by test, not by assertion: two packs and the vault each carrying `README.md`, `CHANGELOG.md`
and a colliding id, with `dupes` green, the canon id space free of duplicates, no `Packs/` path in
the canon walk — and `okf-check` reading all of it in the same test.

### What this found, and did not fix

The same live instance is **not conformant**: 245 checked, 183 conformant, **62 violations** — 33
notes with no `type`, 29 with no frontmatter at all — every one of them inside the pack, every one
invisible until this release. That is the finding, not a regression: those files were non-conformant
yesterday too, under a green verdict. Remediating another vault's content is that vault's work.

Census: no new commands, flags, schemas, components or fixtures. Unit tests 562→570
(`test_okfcheck.py` ×7, `test_commands.py` ×1 — the DEC-067 guard). Additive; no migration.

## [1.54.0] — 2026-07-27 (five gaps between what the machinery claims and what it does — DEC-109)

> **Numbering.** Cut from `mainline` at v1.52.0 / DEC-107 / constitution 2.15.2, and originally
> claimed 1.53.0 / DEC-109. It landed **second** of the three queued changes that day, after
> `parallel feature change` (v1.53.0 / DEC-108) was merged ahead of it on severity, so it shifted up
> one to **1.54.0 / DEC-109**. Its constitution bump 2.15.2→2.16.0 is unaffected: the release ahead
> of it did not amend the constitution. **`1.45.0 / DEC-100 / safe-write 0.7.0` remain reserved** for
> `parallel feature change` and were not taken.

**Five defects, one family: a mechanism that reported more coverage than it had.** Each was confirmed
against live source before a line was changed, and each carries a seeded-failure test proved to fail
against the pre-fix code.

### 1 · CI did not run on most working branches

`.github/workflows/ci.yml` used a hand-maintained push-prefix allow-list. Measured against the active
branch set rather than assumed, **the allow-list omitted the prefixes used by most working branches.** So the
push gate was off for almost everything, and the failure was **silent**: an unlisted branch produces
no red X, it produces nothing, which at a glance is indistinguishable from a green run.

**Catch-all (`branches: ["**"]`), not a longer allow-list, and the reasoning is the point.** Adding
today's missing prefixes would close only today's gap and re-arm the identical trap for the next prefix someone
invents — an allow-list of prefixes is a hand-maintained census of a set that changes whenever
somebody types a branch name, which is DEC-105's finding expressed in YAML. The two errors are also
not symmetric: a run nobody needed costs a minute of compute; a branch nobody checked costs a
release. A `concurrency` group is added with it so a branch pushed three times in a minute runs one
matrix, not three — push and change runs land in different groups by construction (`refs/heads/…` vs
`refs/pull/N/merge`), so cancelling superseded pushes can never cancel the check a merge depends on.

### 2 · `aios upgrade` proved a tenth of what it claimed, and reported the whole

The command's charter says user content, `80 User/`, `.obsidian/`, `Packs/`, the canonical journal
and certification records are never touched, and it *verifies* that: fingerprint before, compare
after, any drift a hard failure. The fingerprint walked `manifest.directories.content` plus
`.obsidian` and `Packs` — a hand-maintained list of a set **the user controls**.

Measured on the live work instance where this was found: **160 files fingerprinted, 1,641 in the
tree.** 1,102 of the gap sat in seven content folders that instance had declared in its own
`folder-registry.yaml` — registered user content, every one of them, none of them known to the
manifest key the walk read. Its manifest also predated `Decisions/`, so two more went unseen for a
second reason. The report said `byte-identical (160 files verified)` either way.

**Extended rather than narrowed, because the measurement said extending was free.** The choice was
posed honestly — a claim narrowed to what it verifies is better than a false assurance — but a
full-tree fingerprint of that same 1,641-file / 38 MB vault takes **0.11 s**, twice per upgrade. At
that price there is no argument for verifying less, and a narrowed claim would have left the actual
promise ("your notes are untouched") resting on nothing for 90% of the notes.

The scope is now the **complement** of the upgrade surface, not a list: everything in the tree minus
what the product replaces, minus the two folders the post-upgrade `generate` legitimately rewrites.
That is what makes it unrepeatable rather than merely fixed — **a folder invented tomorrow is covered
the day it is made**, and there is no list to forget to update. It also brought in three things the
docstring had always promised and nothing had ever checked: the change journal, the instance's
certification records, and the user's own root files. Verified against the real vault, read-only:
**1,294 files, 0.25 s** (the remainder is the `System/` surface, correctly excluded). And the report
now states its own scope, because a reader of an upgrade report has no other way to learn what
"verified" covered — including naming the two folders it cannot cover.

### 3 · Every version claim except one was unaudited (GAP-4)

`doc-audit` verified `system_version` and no other version, in a product that bumps a dozen of them a
week and restates them across the doc set. A new **component-version truth key** resolves a claimed
version against the file that declares it: capability `SKILL.md`, agent `AGENT.md`, workflow, schema
`schema_version`, the constitution's own frontmatter, the manifest's `vault_profile_version`.

It found the corpus's densest concentration of these claims immediately: the constitution gives every
capability and agent a section stamped with its version, and **ten of those seventeen stamps were
stale** — `safe-write` at v0.2.1 against a component at 0.6.0, `import-vault` and `manage-packs` at
v0.1.0 against 0.3.0, `retrieve-context` at v0.2.0 against 0.4.2, `steward` and `onboarding-guide` a
minor version behind each. All ten are corrected here, and the gate is what makes the eleventh
impossible.

Two claim shapes are matched — the catalogue stamp and inline `` `name` X.Y.Z `` — and three are
exempt because they are not claims about now: transitions (`0.4.0→0.6.0`, the same rule the
`system_version` check has always used), amendment logs, and the decision register's dated figures
(joining its count exemption; a version is a figure of exactly that kind). Dated provenance is
exempt too — §4.10's *"Source: `safe-write` v0.2.1, shipped in v1.14.0"* records where a passage came
from and stays true as the source moves on.

**What it cannot reach is named in its own report, not implied.** Three classes have no
machine-readable local source: external specification versions (Open Knowledge Format; the Obsidian
plugin versions in the adapter docs), the Python floor and dependency pins (declared as ranges, not
equalities), and documents cited by title rather than by component name. `aios doc-audit` prints all
three every run. A gate that implied coverage it lacked is the defect this release exists to close;
it would be a poor joke to close it by building another one.

### 4 · `doc-paths` exempted the decision register wholesale (GAP-8)

`doc-audit` had already taken the correct position on that file: **count** claims are exempt (a dated
entry's figures were true when written), behaviour claims are not. `doc-paths` skipped it entirely —
a category error, because §4.8 protects a dated *statement of fact*, and a path is not that. It is a
pointer, it is followed by whoever reads the entry, and a dead one is dead in any year.

It was hiding a real one: **`System/Capabilities/manage-packs.md`**, dead since capabilities became
folders at DEC-070, sitting in the very entry that introduced the capability. Repointed at
`System/Capabilities/manage-packs/SKILL.md`. The gate now checks 205 path references, up from 168.

One allowance rides with it, because otherwise the gate is wrong in the other direction: an entry
recording that a file was **removed** necessarily names a file that is gone, and reporting DEC-057's
`System/Documentation/Deferred Backlog.md` as *"stale — moved/renamed?"* would be a false positive
about the one document telling the truth. A path is skipped when the **sentence** containing it says
it was removed — scoped to the sentence and never the line, since a register entry is one 900-word
line and a line-scoped window would exempt every path in it. **The count of what the allowance
skipped is reported** (`paths_exempt_as_removed`): an exemption nobody can see is an exemption nobody
audits.

### 5 · The owner's given name was compiled into the shipped product

`measure.py`'s `VOICE_PATTERNS` carried it as a `human` alternative beside `human`/`user`/`me` — a
personal identifier in a regex, on a master whose manifest declares `instance_role: generic-master`
with *"personal data is PROHIBITED here"*. DEC-106 found it and deliberately left it, because
deleting it is not neutral: a transcript headed with that name would stop being attributed and the
split `ingest-and-connect` step 3a depends on would silently change.

**Owner's ruling: configurable, not deleted.** The shipped vocabulary is now generic, and the user's
own speaker labels live in `80 User/transcript-voices.yaml` — the `80 User/` hook pattern the estate
already uses for `vocab-guard.yaml`, `voice.md`, `authoring.md` and `handoff.md`: loaded if it
exists, absent it the defaults stand and nothing breaks. Two lines (`human: [label]`,
`assistant: [label]`), applied in both export dialects and in the annotation split as well as the
parse, since a marker the splitter cannot see reclassifies the whole file.

Three deliberate properties: labels are **escaped and shape-checked**, so a user's typo cannot
corrupt the marker set; a malformed file is **reported, never fatal**; and every run prints a
`voice_markers` line naming which set it used, because a config silently ignored is worse than no
config — the caller would read a split computed with markers they believed they had replaced.
Documented in the Human User Manual §8, in `ingest-and-connect` step 3a (with the instruction to fix
the hook and re-run rather than patch the number by hand), and in the module itself.

### Also settled with evidence

The **Claude Adapter Guide**'s privacy claim — that `private`-classified content *"stays out of its
context entirely"* while the shipped profile sets `may_process_private: true` — was reported fixed by
one audit and still present by another. **It is fixed**, on `main`, since 2026-07-27 (DEC-105's
stamp-integrity pass). The live sentence now says `private` **does** reach a hosted runtime, names
`allowed_privacy_classifications: [public, internal, private]` and `may_process_private: true` as its
evidence, tells the user the switch is theirs (`may_process_private: false`), and carries a dated
note that the old wording ran from v1.0.0-rc.1. No change was needed; the disagreement is closed by
reading the file, not by another opinion.

Capabilities: `ingest-and-connect` 0.16.0→0.17.0. Constitution 2.15.2→2.16.0; twenty stamped
documents re-stamped. Additive throughout; no migration, no schema change, no new command.
system_version 1.53.0→1.54.0.

## [1.53.0] — 2026-07-27 (a stranger's pack manifest is reported, never raised — and the contract it is held to is now a file — DEC-108)

> **Numbering.** Authored on a branch cut from `mainline` at v1.52.0 / DEC-107, alongside two
> other queued changes, and originally claimed **1.55.0 / DEC-110** on the expectation that both landed
> first. It was **merged first instead** — this is the highest-severity of the three (a crafted
> ZIP could write or delete outside the vault while the gate reported success) — so it was
> renumbered down to **1.53.0 / DEC-108**, the next number actually free above v1.52.0, exactly
> as that branch's own instruction said to do. The two queued changes it was cut alongside land after it and
> shift up by one each. **`1.45.0 / DEC-100 / safe-write 0.7.0` remain reserved** and were not
> taken.

**Found by measurement, not by a bug report.** While measuring OKF coverage, the manifest gate was
read against the two real pack manifests in the estate — and they disagree about shape. PMM Engine
declares a **flat top-level `resources:` list**; Content Engine nests **`resources:` under
`components:`**. `aios pack` assumed a mapping in both places and called `.values()` on whatever it
found, so installing a PMM-shaped ZIP raised `AttributeError: 'list' object has no attribute
'values'` — a Python traceback where a trust boundary was supposed to produce a verdict.

### Both shapes are canonical, because the gate never cared which one it was

The gate's only question about a listed path is *does this exist in the ZIP*. The grouping keys are
documentation for the reader; nothing downstream consumes them. So refusing either shape would have
broken a shipped pack in exchange for no safety, and a mapping-only rule would have rejected PMM
Engine at install with a message about a key it had no reason to write. **`components:` and
`resources:` now each accept a mapping of group → paths, a flat list, or a single string, at the top
level or nested — all four combinations.** The real 278-file PMM Engine ZIP now passes the gate
clean, as does the Content Engine shape.

One valid pack was being rejected for a second reason: a listed path naming a **folder** (PMM's
`"01 Messaging Hub"`) was checked for literal membership in the ZIP's name list, and a ZIP need not
store directory entries at all. A listed path is now satisfied by a file, a directory entry, **or
anything beneath it**.

### The larger half: a stranger's ZIP must never produce a traceback

The list crash was one instance of a class. Auditing the whole gate for shape and type assumptions
found **eleven ways a malformed manifest crashed instead of reporting** — invalid YAML, non-UTF-8
bytes, a manifest that is a list or a bare scalar, a corrupt or password-encrypted ZIP, `depends_on`
as a list, a path entry that is a mapping or a number, a group value that is a number, `resources`
as a bare string, and a nested mapping where a path list belonged. Each now produces an actionable
message, a non-zero exit, and a **provably unchanged tree** — asserted by hashing the vault before
and after in every seeded-failure case, under `--verify` *and* under `--apply --confirm`.

Three were worse than crashes:

- **A ZIP member that escapes the pack folder passed the gate** and was caught only during
  placement — by which point, on an UPDATE, the installed pack had already been deleted and the new
  one half-written. The `RuntimeError` then escaped `run()` entirely, so the **DEC-077 recovery
  never ran** and the vault was left holding a half-installed pack with no rollback. Escaping
  members are now refused **at the gate**, before the checkpoint; placement keeps its assertion as a
  backstop, and any failure during placement now falls into the same DEC-077 recovery as a red
  validate instead of escaping.
- **`aios pack ../../anything --remove --confirm` deleted a directory outside the vault** and
  reported `leave_no_trace: validate green`. Not a crash — the inverse: success reported over
  destruction. A remove target must now be a single folder name under `Packs/`.
- **A duplicate top-level key was silently accepted.** A manifest declaring `kind:` twice was gated
  on the second, which can disable a clause. The note-class schemas have carried this guard since
  the `subtype` defect; pack manifests now carry it too.

### The contract is a file now, not just code

`System/Schemas/pack-manifest.yaml` is new: the manifest's required keys, patterns, `kind`
vocabulary, accepted path-group shapes and path rules, as data. `aios pack --verify` **loads it**
and gates against it, falling back to in-code constants with a warning if it is unreadable, so a
damaged vault can still refuse a bad pack. A test asserts the two never drift.

This closes the gap that let PMM Engine ship `kind: role` — not in the vocabulary, so its ZIP would
have been **rejected at install** — and sit that way for a month with nothing to check it against.

**It deliberately carries no top-level `schema:` key.** `validate.load_schemas` registers any file in
that folder that has one as a note class, which would have invented a phantom `pack-manifest` record
type no note could satisfy. It carries no top-level `fields:` or `required:` either, for the same
reason at one remove — `doc-audit` unions those keys across the folder to count the system's note
fields. Three census derivations that assumed *every file in `System/Schemas/` is a note class* were
corrected to read the `schema:` key instead of the filename: `generate`'s record-type table,
`doc-audit`'s note-class set, and `test_docgen`'s independent count.

**Scope held.** The `layout:` block, scaffold-vs-workspace semantics, and everything else in
`SPEC-pack-workspace-split.md` are **not** built here — that feature is owner-gated and separate.
This schema describes only the contract that exists today, so the spec's block remains a clean
additive change when it ships.

system_version 1.52.0→1.53.0. Unit tests 517→531 (`test_pack.py` 11→25); error/warning call sites
262→270. No migration, no vocabulary change, no behaviour change for any manifest that was already
valid.

## [1.52.0] — 2026-07-27 (the documentation is routed by depth, and the system can be placed against the field's vocabulary — DEC-107)

> **Numbering.** Cut from `mainline` at v1.51.0 / DEC-106 / constitution 2.15.1, with reviewed change
> merged. **`1.45.0 / DEC-100 / safe-write 0.7.0` remain reserved** for `parallel feature change`
> and were not taken.

**This release exists because the work it describes had already been written and had no record.**
The content below arrived on `the documentation-routing change` (reviewed change) carrying no version bump, no
CHANGELOG entry and no register line — shipped prose with nothing saying what it was or why. The
prose is another session's and stands on its merit; the release record, the reconciliation of the two
documents it contradicted, and this numbering are authored here so that `main` never carries content
no document accounts for.

### Documentation is routed by depth, not handed over as a list

`reading_order.human` in `SYSTEM-MANIFEST.yaml` was six paths in no stated order, with **How the
System Works** — the longest document in the human set — sitting third, ahead of the guide that
actually sets the system up. It is now three tiers, and the tier names are the routing:

- **Get Started** — START-HERE → Product Overview → Quick Start → **Human Onboarding Guide** → Human
  User Manual. The quick, plain path, and the onboarding guide moves up into it because setup is what
  a new owner does next, not the fifth thing they read about.
- **Understand It** — How the System Works. The bridge to the reference layer, for the reader who
  wants to explain the system to someone else.
- **Reference** — the canonical and architecture docs, read on demand and deliberately **not listed**
  in the manifest sequence. START-HERE's *Where authority lives* table is their index.

Onboarding stage 1 now names those tiers instead of reciting a document list, in all three parity
documents (Specification, AI Procedure, Human Guide — all three stay at 1.9.0; nothing regressed).
The framing is explicit that **reading is offered and never required, and no stage waits on it** —
without that line, naming five documents at the moment of consent reads as homework.

### The system can be placed against the vocabulary the field is using

**How the System Works §10** — the plain-words/technical-words table — gains a third column, *In the
field's terms*, and a row for **how information compounds**. The column is scoped in its own opening
sentence: it is for comparing, explaining or evaluating this system against tools the reader has read
about, and **you never need it to use the system**. The section closes by placing the product where
three young categories overlap — a **memory layer**, **context engineering**, and **AI governance** —
and names the word the other three cannot say: **owned**. Plain files kept across vendors, not a
feature rented inside one AI product.

The **Glossary** gains the four field terms that closing paragraph depends on — *context
engineering*, *context store (owned)*, *governance (AI governance)*, *memory layer* — each defined by
what this system concretely does rather than by the category label, so the register cannot be read as
a claim to be those products. The **Product Overview** gains the one-line framing the onboarding
stage now speaks aloud: *a second brain stores what you know; this stores what you know, how it
connects, and how the work actually gets done on it.*

### Two documents contradicted the change and are reconciled here

Reordering the manifest is not free, because two places had written the old sequence down:

- **`START-HERE.md`'s *Reading order* section** still ran Product Overview → Quick Start → How the
  System Works → Human User Manual, and **omitted the Human Onboarding Guide entirely** — so the one
  place a human meets the reading order disagreed with the manifest that defines it. It now states
  the three tiers and says it matches `reading_order.human` exactly.
- **The constitution** described the list twice: §2.1 called it "flat" (true of the YAML, misleading
  about the structure) and §8's dependency-6 row enumerated the six paths in the superseded order.
  Both now read from the manifest. Constitution 2.15.1→2.15.2; twenty documents stamped against it
  re-stamped as confirmed unaffected, verified by searching all twenty for prose that states a
  reading sequence — none does.

**The gate lesson, recorded because it is the second of its kind in two releases.** No check went
red on either contradiction. The dependency row's **count** was right (six) and its **set** was right
(the same six files); only the **sequence** was stale, and `doc-audit` audits counts, not order.
DEC-105 closed the "whole classes of countable fact have no truth key" gap; this is the adjacent one
— an enumeration whose membership is checked and whose ordering is not is a half-audited claim.

Prose and one manifest key only: no schema, no migration, no behaviour change, no new command, no
count moved. Documents versioned: How the System Works 1.2.0→1.3.0, Product Overview 1.2.1→1.3.0.
system_version 1.51.0→1.52.0.

*(Release record authored at merge for reviewed change's content, which shipped without one. The prose changes
are `the documentation-routing change`'s; the numbering, the two reconciliations, the amendment and this
entry are the merge's.)*

## [1.51.0] — 2026-07-27 (the shipped product stops naming the owner's employer — DEC-106)

> **Numbering.** Cut from the mainline at v1.50.0 / DEC-105 / constitution 2.15.0, after the
> preceding reviewed changes merged. **`1.45.0 / DEC-100 / safe-write 0.7.0` remain reserved** for `parallel feature change`
> and were not taken.

**The manifest has said `instance_role: generic-master` — *"personal data is PROHIBITED here"* — since
the master was reset to a clean generic seed, and the shipped tree contradicted it in five places.**
This release is prose and fixture data only. No schema, no migration, no behaviour change, no count
moved. It is listed as a release rather than folded into a docs sweep because it acts on a verbatim
owner ruling and because half of it is a decision *not* to edit.

### The rule this release applies

A provenance claim exists because it is evidence: *this feature was tested on real material, at this
size, on this date.* Anonymizing such a claim must remove the **identity** and keep the **evidence**.
Every rewrite below was checked against that test, and where a sentence would have lost its meaning
anonymized it was reworded rather than deleted. Nothing was silently dropped.

### What was rewritten (five live-prose sites)

- **Constitution §0.2** listed the out-of-scope instance vaults by name — five of them, one a real
  company. The scope statement never needed the names; it needed the **kinds**, and now states them:
  the owner's personal instance, the commercial instance, the work instance, and the disposable test
  and proving scaffolds.
- **`System/Scripts/cmd/import_vault.py`** credited its two modes to a named employer migration of
  1,095 files and a named personal-vault migration of 426. Both now read as a lived-in work vault and
  a lived-in personal vault — **with both file counts intact**, because the counts are the proof that
  the modes were exercised on real corpora before the command existed.
- **`System/Scripts/cmd/dupes.py`**'s convention-basename docstring attributed the case to a named
  method on a named vault. It now describes the case that actually justifies the rule — a method
  mandating a per-project `HANDOFF.md`, two projects, two handoffs, found on the first fully-synced
  live instance run on v1.30.x — which is strictly more informative than the name was.
- **`System/Tests/scripts/test_commands.py`**, two docstrings: the same convention case, and F-1's
  supersede-and-archive regression. The second **keeps its commit hash** (`5d7782a`); a hash is a
  pointer to evidence, not an identity.
- **`System/Tests/fixtures/27-intake-dedupe/input/make-fixture-batch.py`** used the owner's real name
  as one of the five short boilerplate lines. It is filler standing in for a byline, so a placeholder
  byline serves identically; the fixture's five-line count and its `expected.md` are unchanged.

### What was deliberately left alone, and why

**Dated evidence is never rewritten (§4.8).** The `CHANGELOG` entries below this one, `System/Journal/
change-journal.md`, `System/Tests/results/`, `System/Migrations/` records, and the decision register's
own DEC-050 / DEC-052 / DEC-084 entries all still name the instances they were written about. Each was
true when it was written, and rewriting release history to remove a company from it is precisely the
falsification the estate's rules exist to forbid — the same rule that kept Appendix E's snapshot
figures intact at v2.12.1. **These remain in the shipped tree, and the owner should know that: the
scrub is of live prose, not of history.**

**The licensor's own identifiers stay.** `LICENSE.md`'s copyright line, the repo URL, `pack.yaml`
`source:` fields, and the README attribution are correct as they are — a copyright line naming nobody
is not a copyright line.

**One hit is reported rather than decided.** `System/Scripts/cmd/measure.py` carries the owner's given
name as one alternative inside a speaker-label pattern in `VOICE_PATTERNS`, beside the generic
`human` / `user` / `me` forms. It is not provenance prose and it is not the employer's name, and
removing it changes how a real transcript
is measured — a behaviour change no ruling in hand authorizes. Left for an owner call. If the answer
is "remove it", the better fix is to make the human-voice alternatives user-extensible from
`80 User/`, the way `dupes` conventions and vocabularies already are, rather than to hard-code a
second name.

### Scope of the sweep

The inventory was rebuilt from the shipping tree rather than inherited: the employer's name, the
owner's given name and surname, both of his account handles, and `/Users/`-style absolute paths
carrying a local username — case-insensitively, across every
tracked file — markdown, YAML, Python, SVG, fixtures, `Packs/**`, `.github/`, `.obsidian/` and the
committed generated state. **Twenty-four occurrences in twelve files; zero in `Packs/**`; zero
absolute paths carrying the local username.** Two of the rewritten sites (the journal-adjacent test
docstring and the fixture byline) were not in the record that raised the question, because that scan
was scoped to a pack.

Constitution 2.15.0→2.15.1; twenty derived documents re-stamped as **confirmed unaffected** — verified
by searching all twenty for the removed identifiers, not assumed (the v2.12.1 precedent). system_version
1.50.0→1.51.0.

*(Executes the owner's verbatim ruling of 2026-07-27, "Scrub the employer's name from the shipped
product," on the inventory raised as hits 4–10 of `RECORD-pmm-remediation-2026-07-27.md`.)*

## [1.50.0] — 2026-07-27 (the doc-truth gates can see what they were blind to, and the censuses are emitted rather than typed — DEC-105)

> **Numbering.** Cut from `parallel change line` (v1.49.0 / DEC-104 / constitution 2.14.0), which
> is open as reviewed change and unmerged — **this release merges after it**. So: 1.50.0 / DEC-105 /
> constitution 2.15.0. **`1.45.0 / DEC-100 / safe-write 0.7.0` remain reserved** for
> `parallel feature change` and were not taken.

**Every gate was green while the defects they exist to catch sat in the tree.** That is the finding
this release acts on, and it has one cause repeated six times: the checks could not see the notation,
the file types, or the classes of claim where the drift actually lived. Nine documentation fixes
below were caught by the upgraded gates rather than by reading, which is the only real evidence that
a gate upgrade worked.

### The gates

**`doc-audit` could not read number-words above twenty.** Its vocabulary was a hand-listed scatter
(…twenty, twenty-five, twenty-six, thirty, thirty-nine, fifty, seventy); every other word-number
returned `None` and was skipped **without even being counted as a claim checked**. The constitution
writes almost every census heading in exactly that notation — *"the thirty-eight validate rules"*,
*"the eighty-four unit tests"* — so the document that most needed auditing wrote its figures in the
one form the auditor could not parse. Replaced with a parser over 0–99, the range the corpus uses
(the highest word-number in the whole doc set is *eighty-four*).

**And it demanded strict adjacency.** `9 **AI** playbooks` — the README's second line, wrong for the
third time — has one word between the number and the noun, and that was enough to hide it. The
matcher now tolerates up to two intervening tokens **but only acronyms**: a lowercase modifier
narrows the set ("two concurrency flags", "four governance fields" are true of a slice of a larger
whole), and a gate that reddens on true subset claims is a gate people learn to ignore. Three
related blind spots fell out of the same work: the number token was `[a-z]+`, so *"the **product**
ships six capabilities"* bound `product` and — because a regex scan does not overlap — swallowed the
real claim behind it; identifiers now disqualify themselves (`DEC-070`, `30-folder-rules`, `00–90`
are names, not counts); and a table whose header names a version or a date is read as history.

**It globbed `*.md` only — no YAML, no SVG.** The always-loaded `Task Router.yaml`, the atlas's
`diagram-metadata.yaml` and all 44 diagrams were unscanned, and six of the highest-severity findings
of the 2026-07-27 audit lived in exactly those three file types. Both are now in scope. `svg_text`
blanks non-text nodes to spaces rather than removing them, so a reported line number points at the
line a maintainer will open. The atlas also writes its counts backwards — a box labelled
`Capabilities (7)` beside a list of seven while fourteen shipped — so the trailing-parenthetical form
is matched too, plural nouns only (`the CLI-surface diagram (22)` is a number, not a census).

**Whole classes of countable fact had no truth key.** Added: unit tests · error and warning messages ·
authority-marked files · components · schemas · libraries · documentation files · script modules ·
note-class templates · typed relationships. A probe asserting **999 unit tests** used to pass every
gate. The message extractor documents how it counts, because two obvious methods are both wrong: a
plain grep for `rep.error(`/`rep.warn(` misses the three modules raising through a `_sev(rep)`
severity switch (DEC-083), and a receiver-name match additionally misses the two `certify` raises
through sub-reports named `hsub`/`vsub`. It walks the AST and counts every `.error(…)`/`.warn(…)` on
any receiver plus every `_sev(rep)(…)` — every message a user can be shown. `components` reuses
`doc-check`'s own enumerator rather than introduce a second definition of one number.

**Nothing checked that prose described current *behaviour*.** No count is wrong in *"the weekly pass
drains the inbox"* — the description is. DEC-101 executed the owner's ruling that Inbox processing is
manual and user-directed; the retired promise survived in eleven documents for ten days and in the
Task Router for twelve more. A banned-phrase guard now fails on the retired wording unless it is
negated **before the phrase and on the same line**. Both halves are load-bearing: *"…drains the inbox
automatically with no user consent"* puts its negative word after the phrase and is the exact
sentence the rule exists to catch, and a window reaching into neighbouring lines reads one Task
Router row as an exemption for the row below it. **Deliberately not built on `aios vocab`**, which the
audit proposed: `vocab` is user-owned configuration (`80 User/vocab-guard.yaml`) scanning user content
at warning severity and never scanning `System/` — this polices the product's own prose and must be
an error on the master. Building it inside `doc-audit` also means it inherits the YAML and SVG
scanning above, which is where the surviving instances were.

**`x_reviewed_against` failed open, and could be re-applied without a re-read.** `health` skipped any
stamp whose source declared no `version:`, so three shipped stamps were permanently dead — one of
them is why a Certification Battery naming the **wrong adversary fixtures** shipped with
`derived_docs_behind: 0` on the board. `validate` now errors on a stamp that cannot resolve, and
`health` learned to resolve YAML registry ids (`op-registry` is `operations.yaml`) so the one
legitimately versioned non-markdown source resolves rather than failing closed. `validate` also errors
when a stamp's own `updated:` predates the `updated:` of the source version it claims — arithmetically
impossible unless the number was bumped and the file never opened, which was true of **twenty-two
shipped stamps**. The honest escape hatch is deliberate and costs nothing: leave the stamp at the
version you really reviewed and let `health` report the doc as behind. **A stale stamp is a true
statement; a fresh one you did not earn is not.**

**`docgen` shipped a builder that returned zero.** `block_capabilities` globbed the flat
`Capabilities/*.md` form retired at DEC-070 and returned *"the 0 capabilities"*. Nothing used it, so
nothing noticed — and wiring the README to it before this fix would have replaced one wrong number
with a worse one. Its test asserted `len(glob("Capabilities/*.md"))` — zero — appears in *"the 0
capabilities"*, so the test agreed with the bug and passed. Fixed, plus builders for the seven
generated censuses and three single-number counts, and `docgen` learned to fill a block **inline**
when the author wrote the markers on one line, because a mid-sentence count cannot be block-generated
without breaking the sentence.

### The documentation

**`README.md` advertised 9 AI playbooks against 14** — the second line of the sales pitch, wrong for
the third time. It is now three inline `docgen` blocks generated from disk; a fourth recurrence is not
possible.

**The Task Router promised an automatic Inbox drain**, in two comments, in the file every runtime
loads, which is a protected object. The same rot survived in `svg/17`, two `diagram-metadata.yaml`
entries, and the constitution's own §5.14 — which contradicted its DEC-101 amendment 1,579 lines
further down the same file. All corrected; a tree-wide sweep found two legitimate remaining uses and
both were reworded so the negation sits in the same sentence.

**The onboarding agent was forbidden from performing onboarding's own mandatory first action.**
`prohibited_actions: modifying anything under System/` against a Specification whose stage-1
connection proof *requires* writing and removing a scratch file under `System/Logs/` — a failed write
is how a read-only mirror is detected. **The contract was wrong, not the spec:** a runtime that
refuses the proof fails at step one of the one process it exists for. Two named carve-outs, nothing
else. Its `capabilities_used` and `writes` also gained what the router's own row already loaded.

**The Certification Battery named the wrong adversary fixtures** (29/30; they are 28/29, and 30 is
folder-rules) — a certifier following it runs the wrong test and skips the seeded-flaw eval, the exact
theater failure DEC-099 exists to prevent. Two fixtures appeared in **no level at all** and would
therefore never have run: `15-addon-install`, the DEC-077 regression for the hole that once reported
`[rollback] OK` over a fully-installed broken pack, and `method-kit-generation`.

**Diagram 03 drew 7 of 14 capabilities; diagram 22 drew 13 of 32 commands and 6 of 9 generated
artifacts** while `CATALOG.md` claimed the missing commands were "covered by" it. Both redrawn; the
catalog now claims only what a reader can check by opening the file. The atlas status table stopped at
diagram 38 while 44 were registered, and three range statements in the same file disagreed.

**Overstated privacy, twice.** `capability-profile.yaml` said hosted "therefore private/local-only
content is excluded", and `Claude Adapter Guide.md:15` said `private` content *"stays out of its
context entirely"* — both against `claude-code.yaml`'s shipped `may_process_private: true` (DEC-025).
The adapter-guide sentence has been there since v1.0.0-rc.1 and a prior audit dropped it as
unreproducible; it reproduces.

**`check_coverage.py` does not exist and never has** — yet `PIPELINE.md` (an `authority: canonical`
file) told an implementer to run it at step 2, and `coverage.yaml` and `diagram-metadata.yaml` both
credited it. The real gate is `aios doc-check`. Its `--emit-md` claim that "the catalog cannot drift"
went with it: the catalog's tables are hand-maintained, which is exactly how diagram status rows went
stale unseen. `PIPELINE.md` also shipped another product's internals into the generic master —
removed, closing DEC-057's recorded follow-up.

**Three community plugins ship and the policy said none** — notebook-navigator, obsidian-git and
dataview, one of which is sold as a headline backup option two documents away, against
*"Adopted plugins: none."* Each is now recorded with its purpose and its loss-if-removed, per that
file's own rule 5.

**`aios rollback` cannot restore a zip** — `checkpoint.py` errors with *"zip rollback is manual by
design"* — but the Automations Reference and the Implementation Guide both read as though it could.
That is the row a user reads mid-incident on a no-Git install.

**`Decisions/` was missing from every orientation listing** (`System Map`, which additionally still
filed decisions under `20 Knowledge/`; `START-HERE`; the README's what's-in-the-box block), and so was
`To-Do.md`, despite both being routed since v1.39/1.40.

Plus: the Portable Vault Profile's type-prefix list was missing `working-` (in a protected file, with
a hard-erroring validate rule behind it); Change Control listed 6 protected objects against the
manifest's 11, omitting `System/Runtime/`; the manifest's own
`default_autonomy_for_uncertified_runtimes` read `L0` against DEC-026's `L2`; Versioning and Migration
called `--dry-run` "default-safe" for a command that applies unless it is passed, and described a
`System/`-only surface for a command that also owns four root files; the Metadata Dictionary
documented a `decay` field that exists in no schema; `aios.py`'s docstring listed 29 of 32 commands;
`operation-mapping.yaml` carried build-phase residue on three shipped operations; and the onboarding
progress template stamped `spec_version: 1.4.0` into every new vault against a spec at 1.9.0.

### The censuses

Seven constitution sections stop being transcriptions and become generated blocks: §6.8, §8.2, §8.3,
§9.1, Appendix D, and Appendix E's two tables. §8.5 has argued for exactly this since 2026-07-14, was
approved, and was never executed; it is executed now, and its diagnosis is left standing as the
argument for the next census someone is tempted to type. §8.4's drift-control table — a current-state
verdict that had stopped being current — is re-derived in both directions: two controls reported gaps
that had closed, one declared dead a check DEC-091 built, and `doc-truth` was recorded as unable to
fire while live `certify` lists it passing.

**Tests.** 29 new across `test_doc_audit.py` (the word-number range, the acronym gap and the subset
rule, identifiers, dated tables, every new truth key, the behaviour guard's four cases, SVG
line-number fidelity), a new `test_stamp_integrity.py` (fails closed · cannot predate · rollback is a
legal answer · user content is advised never blocked · registry ids resolve), and `test_docgen.py`
(the capabilities builder, against the shipped folder form). Census: unit tests 488→517; truth keys
20→30; no new commands, schemas, components or fixtures. Additive; no migration.

## [1.49.0] — 2026-07-27 (three safety commands stop lying about what they do — DEC-104)

> **Numbering.** Taken off `mainline` at v1.48.0 / DEC-103 / constitution 2.13.0 after a fetch,
> so this is 1.49.0 / DEC-104 / constitution 2.14.0. **`1.45.0 / DEC-100` remain reserved** for
> `parallel feature change` and were not taken.

**Four defects with one shape: a command's stated contract and its code disagreed, and the document
was the thing being trusted.** All four were confirmed against live source before anything was
changed — including one the report got wrong, which is recorded rather than quietly absorbed.

**`aios certify` could never pass on a personal instance.** The PII check's own comment had said
*"this is a master-only invariant; personal instances legitimately hold PII"* since the day it was
written, and the code never read `instance_role`. It therefore fired on every vault: a real personal
instance produced **34 errors, every one of them a legitimate colleague's work address**. The
product's own certification command was unreachable for the people the product is for. It is now
gated on `instance_role`, exactly as `doc-check`, `doc-paths` and `doc-audit` already are (DEC-083),
on DEC-082's doctrine — the product's rules go red on the product, never on the user's own content.
An absent or unreadable role stays **strict**, so a test scaffold and the master both fail closed.

**The same command was not read-only.** Its idempotency probe runs `aios generate` twice and restored
only `System/Generated`. But `generate` also baselines notes into `System/Logs/freshness-ledger.json`
— a **tracked** file on a personal instance — so the composite gate the estate runs to assert
soundness was quietly rewriting the vault it was assessing, and every "read-only audit" claim that
rested on it was false by exactly that much. The probe now preserves and restores a named
`PROBE_SIDE_EFFECTS` set (the ledger, the freshness event log, the freshness registry) and *deletes*
anything it created that had not existed before. The generic master never activates freshness, which
is exactly why release prep could never see this.

> **A correction to the report.** The defect was filed against `aios health`. `health` was checked
> the same way — a whole-tree hash before and after — and is **genuinely read-only**; it contains no
> ledger writer at all. The mutation came from `certify`, which the same audit ran seconds later.
> The distinction matters because "which command may I safely run on a working vault?" is the
> question the claim exists to answer. `test_read_only.py` now asserts both, so neither answer
> depends on anyone's memory again.

**`aios checkpoint` swept work it did not own.** A bare `git add -A` on a working tree three sessions
shared committed other agents' in-flight files into unrelated commits, under a label that mentioned
none of them — it made a record written as *"nothing committed, that stays his call"* false
twenty-seven seconds after it was written. **The design choice, and why:** checkpoint is the
estate's safety net and is deliberately exempt from the kill switch, because *you can always save
state*. A checkpoint that can refuse to save is not a safety net, so refusing is **not** the default
and the default still commits everything. What is gone is the *silence*:

- the **commit message enumerates every path the commit contains**, and the report returns the same
  list as `committed_paths` — so a checkpoint can never again be a misleading record of what it holds;
- **`--paths <files or folders>`** commits only what the caller declares, leaving everything else
  exactly where it was and naming it in `left_uncommitted`;
- **`--strict`** refuses and explains when anything outside the declared scope has changed, pointing
  at `--paths` and `--zip-only` — the mode for automation running on a tree it does not own.

**A canonical doc claimed a write that no code performs.** The Metadata and Relationship Dictionary
said the *"validator maintains the reciprocal `superseded_by`"*. `validate.py` contains **zero
writes**; its only supersession code is a warning. A runtime that believed the doc left every
supersession chain dangling while the gate stayed green. The doc now states the truth — the link is
**authored**, by whoever performs the supersede, per `safe-write` — and **`validate` was deliberately
not given write behaviour**: a validator that repairs what it validates cannot be trusted to report
on it. A sweep for the same class across the entire doc set found four more, all now corrected:
the Automations Reference presented **approval reset** as machinery (nothing in `System/Scripts/`
reads `approval` and rewrites it, and nothing even *detects* a missed reset), overstated journal
appends and auto-checkpoint as universal when only `migrate`/`import`/`upgrade`/`pack` perform them,
and carried a blanket header telling the reader they trigger none of it; the Glossary said promotion
sets `review_due` *automatically* when only `aios review-due --set-missing` ever writes it. Rows that
are rules a person or an AI performs are now marked as such.

**Tests.** New `test_read_only.py` — every fix carries a seeded failure, and all of them were proved
to fail against the pre-fix code and pass against this one: `certify` clean on a personal-role
fixture and still erroring on a master-role one, whole-tree byte-identity for both `health` and
`certify`, a ledger that did not exist before the probe still absent after it, and `checkpoint`
disclosing / scoping / refusing. New `System/Tests/scripts/scaffold.py`: a fixture must **state** its
`instance_role`, never inherit the host vault's — that inheritance is why the doc-gate severity and
`upgrade` tests could not pass whenever the suite ran from a personal instance, which is precisely
what `certify`'s regression dimension does on a real vault. Census: flags 42→44; unit tests
472→488. No new commands, schemas, components, or fixtures. Additive; no migration.

## [1.48.0] — 2026-07-26 (the OKF surface follows the standard to v0.2, and says which version it answers — DEC-103)

> **Numbering — resolved.** This release was built alongside `parallel feature change`
> (`1.47.0 / DEC-102 / constitution 2.12.1`) and deliberately took the *next* slot,
> **1.48.0 / DEC-103 / constitution 2.13.0**, so the two could not collide whichever landed
> first. **The preceding change merged first on 2026-07-27, so nothing here moved** — this release sits on top of
> 1.47.0 exactly as numbered. **`1.45.0 / DEC-100` remain reserved** for `parallel feature change`
> and were deliberately not taken — the estate has now had eight numbering collisions, and a held
> gap is cheaper than a race.

**Google published Open Knowledge Format v0.2 on 2026-07-24, and every OKF claim in this product
was pinned to v0.1.** The claim was still *true*, which is exactly the failure the standing rule
names: a claim must not read stronger than the evidence, and "conformant with the open standard"
is read as the current one.

**What v0.2 actually changed** (read from `okf/SPEC.md`, commit `780fe9d3`, not from a summary).
Two supersessions, each with a sanctioned fallback: `timestamp` → `generated: {by, at}`, and the
body `# Citations` list → the `sources` frontmatter field. Four new optional families: provenance
(`sources` entries with `resource`/`id`/`title` plus the credibility signals `author`,
`usage_count`, `last_modified`, and a `usage_window` sibling), trust (`generated`, and `verified`
as a list of `{by, at}` events), lifecycle (`status: draft|stable|deprecated`, `stale_after`), and
attestation (`type: Attested Computation` with `runtime`, `parameters`, `computation`, `executor`,
`attester`) — under an actor convention, `human:<id>` / `process:<id>` / `<producer>/<version>`.
**Conformance itself did not change**: v0.2 §11 carries the same three rules as v0.1 §9, so a
conformant v0.1 bundle is a conformant v0.2 bundle and one code path serves both.

**The version is now a stated fact, three times over.** `--okf-version` on `aios okf-check` and
`aios okf-export` (default **0.2**); the emitted bundle declares its target version in the root
`index.md` frontmatter (the §12 marker), in its `okf.yaml`, and in its index prose; `okf-check`
names the version in its verdict; and the export self-gates by running `okf-check` **against the
version it claims**. `--okf-version 0.1` still emits the old shape, unchanged.

**Two AI OS field names are now OKF field names too.** `status` (different vocabulary) and
`sources` (different shape). The export maps the first into OKF's three values and keeps the vault's
own under `x_aios_status`; it rebuilds the second as OKF entries for records that are actually in
the bundle — where `resource` can be a path a consumer can follow — and keeps the raw id-list under
`x_aios_sources`. `review_due` maps to `stale_after`. Reading a vault's folders raw, `okf-check`
reports the collision as **one rolled-up advisory**, not one warning per note, and never as an
error: §11 forbids rejecting a bundle over an optional family.

**What this release refuses to emit is the substance of it.** `verified` is **never** emitted:
this vault records a verification *grade* (`verified | corroborated | reported | inferred |
unverified`) with no actor and no date, while v0.2 records verification *events*. Synthesising
`{by, at}` would fabricate both halves of a trust signal, so every exported concept sits — honestly
— in the spec's lowest trust tier, and the grade rides under its own name. `generated` is emitted
only with an operator-asserted `--author`, because `generated.by` is required inside it and the
vault does not record who wrote a note; without it the last-change time rides as the legacy
`timestamp` that §13.1 tells consumers to fall back to, and the run says so. No Attested Computation
is ever authored: this system has no attestation machinery, and inventing one to look conformant is
the failure being closed.

**Two defects found on the way and fixed here rather than filed.** (1) **`okf-check` had never
implemented conformance rule 3** — the reserved files were skipped outright since v1.25.0 while the
command printed a three-rule conformance verdict. Rule 3's structural MUSTs are now enforced in both
versions: frontmatter in an `index.md` only at the bundle root and only for `okf_version`, and ISO
8601 date headings in `log.md`. (2) **The privacy fence covered content but not references** — a
vault id is a slug of its record's title, so `entities: [person-jane-doe]` carried a name out of a
bundle whose subject note the filter had excluded. All seven id-list fields and both single-id
fields are now filtered to records that may themselves travel, with the withheld count reported.
Related: an unrecognised `status` now fails closed on export (DEC-066 reaching a branch that had only
a blacklist — the v0.2 mapping would otherwise have laundered `status: Active` into `status: stable`).

**On import**, v0.2's families land verbatim under `x_okf_generated`, `x_okf_verified`,
`x_okf_status`, `x_okf_stale_after`, `x_okf_sources`, with anything else a producer wrote preserved
under `x_okf_extra` (so an Attested Computation's whole contract survives). A bare `verified`
mapping is read as a one-element list, as §5.2/§11 require. Their `stale_after` becomes this vault's
`review_due` — the one v0.2 lifecycle field with a true equivalent. Their `verified` **never** raises
this vault's `verification`: the bundle cleared their gate, not this one.

**The honest competitive read, recorded because the marketing rested on it.** Provenance and
verification are no longer differentiators — v0.2 makes them first-class, and on verification
*events* the spec is ahead of this product. What still distinguishes AI OS is **authority** (which
document wins when two disagree), `supersedes`/`contradicts`, privacy classification, governed
determinism, and the kill switch. The buyer-facing docs now say that rather than the old line.

**Proof**: Google's own four published bundles — 53 concept documents — verify conformant with
**zero** advisories and import with every v0.2 family intact; the round trip is measured from the
**original note to the landed note**, because a comparison that starts at the emitted bundle cannot
see a loss introduced on the way out; planted privacy markers cover all six exclusion paths plus all
nine reference fields. Recorded in `System/Tests/results/okf-v02-conformance.md`; the 2026-07-16
v0.1 record stands unedited as the dated evidence it is. Unit suite 428 → 472. Census: flags 40→42;
no new commands, schemas, components, or fixtures. Additive; no migration.
## [1.47.0] — 2026-07-26 (the runtime-errors census, re-extracted — and the atlas catches up — DEC-102)

**A count nobody could check drifted for five releases. The fix is the extractor, not the number.**

- **Appendix D re-extracted (closes DEC-086's flagged pass).** The constitution's error-and-warning
  census had read *129 distinct messages across 19 modules* since before `okf-*`, freshness,
  `upgrade` and `pack` existed. v2.4.1 saw it, declined to guess, and wrote down that it needed "a
  fresh extraction, not a guess." This is that extraction: **241 `rep.error(…)` / `rep.warn(…)` call
  sites across 31 modules**, computed by AST walk. Nine command modules had no row at all
  (`upgrade`, `pack`, `okf-check`, `okf-export`, `okf-import`, `ripple`, `workflow`, `measure`,
  `extract`, `resolve`, `dedupe-batch`); `validate` alone had grown 27→38 and now agrees
  one-for-one with the §6.5 rule table v2.12.0 resynced.
- **The method is now part of the record.** A plain `grep -c 'rep\.\(error\|warn\)('` returns
  **235** and is wrong for exactly three modules: `docaudit`, `doccheck` and `docpaths` raise
  through a `_sev(rep)` severity switch (master = error, instance = warning, DEC-083), so their
  call sites are invisible to text matching. Appendix D's extractor note now says how to count, so
  the next pass reproduces the number instead of re-deriving the method. `checkup` is recorded as
  the one command module that raises none of its own — it composes other gates.
- **Appendix E deliberately untouched.** It is an explicit first-draft / v1.17.0 snapshot; its
  `Error messages | 112` cell is a true historical figure, not a stale one (§4.8 — historical
  records are true when written and never rewritten to match now). Correcting it would have been
  the error, not the fix.
- **Gate-blindness named, not closed.** `doc-audit` has no `error messages` truth key — which is
  precisely why this drifted five releases in silence, and why `validate`'s 27 sat next to a
  source carrying 38. Adding the key is a build; it was not improvised into a docs release.

**The atlas catches up with two behaviours it still drew the old way.**

- **Diagram 08** drew eight note classes and its `<desc>` said "one of eight" — `working`
  (DEC-096) was missing. Added as a ninth box with a caption stating what makes it different
  (project material: plans · logs · captures · drafts · scratch; project layer only, outside
  default retrieval). Canvas 272→312; no existing box moved or narrowed.
- **Diagram 14** drew the pre-triage ingest flow — the gap the CATALOG had been carrying as a
  written follow-up marker since v1.38.0 shipped triage (DEC-093). **Triage → delta register** now
  sits between Extract and Connect, with the four outcome families (Knowledge · Action ·
  Governance · Nothing) stated before the nine effects. Re-laid out as two rows of three at 168px
  rather than squeezing six boxes into one row — the boxes got **wider**, not narrower, so no
  label was shortened to fit. Canvas 332→452. CATALOG's follow-up marker removed.
- **Verified already correct, changed nothing:** diagram **31** (weekly maintenance *reports* the
  Inbox, never drains it — fixed at v1.46.0), **41/42/43** (manage-todo, start-project,
  record-decision — checked line-by-line against their capabilities, including manage-todo's
  "one list at the root, per-project is future scope"), and **44** (adversary gate).

Constitution 2.12.0 → 2.12.1 (amendment v2.12.1, count corrections only); twenty derived docs
re-stamped as confirmed unaffected — no derived doc carries an error-message count. Docs and art
only: no schema, no migration, no folder change, no behaviour change.

## [1.46.0] — 2026-07-26 (folder rules move into the procedures that run them — DEC-101)

> **Numbering — the 1.45.0 gap is deliberate, not an error (resolved on merge, 2026-07-26).**
> This release landed exactly as claimed: **1.46.0 / DEC-101 / `safe-write` 0.6.0**, merged into
> `main` at `a3d3724` (v1.44.0) with zero conflicts. It **skips 1.45.0 / DEC-100 / `safe-write`
> 0.5.0**, which are held for `parallel change line` — a parallel session's live branch
> that is stale at `1.43.0` / `DEC-098` (both taken by `parallel feature change`) and was told in writing,
> in the previous merge pass's record, to renumber into 1.45.0/DEC-100. The reservation was kept at
> merge time because that session is active and may already be acting on it; taking 1.45.0 here would
> have been a live collision, and the estate's five-collision history is why the gap is cheaper than
> the race. **Nothing enforces version contiguity** — `certify`'s release-integrity gate only requires that
> the manifest not *lag* the CHANGELOG — so the gap costs nothing mechanical.
> **If a future reader finds 1.45.0 still missing:** the note-clarity branch landed elsewhere or was
> abandoned. The gap is then permanently cosmetic. Close it by leaving it alone and reusing neither
> number — do not renumber shipped releases, and do not read the hole as a lost decision.

**A rule lives inside the procedure that is running when the rule matters. Anywhere else it is
decoration.** The `_ABOUT.md` signposts in all eight content directories were the **only** home of three real operating
rules — the Inbox's ~20-item threshold, promote-lessons-before-archiving, and *folders stay flat* —
and **nothing loads them**: not one Task Router row references any of the eight. A runtime could
follow every procedure it was handed and still break all three, which is exactly what happened: the
owner's live vault grew three Knowledge subfolders, one of them created *by the session that was at
that moment diagnosing unloaded rules*. Same failure shape as DEC-063 (a user standard nothing
routes to) and DEC-091 (an onboarding question nobody asks), now closed for the folder layer.

**The sorting table came before the surgery.** Every sentence in all eight files was classified
*description* (stays) or *rule* (moves), with an old-location → new-location mapping for each rule,
written and reviewed before a line was edited — the audit trail that proves nothing was lost in
transit. **52 sentences: 17 description, 35 rule** — of which **28 were already stated in a loaded
procedure** and were deleted as duplicate copies (two copies of a rule become two different rules,
and they diverge silently because both keep looking correct), and **7 relocated** into a procedure
that did not carry them. The full table ships in the merge record.

- **The Inbox threshold is now a prompt, and only a prompt** — the owner's verbatim ruling of
  2026-07-15: *"Inbox processing should never be automatic. It should be manual and user directed."*
  Written into `ingest-and-connect`, `maintain-vault` step 2, the `inbox-processing` workflow (new
  §0) and `weekly-maintenance` step 2, and the Steward's first duty. Past ~20 items the runtime
  **reports the count and offers** the workflow, then stops. `cadence_days: 7` means the workflow
  *reports itself due*, never that it runs. **No scheduled task may drain the Inbox**, and a general
  "tidy up my vault" / "do the maintenance" is explicitly **not** the yes — the drain decides on the
  user's behalf what their raw material becomes, which is the one judgment staging exists to keep in
  their hands.
- **Lessons before archive** — `safe-write` gains an **Archiving (including closing a project)**
  section whose step *order* is the rule: durable lessons are promoted to `20 Knowledge/` and listed
  for the user before anything moves to `90 Archive/`. Working material (`type: working`) never
  graduates as-is; what graduates is the knowledge the project produced. Step 3 makes a closure that
  skips it a **flagged incompleteness** — "there was nothing durable to promote" is a finding the
  human confirms, never an assumption made on the way to moving a folder. Mirrored in
  `maintain-vault` step 3 and the Steward's project-state duty.
- **`20 Knowledge/` and `40 Outputs/` stay flat** — into `safe-write`'s folder-decision step, and
  **extended to `40 Outputs`** per the owner's third ruling. Meaning lives in metadata and links,
  because a folder tree is a second taxonomy carrying exactly one axis and the note belonging under
  two headings has to pick. **Project affiliation is tags plus the project note as its own index**,
  with the reverse view generated from frontmatter relations — and explicitly **no new index type**:
  a second index is a second thing to drift. The same step now also carries the `derived_from`
  requirement for every `output`, which had no procedural home at all.
- **The eight `_ABOUT.md` files are human signposts** — one paragraph each, no rules, `authority:
  derived` unchanged. What was description and lived nowhere else moved with it: the `80 User/` file
  inventory to **Human User Manual §8** (which had previously deferred *to* the `_ABOUT`), and
  **pointer discipline** to the **Onboarding Specification** stage 5 (1.8.0→1.9.0) where the
  standards files are actually written — both the spec and the AI procedure had been *citing* the
  `_ABOUT` as the source of a rule nothing loaded.
- **One line of enforcement** — `aios validate` reports subfolders under the two flat-filed
  directories as **one rolled-up warning and never an error**. DEC-082 binds: a lived-in vault never
  goes red on the user's own content. **The user declares a subfolder deliberate by putting an
  `_ABOUT.md` in it** — the same signpost this release redefines, rather than a new marker — after
  which the folder is silent permanently; `Local Only/` is a privacy fence, not a taxonomy, and never
  warns (DEC-065). Existing subfolders in any instance are **that instance's** to resolve; the
  product reports and never force-flattens.
- **Surfaced, not improvised** — the spec required this finding rather than a guess: **project
  closure has no single home.** There is no close-project capability, no router row, and no workflow;
  closure happens as a `safe-write` move, which is where the rule was put. A dedicated closure route
  remains an owner call and was deliberately not invented here.
- **Tests** — fixture **`30-folder-rules`** (three probes: a 21-item seeded Inbox draws a prompt and
  no drain until an explicit yes; closure names the lessons step and a skip is flagged; the flat
  folders hold by persuasion) joins the L3 battery, plus `test_flat_folders.py` (12 tests) pinning
  where the warning fires, where it is silent, and that it is never an error.
- **Census reconciled from source, not from the previous number** — constitution §6.5's heading read
  *twenty-eight* validate rules over a 28-row table against a `validate.py` carrying **37** live
  rules: DEC-092's sync-boundary rules and DEC-066's universal governance check had shipped without
  ever reaching the table. Recounted and the ten missing rows added rather than the heading alone
  corrected (the v2.10.0 precedent for commands and flags). §6.5 is now **thirty-eight**; §9.2
  fixtures 30→31.

Constitution 2.11.0 → 2.12.0. Capability versions: `safe-write` 0.4.0→0.6.0, `ingest-and-connect`
0.15.0→0.16.0, `maintain-vault` 0.2.0→0.3.0; workflows `inbox-processing` and `weekly-maintenance`
1.1.0→1.2.0; agent `steward` 1.1.0→1.2.0; Onboarding Specification 1.8.0→1.9.0. Additive prose plus
one advisory check — **no migration**, no folder renames, no registry change, no new schema, and an
instance that never creates a subfolder sees no change at all.

*(Executes SPEC-about-rules-relocation, owner-approved 2026-07-25, which itself executes three
verbatim owner rulings of 2026-07-15. The spec counted seven `_ABOUT.md` files; there are eight —
`Decisions/_ABOUT.md` arrived with DEC-095 on 2026-07-25 and is covered here.)*

## [1.44.0] — 2026-07-26 (the adversary pre-build gate + the deferred onboarding mentions — DEC-099)

> **Numbering, resolved on merge (2026-07-26):** this branch was built assuming the parallel intake
> bundle held `1.43.0` / `DEC-098` / fixtures `27–28`. That branch merged first and in fact used
> fixtures **26–27**, so this release kept `1.44.0` / `DEC-099` as claimed and its fixtures moved
> `29–30` → **`28–29`**; its constitution amendment moved `2.10.0` → **`2.11.0`**, since the intake
> bundle's amendment took 2.10.0.

**The plan gets attacked before the build spends the money.** Staged as a design since 2026-07-12
and never built (SPEC-adversary-gate, owner-approved 2026-07-25), while this system kept proving its
value by luck: plans that shipped at a third of their filed scope once somebody re-read them
honestly, rules that were false the day they were written, expensive work run before a cheap
decision that would have cancelled it. Each of those was an adversary pass that *happened*. This
makes it a step.

- **NEW `System/Capabilities/adversary/`** — the fourteenth capability, and a **capability, not a
  standing agent**: the cheapest true form is ephemeral execution over a durable procedure (the
  QA-harness precedent), so there is no new agent contract and no new authority. The report has
  **five fixed sections** — load-bearing assumptions each with *how we'd know it's false* · failure
  modes the plan doesn't name · the cheaper version a skeptic would build · scope traps and hidden
  dependencies · the plan-killer, named singly and ranked first. **Every finding cites the line it
  attacks and states its own falsifier** (a finding with no falsifier is a generic objection in a
  costume). Verdict: exactly three — *proceed · proceed-with-amendments · redesign* — and a
  proceed-with-amendments that lists no amendments is `proceed` with hedging. Two honesty rules:
  attack the work never the author, and **name at least one thing the plan gets right**.
- **Wired as a gate, or it is decoration.** `build-extension` 0.1.0→**0.2.0** gains step **3b**:
  every High-tier build (a new schema, template, capability, agent, script, workflow, or a
  structural change) owes a pass **before anything is created**. A skip is recorded in the build's
  plan — *"adversary gate skipped — owner OK, \<date\>"* — because a skip is the absence of
  evidence, never a pass. Low/Medium changes are deliberately ungated: a gate that fires on a typo
  fix is a gate people learn to ignore. The verdict **advises and never blocks**; a build against a
  `redesign` verdict is recorded, not refused.
- **The report is working material.** `type: working`, subtype `log` (DEC-096's class, its first
  external consumer), filed beside the plan — `10 Projects/<Name>/`, or `00 Inbox/` when there is no
  project folder yet, and **never** `20 Knowledge/`. Findings the build rejects get one line saying
  why, appended rather than deleted.
- **Routed twice, on purpose.** A `red-team-plan` `normal:` row carries the on-demand trigger
  ("red-team this", "poke holes in this"), and the developer lane's `_all` load carries the gate.
  *The on-demand row goes beyond the spec's stated minimum, deliberately:* DEC-094 and DEC-095 both
  record the same failure — a capability nothing routes to becomes the next forgotten convention —
  and without a row the fallback would have sent "red-team this" to `answer-question` and produced a
  chat opinion instead of a filed report. **This was found by the eval, not by review** (see below).
- **The evals are the point, and they are permanent.** A red-team pass is unfalsifiable by nature, so
  the capability ships with a bar rather than a promise. `28-adversary-seeded-flaw`: a plausible
  user-written plan with exactly three planted defects — a false assumption (a scheduler this product
  does not have), an unnamed failure mode (a digest that mails vault content off-machine with no
  privacy fence), and an unconsidered cheaper path (the top rung of the component ladder reached for
  on the first move) — **3/3 or FAIL**, with the gate required to fire before construction.
  `29-adversary-retrodiction`: a real plan from this product's own history, read **cold**, whose
  post-hoc correction is on the record — because a pass that finds only planted flaws is theater with
  a scorecard. Both join the L3 battery. If they are ever dropped, the honest replacement is five
  questions on a checklist inside `build-extension`, and the capability says so about itself.
- **The eval found a defect in the capability, before the capability shipped.** The first
  retrodiction run disclosed partial contamination: `adversary/SKILL.md` illustrated its own doctrine
  with the very case fixture 29 uses, and SKILL.md is loaded on **every** pass — so the procedure was
  handing the eval its answer. The file is now deliberately unillustrated (the cases live in the
  constitution's amendment log), the fixture's run sheet fences the recorded answer, and a
  **leak-regression test** fails if an illustration ever returns. The same run reported the missing
  router row.
- **Designed for the second customer, not built for it.** Pointed at an incoming *pack* instead of a
  plan, the same five reads are the pre-install trust scan. That framing is deliberately **not**
  built here; the capability is shaped so it can be added as an entry framing rather than a second
  engine.

**Also in this release, and unrelated — the DEC-062 onboarding trio takes its two deferred mentions.**
v1.39.0 and v1.40.0 each deferred an onboarding mention because parallel branches held the
parity-locked trio; both branches have merged, so the mentions land now, together, with the scripted
parity proof. **Stage 4** names the root `To-Do.md` while the user is looking at the first jobs they
just described — the routed home for work items, with a **single** offer to capture one as a first
item and nothing seeded silently. **Stage 8** gives the decision review's amendments a stated home:
they are written to the top-level `Decisions/` folder via `record-decision`, and the boundary is said
out loud while both registers are in view — `System/Governance/Active Decisions.md` is the *product's*
register, read and cross-referenced, never written to, because product updates overwrite it. This
closes a dangling pointer: the review already promised "a new dated decision" and never said where.
Onboarding Specification 1.7.0→**1.8.0**; Human Guide and AI Procedure re-derived and re-stamped;
Quick Start and the Implementation and Admin Guide re-read against the new spec and re-stamped.

Diagram **44** (adversary pre-build gate) joins the atlas; `test_adversary.py` adds 25 unit tests
(structure, wiring, and the two anti-disarm regressions); constitution **2.10.0→2.11.0** (components
18→19, capabilities 13→14, routes 19→20, atlas 43→44, fixtures gain 28 and 29 — and §9.2's table
picks up `24-small-fixes`, which the previous merge pass left unlisted). Additive throughout: no
schema change, no migration, no new `aios` command. Existing instances gain a capability, a route,
and a gate on builds they choose to run.

## [1.43.0] — 2026-07-26 (the intake bundle: verified document extraction + intake-batch overlap — DEC-098)

> **Numbering note, resolved on merge (2026-07-26):** `parallel change line` also
> claimed 1.43.0/DEC-098 — both branches were cut from `56028e8`, where 1.42.0/DEC-097 was the
> highest on origin, so neither could see the other's claim until both existed. This branch merged
> first and **keeps** 1.43.0/DEC-098; `parallel feature change` is the one that must renumber
> (to the next free slots above whatever is on `main` when it lands).

**Two owner-approved specs (rulings 2026-07-25), one release, because they are two halves of one
defect: what arrives is not understood, and what arrives *together* is not compared.**

- **`aios extract` — the product can read a Word document (SPEC-doc-extraction).** Until now
  `ingest-and-connect`'s final line routed every non-Markdown file to `Attachments/` plus a pointer
  note: correct for a photograph, silently destructive for a document — the file survived, the ideas
  inside it never entered the vault. Proven on ~648,000 words of `.docx` that had to be hand-converted
  in a throwaway script, differently each session. Now `.docx` → Markdown from the **standard library
  alone** (`zipfile` + `xml.etree`; python-docx would be a second third-party dependency against the
  PyYAML-only floor), preserving heading levels, list nesting **and numbering**, bold/italic runs,
  hyperlinks, tables, and images written beside the original and referenced **at their true position**.
- **The verification gate is the feature, not a nicety.** After converting, every text-bearing
  paragraph of the source is proved present in the output, character for character, and the counts
  appear in the report on every run. **A failed proof emits no Markdown at all** — the original is
  filed to `Attachments/` with a pointer note that names the failure. There is deliberately no
  best-effort mode and no flag to add one: the defect being closed is not "the converter is
  imperfect" but "its losses are invisible", and invisible losses land in the one layer the system
  exists to protect. Footnotes, endnotes and comments are reported **with counts**, never dropped in
  silence; text-box prose is extracted with the honest caveat that a floating frame's position cannot
  be expressed in Markdown. Originals stay immutable and are named in `original_location`; the
  derivative is born `status: draft` and re-enters the pipeline at step 1 as an ordinary capture. A
  document under a `Local Only/` path keeps its original and images **inside that fence** (DEC-065).
- **`aios dedupe-batch` — the files arriving together are compared to each other
  (SPEC-intake-dedupe).** `aios dupes` is the *canon* checker: it compares records to what the vault
  already holds, by id, title, and alias. Nothing compared **incoming files to one another** — and
  material arrives as folders of overlapping exports. Proven live: of four documents handed over as
  one corpus, one was **97% a paste-up**, reproducing 95% of one sibling and 49% of another under
  literal `Tab 1`/`Tab 2` markers. The four shared no id, no title, and no alias, so every shipped
  check passed them cleanly. **The damage is not wasted disk — it is manufactured corroboration:** an
  extraction pass finds one claim in three "independent" sources and promotes it as triply-attested
  when it was written once and pasted twice. Detection is normalize → hash → pairwise matrix (no
  model, no new dependency, seconds over 648k words): shared count plus the percentage of **each**
  side, because one number hides which file was absorbed whole, plus every file's unique
  contribution. Paragraphs under eight words are **excluded from the matrix and counted separately**,
  so boilerplate never reads as corroboration.
- **A report, never an action.** It never discards, and the constraint is arithmetic rather than
  timidity: in the proven case the near-duplicate was the **superset**, so "keep the biggest" would
  have been right by accident and wrong in general. It reports percentages and refuses to classify —
  near-duplication is a spectrum and the verdict is the human's. After they decide, `--annotate`
  writes the overlap map into the surviving sources' frontmatter as `x_overlap_*` fields so the next
  extraction counts shared material once; **bodies are byte-identical** — sources stay immutable.
- **Wired into the procedures, not left as machinery** (the DEC-063 lesson). `ingest-and-connect`
  0.15.0: step 1 sends multi-file intake through `dedupe-batch` *before* extraction, and the final
  line stops calling an extractable document a binary. `import-vault` 0.3.0: a new step 1a runs the
  overlap check ahead of the plan, because an external tree is the worst case for repetition.
- **Follow-up closed from the v1.41.0 merge record.** `ingest-and-connect` 3t's **Action family now
  names its destination**: `manage-todo` and `start-project` (DEC-094) are the generic floor, with an
  installed method's vocabulary layering on top. Ingest records the item and its destination; it does
  not invent a task mechanism where these exist.
- Fixtures `26-doc-extraction` (L2) and `27-intake-dedupe` (L3) join the certification battery, each
  built by a committed **generator script** rather than an opaque binary or four pasted files — the
  fixture is its own specification, and the same generator feeds the unit suite, so the behavioral
  fixture and the regression test can never drift onto different material. 46 new unit tests; both
  writers join the kill-switch coverage regression.
- Constitution 2.9.0 → **2.10.0**. Census: commands 30→32 (§6.2 read 18→22, §6.3 write 9→10), flags
  39→40, fixtures 26→28. **Census reconciliation carried in the same pass** (recounted from source,
  not from the previous number): §6's intro claimed 27 commands against a source of 30 — `docgen`,
  `resolve` and `pack` had reached the CLI without reaching the tables; §6.4's heading claimed
  thirty-three flags over a table of 25 against a source of 39, so the fifteen absent rows were added
  rather than the heading alone corrected; §9.2 had never listed `24-small-fixes`. Additive
  throughout; no migration.

## [1.42.0] — 2026-07-26 (the small-fixes bundle: import review queue, upgrade root files, health riders, Obsidian de-clutter — DEC-097)

**Four owner-approved small fixes (rulings 2026-07-25), one release — every one closes a "the
system forgets its own instruction" gap.**

- **Import review queue (SPEC-import-review-queue).** `aios import` mints project stubs saying
  *"Stage not set — owner to review"* — and until now nothing ever surfaced them again (six sat
  untouched in a live vault since 2026-07-10). Now: every minted stub carries **`review_due`**
  (default +14 days; plan `review_after_days:` or new CLI `--review-days` tunes it), so the
  existing `aios review-due` machinery IS the queue; the apply drops a generated
  **`review-queue.md`** beside the plan (path, source folder, file count, review_due per stub —
  the delta-register pattern; a view, never hand-maintained); the stub's new **"Contains:" line is
  truthful** — empty scaffolding is named as empty ("Contains: empty scaffolding only — Notes,
  Writing (0 files)."), never advertised as material, and a files-empty project dir now still gets
  its stub; and **`aios health` reports overdue never-reviewed stubs** as one rolled-up
  `[import-review]` warning (marker-sentence detector, so ordinary stage-less projects are never
  counted; pre-feature stubs with no `review_due` count — that IS the live defect). The mid-word
  summary-truncation fix from the v1.2.x hardening gains its seeded regression test. Review stays
  human: no auto-staging, no auto-archiving.
- **`aios upgrade` root-files gap (DEC-097).** Upgrade only ever touched `System/` — proven live
  by the PMM Phase 0 inventory, where a successful upgrade left CLAUDE.md ~18 versions stale. The
  product-owned root files (**CLAUDE.md, pyproject.toml, README.md, START-HERE.md** — encoded
  explicitly in the command, one comment per file) now ride the same three-way classification:
  pristine → replaced, instance-edited → kept, both-changed → conflict, never merged. User-owned
  root files are outside the surface by name: **LICENSE.md** (the user's license choice),
  **CHANGELOG.md** (the instance's own journey), **SYSTEM-MANIFEST.yaml** (version bump only, as
  before), and **CONNECT-CHECK.md** (ambiguous → user-owned by default rule). New-release root
  seeds (**To-Do.md** v1.39.0, **Decisions/** v1.40.0 — their register entries point here) are
  delivered **additively when absent** and never touched once present. The shipped baseline
  manifest now records the product root files, so classification is exact from this release on;
  older baselines classify differing root files as conflicts (honest: no evidence, no overwrite).
- **Health riders (determinism audit finding 4 — checked against merged main first: absent, so
  built).** (i) **Per-item Inbox age**: the >14-day triage rule is now a computed `[inbox]`
  warning (count + oldest age; frontmatter `created` when parseable, file mtime for non-markdown
  drops; `_`-prefixed files exempt). (ii) **Generated-tamper evidence**: every `aios generate` now
  records volatile-normalized sha256 digests of what it wrote
  (`System/Generated/.digests.json`); `aios health` compares and reports hand-edited generated
  files as one `[generated-tamper]` warning — hand edits to machine-owned state are lost work
  waiting to happen. Silent when no digest record exists (activates on the next generate;
  rollback-clean); timestamp-only differences are not tamper.
- **Obsidian System de-clutter.** The seed `.obsidian/app.json` ships
  `userIgnoreFilters: ["System/", ".obsidian/", ".trash/"]` — Obsidian *down-ranks* (never hides)
  machinery in search, quick switcher, and link suggestions, so the user's own notes surface
  first. A regression test now pins that `aios upgrade` never touches an instance's `.obsidian`
  (it never did; now it can't silently start).

*Merge-pass amendment (2026-07-26):* since v1.40.0 registered `Decisions/` as a content
directory, the additively-seeded `Decisions/_ABOUT.md` landed *inside* the user world and tripped
`upgrade`'s content-integrity check — a false positive on a deliberate, absence-gated addition. The
check now excludes the paths it recorded in `seeded_root_files`, the same way it already excludes
the regenerated `.claude/skills/` projections. Found only once both branches were on one tree.

Import-vault capability 0.1.0→0.2.0 (names the queue); Upgrading.md 1.1.0→1.2.0 (root-file
ownership table); Obsidian Setup Tips + Migrations README updated; fixture `24-small-fixes` joins
the battery (L3 row); new unit files `test_health_riders.py` + root-file/seed/.obsidian upgrade
tests + import queue/contains/truncation tests. Additive throughout; no migration. Instances see
the new health findings only where the seeded conditions exist.

## [1.41.0] — 2026-07-26 (the working class: the thinking layer gets checked — DEC-096)

**Project working material gets a legal class — owner ruling 2026-07-25, option (a) ratified.** The
schema layer had no class for the files where the user actually thinks: `note.yaml` binds knowledge
to `20 Knowledge`, `project.yaml` covers exactly one note per project, so every plan, log, or capture
under `10 Projects/<name>/` was either untyped noise (a substantial share of one instance's 86
standing no-frontmatter warnings) or an unschema'd foreign type. The layer where the thinking happens
was the one layer the system did not check.

- **NEW `System/Schemas/working.yaml`** — eighth content class. Required fields deliberately light
  (`id`, `type`, `subtype`, `created`/`updated`, `summary`, `status` — the spec's own fence: heavier
  frontmatter than a scratch file deserves means people stay untyped and the gap survives with a new
  name). `working_subtypes` vocabulary: plan · log · capture · draft · scratch. Minimal template
  `System/Templates/working.md`.
- **The boundary is enforced both ways — a first — but asymmetrically, per DEC-082.** The schemas'
  `directories:` bindings had been documentation only (verified empirically this release: a
  `type: note` under `10 Projects/` validated green). Now, in the user content layer: `type: working`
  outside the projects folder (+ Inbox/Archive) is an **error** (new class, no legacy corpus);
  `type: note` under the project layer draws **one rolled-up advisory warning** naming the retype as
  the fix — never an error. *Amended from a hard error before merge, on review against DEC-082 ("a
  lived-in vault never goes red on the user's own notes"): typed notes in the project layer are
  pre-existing lived-in content, so they get the DEC-092 grandfathering shape — legacy advisory,
  new strict.* The project-layer no-frontmatter warning names the class, gently — *"untyped project
  file — consider `type: working`… Untyped is allowed; nothing will auto-type it."* Validate rules
  25→28.
- **Retrieval keeps knowledge-first semantics**: working records are excluded from default
  `aios search`; the new `--project <Name>` flag scopes the search to one project's folder and
  surfaces its working material (a draft plan IS the project's current state, so the status gate
  yields inside an explicit project scope); `aios read --id` and the Steward's survey (agent 1.1.0)
  see them as always. Working material informs *status*, never canon.
- **Consumers wired, not implied** (the DEC-063 lesson): `start-project` 0.2.0 names the class for
  every non-project-note file in a project folder; `retrieve-context` 0.4.2 names the exclusion and
  the scope; the Method Kit generator declares `type: working` on project-layer skeletons
  (plan/journal/handoff). **Deferred, recorded in DEC-096**: the `ingest-and-connect` Action-family
  destination line — that step's text lives on the unmerged `parallel feature change` branch, not in this
  branch's base; it lands as a one-line edit after both merge.
- **Migration: additive — nothing reddens.** No auto-typing, no retroactive errors on any
  pre-existing user content (DEC-082 honored): untyped files keep the gentler warning, typed notes
  under the projects folder roll up to one advisory. Convergence is a frontmatter-only retype or a
  move, at the instance's own pace — proven in this release's dogfood: a real Workshop-style
  `PLAN-*.md` re-typed in a scratch vault validated green with zero body change (hash-verified).
- Fixture `23-working-material` joins the battery; `test_working.py` unit tests; constitution
  2.6.0→2.7.0 (amendment v2.7.0; census: classes 8→9, vocabularies 14→15, values 70→75, flags 32→33,
  validate rules 25→28); Glossary, Metadata Dictionary, folder registry, `10 Projects/_ABOUT.md`,
  `20 Knowledge/_ABOUT.md` updated; derived docs re-stamped.

## [1.40.0] — 2026-07-26 (the routed decisions space — DEC-095)

**Decisions get the home the owner ruled they deserve — shipped WITH the machinery, per his own
recorded condition: routed, or not at all.** The product carried full decision machinery (schema,
template, generated index) that had never been used once in its owner's own vault, because nothing
routed to it and its home (`20 Knowledge/`) had to be told about. Meanwhile the estate scattered
decisions across five registers and collided hand-claimed numbers four times. All three owner-ratified
design calls land (rulings 2026-07-25):

**D1 — a top-level `Decisions/` folder**, the one deliberate exception to the numbered-folder
convention: a decisions space must be as findable as the Inbox, and a space nested inside Knowledge
is a space you have to be told about. Registered in the folder registry (`decisions`), added to the
manifest's content directories, `decision.yaml` updated (`20 Knowledge` stays tolerated for
pre-existing records — no retroactive migration, no reddened user notes). The seed ships the folder,
its `_ABOUT.md`, and one example decision that is also a true record of the convention it
demonstrates.

**D2 — ONE consolidated space.** Project decisions live here too, scoped by the new `project:` field
(decision schema 1.1.0; link-checked like any relation; the reverse views give every project an
inbound `decisions:` line). Per-project decision files would recreate the scatter this ends.

**D3 — numbering derived, never claimed.** Ids are the schema's dated slugs
(`decision-YYYY-MM-DD-<slug>`); no record carries a number of any kind; the human-readable register
(`System/Generated/index-decision.md` — newest first, grouped by project) is generated from
frontmatter on every `aios generate`. Two decisions recorded in parallel therefore cannot collide by
construction — the race is simulated in `System/Tests/scripts/test_decisions.py` (register
byte-identical regardless of creation order; an identical-slug collision surfaces as a validate
error, never a silent merge).

**`record-decision`** — the thirteenth capability, with the router's nineteenth `normal:` row
(edited under the spec's owner approval — the router is a protected object). The trigger bar is
honest: **a decision closes alternatives or changes scope** — "let's go with option B", "approved",
"we're not doing X"; a passing preference is not a decision, and over-capture fails the fixture. The
whole record (Decision/Why/Alternatives/Evidence/Tacit context) is drafted from the conversation
with at most ONE clarifying question (manage-todo's friction bar); a declined answer yields a
flagged record, never a lost decision. Supersession marks, never deletes. The product's own
`System/Governance/Active Decisions.md` remains the product's register — cross-referenced, never
merged, never written with user decisions.

Fixture `22-decisions-space` joins the L3 battery; diagram 43 (atlas 42→43); constitution
2.5.0→2.6.0 (routes 18→19, components 17→18, folders 12→13, fields 52→53); Glossary, How the System
Works, Operator Manual, User Manual, Quick Start, Flow 4, and the Metadata Dictionary updated;
derived docs re-stamped. Deliberate deferrals, mirroring v1.39.0: the onboarding-trio mention (the
trio is touched by pending branches; the mention lands in Quick Start + the manuals now) and
instance delivery of the new top-level folder (rides the queued `upgrade` root-files gap fix).
DoD-4 (a real owner decision recorded through the route in the personal instance post-upgrade) is instance
work, not this release's.

## [1.39.0] — 2026-07-25 (to-do and project routing — DEC-094)

**"Add to my to-do list" and "let's start a project" route somewhere at last.** The owner-verified
gap: both intents routed nowhere — `To-Do.md` was a plain note kept alive by a sentence in its own
body, so nothing re-read it and items rotted; project creation existed only as one user's personal
method skill. The doing layer gains its eleventh and twelfth capabilities and the router two
`normal:` rows (edited under this spec's owner approval — the router is a protected object).

**`manage-todo`** — add/complete/reprioritize in the root `To-Do.md`, which the seed vault now
ships. The paired rule ships with its enforcer (the owner's recorded warning: a rule with no
capability to enforce it becomes the next stale convention): *an item states what, why it matters,
what it blocks or is blocked by, and a path that resolves — a bare file reference is not an item.*
Capture stays light: all four parts are drafted from the conversation and **at most one** clarifying
question is asked (a declined answer yields a visibly flagged item, never a lost capture, never a
silent bare write). On every load, the paths in items touched are link-checked and dead ones flagged
in place with `⚠` — the rot detector half. Order is priority; done items move to `## Done`, dated;
counts about the vault come from scripts, never from the list's prose.

**`start-project`** — the generic floor: resolve first (an existing project is resumed, never
duplicated), `10 Projects/<Name>/` + a schema-valid project note from the template (minted id,
stage, goal, relations), `aios generate` registration, validate, and a statement of where next
actions go (the note's `## Next actions` + the root To-Do via `manage-todo`). **No plans, handoffs,
or gates from core, ever** — an installed method pack (Method Kit output) governs everything above
the floor and is consulted by explicit mention (the DEC-085 split, applied to projects).

Fixtures `20-todo-routing` and `21-start-project` join the L3 battery; diagram atlas 40→42 (41
manage-todo loop, 42 start-project flow); constitution 2.6.0→2.7.0 (routes 16→18, components
15→17); Glossary, How the System Works, AI Operator Manual, Human User Manual, and Quick Start
updated. **Deliberate deferrals:** the onboarding-trio mention of `To-Do.md` (the DEC-062
parity-locked trio is touched by multiple pending branches; the mention lands in Quick Start and
the manuals now and joins the trio on its next unlocked edit) and delivery of `To-Do.md` to
existing instances (rides the already-queued `aios upgrade` root-files gap fix, not this release).

## [1.38.0] — 2026-07-26 (ingest triage + the promotion gate's checklists — DEC-093)

**The pipeline decides cheap before it builds expensive.** `ingest-and-connect` (0.13.0→0.14.0) gains triage step **3t**: extraction now produces a **delta register** — every finding classified into one of the four outcome families (**Knowledge** / **Action** / **Governance** / **Nothing**) with its source line, voice, rationale, and an owner-ruling column — *before* any note is built; only Knowledge-routed findings reach build-out (3a/3b doctrine untouched). The register is the ninth template (`delta-register.md`), canonized from the two proven 2026-07-14 prototypes. Step 4's dangling "four outcomes" pointer resolves. The **promotion gate gains per-class verification checklists** — refusal always names the failing line. Bug fix: step 2's `provider` → `provided_by` (the prose instructed a validation error; regression-tested). Fixture `25-ingest-triage` (L3); +16 unit tests; constitution 2.5.0→2.6.0 (nineteen derived docs re-stamped). Additive; no migration. *(Version and DEC held at the merge pass; only the fixture number moved — `19` went to `parallel feature change`, which merged first, so this fixture landed as `25-ingest-triage`.)*

## [1.37.0] — 2026-07-26 (the sync storage boundary — DEC-092)

**"Never leaves this machine" gets its own field.** The most common privacy intent a user
has could not be expressed: people reached for `classification: restricted`, which actually
means "no AI may ever read this," and their content silently vanished from retrieval — the
owner's own twin modules were unloadable for four days, invisibly. New fourth governance
field `sync: allowed | local-only` (storage only; retrieval stays `ai_use`, readability stays
`classification`): absence = allowed, unrecognized values fail closed out of every
export/sync surface (`okf-export` refuses them; `local-only` never enters an exchange
bundle on any profile), and a `Local Only/` folder implies the marking (DEC-065 extended).
`validate` cross-checks the promise against the root `.gitignore` both ways — unbacked
explicit field = error, unbacked folder-implied marking = advisory (the folder predates this
field; an upgrading vault never goes red on its own content, U1), gitignored-but-unmarked =
warning — with a conservative matcher that reports "unverifiable" rather than ever guessing
"covered"; folder/field disagreement is an error; every `classification: restricted` draws
one rolled-up warning naming the right pair.
Onboarding stage 2 asks the storage question separately from the sensitivity question (trio
1.7.0, DEC-062 parity). safe-write 0.4.0 counsels at write time. Constitution amendment
v2.5.0 (§3.3 storage axis; §4.3 52 fields; §4.4 15 vocabularies / 72 values); Privacy and
Boundaries 1.1.0, Metadata Dictionary 1.1.0, Backup and Recovery Options 1.1.0 cross-ref.
The product `.gitignore` backs the `Local Only/` folder convention by default. **Additive —
no migration**: existing vaults change behavior only when they mark something. Fixture 19
+ 15 unit tests (`test_sync_boundary.py`), including a scripted onboarding-trio parity check.
*(Built as 1.34.0/DEC-089; renumbered to 1.37.0/DEC-092 at the 2026-07-26 merge pass — 1.33.0–1.36.0
and DEC-088–091 were consumed by the backup-onboarding and determinism-audit branches, which merged first.)*

## [1.36.0] — 2026-07-25 (backup evidence + the standards ask — DEC-091)

**Two closures of the same failure shape** — something real existing with nothing wired to notice
it — both landing in the DEC-062 parity-locked onboarding trio, so they ship as one release.

**Backup evidence (SPEC-backup-onboarding, second half).** The stage-8 backup beat shipped in
v1.10.0; what was missing was any way for the vault to *know* a backup happened. Now: `aios health`
counts content that exists on this machine only (any `Local Only/` path segment — the DEC-065
marking — plus `ai_use: local-only` frontmatter) and reports it against the evidence marker
**`80 User/LAST-BACKUP.txt`**: *"N file(s) marked local-only … last recorded backup: \<date | never\>"*.
New helper **`System/Scripts/backup-clone.sh <destination>`** clones the whole vault to a drive
(refuses destinations inside the vault or holding unrelated files) and writes the marker only after
the copy succeeds; manual copiers get the one-line marker command verbatim in the options doc. The
fence is absolute and unit-locked: **no marker = never, a malformed marker = never, and a readable
marker is worded as evidence of that run only** — a false "covered" is impossible by construction.
A warning, never an error (health informs, the human decides), silent wherever no local-only content
exists — so the generic master and clean scaffolds are untouched. Staleness window 30 days, tunable
via `window_days:` in the marker itself. `Backup and Recovery Options.md` (1.1.0) gains the fourth
owner-ruled tradeoff axis — **account-independent?** — for all six options, plus the marker
convention; the backup story is now stated in every user-facing manual (Product Overview, Quick
Start "eight things", Human User Manual, Implementation and Admin Guide — START-HERE already had it).

**Onboarding asks about your standards (owner-approved 2026-07-25).** The Task Router has loaded
`80 User/voice.md` and `80 User/authoring.md` since DEC-036/DEC-063 (`load_if_present`) — but
onboarding never asked whether the user *has* writing or note-building standards, so a user who did
got the shipped defaults anyway: the exact nothing-routes → nothing-loads rot DEC-063 recorded, one
layer up. **Stage 5** now asks both questions (how should your writing sound? how should your notes
be built?), both skippable; yes → the pointer file is written (rules inline when short, else a
one-line pointer to the canonical home — pointer discipline); no → the shipped defaults are named
plainly and either file can be created later with nothing else to change.

Onboarding Specification 1.6.0→**1.7.0**; Human Guide + AI Procedure re-derived and re-stamped
1.7.0; Quick Start and the Implementation and Admin Guide re-read against the new spec and
re-stamped. **DEC-062 parity now has a scripted proof**: a unit test pins the derived pair's
`x_reviewed_against` to the spec's current version and all three docs to the same eight stages.
+13 unit tests (236 total). Additive; no migration; no new `aios` command; no schema change.

## [1.35.0] — 2026-07-25 (aios pack: the trust boundary gets a script — DEC-090)

NEW `aios pack` — the mechanical core of pack install/update/remove, on the `import`
architecture: `--verify` = seven-clause manifest gate + INSTALL/UPDATE plan (read-only);
`--apply --confirm` = checkpoint, place/full-replace, generate, validate, ZIP cleanup, and the
DEC-077 recovery ordering as executable code (remove placed pack first, rollback, judge only on
post-recovery validate); `--remove --confirm` = checkpointed leave-no-trace uninstall. Path
traversal refused; kill switch honored on writes; `--confirm` always carries the owner's OK from
the manage-packs plan step. manage-packs 0.3.0 now delegates its mechanics. +11 unit tests
(`test_pack.py`).


## [1.34.0] — 2026-07-25 (aios resolve: search-before-creating is computed — DEC-089)

NEW `aios resolve --query <term>` — the canonical-record resolver: deterministic match ladder
(id → title/component name → alias → substring → body phrase), supersession chains followed to
the terminal record (cycles error), drafts/superseded visible because they are still dedupe
targets, privacy filtered first and fail-closed. `--mint --type <t>` returns the collision-checked
`<type>-<slug>` id + F-6-sanitized filename at birth. safe-write, ingest-and-connect,
retrieve-context, and the AI Operator Manual now mandate it. +10 unit tests (`test_resolve.py`).


## [1.33.0] — 2026-07-25 (determinism fixes: prose now loads the machinery — DEC-088)

Three fixes from the Workshop's determinism audit, all the same defect shape (machinery existed,
no procedure loaded it): `retrieve-context` now mandates `aios search` / `aios read --id` as the
deterministic privacy-filtered transport (capability 0.3.0→0.4.0); `vocab` rides the `health`
composite so the banned-term guard runs whenever health does (unconfigured instances no-op,
violations stay warnings); and NEW `aios ripple --refs <old-name>` computes the rename-time
operational reference sweep Change Control's medium tier previously ordered as a hand-grep
(read-only, works without the freshness registry; Change Control 1.0.1 points at it). +5 unit
tests (`test_determinism_fixes.py`).

## [1.32.0] — 2026-07-17 (self-generating doc enumerations — DEC-087)

**Hand-maintained lists in the docs now generate themselves.** `aios docgen` fills marked `<!-- docgen:KEY -->` blocks from source; `docgen --check` (inside `health`) fails the build if a block is stale. The Glossary command list is the first block. Third layer of the freshness story — `doc-audit` catches wrong numbers, the stamp checks catch stale prose, `docgen` writes correct prose. Additive.

## [1.31.1] — 2026-07-17 (docs-only: constitution command census reconciled to source — DEC-086)

**The Constitution's own command tables had fallen five releases behind the CLI.** The OKF surface (`okf-check` DEC-075, `okf-export`/`okf-import` DEC-076) and the freshness commands (`ripple`/`workflow`) had reached `aios`, the Glossary, and *How the System Works* — but the Canonical Architecture Specification's §6.2/§6.3 tables still read "fourteen read / seven write" and its intro still said "20 commands → 19 modules." The v1.30.0 reconciliation carried code and derived docs forward, not the constitution; v2.4.0 (session-handoff) bumped the spec for routes/components without touching commands. Corrected to source: §6.2 read 14→18, §6.3 write 7→9, intro 20→27 commands / 19→26 modules, with the three `okf-*` name-mappings; amendment v2.4.1 logged; constitution 2.4.0→2.4.1; nineteen derived docs re-stamped to 2.4.1 (they were *ahead* of the constitution here — no content changed). Same gate-blind class as DEC-072: the read/write sub-splits are spelled-out prose `doc-audit` cannot count. Flagged for a separate pass: the runtime-errors census still reads "129 messages across 19 modules" (module count is now 26; message total needs a real extraction). No behavior or schema change; `certify` green.

## [1.31.0] — 2026-07-25 (a session closes, it doesn't just stop — DEC-085)

**The conversation lifecycle gets its missing endpoint.** Intake was governed from day one
(`process-inbox-item`); the close-out was nothing — a session that ended mid-work left no record a
cold session could resume from, and hand-made handoff files rotted with nothing routing to them. New
core capability **`session-handoff`** (the tenth) with router routes **`close-session`** and
**`resume-session`**: closing a substantive session is journal sweep → checkpoint → validate → an
honest resumable stopping point (what was done with evidence, open items in order, anything left
broken); resuming reads the record before acting and **re-verifies its claims against live state**.
Pure Q&A sessions are exempt — no ceremony nobody needs. The floors are core; the record's form is
the user's: new `80 User/handoff.md` pointer (DEC-036 pattern, consulted by both routes and emitted
by the Method Kit generator on pack install), or an installed method pack's own artifact (per-project
`HANDOFF.md`, a recognized convention since DEC-084). Behavioral fixture `18-session-handoff` joins
the L3 certification battery; diagram atlas 39→40 (Session Handoff Loop); constitution 2.3.1→2.4.0
(§5.15, §2.6 routes 14→16, census 14→15 components, §9.2 fixture table regularized — it had missed
`17-knowledge-freshness`). GENERATOR 0.2.0→0.3.0. No schema migration.

## [1.30.6] — 2026-07-25 (docs-only: the product no longer cites the corpus it was derived from)

**The knowledge-note standard is a design decision, not an empirical claim about one author.** The
shipped defaults in `safe-write` were derived (2026-07-14, DEC-063) by measuring a mature private
corpus; the two living docs cited that measurement ("a mature 248-note knowledge corpus against the
same author's 82,000 words of outward writing"). Owner ruling: the product should not reference its
author's private corpus — the standard stands on its own. Removed the derivation citation from
`safe-write` `SKILL.md` and the architecture spec's `[INTERNALS]` note; the derivation record is
preserved in the construction workshop, and the DEC-063 register entry is unchanged (history is not
rewritten). safe-write 0.2.1→0.2.2. Docs only; no behavior change; no migration.

## [1.30.5] — 2026-07-24 (docs-only: voice attribution reaches the human-facing docs)

**The rule that keeps an AI's ideas from silently becoming the user's was invisible outside the capability layer.** DEC-063's voice-attribution doctrine (`ingest-and-connect` steps 3a/3b) and the knowledge-note standard (safe-write) shipped 2026-07-14 and are certified by fixture 16 — but no human-facing document mentioned either: a user could read every manual and never learn the system does this. Propagated: Human User Manual ("Your words stay yours" in §1; the optional `voice.md` / `authoring.md` hooks in §8), AI Operator Manual (§6 multi-voice attribution procedure, §7 never-do), How the System Works (§6 ingest playbook row, §9 step 7), Product Overview (new "Your ideas stay yours" differentiator), Glossary (**Voice attribution**, **Knowledge-note standard**), and onboarding stage 6 across the parity trio (spec 1.5.0→1.6.0, both derived docs re-tagged). Also fixes fixture 16 missing from `ingest-and-connect`'s own `tests:` list (the fixture certified 3a/3b uncited since 2026-07-15). Docs only; no behavior change; no migration.

## [1.30.4] — 2026-07-24 (a method's convention is not ambiguity — DEC-084)

**`dupes` respects per-project convention filenames.** A user's method may *require* the same
filename once per project folder — an owner-defined method's `HANDOFF.md` is the proven case, found on the
first fully-synced personal-instance run: two projects, two handoffs, distinct ids, and a hard health
error for following his own doctrine. Now: a known convention basename recurring across *different*
folders with *distinct* ids is a warning (visible, never red); the same name colliding inside one
folder, or with duplicate ids, stays an error — the ambiguity rule loses nothing it was built for.
The convention set ships with `HANDOFF.md` and is user-extensible via `80 User/dupes-conventions.yaml`
(the vocabulary-extensions pattern). Third gate-scoping release in a row (DEC-082 → 083 → 084), same
lesson each time: the gates were right about the product and wrong about the lived-in vault.
+3 tests. Additive; no migration.


## [1.30.3] — 2026-07-24 (freshness reaches the front door: onboarding + upgrade docs)

**Docs-only.** The knowledge-freshness feature (v1.30.0–.2) was documented in the constitution,
manuals, Glossary, and guides — but not where a new user first meets the product. Now it is:
the Onboarding Specification (1.5.0) gains a freshness awareness beat in stage 8, carried into the
Human Onboarding Guide and AI Onboarding Procedure in their own voices; `Upgrading.md` (1.1.0) states
the per-vault activation rule (epoch stamps at first `aios generate`; nothing pre-existing accrues
obligations). Four downstream stamps refreshed after delta review. Found by the owner's
closeout question — the completeness check doing its job. Additive; no migration.


## [1.30.2] — 2026-07-24 (doc gates police the product, advise the instance — DEC-083)

**doc-check, doc-audit, and doc-paths are master-strict, instance-advisory.** Found live on the
first v1.30.1 instance upgrade: after a clean sync, 29 residual health errors — every one the same
class, the product's own documentation gates faulting *sanctioned instance divergence* (instance-
added components not in the product atlas, product-doc counts re-counted against an extended
instance, optional docs the instance deliberately removed). The gates were built to keep the
product's docs true, and on the master nothing changes: every one stays a hard error, CI unchanged.
On a vault whose `instance_role` is not `generic-master`, the same findings surface as warnings —
visible, actionable, never a permanent red. Same scoping doctrine as DEC-082, one release apart,
same lesson as ever: lived-in instances reveal test-scope defects the product alone never can
(fifth repetition). No-manifest scaffolds stay strict, so the product's own tests lose nothing.
+3 tests. Additive; no migration.


## [1.30.1] — 2026-07-24 (a lived-in vault never goes red on the user's own notes — DEC-082)

**DEC-069's hard error is scoped to the product's docs (U1 closed).** The upgrade rehearsal proved
the defect on a real clone: bringing a lived-in vault's `validate.py` current made 14 of the owner's
own notes hard errors, because `authority: derived` on a *user* note means "I based this on
something," not "I am a product doc tracking a source version" — and demanding a machine-checkable
stamp on the user's writing is the product telling them how to keep their notes, the one thing it
promises never to do. Now: an unstamped derived doc under `System/` stays a **hard error** (DEC-069's
promise intact); the same condition on user content is one **rolled-up advisory warning** — visible,
approval-gated, never blocking (the owner's recorded direction: freshness yes, updates require user
approval). The rehearsal's regression case is enshrined as a unit test: the old test that expected an
error on a `20 Knowledge/` note now asserts the opposite. Fourth instance of the lived-in-vaults-find-
test-scope-defects pattern. Additive; no migration.


## [1.30.0] — 2026-07-24 (knowledge freshness: ripple, review clocks, workflow cadence — DEC-081)

**User knowledge can no longer rot in silence (DEC-081).** The documentation half of
freshness was finished in 1.15–1.21; this release ships the user-knowledge half the product's own
pitch has promised since day one — when something changes, everything connected gets checked. Three
mechanisms, one doctrine (scripts detect, capabilities judge, humans approve, `health` makes
skipping visible): **Ripple** — a changed note's linked, referencing, and referenced live notes are
listed by `aios ripple` until each effect is judged and recorded (`--ack … --effect`, the ingest
nine + `no-impact`); an ack binds to the note's hash, so changing it again reopens the triage;
`makes-stale` sets the neighbor's status line and nothing else — prose is never auto-rewritten.
**Review clocks** — promotion to canon stamps `review_due` (today + the type's horizon from the new
`System/Registries/freshness.yaml`; `aios review-due --set-missing` is the deterministic backstop);
sources, decisions, and outputs are exempt — dated records don't rot by clock. **Workflow cadence**
— a workflow declaring `cadence_days` reports last-run/overdue via `aios workflow` (`--ran` records
a run); a domain registers its own recurring check by shipping a cadenced workflow file, no other
mechanism (graduates the parked workflow-freshness idea; pattern proven by TX `check_freshness.py`,
parity replay 5/5 classes — Workshop RECORD). **Never retroactive by construction**: the master
ships `enforced_since: null` (installed-but-not-activated, health silent); an instance's first
`aios generate` stamps its own epoch and baselines existing notes without obligations — covering
install, upgrade, `aios import`, and ledger loss with one rule; grandfathered notes never nag.
State is two files under `System/Logs/` (the regenerable hash ledger + the append-only event log —
not `Generated/`, which is wiped per run and built at the hosted privacy floor); listings pass the
same `permitted()` predicate as search; health reports rolled-up counts only, and all freshness
findings are **warnings** this release (the error flip is a later release, gated on live vaults
running clean — the DEC-064→069 arc, owner D5). Constitution v2.3.1 (§6.9 + amendment), 19 derived
docs re-stamped, Glossary/manuals/guides updated, fixture 17 joins the L3 battery, capabilities
maintain-vault 0.2.0 / ingest-and-connect 0.10.0 / retrieve-context 0.3.0. +19 tests (215 total,
suite green); health 0 errors, 0 warnings. Additive; no migration.


All notable changes to this system are recorded here. Versioning follows the rules in `System/Governance/Versioning and Migration.md`.

All notable changes to this system are recorded here. Versioning follows the rules in `System/Governance/Versioning and Migration.md`.

## [0.1.0] — 2026-07-10

Foundational construction begun from Canonical Architecture Specification v1.0 (frozen 2026-07-10).

- B1: Root entry points — START-HERE, SYSTEM-MANIFEST, LICENSE, folder skeleton, Obsidian minimal settings.

## [1.0.0 — WITHDRAWN same day] — 2026-07-10

*(This acceptance was premature — the release gates had not all passed. Formally superseded by the rc.1 correction below; kept for honest history.)*

Foundational build complete: B1–B14 per the approved build manifest.

- Information model: 7 note classes, 9 schemas, 7 templates, metadata & relationship dictionary
- Governance: proportional preflight, privacy & boundaries, 15-operation contract, versioning & migrations
- Toolkit: aios.py with 9 subcommands (9 unit tests), 11 skills, 3 agents, 2 workflows
- Onboarding: canonical 8-stage spec + derived human guide + AI procedure (parity-checked)
- Adapters: Claude (pointer + full op mapping), Obsidian (+ plugin policy), Local-Runtime spec + certification
- Tests: 10 behavioral fixtures, certification battery, portability procedure (tests 1–4 executed and passing)
- Documentation: manuals, system map, glossary, extension guide, maintenance & recovery, deferred backlog
- Example content across all classes incl. tacit source and supersession pair

## [1.29.0] — 2026-07-17 (aios measure — the transcript job — DEC-079)

**The voice split of a chat transcript is now a computed fact, not a hand-count.** New read-only
command `aios measure <transcript>` closes PLAN-standards-execution Phase E (spec A5) and the last
hand-performed step in `ingest-and-connect`. It reports the per-voice word and substantive-turn
split, emits the exact `source_note_line` step 3a asks to be pasted into the source note, and with
`--terms "a,b"` traces which voice said a phrase FIRST — the check that caught 11 of 18 note titles
built on the assistant's coinages. `--extract <out.md>` writes the human's turns, in isolation
(quoted material stripped), for the reading step 3a requires where his share is small.

**Why a script and not a glance:** the counting rules are non-obvious and all bias the ratio toward
hiding the problem. Blockquoted pastes inside a turn are a *third voice*, credited to no speaker.
The vault's own annotation block above an imported transcript's verbatim divider is nobody's turn —
and it discusses the transcript in the transcript's own vocabulary, so scanning it would report the
assistant's coinage as "pre-existing" and clear the very term the check exists to catch. The
Runtime Kernel forbids hand-performing what a script can do (§4); this is that script, and
`ingest-and-connect` (0.10.0→0.11.0) now CALLS it instead of describing the measurement.

**Privacy (DEC-079):** the command separates measurement from content — counts, percentages, and a
term's first-speaker go to stdout; transcript text never does (two tests enforce it). So a hosted
runtime can measure a `Local Only` transcript (DEC-065) it may not read, and the owner has approved
that derived statistics of a local-only source may be shown to a hosted runtime while the content
stays withheld. `--extract` writes content to disk for a human or local runtime and is kill-switch
gated; a hosted runtime must not open it.

+20 unit tests, all fixtures synthetic (generic-master carries no personal data).
Validated against a private historical evaluation corpus (not shipped): reproduces the
FINDING — the assistant dominates ~6:1 and six of seven found note titles trace to it, one sampled
term to the human — while correcting the hand-recorded FIGURES (the by-eye 11% / 64-turn count
mis-attributed blockquotes and used an unwritten "substantive" threshold; the tool measures 15% and
credits pasted material to nobody). Docs: Glossary (24→25 commands), How the System Works,
Maintenance and Recovery Guide, Architecture Spec §6.2 (fourteen read commands) + §6.4 (twenty-four
flags). system_version 1.28.0→1.29.0.

## [1.28.0] — 2026-07-17 (the seed vault's first third-party pack: obsidian-bases — DEC-078)

**Every new instance now ships Bases fluency day one.** `Packs/obsidian-bases/` — the first pack the owner didn't write — vendors kepano/obsidian-skills' Bases reference verbatim (MIT, license inside the pack) behind a thin `author-bases` capability carrying the AI OS guardrails: a `.base` file is a view and never canon, display-only, no map views, vendored examples are never this vault's schema. Default-installed but always removable: one folder, one deletion, never a core dependency, never in the Task Router (DEC-067 keeps its internals out of canon scanning). Survived the full Phase D gauntlet first — evaluation gate, trust scan, sandbox install (which surfaced DEC-077), leave-no-trace uninstall proof, owner ruling. The other four kepano skills stay out, `defuddle` by explicit owner rejection. Additive; no migration; delete the folder to decline.

## [1.27.0] — 2026-07-17 (a rollback that actually rolls back a pack install — DEC-077)

**`manage-packs` promised a rollback it could not perform.** Its step 8 said a failed install "never leaves a half-installed pack." It did — every time. Found the first time a pack the owner didn't write was put through the format (`kepano/obsidian-skills`, Phase D): the install failed the activation gate, the rollback ran, and `[rollback] OK` printed over a vault that still had the pack installed and still failed `validate`. Neither part was buggy alone. A checkpoint is a git commit; `manage-packs` mandates checkpointing *before* placing, so the pack is untracked when rollback runs; and rollback deliberately spares never-committed files as the user's in-flight work. **The mandated ordering guaranteed the failure.** Uninstall was never affected — its checkpoint commits the pack first — so only the install path, the exact path a third-party pack takes, was hollow. Step 8 now removes `Packs/<name>/` itself before rolling back, regenerates, and takes **`validate`'s zero-error result** as the pass bar rather than `rollback`'s headline. One instruction covers both paths: on INSTALL the removal undoes the placement; on UPDATE the pre-update checkpoint already committed the previous pack (`checkpoint` stages `git add -A`), so rollback restores it. Fixture 15 carries the regression. Doc-only change to a capability procedure; no script changed; no migration.

## [1.26.0] — 2026-07-17 (okf-export / okf-import — knowledge travels both ways — DEC-076)

**The OKF surface is complete: check, emit, ingest.** Two new commands close
PLAN-standards-execution Phase C on the heels of 1.25.0's `okf-check`:

`aios okf-export <scope>` emits a folder (default `knowledge`) as an Open Knowledge Format v0.1
bundle in `40 Outputs/okf-<scope>/`. AI OS frontmatter is a strict superset of OKF, so nothing
converts and nothing is lost: the OKF fields map across (`summary`→`description`, `updated`→
`timestamp`, `original_location`→`resource`, H1→`title`) and every AI OS field rides as an extra
top-level key — which the spec expressly permits and asks consumers to preserve. **Privacy is
fail-closed and deliberately STRICTER than retrieval**: `local-only` never exports on ANY profile
(a bundle travels; a runtime doesn't), `private`/`restricted`/draft/`Local Only/`-foldered content
never exports, unrecognised governance values exclude (DEC-066 on the way out). The bundle carries
an `okf.yaml` marker (generator, scope, inherited most-sensitive classification, `approval: none` —
Privacy §2), and **every export is verified by `okf-check` before it reports success** — conformant
by construction, or the command fails. Kill-switch gated.

`aios okf-import <bundle>` lands a foreign OKF bundle as **evidence, never knowledge**: each
concept becomes an immutable `source` note born `status: draft` / `verification: unverified`, OKF
values preserved verbatim under `x_okf_*` keys, bundle hierarchy and filenames kept so the
producer's internal relative links keep resolving (proven: Google's stackoverflow bundle imports
with zero broken links; flattening produced 68). Ids minted to vault grammar, collisions suffixed,
re-import refused (sources are immutable). From there `ingest-and-connect` owns the pipeline —
dedupe, attribute (a bundle's confidence is the producer's, not evidence), extract, connect,
promotion gate. A machine never auto-promotes.

Proofs recorded in `System/Tests/results/okf-round-trip.md`: round-trip lossless on all 19 shared
fields; three planted privacy markers (private, local-only, draft) never appear in any bundle;
all three of Google's own sample bundles (65 concepts) import to a green suite; negative control
confirms the `okf.yaml` marker is what keeps a bundle from being judged as vault canon (16 errors
without it, 0 with). +27 tests (176 total). `ingest-and-connect` 0.9.0→0.10.0. Docs: Automations
Reference, Glossary, AI Operator Manual, How the System Works. Closes the loop 1.25.0 opened:
the format is Google's, the check is one command, and now the knowledge travels both ways.
*(Recorded as DEC-076 — DEC-075 was claimed by the 1.25.1 conformance-claim ruling that landed
first; the estate's fifth numbering collision, resolved at rebase by checking origin.)*

## [1.25.1] — 2026-07-17 (the OKF story reaches the docs a buyer actually reads — DEC-075)

**v1.25.0 shipped the capability; only the reference docs mentioned it.** The Glossary, AI Operator
Manual, and How the System Works carried `okf-check` — enough to pass the `doc-commands` gate, and
nowhere near the pages someone reads when deciding whether to trust this thing with their knowledge.
Now: README (the open-standard claim, up front, with the verify command), START-HERE (the
one-minute model says the numbered folders *are* an OKF bundle), Product Overview (a "why it's
different" line: open format, verifiable, superset), Human User Manual §10 (a new section — how to
check your own portability, and what a green result means), Backup and Recovery Options (the third
risk most backup advice ignores: a backup in a format you can't read later). **DEC-075** records the
standing rule the docs now state — scope the claim to the knowledge layer, never the repo; never
imply priority; be the superset.

Two front-door defects fixed while in there, both structurally invisible to the gates: the README
advertised **"6 AI playbooks"** (there are nine — `doc-audit` tracks the word *capabilities*, not
*playbooks*) and **"Current status: 1.0.0-rc.1"**, twenty-five releases stale, because the version
gate only matches the phrasing `system_version: X.Y.Z`. The status line now points at
`SYSTEM-MANIFEST.yaml` instead of restating a number that rots. Same bug class as DEC-072's finding:
a true claim in a phrasing no gate watches.

**Known debt, deliberately deferred:** the constitution's CLI table and module census still lack
`okf-check` (and its module count reads 19 against a real 21). Amending it re-stamps 19 derived docs
under DEC-069, and those reviews have to be real — that earns its own change, not a rubber stamp
tacked onto a docs release.

## [1.25.0] — 2026-07-16 (okf-check — verify OKF conformance with one command)

**The portability claim becomes a command anyone can run.** New `aios okf-check` (21st command):
verifies a directory tree against Google's Open Knowledge Format v0.1 (published 2026-06-12) —
every non-reserved `.md` file must carry parseable YAML frontmatter with a non-empty `type` field;
OKF's reserved filenames (`index.md`, `log.md`) are exempt. Default target is the vault's knowledge
layer (the manifest's content directories), which is an OKF bundle in the spec's
bundle-as-subdirectory form — so "is my knowledge in the open format?" is now a checkable fact, not
a promise. Point it at any directory (a future `okf-export` output, a foreign bundle) to verify
portability yourself. Read-only; nonzero exit on violation, so it can gate exports and CI. A
regression test pins the seed vault's own knowledge layer CONFORMANT forever. +9 tests (137).
Docs: Glossary (count 21→22), AI Operator Manual, How the System Works.

## [1.24.1] — 2026-07-16 (frontmatter hygiene — every system doc self-describes)

**Two documentation files had no frontmatter; generated docs lacked `type`.** Found while
verifying the vault against Google's Open Knowledge Format (OKF v0.1), whose single hard
requirement — every concept file carries a `type` field — is also this vault's own standard.
`System/Documentation/Diagrams/PIPELINE.md` and `CATALOG.md` (hand-authored, canonical) gain
standard frontmatter blocks; the `generate` header helper now stamps `type: system-doc` on every
generated markdown doc, so `System/Generated/*.md` self-describe like everything else. `validate`
warnings drop 7 → 5; the five that remain are repo furniture (README, LICENSE, CLAUDE.md, two
tooling READMEs), which is deliberate. Test fixtures stay raw by design — they exist to prove the
system reads unformatted input. No behavior, schema, or routing changes.

## [1.24.0] — 2026-07-16 (aios upgrade — the product-update importer — DEC-073/074)

**An installed vault can now take a new version without a hand-migration.** New `aios upgrade
<path-to-release>` applies a release's `System/` — and only `System/` — into an existing instance:
content directories, `80 User/`, `.obsidian/`, `Packs/`, the canonical journal (DEC-016), and
certification records are outside the surface entirely and are never read, merged, or written. The
release is a local folder (a zip or a checkout); no network, no Git, no product repo — a tester
handed a zip can upgrade.

Classification is three-way — base vs release vs instance — against a new shipped artifact,
`System/.baseline-manifest.json` (**DEC-074**): the release's own record of its pristine file
hashes, regenerated on the master with `aios upgrade --make-baseline` and CI-checked for freshness,
so "which of my files are untouched?" is a computed fact rather than an inference. Pristine files
are replaced; instance-edited files are **kept** and reported; files changed on both sides are
**conflicts** — left exactly as they are, never auto-merged. Without a baseline (an instance older
than this release) the command falls back to the safe reading: every difference is a conflict and
nothing is replaced, because a wrong "unchanged" call is the one failure that destroys user work.
A baseline whose version doesn't match the instance is refused rather than trusted.

**The Task Router is never merged** (**DEC-073**): divergence yields a per-row review list — which
rows are only yours, which are new in the release, which differ — and your file is untouched.
Losing a user's router rows is the worst outcome this command could produce, so it doesn't take the
chance; the `Task Router.local.yaml` overlay is the designated fast-follow.

Discipline is `migrate.py`'s: kill-switch-governed (added to the write-command set and its
regression), checkpoint-or-halt before any write, `--dry-run` that provably writes nothing and whose
plan matches the real run, regenerate + validate + health after, a durable report in `System/Logs/`,
and a journal line. Failures are loud and name the checkpoint — never a success claim over a red
gate. **The version bump is earned**: `system_version` advances only when gates are green, no
protected path is in conflict, no migration is pending, and classification had a real baseline —
found by the fallback test, which bumped to the new version while every file still held the old
content. Migrations arriving with a release are delivered and listed, never auto-applied. Fused
instances (many edits inside protected files — the PMM Engine shape) are refused by name before
anything is written; that vertical needs the role-pack refactor first. Idempotent: a second run
reports "already at version" and touches nothing. New `System/Documentation/Upgrading.md`;
Versioning and Migration 1.0.0→1.1.0 (§4a). Twelve new unit tests (140 total).

## [1.23.0] — 2026-07-16 (the doc-paths gate — DEC-072)

**A doc can no longer point at a file that moved.** New `aios doc-paths` gate — the fourth
documentation question (drawn? documented? true? → **do the cited paths resolve?**): every
backticked `System/` path in prose must exist on disk. That reference class was invisible to every
gate by design — `links` strips code spans (backticks mean "literal text"), and external markdown
checkers do the same — which is how a stale capability pointer survived a fully green CI the day
v1.22.0 merged. Composed into `health`, so CI now enforces it on every merge. Noise discipline per
the DEC-032 retired-for-noise lesson: only always-committed `System/` roots are checked;
placeholders (`<name>`, `NNN-…`, globs), runtime-born dirs (`Generated/`, `Logs/`), the
install-optional `Packs/`, and historical records are exempt — deliberately excluding docaudit's
blanket `Migrations/` exemption, since that tree's README is a live doc and the origin bug's own
site (a planted-bug probe during the build caught the over-exemption before it shipped). Also in
this change: doc-audit's command-count matcher tolerates backticked tool names (it silently skipped
"the 19 `aios` subcommands" — found when adding the twentieth command made that claim false and
nothing fired); constitution command tables and censuses re-extracted from source (test count and
error-message census had drifted since 2.0.0). Six new unit tests (128 total). Read-only command;
no migration — instances pick it up with the release.

## [1.22.0] — 2026-07-16 (Agent Skills packaging — DEC-070/071)

**Capabilities adopt the industry's Agent Skills packaging without conceding the architecture.** All
nine capabilities move from flat files to `System/Capabilities/<name>/SKILL.md` directories (git
history follows; contracts, ids, versions unchanged), each gaining the spec's required `description`
(what it does *and when to use it*; `summary` stays canonical). `aios generate` gains an eighth
artifact: a **spec-valid Agent Skill projection** of every active capability under
`.claude/skills/aios-<name>/` — six spec fields only, AI OS extras stringified under `metadata`,
`compatibility` declaring the vault dependency (DEC-071), and a body that says loudly that governance
does not travel with the file. All nine projections pass the reference validator (`skills-ref`),
which is also the evidence that forced the design: extra top-level frontmatter keys are a validator
**error**, and the `metadata` escape hatch string-mangles lists — so the canonical file keeps the AI
OS superset and the spec surface is *generated*, never inherited (the OKF ruling, applied twice).
Emission is namespaced (`aios-*`), marker-guarded (a user's own skills are never touched), stale-safe
(removed capabilities lose their projection on regenerate), and kill-switch-governed like every
writer. Core routing is untouched: the Task Router still names capabilities deterministically;
`description` discovery is for packs and foreign agents (DEC-070). Scaffold now creates the directory
form; the four capability-glob consumers (`doc-check`, `doc-audit`, `generate`, `scaffold`) updated
with tests; `SKILL.md` left the retired-artifact list (it returns as the standard, not the retired
architecture). Constitution amended 2.0.0→2.1.0 (§5, §7.1); 19 derived docs re-screened against the
delta and re-stamped. Four new emission unit tests (122 total). No migration: instances re-run
`aios generate`; any external references to `System/Capabilities/<name>.md` become
`System/Capabilities/<name>/SKILL.md`.

## [1.21.0] — 2026-07-16 (prose freshness enforced)

**Documentation can no longer silently fall behind the product (DEC-069).** Two doc-freshness checks that were advisory become hard errors: a `derived` doc without an `x_reviewed_against` stamp fails `validate`, and a stamp that lags its source fails `health`. This completes DEC-064's promise from the other side — that decision made *numbers* unable to lie; this one makes *prose* unable to drift unnoticed. It could only be turned on after the coverage gap was actually closed: the last 14 unstamped derived docs were each re-read against their source and stamped in this change (the seven folder `_ABOUT` guides and the three adapter docs derive from the constitution; Quick Start and the Implementation Guide from the onboarding spec; ANSWER-RECORD from the Method-Kit interview + dials). Proven live. Additive; no migration.

## [1.20.0] — 2026-07-16 (the Constitution — spec v2.0.0)

**The architecture specification is replaced by the verified manual (DEC-068).** The frozen v1.0 spec served ten amendments and then drifted six ways from the product it governed; its successor was built the opposite way — extracted from the live source, audited against v1.19.0, and subject to the same `doc-audit` gate as every other document. Same id, same path, same rule domain (option C), so nothing that depended on it breaks: seven derived docs re-stamped to 2.0.0, the v1 amendment log preserved inside the new document, and a v1→v2 section concordance keeps every old "spec §N" citation resolvable. The audit companion stays in the construction workshop (DEC-057). Additive for user data; no migration.

## [1.19.0] — 2026-07-16 (packs install clean + real folder indirection)

**Every well-formed add-on pack failed `health` — fixed (DEC-067).** A pack ships its own `CHANGELOG.md`/`README.md`; the vault scanned them as canon and `dupes` collided them with its own. `Packs/` is now skipped by the canon scanner, so pack internals never masquerade as vault canon — while pack *components* stay discoverable via the explicit `Packs/*/` globs. Verified: the Content Engine pack v2.0.0 installs to a green vault, four capabilities indexed.

**Folder indirection (DEC-004) is now real, not decorative.** Nine scripts hardcoded content-folder names while three canonical docs claimed the registry made renames edit-free. The renameable content folders (10 Projects, 20 Knowledge, 30 Sources, 40 Outputs) now resolve through `vaultpaths.rel_folder`; reserved dirs (Vault Profile §9) stay literal by design, and the docs say so precisely. Additive; no migration.

## [1.18.0] — 2026-07-16 (privacy fails closed + the resurrected doc-truth gate)

**A typo in a privacy field can never widen access again (DEC-066).** The filter permitted anything it didn't recognise — `Restricted`, `local_only`, any misspelling. Unrecognised values now fail closed everywhere, `validate` errors on them on every record regardless of `type`, and unrecognised types themselves get one rolled-up warning (still tolerated — never invisible). **doc-truth actually fires now**: it compared the manifest against the *first* CHANGELOG heading — the oldest entry — so it could never fail; it now takes the latest version. **`search` discloses truncation** (`matches_total`, "first 25 of N"). **A failed import no longer locks out the retry** — its one-time marker is removed on validation failure so restore-then-re-run works. **Fixture 04** adopts the deterministic/behavioral split so the privacy certification can actually fail. Additive; no migration.

## [1.17.0] — 2026-07-16 (safer imports, pure snapshots, Local Only honored)

**`aios import` now halts when its safety net fails.** The pre-import checkpoint's result was never checked — a failed checkpoint (e.g. `git init` with no identity) let the import write everything with no recovery point and report "restore checkpoint ?". It now refuses with nothing written, exactly as `migrate` always has (checkpoint-or-halt).

**`checkpoint --zip-only` — a pure snapshot.** `--zip` also *commits* when git is present, which is a trap on a tree carrying unready work. `--zip-only` writes the human-restorable zip and touches nothing else.

**A folder named `Local Only/` is now a real privacy marking (DEC-065).** The filter treats any `Local Only` path segment as `ai_use: local-only`, fail-closed: hosted runtimes never see the content. Previously the folder name did nothing — and one shipped doc already described it as a marking.

**Doc-freshness coverage is now visible.** `validate` warns (one rolled-up line) when derived docs lack their `x_reviewed_against` stamp — skew from their sources is invisible until they're stamped. First step of enforced prose freshness; the stamping pass and the error-level upgrade follow.

Additive; no migration.

## [1.16.0] — 2026-07-16 (documentation-truth gate + rollback dirty-tree protection)

**Documentation can no longer contradict the product it describes (DEC-064).** New read-only command `aios doc-audit` reads the true counts from source on every run — the CLI via argparse AST, components from disk, principles/diagrams/vocabularies from their registries, the version from the manifest — and errors on any countable claim in prose that disagrees. Historical records (CHANGELOG, change-journal, test results, migrations) are exempt: they were true when written (spec §15). Composed into `health`; CI now runs `health`. Ten live drifts found and fixed in this change — six in the Architecture Spec (capability/principle/key/document totals → spec v1.0.10), the AI Support Guide and atlas-catalog diagram counts, and the catalog's pinned `system_version` (removed: headers must not hardcode what they cannot track). §32's fixed total became a structural rule instead of a fresh number. Four derived docs re-reviewed and re-stamped against spec 1.0.10.

**`aios rollback` no longer destroys uncommitted work.** `git checkout <target> -- .` silently overwrote uncommitted edits to tracked files (independent audit M-02's last open half). A dirty tree is now zip-preserved to the Snapshots folder automatically before any restore, and the report says where. The kill-switch regression now covers every write command including `import` (audit H-05, complete). Additive; no migration.

## [1.15.0] — 2026-07-16 (router load paths must resolve)

**The Task Router's own header promises "every load entry is a real vault path" — and until today nothing checked it.** Found live in an instance: the `onboarding: run-or-resume` row loaded `System/Capabilities/method-kit.md`, the file was absent from that vault, and `aios validate` passed with 0 errors. A dangling router row is invisible by construction — the route simply loads less than its contract says, and the output still looks correct (the DEC-063 failure shape, again). `validate` now walks the router: every `load:` path must resolve to a real file (error), and a `System/` path under `load_if_present:` draws a warning, since the header rules that System files must exist and belong in `load`. Skips gracefully in a vault with no router (minimal test scaffolds). +6 unit tests (90 total). Additive; no migration.

## [1.14.0] — 2026-07-14 (the knowledge-note standard ships)

**A knowledge note is an input, not an output — and until today the product never said so.** `safe-write` (0.2.0→0.2.1) covered only mechanics: ids, templates, folders, grounding. Nothing about what makes a note *useful*, so every runtime improvised one from its own defaults and the drift was invisible because the output still looked like a note. It now carries generic doctrine: the inputs principle; how a knowledge note reads (more academic than the same author's outward writing — longer sentences, almost no bold, headers that carry claims rather than labels, prose allowed to run, objections woven, citations dense and precise); the four reusability properties (a lift-ready summary, scope conditions, a falsification condition, counterarguments); and citation discipline. **The standard always exists** — the shipped defaults are the baseline, the user's `authoring.md` refines them, their corpus refines them further, and the model's house style is never the fallback.

Derived by measuring a mature 248-note knowledge corpus against the same author's 82,000 words of outward writing. The gap was consistent and large (sentences roughly a third longer, a third past thirty words, bold median zero per note, zero generic headers across 248 files). Shipped as **direction, not figures** — one corpus is one data point, and the calibration is labelled as such.

**`ingest-and-connect` 0.5.0→0.9.0**, refining step 3a through use. The test is **fidelity, not authorship**, and it resolves three ways: *enhancement* (assistant strengthens a raw idea while keeping its truth → capture; this is the most common form of real value in a transcript and discarding it produces a note thinner than the conversation that made it), *solicited answer* (the human asked → capture; a reference consulted at his request), *redirection* (reshapes toward the assistant's own framing → **never silently absorbed**; file as a distinct idea with attribution and a `contradicts` link, or drop). The middle path — absorbing the assistant's thesis into a note carrying the user's name with no attribution — is the one thing never permitted. Step 3b adds the build-out rules and the no-meta rule.

Additive; no migration. See DEC-063.

## [1.13.0] — 2026-07-14 (voice attribution + the orphaned authoring standard)

**A source is not always one voice.** Ingesting a ChatGPT export exposed two defects in `ingest-and-connect`. The pipeline assumed one author per source — but a chat transcript has two, and in that export the assistant had written 43,121 words against the human's 5,433. Reading it whole yielded the assistant's framing, so extracted notes came out as its paraphrase under the human's name, including note titles built on its coinages. **New step 3a**: extract from the human's turns only; assistant turns are commentary on the source, not source; measure and record the voice split on the source note; read the human's turns in isolation first when his share is small; coinages carry attribution; an assistant-originated central claim is not `inferred`, it is not his claim at all.

**And attribution is the floor, not the ceiling.** The first correction over-swung into stripping notes to bare quotes, which is the opposite failure. **New step 3b**: one concept per note, built to the depth the user's authoring standard requires (specific works, dates, named authors, counterarguments, historical grounding), with the human's claim as thesis and spine — research recruited to strengthen it, never to displace it. Assistant turns are usable here where true to what the human said.

**Root cause.** `80 User/Authoring Standards` has been `status: active` since 2026-07-10 and **no route ever loaded it**. Every note since was authored against an improvised standard while the real one sat unread — invisible, because the output still looked like a note. Closed with the DEC-036 pointer pattern: `80 User/authoring.md` (holds no rules, points at the canonical file), wired into `create-note`, `update-note`, and `process-inbox-item` via `load_if_present`. Note that `update-note` previously loaded no user standard at all, so edits were held to a lower bar than creations.

`ingest-and-connect` 0.3.0→0.5.0. Task Router touched (protected object; owner-instructed). Additive; no migration. See DEC-063.

## [1.12.0] — 2026-07-14 (command-documentation gate)

**Every CLI command must be documented — now checkable.** New read-only command `aios doc-commands` reads the actual command list straight from `aios.py` (AST-parsed, so it can never drift from what the CLI accepts) and fails if any command is undocumented in `System/Documentation/` or `System/Onboarding/`. "Documented" means an `aios <cmd>` invocation or a backtick-wrapped command name, so short names like `read` are not matched inside ordinary prose. Folded into `aios health` alongside `doc-check`, so a new command can no longer ship undocumented and slip by unnoticed — the command-surface sibling of the DEC-051 component documentation gate. Skips gracefully in a vault with no CLI (minimal test scaffolds). +6 unit tests (84 total). Additive; no migration.

## [1.11.1] — 2026-07-14 (doc currency)

**Manuals brought current + freshness wiring.** User-facing docs that predated recent features now describe them: the **Method Kit** appears in the Product Overview and the Human User Manual ("grow the system"); the **doc-check** activation gate (a component can't activate without a documented diagram, DEC-051) is stated in the Extension Guide; `aios checkup` is listed among the tools in How the System Works. Each freshened doc now declares `x_reviewed_against: ["doc-canonical-architecture:1.0.8"]`, so `aios health` (derived_doc_drift) will flag it for review the next time the architecture spec bumps — closing the silent-doc-drift gap (Principle #24). Docs-only; additive; no migration.

## [1.11.0] — 2026-07-14 (checkup on demand)

**`aios checkup` — the state of your core, on demand (DEC-059).** A friendly, one-line readout of the doctrine signals: how much is waiting in staging (inbox), what is due for review, and what is filed as knowledge but never verified — or "your vault is tidy" when all clear. Pull, not push: it answers only when asked and never nags; deterministic and runtime-agnostic (a human can run it too). Light — it counts, it does not validate (that stays `aios health`). +1 test; discoverable from the Runtime Kernel tool list and the Human User Manual. Additive; no migration.

## [1.10.0] — 2026-07-14

Backup becomes a first-class part of onboarding (owner: "it needs to be").
Previously backup was documented only for implementers; a self-onboarding
user was never walked through protecting their vault.

- **New doc `System/Documentation/Backup and Recovery Options.md`** — the full
  menu (GitHub private remote, obsidian-git auto-push, encrypted external
  drives, built-in zip snapshots, cloud-synced folder, whole-disk) with honest
  tradeoffs, the two failure modes it guards (bad change vs. dead machine), and
  the one hard rule (sensitive content stays off any cloud). Shows all options
  and lets the user choose — nothing prescribed.
- **Onboarding stage 8 gains a backup beat** — offer, present the options, let
  the user choose, offer to connect the chosen one, record the choice (or
  defer). Added across all three parity-locked onboarding docs (spec → 1.2.0,
  AI Procedure + Human Guide re-derived and re-tagged).
- **Links** from START-HERE and the Human User Manual to the new doc.

## [1.9.0] — 2026-07-13 (canonical core doctrine)

**The canonical core doctrine, made explicit (DEC-058).** Named **Principle 26** — *context is staging; knowledge is canon* — the rule the schema, ingest pipeline, and retrieval already embodied but that was stated nowhere: raw capture must earn promotion into the trusted core through a quality gate, and the vault's worth is the trustworthiness of its canon, not the volume of its context. Design Principles 1.0.1→1.0.2; Runtime Kernel 1.0.0→1.0.1 (one always-loaded orientation line); Canonical Architecture Specification 1.0.7→1.0.8 (§17). The **promotion gate** is now an explicit named step in `ingest-and-connect` (v0.3.0, cross-referenced from `safe-write`) — no schema change, since the `note` template already births knowledge as `status: draft`. `aios health` gains an advisory **`unverified_in_knowledge`** signal (notes filed as canon but never verified). Taught in plain language in the Human User Manual, Product Overview, and Human Onboarding Guide; pointer references added across the runtime docs. New behavioral fixture `14-promotion-gate` (L3). Additive; no migration. All 74 tests pass; validate / doc-check / certify green.

## [1.8.0] — 2026-07-13 (Method Kit)

Added the **Method Kit** as a default capability plus an optional onboarding module: an AI-administered interview that builds a user their own operating-method pack — their rulebook plus wired skills. Owner-approved to ship into the product (DEC-052).

**`aios certify` hardened to be fully non-destructive.** It no longer writes a certification record into `System/Tests/results/` — it emits its ranked report to stdout (and `--json`), exactly like every other `aios` command; save it by redirecting output. The idempotency probe now backs up and restores `System/Generated`, so certify leaves the tree byte-for-byte as it found it. This removes a recurring untracked-artifact and makes certify safe to run on the master and while another session is working. Behavior/coverage otherwise unchanged; tests green. 

**Docs + certify F-3 fix.** The Glossary now distinguishes a **command** (a script-level `aios` tool — validate/health/certify/etc., no contract or diagram) from a **capability** (a governed component). `certify` governance no longer flags a *forward-looking* protected-object glob (e.g. `80 User/privacy*`) that legitimately matches nothing in the generic master — that user content is created at onboarding and kept out of the clean seed (per `test_clean_seed_content_dirs`). certify now runs 0 warnings on a clean master. A seeded test locks the behavior.

**Instance-side privacy-file check.** `aios health` now warns when a *personal instance* (`instance_role: personal-instance`) has no `80 User/privacy-rules` file — the counterpart to certify's master-side handling. certify does not require the file on the generic master (it is created per-user at onboarding stage 2 and kept out of the clean seed); health verifies a real instance actually got it. Advisory only: a missing file falls back to the always-present `System/Governance/Privacy and Boundaries.md` defaults (private-by-default), so privacy still holds conservatively meanwhile. 3 seeded tests; the generic master and disposable scaffolds are exempt.

- Capability `method-kit` (`System/Capabilities/method-kit.md`) — interview -> resolve the 11 dials -> generate the user's `<Name>-Method/` pack + install pack-skills; activated against fixture `method-kit-generation`.
- Instrument vendored generic into `System/Method-Kit/` (CORE, DIALS, INTERVIEW, GENERATOR, ANSWER-RECORD, Adapters), re-stamped to product reference-doc schema; personal-data-clean.
- Onboarding: an optional, deferrable step in Stage 8 across all three onboarding docs; a skip records to `unresolved` and re-surfaces on re-onboarding.
- Router: the `onboarding` route now loads `method-kit` so the Stage 8 offer resolves (a route must carry its procedures' full dependency set, audit B-03). Protected-object edit, owner-instructed; preflighted + sandboxed (72/72 tests, certify green).
- Atlas: diagram 38 (method-kit flow) + coverage/metadata (satisfies DEC-051). Test: fixture + passing result; dogfooded end-to-end on a synthetic subject.

## [1.7.0] — 2026-07-13

**The in-product documentation system.** Promotes the documentation work landed under the 1.6.0-dated entries below to a minor release. AI OS now ships: a 37-diagram atlas in `System/Documentation/Diagrams/` (concept diagrams, user-flow walkthroughs, the portability contract, the always-on automations layer); `aios doc-check` — a coverage gate enforcing that every component *and* every user-flow walkthrough maps to a described diagram (rolled into `aios health` and the weekly pass; hard-blocks undocumented component activation, DEC-051); an AI support harness (`AI Support Guide.md` + generated `support-index.json`) that points any AI at the docs to answer "how does this work" with citations; a task-oriented how-to layer in `System/Documentation/Flows/` (11 walkthroughs + an Automations & Checks reference); and a positioning correction (Obsidian framed as the recommended default, not merely optional). Additive; no migration. All 63 tests pass.

**Internal QA / certification harness.** Adds `aios certify` — a one-command product-integrity certification that composes the mechanical checks (via `aios health`, so nothing is duplicated) with certification-specific gates nothing else covered: governance/safety (kill-switch enforcement, `protected_objects` existence incl. `System/Agents`, and no personal data in the generic master), command idempotency (`generate` run twice yields identical derived state), doc-truth (manifest `system_version` must not lag the latest CHANGELOG version — a hard release-integrity gate), and the regression suite. Writes a ranked certification record to `System/Tests/results/`. `aios health` gains an advisory `doc_staleness` check (every manifest entrypoint / reading-order path must still exist). Read-only against vault content. 9 new seeded-failure tests prove each assertion catches a planted break; 72 tests pass total. Additive; no migration.

## [1.6.0] — 2026-07-13 (user-flow how-to layer)

Task-oriented documentation layer (Diátaxis how-to guides). Adds `System/Documentation/Flows/`: a "Flows of Work" overview mapping all 11 user flows, a step-by-step walkthrough for each (Goal / What you say / What happens / What you get / If it goes wrong / Related), and an "Automations & Checks Reference" cataloguing every background check/automation. 13 new user-perspective diagrams (24–36). `aios doc-check` gains a `flows` dimension: every `Flows/*.md` walkthrough must map to an existing, described diagram (parity with the component gate). Support index now spans 53 docs + 36 diagrams. Additive; no migration.

## [1.6.0] — 2026-07-13 (documentation system)

In-product documentation system + support harness (DEC-051). The 23-diagram atlas moves into `System/Documentation/Diagrams/` (svg + `coverage.yaml` + `diagram-metadata.yaml` + `CATALOG.md` + `PIPELINE.md`). New `aios doc-check` enumerates components from disk and fails on any undiagrammed component, missing diagram SVG, or undescribed diagram; rolled into `aios health` and the weekly-maintenance drift checks. Component activation (`aios scaffold --register`) now hard-blocks an undocumented component — documentation is a peer of tests. A support harness (`System/Documentation/AI Support Guide.md` + generated `System/Generated/support-index.json`, built by `aios generate`) lets any AI answer "how does this work" questions from the product's own docs with citations. Additive; no migration. *(Whether to promote this to a 1.7.0 bump is deferred to the owner given concurrent 1.6.0-rolling entries.)*

## [1.6.0] — 2026-07-13

Vocabulary addition (DEC-050): `conversation` added to `source_subtypes` (`System/Schemas/vocabularies.yaml` schema_version 1.0.0 → 1.1.0), so imported chat / AI-session transcripts are first-class sources instead of generic `document`s. Additive and non-breaking — existing files stay valid, no migration. `source.yaml` and the validator pick it up automatically via the `{vocab: source_subtypes}` indirection. Propagated to the live instances (the personal, commercial-role, and customized work instances); test/proving scaffolds inherit it on regeneration from the master.

## [1.6.0] — 2026-07-12

Voice-aware drafting (DEC-036). The Task Router gains a `draft-content` row: outward-facing
drafting loads the user's voice standard (`80 User/voice.md`, user-owned, optional, pointer or
rules) via `load_if_present`. Motivated by the owner-instance voice rebuild: both live instances
had customized the stock router to load their voice files; this generic row retires that drift.

## [1.6.0] — 2026-07-11

Documentation self-monitoring (DEC-039 Phase 3) + a terminology fix.
- `aios health` now also reports **how long since the generated docs were last
  rebuilt** and warns when they're overdue (>10 days) — so the "keep everything
  current" loop notices its own staleness. (Fully hands-free background running
  still needs an external scheduler; this is the self-monitoring half.) One unit
  test added.
- Design Principle 15 wording aligned **"skills" → "capabilities"** (the rename
  ratified in DEC-024; principles doc → 1.0.1, with an amendment note). No
  meaning change; historical mentions of "skills" as past state are unchanged.

## [1.5.0] — 2026-07-11

Prose drift-flagging (DEC-039 Phase 2). `aios health` now reports **derived docs
that have fallen behind their source**: a derived document may record the source
version it was written against (`x_reviewed_against: ["source-id:version", …]`),
and health warns when that source has since advanced — so hand-authored prose
gets refreshed instead of silently going stale. Facts self-update via
`aios generate` (v1.4.0); **prose is never auto-rewritten** — it is flagged for a
human/AI to update. The two onboarding derived docs carry the marker as live
exemplars; one unit test added (drift flagged, then cleared by bumping the marker).

## [1.4.0] — 2026-07-11

Self-updating documentation (DEC-039). `aios generate` now emits
`System/Generated/system-reference.md` — a human-readable catalog of the
registered components, the 15 stable operations, the schemas, the controlled
vocabularies, and the folder registry — built entirely from source on every
run, so the factual reference is **never stale by construction** (same pattern
as `component-index.json`). Judgment prose (glossary, manuals) stays
hand-authored and `derived_from`; only facts are generated, never explanations.
Two unit-test assertions added (source-reflection + presence in the rebuilt set).

## [1.3.0] — 2026-07-11

Four improvements from the PMM Engine migration (the first domain product
built on this OS), each merged from its own suite-green branch after owner
approval:

- `aios vocab` — banned-term guard as a first-class read-only command; user-owned
  config at `80 User/vocab-guard.yaml`; unconfigured instances no-op cleanly.
- Components self-identify: any file declaring `component_type` carries the
  contract wherever it lives — domain packs need no wrapper files (DEC-033).
- Product seeds self-declare: `product_seed: true` marks deliberately shipped
  files; the generic-seed personal-data check stays armed for everything
  undeclared (DEC-034).
- Drift test scope: the bare-word "skill(s)" rule is retired (three
  false-positive incidents vs zero unique catches; "skill" is the ecosystem's
  own vocabulary); specific retired-artifact checks unchanged (DEC-032).

## [1.2.1] — 2026-07-11

Completes v1.2.0 (its change was merged before the final two commits): the
import engine's five proving-run fixes (registry id-collision
disambiguation, anchor-asserted `patches:`, writable imports from frozen
sources, empty-scaffolding-dir mirroring, sentence-boundary summaries) plus
`prefix_parent`, and the documentation sweep — START-HERE authority row,
Quick Start, Product Overview, Human User Manual §8, Implementation Guide
stage 7b, Glossary, AI Operator Manual, regenerated indexes. The v1.2.0
changelog entry below describes the feature; this version is the state the
replays actually certified.

## [1.2.0] — 2026-07-11

Vault import tool (doc 12 Part A; both 2026-07-10 real migrations distilled
into product machinery):

- **`aios import --plan NNN-name [--apply]`**: bulk-import an existing
  external vault from a declarative `import-plan.yaml`. Two proven modes —
  `verbatim` (byte-identical; foreign folders registered
  `conventions: foreign`; root adapter-slot rename) and `mapped` (per-rule
  transforms: `copy`/`note`/`source`/`user`; legacy keys survive as `x_`
  extensions; summaries lifted; ids minted; mandatory terminal `**` rule
  quarantines everything unmapped to the Inbox — nothing is ever dropped).
- **Fixed pipeline**: preflight (collisions, case collisions, sanitized
  names, secret flags, source link baseline) → dry-run default, writes
  nothing → owner approval → `--apply` (checkpoint first, validate after,
  one-time marker refuses re-runs). Source opened strictly read-only.
  Optional `.obsidian` import (minus workspace.json, never overwriting).
- **`import-vault` capability** — the human side: mode from the workstyle
  answers, plan authored folder-by-folder with the owner, report presented
  in their vocabulary, migration suggested once and never again.
- **Proving-run hardening** (both real migrations replayed through the
  engine before merge): registry id-collision disambiguation + explicit ids;
  anchor-asserted `patches:` (declared adaptations, e.g. foreign checkers'
  jurisdiction seams); imports from read-only/frozen sources come out
  writable; verbatim mode mirrors empty scaffolding dirs (automation refs);
  sentence-boundary summary capping; per-rule `prefix_parent` filename
  disambiguation. Evidence: work-instance replay — 1,095 files byte-identical,
  TX check suite 15/266 findings identical sets, proof engine no-op, health
  green; second historical-corpus replay — health green after the recorded dedupe
  resolutions.
- Fixture 13 (vault-import probe) added to the L4 battery; 14 unit tests
  (dry-run purity, transform correctness, verbatim parity, quarantine,
  one-time marker, secret gate, sanitization, kill switch, link baseline).

## [1.1.0] — 2026-07-11

Workstyle adaptability (owner-requested; designed pre-release, built under
DEC-030): the system learns how its user already works instead of imposing
its own method.

- **Workstyle map** (`80 User/workstyle.md`, drafted at onboarding stage 4):
  the user's vocabulary, groupings, tag translations, rituals, load-bearing
  machinery, a binding keep list, and a coexistence posture. User-owned;
  deleting it restores default behavior exactly.
- **Observe first, confirm second**: with one explicit consent, the AI reads
  the user's existing corpus read-only and DRAFTS the map for correction;
  only intent (keep list, posture, tag meanings) is ever asked. Full
  interview remains as the no-corpus fallback. Onboarding spec v1.1.0.
- **Capability awareness**: safe-write and ingest-and-connect consult the
  map — user's terms in every filing report, their tags applied verbatim
  alongside standard fields; keep/machinery lists are absolute.
- **Router `load_if_present`** (v1.1.0): user-created files a route consults
  when they exist — absent on a fresh seed, never an error; integrity-tested.
- **Fixtures 11 (adaptation) + 12 (inference)** added to the L3 battery;
  new template `System/Templates/workstyle.md`; How the System Works §11
  ("If you already have a system", with the PARA mapping).

## [1.0.6] — 2026-07-10

Tone fix (owner catch): the README's license note dropped its finger-wagging
second sentence — it now states only what the license covers, positively.
The license file itself does the boundary-setting. Also: one leftover
"skills" in LICENSE.md updated to "capabilities."

## [1.0.5] — 2026-07-10

README reframed for licensed distribution (owner catch): "download or clone
this repository" invited redistribution. Copies now come from the
implementer; the ownership promise (your copy is yours — portable, editable,
backed up, vendor-free forever) is stated more strongly, alongside a plain
note that the license covers your copy, not passing copies along.

## [1.0.4] — 2026-07-10

Obsidian arrives pre-configured (owner-tested in a live trial vault before
shipping). The vault now ships a curated `.obsidian/`:

- **Three plugins included** — Notebook Navigator, Git, Dataview — their code
  travels inside the vault (~6.5 MB, MIT-licensed, freshly harvested); one
  trust-click on first open is the entire installation.
- **Every Setup-Tips setting pre-applied**: dark mode, auto-updating links,
  attachments → `30 Sources/Attachments`, new notes → `00 Inbox`, templates
  folder, the Cmd+T/Cmd+N hotkey swaps, unused core plugins trimmed.
- **A minimal workspace seed**: left sidebar pre-widened to 450px in
  Notebook Navigator dual-pane mode — layout skeleton only, zero session
  state (stale copied workspace state was identified as the reason copied
  plugins historically appeared broken).
- Docs reframed: the Tips now document what arrived and why; Quick Start and
  the Implementation Guide mention the single trust prompt. Instance
  `.obsidian/` folders are user-owned and never touched by product syncs.

## [1.0.3] — 2026-07-10

Hotfix: the drift test's bare-word rule flagged instance-added router routes
that use the owner's own domain vocabulary (found on the live customized work
instance). The rule is scoped off `System/Runtime`; specific retired-artifact
names still guard it, and router-integrity tests catch dead loads.

## [1.0.2] — 2026-07-10

Hotfix: the retired-machinery drift test scanned user content in `00 Inbox`
and `90 Archive`, so any lived-in personal instance failed its own test
suite on legitimate user words (found on the first post-1.0.1 instance run).
The test now scans only the structural `_`-prefixed guide files there.

## [1.0.1] — 2026-07-10

Fixes from the first two real-workload imports (customized work-instance vault, 1,095
files; second historical corpus, 444 files) — the class of defect only a foreign
corpus at scale reveals.

- **dupes** (F-1, high): the documented supersede-and-archive workflow no
  longer reddens health — 90 Archive and superseded/archived records are
  exempt; title collisions error only when two typed canonical records
  collide, and warn for untyped/legacy files converging gradually. Folder
  paths resolve via the registry.
- **links** (F-2): non-note wikilinks (images, PDFs, any file) resolve by
  vault-wide basename, matching Obsidian semantics.
- **migrate** (F-3): new `transform: {script: <file>}` — migration-local
  scripts run under the runner's own discipline (kill switch, checkpoint-or-
  halt, dry-run default, validate-after, journal). Checkpoint-or-halt now
  also guards the rename path.
- **validate** (F-4): folders registered `conventions: foreign` collapse
  per-file no-frontmatter warnings into one count line.
- **docs** (F-5, F-6): bring-your-`.obsidian` guidance for corpus imports;
  filename rules stated at every capture entry point.
- 5 new regression tests (42 total). Real-corpus verification: a 1,095-file
  import went from 22 permanent health errors to green.

## [1.0.0] — 2026-07-10 — RELEASED

The supervised, light product (DEC-028): the owner, friends, and
implementer-led clients. Release evidence, commit-bound and dated:
`System/Tests/results/release-evidence.md`.

- Portability gates 1–5: PASS on the frozen candidate (Obsidian independence,
  generated-state independence, path move, case/character, full 13-step
  acceptance incl. second-runtime simulation and no-git change/rollback).
- Certification battery: 10/10 fixtures PASS, owner-present observer —
  L0–L3 certified for the reference runtime on this exact state.
- Gate 6 (owner-only recovery walkthrough): waived by owner (DEC-029); the
  mechanical recovery paths (zip-only restore, rollback-while-off, exact-tree
  restore) are proven in the evidence.
- Pressure-tested: a clean instance through two simulated weeks, 1,632-file
  scale, hostile input, git-less life, and crash-mid-operation — two defects
  found and fixed before freeze (P-1, P-2).
- v1 platform claim: tooling CI-proven on Linux (Python 3.9/3.11) and macOS;
  vault files are plain text everywhere.

## RC hardening line after 1.0.0-rc.1 — 2026-07-10 (later the same day)

Everything after the rc.1 correction, in order. The manifest stays at
1.0.0-rc.1 throughout; spec version advanced 1.0.1 → 1.0.7.

- Product/person separation (DEC-020/021): personal data prohibited in the
  generic master, CI-enforced tripwire; private instance data split out.
- Pointer-only Claude adapter — runtime mirror copies removed (DEC-022).
- Progressive disclosure (reviewed change, DEC-023): Runtime Kernel + Task Router;
  always-loaded context −74%; four test-vault-proven bug fixes.
- Lean architecture (reviewed change, DEC-024): six single-file capabilities replace
  eleven skills; hand registry deleted for a generated index; lazy generation.
- Second independent-audit repair set: onboarding state parity;
  zero-trace generated-state privacy at the hosted floor; de-personalized
  seed + protected authority files (DEC-025: ships read-write, never ships
  another instance's certifications); exact-tree rollback; real activation;
  router v0.2.0 with integrity tests; journaling unified on kernel lanes.
- Delta-audit closure (DEC-026): uncertified runtimes ship at L2 (L3+ earned
  via the certification battery); no field-level secrecy promises — privacy
  filtering is whole-record and what enters the vault is the user's choice;
  router routes carry their full dependency sets with a closure test;
  activation requires a recorded passing result; architecture spec body
  reconciled with the lean implementation (v1.0.7); compact product-local
  decision register installed.

## [1.0.0-rc.1] — 2026-07-10

Status corrected per independent audit (ChatGPT 5.6) and DEC-017: the v1.0.0
acceptance was premature — the system's own release rule requires all
portability and recovery gates to pass. Repairs on branch
maintenance change per decisions DEC-013 through DEC-018.
