---
id: doc-upgrading
type: system-doc
file_class: canonical
authority: canonical
canonical_for: upgrading
version: 1.5.1
created: 2026-07-16
updated: 2026-08-14
summary: How upgrades use a read-only semantic review, exact reviewed apply, transactional candidates, exact recovery, release identity, and license-transition preconditions.
---

# Upgrading to a new version

> **Recovery release.** Real rehearsals upgrading to 1.64.0 failed after files had already been applied, leaving mixed-version installations. Version 1.64.1 is the repair target. Keep an external backup and do not use it on an irreplaceable or only copy unless the tagged release carries passing transactional-upgrade, historical-upgrade, and exact-recovery qualification evidence.

> **Current publication release.** Version 1.64.2 integrates the public documentation and release assets. Before upgrading an irreplaceable or only copy, verify that the `v1.64.2` tag resolves to the release commit and that its separately published, target-bound qualification evidence passes. The historical 1.64.0 and 1.64.1 statements above remain part of the upgrade record.

When a new version of the system ships, `aios upgrade` brings your `System/` folder — plus the
handful of **product-owned root files** — up to it. Your notes, your `80 User/` configuration,
your `.obsidian` setup, your installed `Packs/`, your change journal, and your test records are
never touched — not read for merging, not rewritten, not moved.

## Which root files are the product's, and which are yours

The vault root mixes product files with your files, so the list is explicit (encoded in the
command itself, one deliberate call per file):

- **Product-owned — upgraded like `System/` files**: `CLAUDE.md` (the AI adapter pointer),
  `pyproject.toml`, `README.md`, `START-HERE.md`, `CONTRIBUTING.md`, and `SECURITY.md`. Same rules as everything else: if you edited
  one, your edit is kept or flagged as a conflict — never overwritten.
- **Yours — never touched by ordinary file classification**: `LICENSE.md`, `CHANGELOG.md` (it records
  *your vault's* journey; the release's own history arrives in the release tree),
  `SYSTEM-MANIFEST.yaml` (only your version number is updated, as before), and
  `CONNECT-CHECK.md`.
- **Seeded once, then yours**: root files a release introduces (`To-Do.md`, `Decisions/`)
  arrive as **new files only if you don't have them**. The moment they exist they are your
  content, and no upgrade will ever replace, merge, or remove them.

### Distribution and license preconditions

`system.distribution_id` identifies the release line independently of
`system.id` and `instance_role`. Core declares `personal-ai-os`; PMM Engine
declares `pmm-engine`. A migration manifest binds exactly one
`source_distribution`, and an absent, unknown, or different value refuses the
edge before a transform. A matching version string or core baseline is not
enough.

License transitions are the narrow exception to ordinary root-file ownership.
They use hash-bound migration data: only the recorded legacy license hash (or
the already-correct target hash) is accepted; any modified or unknown license
blocks for review. A separately licensed pack must first carry its own license
inside its pack and point `pack.yaml` to that file. PMM therefore never takes
the `personal-ai-os` MIT edge, and its root license may not be replaced until
that attachment and `pmm-engine` identity are both present.

(Before v1.42.0 upgrades skipped root files entirely, which could leave `CLAUDE.md` versions
behind — if your vault upgraded across that era, expect these files to appear as conflicts once
and resolve them by hand.)

## One behavior specific to knowledge freshness

The freshness feature (ripple checks, review clocks, workflow cadence) activates **per vault, not
per release**: the product ships `System/Registries/freshness.yaml` with `enforced_since: null`,
and *your* vault's first `aios generate` after the upgrade stamps that date and quietly baselines
every existing note. Nothing you wrote before that moment accrues ripple or review obligations —
an upgrade never turns years of old notes into a to-do list.

## The short version

Run the launcher that came **inside the new release**. This direction matters:
an older vault may contain an older, unsafe upgrade command, so never initiate a
cross-version upgrade with the installed vault's `System/Scripts/aios.py`.

```bash
# Review only — both paths must be absolute.
python3 /path/to/new-release/upgrade-existing.py \\
  --installed /path/to/your-existing-vault \\
  --authorize-official-legacy-core

# Apply the exact fresh plan through the SAME new-release launcher.
python3 /path/to/new-release/upgrade-existing.py \\
  --installed /path/to/your-existing-vault \\
  --authorize-official-legacy-core \\
  --apply --confirm --review-sha256 <printed-hash>
```

The legacy authorization is accepted only when the installed tree exactly
matches the release's frozen allowlist of official Personal AI OS versions; a
same-version rival, modified identity, or different distribution still refuses.

The release is a folder: a copy of the new version, unzipped or checked out. You do not need Git,
a GitHub account, or a network connection — a zip someone hands you is enough.

**The bare command is always read-only.** `--dry-run` is an optional explicit alias for the same
mode. It creates no checkpoint or candidate. Read the classification and the stated semantic-plan
limitation, then approve only the printed hash. If the live vault, release, baseline, migration,
accepted conflicts, or protected-object policy changes, the hash goes stale and apply refuses the
whole operation; run the bare command again and review the new plan.

The review is exact about **semantic inputs**, not bytes that do not exist yet. Candidate-local
migrations, generation, and documentation refresh materialize final output only during apply. The
plan says that directly. The transaction journal then pins the full materialized tree identities
used for exact recovery; neither stage pretends to prove the other.

## What it does, in order

1. **Reviews without writing** — the release, distribution, versions, baseline, classification,
   accepted conflicts, seeds, migration inputs, and protected-object policy are bound into one
   deterministic semantic plan. No checkpoint or candidate exists yet.
1b. **Starts only the approved apply** — `--apply --confirm` plus the exact fresh review hash is
   required. The command re-proves the plan, then creates the checkpoint. If reproof or checkpoint
   fails, no candidate is published and the live tree is unchanged.
2. **Sorts every `System/` file (and product-owned root file) into one of four piles** by comparing three versions of it: what
   your version originally shipped (the baseline), what the new release carries, and what you
   actually have on disk.
   - **replace** — you never touched it, so it takes the new version.
   - **keep** — you customized it and the release didn't change it. Your file stays. Reported.
   - **conflict** — you customized it *and* the release changed it. **Your file stays untouched**
     and lands on a review list. Nothing is ever auto-merged.
   - **add / remove** — new files arrive; files the product retired (and you never edited) go.
3. **Rebuilds and checks** — `generate`, then `validate` and `health`. If any of them go red, the
   report says so loudly and points at your checkpoint. It will not tell you it worked when it
   didn't.
3b. **Proves your files were not touched** — it fingerprints every file it promised to leave alone
   *before* it starts and checks them again at the end, byte for byte. Anything that moved is a
   hard failure telling you to roll back, not a footnote. The report says what the check covered:
   **every file outside the upgrade surface** — your content folders (all of them, including any
   you added and registered yourself), `80 User/`, `Packs/`, your `.obsidian` settings, your change journal,
   your test records, and your own root files. It excludes `System/Generated/` and `System/Logs/`
   from this byte-identity claim and names that exclusion rather than letting "verified" imply it.
   The reason is different for each: Generated is rebuilt; Logs is mixed runtime state, including
   durable freshness history and live obligations, and is preserved under its own contract rather
   than mislabeled as wholly rebuildable.

   *(Before v1.54.0 this check walked a fixed list of folder names and missed anything outside it.
   On a real work vault that meant 160 files verified out of 1,641 — the other 1,102 sat in content
   folders that vault had registered itself. The report said "byte-identical" either way. It is now
   computed as everything-except-the-upgrade-surface, so a folder you invent tomorrow is covered
   the day you make it.)*

   **You can leave Obsidian open.** Since v1.60.0 the one thing this check does *not* judge is your
   editor's own session state — `.obsidian/workspace.json` and its siblings, the files that record
   which panes you have open. Obsidian rewrites them by itself whenever the vault changes, and step
   3 changes the vault, so before v1.60.0 every upgrade run with the app open ended in
   `CONTENT INTEGRITY FAILURE` and refused to record the new version. Your `.obsidian` *settings* —
   hotkeys, appearance, plugin configuration — are yours and are still verified byte for byte. If a
   session-state file does move during a run, the report names it and says why it was not counted.
4. **Updates your version number** — but only if the checks are green, no migration is still
   waiting, and every conflict in a protected file is **accounted for** (see below). Otherwise your
   version stays where it is, because claiming the new one would be a lie.
5. **Writes a report** to `System/Logs/` listing every file in every pile, plus the checkpoint to
   roll back to.

## Why a conflict does not always stop the version bump

Customizing your vault must not cost you the ability to record that you upgraded. Until v1.56.0 it
did — and the vault it hit hardest was the tidiest one. A real work instance took a release
cleanly, passed **every** check with zero errors, had 318 of the 322 shipped files byte-identical,
and still could not update its version number. Its only two divergences were a **customized Task
Router**, which this system explicitly invites you to have and promises never to merge, and the
**regenerated counts in its constitution**, which `aios health` *requires* it to regenerate. Both
were things the product had asked it to do. Accepting either meant never bumping again, ever.

So the gate now asks *why* a protected file differs, not merely *whether* it does. A conflict is
**accounted for** in exactly three ways:

| | What it means |
|---|---|
| **sanctioned** | The product declares this file yours and never auto-merges it. Today that is the Task Router. |
| **derived** | The two copies differ **only** inside generated `<!-- docgen:… -->` blocks — numbers each side counted from its own vault. If *anything* outside those blocks differs, even one sentence, this does not apply. |
| **accepted** | You reviewed the conflict and named it: `aios upgrade <release> --accept "System/Governance/Some File.md"` (repeatable). |

Anything else still blocks the bump, exactly as before.

**None of this changes your files.** An accounted conflict is still a conflict: your copy is kept
untouched, nothing is merged, and it still appears on the review list. `--accept` does not resolve
the file for you — it records that *you* looked and decided. What changes is only whether the
version number is allowed to move.

And the version number carries its own caveat. If the bump was granted over declared divergences,
the manifest says so on the same line:

```yaml
system_version: 1.56.0       # upgraded from 1.55.0 via aios upgrade — 1 declared divergence(s) kept: System/Runtime/Task Router.yaml (see the upgrade report)
```

The upgrade report lists each one under its own heading, with the reason. If you `--accept` a path
that isn't actually in conflict, you get a warning rather than silence — a typo should never read
like a resolution.

## The Task Router is special

Your router (`System/Runtime/Task Router.yaml`) usually holds rows the product shipped **and** rows
that are yours. If both you and the release changed it, the upgrade **never merges it** — it leaves
your file exactly as it is and gives you a per-row list: which rows are only yours, which are new
in the release, which differ. You copy across what you want. Losing your router rows is the worst
thing this command could do, so it does not take the chance.

## Migrations

If the new release carries a direct migration for this exact source, upgrade
selects it before checkpoint creation using the old version, target version,
canonical baseline identity, and every declared old-file hash. Exactly one edge
must match. The public migration command remains preview-only:

```bash
python3 System/Scripts/aios.py migrate --migration <name>
```

Direct `--apply` is refused. Upgrade applies the selected edge only inside its
owned candidate, after the target package and baseline arrive and before
generation and final validation. A mismatch or ambiguity leaves the live tree
untouched.

## When it refuses

- **"already at version"** — you're current. Running it twice is safe; the second run does nothing.
- **"release is OLDER"** — going backwards is a restore, not an upgrade. Use a checkpoint or a
  snapshot zip (see `System/Documentation/Maintenance and Recovery Guide.md` Part 3).
- **"fused customizations"** — you have edits inside many protected files. An upgrade can't safely
  separate your work from the product's there; the message names the files.
- **"no baseline"** — your version predates baseline manifests, so the command can't prove which
  files are untouched. It falls back to the safe reading: **every difference is a conflict, nothing
  is replaced**. Point it at the old release with `--base ../old-release` to get exact answers.

## If something goes wrong

Every run reports its checkpoint and exact rollback command first. To undo, run
that printed command unchanged. Its recorded full commit/snapshot identity and
SHA-256 are required for the exact recovery proof. The generic form is:

```bash
python3 System/Scripts/aios.py rollback <checkpoint> --expected-sha256 <printed-sha256> --confirm
```

Full recovery instructions: `System/Documentation/Maintenance and Recovery Guide.md` Part 3.

If a prior upgrade left an authenticated unfinished transaction, the bare command reports a
separate **recovery semantic review**. Recovery also requires its newly printed
`--apply --confirm --review-sha256 <hash>`; an ordinary upgrade approval cannot be reused to clean
up or resume a different transaction state.

## A note on authority

This command writes into protected paths — that's its job. The rule in
`System/Governance/Change Control and Preflight.md` is that protected objects change only on
explicit human instruction bound to the reviewed operation. **Running the bare command is not that
instruction; it is read-only.** Authority for apply is the human's deliberate use of `--apply
--confirm` with the exact fresh hash they just reviewed. It is never automatic, never scheduled,
and never something an AI decides to do on your behalf.
