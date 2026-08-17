---
id: adapter-claude-guide
type: adapter
file_class: runtime-specific
authority: derived
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
derived_from: [doc-canonical-architecture]
created: 2026-07-10
updated: '2026-08-14'
summary: How the Claude adapter is wired — pointer file, operation mapping, and the rules for keeping this adapter thin.
---

# Claude Adapter Guide

Three pieces: the vault-root `CLAUDE.md` (pointer file Claude Code loads automatically), `operation-mapping.yaml` (vault.* → Claude-native), and the capability notes. **This adapter translates; it never owns rules.** If you find a rule stated here that isn't in a canonical governance/architecture doc, that's drift — report it. Claude is hosted, and the active profile controls what the filtered `aios search`/`read` transport returns: `restricted`, `ai_use: local-only`, and `ai_use: prohibited` are excluded; `private` is allowed by the shipped `may_process_private: true` setting. **Claude Code also has native file access.** In that mode the same restrictions are binding compliance rules, not physical confinement—the vault cannot prevent it opening another readable path. A user needing a mechanical boundary must keep the material outside that runtime's filesystem reach; the brokered design is not implemented in the current release.

**Agent Skills projections** (DEC-070/071, constitution §7.1): `aios generate` emits every active
capability as a spec-valid Agent Skill under `.claude/skills/aios-<name>/SKILL.md`, so Claude Code
(and any skills-compatible runtime) can discover the procedure natively. These are generated,
disposable, and gitignored — the canonical capability stays `System/Capabilities/<name>/SKILL.md`
with its full AI OS contract. Inside the vault, the **Task Router still names the capability
deterministically**; the projections exist for foreign agents and discovery, never for core routing.
An emitted skill is a procedure, not the OS — governance does not travel with it. Only the `aios-*`
namespace is managed by the emitter; a user's own `.claude/skills/` entries are never touched.
