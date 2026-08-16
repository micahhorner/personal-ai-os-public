"""Durable whole-root transactions using atomic directory exchange.

The caller owns candidate construction and validation.  This module owns only
the commit boundary.  ``live`` and its prepared sibling ``candidate`` exchange
names in one kernel operation, so the canonical live path is never absent:
before a crash it names the old tree; after a crash it names the new tree.

There is deliberately no two-rename fallback.  macOS uses ``renameatx_np`` with
``RENAME_SWAP`` and Linux uses ``renameat2`` with ``RENAME_EXCHANGE``.  Other
platforms, kernels, or filesystems fail closed during preflight.
"""
from __future__ import annotations

import ctypes
import errno
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Union


PathValue = Union[str, os.PathLike]
Boundary = Optional[Callable[[str, str, Path], None]]
SCHEMA = "aios-directory-exchange-v3"
_STATES = {
    "prepared",
    "exchanged",
    "committed",
    "rolling-back",
    "rolled-back",
    "cleanup",
    "cleaned",
}
_JOURNAL_KEYS = {
    "schema",
    "transaction_id",
    "live",
    "candidate",
    "previous",
    "journal",
    "original_identity",
    "candidate_identity",
    "original_content_identity",
    "candidate_content_identity",
    "context",
    "state",
    "sequence",
    "updated_ns",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UNSUPPORTED = {
    errno.ENOSYS,
    errno.EINVAL,
    errno.EXDEV,
    getattr(errno, "ENOTSUP", errno.EINVAL),
    getattr(errno, "EOPNOTSUPP", errno.EINVAL),
}


class TransactionError(RuntimeError):
    """A directory transaction was unsafe or could not recover exactly."""

    def __init__(
        self, message: str, evidence: Optional[Mapping[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.evidence = dict(evidence or {})


def _transaction_boundary(name: str, phase: str, root: Path) -> None:
    """Default no-op seam matching the release fault-injection contract."""
    if name not in {"commit-swap", "cleanup"} or phase not in {"before", "after"}:
        raise TransactionError(f"invalid transaction boundary: {name}/{phase}")


def _exchange_completed(root: Path) -> None:
    """Immediate post-syscall crash-test seam; production behavior is a no-op."""
    del root


def _call_boundary(boundary: Boundary, name: str, phase: str, root: Path) -> None:
    (boundary or _transaction_boundary)(name, phase, root)


def _real_directory(value: PathValue, label: str) -> Path:
    supplied = Path(value).expanduser().absolute()
    if supplied.is_symlink():
        raise TransactionError(f"{label} must not be a symbolic link")
    try:
        resolved = supplied.resolve(strict=True)
    except OSError as exc:
        raise TransactionError(f"{label} is unavailable: {supplied}") from exc
    if not resolved.is_dir():
        raise TransactionError(f"{label} must be a directory: {resolved}")
    return resolved


def _sibling_file(value: PathValue) -> Path:
    supplied = Path(value).expanduser().absolute()
    return supplied.parent.resolve() / supplied.name


def _identity(path: Path) -> Dict[str, int]:
    try:
        info = path.stat()
    except OSError as exc:
        raise TransactionError(f"cannot identify directory: {path}") from exc
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
        raise TransactionError(f"path is not a real directory: {path}")
    if info.st_ino == 0:
        raise TransactionError(
            f"filesystem does not expose a stable directory identity: {path}"
        )
    return {"device": int(info.st_dev), "inode": int(info.st_ino)}


def _matches(path: Path, identity: Mapping[str, Any]) -> bool:
    try:
        info = path.stat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise TransactionError(f"cannot inspect transaction path: {path}") from exc
    return (
        not path.is_symlink()
        and stat.S_ISDIR(info.st_mode)
        and info.st_dev == identity["device"]
        and info.st_ino == identity["inode"]
    )


def _same_filesystem(a: PathValue, b: PathValue) -> bool:
    """Seam used by tests and callers that must prove exchange eligibility."""
    try:
        return Path(a).stat().st_dev == Path(b).stat().st_dev
    except OSError:
        return False


def _fsync_dir(path: Path) -> bool:
    """Durably order directory metadata where the platform supports it."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError as exc:
        if os.name == "nt" or exc.errno in _UNSUPPORTED:
            return False
        raise
    try:
        try:
            os.fsync(descriptor)
            return True
        except OSError as exc:
            if os.name == "nt" or exc.errno in _UNSUPPORTED:
                return False
            raise
    finally:
        os.close(descriptor)


def _exchange_syscall_at(first_dir_fd: int, first, second_dir_fd: int, second) -> None:
    """Invoke one platform exchange syscall relative to caller-held dirs."""
    library = ctypes.CDLL(None, use_errno=True)
    ctypes.set_errno(0)
    if sys.platform == "darwin":
        try:
            operation = library.renameatx_np
        except AttributeError as exc:
            raise OSError(errno.ENOSYS, "renameatx_np is unavailable") from exc
        operation.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        operation.restype = ctypes.c_int
        result = operation(
            first_dir_fd, os.fsencode(first), second_dir_fd, os.fsencode(second),
            0x00000002,
        )
    elif sys.platform.startswith("linux"):
        try:
            operation = library.renameat2
        except AttributeError as exc:
            raise OSError(errno.ENOSYS, "renameat2 is unavailable") from exc
        operation.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        operation.restype = ctypes.c_int
        result = operation(
            first_dir_fd, os.fsencode(first), second_dir_fd, os.fsencode(second),
            0x00000002,
        )
    else:
        raise OSError(errno.ENOSYS, "atomic directory exchange is unsupported")
    if result != 0:
        code = ctypes.get_errno() or errno.EIO
        raise OSError(code, os.strerror(code), f"{first} <-> {second}")


def _exchange_syscall(first: Path, second: Path) -> None:
    """Invoke exactly one platform atomic directory-exchange syscall."""
    at_fdcwd = -2 if sys.platform == "darwin" else -100
    _exchange_syscall_at(at_fdcwd, first, at_fdcwd, second)


def atomic_exchange_at(parent_fd: int, first: str, second: str) -> None:
    """Atomically exchange two child directories of one held parent."""
    if (not first or not second or first == second
            or "/" in first or "/" in second or "\\" in first or "\\" in second):
        raise TransactionError("atomic exchange names must be distinct direct children")
    for name in (first, second):
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise TransactionError("atomic exchange requires two real child directories")
    _exchange_syscall_at(parent_fd, first, parent_fd, second)
    os.fsync(parent_fd)


def atomic_exchange_supported_at(parent_fd: int) -> bool:
    """Probe exchange support inside a held directory without touching live."""
    token = uuid.uuid4().hex
    first = f".aios-exchange-probe-a-{token}"
    second = f".aios-exchange-probe-b-{token}"
    try:
        os.mkdir(first, 0o700, dir_fd=parent_fd)
        os.mkdir(second, 0o700, dir_fd=parent_fd)
        try:
            atomic_exchange_at(parent_fd, first, second)
            atomic_exchange_at(parent_fd, first, second)
            return True
        except OSError as exc:
            if exc.errno in _UNSUPPORTED:
                return False
            raise TransactionError(f"atomic exchange probe failed: {exc}") from exc
    finally:
        for name in (first, second):
            try:
                os.rmdir(name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.fsync(parent_fd)


def _atomic_exchange(first: Path, second: Path) -> None:
    """Atomically exchange two real sibling directories and fsync the parent."""
    if first.parent != second.parent:
        raise TransactionError("atomic exchange paths must be direct siblings")
    if first.is_symlink() or second.is_symlink():
        raise TransactionError("atomic exchange refuses symbolic links")
    if not first.is_dir() or not second.is_dir():
        raise TransactionError("atomic exchange requires two directories")
    _exchange_syscall(first, second)
    _fsync_dir(first.parent)


def _atomic_exchange_supported(parent: PathValue) -> bool:
    """Probe the actual parent filesystem without ever touching the live tree."""
    parent_path = _real_directory(parent, "exchange parent")
    first = Path(tempfile.mkdtemp(prefix=".aios-exchange-probe-a-", dir=str(parent_path)))
    second = Path(tempfile.mkdtemp(prefix=".aios-exchange-probe-b-", dir=str(parent_path)))
    try:
        try:
            _atomic_exchange(first, second)
            _atomic_exchange(first, second)
            return True
        except OSError as exc:
            if exc.errno in _UNSUPPORTED:
                return False
            raise TransactionError(f"atomic exchange probe failed: {exc}") from exc
    finally:
        shutil.rmtree(str(first), ignore_errors=True)
        shutil.rmtree(str(second), ignore_errors=True)
        _fsync_dir(parent_path)


def _canonical(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _write_journal(path: Path, record: Dict[str, Any]) -> None:
    record["sequence"] += 1
    record["updated_ns"] = time.time_ns()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".partial", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical(record))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
        _fsync_dir(path.parent)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _set_state(path: Path, record: Dict[str, Any], state: str) -> None:
    if state not in _STATES:
        raise TransactionError(f"unknown transaction state: {state}")
    record["state"] = state
    _write_journal(path, record)


def _validate_identity(raw: Any, label: str) -> Dict[str, int]:
    if not isinstance(raw, dict) or set(raw) != {"device", "inode"}:
        raise TransactionError(f"invalid {label} identity in transaction journal")
    for key in ("device", "inode"):
        if not isinstance(raw[key], int) or isinstance(raw[key], bool) or raw[key] < 0:
            raise TransactionError(f"invalid {label} identity in transaction journal")
    if raw["inode"] == 0:
        raise TransactionError(f"invalid {label} identity in transaction journal")
    return {"device": raw["device"], "inode": raw["inode"]}


def _validate_content_identity(raw: Any, label: str,
                               *, nullable: bool = True) -> Optional[str]:
    if raw is None and nullable:
        return None
    if not isinstance(raw, str) or not _SHA256.fullmatch(raw):
        raise TransactionError(
            f"{label} content identity must be a lowercase SHA-256"
        )
    return raw


def _content_identities(
    original: Any, candidate: Any
) -> Tuple[Optional[str], Optional[str]]:
    original_id = _validate_content_identity(original, "original")
    candidate_id = _validate_content_identity(candidate, "candidate")
    if (original_id is None) != (candidate_id is None):
        raise TransactionError(
            "original and candidate content identities must be supplied together"
        )
    return original_id, candidate_id


def _verify_content(record: Mapping[str, Any], path: Path, role: str,
                    content_identity: Optional[Callable[[Path], str]]) -> None:
    expected = record[f"{role}_content_identity"]
    if expected is None:
        return
    if content_identity is None:
        raise TransactionError(
            "content_identity callback is required by the durable transaction"
        )
    try:
        observed = content_identity(path)
    except BaseException as exc:
        raise TransactionError(
            f"could not compute {role} content identity at {path}: {exc}"
        ) from exc
    observed = _validate_content_identity(
        observed, f"observed {role}", nullable=False
    )
    if observed != expected:
        raise TransactionError(
            f"{role} content identity mismatch at {path}",
            {"path": str(path), "expected": expected, "observed": observed},
        )


def _load_journal(path: Path) -> Dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise TransactionError(f"transaction journal is unavailable: {path}")
    try:
        with path.open("rb") as handle:
            raw = handle.read(1024 * 1024 + 1)
    except OSError as exc:
        raise TransactionError(f"transaction journal cannot be read: {path}") from exc
    if len(raw) > 1024 * 1024:
        raise TransactionError("transaction journal is unreasonably large")
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransactionError("transaction journal is corrupt") from exc
    if not isinstance(record, dict) or set(record) != _JOURNAL_KEYS:
        raise TransactionError("transaction journal fields are incomplete or unknown")
    if record.get("schema") != SCHEMA:
        raise TransactionError("unsupported transaction journal schema")
    transaction_id = record.get("transaction_id")
    try:
        if str(uuid.UUID(transaction_id)) != transaction_id:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise TransactionError("transaction journal id is invalid") from exc
    if record.get("state") not in _STATES:
        raise TransactionError("transaction journal state is invalid")
    if not isinstance(record.get("sequence"), int) or isinstance(
        record["sequence"], bool
    ) or record["sequence"] < 1:
        raise TransactionError("transaction journal sequence is invalid")
    if not isinstance(record.get("updated_ns"), int) or isinstance(
        record["updated_ns"], bool
    ) or record["updated_ns"] <= 0:
        raise TransactionError("transaction journal timestamp is invalid")
    record["original_identity"] = _validate_identity(
        record.get("original_identity"), "original"
    )
    record["candidate_identity"] = _validate_identity(
        record.get("candidate_identity"), "candidate"
    )
    (
        record["original_content_identity"],
        record["candidate_content_identity"],
    ) = _content_identities(
        record.get("original_content_identity"),
        record.get("candidate_content_identity"),
    )
    record["context"] = _validate_context(record.get("context"))
    for key in ("live", "candidate", "previous", "journal"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise TransactionError(f"transaction journal path is invalid: {key}")
    return record


def _verify_record_paths(
    record: Mapping[str, Any], live: Path, candidate: Path, journal: Path
) -> Tuple[Path, Path, Path]:
    recorded_live = Path(record["live"])
    recorded_candidate = Path(record["candidate"])
    recorded_journal = Path(record["journal"])
    if (recorded_live, recorded_candidate, recorded_journal) != (
        live,
        candidate,
        journal,
    ):
        raise TransactionError("transaction arguments do not match durable journal")
    if record["previous"] != record["candidate"]:
        raise TransactionError("preserved prior tree must occupy the candidate path")
    parent = live.parent
    if any(path.parent != parent for path in (
        recorded_live, recorded_candidate, recorded_journal
    )):
        raise TransactionError("every transaction path must remain a direct sibling")
    return recorded_live, recorded_candidate, recorded_journal


def _slot(path: Path, original: Mapping[str, Any],
          candidate: Mapping[str, Any]) -> str:
    if not path.exists() and not path.is_symlink():
        return "missing"
    if _matches(path, original):
        return "original"
    if _matches(path, candidate):
        return "candidate"
    return "other"


def _layout(record: Mapping[str, Any]) -> Tuple[str, str]:
    original = record["original_identity"]
    candidate = record["candidate_identity"]
    return (
        _slot(Path(record["live"]), original, candidate),
        _slot(Path(record["candidate"]), original, candidate),
    )


def _evidence(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "transaction_id": record["transaction_id"],
        "state": record["state"],
        "live": record["live"],
        "candidate": record["candidate"],
        "previous": record["previous"],
        "journal": record["journal"],
        "layout": _layout(record),
        "atomic_exchange": True,
        "context": record["context"],
    }


def _validate_context(value: Any) -> Optional[Dict[str, Any]]:
    """Accept a small, canonical JSON object for caller-owned recovery proof."""
    if value is None:
        return None
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise TransactionError("transaction context must be a JSON mapping or null")

    def plain(item: Any, depth: int = 0) -> Any:
        if depth > 12:
            raise TransactionError("transaction context nesting is excessive")
        if item is None or isinstance(item, (str, bool)):
            return item
        if isinstance(item, int) and not isinstance(item, bool):
            return item
        if isinstance(item, list):
            return [plain(child, depth + 1) for child in item]
        if isinstance(item, dict) and all(
            isinstance(key, str) for key in item
        ):
            return {key: plain(child, depth + 1) for key, child in item.items()}
        raise TransactionError("transaction context contains a non-JSON value")

    result = plain(value)
    encoded = json.dumps(
        result, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) > 256 * 1024:
        raise TransactionError("transaction context is unreasonably large")
    return result


def prepare_swap(live: PathValue, candidate: PathValue,
                 journal: PathValue, *,
                 original_content_identity: Optional[str] = None,
                 candidate_content_identity: Optional[str] = None,
                 context: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Durably record an atomic sibling exchange without changing live."""
    live_path = _real_directory(live, "live tree")
    candidate_path = _real_directory(candidate, "candidate tree")
    journal_path = _sibling_file(journal)
    original_content, candidate_content = _content_identities(
        original_content_identity, candidate_content_identity
    )
    supplied_context = _validate_context(context)
    if len({live_path, candidate_path, journal_path}) != 3:
        raise TransactionError("live, candidate, and journal paths must be distinct")
    if live_path.parent != candidate_path.parent or live_path.parent != journal_path.parent:
        raise TransactionError("candidate and journal must be direct siblings of live")
    if journal_path.is_symlink():
        raise TransactionError("transaction journal must not be a symbolic link")
    if journal_path.exists():
        record = _load_journal(journal_path)
        _verify_record_paths(record, live_path, candidate_path, journal_path)
        supplied = (original_content, candidate_content)
        recorded = (
            record["original_content_identity"],
            record["candidate_content_identity"],
        )
        if supplied != (None, None) and supplied != recorded:
            raise TransactionError(
                "supplied content identities do not match durable journal"
            )
        if supplied_context is not None and supplied_context != record["context"]:
            raise TransactionError(
                "supplied context does not match durable journal"
            )
        return _evidence(record)
    if not _same_filesystem(live_path, candidate_path):
        raise TransactionError("candidate and live tree are not on the same filesystem")
    if not _atomic_exchange_supported(live_path.parent):
        raise TransactionError(
            "atomic directory exchange is unsupported; refusing gapful fallback"
        )
    transaction_id = str(uuid.uuid4())
    record: Dict[str, Any] = {
        "schema": SCHEMA,
        "transaction_id": transaction_id,
        "live": str(live_path),
        "candidate": str(candidate_path),
        "previous": str(candidate_path),
        "journal": str(journal_path),
        "original_identity": _identity(live_path),
        "candidate_identity": _identity(candidate_path),
        "original_content_identity": original_content,
        "candidate_content_identity": candidate_content,
        "context": supplied_context,
        "state": "prepared",
        "sequence": 0,
        "updated_ns": 0,
    }
    _write_journal(journal_path, record)
    return _evidence(record)


def _rollback(journal: Path, record: Dict[str, Any],
              content_identity: Optional[Callable[[Path], str]] = None) -> None:
    layout = _layout(record)
    errors = []
    if layout == ("original", "candidate"):
        _verify_content(record, Path(record["live"]), "original", content_identity)
        try:
            _set_state(journal, record, "rolled-back")
        except BaseException as exc:
            raise TransactionError(
                f"tree is rolled back but journal update failed: {exc}",
                _evidence(record),
            ) from exc
        return
    try:
        _set_state(journal, record, "rolling-back")
    except BaseException as exc:
        errors.append(exc)
    if layout == ("candidate", "original"):
        # The failed new live may have changed while failing validation.  The
        # preserved old side is the one fact restoration must prove.
        _verify_content(
            record, Path(record["candidate"]), "original", content_identity
        )
        try:
            _atomic_exchange(Path(record["live"]), Path(record["candidate"]))
        except BaseException as exc:
            # The syscall may have succeeded and only parent fsync failed.
            if _layout(record) != ("original", "candidate"):
                raise
            errors.append(exc)
        layout = _layout(record)
    if layout != ("original", "candidate"):
        raise TransactionError(
            "automatic rollback could not prove a safe filesystem layout",
            _evidence(record),
        )
    _verify_content(record, Path(record["live"]), "original", content_identity)
    try:
        _set_state(journal, record, "rolled-back")
    except BaseException as exc:
        errors.append(exc)
    if errors:
        raise TransactionError(
            "tree was restored but rollback durability recording failed: "
            + "; ".join(str(error) for error in errors),
            _evidence(record),
        )


def commit_swap(live: PathValue, candidate: PathValue, journal: PathValue,
                *, boundary: Boundary = None,
                content_identity: Optional[Callable[[Path], str]] = None) -> Dict[str, Any]:
    """Commit or resume an atomic exchange; exchange again on every exception."""
    live_arg = _sibling_file(live)
    candidate_arg = _sibling_file(candidate)
    journal_path = _sibling_file(journal)
    if not journal_path.exists():
        prepare_swap(live_arg, candidate_arg, journal_path)
    record = _load_journal(journal_path)
    live_path, candidate_path, _ = _verify_record_paths(
        record, live_arg, candidate_arg, journal_path
    )
    layout = _layout(record)
    if record["state"] == "cleaned":
        raise TransactionError("cleaned transaction cannot be committed again")
    if record["state"] == "rolled-back" and layout == ("original", "candidate"):
        _verify_content(record, live_path, "original", content_identity)
        return dict(_evidence(record), status="rolled-back")
    if record["state"] == "committed" and layout == ("candidate", "original"):
        try:
            _verify_content(record, live_path, "candidate", content_identity)
            _verify_content(record, candidate_path, "original", content_identity)
        except BaseException as exc:
            try:
                _rollback(journal_path, record, content_identity)
            except BaseException as rollback_exc:
                raise TransactionError(
                    "committed content proof failed and automatic rollback "
                    f"failed: {rollback_exc}",
                    _evidence(record),
                ) from exc
            raise
        return dict(_evidence(record), status="already-committed")
    if record["state"] == "cleanup":
        raise TransactionError("transaction cleanup is incomplete; resume cleanup")
    if record["state"] == "rolling-back":
        _rollback(journal_path, record, content_identity)
        return dict(_evidence(record), status="rolled-back")
    if layout not in {("original", "candidate"), ("candidate", "original")}:
        raise TransactionError(
            "transaction paths do not match any recoverable layout",
            _evidence(record),
        )
    try:
        if layout == ("original", "candidate"):
            _call_boundary(boundary, "commit-swap", "before", live_path)
            # The boundary may be supplied by fault injection or integration
            # code.  Re-prove both roots after it, at the last possible moment.
            _verify_content(record, live_path, "original", content_identity)
            _verify_content(record, candidate_path, "candidate", content_identity)
            _atomic_exchange(live_path, candidate_path)
            _exchange_completed(live_path)
            layout = _layout(record)
        if layout != ("candidate", "original"):
            raise TransactionError(
                "atomic exchange ended in an unprovable filesystem layout",
                _evidence(record),
            )
        _verify_content(record, live_path, "candidate", content_identity)
        _verify_content(record, candidate_path, "original", content_identity)
        _set_state(journal_path, record, "exchanged")
        _set_state(journal_path, record, "committed")
        _call_boundary(boundary, "commit-swap", "after", live_path)
        return dict(_evidence(record), status="committed")
    except BaseException as exc:
        try:
            _rollback(journal_path, record, content_identity)
        except BaseException as rollback_exc:
            raise TransactionError(
                f"transaction failed and automatic rollback failed: {rollback_exc}",
                _evidence(record),
            ) from exc
        raise


def rollback_swap(live: PathValue, candidate: PathValue, journal: PathValue,
                  *, boundary: Boundary = None,
                  content_identity: Optional[Callable[[Path], str]] = None) -> Dict[str, Any]:
    """Restore the original live tree without deleting the failed candidate.

    This is the public recovery operation for a later validation/reporting
    failure.  It also resumes a process that died after the exchange or during
    rollback.  Layout is proved from the durable journal and directory
    identities before any exchange occurs.
    """
    live_arg = _sibling_file(live)
    candidate_arg = _sibling_file(candidate)
    journal_path = _sibling_file(journal)
    record = _load_journal(journal_path)
    live_path, _, _ = _verify_record_paths(
        record, live_arg, candidate_arg, journal_path
    )
    state = record["state"]
    layout = _layout(record)
    if state in {"cleanup", "cleaned"}:
        raise TransactionError(
            f"transaction cannot roll back after cleanup boundary: {state}",
            _evidence(record),
        )
    if layout not in {("original", "candidate"), ("candidate", "original")}:
        raise TransactionError(
            "rollback paths do not match any recoverable layout",
            _evidence(record),
        )
    if state == "rolled-back":
        if layout != ("original", "candidate"):
            raise TransactionError(
                "rolled-back journal disagrees with filesystem layout",
                _evidence(record),
            )
        _verify_content(record, live_path, "original", content_identity)
        return dict(_evidence(record), status="already-rolled-back")
    if state not in {
        "prepared", "exchanged", "committed", "rolling-back"
    }:
        raise TransactionError(
            f"transaction state cannot be rolled back: {state}",
            _evidence(record),
        )
    _call_boundary(boundary, "commit-swap", "before", live_path)
    _rollback(journal_path, record, content_identity)
    _call_boundary(boundary, "commit-swap", "after", live_path)
    return dict(_evidence(record), status="rolled-back")


def _remove_tree(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise TransactionError(f"cleanup target is not a real directory: {path}")
    shutil.rmtree(str(path))
    _fsync_dir(path.parent)


def cleanup_swap(live: PathValue, candidate: PathValue, journal: PathValue,
                 *, confirm: bool = False, boundary: Boundary = None,
                 content_identity: Optional[Callable[[Path], str]] = None) -> Dict[str, Any]:
    """Explicitly discard the non-live side after commit or rollback.

    The journal remains as a durable tombstone.  A crash during confirmed
    cleanup resumes deletion; it never reconstructs a tree the caller explicitly
    authorized this operation to discard.
    """
    if not confirm:
        raise TransactionError("cleanup is destructive; explicit confirm=True is required")
    live_arg = _sibling_file(live)
    candidate_arg = _sibling_file(candidate)
    journal_path = _sibling_file(journal)
    record = _load_journal(journal_path)
    live_path, candidate_path, _ = _verify_record_paths(
        record, live_arg, candidate_arg, journal_path
    )
    state = record["state"]
    if state == "cleaned":
        live_role = _slot(
            live_path, record["original_identity"], record["candidate_identity"]
        )
        if live_role not in {"original", "candidate"}:
            raise TransactionError(
                "cleaned transaction cannot prove canonical live tree",
                _evidence(record),
            )
        _verify_content(record, live_path, live_role, content_identity)
        return dict(_evidence(record), status="already-cleaned")
    if state not in {"committed", "rolled-back", "cleanup"}:
        raise TransactionError(
            f"transaction is not at a cleanup boundary: {state}",
            _evidence(record),
        )
    live_role = _slot(
        live_path, record["original_identity"], record["candidate_identity"]
    )
    if live_role not in {"original", "candidate"}:
        raise TransactionError("cleanup cannot prove which tree is live", _evidence(record))
    expected = (
        record["original_identity"] if live_role == "candidate"
        else record["candidate_identity"]
    )
    expected_role = "original" if live_role == "candidate" else "candidate"
    _verify_content(record, live_path, live_role, content_identity)
    if state != "cleanup":
        if not _matches(candidate_path, expected):
            raise TransactionError(
                "cleanup target does not match the preserved tree identity",
                _evidence(record),
            )
        # Cleanup is the irreversible boundary.  Prove the exact content being
        # authorized for deletion before recording that authorization.
        _verify_content(record, candidate_path, expected_role, content_identity)
        _set_state(journal_path, record, "cleanup")
    _call_boundary(boundary, "cleanup", "before", live_path)
    if candidate_path.exists() or candidate_path.is_symlink():
        if not _matches(candidate_path, expected):
            raise TransactionError(
                "cleanup target was replaced after cleanup began",
                _evidence(record),
            )
        # Authorization may predate a crash or interruption.  For a
        # content-bound journal, prove the bytes again at the last possible
        # moment; never let an earlier cleanup state authorize deletion of data
        # that arrived afterward.  An inode-only legacy transaction retains its
        # resumable partial-rmtree behavior.
        _verify_content(
            record, candidate_path, expected_role, content_identity
        )
        _remove_tree(candidate_path)
    _set_state(journal_path, record, "cleaned")
    _call_boundary(boundary, "cleanup", "after", live_path)
    return dict(_evidence(record), status="cleaned")
