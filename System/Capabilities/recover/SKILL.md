---
id: capability-recover
name: recover
component_type: capability
status: active
version: 0.1.1
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-recover
summary: Stabilize, diagnose, restore — the AI side of recovery.
description: "Stabilize, diagnose, and restore the vault after damage or suspected corruption. Use when validation fails unexpectedly, content is missing, or a checkpoint must be rolled back."
consolidates:
- skill-recover
reads:
- vault
writes:
- per-procedure
permissions:
- uses-vault-operations-only
dependencies:
- doc-runtime-kernel
tests:
- System/Tests/scripts/test_core_procedure_contracts.py
- System/Tests/scripts/test_recovery_git.py
- System/Tests/scripts/test_recovery_snapshot.py
x_runtime_evaluations:
- System/Tests/fixtures/09-readonly-write-refused
- System/Tests/fixtures/10-generated-rebuild
documentation: self
created: '2026-07-10'
updated: 2026-08-09
---

# Capability — recover

1. **Stabilize**: ongoing misbehavior → point the human at the kill switch (or set it if asked). Stop your own writes immediately.
2. **Diagnose**: `aios health`; journal tail; last good checkpoint (`git log` / snapshot zips).
3. Generated-state weirdness → `aios generate` is the whole fix (requires writes on — regenerate after re-enabling, it can wait). Wrong output after regen = the defect is in canonical files.
4. Content damage → propose the rollback target + what's lost/kept; **human approves**; `aios rollback <ref> --confirm [--clean]` (works even while the kill switch is off — the human's --confirm is the authorization) or hand-restore per the Recovery Guide.
5. Verify (`validate`+`links`+`health` green); journal the incident + what would prevent recurrence (propose, don't silently add).
