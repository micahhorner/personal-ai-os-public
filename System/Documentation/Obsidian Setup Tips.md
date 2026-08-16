---
id: doc-obsidian-setup-tips
type: system-doc
file_class: canonical
authority: canonical
canonical_for: obsidian-setup-tips
version: 1.0.0
created: 2026-07-10
updated: 2026-07-10
summary: "Practical Obsidian setup for first-time users: the dozen settings, three plugins, and hotkeys that matter — then stop configuring. Obsidian is the optional viewer; none of this affects the vault's meaning."
---

# Obsidian Setup Tips (for first-time users)

Obsidian is this vault's optional, pleasant viewer — never a requirement (the vault is plain files; see the plugin policy in `System/Adapters/Obsidian/`).

**Good news: this vault arrives pre-configured.** Everything below is already set — dark mode, the settings, the hotkeys, and the three plugins (their code ships inside the vault's `.obsidian/` folder). On first open, Obsidian asks one question — *"this vault contains community plugins — trust and enable?"* — click yes, and you're done. The sections below document what was chosen and why, so you can adjust anything to taste.

## Core settings (Settings app)

- **Dark mode** — Appearance → Base color scheme → **Dark** (or "Adapt to system" if you switch by time of day). Easier on the eyes for long sessions; set it first and forget it.
- **Auto-update internal links** — Files & Links → "Automatically update internal links" → **ON**. Renaming or moving notes silently fixes every link pointing to them. Turn this on before you create your tenth note.
- **Show all file types** — Files & Links → "Detect all file extensions" → **ON**. PDFs, images, and other attachments become visible in the navigator instead of invisible.
- **Give attachments their own folder** — Files & Links → "Default location for new attachments" → a dedicated folder (this vault already uses `30 Sources/Attachments`). Otherwise pasted images land beside your notes and clutter every folder.
- **Route new notes to an Inbox** — Files & Links → "Default location for new notes" → your capture folder (`00 Inbox`). Capture first, file later — new notes never scatter across the vault.
- **Keep wikilinks** (the default) — `[[wikilinks]]` are shorter to type and easier to read than markdown links; leave this alone.
- **Keep "Confirm file deletion" ON** (the default). One accidental keystroke shouldn't silently destroy a note.
- **Set a Templates folder** — point Settings → Templates → Template folder at `System/Templates`.
- **Machinery is down-ranked in search** — Files & Links → "Excluded files" ships with
  `System/`, `.obsidian/`, and `.trash/` pre-filled. Obsidian *down-ranks* (not hides) matches
  from these paths in search, quick switcher, and link suggestions, so your own notes surface
  first and the OS's internals stay out of the way. Everything is still there — expand the
  collapsed "excluded" group in any search to see it. Remove the filters if you prefer raw
  results.

## Hotkeys

- **Cmd/Ctrl+T → Insert template** (unbind *New tab* from it first). You insert templates far more often than you open tabs.
- **Cmd/Ctrl+N → your navigator's "New note"** (if using Notebook Navigator, unbind the stock *Create new file* and bind NN's *New note* instead), so new notes respect your folder context and Inbox routing.

## Plugins (included, pre-installed)

- **Notebook Navigator** — replaces the stock file explorer with a two-pane navigator: folder tree plus the selected folder's notes with previews.
- **Git (obsidian-git)** — ships installed. Default settings are fine; connect a private remote (your implementer usually does this at handoff) and you get full version history plus off-machine backup for free. Until a remote exists it sits politely idle.
- **Dataview** — live queries/tables over your notes (task rollups, indexes). Included because imported corpora often rely on it; defaults are fine.

## Notebook Navigator configuration

- **The left sidebar arrives pre-widened for both panes** (folder tree + note list side by side). If you ever narrow it and it collapses to a single pane, just drag it wider again — width is the whole trick.
- **Give top-level folders emoji icons** (📥 Inbox, 🏗️ Projects, 🏛️ Archive, 👤 Me…). Thirty seconds of work, permanent scannability.
- **Set per-folder sort orders** to match each folder's job: Inbox → created, newest first (fresh captures on top); concept/reference/glossary folders → alphabetical; leave everything else on the modified-date default.
- **Pin shortcuts to your daily entry points** — a home/master-map note, your to-do list, `START-HERE.md`. They sit at the top of the sidebar, one click from anywhere.
- **Hide the attachments folder** in the navigator (NN's hidden-folders setting) — you never browse it directly, so remove it from view.

## Core plugins — trim what you won't use

Optionally disable core plugins you don't use (Canvas, Daily Notes, Sync, Note Composer, Slides, Audio Recorder…). Less UI, fewer commands in the palette, nothing lost — you can re-enable any of them in seconds.

## Philosophy

Stop configuring after the above. Theme, appearance, graph view, and editor defaults are all good out of the box. A heavily-used real-world vault runs on exactly two plugins and roughly a dozen deliberate changes — everything else at factory settings. Set up these basics, go write notes, and only tweak again when a real friction appears.
