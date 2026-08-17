---
id: doc-result-okf-round-trip
type: system-doc
file_class: canonical
authority: canonical
canonical_for: result-okf-round-trip
created: 2026-07-16
updated: 2026-07-16
summary: "Passing proof for the OKF emitter/importer (aios okf-export / okf-import) — round-trip lossless on shared fields, planted-privacy fail-closed, and Google's own sample bundles land clean. Phase C gate evidence."
---

# Result — OKF emitter + importer

**Run**: 2026-07-16 · **Development line**: isolated change line · **Verdict: PASS.**

Six proofs, all run live against a disposable clone of the product and against
Google's real published sample bundles (`GoogleCloudPlatform/knowledge-catalog`,
Apache-2.0, cloned at proof time — the repo is the source of truth, verified per
the verify-against-live-source rule, not the blog post).

## 1. Live-spec verification (the plan's first mandated step)

Fetched `okf/SPEC.md` and sample bundles. **One finding corrected the plan's
assumption:** the plan lists `timestamp`, `resource`, `description` etc. as a
fixed mapping, but the spec makes **`type` the only required field** — everything
else is *recommended*, and **extra keys are explicitly permitted** ("Producers
MAY include any additional keys. Consumers SHOULD preserve unknown keys when
round-tripping"). So the AI OS superset rides along as top-level keys and
**nothing is dropped** — the plan's "AI OS extras dropped with a manifest note"
fallback proved unnecessary. `index.md`/`log.md` are the only reserved filenames
and are exempt from the frontmatter rule.

## 2. Export — the emitted bundle is OKF-conformant

`aios okf-export knowledge` on a seeded vault (6 notes) → a bundle of 3 concepts
plus `index.md` and the `okf.yaml` marker. Each concept carries a non-empty
`type` (the one hard requirement); the OKF fields (`title`, `description`,
`resource`, `tags`, `timestamp`) come first, the AI OS fields after.

## 3. Planted-privacy — fail-closed on the way out

Of the 6 seeded notes, 3 carried planted markers: one `classification: private`,
one under a `Local Only/` folder, one `status: draft`. **`grep -r PLANTED_ bundle/`
returned nothing** — 0 of 3 leaked. The export filter is deliberately *stricter*
than `aios search`: `local-only` never exports **on any runtime profile** (a
local runtime may read it, but a bundle is built to travel), and `private`/
`restricted`/draft never export at all.

## 4. Import — foreign knowledge lands as evidence, never canon

`aios okf-import` on Google's three real bundles:

| Bundle | Concepts imported as sources |
|---|---|
| `stackoverflow` | 49 |
| `ga4` | 11 |
| `crypto_bitcoin` | 5 |

Every one landed as an immutable `source` note, born `status: draft` /
`verification: unverified`, OKF values preserved under `x_okf_*` keys. **None was
auto-promoted** (checked: 0 landed sources with status ≠ draft). The bundle's own
hierarchy (`tables/`, `datasets/`, `references/`) and filenames are preserved, so
its internal relative links keep resolving.

## 5. Round trip — zero content loss on shared fields

Export a seeded set from vault A → re-import into scratch vault B → scripted
field-by-field comparison: **19 shared fields compared across 3 concepts, 0
losses.** `type`, `title`, `description`, `tags`, `timestamp`, `resource`, and the
concept body all survive byte-identical. This is the portability claim proven
against an external yardstick, not asserted.

## 6. The bundle does not corrupt the vault that holds it

A bundle lives inside `40 Outputs/`, which the vault scans as canon. **Negative
control:** with the `okf.yaml` marker present, `validate` is green; remove the
marker and the same bundle produces **16 errors** (duplicate ids against the
source notes it was copied from, unknown OKF keys against the note schema). The
marker makes `iter_markdown` prune the bundle — a foreign artifact is not judged
as though the vault authored it (the same principle as `Packs/`, DEC-067).

**Full suite after importing all three Google bundles (65+ foreign sources
in-vault):** `validate` `links` `dupes` `doc-check` `doc-commands` `doc-audit`
`health` — all green (0 errors). Broken-link warnings from imported OKF sources:
**68 → 0** once the bundle hierarchy was preserved instead of flattened.

**Unit tests:** `System/Tests/scripts/test_okf.py`, 27 tests; full suite 145
tests green.
