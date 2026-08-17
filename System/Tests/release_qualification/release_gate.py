"""Fail-closed contracts for a final release-qualification verdict.

This module deliberately consumes evidence; it does not manufacture it.  In
particular, recovery commands must be copied from product output and transaction
fault results must cover the complete public boundary/phase matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
import shlex
from typing import Any, Iterable, Mapping

try:
    from . import estate
    from .support_matrix import SupportMatrix
    from .transaction_faults import BOUNDARIES, PHASES
except ImportError:  # direct-file execution/import
    import estate  # type: ignore
    from support_matrix import SupportMatrix  # type: ignore
    from transaction_faults import BOUNDARIES, PHASES  # type: ignore


LEGAL_ROOT_PATHS = frozenset({
    "LICENSE.md",
    "README.md",
    "START-HERE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
})
RECOVERY_MODES = frozenset({"clean-git", "no-git"})
GENERIC_MASTER_SOURCE_ADVISORIES = frozenset({
    "[health (mechanical)] [validate] AGENTS.md: no frontmatter",
    "[health (mechanical)] [validate] CLAUDE.md: no frontmatter",
    "[health (mechanical)] [validate] CONTRIBUTING.md: no frontmatter",
    "[health (mechanical)] [validate] LICENSE.md: no frontmatter",
    "[health (mechanical)] [validate] README.md: no frontmatter",
    "[health (mechanical)] [validate] SECURITY.md: no frontmatter",
    "[health (mechanical)] [validate] System/Migrations/000-example/README.md: no frontmatter",
    "[health (mechanical)] [validate] System/Migrations/020-core-license-boundary/README.md: no frontmatter",
    "[health (mechanical)] [validate] System/Migrations/020-core-license-boundary/payloads/LICENSE.md: no frontmatter",
    "[health (mechanical)] [validate] System/Tests/README.md: no frontmatter",
    "[health (mechanical)] [pack-check] 1 advisory finding(s) across 1 installed pack(s) — run `aios pack-check` for the detail",
})


class ReleaseGateError(ValueError):
    """Required release evidence is absent, ambiguous, or contradictory."""


@dataclass(frozen=True)
class GateResult:
    passed: bool
    checks: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": "passed" if self.passed else "failed",
            "checks": [dict(check) for check in self.checks],
        }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReleaseGateError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ReleaseGateError(f"{label} must be a nonempty string")
    return value


def _commit_version(value: Any, label: str) -> tuple[str, str]:
    item = _mapping(value, label)
    return _text(item.get("commit"), f"{label}.commit"), _text(
        item.get("version"), f"{label}.version")


def verify_authoritative_coverage(
    matrix: SupportMatrix, authority: Mapping[str, Any]
) -> dict[str, Any]:
    """Prove every release in a separately generated mainline estate is pinned."""
    authority = _mapping(authority, "support authority")
    if authority.get("kind") != "git-mainline-estate":
        raise ReleaseGateError(
            "support authority.kind must be git-mainline-estate")
    if authority.get("complete") is not True:
        raise ReleaseGateError("support authority must assert complete=true")
    if authority.get("target_commit") != matrix.target.commit:
        raise ReleaseGateError("support authority target does not match matrix target")
    records = authority.get("records")
    if not isinstance(records, list) or not records:
        raise ReleaseGateError("support authority.records must be nonempty")
    authoritative = [_commit_version(item, f"authority.records[{index}]")
                     for index, item in enumerate(records)]
    if len(authoritative) != len(set(authoritative)):
        raise ReleaseGateError("support authority contains duplicate release identities")
    target_identity = (matrix.target.commit, matrix.target.version)
    if authoritative.count(target_identity) != 1:
        raise ReleaseGateError("support authority must contain the exact target once")
    expected = set(authoritative) - {target_identity}
    pinned = {(source.commit, source.version) for source in matrix.sources}
    if len(pinned) != len(matrix.sources):
        raise ReleaseGateError("matrix contains duplicate commit/version identities")
    missing = sorted(expected - pinned)
    extra = sorted(pinned - expected)
    if missing or extra:
        raise ReleaseGateError(
            f"support matrix is not authoritative-complete; missing={missing}, extra={extra}")
    return {"name": "authoritative-support-coverage", "passed": True,
            "release_count": len(authoritative)}


def discover_and_verify_authoritative_coverage(
    repository: str, matrix: SupportMatrix, *, minimum_version: str
) -> dict[str, Any]:
    """Derive coverage from Git history rather than trusting matrix declarations.

    ``minimum_version`` must come from the separately owned product support
    policy.  The target commit is both the mainline tip and inclusive maximum;
    moving branches and the current working tree are never consulted.
    """
    minimum_version = _text(minimum_version, "minimum_version")
    commits = estate.discover_mainline_states(
        repository, matrix.target.commit,
        minimum_version=minimum_version,
        maximum_version=matrix.target.version,
    )
    authority = {
        "kind": "git-mainline-estate",
        "complete": True,
        "target_commit": matrix.target.commit,
        "records": [
            {
                "commit": record.commit,
                "version": record.system_version,
            }
            for record in (estate.load_release(repository, commit)
                           for commit in commits)
        ],
    }
    result = verify_authoritative_coverage(matrix, authority)
    return {**result, "minimum_version": minimum_version,
            "maximum_version": matrix.target.version,
            "derivation": "estate.discover_mainline_states"}


def verify_target_convergence(
    target_state: Mapping[str, Any], sources: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Require dry-run immutability and exact post-apply product/legal bytes."""
    target = _mapping(target_state, "target product state")
    hashes = _mapping(target.get("exact_file_hashes"),
                      "target product state exact_file_hashes")
    absent_legal = sorted(LEGAL_ROOT_PATHS - set(hashes))
    if absent_legal:
        raise ReleaseGateError(
            "target product state omits legal/root surfaces: " +
            ", ".join(absent_legal))
    missing_legal = sorted(
        path for path in LEGAL_ROOT_PATHS
        if not isinstance(hashes[path], Mapping)
        or hashes[path].get("kind") == "missing"
    )
    if missing_legal:
        raise ReleaseGateError(
            "target is missing required legal/root files: " +
            ", ".join(missing_legal))
    for key in ("distribution_id", "system_version", "license", "instance_role"):
        _text(target.get(key), f"target product state.{key}")
    checked = 0
    for index, raw in enumerate(sources):
        source = _mapping(raw, f"sources[{index}]")
        if source.get("execution") == "skipped-not-supported":
            continue
        dry = _mapping(source.get("dry_run"), f"sources[{index}].dry_run")
        apply = _mapping(source.get("apply"), f"sources[{index}].apply")
        dry_state = _mapping(dry.get("product_state"), "dry-run product_state")
        apply_state = _mapping(apply.get("product_state"), "apply product_state")
        if dry_state.get("before") != dry_state.get("after"):
            raise ReleaseGateError(
                f"sources[{index}] dry-run changed product/legal state")
        after = apply_state.get("after")
        if not isinstance(after, Mapping):
            raise ReleaseGateError(
                f"sources[{index}] apply product state is malformed")
        normalized_target = dict(target)
        normalized_after = dict(after)
        if (target.get("instance_role") == "generic-master"
                and after.get("instance_role") == "personal-instance"):
            normalized_after["instance_role"] = "generic-master"
        def semantic_hashes(value: Any) -> Any:
            if not isinstance(value, Mapping):
                return value
            return {
                path: ({key: item[key] for key in ("kind", "size", "sha256")
                        if key in item}
                       if isinstance(item, Mapping) else item)
                for path, item in value.items()
            }
        normalized_target["exact_file_hashes"] = semantic_hashes(
            target.get("exact_file_hashes"))
        normalized_after["exact_file_hashes"] = semantic_hashes(
            after.get("exact_file_hashes"))
        if normalized_after != normalized_target:
            raise ReleaseGateError(
                f"sources[{index}] did not converge to exact target product/legal state")
        checked += 1
    if checked == 0:
        raise ReleaseGateError("target convergence has no executed source")
    return {"name": "target-product-legal-convergence", "passed": True,
            "source_count": checked}


def verify_source_check(
    evidence: Mapping[str, Any], target_commit: str
) -> dict[str, Any]:
    evidence = _mapping(evidence, "source-check evidence")
    if evidence.get("target_commit") != target_commit:
        raise ReleaseGateError("source-check evidence is not bound to target commit")
    if evidence.get("command") != "source-check":
        raise ReleaseGateError("source-check evidence names the wrong command")
    if evidence.get("returncode") != 0:
        raise ReleaseGateError("source-check command did not exit zero")
    report = _mapping(evidence.get("report"), "source-check report")
    info = _mapping(report.get("info"), "source-check report.info")
    warnings = report.get("warnings")
    allowed_warnings = (
        isinstance(warnings, list)
        and len(warnings) == len(set(warnings))
        and set(warnings) == GENERIC_MASTER_SOURCE_ADVISORIES
        and info.get("health (mechanical)") == "PASS — 0 errors, 11 warnings"
        and info.get("  health.validate") == "0 errors, 10 warnings"
        and info.get("  health.pack-check") == "0 errors, 1 warnings"
    )
    if (report.get("command") != "source-check"
            or report.get("ok") is not True
            or not str(info.get("verdict_scope", "")).startswith("SOURCE CHECK")
            or report.get("errors") not in ([], 0)
            or (warnings not in ([], 0) and not allowed_warnings)):
        raise ReleaseGateError("source-check report is not a clean SOURCE CHECK pass")
    if (not str(info.get("runtime_certification", "")).startswith("NOT RUN")
            or not str(info.get("release_qualification", "")).startswith("NOT RUN")):
        raise ReleaseGateError("source-check report overclaims runtime/release scope")
    return {"name": "source-check-evidence", "passed": True}


def verify_fault_evidence(
    evidence: Mapping[str, Any], target_commit: str
) -> dict[str, Any]:
    """Require exactly one old-or-new result at every transaction interruption."""
    evidence = _mapping(evidence, "fault evidence")
    if evidence.get("target_commit") != target_commit:
        raise ReleaseGateError("fault evidence is not bound to target commit")
    if evidence.get("fault_injection_enabled") is not True:
        raise ReleaseGateError("fault evidence does not prove injection was enabled")
    cases = evidence.get("cases")
    if not isinstance(cases, list):
        raise ReleaseGateError("fault evidence.cases must be an array")
    required = {(boundary, phase) for boundary in BOUNDARIES for phase in PHASES}
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(cases):
        case = _mapping(raw, f"fault cases[{index}]")
        key = (case.get("boundary"), case.get("phase"))
        if key not in required:
            raise ReleaseGateError(f"fault cases[{index}] names an unknown boundary/phase")
        if key in seen:
            raise ReleaseGateError(f"fault evidence duplicates {key[0]}:{key[1]}")
        seen.add(key)  # type: ignore[arg-type]
        old_hash = _text(case.get("old_tree_sha256"), "old_tree_sha256")
        new_hash = _text(case.get("new_tree_sha256"), "new_tree_sha256")
        live_hash = _text(case.get("live_tree_sha256"), "live_tree_sha256")
        classification = case.get("classification")
        expected_hash = old_hash if classification == "exact-old" else (
            new_hash if classification == "exact-new" else None)
        if expected_hash is None or live_hash != expected_hash:
            raise ReleaseGateError(
                f"fault {key[0]}:{key[1]} is hybrid, ambiguous, or mislabeled")
    missing = sorted(required - seen)
    if missing:
        raise ReleaseGateError(f"fault evidence is incomplete; missing={missing}")
    if len(cases) != len(required):
        raise ReleaseGateError("fault evidence contains unexpected cases")
    return {"name": "mandatory-transaction-faults", "passed": True,
            "case_count": len(cases)}


def verify_recovery_evidence(
    evidence: Mapping[str, Any], target_commit: str
) -> dict[str, Any]:
    """Require exact product-issued commands to restore Git and no-Git fixtures."""
    evidence = _mapping(evidence, "recovery evidence")
    records = evidence.get("records")
    if not isinstance(records, list):
        raise ReleaseGateError("recovery evidence.records must be an array")
    modes: set[str] = set()
    for index, raw in enumerate(records):
        record = _mapping(raw, f"recovery records[{index}]")
        mode = record.get("fixture_mode")
        if mode not in RECOVERY_MODES or mode in modes:
            raise ReleaseGateError("recovery evidence must contain each fixture mode once")
        modes.add(mode)  # type: ignore[arg-type]
        if record.get("target_commit") != target_commit:
            raise ReleaseGateError("recovery record is not bound to target commit")
        issued = _text(record.get("product_issued_command"),
                       "product_issued_command")
        argv = record.get("executed_argv")
        if not isinstance(argv, list) or any(not isinstance(arg, str) for arg in argv):
            raise ReleaseGateError("executed_argv must be an array of strings")
        try:
            parsed = shlex.split(issued)
        except ValueError as exc:
            raise ReleaseGateError("product-issued recovery command is malformed") from exc
        if parsed != argv or record.get("shell") is not False:
            raise ReleaseGateError(
                "executed recovery argv is not the exact product-issued command")
        if (record.get("returncode") != 0 or record.get("recovery_qualified") is not True
                or record.get("before_tree_sha256") != record.get("after_tree_sha256")):
            raise ReleaseGateError(f"{mode} exact recovery was not proved")
    if modes != RECOVERY_MODES:
        raise ReleaseGateError(
            "recovery evidence must prove both clean-git and no-git modes")
    return {"name": "product-issued-git-and-no-git-recovery", "passed": True,
            "modes": sorted(modes)}


def evaluate_release_gate(
    *, matrix: SupportMatrix, authority: Mapping[str, Any],
    target_state: Mapping[str, Any], sources: Iterable[Mapping[str, Any]],
    source_check: Mapping[str, Any], fault_evidence: Mapping[str, Any],
    recovery_evidence: Mapping[str, Any],
) -> GateResult:
    """Return PASS only when every independent release proof is present."""
    checks = (
        verify_authoritative_coverage(matrix, authority),
        verify_target_convergence(target_state, sources),
        verify_source_check(source_check, matrix.target.commit),
        verify_fault_evidence(fault_evidence, matrix.target.commit),
        verify_recovery_evidence(recovery_evidence, matrix.target.commit),
    )
    return GateResult(True, checks)
