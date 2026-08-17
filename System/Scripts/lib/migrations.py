"""Strict migration manifests and the canonical append-only applied ledger.

This module deliberately owns policy, parsing, ordering, hashing, and ledger
durability. The command module owns isolated-candidate transform and validation;
the outer upgrade transaction owns checkpoint, discard, and live swap.
"""
from __future__ import annotations

import datetime as _datetime
import errno
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


TOOL_VERSION = "2.1.0"
SCHEMA_VERSION = "1.1.0"
LEDGER_RELATIVE_PATH = Path("System/Journal/migration-ledger.jsonl")
CHANGE_JOURNAL_NAME = "change-journal.md"
SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
ID_RE = re.compile(r"^migration-[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*$")
KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")

MANIFEST_FIELDS = {
    "schema_version",
    "id",
    "version_target",
    "source_distribution",
    "source_identity",
    "from_version",
    "to_version",
    "prerequisites",
    "content_selector",
    "transform",
    "validation",
    "rollback",
    "idempotency_key",
    "manifest_hash",
}
LEDGER_FIELDS = {
    "id",
    "version_target",
    "source_distribution",
    "source_identity",
    "from_version",
    "to_version",
    "manifest_hash",
    "timestamp",
    "checkpoint",
    "result",
    "tool_version",
    "idempotency_key",
}
RESULTS = {"applied"}
VERSION_TARGETS = {"system_version", "vault_profile_version"}
DISTRIBUTIONS = {"personal-ai-os", "pmm-engine"}


class MigrationError(RuntimeError):
    """A fail-closed migration contract or sequencing error."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise MigrationError("YAML mapping keys must be scalar/hashable") from exc
        if duplicate:
            raise MigrationError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
)


def load_unique_yaml_text(text: str, label: str) -> Any:
    try:
        return yaml.load(text, Loader=_UniqueKeyLoader)
    except (yaml.YAMLError, MigrationError) as exc:
        raise MigrationError(f"{label} is invalid: {exc}") from exc


def _read_regular_nofollow(path: Path, label: str) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, os.O_RDONLY | nofollow)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise MigrationError(f"{label} must be a regular file")
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)
    except OSError as exc:
        raise MigrationError(f"{label} is missing, unsafe, symlinked, or unreadable: {exc}") from exc


def _read_vault_regular(root: Path, parts: tuple[str, ...], label: str) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
    fds = []
    try:
        current = os.open(root, directory_flags); fds.append(current)
        for part in parts[:-1]:
            current = os.open(part, directory_flags, dir_fd=current); fds.append(current)
        leaf = os.open(parts[-1], os.O_RDONLY | nofollow, dir_fd=current); fds.append(leaf)
        if not stat.S_ISREG(os.fstat(leaf).st_mode):
            raise MigrationError(f"{label} must be a regular file")
        chunks = []
        while True:
            chunk = os.read(leaf, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError as exc:
        raise MigrationError(
            f"{label} is missing, unsafe, symlinked, or unreadable: {exc}"
        ) from exc
    finally:
        for fd in reversed(fds):
            os.close(fd)


def load_unique_yaml_file(path: os.PathLike[str] | str, label: str) -> Any:
    try:
        text = _read_regular_nofollow(Path(path), label).decode("utf-8")
    except UnicodeError as exc:
        raise MigrationError(f"{label} is not UTF-8: {exc}") from exc
    return load_unique_yaml_text(text, label)


def _safe_relative(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or os.path.isabs(value):
        raise MigrationError(f"{label} must be a safe relative POSIX path")
    path = Path(value)
    if path.as_posix() != value or any(part in {"", ".", ".."} for part in path.parts):
        raise MigrationError(f"{label} must be a safe relative POSIX path")
    return path


@dataclass(frozen=True)
class Manifest:
    directory: Path
    data: dict[str, Any]
    manifest_hash: str
    sequence: int

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def from_version(self) -> str:
        return self.data["from_version"]

    @property
    def to_version(self) -> str:
        return self.data["to_version"]

    @property
    def version_target(self) -> str:
        return self.data["version_target"]

    @property
    def source_identity(self) -> str:
        return self.data["source_identity"]

    @property
    def source_distribution(self) -> str:
        return self.data["source_distribution"]


def _plain(value: Any) -> Any:
    """Reject YAML-specific/non-JSON values before canonical hashing."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise MigrationError("manifest mapping keys must be strings")
        return {key: _plain(item) for key, item in value.items()}
    raise MigrationError(f"manifest contains unsupported value type: {type(value).__name__}")


def compute_manifest_hash(data: dict[str, Any]) -> str:
    payload = dict(_plain(data))
    payload.pop("manifest_hash", None)
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compute_source_identity(root: os.PathLike[str] | str) -> str:
    """Hash the canonical release baseline, excluding generated-time metadata.

    The instance may legitimately edit product files, so identity is bound to
    the release's canonical ``files`` map rather than to its current working
    bytes. Rival distributions sharing a version string carry a different map
    and therefore cannot enter an official migration edge by version alone.
    """
    root_path = Path(root).resolve(strict=True)
    path = root_path / "System/.baseline-manifest.json"
    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise MigrationError(
                    f"canonical source baseline has duplicate JSON key: {key}"
                )
            result[key] = value
        return result

    try:
        data = json.loads(
            _read_vault_regular(
                root_path, ("System", ".baseline-manifest.json"),
                "canonical source baseline",
            ).decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationError(f"canonical source baseline cannot be read: {exc}") from exc
    if not isinstance(data, dict):
        raise MigrationError("canonical source baseline must be a JSON object")
    system_version = data.get("system_version")
    files = data.get("files")
    if not isinstance(system_version, str) or not SEMVER_RE.fullmatch(system_version):
        raise MigrationError("canonical source baseline has invalid system_version")
    if not isinstance(files, dict) or not files:
        raise MigrationError("canonical source baseline has no files map")
    casefolded_paths = set()
    for relpath, digest in files.items():
        parts = Path(relpath).parts if isinstance(relpath, str) else ()
        if (
            not isinstance(relpath, str)
            or not relpath
            or "\\" in relpath
            or os.path.isabs(relpath)
            or not parts
            or any(part in {"", ".", ".."} for part in parts)
            or Path(relpath).as_posix() != relpath
            or not isinstance(digest, str)
            or not HASH_RE.fullmatch(digest)
        ):
            raise MigrationError("canonical source baseline has an invalid path/hash entry")
        folded = relpath.casefold()
        if folded in casefolded_paths:
            raise MigrationError("canonical source baseline has a case-colliding path")
        casefolded_paths.add(folded)
    manifest_path = root_path / "SYSTEM-MANIFEST.yaml"
    try:
        live_manifest = load_unique_yaml_file(manifest_path, "SYSTEM-MANIFEST.yaml")
        live_system_version = str(live_manifest["system"]["system_version"])
    except (MigrationError, KeyError, TypeError) as exc:
        raise MigrationError(f"live system version cannot be verified: {exc}") from exc
    if live_system_version != system_version:
        raise MigrationError(
            "canonical source baseline version does not match live system_version: "
            f"{system_version} != {live_system_version}"
        )
    canonical = json.dumps(
        {"files": files, "system_version": system_version},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _semver(value: Any, field: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not SEMVER_RE.fullmatch(value):
        raise MigrationError(f"{field} must be an exact stable SemVer (MAJOR.MINOR.PATCH)")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def _strict_keys(mapping: Any, allowed: set[str], label: str) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        raise MigrationError(f"{label} must be a mapping")
    unknown = set(mapping) - allowed
    if unknown:
        raise MigrationError(f"{label} has unknown field(s): {sorted(unknown)}")
    return mapping


def _validate_selector(selector: Any) -> None:
    selector = _strict_keys(selector, {"all", "type", "path_prefix"}, "content_selector")
    if not selector:
        raise MigrationError("content_selector must not be empty")
    if "all" in selector and selector["all"] is not True:
        raise MigrationError("content_selector.all, when present, must be true")
    if selector.get("all") and len(selector) != 1:
        raise MigrationError("content_selector.all cannot be combined with another selector")
    if "type" in selector and (
        not isinstance(selector["type"], str) or not selector["type"].strip()
    ):
        raise MigrationError("content_selector.type must be a non-empty string")
    if "path_prefix" in selector:
        prefix = selector["path_prefix"]
        if (
            not isinstance(prefix, str)
            or not prefix
            or os.path.isabs(prefix)
            or ".." in Path(prefix).parts
        ):
            raise MigrationError("content_selector.path_prefix must be a safe relative path")


def _validate_transform(transform: Any) -> None:
    transform = _strict_keys(transform, {"replace_exact_files"}, "transform")
    if set(transform) != {"replace_exact_files"}:
        raise MigrationError("transform must declare replace_exact_files")
    entries = transform["replace_exact_files"]
    if not isinstance(entries, list) or not entries:
        raise MigrationError("replace_exact_files must be a non-empty list")
    destinations = set()
    for index, entry in enumerate(entries):
        entry = _strict_keys(
            entry,
            {"path", "old_sha256", "payload", "new_sha256", "mode"},
            f"replace_exact_files[{index}]",
        )
        required = {"path", "old_sha256", "payload", "new_sha256"}
        if not required.issubset(entry):
            raise MigrationError(f"replace_exact_files[{index}] has missing fields")
        destination = _safe_relative(entry["path"], f"replace_exact_files[{index}].path")
        _safe_relative(entry["payload"], f"replace_exact_files[{index}].payload")
        if destination.as_posix() in destinations:
            raise MigrationError("replace_exact_files destination paths must be unique")
        destinations.add(destination.as_posix())
        old_hash = entry["old_sha256"]
        old_hashes = old_hash if isinstance(old_hash, list) else [old_hash]
        if (
            not old_hashes
            or len(set(old_hashes)) != len(old_hashes)
            or any(
                value != "absent"
                and (not isinstance(value, str) or not HASH_RE.fullmatch(value))
                for value in old_hashes
            )
        ):
            raise MigrationError(
                "old_sha256 must be a lowercase SHA-256, 'absent', or a "
                "non-empty unique list of those exact preconditions"
            )
        if "absent" in old_hashes:
            if entry.get("mode") not in {"0600", "0644", "0755"}:
                raise MigrationError(
                    "absent exact-file destinations require safe mode 0600, 0644, or 0755"
                )
        elif "mode" in entry:
            raise MigrationError("mode is only allowed when old_sha256 is 'absent'")
        if not isinstance(entry["new_sha256"], str) or not HASH_RE.fullmatch(
            entry["new_sha256"]
        ):
            raise MigrationError("new_sha256 must be a lowercase SHA-256")


def _validate_checks(checks: Any) -> None:
    if not isinstance(checks, list) or not checks:
        raise MigrationError("validation must be a non-empty list")
    for index, item in enumerate(checks):
        item = _strict_keys(item, {"check", "field"}, f"validation[{index}]")
        check = item.get("check")
        if check == "vault-validate":
            if set(item) != {"check"}:
                raise MigrationError("vault-validate accepts no additional fields")
        elif check in {"field-absent", "field-present"}:
            if (
                set(item) != {"check", "field"}
                or not isinstance(item["field"], str)
                or not FIELD_RE.fullmatch(item["field"])
            ):
                raise MigrationError(f"{check} requires one field matching [a-z][a-z0-9_]*")
        else:
            raise MigrationError(f"validation[{index}] has unsupported check: {check!r}")
    if not any(item.get("check") == "vault-validate" for item in checks):
        raise MigrationError("validation must include vault-validate")


def load_manifest(path: os.PathLike[str] | str) -> Manifest:
    manifest_path = Path(path)
    loaded = load_unique_yaml_file(manifest_path, "migration manifest")
    data = _strict_keys(loaded, MANIFEST_FIELDS, "manifest")
    missing = MANIFEST_FIELDS - set(data)
    if missing:
        raise MigrationError(f"manifest is missing required field(s): {sorted(missing)}")
    if data["schema_version"] != SCHEMA_VERSION:
        raise MigrationError(
            f"unsupported migration schema_version {data['schema_version']!r}; "
            f"expected {SCHEMA_VERSION}"
        )
    if data["version_target"] not in VERSION_TARGETS:
        raise MigrationError(
            "version_target must be one of: "
            + ", ".join(sorted(VERSION_TARGETS))
        )
    if (
        not isinstance(data["source_distribution"], str)
        or data["source_distribution"] not in DISTRIBUTIONS
    ):
        raise MigrationError(
            "source_distribution must be one of: "
            + ", ".join(sorted(DISTRIBUTIONS))
        )
    if not isinstance(data["source_identity"], str) or not HASH_RE.fullmatch(
        data["source_identity"]
    ):
        raise MigrationError("source_identity must be a lowercase SHA-256")
    directory = manifest_path.parent
    if directory.is_symlink():
        raise MigrationError("migration directory must not be a symlink")
    match = re.fullmatch(r"([0-9]{3})-[a-z0-9]+(?:-[a-z0-9]+)*", directory.name)
    if not match:
        raise MigrationError("migration directory must be NNN-kebab-case")
    sequence = int(match.group(1))
    expected_id = f"migration-{directory.name}"
    if data["id"] != expected_id or not ID_RE.fullmatch(str(data["id"])):
        raise MigrationError(f"id must exactly match its directory: {expected_id}")
    start = _semver(data["from_version"], "from_version")
    end = _semver(data["to_version"], "to_version")
    if end <= start:
        raise MigrationError("to_version must be greater than from_version")
    prereqs = data["prerequisites"]
    if (
        not isinstance(prereqs, list)
        or any(not isinstance(item, str) or not ID_RE.fullmatch(item) for item in prereqs)
        or len(set(prereqs)) != len(prereqs)
        or data["id"] in prereqs
    ):
        raise MigrationError("prerequisites must be unique migration ids and may not include self")
    _validate_selector(data["content_selector"])
    _validate_transform(data["transform"])
    _validate_checks(data["validation"])
    rollback = _strict_keys(
        data["rollback"],
        {"strategy", "automatic_on_validation_failure"},
        "rollback",
    )
    if rollback != {
        "strategy": "exact-checkpoint",
        "automatic_on_validation_failure": True,
    }:
        raise MigrationError(
            "rollback must require exact-checkpoint and automatic_on_validation_failure: true"
        )
    if not isinstance(data["idempotency_key"], str) or not KEY_RE.fullmatch(
        data["idempotency_key"]
    ):
        raise MigrationError("idempotency_key must be a lowercase kebab-case string")
    declared = data["manifest_hash"]
    actual = compute_manifest_hash(data)
    if not isinstance(declared, str) or not HASH_RE.fullmatch(declared):
        raise MigrationError("manifest_hash must be a lowercase SHA-256")
    if declared != actual:
        raise MigrationError(
            f"manifest_hash mismatch: declared {declared}, computed {actual}"
        )
    return Manifest(directory=directory, data=data, manifest_hash=actual, sequence=sequence)


def discover(migrations_dir: os.PathLike[str] | str) -> list[Manifest]:
    root = Path(migrations_dir)
    try:
        system = root.parent
        vault = system.parent.resolve(strict=True)
        if root.resolve(strict=True) != vault / "System/Migrations":
            raise MigrationError("migration root must be exactly vault/System/Migrations")
        for path, label in ((system, "System"), (root, "System/Migrations")):
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise MigrationError(f"{label} must be a real directory, not a symlink")
    except OSError as exc:
        raise MigrationError(f"migration root is missing or unsafe: {exc}") from exc
    manifests = []
    for entry in sorted(os.scandir(root), key=lambda item: item.name):
        if not re.fullmatch(r"[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*", entry.name):
            continue
        if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
            raise MigrationError(f"migration directory is unsafe: {entry.name}")
        if entry.name.startswith("000-"):
            continue
        manifests.append(load_manifest(Path(entry.path) / "migration.yaml"))
    ids = [item.id for item in manifests]
    keys = [item.data["idempotency_key"] for item in manifests]
    if len(ids) != len(set(ids)):
        raise MigrationError("duplicate migration id")
    if len(keys) != len(set(keys)):
        raise MigrationError("duplicate migration idempotency_key")
    sequences = [item.sequence for item in manifests]
    if len(sequences) != len(set(sequences)):
        raise MigrationError("duplicate migration sequence number")
    known = {item.id: item for item in manifests}
    for manifest in manifests:
        for prerequisite in manifest.data["prerequisites"]:
            dependency = known.get(prerequisite)
            if dependency is None:
                raise MigrationError(
                    f"{manifest.id} names unknown prerequisite {prerequisite}"
                )
            if dependency.sequence >= manifest.sequence:
                raise MigrationError(
                    f"{manifest.id} prerequisite must have a lower sequence: {prerequisite}"
                )
    return manifests


def load_ledger(root: os.PathLike[str] | str) -> list[dict[str, Any]]:
    root_path = Path(root).resolve(strict=True)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    directory_flags = os.O_RDONLY | directory | nofollow
    root_fd = system_fd = journal_fd = ledger_fd = None
    try:
        root_fd = os.open(root_path, directory_flags)
        system_fd = os.open("System", directory_flags, dir_fd=root_fd)
        journal_fd = os.open("Journal", directory_flags, dir_fd=system_fd)
        try:
            ledger_fd = os.open(
                LEDGER_RELATIVE_PATH.name,
                os.O_RDONLY | nofollow,
                dir_fd=journal_fd,
            )
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                return []
            raise
        if not stat.S_ISREG(os.fstat(ledger_fd).st_mode):
            raise MigrationError("migration ledger must be a regular file")
        chunks = []
        while True:
            chunk = os.read(ledger_fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        text = b"".join(chunks).decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise MigrationError(
            f"migration ledger path is missing, unsafe, symlinked, or unreadable: {exc}"
        ) from exc
    finally:
        for fd in (ledger_fd, journal_fd, system_fd, root_fd):
            if fd is not None:
                os.close(fd)
    records = []
    seen_ids = set()
    seen_keys = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            raise MigrationError(f"migration ledger line {number} is blank")
        try:
            record = json.loads(
                line,
                object_pairs_hook=lambda pairs: _reject_duplicate_json(
                    pairs, f"migration ledger line {number}"
                ),
            )
        except (json.JSONDecodeError, MigrationError) as exc:
            raise MigrationError(f"migration ledger line {number} is invalid JSON") from exc
        if not isinstance(record, dict) or set(record) != LEDGER_FIELDS:
            raise MigrationError(f"migration ledger line {number} has an invalid record shape")
        if (
            not ID_RE.fullmatch(str(record["id"]))
            or record["version_target"] not in VERSION_TARGETS
            or not KEY_RE.fullmatch(str(record["source_distribution"]))
            or not HASH_RE.fullmatch(str(record["source_identity"]))
            or not HASH_RE.fullmatch(str(record["manifest_hash"]))
            or record["result"] not in RESULTS
            or not KEY_RE.fullmatch(str(record["idempotency_key"]))
        ):
            raise MigrationError(f"migration ledger line {number} has invalid values")
        _semver(record["from_version"], f"ledger line {number} from_version")
        _semver(record["to_version"], f"ledger line {number} to_version")
        _semver(record["tool_version"], f"ledger line {number} tool_version")
        try:
            timestamp = record["timestamp"]
            if (
                not isinstance(timestamp, str)
                or not timestamp.endswith("Z")
                or "T" not in timestamp
            ):
                raise ValueError
            parsed_timestamp = _datetime.datetime.fromisoformat(
                timestamp[:-1] + "+00:00"
            )
            if parsed_timestamp.tzinfo != _datetime.timezone.utc:
                raise ValueError
        except (AttributeError, ValueError) as exc:
            raise MigrationError(f"migration ledger line {number} timestamp is invalid") from exc
        if not isinstance(record["checkpoint"], dict):
            raise MigrationError(f"migration ledger line {number} checkpoint is invalid")
        _validate_checkpoint_identity(record["checkpoint"], f"migration ledger line {number}")
        if record["id"] in seen_ids:
            raise MigrationError(f"migration ledger has duplicate applied id: {record['id']}")
        if record["idempotency_key"] in seen_keys:
            raise MigrationError("migration ledger has duplicate idempotency_key")
        seen_ids.add(record["id"])
        seen_keys.add(record["idempotency_key"])
        records.append(record)
    return records


def _reject_duplicate_json(pairs, label: str):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MigrationError(f"{label} has duplicate JSON key: {key}")
        result[key] = value
    return result


def _validate_checkpoint_identity(identity: Any, label: str) -> None:
    if not isinstance(identity, dict):
        raise MigrationError(f"{label} checkpoint is not a mapping")
    common = {
        "kind", "target", "scope", "coverage", "exact_recovery",
    }
    kind = identity.get("kind")
    if kind == "git-commit":
        required = common | {"tracked_sha256", "git_tree"}
        if set(identity) != required:
            raise MigrationError(f"{label} git checkpoint has an invalid shape")
        if (
            not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", str(identity.get("target")))
            or not HASH_RE.fullmatch(str(identity.get("tracked_sha256")))
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", str(identity.get("git_tree")))
        ):
            raise MigrationError(f"{label} git checkpoint has invalid hashes")
    elif kind == "zip-snapshot":
        required = common | {"sha256", "tree_sha256"}
        if set(identity) != required:
            raise MigrationError(f"{label} snapshot checkpoint has an invalid shape")
        if not HASH_RE.fullmatch(str(identity.get("sha256"))) or not HASH_RE.fullmatch(
            str(identity.get("tree_sha256"))
        ):
            raise MigrationError(f"{label} snapshot checkpoint has invalid hashes")
        if not isinstance(identity.get("target"), str) or not identity["target"]:
            raise MigrationError(f"{label} snapshot checkpoint target is invalid")
    else:
        raise MigrationError(f"{label} checkpoint kind is invalid")
    scope = identity.get("scope")
    if kind == "git-commit":
        valid_scope = (
            isinstance(scope, dict)
            and set(scope) == {"mode", "requested_paths", "committed_paths"}
            and scope.get("mode") in {"whole-tree", "clean-head"}
            and scope.get("requested_paths") == []
            and isinstance(scope.get("committed_paths"), list)
            and (
                scope.get("mode") != "clean-head"
                or scope.get("committed_paths") == []
            )
        )
    else:
        valid_scope = scope == {"mode": "whole-tree", "paths": []}
    if (
        identity.get("coverage") != "whole-tree"
        or identity.get("exact_recovery") is not True
        or not valid_scope
    ):
        raise MigrationError(f"{label} checkpoint is not exact whole-tree recovery")


def append_ledger(root: os.PathLike[str] | str, record: dict[str, Any]) -> None:
    if set(record) != LEDGER_FIELDS:
        raise MigrationError("refusing to append malformed migration ledger record")
    root_path = Path(root).resolve(strict=True)
    path = root_path / LEDGER_RELATIVE_PATH
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    directory_flags = os.O_RDONLY | directory | nofollow
    try:
        root_fd = os.open(root_path, directory_flags)
        system_fd = os.open("System", directory_flags, dir_fd=root_fd)
        journal_fd = os.open("Journal", directory_flags, dir_fd=system_fd)
    except OSError as exc:
        for fd_name in ("journal_fd", "system_fd", "root_fd"):
            fd = locals().get(fd_name)
            if fd is not None:
                os.close(fd)
        raise MigrationError(
            f"migration ledger parent is missing, unsafe, or symlinked: {exc}"
        ) from exc
    line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | nofollow
    try:
        fd = os.open(path.name, flags, 0o600, dir_fd=journal_fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise MigrationError("migration ledger target is not a regular file")
            payload = line.encode("utf-8")
            if os.write(fd, payload) != len(payload):
                raise MigrationError("migration ledger append was incomplete")
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(journal_fd)
    except OSError as exc:
        raise MigrationError(f"migration ledger append refused: {exc}") from exc
    finally:
        os.close(journal_fd)
        os.close(system_fd)
        os.close(root_fd)


def append_change_journal(root: os.PathLike[str] | str, line: str) -> None:
    """Append one durable line without following any vault-internal symlink."""
    root_path = Path(root).resolve(strict=True)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
    fds = []
    try:
        root_fd = os.open(root_path, directory_flags); fds.append(root_fd)
        system_fd = os.open("System", directory_flags, dir_fd=root_fd); fds.append(system_fd)
        journal_fd = os.open("Journal", directory_flags, dir_fd=system_fd); fds.append(journal_fd)
        fd = os.open(CHANGE_JOURNAL_NAME, os.O_APPEND | os.O_WRONLY | nofollow, dir_fd=journal_fd)
        fds.append(fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise MigrationError("change journal must be a regular file")
        payload = ("\n" + line.rstrip("\n")).encode("utf-8")
        if os.write(fd, payload) != len(payload):
            raise MigrationError("change journal append was incomplete")
        os.fsync(fd)
        os.fsync(journal_fd)
    except OSError as exc:
        raise MigrationError(
            f"change journal append refused; path is missing, unsafe, or symlinked: {exc}"
        ) from exc
    finally:
        for fd in reversed(fds):
            os.close(fd)


def successful_ids(records: Iterable[dict[str, Any]]) -> set[str]:
    return {record["id"] for record in records if record["result"] == "applied"}


def preflight_sequence(
    selected: Manifest,
    available: list[Manifest],
    records: list[dict[str, Any]],
    current_version: str,
    current_source_identity: str | None,
) -> str:
    """Return ``apply`` or ``noop``; otherwise refuse before any mutation."""
    _semver(current_version, f"current {selected.version_target}")
    known = {manifest.id: manifest for manifest in available}
    applied_history = successful_ids(records)
    earlier_ids: set[str] = set()
    for record in records:
        manifest = known.get(record["id"])
        if manifest is None:
            raise MigrationError(f"ledger references unknown migration: {record['id']}")
        expected = {
            "version_target": manifest.version_target,
            "source_distribution": manifest.source_distribution,
            "source_identity": manifest.source_identity,
            "from_version": manifest.from_version,
            "to_version": manifest.to_version,
            "manifest_hash": manifest.manifest_hash,
            "idempotency_key": manifest.data["idempotency_key"],
        }
        if any(record[field] != value for field, value in expected.items()):
            raise MigrationError(f"ledger record does not match discovered manifest: {manifest.id}")
        missing = set(manifest.data["prerequisites"]) - earlier_ids
        if missing:
            raise MigrationError(
                f"ledger record {manifest.id} lacks prerequisite record(s): {sorted(missing)}"
            )
        earlier_ids.add(record["id"])
    same_id = [record for record in records if record["id"] == selected.id]
    if any(record["manifest_hash"] != selected.manifest_hash for record in same_id):
        raise MigrationError(
            f"{selected.id} was previously recorded with a different manifest hash"
        )
    for record in same_id:
        expected = {
            "version_target": selected.version_target,
            "source_distribution": selected.source_distribution,
            "source_identity": selected.source_identity,
            "from_version": selected.from_version,
            "to_version": selected.to_version,
            "idempotency_key": selected.data["idempotency_key"],
        }
        if any(record[field] != value for field, value in expected.items()):
            raise MigrationError(
                f"{selected.id} has an inconsistent applied ledger record"
            )
    if any(record["result"] == "applied" for record in same_id):
        if current_version != selected.to_version:
            raise MigrationError(
                f"{selected.id} is recorded applied, but live "
                f"{selected.version_target} is {current_version}, "
                f"not {selected.to_version}"
            )
        return "noop"

    if not isinstance(current_source_identity, str) or not HASH_RE.fullmatch(
        current_source_identity
    ):
        raise MigrationError("current source identity is not a lowercase SHA-256")

    applied = applied_history

    # Sequence numbers prove the shipped manifest set is intact; they do not
    # define one universal execution history. Multiple later-numbered root
    # migrations may be alternative direct edges from distinct supported
    # historical versions. Only an explicitly declared prerequisite creates an
    # ordering obligation.
    required: set[str] = set()
    pending = list(selected.data["prerequisites"])
    while pending:
        prerequisite = pending.pop()
        if prerequisite in required:
            continue
        dependency = known.get(prerequisite)
        if dependency is None:  # discover() normally catches this; fail closed here too.
            raise MigrationError(f"unknown prerequisite: {prerequisite}")
        required.add(prerequisite)
        pending.extend(dependency.data["prerequisites"])

    missing_prereqs = required - applied
    if missing_prereqs:
        raise MigrationError(
            "declared prerequisite chain is incomplete; missing: "
            f"{sorted(missing_prereqs)}"
        )
    for prerequisite in required:
        dependency = known[prerequisite]
        expected = {
            "version_target": dependency.version_target,
            "source_distribution": dependency.source_distribution,
            "source_identity": dependency.source_identity,
            "from_version": dependency.from_version,
            "to_version": dependency.to_version,
            "manifest_hash": dependency.manifest_hash,
        }
        applied_records = [
            record
            for record in records
            if record["id"] == prerequisite and record["result"] == "applied"
        ]
        if any(
            record[field] != value
            for record in applied_records
            for field, value in expected.items()
        ):
            raise MigrationError(
                f"declared prerequisite {prerequisite} has an inconsistent ledger record"
            )

    # Each same-authority prerequisite edge must join exactly. Dependencies on
    # another version authority are gates, not version edges, and therefore do
    # not participate in this comparison.
    for node in [selected] + [known[item] for item in required]:
        for prerequisite in node.data["prerequisites"]:
            dependency = known[prerequisite]
            if (
                dependency.version_target == node.version_target
                and dependency.to_version != node.from_version
            ):
                raise MigrationError(
                    f"version-chain gap for {node.version_target}: "
                    f"{dependency.id} ends at {dependency.to_version}, "
                    f"but {node.id} starts at {node.from_version}"
                )
    if current_version != selected.from_version:
        raise MigrationError(
            f"wrong source version: vault is {current_version}, "
            f"migration requires exactly {selected.from_version}"
        )
    if current_source_identity != selected.source_identity:
        raise MigrationError(
            "wrong source identity: version matches, but the canonical baseline "
            "does not match this migration edge"
        )
    return "apply"


def ledger_record(
    manifest: Manifest, checkpoint: dict[str, Any], result: str
) -> dict[str, Any]:
    if result not in RESULTS:
        raise MigrationError(f"invalid migration result: {result}")
    _validate_checkpoint_identity(checkpoint, "new ledger record")
    return {
        "id": manifest.id,
        "version_target": manifest.version_target,
        "source_distribution": manifest.source_distribution,
        "source_identity": manifest.source_identity,
        "from_version": manifest.from_version,
        "to_version": manifest.to_version,
        "manifest_hash": manifest.manifest_hash,
        "timestamp": _datetime.datetime.now(_datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "checkpoint": checkpoint,
        "result": result,
        "tool_version": TOOL_VERSION,
        "idempotency_key": manifest.data["idempotency_key"],
    }
