---
id: doc-maintenance-and-recovery-guide
type: system-doc
file_class: canonical
authority: canonical
canonical_for: maintenance-and-recovery
version: 1.1.1
created: 2026-07-10
updated: 2026-08-14
summary: Keeping the system healthy, fixing what breaks, and — most importantly — recovering everything with nothing but a file manager and a text editor.
---

# Maintenance and Recovery Guide

## Part 1 — Maintenance (normal life)

- **Weekly**: the `weekly-maintenance` workflow in `System/Workflows/` (the Steward runs it; you get a short judgment-call list — your half is just deciding those calls).
- **Signals something needs attention**: the Inbox aging past two weeks · a review queue over ~10 items (retune, don't push harder) · validation warnings you don't recognize · the journal showing changes you didn't expect.
- **Read-only checks** (safe to run without changing vault content): `health`, `validate`, `links`, `dupes`, `doc-check`, `doc-commands`, `doc-audit`, `doc-paths`, `certify`, `review-due`, `measure <transcript>`, and `dedupe-batch <folder>` (unless you explicitly add its writing `--annotate` option). `doc-commands` checks command coverage; `doc-audit` checks source-backed counts; `doc-paths` checks cited `System/` paths.
- **Commands that write or can publish state** (run only when you intend their documented effect): `generate` rebuilds indexes/views; `checkpoint -m "label"` creates a recovery point and may commit the selected tree (`--zip-only` makes only a snapshot; `--paths` narrows a Git checkpoint; `--strict` refuses when other changes exist); `review-due --set-missing` stamps dates; `extract <file.docx>` preserves the original and emits verified Markdown only after its checks; `dedupe-batch <folder> --annotate` changes frontmatter. Apply/remove/rollback commands have their own explicit confirmation gates. The kill switch and proportional preflight still apply.
- **When a new version ships**: run the **new release's** `upgrade-existing.py --installed /absolute/path/to/your-vault --authorize-official-legacy-core` to get the read-only semantic plan and review hash; never run an older installed vault's upgrade code. Apply only through that same new-release launcher with `--apply --confirm --review-sha256 <printed-hash>`. A stale or changed plan refuses. It keeps your notes, `80 User/`, `.obsidian`, `Packs/`, and journal, and never merges a conflict silently. Full commands: `System/Documentation/Upgrading.md`.

## Part 2 — Troubleshooting

| Symptom | Fix |
|---|---|
| Indexes/views look wrong or missing | `aios generate` — they're disposable; regeneration is the whole fix |
| Validation errors after an edit | Read the message — it names the file and field; the Metadata Dictionary defines every field |
| A note the AI changed looks wrong | Journal (`System/Journal/change-journal.md`) shows what happened; restore from checkpoint if needed (Part 3) |
| Scripts won't run: `No module named 'yaml'` | `python3 -m pip install --user "PyYAML>=6.0,<7"` — the system's only dependency |
| Scripts won't run at all | You don't need them to read/edit/export — everything is plain files; fix Python later |
| Answers cite the wrong notes, or miss obvious ones | Ask "which records did you use and why?" — if retrieval skipped something, check the note's `status` (stale/draft is excluded by design) and its privacy switches; then `aios generate` to refresh views |
| Unsure whether the AI can see something private | Ask it "can you see <the note>? why or why not?" — the answer must cite the note's switches; `aios search --domain <work|personal|shared>` applies the same rules deterministically and fails closed without a domain |
| The AI wrote something it shouldn't have | Kill switch off → journal to see what/when → rollback if needed → the incident belongs in the journal; protected-object violations are defects, not judgment calls |
| AI behaving badly right now | **Part 3, step 1. Now.** |

## Part 3 — RECOVERY (no AI, no Python, no Git required)

Printed-page simple. You need: a file manager and any text editor.

### 1. Stop all AI writes (the kill switch)

Open `SYSTEM-MANIFEST.yaml` in any text editor. Find `ai_writes_enabled: true`. Change `true` to `false`. Save. Done — every compliant runtime and script now refuses to write. Your files are untouched and yours.

### 2. Find your bearings

Open `START-HERE.md`. Its authority table says which file governs what. Your knowledge is in the numbered folders — ordinary Markdown you can read, edit, and search (your OS's file search works fine: Spotlight, Windows Search, grep).

### 3. Restore a checkpoint

**The preferred path (zip snapshots)** — run the exact `rollback_command` printed when the snapshot was made. If Python is unavailable, keep the current vault intact, extract the zip into a separate folder, verify that it contains `AIOS-SNAPSHOT.json` and `payload/`, then rename the current vault aside and rename `payload` to the vault's original name. Never extract over the live vault.

**Use the exact `rollback_command` printed by checkpoint.** It contains the full restore identity and the confirmation flag, so you do not need to assemble a technical command yourself. With Git, it verifies the full commit and recorded tree hash, removes files created later, and first archives any uncommitted or untracked bytes it will overwrite or clean. With no Git, it verifies the snapshot archive and every embedded file, builds the restored vault safely beside the live one, then swaps it into place. Same-version restoration must also pass the trusted current validator or the previous live tree is put back. Across an intentional version boundary, exact authenticated identity is the recovery gate: current-validator findings are preserved as advisory evidence because newer rules can reject a valid older release, and code from the restored tree is never executed automatically. A scoped `checkpoint --paths …` prints a scope-bound command: it restores and cleans only the named paths and deliberately leaves unrelated staged, tracked, untracked, and ignored work alone. ⚠️ Do **not** use bare `git checkout <ref> -- .`: it looks like a restore but silently leaves behind files created after the checkpoint.

### 4. Export / move everything

Copy the folder. That is the entire export procedure — to a drive, another machine, anywhere. Nothing external is required to read it.

### 5. Rebuild the machinery later (optional)

When ready: install Python 3.9+ and PyYAML, run `python3 System/Scripts/aios.py validate` (read-only). Re-enable writes when you're satisfied (kill switch back to `true`), then run `generate` to rebuild the indexes. Reconnect a supported runtime by pointing it at the vault; it must begin at the root `AGENTS.md`, then follow the manifest and `reading_order.ai` chain. One exception while writes are off: the exact rollback command printed by checkpoint still works — its `--confirm` is the human authorization the switch exists to protect.

### 6. Delete something permanently

Remove the file(s); if using snapshots/Git and the content must be gone from history too, delete old snapshot zips containing it (Git history rewriting is technical — ask for help or keep the repo private). Personal-data deletion beats archiving when you want it gone.

**Make sure you HAVE a zip** — on a Git-based install, checkpoints are commits, which need tools to restore. Create a human-restorable snapshot anytime with `python3 System/Scripts/aios.py checkpoint --zip -m "safety net"` (or `--zip-only` to snapshot without a git commit) — do it once now, and your implementer should have made one at handoff.

**The recovery promise**: every step above was designed to work when everything else fails. Walk through steps 1–4 once while things are fine (the Portability Test Procedure includes it) so the first time isn't an emergency.
