---
id: doc-privacy-and-boundaries
type: system-doc
file_class: canonical
authority: canonical
canonical_for: privacy
version: 1.2.0
created: 2026-07-10
updated: 2026-08-09
summary: Privacy classifications, AI-use permissions, domain boundaries, the sync storage boundary, routing rules, enforcement modes, and secret handling.
---

# Privacy and Boundaries

## 1. The four governance fields (DEC-008; `sync` added by DEC-092)

| Field | Values | Governs |
|---|---|---|
| `classification` | `public` · `internal` · `private` · `restricted` | Sensitivity of the content itself — **who may read it** |
| `domain` | `work` · `personal` · `shared` | Which sphere of life it belongs to |
| `ai_use` | `allowed` · `local-only` · `prohibited` | What any AI runtime may do with it |
| `sync` | `allowed` · `local-only` | **Where it may be stored** — may this file leave the machine via git push, cloud sync, or a hosted backup? Nothing else: retrieval stays with `ai_use`, readability with `classification` |

Plain-language: *who can read it* (`classification` + `ai_use`) and *where it may live* (`sync`) are different questions. A note can be readable by your hosted AI yet never leave your machine (`ai_use: allowed` + `sync: local-only`), or unreadable by AI yet safely synced (`ai_use: prohibited` + `sync: allowed`).

## 2. Routing rules (DEC-013 — mechanically enforced by filtered transports; a compliance obligation in direct-file mode)

`classification` describes **sensitivity**; `ai_use` is the **routing boundary**. They are orthogonal:

- `restricted` or `ai_use: prohibited` → excluded from every compliant retrieval result. This is a mechanical boundary only when the filtered transport is the runtime's sole route to content.
- `ai_use: local-only` → available through filtered retrieval only to a runtime whose trusted profile declares local execution. A hosted runtime with native file access is required not to open it, but the vault cannot physically prevent that access.
- **A folder named `Local Only/`** anywhere in a note's path marks everything under it `ai_use: local-only` (DEC-065) — the folder is the marking, honored fail-closed. Frontmatter still wins where stronger (`prohibited`, `restricted`).
- **Unrecognised values fail closed** (DEC-066): a misspelled `classification` or `ai_use` excludes the record everywhere until fixed — a typo must never widen access. `validate` errors on it, on every record, regardless of `type`.
- `private` + `ai_use: allowed` → may be processed by a hosted runtime **only if the human has approved that runtime for private content** (`may_process_private: true` in its profile). Without that approval, treat as local-only.
- Cross-domain: a task declared `work` does not receive `personal` material (and vice versa) unless the user explicitly asks; `shared` flows to both.
- In filtered retrieval, exclusion happens **before** relevance ranking — excluded content is invisible to that result, not just deprioritized.
- Exports and outputs inherit the most sensitive classification of their `derived_from` chain until a human reviews and re-classifies.
- **A reference is content (DEC-103).** A vault id is a slug of its record's title, so a relationship field carries that title even when the record itself was excluded — `entities: [person-jane-doe]` names a person; `contradicts: [note-the-thing-we-got-wrong]` states a claim. Every export therefore filters **all** id-bearing fields (`sources`, `related`, `derived_from`, `depends_on`, `supports`, `contradicts`, `entities`, `supersedes`, `superseded_by`) to records that may themselves travel, and reports the withheld count rather than silently thinning the graph.

**The storage boundary (DEC-092)** — `sync: local-only` means *never leaves this machine via any sync channel*. Enforcement rules:

- The promise must be **backed by a real `.gitignore` rule** in the vault root. `aios validate` cross-checks both directions: an explicit `sync: local-only` field no rule covers is an **error** (the promise is unbacked); a gitignored content file *not* marked is a **warning** (enforcement without a marking — the reverse drift). The matcher is conservative: when it cannot be sure a rule covers a file (negations, exotic patterns), it says **unverifiable** and warns — it never claims "covered" on a guess.
- A **`Local Only/` path segment implies `sync: local-only`** exactly as it implies `ai_use: local-only` (DEC-065). The product's own `.gitignore` backs the folder convention by default; folder and field may not disagree — `sync: allowed` inside a `Local Only/` folder is an error. One grandfathering rule: a folder-implied marking with no backing rule is **advisory** (warning), because the folder convention predates this field — an existing vault upgrading into this release must never go red on its own content; write the explicit field when you want the strict check.
- **Unrecognized `sync` values fail closed** (DEC-066 pattern): the record is excluded from every export/sync-dependent surface (`okf-export` refuses it) and `validate` errors, on every record, regardless of `type`. `sync: local-only` content never enters an exchange bundle on any profile.
- **`classification: restricted` is almost always the wrong field.** In a vault whose purpose is AI context, "don't put this in the cloud" is the common intent — and `restricted` instead removes the record from compliant retrieval, silently. `validate` warns on every `restricted` it finds and names the right pair: `sync: local-only` (storage) + `ai_use: local-only` (no hosted AI). This is the trap that unloaded a user's own context for four days without a symptom. In direct-file mode, neither field is a physical barrier against the runtime itself.
- Scope fence: `sync` answers **only** "may this leave the machine via sync/backup." It plays no part in retrieval, ranking, or AI readability — reusing it for those would recreate the conflation it exists to kill.

Defaults when unset: content notes `internal` / `shared` / `allowed`; everything in `80 User/` is `private` / `shared` / `allowed` — except onboarding answers the user marks sensitive, which are `local-only` (DEC-014).

**Enforcement honesty (DEC-013)**: `aios search` and `aios read` deterministically apply these rules before returning content. They form a mechanical privacy boundary only when a launcher or runtime integration makes them the runtime's sole content transport and the runtime has no native path to the vault or its copies. For a runtime with native file access (Claude Code today), the rules are a binding compliance obligation verified through the journal and spot checks — not a physical barrier. The product does not currently ship a qualifying launcher or sandbox. `System/Documentation/Brokered Retrieval Design.md` is explicitly a follow-on design, not an implemented mode. Choose runtimes accordingly for your most sensitive content.

## 3. Approval boundary

The system never claims ownership of the user's beliefs, values, public claims, relationships, irreversible decisions, or creative identity. Material for external use requires `approval: approved`, set only by the human. Editing an approved record resets it to `pending`.

## 4. Other people's information

Notes about people (entity subtype `person`) store what helps the user be a better colleague, friend, or family member — not surveillance. Another person's sensitive information defaults to `private` + `local-only`. When in doubt, escalate to the human.

## 5. Secrets

Never stored in the vault in any form: passwords, API keys, tokens, recovery codes, certificates. Reference environment-variable names only (`source: environment`, `variable: NAME`). `aios.py validate` greps for common secret patterns and fails loudly.

## 6. Retention and deletion

Deletion of canonical records follows change control (critical tier, human-approved). Personal data the user wants gone is deleted, not archived — including from checkpoints where practical; the recovery guide documents the procedure. Onboarding answers live in `80 User/onboarding-answers.yaml`, classified `private`; hosted-safe progress lives in `80 User/onboarding-progress.yaml`. Both may be pruned at completion. There is no field-level secrecy inside a file (DEC-026): filtering operates on whole records, and what enters the vault is the user's choice.
