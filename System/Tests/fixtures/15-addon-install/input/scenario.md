---
id: doc-fixture-15-input-scenario
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-15-input-scenario
created: 2026-07-14
updated: 2026-07-14
summary: "Input for fixture 15-addon-install: the dropped pack and the three user asks."
---

# Input — 15-addon-install

A file `demo-pack.zip` sits in the OS root. Unzipped, it is a self-contained pack:

- `pack.yaml` — `id: pack-demo`, `name: "Demo Pack"`, `version: 1.0.0`, `kind: capability`, `license: MIT`, `source` set, `components.capabilities: [capabilities/demo.md]`.
- `capabilities/demo.md` — one active capability, `id: capability-demo`, that reports the installed pack version.
- `tests/test-demo.sh` — the capability's test.

The three user asks, in sequence:

1. "Install the new pack." (folder `Packs/demo/` does not yet exist)
2. Later, with a `demo-pack.zip` at `version: 1.1.0` dropped in the root again: "Install the new pack." (an update — `Packs/demo/` exists at 1.0.0)
3. Later: "Remove the demo pack."
