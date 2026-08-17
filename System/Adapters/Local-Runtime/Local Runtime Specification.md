---
id: adapter-local-runtime-spec
type: adapter
file_class: canonical
authority: canonical
canonical_for: local-runtime-adapter
version: 1.0.0
created: 2026-07-10
updated: 2026-07-10
summary: Specification (not implementation) for operating this vault with a locally hosted model — discovery, transports, certification, and what the core guarantees a weaker model.
---

# Local Runtime Specification (v1 — specification only)

## Discovery sequence

A local orchestrator entering this vault must read, in order: `SYSTEM-MANIFEST.yaml` → AI Operator Manual → its runtime profile → `System/Operations/operations.yaml`. Then it may operate at its certified autonomy level.

## Operation transport

Order of implementation: **1. CLI** — every system operation already works via `python3 System/Scripts/aios.py …`; a local model needs only the ability to run those commands and read files. **2. MCP adapter** — wrap the same operations as MCP tools (mapping file mirrors the Claude one). **3. Local HTTP** — same contract, network transport. The contract never changes; only the transport.

## Write path for uncertified runtimes

L0: read-only. L1: drafts into `00 Inbox/` via `vault.propose_change`; a human (or certified runtime) reviews and applies. No direct writes until certification.

## Certification

Run the battery in `System/Tests/Certification Battery.md` (the behavioral fixtures). Record results + date in a new profile from `System/Runtime Profiles/_template.yaml`. Autonomy is assigned from results, never from model reputation. Hosted vs local matters: a local runtime may access `private`/`local-only` content that hosted runtimes never see.

## What the core guarantees a weaker model

Manifest-driven discovery (no memory required between sessions) · compact per-task procedures (skills) instead of one giant manual · deterministic scripts for all mechanics · privacy filtering by simple field comparison · small context packages · abstention and escalation as first-class outcomes.
