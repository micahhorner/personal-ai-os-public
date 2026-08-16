"""Shared, fail-closed filesystem containment for mutating CLI commands.

Read-only commands may inspect explicit external inputs.  A mutating command
uses :func:`preflight_contained_regular_files`, which holds no-follow directory
descriptors from preflight through read, staging, commit, and rollback.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import stat
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Iterable, Mapping, Sequence


class SafePathError(RuntimeError):
    """A proposed filesystem mutation was refused or could not recover safely."""


@dataclass(frozen=True)
class ContainedFile:
    path: str
    relpath: str
    parent_parts: tuple[str, ...]
    name: str
    parent_fd: int
    parent_device: int
    parent_inode: int
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class BatchReplaceResult:
    committed: bool
    durable: bool
    cleanup_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReadOnlyFile:
    path: str
    device: int
    inode: int
    mode: int
    data: bytes
    digest: str
    max_bytes: int | None = None

    def reprove(self) -> None:
        current = read_regular_file(self.path, max_bytes=self.max_bytes)
        if ((current.device, current.inode, current.mode, current.digest)
                != (self.device, self.inode, self.mode, self.digest)):
            raise SafePathError(f"read-only input changed after preflight: {self.path}")


@dataclass(frozen=True)
class TreeFile:
    relpath: str
    parent_parts: tuple[str, ...]
    name: str
    parent_device: int
    parent_inode: int
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int


class ReadOnlyTree:
    """A no-follow external directory tree held by its root descriptor."""

    def __init__(self, path: str, root_fd: int):
        self.path = path
        self.root_fd = root_fd
        self.files: dict[str, TreeFile] = {}
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        os.close(self.root_fd)

    def _reprove_root(self) -> None:
        fresh = _open_absolute_directory(self.path)
        try:
            if _identity(os.fstat(fresh)) != _identity(os.fstat(self.root_fd)):
                raise SafePathError("source root changed after preflight")
        finally:
            os.close(fresh)

    def walk(self, *, prune=None) -> tuple[list[str], list[str]]:
        """Enumerate regular files/directories without following any link."""
        self.files = {}
        directories = []

        def descend(fd: int, parts: tuple[str, ...]) -> None:
            entries = sorted(os.listdir(fd))
            aliases = {}
            for name in entries:
                key = unicodedata.normalize("NFC", name).casefold()
                if key in aliases:
                    raise SafePathError(
                        "source tree contains a case/Unicode collision: "
                        f"{'/'.join(parts + (aliases[key],))} and "
                        f"{'/'.join(parts + (name,))}"
                    )
                aliases[key] = name
            for name in entries:
                rel = "/".join(parts + (name,))
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    raise SafePathError(f"source tree contains a symlink: {rel}")
                if stat.S_ISDIR(info.st_mode):
                    if prune is not None and prune(rel):
                        continue
                    child = os.open(
                        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                    )
                    try:
                        opened = os.fstat(child)
                        if _identity(opened) != _identity(info):
                            raise SafePathError(f"source directory changed while opening: {rel}")
                        directories.append(rel)
                        descend(child, parts + (name,))
                    finally:
                        os.close(child)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise SafePathError(f"source tree member is not a regular file: {rel}")
                parent_info = os.fstat(fd)
                self.files[rel] = TreeFile(
                    rel, parts, name, int(parent_info.st_dev), int(parent_info.st_ino),
                    int(info.st_dev), int(info.st_ino), stat.S_IMODE(info.st_mode),
                    int(info.st_size), int(info.st_mtime_ns),
                )

        descend(self.root_fd, ())
        return sorted(self.files), sorted(directories)

    def read_files(self, relpaths: Iterable[str], *, max_file_bytes: int,
                   max_total_bytes: int) -> dict[str, bytes]:
        if self._closed:
            raise SafePathError("source tree is already closed")
        if max_file_bytes < 0 or max_total_bytes < 0:
            raise SafePathError("source byte limits must be non-negative")
        payloads = {}
        total = 0
        for index, rel in enumerate(relpaths):
            record = self.files.get(rel.replace(os.sep, "/"))
            if record is None:
                raise SafePathError(f"source member was not safely enumerated: {rel}")
            if record.size > max_file_bytes or total + record.size > max_total_bytes:
                raise SafePathError(f"source input size exceeds its safety budget: {record.relpath}")
            _mutation_boundary("before-source-read", index, None)
            try:
                self._reprove_root()
            except (OSError, SafePathError) as exc:
                raise SafePathError(
                    f"source root or ancestor changed or became unsafe: {self.path}"
                ) from exc
            try:
                parent = _open_parent(self.root_fd, record.parent_parts)
            except (OSError, SafePathError) as exc:
                raise SafePathError(
                    f"source parent changed, disappeared, or became unsafe: {record.relpath}"
                ) from exc
            try:
                parent_info = os.fstat(parent)
                if _identity(parent_info) != (record.parent_device, record.parent_inode):
                    raise SafePathError(f"source parent changed after enumeration: {record.relpath}")
                current = os.stat(record.name, dir_fd=parent, follow_symlinks=False)
                if (not stat.S_ISREG(current.st_mode)
                        or _identity(current) != (record.device, record.inode)):
                    raise SafePathError(f"source member changed after enumeration: {record.relpath}")
                fd = os.open(record.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                try:
                    opened = os.fstat(fd)
                    if _identity(opened) != (record.device, record.inode):
                        raise SafePathError(f"source member changed while opening: {record.relpath}")
                    chunks = []
                    read_total = 0
                    while True:
                        request = min(1024 * 1024, max_file_bytes - read_total + 1,
                                      max_total_bytes - total - read_total + 1)
                        chunk = os.read(fd, max(1, request))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        read_total += len(chunk)
                        if (read_total > max_file_bytes
                                or total + read_total > max_total_bytes):
                            raise SafePathError(
                                f"source input size exceeds its safety budget: {record.relpath}"
                            )
                    after = os.fstat(fd)
                finally:
                    os.close(fd)
                if ((current.st_size, current.st_mtime_ns, _identity(current))
                        != (after.st_size, after.st_mtime_ns, _identity(after))):
                    raise SafePathError(f"source member changed while reading: {record.relpath}")
                payloads[record.relpath] = b"".join(chunks)
                total += read_total
            finally:
                os.close(parent)
        return payloads

    def snapshot(self, *, max_file_bytes: int,
                 max_total_bytes: int) -> tuple[dict[str, bytes], str]:
        """Return one stable, no-follow byte snapshot and its tree proof.

        The digest is taken on both sides of the bounded reads.  This catches
        additions, removals, metadata changes, and replacements that a list of
        the initially enumerated files alone could miss.
        """
        relpaths, _directories = self.walk()
        before = _tree_digest_fd(self.root_fd)
        payloads = self.read_files(
            relpaths,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )
        after = _tree_digest_fd(self.root_fd)
        if after != before:
            raise SafePathError("source tree changed while taking its byte snapshot")
        self._reprove_root()
        return payloads, before


def _tree_digest_fd(root_fd: int, *, markdown_only: bool = False) -> str:
    """Hash one held tree while rejecting non-portable or unsafe members."""
    digest = hashlib.sha256()
    inodes: dict[tuple[int, int], str] = {}

    def descend(fd: int, parts: tuple[str, ...]) -> None:
        entries = sorted(os.listdir(fd))
        aliases = {}
        for name in entries:
            key = unicodedata.normalize("NFC", name).casefold()
            if key in aliases:
                raise SafePathError(
                    "tree contains a case/Unicode collision: "
                    f"{'/'.join(parts + (aliases[key],))} and "
                    f"{'/'.join(parts + (name,))}"
                )
            aliases[key] = name
        for name in entries:
            rel = "/".join(parts + (name,))
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise SafePathError(f"tree contains a symlink: {rel}")
            if stat.S_ISDIR(info.st_mode):
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                try:
                    if _identity(os.fstat(child)) != _identity(info):
                        raise SafePathError(f"tree directory changed while opening: {rel}")
                    digest.update(f"D\0{rel}\0{stat.S_IMODE(info.st_mode):o}\0".encode())
                    descend(child, parts + (name,))
                finally:
                    os.close(child)
                continue
            included = not markdown_only or name.lower().endswith(".md")
            if not stat.S_ISREG(info.st_mode):
                if included:
                    raise SafePathError(f"tree member is not a regular file: {rel}")
                continue
            if not included:
                continue
            identity = _identity(info)
            if int(info.st_nlink) != 1 or identity in inodes:
                raise SafePathError(f"tree member is hardlinked: {rel}")
            inodes[identity] = rel
            file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                opened = os.fstat(file_fd)
                if _identity(opened) != identity or not stat.S_ISREG(opened.st_mode):
                    raise SafePathError(f"tree member changed while opening: {rel}")
                content = hashlib.sha256()
                while True:
                    chunk = os.read(file_fd, 1024 * 1024)
                    if not chunk:
                        break
                    content.update(chunk)
                after = os.fstat(file_fd)
                if ((opened.st_size, opened.st_mtime_ns, _identity(opened))
                        != (after.st_size, after.st_mtime_ns, _identity(after))):
                    raise SafePathError(f"tree member changed while reading: {rel}")
            finally:
                os.close(file_fd)
            digest.update(
                f"F\0{rel}\0{identity[0]}\0{identity[1]}\0"
                f"{stat.S_IMODE(info.st_mode):o}\0".encode()
            )
            digest.update(content.digest())

    descend(root_fd, ())
    return digest.hexdigest()


def safe_tree_digest(path: str, *, markdown_only: bool = False) -> str:
    """Return a no-follow content/identity digest for a real directory tree."""
    fd = _open_absolute_directory(path)
    try:
        return _tree_digest_fd(fd, markdown_only=markdown_only)
    finally:
        os.close(fd)


def _canonical_platform_path(path: str) -> str:
    absolute = os.path.abspath(path)
    # macOS exposes these historical system aliases; canonicalize only these
    # fixed platform prefixes, never arbitrary caller-controlled symlinks.
    if sys.platform == "darwin":
        for alias, canonical in (("/var", "/private/var"), ("/tmp", "/private/tmp")):
            if absolute == alias or absolute.startswith(alias + os.sep):
                absolute = canonical + absolute[len(alias):]
                break
    return absolute


def _open_absolute_directory(path: str) -> int:
    absolute = _canonical_platform_path(path)
    parts = Path(absolute).parts
    current = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[1:]:
            if not _portable_entry(os.listdir(current), part, "source root"):
                raise SafePathError(f"source root component is missing: {part}")
            nxt = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
            )
            os.close(current)
            current = nxt
        return current
    except BaseException:
        os.close(current)
        raise


def open_readonly_tree(path: str) -> ReadOnlyTree:
    """Open an absolute directory without following its declared ancestors."""
    absolute = _canonical_platform_path(path)
    return ReadOnlyTree(absolute, _open_absolute_directory(absolute))


def _mutation_boundary(event: str, index: int, target: ContainedFile | None) -> None:
    """No-op fault-injection seam used by the path-transaction tests."""
    del event, index, target


def _platform_supported() -> bool:
    """The containment contract needs POSIX dir-fd and no-follow operations."""
    required = (os.open, os.stat, os.unlink, os.mkdir, os.rmdir, os.link)
    return bool(
        os.name == "posix"
        and getattr(os, "O_NOFOLLOW", 0)
        and getattr(os, "O_DIRECTORY", 0)
        and hasattr(os, "fchmod")
        and all(fn in os.supports_dir_fd for fn in required)
        and os.stat in os.supports_follow_symlinks
        and os.link in os.supports_follow_symlinks
    )


def _collision_key(relpath: str) -> str:
    return "/".join(
        unicodedata.normalize("NFC", part).casefold()
        for part in relpath.replace(os.sep, "/").split("/")
    )


def _inside(root: str, path: str) -> bool:
    try:
        return os.path.commonpath((root, path)) == root
    except ValueError:
        return False


def safe_relative_path(value: str, label: str = "output path") -> str:
    """Return one canonical relative POSIX path or fail closed."""
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise SafePathError(f"{label} must be a contained relative POSIX path")
    if unicodedata.normalize("NFC", value) != value:
        raise SafePathError(f"{label} must use NFC-normalized Unicode")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise SafePathError(f"{label} must be a contained relative POSIX path")
    if any(part in ("", ".", "..") for part in posix.parts) or posix.as_posix() != value:
        raise SafePathError(f"{label} must be a contained relative POSIX path")
    return value


def read_regular_file(path: str, *, max_bytes: int | None = None) -> ReadOnlyFile:
    """Read an explicit input without following any path component."""
    if max_bytes is not None and max_bytes < 0:
        raise SafePathError("input byte limit must be non-negative")
    absolute = _canonical_platform_path(path)
    parent_path, name = os.path.split(absolute)
    try:
        parent_fd = _open_absolute_directory(parent_path)
    except OSError as exc:
        raise SafePathError(f"input cannot be opened safely: {path} ({exc})") from exc
    try:
        parent_identity = _identity(os.fstat(parent_fd))
        if not _portable_entry(os.listdir(parent_fd), name, "input"):
            raise SafePathError(f"input is unavailable: {path}")
        listed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_ISLNK(listed.st_mode):
            raise SafePathError(f"input is a symlink: {path}")
        if not stat.S_ISREG(listed.st_mode):
            raise SafePathError(f"input is not a regular file: {path}")
        if max_bytes is not None and listed.st_size > max_bytes:
            raise SafePathError(f"input size exceeds the {max_bytes}-byte safety limit: {path}")
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError as exc:
            raise SafePathError(f"input cannot be opened safely: {path} ({exc})") from exc
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or _identity(before) != _identity(listed):
                raise SafePathError(f"input changed while opening: {path}")
            if max_bytes is not None and before.st_size > max_bytes:
                raise SafePathError(f"input size exceeds the {max_bytes}-byte safety limit: {path}")
            chunks = []
            total = 0
            while True:
                request = 1024 * 1024
                if max_bytes is not None:
                    request = min(request, max_bytes - total + 1)
                chunk = os.read(fd, request)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    raise SafePathError(f"input size exceeds the {max_bytes}-byte safety limit: {path}")
            after = os.fstat(fd)
        finally:
            os.close(fd)
        try:
            fresh_parent = _open_absolute_directory(parent_path)
        except OSError as exc:
            raise SafePathError(
                f"input parent changed or became unsafe while reading: {path} ({exc})"
            ) from exc
        try:
            if _identity(os.fstat(fresh_parent)) != parent_identity:
                raise SafePathError(f"input parent changed while reading: {path}")
        finally:
            os.close(fresh_parent)
    except OSError as exc:
        raise SafePathError(f"input changed or became unavailable: {path} ({exc})") from exc
    finally:
        os.close(parent_fd)
    if ((before.st_size, before.st_mtime_ns, _identity(before))
            != (after.st_size, after.st_mtime_ns, _identity(after))):
        raise SafePathError(f"input changed while reading: {path}")
    data = b"".join(chunks)
    return ReadOnlyFile(
        absolute, int(after.st_dev), int(after.st_ino), stat.S_IMODE(after.st_mode),
        data, hashlib.sha256(data).hexdigest(), max_bytes,
    )


def _open_parent(root_fd: int, parent_parts: Sequence[str]) -> int:
    """Traverse from the held root descriptor; no pathname ancestor is followed."""
    current = os.dup(root_fd)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        for part in parent_parts:
            if not _portable_entry(os.listdir(current), part, "contained path"):
                raise FileNotFoundError(f"contained path component is missing: {part}")
            nxt = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = nxt
        return current
    except BaseException:
        os.close(current)
        raise


def _identity(info) -> tuple[int, int]:
    return int(info.st_dev), int(info.st_ino)


class ContainedBatch:
    """A held, preflighted write set.  Call :meth:`close` in ``finally``."""

    def __init__(self, root: str, root_fd: int, targets: list[ContainedFile],
                 require_writable: bool = True):
        self.root = root
        self.root_fd = root_fd
        self.targets = targets
        self._closed = False
        self._require_writable = require_writable
        self._original: dict[str, bytes] = {}
        self._digest: dict[str, str] = {}

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for target in self.targets:
            try:
                os.close(target.parent_fd)
            except OSError:
                pass
        try:
            os.close(self.root_fd)
        except OSError:
            pass

    def _reprove_parent(self, target: ContainedFile) -> None:
        try:
            fresh = _open_parent(self.root_fd, target.parent_parts)
        except OSError as exc:
            raise SafePathError(
                f"annotation parent became missing, unsafe, or symlinked: "
                f"{target.relpath} ({exc})"
            ) from exc
        try:
            if _identity(os.fstat(fresh)) != (target.parent_device, target.parent_inode):
                raise SafePathError(
                    f"annotation parent changed after preflight: {target.relpath}"
                )
        finally:
            os.close(fresh)

    def _target_stat(self, target: ContainedFile):
        try:
            info = os.stat(target.name, dir_fd=target.parent_fd, follow_symlinks=False)
        except OSError as exc:
            raise SafePathError(
                f"annotation target became unavailable: {target.relpath} ({exc})"
            ) from exc
        if not stat.S_ISREG(info.st_mode) or _identity(info) != (target.device, target.inode):
            raise SafePathError(f"annotation target changed after preflight: {target.relpath}")
        current_mode = stat.S_IMODE(info.st_mode)
        if self._require_writable and current_mode & 0o222 == 0:
            raise SafePathError(f"annotation target is not writable: {target.relpath}")
        if self._require_writable and int(info.st_nlink) != 1:
            raise SafePathError(
                f"annotation target is a hardlinked alias identifying the same file: {target.relpath}"
            )
        if current_mode != target.mode:
            raise SafePathError(f"annotation target permissions changed after preflight: {target.relpath}")
        return info

    def _read(self, target: ContainedFile) -> bytes:
        self._reprove_parent(target)
        before = self._target_stat(target)
        flags = os.O_RDONLY | os.O_NOFOLLOW
        try:
            fd = os.open(target.name, flags, dir_fd=target.parent_fd)
        except OSError as exc:
            raise SafePathError(f"annotation target cannot be read: {target.relpath} ({exc})") from exc
        try:
            opened = os.fstat(fd)
            if _identity(opened) != (target.device, target.inode):
                raise SafePathError(f"annotation target changed while opening: {target.relpath}")
            chunks = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(fd)
        finally:
            os.close(fd)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise SafePathError(f"annotation target changed while reading: {target.relpath}")
        return b"".join(chunks)

    def read_texts(self) -> dict[str, str]:
        """Read every target exactly once through its held no-follow parent."""
        texts = {}
        for target in self.targets:
            raw = self._read(target)
            try:
                texts[target.path] = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SafePathError(f"annotation target is not UTF-8: {target.relpath}") from exc
            self._original[target.relpath] = raw
            self._digest[target.relpath] = hashlib.sha256(raw).hexdigest()
        return texts

    def read_bytes(self, *, max_bytes: int | None = None) -> dict[str, bytes]:
        if max_bytes is not None and max_bytes < 0:
            raise SafePathError("input byte limit must be non-negative")
        payloads = {}
        for target in self.targets:
            if max_bytes is not None and target.size > max_bytes:
                raise SafePathError(
                    f"input exceeds the {max_bytes}-byte safety limit: {target.relpath}"
                )
            raw = self._read(target)
            if max_bytes is not None and len(raw) > max_bytes:
                raise SafePathError(
                    f"input exceeds the {max_bytes}-byte safety limit: {target.relpath}"
                )
            payloads[target.path] = raw
            self._original[target.relpath] = raw
            self._digest[target.relpath] = hashlib.sha256(raw).hexdigest()
        return payloads

    def _reprove_content(self, target: ContainedFile) -> None:
        if target.relpath not in self._digest:
            raise SafePathError(f"annotation target was not bound by a safe read: {target.relpath}")
        raw = self._read(target)
        if hashlib.sha256(raw).hexdigest() != self._digest[target.relpath]:
            raise SafePathError(f"annotation target content changed after reading: {target.relpath}")

    def reprove(self) -> None:
        """Re-prove every safely read member without changing it."""
        for target in self.targets:
            self._reprove_parent(target)
            self._reprove_content(target)

    @staticmethod
    def _write_temp(target: ContainedFile, name: str, payload: bytes) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        fd = None
        created = False
        try:
            fd = os.open(name, flags, target.mode, dir_fd=target.parent_fd)
            created = True
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("incomplete staged write")
                view = view[written:]
            os.fchmod(fd, target.mode)
            os.fsync(fd)
        except BaseException:
            if created:
                try:
                    os.unlink(name, dir_fd=target.parent_fd)
                except OSError:
                    pass
            raise
        finally:
            if fd is not None:
                os.close(fd)

    @staticmethod
    def _unlink(target: ContainedFile, name: str) -> str | None:
        try:
            os.unlink(name, dir_fd=target.parent_fd)
            return None
        except FileNotFoundError:
            return None
        except OSError as exc:
            return f"{target.relpath}: {exc}"

    def atomic_replace_many(
        self, replacements: Mapping[str, bytes], *,
        read_only_inputs: Sequence[ReadOnlyFile] = (),
    ) -> BatchReplaceResult:
        """Stage, commit, and durably recover a complete target set.

        Any failure through commit or the first durability barrier restores all
        original bytes.  A rollback failure is reported as INCOMPLETE, never as
        a safe refusal.  Cleanup after a durable commit is truthful but does not
        pretend the committed content was rolled back.
        """
        if self._closed:
            raise SafePathError("annotation batch is already closed")
        expected = {target.relpath for target in self.targets}
        if set(replacements) != expected:
            raise SafePathError("annotation replacement set does not match preflighted targets")

        staged: dict[str, str] = {}
        backups: dict[str, str] = {}
        token = secrets.token_hex(8)
        try:
            # Re-prove every binding before creating even a temporary file.
            for target in self.targets:
                self._reprove_parent(target)
                self._reprove_content(target)
            for readonly in read_only_inputs:
                readonly.reprove()
            for index, target in enumerate(self.targets):
                stage = f".{target.name}.aios-{token}-{index}.stage"
                backup = f".{target.name}.aios-{token}-{index}.backup"
                _mutation_boundary("before-stage", index, target)
                self._write_temp(target, stage, replacements[target.relpath])
                staged[target.relpath] = stage
                self._write_temp(target, backup, self._original[target.relpath])
                backups[target.relpath] = backup
                _mutation_boundary("after-stage", index, target)

            _mutation_boundary("before-final-reproof", -1, None)
            for target in self.targets:
                self._reprove_parent(target)
                self._reprove_content(target)
            for readonly in read_only_inputs:
                readonly.reprove()

            for index, target in enumerate(self.targets):
                _mutation_boundary("before-commit", index, target)
                self._reprove_parent(target)
                self._reprove_content(target)
                for readonly in read_only_inputs:
                    readonly.reprove()
                os.replace(
                    staged[target.relpath], target.name,
                    src_dir_fd=target.parent_fd, dst_dir_fd=target.parent_fd,
                )
                staged.pop(target.relpath, None)
                _mutation_boundary("after-commit", index, target)
            for target in self.targets:
                os.fsync(target.parent_fd)
            for readonly in read_only_inputs:
                readonly.reprove()
        except BaseException as exc:
            rollback_errors = []
            retain_backups = set()
            for index, target in reversed(list(enumerate(self.targets))):
                try:
                    _mutation_boundary("before-rollback", index, target)
                    try:
                        current = os.stat(
                            target.name, dir_fd=target.parent_fd, follow_symlinks=False
                        )
                        needs_restore = _identity(current) != (target.device, target.inode)
                    except FileNotFoundError:
                        needs_restore = True
                    if needs_restore:
                        backup = backups.get(target.relpath)
                        if backup is None:
                            raise SafePathError("original backup is unavailable")
                        os.replace(
                            backup, target.name,
                            src_dir_fd=target.parent_fd, dst_dir_fd=target.parent_fd,
                        )
                        backups.pop(target.relpath, None)
                    _mutation_boundary("after-rollback", index, target)
                except BaseException as rollback_exc:
                    retain_backups.add(target.relpath)
                    rollback_errors.append(f"{target.relpath}: {rollback_exc}")
            for target in self.targets:
                try:
                    os.fsync(target.parent_fd)
                except OSError as rollback_exc:
                    rollback_errors.append(f"{target.relpath} durability: {rollback_exc}")
            for target in self.targets:
                stage = staged.pop(target.relpath, None)
                backup = backups.pop(target.relpath, None)
                if stage:
                    self._unlink(target, stage)
                if backup:
                    if target.relpath in retain_backups:
                        rollback_errors.append(
                            f"{target.relpath}: recovery backup retained as {backup}"
                        )
                    else:
                        self._unlink(target, backup)
            if rollback_errors:
                raise SafePathError(
                    "annotation transaction failed and ROLLBACK IS INCOMPLETE: "
                    + "; ".join(rollback_errors)
                    + f"; original failure: {exc}"
                ) from exc
            raise SafePathError(
                f"annotation transaction failed; all targets rolled back: {exc}"
            ) from exc

        cleanup = []
        for target in self.targets:
            backup = backups.pop(target.relpath, None)
            if backup:
                warning = self._unlink(target, backup)
                if warning:
                    cleanup.append(warning)
        for target in self.targets:
            try:
                os.fsync(target.parent_fd)
            except OSError as exc:
                cleanup.append(f"{target.relpath} cleanup durability: {exc}")
        return BatchReplaceResult(True, True, tuple(cleanup))


def preflight_contained_regular_files(
    root: str, paths: Iterable[str], *, require_writable: bool = True
) -> ContainedBatch:
    """Preflight and hold contained regular files for safe reads or mutation."""
    if not _platform_supported():
        raise SafePathError(
            "safe annotation is unsupported on this OS/Python filesystem backend; "
            "refusing to fall back to pathname writes"
        )
    supplied_root = os.path.abspath(root)
    if os.path.islink(supplied_root) or not os.path.isdir(supplied_root):
        raise SafePathError("vault root must be a real directory, not a symlink")
    root_fd = os.open(supplied_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    opened: list[int] = []
    try:
        root_info = os.fstat(root_fd)
        if not stat.S_ISDIR(root_info.st_mode):
            raise SafePathError("vault root is not a directory")
        targets: list[ContainedFile] = []
        keys: dict[str, str] = {}
        inodes: dict[tuple[int, int], str] = {}
        for raw in paths:
            absolute = os.path.abspath(raw)
            if not _inside(supplied_root, absolute):
                raise SafePathError(f"annotation target is outside the vault: {raw}")
            rel = os.path.relpath(absolute, supplied_root)
            if rel in ("", ".", "..") or rel.startswith(".." + os.sep):
                raise SafePathError(f"annotation target is outside the vault: {raw}")
            parts = Path(rel).parts
            if not parts or any(part in ("", ".", "..") for part in parts):
                raise SafePathError(f"annotation target is not canonical: {raw}")
            key = _collision_key(rel)
            if key in keys:
                raise SafePathError(
                    "annotation targets contain a case/Unicode alias: "
                    f"{keys[key]} and {rel}"
                )
            keys[key] = rel
            try:
                parent_fd = _open_parent(root_fd, parts[:-1])
            except OSError as exc:
                raise SafePathError(
                    f"annotation target parent is missing, unsafe, or symlinked: {rel} ({exc})"
                ) from exc
            opened.append(parent_fd)
            parent_info = os.fstat(parent_fd)
            try:
                if not _portable_entry(
                    os.listdir(parent_fd), parts[-1], "annotation target"
                ):
                    raise FileNotFoundError(parts[-1])
                info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
            except OSError as exc:
                raise SafePathError(f"annotation target is unavailable: {rel} ({exc})") from exc
            if stat.S_ISLNK(info.st_mode):
                raise SafePathError(f"annotation target traverses a symlink: {rel}")
            if not stat.S_ISREG(info.st_mode):
                raise SafePathError(f"annotation target is not a regular file: {rel}")
            mode = stat.S_IMODE(info.st_mode)
            if require_writable and mode & 0o222 == 0:
                raise SafePathError(f"annotation target is not writable: {rel}")
            if require_writable and int(info.st_nlink) != 1:
                raise SafePathError(
                    f"annotation target is a hardlinked alias identifying the same file: {rel}"
                )
            identity = _identity(info)
            if identity in inodes:
                raise SafePathError(
                    "annotation targets identify the same file: "
                    f"{inodes[identity]} and {rel}"
                )
            inodes[identity] = rel
            targets.append(ContainedFile(
                path=absolute, relpath=rel, parent_parts=tuple(parts[:-1]),
                name=parts[-1], parent_fd=parent_fd,
                parent_device=int(parent_info.st_dev), parent_inode=int(parent_info.st_ino),
                device=identity[0], inode=identity[1], mode=mode,
                size=int(info.st_size), mtime_ns=int(info.st_mtime_ns),
            ))
        opened.clear()  # ownership transferred to ContainedBatch
        return ContainedBatch(supplied_root, root_fd, targets, require_writable)
    except BaseException:
        for fd in opened:
            try:
                os.close(fd)
            except OSError:
                pass
        os.close(root_fd)
        raise


def _portable_entry(entries: Sequence[str], wanted: str, label: str) -> bool:
    """Whether exact ``wanted`` exists; refuse any portable spelling alias."""
    key = unicodedata.normalize("NFC", wanted).casefold()
    aliases = [entry for entry in entries
               if unicodedata.normalize("NFC", entry).casefold() == key]
    if any(entry != wanted for entry in aliases):
        raise SafePathError(f"{label} has a case/Unicode collision: {wanted}")
    return wanted in aliases


def _preflight_new_parent(root_fd: int, parts: Sequence[str], label: str) -> None:
    current = os.dup(root_fd)
    try:
        for part in parts:
            entries = os.listdir(current)
            if not _portable_entry(entries, part, label):
                return  # the remaining suffix is new by construction
            nxt = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
            )
            os.close(current)
            current = nxt
    except OSError as exc:
        raise SafePathError(f"{label} parent is missing, unsafe, or symlinked ({exc})") from exc
    finally:
        os.close(current)


def _open_or_create_parent(
    root_fd: int, parts: Sequence[str],
    created: list[tuple[tuple[str, ...], str, int]],
) -> int:
    current = os.dup(root_fd)
    walked: list[str] = []
    try:
        for part in parts:
            entries = os.listdir(current)
            exists = _portable_entry(entries, part, "output path")
            if not exists:
                os.mkdir(part, 0o755, dir_fd=current)
                created.append((tuple(walked), part, os.dup(current)))
                os.fsync(current)
            nxt = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
            )
            os.close(current)
            current = nxt
            walked.append(part)
        return current
    except BaseException:
        os.close(current)
        raise


def _remove_created_dirs(root_fd: int, created) -> list[str]:
    del root_fd  # every created directory keeps its original parent descriptor
    errors = []
    for parent_parts, name, parent in reversed(created):
        try:
            os.rmdir(name, dir_fd=parent)
            os.fsync(parent)
        except OSError as exc:
            errors.append(f"{'/'.join(parent_parts + (name,))}: {exc}")
        finally:
            try:
                os.close(parent)
            except OSError:
                pass
    created.clear()
    return errors


def _close_created_dir_fds(created) -> None:
    for _parent_parts, _name, parent in created:
        try:
            os.close(parent)
        except OSError:
            pass
    created.clear()


def _reprove_output_parent(root_fd: int, rel: str, held_fd: int) -> None:
    parts = PurePosixPath(rel).parts[:-1]
    try:
        fresh = _open_parent(root_fd, parts)
    except (OSError, SafePathError) as exc:
        raise SafePathError(
            f"output parent became missing, unsafe, or moved outside the vault: {rel} ({exc})"
        ) from exc
    try:
        if _identity(os.fstat(fresh)) != _identity(os.fstat(held_fd)):
            raise SafePathError(f"output parent changed or moved outside the vault: {rel}")
    finally:
        os.close(fresh)


def _cleanup_output_stage(root_fd: int, stage_fd: int | None, stage_name: str,
                          owned_names: set[str]) -> list[str]:
    """Remove every staging artifact and report any residue truthfully."""
    errors = []
    if stage_fd is not None:
        for name in sorted(owned_names):
            try:
                os.unlink(name, dir_fd=stage_fd)
            except FileNotFoundError:
                pass
            except OSError as exc:
                errors.append(f"staged output {name}: {exc}")
        try:
            os.close(stage_fd)
        except OSError as exc:
            errors.append(f"staging directory close: {exc}")
    try:
        os.rmdir(stage_name, dir_fd=root_fd)
        os.fsync(root_fd)
    except FileNotFoundError:
        pass
    except OSError as exc:
        errors.append(f"staging directory {stage_name}: {exc}")
    return errors


def atomic_create_files(
    root: str,
    writes: Mapping[str, bytes],
    *,
    remove_batch: ContainedBatch | None = None,
    remove_target: ContainedFile | None = None,
    read_only_inputs: Sequence[ReadOnlyFile] = (),
    replace_batch: ContainedBatch | None = None,
    create_dirs: Sequence[str] = (),
) -> BatchReplaceResult:
    """Create/replace a contained set, optionally filing one live input.

    Outputs are new unless preflighted through ``replace_batch``. On failure,
    new outputs disappear, replacements recover their bound old bytes, created
    directories are removed, and a filed source regains its inode and name.
    """
    if not _platform_supported():
        raise SafePathError("contained output transactions are unsupported on this OS backend")
    normalized = {}
    keys = {}
    for raw, payload in writes.items():
        rel = safe_relative_path(raw)
        key = _collision_key(rel)
        if key in keys:
            raise SafePathError(
                f"output write set has a case/Unicode collision: {keys[key]} and {rel}"
            )
        keys[key] = rel
        normalized[rel] = payload
    if not normalized:
        raise SafePathError("output transaction has no files")
    if (remove_batch is None) != (remove_target is None):
        raise SafePathError("internal source removal contract is incomplete")

    replacement_targets = {}
    if replace_batch is not None:
        if replace_batch._closed or os.path.abspath(replace_batch.root) != os.path.abspath(root):
            raise SafePathError("replacement batch is closed or belongs to another root")
        replacement_targets = {target.relpath: target for target in replace_batch.targets}
        if not set(replacement_targets) <= set(normalized):
            raise SafePathError("replacement batch contains a target absent from the write set")
        for target in replacement_targets.values():
            if target.relpath not in replace_batch._original:
                raise SafePathError(
                    f"replacement target was not bound by a safe read: {target.relpath}"
                )

    normalized_dirs = []
    dir_keys = {}
    for raw in create_dirs:
        rel = safe_relative_path(raw, "directory output")
        key = _collision_key(rel)
        if key in dir_keys:
            raise SafePathError(
                f"directory write set has a case/Unicode collision: {dir_keys[key]} and {rel}"
            )
        if key in keys:
            raise SafePathError(f"output path is both a file and directory: {rel}")
        dir_keys[key] = rel
        normalized_dirs.append(rel)

    absolute_root = os.path.abspath(root)
    root_fd = os.open(absolute_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    parent_fds: dict[str, int] = {}
    created_dirs = []
    committed: dict[str, tuple[int, int]] = {}
    replaced: dict[str, tuple[tuple[int, int], str]] = {}
    stage_fd = None
    stage_owned: set[str] = set()
    stage_name = f".aios-output-{secrets.token_hex(10)}"
    source_backup = None
    cleanup = []
    try:
        # Whole write-set preflight occurs before the staging directory exists.
        for rel in normalized:
            parts = PurePosixPath(rel).parts
            _preflight_new_parent(root_fd, parts[:-1], rel)
            try:
                parent = _open_parent(root_fd, parts[:-1])
            except OSError:
                parent = None  # one or more parents are legitimately new
            if parent is not None:
                try:
                    entries = os.listdir(parent)
                    exists = _portable_entry(entries, parts[-1], rel)
                    if exists and rel not in replacement_targets:
                        raise SafePathError(f"output already exists: {rel}")
                    if not exists and rel in replacement_targets:
                        raise SafePathError(f"replacement output disappeared: {rel}")
                finally:
                    os.close(parent)
        for rel in normalized_dirs:
            parts = PurePosixPath(rel).parts
            _preflight_new_parent(root_fd, parts[:-1], rel)
            try:
                parent = _open_parent(root_fd, parts[:-1])
            except OSError:
                parent = None
            if parent is not None:
                try:
                    if _portable_entry(os.listdir(parent), parts[-1], rel):
                        raise SafePathError(f"directory output already exists: {rel}")
                finally:
                    os.close(parent)
        if remove_batch is not None:
            remove_batch._reprove_parent(remove_target)
            remove_batch._reprove_content(remove_target)
        for readonly in read_only_inputs:
            readonly.reprove()
        if replace_batch is not None:
            for target in replacement_targets.values():
                replace_batch._reprove_parent(target)
                replace_batch._reprove_content(target)

        os.mkdir(stage_name, 0o700, dir_fd=root_fd)
        stage_fd = os.open(
            stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
        )
        for index, (rel, payload) in enumerate(normalized.items()):
            mode = replacement_targets[rel].mode if rel in replacement_targets else 0o644
            pseudo = ContainedFile("", rel, (), str(index), stage_fd, 0, 0, 0, 0,
                                   mode, 0, 0)
            ContainedBatch._write_temp(pseudo, str(index), payload)
            stage_owned.add(str(index))
            if rel in replacement_targets:
                backup = f"backup-{index}"
                pseudo = ContainedFile("", rel, (), backup, stage_fd, 0, 0, 0, 0,
                                       replacement_targets[rel].mode, 0, 0)
                ContainedBatch._write_temp(
                    pseudo, backup, replace_batch._original[rel]
                )
                stage_owned.add(backup)

        for rel in sorted(normalized_dirs, key=lambda value: len(PurePosixPath(value).parts)):
            parent = _open_or_create_parent(
                root_fd, PurePosixPath(rel).parts, created_dirs
            )
            os.close(parent)

        _mutation_boundary("before-output-parents", -1, None)
        for rel in normalized:
            parts = PurePosixPath(rel).parts
            parent = _open_or_create_parent(root_fd, parts[:-1], created_dirs)
            entries = os.listdir(parent)
            exists = _portable_entry(entries, parts[-1], rel)
            if exists and rel not in replacement_targets:
                os.close(parent)
                raise SafePathError(f"output appeared after preflight: {rel}")
            if not exists and rel in replacement_targets:
                os.close(parent)
                raise SafePathError(f"replacement output disappeared after preflight: {rel}")
            parent_fds[rel] = parent
            _reprove_output_parent(root_fd, rel, parent)
        if remove_batch is not None:
            remove_batch._reprove_parent(remove_target)
            remove_batch._reprove_content(remove_target)
        for readonly in read_only_inputs:
            readonly.reprove()
        if replace_batch is not None:
            for target in replacement_targets.values():
                replace_batch._reprove_parent(target)
                replace_batch._reprove_content(target)

        for index, rel in enumerate(normalized):
            _mutation_boundary("before-output-commit", index, None)
            _reprove_output_parent(root_fd, rel, parent_fds[rel])
            if remove_batch is not None:
                remove_batch._reprove_parent(remove_target)
                remove_batch._reprove_content(remove_target)
            for readonly in read_only_inputs:
                readonly.reprove()
            staged_info = os.stat(str(index), dir_fd=stage_fd, follow_symlinks=False)
            if rel in replacement_targets:
                target = replacement_targets[rel]
                replace_batch._reprove_parent(target)
                replace_batch._reprove_content(target)
                os.replace(
                    str(index), target.name,
                    src_dir_fd=stage_fd, dst_dir_fd=target.parent_fd,
                )
                replaced[rel] = (_identity(staged_info), f"backup-{index}")
                stage_owned.discard(str(index))
            else:
                os.link(
                    str(index), PurePosixPath(rel).name,
                    src_dir_fd=stage_fd, dst_dir_fd=parent_fds[rel],
                    follow_symlinks=False,
                )
                committed[rel] = _identity(staged_info)
                os.unlink(str(index), dir_fd=stage_fd)
                stage_owned.discard(str(index))
            _mutation_boundary("after-output-commit", index, None)

        for readonly in read_only_inputs:
            readonly.reprove()

        if remove_batch is not None:
            remove_batch._reprove_parent(remove_target)
            remove_batch._reprove_content(remove_target)
            source_backup = f".{remove_target.name}.aios-file-{secrets.token_hex(8)}.backup"
            _mutation_boundary("before-source-file", -1, remove_target)
            remove_batch._reprove_parent(remove_target)
            remove_batch._reprove_content(remove_target)
            os.replace(
                remove_target.name, source_backup,
                src_dir_fd=remove_target.parent_fd, dst_dir_fd=remove_target.parent_fd,
            )
            _mutation_boundary("after-source-file", -1, remove_target)
            remove_batch._reprove_parent(remove_target)

        for fd in parent_fds.values():
            os.fsync(fd)
        if remove_target is not None:
            os.fsync(remove_target.parent_fd)
    except BaseException as exc:
        recovery_errors = []
        if source_backup is not None:
            try:
                os.replace(
                    source_backup, remove_target.name,
                    src_dir_fd=remove_target.parent_fd,
                    dst_dir_fd=remove_target.parent_fd,
                )
                os.fsync(remove_target.parent_fd)
                source_backup = None
                remove_batch._reprove_parent(remove_target)
            except BaseException as restore_exc:
                recovery_errors.append(f"source restore: {restore_exc}")
        for rel in reversed(replaced):
            identity, backup = replaced[rel]
            target = replacement_targets[rel]
            try:
                current = os.stat(
                    target.name, dir_fd=target.parent_fd, follow_symlinks=False
                )
                if _identity(current) != identity:
                    raise SafePathError(
                        f"replacement output was altered before rollback: {rel}"
                    )
                os.replace(
                    backup, target.name,
                    src_dir_fd=stage_fd, dst_dir_fd=target.parent_fd,
                )
                stage_owned.discard(backup)
                os.fsync(target.parent_fd)
                replace_batch._reprove_parent(target)
            except (OSError, SafePathError) as rollback_exc:
                recovery_errors.append(f"{rel}: {rollback_exc}")
        for rel in reversed(committed):
            try:
                current = os.stat(
                    PurePosixPath(rel).name,
                    dir_fd=parent_fds[rel], follow_symlinks=False,
                )
                if _identity(current) != committed[rel]:
                    raise SafePathError(
                        f"committed output was replaced before rollback: {rel}"
                    )
                os.unlink(PurePosixPath(rel).name, dir_fd=parent_fds[rel])
                os.fsync(parent_fds[rel])
                _reprove_output_parent(root_fd, rel, parent_fds[rel])
            except (OSError, SafePathError) as rollback_exc:
                recovery_errors.append(f"{rel}: {rollback_exc}")
        recovery_errors.extend(
            _cleanup_output_stage(root_fd, stage_fd, stage_name, stage_owned)
        )
        stage_fd = None
        recovery_errors.extend(_remove_created_dirs(root_fd, created_dirs))
        if recovery_errors:
            raise SafePathError(
                "output transaction failed and ROLLBACK IS INCOMPLETE: "
                + "; ".join(recovery_errors) + f"; original failure: {exc}"
            ) from exc
        raise SafePathError(f"output transaction failed; prior state restored: {exc}") from exc
    finally:
        for fd in parent_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        _close_created_dir_fds(created_dirs)
        if stage_fd is not None:
            cleanup.extend(
                _cleanup_output_stage(root_fd, stage_fd, stage_name, stage_owned)
            )
            stage_fd = None
        os.close(root_fd)

    if source_backup is not None:
        try:
            os.unlink(source_backup, dir_fd=remove_target.parent_fd)
            os.fsync(remove_target.parent_fd)
        except OSError as exc:
            cleanup.append(
                f"source was filed durably; retained source cleanup artifact "
                f"{source_backup}: {exc}"
            )
    return BatchReplaceResult(True, True, tuple(cleanup))


def _remove_tree_at(parent_fd: int, name: str, expected: tuple[int, int]) -> None:
    """Remove an owned child tree through its held parent without following links."""
    info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or _identity(info) != expected:
        raise SafePathError("owned staging tree changed before cleanup")
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        for child in os.listdir(fd):
            child_info = os.stat(child, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(child_info.st_mode) and not stat.S_ISLNK(child_info.st_mode):
                _remove_tree_at(fd, child, _identity(child_info))
            else:
                os.unlink(child, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def atomic_replace_tree(
    root: str,
    destination_rel: str,
    builder: Callable[[str], object],
    validator: Callable[[str], None],
    *,
    reprovers: Sequence[Callable[[], None]] = (),
    existing_marker: str | None = None,
) -> tuple[object, BatchReplaceResult]:
    """Build, validate, and publish one contained directory as a whole tree.

    A first publication is one same-parent rename.  Replacement of an existing
    non-empty tree requires the feature-detected atomic exchange primitive in
    :mod:`lib.transaction`; unsupported filesystems fail closed.
    """
    from lib.transaction import atomic_exchange_at, atomic_exchange_supported_at

    if not _platform_supported():
        raise SafePathError("contained tree transactions are unsupported on this OS backend")
    rel = safe_relative_path(destination_rel, "tree destination")
    parts = PurePosixPath(rel).parts
    if len(parts) < 2:
        raise SafePathError("tree destination must have a contained parent directory")
    supplied_root = os.path.abspath(root)
    if os.path.islink(supplied_root) or not os.path.isdir(supplied_root):
        raise SafePathError("vault root must be a real directory, not a symlink")
    root_fd = os.open(supplied_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    parent_fd = None
    stage_fd = None
    stage_name = f".aios-tree-{secrets.token_hex(10)}.stage"
    stage_identity = None
    cleanup_errors = []
    exchanged = False
    old_identity = None
    old_digest = None
    candidate_digest = None
    cleanup_started = False
    published_first = False
    try:
        parent_fd = _open_parent(root_fd, parts[:-1])
        parent_info = os.fstat(parent_fd)
        parent_identity = _identity(parent_info)
        entries = os.listdir(parent_fd)
        exists = _portable_entry(entries, parts[-1], rel)
        if exists:
            old_info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISDIR(old_info.st_mode) or stat.S_ISLNK(old_info.st_mode):
                raise SafePathError(f"tree destination is not a real directory: {rel}")
            old_identity = _identity(old_info)
            old_fd = os.open(
                parts[-1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            try:
                if existing_marker is not None:
                    marker_info = os.stat(
                        existing_marker, dir_fd=old_fd, follow_symlinks=False
                    )
                    if not stat.S_ISREG(marker_info.st_mode):
                        raise SafePathError(
                            f"existing tree lacks a regular {existing_marker} marker"
                        )
                old_digest = _tree_digest_fd(old_fd)
            except FileNotFoundError as exc:
                raise SafePathError(
                    f"existing tree lacks required marker {existing_marker}"
                ) from exc
            finally:
                os.close(old_fd)

        for reprove in reprovers:
            reprove()
        os.mkdir(stage_name, 0o700, dir_fd=parent_fd)
        stage_info = os.stat(stage_name, dir_fd=parent_fd, follow_symlinks=False)
        stage_identity = _identity(stage_info)
        stage_path = os.path.join(supplied_root, *parts[:-1], stage_name)
        built = builder(stage_path)

        _reprove_output_parent(root_fd, rel, parent_fd)
        if _identity(os.fstat(parent_fd)) != parent_identity:
            raise SafePathError("tree destination parent changed after preflight")
        stage_fd = os.open(
            stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        if _identity(os.fstat(stage_fd)) != stage_identity:
            raise SafePathError("staging tree changed during build")
        candidate_digest = _tree_digest_fd(stage_fd)
        os.close(stage_fd)
        stage_fd = None
        validator(stage_path)
        for reprove in reprovers:
            reprove()
        _reprove_output_parent(root_fd, rel, parent_fd)

        stage_fd = os.open(
            stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        if _identity(os.fstat(stage_fd)) != stage_identity:
            raise SafePathError("staging tree changed during build")
        if _tree_digest_fd(stage_fd) != candidate_digest:
            raise SafePathError("staging tree changed during validation")
        os.close(stage_fd)
        stage_fd = None

        entries = os.listdir(parent_fd)
        now_exists = _portable_entry(entries, parts[-1], rel)
        if exists != now_exists:
            raise SafePathError("live tree appeared or disappeared during build")
        if exists:
            live_info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
            if _identity(live_info) != old_identity:
                raise SafePathError("live tree identity changed during build")
            live_fd = os.open(
                parts[-1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            try:
                if _tree_digest_fd(live_fd) != old_digest:
                    raise SafePathError("live tree content changed during build")
            finally:
                os.close(live_fd)
            if not atomic_exchange_supported_at(parent_fd):
                raise SafePathError(
                    "atomic directory exchange is unsupported; refusing gapful replacement"
                )
            try:
                atomic_exchange_at(parent_fd, parts[-1], stage_name)
                exchanged = True
            except BaseException:
                live_now = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
                stage_now = os.stat(stage_name, dir_fd=parent_fd, follow_symlinks=False)
                if (_identity(live_now) == stage_identity
                        and _identity(stage_now) == old_identity):
                    exchanged = True
                raise
            live_fd = os.open(
                parts[-1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            prior_fd = os.open(
                stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            try:
                if (_tree_digest_fd(live_fd) != candidate_digest
                        or _tree_digest_fd(prior_fd) != old_digest):
                    raise SafePathError("atomic exchange content proof failed")
            finally:
                os.close(live_fd)
                os.close(prior_fd)
            cleanup_started = True
            _remove_tree_at(parent_fd, stage_name, old_identity)
            stage_identity = None
        else:
            os.rename(
                stage_name, parts[-1], src_dir_fd=parent_fd, dst_dir_fd=parent_fd
            )
            published_first = True
            os.fsync(parent_fd)
            stage_identity = None
        return built, BatchReplaceResult(True, True, ())
    except BaseException as exc:
        # If exchange completed before a later proof failed, restore the exact
        # old live tree before attempting to discard our candidate.
        if (exchanged and not cleanup_started and parent_fd is not None
                and old_identity is not None):
            try:
                live_info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
                prior_info = os.stat(stage_name, dir_fd=parent_fd, follow_symlinks=False)
                if (_identity(live_info) == stage_identity
                        and _identity(prior_info) == old_identity):
                    atomic_exchange_at(parent_fd, parts[-1], stage_name)
                    exchanged = False
                elif not (_identity(live_info) == old_identity
                           and _identity(prior_info) == stage_identity):
                    cleanup_errors.append("tree exchange layout is unprovable")
            except BaseException as rollback_exc:
                cleanup_errors.append(f"tree rollback: {rollback_exc}")
        elif exchanged and cleanup_started:
            cleanup_errors.append(
                "new tree is live but preserved old-tree cleanup is incomplete"
            )
        if published_first and parent_fd is not None and stage_identity is not None:
            try:
                live_info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
                if _identity(live_info) != stage_identity:
                    raise SafePathError("first-publish live identity is unprovable")
                os.rename(
                    parts[-1], stage_name,
                    src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
                )
                os.fsync(parent_fd)
                published_first = False
            except BaseException as rollback_exc:
                cleanup_errors.append(f"first-publish rollback: {rollback_exc}")
        if stage_identity is not None and parent_fd is not None and not exchanged:
            try:
                _remove_tree_at(parent_fd, stage_name, stage_identity)
                stage_identity = None
            except FileNotFoundError:
                stage_identity = None
            except BaseException as cleanup_exc:
                cleanup_errors.append(f"staging cleanup: {cleanup_exc}")
        if cleanup_errors:
            raise SafePathError(
                "tree transaction failed and ROLLBACK IS INCOMPLETE: "
                + "; ".join(cleanup_errors) + f"; original failure: {exc}"
            ) from exc
        raise SafePathError(f"tree transaction refused; prior state preserved: {exc}") from exc
    finally:
        if stage_fd is not None:
            os.close(stage_fd)
        if parent_fd is not None:
            os.close(parent_fd)
        os.close(root_fd)


def _write_payload_tree(parent_fd: int, writes: Mapping[str, bytes]) -> None:
    created = []
    try:
        keys = {}
        for index, (raw, payload) in enumerate(writes.items()):
            rel = safe_relative_path(raw, "archive member")
            key = _collision_key(rel)
            if key in keys:
                raise SafePathError(
                    f"archive members contain a case/Unicode collision: {keys[key]} and {rel}"
                )
            keys[key] = rel
            parts = PurePosixPath(rel).parts
            target_parent = _open_or_create_parent(parent_fd, parts[:-1], created)
            try:
                if _portable_entry(os.listdir(target_parent), parts[-1], rel):
                    raise SafePathError(f"archive staging member already exists: {rel}")
                pseudo = ContainedFile(
                    "", rel, (), parts[-1], target_parent, 0, 0, 0, 0, 0o644, 0, 0
                )
                ContainedBatch._write_temp(pseudo, parts[-1], payload)
                _mutation_boundary("after-archive-member", index, None)
                os.fsync(target_parent)
            finally:
                os.close(target_parent)
    finally:
        _close_created_dir_fds(created)


def _payload_tree_fd(root_fd: int) -> dict[str, bytes]:
    out = {}

    def descend(fd: int, parts: tuple[str, ...]) -> None:
        aliases = {}
        for name in sorted(os.listdir(fd)):
            key = unicodedata.normalize("NFC", name).casefold()
            if key in aliases:
                raise SafePathError("archive staging contains a case/Unicode collision")
            aliases[key] = name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            rel = "/".join(parts + (name,))
            if stat.S_ISLNK(info.st_mode):
                raise SafePathError(f"archive staging contains a symlink: {rel}")
            if stat.S_ISDIR(info.st_mode):
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                try:
                    descend(child, parts + (name,))
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    chunks = []
                    while True:
                        chunk = os.read(file_fd, 1024 * 1024)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    out[rel] = b"".join(chunks)
                finally:
                    os.close(file_fd)
            else:
                raise SafePathError(f"archive staging member is not regular: {rel}")

    descend(root_fd, ())
    return out


def atomic_archive_and_remove_tree(
    root: str,
    source_rel: str,
    archive_rel: str | None,
    archive_writes: Mapping[str, bytes],
    gate: Callable[[], None],
    *,
    reprovers: Sequence[Callable[[], None]] = (),
    boundary: Callable[[str], None] | None = None,
    expected_source_digest: str | None = None,
) -> BatchReplaceResult:
    """Archive selected bytes and remove a contained tree as one recoverable unit."""
    source = safe_relative_path(source_rel, "removal source")
    source_parts = PurePosixPath(source).parts
    if len(source_parts) < 2:
        raise SafePathError("removal source must have a contained parent")
    archive = (safe_relative_path(archive_rel, "archive destination")
               if archive_rel is not None else None)
    if archive is None and archive_writes:
        raise SafePathError("purge transaction cannot carry archive writes")
    supplied_root = os.path.abspath(root)
    root_fd = os.open(supplied_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    source_parent = archive_parent = archive_stage_fd = None
    created_dirs = []
    source_name = source_parts[-1]
    quarantine = f".aios-remove-{source_name}-{secrets.token_hex(8)}.stage"
    archive_stage = f".aios-archive-{secrets.token_hex(8)}.stage"
    source_identity = archive_stage_identity = None
    quarantined = published = cleanup_started = False
    errors = []
    try:
        source_parent = _open_parent(root_fd, source_parts[:-1])
        _reprove_output_parent(root_fd, source, source_parent)
        if not _portable_entry(os.listdir(source_parent), source_name, source):
            raise SafePathError(f"removal source disappeared: {source}")
        source_info = os.stat(source_name, dir_fd=source_parent, follow_symlinks=False)
        if not stat.S_ISDIR(source_info.st_mode) or stat.S_ISLNK(source_info.st_mode):
            raise SafePathError(f"removal source is not a real directory: {source}")
        source_identity = _identity(source_info)
        source_fd = os.open(
            source_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=source_parent,
        )
        try:
            source_digest = _tree_digest_fd(source_fd)
        finally:
            os.close(source_fd)
        if (expected_source_digest is not None
                and source_digest != expected_source_digest):
            raise SafePathError("removal source changed after its owner bytes were bound")

        if archive is not None:
            archive_parts = PurePosixPath(archive).parts
            archive_parent = _open_or_create_parent(
                root_fd, archive_parts[:-1], created_dirs
            )
            _reprove_output_parent(root_fd, archive, archive_parent)
            if _portable_entry(os.listdir(archive_parent), archive_parts[-1], archive):
                raise SafePathError(f"archive destination already exists: {archive}")
            os.mkdir(archive_stage, 0o700, dir_fd=archive_parent)
            archive_stage_info = os.stat(
                archive_stage, dir_fd=archive_parent, follow_symlinks=False
            )
            archive_stage_identity = _identity(archive_stage_info)
            archive_stage_fd = os.open(
                archive_stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=archive_parent,
            )
            _write_payload_tree(archive_stage_fd, archive_writes)
            if _payload_tree_fd(archive_stage_fd) != dict(archive_writes):
                raise SafePathError("staged archive does not match bound owner bytes")
            os.fsync(archive_stage_fd)
            os.close(archive_stage_fd)
            archive_stage_fd = None

        if boundary:
            boundary("before-pack-quarantine")
        for reprove in reprovers:
            reprove()
        _reprove_output_parent(root_fd, source, source_parent)
        current = os.stat(source_name, dir_fd=source_parent, follow_symlinks=False)
        if _identity(current) != source_identity:
            raise SafePathError("removal source identity changed before commit")
        current_fd = os.open(
            source_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=source_parent,
        )
        try:
            if _tree_digest_fd(current_fd) != source_digest:
                raise SafePathError("removal source content changed before commit")
        finally:
            os.close(current_fd)
        if archive is not None:
            _reprove_output_parent(root_fd, archive, archive_parent)

        os.rename(
            source_name, quarantine,
            src_dir_fd=source_parent, dst_dir_fd=source_parent,
        )
        quarantined = True
        os.fsync(source_parent)
        if boundary:
            boundary("after-pack-quarantine")
        if archive is not None:
            os.rename(
                archive_stage, archive_parts[-1],
                src_dir_fd=archive_parent, dst_dir_fd=archive_parent,
            )
            published = True
            os.fsync(archive_parent)
            if boundary:
                boundary("after-archive-publish")

        gate()
        if boundary:
            boundary("before-pack-finalize")
        # The quarantined tree can still be changed through a file descriptor
        # an owner already had open before the rename.  Reprove both sides at
        # the last reversible moment so such an edit is restored live rather
        # than discarded, and a concurrently altered archive is never blessed.
        held = os.stat(quarantine, dir_fd=source_parent, follow_symlinks=False)
        if _identity(held) != source_identity:
            raise SafePathError("quarantined source identity changed before finalize")
        held_fd = os.open(
            quarantine, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=source_parent,
        )
        try:
            if _tree_digest_fd(held_fd) != source_digest:
                raise SafePathError("quarantined source content changed before finalize")
        finally:
            os.close(held_fd)
        if archive is not None:
            final_info = os.stat(
                archive_parts[-1], dir_fd=archive_parent, follow_symlinks=False
            )
            if _identity(final_info) != archive_stage_identity:
                raise SafePathError("published archive identity changed before finalize")
            final_fd = os.open(
                archive_parts[-1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=archive_parent,
            )
            try:
                if _payload_tree_fd(final_fd) != dict(archive_writes):
                    raise SafePathError("published archive content changed before finalize")
            finally:
                os.close(final_fd)
        cleanup_started = True
        _remove_tree_at(source_parent, quarantine, source_identity)
        quarantined = False
        return BatchReplaceResult(True, True, ())
    except BaseException as exc:
        if not cleanup_started:
            if published and archive_parent is not None:
                try:
                    final_info = os.stat(
                        archive_parts[-1], dir_fd=archive_parent, follow_symlinks=False
                    )
                    if _identity(final_info) != archive_stage_identity:
                        raise SafePathError("published archive identity changed before rollback")
                    os.rename(
                        archive_parts[-1], archive_stage,
                        src_dir_fd=archive_parent, dst_dir_fd=archive_parent,
                    )
                    os.fsync(archive_parent)
                    published = False
                except BaseException as rollback_exc:
                    errors.append(f"archive rollback: {rollback_exc}")
            if quarantined:
                try:
                    held = os.stat(
                        quarantine, dir_fd=source_parent, follow_symlinks=False
                    )
                    if _identity(held) != source_identity:
                        raise SafePathError("quarantined source identity changed")
                    os.rename(
                        quarantine, source_name,
                        src_dir_fd=source_parent, dst_dir_fd=source_parent,
                    )
                    os.fsync(source_parent)
                    quarantined = False
                except BaseException as rollback_exc:
                    errors.append(f"source rollback: {rollback_exc}")
        else:
            errors.append("pack removal committed but quarantine cleanup is incomplete")
        if (archive_stage_identity is not None and archive_parent is not None
                and not published):
            try:
                _remove_tree_at(archive_parent, archive_stage, archive_stage_identity)
                archive_stage_identity = None
            except FileNotFoundError:
                archive_stage_identity = None
            except BaseException as cleanup_exc:
                errors.append(f"archive staging cleanup: {cleanup_exc}")
        if errors:
            raise SafePathError(
                "archive/removal transaction failed and ROLLBACK IS INCOMPLETE: "
                + "; ".join(errors) + f"; original failure: {exc}"
            ) from exc
        raise SafePathError(
            f"archive/removal transaction refused; prior state restored: {exc}"
        ) from exc
    finally:
        if archive_stage_fd is not None:
            os.close(archive_stage_fd)
        if archive_parent is not None:
            os.close(archive_parent)
        if source_parent is not None:
            os.close(source_parent)
        if errors or (not quarantined and not published):
            _remove_created_dirs(root_fd, created_dirs)
        else:
            _close_created_dir_fds(created_dirs)
        os.close(root_fd)
