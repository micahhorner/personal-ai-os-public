"""vault.doc-commands — the command-documentation coverage gate.

Fails if any user-facing `aios` subcommand exists in the CLI but is not
documented anywhere in the product docs. This makes "is every command
documented?" a checkable fact instead of a hope — the sibling of `doc-check`
(which covers components) for the command surface. A new command can no longer
ship undocumented and slip by unnoticed.

Source of truth for the command list is the argparse `choices` in `aios.py`,
read straight from source (AST) so the list can never drift from what the CLI
actually accepts. "Documented" = the command appears in a Markdown doc under
System/Documentation/ or System/Onboarding/, either as an `aios <cmd>`
invocation or backtick-wrapped in a command list. Read-only; writes nothing.
"""
from __future__ import annotations
import ast
import glob
import os
import re

from lib.report import Report

# The documented surface: docs a human/AI is expected to consult. Diagrams
# (SVGs) do NOT count — a command named only in a picture is not documented.
DOC_DIRS = [
    os.path.join("System", "Documentation"),
    os.path.join("System", "Onboarding"),
]

# Commands deliberately kept out of user docs, each with a reason. Empty today;
# an explicit allowlist keeps the gate honest instead of silently skipping.
INTENTIONALLY_UNDOCUMENTED: dict[str, str] = {}


def cli_commands(root):
    """The user-facing command names, read from aios.py's argparse `choices`.
    AST-parsed so a multi-line choices=[...] is read exactly as written — the
    list is whatever the CLI actually accepts, never a hand-kept copy."""
    src = os.path.join(root, "System", "Scripts", "aios.py")
    with open(src, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "choices" and isinstance(kw.value, ast.List):
                    vals = [e.value for e in kw.value.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                    if vals:                      # first add_argument with choices = the command positional
                        return vals
    return []


def doc_text(root):
    """Concatenated text of every Markdown doc in the documented surface."""
    chunks = []
    for d in DOC_DIRS:
        for f in glob.glob(os.path.join(root, d, "**", "*.md"), recursive=True):
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    chunks.append(fh.read())
            except OSError:
                pass
    return "\n".join(chunks)


def is_documented(cmd, text):
    """True if `cmd` appears in command context: an `aios <cmd>` / `aios.py <cmd>`
    invocation, or backtick-wrapped (`cmd` or `cmd -m "x"`). \\b-anchored so short
    names (read, search) never match inside ordinary prose words."""
    c = re.escape(cmd)
    invocation = re.compile(r"aios(?:\.py)?\s+" + c + r"\b")
    backticked = re.compile(r"`" + c + r"\b")
    return bool(invocation.search(text) or backticked.search(text))


def run(root, args, rep: Report):
    # No CLI in this vault (e.g. a minimal test scaffold) — nothing to document, skip.
    if not os.path.exists(os.path.join(root, "System", "Scripts", "aios.py")):
        rep.info["commands_checked"] = "skipped (no System/Scripts/aios.py)"
        return rep
    commands = cli_commands(root)
    if not commands:
        rep.error("aios.py present but its command list could not be read — cannot verify command documentation")
        return rep
    text = doc_text(root)
    documented, undocumented = [], []
    for cmd in commands:
        if cmd in INTENTIONALLY_UNDOCUMENTED:
            continue
        if is_documented(cmd, text):
            documented.append(cmd)
        else:
            undocumented.append(cmd)
            rep.error(f"UNDOCUMENTED command: `aios {cmd}` exists in the CLI but is not documented "
                      f"in {' or '.join(DOC_DIRS)} — add it to a command reference")
    rep.info["commands_total"] = len(commands)
    rep.info["commands_documented"] = len(documented)
    rep.info["commands_undocumented"] = len(undocumented)
    return rep
