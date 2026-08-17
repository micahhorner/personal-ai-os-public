"""vault.doc-paths — the prose path-reference gate.

Documentation references vault files in backticks (`System/Capabilities/…`)
— the house style — and precisely that reference class is invisible to every
other gate: `links` strips code spans by design (backticks mean "literal
text"), and external markdown link checkers do the same. Found live the day
v1.22.0 merged: a Migrations README pointer at a renamed capability path
sailed through a fully green CI run. This gate asks the fourth documentation
question — sibling of `doc-check` (every component drawn?), `doc-commands`
(every command documented?), and `doc-audit` (every number true?):
**does every path in prose still resolve?**

The design constraint is noise, not detection (the DEC-032 lesson: a gate
that cries wolf gets retired). So only paths under always-committed System/
roots are checked — reserved directories per Vault Profile §9, never
renameable, so literal prefixes are correct here (DEC-067 folder indirection
covers the *renameable* content folders, which this gate deliberately does
not police: user content may say anything). Skipped entirely:

- runtime-born state (`System/Generated/`, `System/Logs/`) and the
  install-optional `Packs/` — absent by design on a fresh clone;
- placeholder patterns (`NNN-…`, `<name>`, globs) — documentation of shapes,
  not pointers to files;
- historical records (docaudit's own HIST tuple) — dated evidence is never
  rewritten to match now (constitution §4.8).

The decision register is NOT one of them, since v1.54.0 (DEC-109, closing audit
GAP-8). It used to be exempt wholesale, which is a category error `doc-audit`
had already avoided on the same file: §4.8 protects a *dated statement of fact*
— "two new capabilities", "129 messages" — because it was true when written. A
**path** is not that kind of claim. It is a pointer, it is followed by whoever
reads the entry, and when it dies the entry stops being navigable no matter what
year it was written in. So `doc-audit` exempts the register from COUNT claims
only and still checks behaviour; this gate now matches that shape exactly and
checks its paths. The blanket exemption had been hiding a real one:
`System/Capabilities/manage-packs.md`, dead since capabilities became folders at
DEC-070, in the entry that introduced the capability.

One narrow allowance comes with it, because otherwise the gate would be wrong in
the other direction: an entry recording that a file was REMOVED necessarily names
a file that no longer exists, and calling that "stale — file moved/renamed?" is a
false positive about the one document whose job is to record the removal. A path
is skipped when the sentence containing it says it was removed. Scoped to the
sentence, never the line: a register entry is one 900-word line, and a
line-scoped window would exempt every path in it. The count of what this
allowance skipped is REPORTED (`paths_exempt_as_removed`) rather than silently
dropped — an exemption nobody can see is an exemption nobody audits.

Read-only; composed into `health`, so CI guards every merge.
Proven before building: on the pre-fix v1.22.0 tree this flags exactly the
one real dead path and nothing else (168 references checked, 0 noise).
"""
from __future__ import annotations
import os, re
from lib.frontmatter import iter_markdown
from lib.report import Report

_STRICT = True   # set per-run from instance_role; strict by default (test scaffolds, master)

def _sev(rep):
    return rep.error if _STRICT else rep.warn

def _master(root):
    """Doc gates police the PRODUCT; on an instance they advise (DEC-083).
    A customized instance legitimately diverges from the product's own docs —
    instance-added components, deleted optional docs, extended counts — and a
    gate that reddens that divergence forever punishes sanctioned customization
    (found live: first v1.30.1 instance upgrade, 29 residual errors, all this
    class). Master = error; instance = warning. Same scoping doctrine as
    DEC-082."""
    import yaml as _y, os as _o
    try:
        with open(_o.path.join(root, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as stream:
            man = _y.safe_load(stream) or {}
    except Exception:
        return True   # no manifest = test scaffold/product context: stay strict
    return str(((man.get("system") or {}).get("instance_role") or "generic-master")).strip() == "generic-master"


# Reserved, always-committed roots (Vault Profile §9): a dead path here is a
# real documentation bug, not a runtime/install condition.
CHECKED_ROOTS = (
    "System/Adapters/", "System/Agents/", "System/Architecture/",
    "System/Capabilities/", "System/Documentation/", "System/Governance/",
    "System/Onboarding/", "System/Operations/", "System/Registries/",
    "System/Runtime/", "System/Schemas/", "System/Scripts/",
    "System/Templates/", "System/Tests/", "System/Workflows/",
)

# A token containing any of these is a placeholder/pattern, not a path.
PLACEHOLDER = ("<", ">", "{", "}", "*", "?", "NNN", "|")

SPAN = re.compile(r"`([^`\n]+)`")

# Dated evidence and test assets. Deliberately NOT docaudit's HIST verbatim:
# that tuple exempts the whole Migrations/ tree, but Migrations/README.md is a
# live doc — the very file whose stale path motivated this gate. Only the
# numbered migration record dirs (NNN-…) are historical; the README is not.
# (Found by the planted-bug probe during this gate's own build.)
# `Active Decisions.md` is deliberately absent (DEC-109 / GAP-8): see the module
# docstring. Count claims in it are exempt — that is `doc-audit`'s HIST_COUNTS,
# and it stays — but its paths are checked like anyone else's.
HIST_FILES = ("CHANGELOG.md", "change-journal.md")
HIST_DIRS = (os.sep + "results" + os.sep, os.sep + "fixtures" + os.sep)
MIGRATION_RECORD = re.compile(r"(^|/)System/Migrations/\d")


def _exempt_file(relpath: str) -> bool:
    rel = relpath.replace(os.sep, "/")
    if any(rel.endswith(h) for h in HIST_FILES):
        return True
    if any(d in relpath.replace("/", os.sep) for d in HIST_DIRS):
        return True
    return bool(MIGRATION_RECORD.search(rel))


# "…is removed from the product master", "was retired at DEC-070", "has been
# deleted". Present tense included ("is removed") because that is how the
# register actually writes it. Deliberately NOT "formerly" or "old", which
# attach to properties of a file that still exists.
_REMOVED = re.compile(
    r"\b(?:is|was|were|are|has been|have been|been)\s+(?:now\s+|since\s+)?"
    r"(?:removed|retired|deleted|dropped|withdrawn)\b"
    r"|\bno longer (?:exists|ships|present|shipped|in the (?:product|tree))\b"
    r"|\bremoved from the (?:product|tree|master)\b", re.I)

# Sentence boundaries as this corpus writes them: a period/question/exclamation
# followed by whitespace and a capital or a backtick. Bare "." is not enough —
# `v1.22.0`, `§4.8` and `manage-packs.md` are all full of them.
_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`*_(\[])")


def _removal_context(text: str, pos: int) -> bool:
    """Does the SENTENCE containing offset `pos` declare the file removed?"""
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    line = text[line_start:line_end if line_end != -1 else len(text)]
    off = pos - line_start
    start = 0
    for m in _SENT_END.finditer(line):
        if m.end() > off:
            break
        start = m.end()
    end = len(line)
    for m in _SENT_END.finditer(line):
        if m.start() > off:
            end = m.start()
            break
    return bool(_REMOVED.search(line[start:end]))


def _checkable(token: str) -> bool:
    t = token.strip()
    if not t.startswith(CHECKED_ROOTS):
        return False
    return not any(c in t for c in PLACEHOLDER)


def run(root, args, rep: Report):
    global _STRICT
    _STRICT = _master(root)
    checked = 0
    exempt_removed = 0
    for n in iter_markdown(root):
        if n.error or _exempt_file(n.relpath):
            continue
        try:
            with open(os.path.join(root, n.relpath), encoding="utf-8") as stream:
                text = stream.read()
        except OSError:
            continue
        seen = set()
        for m in SPAN.finditer(text):
            t = m.group(1).strip()
            if not _checkable(t) or t in seen:
                continue
            seen.add(t)
            checked += 1
            if os.path.exists(os.path.join(root, t.rstrip("/"))):
                continue
            if _removal_context(text, m.start()):
                exempt_removed += 1
                continue
            _sev(rep)(f"{n.relpath}: references `{t}` which does not exist — "
                      f"the doc is stale (file moved/renamed?) or the path is a typo")
    rep.info["path_references_checked"] = checked
    if exempt_removed:
        rep.info["paths_exempt_as_removed"] = (
            f"{exempt_removed} dead path(s) skipped — the sentence naming each one "
            f"records that the file was removed")
    return rep
