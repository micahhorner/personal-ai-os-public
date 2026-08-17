---
id: adapter-obsidian-guide
type: adapter
file_class: runtime-specific
authority: derived
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
derived_from: [doc-canonical-architecture]
created: 2026-07-10
updated: '2026-08-09'
summary: How Obsidian is configured as the human interface, and what it must never be responsible for.
---

# Obsidian Adapter Guide

Obsidian is the recommended human interface: editing, wikilink autocomplete, backlinks, search, properties. The shipped `.obsidian/` contains minimal settings: links auto-update on rename, new files land in `00 Inbox`, attachments in `30 Sources/Attachments`, and a conservative core-plugin set. **Three community plugins do ship pre-installed** (`.obsidian/community-plugins.json` + their code under `.obsidian/plugins/`) — Notebook Navigator, obsidian-git and Dataview; each is recorded with its purpose and its loss-if-removed in `plugin-policy.md`, and none of them holds canonical meaning.

**The invariant: deleting `.obsidian/` loses zero meaning.** Everything Obsidian shows comes from the files themselves. Templates work with Obsidian's core Templates plugin ({{title}}/{{date}}), and identically as copy-and-fill for any other editor.
