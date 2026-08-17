"""Strict, read-only release-version and changelog record checks.

``SYSTEM-MANIFEST.yaml`` is the sole release-version authority.
``pyproject.toml`` and ``System/.baseline-manifest.json`` are synchronized
mirrors.  The changelog is history, not another authority.  Historical mistakes
are never edited away; an optional correction registry can classify an exact
section while leaving every original byte in place.

Correction registry format (``System/Release/version-record-corrections.json``):

.. code-block:: json

  {
    "schema_version": 1,
    "records": [
      {
        "id": "correction-legacy-rolling-1-6-a",
        "disposition": "amendment",
        "target_section_sha256": "<sha256 of heading and body through next ##>",
        "reason": "Duplicate rolling release label; retained as history."
      },
      {
        "id": "non-main-release-1-61-0",
        "disposition": "non-main-release",
        "version": "1.61.0",
        "reason": "Released on a historical branch, but not on supported main."
      }
    ]
  }

The section digest distinguishes repeated headings by their bodies.  A target
must resolve to exactly one section; zero or multiple matches fail closed.
``misplaced-release`` retains a genuine release and exempts only its physical
ordering position.  ``amendment`` retains a historical section without treating
it as a separate release.  ``withdrawn`` records an explicit non-release.
``non-main-release`` records a version that genuinely existed on another
historical line without asserting that it shipped on, or remains supported by,
main.
"""

from dataclasses import dataclass
import hashlib
import json
import os
import re
import stat
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


MANIFEST = "SYSTEM-MANIFEST.yaml"
PACKAGE = "pyproject.toml"
BASELINE = os.path.join("System", ".baseline-manifest.json")
CHANGELOG = "CHANGELOG.md"
CORRECTIONS = os.path.join(
    "System", "Release", "version-record-corrections.json")
BASELINE_EXCLUDED_PREFIXES = (
    "System/Generated/", "System/Logs/", "System/Journal/",
    "System/Tests/results/",
)
BASELINE_SKIP_NAMES = {".DS_Store", "__pycache__"}
BASELINE_ROOT_FILES = (
    "CLAUDE.md", "pyproject.toml", "README.md", "START-HERE.md",
    "CONTRIBUTING.md", "SECURITY.md",
)

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
HEADING_RE = re.compile(r"^##\s+\[([^\]]+)\](?:\s+.*)?$")
# Structural detector deliberately accepts more than HEADING_RE.  Any
# heading-shaped line containing a numeric version must either satisfy the exact
# release-heading grammar or produce a finding; malformed headings may never
# become invisible merely because the strict parser cannot see them.
VERSION_HEADING_CANDIDATE_RE = re.compile(
    r"^\s*#{2,}\s+\[\s*\d+\.\d+(?:\.\d+)?[^\]]*\]")
VERSION_PREFIX_RE = re.compile(
    r"^((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?)")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
PROJECT_RE = re.compile(r"^\[project\]\s*$", re.MULTILINE)
PACKAGE_VERSION_RE = re.compile(
    r'^version\s*=\s*"([^"]+)"\s*(?:#.*)?$', re.MULTILINE)
INFORMAL_STATUS_RE = re.compile(
    r"(?i)(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)"
    r"[^.\n]{0,100}\b(reserved|withdrawn)\b")


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    path: str
    line: Optional[int] = None


@dataclass(frozen=True)
class ChangelogRecord:
    record_id: str
    version: str
    disposition: str
    line: int
    heading: str
    section_sha256: str


@dataclass(frozen=True)
class VersionAudit:
    versions: Dict[str, Optional[str]]
    baseline_identity: Optional[str]
    records: Tuple[ChangelogRecord, ...]
    findings: Tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings


def _finding(code: str, message: str, path: str,
             line: Optional[int] = None) -> Finding:
    return Finding(code, message, path.replace(os.sep, "/"), line)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _semver(version: object) -> Optional[str]:
    value = str(version).strip() if version is not None else ""
    match = SEMVER_RE.fullmatch(value)
    if not match:
        return None
    prerelease = match.group(4)
    if prerelease and any(
            part.isdigit() and len(part) > 1 and part.startswith("0")
            for part in prerelease.split(".")):
        return None
    return value


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader which refuses duplicate mapping keys."""


def _unique_yaml_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.YAMLError("duplicate YAML key %r" % key)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_yaml_mapping)


def _semver_key(version: str) -> Tuple[object, ...]:
    """Comparable SemVer key; build metadata does not affect precedence."""
    match = SEMVER_RE.fullmatch(version)
    if not match:
        raise ValueError("not SemVer: %r" % version)
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    prerelease = match.group(4)
    if prerelease is None:
        prekey: Tuple[object, ...] = ((1, ""),)
    else:
        parts: List[Tuple[int, object]] = []
        for part in prerelease.split("."):
            parts.append((0, int(part)) if part.isdigit() else (1, part))
        prekey = ((0, ""),) + tuple(parts)
    return major, minor, patch, prekey


def _manifest_version(root: str, findings: List[Finding]
                      ) -> Tuple[Optional[str], Optional[str]]:
    path = os.path.join(root, MANIFEST)
    try:
        data = yaml.load(_read(path), Loader=_UniqueKeyLoader)
        raw = data["system"]["system_version"]
        role = data["system"].get("instance_role")
    except (OSError, UnicodeError, yaml.YAMLError, KeyError, TypeError) as exc:
        findings.append(_finding(
            "manifest-unreadable", "cannot read system.system_version: %s" % exc,
            MANIFEST))
        return None, None
    value = _semver(raw)
    if value is None:
        findings.append(_finding(
            "manifest-version-invalid",
            "system.system_version is not strict SemVer: %r" % raw, MANIFEST))
    return value, str(role) if role is not None else None


def _package_version(root: str, findings: List[Finding]) -> Optional[str]:
    path = os.path.join(root, PACKAGE)
    try:
        text = _read(path)
    except (OSError, UnicodeError) as exc:
        findings.append(_finding(
            "package-unreadable", "cannot read package version: %s" % exc,
            PACKAGE))
        return None
    projects = list(PROJECT_RE.finditer(text))
    if len(projects) != 1:
        findings.append(_finding(
            "package-project-count",
            "expected exactly one [project] table, found %d" % len(projects),
            PACKAGE))
        return None
    start = projects[0].end()
    next_table = re.search(r"^\[", text[start:], re.MULTILINE)
    block = text[start:start + next_table.start()] if next_table else text[start:]
    matches = PACKAGE_VERSION_RE.findall(block)
    if len(matches) != 1:
        findings.append(_finding(
            "package-version-count",
            "expected exactly one [project] version, found %d" % len(matches),
            PACKAGE))
        return None
    value = _semver(matches[0])
    if value is None:
        findings.append(_finding(
            "package-version-invalid",
            "[project] version is not strict SemVer: %r" % matches[0], PACKAGE))
    return value


def _object_without_duplicate_keys(pairs: Sequence[Tuple[str, object]]):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key %r" % key)
        result[key] = value
    return result


def _valid_baseline_path(path: object) -> bool:
    if not isinstance(path, str) or not path or "\\" in path:
        return False
    if os.path.isabs(path):
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _confined_regular_file(root: str, path: str) -> Tuple[bool, str]:
    """Require a regular file reached without symlinks and confined to root."""
    root_real = os.path.realpath(root)
    path_abs = os.path.abspath(path)
    try:
        if os.path.commonpath((root_real, os.path.realpath(path_abs))) != root_real:
            return False, "resolves outside vault root"
    except ValueError:
        return False, "is outside vault root"
    relative = os.path.relpath(path_abs, os.path.abspath(root))
    cursor = os.path.abspath(root)
    try:
        for part in relative.split(os.sep):
            cursor = os.path.join(cursor, part)
            mode = os.lstat(cursor).st_mode
            if stat.S_ISLNK(mode):
                return False, "uses a symlink"
        if not stat.S_ISREG(os.lstat(path_abs).st_mode):
            return False, "is not a regular file"
    except OSError as exc:
        return False, "is unreadable: %s" % exc
    return True, ""


def _expected_baseline_surface(root: str) -> Tuple[set, List[Tuple[str, str]]]:
    """Return exact product-master surface plus invalid filesystem objects."""
    expected = set()
    invalid: List[Tuple[str, str]] = []
    top = os.path.join(root, "System")
    for dirpath, dirnames, filenames in os.walk(top):
        kept_dirs = []
        for name in dirnames:
            if name in BASELINE_SKIP_NAMES:
                continue
            absolute = os.path.join(dirpath, name)
            if os.path.islink(absolute):
                rel = os.path.relpath(absolute, root).replace(os.sep, "/")
                invalid.append((rel, "directory is a symlink"))
            else:
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in filenames:
            if name in BASELINE_SKIP_NAMES or name.endswith(".pyc"):
                continue
            absolute = os.path.join(dirpath, name)
            rel = os.path.relpath(absolute, root).replace(os.sep, "/")
            if rel == BASELINE.replace(os.sep, "/"):
                continue
            if any(rel.startswith(prefix)
                   for prefix in BASELINE_EXCLUDED_PREFIXES):
                continue
            valid, reason = _confined_regular_file(root, absolute)
            if valid:
                expected.add(rel)
            else:
                invalid.append((rel, reason))
    for rel in BASELINE_ROOT_FILES:
        absolute = os.path.join(root, rel)
        if os.path.lexists(absolute):
            valid, reason = _confined_regular_file(root, absolute)
            if valid:
                expected.add(rel)
            else:
                invalid.append((rel, reason))
    return expected, invalid


def _baseline(root: str, expected_version: Optional[str],
              findings: List[Finding], verify_surface: bool,
              verify_live: bool
              ) -> Tuple[Optional[str], Optional[str]]:
    finding_start = len(findings)
    path = os.path.join(root, BASELINE)
    try:
        data = json.loads(
            _read(path), object_pairs_hook=_object_without_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        findings.append(_finding(
            "baseline-unreadable", "cannot read baseline: %s" % exc, BASELINE))
        return None, None
    if not isinstance(data, dict):
        findings.append(_finding(
            "baseline-not-object", "baseline must be a JSON object", BASELINE))
        return None, None
    raw_version = data.get("system_version")
    version = _semver(raw_version)
    if version is None:
        findings.append(_finding(
            "baseline-version-invalid",
            "system_version is not strict SemVer: %r" % raw_version, BASELINE))
    if expected_version and version and expected_version != version:
        findings.append(_finding(
            "baseline-mirror-mismatch",
            "baseline mirror %s does not match manifest authority %s" %
            (version, expected_version), BASELINE))
    files = data.get("files")
    derived = data.get("derived", {})
    for name, mapping in (("files", files), ("derived", derived)):
        if not isinstance(mapping, dict):
            findings.append(_finding(
                "baseline-%s-invalid" % name,
                "%s must be a JSON object" % name, BASELINE))
            continue
        for rel, digest in sorted(mapping.items(), key=lambda item: str(item[0])):
            if not _valid_baseline_path(rel):
                findings.append(_finding(
                    "baseline-path-invalid",
                    "%s contains unsafe/non-canonical path %r" % (name, rel),
                    BASELINE))
            if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
                findings.append(_finding(
                    "baseline-hash-invalid",
                    "%s entry %r is not a lowercase SHA-256" % (name, rel),
                    BASELINE))
    if not isinstance(files, dict) or not isinstance(derived, dict):
        return version, None
    for rel in sorted(set(derived) - set(files)):
        findings.append(_finding(
            "baseline-derived-orphan",
            "derived entry is absent from files: %s" % rel, BASELINE))
    if verify_surface:
        expected_surface, invalid_objects = _expected_baseline_surface(root)
        for rel, reason in invalid_objects:
            findings.append(_finding(
                "baseline-surface-special",
                "product-master release surface %s: %s" % (rel, reason),
                BASELINE))
        recorded_surface = set(files)
        for rel in sorted(expected_surface - recorded_surface):
            findings.append(_finding(
                "baseline-surface-missing",
                "product-master baseline omits release file: %s" % rel,
                BASELINE))
        for rel in sorted(recorded_surface - expected_surface):
            findings.append(_finding(
                "baseline-surface-extra",
                "product-master baseline records non-release file: %s" % rel,
                BASELINE))
    if verify_live:
        for rel, expected in sorted(files.items()):
            if not _valid_baseline_path(rel) or not isinstance(
                    expected, str) or not HASH_RE.fullmatch(expected):
                continue
            live = os.path.join(root, *rel.split("/"))
            valid, reason = _confined_regular_file(root, live)
            if not valid:
                findings.append(_finding(
                    "baseline-file-invalid",
                    "baseline path %s %s" % (rel, reason), BASELINE))
                continue
            try:
                with open(live, "rb") as stream:
                    actual = hashlib.sha256(stream.read()).hexdigest()
            except (OSError, UnicodeError) as exc:
                findings.append(_finding(
                    "baseline-file-invalid",
                    "baseline path %s is unreadable: %s" % (rel, exc), BASELINE))
                continue
            if actual != expected:
                findings.append(_finding(
                    "baseline-file-mismatch",
                    "%s expected %s but has %s" % (rel, expected, actual),
                    BASELINE))

    # Use the exact production neutralisation implementation.  A second copy of
    # its regex here would be another contract capable of drifting.
    actual_derived = {}
    if verify_live:
        try:
            from cmd.upgrade import _neutralised_sha
        except (ImportError, AttributeError) as exc:
            findings.append(_finding(
                "baseline-derived-contract",
                "cannot load production neutralisation contract: %s" % exc,
                BASELINE))
            _neutralised_sha = None
    else:
        _neutralised_sha = None
    if verify_live and _neutralised_sha is not None:
        for rel in sorted(files):
            if not _valid_baseline_path(rel):
                continue
            live = os.path.join(root, *rel.split("/"))
            valid, _ = _confined_regular_file(root, live)
            if not valid:
                continue
            digest = _neutralised_sha(live)
            if digest is not None:
                actual_derived[rel] = digest
        for rel in sorted(set(actual_derived) - set(derived)):
            findings.append(_finding(
                "baseline-derived-missing",
                "derived mirror omits neutralised release file: %s" % rel,
                BASELINE))
        for rel in sorted(set(derived) - set(actual_derived)):
            findings.append(_finding(
                "baseline-derived-extra",
                "derived mirror records file with no production docgen body: %s"
                % rel, BASELINE))
        for rel in sorted(set(derived) & set(actual_derived)):
            if derived[rel] != actual_derived[rel]:
                findings.append(_finding(
                    "baseline-derived-mismatch",
                    "%s neutralised digest expected %s but has %s" %
                    (rel, derived[rel], actual_derived[rel]), BASELINE))
    if len(findings) != finding_start:
        return version, None
    surface = {
        "system_version": str(raw_version),
        "files": files,
        "derived": derived,
    }
    canonical = json.dumps(
        surface, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")
    identity = hashlib.sha256(canonical).hexdigest()
    return version, identity


def _load_corrections(root: str, findings: List[Finding]
                      ) -> List[Dict[str, str]]:
    path = os.path.join(root, CORRECTIONS)
    if not os.path.exists(path):
        return []
    try:
        data = json.loads(
            _read(path), object_pairs_hook=_object_without_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        findings.append(_finding(
            "corrections-unreadable", "cannot read corrections: %s" % exc,
            CORRECTIONS))
        return []
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        findings.append(_finding(
            "corrections-schema",
            "correction registry must be an object with schema_version 1",
            CORRECTIONS))
        return []
    entries = data.get("records")
    if not isinstance(entries, list):
        findings.append(_finding(
            "corrections-records",
            "correction registry records must be an array", CORRECTIONS))
        return []
    clean_entries: List[Dict[str, str]] = []
    ids = set()
    targets = set()
    version_dispositions = set()
    for index, entry in enumerate(entries):
        label = "record %d" % (index + 1)
        if not isinstance(entry, dict):
            findings.append(_finding(
                "correction-invalid", "%s must be an object" % label,
                CORRECTIONS))
            continue
        ident = entry.get("id")
        reason = entry.get("reason")
        disposition = entry.get("disposition")
        if (not isinstance(ident, str) or not ident or ident in ids
                or not isinstance(reason, str) or not reason.strip()):
            findings.append(_finding(
                "correction-identity",
                "%s needs a unique non-empty id and reason" % label,
                CORRECTIONS))
            continue
        ids.add(ident)
        if disposition in ("withdrawn", "amendment", "misplaced-release"):
            target = entry.get("target_section_sha256")
            if not isinstance(target, str) or not HASH_RE.fullmatch(target):
                findings.append(_finding(
                    "correction-target",
                    "%s %s record needs a section SHA-256" %
                    (label, disposition),
                    CORRECTIONS))
            elif "version" in entry:
                findings.append(_finding(
                    "correction-contradictory",
                    "%s targeted correction must not also declare version" %
                    label, CORRECTIONS))
            elif target in targets:
                findings.append(_finding(
                    "correction-target-duplicate",
                    "multiple correction dispositions target section %s" %
                    target,
                    CORRECTIONS))
            else:
                targets.add(target)
                clean_entries.append(dict(entry))
        elif disposition in ("reserved", "non-main-release"):
            version = _semver(entry.get("version"))
            if version is None:
                findings.append(_finding(
                    "correction-version",
                    "%s %s record needs a SemVer version" %
                    (label, disposition),
                    CORRECTIONS))
            elif "target_section_sha256" in entry:
                findings.append(_finding(
                    "correction-contradictory",
                    "%s %s record must not target a changelog section" %
                    (label, disposition), CORRECTIONS))
            elif version in version_dispositions:
                findings.append(_finding(
                    "correction-version-duplicate",
                    "multiple version dispositions claim %s" % version,
                    CORRECTIONS))
            else:
                version_dispositions.add(version)
                clean = dict(entry)
                clean["version"] = version
                clean_entries.append(clean)
        else:
            findings.append(_finding(
                "correction-disposition",
                "%s disposition must be amendment, misplaced-release, "
                "non-main-release, reserved, or withdrawn" % label,
                CORRECTIONS))
    return clean_entries


def _section_digest(lines: Sequence[str]) -> str:
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _changelog(root: str, current_version: Optional[str],
               findings: List[Finding]) -> Tuple[ChangelogRecord, ...]:
    path = os.path.join(root, CHANGELOG)
    try:
        text = _read(path)
    except (OSError, UnicodeError) as exc:
        findings.append(_finding(
            "changelog-unreadable", "cannot read changelog: %s" % exc,
            CHANGELOG))
        return ()
    corrections = _load_corrections(root, findings)
    targeted = {
        entry["target_section_sha256"]: entry for entry in corrections
        if isinstance(entry.get("target_section_sha256"), str)
    }
    version_dispositions = [
        entry for entry in corrections
        if entry.get("disposition") in ("reserved", "non-main-release")
        and isinstance(entry.get("version"), str)
    ]
    records: List[ChangelogRecord] = []
    lines = text.splitlines(keepends=True)
    section_starts = [
        index for index, line in enumerate(lines) if line.startswith("## ")]
    section_starts.append(len(lines))
    section_counts: Dict[str, int] = {}
    parsed_sections = []
    for index, line in enumerate(lines):
        heading = line.rstrip("\r\n")
        if (VERSION_HEADING_CANDIDATE_RE.match(heading)
                and not (line.startswith("## ")
                         and HEADING_RE.fullmatch(heading))):
            findings.append(_finding(
                "changelog-heading-malformed",
                "version-like heading does not use exact '## [SemVer]' "
                "structure: %s" % heading,
                CHANGELOG, index + 1))
    for offset, start in enumerate(section_starts[:-1]):
        end = section_starts[offset + 1]
        heading = lines[start].rstrip("\r\n")
        digest = _section_digest(lines[start:end])
        section_counts[digest] = section_counts.get(digest, 0) + 1
        parsed_sections.append((start + 1, heading, digest))

    valid_targets = set()
    for target, entry in targeted.items():
        count = section_counts.get(target, 0)
        if count != 1:
            findings.append(_finding(
                "correction-target-%s" % ("missing" if count == 0 else "ambiguous"),
                "%s correction target resolves to %d changelog sections: %s" %
                (entry.get("disposition"), count, target), CORRECTIONS))
        else:
            valid_targets.add(target)

    for line_no, heading, digest in parsed_sections:
        match = HEADING_RE.fullmatch(heading)
        if not match:
            continue
        token = match.group(1).strip()
        version_match = VERSION_PREFIX_RE.match(token)
        if not version_match:
            if re.match(r"^\d", token):
                findings.append(_finding(
                    "changelog-version-invalid",
                    "version-like heading is not strict SemVer: %s" % heading,
                    CHANGELOG, line_no))
            continue
        version = _semver(version_match.group(1))
        if version is None:
            findings.append(_finding(
                "changelog-version-invalid",
                "heading does not start with strict SemVer: %s" % heading,
                CHANGELOG, line_no))
            continue
        suffix_raw = token[version_match.end():]
        if suffix_raw and not re.fullmatch(r"\s+(?:—|-)\s+.+", suffix_raw):
            findings.append(_finding(
                "changelog-token-partial",
                "SemVer token has an invalid attached suffix: %s" % heading,
                CHANGELOG, line_no))
            continue
        suffix = suffix_raw.strip()
        status_match = re.search(r"(?i)\b(WITHDRAWN|RESERVED)\b", suffix)
        disposition = status_match.group(1).lower() if status_match else "release"
        if digest in valid_targets:
            corrected = targeted[digest]["disposition"]
            if disposition != "release":
                findings.append(_finding(
                    "correction-contradictory",
                    "section already declares %s but registry also declares %s" %
                    (disposition, corrected), CORRECTIONS))
            else:
                disposition = corrected
        if disposition in ("release", "misplaced-release"):
            record_id = "release:%s" % version
        else:
            record_id = "%s:%s" % (disposition, digest)
        records.append(ChangelogRecord(
            record_id=record_id,
            version=version,
            disposition=disposition,
            line=line_no,
            heading=heading,
            section_sha256=digest,
        ))
    for entry in version_dispositions:
        version = entry["version"]
        disposition = entry["disposition"]
        records.append(ChangelogRecord(
            record_id="%s:%s" % (disposition, version),
            version=version,
            disposition=disposition,
            line=0,
            heading="correction registry: %s" % entry["id"],
            section_sha256="",
        ))

    release_records = [
        record for record in records
        if record.disposition in ("release", "misplaced-release")]
    released_versions = {record.version for record in release_records}
    for entry in version_dispositions:
        if entry["version"] in released_versions:
            findings.append(_finding(
                "correction-version-contradictory",
                "%s is both a mainline release and %s" %
                (entry["version"], entry["disposition"]),
                CORRECTIONS))
    for field, key in (
            ("record id", lambda record: record.record_id),
            ("release version", lambda record: record.version)):
        groups: Dict[str, List[ChangelogRecord]] = {}
        for record in release_records:
            groups.setdefault(key(record), []).append(record)
        for value, group in sorted(groups.items()):
            if len(group) > 1:
                findings.append(_finding(
                    "changelog-%s-duplicate" % field.replace(" ", "-"),
                    "duplicate %s %s at lines %s" %
                    (field, value, ", ".join(str(item.line) for item in group)),
                    CHANGELOG, group[0].line))

    ordered_records = [
        record for record in release_records
        if record.disposition != "misplaced-release"]
    for earlier, later in zip(ordered_records, ordered_records[1:]):
        if _semver_key(earlier.version) <= _semver_key(later.version):
            findings.append(_finding(
                "changelog-order",
                "release order is not strictly descending: %s (line %d) "
                "before %s (line %d)" %
                (earlier.version, earlier.line, later.version, later.line),
                CHANGELOG, later.line))

    explicit = {
        record.version for record in records
        if record.disposition in (
            "non-main-release", "reserved", "withdrawn")}
    current_match = SEMVER_RE.fullmatch(current_version or "")
    current_major = int(current_match.group(1)) if current_match else None
    informal_reported = set()
    for match in INFORMAL_STATUS_RE.finditer(text):
        version = _semver(match.group(1))
        parsed = SEMVER_RE.fullmatch(version or "")
        if (version and parsed and int(parsed.group(1)) == current_major
                and version not in explicit and version not in informal_reported):
            informal_reported.add(version)
            line_no = text.count("\n", 0, match.start()) + 1
            findings.append(_finding(
                "changelog-status-informal",
                "%s is described as %s only in prose; add an explicit "
                "reserved/withdrawn correction record" %
                (version, match.group(2).lower()), CHANGELOG, line_no))

    if current_version:
        current = SEMVER_RE.fullmatch(current_version)
        assert current
        major, highest_minor = int(current.group(1)), int(current.group(2))
        represented = {
            (int(match.group(1)), int(match.group(2)))
            for record in records
            for match in [SEMVER_RE.fullmatch(record.version)]
            if (match and int(match.group(3)) == 0
                and match.group(4) is None and match.group(5) is None
                and record.disposition in (
                    "release", "misplaced-release", "non-main-release",
                    "reserved", "withdrawn"))
        }
        for minor in range(highest_minor + 1):
            if (major, minor) not in represented:
                findings.append(_finding(
                    "changelog-minor-gap",
                    "%d.%d.0 is neither a mainline release nor explicitly "
                    "disposed as non-main/reserved/withdrawn" %
                    (major, minor), CHANGELOG))
        if not release_records or release_records[0].version != current_version:
            top = release_records[0].version if release_records else "none"
            findings.append(_finding(
                "changelog-current-mismatch",
                "first release record is %s, current authority is %s" %
                (top, current_version), CHANGELOG))
    return tuple(records)


def audit_version_records(root: str, expected_role: str) -> VersionAudit:
    """Return defects for an explicitly selected vault role.

    ``generic-master`` proves the exact release surface and complete changelog.
    ``personal-instance`` proves the authority and mirror records without
    treating an instance-owned changelog or intentional file customizations as
    product-release defects.  The manifest may not select its own weaker mode.
    """
    root = os.path.abspath(root)
    findings: List[Finding] = []
    if expected_role not in ("generic-master", "personal-instance"):
        raise ValueError("expected_role must be generic-master or personal-instance")
    manifest_version, instance_role = _manifest_version(root, findings)
    if instance_role != expected_role:
        findings.append(_finding(
            "manifest-role-mismatch",
            "caller requires %s but manifest declares %r" %
            (expected_role, instance_role), MANIFEST))
    package_version = _package_version(root, findings)
    baseline_version, identity = _baseline(
        root, manifest_version, findings,
        verify_surface=expected_role == "generic-master",
        verify_live=expected_role == "generic-master")
    versions = {
        "authority": manifest_version,
        "package_mirror": package_version,
        "baseline_mirror": baseline_version,
    }
    if (manifest_version is not None and package_version is not None
            and package_version != manifest_version):
        findings.append(_finding(
            "package-mirror-mismatch",
            "package mirror %s does not match manifest authority %s" %
            (package_version, manifest_version), PACKAGE))
    records = (_changelog(root, manifest_version, findings)
               if expected_role == "generic-master" else ())
    findings.sort(key=lambda item: (
        item.path, item.line if item.line is not None else 0,
        item.code, item.message))
    return VersionAudit(
        versions=versions,
        baseline_identity=identity,
        records=records,
        findings=tuple(findings),
    )


__all__ = [
    "ChangelogRecord",
    "CORRECTIONS",
    "Finding",
    "VersionAudit",
    "audit_version_records",
]
