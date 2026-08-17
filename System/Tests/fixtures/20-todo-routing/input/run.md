Use a scratch copy. Seed `To-Do.md` with one extra item whose path is dead (e.g. `path: 20 Knowledge/Does Not Exist.md`). Run five probes in order:

1. Say: "Add to my to-do list: review the Backup and Recovery Options doc before Friday — the drive-rotation decision is blocked until I pick an option; the doc is System/Documentation/Backup and Recovery Options.md." Expect: routed to `manage-todo` (not a freestyle edit), one new item under `## Items` carrying all four parts (what · why · blocks · path), **no clarifying question** (everything was inferable), `updated:` bumped, `aios validate` run.
2. Say: "Add to my list: fix the thing." Expect: **exactly one** clarifying question — not a bare write, and not a part-by-part interrogation. After the answer, a complete four-part item is written.
3. Observe probe 1 or 2's load: expect the seeded dead path flagged **in place** (`⚠ path does not resolve:` prefix) and reported to the user — not silently kept, not silently deleted.
4. Say: "Mark the review item done." Expect: the item moved to `## Done` with today's date (not deleted), validate green.
5. Say: "Make 'fix the thing' my top priority." Expect: reorder under `## Items` only — item content untouched.
