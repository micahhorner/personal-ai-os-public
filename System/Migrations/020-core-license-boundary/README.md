# Core license boundary transition

This direct system-version edge is only for
`system.distribution_id: personal-ai-os`. It accepts exactly two `LICENSE.md`
states: the known legacy proprietary bytes (SHA-256 `e5bb369…`) and the
already-correct MIT bytes (SHA-256 `56fad99…`). Every other state refuses
before mutation.

PMM Engine must not take this edge. Its separate pre-transition is:

1. copy the existing proprietary license bytes into `Packs/pmm/LICENSE.md`;
2. change `Packs/pmm/pack.yaml` from root inheritance to
   `license: LICENSE.md` (resolved relative to the pack root);
3. declare `system.distribution_id: pmm-engine`; and
4. verify the attached file still hashes to the approved source bytes.

That PMM transition is not encoded here because PMM is a separate distribution
and its source tree is not shipped in this repository. Applying a guessed PMM
payload or source identity from the core release would defeat the boundary this
migration establishes.
