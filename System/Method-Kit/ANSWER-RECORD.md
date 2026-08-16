---
id: doc-method-kit-answer-record
type: system-doc
file_class: canonical
authority: derived
x_reviewed_against: ["doc-method-kit-interview:0.2.0", "doc-method-kit-dials:0.1.0"]
derived_from: [doc-method-kit-interview, doc-method-kit-dials]
canonical_for: method-kit-answer-record-format
version: 0.2.0
status: active
created: 2026-07-11
updated: 2026-07-11
summary: "The required format for an interview's answer record — what the generator consumes. Fixes F-1; stakes field fixes F-3."
---

# Answer record — required format (fills during the interview, per section)

```markdown
# Answer record — <subject>, <YYYY-MM-DD>

**Subject:** <who, context from §1>. **Interviewer:** <runtime/model>. **Probes consented:** yes/no/partial.

## §1..§7 (one block per section)
- Key quotes, each graded [E1|E2|E3|E4]
- Inferred dial settings, marked *inferred* until §8
- Contradictions observed (claim vs. story vs. probe)
- Fits-no-dial personal rules

## Stakes note (from §3's expensive-mistake question)
<LOW | MEDIUM | HIGH per zone of their work, and who besides them gets hurt.>
The generator uses this to lean ambiguous dials: HIGH stakes → lean conservative; LOW → lean light.

## §8 Readback
- Corrected: <dial: old → new>
- Confirmed: <dials>
- Defaulted (weak signal → revisit list): <dials>
- Contradictions surfaced & how received
- Consent to generate: yes/no · Pack name: <name>
```

Rules: quotes stay verbatim (they become the pack's citations); every one of the 11 dials appears exactly once across *inferred/corrected/confirmed/defaulted*; the stakes note is mandatory even when it's "LOW everywhere."
