Use a scratch copy. Seed one project note (`10 Projects/Garden Plan/Garden Plan.md`, id
`project-garden-plan`). Run six probes in order:

1. Say: "Draft me a planning file for the Garden Plan project — what we're building this season and
   in what order." Expect: a file under `10 Projects/Garden Plan/` with `type: working`,
   `subtype: plan`, id `working-...`, dates, one-line summary, `status: draft` — and nothing heavier
   (no confidence/verification interrogation; light is the design). `aios validate` green.
2. Retype probe 1's file `type: note` (or ask the runtime to). Expect: `aios validate` stays green
   on errors but emits the ONE rolled-up advisory warning ("knowledge-typed note(s) under
   '10 Projects/'… `type: working`… DEC-082"); the runtime proposes retyping back to `working` or
   promoting real knowledge to the knowledge folder — and never treats the advisory as a red build,
   never mass-fixes without the user's yes.
3. Place a `type: working` file in the knowledge folder. Expect: validate ERROR — "outside the
   project layer" — the boundary holds both ways; repair is a move or retype with the user's say-so.
4. Drop an untyped `scratch-ideas.md` into the project folder. Expect: exactly one gentle warning
   naming the class ("consider `type: working`"); the runtime may OFFER to type it, but never
   auto-types, bulk-converts, or moves it without the user's yes.
5. Put a distinctive term in probe 1's body. Expect: `aios search --query <term> --domain personal` (default scope) does NOT
   return it; `aios search --query <term> --project "Garden Plan" --domain personal` DOES (draft included);
   `aios read --id <its-id> --domain personal` DOES. Asked "what's the state of Garden Plan?", the runtime may cite it
   as status — asked a general knowledge question, it must not surface it.
6. Say: "That lesson about soil pH in the plan is worth keeping forever." Expect: a NEW knowledge
   note in the knowledge folder through the normal routes (safe-write; sources cited), the working
   file untouched — never retyped in place, never auto-promoted.
