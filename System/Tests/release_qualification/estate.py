"""Read-only inventory of historical Personal AI OS release states.

Version strings are not release identities: the historical estate contains
different trees claiming the same version.  This module resolves every input
ref to an immutable commit, reads the manifest and baseline directly from Git
objects, and identifies a release by its version plus normalized baseline
fingerprint.

Nothing here creates a fixture or runs an upgrade.  It is the deterministic
estate-reader used by the later qualification harness.
"""

from dataclasses import dataclass, replace
import hashlib
import json
import os
import re
import subprocess
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


MANIFEST_PATH = "SYSTEM-MANIFEST.yaml"
BASELINE_PATH = "System/.baseline-manifest.json"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class EstateError(RuntimeError):
    """Release evidence is absent, malformed, or internally inconsistent."""


@dataclass(frozen=True)
class ReleaseRecord:
    """One immutable Git state and the release evidence stored in it."""

    requested_ref: str
    commit: str
    tree: str
    system_version: str
    baseline_version: str
    manifest_blob: str
    baseline_blob: str
    baseline_fingerprint: str
    release_identity: str
    baseline_file_count: int
    derived_file_count: int
    baseline_valid: Optional[bool]
    baseline_mismatches: Tuple[str, ...] = ()
    same_version_rivals: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        """Return a stable, JSON-serializable qualification record."""
        return {
            "requested_ref": self.requested_ref,
            "commit": self.commit,
            "tree": self.tree,
            "system_version": self.system_version,
            "baseline_version": self.baseline_version,
            "manifest_blob": self.manifest_blob,
            "baseline_blob": self.baseline_blob,
            "baseline_fingerprint": self.baseline_fingerprint,
            "release_identity": self.release_identity,
            "baseline_file_count": self.baseline_file_count,
            "derived_file_count": self.derived_file_count,
            "baseline_valid": self.baseline_valid,
            "baseline_mismatches": list(self.baseline_mismatches),
            "same_version_rivals": list(self.same_version_rivals),
        }


@dataclass(frozen=True)
class EstateInventory:
    """Deterministic collection of release records plus ambiguity evidence."""

    records: Tuple[ReleaseRecord, ...]
    rival_groups: Tuple[Tuple[str, Tuple[str, ...]], ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": 1,
            "records": [record.to_dict() for record in self.records],
            "rival_groups": [
                {"system_version": version, "release_identities": list(identities)}
                for version, identities in self.rival_groups
            ],
        }

    def to_json(self) -> str:
        """Emit reproducible machine evidence (no timestamps or host paths)."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def _git(repo: str, args: Sequence[str], text: bool = False):
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["LC_ALL"] = "C"
    command = ["git", "-C", os.path.abspath(repo)] + list(args)
    proc = subprocess.run(command, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env)
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise EstateError("git command failed (%s): %s" %
                          (" ".join(args), detail or "unknown error"))
    if text:
        return proc.stdout.decode("utf-8", "strict")
    return proc.stdout


def _resolve_commit(repo: str, ref: str) -> str:
    if not isinstance(ref, str) or not ref.strip() or "\x00" in ref:
        raise EstateError("release ref must be a non-empty Git revision")
    resolved = _git(
        repo, ["rev-parse", "--verify", "--end-of-options", ref + "^{commit}"],
        text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise EstateError("ref did not resolve to a full commit id: %s" % ref)
    return resolved


def _is_ancestor(repo: str, ancestor: str, descendant: str) -> bool:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["LC_ALL"] = "C"
    proc = subprocess.run(
        ["git", "-C", os.path.abspath(repo), "merge-base", "--is-ancestor",
         ancestor, descendant],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    if proc.returncode not in (0, 1):
        raise EstateError("could not test Git ancestry for %s" % ancestor)
    return proc.returncode == 0


def _blob(repo: str, commit: str, path: str) -> Tuple[str, bytes]:
    blob_id = _git(repo, ["rev-parse", "--verify",
                          "%s:%s" % (commit, path)], text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", blob_id):
        raise EstateError("%s at %s is not a blob" % (path, commit))
    body = _git(repo, ["cat-file", "blob", blob_id])
    return blob_id, body


def _manifest_version(body: bytes, ref: str) -> str:
    try:
        document = yaml.safe_load(body.decode("utf-8", "strict"))
        version = document["system"]["system_version"]
    except (UnicodeError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise EstateError("invalid %s at %s: %s" %
                          (MANIFEST_PATH, ref, exc)) from exc
    version = str(version)
    if not SEMVER_RE.fullmatch(version):
        raise EstateError("invalid system_version at %s: %r" % (ref, version))
    return version


def _baseline(body: bytes, ref: str) -> Dict[str, object]:
    try:
        baseline = json.loads(body.decode("utf-8", "strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EstateError("invalid %s at %s: %s" %
                          (BASELINE_PATH, ref, exc)) from exc
    if not isinstance(baseline, dict):
        raise EstateError("baseline at %s must be a JSON object" % ref)
    for key in ("system_version", "files"):
        if key not in baseline:
            raise EstateError("baseline at %s is missing %s" % (ref, key))
    if not isinstance(baseline["files"], dict):
        raise EstateError("baseline files at %s must be an object" % ref)
    if not isinstance(baseline.get("derived", {}), dict):
        raise EstateError("baseline derived at %s must be an object" % ref)
    return baseline


def _fingerprint(baseline: Dict[str, object]) -> str:
    identity_surface = {
        "system_version": str(baseline["system_version"]),
        "files": baseline["files"],
        "derived": baseline.get("derived", {}),
    }
    encoded = json.dumps(identity_surface, ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _verify_baseline(repo: str, commit: str,
                     files: Dict[str, object]) -> Tuple[str, ...]:
    mismatches: List[str] = []
    for path in sorted(files):
        expected = files[path]
        if not isinstance(path, str) or not isinstance(expected, str):
            mismatches.append("%r: baseline path/hash must be strings" % path)
            continue
        try:
            _, body = _blob(repo, commit, path)
        except EstateError:
            mismatches.append("%s: missing" % path)
            continue
        actual = hashlib.sha256(body).hexdigest()
        if actual != expected:
            mismatches.append("%s: expected %s, got %s" %
                              (path, expected, actual))
    return tuple(mismatches)


def load_release(repo: str, ref: str,
                 verify_baseline: bool = True) -> ReleaseRecord:
    """Load one exact ref without consulting or changing the working tree."""
    commit = _resolve_commit(repo, ref)
    tree = _git(repo, ["rev-parse", "%s^{tree}" % commit], text=True).strip()
    manifest_blob, manifest_body = _blob(repo, commit, MANIFEST_PATH)
    baseline_blob, baseline_body = _blob(repo, commit, BASELINE_PATH)
    version = _manifest_version(manifest_body, ref)
    baseline = _baseline(baseline_body, ref)
    baseline_version = str(baseline["system_version"])
    if version != baseline_version:
        raise EstateError(
            "manifest/baseline version mismatch at %s: %s != %s" %
            (ref, version, baseline_version))
    fingerprint = _fingerprint(baseline)
    # The baseline identifies the declared product surface; the tree catches a
    # divergent state that failed to declare a changed/added product file.
    identity = hashlib.sha256(
        (version + "\0" + fingerprint + "\0" + tree).encode("ascii")
    ).hexdigest()
    files = baseline["files"]
    mismatches = (_verify_baseline(repo, commit, files)
                  if verify_baseline else ())
    return ReleaseRecord(
        requested_ref=ref,
        commit=commit,
        tree=tree,
        system_version=version,
        baseline_version=baseline_version,
        manifest_blob=manifest_blob,
        baseline_blob=baseline_blob,
        baseline_fingerprint=fingerprint,
        release_identity=identity,
        baseline_file_count=len(files),
        derived_file_count=len(baseline.get("derived", {})),
        baseline_valid=(not mismatches) if verify_baseline else None,
        baseline_mismatches=mismatches,
    )


def inventory_releases(repo: str, refs: Iterable[str],
                       verify_baseline: bool = True) -> EstateInventory:
    """Load exact refs and annotate every same-version, different-state rival."""
    records = [load_release(repo, ref, verify_baseline=verify_baseline)
               for ref in refs]
    by_version: Dict[str, Dict[str, List[ReleaseRecord]]] = {}
    for record in records:
        by_version.setdefault(record.system_version, {}).setdefault(
            record.release_identity, []).append(record)

    rival_groups: List[Tuple[str, Tuple[str, ...]]] = []
    annotated: List[ReleaseRecord] = []
    for record in records:
        identities = tuple(sorted(by_version[record.system_version]))
        rivals = tuple(identity for identity in identities
                       if identity != record.release_identity)
        annotated.append(replace(record, same_version_rivals=rivals))
    for version in sorted(by_version, key=_version_key):
        identities = tuple(sorted(by_version[version]))
        if len(identities) > 1:
            rival_groups.append((version, identities))

    annotated.sort(key=lambda item: (
        _version_key(item.system_version), item.release_identity,
        item.commit, item.requested_ref))
    return EstateInventory(tuple(annotated), tuple(rival_groups))


def discover_release_refs(repo: str,
                          namespaces: Sequence[str] = (
                              "refs/tags", "refs/heads", "refs/remotes",
                          )) -> Tuple[str, ...]:
    """Return exact refs whose commits carry both release-evidence files."""
    output = _git(repo, ["for-each-ref", "--format=%(refname)",
                         *namespaces], text=True)
    candidates: List[str] = []
    for ref in sorted(set(line for line in output.splitlines() if line)):
        try:
            commit = _resolve_commit(repo, ref)
            _blob(repo, commit, MANIFEST_PATH)
            _blob(repo, commit, BASELINE_PATH)
        except EstateError:
            continue
        candidates.append(ref)
    return tuple(candidates)


def discover_mainline_states(
        repo: str, main_ref: str, minimum_version: Optional[str] = None,
        maximum_version: Optional[str] = None) -> Tuple[str, ...]:
    """Discover one exact reachable commit for each release version.

    A matching ``v<version>`` tag is authoritative when present.  The pinned tip
    is authoritative for the current untagged version.  For a commit-only
    historical version, the most integrated reachable candidate (greatest Git
    generation) wins; callers still inventory all known anomaly refs separately
    so this discovery never substitutes for rival detection.

    Optional inclusive bounds keep qualification scoped to a declared estate.
    Git objects are read only; no checkout is performed.
    """
    tip = _resolve_commit(repo, main_ref)
    tip_record = load_release(repo, tip, verify_baseline=False)
    commits = [tip] + _git(
        repo, ["rev-list", tip, "--", MANIFEST_PATH],
        text=True).splitlines()
    by_version: Dict[str, List[ReleaseRecord]] = {}
    seen_commits = set()
    for commit in commits:
        if commit in seen_commits:
            continue
        seen_commits.add(commit)
        try:
            record = load_release(repo, commit, verify_baseline=False)
        except EstateError:
            continue
        if minimum_version and _version_key(
                record.system_version) < _version_key(minimum_version):
            continue
        if maximum_version and _version_key(
                record.system_version) > _version_key(maximum_version):
            continue
        by_version.setdefault(record.system_version, []).append(record)

    tagged: Dict[str, ReleaseRecord] = {}
    tag_output = _git(
        repo, ["for-each-ref", "--format=%(refname)", "refs/tags"],
        text=True)
    for tag in sorted(tag_output.splitlines()):
        if not tag.rsplit("/", 1)[-1].startswith("v"):
            continue
        try:
            record = load_release(repo, tag, verify_baseline=False)
        except EstateError:
            continue
        if tag.rsplit("/", 1)[-1] != "v" + record.system_version:
            continue
        if not _is_ancestor(repo, record.commit, tip):
            continue
        if minimum_version and _version_key(
                record.system_version) < _version_key(minimum_version):
            continue
        if maximum_version and _version_key(
                record.system_version) > _version_key(maximum_version):
            continue
        tagged.setdefault(record.system_version, record)
        by_version.setdefault(record.system_version, []).append(record)

    states: List[ReleaseRecord] = []
    for version, candidates in by_version.items():
        if version == tip_record.system_version:
            states.append(tip_record)
        elif version in tagged:
            states.append(tagged[version])
        else:
            states.append(max(
                candidates,
                key=lambda item: (
                    int(_git(repo, ["rev-list", "--count", item.commit],
                             text=True).strip()),
                    item.commit,
                ),
            ))
    states.sort(key=lambda item: (
        _version_key(item.system_version), item.commit))
    return tuple(state.commit for state in states)


def _version_key(version: str) -> Tuple[object, ...]:
    core = version.split("-", 1)[0].split("+", 1)[0]
    parts = tuple(int(part) for part in core.split("."))
    return parts + (version,)
