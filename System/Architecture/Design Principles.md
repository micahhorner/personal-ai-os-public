---
id: doc-design-principles
type: system-doc
file_class: canonical
authority: canonical
canonical_for: design-principles
version: 1.0.2
created: 2026-07-10
updated: 2026-07-13
summary: The design principles of this system — 25 adopted verbatim from the project source at architecture freeze, plus Principle 26 (context is staging; knowledge is canon) added by amendment 1.0.2 (principle 15 wording aligned "skills" → "capabilities" per DEC-024; see amendment notes).
---

# Design Principles


These principles should become enforceable architectural rules.

1. **The user owns the durable core.**
2. **The model is replaceable.**
3. **The interface is replaceable.**
4. **Canonical state is portable, human-readable, and versioned.**
5. **Derived state is disposable and rebuildable.**
6. **Store truth once; present it many ways.**
7. **Search before creating.**
8. **Preserve sources, uncertainty, and history.**
9. **Separate evidence, interpretation, decision, and output.**
10. **Use the smallest structure that supports the real requirement.**
11. **Do not prebuild specialized complexity.**
12. **Every write receives proportional preflight.**
13. **Every consequential change is reversible or explicitly approved.**
14. **Deterministic work belongs in scripts.**
15. **Judgment-heavy repeatable work belongs in capabilities.**
16. **Specialist responsibilities and permissions may justify agents.**
17. **Vendor-specific behavior belongs in adapters.**
18. **Essential meaning must not depend on Obsidian plugins.**
19. **A weaker model should still be able to locate and follow the rules.**
20. **Humans must be able to inspect, edit, export, and recover the system without AI.**
21. **Onboarding and documentation are executable parts of the system.**
22. **The system grows from actual use and tested extensions.**
23. **No invisible maintenance.**
24. **No silent architectural drift.**
25. **Future change is handled through versioned migration, not wishful permanence.**
26. **Context is staging; knowledge is canon — raw capture earns its way into the trusted core through a quality gate, never by accumulation.**

---

*Amendment 1.0.1 (2026-07-11): principle 15 wording aligned "skills" → "capabilities" — the rename ratified in DEC-024. No change in meaning; the principle predates the skills→capabilities consolidation. Historical mentions of "skills" elsewhere (e.g., the architecture spec's account of consolidating the original eleven skills) are accurate history and remain unchanged.*

*Amendment 1.0.2 (2026-07-13): added Principle 26 (context is staging; knowledge is canon), naming the doctrine the schema, the ingest pipeline, and retrieval already implement — raw context must earn promotion into the trusted core through a quality gate; the vault's worth is the trustworthiness of its canon, not the volume of its context. Ratified in DEC-058; see §17 (Knowledge-compounding model) of the Canonical Architecture Specification. "Canonical" here names the trusted tier of a record — for knowledge, `status: active` + a real `verification`; distinct from `file_class: canonical`, which marks trusted infrastructure (components, system docs).*
