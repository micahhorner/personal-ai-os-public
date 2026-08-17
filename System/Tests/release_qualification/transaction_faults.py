"""Reusable child-process fault qualification for transactional upgrades.

Production exposes one inert test seam::

    _transaction_boundary(name, phase, root)

where ``name`` is one of :data:`BOUNDARIES` and ``phase`` is ``before`` or
``after``.  This module patches that seam only inside an armed disposable child
process and terminates with ``os._exit(86)``.  The source tree is never patched
on disk and the parent remains alive to classify the live vault as complete-old,
complete-new, or unsafe hybrid.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import ModuleType
from typing import Any, Dict, Mapping, Sequence


ABRUPT_EXIT_CODE = 86
FAULT_TARGET_MARKER = ".release-qualification-fault-target"
FAULT_TARGET_CONTENT = "armed transactional-upgrade fixture\n"
BOUNDARIES = (
    "checkpoint",
    "plan",
    "candidate-copy",
    "candidate-delete",
    "baseline-replacement",
    "generation",
    "validation",
    "version-bump",
    "report-write",
    "commit-swap",
    "cleanup",
)
PHASES = ("before", "after")
_SPEC_ENV = "PAIOS_TRANSACTION_FAULT_SPEC"
_ARGV_ENV = "PAIOS_TRANSACTION_FAULT_ARGV"


class TransactionFaultError(ValueError):
    """The requested qualification run is unsafe or malformed."""


class HybridStateError(AssertionError):
    """The interrupted live tree is neither the complete old nor new state."""


@dataclass(frozen=True)
class TransactionFaultSpec:
    boundary: str
    phase: str
    vault_root: str

    def __post_init__(self) -> None:
        if self.boundary not in BOUNDARIES:
            raise TransactionFaultError(
                f"boundary must be one of {list(BOUNDARIES)}, got {self.boundary!r}"
            )
        if self.phase not in PHASES:
            raise TransactionFaultError(
                f"phase must be one of {list(PHASES)}, got {self.phase!r}"
            )
        root = _existing_real_dir(self.vault_root, "vault_root")
        if root == Path(root.anchor):
            raise TransactionFaultError("vault_root may not be a filesystem root")
        object.__setattr__(self, "vault_root", str(root))

    def to_dict(self) -> Dict[str, str]:
        return {
            "boundary": self.boundary,
            "phase": self.phase,
            "vault_root": self.vault_root,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransactionFaultSpec":
        return cls(
            boundary=str(value.get("boundary", "")),
            phase=str(value.get("phase", "")),
            vault_root=str(value.get("vault_root", "")),
        )


@dataclass(frozen=True)
class TransactionFaultRun:
    returncode: int
    stdout: str
    stderr: str

    @property
    def interrupted(self) -> bool:
        return self.returncode == ABRUPT_EXIT_CODE


def _existing_real_dir(value: os.PathLike, label: str) -> Path:
    lexical = Path(value).expanduser().absolute()
    if lexical.is_symlink():
        raise TransactionFaultError(f"{label} must not be a symbolic link")
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise TransactionFaultError(f"{label} must exist") from exc
    if not resolved.is_dir():
        raise TransactionFaultError(f"{label} must be a directory")
    return resolved


def arm_fault_target(vault_root: os.PathLike) -> Path:
    root = _existing_real_dir(vault_root, "vault_root")
    marker = root / FAULT_TARGET_MARKER
    if marker.is_symlink():
        raise TransactionFaultError("fault-target marker must not be a symbolic link")
    if marker.exists():
        if (
            not marker.is_file()
            or marker.read_text(encoding="utf-8") != FAULT_TARGET_CONTENT
        ):
            raise TransactionFaultError("fault-target marker has unexpected content")
    else:
        marker.write_text(FAULT_TARGET_CONTENT, encoding="utf-8")
    return marker


def _require_armed(root: Path) -> None:
    marker = root / FAULT_TARGET_MARKER
    if (
        marker.is_symlink()
        or not marker.is_file()
        or marker.read_text(encoding="utf-8") != FAULT_TARGET_CONTENT
    ):
        raise TransactionFaultError(
            f"refusing unarmed target; call arm_fault_target() first: {marker}"
        )


def _entry(path: Path) -> Dict[str, Any]:
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if path.is_symlink():
        return {"kind": "symlink", "mode": mode, "target": os.readlink(path)}
    if path.is_dir():
        return {"kind": "directory", "mode": mode}
    if path.is_file():
        return {
            "kind": "file",
            "mode": mode,
            "size": info.st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return {"kind": "other", "mode": mode}


def capture_tree(root: os.PathLike) -> Dict[str, Any]:
    """Capture a deterministic live-tree identity, excluding Git internals."""
    base = _existing_real_dir(root, "tree root")
    entries: Dict[str, Dict[str, Any]] = {}

    def visit(directory: Path) -> None:
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            relative = child.relative_to(base).as_posix()
            if relative == ".git":
                continue
            record = _entry(child)
            entries[relative] = record
            if record["kind"] == "directory":
                visit(child)

    visit(base)
    digest = hashlib.sha256()
    for relative in sorted(entries):
        encoded = json.dumps(
            [relative, entries[relative]],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return {"sha256": digest.hexdigest(), "entries": entries}


def classify_atomic_state(
    vault_root: os.PathLike,
    *,
    old_sha256: str,
    new_sha256: str,
) -> str:
    """Return ``old`` or ``new``; raise when the live tree is hybrid."""
    actual = capture_tree(vault_root)["sha256"]
    if actual == old_sha256:
        return "old"
    if actual == new_sha256:
        return "new"
    raise HybridStateError(
        f"live tree is hybrid: {actual}; expected old={old_sha256} or new={new_sha256}"
    )


def assert_upgrade_contract(module: ModuleType) -> None:
    """Fail with the exact production seam required by this harness."""
    missing = [
        name
        for name in ("_transaction_boundary", "_free_bytes", "_same_filesystem")
        if not callable(getattr(module, name, None))
    ]
    if missing:
        raise TransactionFaultError(
            "upgrade transaction contract is missing callable(s): " + ", ".join(missing)
        )


def run_with_fault(
    scripts_dir: os.PathLike,
    argv: Sequence[str],
    spec: TransactionFaultSpec,
    *,
    timeout: float = 30.0,
) -> TransactionFaultRun:
    """Run a supplied upgrade executable with one abrupt boundary interruption."""
    scripts = _existing_real_dir(scripts_dir, "scripts_dir")
    root = Path(spec.vault_root)
    if root == scripts or root in scripts.parents or scripts in root.parents:
        raise TransactionFaultError(
            "fault target and executable source must be separate trees"
        )
    if not (scripts / "aios.py").is_file():
        raise TransactionFaultError(f"scripts_dir has no aios.py: {scripts}")
    _require_armed(root)
    if not isinstance(argv, (list, tuple)) or not all(
        isinstance(item, str) for item in argv
    ):
        raise TransactionFaultError("argv must be a sequence of strings")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise TransactionFaultError("timeout must be greater than zero")

    environment = os.environ.copy()
    environment[_SPEC_ENV] = json.dumps(spec.to_dict(), sort_keys=True)
    environment[_ARGV_ENV] = json.dumps(list(argv))
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", str(scripts)],
        capture_output=True,
        text=True,
        env=environment,
        timeout=timeout,
        check=False,
    )
    return TransactionFaultRun(result.returncode, result.stdout, result.stderr)


def _install(spec: TransactionFaultSpec) -> None:
    upgrade = importlib.import_module("cmd.upgrade")
    assert_upgrade_contract(upgrade)
    original = upgrade._transaction_boundary
    fired = False

    def boundary(name: str, phase: str, root: str) -> None:
        nonlocal fired
        selected = (
            not fired
            and name == spec.boundary
            and phase == spec.phase
            and Path(root).resolve(strict=False) == Path(spec.vault_root)
        )
        if selected:
            fired = True
            os._exit(ABRUPT_EXIT_CODE)
        original(name, phase, root)

    upgrade._transaction_boundary = boundary


def _child(scripts_dir: str) -> int:
    raw_spec = os.environ.get(_SPEC_ENV)
    raw_argv = os.environ.get(_ARGV_ENV)
    if raw_spec is None or raw_argv is None:
        raise TransactionFaultError("child fault configuration is missing")
    spec = TransactionFaultSpec.from_dict(json.loads(raw_spec))
    argv = json.loads(raw_argv)
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        raise TransactionFaultError("child argv is invalid")
    scripts = _existing_real_dir(scripts_dir, "scripts_dir")
    _require_armed(Path(spec.vault_root))
    sys.path.insert(0, str(scripts))
    _install(spec)
    aios = importlib.import_module("aios")
    result = aios.main(argv)
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--child":
        raise SystemExit(
            "transaction_faults.py is a test harness; use --child SCRIPTS_DIR"
        )
    raise SystemExit(_child(sys.argv[2]))
