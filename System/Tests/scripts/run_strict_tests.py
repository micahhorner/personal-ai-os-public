#!/usr/bin/env python3
"""Run unittest discovery while making warnings, unraisables, and skips fatal.

CPython reports exceptions raised while finalizing an object through
``sys.unraisablehook``.  In Python 3.9, turning ``ResourceWarning`` into an
error can therefore print ``Exception ignored in:`` while unittest still exits
zero.  This outer-process gate inspects the complete child output instead of
trusting its exit status alone.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys


SKIP_RE = re.compile(
    r"(?m)^(?P<method>\S+) \((?P<owner>[^)]+)\)"
    r"(?:\n(?!\S+ \([^)]+\)).*)*? \.\.\. skipped "
)
SKIP_TOTAL_RE = re.compile(r"(?:OK|FAILED) \([^)]*skipped=(?P<count>[0-9]+)[^)]*\)")


def _arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="Strict unittest discovery with independently enforced diagnostics."
    )
    parser.add_argument("--start-directory", "-s", default="System/Tests/scripts")
    parser.add_argument("--pattern", "-p", default="test_*.py")
    parser.add_argument("--top-level-directory", "-t")
    parser.add_argument(
        "--allow-skip", action="append", default=[], metavar="TEST_ID",
        help="exact unittest id permitted to skip; repeat for multiple ids",
    )
    parser.add_argument(
        "--allow-skip-prefix", action="append", default=[], metavar="TEST_PREFIX",
        help=("exact unittest module/class prefix permitted to skip; intended for "
              "an explicitly separated qualification scope"),
    )
    return parser.parse_args(argv)


def _test_command(args):
    command = [
        sys.executable, "-W", "always::ResourceWarning", "-m", "unittest",
        "discover", "-s", args.start_directory, "-p", args.pattern, "-v",
    ]
    if args.top_level_directory:
        command.extend(["-t", args.top_level_directory])
    return command


def _tee(command):
    """Return ``(status, complete combined output)`` without hiding a byte."""
    environment = os.environ.copy()
    # Descendant Python processes inherit this too.  ``always`` keeps destructor
    # warnings printable; unlike ``error``, it does not turn them into a
    # zero-status unraisable before this outer process can see them.
    environment["PYTHONWARNINGS"] = "always::ResourceWarning"
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment
    )
    captured = bytearray()
    assert process.stdout is not None
    while True:
        chunk = process.stdout.read(64 * 1024)
        if not chunk:
            break
        captured.extend(chunk)
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
    return process.wait(), bytes(captured)


def _skipped_ids(text):
    skipped = set()
    for match in SKIP_RE.finditer(text):
        method = match.group("method")
        owner = match.group("owner")
        # Newer unittest renderings may put the complete test id inside the
        # parentheses (``method (module.Class.method)``).  Older renderings put
        # only the owner there.  Accept both without ever broadening matching:
        # the result remains one exact unittest id.
        skipped.add(owner if owner.endswith("." + method) else f"{owner}.{method}")
    return skipped


def main(argv=None):
    args = _arguments(argv)
    status, raw = _tee(_test_command(args))
    text = raw.decode("utf-8", errors="replace")

    violations = []
    warning_count = text.count("ResourceWarning:")
    if warning_count:
        violations.append(f"{warning_count} ResourceWarning diagnostic(s)")

    unraisable_count = text.count("Exception ignored in:")
    if unraisable_count:
        violations.append(f"{unraisable_count} unraisable exception diagnostic(s)")

    skipped = _skipped_ids(text)
    totals = [int(match.group("count")) for match in SKIP_TOTAL_RE.finditer(text)]
    reported_skips = totals[-1] if totals else 0
    if reported_skips != len(skipped):
        violations.append(
            f"unidentified skip diagnostics: unittest reported {reported_skips}, "
            f"gate parsed {len(skipped)}"
        )
    allowed_exact = set(args.allow_skip)
    allowed_prefixes = tuple(prefix + "." for prefix in args.allow_skip_prefix)
    unexpected = sorted(
        test_id for test_id in skipped
        if test_id not in allowed_exact
        and not test_id.startswith(allowed_prefixes)
    )
    if unexpected:
        violations.append("unexpected skip(s): " + ", ".join(unexpected))

    if status or violations:
        details = "; ".join(violations) if violations else "unittest failure"
        print(f"\nSTRICT TEST GATE: FAIL — {details}", file=sys.stderr)
        return status or 1

    print("\nSTRICT TEST GATE: PASS — no resource warnings, unraisables, or unexpected skips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
