---
id: doc-method-kit-generator
type: system-doc
file_class: canonical
authority: canonical
canonical_for: method-kit-generator
version: 0.3.0
status: active
created: 2026-07-11
updated: 2026-07-25
summary: "How an AI turns a completed interview answer record into a person's doctrine pack: dial resolution, pack assembly, honest-position note, ratification gate, and skill hookup."
---

# The Generator

Input: a completed answer record in the [ANSWER-RECORD.md](ANSWER-RECORD.md) format, produced by [INTERVIEW.md](INTERVIEW.md). Output: the person's **doctrine pack** — their own folder of plain-text operating rules, ratified by them, plus working skills pointed at it. Follow this exactly; the pack's credibility is the product.

## Step 1 — Resolve the dials

For each of the 11 dials in [DIALS.md](DIALS.md): take the readback-confirmed setting; if signal was missing or contradictory, take the **bold default** and add the dial to the "revisit after two weeks" list — then lean it by the record's **stakes note**: HIGH stakes → the more conservative neighboring setting; LOW → the lighter one. Apply the registry's four rules — especially rule 3: **no setting may weaken the Core** (spine, evidence rule, checkpoint-before-risk, off-machine-backup floor).

## Step 2 — Assemble the pack

Create `<Name>-Method/` containing:

| File | Built from |
|---|---|
| `README.md` | Entry point: what this pack is, its status (`draft — awaiting your ratification`), how any AI should use it ("read AI-PROTOCOL first"), and the ownership promise: plain files, portable, editable, theirs |
| `PRINCIPLES.md` | CORE §7–§8 honesty/portability rules + the person's own values, each **cited to their interview stories** ("from your lost-thesis story: …") — evidence-cited exactly like a serious doctrine, because the citations are why they'll believe it |
| `METHOD.md` | CORE §1–§6 with every `⟨Dn⟩` marker replaced by their resolved setting, written as *their* rule in plain prose — no marker syntax survives into a pack |
| `AI-PROTOCOL.md` | The session contract for any AI working for them: their approval boundaries (D2–D4), autonomy posture (D10), report style (D11), session start/end rituals scaled to their handoff depth (D9) |
| `TEMPLATES.md` | Plan / decision / journal-line / handoff skeletons, pre-sized to their ceremony budget (D1, D5, D6). Where the pack lives inside an AI OS vault, project-layer skeletons (plan, journal, handoff) declare `type: working` with the apt subtype (`working.yaml`, DEC-096) — schema-legal from birth, first-class to `validate`, never mistaken for knowledge |
| `HONEST-POSITION.md` | The E4-vs-stated gaps from the interview, framed as a starting to-do, not a judgment ("no off-machine backup existed on interview day — first action item"), plus the revisit-list of defaulted dials |
| `CHANGELOG.md` | One entry: v0.1.0, interview date, "draft awaiting ratification" |

Formatting rules: every file gets minimal frontmatter (id, dates, one-line summary) regardless of their D6 setting — *the pack itself* is infrastructure; D6 governs what the pack asks of *their* artifacts. All dates absolute. Second person throughout ("you approve deletions per instance"), never third.

## Step 3 — The ratification gate (never skip)

The pack is **their** law, so they ratify it exactly as a serious owner would:

1. Walk them through the judgment calls — one plain-language claim per dial plus each honest-position item — and let them approve or edit each.
2. Fold in corrections. Flip every file's status to `active — ratified <date>`, changelog entry, version 1.0.0.
3. If they have git: init, commit, and offer a **private** remote push. If not: create a dated zip and tell them where it lives. Either way the off-machine-backup floor gets satisfied *now* — the pack's first proof that the rules are real.

## Step 4 — Hook up the machinery

Where the person runs a compatible AI runtime, install the pack skills from `Adapters/pack-skills/` (pk-new-project, pk-plan, pk-handoff), replacing every `<PACK_PATH>` placeholder with the absolute path of **their** pack. The adapter pattern holds: skills contain pointers, never rules — each reads the person's own METHOD/TEMPLATES, not the kit's and not anyone else's.

When the pack lives inside an AI OS vault, also write `80 User/handoff.md` — a one-line pointer to the pack's handoff doctrine (its METHOD re-entry ritual and TEMPLATES skeleton), same pattern as `voice.md`/`authoring.md` (DEC-036). The Task Router consults it on `close-session`/`resume-session`, so the person's routed session closes follow *their* ritual, not the generic floor (DEC-085). If the file already exists, leave it — it is user-owned.

## Step 5 — Close the loop

Tell them the truth about what they have: a v1.0 extracted from 45 minutes, not from lived evidence — so the pack improves by use. Schedule the two-week revisit (defaulted dials + honest-position items). Their edits go in *their* files with a changelog line; the kit never phones home and never overwrites a personal pack.

## Failure modes to refuse

- **No ratification, no pack.** An unread rulebook is worse than none; if they won't do the readback, deliver only the honest-position note.
- **Never generate from self-description alone.** If every E4 probe was declined, say plainly the pack is aspiration-graded and mark it so.
- **Never copy another person's pack** (including the kit author's) as a shortcut — the interview *is* the product.
