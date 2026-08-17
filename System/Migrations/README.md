---
id: doc-migrations-readme
x_reviewed_against: ["doc-versioning-and-migration:1.4.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-versioning-and-migration]
created: 2026-07-10
updated: 2026-08-09
summary: Strict manifest, ordering, ledger, checkpoint, validation, and rollback contract for migrations.
---

# Migrations

A migration transforms versioned instance state. Its explicit `version_target`
selects either `system.system_version` or `system.vault_profile_version`;
unknown targets fail closed. Every manifest also binds the exact
`system.distribution_id` as `source_distribution`; absent, unknown, or
different values fail before transform. Upgrade may run one exact historical
`system_version` edge inside its isolated candidate; portable schema/content
migrations target `vault_profile_version`. The public migration command remains
preview-only and never applies directly to the live tree.

## Directory and manifest

Real migrations use unique numbered directories (`001-name/`, `002-name/`, …).
Each contains a strict `migration.yaml`, a human `README.md`, and optionally
hash-bound payload files. Executable migration scripts are prohibited.
`000-example/` is a validated template and can never run.

The manifest requires exactly these fields:

- `schema_version`
- `id`, exactly `migration-<directory-name>`
- `version_target` (`system_version` or `vault_profile_version`)
- `source_distribution`, exactly matching `system.distribution_id`
- `source_identity`, the exact canonical release-baseline SHA-256
- exact stable `from_version` and `to_version` SemVer values
- `prerequisites`
- `content_selector`
- one hash-bound `replace_exact_files` transform; an entry may enumerate exact
  known old/postcondition hashes, every unlisted hash refuses, and an accepted
  destination already equal to its payload is verified without a physical rewrite
- non-empty `validation`
- exact-checkpoint `rollback` with automatic restoration on validation failure
- unique `idempotency_key`
- `manifest_hash`

The hash is SHA-256 over canonical JSON (sorted keys, compact separators, UTF-8)
with `manifest_hash` omitted. Unknown fields, YAML-specific values, unsafe
paths, symlinks, ambiguous transforms, and hash mismatches fail closed.

`source_identity` is independently derived from the canonical
`System/.baseline-manifest.json`: SHA-256 over canonical JSON containing its
`system_version` and `files` map (not its timestamp or derived outputs). The
baseline version must also equal the live manifest's `system_version`. This
detects accidental mismatch and distinguishes known baselines that reuse a
version string; it is not provenance authentication because baseline metadata
can be copied. Signed/external provenance is outside this local boundary.

Preview runs derive this identity from the inspected root. Bare upgrade is also
read-only: it captures the pre-overlay identity, resolves one edge by exact
version/identity/file preconditions, and includes the migration source and plan
hashes in its semantic review. Apply requires the fresh review hash, then passes
the edge through the owned candidate API with a materially verified outer
checkpoint. Final candidate bytes do not exist at review time; the upgrade
journal pins the materialized tree identities used for recovery. The public
migration surface remains preview-only.

## Ordered execution

Run `aios migrate --migration NNN-name` for a read-only preview. Direct
`--apply` is refused. Candidate application is invoked only by the upgrade
transaction after its exact edge resolver and checkpoint gates pass.

Before any mutation, the runner verifies:

1. the current value at `version_target` exactly equals `from_version`;
2. `system.distribution_id` exactly equals `source_distribution`;
3. the current canonical source identity exactly equals `source_identity`;
4. migration ids, numbers, and idempotency keys are unique;
5. every migration in the selected edge's declared prerequisite closure succeeded;
6. every same-target prerequisite edge joins exactly;
7. no ledger record pins the id to another manifest hash.

Directory order is not a universal execution history. Later-numbered root
migrations with no prerequisites may be alternative direct edges from different
supported historical versions; any one may run when its exact source matches.
An already-successful id with the exact same hash is an idempotent no-op only
after recovery evidence, transform postconditions, mirrors, and full validation
are rechecked.

## Checkpoint, validation, and ledger

The candidate integration contract fixes this order:

`outer exact checkpoint proof → strict preflight → dry-run transform → transform
→ version update → declared validation → append journal + applied ledger`

If validation or final recording fails, the isolated candidate is discarded.
The migration runner never creates an internal checkpoint or rollback that
could touch shared Git state; the outer upgrade transaction owns live recovery.

The canonical append-only-by-tool **applied** ledger is
`System/Journal/migration-ledger.jsonl`. Each JSON line records the migration
id, idempotency key, version target, source identity, exact from/to versions, manifest hash, UTC
timestamp, checkpoint identity, result, and runner version. Failed attempts are not
written into the restored vault: that would make an otherwise exact rollback
non-exact. Their evidence remains in command output; only a successful apply is
durable migration history. It is consistency-checked, not externally immutable
or tamper-proof without a Git or external anchor.

## Imports and upgrades

Bulk import plans may also live under `System/Migrations/`, but use
`import-plan.yaml` and `aios import`; they are not migration manifests. Upgrade
may invoke a selected historical migration only against its proven candidate
before the live swap. It never mutates the live tree in place.

## Historical 1.64.5 data status

`historical-sources.yaml` pins the exact 24 supported official source commits,
their canonical baseline identities, the three explicitly refused non-main
identities, and the exact old `_ABOUT.md` and `LICENSE.md` hashes.
`generate_historical.py` recomputes that evidence from Git and deterministically
emits 19 direct combined edges from 1.43.0–1.63.0. Each accepts only the
pristine historical `_ABOUT.md` and approved legacy core license, then installs
the exact target user-surface and MIT payloads. Every historical edge targets
1.64.5 directly; none requires an intermediate migration. Exact no-write
postcondition edges preserve pristine v1.64.1, v1.64.2, v1.64.3, and v1.64.4 sources while
refusing an edited license before publication.

Official 1.64.0 has a different baseline identity from the development
1.64.0 state accepted by migration 020. Alternative edge 021 recognizes the
official identity and treats the already-correct MIT bytes as an exact
postcondition; the runner verifies but does not rewrite them. Its byte-identical
license needs no physical write; its exact legacy root surfaces are separately
hash-bound and updated.

Official 1.64.1 edge 022 is bound to the final v1.64.1 source identity. It has
one exact MIT-license postcondition whose old and new hashes are identical. A
pristine license produces no physical write; any custom or edited license
refuses before the transform begins.

Official 1.64.2 and 1.64.3 edges 023 and 024 use the same exact no-write MIT
postcondition pattern, each bound to its immutable public release identity.

The legal payload evidence and exact final v1.64.1 source ref are pinned. These
edges do not infer a missing legacy `distribution_id` and
do not authorize PMM migration; absent distribution evidence remains a hard
preflight refusal.
