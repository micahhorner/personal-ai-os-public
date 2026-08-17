"""Component census and activation-evidence checks.

The generated census may include activated packs.  Activation evidence is a
product-core contract and deliberately covers only the three canonical core
entrypoint locations; pack evidence remains governed by the pack lifecycle.
"""
from __future__ import annotations

import glob
import os
import stat
from dataclasses import dataclass

import yaml

from lib.frontmatter import parse_file
from lib.packtrust import activation_status
from lib.safepaths import SafePathError, safe_relative_path


CORE_PATTERNS = (
    "System/Capabilities/*/SKILL.md",
    "System/Agents/*/AGENT.md",
    "System/Workflows/*.md",
)
PACK_PATTERNS = (
    "Packs/*/capabilities/*.md",
    "Packs/*/agents/*/AGENT.md",
    "Packs/*/workflows/*.md",
)


@dataclass(frozen=True)
class EvidenceFinding:
    component: str
    code: str
    detail: str

    def message(self) -> str:
        return f"{self.component}: {self.detail} [{self.code}]"


@dataclass(frozen=True)
class EvidenceAudit:
    active_components: int
    findings: tuple[EvidenceFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def count(self, code: str) -> int:
        return sum(f.code == code for f in self.findings)


def _component_row(note):
    meta = note.meta or {}
    if not (meta.get("component_type") or str(meta.get("type")) == "workflow"):
        return None
    return {
        "id": meta.get("id"),
        "component_type": meta.get("component_type") or "workflow",
        "status": meta.get("status", "active"),
        "version": meta.get("version"),
        "dependencies": meta.get("dependencies"),
        "path": note.relpath.replace(os.sep, "/"),
    }


def _contained_kind(root: str, rel: str):
    """Return final lstat while rejecting a symlink in every path component."""
    current = root
    info = None
    for part in rel.split("/"):
        current = os.path.join(current, part)
        info = os.stat(current, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            raise SafePathError(f"contained path traverses a symlink: {rel}")
    return info


def component_census(root: str, *, include_active_packs: bool = True):
    """Return deterministic generated-index rows plus non-activated-pack notes."""
    patterns = list(CORE_PATTERNS)
    warnings = []
    active_packs = set()
    if include_active_packs:
        packs_dir = os.path.join(root, "Packs")
        if os.path.isdir(packs_dir):
            for pack_name in sorted(os.listdir(packs_dir)):
                pack_root = os.path.join(packs_dir, pack_name)
                if not os.path.isfile(os.path.join(pack_root, "pack.yaml")):
                    continue
                active, reason, _tree_hash = activation_status(root, pack_root)
                if active:
                    active_packs.add(pack_name)
                else:
                    warnings.append(
                        f"Packs/{pack_name} components not activated: {reason}; "
                        "install through `aios pack` to create a matching receipt"
                    )
        patterns.extend(PACK_PATTERNS)
    rows = []
    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(root, pattern))):
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            parts = rel.split("/")
            if parts[0] == "Packs" and (len(parts) < 2 or parts[1] not in active_packs):
                continue
            try:
                info = _contained_kind(root, rel)
            except OSError as exc:
                raise SafePathError(f"component source is unavailable: {rel}") from exc
            if not stat.S_ISREG(info.st_mode):
                raise SafePathError(f"component source is not a regular file: {rel}")
            row = _component_row(parse_file(path, root))
            if row is not None:
                rows.append(row)
    return rows, warnings


def _safe_test_target(root: str, ref: object):
    if not isinstance(ref, str):
        return "test reference must be a string"
    try:
        rel = safe_relative_path(ref, "component test reference")
    except SafePathError as exc:
        return str(exc)
    if not rel.startswith("System/Tests/scripts/") or not rel.endswith(".py"):
        return "activation test must be an executable Python script under System/Tests/scripts/"
    try:
        info = _contained_kind(root, rel)
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            return f"test reference is not a regular file or directory: {rel}"
    except SafePathError as exc:
        return str(exc)
    except OSError:
        return f"test reference does not exist: {rel}"
    return None


def _safe_evaluation_target(root: str, ref: object):
    if not isinstance(ref, str):
        return "runtime evaluation reference must be a string"
    try:
        rel = safe_relative_path(ref, "runtime evaluation reference")
    except SafePathError as exc:
        return str(exc)
    if not rel.startswith("System/Tests/fixtures/"):
        return "runtime evaluation must be confined under System/Tests/fixtures/"
    try:
        info = _contained_kind(root, rel)
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            return f"runtime evaluation is not a regular file or directory: {rel}"
    except SafePathError as exc:
        return str(exc)
    except OSError:
        return f"runtime evaluation does not exist: {rel}"
    return None


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    out = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in out:
            raise yaml.YAMLError(f"duplicate key: {key}")
        out[key] = loader.construct_object(value_node, deep=deep)
    return out


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping
)


def _result_record(root: str, component: str):
    rel = f"System/Tests/results/{component}.yaml"
    path = os.path.join(root, *rel.split("/"))
    try:
        info = _contained_kind(root, rel)
        if not stat.S_ISREG(info.st_mode):
            return rel, None, "result record is not a confined regular file"
        with open(path, encoding="utf-8") as stream:
            value = yaml.load(stream, Loader=_UniqueKeyLoader)
    except FileNotFoundError:
        return rel, None, "missing current-version passing result record"
    except SafePathError as exc:
        return rel, None, f"result record is not safely confined ({exc})"
    except (OSError, UnicodeError, TypeError, yaml.YAMLError) as exc:
        return rel, None, f"result record is unreadable or invalid YAML ({exc})"
    if not isinstance(value, dict):
        return rel, None, "result record must be a YAML mapping"
    return rel, value, None


def audit_core_component_evidence(root: str) -> EvidenceAudit:
    rows, _warnings = component_census(root, include_active_packs=False)
    findings = []
    active = 0
    for row in rows:
        if row.get("status") != "active":
            continue
        active += 1
        cid = str(row.get("id") or row.get("path"))
        note = parse_file(os.path.join(root, *str(row["path"]).split("/")), root)
        tests = (note.meta or {}).get("tests")
        if not isinstance(tests, list) or not tests:
            findings.append(EvidenceFinding(cid, "tests-missing", "active core component has no tests"))
        else:
            for ref in tests:
                error = _safe_test_target(root, ref)
                if error:
                    findings.append(EvidenceFinding(cid, "test-ref-invalid", error))
        evaluations = (note.meta or {}).get("x_runtime_evaluations", [])
        if not isinstance(evaluations, list):
            findings.append(EvidenceFinding(
                cid, "evaluation-ref-invalid", "x_runtime_evaluations must be a list"
            ))
        else:
            for ref in evaluations:
                error = _safe_evaluation_target(root, ref)
                if error:
                    findings.append(EvidenceFinding(cid, "evaluation-ref-invalid", error))
        rel, record, error = _result_record(root, cid)
        if error:
            code = "result-missing" if record is None and error.startswith("missing") else "result-invalid"
            findings.append(EvidenceFinding(cid, code, f"{rel}: {error}"))
            continue
        if record.get("component") != cid:
            findings.append(EvidenceFinding(cid, "result-component-mismatch", f"{rel}: component must equal '{cid}'"))
        if record.get("result") != "pass":
            findings.append(EvidenceFinding(cid, "result-not-pass", f"{rel}: result must equal 'pass'"))
        if str(record.get("version")) != str(row.get("version")):
            findings.append(EvidenceFinding(
                cid, "result-version-stale",
                f"{rel}: passing version {record.get('version')!r} does not match current {row.get('version')!r}",
            ))
    return EvidenceAudit(active, tuple(findings))
