---
id: doc-backup-and-recovery-options
type: system-doc
file_class: canonical
authority: canonical
canonical_for: backup-options
version: 1.1.1
created: 2026-07-14
updated: 2026-08-13
summary: "Every way to back up your vault, with honest tradeoffs, so you can choose. Onboarding links here; nothing is prescribed. The vault is plain files — backing it up is copying a folder, done well."
---

# Backup and Recovery Options

Your vault is plain files in a folder. Backing it up is, at bottom, **keeping a copy somewhere the loss of this computer can't reach** — plus a way to undo a bad change. This doc lays out every option with its honest tradeoffs so you can pick what fits. There is no single "right" answer, and you can combine several. Onboarding walks you through choosing one; you can revisit anytime.

## The two things backup protects against (they're different)

1. **A bad change** — you or the AI edited or deleted something and you want it back. Solved by *versioned* or *snapshot* backups you can roll back to (the vault's built-in checkpoints already do this — see the Maintenance and Recovery Guide).
2. **A dead machine** — the laptop is lost, stolen, or fails. Solved only by an **off-machine** copy: another disk, or a remote. Same-machine snapshots do *not* protect against this.

A complete posture usually covers both. Ask of any option: *is the copy off this machine? does it happen automatically? is it encrypted? does it survive losing an online account?*

**A related event, separately solved: moving to a new version.** "How do I update when a newer release ships?" is not a backup question — it has its own one-command answer, `aios upgrade`, which brings your `System/` current while leaving your notes and customizations untouched and never merging a conflict silently (see `Upgrading.md`). Backup and upgrade pair up: take a checkpoint before you upgrade, and a bad update is just another *bad change* you can roll back.

There's a third risk most backup advice ignores: **a backup you can't read later.** A copy is only as good as the format it's in — an export from a proprietary app can be worthless once that app is gone. That risk doesn't apply here, and you can prove it rather than assume it. Your knowledge folders are plain Markdown in Google Cloud's **Open Knowledge Format** (OKF v0.2, the current spec), so any backup of them is readable with a text editor forever and usable by any tool that speaks the format. Run `aios okf-check` on a restored copy to confirm the format survived the round trip.

## Your options

| Option | Off-machine? | Automatic? | Encrypted? | Account-independent? | Notes |
|---|---|---|---|---|---|
| **GitHub private remote** | ✅ | on push | in transit + at rest (GitHub's) | ❌ needs the account | Free, full version history, easy to restore anywhere. A hosted copy — so keep truly sensitive content out of it (see below). |
| **obsidian-git auto-push** | ✅ (to GitHub) | ✅ every N min | same as GitHub | ❌ needs the account | The plugin that automates the GitHub push, so edits back up without waiting for a session. Setup in `Obsidian Setup Tips.md`. |
| **Encrypted external drive** | ✅ | ❌ manual (`System/Scripts/backup-clone.sh` makes it one command) | ✅ (you set it) | ✅ | Survives losing any online account; nothing hosted. The most sovereign option; the cost is remembering to plug it in. Best paired with an off-site second drive. |
| **Built-in zip snapshots** | ❌ same machine | on checkpoint | ❌ | ✅ | `aios checkpoint --zip` writes a verified exact snapshot beside the vault and prints its identity-bound rollback command. Protects against bad changes, **not** a dead machine. |
| **Cloud-synced folder** (iCloud/Dropbox/Drive) | ✅ | ✅ | provider's | ❌ needs the account | Easiest, but it's a hosted copy of *everything* in the folder — same sensitivity caution as GitHub, and sync conflicts can corrupt an actively-edited vault. |
| **Whole-disk backup** (external drive image, etc.) | ✅ if the target is | ✅ if scheduled | depends | ✅ if the target is yours | Catches the vault as part of everything. Independent of the vault's own tooling. |

## The one hard rule: sensitive content stays off any cloud

Whatever you choose, content you'd never want on someone else's servers — for many people that's anything about politics, religion, health, or personal relationships — should **not** go to GitHub, a cloud-synced folder, or any hosted remote, even a private one. This rule now has its own field: mark such content `sync: local-only` (or keep it in a `Local Only/` folder, which implies the marking), and back it with a `.gitignore` rule so git-based backups skip it automatically — `aios validate` checks the marking and the rule agree in both directions, so the promise is enforced rather than remembered (DEC-092; the full rules live in `System/Governance/Privacy and Boundaries.md` §2 — cross-referenced here, not duplicated). Note what `.gitignore` does *not* cover: a cloud-synced folder (iCloud/Dropbox) or a whole-disk image copies **everything**, ignored or not — if you use those, keep `sync: local-only` material outside the synced folder or accept that only the encrypted-drive path honors the boundary. `ai_use: local-only` is the separate switch that keeps material off hosted AI; sensitive content usually wants both. Encrypted external drives are the safe home for local-only material you still want backed up.

## A sensible default (one example, not a mandate)

A common, robust setup: **GitHub private remote** (via the obsidian-git plugin for automatic pushes) for everything shareable, **plus an encrypted external drive** copied every week or two for a fully-owned, account-independent copy — with sensitive content kept off GitHub and only on the encrypted drive. That covers both failure modes and both sovereignty and convenience. But it's one example; a privacy-maximalist might use only encrypted drives, and someone who lives in Obsidian might lean on obsidian-git plus occasional zips.

## How the vault knows a backup happened: the marker

A backup nobody records is a backup nobody can rely on. The convention is one small file:

**`80 User/LAST-BACKUP.txt`** — first line `last_backup: <ISO date>`, e.g. `last_backup: 2026-07-25T12:00:00Z`. `aios health` reads it and, whenever content marked local-only exists (a `Local Only/` folder or `ai_use: local-only`), reports how many such files exist on this machine only and the last recorded backup date — *never* as a guarantee, always as "last **recorded** backup": the marker is evidence of that one run, nothing more. No marker means **never**, period — the check cannot be talked into a false "covered." The default staleness window is 30 days; tune it with an optional `window_days: <N>` line in the marker itself.

Two ways the marker gets written:

- **`System/Scripts/backup-clone.sh`**, run with your destination path — the exact drive-clone helper (macOS/Linux, `rsync` required). It mirrors the whole vault, including deletion of destination files that no longer exist in the source, and writes the marker only after the exact copy succeeds. It refuses when `rsync` is unavailable, when the destination is inside the vault, or when the destination holds unrelated files; an additive copy is never labeled current.
- **You copied by hand** (Finder drag, `cp -R`, whatever works). Then record it yourself — one command, run in the vault folder:

  ```
  date -u +"last_backup: %Y-%m-%dT%H:%M:%SZ" > "80 User/LAST-BACKUP.txt"
  ```

Options that are automatic and versioned (GitHub remote, obsidian-git) are their own evidence — `git log` knows when you last pushed — so the marker matters most for the manual paths, which are exactly the paths that guard your most sensitive content.

## Restoring

- **Undo a bad change:** run the exact `rollback_command` printed by checkpoint. It authenticates the Git tree or snapshot, preserves displaced bytes, restores exactly, and validates. Full steps: `Maintenance and Recovery Guide.md` Part 3.
- **Recover from a dead machine:** install the tools on the new machine, clone your GitHub repo (or copy from your drive), open the folder. Everything is there — it's just files.

## Set it up

Onboarding offers to help you choose and connect one (typically the GitHub remote). To do it yourself later: create a private repo, add it as the remote, push — or enable the obsidian-git plugin (`Obsidian Setup Tips.md`) to automate it. For an encrypted drive: format it encrypted, then run `System/Scripts/backup-clone.sh` (destination: a folder on the drive) on your chosen cadence — or copy the folder by hand and touch the marker (one command, above).
