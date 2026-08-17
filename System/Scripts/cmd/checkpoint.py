"""vault.checkpoint / vault.rollback — git commit when available, zip snapshot otherwise (DEC-011).

CONCURRENCY (v1.49.0). `checkpoint` used to run a bare `git add -A`: it committed
whatever was in the tree, under whatever label the caller passed, and reported only
the resulting ref. With three sessions sharing one working tree that swept other
agents' in-flight files into unrelated commits, and it made a record written as
"nothing committed, that stays his call" false twenty-seven seconds after it was
written — the commit said nothing about what it actually contained.

Three properties are now guaranteed, in this order of importance:

1. **You can always save state.** Checkpoint is the safety net and is deliberately
   exempt from the kill switch. The default therefore still commits everything;
   nothing here can refuse to save your work unless you explicitly ask it to.
2. **A checkpoint is never a misleading record.** The commit message enumerates
   every path the commit contains, and the report returns the same list in
   `committed_paths`. Sweeping is still possible; sweeping *silently* is not.
3. **A caller who knows its scope can declare it.** `--paths A B` stages only those
   and reports everything else as `left_uncommitted`, untouched.

`--strict` is the refuse-and-explain mode for automation that must not touch a tree
it does not own. It is opt-in, never the default, precisely because of (1).
"""
from __future__ import annotations
import os, shlex, subprocess, sys, time, shutil
from lib import recovery, snapshot
from lib.report import Report


def _porcelain(root: str) -> list[str]:
    r = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def _path_of(line: str) -> str:
    """Path out of a porcelain line, un-quoting and taking the destination of a rename."""
    p = line[3:]
    if " -> " in p:
        p = p.split(" -> ", 1)[1]
    p = p.strip()
    if p.startswith('"') and p.endswith('"'):
        p = p[1:-1].encode().decode("unicode_escape")
    return p


def _changed_paths(root: str) -> list[str]:
    """Every path git would include in `add -A`: modified, staged, and untracked."""
    return sorted({_path_of(l) for l in _porcelain(root)})


def _staged_paths(root: str, scope: list[str] | None = None) -> list[str]:
    argv = ["git", "diff", "--cached", "--name-only"]
    if scope:
        argv += ["--"] + scope
    r = subprocess.run(argv, cwd=root,
                       capture_output=True, text=True)
    return sorted({p for p in r.stdout.splitlines() if p.strip()})


def _outside_scope(changed: list[str], scope: list[str]) -> list[str]:
    """Changed paths not covered by any declared scope entry (file or directory)."""
    norm = [s.rstrip("/") for s in scope]
    out = []
    for p in changed:
        if not any(p == s or p.startswith(s + "/") for s in norm):
            out.append(p)
    return out

def snapshot_dir(root: str) -> str:
    d = os.path.join(os.path.dirname(root), os.path.basename(root) + "-Snapshots")
    os.makedirs(d, exist_ok=True)
    return d

def has_git(root: str) -> bool:
    if not shutil.which("git"):
        return False
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return False
    return os.path.realpath(r.stdout.strip()) == os.path.realpath(root)


def _git_target(root: str) -> str | None:
    """Return the immutable full commit id at HEAD, verified as a commit."""
    r = subprocess.run(["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=root,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _rollback_fields(root: str, target: str, expected_sha256: str,
                     *, clean: bool, scope_paths: list[str] | None = None) -> dict:
    """Structured exact rollback invocation plus its argv-safe rendering."""
    argv = [
        sys.executable,
        os.path.join(root, "System", "Scripts", "aios.py"),
        "rollback",
        target,
        "--expected-sha256",
        expected_sha256,
        "--confirm",
    ]
    if clean:
        argv.append("--clean")
    if scope_paths:
        argv += ["--paths"] + scope_paths
    argv += ["--root", root]
    return {
        "target": target,
        "expected_sha256": expected_sha256,
        "exact": True,
        "cleanup": (
            "remove-post-checkpoint-paths-within-declared-scope"
            if scope_paths else
            "remove-post-checkpoint-untracked-while-preserving-ignored-runtime-state"
            if clean else "whole-tree-snapshot-swap"
        ),
        "scope_paths": list(scope_paths or []),
        "argv": argv,
        "command": shlex.join(argv),
    }


def _record_git_identity(root: str, rep: Report, target: str,
                         scope: dict, display: str, *, whole_tree_exact: bool) -> None:
    # Compatibility: pack recovery recognizes the `git <ref>` form. The exact
    # machine target lives separately and is always the verified full commit id.
    rep.info["checkpoint"] = f"git {target}"
    rep.info["checkpoint_display"] = display
    requested_scope = list(scope.get("requested_paths") or [])
    proof = recovery.inspect_commit(
        root, target, scope_paths=requested_scope if not whole_tree_exact else None
    )
    rep.info["checkpoint_identity"] = {
        "kind": "git-commit",
        "target": target,
        "tracked_sha256": proof["tracked_sha256"],
        "git_tree": proof["git_tree"],
        "scope": scope,
        "coverage": "whole-tree" if whole_tree_exact else "declared-paths-only",
        "exact_recovery": True,
    }
    if not whole_tree_exact:
        rep.info["checkpoint_identity"]["scope_sha256"] = proof["tracked_sha256"]
    rollback = _rollback_fields(
        root,
        target,
        proof["tracked_sha256"],
        clean=True,
        scope_paths=None if whole_tree_exact else requested_scope,
    )
    rep.info["rollback"] = rollback
    rep.info["rollback_command"] = rollback["command"]
    if not whole_tree_exact:
        rep.info["recovery_limit"] = (
            "The exact command restores only the declared checkpoint scope and "
            "leaves out-of-scope tracked, staged, untracked, and ignored work untouched"
        )


def _snapshot_identity(created: dict) -> dict:
    return {
        "kind": "zip-snapshot",
        "target": created["path"],
        "sha256": created["sha256"],
        "tree_sha256": created["manifest"]["tree_sha256"],
        "scope": {"mode": "whole-tree", "paths": []},
        "coverage": "whole-tree",
        "exact_recovery": True,
    }


def _record_snapshot_identity(root: str, rep: Report, created: dict) -> None:
    identity = _snapshot_identity(created)
    dest = identity["target"]
    rep.info["checkpoint"] = dest
    rep.info["checkpoint_display"] = f"snapshot {os.path.basename(dest)}"
    rep.info["checkpoint_identity"] = identity
    rollback = _rollback_fields(
        root, dest, identity["sha256"], clean=False
    )
    rep.info["rollback"] = rollback
    rep.info["rollback_command"] = rollback["command"]


def _zip_snapshot(root: str, label: str) -> dict:
    """Write a validated exact snapshot of the working tree as it stands."""
    stem = (time.strftime("%Y-%m-%d-%H%M%S") + "-"
            + "".join(c if c.isalnum() else "-" for c in label)[:40])
    # Snapshot publication itself is exclusive/no-clobber.  If two valid
    # checkpoints share the same second and label, retry with a deterministic
    # suffix; never replace or reuse the older archive.
    for attempt in range(1, 10001):
        suffix = "" if attempt == 1 else f"-{attempt}"
        dest = os.path.join(snapshot_dir(root), stem + suffix + ".zip")
        try:
            return snapshot.create_snapshot(root, dest)
        except snapshot.SnapshotError as exc:
            if "archive already exists" in str(exc) and os.path.lexists(dest):
                continue
            raise
    raise snapshot.SnapshotError(
        "could not allocate a collision-free snapshot archive name")


def _system_version(path: str) -> str | None:
    try:
        import yaml
        with open(os.path.join(path, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return str(data["system"]["system_version"])
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        return None


def _validate_restored_state(path: str, args, invoking_version: str | None) -> dict:
    """Run trusted current validation, advisory-only across version boundaries.

    Exact commit/archive identity is the recovery gate. A newer validator may
    legitimately reject an older release, so version-skew findings are recorded
    without undoing authenticated restoration. Restored code is never executed.
    """
    from cmd import validate as v_mod
    vrep = Report("validate")
    try:
        v_mod.run(path, args, vrep)
    except Exception as exc:
        vrep.error(f"validation raised {type(exc).__name__}: {exc}")
    restored_version = _system_version(path)
    version_skew = bool(
        invoking_version and restored_version and invoking_version != restored_version
    )
    return {
        "performed": True,
        "passed": True if version_skew else vrep.ok,
        "errors": [] if version_skew else vrep.errors,
        "warnings": vrep.warnings,
        "validator": "trusted-invoking-runtime",
        "invoking_version": invoking_version,
        "restored_version": restored_version,
        "version_skew": version_skew,
        "advisory_passed": vrep.ok,
        "advisory_errors": vrep.errors if version_skew else [],
    }

def run(root, args, rep: Report):
    label = getattr(args, "message", None) or "checkpoint"
    if getattr(args, "rollback", None):
        target = args.rollback
        invoking_version = _system_version(root)
        if not getattr(args, "confirm", False):
            rep.error("rollback is destructive; re-run with --confirm "
                      "(or restore by hand: see Maintenance and Recovery Guide)")
            return rep
        expected = getattr(args, "expected_sha256", None)
        is_snapshot = target.endswith(".zip") or not has_git(root)
        if is_snapshot:
            if not expected:
                rep.error(
                    "snapshot rollback needs --expected-sha256 from the checkpoint "
                    "identity; refusing an unauthenticated archive"
                )
                return rep
            try:
                # The live directory is about to be renamed. Keep the process
                # outside it so cwd does not pin or follow the preserved old tree.
                os.chdir(os.path.dirname(os.path.realpath(root)))
                evidence = snapshot.restore_snapshot(
                    root, {"path": target, "sha256": expected}
                )
            except snapshot.SnapshotError as exc:
                rep.error(f"snapshot rollback refused: {exc}")
                return rep
            evidence["validation"] = _validate_restored_state(
                root, args, invoking_version
            )
            if not evidence["validation"]["passed"]:
                previous = evidence.get("previous_tree")
                if previous:
                    try:
                        evidence["semantic_revert"] = snapshot.revert_restoration(
                            root, previous
                        )
                    except snapshot.SnapshotError as exc:
                        rep.info["recovery"] = evidence
                        rep.error(
                            "restored snapshot failed validation and automatic "
                            f"reversion also failed: {exc}"
                        )
                        return rep
                rep.info["recovery"] = evidence
                rep.error(
                    "restored snapshot failed validation; the pre-restore live "
                    "tree was put back"
                )
                return rep
            rep.info["rolled_back_to"] = target
            rep.info["recovery"] = evidence
            rep.info["exact_restoration"] = True
            if evidence.get("previous_tree"):
                rep.warn(
                    "the pre-restore live tree was preserved at "
                    f"{evidence['previous_tree']}"
                )
            return rep

        try:
            proof = recovery.inspect_commit(root, target)
            if expected is None:
                # Backward-compatible manual use remains available, but generated
                # checkpoint commands always carry the independently recorded hash.
                expected = proof["tracked_sha256"]
                rep.warn(
                    "--expected-sha256 was omitted; using the validated commit's "
                    "tracked hash. Prefer the exact command printed by checkpoint."
                )

            def validate_restored(path):
                return _validate_restored_state(
                    str(path), args, invoking_version
                )

            evidence = recovery.restore_commit(
                root,
                target,
                expected_tracked_sha256=expected,
                clean=bool(getattr(args, "clean", False)),
                validator=validate_restored,
                scope_paths=getattr(args, "paths", None),
            )
        except recovery.RecoveryError as exc:
            if exc.evidence:
                rep.info["recovery"] = exc.evidence
            rep.error(f"git rollback refused: {exc}")
            return rep
        rep.info["rolled_back_to"] = evidence["commit"]
        rep.info["recovery"] = evidence
        rep.info["exact_restoration"] = evidence["exact_restoration"]
        rep.info["post_rollback_validate"] = (
            "OK" if evidence["validation"]["passed"] else "FAILED"
        )
        if evidence.get("snapshot"):
            rep.warn(
                "pre-restore working bytes were preserved at "
                f"{evidence['snapshot']}"
            )
        return rep
    if getattr(args, "zip_only", False):
        # A pure snapshot that never touches git. Exists because `--zip` also
        # COMMITS when git is present — on a tree carrying unready work that was
        # a trap (hit while executing DEC-064's own rollback plan).
        created = _zip_snapshot(root, label)
        rep.info["snapshot"] = created["path"]
        _record_snapshot_identity(root, rep, created)
        return rep
    if has_git(root):
        changed = _changed_paths(root)
        scope = [p for p in (getattr(args, "paths", None) or []) if p]
        outside = _outside_scope(changed, scope) if scope else changed

        # STRICT is refuse-and-explain, and it is OPT-IN on purpose. Checkpoint is
        # the estate's safety net and is deliberately kill-switch-exempt: "you can
        # always save state" (H-07) is a guarantee, and a gate that can refuse to
        # save is not a safety net. So the concurrency hazard is closed by
        # DISCLOSURE by default and by REFUSAL only when the caller asks for it.
        if getattr(args, "strict", False) and outside:
            rep.error(
                f"--strict: {len(outside)} change(s) outside the declared scope: "
                f"{outside[:10]}{' …' if len(outside) > 10 else ''} — on a shared tree "
                f"these may be another session's work. Declare them with `--paths`, "
                f"snapshot without committing with `--zip-only`, or re-run without "
                f"`--strict` to commit everything (the full list is recorded in the "
                f"commit message either way).")
            return rep

        if scope:
            # Commit ONLY what the caller declared. Anything else is left exactly
            # where it was and named in the report — the whole point on a tree that
            # three sessions share.
            subprocess.run(["git", "add", "--"] + scope, cwd=root, capture_output=True)
            committed = _staged_paths(root, scope)
            if outside:
                rep.info["left_uncommitted"] = outside
                rep.warn(f"{len(outside)} change(s) outside `--paths` were left uncommitted: "
                         f"{outside[:10]}{' …' if len(outside) > 10 else ''}")
        else:
            subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True)
            committed = _staged_paths(root)

        # A clean Git tree is already checkpointed. Its identity is HEAD's full,
        # immutable commit id — never display prose such as "nothing to commit".
        if not committed:
            target = _git_target(root)
            if not target:
                rep.error("Git checkpoint has no commit identity: HEAD does not resolve "
                          "to a commit; create an initial commit or use --zip-only")
                return rep
            scope_mode = "declared-paths-no-changes" if scope else "clean-head"
            display = (f"declared scope unchanged at git {target[:12]}"
                       if scope else f"clean working tree at git {target[:12]}")
            _record_git_identity(
                root, rep, target,
                {"mode": scope_mode, "requested_paths": scope, "committed_paths": []},
                display,
                whole_tree_exact=not scope,
            )
            if getattr(args, "force_zip", False):
                created = _zip_snapshot(root, label)
                rep.info["snapshot"] = created["path"]
                rep.info["snapshot_identity"] = _snapshot_identity(created)
            return rep

        # The commit message ENUMERATES what it contains. A checkpoint's record can
        # then never be misleading about someone else's work: before this, `git add
        # -A` under a label like "nothing committed, that stays his call" swept three
        # sessions' files into one commit and the message said none of it.
        msg = f"checkpoint: {label}"
        if committed:
            listed = committed[:50]
            msg += ("\n\n" + f"Contains {len(committed)} path(s)"
                    + (" (scope declared with --paths)" if scope else
                       " — the whole working tree, undeclared")
                    + ":\n" + "\n".join("  " + p for p in listed)
                    + (f"\n  … and {len(committed) - len(listed)} more"
                       if len(committed) > len(listed) else ""))
        commit_argv = ["git", "commit", "-m", msg]
        if scope:
            # Path-limit the commit itself. `git add -- <scope>` alone is not
            # sufficient: an unrelated path staged before this command would
            # otherwise be swept into the commit while the report claimed scope.
            commit_argv += ["--"] + scope
        r = subprocess.run(commit_argv, cwd=root,
                           capture_output=True, text=True)
        if r.returncode == 0:
            target = _git_target(root)
            if not target:
                rep.error("git commit succeeded but its full immutable identity could not "
                          "be verified")
                return rep
            _record_git_identity(
                root, rep, target,
                {
                    "mode": "declared-paths" if scope else "whole-tree",
                    "requested_paths": scope,
                    "committed_paths": committed,
                },
                f"git {target[:12]} ({len(committed)} path(s))",
                whole_tree_exact=not scope,
            )
            rep.info["committed_paths"] = committed
        elif "nothing to commit" in r.stdout + r.stderr:
            target = _git_target(root)
            if not target:
                rep.error("Git reported a clean tree but HEAD has no commit identity")
                return rep
            scope_mode = "declared-paths-no-changes" if scope else "clean-head"
            display = (f"declared scope unchanged at git {target[:12]}"
                       if scope else f"clean working tree at git {target[:12]}")
            _record_git_identity(
                root, rep, target,
                {"mode": scope_mode, "requested_paths": scope, "committed_paths": []},
                display,
                whole_tree_exact=not scope,
            )
        else:
            rep.error(f"git commit failed: {r.stderr.strip()}")
    # a human-restorable zip is written when git is absent, or on request
    # (--zip): git alone leaves a nontechnical user with no snapshot they can
    # restore without tools (release-audit H-07)
    if ((not has_git(root) or getattr(args, "force_zip", False))
            and "snapshot" not in rep.info):
        created = _zip_snapshot(root, label)
        rep.info["snapshot"] = created["path"]
        # When --zip accompanies a Git checkpoint, the Git commit remains the
        # primary machine target; the snapshot carries its own explicit identity.
        if "checkpoint_identity" not in rep.info:
            _record_snapshot_identity(root, rep, created)
        else:
            rep.info["snapshot_identity"] = _snapshot_identity(created)
    return rep
