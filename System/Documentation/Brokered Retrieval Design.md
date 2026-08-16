---
id: doc-brokered-retrieval-design
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture, doc-privacy-and-boundaries]
x_reviewed_against: ["doc-canonical-architecture:2.22.0", "doc-privacy-and-boundaries:1.2.0"]
version: 0.1.2
created: 2026-08-02
updated: 2026-08-14
summary: "DESIGN ONLY / NOT IMPLEMENTED: the bounded deployment and API design required for mechanically filtered retrieval."
---

# Brokered Retrieval Design

> **DESIGN ONLY / NOT IMPLEMENTED.** The current Personal AI OS release does not ship a
> brokered runtime, launcher, sandbox, or mechanical privacy boundary. The
> design below is a separately approved follow-on, not a feature of the
> current release.

## Verdict

**FOLLOW-ON.** The existing `aios search` and `aios read` commands are useful
filtered-retrieval primitives, but a command cannot secure a model that can
also open the same files directly. Mechanical privacy therefore requires a
launcher or runtime integration outside the current CLI boundary, together
with an operating-system boundary that removes the model's native access to
the vault. Running a broker while leaving native file or shell access enabled
does not create brokered mode and must never be described as doing so.

Direct-file operation remains supported. Its privacy, kill-switch, protected-
object, and instruction-trust rules are compliance controls that a runtime is
required to obey; they are not confinement against that runtime.

## Security objective and non-objectives

The objective is narrow: a model receives only records that the privacy policy
allows for a declared runtime and task domain, and it cannot bypass that
decision by using another filesystem path or tool.

This design does not attempt to protect a compromised machine, an attacker who
already controls the broker account, content the user deliberately allowed the
model to read, or facts that allowed records themselves reveal. Filtering is
whole-record, not field-level. Prompt injection remains an instruction-trust
problem: broker output is untrusted content, never operating authority.

## Required topology

Three principals must be distinct:

1. **The owner** controls the vault and the policy.
2. **The trusted broker** can read the vault and evaluates retrieval requests.
3. **The model runtime** cannot read the vault and can communicate only with
   the broker's allowlisted interface.

The model process must not receive the vault as its working directory, a mount,
an inherited file descriptor, a native file tool, or an unrestricted shell.
It must also be unable to reach alternate copies through Git history,
snapshots, backups, generated indexes, editor caches, logs, attachments, or a
sync client. The broker's policy and runtime identity must be fixed by the
launcher or another owner-controlled location; the model may not select or
rewrite them.

On macOS or Linux, a viable deployment uses a separate OS account, a container,
or an equivalently reviewed sandbox. The vault is readable only to the owner
and broker. The model receives a separate scratch area for outputs. The IPC
endpoint exposes named operations rather than a general command runner. A
Windows design must establish the equivalent ACL, process, and mount boundary
before claiming the same property.

## Retrieval interface

The minimum broker surface is read-only:

- `search(query, task_domain, state_scope, project_scope)` returns a bounded
  list of permitted stable ids, paths, and summaries.
- `read(id, task_domain)` returns one permitted record through a structured
  envelope that marks its body and metadata as untrusted vault content.

The broker, not the model, supplies the runtime profile and validates the task
domain. Missing, malformed, or unrecognised policy values fail closed. A hidden
id and an absent id produce indistinguishable responses. Counts, paths,
relationship ids, aliases, and error details that would reveal an excluded
record are withheld. Relationship fields are filtered under the same rule as
record bodies because an id can reveal a person or claim.

The implementation must accept only regular files contained by the declared
vault roots after canonical path resolution. It refuses symbolic links,
special files, path traversal, and policy paths outside the trusted
configuration root. Requests are size- and result-bounded. Audit records state
which operation and policy identity were used without copying hidden content
or hidden-record counts into the log.

`aios search` and `aios read` may be hardened to supply this policy engine, but
the CLI alone does not satisfy the topology above. The broker must expose only
the approved operations; access to `python`, a shell, or arbitrary `aios`
subcommands would restore a bypass.

## Write interface

Brokered retrieval does not require model writes. If a later deployment allows
them, reads and writes use separate capabilities. A write request is data, not
an executable command, and names its target, expected pre-write hash, proposed
bytes or patch, and approval class.

The write broker must enforce the kill switch, allowed roots, regular-file and
symlink checks, expected-base matching, protected-object classification,
checkpointing, atomic replacement, validation, journaling, and exact rollback.
Protected writes require an owner-originated approval receipt bound to the
exact target and proposed effect. A model-generated `--confirm` value is not
proof of human approval. Direct-file mode may require the same mediated path as
operating procedure, but it can still bypass it physically until native write
access is removed.

## Launcher and runtime requirements

A qualifying launcher must:

- prove the model starts without vault read or write permission;
- bind the broker to one canonical vault root and immutable policy identity;
- inject hosted/local status and the task domain rather than accepting the
  model's self-description;
- allowlist broker RPCs and deny arbitrary process execution and raw paths;
- isolate scratch output from the vault until a separately authorized write;
- close inherited descriptors and prevent access to alternate vault copies;
- fail closed when any confinement or policy check cannot be established; and
- emit a deployment attestation that names the boundary actually tested.

Runtime certification evaluates behavior; it does not substitute for these OS
conditions. A compliant model with unrestricted file access is still
direct-file mode.

## Verification gate

No implementation may use the term **brokered mode** until an end-to-end test
proves all of the following from the model process:

- raw vault paths, Git objects, snapshots, backups, caches, and shells are
  inaccessible;
- every privacy-class, `ai_use`, domain, runtime-profile, and `Local Only/`
  combination returns the expected allow or deny result;
- missing and invalid policy values deny access;
- hidden and absent records are indistinguishable, including metadata and
  relationship references;
- symlink, traversal, alternate-root, race, and malformed-file probes fail
  closed;
- untrusted note, source, Inbox, pack, and pull-request text cannot become boot
  authority or grant itself a tool; and
- any enabled write API stays inside declared roots and proves checkpoint,
  approval, validation, journal, and rollback behavior under injected faults.

Evidence must name the OS, launcher version, runtime version, policy identity,
test corpus, and exact result. Passing CLI unit tests without the confinement
test is evidence for filtered commands only, not brokered privacy.

## Residual risks

The broker can still disclose allowed content to the selected model provider.
Allowed content can contain sensitive facts, malicious instructions, or links
to external systems. Whole-record metadata can be incomplete or wrong. The
owner and broker account remain trusted, and backups outside the broker remain
the owner's responsibility. Traffic analysis, model-provider retention, and a
compromised host are outside this boundary unless a later deployment states
and proves otherwise.

Until the follow-on is implemented and qualified, the accurate product claim
is: **the CLI filters retrieval deterministically when it is the only content
transport; direct-file runtimes follow the same policy by compliance, without
mechanical isolation.**
