"""Exact, no-Git vault snapshots with fail-closed staged restore.

This module deliberately has no dependency on the CLI or Git.  A snapshot is a
ZIP containing a canonical manifest plus a ``payload/`` tree.  Restore validates
the complete archive into a sibling directory before the live tree is renamed.
The previous live tree is retained after success and put back automatically if
the swap cannot complete.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, Union


MANIFEST_MEMBER = "AIOS-SNAPSHOT.json"
PAYLOAD_PREFIX = "payload/"
SCHEMA = "aios-exact-snapshot-v1"
_CHUNK = 1024 * 1024


class SnapshotError(RuntimeError):
    """Base class for a snapshot or restore refusal."""


class UnsafeArchiveError(SnapshotError):
    """The archive cannot be extracted without crossing a trust boundary."""


class CorruptSnapshotError(SnapshotError):
    """The archive does not match its manifest or supplied identity."""


class InsufficientStagingError(SnapshotError):
    """A complete sibling candidate cannot be staged safely."""


class RestoreError(SnapshotError):
    """A validated candidate could not safely replace the live tree."""


SnapshotRef = Union[str, os.PathLike, Mapping[str, Any]]
InterruptHook = Optional[Callable[[str], None]]


def _resolved_parent_path(value: Union[str, os.PathLike]) -> Path:
    """Normalize parents without following the final path component."""
    path = Path(value).expanduser().absolute()
    return path.parent.resolve() / path.name


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _tree_sha(entries: Iterable[Mapping[str, Any]], root_mode: int) -> str:
    return hashlib.sha256(
        _canonical_json({"root_mode": root_mode, "entries": list(entries)})
    ).hexdigest()


def _portable_key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def _validate_relative(path: str) -> str:
    if not isinstance(path, str) or not path:
        raise UnsafeArchiveError("archive path is empty or not text")
    if "\x00" in path or "\\" in path:
        raise UnsafeArchiveError("archive path contains NUL or backslash")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise UnsafeArchiveError("archive path is absolute")
    parts = PurePosixPath(path).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise UnsafeArchiveError("archive path traverses outside the snapshot")
    normalized = "/".join(parts)
    if normalized != path.rstrip("/"):
        raise UnsafeArchiveError("archive path is not canonical")
    return normalized


def _mode(info: zipfile.ZipInfo) -> int:
    return (info.external_attr >> 16) & 0xFFFF


def _zip_kind(info: zipfile.ZipInfo) -> str:
    mode = _mode(info)
    file_type = stat.S_IFMT(mode)
    if info.is_dir():
        if file_type and not stat.S_ISDIR(mode):
            raise UnsafeArchiveError(f"directory has unsafe type: {info.filename}")
        return "dir"
    if file_type and not stat.S_ISREG(mode):
        raise UnsafeArchiveError(
            f"non-regular archive member refused: {info.filename}"
        )
    return "file"


def _ensure_unique(paths: Iterable[str]) -> None:
    exact = set()
    portable: Dict[str, str] = {}
    for path in paths:
        normalized = _validate_relative(path)
        if normalized in exact:
            raise UnsafeArchiveError(f"duplicate archive path: {normalized}")
        exact.add(normalized)
        key = _portable_key(normalized)
        if key in portable:
            raise UnsafeArchiveError(
                "case/Unicode-colliding archive paths: "
                f"{portable[key]!r} and {normalized!r}"
            )
        portable[key] = normalized


def _entry(path: str, kind: str, mode: int, size: int = 0,
           sha256: Optional[str] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "path": path,
        "kind": kind,
        "mode": stat.S_IMODE(mode),
        "size": size,
    }
    if sha256 is not None:
        result["sha256"] = sha256
    return result


def _scan_tree(root: Path) -> List[Dict[str, Any]]:
    """Return the canonical content/mode manifest for an existing tree."""
    if root.is_symlink() or not root.is_dir():
        raise SnapshotError(f"snapshot root must be a real directory: {root}")
    entries: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        base = Path(dirpath)
        for name in list(dirnames):
            path = base / name
            if path.is_symlink():
                raise SnapshotError(f"snapshot refuses symbolic link: {path}")
            st = os.stat(str(path), follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode):
                raise SnapshotError(f"snapshot refuses special path: {path}")
            rel = path.relative_to(root).as_posix()
            entries.append(_entry(rel, "dir", st.st_mode))
        for name in filenames:
            path = base / name
            if path.is_symlink():
                raise SnapshotError(f"snapshot refuses symbolic link: {path}")
            st = os.stat(str(path), follow_symlinks=False)
            if not stat.S_ISREG(st.st_mode):
                raise SnapshotError(f"snapshot refuses special file: {path}")
            entries.append(
                _entry(
                    path.relative_to(root).as_posix(),
                    "file",
                    st.st_mode,
                    st.st_size,
                    _sha256_file(path),
                )
            )
    entries.sort(key=lambda item: (item["path"], item["kind"]))
    _validate_manifest_entries(entries)
    return entries


def _validate_manifest_entries(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        raise CorruptSnapshotError("snapshot manifest entries must be a list")
    entries: List[Dict[str, Any]] = []
    paths: List[str] = []
    kinds: Dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise CorruptSnapshotError("snapshot manifest entry is not an object")
        if set(item) not in (
            {"path", "kind", "mode", "size"},
            {"path", "kind", "mode", "size", "sha256"},
        ):
            raise CorruptSnapshotError("snapshot manifest entry has unknown fields")
        path = _validate_relative(item.get("path"))
        kind = item.get("kind")
        mode = item.get("mode")
        size = item.get("size")
        if kind not in ("file", "dir"):
            raise CorruptSnapshotError(f"unknown manifest entry kind: {path}")
        if not isinstance(mode, int) or isinstance(mode, bool) or not 0 <= mode <= 0o7777:
            raise CorruptSnapshotError(f"invalid mode in manifest: {path}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise CorruptSnapshotError(f"invalid size in manifest: {path}")
        if kind == "dir":
            if size != 0 or "sha256" in item:
                raise CorruptSnapshotError(f"invalid directory manifest entry: {path}")
        else:
            digest = item.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise CorruptSnapshotError(f"invalid file hash in manifest: {path}")
        paths.append(path)
        kinds[path] = kind
        entries.append(dict(item))
    _ensure_unique(paths)
    path_set = set(paths)
    for path in paths:
        parts = path.split("/")
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index])
            if parent in path_set and kinds[parent] != "dir":
                raise UnsafeArchiveError(
                    f"manifest places a child below a file: {parent}"
                )
    if entries != sorted(entries, key=lambda item: (item["path"], item["kind"])):
        raise CorruptSnapshotError("snapshot manifest entries are not canonical")
    return entries


def _manifest(entries: List[Dict[str, Any]], root_mode: int) -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "root_mode": root_mode,
        "entries": entries,
        "tree_sha256": _tree_sha(entries, root_mode),
        "total_file_bytes": sum(e["size"] for e in entries if e["kind"] == "file"),
    }


def _zipinfo(name: str, mode: int, directory: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name + ("/" if directory else ""))
    info.create_system = 3
    kind = stat.S_IFDIR if directory else stat.S_IFREG
    info.external_attr = (kind | stat.S_IMODE(mode)) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def create_snapshot(root: Union[str, os.PathLike],
                    archive_path: Union[str, os.PathLike],
                    *, interrupt: InterruptHook = None) -> Dict[str, Any]:
    """Create a complete snapshot and return its exact external identity.

    The returned mapping contains the absolute archive path, the SHA-256 of the
    archive bytes, and the embedded canonical manifest.  Supplying that mapping
    to :func:`restore_snapshot` detects replacement or modification of the ZIP.
    """
    source_input = Path(root).expanduser().absolute()
    if source_input.is_symlink() or not source_input.is_dir():
        raise SnapshotError(f"snapshot root must be a real directory: {source_input}")
    source = source_input.resolve()
    archive = _resolved_parent_path(archive_path)
    try:
        archive.relative_to(source)
    except ValueError:
        pass
    else:
        raise SnapshotError("snapshot archive must be outside the snapshotted tree")
    archive.parent.mkdir(parents=True, exist_ok=True)
    entries = _scan_tree(source)
    root_mode = stat.S_IMODE(os.stat(str(source), follow_symlinks=False).st_mode)
    manifest = _manifest(entries, root_mode)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{archive.name}.", suffix=".partial", dir=str(archive.parent)
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        by_path = {entry["path"]: entry for entry in entries}
        with zipfile.ZipFile(str(temporary), "w", allowZip64=True) as bundle:
            for entry in entries:
                rel = entry["path"]
                if entry["kind"] == "dir":
                    bundle.writestr(
                        _zipinfo(PAYLOAD_PREFIX + rel, entry["mode"], True), b""
                    )
                    continue
                source_path = source.joinpath(*PurePosixPath(rel).parts)
                before = os.stat(str(source_path), follow_symlinks=False)
                if not stat.S_ISREG(before.st_mode):
                    raise SnapshotError(f"file changed type during snapshot: {rel}")
                digest = hashlib.sha256()
                size = 0
                with source_path.open("rb") as src, bundle.open(
                    _zipinfo(PAYLOAD_PREFIX + rel, entry["mode"]), "w"
                ) as dest:
                    for chunk in iter(lambda: src.read(_CHUNK), b""):
                        digest.update(chunk)
                        size += len(chunk)
                        dest.write(chunk)
                after = os.stat(str(source_path), follow_symlinks=False)
                if (
                    before.st_dev,
                    before.st_ino,
                    before.st_size,
                    before.st_mtime_ns,
                ) != (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                ):
                    raise SnapshotError(f"file changed while snapshot was read: {rel}")
                if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                    raise SnapshotError(f"file content changed during snapshot: {rel}")
                if by_path[rel] != entry:
                    raise SnapshotError(f"manifest changed during snapshot: {rel}")
            bundle.writestr(
                _zipinfo(MANIFEST_MEMBER, 0o600), _canonical_json(manifest)
            )
        if interrupt:
            interrupt("before-publish")
        try:
            # Publish by exclusive hard-link creation.  Unlike os.replace(),
            # this is atomic and cannot silently destroy an older recovery
            # artifact when two checkpoints choose the same timestamp/label.
            os.link(str(temporary), str(archive), follow_symlinks=False)
        except FileExistsError as exc:
            raise SnapshotError(
                f"snapshot archive already exists; refusing to replace it: {archive}"
            ) from exc
        temporary.unlink()
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return {
        "path": str(archive),
        "sha256": _sha256_file(archive),
        "manifest": manifest,
    }


def _snapshot_reference(snapshot: SnapshotRef) -> Tuple[Path, Optional[str],
                                                        Optional[Mapping[str, Any]]]:
    if isinstance(snapshot, Mapping):
        allowed = {"path", "sha256", "manifest"}
        minimal = {"path", "sha256"}
        if set(snapshot) not in (allowed, minimal):
            raise CorruptSnapshotError("snapshot identity fields are incomplete or unknown")
        path = snapshot.get("path")
        digest = snapshot.get("sha256")
        manifest = snapshot.get("manifest")
        if not isinstance(path, (str, os.PathLike)):
            raise CorruptSnapshotError("snapshot identity path is invalid")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CorruptSnapshotError("snapshot identity SHA-256 is invalid")
        if manifest is not None and not isinstance(manifest, Mapping):
            raise CorruptSnapshotError("snapshot identity manifest is invalid")
        return _resolved_parent_path(path), digest, manifest
    return _resolved_parent_path(snapshot), None, None


def _read_archive(snapshot: SnapshotRef) -> Tuple[Path, Dict[str, Any],
                                                  Dict[str, zipfile.ZipInfo]]:
    path, expected_sha, expected_manifest = _snapshot_reference(snapshot)
    if not path.is_file() or path.is_symlink():
        raise CorruptSnapshotError(f"snapshot archive is not a regular file: {path}")
    if expected_sha is not None and _sha256_file(path) != expected_sha:
        raise CorruptSnapshotError("snapshot archive SHA-256 does not match its identity")
    try:
        with zipfile.ZipFile(str(path), "r") as bundle:
            infos = bundle.infolist()
            raw_names = [info.filename.rstrip("/") for info in infos]
            _ensure_unique(raw_names)
            info_map = {info.filename.rstrip("/"): info for info in infos}
            # Reject links/devices even when the member is unlisted.  An unsafe
            # type is a trust-boundary violation, not merely a manifest mismatch.
            for info in infos:
                _zip_kind(info)
            if MANIFEST_MEMBER not in info_map:
                raise CorruptSnapshotError("snapshot manifest is missing")
            if _zip_kind(info_map[MANIFEST_MEMBER]) != "file":
                raise UnsafeArchiveError("snapshot manifest is not a regular file")
            if info_map[MANIFEST_MEMBER].file_size > 64 * 1024 * 1024:
                raise CorruptSnapshotError("snapshot manifest is unreasonably large")
            try:
                manifest = json.loads(bundle.read(info_map[MANIFEST_MEMBER]).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CorruptSnapshotError("snapshot manifest is not valid UTF-8 JSON") from exc
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError) as exc:
        if isinstance(exc, SnapshotError):
            raise
        raise CorruptSnapshotError(f"snapshot archive cannot be read: {exc}") from exc
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema", "root_mode", "entries", "tree_sha256", "total_file_bytes"
    }:
        raise CorruptSnapshotError("snapshot manifest fields are incomplete or unknown")
    if manifest.get("schema") != SCHEMA:
        raise CorruptSnapshotError("unsupported snapshot manifest schema")
    entries = _validate_manifest_entries(manifest["entries"])
    root_mode = manifest.get("root_mode")
    if (
        not isinstance(root_mode, int)
        or isinstance(root_mode, bool)
        or not 0 <= root_mode <= 0o7777
    ):
        raise CorruptSnapshotError("snapshot manifest root mode is invalid")
    tree_digest = manifest.get("tree_sha256")
    if not isinstance(tree_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", tree_digest):
        raise CorruptSnapshotError("snapshot manifest tree hash is invalid")
    if tree_digest != _tree_sha(entries, root_mode):
        raise CorruptSnapshotError("snapshot manifest tree hash is invalid")
    total = sum(e["size"] for e in entries if e["kind"] == "file")
    declared_total = manifest.get("total_file_bytes")
    if not isinstance(declared_total, int) or isinstance(declared_total, bool) \
            or declared_total < 0 or declared_total != total:
        raise CorruptSnapshotError("snapshot manifest byte count is invalid")
    if expected_manifest is not None and _canonical_json(manifest) != _canonical_json(
        expected_manifest
    ):
        raise CorruptSnapshotError("embedded manifest does not match snapshot identity")
    expected_members = {MANIFEST_MEMBER}
    for entry in entries:
        expected_members.add(PAYLOAD_PREFIX + entry["path"])
    if set(info_map) != expected_members:
        extra = sorted(set(info_map) - expected_members)
        missing = sorted(expected_members - set(info_map))
        raise CorruptSnapshotError(
            f"archive members do not match manifest; extra={extra[:3]}, missing={missing[:3]}"
        )
    for entry in entries:
        info = info_map[PAYLOAD_PREFIX + entry["path"]]
        if _zip_kind(info) != entry["kind"]:
            raise UnsafeArchiveError(f"archive member type disagrees: {entry['path']}")
        if entry["kind"] == "file" and info.file_size != entry["size"]:
            raise CorruptSnapshotError(f"archive member size disagrees: {entry['path']}")
    return path, manifest, info_map


def validate_snapshot(snapshot: SnapshotRef) -> Dict[str, Any]:
    """Validate structure and identity without extracting the archive."""
    path, manifest, _ = _read_archive(snapshot)
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "manifest": manifest,
    }


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(str(path)).free


def _contained(root: Path, child: Path) -> None:
    try:
        child.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise UnsafeArchiveError(f"archive path escapes staged candidate: {child}") from exc


def _extract_candidate(archive: Path, manifest: Mapping[str, Any],
                       info_map: Mapping[str, zipfile.ZipInfo],
                       candidate: Path) -> None:
    entries = manifest["entries"]
    with zipfile.ZipFile(str(archive), "r") as bundle:
        for entry in entries:
            if entry["kind"] != "dir":
                continue
            dest = candidate.joinpath(*PurePosixPath(entry["path"]).parts)
            _contained(candidate, dest)
            dest.mkdir(parents=True, exist_ok=False)
        for entry in entries:
            if entry["kind"] != "file":
                continue
            dest = candidate.joinpath(*PurePosixPath(entry["path"]).parts)
            _contained(candidate, dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            written = 0
            with bundle.open(info_map[PAYLOAD_PREFIX + entry["path"]], "r") as src, \
                    dest.open("xb") as out:
                while True:
                    chunk = src.read(_CHUNK)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > entry["size"]:
                        raise CorruptSnapshotError(
                            f"archive member exceeds manifest size: {entry['path']}"
                        )
                    digest.update(chunk)
                    out.write(chunk)
            if written != entry["size"] or digest.hexdigest() != entry["sha256"]:
                raise CorruptSnapshotError(
                    f"archive member hash disagrees: {entry['path']}"
                )
            os.chmod(str(dest), entry["mode"])
        # Apply directory modes only after their children exist.  A legitimate
        # snapshot may contain read-only directories that cannot be populated
        # after their final permissions are installed.
        directories = [entry for entry in entries if entry["kind"] == "dir"]
        for entry in sorted(
            directories, key=lambda item: len(PurePosixPath(item["path"]).parts),
            reverse=True,
        ):
            dest = candidate.joinpath(*PurePosixPath(entry["path"]).parts)
            os.chmod(str(dest), entry["mode"])
    actual = _scan_tree(candidate)
    if (
        actual != entries
        or _tree_sha(actual, manifest["root_mode"]) != manifest["tree_sha256"]
    ):
        raise CorruptSnapshotError("staged candidate does not exactly match snapshot")
    os.chmod(str(candidate), manifest["root_mode"])


def _unique_sibling(root: Path, suffix: str) -> Path:
    for number in range(10000):
        ending = suffix if number == 0 else f"{suffix}-{number}"
        candidate = root.with_name(root.name + ending)
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    raise RestoreError("no collision-free sibling path is available")


def restore_snapshot(root: Union[str, os.PathLike], snapshot: SnapshotRef,
                     *, reserve_bytes: int = 1024 * 1024,
                     interrupt: InterruptHook = None) -> Dict[str, Any]:
    """Restore exactly, staging beside ``root`` and preserving the old live tree.

    ``interrupt`` is a narrow fault-injection hook.  It is called at
    ``after-stage``, ``after-live-move``, and ``after-install``.  Exceptions from
    the hook exercise the same recovery path as an operating-system failure.
    """
    live_input = Path(root).expanduser().absolute()
    if live_input.is_symlink() or not live_input.is_dir():
        raise RestoreError(f"live root must be a real directory: {live_input}")
    live = live_input.resolve()
    if not isinstance(reserve_bytes, int) or isinstance(reserve_bytes, bool) or reserve_bytes < 0:
        raise ValueError("reserve_bytes must be a non-negative integer")
    archive, manifest, info_map = _read_archive(snapshot)
    try:
        archive.relative_to(live)
    except ValueError:
        pass
    else:
        raise RestoreError("snapshot archive must be outside the live tree")
    try:
        current = _scan_tree(live)
    except SnapshotError:
        current = None
    current_root_mode = stat.S_IMODE(live.stat().st_mode)
    if current is not None and _tree_sha(current, current_root_mode) == manifest["tree_sha256"] \
            and current == manifest["entries"]:
        return {
            "status": "already-restored",
            "path": str(live),
            "tree_sha256": manifest["tree_sha256"],
            "previous_tree": None,
        }
    required = manifest["total_file_bytes"] + reserve_bytes
    if _free_bytes(live.parent) < required:
        raise InsufficientStagingError(
            f"safe sibling staging needs {required} free bytes"
        )
    candidate = Path(tempfile.mkdtemp(prefix=f".{live.name}.restore-", dir=str(live.parent)))
    previous: Optional[Path] = None
    installed = False
    failed_install: Optional[Path] = None
    try:
        if candidate.stat().st_dev != live.stat().st_dev:
            raise InsufficientStagingError("sibling staging is not on the live filesystem")
        _extract_candidate(archive, manifest, info_map, candidate)
        if interrupt:
            interrupt("after-stage")
        previous = _unique_sibling(live, ".pre-restore")
        os.rename(str(live), str(previous))
        try:
            if interrupt:
                interrupt("after-live-move")
            os.rename(str(candidate), str(live))
            installed = True
            if interrupt:
                interrupt("after-install")
            final = _scan_tree(live)
            final_root_mode = stat.S_IMODE(live.stat().st_mode)
            if (
                final != manifest["entries"]
                or _tree_sha(final, final_root_mode) != manifest["tree_sha256"]
            ):
                raise RestoreError("post-restore tree hash does not match snapshot")
        except BaseException:
            if installed:
                failed_install = _unique_sibling(live, ".failed-restore")
                os.rename(str(live), str(failed_install))
                installed = False
            if previous.exists() and not live.exists():
                os.rename(str(previous), str(live))
                previous = None
            raise
    except BaseException:
        if candidate.exists():
            shutil.rmtree(str(candidate), ignore_errors=True)
        raise
    return {
        "status": "restored",
        "path": str(live),
        "tree_sha256": manifest["tree_sha256"],
        "previous_tree": str(previous) if previous is not None else None,
        "failed_candidate": str(failed_install) if failed_install is not None else None,
    }


def revert_restoration(root: Union[str, os.PathLike],
                       previous_tree: Union[str, os.PathLike]) -> Dict[str, str]:
    """Put a preserved pre-restore sibling back after a semantic gate fails."""
    live = _resolved_parent_path(root)
    previous = _resolved_parent_path(previous_tree)
    if live.is_symlink() or previous.is_symlink():
        raise RestoreError("semantic rollback refuses symbolic-link roots")
    if not live.is_dir() or not previous.is_dir():
        raise RestoreError("semantic rollback needs both live and previous trees")
    if live.parent != previous.parent or not previous.name.startswith(
        live.name + ".pre-restore"
    ):
        raise RestoreError("previous tree is not the expected preserved sibling")
    failed = _unique_sibling(live, ".failed-validation")
    os.rename(str(live), str(failed))
    try:
        os.rename(str(previous), str(live))
    except BaseException:
        os.rename(str(failed), str(live))
        raise
    return {"restored_previous": str(live), "failed_candidate": str(failed)}
