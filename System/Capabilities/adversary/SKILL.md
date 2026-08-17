---
id: capability-adversary
name: adversary
component_type: capability
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-adversary
status: active
version: 0.1.1
summary: "Attack a plan before the build spends the money: a hostile read that names the load-bearing assumptions, the unnamed failure modes, the cheaper version, the scope traps, and the plan-killer — every finding citing the line it attacks."
description: "Red-team a plan, spec, or scope before it is built. Use on demand ('red-team this', 'poke holes in this', 'pressure-test this') and as the pre-build gate the component-building procedure owes on High-tier builds. Produces one working-material report in fixed sections with a proceed / proceed-with-amendments / redesign verdict. It advises; the human decides. It tests soundness, never demand."
consolidates: []
reads: [vault]
writes: [per-procedure]
permissions: [uses-vault-operations-only]
dependencies: [doc-runtime-kernel, capability-safe-write]
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
- System/Tests/scripts/test_adversary.py
x_runtime_evaluations:
- System/Tests/fixtures/28-adversary-seeded-flaw
- System/Tests/fixtures/29-adversary-retrodiction
documentation: self
created: 2026-07-26
updated: 2026-08-09
---

# Capability — adversary

A defect found in a plan costs a conversation. The same defect found in a finished
build costs the build. This capability spends the conversation on purpose: a
deliberately hostile pass over a plan, spec, or scope *before* construction starts.

This system's own history proves the value by accident: plans that shipped at a
third of their filed scope once somebody re-read them honestly, rules that were
false the day they were written, expensive work run before a cheap decision that
would have cancelled it. Every one of those was an adversary pass that happened by
luck. This makes it a step.

*(Deliberately unillustrated. The cases are named in the constitution's amendment
log, not here: this file is loaded on every run, and a worked example inside it
would hand the answer to the retrodiction eval that keeps the capability honest.)*

**It is a procedure, not a standing critic.** Nothing here fires on its own: the
capability runs when a human asks, or when the component-building procedure
reaches its pre-build gate. A
critic that comments on everything is a critic nobody reads.

## When it runs

- **On demand** — "red-team this", "pressure-test this", "poke holes in this",
  "what am I missing?", pointed at a plan, spec, scope, or proposal.
- **As the pre-build gate** — step **3b** of the component-building procedure in
  the developer lane, which names this capability and loads it: a **High-tier** build (a
  new schema, template, capability, agent, script, workflow, or a structural
  change — the change-control High tier) gets an adversary report *before* any
  file is created. Not Low- or Medium-tier changes: gating a typo fix is how a
  gate becomes noise.
- **Never automatically on Low/Medium work, and never on the user's own notes.**

## The frame — set it before reading

1. **Read the artifact, not the argument for it.** Attack what the plan *says*,
   not the enthusiasm around it. Where the plan's rationale lives outside the
   document, do not go get it first: if the plan cannot survive being read cold,
   that is a finding.
2. **Attack the work, not the author.** No finding may characterize the person who
   wrote it. "This assumes X" — never "you always assume X."
3. **Say who is holding the knife.** Record in the report whether the pass was run
   by the same session that wrote the plan. A self-review is the weakest form of
   this pass — it cannot see the assumptions it made unconsciously — and the
   report says so in one line rather than pretending otherwise. When a separate
   session or subagent is available, prefer it.
4. **One thing right, minimum.** The report must name at least one thing the plan
   gets right, and mean it. A pass that only objects is exactly as unfalsifiable
   as a pass that only praises; both are theater with different manners.

## Procedure

1. **Locate the artifact and pin its lines.** Read the plan in full. Note the
   lines you will cite (file + line, or the section heading when the source has no
   stable lines). A finding that cannot point at text is an opinion, not a finding.
2. **Steelman first.** State the plan's strongest version in two or three
   sentences — the version its author would recognize. You may not attack a weaker
   one afterwards.
3. **Run the five reads** (the report's five sections, below). Each read is a
   separate pass over the same text; do not merge them, because each one finds a
   different class of defect.
4. **Falsify every finding.** For each finding, write what would show it to be
   *wrong* — the observation, test, or number that would settle it. A finding with
   no falsifier is a generic objection wearing a costume; delete it or make it
   specific.
5. **Rank.** Order findings by what they would cost if true, not by how clever
   they are. Name the plan-killer explicitly, even when the answer is "there
   isn't one" — a plan with no plan-killer is a claim, and stating it makes it
   checkable.
6. **Verdict** (one of exactly three):
   - **proceed** — findings are real but none change what gets built.
   - **proceed-with-amendments** — build it, with these named amendments. Each
     amendment names the finding it closes and is small enough to actually do; a
     proceed-with-amendments verdict that lists no amendments is not this verdict,
     it is `proceed` with hedging.
   - **redesign** — a finding invalidates the approach, not a detail of it.
7. **Close with the limit.** Every report ends with the reality line:
   *"This pass tested the plan's soundness. It did not test demand. Nothing here
   tells you whether anyone wants this — only contact with the world does that."*
   It is mandatory because the failure mode it guards is a pass that makes a bad
   idea *feel* validated.
8. **File it** (see below), then hand it to the human. The verdict advises. The
   human decides, always.

## The report — fixed sections

Fixed because a variable shape is a shape that quietly drops the section that
hurt. Every finding cites the line it attacks and states its falsifier.

```
# Adversary pass — <artifact>
Run by: <session/runtime> · Self-review: yes | no · Date: <YYYY-MM-DD>

## Strongest version
<the steelman, 2-3 sentences>

## 1. Load-bearing assumptions
For each: the assumption · the line it rests on · **how we'd know it's false**.

## 2. Failure modes the plan doesn't name
For each: the mode · the line that should have named it · what it costs.

## 3. The cheaper version
What would a skeptic build instead? State it concretely, state what it loses,
and state the condition under which the cheaper version is simply correct.

## 4. Scope traps and hidden dependencies
What this drags in that the plan doesn't budget for: other components it forces
open, work it implies but doesn't name, decisions it silently pre-commits.

## 5. What this plan cannot survive - the plan-killer
Named, singular, ranked first among the findings. Or: "no plan-killer found",
with the reasoning that makes that checkable.

## What the plan gets right
At least one thing, specifically.

## Verdict
proceed | proceed-with-amendments | redesign
<amendments, each naming the finding it closes>

> This pass tested the plan's soundness. It did not test demand. Nothing here
> tells you whether anyone wants this - only contact with the world does that.
```

## Where the report lives

The report is **working material** (`type: working`, subtype `log` — a record of a
pass that happened, not a plan and not knowledge) filed with the work it attacks:

- A build inside a project → `10 Projects/<Name>/`, beside the plan, per `safe-write`.
- A build with no project folder yet → `00 Inbox/`, named for the artifact; it
  moves when the project does.
- It never lands in `20 Knowledge/`. A critique of one plan is not knowledge; a
  durable lesson learned from it is, and it graduates by the normal route.

**Findings the build rejects get one line saying why**, appended to the report
under the finding — not deleted. Honest disagreement recorded is cheap; a rejected
finding that vanishes is how the same defect returns next quarter.

## Fences

- **It advises, never approves, and never blocks.** No verdict stops a build. The
  human may build against a `redesign` verdict; that override is recorded in one
  line in the build's plan, the same way a skip is.
- **A skipped gate is recorded, never silent.** If a High-tier build proceeds
  without a pass, the build's plan records *"adversary gate skipped — owner OK,
  <date>"*. A skip is the absence of evidence, not a pass, and the record must
  never read like one.
- **It tests soundness, not demand.** Structural, and the reason for the mandatory
  closing line. If this becomes a substitute for talking to one real user, it is
  actively harmful.
- **It does not rewrite the plan.** It produces findings; amending is the author's
  work, so the plan keeps one author.
- **It never runs on a person.** Plans, specs, scopes, proposals — not the user's
  behaviour, their notes, or their decisions about their own life.
- **Cheaper-version discipline applies to this capability too:** the honest
  alternative to it is five questions on a checklist inside the component-building
  procedure.
  What justifies a component instead is the pair of evals that keep it falsifiable
  (fixtures `28-adversary-seeded-flaw` and `29-adversary-retrodiction`). If those
  are ever dropped, the checklist is the correct answer and this capability should
  be retired to one.

## The same engine, pointed elsewhere

This is a hostile read of an artifact against fixed sections. Pointed at a plan it
is a pre-build gate; pointed at an **incoming pack** — third-party content arriving
from outside the trust boundary — the same five reads become a pre-install trust
scan: what does this pack assume about my vault, what does it fail to say, what is
the cheaper thing it should have been, what does it drag in, and what could it do
that cannot be undone. That second framing is deliberately **not** built here. The
design above is shaped so it can be added later as an entry framing rather than as
a second engine.
