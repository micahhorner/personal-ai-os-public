"""Strict loader for the release-qualification support matrix."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import re
from typing import Any

import yaml


SCHEMA_VERSION = 1
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DISPOSITIONS = frozenset({
    "candidate-direct",
    "candidate-anchor",
    "candidate-bridge",
    "rescue",
    "not-supported",
})
FIXTURE_MODES = frozenset({"clean-git", "no-git"})


class MatrixError(ValueError):
    """The support matrix is malformed or insufficiently pinned."""


@dataclass(frozen=True)
class ReleasePin:
    ref: str
    commit: str
    version: str


@dataclass(frozen=True)
class SourcePin(ReleasePin):
    id: str
    disposition: str
    fixture_mode: str = "clean-git"
    accepted_paths: tuple[str, ...] = ()
    authorize_legacy_core: bool = False


@dataclass(frozen=True)
class SupportMatrix:
    schema_version: int
    target: ReleasePin
    sources: tuple[SourcePin, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MatrixError(f"{label} must be an object")
    return value


def _keys(value: dict[str, Any], allowed: set[str], required: set[str],
          label: str) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        raise MatrixError(f"{label} has unknown keys: {', '.join(unknown)}")
    if missing:
        raise MatrixError(f"{label} is missing keys: {', '.join(missing)}")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise MatrixError(f"{label} must be a nonempty string")
    return value


def _release(value: Any, label: str) -> ReleasePin:
    item = _mapping(value, label)
    _keys(item, {"ref", "commit", "version"},
          {"ref", "commit", "version"}, label)
    ref = _text(item["ref"], f"{label}.ref")
    commit = _text(item["commit"], f"{label}.commit")
    version = _text(item["version"], f"{label}.version")
    if not COMMIT_RE.fullmatch(commit):
        raise MatrixError(f"{label}.commit must be a full lowercase SHA-1")
    if not VERSION_RE.fullmatch(version):
        raise MatrixError(f"{label}.version must be SemVer")
    return ReleasePin(ref, commit, version)


def _source(value: Any, index: int) -> SourcePin:
    label = f"sources[{index}]"
    item = _mapping(value, label)
    allowed = {
        "id", "ref", "commit", "version", "disposition",
        "fixture_mode", "accepted_paths", "authorize_legacy_core",
    }
    required = {"id", "ref", "commit", "version", "disposition"}
    _keys(item, allowed, required, label)
    release = _release(
        {key: item[key] for key in ("ref", "commit", "version")}, label)
    run_id = _text(item["id"], f"{label}.id")
    if not ID_RE.fullmatch(run_id):
        raise MatrixError(f"{label}.id is not a safe run identifier")
    disposition = _text(item["disposition"], f"{label}.disposition")
    if disposition not in DISPOSITIONS:
        raise MatrixError(f"{label}.disposition is not recognized")
    fixture_mode = item.get("fixture_mode", "clean-git")
    if fixture_mode not in FIXTURE_MODES:
        raise MatrixError(f"{label}.fixture_mode is not recognized")
    authorize_legacy_core = item.get("authorize_legacy_core", False)
    if not isinstance(authorize_legacy_core, bool):
        raise MatrixError(f"{label}.authorize_legacy_core must be boolean")
    if disposition == "not-supported" and authorize_legacy_core:
        raise MatrixError(
            f"{label}.authorize_legacy_core cannot authorize an unsupported source"
        )
    paths = item.get("accepted_paths", [])
    if not isinstance(paths, list) or any(
            not isinstance(path, str) or not path or "\x00" in path
            for path in paths):
        raise MatrixError(f"{label}.accepted_paths must be nonempty strings")
    if len(paths) != len(set(paths)):
        raise MatrixError(f"{label}.accepted_paths contains duplicates")
    for path in paths:
        parsed = PurePosixPath(path)
        if (parsed.is_absolute() or "\\" in path
                or any(part in {"", ".", ".."} for part in parsed.parts)):
            raise MatrixError(
                f"{label}.accepted_paths must be contained relative paths")
    return SourcePin(
        ref=release.ref,
        commit=release.commit,
        version=release.version,
        id=run_id,
        disposition=disposition,
        fixture_mode=fixture_mode,
        accepted_paths=tuple(paths),
        authorize_legacy_core=authorize_legacy_core,
    )


def load_support_matrix(path: str | Path) -> SupportMatrix:
    """Load and strictly validate one YAML or JSON support matrix."""
    source = Path(path)
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise MatrixError(f"cannot read support matrix {source}: {exc}") from exc
    root = _mapping(document, "matrix")
    _keys(root, {"schema_version", "target", "sources"},
          {"schema_version", "target", "sources"}, "matrix")
    if root["schema_version"] != SCHEMA_VERSION:
        raise MatrixError(
            f"matrix.schema_version must be {SCHEMA_VERSION}")
    sources = root["sources"]
    if not isinstance(sources, list) or not sources:
        raise MatrixError("matrix.sources must be a nonempty list")
    loaded = tuple(_source(value, index)
                   for index, value in enumerate(sources))
    ids = [source.id for source in loaded]
    if len(ids) != len(set(ids)):
        raise MatrixError("matrix.sources contains duplicate ids")
    return SupportMatrix(
        schema_version=SCHEMA_VERSION,
        target=_release(root["target"], "target"),
        sources=loaded,
    )
