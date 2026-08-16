# Claude — operating instructions for this vault

You are operating a human-owned Personal AI OS. This file is the **Claude adapter pointer** — it tells you where the rules are. It does not contain the rules; never treat it as a substitute for them.

## Before any work

1. Read `SYSTEM-MANIFEST.yaml`, then its `reading_order.ai`: the **Runtime Kernel** (your complete standing law), the **Task Router** (what to load per task), and your runtime profile. Load nothing else unless the router names it.
2. Confirm `runtime.ai_writes_enabled: true`. If false: read-only, no exceptions.
3. Your capabilities and autonomy level: the file named by `runtime.active_profile` in the manifest. Operate at or below it.

## Non-negotiables (details in the canonical docs)

- **Preflight every write** — `System/Governance/Change Control and Preflight.md`. Search before creating. Smallest valid change. Validate after.
- **Privacy filters before content reaches you or leaves this machine** — `System/Governance/Privacy and Boundaries.md`.
- **Protected objects are off-limits** — listed in the manifest. That includes this system's governance, schemas, agent contracts, and the user's privacy rules.
- **Sources are immutable. Inference is labeled. Contradictions are preserved.**
- **Use the scripts** for deterministic work; **follow the capabilities** (`System/Capabilities/`, and any installed add-on under `Packs/`) for procedures — don't improvise parallel ones.
- **Escalate when uncertain.** Asking the human is a correct outcome.

## Commands

```bash
python3 System/Scripts/aios.py validate      # after every write session
python3 System/Scripts/aios.py links         # after anything touching references
python3 System/Scripts/aios.py checkpoint -m "label"   # before risky work
python3 System/Scripts/aios.py health        # weekly / on request
python3 System/Scripts/aios.py generate      # rebuild all generated state
```

## Operation mapping

How the 15 vault operations map onto your native abilities: `System/Adapters/Claude/operation-mapping.yaml`. The contract in `System/Operations/operations.yaml` is canonical; your file tools are just the current transport.

## Working style

Journal medium+ changes (`System/Journal/change-journal.md`). Report what changed, what was checked, what was flagged. When acting as the Onboarding Guide, Steward, or Extension Builder, load that agent's `AGENT.md` and stay inside its contract.
