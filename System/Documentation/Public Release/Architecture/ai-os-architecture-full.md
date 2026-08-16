---
id: doc-public-architecture-full-companion
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture]
canonical_for: public-full-architecture-companion
version: 1.0.0
status: active
created: 2026-08-14
updated: 2026-08-14
summary: "Accessible plain-language companion to the v1.64.3 full architecture diagram."
---

# How Personal AI OS works — plain-language companion

This is the accessible text version of `ai-os-architecture-full.svg`. It explains Personal AI OS v1.64.3 without requiring technical knowledge. Qualification claims are valid only when they identify the exact released tag and commit.

## 1. Use the AI you prefer

The folder is the lasting part. The AI is replaceable.

Personal AI OS comes ready to connect to Claude Code and Codex. Other AI tools can be added after someone checks that they can follow the system correctly. This does not mean every AI has been tested or certified.

The AI does the thinking. Your folder keeps the memory, rules, methods and proof.

## 2. The AI reads the house rules

Before doing a task, the AI follows one clear starting path to four things:

- rules it must always follow;
- the guide that picks the right instructions for the job;
- settings that say what this AI may do;
- owner controls, including the off switch and files that need special approval.

These are written rules the AI is required to obey. They are not a security wall: an AI that can directly open the folder is technically able to ignore them.

## 3. It works out what kind of help you need

The system decides whether you are asking it to find something, write something, bring material in, tidy up, recover, set up the system or improve the system itself.

It opens only the instructions for that job instead of loading a giant manual every time.

## 4. It follows a step-by-step method

The delivered product contains 15 ready-made methods. The most recognizable jobs are:

- find an answer and tell you which notes it used;
- write or update something carefully;
- bring in new material without treating it as trusted fact;
- show what is stale, broken or due for attention;
- bring old notes into the system through a reviewed plan;
- learn your preferences and privacy choices during setup;
- add or remove an optional extra;
- teach the system a new job through design, challenge, testing and approval;
- recover from a problem or update to a newer release.

Behind those jobs are 14 core methods plus one supplied by the included open add-on, three specialist AI roles, two recurring workflows and 36 documented commands for repeatable mechanical work.

## 5. Reading and writing take different paths

### When you ask a question

The system:

1. starts with short summaries rather than loading every full note into the answer context;
2. leaves out notes that are private for this AI, in the wrong area, unfinished or no longer current;
3. opens only the few notes likely to answer the question;
4. treats instructions found inside notes as content, never as commands;
5. tells you which notes it used, or says that none fit.

The built-in search and read tools enforce these rules. An AI with direct folder access must still choose to use those tools and obey the rules; the product does not place it inside a security sandbox.

### When something needs to change

The system first checks whether writing is turned off, what rules apply and whether the thing already exists.

- **Small change:** use the right form, save it and check the result.
- **Change that affects other things:** find what depends on it, deal with each effect and record what changed.
- **Change to the rules or system:** save a restore point, explain the impact and wait for the owner's approval.

The built-in writing tools recheck their inputs and either complete a whole supported change or leave the prior state recoverable. This protection applies to those tools; it cannot physically control every edit another program or person might make directly.

## 6. You own the folder

The folder contains:

- an Inbox where new material waits to be checked;
- projects, knowledge, decisions and a to-do list;
- original sources that stay unchanged;
- things you made and older material you want to keep;
- your preferences, voice, privacy choices and working style;
- optional extras that add new jobs;
- the rulebook, step-by-step methods and automatic checks;
- rebuildable views plus activity and recovery records.

The knowledge is ordinary Markdown and YAML. You can read it without an AI. Obsidian and Git are optional.

Do not store passwords, secret keys or recovery codes in the folder.

## What release evidence can—and cannot—prove

Target-bound machine evidence is distributed with the GitHub release assets for tag `v1.64.3`. Accept a qualification claim only when that evidence identifies the exact tag and commit.

Release evidence proves only the tested product mechanics. It does not prove perfect AI judgment, compatibility with every AI tool, a physical security sandbox, independent human usability or outside live-model certification.
