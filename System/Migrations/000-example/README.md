# Example migration

This is a structurally valid template, not a historical migration. Sequence
`000` is permanently non-executable.

Copy the directory to an unused unique `NNN-kebab-case` name, make the
manifest id exactly `migration-<directory-name>`, and replace every example
value. Compute `manifest_hash` last: it is the SHA-256 of canonical JSON for
the manifest with `manifest_hash` omitted.

The manifest explicitly selects `system_version` or `vault_profile_version`
and binds the exact canonical source-baseline identity; a matching version
string alone never authorizes the edge.
The preview runner refuses an inexact source version, a missing predecessor or
prerequisite, out-of-order execution, changed manifests previously seen in the
ledger, and unsafe paths before transform. A repeated successful
id with the exact same hash is a no-op only while transform postconditions,
recovery evidence, mirror checks, and full-vault validation still pass.

Public direct apply is disabled. An exact eligible edge may run only inside an
upgrade candidate after the user reviews the upgrade's semantic-input plan and
apply proves candidate ownership plus a materially verified outer checkpoint.
Do not write a migration whose rollback contract permits weaker recovery.
