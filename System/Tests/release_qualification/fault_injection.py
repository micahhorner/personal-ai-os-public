"""Child-process fault injection for release-qualification tests.

The product has no fault-injection API.  This test-only module installs narrow
wrappers around the exact upgrade call graph, invokes ``aios.main`` in a fresh
Python process, and terminates that process with ``os._exit`` at the selected
boundary.  The parent remains alive to inspect the fixture left on disk.

Filesystem hooks are always scoped to one exact vault and, where the operation
could otherwise match many paths, one exact target path.  A global copy,
delete, rmdir, or open wrapper is never an accepted public configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
import builtins
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


ABRUPT_EXIT_CODE = 86
CLEANUP_COVERAGE = "unavailable-no-production-boundary"
FAULT_TARGET_MARKER = ".release-qualification-fault-target"
_FAULT_TARGET_CONTENT = "armed test fixture; abrupt termination permitted\n"
PHASES = frozenset({"before", "after"})
HOOKS = frozenset(
    {
        "classification",
        "checkpoint",
        "copy",
        "delete",
        "rmdir",
        "baseline-replacement",
        "generation",
        "validation",
        "version-bump",
        "report-write",
    }
)
_EXACT_TARGET_HOOKS = frozenset({"copy", "delete", "rmdir"})
_SPEC_ENV = "PAIOS_RELEASE_FAULT_SPEC"
_ARGV_ENV = "PAIOS_RELEASE_FAULT_ARGV"


class FaultInjectionError(ValueError):
    """The requested injection is unsafe or cannot identify a real boundary."""


@dataclass(frozen=True)
class FaultSpec:
    """One scoped, single-shot abrupt interruption."""

    hook: str
    phase: str
    vault_root: str
    target_path: str | None = None

    def __post_init__(self) -> None:
        if self.hook == "cleanup":
            raise FaultInjectionError(CLEANUP_COVERAGE)
        if self.hook not in HOOKS:
            raise FaultInjectionError(f"unknown fault hook: {self.hook!r}")
        if self.phase not in PHASES:
            raise FaultInjectionError(
                f"phase must be one of {sorted(PHASES)}, got {self.phase!r}"
            )

        root = _canonical_vault_root(self.vault_root)
        if root == Path(root.anchor):
            raise FaultInjectionError("vault_root may not be a filesystem root")
        object.__setattr__(self, "vault_root", str(root))

        if self.hook in _EXACT_TARGET_HOOKS:
            if self.target_path is None:
                raise FaultInjectionError(
                    f"{self.hook} requires one exact target_path; "
                    "unscoped/global filesystem hooks are forbidden"
                )
            target = _canonical_target(self.target_path)
            if target == root or root not in target.parents:
                raise FaultInjectionError(
                    "target_path must be a descendant of vault_root"
                )
            object.__setattr__(self, "target_path", str(target))
        elif self.target_path is not None:
            raise FaultInjectionError(
                f"{self.hook} derives its exact scope from vault_root and "
                "does not accept target_path"
            )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "hook": self.hook,
            "phase": self.phase,
            "vault_root": self.vault_root,
            "target_path": self.target_path,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FaultSpec":
        return cls(
            hook=str(value.get("hook", "")),
            phase=str(value.get("phase", "")),
            vault_root=str(value.get("vault_root", "")),
            target_path=value.get("target_path"),
        )


@dataclass(frozen=True)
class FaultRun:
    """Observable child result; fixture inspection remains the caller's job."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def interrupted(self) -> bool:
        return self.returncode == ABRUPT_EXIT_CODE


def run_aios_with_fault(
    scripts_dir: os.PathLike[str] | str,
    argv: Sequence[str],
    spec: FaultSpec,
    *,
    timeout: float = 30,
) -> FaultRun:
    """Run the target ``aios.main`` in a child with one installed fault."""

    scripts = _canonical_existing_dir(scripts_dir, "scripts_dir")
    root = Path(spec.vault_root)
    if root == scripts or root in scripts.parents or scripts in root.parents:
        raise FaultInjectionError(
            "fault target and scripts worktree must be separate trees"
        )
    aios = scripts / "aios.py"
    if not aios.is_file():
        raise FaultInjectionError(f"scripts_dir has no aios.py: {scripts}")
    _require_armed_target(root)
    if not isinstance(argv, (list, tuple)) or not all(
        isinstance(item, str) for item in argv
    ):
        raise FaultInjectionError("argv must be a sequence of strings")

    env = os.environ.copy()
    env[_SPEC_ENV] = json.dumps(spec.to_dict(), sort_keys=True)
    env[_ARGV_ENV] = json.dumps(list(argv))
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", str(scripts)],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    return FaultRun(result.returncode, result.stdout, result.stderr)


def arm_fault_target(vault_root: os.PathLike[str] | str) -> Path:
    """Explicitly mark a disposable fixture as eligible for abrupt termination."""

    root = _canonical_vault_root(vault_root)
    marker = root / FAULT_TARGET_MARKER
    if marker.is_symlink():
        raise FaultInjectionError("fault-target marker must not be a symlink")
    if marker.exists():
        if not marker.is_file() or marker.read_text(encoding="utf-8") != _FAULT_TARGET_CONTENT:
            raise FaultInjectionError("fault-target marker exists with unexpected content")
    else:
        marker.write_text(_FAULT_TARGET_CONTENT, encoding="utf-8")
    return marker


def _absolute_path(value: os.PathLike[str] | str, label: str) -> Path:
    if not isinstance(value, (str, os.PathLike)) or not str(value):
        raise FaultInjectionError(f"{label} must be a nonempty absolute path")
    path = Path(value)
    if not path.is_absolute():
        raise FaultInjectionError(f"{label} must be absolute")
    return Path(os.path.abspath(os.fspath(path)))


def _canonical_existing_dir(
    value: os.PathLike[str] | str,
    label: str,
) -> Path:
    lexical = _absolute_path(value, label)
    try:
        resolved = lexical.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FaultInjectionError(f"{label} must exist") from exc
    if lexical.is_symlink():
        raise FaultInjectionError(f"{label} must not traverse symlinks")
    if not resolved.is_dir():
        raise FaultInjectionError(f"{label} must be a directory")
    return resolved


def _canonical_vault_root(value: os.PathLike[str] | str) -> Path:
    return _canonical_existing_dir(value, "vault_root")


def _canonical_target(value: os.PathLike[str] | str) -> Path:
    lexical = _absolute_path(value, "target_path")
    resolved = lexical.resolve(strict=False)
    if lexical.is_symlink():
        raise FaultInjectionError("target_path must not traverse symlinks")
    return resolved


def _require_armed_target(root: Path) -> None:
    marker = root / FAULT_TARGET_MARKER
    if (
        marker.is_symlink()
        or not marker.is_file()
        or marker.read_text(encoding="utf-8") != _FAULT_TARGET_CONTENT
    ):
        raise FaultInjectionError(
            f"refusing unarmed fault target; call arm_fault_target() for the "
            f"disposable fixture ({marker})"
        )


def _same_path(value: Any, expected: str) -> bool:
    if not isinstance(value, (str, os.PathLike)):
        return False
    return str(Path(os.path.abspath(os.fspath(value))).resolve(strict=False)) == expected


def _crash() -> None:
    os._exit(ABRUPT_EXIT_CODE)


def _around(
    original: Callable[..., Any],
    phase: str,
    matches: Callable[[tuple[Any, ...], dict[str, Any]], bool],
) -> Callable[..., Any]:
    fired = False

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        nonlocal fired
        selected = not fired and matches(args, kwargs)
        if selected:
            fired = True
            if phase == "before":
                _crash()
        result = original(*args, **kwargs)
        if selected:
            _crash()
        return result

    return wrapped


def _root_arg_matches(root: str) -> Callable[[tuple[Any, ...], dict[str, Any]], bool]:
    def matches(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
        value = args[0] if args else kwargs.get("root")
        return _same_path(value, root)

    return matches


def _install_function_hook(spec: FaultSpec, module: Any, name: str) -> None:
    original = getattr(module, name)
    setattr(
        module,
        name,
        _around(original, spec.phase, _root_arg_matches(spec.vault_root)),
    )


def _install_copy_hook(spec: FaultSpec, upgrade: Any) -> None:
    target = str(spec.target_path)
    original = upgrade.shutil.copyfile

    def matches(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
        dst = args[1] if len(args) > 1 else kwargs.get("dst")
        return _same_path(dst, target)

    upgrade.shutil.copyfile = _around(original, spec.phase, matches)


def _install_delete_hook(spec: FaultSpec, upgrade: Any, name: str) -> None:
    target = str(spec.target_path)
    original = getattr(upgrade.os, name)

    def matches(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
        value = args[0] if args else kwargs.get("path")
        return _same_path(value, target)

    setattr(upgrade.os, name, _around(original, spec.phase, matches))


class _WriteProxy:
    def __init__(self, stream: Any, phase: str) -> None:
        self._stream = stream
        self._phase = phase
        self._fired = False

    def write(self, value: Any) -> Any:
        if not self._fired:
            self._fired = True
            if self._phase == "before":
                _crash()
            result = self._stream.write(value)
            self._stream.flush()
            os.fsync(self._stream.fileno())
            _crash()
        return self._stream.write(value)

    def __enter__(self) -> "_WriteProxy":
        self._stream.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        return self._stream.__exit__(*args)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _install_open_hook(spec: FaultSpec) -> None:
    original = builtins.open
    root = Path(spec.vault_root)
    manifest = str(root / "SYSTEM-MANIFEST.yaml")
    logs = str(root / "System" / "Logs")

    def selected(file: Any, mode: str) -> bool:
        if "w" not in mode or not isinstance(file, (str, os.PathLike)):
            return False
        path = str(
            Path(os.path.abspath(os.fspath(file))).resolve(strict=False)
        )
        if spec.hook == "version-bump":
            return path == manifest
        parent, name = os.path.split(path)
        return (
            parent == logs
            and name.startswith("upgrade-report-")
            and name.endswith(".md")
        )

    def wrapped(
        file: Any,
        mode: str = "r",
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if selected(file, mode) and spec.phase == "before":
            _crash()
        stream = original(file, mode, *args, **kwargs)
        if selected(file, mode):
            return _WriteProxy(stream, spec.phase)
        return stream

    builtins.open = wrapped


def _install_fault(spec: FaultSpec) -> None:
    from cmd import upgrade

    if spec.hook == "classification":
        _install_function_hook(spec, upgrade, "_classify")
    elif spec.hook == "checkpoint":
        _install_function_hook(spec, upgrade.ckpt_mod, "run")
    elif spec.hook == "copy":
        _install_copy_hook(spec, upgrade)
    elif spec.hook == "delete":
        _install_delete_hook(spec, upgrade, "remove")
    elif spec.hook == "rmdir":
        _install_delete_hook(spec, upgrade, "rmdir")
    elif spec.hook == "baseline-replacement":
        derived = FaultSpec(
            "copy",
            spec.phase,
            spec.vault_root,
            str(Path(spec.vault_root) / "System" / ".baseline-manifest.json"),
        )
        _install_copy_hook(derived, upgrade)
    elif spec.hook == "generation":
        from cmd import generate

        _install_function_hook(spec, generate, "run")
    elif spec.hook == "validation":
        from cmd import validate

        _install_function_hook(spec, validate, "run")
    elif spec.hook in {"version-bump", "report-write"}:
        _install_open_hook(spec)
    else:  # guarded by FaultSpec validation
        raise FaultInjectionError(f"unsupported fault hook: {spec.hook}")


def _child_main(scripts_dir: str) -> int:
    raw_spec = os.environ.get(_SPEC_ENV)
    raw_argv = os.environ.get(_ARGV_ENV)
    if raw_spec is None or raw_argv is None:
        raise FaultInjectionError("child fault configuration is missing")
    spec = FaultSpec.from_dict(json.loads(raw_spec))
    argv = json.loads(raw_argv)
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        raise FaultInjectionError("child argv is invalid")

    scripts = _canonical_existing_dir(scripts_dir, "scripts_dir")
    _require_armed_target(Path(spec.vault_root))
    sys.path.insert(0, str(scripts))
    _install_fault(spec)
    import aios

    result = aios.main(argv)
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--child":
        raise SystemExit("fault_injection.py is a test harness; use --child SCRIPTS_DIR")
    raise SystemExit(_child_main(sys.argv[2]))
