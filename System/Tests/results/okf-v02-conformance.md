---
id: doc-result-okf-v02-conformance
type: system-doc
file_class: canonical
authority: canonical
canonical_for: result-okf-v02-conformance
created: 2026-07-26
updated: 2026-07-26
summary: "Passing proof for the OKF v0.2 surface (aios okf-check / okf-export / okf-import at DEC-103) — round trip measured from the original note to the landed note, privacy fail-closed on content AND references, and Google's own four published v0.2 bundles verified and imported clean."
---

# Result — OKF v0.2 conformance

**Run**: 2026-07-26 · **Development line**: isolated change line · **Verdict: PASS.**

The 2026-07-16 record (`okf-round-trip.md`) proved the v0.1 surface and stands as
written — it was true when written. This is the separate proof for v0.2, run
against the live spec and Google's own migrated bundles rather than against that
record.

## 0. The spec, read from source

`okf/SPEC.md` at `GoogleCloudPlatform/knowledge-catalog` (Apache-2.0), fetched
2026-07-26 along with the commit history: **v0.2 landed 2026-07-24** in commit
`780fe9d3` ("okf: migrate format and tooling to Open Knowledge Format v0.2",
#227), followed by `3fcbb9f8`. v0.1 was `d44368c1`, 2026-06-21.

Both spec texts were diffed. **Conformance (§11) is unchanged from v0.1 §9 —
three rules, not two.** A first pass through the spec read only two, because rule
3 fell in the gap between two chunked reads of the file; the pre-build adversary
pass caught it against the source before any of it reached shipped prose. That
correction is recorded here because it is the same failure the release exists to
close, one version up.

## 1. Google's own bundles — the external yardstick

All four published bundles, checked at v0.2 and imported:

| Bundle | Concepts | Rule 3 | Advisories | Verdict |
|---|---|---|---|---|
| `acme_retail` | 9 | 8/8 | 0 | CONFORMANT |
| `crypto_bitcoin` | 9 | 6/6 | 0 | CONFORMANT |
| `ga4` | 9 | 5/5 | 0 | CONFORMANT |
| `stackoverflow` | 26 | 6/6 | 0 | CONFORMANT |

**53 concept documents, 0 errors, 0 advisories.** Zero advisories on a corpus
that exercises every v0.2 family is the signal that matters: the advisory checks
match real v0.2 usage rather than a reading of it. Field census across the four
bundles: `generated` on 53, `sources` on 49, `status` on 10, `verified` on 8,
`stale_after` on 7, the Attested Computation contract on 2 — and **zero** legacy
`timestamp` or `# Citations`, so Google's own tooling completed the migration.

`aios okf-import bundles/acme_retail` into a fresh vault: their `generated`
(`reference_agent/gemini-2.5-pro`), their `verified` events, their `deprecated`
status, their `stale_after`, their `sources`, and the whole Attested Computation
contract (`runtime`, `executor`, `attester`, `parameters`) all landed. Their
`verified` did **not** raise this vault's `verification`, which stayed
`unverified`.

## 2. Round trip — original note → landed note

Measured from the **source note**, not from the emitted bundle. The older
comparison started at the bundle, which structurally cannot see a field dropped on
the way out — and every mapping v0.2 added happens on the way out.

Seeded fresh scratch vault (the shipped Test-Vault is stale) → `okf-export
knowledge --author human:proof` → `okf-import` into a second fresh vault. Zero
loss on every shared field: `type`, `title`, `description`/`summary`, `tags`,
`resource`/`original_location`, `review_due` (out as `stale_after`, back as
`review_due`), `updated` (out as `generated.at`), the asserted `generated.by`,
`id`, `created`, `verification`, the AI OS `status`, and the `sources` id-list.
Body prose byte-identical. The landed record is `type: source`, `status: draft`,
`verification: unverified` — evidence, never canon.

The same trip at `--okf-version 0.1` is lossless on the same fields via
`timestamp`.

## 3. Privacy — planted markers, content and references

Six planted records, none of which may travel: `classification: private`,
`classification: restricted`, `ai_use: local-only`, `sync: local-only`, a
`Local Only/` folder, and an unrecognised `status: Active`. **No marker string
appeared anywhere in the bundle**, and neither did any of their **ids** — the
reference fence, new in this release. A vault id is a slug of its record's title,
so a `sources`, `related`, `derived_from`, `depends_on`, `supports`,
`contradicts`, `entities`, `supersedes`, or `superseded_by` entry pointing at an
excluded record used to carry that record's title out of the vault. Each of the
nine fields is covered by its own regression test.

The unrecognised-status case is DEC-066 reaching a branch that had only a
blacklist: before this release `status: Active` exported, and the v0.2 mapping
would have laundered it into `status: stable`.

## 4. What the export refuses to say

- **`verified` is never emitted.** AI OS records a verification *grade* with no
  actor and no date; v0.2 records verification *events*. Every exported concept
  therefore sits in §5.3's lowest trust tier — the honest position, and a real gap
  in what this vault records rather than in what it will claim.
- **`generated` only with `--author`.** `generated.by` is required inside it, and
  the vault does not record who wrote a note. Without the flag the last-change
  time rides as the legacy `timestamp`, which §13.1 sanctions consumers to fall
  back to, and the run says so in a warning.
- **No Attested Computation is authored.** This system has no attestation
  machinery.

## 5. Gates

Unit suite **472 tests, OK** (428 before; +44 across `test_okf.py` and
`test_okfcheck.py`). `validate` · `links` · `dupes` · `doc-check` ·
`doc-commands` · `doc-audit` · `doc-paths` · `health` · `certify` ·
`docgen --check` all green; baseline regenerated. Full run recorded in the
release's change-journal entry.
