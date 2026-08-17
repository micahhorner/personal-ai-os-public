---
id: doc-method-kit-core
type: system-doc
file_class: canonical
authority: canonical
canonical_for: method-kit-universal-core
version: 0.1.0
status: active
created: 2026-07-11
updated: 2026-07-11
summary: "The universal skeleton every generated doctrine pack shares: lifecycle, gates, risk tiers, records, backups, portability. Everything personal is a dial (see DIALS.md); everything here is physics."
---

# The Core — what every operator gets

This file is the non-negotiable skeleton of a generated doctrine pack. It contains only rules that hold for anyone doing consequential work with AI. Anywhere a rule could legitimately vary by person, it doesn't live here — it lives in [DIALS.md](DIALS.md) and gets set by the interview. Markers like `⟨D3⟩` mean "this dial's setting slots in here."

## 1. The spine (every piece of work follows it)

```
Understand → Plan → Owner gate → Build in checked steps → Verify → Record → Close
```

Small work compresses the spine into minutes (see §4); big work gives each phase its own artifact. What never gets skipped, at any size: **understanding before acting, a check after every change, and a record of what happened.**

## 2. Plans and decisions

- Work beyond task size starts with a **written plan** that survives the conversation that produced it: what this is, what exists now, what will change, in what order, with what checks.
- Every question only the owner can answer is surfaced **explicitly, with the AI's recommendation attached** — never buried, never assumed.
- A decision, once made, is **written down where future sessions will find it**. A skipped check is itself a decision and gets recorded with its reason.
- Approval is explicit words from the owner. Scope of an approval: ⟨D4⟩.

## 3. Risk tiers (proportionality)

Every change lands in a tier, and ceremony scales with the tier — meticulous is not the same as maximal:

| Tier | Nature | Minimum treatment |
|---|---|---|
| **Low** | trivially reversible, nothing depends on it | do it; no record needed |
| **Medium** | edits things others/other-things depend on | check impact, do it, one journal line |
| **High** | structure, automation, merges, anything hard to undo | checkpoint first, owner approval ⟨D2⟩, verify after, record |
| **Critical** | deletion, bulk operations, anything public/outward | all of the above + rollback plan stated **before** acting + owner approval per instance |

Where the tier boundaries sit for this person: ⟨D2⟩. When in doubt, escalate one tier. **Publishing, sending, spending, and deleting are never below High.**

## 4. The task lane

Task-sized work (short, low/medium tier, no structure touched) runs three steps: **orient** (what am I standing in? does this already exist?) → **do** the smallest valid change and check it → **record** per tier. The moment a "task" wants to touch High/Critical territory, it is a project in disguise: stop and give it a plan. The task/project threshold for this person: ⟨D1⟩.

## 5. Records (three layers, never conflated)

1. **Version control** — git where possible, dated snapshots otherwise. Work not committed is work that doesn't exist yet.
2. **Changelog** — one entry per release of a versioned thing, honest history: withdrawn or failed releases stay in the file, labeled. History is never rewritten to look better.
3. **Journal** — append-only, one line per medium+ change, written *when the change is made*, not reconstructed later: date · actor · what · outcome · rollback point. Journaling depth for this person: ⟨D5⟩.

Every substantive artifact carries minimal metadata: a stable ID, dates (absolute, never "yesterday"), and a one-line summary a human can skim and an AI can index. Metadata richness: ⟨D6⟩.

## 6. Safety rails

- **Checkpoint before risk**: a commit or snapshot immediately before anything High/Critical, so there is always a way back.
- **Sandbox first**: consequential changes happen on a copy before they happen on the real thing. Anything irreversible gets **rehearsed** before it gets performed.
- **Originals stay untouched** until the replacement is proven in real use; deletion of anything canonical is never automatic — archive or supersede instead. Deletion authority: ⟨D3⟩.
- **Backups are layered**: local history + off-machine copy at minimum. Depth of the stack: ⟨D7⟩.

## 7. Honesty rules (for the AI and the human)

- Claims of success carry **evidence** — counts, test output, before/after proof. "Done" without evidence is not done.
- Failures are the headline of a report, never buried under successes.
- What the person *does* outweighs what they *say about themselves* when the two conflict — and the conflict gets noted, not smoothed over.
- **Escalating to the owner is a correct outcome**, not a failure — mandatory when confidence is low, sources conflict, or the action would publish, send, spend, or destroy.

## 8. Portability (no lock-in)

- Plain, exportable formats by default; anything proprietary requires a deliberate decision and a named exit path. Strictness: ⟨D8⟩.
- Tool-specific files **point** at canonical rules rather than copying them, so no tool accumulates its own divergent rulebook.
- A project folder must make sense moved to another machine with zero verbal context: entry point, plan, journal, handoff all present. Handoff depth: ⟨D9⟩.

## 9. Working with AI

- The AI reports before it repairs anything consequential: findings + recommendation, owner decides. Autonomy level: ⟨D10⟩.
- Reports answer, in order: what changed, what was checked (numbers), what was flagged, the rollback point, what needs the owner. Style and length: ⟨D11⟩.
- Sessions end so the next session — any model, cold — can resume from the written record alone.
