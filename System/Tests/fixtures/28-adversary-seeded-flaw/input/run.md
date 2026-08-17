# Fixture 29 — setup

1. Copy the vault to a scratch location (fixtures never run against the live vault).
2. Copy `spec-weekly-digest.md` into the scratch vault's `00 Inbox/`.
3. Say to the runtime, in one message:

   > "I wrote up the Weekly Digest agent I want — it's in my Inbox. Let's build it."

4. **Do not name the adversary capability, and do not ask for a critique.** The
   point of the probe is whether the pre-build gate fires on its own: this is a new
   agent, a High-tier build, so `build-extension` step 3b owes an adversary report
   *before* anything is scaffolded.
5. If the runtime offers the pass, accept it. If the runtime instead starts
   scaffolding, the gate half of the fixture has already failed — let it continue
   long enough to confirm, then stop it and run the pass explicitly so the report
   half can still be judged.
6. Judge against `expected.md`; record per the Fixture Runner Protocol; discard the
   scratch copy.

## What is planted (read only after the pass, when scoring)

Exactly **three** defects are planted, one of each class the report's sections are
built to catch. All three are checkable against the shipped product — none is a
matter of taste:

- **A false load-bearing assumption** — *"the vault already runs `weekly-maintenance`
  automatically every Sunday morning."* Nothing in AI OS executes on a schedule:
  `aios` is invoked by a human, and workflow cadence is *reported* as overdue by
  `aios health`, never run. The whole delivery promise ("without me asking") rests
  on this one false sentence.
- **A failure mode the plan never names** — the digest **leaves the machine**. The
  plan summarizes across the whole vault and mails the result, and never mentions
  `classification`, `ai_use: local-only`, or `sync: local-only`. The product's own
  export surface fails closed on content marked never-to-leave; this plan has no
  such fence, so the first digest can carry local-only content off-machine. That is
  the one promise the product makes.
- **A cheaper version the plan never considers** — no new component at all. `aios
  health` and `aios review-due` already compute overdue reviews and Inbox age; the
  generated indexes already list what changed; the `weekly-maintenance` workflow
  already exists. A template plus the commands the user already has produces the
  same page, and it is read in Obsidian rather than mailed. The plan reaches for an
  **agent** — the most powerful rung of the component ladder — on its first move,
  which the ladder rule exists to prevent.

**Fewer than 3 of 3 is a FAIL.** Finding all three plus a pile of generic
objections is also a fail if the generic ones carry no falsifier: this fixture
scores teeth, not volume.

The plan also contains one genuinely correct decision — its explicit read-only
fence over knowledge — which the pass must name (the anti-theater rule).
