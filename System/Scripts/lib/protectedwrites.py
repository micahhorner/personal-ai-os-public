"""Manifest-derived protected-target classification for ordinary writers.

This module does not grant authority.  It only answers the fail-closed half of
the question: whether a relative target intersects an object the live vault
manifest says requires explicit human instruction.
"""
from __future__ import annotations

import fnmatch
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping

import yaml

from lib.safepaths import ReadOnlyFile, SafePathError, read_regular_file


class ProtectedTargetError(RuntimeError):
    """An ordinary/content-derived write selected a protected target."""


_MANIFEST_MAX_BYTES = 1024 * 1024
_FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", re.DOTALL)


@dataclass(frozen=True)
class ProtectionProof:
    """Descriptor-bound live policy that can be re-proved at commit time."""

    manifest: ReadOnlyFile
    entries: tuple[str, ...]

    def reprove(self) -> None:
        self.manifest.reprove()

    def match(self, relpath: str) -> str | None:
        target = _key(_portable(relpath))
        for entry in self.entries:
            pattern = _key(entry)
            if not any(char in pattern for char in "*?["):
                if target == pattern or target.startswith(pattern + "/"):
                    return entry
            elif fnmatch.fnmatchcase(target, pattern):
                return entry
        return None


def _portable(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ProtectedTargetError("protected-write target must be a portable relative path")
    value = value.replace(os.sep, "/")
    if (value.startswith("/") or re.match(r"^[A-Za-z]:", value)
            or any(part in ("", ".", "..") for part in value.rstrip("/").split("/"))):
        raise ProtectedTargetError(
            f"protected-write target must be a contained canonical relative path: {value}"
        )
    return unicodedata.normalize("NFC", value.rstrip("/"))


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def protection_proof(root: str) -> ProtectionProof:
    """Bind and strictly parse the live manifest's protected-object policy."""
    path = os.path.join(os.path.abspath(root), "SYSTEM-MANIFEST.yaml")
    try:
        bound = read_regular_file(path, max_bytes=_MANIFEST_MAX_BYTES)
        manifest = yaml.safe_load(bound.data.decode("utf-8"))
        entries = manifest.get("protected_objects") if isinstance(manifest, dict) else None
        if not isinstance(entries, list) or not entries:
            raise ValueError("protected_objects is absent or empty")
        if not all(isinstance(entry, str) for entry in entries):
            raise ValueError("protected_objects entries must be strings")
        normalized = tuple(_portable(entry) for entry in entries)
        keys = [_key(entry) for entry in normalized]
        if len(keys) != len(set(keys)):
            raise ValueError("protected_objects contains a case/Unicode duplicate")
        return ProtectionProof(bound, normalized)
    except (OSError, UnicodeDecodeError, KeyError, TypeError, ValueError,
            yaml.YAMLError, SafePathError,
            ProtectedTargetError) as exc:
        raise ProtectedTargetError(
            f"cannot establish protected targets from SYSTEM-MANIFEST.yaml: {exc}"
        ) from exc


def protected_objects(root: str) -> tuple[str, ...]:
    """Return the strict live declarations; retained for read-only callers."""
    return protection_proof(root).entries


def protected_target(root: str, relpath: str) -> str | None:
    """Return the matching manifest declaration, including directory/glob roots."""
    return protection_proof(root).match(relpath)


def _approved(text: str | bytes, relpath: str) -> bool:
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtectedTargetError(
                f"cannot establish approval protection for {relpath}: {exc}"
            ) from exc
    if not isinstance(text, str):
        raise ProtectedTargetError(
            f"cannot establish approval protection for {relpath}: target text is unavailable"
        )
    match = _FRONTMATTER.match(text)
    if match is None:
        return False
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ProtectedTargetError(
            f"cannot establish approval protection for {relpath}: malformed frontmatter: {exc}"
        ) from exc
    if not isinstance(meta, dict):
        raise ProtectedTargetError(
            f"cannot establish approval protection for {relpath}: frontmatter is not a mapping"
        )
    return str(meta.get("approval", "")).casefold() == "approved"


def guard_ordinary_write_set(
    root: str,
    relpaths,
    operation: str,
    *,
    texts: Mapping[str, str | bytes] | None = None,
) -> ProtectionProof:
    """Refuse a complete ordinary write set and return its commit-time proof."""
    proof = protection_proof(root)
    normalized_texts = {
        _key(_portable(str(relpath))): text for relpath, text in (texts or {}).items()
    }
    for raw in relpaths:
        relpath = _portable(str(raw))
        matched = proof.match(relpath)
        if matched is not None:
            raise ProtectedTargetError(
                f"{operation} refused: {relpath} intersects protected object {matched}; "
                "content and ordinary commands cannot authorize protected writes"
            )
        text = normalized_texts.get(_key(relpath))
        if text is not None and _approved(text, relpath):
            raise ProtectedTargetError(
                f"{operation} refused: {relpath} has approval: approved; ordinary commands "
                "cannot edit approved material or silently reset the owner's approval"
            )
    return proof


def refuse_protected_targets(root: str, relpaths, operation: str) -> ProtectionProof:
    """Reject the first protected target selected by an ordinary write path."""
    return guard_ordinary_write_set(root, relpaths, operation)
