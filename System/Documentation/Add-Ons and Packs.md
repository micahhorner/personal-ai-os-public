---
id: doc-add-ons-and-packs
type: system-doc
file_class: canonical
authority: canonical
canonical_for: add-ons-and-packs
version: 1.2.0
created: 2026-07-14
updated: 2026-08-09
summary: "What an add-on is, and how exact reviewed install/update and transactional removal protect its vendor files, user workspace, activation authority, and recovery."
---

# Add-Ons and Packs

Your AI OS can be extended with **add-ons** — new capabilities you install when you want them (a content engine, a role pack, a life-skill pack). An add-on is not baked into the core; it is something you add and can remove without a trace.

An add-on is distributed as a **pack**: a single self-contained folder carrying a `pack.yaml` manifest plus its components. Because a pack is just a folder, the whole lifecycle is simple.

## Install

1. Download the pack — usually GitHub's **"Download ZIP"** button (no git required).
2. Drop the ZIP into your **AI OS root folder** (the top folder of your vault — the one place you can't get wrong).
3. Tell your AI: *"install the new pack."*

Your AI reads the pack's manifest, labels the pack's prose and declared gates as the publisher's claims, and shows you the exact plan plus its review hash. After you approve that hash, apply requires `--apply --confirm --review-sha256 <printed-hash>`. A changed archive or mismatched hash refuses before placement. The command checks the frozen archive in staging, checkpoints, places it, validates, writes an activation receipt bound to the reviewed and installed hashes, then refreshes the index. A ZIP you deliberately dropped in the vault root is removed on success; a ZIP selected from outside the vault is caller-owned and preserved.

This requires an AI that can read and write your folder (Claude Code, Cowork, or Codex). A chat app that can only read your files can't install a pack.

## Update

The same gesture. Download the newer ZIP, drop it in the root, and ask your AI to install it. Because the pack is already there, your AI treats it as an update: it checks the version and replaces the vendor's files with the new ones.

**What "replaces" covers depends on whether the pack declares a workspace** (see below). A pack that declares none — the original and still the default — has its whole folder swapped, a clean replacement and never a merge. A pack that declares one keeps your side of it untouched.

The plan you approve before anything is written always says which it is, in words. If a pack declares no workspace, the plan says so outright rather than staying silent about it.

## Scaffold and workspace: which files are the vendor's and which are yours

Early packs were pure vendor material — a capability and a reference file — so replacing the folder wholesale was exactly right. A **role pack** is different: once you are working in it, `Packs/<name>/` holds your own messaging, your enablement library, your research, your published work, your voice profile. Replacing that folder would take all of it, and report success.

So a pack may declare a `layout:` block in its `pack.yaml`, naming three kinds of path:

| Class | Whose | On update | On removal |
|---|---|---|---|
| `scaffold` | the vendor's | replaced | deleted |
| `workspace` | **yours** | **never touched** — not read, not diffed, not replaced | **archived, never deleted** |
| `seed` | the vendor's starter content, yours once it exists | written only where the file is **absent** | **archived, never deleted** |

The most specific declaration wins, so a pack can keep a vendor-maintained folder inside your workspace (or the reverse). **A path nobody declared is scaffold**, which is why a pack with no `layout:` block behaves exactly as packs always have.

Two details worth knowing:

- **A scaffold file *you* edited is never overwritten and never auto-merged.** Your copy stays; the incoming version is written beside it as `<name>.incoming` and reported, for you to merge by hand. The system knows which files you touched because it fingerprints the vendor's scaffold when the pack is installed.
- **The vendor never re-seeds.** Once a workspace folder exists it is yours, including any EXAMPLE files you chose to keep — and if you deleted them, they do not come back.

A pack declaring `layout:` must also declare `min_system_version: '1.57.0'` or newer. An older system would not understand the block and would replace the whole folder; the version floor is what stops it from installing there at all.

## Remove

Any of these:

- Tell your AI: *"remove the &lt;name&gt; pack."* It transactionally archives declared user workspace, quarantines the pack, rebuilds and validates while removal is reversible, then commits the removal.
- You can delete `Packs/<name>/` manually, but that bypasses workspace archival, path-safety checks, rollback, and the validation gate; the governed command is the safe route.
- Or just leave it. An installed pack you don't use sits quietly and does nothing until you ask for it.

**If the pack declared a workspace, removal preserves exact copies under `90 Archive/packs/<name>-<date>/` rather than deleting them**, keeping the folder structure, and tells you exactly what it retained and where. The pack and archive are committed together only after generated state and validation pass. A symlinked, special, hard-linked, changed, or colliding source refuses rather than producing an ambiguous archive.

To delete everything including your workspace, ask for a **purge**: `aios pack <name> --remove --purge --confirm`. It is the only route to that, it has to be asked for by name, and it states how many files it is about to take — including how many are yours — before it takes them. The same reversible quarantine and validation transaction applies; purge changes only the final archive decision.

## Checking what is inside a pack — `aios pack-check`

The vault's everyday checks (`aios validate`, `links`, `dupes`) deliberately **do not look inside `Packs/`**. They must not: a pack ships its own `README.md` and `CHANGELOG.md`, and its notes carry their own ids, so folding them into the vault's canon would report collisions that are not collisions.

The cost of that is worth stating plainly, because it is easy to misread a green result: **on a vault whose knowledge arrives through a pack, a green `validate` is evidence about the vault *around* the pack, not about the pack.** On one real instance that was 165 files checked out of 446.

`aios pack-check` closes it. It reads every installed pack **as a pack** — resolving that pack's ids, titles and links against itself plus your vault, in its own pass — and reports:

- frontmatter that will not parse, a `type` that is not a real class, a `subtype` in no vocabulary, an id that does not match its type
- duplicate ids **within** a pack (an error) — an id **shared with your vault** is only a note, because a pack is entitled to its own namespace
- wikilinks and frontmatter relations that resolve to nothing
- duplicate titles, and files with no frontmatter (both advisory — a pack's READMEs have none by nature)
- anything that looks like a committed credential

**A pack's templates are read as templates.** A template carries a blank where its id will go —
`id: note-<slug>` — and a folder of templates sharing that blank is not a folder of notes claiming one id.
Since v1.60.0 a placeholder id inside a `Templates` folder is left alone, exactly as `aios validate`
has always left the product's own `System/Templates/`, and an empty `[[ ]]` link slot is reported as
the blank it is rather than as a broken link. The tolerance stops at the folder: an unfilled id in a
shipped **record** is an error, because that is a note nobody finished.

Nothing it reads is merged into your vault. Pack ids stay the pack's; `validate` and `dupes` see exactly what they saw before.

It runs inside `aios health` (and therefore `aios certify`), rolled up to a single line, so you do not need to remember it. On the product master these findings are errors — a pack shipping to customers should be clean. **In your own vault they are warnings**, because your content is yours.

## Citing a pack note from your own notes

A note outside `Packs/` may reference a note inside one — `sources: [source-example-northwind]` — and it resolves. It used to be a hard error, which meant a note that declared where its material came from turned your checks red while a note that stayed green could not declare it.

The reference resolves; it does not merge. And because those references are real, **removing a pack that your notes cite is refused**, and the notes are named, so an uninstall cannot quietly leave your vault pointing at nothing. Edit or drop the references first, then remove.

## What the manifest has to say — and what happens when it doesn't

Every pack carries a `pack.yaml` at its root. The full contract is
`System/Schemas/pack-manifest.yaml`, and `aios pack --verify` gates against that file rather than
against rules buried in code — so a pack author can read what they will be held to before they ship.

Six keys are required: **`id`** (`pack-` plus lowercase letters, digits and hyphens — the folder name
is the id minus the prefix), **`name`**, **`version`** (semver `X.Y.Z`, the pack's own, independent of
your system version), **`kind`** (one of `capability`, `role-pack`, `life-skill-pack`,
`governance-kit`, `starter-bundle`), **`license`**, and **`source`** (an `https://` URL). Optional:
`summary`, `min_system_version`, `depends_on`, `components`, `resources`, and `gates` — the pack's own
standing rules, shown to you verbatim before you approve an install.

**What a pack ships can be written either way.** `components:` and `resources:` may be a mapping of
group → paths, or a flat list, and `resources:` may sit at the top level or nested inside
`components:`. All four combinations are valid, and both shapes are in the field. The check is only
whether each listed path exists in the ZIP; a path naming a folder is satisfied by anything inside it.

**A pack from a stranger fails safely.** The manifest is third-party input, so the gate is written to
report rather than break: a malformed, mistyped, wrongly shaped, corrupt, encrypted or non-UTF-8
manifest produces a plain description of what is wrong, a REJECTED verdict, and **no change to your
vault at all** — no checkpoint, no partial install, nothing to undo. Paths are confined to the pack's
own folder; a ZIP that tries to write anywhere else is refused outright, before anything is touched.

## Where add-ons live and how they run

Installed packs live in the top-level `Packs/` folder, one folder per add-on. A pack's capabilities are discovered in place and run **by name** — you ask for them (for example, *"run the content engine"*). They don't silently change how your OS behaves; you invoke them deliberately.

## Where to find add-ons

Your OS already ships with one pack installed: **obsidian-bases**, the first third-party pack, lives in `Packs/` out of the box — a working example of the format you can inspect, use, or remove without a trace.

Beyond the bundled one, packs are published as GitHub repositories. The free-updates newsletter announces new packs and versions as they ship. (A browsable catalog is planned.)
