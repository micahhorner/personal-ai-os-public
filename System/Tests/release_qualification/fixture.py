"""Build deterministic personal-instance fixtures from real Git history.

This module is test-only release-qualification machinery.  It deliberately
uses ``git archive`` rather than checkout/worktree operations: constructing a
fixture must never move a repository ref, alter its index, or attach another
worktree.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
from typing import Any, Iterable


_ROLE_RE = re.compile(
    r"^(\s*instance_role:\s*)generic-master(?:\s*(?:#.*)?)$",
    re.MULTILINE,
)


class FixtureError(RuntimeError):
    """Base class for a historical-instance construction failure."""


class UnsafeDestinationError(FixtureError):
    """The caller-supplied destination is not an empty, real directory."""


class UnsafeArchiveError(FixtureError):
    """The selected Git tree cannot be extracted without escaping containment."""


@dataclass(frozen=True)
class FileInventory:
    """One regular file in a materialized tree."""

    path: str
    size: int
    mode: int
    sha256: str


@dataclass(frozen=True)
class HistoricalInstanceFixture:
    """Machine-readable evidence returned for one constructed instance."""

    requested_ref: str
    resolved_commit: str
    destination: str
    base_tree_sha256: str
    final_tree_sha256: str
    base_files: tuple[FileInventory, ...]
    final_files: tuple[FileInventory, ...]
    seeded_paths: tuple[str, ...]
    modified_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)


def build_historical_instance(
    repository: os.PathLike[str] | str,
    git_ref: str,
    destination: os.PathLike[str] | str,
) -> HistoricalInstanceFixture:
    """Materialize ``git_ref`` and seed a deterministic personal instance.

    ``destination`` must already exist as an empty, non-symlink directory.  The
    repository is only queried with read-only Git commands.  On any failure,
    everything this call created is removed and the destination is empty again.
    """

    repo = Path(repository).resolve(strict=True)
    dest = _require_empty_destination(destination)
    if dest == repo or repo in dest.parents:
        raise UnsafeDestinationError(
            "destination must be outside the source repository worktree"
        )
    commit = _resolve_commit(repo, git_ref)

    try:
        archive = _git_archive(repo, commit)
        _extract_archive(archive, dest)
        base_files = _inventory(dest)

        modified = [
            _personalize_manifest(dest),
            _seed_system_customization(dest),
        ]
        seeded = list(_seed_representative_state(dest))
        journal_path = _seed_journal(dest)
        if journal_path in {entry.path for entry in base_files}:
            modified.append(journal_path)
        else:
            seeded.append(journal_path)

        final_files = _inventory(dest)
        return HistoricalInstanceFixture(
            requested_ref=git_ref,
            resolved_commit=commit,
            destination=str(dest),
            base_tree_sha256=_tree_hash(base_files),
            final_tree_sha256=_tree_hash(final_files),
            base_files=base_files,
            final_files=final_files,
            seeded_paths=tuple(sorted(seeded)),
            modified_paths=tuple(sorted(modified)),
        )
    except Exception:
        _clear_destination(dest)
        raise


def _require_empty_destination(destination: os.PathLike[str] | str) -> Path:
    dest = Path(destination)
    if dest.is_symlink():
        raise UnsafeDestinationError("destination must not be a symlink")
    try:
        resolved = dest.resolve(strict=True)
    except FileNotFoundError as exc:
        raise UnsafeDestinationError(
            "destination must already exist as an empty directory"
        ) from exc
    if not resolved.is_dir():
        raise UnsafeDestinationError("destination must be a directory")
    if any(resolved.iterdir()):
        raise UnsafeDestinationError("refusing nonempty destination")
    return resolved


def _run_git(repo: Path, args: list[str], *, text: bool) -> subprocess.CompletedProcess:
    command = ["git", "-C", str(repo), *args]
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=text,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr if text else exc.stderr.decode("utf-8", "replace")
        raise FixtureError(f"Git command failed: {detail.strip()}") from exc


def _resolve_commit(repo: Path, git_ref: str) -> str:
    if not isinstance(git_ref, str) or not git_ref.strip():
        raise FixtureError("git_ref must be a nonempty string")
    result = _run_git(
        repo,
        ["rev-parse", "--verify", "--end-of-options", f"{git_ref}^{{commit}}"],
        text=True,
    )
    commit = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
        raise FixtureError(f"Git returned an invalid commit id: {commit!r}")
    return commit.lower()


def _git_archive(repo: Path, commit: str) -> bytes:
    result = _run_git(repo, ["archive", "--format=tar", commit], text=False)
    return result.stdout


def _validated_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    seen: set[str] = set()
    seen_casefold: dict[str, str] = {}
    for member in members:
        raw_name = member.name
        posix = PurePosixPath(raw_name)
        parts = posix.parts
        if (
            not raw_name
            or posix.is_absolute()
            or "\\" in raw_name
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise UnsafeArchiveError(f"unsafe archive path: {raw_name!r}")
        normalized = posix.as_posix()
        if normalized in seen:
            raise UnsafeArchiveError(f"duplicate archive path: {normalized}")
        folded = normalized.casefold()
        if folded in seen_casefold and seen_casefold[folded] != normalized:
            raise UnsafeArchiveError(
                "case-colliding archive paths: "
                f"{seen_casefold[folded]!r} and {normalized!r}"
            )
        seen.add(normalized)
        seen_casefold[folded] = normalized
        if not (member.isdir() or member.isreg()):
            raise UnsafeArchiveError(
                f"archive links and special files are not permitted: {normalized}"
            )
    return members


def _extract_archive(archive_bytes: bytes, destination: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        members = _validated_members(archive)
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                target.chmod(member.mode & 0o777)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise UnsafeArchiveError(f"cannot read archive file: {member.name}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(member.mode & 0o777)


def _personalize_manifest(destination: Path) -> str:
    path = destination / "SYSTEM-MANIFEST.yaml"
    if not path.is_file():
        raise FixtureError("selected release has no SYSTEM-MANIFEST.yaml")
    text = path.read_text(encoding="utf-8")
    personalized, replacements = _ROLE_RE.subn(
        r"\1personal-instance",
        text,
        count=1,
    )
    if replacements != 1:
        raise FixtureError(
            "selected release is not a generic-master with one instance_role"
        )
    path.write_text(personalized, encoding="utf-8")
    return "SYSTEM-MANIFEST.yaml"


def _write_new(destination: Path, relative: str, content: str) -> str:
    path = destination.joinpath(*PurePosixPath(relative).parts)
    if path.exists() or path.is_symlink():
        raise FixtureError(f"fixture seed path already exists: {relative}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o644)
    return relative


def _seed_system_customization(destination: Path) -> str:
    relative = "System/Runtime/Task Router.yaml"
    path = destination.joinpath(*PurePosixPath(relative).parts)
    if not path.is_file() or path.is_symlink():
        raise FixtureError(
            "selected release has no regular System/Runtime/Task Router.yaml"
        )
    existing = path.read_text(encoding="utf-8")
    separator = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(
        existing
        + separator
        + "# release-qualification instance customization: preserve this line\n",
        encoding="utf-8",
    )
    return relative


def _seed_representative_state(destination: Path) -> Iterable[str]:
    note = """---
id: note-release-qualification-knowledge
type: note
status: active
verification: verified
created: 2026-07-28
updated: 2026-07-28
summary: Deterministic user knowledge for historical release qualification.
---

# Release qualification knowledge

This user-owned sentence must survive every upgrade byte-for-byte.
"""
    inbox = """---
id: note-release-qualification-inbox
type: note
status: draft
created: 2026-07-28
updated: 2026-07-28
summary: Deterministic unprocessed capture for historical qualification.
---

# Unprocessed fixture capture

This capture intentionally remains in staging.
"""
    project = """---
id: project-release-qualification
type: project
status: active
stage: active
created: 2026-07-28
updated: 2026-07-28
summary: Deterministic project state with spaces and Unicode in its path.
---

# Release Qualification Ω

## Next actions

- Preserve every representative user surface.
"""
    pack_note = """---
id: note-release-qualification-pack-state
type: note
status: active
verification: verified
created: 2026-07-28
updated: 2026-07-28
summary: Deterministic content owned by an installed fixture pack.
---

# Pack-owned fixture state

This installed-pack content must survive qualification unchanged.
"""
    seeds = (
        (
            "20 Knowledge/Release Qualification Knowledge.md",
            note,
        ),
        (
            "00 Inbox/Release Qualification Capture.md",
            inbox,
        ),
        (
            "10 Projects/Release Qualification Ω/Project.md",
            project,
        ),
        (
            "80 User/release-qualification.yaml",
            "fixture: historical-release-qualification\n"
            "preferred_term: \"careful Ω\"\n"
            "enabled: true\n",
        ),
        (
            ".obsidian/release-qualification.json",
            '{\n  "fixture": true,\n  "workspace": "Release Qualification Ω"\n}\n',
        ),
        (
            "Packs/release-qualification-pack/pack.yaml",
            "id: pack-release-qualification\n"
            'name: "Release Qualification Fixture Pack"\n'
            "version: 1.0.0\n"
            "kind: role-pack\n"
            'summary: "Deterministic installed-pack state for lifecycle tests."\n'
            "license: MIT\n"
            'source: "https://example.invalid/release-qualification"\n'
            "depends_on:\n"
            "  core_primitives: []\n"
            '  min_system_version: "1.0.0"\n'
            "  runtime: any\n",
        ),
        (
            "Packs/release-qualification-pack/content/Pack State.md",
            pack_note,
        ),
        (
            "RELEASE-QUALIFICATION-ROOT.txt",
            "historical fixture root state\nunicode: Ω\n",
        ),
    )
    for relative, content in seeds:
        yield _write_new(destination, relative, content)


def _seed_journal(destination: Path) -> str:
    relative = "System/Journal/change-journal.md"
    path = destination.joinpath(*PurePosixPath(relative).parts)
    marker = (
        "- 2026-07-28 · release-qualification-fixture · seed · "
        "representative historical instance state · deterministic fixture\n"
    )
    if path.exists():
        if not path.is_file() or path.is_symlink():
            raise FixtureError(f"journal path is not a regular file: {relative}")
        existing = path.read_text(encoding="utf-8")
        separator = "" if not existing or existing.endswith("\n") else "\n"
        path.write_text(existing + separator + marker, encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Change journal\n\n"
            "Append-only historical fixture state.\n\n"
            + marker,
            encoding="utf-8",
        )
        path.chmod(0o644)
    return relative


def _inventory(root: Path) -> tuple[FileInventory, ...]:
    entries: list[FileInventory] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                raise UnsafeArchiveError(
                    f"inventory encountered a non-regular file: {path.relative_to(root)}"
                )
            data = path.read_bytes()
            entries.append(
                FileInventory(
                    path=path.relative_to(root).as_posix(),
                    size=len(data),
                    mode=stat.S_IMODE(path.stat().st_mode),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )
    return tuple(sorted(entries, key=lambda item: item.path))


def _tree_hash(entries: Iterable[FileInventory]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f"{entry.mode:o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(str(entry.size).encode("ascii"))
        digest.update(b"\0")
        digest.update(entry.sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _clear_destination(destination: Path) -> None:
    for child in destination.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
