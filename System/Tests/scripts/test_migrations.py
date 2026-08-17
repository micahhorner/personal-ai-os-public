"""Focused tests for strict migration manifests, ordering, ledger, and rollback."""
from __future__ import annotations

import json
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

VAULT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(VAULT / "System/Scripts"))

from cmd import migrate as migrate_mod  # noqa: E402
from lib.migrations import (  # noqa: E402
    MigrationError,
    append_ledger,
    append_change_journal,
    compute_manifest_hash,
    compute_source_identity,
    ledger_record,
    load_ledger,
    load_manifest,
    discover,
)
from lib.report import Report  # noqa: E402
from lib import snapshot as snapshot_mod  # noqa: E402
from lib import upgrade_candidate as candidate_mod  # noqa: E402

NOTE_OLD = (
    "---\nid: note-n\ntype: note\ncreated: 2026-07-28\n"
    "updated: 2026-07-28\nsummary: n\nx_old: value\n---\nbody\n"
)
NOTE_NEW = NOTE_OLD.replace("x_old:", "x_new:")


def _manifest(name="001-test", start="1.0.0", end="1.1.0", **updates):
    data = {
        "schema_version": "1.1.0",
        "id": f"migration-{name}",
        "version_target": "vault_profile_version",
        "source_distribution": "personal-ai-os",
        "source_identity": "0" * 64,
        "from_version": start,
        "to_version": end,
        "prerequisites": [],
        "content_selector": {"type": "note"},
        "transform": {
            "replace_exact_files": [{
                "path": "20 Knowledge/n.md",
                "old_sha256": hashlib.sha256(NOTE_OLD.encode()).hexdigest(),
                "payload": "payload.txt",
                "new_sha256": hashlib.sha256(NOTE_NEW.encode()).hexdigest(),
            }]
        },
        "validation": [{"check": "vault-validate"}],
        "rollback": {
            "strategy": "exact-checkpoint",
            "automatic_on_validation_failure": True,
        },
        "idempotency_key": f"migration-{name}-v1",
        "manifest_hash": "",
    }
    data.update(updates)
    data["manifest_hash"] = compute_manifest_hash(data)
    return data


def _write_manifest(root: Path, name="001-test", **kwargs) -> Path:
    directory = root / "System/Migrations" / name
    directory.mkdir(parents=True, exist_ok=True)
    if "transform" not in kwargs:
        (directory / "payload.txt").write_text(NOTE_NEW)
    path = directory / "migration.yaml"
    kwargs.setdefault("source_identity", compute_source_identity(root))
    path.write_text(yaml.safe_dump(_manifest(name=name, **kwargs), sort_keys=False))
    return path


def _vault(root: Path, version="1.0.0") -> Path:
    (root / "System/Migrations").mkdir(parents=True)
    (root / "System/Journal").mkdir(parents=True)
    (root / "20 Knowledge").mkdir(parents=True)
    (root / "SYSTEM-MANIFEST.yaml").write_text(
        "system:\n"
        "  distribution_id: personal-ai-os\n"
        "  system_version: 9.9.9\n"
        f"  vault_profile_version: {version}\n"
        "runtime:\n"
        "  ai_writes_enabled: true\n"
    )
    (root / "System/.baseline-manifest.json").write_text(
        json.dumps(
            {
                "system_version": "9.9.9",
                "files": {"SYSTEM-MANIFEST.yaml": "d" * 64},
                "generated_at": "ignored",
            }
        )
    )
    (root / "System/Journal/change-journal.md").write_text("# Change journal\n")
    (root / "20 Knowledge/n.md").write_text(NOTE_OLD)
    return root


def _git_checkpoint():
    return {
        "kind": "git-commit",
        "target": "a" * 40,
        "tracked_sha256": "b" * 64,
        "git_tree": "c" * 40,
        "scope": {
            "mode": "whole-tree",
            "requested_paths": [],
            "committed_paths": ["SYSTEM-MANIFEST.yaml"],
        },
        "coverage": "whole-tree",
        "exact_recovery": True,
    }


def _snapshot_checkpoint(root: Path):
    created = snapshot_mod.create_snapshot(
        root, root.parent / f"{root.name}-outer-{os.urandom(4).hex()}.zip"
    )
    return {
        "kind": "zip-snapshot",
        "target": created["path"],
        "sha256": created["sha256"],
        "tree_sha256": created["manifest"]["tree_sha256"],
        "scope": {"mode": "whole-tree", "paths": []},
        "coverage": "whole-tree",
        "exact_recovery": True,
    }


def _invoke_candidate(root, args, report, source_identity, checkpoint=None):
    checkpoint = checkpoint or _snapshot_checkpoint(root)
    authorization = {
        "migration_name": args.migration,
        "source_identity": source_identity,
    }
    system = yaml.safe_load((root / "SYSTEM-MANIFEST.yaml").read_text()).get(
        "system", {}
    )
    verified = {
        "outer_checkpoint": checkpoint,
        "live": str(root),
        "system_source_version": None,
        "source_distribution": system.get("distribution_id"),
    }
    with mock.patch.object(
        migrate_mod.upgrade_candidate_mod,
        "verify_migration_authorization",
        return_value=verified,
    ):
        return migrate_mod._run_upgrade_candidate(
            str(root), args, report, authorization
        )


class Args(SimpleNamespace):
    def __init__(self, migration="001-test", apply=False):
        super().__init__(
            migration=migration,
            apply=apply,
            message=None,
            rollback=None,
            confirm=False,
            clean=False,
            paths=None,
            strict=False,
            expected_sha256=None,
            force_zip=False,
            zip_only=False,
        )


class FakeRecovery:
    """In-memory checkpoint double; recovery machinery has its own fault suite."""

    def __init__(self, root: Path):
        self.root = root
        self.before = None
        self.checkpoints = 0
        self.rollbacks = 0

    def run(self, root, args, report):
        if args.rollback:
            self.rollbacks += 1
            for child in list(self.root.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            shutil.copytree(self.before, self.root, dirs_exist_ok=True)
            report.info["exact_restoration"] = True
            report.info["rolled_back_to"] = args.rollback
            return report
        self.checkpoints += 1
        self.before = Path(tempfile.mkdtemp()) / "saved"
        shutil.copytree(self.root, self.before)
        report.info["checkpoint_identity"] = _git_checkpoint()
        report.info["rollback_command"] = "exact rollback command"
        return report


class TestManifestContract(unittest.TestCase):
    def test_example_is_valid_and_hash_bound(self):
        manifest = load_manifest(
            VAULT / "System/Migrations/000-example/migration.yaml"
        )
        self.assertEqual(manifest.data["schema_version"], "1.1.0")
        self.assertEqual(manifest.manifest_hash, manifest.data["manifest_hash"])

    def test_unknown_field_and_changed_bytes_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            path = _write_manifest(root)
            data = yaml.safe_load(path.read_text())
            data["surprise"] = True
            path.write_text(yaml.safe_dump(data))
            with self.assertRaisesRegex(MigrationError, "unknown field"):
                load_manifest(path)
            data.pop("surprise")
            data["to_version"] = "1.2.0"
            path.write_text(yaml.safe_dump(data))
            with self.assertRaisesRegex(MigrationError, "manifest_hash mismatch"):
                load_manifest(path)

    def test_versions_are_exact_stable_semver(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            path = _write_manifest(root, start=">=1.0", end="1.1.0")
            with self.assertRaisesRegex(MigrationError, "exact stable SemVer"):
                load_manifest(path)

    def test_unknown_source_distribution_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            path = _write_manifest(root, source_distribution="unknown-product")
            with self.assertRaisesRegex(MigrationError, "must be one of"):
                load_manifest(path)

    def test_source_identity_rejects_duplicate_keys_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            baseline = root / "System/.baseline-manifest.json"
            baseline.write_text(
                '{"system_version":"9.9.9","system_version":"9.9.9",'
                '"files":{"x":"' + "a" * 64 + '"}}'
            )
            with self.assertRaisesRegex(MigrationError, "duplicate JSON key"):
                compute_source_identity(root)

            baseline.write_text(
                json.dumps(
                    {
                        "system_version": "9.9.9",
                        "files": {"../outside": "a" * 64},
                    }
                )
            )
            with self.assertRaisesRegex(MigrationError, "invalid path/hash"):
                compute_source_identity(root)

    def test_duplicate_yaml_rename_transform_and_missing_full_validation_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            path = _write_manifest(root)
            text = path.read_text()
            path.write_text(text.replace("schema_version: 1.1.0", "schema_version: 1.1.0\nschema_version: 1.1.0"))
            with self.assertRaisesRegex(MigrationError, "duplicate YAML key"):
                load_manifest(path)
            path = _write_manifest(
                root,
                transform={"rename_fields": {"old_field": "new_field"}},
            )
            with self.assertRaisesRegex(MigrationError, "unknown field"):
                load_manifest(path)
            path = _write_manifest(
                root,
                validation=[{"check": "field-absent", "field": "x_old"}],
            )
            with self.assertRaisesRegex(MigrationError, "must include vault-validate"):
                load_manifest(path)

    def test_symlinked_migrations_root_and_baseline_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            outside = Path(temp) / "outside"
            shutil.copytree(root / "System/Migrations", outside)
            shutil.rmtree(root / "System/Migrations")
            (root / "System/Migrations").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(MigrationError, "migration root|symlink|real directory"):
                discover(root / "System/Migrations")
            (root / "System/Migrations").unlink()
            (root / "System/Migrations").mkdir()
            baseline = root / "System/.baseline-manifest.json"
            content = baseline.read_text()
            baseline.unlink()
            external = Path(temp) / "baseline.json"
            external.write_text(content)
            baseline.symlink_to(external)
            with self.assertRaisesRegex(MigrationError, "symlinked|unsafe"):
                compute_source_identity(root)

    def test_exact_file_transform_is_hash_bound_and_preserves_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            destination = root / "20 Knowledge/exact.txt"
            destination.write_bytes(b"old")
            destination.chmod(0o640)
            directory = root / "System/Migrations/001-test"
            directory.mkdir(parents=True)
            payload = directory / "payload.txt"
            payload.write_bytes(b"new")
            _write_manifest(
                root,
                transform={
                    "replace_exact_files": [{
                        "path": "20 Knowledge/exact.txt",
                        "old_sha256": __import__("hashlib").sha256(b"old").hexdigest(),
                        "payload": "payload.txt",
                        "new_sha256": __import__("hashlib").sha256(b"new").hexdigest(),
                    }]
                },
                content_selector={"all": True},
                validation=[{"check": "vault-validate"}],
            )
            report = Report("migrate")
            _invoke_candidate(
                root, Args(apply=True), report, compute_source_identity(root)
            )
            self.assertTrue(report.ok, report.errors)
            self.assertEqual(destination.read_bytes(), b"new")
            self.assertEqual(destination.stat().st_mode & 0o777, 0o640)

    def test_duplicate_ledger_json_key_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            (root / "System/Journal/migration-ledger.jsonl").write_text(
                '{"id":"migration-001-x","id":"migration-001-x"}\n'
            )
            with self.assertRaisesRegex(MigrationError, "invalid JSON"):
                load_ledger(root)

    def test_ledger_rejects_naive_timestamp_and_accepts_clean_head_shape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            manifest = load_manifest(_write_manifest(root))
            checkpoint = _git_checkpoint()
            checkpoint["scope"]["mode"] = "clean-head"
            checkpoint["scope"]["committed_paths"] = []
            record = ledger_record(manifest, checkpoint, "applied")
            ledger = root / "System/Journal/migration-ledger.jsonl"
            ledger.write_text(json.dumps(record) + "\n")
            self.assertEqual(load_ledger(root)[0]["checkpoint"]["scope"]["mode"], "clean-head")
            record["timestamp"] = "2026-07-28"
            ledger.write_text(json.dumps(record) + "\n")
            with self.assertRaisesRegex(MigrationError, "timestamp"):
                load_ledger(root)

    def test_system_mirror_audit_rejects_extra_version_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            (root / "pyproject.toml").write_text(
                '[project]\nname = "x"\nversion = "9.9.9"\n'
                '[tool.probe]\nversion = "9.9.9"\n'
            )
            with self.assertRaisesRegex(MigrationError, "exactly one version"):
                migrate_mod._audit_system_version_mirrors(str(root), "9.9.9")

    def test_change_journal_symlink_is_refused_without_touching_outside(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            journal = root / "System/Journal/change-journal.md"
            journal.unlink()
            outside = Path(temp) / "outside.md"
            outside.write_text("sentinel\n")
            journal.symlink_to(outside)
            with self.assertRaisesRegex(MigrationError, "unsafe|symlinked"):
                append_change_journal(root, "- unsafe")
            self.assertEqual(outside.read_text(), "sentinel\n")

    def test_ledger_short_write_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            manifest = load_manifest(_write_manifest(root))
            record = ledger_record(manifest, _git_checkpoint(), "applied")
            real_write = os.write

            def short_write(fd, payload):
                real_write(fd, payload[:-1])
                return len(payload) - 1

            with mock.patch("lib.migrations.os.write", side_effect=short_write):
                with self.assertRaisesRegex(MigrationError, "incomplete"):
                    append_ledger(root, record)

    def test_duplicate_live_manifest_fails_before_apply(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            _write_manifest(root)
            live = root / "SYSTEM-MANIFEST.yaml"
            live.write_text(live.read_text() + "\nsystem:\n  system_version: 9.9.9\n")
            report = Report("migrate")
            migrate_mod.run(str(root), Args(), report)
            self.assertFalse(report.ok)
            self.assertIn("duplicate YAML key", " ".join(report.errors))



class TestSequenceAndLedger(unittest.TestCase):
    def _run(self, root, args, recovery):
        report = Report("migrate")
        with mock.patch.object(
            migrate_mod.validate_mod, "run", lambda _root, _args, _report: _report
        ):
            try:
                source_identity = compute_source_identity(root)
            except MigrationError:
                source_identity = load_manifest(
                    root / "System/Migrations" / args.migration / "migration.yaml"
                ).source_identity
            _invoke_candidate(root, args, report, source_identity)
        return report

    def test_success_records_required_ledger_and_repeat_is_noop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            _write_manifest(root)
            recovery = FakeRecovery(root)
            first = self._run(root, Args(apply=True), recovery)
            self.assertTrue(first.ok, first.errors)
            self.assertEqual(recovery.checkpoints, 0)
            self.assertIn("vault_profile_version: 1.1.0", (root / "SYSTEM-MANIFEST.yaml").read_text())
            self.assertIn("x_new:", (root / "20 Knowledge/n.md").read_text())
            records = load_ledger(root)
            self.assertEqual(len(records), 1)
            self.assertEqual(
                set(records[0]),
                {
                    "id",
                    "version_target",
                    "source_distribution",
                    "source_identity",
                    "from_version",
                    "to_version",
                    "manifest_hash",
                    "timestamp",
                    "checkpoint",
                    "result",
                    "tool_version",
                    "idempotency_key",
                },
            )
            self.assertEqual(records[0]["result"], "applied")

            repeat = self._run(root, Args(apply=True), recovery)
            self.assertTrue(repeat.ok, repeat.errors)
            self.assertIn("no-op", repeat.info["result"])
            self.assertEqual(recovery.checkpoints, 0)
            self.assertEqual(len(load_ledger(root)), 1)

            # A ledger is not permission to trust drifted destination state.
            note_path = root / "20 Knowledge/n.md"
            note_path.write_text(note_path.read_text().replace("x_new:", "x_old:"))
            drifted = self._run(root, Args(apply=True), recovery)
            self.assertFalse(drifted.ok)
            self.assertIn("postconditions", " ".join(drifted.errors))

    def test_system_version_target_is_refused_by_standalone_runner(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            _write_manifest(
                root,
                version_target="system_version",
                start="9.9.9",
                end="10.0.0",
            )
            report = Report("migrate")
            migrate_mod.run(str(root), Args(apply=True), report)
            self.assertFalse(report.ok)
            self.assertIn("candidate-only", " ".join(report.errors))
            manifest_text = (root / "SYSTEM-MANIFEST.yaml").read_text()
            self.assertIn("system_version: 9.9.9", manifest_text)
            self.assertIn("vault_profile_version: 1.0.0", manifest_text)
            self.assertEqual(load_ledger(root), [])

    def test_same_version_rival_source_identity_refuses_before_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            official = compute_source_identity(root)
            self.assertNotEqual(official, "f" * 64)
            _write_manifest(root, source_identity="f" * 64)
            recovery = FakeRecovery(root)
            report = self._run(root, Args(apply=True), recovery)
            self.assertFalse(report.ok)
            self.assertIn("wrong source identity", " ".join(report.errors))
            self.assertEqual(recovery.checkpoints, 0)
            self.assertIn("x_old:", (root / "20 Knowledge/n.md").read_text())

    def test_distribution_precondition_refuses_absent_unknown_and_pmm(self):
        for label, distribution_line in (
            ("absent", ""),
            ("unknown", "  distribution_id: unknown-product\n"),
            ("pmm", "  distribution_id: pmm-engine\n"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                root = _vault(Path(temp) / "v")
                _write_manifest(root)
                manifest_path = root / "SYSTEM-MANIFEST.yaml"
                text = manifest_path.read_text()
                text = text.replace("  distribution_id: personal-ai-os\n", distribution_line)
                manifest_path.write_text(text)
                report = self._run(root, Args(apply=True), FakeRecovery(root))
                self.assertFalse(report.ok)
                self.assertIn("source distribution", " ".join(report.errors))
                self.assertIn("x_old:", (root / "20 Knowledge/n.md").read_text())
                self.assertEqual(load_ledger(root), [])

    def test_core_and_pmm_edges_cannot_match_each_other(self):
        with tempfile.TemporaryDirectory() as temp:
            core = _vault(Path(temp) / "core")
            _write_manifest(core, source_distribution="pmm-engine")
            report = self._run(core, Args(apply=True), FakeRecovery(core))
            self.assertFalse(report.ok)
            self.assertIn("wrong source distribution", " ".join(report.errors))

        with tempfile.TemporaryDirectory() as temp:
            pmm = _vault(Path(temp) / "pmm")
            manifest_path = pmm / "SYSTEM-MANIFEST.yaml"
            manifest_path.write_text(
                manifest_path.read_text().replace(
                    "distribution_id: personal-ai-os",
                    "distribution_id: pmm-engine",
                )
            )
            _write_manifest(pmm, source_distribution="personal-ai-os")
            report = self._run(pmm, Args(apply=True), FakeRecovery(pmm))
            self.assertFalse(report.ok)
            self.assertIn("wrong source distribution", " ".join(report.errors))

    def test_changed_hash_repeat_is_refused_before_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            path = _write_manifest(root)
            old = load_manifest(path)
            ledger_path = root / "System/Journal/migration-ledger.jsonl"
            ledger_path.write_text(
                json.dumps(
                    ledger_record(
                        old,
                        _snapshot_checkpoint(root),
                        "applied",
                    )
                )
                + "\n"
            )
            _write_manifest(
                root,
                transform={
                    "replace_exact_files": [{
                        "path": "20 Knowledge/n.md",
                        "old_sha256": hashlib.sha256(NOTE_OLD.encode()).hexdigest(),
                        "payload": "payload.txt",
                        "new_sha256": "f" * 64,
                    }]
                },
                validation=[{"check": "vault-validate"}],
            )
            recovery = FakeRecovery(root)
            report = self._run(root, Args(apply=True), recovery)
            self.assertFalse(report.ok)
            self.assertIn("new_sha256 payload mismatch", " ".join(report.errors))
            self.assertEqual(recovery.checkpoints, 0)
            self.assertIn("x_old:", (root / "20 Knowledge/n.md").read_text())

    def test_repeat_refuses_inconsistent_ledger_or_live_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            manifest = load_manifest(_write_manifest(root))
            record = ledger_record(
                manifest,
                _snapshot_checkpoint(root),
                "applied",
            )
            ledger_path = root / "System/Journal/migration-ledger.jsonl"
            inconsistent = dict(record)
            inconsistent["source_identity"] = "f" * 64
            ledger_path.write_text(json.dumps(inconsistent) + "\n")
            recovery = FakeRecovery(root)
            report = self._run(root, Args(apply=True), recovery)
            self.assertIn("does not match discovered manifest", " ".join(report.errors))
            self.assertEqual(recovery.checkpoints, 0)

            ledger_path.write_text(json.dumps(record) + "\n")
            report = self._run(root, Args(apply=True), recovery)
            self.assertIn("recorded applied", " ".join(report.errors))
            self.assertIn("not 1.1.0", " ".join(report.errors))
            self.assertEqual(recovery.checkpoints, 0)

    def test_ledger_symlink_escape_is_refused_without_touching_outside(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            manifest = load_manifest(_write_manifest(root))
            outside = Path(temp) / "outside"
            outside.mkdir()
            sentinel = outside / "migration-ledger.jsonl"
            sentinel.write_text("do not touch\n")
            shutil.rmtree(root / "System/Journal")
            (root / "System/Journal").symlink_to(outside, target_is_directory=True)
            record = ledger_record(
                manifest,
                _git_checkpoint(),
                "applied",
            )
            with self.assertRaisesRegex(MigrationError, "unsafe|symlinked"):
                append_ledger(root, record)
            self.assertEqual(sentinel.read_text(), "do not touch\n")

    def test_wrong_source_refuses_before_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v", version="9.0.0")
            _write_manifest(root, "001-one")
            recovery = FakeRecovery(root)
            wrong = self._run(root, Args("001-one", True), recovery)
            self.assertIn("wrong source version", " ".join(wrong.errors))
            self.assertEqual(recovery.checkpoints, 0)

    def test_later_root_alternative_runs_from_exact_source_with_empty_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v", version="1.60.0")
            _write_manifest(
                root,
                "001-from-143",
                start="1.43.0",
                end="1.64.0",
                prerequisites=[],
            )
            _write_manifest(
                root,
                "002-from-160",
                start="1.60.0",
                end="1.64.0",
                prerequisites=[],
            )
            recovery = FakeRecovery(root)
            report = self._run(root, Args("002-from-160", True), recovery)
            self.assertTrue(report.ok, report.errors)
            self.assertEqual(recovery.checkpoints, 0)
            self.assertIn(
                "vault_profile_version: 1.64.0",
                (root / "SYSTEM-MANIFEST.yaml").read_text(),
            )
            self.assertEqual(load_ledger(root)[0]["id"], "migration-002-from-160")

    def test_declared_prerequisite_chain_cannot_be_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v", version="1.2.0")
            one = load_manifest(
                _write_manifest(
                    root, "001-one", start="1.0.0", end="1.1.0"
                )
            )
            two = load_manifest(
                _write_manifest(
                    root,
                    "002-two",
                    start="1.1.0",
                    end="1.2.0",
                    prerequisites=[one.id],
                )
            )
            _write_manifest(
                root,
                "003-three",
                start="1.2.0",
                end="1.3.0",
                prerequisites=[two.id],
            )
            # A corrupt/incomplete history that claims 002 but omits 001 may
            # not satisfy 003 merely because its direct prerequisite is present.
            (root / "System/Journal/migration-ledger.jsonl").write_text(
                json.dumps(
                    ledger_record(
                        two,
                        _snapshot_checkpoint(root),
                        "applied",
                    )
                )
                + "\n"
            )
            recovery = FakeRecovery(root)
            report = self._run(root, Args("003-three", True), recovery)
            self.assertFalse(report.ok)
            self.assertIn("lacks prerequisite", " ".join(report.errors))
            self.assertIn(one.id, " ".join(report.errors))
            self.assertEqual(recovery.checkpoints, 0)

    def test_ledger_prerequisite_must_appear_on_an_earlier_line(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v", version="1.2.0")
            one = load_manifest(_write_manifest(root, "001-one"))
            two = load_manifest(_write_manifest(
                root, "002-two", start="1.1.0", end="1.2.0",
                prerequisites=[one.id],
            ))
            records = [
                ledger_record(two, _snapshot_checkpoint(root), "applied"),
                ledger_record(one, _snapshot_checkpoint(root), "applied"),
            ]
            (root / "System/Journal/migration-ledger.jsonl").write_text(
                "".join(json.dumps(record) + "\n" for record in records)
            )
            report = self._run(root, Args("002-two", True), FakeRecovery(root))
            self.assertFalse(report.ok)
            self.assertIn("lacks prerequisite", " ".join(report.errors))

    def test_numbering_gap_is_allowed_for_other_plan_kinds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v", version="1.1.0")
            one_path = _write_manifest(root, "001-one")
            one = load_manifest(one_path)
            (root / "System/Journal/migration-ledger.jsonl").write_text(
                json.dumps(
                    ledger_record(
                        one,
                        _snapshot_checkpoint(root),
                        "applied",
                    )
                )
                + "\n"
            )
            _write_manifest(
                root,
                "003-three",
                start="1.1.0",
                end="1.2.0",
                prerequisites=["migration-001-one"],
            )
            recovery = FakeRecovery(root)
            report = self._run(root, Args("003-three", True), recovery)
            self.assertTrue(report.ok, report.errors)
            self.assertEqual(recovery.checkpoints, 0)


class TestCandidateIsolation(unittest.TestCase):
    def test_candidate_uses_outer_checkpoint_and_never_invokes_checkpoint_or_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            _write_manifest(
                root,
                validation=[
                    {"check": "field-present", "field": "never_created"},
                    {"check": "vault-validate"},
                ],
            )
            recovery = FakeRecovery(root)
            report = Report("migrate")
            _invoke_candidate(
                root, Args(apply=True), report, compute_source_identity(root)
            )
            self.assertFalse(report.ok)
            self.assertEqual(recovery.checkpoints, 0)
            self.assertEqual(recovery.rollbacks, 0)
            self.assertEqual(load_ledger(root), [])
            self.assertIn("candidate must be discarded", " ".join(report.errors))

    def test_standalone_apply_refuses_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            _write_manifest(
                root,
                validation=[
                    {"check": "field-present", "field": "never_created"},
                    {"check": "vault-validate"},
                ],
            )

            def tree_bytes():
                return {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob("*")
                    if path.is_file()
                }

            before = tree_bytes()
            report = Report("migrate")
            migrate_mod.run(str(root), Args(apply=True), report)
            self.assertFalse(report.ok)
            self.assertEqual(tree_bytes(), before)
            self.assertFalse(
                (root / "System/Journal/migration-ledger.jsonl").exists(),
                "a failure record inside the restored tree would make rollback non-exact",
            )
            self.assertIn("standalone live-vault", " ".join(report.errors))

    def test_candidate_authorization_and_material_checkpoint_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _vault(Path(temp) / "v")
            _write_manifest(root)
            before = (root / "20 Knowledge/n.md").read_bytes()
            report = Report("migrate")
            migrate_mod._run_upgrade_candidate(
                str(root), Args(apply=True), report, {}
            )
            self.assertFalse(report.ok)
            self.assertIn("authorization", " ".join(report.errors))

            report = Report("migrate")
            _invoke_candidate(
                root, Args(apply=True), report, compute_source_identity(root),
                checkpoint=_git_checkpoint(),
            )
            self.assertFalse(report.ok)
            self.assertIn("materially verified", " ".join(report.errors))
            self.assertEqual((root / "20 Knowledge/n.md").read_bytes(), before)

    def test_owned_staged_candidate_authorization_is_bound_to_live_and_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            live = _vault(Path(temp) / "live")
            _write_manifest(live)
            source_identity = compute_source_identity(live)
            checkpoint = _snapshot_checkpoint(live)
            info = candidate_mod.build_candidate(
                str(live),
                str(live),
                {"replace": [], "add": [], "remove": []},
                is_product_path=lambda _path: True,
            )
            selected = migrate_mod.discover(
                str(Path(info["candidate"]) / "System/Migrations")
            )[0]
            effects = migrate_mod.exact_transform_contract(
                info["candidate"], selected
            )
            authorization = candidate_mod.authorize_migration(
                info,
                root=str(live),
                migration_name="001-test",
                source_identity=source_identity,
                source_distribution=selected.source_distribution,
                manifest_hash=selected.manifest_hash,
                effects=effects,
                outer_checkpoint=checkpoint,
            )
            report = Report("migrate")
            with mock.patch.object(
                migrate_mod.validate_mod,
                "run",
                lambda _root, _args, _report: _report,
            ):
                migrate_mod._run_upgrade_candidate(
                    info["candidate"], Args(apply=False), report, authorization
                )
            self.assertTrue(report.ok, report.errors)
            self.assertIn(
                "x_new:", (Path(info["candidate"]) / "20 Knowledge/n.md").read_text()
            )
            self.assertIn("x_old:", (live / "20 Knowledge/n.md").read_text())


if __name__ == "__main__":
    unittest.main()
