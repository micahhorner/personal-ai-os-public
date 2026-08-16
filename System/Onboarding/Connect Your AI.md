---
id: doc-connect-your-ai
type: system-doc
file_class: canonical
authority: canonical
canonical_for: connect-your-ai
created: 2026-07-14
updated: 2026-08-14
summary: "How to connect a shipped Claude Code or Codex profile to this OS folder, prove read and write access, and enter through the root operator rule chain before onboarding."
---

# Connect Your AI

Run `python3 System/Scripts/setup.py` from the OS root first. Then use this page to connect a supported AI runtime and prove it can both **read** and **write** the real folder. Once both proofs pass, the runtime must enter through the root operator rule chain before it starts onboarding.

## Which AI can operate your OS

Operating the OS (reading it *and* writing back to it) is an **agent** capability, not a chat-app capability.

| Runtime | Status in this release | Setup |
|---|---|---|
| **Claude Code** (Anthropic) | Shipped hosted, filesystem-capable profile; conservative uncertified L2 default | Install Claude Code, then open it with this folder as the working folder |
| **Codex** (OpenAI) | Shipped hosted, filesystem-capable profile; conservative uncertified L2 default | Open Codex with read/write access to this folder |
| **Cowork or another runtime** | No shipped profile or qualification evidence in this release | Treat as unprofiled and unverified until an adapter and evidence are added |
| **A plain chat session without filesystem tools** | Cannot operate the folder | It may reason about files you provide, but it cannot complete the write proof or run the OS |

"Shipped" does not mean universally certified. Both supplied profiles start at the conservative uncertified L2 default; certification is earned and recorded per installation.

## The four setup steps

1. **Run setup from this folder** — `python3 System/Scripts/setup.py` must complete successfully.
2. **Point your supported runtime at this folder** — the top folder of your OS (the one containing `AGENTS.md`, `SYSTEM-MANIFEST.yaml`, `System/`, `CONNECT-CHECK.md`, and the numbered folders).
3. **Run the connection check** (below) — don't assume it worked; prove it.
4. **Enter through the root operator chain** — ask it to read `AGENTS.md` and set the system up for you.

## Prove the connection (do not skip)

Two steps. Both must pass.

1. **Read proof.** Ask: *"read `CONNECT-CHECK.md` and tell me the token."* If it returns `AIOS-CONNECTED-4F9K`, it can see your real folder — not an uploaded copy, not a stale mirror.
2. **Write proof.** Ask: *"write a file called `System/Logs/connect-test.md` that says hello, then tell me."* Open your folder (or Obsidian) and confirm the file is really there. Then tell your AI to delete it.

- **Both pass** → you're connected as an operator. Say: *"Read `AGENTS.md` and set this system up for me."*
- **Only read passes** → this session is read-only. Fine for reading and drafting, but it cannot operate the OS; switch to a shipped, filesystem-capable runtime and try again.
- **Neither passes** → your AI is looking at an upload or a mirror, not your folder. Re-point it at the folder and try again.

*Why the write proof matters: the most common setup mistake is believing your AI is editing your vault when it's really reading a copy. The write step catches that before onboarding tries to make a change and fails confusingly.*

## What the operator entry chain does

`AGENTS.md` points the runtime to `SYSTEM-MANIFEST.yaml`. The manifest then requires the AI reading order: Runtime Kernel, Task Router, and the active runtime profile. The router selects the onboarding procedure and its dependencies. Claude's `CLAUDE.md` is a thin adapter pointer into this same chain; it does not replace `AGENTS.md` or the manifest.

---

*Runtime support is release-specific. A runtime that can technically access files is not automatically profiled, qualified, or supported by this product.*
