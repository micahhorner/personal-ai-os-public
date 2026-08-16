---
id: doc-public-claims-ledger
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture]
canonical_for: public-claims
version: 1.0.0
product: personal-ai-os
status: active
created: 2026-08-13
updated: 2026-08-14
summary: "Marketing claim boundaries for the v1.64.2, with v1.64.1 evidence kept explicitly historical."
---

# Personal AI OS v1.64.2 — claims ledger

Factual authority for product descriptions: the current v1.64.2's canonical product state. Target-bound machine evidence is distributed separately with the GitHub release assets for tag `v1.64.2`. The [`v1.64.1 evidence summary`](../Evidence/v1.64.1.md) and [machine-readable gate](../Evidence/final-gate-v1.64.1.json) remain historical evidence for commit `fc39fc55002a3822a201bda3af0bab63d49a03a2`; they are not v1.64.2 evidence.

## Claims we may make

| Topic | Approved wording | Evidence/scope |
|---|---|---|
| Ownership | “Your knowledge remains ordinary Markdown and YAML files in a folder you control.” | Product storage model; no database or hosted product service required. |
| License | “The Personal AI OS core and the open packs shipped with it are MIT-licensed.” | Root `LICENSE.md` and README. PMM Engine is separate and proprietary. |
| Open format | “The knowledge layer is stored as a conformant OKF v0.2 bundle and can be checked locally.” | `aios okf-check`; say **knowledge layer**, never the whole repository. |
| Runtime design | “The runtime is replaceable by design; the release ships Claude Code and Codex profiles.” | Two shipped profiles. This is not certification of every runtime. |
| Source quality | “Target-bound source-gate evidence is attached to the v1.64.2 GitHub release.” | Do not transcribe a count unless quoting that exact release asset. Historical v1.64.1 counts require an explicit version label. |
| Upgrade estate | “The target-bound upgrade and recovery evidence is attached to the v1.64.2 GitHub release.” | Do not carry v1.64.1 lifecycle totals forward. |
| Transaction safety | “Supported transactional workflows are designed around reviewed inputs, atomic publication, validation and recovery.” | Architecture claim only in the release-attached evidence. |
| Recovery | “The product provides Git and no-Git recovery paths.” | Mechanism claim only until v1.64.2 qualification. Do not imply all ignored local files are restored by Git clean recovery. |
| Components | “The delivered release has 15 active capabilities: 14 core capabilities plus one from the preinstalled open Obsidian Bases pack. The core also has three agents and two workflows.” | `System/Generated/component-index.json`: 20 active delivered components = 14 core capabilities + 3 core agents + 2 core workflows + 1 pack capability. The README/docgen core count remains 14. |
| Commands | “All 36 CLI commands are documented.” | `aios doc-commands`: 36/36. |
| Scale | No performance claim without release-attached evidence. | Historical v1.64.1 benchmarks may be cited only when explicitly labeled historical and not implied to describe v1.64.2. |
| Privacy | “Filtered retrieval enforces note-level privacy and domain rules.” | Broker/retrieval tests. Direct native file access remains compliance-based. |
| Checkpoints | “Risky supported workflows create exact recovery artifacts and refuse unsafe paths.” | Git and ZIP checkpoint/rollback suites. Avoid “everything is always reversible.” |

## Claims requiring exact qualification

- **“Safe”** must name the mechanism: reviewed plan, confirmation, no-follow paths, atomic transaction, validation, or rollback. Never use it as a blanket adjective.
- **“Any AI”** means replaceable architecture, not verified interoperability. Prefer: “a replaceable filesystem-capable runtime; Claude Code and Codex profiles ship today.”
- **“Private”** means local, user-controlled files plus filtered retrieval rules. Direct-file runtimes are not sandboxed and can technically read files their OS account can reach.
- **“Citations”** means the supported retrieval workflow names the records used. It is not a guarantee that every free-form model answer will cite or abstain.
- **“Stays true”** means the system surfaces dependencies, stale records, and review obligations. It does not autonomously make every dependent statement correct.
- **“Open source”** applies to the MIT core and open shipped packs, not PMM Engine or every future vertical.

## Claims prohibited until new evidence exists

- “Certified,” “Claude-certified,” “Codex-certified,” or “externally certified.” Both shipped runtime profiles remain `NOT CERTIFIED` with no complete recorded external battery.
- “Sandboxed,” “the AI cannot read/touch this,” or any graphic suggesting physical confinement in direct-file mode.
- “Works with every AI,” “works everywhere,” or a named runtime beyond the shipped/rehearsed profiles without current evidence.
- “Never hallucinates,” “never forgets,” “always cites,” “automatically keeps everything correct,” or “everything is reversible.”
- Customer outcomes, testimonials, adoption, ROI, or “proven with clients.” No independent beta/human validation has been completed.
- Any v1.64.2 test, upgrade, fault, recovery or benchmark total without support from the target-bound GitHub release evidence.
- The old 1,600-token always-on figure, “four corpora migrated,” 10/10 certification, the legacy single-digit capability count, 42 tests, or any other retired count.

## Historical claims — v1.64.1 only

When the exact version and historical scope are visible, the immutable v1.64.1 evidence supports: 1,156 strict tests; 20 official historical upgrade/recovery source rows; 22 required fault cases; and product-issued recovery in Git and no-Git modes. These figures must never appear as v1.64.2 evidence.

## Business promises, not product facts

Prices, guarantees, response times, support periods, migration acceptance criteria, and backup custody are owner/legal commitments. They may appear only when the current owner-approved commercial policy is cited and must not be presented as release-test evidence.
