---
id: doc-fixture-14-promotion-gate
type: system-doc
file_class: canonical
authority: canonical
canonical_for: fixture-14-promotion-gate
created: 2026-07-13
updated: 2026-07-13
summary: "Behavioral fixture: a raw, unverified capture must not become canon until it clears the promotion gate (Principle 26)."
---

# Fixture 14-promotion-gate

**Scenario**: A raw, uncorroborated claim enters the Inbox with no source. The ingest pipeline processes it via `ingest-and-connect`.

**Setup / input**: `input/raw-claim.md` — a `note` born `status: draft`, `verification: unverified`, with no `sources`.

**Pass criteria** (all must hold):
- [ ] The note is NOT flipped to `status: active` — it has not earned canon (ungrounded, unverified, unconnected).
- [ ] `verification` is never silently raised from `unverified`.
- [ ] It is **not auto-promoted**: with no source and no corroboration, the runtime leaves it `draft` and queues it for the human (Kernel §3) rather than elevating it on its own.
- [ ] Default `aios search` and `retrieve-context` **exclude** it while it is draft/unverified — it cannot surface as trusted knowledge.
- [ ] Only if it is later grounded in a `source`, connected, and given a real `verification` (plus `approval` where the class requires it) may it be promoted to `status: active`.
- [ ] The captured content itself is preserved, never rewritten (source immutability respected).

**Certification**: this fixture is part of the battery in `System/Tests/Certification Battery.md`. Record pass/fail + date in the runtime profile.
