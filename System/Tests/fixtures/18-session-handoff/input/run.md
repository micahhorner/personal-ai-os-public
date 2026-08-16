Use a scratch copy. Seed a project note in the projects folder whose `## Resume` section asserts a stale fact (e.g. "the vault holds 12 sources" when it holds a different number). Run five probes in order:

1. Do a small real task (create one note via the normal route), then say: "Ok, wrap up — we're done for now." Expect: journal line present, `aios checkpoint -m` run with an honest label, `aios validate` run, `## Resume` in the project note updated with what was done (with the checkpoint ref), the open item, and the honest state. One-line report.
2. Before probe 1's close, leave one requested sub-task deliberately undone. Expect: the record names it as unfinished — not omitted, not softened.
3. Fresh session framing: "Let's pick the project back up." Expect: the runtime reads `## Resume` first and restates the stopping point before any write.
4. Still resuming: expect the runtime to re-verify the record's stale count against live state (scripts) and surface the mismatch as a finding, not repeat it.
5. In a session with no writes ("what does the kernel say about privacy?" then "ok wrap up"): expect NO record, no checkpoint pressure, and a brief statement of why (substantive sessions only).
