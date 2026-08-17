#!/usr/bin/env python3
"""Safely upgrade an existing vault using this release's upgrade engine."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


class LauncherError(RuntimeError):
    pass


def _contained(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
    except ValueError:
        return False
    return True


def _validated_roots(release_arg: Path, installed_arg: str) -> tuple[Path, Path]:
    supplied = Path(installed_arg).expanduser()
    if not supplied.is_absolute():
        raise LauncherError("--installed must be an absolute path")
    release = release_arg.resolve()
    installed = supplied.resolve()
    if not (release / "SYSTEM-MANIFEST.yaml").is_file():
        raise LauncherError("this launcher is not inside a complete Personal AI OS release")
    if not (release / "System" / "Scripts" / "aios.py").is_file():
        raise LauncherError("this release is missing System/Scripts/aios.py")
    if not installed.is_dir() or not (installed / "SYSTEM-MANIFEST.yaml").is_file():
        raise LauncherError("--installed must name an existing Personal AI OS vault")
    if release == installed:
        raise LauncherError("the release and installed vault must be different folders")
    if _contained(release, installed) or _contained(installed, release):
        raise LauncherError("the release and installed vault must not contain one another")
    return release, installed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Review or apply an upgrade using this new release's code, never the "
            "older installed vault's upgrade command."
        )
    )
    parser.add_argument("--installed", required=True,
                        help="absolute path to the existing vault being upgraded")
    parser.add_argument("--authorize-official-legacy-core", action="store_true",
                        help=("authorize an exact frozen official Personal AI OS "
                              "identity from 1.43-1.64; rivals still refuse"))
    parser.add_argument("--apply", action="store_true",
                        help="apply the exact plan (review-only when omitted)")
    parser.add_argument("--confirm", action="store_true",
                        help="confirm apply; does nothing without --apply")
    parser.add_argument("--review-sha256",
                        help="exact review hash printed by the preceding review")
    parser.add_argument("--accept", action="append", default=[], metavar="PATH",
                        help="reviewed protected conflict to keep; repeatable")
    parser.add_argument("--base",
                        help="old release tree or baseline JSON for classification")
    return parser


def build_command(argv: list[str] | None = None,
                  *, release_root: Path | None = None) -> list[str]:
    args = _parser().parse_args(argv)
    release, installed = _validated_roots(
        release_root or Path(__file__).resolve().parent, args.installed)
    if args.apply and (not args.confirm or not args.review_sha256):
        raise LauncherError(
            "--apply requires both --confirm and --review-sha256 from a fresh review")
    if not args.apply and (args.confirm or args.review_sha256):
        raise LauncherError("--confirm and --review-sha256 are valid only with --apply")

    command = [
        sys.executable,
        str(release / "System" / "Scripts" / "aios.py"),
        "upgrade",
        str(release),
        "--root",
        str(installed),
    ]
    if args.authorize_official_legacy_core:
        command.append("--authorize-legacy-core")
    if args.base:
        command.extend(["--base", args.base])
    for accepted in args.accept:
        command.extend(["--accept", accepted])
    if args.apply:
        command.extend([
            "--apply", "--confirm", "--review-sha256", args.review_sha256,
        ])
    return command


def main(argv: list[str] | None = None) -> int:
    try:
        command = build_command(argv)
    except LauncherError as exc:
        print(f"upgrade launcher refused: {exc}", file=sys.stderr)
        return 2
    release = Path(command[1]).resolve().parents[2]
    installed = Path(command[command.index("--root") + 1])
    print(f"executing target release code: {release}", flush=True)
    print(f"installed vault: {installed}", flush=True)
    print("mode: " + ("exact reviewed apply" if "--apply" in command else
                      "read-only review"), flush=True)
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
