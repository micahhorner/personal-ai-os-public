"""Compose append-only release evidence into the one final gate verdict."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import estate
    from .release_gate import (discover_and_verify_authoritative_coverage,
                               evaluate_release_gate)
    from .support_matrix import load_support_matrix
except ImportError:
    import estate  # type: ignore
    from release_gate import (discover_and_verify_authoritative_coverage,
                              evaluate_release_gate)
    from support_matrix import load_support_matrix


class ComposeError(ValueError):
    pass


def _load(path: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ComposeError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ComposeError(f"{label} must be a JSON object")
    return value


def compose(*, repository: str, matrix_path: str, qualification_path: str,
            source_check_path: str, fault_path: str,
            minimum_version: str, authority_repository: str | None = None,
            authority_ref: str | None = None,
            authority_commit: str | None = None,
            predecessor_repository: str | None = None,
            predecessor_ref: str | list[str] | None = None,
            predecessor_commit: str | list[str] | None = None) -> dict[str, Any]:
    matrix = load_support_matrix(matrix_path)
    qualification = _load(qualification_path, "qualification")
    if qualification.get("verdict") != "passed":
        raise ComposeError("qualification verdict must be passed")
    target = qualification.get("target")
    sources = qualification.get("sources")
    if not isinstance(target, dict) or not isinstance(sources, list):
        raise ComposeError("qualification target/sources are malformed")
    if (target.get("commit") != matrix.target.commit
            or target.get("version") != matrix.target.version):
        raise ComposeError("qualification target is not the matrix target")
    recovery_by_mode: dict[str, list[tuple[str, dict[str, Any]]]] = {
        "clean-git": [], "no-git": []}
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or source.get("execution") == "skipped-not-supported":
            continue
        record = source.get("recovery")
        if not isinstance(record, dict):
            raise ComposeError(f"sources[{index}] omits recovery evidence")
        mode = record.get("fixture_mode")
        if mode in recovery_by_mode and record.get("recovery_qualified") is True:
            source_id = source.get("id")
            if not isinstance(source_id, str) or not source_id:
                raise ComposeError(f"sources[{index}] has no stable id")
            recovery_by_mode[mode].append((source_id, record))
    missing_modes = [mode for mode, records in recovery_by_mode.items()
                     if not records]
    if missing_modes:
        raise ComposeError(
            "qualification omits qualified recovery mode(s): "
            + ", ".join(sorted(missing_modes)))
    # One exact proof per mode is the release-gate contract. Selection is stable
    # across input ordering and never rewrites the product-issued record.
    recovery_records = [
        sorted(recovery_by_mode[mode], key=lambda item: item[0])[0][1]
        for mode in ("clean-git", "no-git")
    ]
    split = any(value is not None for value in (
        authority_repository, authority_ref, authority_commit))
    if split and not all(isinstance(value, str) and value for value in (
            authority_repository, authority_ref, authority_commit)):
        raise ComposeError(
            "split authority requires repository, ref, and full commit pin")
    if split and (len(authority_commit) != 40 or any(
            char not in "0123456789abcdef" for char in authority_commit)):
        raise ComposeError("authority commit must be a full lowercase SHA-1")
    predecessor = any(value is not None for value in (
        predecessor_repository, predecessor_ref, predecessor_commit))
    if predecessor and not split:
        raise ComposeError("predecessor authority requires split historical authority")
    predecessor_refs = ([predecessor_ref] if isinstance(predecessor_ref, str)
                        else predecessor_ref)
    predecessor_commits = ([predecessor_commit]
                           if isinstance(predecessor_commit, str)
                           else predecessor_commit)
    if predecessor and not (
            isinstance(predecessor_repository, str) and predecessor_repository
            and isinstance(predecessor_refs, list) and predecessor_refs
            and isinstance(predecessor_commits, list) and predecessor_commits
            and len(predecessor_refs) == len(predecessor_commits)
            and all(isinstance(value, str) and value
                    for value in predecessor_refs + predecessor_commits)):
        raise ComposeError(
            "predecessor authority requires one repository and equal nonempty ref/commit pins")
    if predecessor and any(
            len(commit) != 40
            or any(char not in "0123456789abcdef" for char in commit)
            for commit in predecessor_commits):
        raise ComposeError("predecessor commits must be full lowercase SHA-1 values")
    target_record = estate.load_release(repository, matrix.target.ref)
    if (target_record.commit != matrix.target.commit
            or target_record.system_version != matrix.target.version):
        raise ComposeError("target repository ref does not match the matrix target")
    if split:
        authority_tip = estate.load_release(authority_repository, authority_ref)
        if authority_tip.commit != authority_commit:
            raise ComposeError("authority ref does not match its pinned commit")
        if estate._version_key(authority_tip.system_version) >= estate._version_key(
                matrix.target.version):
            raise ComposeError("historical authority must end before the target version")
        predecessor_records = []
        if predecessor:
            for predecessor_ref_value, predecessor_commit_value in zip(
                    predecessor_refs, predecessor_commits):
                record = estate.load_release(
                    predecessor_repository, predecessor_ref_value)
                if record.commit != predecessor_commit_value:
                    raise ComposeError(
                        "predecessor ref does not match its pinned commit")
                predecessor_records.append(record)
            predecessor_records.sort(
                key=lambda record: estate._version_key(record.system_version))
            predecessor_versions = [
                estate._version_key(record.system_version)
                for record in predecessor_records
            ]
            if (len({record.commit for record in predecessor_records})
                    != len(predecessor_records)
                    or len(set(predecessor_versions)) != len(predecessor_versions)
                    or not (estate._version_key(authority_tip.system_version)
                            < predecessor_versions[0]
                            and predecessor_versions[-1]
                            < estate._version_key(matrix.target.version))):
                raise ComposeError(
                    "predecessor versions must be unique, follow historical authority, and precede target")
        commits = estate.discover_mainline_states(
            authority_repository, authority_commit,
            minimum_version=minimum_version,
            maximum_version=authority_tip.system_version)
        records = [estate.load_release(authority_repository, commit)
                   for commit in commits]
        records.extend(predecessor_records)
        records.append(target_record)
        authority_envelope = {
            "kind": "git-mainline-estate", "complete": True,
            "target_commit": matrix.target.commit,
            "records": [{"commit": r.commit, "version": r.system_version}
                        for r in records],
        }
        # Import through release_gate's public verifier; never trust an asserted
        # complete=true envelope without checking it against the pinned matrix.
        try:
            from .release_gate import verify_authoritative_coverage
        except ImportError:
            from release_gate import verify_authoritative_coverage  # type: ignore
        authority = {
            **verify_authoritative_coverage(matrix, authority_envelope),
            "minimum_version": minimum_version,
            "maximum_version": authority_tip.system_version,
            "derivation": "split-git-mainline-estate",
            "authority_commit": authority_commit,
        }
        if predecessor_records:
            authority["predecessors"] = [
                {"commit": record.commit, "version": record.system_version}
                for record in predecessor_records
            ]
    else:
        authority = discover_and_verify_authoritative_coverage(
            repository, matrix, minimum_version=minimum_version)
    # evaluate_release_gate expects the independently derived authority envelope,
    # while discovery returns its verified summary. Re-derive the exact records
    # through the public estate API is intentionally kept in release_gate.
    if not split:
        commits = estate.discover_mainline_states(
            repository, matrix.target.commit, minimum_version=minimum_version,
            maximum_version=matrix.target.version)
        authority_envelope = {
            "kind": "git-mainline-estate", "complete": True,
            "target_commit": matrix.target.commit,
            "records": [{"commit": r.commit, "version": r.system_version}
                        for r in (estate.load_release(repository, c) for c in commits)],
        }
    result = evaluate_release_gate(
        matrix=matrix, authority=authority_envelope,
        target_state=target.get("product_state", {}), sources=sources,
        source_check=_load(source_check_path, "source-check evidence"),
        fault_evidence=_load(fault_path, "fault evidence"),
        recovery_evidence={"records": recovery_records},
    ).to_dict()
    return {"schema_version": 1, "target": matrix.target.__dict__,
            "authority": authority, "gate": result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose final release evidence")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--qualification", required=True)
    parser.add_argument("--source-check", required=True)
    parser.add_argument("--fault-evidence", required=True)
    parser.add_argument("--minimum-version", required=True)
    parser.add_argument("--authority-repository")
    parser.add_argument("--authority-ref")
    parser.add_argument("--authority-commit")
    parser.add_argument("--predecessor-repository")
    parser.add_argument("--predecessor-ref", action="append")
    parser.add_argument("--predecessor-commit", action="append")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        raise ComposeError("refusing to replace existing gate evidence")
    payload = compose(repository=args.repository, matrix_path=args.matrix,
                      qualification_path=args.qualification,
                      source_check_path=args.source_check,
                      fault_path=args.fault_evidence,
                      minimum_version=args.minimum_version,
                      authority_repository=args.authority_repository,
                      authority_ref=args.authority_ref,
                      authority_commit=args.authority_commit,
                      predecessor_repository=args.predecessor_repository,
                      predecessor_ref=args.predecessor_ref,
                      predecessor_commit=args.predecessor_commit)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(json.dumps({"verdict": payload["gate"]["verdict"],
                      "evidence": str(output.resolve())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
