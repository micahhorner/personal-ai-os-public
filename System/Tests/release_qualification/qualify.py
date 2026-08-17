"""Compose estate, fixture, and runner into historical release qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from typing import Any, Iterable
import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / "Scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from lib import recovery as recovery_lib  # noqa: E402

try:
    from . import estate, fixture, runner
    from .support_matrix import (
        SourcePin,
        SupportMatrix,
        load_support_matrix,
    )
except ImportError:  # direct-file CLI execution
    import estate  # type: ignore
    import fixture  # type: ignore
    import runner  # type: ignore
    from support_matrix import (  # type: ignore
        SourcePin,
        SupportMatrix,
        load_support_matrix,
    )


class QualificationError(RuntimeError):
    """Qualification cannot proceed without weakening an evidence boundary."""


PRODUCT_STATE_PATHS = (
    "LICENSE.md",
    "README.md",
    "START-HERE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "System/Release/version-record-corrections.json",
)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _existing_directory(value: os.PathLike[str] | str, label: str) -> Path:
    path = Path(value).resolve()
    if not path.is_dir():
        raise QualificationError(f"{label} must be an existing directory")
    return path


def _empty_output(value: os.PathLike[str] | str) -> Path:
    path = _existing_directory(value, "output_dir")
    if any(path.iterdir()):
        raise QualificationError("output_dir must be empty; evidence is append-only")
    return path


def _git(repo: Path, args: Iterable[str], *, check: bool = True,
         environment: dict[str, str] | None = None) -> str:
    arguments = tuple(args)
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["LC_ALL"] = "C"
    if environment:
        env.update(environment)
    process = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    if check and process.returncode:
        raise QualificationError(
            "Git command failed (%s): %s" %
            (" ".join(arguments), process.stderr.strip()))
    return process.stdout


def _source_state(repo: Path) -> dict[str, str]:
    """Capture enough repository state to prove read-only orchestration."""
    parts = {
        "head": _git(repo, ("rev-parse", "HEAD")).strip(),
        "status": _git(
            repo, ("status", "--porcelain=v1", "--untracked-files=all")),
        "refs": _git(repo, ("show-ref",), check=False),
        "worktrees": _git(repo, ("worktree", "list", "--porcelain")),
    }
    encoded = json.dumps(
        {key: parts[key] for key in ("head", "status", "refs")},
        ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")
    parts["sha256"] = hashlib.sha256(encoded).hexdigest()
    parts["worktrees_sha256"] = hashlib.sha256(
        parts["worktrees"].encode("utf-8")
    ).hexdigest()
    return parts


def _source_core_unchanged(before: dict[str, str], after: dict[str, str]) -> bool:
    return all(before[key] == after[key] for key in ("head", "status", "refs"))


def _source_evidence(state: dict[str, str]) -> dict[str, str]:
    """Expose immutable fingerprints, never private paths, refs, or filenames."""
    return {
        "head": state["head"],
        "state_sha256": state["sha256"],
        "worktrees_sha256": state["worktrees_sha256"],
    }


def _write_json(path: Path, value: Any) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False,
                      indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise QualificationError(
            f"refusing to replace existing evidence: {path}") from exc


def _materialize_release(repo: Path, commit: str, destination: Path) -> None:
    """Materialize a generic target release without checkout or personalization."""
    fixture._require_empty_destination(destination)
    archive = fixture._git_archive(repo, commit)
    fixture._extract_archive(archive, destination)


def _local_git(instance: Path, mode: str) -> dict[str, Any]:
    if mode == "no-git":
        return {
            "mode": mode,
            "initialized": False,
            "head": None,
            "status": None,
        }
    if mode != "clean-git":
        raise QualificationError(f"unsupported fixture mode: {mode}")
    isolated_environment = {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_DATE": "2026-07-28T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-07-28T00:00:00+00:00",
    }
    _git(instance, ("init", "-q", "-b", "qualification"),
         environment=isolated_environment)
    _git(instance, ("add", "-A"), environment=isolated_environment)
    index = _git(
        instance, ("ls-files", "--stage", "-z"),
        environment=isolated_environment)
    for record in index.split("\0"):
        if not record:
            continue
        metadata, relative = record.split("\t", 1)
        git_mode = metadata.split(" ", 1)[0]
        path = instance / relative
        if git_mode == "100644":
            path.chmod(0o644)
        elif git_mode == "100755":
            path.chmod(0o755)
    _git(
        instance,
        ("-c", "user.name=Release Qualification",
         "-c", "user.email=qualification@example.invalid",
         "commit", "--no-verify", "-qm", "qualification fixture baseline"),
        environment=isolated_environment,
    )
    # Verify the normalized index/worktree pair before capturing the target.
    _git(instance, ("reset", "--hard", "HEAD"),
         environment=isolated_environment)
    status = _git(
        instance, ("status", "--porcelain=v1", "--untracked-files=all"))
    if status:
        raise QualificationError("clean-git fixture was not clean after commit")
    head = _git(instance, ("rev-parse", "HEAD")).strip()
    tracked = recovery_lib.inspect_commit(instance, head)
    return {
        "mode": mode,
        "initialized": True,
        "identity_scope": "per-command",
        "head": head,
        "tracked_sha256": tracked["tracked_sha256"],
        "git_tree": tracked["git_tree"],
        "status": status,
    }


def _git_after(instance: Path, mode: str) -> dict[str, Any]:
    if mode == "no-git":
        return {
            "mode": mode,
            "initialized": False,
            "head": None,
            "status": None,
        }
    return {
        "mode": mode,
        "initialized": True,
        "head": _git(instance, ("rev-parse", "HEAD")).strip(),
        "status": _git(
            instance, ("status", "--porcelain=v1", "--untracked-files=all")),
    }


def _selected_hashes(root: Path, paths: Iterable[str]) -> dict[str, Any]:
    tree = runner.capture_tree(root)["entries"]
    return {
        path: tree.get(path, {"kind": "missing"})
        for path in sorted(set(paths))
    }


def _product_state(root: Path) -> dict[str, Any]:
    try:
        manifest = yaml.safe_load(
            (root / "SYSTEM-MANIFEST.yaml").read_text(encoding="utf-8")
        )
        system = manifest["system"]
    except (OSError, UnicodeError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise QualificationError(f"cannot read product state: {exc}") from exc
    return {
        "distribution_id": system.get("distribution_id"),
        "system_version": str(system.get("system_version")),
        "license": system.get("license"),
        "instance_role": system.get("instance_role"),
        "exact_file_hashes": _selected_hashes(root, PRODUCT_STATE_PATHS),
    }


def _phase(
    repo: Path,
    target_dir: Path,
    source: SourcePin,
    phase: str,
    phase_root: Path,
    output_dir: Path,
    timeout_seconds: float,
    python_executable: os.PathLike[str] | str,
) -> dict[str, Any]:
    instance = phase_root / f"{source.id} {phase} Instance Ω"
    scratch = phase_root / f"{source.id} {phase} Scratch Ω"
    instance.mkdir()
    scratch.mkdir()
    built = fixture.build_historical_instance(repo, source.ref, instance)
    if built.resolved_commit != source.commit:
        raise QualificationError(
            f"{source.id}: fixture resolved {built.resolved_commit}, "
            f"expected {source.commit}")

    git_before = _local_git(instance, source.fixture_mode)
    watched = tuple(sorted(set(built.seeded_paths + built.modified_paths)))
    protected_before = _selected_hashes(instance, watched)
    product_state_before = _product_state(instance)
    recovery_tree_before = runner.capture_tree(
        instance, normalize_directory_modes=True
    )
    args: list[str] = []
    if source.authorize_legacy_core:
        args.append("--authorize-legacy-core")
    for path in source.accepted_paths:
        args.extend(("--accept", path))
    if phase == "dry-run":
        args.append("--dry-run")

    result = runner.run_upgrade(
        instance,
        target_dir,
        scratch,
        output_dir,
        run_id=f"{source.id}.{phase}",
        timeout_seconds=timeout_seconds,
        python_executable=python_executable,
        extra_args=args,
    )
    protected_after = _selected_hashes(instance, watched)
    product_state_after = _product_state(instance)
    git_after = _git_after(instance, source.fixture_mode)
    seeded_preserved = all(
        protected_before.get(path) == protected_after.get(path)
        for path in built.seeded_paths
    )
    envelope = {
        "schema_version": 1,
        "source_id": source.id,
        "source_ref": source.ref,
        "source_commit": source.commit,
        "phase": phase,
        "fixture_mode": source.fixture_mode,
        "fixture_paths": {
            "instance": str(instance),
            "scratch": str(scratch),
        },
        "fixture": {
            "base_tree_sha256": built.base_tree_sha256,
            "final_tree_sha256": built.final_tree_sha256,
            "seeded_paths": list(built.seeded_paths),
            "modified_paths": list(built.modified_paths),
        },
        "git": {"before": git_before, "after": git_after},
        "recovery_tree_before": recovery_tree_before,
        "protected_surfaces": {
            "before": protected_before,
            "after": protected_after,
            "seeded_paths_preserved": seeded_preserved,
        },
        "product_state": {
            "before": product_state_before,
            "after": product_state_after,
        },
        "runner_evidence_path": result["evidence_path"],
        "runner": result,
    }
    envelope_path = output_dir / f"{source.id}.{phase}.qualification.json"
    _write_json(envelope_path, envelope)
    envelope["evidence_path"] = str(envelope_path)
    return envelope


def _recovery(
    target_dir: Path,
    source: SourcePin,
    apply: dict[str, Any],
    phase_root: Path,
    output_dir: Path,
    timeout_seconds: float,
    python_executable: os.PathLike[str] | str,
    target_commit: str,
) -> dict[str, Any]:
    """Attempt exact Git recovery using only harness-captured identities."""
    product_report = apply.get("runner", {}).get("report")
    product_info = product_report.get("info", {}) if isinstance(product_report, dict) else {}
    product_issued = product_info.get("rollback_command")
    if source.fixture_mode == "no-git":
        issued = product_issued
        if not isinstance(issued, str) or not issued:
            raise QualificationError(
                f"{source.id}: apply omitted product-issued no-Git rollback command")
        try:
            argv = shlex.split(issued)
        except ValueError as exc:
            raise QualificationError(
                f"{source.id}: product-issued rollback command is malformed") from exc
        if not argv or any(not isinstance(value, str) for value in argv):
            raise QualificationError(
                f"{source.id}: product-issued rollback argv is invalid")
        instance = Path(apply["fixture_paths"]["instance"])
        before = apply["recovery_tree_before"]
        process = subprocess.run(
            argv, cwd=instance, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_seconds,
            check=False,
        )
        after = runner.capture_tree(instance, normalize_directory_modes=True)
        passed = process.returncode == 0 and before["sha256"] == after["sha256"]
        evidence = {
            "schema_version": 1,
            "source_id": source.id,
            "status": "recovery-passed" if passed else "recovery-failed",
            "recovery_qualified": passed,
            "fixture_mode": "no-git",
            "target_commit": target_commit,
            "product_issued_command": issued,
            "executed_argv": argv,
            "shell": False,
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "before_tree_sha256": before["sha256"],
            "after_tree_sha256": after["sha256"],
        }
        evidence_path = (
            output_dir / f"{source.id}.recovery.qualification.json")
        _write_json(evidence_path, evidence)
        evidence["evidence_path"] = str(evidence_path)
        return evidence

    instance = Path(apply["fixture_paths"]["instance"])
    scratch = phase_root / f"{source.id} recovery Scratch Ω"
    scratch.mkdir()
    rollback_ref = apply["git"]["before"]["head"]
    expected_hash = apply["recovery_tree_before"]["sha256"]
    expected_tracked = apply["git"]["before"]["tracked_sha256"]
    if not isinstance(product_issued, str) or not product_issued:
        raise QualificationError(
            f"{source.id}: apply omitted product-issued Git rollback command")
    try:
        product_argv = shlex.split(product_issued)
    except ValueError as exc:
        raise QualificationError(
            f"{source.id}: product-issued Git rollback command is malformed") from exc
    before_recovery = runner.capture_tree(instance, normalize_directory_modes=True)
    process = subprocess.run(
        product_argv, cwd=scratch, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout_seconds,
        check=False,
    )
    after_recovery = runner.capture_tree(instance, normalize_directory_modes=True)
    passed = process.returncode == 0 and after_recovery["sha256"] == expected_hash
    envelope = {
        "schema_version": 1,
        "source_id": source.id,
        "status": "recovery-passed" if passed else "recovery-failed",
        "recovery_qualified": passed,
        "fixture_mode": "clean-git",
        "target_commit": target_commit,
        "product_issued_command": product_issued,
        "executed_argv": product_argv,
        "shell": False,
        "returncode": process.returncode,
        "before_tree_sha256": expected_hash,
        "after_tree_sha256": after_recovery["sha256"],
        "rollback_target": {
            "value": rollback_ref,
            "origin": "harness-captured-pre-apply-head",
            "product_generated": False,
        },
        "expected_tree": {
            "sha256": expected_hash,
            "origin": "harness-captured-pre-apply-git-restorable-tree",
            "directory_mode_policy": "normalized-git-restorable",
        },
        "expected_tracked_identity": {
            "sha256": expected_tracked,
            "origin": "harness-captured-pre-apply-commit-proof",
        },
        "process": {"stdout": process.stdout, "stderr": process.stderr},
        "tree_before_recovery_sha256": before_recovery["sha256"],
    }
    envelope_path = output_dir / f"{source.id}.recovery.qualification.json"
    _write_json(envelope_path, envelope)
    envelope["evidence_path"] = str(envelope_path)
    return envelope


def _source_result(source: SourcePin, record: estate.ReleaseRecord,
                   dry: dict[str, Any], apply: dict[str, Any],
                   recovery: dict[str, Any]) -> dict[str, Any]:
    dry_pass = dry["runner"]["phase_verdict"]["status"] == "passed"
    apply_pass = apply["runner"]["phase_verdict"]["status"] == "passed"
    protected = (
        dry["protected_surfaces"]["seeded_paths_preserved"]
        and apply["protected_surfaces"]["seeded_paths_preserved"]
    )
    upgrade_qualified = dry_pass and apply_pass and protected
    recovery_qualified = recovery["recovery_qualified"] is True
    return {
        "id": source.id,
        "ref": source.ref,
        "commit": source.commit,
        "version": source.version,
        "release_identity": record.release_identity,
        "disposition": source.disposition,
        "fixture_mode": source.fixture_mode,
        "upgrade_qualified": upgrade_qualified,
        "recovery_qualified": recovery_qualified,
        "qualified": upgrade_qualified and recovery_qualified,
        "dry_run": dry,
        "apply": apply,
        "recovery": recovery,
    }


def _require_verified_release(record: estate.ReleaseRecord, label: str) -> None:
    if record.baseline_valid is not True:
        detail = "; ".join(record.baseline_mismatches[:3])
        raise QualificationError(
            f"{label}: baseline verification failed"
            + (f": {detail}" if detail else ""))


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Release qualification summary",
        "",
        f"- Target: `{payload['target']['version']}` at "
        f"`{payload['target']['commit']}`",
        f"- Overall verdict: **{payload['verdict'].upper()}**",
        f"- Source repository unchanged: "
        f"**{'yes' if payload['source_repository_unchanged'] else 'NO'}**",
        f"- Shared worktree registry stable during run: "
        f"**{'yes' if payload['source_worktree_registry_unchanged'] else 'no (advisory)'}**",
        "",
        "| Source | From | Fixture | Dry-run | Apply | Recovery | Seeded surfaces | Verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in payload["sources"]:
        if item.get("execution") == "skipped-not-supported":
            lines.append(
                f"| `{item['id']}` | `{item['version']}` | — | — | — | — | — | "
                "not supported |")
            continue
        dry = item["dry_run"]["runner"]["phase_verdict"]["code"]
        apply = item["apply"]["runner"]["phase_verdict"]["code"]
        recovery = item["recovery"]["status"]
        preserved = (
            item["dry_run"]["protected_surfaces"]["seeded_paths_preserved"]
            and item["apply"]["protected_surfaces"]["seeded_paths_preserved"]
        )
        verdict = "PASS" if item["qualified"] else "FAIL"
        lines.append(
            f"| `{item['id']}` | `{item['version']}` | "
            f"`{item['fixture_mode']}` | `{dry}` | `{apply}` | `{recovery}` | "
            f"{'preserved' if preserved else 'CHANGED'} | **{verdict}** |")
    lines.extend([
        "",
        "Dry-run and apply used separate freshly materialized fixtures for every "
        "executed source. Paths deliberately contained spaces and Unicode.",
        "",
    ])
    return "\n".join(lines)


def qualify_matrix(
    repository: os.PathLike[str] | str,
    matrix: SupportMatrix | os.PathLike[str] | str,
    output_dir: os.PathLike[str] | str,
    work_root: os.PathLike[str] | str,
    *,
    source_repository: os.PathLike[str] | str | None = None,
    timeout_seconds: float = 300.0,
    python_executable: os.PathLike[str] | str = sys.executable,
) -> dict[str, Any]:
    """Qualify every executable matrix source against one pinned target."""
    repo = _existing_directory(repository, "repository")
    source_repo = (_existing_directory(source_repository, "source_repository")
                   if source_repository is not None else repo)
    output = _empty_output(output_dir)
    work = _existing_directory(work_root, "work_root")
    if any(_is_within(path, repo) or _is_within(path, source_repo)
           for path in (output, work)):
        raise QualificationError(
            "output_dir and work_root must be outside both repositories")
    loaded = matrix if isinstance(matrix, SupportMatrix) else load_support_matrix(matrix)
    source_before = _source_state(repo)
    historical_before = (_source_state(source_repo)
                         if source_repo != repo else source_before)
    payload: dict[str, Any]
    failure: BaseException | None = None
    try:
        target_record = estate.load_release(repo, loaded.target.ref)
        if (target_record.commit != loaded.target.commit
                or target_record.system_version != loaded.target.version):
            raise QualificationError(
                "target ref does not match its pinned commit/version")
        _require_verified_release(target_record, "target")
        results: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(
                prefix="PAIOS Qualification Ω ", dir=work) as temporary:
            root = Path(temporary)
            target_dir = root / "Target Release Ω"
            target_dir.mkdir()
            _materialize_release(repo, target_record.commit, target_dir)
            target_product_state = _product_state(target_dir)
            for source in loaded.sources:
                record = estate.load_release(source_repo, source.ref)
                if (record.commit != source.commit
                        or record.system_version != source.version):
                    raise QualificationError(
                        f"{source.id}: ref does not match pinned commit/version")
                _require_verified_release(record, source.id)
                if source.disposition == "not-supported":
                    results.append({
                        "id": source.id,
                        "ref": source.ref,
                        "commit": source.commit,
                        "version": source.version,
                        "release_identity": record.release_identity,
                        "disposition": source.disposition,
                        "execution": "skipped-not-supported",
                        "qualified": False,
                    })
                    continue
                dry = _phase(
                    source_repo, target_dir, source, "dry-run", root, output,
                    timeout_seconds, python_executable)
                apply = _phase(
                    source_repo, target_dir, source, "apply", root, output,
                    timeout_seconds, python_executable)
                if (dry["fixture_paths"]["instance"]
                        == apply["fixture_paths"]["instance"]):
                    raise QualificationError(
                        f"{source.id}: dry-run/apply fixture reuse is prohibited")
                recovery = _recovery(
                    target_dir, source, apply, root, output,
                    timeout_seconds, python_executable, loaded.target.commit)
                results.append(
                    _source_result(source, record, dry, apply, recovery))
        executed = [
            item for item in results
            if item.get("execution") != "skipped-not-supported"
        ]
        payload = {
            "schema_version": 1,
            "target": {
                **loaded.target.__dict__,
                "release_identity": target_record.release_identity,
                "product_state": target_product_state,
            },
            "sources": results,
            "verdict": (
                "passed"
                if executed and all(item["qualified"] for item in executed)
                else ("failed" if executed else "not-run")
            ),
            "source_repository_before": _source_evidence(source_before),
            "source_repository_after": None,
            "source_repository_unchanged": None,
            "historical_repository_before": _source_evidence(historical_before),
            "historical_repository_after": None,
            "historical_repository_unchanged": None,
        }
    except BaseException as exc:
        failure = exc
        payload = {}

    source_after = _source_state(repo)
    historical_after = (_source_state(source_repo)
                        if source_repo != repo else source_after)
    unchanged = _source_core_unchanged(source_before, source_after)
    historical_unchanged = _source_core_unchanged(
        historical_before, historical_after)
    worktrees_unchanged = (
        source_before["worktrees"] == source_after["worktrees"]
    )
    if failure is not None:
        if not unchanged or not historical_unchanged:
            raise QualificationError(
                "target or historical repository changed during failed qualification") from failure
        raise failure
    if not unchanged or not historical_unchanged:
        raise QualificationError(
            "target or historical repository changed during qualification")
    payload["source_repository_after"] = _source_evidence(source_after)
    payload["source_repository_unchanged"] = True
    payload["historical_repository_after"] = _source_evidence(historical_after)
    payload["historical_repository_unchanged"] = True
    payload["source_worktree_registry_unchanged"] = worktrees_unchanged
    _write_json(output / "qualification.json", payload)
    summary = _markdown(payload)
    try:
        with (output / "qualification.md").open(
                "x", encoding="utf-8", newline="\n") as handle:
            handle.write(summary)
    except FileExistsError as exc:
        raise QualificationError(
            "refusing to replace qualification.md") from exc
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Qualify exact historical release refs against a pinned target")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-repository")
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    args = parser.parse_args(argv)
    result = qualify_matrix(
        args.repository,
        args.matrix,
        args.output_dir,
        args.work_root,
        source_repository=args.source_repository,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({
        "verdict": result["verdict"],
        "qualification": str(Path(args.output_dir).resolve()
                             / "qualification.json"),
        "summary": str(Path(args.output_dir).resolve()
                       / "qualification.md"),
    }, sort_keys=True))
    return 0 if result["verdict"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
