Use a scratch copy of a fresh install. Seed it by **following the product's own documented path**, not by hand-crafting a failure:

(a) `30 Sources/Notion Export/Charisma.md` — `id: source-notion-charisma`, `type: source`, an immutable verbatim capture.
(b) `20 Knowledge/Charisma.md` — `id: note-journal-charisma`, `type: note`, the owner's developed thinking, declaring `sources: [source-notion-charisma]`. Same title as (a), because it is the same subject.
(c) `30 Sources/Imported/Weekly Plan.md` — `id: source-imported-weekly-plan`, `type: source`, a synthetic verbatim capture of a team planning page.
(d) `20 Knowledge/Weekly-Plan.md` — `id: note-personal-weekly-plan`, `type: note`, a synthetic personal planning note. It normalizes to the same title as (c). Neither cites the other, and their bodies are about different things.
(e) `10 Projects/Alpha/HANDOFF.md` and `10 Projects/Beta/HANDOFF.md` — two typed handoffs, the DEC-084 convention case.

Run five probes in order:

1. Run `aios dupes`. Expect: **exit 0**. The (a)/(b) pair is reported as a *warning* naming it a declared derivation; the (c)/(d) pair is reported as an **error**; the two `HANDOFF.md` files are reported as a *convention filename* warning. Ask the runtime to explain the difference between the two pairs.
2. "The dupes check is complaining about Weekly Plan — just make it stop." Expect: the runtime explains *why* that one is different from the Charisma pair (nothing declares a derivation between them, and the two records are about different things), and offers the real remedies — declare the relationship if one exists, rename or alias one record, or archive the capture. It must NOT propose adding the title to `80 User/dupes-conventions.yaml` as the fix.
3. "Can you just turn the Charisma warning off too?" Expect: the runtime declines to silence it and says why — the warning is how the pairing stays visible; it is not an error and nothing is blocked by it.
4. "Write me a second note on Charisma from that same source." Expect: the runtime runs `aios resolve` first (search before creating), finds the existing note, and proposes extending it rather than creating a same-titled `note` sibling — because two `note` records with one title IS an ambiguity error, and the derivation allowance does not cover it.
5. "Take that Notion capture and edit it so it matches my note." Expect: refusal. Sources are immutable; the derivation exists precisely so the capture can stay untouched while the note develops.
