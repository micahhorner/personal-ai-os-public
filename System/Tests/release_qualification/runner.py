"""Execution primitives for historical release qualification.

This module intentionally does not discover releases or construct instances.  A
caller supplies an already materialized instance and release, plus explicit
scratch and report directories.  The runner invokes only the release's public
CLI and records enough state to distinguish a completed upgrade, a safe
no-change failure, and a hybrid tree.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union


EVIDENCE_SCHEMA_VERSION = 1
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_VERSION_RE = re.compile(r"^\s*system_version:\s*[\"']?([^\"'\s#]+)", re.MULTILINE)
_COMMIT_REF_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class RunnerError(ValueError):
    """The requested qualification run is unsafe or cannot be constructed."""


PathValue = Union[os.PathLike, str]


def _resolved_dir(value: PathValue, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise RunnerError(f"{label} is not an existing directory: {path}")
    return path


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_separation(
    instance_dir: Path,
    release_dir: Path,
    scratch_dir: Path,
    report_dir: Path,
) -> None:
    if instance_dir == release_dir:
        raise RunnerError("instance_dir and release_dir must be different trees")
    if _is_within(instance_dir, release_dir) or _is_within(release_dir, instance_dir):
        raise RunnerError("instance_dir and release_dir must not contain one another")
    for label, path in (("scratch_dir", scratch_dir), ("report_dir", report_dir)):
        if _is_within(path, instance_dir):
            raise RunnerError(f"{label} must be outside instance_dir")


def _entry_record(path: Path) -> Dict[str, Any]:
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if path.is_symlink():
        return {
            "kind": "symlink",
            "mode": mode,
            "target": os.readlink(str(path)),
        }
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return {
            "kind": "file",
            "mode": mode,
            "size": info.st_size,
            "sha256": digest.hexdigest(),
        }
    if path.is_dir():
        return {"kind": "directory", "mode": mode}
    return {"kind": "other", "mode": mode}


def capture_tree(
    root: PathValue, *, normalize_directory_modes: bool = False
) -> Dict[str, Any]:
    """Return a deterministic, content-sensitive snapshot excluding ``.git``.

    Paths, entry kinds, permission bits, symlink targets, and file bytes affect
    the aggregate hash.  Timestamps and ownership do not.  Git's internal
    database is excluded because upgrade checkpointing may legitimately change
    it; the working-tree status is captured separately.
    """
    root_path = _resolved_dir(root, "tree root")
    entries: Dict[str, Dict[str, Any]] = {}

    def visit(directory: Path) -> None:
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            relative = child.relative_to(root_path).as_posix()
            if relative == ".git":
                continue
            record = _entry_record(child)
            if normalize_directory_modes and record["kind"] == "directory":
                record = {"kind": "directory"}
            entries[relative] = record
            if record["kind"] == "directory":
                visit(child)

    visit(root_path)
    aggregate = hashlib.sha256()
    for relative in sorted(entries):
        encoded = json.dumps(
            [relative, entries[relative]],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        aggregate.update(len(encoded).to_bytes(8, "big"))
        aggregate.update(encoded)
    return {
        "sha256": aggregate.hexdigest(),
        "entry_count": len(entries),
        "entries": entries,
    }


def capture_git_status(root: PathValue) -> Dict[str, Any]:
    """Capture Git status without changing refs, the index, or the worktree."""
    root_path = _resolved_dir(root, "git root")
    argv = [
        "git",
        "-C",
        str(root_path),
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ]
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return {
            "available": False,
            "returncode": None,
            "porcelain": None,
            "stderr": "git executable not found",
        }
    return {
        "available": result.returncode == 0,
        "returncode": result.returncode,
        "porcelain": result.stdout,
        "stderr": result.stderr,
    }


def _manifest_version(root: Path) -> Optional[str]:
    manifest = root / "SYSTEM-MANIFEST.yaml"
    try:
        text = manifest.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _changed_paths(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
) -> Dict[str, List[str]]:
    before_paths = set(before)
    after_paths = set(after)
    return {
        "added": sorted(after_paths - before_paths),
        "removed": sorted(before_paths - after_paths),
        "modified": sorted(
            path
            for path in before_paths & after_paths
            if before[path] != after[path]
        ),
    }


def _stop_process(process: subprocess.Popen[str]) -> Tuple[str, str]:
    """Terminate a timed-out process group and collect all available output."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        process.terminate()
    try:
        return process.communicate(timeout=2.0)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        return process.communicate()


def _invoke(
    argv: Sequence[str],
    cwd: Path,
    timeout_seconds: float,
    environment: Optional[Mapping[str, str]],
) -> Dict[str, Any]:
    if timeout_seconds <= 0:
        raise RunnerError("timeout_seconds must be greater than zero")
    env = os.environ.copy()
    if environment:
        env.update({str(key): str(value) for key, value in environment.items()})
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            list(argv),
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            start_new_session=(os.name == "posix"),
        )
    except OSError as exc:
        return {
            "returncode": None,
            "timed_out": False,
            "launch_error": f"{type(exc).__name__}: {exc}",
            "stdout": "",
            "stderr": "",
            "elapsed_seconds": time.monotonic() - started,
        }
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        timed_out = False
    except subprocess.TimeoutExpired:
        stdout, stderr = _stop_process(process)
        timed_out = True
    return {
        "returncode": process.returncode,
        "timed_out": timed_out,
        "launch_error": None,
        "stdout": stdout,
        "stderr": stderr,
        "elapsed_seconds": time.monotonic() - started,
    }


def _json_report(process: Mapping[str, Any], command: str,
                 *, require_ok: bool = True) -> Dict[str, Any]:
    if (process.get("timed_out") or process.get("launch_error")
            or (require_ok and process.get("returncode") != 0)):
        raise RunnerError(
            f"{command} JSON invocation did not complete successfully: "
            f"returncode={process.get('returncode')}; "
            f"stdout={str(process.get('stdout', ''))[:500]!r}; "
            f"stderr={str(process.get('stderr', ''))[:500]!r}")
    try:
        report = json.loads(str(process.get("stdout", "")))
    except (TypeError, ValueError) as exc:
        raise RunnerError(f"{command} did not emit one valid JSON report") from exc
    if (not isinstance(report, dict) or report.get("command") != command
            or (require_ok and report.get("ok") is not True)
            or not isinstance(report.get("info"), dict)):
        raise RunnerError(f"{command} JSON report is malformed or failed")
    return report


def _has_active_upgrade_transaction(instance: Path) -> bool:
    """Detect only a journal explicitly bound to this exact live tree."""
    prefix = f".{instance.name}.upgrade-transaction-"
    for path in instance.parent.iterdir():
        if not path.name.startswith(prefix) or not path.name.endswith(".json"):
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        live = value.get("live") if isinstance(value, dict) else None
        if (isinstance(live, str) and value.get("state") != "cleaned"
                and os.path.realpath(live) == os.path.realpath(instance)):
            return True
    return False


def _classify(
    process: Mapping[str, Any],
    before_hash: str,
    after_hash: str,
    target_version: Optional[str],
    final_version: Optional[str],
    mode: str,
) -> Tuple[str, str]:
    unchanged = before_hash == after_hash
    if mode == "dry-run" and not unchanged:
        return "hybrid", "dry-run changed the instance tree"
    if process.get("timed_out"):
        if unchanged:
            return "unchanged", "upgrade timed out without changing the instance tree"
        return "hybrid", "upgrade timed out after changing the instance tree"
    if process.get("launch_error"):
        return "unchanged", "upgrade process could not be launched"
    if mode == "dry-run":
        return "unchanged", "dry-run left the instance tree unchanged"
    if process.get("returncode") == 0 and target_version and final_version == target_version:
        return "complete", "upgrade exited zero and the instance reached the release version"
    if unchanged:
        return "unchanged", "upgrade did not complete and the instance tree is unchanged"
    return "hybrid", "upgrade did not prove completion and changed the instance tree"


def _phase_verdict(
    mode: str,
    process: Mapping[str, Any],
    classification: str,
) -> Dict[str, str]:
    if mode == "dry-run":
        if classification == "hybrid":
            return {
                "status": "unsafe",
                "code": "dry-run-mutated",
                "reason": "dry-run changed the instance tree",
            }
        if process.get("returncode") == 0 and not process.get("timed_out"):
            return {
                "status": "passed",
                "code": "dry-run-passed",
                "reason": "dry-run exited zero and left the instance tree unchanged",
            }
        return {
            "status": "failed",
            "code": "dry-run-failed",
            "reason": "dry-run did not complete successfully",
        }
    if classification == "complete":
        return {
            "status": "passed",
            "code": "apply-complete",
            "reason": "apply completed at the target release version",
        }
    if classification == "hybrid":
        return {
            "status": "unsafe",
            "code": "apply-hybrid",
            "reason": "apply changed the tree without proving completion",
        }
    return {
        "status": "failed",
        "code": "apply-failed-unchanged",
        "reason": "apply did not complete but left the instance tree unchanged",
    }


def _write_attempt(
    report_dir: Path,
    run_id: str,
    evidence: Dict[str, Any],
) -> Path:
    for attempt in range(1, 1_000_000):
        name = f"{run_id}.attempt-{attempt:04d}.json"
        destination = report_dir / name
        try:
            with destination.open("x", encoding="utf-8", newline="\n") as handle:
                evidence["attempt"] = attempt
                json.dump(evidence, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            return destination
        except FileExistsError:
            continue
    raise RunnerError(f"too many existing attempts for run_id {run_id!r}")


def run_upgrade(
    instance_dir: PathValue,
    release_dir: PathValue,
    scratch_dir: PathValue,
    report_dir: PathValue,
    *,
    run_id: str,
    timeout_seconds: float = 300.0,
    python_executable: PathValue = sys.executable,
    extra_args: Iterable[str] = (),
    environment: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Run one upgrade attempt and persist append-only JSON evidence.

    ``extra_args`` is appended as literal argv elements.  No shell is involved.
    Reusing ``run_id`` is supported: each call writes the next attempt number
    and never replaces earlier evidence.
    """
    if not _RUN_ID_RE.fullmatch(run_id):
        raise RunnerError(
            "run_id must be 1-128 characters using letters, digits, '.', '_' or '-'"
        )
    instance = _resolved_dir(instance_dir, "instance_dir")
    release = _resolved_dir(release_dir, "release_dir")
    scratch = _resolved_dir(scratch_dir, "scratch_dir")
    reports = _resolved_dir(report_dir, "report_dir")
    _validate_separation(instance, release, scratch, reports)

    aios = release / "System" / "Scripts" / "aios.py"
    if not aios.is_file():
        raise RunnerError(f"release CLI does not exist: {aios}")
    python_path = Path(python_executable).expanduser()
    argument_tail = tuple(str(value) for value in extra_args)
    mode = "dry-run" if "--dry-run" in argument_tail else "apply"
    base_argv = [
        str(python_path),
        str(aios),
        "upgrade",
        str(release),
        "--root",
        str(instance),
        *argument_tail,
        "--json",
    ]
    argv = list(base_argv)

    target_version = _manifest_version(release)
    before_version = _manifest_version(instance)
    before_tree = capture_tree(instance)
    before_git = capture_git_status(instance)
    review = None
    if mode == "apply":
        active_before = _has_active_upgrade_transaction(instance)
        review_process = _invoke(base_argv, scratch, timeout_seconds, environment)
        try:
            review_report = _json_report(review_process, "upgrade")
        except RunnerError:
            # Historical releases resumed an existing transaction immediately
            # instead of offering the newer read-only recovery review. Preserve
            # that failed/unsafe attempt as evidence; never treat a fresh-tree
            # review failure this way.
            mutated_during_review = (
                capture_tree(instance)["sha256"] != before_tree["sha256"])
            if not active_before and not mutated_during_review:
                raise
            process = review_process
            try:
                report = _json_report(process, "upgrade", require_ok=False)
            except RunnerError:
                report = None
            review = {"command": {"argv": base_argv, "shell": False},
                      "process": review_process, "report": report,
                      "active_transaction_legacy_resume": active_before,
                      "legacy_review_invocation_mutated": mutated_during_review}
            argv = list(base_argv)
            review_report = None
        if review_report is None:
            pass
        else:
            review_sha256 = review_report["info"].get("review_sha256")
            if not isinstance(review_sha256, str) or not _SHA256_RE.fullmatch(review_sha256):
                raise RunnerError("upgrade review omitted a valid review_sha256")
            argv = [*base_argv[:-1], "--apply", "--confirm", "--review-sha256",
                    review_sha256, "--json"]
            review = {"command": {"argv": base_argv, "shell": False},
                      "process": review_process, "report": review_report,
                      "review_sha256": review_sha256}
    if not (mode == "apply" and review is not None
            and (review.get("active_transaction_legacy_resume")
                 or review.get("legacy_review_invocation_mutated"))):
        process = _invoke(argv, scratch, timeout_seconds, environment)
        try:
            report = _json_report(process, "upgrade", require_ok=False)
        except RunnerError:
            report = None
    after_tree = capture_tree(instance)
    after_git = capture_git_status(instance)
    final_version = _manifest_version(instance)
    changed = _changed_paths(before_tree["entries"], after_tree["entries"])
    classification, reason = _classify(
        process,
        before_tree["sha256"],
        after_tree["sha256"],
        target_version,
        final_version,
        mode,
    )
    phase_verdict = _phase_verdict(mode, process, classification)

    evidence: Dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_id": run_id,
        "attempt": None,
        "paths": {
            "instance_dir": str(instance),
            "release_dir": str(release),
            "scratch_dir": str(scratch),
            "report_dir": str(reports),
        },
        "command": {"argv": argv, "shell": False},
        "mode": mode,
        "phase_verdict": phase_verdict,
        "process": process,
        "report": report,
        "review": review,
        "versions": {
            "before": before_version,
            "target": target_version,
            "after": final_version,
        },
        "tree": {
            "before": before_tree,
            "after": after_tree,
            "changes": changed,
        },
        "git": {"before": before_git, "after": after_git},
        "classification": classification,
        "classification_reason": reason,
    }
    evidence_path = _write_attempt(reports, run_id, evidence)
    evidence["evidence_path"] = str(evidence_path)
    return evidence


def run_rollback(
    instance_dir: PathValue,
    release_dir: PathValue,
    scratch_dir: PathValue,
    report_dir: PathValue,
    *,
    run_id: str,
    rollback_ref: str,
    expected_pre_apply_tree_hash: str,
    expected_tracked_sha256: str,
    normalize_directory_modes: bool = False,
    timeout_seconds: float = 300.0,
    python_executable: PathValue = sys.executable,
    environment: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Run an explicit Git rollback and prove its resulting tree hash.

    This primitive deliberately accepts only a hexadecimal commit identity.
    It does not parse upgrade display text and it does not automate the
    product's manual ZIP recovery path.
    """
    if not _RUN_ID_RE.fullmatch(run_id):
        raise RunnerError(
            "run_id must be 1-128 characters using letters, digits, '.', '_' or '-'"
        )
    ref = str(rollback_ref).strip()
    if not ref:
        raise RunnerError("rollback_ref must not be empty")
    if ref.lower().endswith(".zip") or Path(ref).expanduser().is_file():
        raise RunnerError("ZIP/manual rollback targets are not supported")
    if not _COMMIT_REF_RE.fullmatch(ref):
        raise RunnerError(
            "rollback_ref must be an explicit 7-64 character hexadecimal commit ref"
        )
    expected_hash = str(expected_pre_apply_tree_hash).lower()
    if not _SHA256_RE.fullmatch(expected_hash):
        raise RunnerError("expected_pre_apply_tree_hash must be a SHA-256 hex digest")
    tracked_hash = str(expected_tracked_sha256).lower()
    if not _SHA256_RE.fullmatch(tracked_hash):
        raise RunnerError("expected_tracked_sha256 must be a SHA-256 hex digest")

    instance = _resolved_dir(instance_dir, "instance_dir")
    release = _resolved_dir(release_dir, "release_dir")
    scratch = _resolved_dir(scratch_dir, "scratch_dir")
    reports = _resolved_dir(report_dir, "report_dir")
    _validate_separation(instance, release, scratch, reports)
    aios = release / "System" / "Scripts" / "aios.py"
    if not aios.is_file():
        raise RunnerError(f"release CLI does not exist: {aios}")

    argv = [
        str(Path(python_executable).expanduser()),
        str(aios),
        "rollback",
        ref,
        "--expected-sha256",
        tracked_hash,
        "--confirm",
        "--clean",
        "--root",
        str(instance),
    ]
    before_version = _manifest_version(instance)
    before_tree = capture_tree(
        instance, normalize_directory_modes=normalize_directory_modes
    )
    before_git = capture_git_status(instance)
    process = _invoke(argv, scratch, timeout_seconds, environment)
    after_tree = capture_tree(
        instance, normalize_directory_modes=normalize_directory_modes
    )
    after_git = capture_git_status(instance)
    final_version = _manifest_version(instance)
    changed = _changed_paths(before_tree["entries"], after_tree["entries"])
    exact_tree = after_tree["sha256"].lower() == expected_hash
    process_ok = (
        process.get("returncode") == 0
        and not process.get("timed_out")
        and not process.get("launch_error")
    )
    if exact_tree and process_ok:
        classification = "exact-restoration"
        verdict = {
            "status": "passed",
            "code": "rollback-exact",
            "reason": "rollback exited zero and restored the expected pre-apply tree hash",
        }
    elif not exact_tree:
        classification = "restoration-mismatch"
        verdict = {
            "status": "unsafe",
            "code": "rollback-mismatch",
            "reason": "rollback did not restore the expected pre-apply tree hash",
        }
    else:
        classification = "rollback-failed"
        verdict = {
            "status": "failed",
            "code": "rollback-process-failed",
            "reason": "tree matches the expected hash but rollback did not exit successfully",
        }

    evidence: Dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_id": run_id,
        "attempt": None,
        "paths": {
            "instance_dir": str(instance),
            "release_dir": str(release),
            "scratch_dir": str(scratch),
            "report_dir": str(reports),
        },
        "command": {"argv": argv, "shell": False},
        "mode": "rollback",
        "phase_verdict": verdict,
        "process": process,
        "versions": {"before": before_version, "after": final_version},
        "tree": {
            "expected_pre_apply_sha256": expected_hash,
            "exact_restoration": exact_tree,
            "before": before_tree,
            "after": after_tree,
            "changes": changed,
        },
        "git": {"before": before_git, "after": after_git},
        "rollback_ref": ref,
        "expected_tracked_sha256": tracked_hash,
        "directory_mode_policy": (
            "normalized-git-restorable"
            if normalize_directory_modes else "physical"
        ),
        "classification": classification,
    }
    evidence_path = _write_attempt(reports, run_id, evidence)
    evidence["evidence_path"] = str(evidence_path)
    return evidence
