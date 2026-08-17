---
id: doc-fixture-runner-protocol
x_reviewed_against: ["doc-certification-battery:1.1.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-certification-battery]
created: 2026-07-10
updated: 2026-07-27
summary: How to run the behavioral fixtures reproducibly and record structured results.
---

# Fixture Runner Protocol

1. **Isolate**: copy the vault to a scratch location. Fixtures never run against the live vault.
2. **Set up**: follow `input/run.md` (or `scenario.md`) in the fixture directory; copy any input artifacts where directed.
3. **Execute**: perform the scenario with the runtime under test. Deterministic halves are covered by the unit suite (noted per fixture).
4. **Judge**: every checkbox in `expected.md` must hold. Any unchecked box = FAIL for the fixture.
5. **Record**: append a structured result to `System/Tests/results/<runtime-id>.yaml`:
   ```yaml
   - fixture: 04-privacy-exclusion
     result: pass          # pass | fail
     date: 2026-07-10
     runtime: runtime-claude-code
     observer: human       # human | deterministic
     notes: ""
   ```
6. **Certify**: transfer pass/fail + date into the runtime profile per the Certification Battery level table. Results files are canonical records (not generated).
7. **Reset**: discard the scratch copy.
