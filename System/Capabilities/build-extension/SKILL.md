---
id: capability-build-extension
name: build-extension
component_type: capability
status: active
version: 0.2.1
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-build-extension
summary: Grow the system safely — design, scaffold, test, activate new components.
description: "Design, scaffold, test, and activate new system components — capabilities, agents, workflows, templates, schemas. Use when extending the system with a new component or changing an existing component's contract."
consolidates:
- skill-build-extension
reads:
- vault
writes:
- per-procedure
permissions:
- uses-vault-operations-only
dependencies:
- doc-runtime-kernel
- capability-adversary
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
- System/Tests/scripts/test_adversary.py
- System/Tests/scripts/test_commands.py
x_runtime_evaluations:
- System/Tests/fixtures/08-extension-request
- System/Tests/fixtures/28-adversary-seeded-flaw
documentation: self
created: '2026-07-10'
updated: 2026-08-09
---

# Capability — build-extension

1. Clarify the outcome; check what exists (extend > invent).
2. Least powerful type that works: script < template/note-class < workflow < capability < agent. Recommending *no new component* is a common correct answer.
3. One-page design (purpose, reads/writes, permissions, failure, tests) → **human sign-off before anything is created**.
3b. **The adversary gate — High-tier builds only.** Every new component (schema, template, capability, agent, script, workflow) and every structural change is a **High**-tier change, and a High-tier build gets an adversary pass on the design **before anything is created**: follow `System/Capabilities/adversary/SKILL.md`, file the report as working material with the plan, and hand the verdict to the human — *proceed · proceed-with-amendments · redesign*. The verdict advises; the human decides, and may build against a `redesign`. A build that skips the gate records one line in its plan — *"adversary gate skipped — owner OK, \<date\>"* — because a skip is the absence of evidence, never a pass, and a silent skip is how a gate becomes decoration. Low- and Medium-tier changes are **not** gated: a gate that fires on a typo fix is a gate people learn to ignore.
4. `aios scaffold` → implement → write its test → `aios validate`.
5. Activate only with passing tests, **documentation** (a diagram in `System/Documentation/Diagrams/` mapped and described in `coverage.yaml` / `diagram-metadata.yaml`; `aios doc-check` green for the component), + human approval. `aios scaffold --register` hard-blocks an undocumented component (DEC-051) — documentation is a peer of tests. Hard limits: never governance, existing schemas, or any agent contract — those are amendments. No component grants itself permissions.
