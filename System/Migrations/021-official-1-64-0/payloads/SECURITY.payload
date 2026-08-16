# Security Policy

## Reporting a vulnerability

Please report security issues **privately**, not in a public issue.

Use GitHub's [private vulnerability reporting](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) on this repository (Security → Report a vulnerability). If that is unavailable to you, open a public issue containing **no details** — just a request for a private channel — and you will be contacted.

Expect an acknowledgement within a week. This is a small project maintained by one person, so please size your expectations accordingly; there is no paid bounty.

## What is in scope

This system is a folder of Markdown, YAML, and a small deterministic Python utility layer (`System/Scripts/`). The interesting attack surface is narrow but real:

- **The Python utilities** — path traversal, unsafe YAML handling, or anything in `aios.py` and its subcommands that could read or write outside the vault it was pointed at. Pack installation (`aios pack`) handles third-party ZIPs and is the highest-value target here.
- **Add-on packs** — a pack is third-party content that a runtime is instructed to trust. Manifest-gate bypasses, or a pack that can escape `Packs/<name>/`, are in scope.
- **The governance rules themselves** — if the documented rules can be read to authorize something they should forbid (for example, a phrasing that lets an AI runtime write outside its permitted surface, or defeat the `ai_writes_enabled` kill switch), that is a legitimate report even though no code is involved. In a system whose security properties are partly written in prose, the prose is part of the attack surface.
- **Hostile-content instruction attacks** — notes, transcripts, imports, attachments, pack prose, issues, pull requests, or tool/web output that can make a supported runtime treat content as authority, bypass a gate, disclose protected material, or change the boot/rule chain are in scope. The canonical boundary is `System/Governance/Instruction Trust Boundaries.md`.

## What is out of scope

- Arbitrary behavior of an unsupported AI runtime. However, failure of a shipped runtime profile to honor its declared boundaries is in scope. Claude Code and Codex profiles ship at an uncertified L2 default; certification is earned and recorded per installation, not inferred from the presence of a profile. Compliance with the kill switch and change rules remains an obeyed convention—not a physical sandbox—for any runtime with direct file access.
- Anything requiring an attacker to already have write access to your vault or your machine.
- The truth, taste, or ordinary subject matter of content you intentionally store. Its ability to cross the instruction boundary is in scope even when you imported or installed it yourself.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.64.3 | Yes — current release |
| 1.64.2 and earlier | No |

Only the current release is supported; fixes are not backported. A version is
not considered supported merely because its number appears in a candidate
branch: the tagged release must also carry passing release-qualification
evidence.
