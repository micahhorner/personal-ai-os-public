"""Fail-closed primitives for restoring an exact Git commit.

The public entry point, :func:`restore_commit`, deliberately accepts only a
full commit object ID and an independently captured SHA-256 identity for its
tracked tree.  It does not move HEAD and it never uses ``reset --hard``.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import subprocess
import tarfile
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union


PathValue = Union[str, os.PathLike]
Validator = Callable[[Path], Union[bool, Mapping[str, Any]]]
_FULL_OBJECT_ID = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_SAFE_MODES = {"100644", "100755", "120000"}


class RecoveryError(RuntimeError):
    """Exact restoration was unsafe, invalid, or could not be proved."""

    def __init__(
        self, message: str, evidence: Optional[Mapping[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.evidence = dict(evidence or {})


def _run_git(
    root: Path, args: Sequence[str], *, check: bool = True
) -> subprocess.CompletedProcess:
    command = ["git", "-C", str(root)] + list(args)
    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise RecoveryError("git executable not found") from exc
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RecoveryError(
            "git command failed: "
            + " ".join(args[:2])
            + (f": {detail}" if detail else "")
        )
    return result


def _repository_root(value: PathValue) -> Path:
    supplied = Path(value).expanduser()
    if supplied.is_symlink():
        raise RecoveryError("repository path must not be a symbolic link")
    try:
        root = supplied.resolve(strict=True)
    except OSError as exc:
        raise RecoveryError(f"repository path is unavailable: {supplied}") from exc
    if not root.is_dir():
        raise RecoveryError(f"repository path is not a directory: {root}")
    result = _run_git(root, ["rev-parse", "--show-toplevel"])
    top = Path(os.fsdecode(result.stdout).strip()).resolve()
    if top != root:
        raise RecoveryError(
            f"repository path must be the worktree root, not a subdirectory: {root}"
        )
    return root


def _split_z(data: bytes) -> List[str]:
    return [os.fsdecode(item) for item in data.split(b"\0") if item]


def _safe_relative(raw: str) -> str:
    if not raw or "\0" in raw or "\\" in raw:
        raise RecoveryError(f"unsafe Git tree path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", "..", ".git"} for part in path.parts):
        raise RecoveryError(f"unsafe Git tree path: {raw!r}")
    return path.as_posix()


def _safe_symlink(path: str, target_bytes: bytes) -> str:
    if b"\0" in target_bytes:
        raise RecoveryError(f"unsafe symbolic-link target at {path!r}")
    target = os.fsdecode(target_bytes)
    posix = PurePosixPath(target)
    windows = PureWindowsPath(target)
    if not target or posix.is_absolute() or windows.is_absolute():
        raise RecoveryError(f"unsafe symbolic-link target at {path!r}: {target!r}")
    depth = len(PurePosixPath(path).parent.parts)
    for part in posix.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            depth -= 1
            if depth < 0:
                raise RecoveryError(
                    f"symbolic link escapes repository at {path!r}: {target!r}"
                )
        else:
            depth += 1
    return target


def _resolve_commit(root: Path, commit: str) -> Tuple[str, str]:
    identity = str(commit).strip()
    if not _FULL_OBJECT_ID.fullmatch(identity):
        raise RecoveryError(
            "restore target must be a full 40- or 64-character hexadecimal commit ID"
        )
    result = _run_git(
        root, ["rev-parse", "--verify", f"{identity}^{{commit}}"], check=False
    )
    if result.returncode != 0:
        raise RecoveryError(f"restore target is not a reachable commit: {identity}")
    resolved = os.fsdecode(result.stdout).strip().lower()
    if resolved != identity.lower():
        raise RecoveryError(
            f"restore target did not resolve to the exact supplied commit: {identity}"
        )
    tree = os.fsdecode(
        _run_git(root, ["rev-parse", f"{resolved}^{{tree}}"]).stdout
    ).strip()
    return resolved, tree


def _commit_entries(root: Path, commit: str) -> List[Dict[str, Any]]:
    result = _run_git(root, ["ls-tree", "-rz", "--full-tree", commit])
    entries: List[Dict[str, Any]] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            metadata, raw_path = raw.split(b"\t", 1)
            mode_b, kind_b, oid_b = metadata.split(b" ", 2)
        except ValueError as exc:
            raise RecoveryError("Git returned an invalid tree record") from exc
        mode = mode_b.decode("ascii")
        kind = kind_b.decode("ascii")
        oid = oid_b.decode("ascii")
        path = _safe_relative(os.fsdecode(raw_path))
        if kind != "blob" or mode not in _SAFE_MODES:
            raise RecoveryError(
                f"unsupported Git entry at {path!r}: mode={mode} type={kind}"
            )
        content = _run_git(root, ["cat-file", "blob", oid]).stdout
        entry: Dict[str, Any] = {
            "path": path,
            "mode": mode,
            "kind": "symlink" if mode == "120000" else "file",
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        if mode == "120000":
            entry["target"] = _safe_symlink(path, content)
        entries.append(entry)
    return entries


def _entries_hash(entries: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: str(item["path"])):
        encoded = json.dumps(
            dict(entry),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _normalized_scope(scope_paths: Optional[Sequence[str]]) -> List[str]:
    if not scope_paths:
        return []
    normalized = sorted({_safe_relative(str(path).rstrip("/")) for path in scope_paths})
    for index, path in enumerate(normalized):
        for other in normalized[index + 1:]:
            if other.startswith(path + "/"):
                raise RecoveryError(
                    f"restore scope overlaps or is redundant: {path!r}, {other!r}"
                )
    return normalized


def _in_scope(path: str, scope: Sequence[str]) -> bool:
    return not scope or any(
        path == base or path.startswith(base + "/") for base in scope
    )


def _proof_hash(
    entries: Sequence[Mapping[str, Any]], commit: str, scope: Sequence[str]
) -> str:
    if not scope:
        return _entries_hash(entries)
    payload = {
        "schema": "aios-git-scope-v1",
        "commit": commit,
        "scope_paths": list(scope),
        "entries": list(entries),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def inspect_commit(
    repository: PathValue,
    commit: str,
    *,
    scope_paths: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Validate a full commit identity and return its deterministic tree proof."""
    root = _repository_root(repository)
    resolved, git_tree = _resolve_commit(root, commit)
    scope = _normalized_scope(scope_paths)
    entries = [
        entry
        for entry in _commit_entries(root, resolved)
        if _in_scope(str(entry["path"]), scope)
    ]
    if scope and not entries:
        raise RecoveryError("restore scope contains no paths in the target commit")
    return {
        "commit": resolved,
        "git_tree": git_tree,
        "tracked_sha256": _proof_hash(entries, resolved, scope),
        "tracked_entry_count": len(entries),
        "scope_paths": scope,
    }


def _working_entries(root: Path, expected: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    actual: List[Dict[str, Any]] = []
    for wanted in expected:
        relative = str(wanted["path"])
        path = root.joinpath(*PurePosixPath(relative).parts)
        try:
            info = path.lstat()
        except OSError as exc:
            raise RecoveryError(f"restored tracked path is missing: {relative}") from exc
        if wanted["kind"] == "symlink":
            if not stat.S_ISLNK(info.st_mode):
                raise RecoveryError(f"restored path is not a symlink: {relative}")
            target = os.readlink(path)
            content = os.fsencode(target)
            _safe_symlink(relative, content)
            mode = "120000"
        else:
            if not stat.S_ISREG(info.st_mode):
                raise RecoveryError(f"restored path is not a regular file: {relative}")
            content = path.read_bytes()
            mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
        actual.append(
            {
                "path": relative,
                "mode": mode,
                "kind": wanted["kind"],
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                **({"target": os.fsdecode(content)} if wanted["kind"] == "symlink" else {}),
            }
        )
    return actual


def _whole_tree_hash(root: Path) -> str:
    records: List[Dict[str, Any]] = []

    def visit(directory: Path) -> None:
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            relative = child.relative_to(root).as_posix()
            if relative == ".git":
                continue
            info = child.lstat()
            if stat.S_ISLNK(info.st_mode):
                record = {
                    "path": relative,
                    "kind": "symlink",
                    "target": os.readlink(child),
                }
            elif stat.S_ISDIR(info.st_mode):
                record = {"path": relative, "kind": "directory"}
                records.append(record)
                visit(child)
                continue
            elif stat.S_ISREG(info.st_mode):
                record = {
                    "path": relative,
                    "kind": "file",
                    "mode": stat.S_IMODE(info.st_mode),
                    "sha256": hashlib.sha256(child.read_bytes()).hexdigest(),
                }
            else:
                record = {"path": relative, "kind": "other"}
            records.append(record)

    visit(root)
    return _entries_hash(records)


def _tracked_status(root: Path) -> List[str]:
    result = _run_git(
        root, ["status", "--porcelain=v1", "-z", "--untracked-files=no"]
    )
    return _split_z(result.stdout)


def _snapshot(root: Path, destination_dir: Optional[PathValue]) -> Path:
    parent = (
        Path(destination_dir).expanduser().resolve()
        if destination_dir is not None
        else root.parent / f"{root.name}-Snapshots"
    )
    if parent == root or root in parent.parents:
        raise RecoveryError("snapshot directory must be outside the repository")
    parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    for attempt in range(1, 1_000_000):
        destination = parent / f"{stamp}-pre-restore-{attempt:04d}.tar.gz"
        if not destination.exists():
            break
    else:
        raise RecoveryError("could not allocate a unique snapshot path")
    with tarfile.open(destination, "x:gz", dereference=False) as archive:
        for child in sorted(root.iterdir(), key=lambda item: item.name):
            if child.name == ".git":
                continue
            archive.add(child, arcname=child.name, recursive=True)
    return destination


def _untracked(root: Path, *, include_ignored: bool) -> List[str]:
    args = ["ls-files", "--others", "-z"]
    if include_ignored:
        args.extend(["--ignored", "--exclude-standard"])
    else:
        args.append("--exclude-standard")
    return [_safe_relative(path) for path in _split_z(_run_git(root, args).stdout)]


def _has_path_conflict(path: str, targets: Sequence[str]) -> bool:
    prefix = path + "/"
    return any(target == path or target.startswith(prefix) or path.startswith(target + "/")
               for target in targets)


def _assert_safe_worktree(root: Path, paths: Sequence[str]) -> None:
    for relative in paths:
        current = root
        for part in PurePosixPath(relative).parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise RecoveryError(
                    f"symbolic-link ancestor would escape restoration: {relative!r}"
                )


def _remove_tracked_worktree(root: Path, paths: Sequence[str]) -> None:
    for relative in sorted(paths, key=lambda value: (value.count("/"), value), reverse=True):
        path = root.joinpath(*PurePosixPath(relative).parts)
        if not os.path.lexists(path):
            continue
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError as exc:
                raise RecoveryError(
                    f"tracked path is occupied by a nonempty directory: {relative!r}"
                ) from exc
        else:
            raise RecoveryError(f"unsupported worktree entry: {relative!r}")
        parent = path.parent
        while parent != root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def _validation_result(validator: Optional[Validator], root: Path) -> Dict[str, Any]:
    if validator is None:
        return {"performed": False, "passed": True}
    try:
        raw = validator(root)
    except Exception as exc:
        return {
            "performed": True,
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if isinstance(raw, Mapping):
        result = dict(raw)
        result["performed"] = True
        result["passed"] = bool(result.get("passed", result.get("ok", False)))
        return result
    return {"performed": True, "passed": bool(raw)}


def restore_commit(
    repository: PathValue,
    commit: str,
    *,
    expected_tracked_sha256: str,
    clean: bool = False,
    snapshot_dir: Optional[PathValue] = None,
    validator: Optional[Validator] = None,
    scope_paths: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Restore tracked content exactly to ``commit`` and return proof.

    Untracked and ignored files survive unless ``clean=True``.  A dirty tracked
    worktree is archived outside the repository before any tracked path changes.
    Any identity, path, post-restore hash, or caller-supplied validation mismatch
    raises :class:`RecoveryError`.
    """
    root = _repository_root(repository)
    if not _SHA256.fullmatch(str(expected_tracked_sha256)):
        raise RecoveryError("expected_tracked_sha256 must be a 64-character SHA-256")
    scope = _normalized_scope(scope_paths)
    resolved, git_tree = _resolve_commit(root, commit)
    expected_entries = [
        entry
        for entry in _commit_entries(root, resolved)
        if _in_scope(str(entry["path"]), scope)
    ]
    if scope and not expected_entries:
        raise RecoveryError("restore scope contains no paths in the target commit")
    computed_expected = _proof_hash(expected_entries, resolved, scope)
    if computed_expected != str(expected_tracked_sha256).lower():
        raise RecoveryError(
            "expected tracked hash does not match the validated restore commit",
            {
                "commit": resolved,
                "supplied_expected_tracked_sha256": str(expected_tracked_sha256),
                "computed_expected_tracked_sha256": computed_expected,
            },
        )

    current_tracked = [
        _safe_relative(path)
        for path in _split_z(_run_git(root, ["ls-files", "-z"]).stdout)
        if _in_scope(_safe_relative(path), scope)
    ]
    target_paths = [str(entry["path"]) for entry in expected_entries]
    _assert_safe_worktree(root, sorted(set(current_tracked + target_paths)))
    dirty = _tracked_status(root)
    untracked = [
        path for path in _untracked(root, include_ignored=False)
        if _in_scope(path, scope)
    ]
    ignored = [
        path for path in _untracked(root, include_ignored=True)
        if _in_scope(path, scope)
    ]
    already_exact = False
    if sorted(current_tracked) == sorted(target_paths):
        try:
            already_exact = (
                _proof_hash(_working_entries(root, expected_entries), resolved, scope)
                == computed_expected
            )
        except RecoveryError:
            already_exact = False
    before = {
        "tree_sha256": _whole_tree_hash(root),
        "tracked_status": dirty,
        "already_exact": already_exact,
    }
    # Status is relative to HEAD.  After an exact restoration HEAD intentionally
    # still names the newer commit, so a rerun can look "dirty" even though this
    # operation would overwrite no tracked bytes.  Snapshot only when tracked
    # state actually differs from the requested target.
    # `clean=True` deliberately removes newer untracked and ignored paths, but
    # those bytes must remain recoverable. Committed tracked differences remain
    # recoverable from Git; uncommitted tracked differences and cleaned paths
    # require an external whole-tree archive.
    will_overwrite_uncommitted = bool(dirty and not already_exact)
    will_clean_other = bool(clean and (untracked or ignored))
    snapshot = (
        str(_snapshot(root, snapshot_dir))
        if will_overwrite_uncommitted or will_clean_other
        else None
    )

    if not clean:
        collisions = sorted(
            path
            for path in untracked + ignored
            if _has_path_conflict(path, target_paths)
        )
        if collisions:
            raise RecoveryError(
                "untracked or ignored paths conflict with the restore target; "
                "preserve them elsewhere or use clean=True",
                {"conflicts": sorted(set(collisions)), "snapshot": snapshot},
            )
    else:
        clean_scope = ["--"] + scope if scope else []
        # Remove post-checkpoint untracked product paths, but preserve ignored
        # reproducible/runtime state such as System/Generated and managed skill
        # projections. `-x` previously destroyed those ignored paths and even
        # the setup interpreter used to execute this command.
        preview = _run_git(root, ["clean", "-ndff"] + clean_scope)
        _run_git(root, ["clean", "-dff"] + clean_scope)
        clean_preview = os.fsdecode(preview.stdout).splitlines()

    _remove_tracked_worktree(root, current_tracked)
    if scope:
        _run_git(
            root,
            ["restore", "--source", resolved, "--staged", "--worktree", "--"] + scope,
        )
    else:
        _run_git(root, ["read-tree", resolved])
        _run_git(root, ["checkout-index", "--all", "--force"])

    actual_entries = _working_entries(root, expected_entries)
    actual_hash = _proof_hash(actual_entries, resolved, scope)
    indexed = [
        _safe_relative(path)
        for path in _split_z(_run_git(root, ["ls-files", "-z"]).stdout)
        if _in_scope(_safe_relative(path), scope)
    ]
    exact = actual_hash == computed_expected and sorted(indexed) == sorted(target_paths)
    validation = _validation_result(validator, root)
    evidence: Dict[str, Any] = {
        "schema_version": 1,
        "repository": str(root),
        "commit": resolved,
        "git_tree": git_tree,
        "clean": bool(clean),
        "scope_paths": scope,
        "coverage": "declared-paths-only" if scope else "whole-tree",
        "snapshot": snapshot,
        "expected_tracked_sha256": computed_expected,
        "before": before,
        "post": {
            "tree_sha256": _whole_tree_hash(root),
            "tracked_sha256": actual_hash,
            "tracked_entry_count": len(actual_entries),
            "indexed_paths_match": sorted(indexed) == sorted(target_paths),
        },
        "validation": validation,
        "exact_restoration": exact and validation["passed"],
    }
    if clean:
        evidence["clean_preview"] = clean_preview
    if not exact:
        raise RecoveryError("restored tracked tree does not match the expected hash", evidence)
    if not validation["passed"]:
        raise RecoveryError("restored tree failed validation", evidence)
    return evidence
