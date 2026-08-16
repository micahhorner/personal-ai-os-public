"""vault.migrate — strict, ordered, checkpointed version-target migrations."""
from __future__ import annotations

import os
import re
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from cmd import validate as validate_mod
from lib.frontmatter import iter_markdown
from lib import recovery, snapshot, upgrade_candidate as upgrade_candidate_mod
from lib.migrations import (
    MigrationError,
    append_change_journal,
    append_ledger,
    compute_source_identity,
    discover,
    ledger_record,
    load_ledger,
    load_unique_yaml_file,
    preflight_sequence,
)
from lib.report import Report
from lib.vaultpaths import ai_writes_enabled

try:  # Python 3.11+
    import tomllib as _toml
except ImportError:  # Python 3.9/3.10: use an available standards-compliant parser.
    try:
        import tomli as _toml
    except ImportError:
        try:  # Test/bootstrap environments commonly expose pip's vendored copy.
            import pip._vendor.tomli as _toml
        except ImportError:
            _toml = None


def _manifest_version(root: str, version_target: str) -> str:
    path = Path(root) / "SYSTEM-MANIFEST.yaml"
    try:
        data = load_unique_yaml_file(path, "SYSTEM-MANIFEST.yaml")
        value = data["system"][version_target]
    except (MigrationError, KeyError, TypeError) as exc:
        raise MigrationError(f"cannot read system.{version_target}: {exc}") from exc
    return str(value)


def _manifest_distribution(root: str) -> str:
    path = Path(root) / "SYSTEM-MANIFEST.yaml"
    try:
        data = load_unique_yaml_file(path, "SYSTEM-MANIFEST.yaml")
        value = data["system"]["distribution_id"]
    except (MigrationError, KeyError, TypeError) as exc:
        raise MigrationError(
            "live source distribution cannot be verified; "
            "system.distribution_id is required"
        ) from exc
    if not isinstance(value, str) or not value:
        raise MigrationError(
            "live source distribution cannot be verified; "
            "system.distribution_id is required"
        )
    return value


def _replace_file(path: Path, text: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise MigrationError(f"refusing to replace non-regular file: {path}")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _set_manifest_version(
    root: str, version_target: str, expected: str, target: str
) -> None:
    path = Path(root) / "SYSTEM-MANIFEST.yaml"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^(\s+{re.escape(version_target)}:\s*)(['\"]?)"
        + re.escape(expected)
        + r"\2(\s*(?:#.*)?)$",
        re.MULTILINE,
    )
    changed, count = pattern.subn(rf"\g<1>{target}\g<3>", text, count=1)
    if count != 1:
        raise MigrationError(
            f"{version_target} changed after preflight; refusing to continue"
        )
    _replace_file(path, changed)


def _audit_system_version_mirrors(root: str, expected: str) -> None:
    manifest = _manifest_version(root, "system_version")
    try:
        baseline = json.loads(
            (Path(root) / "System/.baseline-manifest.json").read_text(encoding="utf-8"),
            object_pairs_hook=lambda pairs: _unique_json_pairs(pairs),
        )
        pyproject_bytes = (Path(root) / "pyproject.toml").read_bytes()
    except (OSError, UnicodeError, json.JSONDecodeError, MigrationError) as exc:
        raise MigrationError(f"system version mirror audit cannot read mirrors: {exc}") from exc
    if _toml is None:
        raise MigrationError("strict TOML parser is unavailable")
    try:
        pyproject = _toml.loads(pyproject_bytes.decode("utf-8"))
    except Exception as exc:
        # All supported TOML parsers raise a parser-specific ValueError subclass.
        raise MigrationError(f"pyproject.toml is invalid TOML: {exc}") from exc

    def version_values(value):
        found = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "version":
                    found.append(child)
                found.extend(version_values(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(version_values(child))
        return found

    versions = version_values(pyproject)
    project = pyproject.get("project") if isinstance(pyproject, dict) else None
    if (
        not isinstance(project, dict)
        or not isinstance(project.get("version"), str)
        or len(versions) != 1
    ):
        raise MigrationError(
            "pyproject.toml must contain exactly one version key: [project].version"
        )
    mirrors = {
        "SYSTEM-MANIFEST.yaml": manifest,
        "System/.baseline-manifest.json": baseline.get("system_version")
        if isinstance(baseline, dict) else None,
        "pyproject.toml": project["version"],
    }
    wrong = {name: value for name, value in mirrors.items() if value != expected}
    if wrong:
        raise MigrationError(f"system_version mirrors are not all {expected}: {wrong}")


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MigrationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _selected_notes(root: str, selector: dict):
    prefix = selector.get("path_prefix")
    prefix_path = Path(prefix) if prefix else None
    selected = []
    for note in iter_markdown(root):
        if prefix_path is not None:
            try:
                Path(note.relpath).relative_to(prefix_path)
            except ValueError:
                continue
        if note.error:
            raise MigrationError(
                f"{note.relpath}: selected content has invalid frontmatter: {note.error}"
            )
        if not note.meta:
            continue
        if selector.get("type") and note.meta.get("type") != selector["type"]:
            continue
        selected.append(note)
    return selected


def _confined_regular(path: Path, base: Path, label: str) -> bytes:
    base = base.resolve(strict=True)
    try:
        relative = path.relative_to(base)
    except ValueError as exc:
        raise MigrationError(f"{label} escapes its allowed root") from exc
    current = base
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink() or not current.is_dir():
            raise MigrationError(f"{label} has an unsafe ancestor")
    if path.is_symlink() or not path.is_file():
        raise MigrationError(f"{label} must be a regular non-symlink file")
    return path.read_bytes()


def _exact_file_plan(root: str, manifest):
    vault = Path(root).resolve(strict=True)
    migration_dir = manifest.directory.resolve(strict=True)
    plan = []
    for entry in manifest.data["transform"]["replace_exact_files"]:
        destination = vault / entry["path"]
        parent = destination.parent
        try:
            parent.relative_to(vault)
        except ValueError as exc:
            raise MigrationError("exact-file destination escapes vault") from exc
        current = vault
        for part in Path(entry["path"]).parts[:-1]:
            current = current / part
            if current.is_symlink() or not current.is_dir():
                raise MigrationError(f"{entry['path']}: unsafe or missing ancestor")
        if destination.is_symlink():
            raise MigrationError(f"{entry['path']}: destination is a symlink")
        exists = destination.exists()
        if exists and not destination.is_file():
            raise MigrationError(f"{entry['path']}: destination is not a regular file")
        old = destination.read_bytes() if exists else None
        actual_old = hashlib.sha256(old).hexdigest() if old is not None else "absent"
        accepted_old = entry["old_sha256"]
        if not isinstance(accepted_old, list):
            accepted_old = [accepted_old]
        if actual_old not in accepted_old:
            raise MigrationError(f"{entry['path']}: old_sha256 precondition mismatch")
        payload_path = migration_dir / entry["payload"]
        payload = _confined_regular(payload_path, migration_dir, "migration payload")
        if hashlib.sha256(payload).hexdigest() != entry["new_sha256"]:
            raise MigrationError(f"{entry['payload']}: new_sha256 payload mismatch")
        mode = (
            int(entry["mode"], 8)
            if old is None
            else destination.stat().st_mode & 0o777
        )
        # An accepted postcondition hash is useful migration evidence even when
        # the destination already contains the exact payload.  Verify it, but
        # do not churn metadata or physically rewrite identical bytes.
        needs_write = old != payload
        plan.append((
            entry["path"], destination, payload, mode, needs_write, actual_old,
        ))
    return plan


def exact_transform_contract(root: str, manifest) -> list[dict[str, object]]:
    """Prove transform preconditions and return the exact integrity contract.

    Upgrade planning uses this read-only boundary before it creates a
    checkpoint.  The private execution plan carries paths and bytes; callers
    receive only manifest-bound relative paths and before/after hashes.
    """
    plan = _exact_file_plan(root, manifest)
    entries = manifest.data["transform"]["replace_exact_files"]
    return [
        {
            "path": relative,
            "accepted_old_sha256": (
                list(entry["old_sha256"])
                if isinstance(entry["old_sha256"], list)
                else [entry["old_sha256"]]
            ),
            "matched_old_sha256": actual_old,
            "new_sha256": entry["new_sha256"],
            "needs_write": needs_write,
        }
        for entry, (
            relative, _destination, _payload, _mode, needs_write, actual_old,
        )
        in zip(entries, plan)
    ]


def _replace_bytes(path: Path, payload: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _replace_exact_files(root: str, manifest, *, apply: bool):
    plan = _exact_file_plan(root, manifest)
    if apply:
        # Re-plan immediately after checkpoint so every old-state and payload
        # hash is reverified at the mutation boundary.
        plan = _exact_file_plan(root, manifest)
        for _, destination, payload, mode, needs_write, _actual_old in plan:
            if needs_write:
                _replace_bytes(destination, payload, mode)
    return [relative for relative, _, _, _, _, _ in plan]


def _verify_transform_postconditions(root: str, manifest) -> None:
    transform = manifest.data["transform"]
    vault = Path(root).resolve(strict=True)
    migration_dir = manifest.directory.resolve(strict=True)
    for entry in transform["replace_exact_files"]:
        destination = vault / entry["path"]
        payload = _confined_regular(
            migration_dir / entry["payload"], migration_dir, "migration payload"
        )
        if hashlib.sha256(payload).hexdigest() != entry["new_sha256"]:
            raise MigrationError(f"{entry['payload']}: payload changed after apply")
        actual = _confined_regular(destination, vault, "exact-file destination")
        if hashlib.sha256(actual).hexdigest() != entry["new_sha256"]:
            raise MigrationError(f"{entry['path']}: applied exact-file hash is wrong")


def _transform(root: str, manifest, *, apply: bool) -> dict:
    files = _replace_exact_files(root, manifest, apply=apply)
    return {"affected_files": len(files), "sample": files[:20]}


def _validation(root: str, args, manifest) -> tuple[bool, list[str]]:
    errors = []
    for check in manifest.data["validation"]:
        if check["check"] == "vault-validate":
            report = Report("validate")
            try:
                validate_mod.run(root, args, report)
            except Exception as exc:  # validation exceptions are failures, never escapes
                report.error(f"validation raised {type(exc).__name__}: {exc}")
            errors.extend(report.errors)
            continue
        notes = _selected_notes(root, manifest.data["content_selector"])
        field = check["field"]
        if check["check"] == "field-absent":
            failures = [note.relpath for note in notes if field in note.meta]
        else:
            failures = [note.relpath for note in notes if field not in note.meta]
        if failures:
            errors.append(
                f"{check['check']} {field!r} failed for {len(failures)} file(s): "
                f"{failures[:10]}"
            )
    return not errors, errors


def _append_change_journal(root: str, manifest, checkpoint: dict) -> None:
    append_change_journal(
        root,
        f"- migrate · {manifest.id} · {manifest.from_version} → "
        f"{manifest.to_version} · checkpoint {checkpoint['target']}",
    )


def _verify_outer_checkpoint(live_root: str, identity: dict) -> None:
    try:
        if identity["kind"] == "git-commit":
            proof = recovery.inspect_commit(live_root, identity["target"])
            if (
                proof["tracked_sha256"] != identity["tracked_sha256"]
                or proof["git_tree"] != identity["git_tree"]
                or proof["commit"] != identity["target"]
            ):
                raise MigrationError("outer Git checkpoint proof does not match")
        else:
            evidence = snapshot.validate_snapshot(
                {"path": identity["target"], "sha256": identity["sha256"]}
            )
            if evidence["manifest"]["tree_sha256"] != identity["tree_sha256"]:
                raise MigrationError("outer snapshot checkpoint tree hash does not match")
    except (
        KeyError, recovery.RecoveryError, snapshot.SnapshotError, OSError
    ) as exc:
        raise MigrationError(f"outer checkpoint cannot be materially verified: {exc}") from exc


def run(root, args, rep: Report):
    if not ai_writes_enabled(root):
        rep.error("kill switch is off — refusing to write")
        return rep
    migrations_dir = Path(root) / "System/Migrations"
    target = getattr(args, "migration", None)
    try:
        available = discover(migrations_dir)
        if not target:
            rep.info["available"] = [item.directory.name for item in available] or "none"
            rep.info["usage"] = (
                "aios migrate --migration <NNN-name> [--apply] (default is dry-run)"
            )
            return rep
        if not re.fullmatch(
            r"[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*", target
        ):
            raise MigrationError("migration target must be an exact NNN-kebab-case name")
        if target.startswith("000-"):
            raise MigrationError("000-example is documentation, not an executable migration")
        by_directory = {item.directory.name: item for item in available}
        manifest = by_directory.get(target)
        if manifest is None:
            raise MigrationError(f"migration is not in the discovered set: {target}")
        if manifest.version_target == "system_version" and not getattr(
            args, "_candidate_system_migration", False
        ):
            raise MigrationError(
                "system_version migrations are candidate-only and cannot be applied "
                "by standalone aios migrate"
            )
        if getattr(args, "_isolated_candidate_migration", False):
            authorized_live = getattr(args, "_authorized_live_root", None)
            outer_identity = getattr(args, "_outer_checkpoint_identity", None)
            if not isinstance(authorized_live, str):
                raise MigrationError("candidate migration lacks authorized live root")
            ledger_record(manifest, outer_identity, "applied")
            _verify_outer_checkpoint(authorized_live, outer_identity)
        if getattr(args, "apply", False) and not getattr(
            args, "_isolated_candidate_migration", False
        ):
            raise MigrationError(
                "standalone live-vault migration apply is disabled; apply is permitted "
                "only inside the isolated upgrade candidate transaction"
            )
        records = load_ledger(root)
        evidence_root = getattr(args, "_authorized_live_root", None) or root
        for record in records:
            try:
                _verify_outer_checkpoint(evidence_root, record["checkpoint"])
            except MigrationError as exc:
                raise MigrationError(
                    f"ledger recovery evidence is no longer available for "
                    f"{record['id']}: {exc}"
                ) from exc
        current_source_identity = getattr(args, "source_identity", None)
        has_prior_applied_record = any(
            record["id"] == manifest.id and record["result"] == "applied"
            for record in records
        )
        if current_source_identity is None and not has_prior_applied_record:
            current_source_identity = compute_source_identity(root)
        current_version = _manifest_version(root, manifest.version_target)
        current_distribution = (
            getattr(args, "_source_distribution", None)
            if getattr(args, "_isolated_candidate_migration", False)
            else _manifest_distribution(root)
        )
        if current_distribution != manifest.source_distribution:
            raise MigrationError(
                "wrong source distribution: vault declares "
                f"{current_distribution!r}, migration requires exactly "
                f"{manifest.source_distribution!r}"
            )
        if manifest.version_target == "system_version" and getattr(
            args, "_system_source_version", None
        ):
            current_version = args._system_source_version
        action = preflight_sequence(
            manifest,
            available,
            records,
            current_version,
            current_source_identity,
        )
        rep.info.update(
            {
                "migration": manifest.id,
                "version_target": manifest.version_target,
                "source_distribution": manifest.source_distribution,
                "source_identity": manifest.source_identity,
                "from_version": manifest.from_version,
                "to_version": manifest.to_version,
                "manifest_hash": manifest.manifest_hash,
            }
        )
        if action == "noop":
            try:
                _verify_transform_postconditions(root, manifest)
                if manifest.version_target == "system_version":
                    _audit_system_version_mirrors(root, manifest.to_version)
            except MigrationError as exc:
                raise MigrationError(
                    f"recorded migration postconditions no longer validate: {exc}"
                ) from exc
            valid, errors = _validation(root, args, manifest)
            if not valid:
                raise MigrationError(
                    "recorded migration postconditions no longer validate: "
                    + "; ".join(errors[:5])
                )
            rep.info["result"] = "already applied — exact id/hash repeat is a no-op"
            return rep
        preview = _transform(root, manifest, apply=False)
        rep.info.update(preview)
        if not getattr(args, "apply", False):
            rep.info["mode"] = (
                "dry-run — application is available only through the isolated "
                "upgrade candidate transaction"
            )
            return rep

        checkpoint = getattr(args, "_outer_checkpoint_identity", None)
        # ledger_record performs the exact kind-specific shape validation.
        ledger_record(manifest, checkpoint, "applied")
        live_root = args._authorized_live_root
        rep.info["checkpoint"] = checkpoint
        try:
            applied = _transform(root, manifest, apply=True)
            rep.info.update(applied)
            overlaid_system = (
                manifest.version_target == "system_version"
                and getattr(args, "_system_source_version", None) is not None
            )
            if not overlaid_system:
                _set_manifest_version(
                    root,
                    manifest.version_target,
                    manifest.from_version,
                    manifest.to_version,
                )
            if manifest.version_target == "system_version":
                _audit_system_version_mirrors(root, manifest.to_version)
            valid, errors = _validation(root, args, manifest)
            if not valid:
                rep.error(
                    f"post-migration validation failed ({len(errors)} errors); "
                    "isolated candidate must be discarded"
                )
                rep.errors.extend(errors[:10])
                return rep
            _append_change_journal(root, manifest, checkpoint)
            _verify_outer_checkpoint(live_root, checkpoint)
            append_ledger(root, ledger_record(manifest, checkpoint, "applied"))
        except Exception as exc:
            rep.error(
                f"candidate migration failed: {type(exc).__name__}: {exc}; "
                "isolated candidate must be discarded"
            )
            return rep
        rep.info["result"] = "applied"
        return rep
    except (MigrationError, OSError) as exc:
        rep.error(f"migration refused before mutation: {exc}")
        return rep


def _run_upgrade_candidate(root, args, rep: Report, authorization):
    """Internal entry point for a structurally proven upgrade candidate."""
    try:
        migration_name = authorization.get("migration_name")
        source_identity = authorization.get("source_identity")
        available = discover(os.path.join(root, "System", "Migrations"))
        selected = {
            item.directory.name: item for item in available
        }.get(migration_name)
        if selected is None:
            raise MigrationError(
                "authorized migration is absent from the sealed candidate"
            )
        if selected.source_identity != source_identity:
            raise MigrationError(
                "wrong source identity: authorization does not match "
                "candidate migration"
            )
        if _manifest_distribution(root) != selected.source_distribution:
            raise MigrationError(
                "wrong source distribution: candidate target declaration does "
                "not match migration contract"
            )
        prior_records = load_ledger(root)
        already_applied = any(
            record["id"] == selected.id
            and record["manifest_hash"] == selected.manifest_hash
            and record["source_identity"] == selected.source_identity
            and record["source_distribution"] == selected.source_distribution
            and record["result"] == "applied"
            for record in prior_records
        )
        effects = (
            authorization.get("effects")
            if already_applied
            else exact_transform_contract(root, selected)
        )
        verified = upgrade_candidate_mod.verify_migration_authorization(
            authorization,
            candidate=root,
            migration_name=migration_name,
            source_identity=source_identity,
            source_distribution=selected.source_distribution,
            manifest_hash=selected.manifest_hash,
            effects=effects,
        )
    except (AttributeError, MigrationError,
            upgrade_candidate_mod.CandidateError) as exc:
        rep.error(f"migration candidate authorization refused: {exc}")
        return rep
    candidate_args = SimpleNamespace(**vars(args))
    candidate_args.migration = migration_name
    candidate_args.apply = True
    candidate_args._isolated_candidate_migration = True
    candidate_args._candidate_system_migration = True
    candidate_args.source_identity = source_identity
    candidate_args._source_distribution = verified["source_distribution"]
    candidate_args._outer_checkpoint_identity = verified["outer_checkpoint"]
    candidate_args._authorized_live_root = verified["live"]
    candidate_args._system_source_version = verified.get("system_source_version")
    return run(root, candidate_args, rep)
