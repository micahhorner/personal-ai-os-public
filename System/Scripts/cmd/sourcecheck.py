"""Scope-honest repository/source verdict.

The implementation remains in :mod:`cmd.certify` for compatibility with code
that imports its seeded behavioral checks.  This public name states what those
checks actually prove.  Release qualification and live-runtime behavior are
deliberately outside this command.
"""
from __future__ import annotations

from lib.report import Report
from cmd import certify as source_impl


def run(root, args, rep: Report):
    return source_impl.run(root, args, rep)
