---
id: doc-diagrams-pipeline
type: system-doc
file_class: canonical
authority: canonical
canonical_for: diagram-coverage-pipeline
version: 1.1.0
created: 2026-07-13
updated: 2026-07-27
summary: "The repeatable process that keeps every AI OS component diagrammed and documented: diagrams authored by hand, coverage enforced by machine."
---

# Documentation Coverage Pipeline

**How we guarantee every AI OS component stays diagrammed and documented. Diagrams are authored by hand; coverage is enforced by machine. This file is the repeatable process — it applies to any product atlas (AI OS today, PMM Engine next).**

---

## The principle

Two halves, and only one can be automated:

- **Authoring** a diagram is a design judgment — no tool can auto-generate a good SVG from a new component. This stays human.
- **Coverage** is a checkable fact — the moment a component exists without a diagram + catalog entry, `check_coverage.py` fails and names it. This is automated.

So the guarantee is not "diagrams appear automatically." It is **"you cannot ship an undiagrammed component without the gate turning red."** The red gate is what triggers the authoring.

## The three artifacts

| File | Role |
|---|---|
| `coverage.yaml` | **Source of truth.** Maps every component → diagram(s), lists all diagrams, records deliberate prose-only exclusions. |
| `aios doc-check` | **The gate.** Enumerates components from the product filesystem, fails on any that aren't mapped or whose SVG is missing, and fails on a diagram with no description or a `CATALOG.md` that does not list it. Composed into `aios health` and into `aios certify`'s doc-truth dimension, so it runs whether or not anyone remembers to. |
| `CATALOG.md` | **Human-readable index.** Prose descriptions (hand-written) + the coverage/status tables (generated from `coverage.yaml`). |

## What the gate enforces

`python3 System/Scripts/aios.py doc-check` (exit 0 = clean, 1 = gaps):

1. Every component on disk (`System/Capabilities/*/SKILL.md`, `System/Agents/*/AGENT.md`, `System/Workflows/*.md`, matched by its frontmatter `id:`) has an entry in `coverage.yaml → components`. **Undiagrammed component → FAIL.**
2. Every diagram referenced by a component or area exists in `coverage.yaml → diagrams` and its SVG file is present on disk. **Missing SVG → FAIL.**
3. No stale coverage rows (mapped component no longer exists) — **warning.**
4. No orphan SVGs (file on disk not registered) — **warning.**

It enumerates from the **filesystem**, not the generated `component-index.json`, so it catches a new component even if the index hasn't been rebuilt.

## The standard workflow — adding or changing a component

When you add or materially change an AI OS capability, agent, or workflow:

1. **Build the component** through the normal AI OS extension lifecycle (design → scaffold → test → register).
2. **Run the gate:** `python3 System/Scripts/aios.py doc-check`. A new component turns it red.
3. **Author the diagram** SVG in `svg/` (follow the design conventions in `CATALOG.md → Regeneration & maintenance`).
4. **Register it:** add the diagram to `coverage.yaml → diagrams` and map the component under `components`.
5. **Add the prose entry** to `CATALOG.md`. There is no `--emit-md`: the catalog's tables are hand-maintained, and `doc-check` verifies only that every registered diagram is *listed* somewhere in the file — so a status row can go stale without the gate noticing. Check the row you are adding against `coverage.yaml` yourself.
6. **Re-run the gate** — it must be green before the change is considered done.
7. If a component genuinely does not warrant its own diagram, record why under `prose_only` — an explicit, reviewed exclusion, never a silent one.

## Where the gate runs (the trigger)

The gate is only a guarantee if something runs it. Options, in increasing robustness:

- **Manual** — run `aios doc-check` when you touch components. (Zero setup; relies on discipline.)
- **Git hook / CI** — a pre-push hook or GitHub Action on the product repo fails the push/PR when coverage is red. (Catches it at commit time.)
- **Weekly maintenance step** — add the gate to the steward's `weekly-maintenance` drift checks, alongside the existing "component-index-vs-reality" check. (Periodic safety net, fits the AI OS model.)
- **Extension-lifecycle gate** — make a green coverage check part of component *activation*, so a component cannot reach `active` status undiagrammed. (Strongest — closes the gap at the moment it is born.)

**Recommended:** the extension-lifecycle gate (closes the gap at creation) + the weekly-maintenance step (catches anything that slips). Both live inside the product and ship to every instance, so the guarantee travels with the system rather than living only in this folder.

## Reusing this for other products

`coverage.yaml` declares `product_path` and the component globs are standard AI OS layout, so
`aios doc-check` works unchanged for any product built on this core: point `product_path` at the
other tree and populate `coverage.yaml`. Nothing in the gate is specific to this product's
component list.

*(This section used to name a specific commercial product and quote its component counts. Those
were another product's internals shipped inside the generic master — the audit DEC-057 asked for.
The reusable part is the mechanism, which is what is left.)*
