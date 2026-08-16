"""Hash-bound activation receipts for installed packs.

Presence under ``Packs/`` is not trust. A component becomes active only when
the installed bytes match an append-only receipt written by ``aios pack`` or a
frozen, exact bootstrap identity shipped with the product.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat

from lib.safepaths import (SafePathError, atomic_create_files,
                           preflight_contained_regular_files)


RECEIPT_REL = os.path.join("System", "Journal", "pack-install-receipts.jsonl")

# Compatibility for the one pack shipped in the recovery-release tree. This is
# an exact byte identity, not "anything already present is trusted". A changed
# or manually copied tree does not match and stays inactive until reviewed by
# `aios pack`. The digest is filled from the release tree by the W5 build.
BOOTSTRAP_TREE_SHA256 = {
    "pack-obsidian-bases": "19f1b32168e3499fce88b3e00b687c8fabc68a731cbe4e07ab1a7d068e0218f5",
}


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def pack_tree_sha256(pack_root: str) -> str:
    """Digest paths, lengths, and bytes for every regular file in a pack."""
    root_mode = os.lstat(pack_root).st_mode
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise ValueError(f"pack root is not a real directory: {pack_root}")
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(pack_root):
        for dirname in dirnames:
            child = os.path.join(dirpath, dirname)
            mode = os.lstat(child).st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise ValueError(f"pack contains non-directory child: {child}")
        dirnames[:] = sorted(dirnames)
        for filename in sorted(filenames):
            path = os.path.join(dirpath, filename)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                raise ValueError(f"pack contains non-regular file: {path}")
            rel = os.path.relpath(path, pack_root).replace(os.sep, "/")
            with open(path, "rb") as stream:
                raw = stream.read()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(len(raw)).encode("ascii"))
            digest.update(b"\0")
            digest.update(raw)
            digest.update(b"\0")
    return digest.hexdigest()


def _manifest_identity(pack_root: str):
    import yaml
    try:
        with open(os.path.join(pack_root, "pack.yaml"), encoding="utf-8") as stream:
            manifest = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return None, None
    if not isinstance(manifest, dict):
        return None, None
    return str(manifest.get("id") or ""), str(manifest.get("version") or "")


def _parse_receipts(text: str):
    previous = ""
    records = []
    try:
        for line in text.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                return None
            claimed = record.get("receipt_sha256")
            body = {k: v for k, v in record.items() if k != "receipt_sha256"}
            if body.get("previous_receipt_sha256", "") != previous:
                return None
            actual = hashlib.sha256(canonical_json(body)).hexdigest()
            if claimed != actual:
                return None
            records.append(record)
            previous = actual
    except json.JSONDecodeError:
        return None
    return records


def _valid_receipts(root: str):
    path = os.path.join(root, RECEIPT_REL)
    if not os.path.isfile(path) or os.path.islink(path):
        return []
    try:
        with open(path, encoding="utf-8") as stream:
            return _parse_receipts(stream.read()) or []
    except (OSError, UnicodeDecodeError):
        return []


def activation_status(root: str, pack_root: str):
    """Return (active, reason, tree hash) without modifying the vault."""
    pack_id, version = _manifest_identity(pack_root)
    if not pack_id or not version:
        return False, "manifest identity unavailable", None
    try:
        tree_hash = pack_tree_sha256(pack_root)
    except (OSError, ValueError):
        return False, "pack tree is not regular and readable", None
    if BOOTSTRAP_TREE_SHA256.get(pack_id) == tree_hash:
        return True, "frozen recovery-release bootstrap identity", tree_hash
    matching = None
    for record in reversed(_valid_receipts(root)):
        if (record.get("pack_id") == pack_id
                and record.get("version") == version
                and record.get("installed_tree_sha256") == tree_hash):
            matching = record
            break
    if matching is None:
        return False, "no matching install receipt", tree_hash
    if matching.get("action") != "activate":
        return False, "matching receipt revokes activation", tree_hash
    return True, "matching hash-bound install receipt", tree_hash


def append_receipt(root: str, *, action: str, pack_id: str, version: str,
                   installed_tree_sha256: str, review_sha256: str,
                   archive_sha256: str) -> dict:
    """Append one chained activation/revocation record; never rewrite history."""
    if action not in ("activate", "revoke"):
        raise ValueError("receipt action must be activate or revoke")
    path = os.path.join(root, RECEIPT_REL)
    batch = None
    try:
        if os.path.lexists(path):
            batch = preflight_contained_regular_files(root, [path])
            raw = batch.read_bytes(max_bytes=16 * 1024 * 1024)[os.path.abspath(path)]
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("pack receipt ledger is not UTF-8") from exc
            existing = _parse_receipts(text)
            if existing is None:
                raise ValueError("pack receipt ledger is malformed; refusing to append")
        else:
            raw, existing = b"", []
        previous = existing[-1]["receipt_sha256"] if existing else ""
        record = {
            "action": action,
            "archive_sha256": archive_sha256,
            "installed_tree_sha256": installed_tree_sha256,
            "pack_id": pack_id,
            "previous_receipt_sha256": previous,
            "review_sha256": review_sha256,
            "version": version,
        }
        record["receipt_sha256"] = hashlib.sha256(canonical_json(record)).hexdigest()
        line = json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
        if batch is None:
            atomic_create_files(root, {RECEIPT_REL: line})
        else:
            batch.atomic_replace_many({RECEIPT_REL: raw + line})
        return record
    except SafePathError as exc:
        raise ValueError(f"pack receipt safe transaction refused: {exc}") from exc
    finally:
        if batch is not None:
            batch.close()
