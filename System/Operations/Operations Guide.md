---
id: doc-operations-guide
x_reviewed_against: ["op-registry:1.2.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [op-registry]
created: 2026-07-10
version: 1.1.0
updated: 2026-08-09
summary: Human explanation of the Stable Vault Operations contract, including the three publication domains and mixed Logs boundary.
---

# Operations Guide

The vault exposes fifteen named operations (`System/Operations/operations.yaml` is the contract; this guide explains it). The point: **any AI runtime — Claude today, a local model later — operates the vault through the same fifteen verbs.** What changes between runtimes is only the adapter that maps each verb onto that runtime's abilities.

**Read operations** (`search`, `read`, `inspect`, `find_canonical`, `preflight`) are always available to any certified runtime — they change nothing.

**Write operations** (`propose_change`, `apply_change`, `scaffold_component`, `register_component`, `migrate`) are gated three ways: the kill switch in the manifest, the runtime's certified autonomy level, and change control's risk tiers. A runtime that can't write safely (autonomy L0/L1) still contributes via `propose_change` — drafts land in staging for human review.

**System operations** (`checkpoint`, `rollback`, `validate`, `health_check`, `rebuild_generated`) are deterministic scripts: `python3 System/Scripts/aios.py <subcommand>`. They behave identically no matter which runtime — or human — invokes them.

`rebuild_generated` publishes three bounded domains in order: a complete staged `System/Generated/` tree, the tool-owned `aios-*` projections while preserving foreign `.claude/skills/` entries, then one compare-and-swap of the freshness registry and ledger after re-proving inputs. These are separately atomic publications, not one cross-filesystem swap. Deleting `System/Generated/` is safe; deleting all of `System/Logs/` is not. That directory mixes disposable reports with the durable freshness event log and a ledger carrying live obligations (DEC-121).
