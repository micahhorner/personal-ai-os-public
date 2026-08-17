---
id: doc-change-control-and-preflight
type: system-doc
file_class: canonical
authority: canonical
canonical_for: change-control
version: 1.1.0
created: 2026-07-10
updated: 2026-08-09
summary: The universal proportional preflight, risk tiers, exact reviewed approval for protected batches, protected objects, and checkpoint/rollback rules. No vault write may bypass this document.
---

# Change Control and Preflight

**Every write to this vault receives a preflight. No exceptions — only the depth varies with risk.** This applies to every actor: human-directed AI, autonomous maintenance, scripts acting on instructions, and future runtimes.

## 1. The universal rule

Before creating, editing, renaming, moving, merging, splitting, archiving, or deleting anything:

1. **Understand** — what is changing, why, and how reversible it is.
2. **Search before creating** — does a canonical record already serve this purpose? (titles, aliases, IDs, similar wording).
3. **Check placement** — correct folder, note class, template, required metadata.
4. **Check impact** — upstream (what this depends on) and downstream (what depends on this), at the depth the risk tier requires.
5. **Make the smallest valid change** — canonical source first, derived material after; prefer marking stale over silently rewriting.
6. **Validate** — the change and its blast radius.
7. **Report** — what changed, what was checked, what propagated, what was marked stale, what needs review, and the rollback point.

## 2. Risk tiers and preflight depth

| Tier | Examples | Depth | Approval |
|---|---|---|---|
| **Low** | new leaf note; typo; status flip; adding a link | **Light**: dedupe search + template/location check + link validation — quiet, no journal entry (kernel ordinary lane) | automatic |
| **Medium** | editing a canonical note; rename/move; new note with dependents; archive | **Standard**: light + upstream/downstream relationship scan + operational grep (old paths, IDs, names across scripts, capabilities, agents, workflows — computed: `aios ripple --refs <old-name>`) + change-journal entry | automatic-with-report, or draft-only where the class table says so |
| **High** | schema, template, capability, agent, script, workflow changes; merging canonical notes; folder structure | **Full**: standard + checkpoint + written impact report (use the Appendix taxonomy) + post-change validation suite + change-record document | **human approval required** |
| **Critical** | deleting canonical records; anything touching protected objects; migrations; changing approval/privacy fields on approved material; bulk multi-file operations | Full, plus explicit rollback plan stated before execution | **human approval required, per instance** |

Deletion of canonical records is never automatic. Archive, deprecate, or supersede instead; delete only on explicit human instruction.

## 3. Approval modes

`automatic` · `automatic-with-report` · `draft-only` (create in Inbox/staging for review) · `approval-required` · `prohibited`. The mode for each action class is set by the tier table above; when in doubt, escalate one level. **Escalating to the human is a valid outcome, not a failure** — mandatory when sources conflict, context is missing or stale, confidence is low, another person's private data is involved, or the action would publish, send, or destroy.

## 4. Protected objects

Changes **prohibited** without explicit, current human instruction (also listed in SYSTEM-MANIFEST.yaml):

- `SYSTEM-MANIFEST.yaml` (except the human flipping the kill switch)
- `System/Architecture/**` and `System/Governance/**`
- `System/Schemas/**`
- Every agent's contract (its `AGENT.md` frontmatter) — **an agent may never alter its own contract or permissions, nor another agent's**
- `System/Runtime/` — **the Runtime Kernel and the Task Router**, the two files every session loads
- `System/Runtime Profiles/` — what a runtime is permitted to do
- `System/Adapters/` — per-runtime translation
- `System/Operations/` — the operation contract
- `System/Tests/results/` — recorded certification evidence
- `80 User/` privacy rules
- Anything with `approval: approved` (changing it resets approval to `pending`)

*(This list is the same eleven the manifest carries, and `upgrade.py` reads the manifest — so the
code was gating more than this section admitted. The five entries above the privacy line were the
gap, and `System/Runtime/` was the one that mattered: the Task Router is the file this very document
tells a runtime to load first.)*

### 4a. Reviewed protected-write batches (DEC-121)

Human approval is necessary but not, by itself, a machine-readable description of the bytes a command may change. A mutating CLI operation that can touch protected objects must first run in its read-only review mode and print a deterministic review plan plus `review_sha256`. The apply is authorized only by all three controls together: `--apply --confirm --review-sha256 <exact fresh hash>`. The command re-proves the live policy and reviewed inputs before its first write and again at its commit boundary; a missing, malformed, changed, expanded, or stale plan refuses the **whole batch** with zero protected writes. `--confirm` alone is never permission to substitute a different plan.

Where final bytes do not yet exist at review time, the review must say so. `upgrade` is the bounded case: its hash binds the exact live and release surfaces, versions and distribution identities, baseline, accepted conflicts, migration source and plan, policy, and other semantic inputs. Candidate-local migrations, generation, and documentation refresh materialize final bytes only after that review. The transaction journal then pins the candidate and live tree identities used for exact recovery. This is an exact **semantic-input** review, not a claim that final output bytes were pre-reviewed.

This mechanism governs commands; it does not turn ordinary native edits into safe transactions. A manually directed protected edit still requires explicit current human instruction, full preflight, a checkpoint, the smallest valid change, and validation.

## 5. Checkpoints and rollback (DEC-011)

- **Checkpoint** = `aios.py checkpoint` — a Git commit when Git is available, a timestamped zip snapshot otherwise. Same command either way.
- Required before: every high/critical change, every migration, every construction batch.
- **Rollback** = `aios.py rollback` — restores the chosen checkpoint; zip snapshots can also be restored by hand (see Maintenance and Recovery Guide).

## 6. The four-outcome invariant ("no invisible maintenance")

Every detected downstream effect ends in exactly one of: **automatically updated** · **marked stale** (`status: stale` + journal note) · **queued for review** · **recorded as unaffected**. Nothing remains silently uncertain.

## 7. Change records and the journal

- Every medium+ change appends a line to `System/Journal/change-journal.md` (date, actor, action, target IDs, outcome, checkpoint ref).
- Every high/critical change also produces a change-record entry in the journal: what/why, impact report summary, validation results, unresolved items, rollback point.

## 8. Kill switch

If `runtime.ai_writes_enabled` is `false` in the manifest, every compliant runtime and every script refuses all writes. Check it before every write session.

---

## Appendix — Full-preflight reference taxonomy

Consulted for **full preflight only** (high/critical changes). Categories of dependency to check — use those relevant to the change, and record which were checked:

1. **Note relationships** — links, backlinks, embeds, every frontmatter relationship field (the `REL_FIELDS` list in `links.py`; enumerated in the Metadata and Relationship Dictionary), aliases, shared metadata values.
2. **Navigation** — generated indexes, MOCs, folder `_ABOUT` notes, dashboards, saved searches.
3. **Paths and filesystem** — folder registry entries, relative links, attachment references, watched/staging folders, external shortcuts.
4. **Schemas and data structure** — property names/values, vocabularies, required fields, existing notes on older schema versions, validation rules.
5. **Templates and creation flow** — templates using the changed schema, default properties, scaffold skeletons, notes created from earlier template versions.
6. **Instructions and governance** — this document, privacy rules, operator manuals, adapter pointer files; contradictions between the change and any active rule.
7. **Capabilities** — any capability that reads, creates, classifies, or validates the changed class/location; their examples and tests.
8. **Agents** — scopes, permissions, prohibited actions, capabilities_used; whether an agent's assumptions survive the change.
9. **Scripts and operations** — hard-coded names/IDs/fields in `System/Scripts/`, operation definitions, CLI mappings, idempotence and dry-run behavior.
10. **Workflows and scheduled activity** — workflow docs, maintenance routines, anything that will run later against the old state.
11. **Queries, reports, generated views** — regeneration needed? stale flags correct afterward?
12. **Provenance and lineage** — does the change break source→knowledge→output traceability in either direction?
13. **Canonical duplication** — is the target a copy, summary, or generated view rather than the canonical record? Update the canonical first.
14. **Decisions and assumptions** — does this conflict with an active decision, invalidate an assumption, resolve or create a question, reintroduce a rejected approach?
15. **Privacy and permissions** — classification/domain/ai_use effects; does a structural change accidentally widen access or exposure?
16. **External systems** — copies or consumers outside the vault (documents, published material); do not modify external systems unless the task explicitly permits it.
17. **Backup and version control** — checkpoint exists and covers affected files; rollback method known; generated state rebuildable.
18. **Tests** — which tests must run, be updated, or be added; a changed rule or component is incomplete until its tests reflect the new state.
19. **Terminology** — old names/phrases in titles, bodies, prompts, components; never rewrite historical wording inside quotations or dated records.
20. **Temporal effects** — validity dates, review dates, supersession chains, lifecycle states of affected records.
21. **Failure scenarios** — partial completion, interrupted migration, concurrent human edit; define the safe stopping point before starting.
