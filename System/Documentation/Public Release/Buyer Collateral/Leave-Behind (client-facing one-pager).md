---
id: output-public-leave-behind
type: output
status: active
audience: client-facing
derived_from: [doc-public-claims-ledger]
created: 2026-08-13
updated: 2026-08-14
summary: "Client-facing explanation of the Personal AI OS v1.64.5 release and its security boundaries."
---

# Personal AI OS — the folder you keep

```yaml
document: leave-behind
date: 2026-08-13
audience: CLIENT-FACING
claim_basis: Personal AI OS v1.64.5 release mechanics; qualification claims require exact tag-bound release evidence
```

Personal AI OS is a folder of ordinary files that holds your notes, sources, decisions, preferences, and working procedures. A filesystem-capable AI reads the folder's rulebook before it works. You keep the folder when you change AI vendors, stop using the service, or stop working with an implementer.

## What is materially different

1. **You own the working context.** It is Markdown and YAML you can open with an ordinary editor. No database or Personal AI OS account is required.
2. **The knowledge layer uses an open format.** `aios okf-check` checks it locally against Open Knowledge Format v0.2 and reports exactly what it inspected.
3. **Retrieval carries receipts.** The supported search/read workflow identifies the records used and says when the folder contains no answer.
4. **Raw material does not become trusted knowledge automatically.** New captures start as drafts. Sources remain unchanged, and imported conversations distinguish the human's words from the AI's.
5. **Changes leave evidence.** Consequential work is journaled. Risky supported workflows use checkpoints, exact review plans, validation, and rollback.
6. **Updates are reviewable.** The new release's launcher shows a read-only plan first. Applying it requires your confirmation and the exact review hash; conflicts and changed inputs cause refusal.
7. **The runtime is replaceable by design.** The release ships profiles for Claude Code and Codex. That is a portability design, not a claim that every AI has been certified.
8. **The product publishes scoped evidence.** The v1.64.5 release has target-bound machine evidence distributed with its GitHub release assets. Retained earlier evidence remains historical and does not qualify v1.64.5.

## The security boundary, plainly

In direct-file mode, privacy markings, protected paths, and the write switch are rules the runtime and supported commands obey. They are not an operating-system sandbox. A runtime with native file access can technically open anything its OS account can reach. Do not place secrets in the vault, and keep material you cannot expose outside that runtime's filesystem reach.

## Services

The core is free and open source under MIT. Optional services can cover guided setup, migration, and ongoing care. The current commercial terms remain: $500 guided install with the owner-approved 30-day guarantee; $250 migration audit credited toward an accepted migration; migration quoted after inspection; care from $50/month. These are service terms, not software-license fees, and should be confirmed in the current agreement before purchase.

**You own the folder. The AI is a guest.**

{contact} · {website or email}
