---
id: doc-automations-reference
type: system-doc
file_class: canonical
authority: canonical
canonical_for: automations-reference
version: 1.0.0
created: 2026-07-13
updated: 2026-07-13
summary: The complete reference of every automatic check and automation that runs behind the scenes to keep the vault safe, consistent, and trustworthy — what each does, when it fires, and why it matters.
---

# Automations & Checks Reference

**The machinery that keeps your knowledge safe, consistent, and trustworthy over years. Each entry: what it does, when it fires, why it matters.**

**Read the "when it fires" column literally.** Most rows are genuine machinery — a script runs them
and you never trigger them. Some are **rules a person or an AI performs**, and those are marked
*(a rule, not machinery)*. The distinction is the whole value of this page: a rule that nobody
performs simply does not happen, and believing it is automatic is how supersession chains and stale
approvals survive a green gate. Where a row names a command, that command has to be run.

Visual overview: `System/Documentation/Diagrams/svg/36-automations-always-on-layer.svg`.

---

## When you write — every save

| Automation | When it fires | What it does | Why it matters |
|---|---|---|---|
| **Preflight** | Before any create/edit/rename/delete | Runs a proportional check: understand the change, search for what exists, check placement and impact | No write happens blind; effort scales with risk |
| **Search-before-create (dedupe)** | On every new record | Resolves the topic against existing records (id → title → aliases → phrases) before creating | Duplicates are treated as corruption; you don't get two of the same thing |
| **Validation** | After every write session | Checks schema, IDs, vocabulary, naming, and registry conformance | Malformed records can't quietly accumulate |
| **Governance-value check** | During validation, every record | Privacy fields (`classification`, `ai_use`, `domain`, `approval`) are validated on every record regardless of its type; unrecognised values are errors and the filter treats them as excluded | A typo in a privacy field can never widen access |
| **Secret scan** | During validation | Greps note text for password/key/token patterns and fails loudly | Backstop against secrets landing in the vault |
| **ID integrity** | During validation | Enforces id grammar (`<type>-<slug>`), uniqueness, and type-prefix match; ids are immutable | Stable references survive renames; no ambiguous or duplicate records |
| **One-owner rule** | During validation | Ensures exactly one document is `canonical_for` each rule domain | No two docs claim authority over the same rule |
| **Portability guards** | During validation | Rejects case-collisions, forbidden filename characters, and over-length paths | The vault stays portable across filesystems (DEC-005/007) |
| **Component-contract check** | During validation / activation | A component must carry its full contract fields and listed tests | Half-built components can't pass as real |
| **Agent self-modification guard** | During validation | An agent's writes may never include its own — or another agent's — contract | An agent cannot rewrite its own permissions |
| **Supersession integrity** | `aios links` (dangling target) / `aios validate` (status disagreement) | `links` **errors** when a `supersedes`/`superseded_by` value names an id no record has. `validate` **warns** when the old record's `status` is not `superseded`/`archived`. Neither writes: the reciprocal `superseded_by` is set by whoever performs the supersede (`safe-write`) | Supersession chains never dangle — but only because the writes are authored; no command repairs one |
| **Four-outcome rule** | On consequential changes | Forces every downstream effect to end as updated · marked stale · queued · or confirmed-unaffected | "No invisible maintenance" — nothing is left silently uncertain |
| **Journal entry** *(a rule, not machinery, except below)* | On every consequential+ change | A line is appended (date, actor, action, targets, outcome, checkpoint). **Only `migrate`, `import` and `upgrade` append it themselves**; for every other change the runtime writes it, per Change Control | Your audit trail; ordinary leaf edits stay out so it stays readable |
| **Auto-checkpoint** *(machinery inside the batch commands; a rule elsewhere)* | Before every high/critical change or batch | A restore point is created (git commit or zip snapshot). `migrate`, `import`, `pack` and `upgrade` checkpoint themselves; an ordinary high-tier edit is checkpointed because the runtime runs `aios checkpoint` first | Any risky change is reversible |

## When you ask — every retrieval

| Automation | When it fires | What it does | Why it matters |
|---|---|---|---|
| **Privacy filter** | Before relevance ranking, on every retrieval | Excludes restricted/prohibited content entirely; enforces local-only, private, and domain rules | Sensitive material is invisible, not just deprioritized |
| **Freshness-on-access** | When a record is retrieved | Flags anything past its review date as "verify before relying" and queues it | Stale material is never silently presented as current fact |

## When you add — inbox / ingest

| Automation | When it fires | What it does | Why it matters |
|---|---|---|---|
| **Source preservation** | On ingesting any material | Stores the original as an immutable Source, annotated but never rewritten | Your evidence stays exactly as captured; claims trace back to it |
| **Nine-effects assessment** | On connecting each ingested item | Evaluates creates · changes · supports · weakens · contradicts · clarifies · connects · makes-stale · enables | New knowledge is reconciled against what you already know; contradictions are preserved, never resolved by deletion |
| **Dedupe & link** | On each inbox item | Resolves against canon and connects to related projects, people, notes | Knowledge compounds instead of fragmenting |

## When structure changes — migrations, imports, recovery

| Automation | When it fires | What it does | Why it matters |
|---|---|---|---|
| **Migration safety** | On `aios migrate` | A numbered migration runs dry-run → human approval → checkpoint → apply → validate, and refuses to continue past a validation failure | Structural change can't half-apply or corrupt the vault |
| **Import quarantine** | On `aios import` | Source stays read-only; dry-run → approval → apply; anything unmapped is quarantined to the Inbox; a one-time marker blocks re-runs | Bringing in a vault never drops or overwrites material |
| **Rollback** | On `aios rollback` (human-confirmed) | Executes the identity-bound command printed by checkpoint. Git restore verifies the full commit and tracked-tree hash and externally preserves bytes before destructive cleanup. No-Git restore verifies the archive hash and embedded per-file manifest, stages beside the vault, swaps atomically, and retains or reinstates the prior live tree on failure. Works even while the kill switch is off (your `--confirm` is the authorization). | Any whole-tree checkpoint is reversible to a verified known-good state |

## Weekly maintenance

| Automation | When it fires | What it does | Why it matters |
|---|---|---|---|
| **Health check** | The weekly pass (or on request) | Aggregates validation, broken-link detection, duplicate detection, review-due count, and inbox age | One command tells you the vault's overall state |
| **Documentation truth** | Inside every health run | `aios doc-audit` reads the real counts from source (commands, capabilities, principles, diagrams, the current version) and errors when any document's stated number disagrees; history is exempt | The docs can't quietly drift from the product they describe |
| **Documentation paths** | Inside every health run | `aios doc-paths` checks every backticked `System/` file path the docs cite and errors on any that no longer exists; placeholders, runtime-created folders, and history are exempt | A doc can't keep pointing at a file that moved — the reference class link-checking skips |
| **Freshness triage** | Weekly | Bumps, re-derives, flags stale, or proposes archival for items whose sources changed | Knowledge stays current without you tracking it |
| **Drift checks** | Weekly (Steward) | Verifies adapters still point at (not restate) rules, generated files aren't hand-edited (hashes), the component index matches reality, doc authority is unique | Catches structural rot before it spreads |
| **Rebuild generated state** | Weekly (`aios generate`) | Regenerates indexes, reverse views, the ops registry, the system reference, and the support index from source | The "card catalog" is always current by construction; never the source of truth |
| **Doc-freshness flag** | During health | Flags derived docs that fell behind the source version they were reviewed against | Prose that needs a human refresh surfaces rather than silently misleading |
| **Generated-age flag** | During health | Warns when generated docs are overdue for a rebuild | Prompts a regenerate before views drift |
| **Doc-check coverage** | During health + at activation | Fails if any component lacks a described diagram, or any diagram is missing/undescribed | Documentation can't fall behind the code (DEC-051) |
| **Doc-staleness flag** | During health | Flags manifest entrypoint / reading-order paths that point to files that no longer exist | The manifest can't silently point at moved or deleted docs |
| **User-privacy check** | During health (personal instances only) | Warns if a personal instance has no `80 User/privacy-rules` file — a sign onboarding stage 2 didn't finish | Verifies your privacy defaults were actually created; conservative governance defaults apply until then |

## On demand

| Command | When you run it | What it does | Why it matters |
|---|---|---|---|
| **`aios certify`** | Before a release/promotion, or any time you want assurance | Composes the mechanical checks (via `health`) with certification-only gates — governance/safety (kill-switch enforced, protected objects present, and — **on the generic master only** — no personal data; your own vault is expected to hold personal data and is not scanned), command idempotency, doc-truth (manifest version must not lag the CHANGELOG — a hard gate), and the regression suite — into one ranked report, printed to stdout. **Non-destructive by restoration, not by abstention:** the idempotency probe really does run `generate` twice, then puts `System/Generated` *and* the freshness ledger/registry back exactly as they were, so the tree ends byte-identical (asserted by `test_read_only.py`, not merely promised) | One command answers "is the product sound enough to ship?" — the deterministic backbone a deeper on-demand review builds on |
| **`aios vocab`** | Any time, or as a writing check | Guards against banned terms from a user-owned list (`80 User/vocab-guard.yaml`); violations are editorial warnings, never structural errors | Keeps writing on-voice without blocking work (DEC-035) |
| **`aios okf-export <scope>`** | When you want a slice of your vault in a portable, vendor-neutral format | Emits a folder (default `knowledge`) as an **Open Knowledge Format bundle** into `40 Outputs/okf-<scope>/`, at a version it declares (`--okf-version`, default **0.2**) — the OKF fields map across and every AI OS field rides along as an extra key, which the spec expressly permits. Privacy is fail-closed and *stricter* than search: `local-only` never exports on any runtime; `private`, `restricted`, draft and unrecognised-status material never export at all; and a *reference* to any of them is withheld too, because a vault id is a slug of its record's title. `generated` is emitted only when you name the author (`--author`); `verified` is never emitted, because this vault records a verification grade rather than verification events. The bundle inherits the most sensitive classification it contains and is never marked approved | Your knowledge is portable to any OKF reader without lock-in — and the export can't quietly carry out what you marked as staying in (Privacy §2/§3) |
| **`aios okf-import <bundle>`** | When someone hands you an OKF bundle | Lands every concept in the bundle as an **immutable `source` note**, born `status: draft` / `verification: unverified`, preserving the OKF values under `x_okf_*` keys — v0.2's `generated`, `verified`, `status`, `stale_after` and `sources` included, with anything else the producer wrote kept under `x_okf_extra`. Their `stale_after` becomes this vault's `review_due`; their `verified` never becomes this vault's verification | Foreign knowledge arrives as *evidence*, not canon. Turning it into knowledge is `ingest-and-connect`'s job, and no machine may promote it on its own (Principle 26) |

## Always on — standing guards

| Automation | When it fires | What it does | Why it matters |
|---|---|---|---|
| **Kill switch** | Whenever `ai_writes_enabled: false` | Every compliant runtime and script refuses all writes | One line stops the AI instantly; your files stay yours |
| **Protected objects** | On any attempt to change governance, schemas, agent contracts, or your privacy rules | Blocks the change without explicit, current human instruction | The system's own law can't be altered silently |
| **Approval reset** *(a rule, not machinery)* | When an `approved` item is edited | The editor — you, or the AI following `safe-write` — sets `approval` back to `pending`. **No command does this and nothing detects a missed reset:** `validate` checks that the *value* is from the vocabulary, never that it is still deserved | "Approved" should always mean the current version — so the demotion has to be performed, not waited for |
| **Activation gates** | When a new component is registered | Refuses activation without passing tests *and* documentation (a described diagram), plus your approval | New capabilities are always tested, documented, and recoverable |
| **Certification gates** | When a runtime operates | Grants autonomy levels only by passing test fixtures; a failure caps the level | Trust is earned by evidence, never assumed |
| **No-personal-data tripwire** | In the generic master (`instance_role: generic-master`) **only** | `certify`'s governance gate fails if personal data appears in the shipped master. It does **not** run on your vault: a personal instance is supposed to hold colleagues' addresses and contact records, and until v1.49.0 the scan fired everywhere, which made `certify` unable to pass on any real vault | The product master never ships a person's data (DEC-020/021) — without calling your own notes a defect |

---

## Related

- The visual overview — `Diagrams/svg/36-automations-always-on-layer.svg`.
- The safety machinery in depth — `Diagrams/svg/05-change-control-tiers.svg` (proportional preflight), `Diagrams/svg/06-privacy-routing-gate.svg` (privacy), `Diagrams/svg/21-recovery-backup.svg` (recovery).
- The flows these run underneath — `Flows/Flows of Work.md`.
