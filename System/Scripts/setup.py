#!/usr/bin/env python3
"""Create the product-local runtime and run the first deterministic checks."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


DEPENDENCY = "PyYAML>=6.0,<7"


class SetupError(RuntimeError):
    pass


def _run(argv: list[str], *, cwd: Path) -> None:
    result = subprocess.run(argv, cwd=str(cwd), check=False)
    if result.returncode:
        raise SetupError("command failed (%d): %s" %
                         (result.returncode, " ".join(argv)))


def setup(root: Path, environment: Path) -> None:
    root = root.resolve()
    environment = environment.resolve()
    if not (root / "SYSTEM-MANIFEST.yaml").is_file():
        raise SetupError("run setup from a Personal AI OS product root")
    try:
        environment.relative_to(root)
    except ValueError:
        pass
    else:
        raise SetupError(
            "the isolated environment must be outside the vault so snapshots and rollback remain exact")

    venv.EnvBuilder(with_pip=True, clear=False).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        raise SetupError("virtual environment did not create its Python executable")
    _run([str(python), "-m", "pip", "install", DEPENDENCY], cwd=root)
    aios = root / "System" / "Scripts" / "aios.py"
    _run([str(python), str(aios), "generate", "--root", str(root)], cwd=root)
    _run([str(python), str(aios), "instance-health", "--root", str(root)], cwd=root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create .venv, install the pinned dependency, generate state, and run instance health.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--venv", default=None,
                        help="environment path (default: sibling .<vault-name>.aios-venv)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    environment = (Path(args.venv) if args.venv else
                   root.resolve().parent / ("." + root.resolve().name + ".aios-venv"))
    try:
        setup(root, environment)
    except (OSError, SetupError) as exc:
        print("setup refused: %s" % exc, file=sys.stderr)
        return 1
    print("setup complete: %s" % environment.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
