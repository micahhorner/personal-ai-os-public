---
id: doc-extension-guide
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [capability-build-extension, schema-component]
created: 2026-07-10
updated: '2026-08-09'
summary: How the system grows — for humans who want new capabilities without becoming engineers.
---

# Extension Guide

Tell the AI what you're trying to accomplish; the Extension Builder does the rest through a controlled lifecycle. What you should know:

**The component ladder** (least powerful that works, always — same order as `build-extension`): a **script** for anything mechanical · a **template/note class** for a genuinely new kind of record · a **workflow** for routines over existing pieces · a **capability** for repeatable judgment · an **agent** only for a standing role with its own permissions (rare — the system shipped with three and may never need a fourth). A workflow that declares `cadence_days` in its frontmatter also opts into freshness tracking — `aios health` reports it when it goes overdue, which is the one and only way a domain registers its own recurring check. Only capabilities and workflows use the `aios scaffold` lifecycle; everything else is a system change through the developer lane.

**Distributing an extension as an add-on.** Package related components as an **add-on pack** — a self-contained `Packs/<id>/` folder with a `pack.yaml` manifest — that anyone installs by dropping the ZIP in their OS root. `manage-packs` binds the exact archive review, validates before activation, and receipts the installed tree; removal preserves declared user workspace transactionally. Components are discovered *in place* under `Packs/`, never copied into `System/`. See `Add-Ons and Packs.md`.

**The lifecycle**: clarify → check what exists (extending beats inventing) → one-page design **you approve** → an **adversary pass on that design** (any new component is a High-tier build, so the plan gets attacked before it gets built — see the `adversary` capability; the verdict advises, you decide, and skipping it is written down rather than assumed) → scaffold (`aios scaffold`) → implement → test → **you approve activation**. Components without tests **or a documented diagram** cannot activate — the tooling enforces both (`aios doc-check`: every component must map to a described diagram in the atlas, DEC-051).

**The hard lines**: extensions never touch governance, existing schemas, or agent contracts — those are amendments (Decision Register + human approval + version bump). No component may grant itself permissions.

**Removing**: components retire by flipping `status` in their own file (`deprecated` → `retired`; the generated index follows), never silent deletion; anything that depended on them gets the four-outcome treatment.
