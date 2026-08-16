"""Safe candidate construction for ``aios upgrade``.

This module deliberately stops before the live-tree commit.  It turns an
already-classified upgrade plan into a complete sibling candidate, validates
that candidate, and removes it again.  The later transaction layer can reuse
the same seams without changing classification semantics.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import uuid
from typing import Callable


class CandidateError(RuntimeError):
    """The candidate could not be proven safe before live mutation."""


MIN_RESERVE_BYTES = 16 * 1024 * 1024
WRITE_ACTIONS = ("replace", "add", "remove")
OWNER_SCHEMA = "aios-upgrade-candidate-owner-v1"
OWNER_FILE = ".aios-candidate-owner.json"
MIGRATION_AUTH_SCHEMA = "aios-upgrade-migration-authorization-v1"
_MIGRATION_AUTH_SECRET = os.urandom(32)


def _free_bytes(path):
    """Available bytes at ``path`` (named seam for deterministic fault tests)."""
    return shutil.disk_usage(path).free


def _same_filesystem(a, b):
    """Whether atomic sibling operations can use one filesystem boundary."""
    return os.stat(a).st_dev == os.stat(b).st_dev


def _transaction_boundary(name, phase, root):
    """No-op hook matching the transaction fault-injection contract."""
    del name, phase, root


def _write_owner(path, record):
    temporary = path + ".partial"
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent_fd = os.open(
            os.path.dirname(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        try:
            os.remove(temporary)
        except FileNotFoundError:
            pass
        raise


def _read_owner(path, expected):
    if os.path.islink(path) or not os.path.isfile(path):
        raise CandidateError(f"candidate ownership marker unavailable: {path}")
    with open(path, encoding="utf-8") as stream:
        record = json.load(stream)
    if not isinstance(record, dict) or record != expected:
        raise CandidateError(f"candidate ownership marker invalid: {path}")
    return record


def _posix_rel(rel):
    rel = str(rel).replace("\\", "/")
    if (not rel or rel.startswith("/") or rel == ".." or rel.startswith("../")
            or "/../" in rel or rel.endswith("/..") or "\x00" in rel):
        raise CandidateError(f"unsafe candidate path: {rel!r}")
    norm = os.path.normpath(rel).replace("\\", "/")
    if norm in ("", ".") or norm != rel:
        raise CandidateError(f"non-canonical candidate path: {rel!r}")
    return rel


def _within(root, path):
    root = os.path.realpath(root)
    path = os.path.realpath(path)
    return path == root or path.startswith(root + os.sep)


def _safe_source(release, rel):
    src = os.path.join(release, *rel.split("/"))
    if not _within(release, src):
        raise CandidateError(f"release source escapes release tree: {rel}")
    if os.path.islink(src) or not os.path.isfile(src):
        raise CandidateError(f"release source is not a regular file: {rel}")
    return src


def _safe_destination(root, rel):
    """Resolve a write target without ever traversing a symlink."""
    target = os.path.join(root, *rel.split("/"))
    current = root
    for part in rel.split("/"):
        current = os.path.join(current, part)
        if os.path.lexists(current) and os.path.islink(current):
            raise CandidateError(f"candidate target traverses a symlink: {rel}")
    if not _within(root, target):
        raise CandidateError(f"candidate target escapes tree: {rel}")
    return target


def tree_identity(root):
    """Stable whole-tree identity, including .git, modes, and symlink targets."""
    root = os.path.abspath(root)
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames.sort()
        filenames.sort()
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        kept = []
        for dirname in dirnames:
            path = os.path.join(dirpath, dirname)
            rel = (rel_dir + "/" + dirname).lstrip("/")
            info = os.lstat(path)
            if os.path.islink(path):
                digest.update(b"L\0" + rel.encode() + b"\0")
                digest.update(str(info.st_mode & 0o7777).encode() + b"\0")
                digest.update(os.readlink(path).encode("utf-8", "surrogateescape") + b"\0")
            else:
                digest.update(b"D\0" + rel.encode() + b"\0")
                digest.update(str(info.st_mode & 0o7777).encode() + b"\0")
                kept.append(dirname)
        dirnames[:] = kept
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            rel = (rel_dir + "/" + filename).lstrip("/")
            info = os.lstat(path)
            if os.path.islink(path):
                digest.update(b"L\0" + rel.encode() + b"\0")
                digest.update(str(info.st_mode & 0o7777).encode() + b"\0")
                digest.update(os.readlink(path).encode("utf-8", "surrogateescape") + b"\0")
                continue
            if not os.path.isfile(path):
                raise CandidateError(f"unsupported special file in vault: {rel}")
            digest.update(b"F\0" + rel.encode() + b"\0")
            digest.update(str(info.st_mode & 0o7777).encode() + b"\0")
            digest.update(str(info.st_size).encode() + b"\0")
            with open(path, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def path_identity(path):
    """Identity of one file/directory/symlink, or ``None`` when absent."""
    if not os.path.lexists(path):
        return None
    if os.path.isdir(path) and not os.path.islink(path):
        return tree_identity(path)
    info = os.lstat(path)
    digest = hashlib.sha256()
    digest.update(str(info.st_mode & 0o7777).encode() + b"\0")
    if os.path.islink(path):
        digest.update(b"L\0")
        digest.update(os.readlink(path).encode("utf-8", "surrogateescape"))
    elif os.path.isfile(path):
        digest.update(b"F\0")
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        raise CandidateError(f"unsupported special path: {path}")
    return digest.hexdigest()


def _tree_bytes(root):
    total = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames
                       if d != "__pycache__"
                       and not os.path.islink(os.path.join(dirpath, d))]
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            try:
                if os.path.isfile(path) and not os.path.islink(path):
                    total += os.path.getsize(path)
            except OSError as exc:
                raise CandidateError(f"cannot measure {path}: {exc}") from exc
    return total


def normalized_write_set(plan):
    """Return the immutable, deterministic write set for a classification."""
    out = {}
    seen = set()
    for action in WRITE_ACTIONS:
        paths = tuple(sorted(_posix_rel(p) for p in plan.get(action, ())))
        if len(paths) != len(set(paths)):
            raise CandidateError(f"duplicate path in {action} plan")
        overlap = seen.intersection(paths)
        if overlap:
            raise CandidateError("path appears in multiple write actions: "
                                 + ", ".join(sorted(overlap)))
        seen.update(paths)
        out[action] = paths
    return out


def plan_identity(plan):
    """Stable identity proving that repeated planning produced the same writes."""
    frozen = normalized_write_set(plan)
    body = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def preflight(root, release, plan, *, is_product_path, seed_paths=(),
              staging_parent=None, reserve_bytes=MIN_RESERVE_BYTES,
              free_bytes=None, same_filesystem=None):
    """Validate the complete declared surface and capacity without writing.

    Capacity is deliberately conservative: one full candidate, one exact
    fallback copy, incoming product bytes, and a fixed reserve.  Refusing early
    is safer than discovering a short disk during commit.
    """
    root = os.path.abspath(root)
    release = os.path.abspath(release)
    parent = os.path.abspath(staging_parent or os.path.dirname(root))
    if not os.path.isdir(parent):
        raise CandidateError(f"candidate parent does not exist: {parent}")
    if _within(root, parent):
        raise CandidateError("candidate parent must be outside the live vault")
    same_filesystem = same_filesystem or _same_filesystem
    free_bytes = free_bytes or _free_bytes
    if not same_filesystem(root, parent):
        raise CandidateError("candidate and live vault are on different filesystems")

    frozen = normalized_write_set(plan)
    seeds = {_posix_rel(p) for p in seed_paths}
    incoming = 0
    for action in ("replace", "add"):
        for rel in frozen[action]:
            if not is_product_path(rel) and rel not in seeds:
                raise CandidateError(f"{action} is outside declared product/seed surface: {rel}")
            _safe_destination(root, rel)
            incoming += os.path.getsize(_safe_source(release, rel))
    for rel in frozen["remove"]:
        if not is_product_path(rel):
            raise CandidateError(f"remove is outside declared product surface: {rel}")
        _safe_destination(root, rel)

    baseline = os.path.join(release, "System", ".baseline-manifest.json")
    if os.path.isfile(baseline) and not os.path.islink(baseline):
        _safe_destination(root, "System/.baseline-manifest.json")
        incoming += os.path.getsize(baseline)
    live_bytes = _tree_bytes(root)
    required = live_bytes * 2 + incoming + max(0, int(reserve_bytes))
    free = free_bytes(parent)
    if free < required:
        raise CandidateError(
            f"insufficient free space for candidate + exact fallback: "
            f"need {required} bytes, have {free}")
    return {
        "plan_identity": plan_identity(plan),
        "live_bytes": live_bytes,
        "incoming_bytes": incoming,
        "reserve_bytes": max(0, int(reserve_bytes)),
        "required_bytes": required,
        "free_bytes": free,
        "same_filesystem": True,
        "write_count": sum(len(frozen[a]) for a in WRITE_ACTIONS),
    }


def _copy_ignore(_dirpath, names):
    return {name for name in names if name == "__pycache__"
            or name.endswith(".pyc")}


def build_candidate(root, release, plan, *, is_product_path, seed_paths=(),
                    staging_parent=None, validator: Callable | None = None,
                    boundary: Callable | None = None, free_bytes=None,
                    same_filesystem=None):
    """Build and validate a full sibling candidate; never mutate ``root``."""
    boundary = boundary or _transaction_boundary
    evidence = preflight(
        root, release, plan, is_product_path=is_product_path,
        seed_paths=seed_paths, staging_parent=staging_parent,
        free_bytes=free_bytes, same_filesystem=same_filesystem)
    parent = os.path.abspath(staging_parent or os.path.dirname(os.path.abspath(root)))
    owner_id = str(uuid.uuid4())
    stage = os.path.join(
        parent,
        f".{os.path.basename(os.path.abspath(root))}.aios-upgrade-{owner_id}")
    os.mkdir(stage, 0o700)
    owner = {
        "schema": OWNER_SCHEMA,
        "candidate_id": owner_id,
        "live": os.path.realpath(root),
        "stage": os.path.realpath(stage),
    }
    owner_marker = os.path.join(stage, OWNER_FILE)
    _write_owner(owner_marker, owner)
    candidate = os.path.join(stage, "candidate")
    frozen = normalized_write_set(plan)
    source_identity = tree_identity(root)
    git_identity = path_identity(os.path.join(root, ".git"))
    try:
        boundary("candidate-copy", "before", root)
        shutil.copytree(root, candidate, symlinks=True, ignore=_copy_ignore)
        for action in ("replace", "add"):
            for rel in frozen[action]:
                src = _safe_source(release, rel)
                dst = _safe_destination(candidate, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
        boundary("candidate-copy", "after", root)
        boundary("candidate-delete", "before", root)
        for rel in frozen["remove"]:
            dst = _safe_destination(candidate, rel)
            if os.path.lexists(dst):
                if os.path.isdir(dst) and not os.path.islink(dst):
                    raise CandidateError(f"planned file removal resolved to directory: {rel}")
                os.remove(dst)
        boundary("candidate-delete", "after", root)
        boundary("baseline-replacement", "before", root)
        rel_baseline = os.path.join(release, "System", ".baseline-manifest.json")
        if os.path.isfile(rel_baseline) and not os.path.islink(rel_baseline):
            shutil.copyfile(rel_baseline,
                            _safe_destination(candidate, "System/.baseline-manifest.json"))
        boundary("baseline-replacement", "after", root)
        if tree_identity(root) != source_identity:
            raise CandidateError("live vault changed while candidate was being captured")
        if path_identity(os.path.join(candidate, ".git")) != git_identity:
            raise CandidateError("candidate did not preserve the exact .git state")
        if validator is not None:
            result = validator(candidate)
            if result is False:
                raise CandidateError("candidate validation failed")
        evidence.update({
            "stage": stage,
            "candidate": candidate,
            "validated": validator is not None,
            "source_identity": source_identity,
            "git_identity": git_identity,
            "candidate_id": owner_id,
            "owner_marker": owner_marker,
        })
        return evidence
    except Exception:
        if os.path.isdir(stage):
            shutil.rmtree(stage)
        raise


def authorize_migration(candidate_info, *, root, migration_name,
                        source_identity, source_distribution, manifest_hash,
                        effects, outer_checkpoint,
                        system_source_version=None):
    """Bind one migration invocation to a proven staged upgrade candidate."""
    required = {
        "stage", "candidate", "candidate_id", "owner_marker",
        "source_identity", "plan_identity",
    }
    if not isinstance(candidate_info, dict) or not required.issubset(candidate_info):
        raise CandidateError("migration authorization requires complete candidate evidence")
    live = os.path.realpath(root)
    stage = os.path.realpath(candidate_info["stage"])
    candidate = os.path.realpath(candidate_info["candidate"])
    if (
        os.path.dirname(stage) != os.path.dirname(live)
        or candidate != os.path.join(stage, "candidate")
        or not os.path.isdir(candidate)
    ):
        raise CandidateError("migration authorization candidate layout is not owned")
    expected_owner = {
        "schema": OWNER_SCHEMA,
        "candidate_id": candidate_info["candidate_id"],
        "live": live,
        "stage": stage,
    }
    marker = os.path.join(stage, OWNER_FILE)
    if os.path.realpath(candidate_info["owner_marker"]) != marker:
        raise CandidateError("migration authorization owner marker path is inconsistent")
    _read_owner(marker, expected_owner)
    if tree_identity(live) != candidate_info["source_identity"]:
        raise CandidateError("live root changed after candidate capture")
    authorization = {
        "schema": MIGRATION_AUTH_SCHEMA,
        "candidate": candidate,
        "live": live,
        "stage": stage,
        "candidate_id": candidate_info["candidate_id"],
        "owner_marker": marker,
        "plan_identity": candidate_info["plan_identity"],
        "live_tree_identity": candidate_info["source_identity"],
        "migration_name": migration_name,
        "source_identity": source_identity,
        "source_distribution": source_distribution,
        "manifest_hash": manifest_hash,
        "effects": effects,
        "outer_checkpoint": outer_checkpoint,
        "system_source_version": system_source_version,
    }
    authorization["seal"] = hmac.new(
        _MIGRATION_AUTH_SECRET,
        json.dumps(authorization, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return authorization


def verify_migration_authorization(authorization, *, candidate, migration_name,
                                   source_identity, source_distribution,
                                   manifest_hash, effects):
    """Revalidate candidate ownership and invocation binding at use time."""
    if not isinstance(authorization, dict):
        raise CandidateError("migration authorization is missing")
    supplied = dict(authorization)
    seal = supplied.pop("seal", None)
    if (
        supplied.get("schema") != MIGRATION_AUTH_SCHEMA
        or not isinstance(seal, str)
        or not hmac.compare_digest(
            seal,
            hmac.new(
                _MIGRATION_AUTH_SECRET,
                json.dumps(supplied, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest(),
        )
        or supplied.get("candidate") != os.path.realpath(candidate)
        or supplied.get("migration_name") != migration_name
        or supplied.get("source_identity") != source_identity
        or supplied.get("source_distribution") != source_distribution
        or supplied.get("manifest_hash") != manifest_hash
        or supplied.get("effects") != effects
    ):
        raise CandidateError("migration authorization binding is invalid")
    expected_owner = {
        "schema": OWNER_SCHEMA,
        "candidate_id": supplied.get("candidate_id"),
        "live": supplied.get("live"),
        "stage": supplied.get("stage"),
    }
    if supplied.get("candidate") != os.path.join(supplied.get("stage", ""), "candidate"):
        raise CandidateError("migration authorization candidate layout is invalid")
    _read_owner(supplied.get("owner_marker", ""), expected_owner)
    if tree_identity(supplied["live"]) != supplied.get("live_tree_identity"):
        raise CandidateError("migration authorization live identity changed")
    return supplied


def retain_as_sibling(candidate_info, *, root):
    """Atomically retain a validated candidate as a collision-free direct sibling."""
    stage = os.path.abspath(candidate_info["stage"])
    candidate = os.path.abspath(candidate_info["candidate"])
    parent = os.path.dirname(os.path.abspath(root))
    if os.path.dirname(stage) != parent or os.path.dirname(candidate) != stage:
        raise CandidateError("candidate staging layout is not owned by this upgrade")
    owner_id = candidate_info["candidate_id"]
    expected = {
        "schema": OWNER_SCHEMA,
        "candidate_id": owner_id,
        "live": os.path.realpath(root),
        "stage": os.path.realpath(stage),
    }
    _read_owner(os.path.join(stage, OWNER_FILE), expected)
    sibling = os.path.join(
        parent, f".{os.path.basename(os.path.abspath(root))}.candidate-{owner_id}")
    if os.path.lexists(sibling):
        raise CandidateError(f"candidate sibling collision: {sibling}")
    sibling_marker = sibling + ".owner.json"
    sibling_owner = {
        "schema": OWNER_SCHEMA,
        "candidate_id": owner_id,
        "live": os.path.realpath(root),
        "candidate": os.path.realpath(sibling),
    }
    _write_owner(sibling_marker, sibling_owner)
    before = tree_identity(candidate)
    os.rename(candidate, sibling)
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.remove(os.path.join(stage, OWNER_FILE))
    os.rmdir(stage)
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    after = tree_identity(sibling)
    if before != after:
        raise CandidateError("candidate identity changed during sibling retention")
    candidate_info.update({
        "stage": None, "candidate": sibling, "candidate_identity": after,
        "owner_marker": sibling_marker})
    return candidate_info


def delete_candidate(candidate_info, *, root, boundary: Callable | None = None):
    """Delete only the exact private staging/sibling candidate returned above."""
    del boundary
    candidate = os.path.abspath(candidate_info["candidate"])
    parent = os.path.dirname(os.path.abspath(root))
    if candidate_info.get("stage") is None:
        if os.path.dirname(candidate) != parent or not os.path.basename(candidate).startswith(
                f".{os.path.basename(os.path.abspath(root))}.candidate-"):
            raise CandidateError(f"refusing unsafe sibling candidate cleanup: {candidate}")
        expected = {
            "schema": OWNER_SCHEMA,
            "candidate_id": candidate_info["candidate_id"],
            "live": os.path.realpath(root),
            "candidate": os.path.realpath(candidate),
        }
        marker = candidate_info["owner_marker"]
        _read_owner(marker, expected)
        if os.path.isdir(candidate):
            shutil.rmtree(candidate)
        os.remove(marker)
        return
    stage = os.path.abspath(candidate_info["stage"])
    if os.path.dirname(stage) != parent or os.path.dirname(candidate) != stage:
        raise CandidateError(f"refusing unsafe candidate cleanup target: {stage}")
    if not os.path.basename(stage).startswith(
            f".{os.path.basename(os.path.abspath(root))}.aios-upgrade-"):
        raise CandidateError(f"refusing unowned candidate cleanup target: {stage}")
    expected = {
        "schema": OWNER_SCHEMA,
        "candidate_id": candidate_info["candidate_id"],
        "live": os.path.realpath(root),
        "stage": os.path.realpath(stage),
    }
    _read_owner(candidate_info["owner_marker"], expected)
    if os.path.isdir(stage):
        shutil.rmtree(stage)


def reap_abandoned(root, referenced=()):
    """Remove authenticated abandoned artifacts; preserve every lookalike."""
    live = os.path.realpath(os.path.abspath(root))
    parent = os.path.dirname(live)
    name = os.path.basename(live)
    referenced = {os.path.realpath(path) for path in referenced}
    removed, refused = [], []
    for entry in sorted(os.listdir(parent)):
        path = os.path.join(parent, entry)
        if entry.startswith(f".{name}.aios-upgrade-"):
            marker = os.path.join(path, OWNER_FILE)
            try:
                owner_id = entry.rsplit("-", 5)[-5:]
                owner_id = "-".join(owner_id)
                if str(uuid.UUID(owner_id)) != owner_id:
                    raise CandidateError("stage id is not canonical UUID")
                expected = {
                    "schema": OWNER_SCHEMA,
                    "candidate_id": owner_id,
                    "live": live,
                    "stage": os.path.realpath(path),
                }
                _read_owner(marker, expected)
                if os.path.islink(path) or not os.path.isdir(path):
                    raise CandidateError("owned stage is not a real directory")
                shutil.rmtree(path)
                removed.append(path)
            except Exception:
                refused.append(path)
        elif entry.startswith(f".{name}.candidate-") and not entry.endswith(
                ".owner.json"):
            marker = path + ".owner.json"
            try:
                owner_id = entry[len(f".{name}.candidate-"):]
                if str(uuid.UUID(owner_id)) != owner_id:
                    raise CandidateError("candidate id is not canonical UUID")
                expected = {
                    "schema": OWNER_SCHEMA,
                    "candidate_id": owner_id,
                    "live": live,
                    "candidate": os.path.realpath(path),
                }
                _read_owner(marker, expected)
                if os.path.realpath(path) in referenced:
                    continue
                if os.path.islink(path) or not os.path.isdir(path):
                    raise CandidateError("owned candidate is not a real directory")
                shutil.rmtree(path)
                os.remove(marker)
                removed.append(path)
            except Exception:
                refused.append(path)
    return {"removed": removed, "refused": refused}


def remove_retained_marker(root, candidate):
    """Remove ownership evidence only after transaction cleanup removed its tree."""
    live = os.path.realpath(os.path.abspath(root))
    candidate = os.path.abspath(candidate)
    prefix = f".{os.path.basename(live)}.candidate-"
    name = os.path.basename(candidate)
    if os.path.dirname(candidate) != os.path.dirname(live) or not name.startswith(prefix):
        raise CandidateError("retained candidate marker target is outside owned scope")
    owner_id = name[len(prefix):]
    if str(uuid.UUID(owner_id)) != owner_id:
        raise CandidateError("retained candidate marker id is invalid")
    if os.path.lexists(candidate):
        raise CandidateError("retained candidate still exists; marker must remain")
    marker = candidate + ".owner.json"
    expected = {
        "schema": OWNER_SCHEMA,
        "candidate_id": owner_id,
        "live": live,
        "candidate": os.path.realpath(candidate),
    }
    _read_owner(marker, expected)
    os.remove(marker)
