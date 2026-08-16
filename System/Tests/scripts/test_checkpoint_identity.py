"""Checkpoint identity and executable rollback-command contract.

Every repository is disposable. The command-execution case copies the real CLI
into a temporary vault so the exact command printed by checkpoint is the command
that performs recovery.
"""
from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)

from cmd import checkpoint as ck_mod  # noqa: E402
from lib.report import Report  # noqa: E402


class Args:
    json = False
    message = "identity test"
    rollback = None
    confirm = False
    clean = False
    force_zip = False
    zip_only = False
    paths = None
    strict = False


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _repo(root: str, *, executable_cli: bool = False) -> str:
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(VAULT, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as fh:
        _write(os.path.join(root, "SYSTEM-MANIFEST.yaml"), fh.read())
    _write(
        os.path.join(root, "20 Knowledge", "state.md"),
        "---\nid: note-state\ntype: note\nstatus: draft\n"
        "created: 2026-07-28\nupdated: 2026-07-28\nsummary: state\n---\n\noriginal\n",
    )
    _write(os.path.join(root, "System", "Journal", "change-journal.md"),
           "# Change journal\n")
    shutil.copytree(os.path.join(VAULT, "System", "Schemas"),
                    os.path.join(root, "System", "Schemas"))
    if executable_cli:
        shutil.copytree(SCRIPTS, os.path.join(root, "System", "Scripts"),
                        dirs_exist_ok=True)
    for argv in (
        ("init", "-q"),
        ("config", "user.email", "checkpoint@test.invalid"),
        ("config", "user.name", "Checkpoint Test"),
        ("add", "-A"),
        ("commit", "-qm", "base"),
    ):
        result = _git(root, *argv)
        if result.returncode:
            raise AssertionError(result.stderr)
    return root


@unittest.skipUnless(shutil.which("git"), "git required")
class TestGitCheckpointIdentity(unittest.TestCase):
    def test_clean_git_returns_full_immutable_target_and_executes_printed_command(self):
        with tempfile.TemporaryDirectory(prefix="checkpoint identity ") as outer:
            root = _repo(os.path.join(outer, "vault ü"), executable_cli=True)
            expected = _git(root, "rev-parse", "HEAD").stdout.strip()

            rep = ck_mod.run(root, Args(), Report("checkpoint"))
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(f"git {expected}", rep.info["checkpoint"])
            self.assertEqual(expected, rep.info["checkpoint_identity"]["target"])
            self.assertEqual("git-commit", rep.info["checkpoint_identity"]["kind"])
            self.assertEqual("clean-head",
                             rep.info["checkpoint_identity"]["scope"]["mode"])
            self.assertTrue(rep.info["checkpoint_identity"]["exact_recovery"])
            self.assertEqual("whole-tree",
                             rep.info["checkpoint_identity"]["coverage"])
            self.assertNotEqual(rep.info["checkpoint_identity"]["target"],
                                rep.info["checkpoint_display"])

            rollback = rep.info["rollback"]
            self.assertEqual(expected, rollback["target"])
            self.assertTrue(rollback["exact"])
            self.assertIn("--clean", rollback["argv"])
            self.assertEqual(rollback["command"], rep.info["rollback_command"])
            self.assertEqual(rollback["argv"], shlex.split(rollback["command"]))

            state = os.path.join(root, "20 Knowledge", "state.md")
            _write(state, _read(state).replace("original", "corrupted"))
            created_after = os.path.join(root, "20 Knowledge", "created after.md")
            _write(created_after, "not present at checkpoint\n")
            # Execute the exact human-rendered command, including its quoting for
            # the spaces and Unicode in this disposable vault's path.
            restored = subprocess.run(rollback["command"], shell=True,
                                      capture_output=True, text=True)
            self.assertEqual(0, restored.returncode,
                             restored.stdout + restored.stderr)
            self.assertIn("original", _read(state))
            self.assertNotIn("corrupted", _read(state))
            self.assertFalse(os.path.exists(created_after))

            _write(state, _read(state).replace("original", "corrupted again"))
            restored_argv = subprocess.run(
                rollback["argv"], capture_output=True, text=True
            )
            self.assertEqual(
                0,
                restored_argv.returncode,
                restored_argv.stdout + restored_argv.stderr,
            )
            self.assertIn("original", _read(state))

    def test_scoped_commit_records_exact_scope_and_preserves_staged_outside_work(self):
        with tempfile.TemporaryDirectory() as outer:
            root = _repo(os.path.join(outer, "vault"), executable_cli=True)
            scoped = os.path.join(root, "20 Knowledge", "state.md")
            outside = os.path.join(root, "outside.md")
            _write(scoped, _read(scoped).replace("original", "scoped"))
            _write(outside, "another session\n")
            self.assertEqual(0, _git(root, "add", "outside.md").returncode)

            args = Args()
            args.paths = ["20 Knowledge/state.md"]
            rep = ck_mod.run(root, args, Report("checkpoint"))
            self.assertTrue(rep.ok, rep.errors)
            target = rep.info["checkpoint_identity"]["target"]
            self.assertRegex(target, r"^[0-9a-f]{40,64}$")
            scope = rep.info["checkpoint_identity"]["scope"]
            self.assertEqual("declared-paths", scope["mode"])
            self.assertEqual(args.paths, scope["requested_paths"])
            self.assertEqual(args.paths, scope["committed_paths"])
            self.assertTrue(rep.info["checkpoint_identity"]["exact_recovery"])
            self.assertEqual(
                rep.info["checkpoint_identity"]["scope_sha256"],
                rep.info["rollback"]["expected_sha256"],
            )
            self.assertEqual("declared-paths-only",
                             rep.info["checkpoint_identity"]["coverage"])
            self.assertIn("rollback_command", rep.info)
            self.assertEqual(args.paths, rep.info["rollback"]["scope_paths"])
            self.assertIn("leaves out-of-scope",
                          rep.info["recovery_limit"])
            committed = _git(root, "show", "--pretty=", "--name-only", target).stdout
            self.assertIn("20 Knowledge/state.md", committed)
            self.assertNotIn("outside.md", committed)
            self.assertIn("A  outside.md", _git(root, "status", "--short").stdout)

            _write(scoped, _read(scoped).replace("scoped", "corrupted"))
            before_outside = _read(outside)
            before_status = _git(root, "status", "--short").stdout
            restored = subprocess.run(
                rep.info["rollback"]["argv"], capture_output=True, text=True
            )
            self.assertEqual(
                0, restored.returncode, restored.stdout + restored.stderr
            )
            self.assertIn("scoped", _read(scoped))
            self.assertNotIn("corrupted", _read(scoped))
            self.assertEqual(before_outside, _read(outside))
            self.assertIn("A  outside.md", _git(root, "status", "--short").stdout)
            self.assertIn("A  outside.md", before_status)

    def test_strict_scope_refuses_unrelated_work_before_creating_identity(self):
        with tempfile.TemporaryDirectory() as outer:
            root = _repo(os.path.join(outer, "vault"))
            state = os.path.join(root, "20 Knowledge", "state.md")
            _write(state, _read(state).replace("original", "scoped"))
            _write(os.path.join(root, "outside.md"), "unrelated\n")
            before = _git(root, "rev-parse", "HEAD").stdout.strip()
            args = Args()
            args.paths = ["20 Knowledge/state.md"]
            args.strict = True
            rep = ck_mod.run(root, args, Report("checkpoint"))
            self.assertFalse(rep.ok)
            self.assertNotIn("checkpoint_identity", rep.info)
            self.assertEqual(before, _git(root, "rev-parse", "HEAD").stdout.strip())

    def test_unchanged_scope_does_not_claim_the_whole_tree_is_clean(self):
        with tempfile.TemporaryDirectory() as outer:
            root = _repo(os.path.join(outer, "vault"))
            _write(os.path.join(root, "outside.md"), "unrelated\n")
            args = Args()
            args.paths = ["20 Knowledge/state.md"]
            rep = ck_mod.run(root, args, Report("checkpoint"))
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(
                "declared-paths-no-changes",
                rep.info["checkpoint_identity"]["scope"]["mode"],
            )
            self.assertIn("declared scope unchanged", rep.info["checkpoint_display"])
            self.assertNotIn("clean working tree", rep.info["checkpoint_display"])
            self.assertIn("outside.md", rep.info["left_uncommitted"])
            self.assertTrue(rep.info["checkpoint_identity"]["exact_recovery"])
            self.assertIn("rollback_command", rep.info)
            self.assertIn("leaves out-of-scope",
                          rep.info["recovery_limit"])


class TestSnapshotCheckpointIdentity(unittest.TestCase):
    def test_cross_version_validation_is_advisory_but_same_version_is_gated(self):
        with tempfile.TemporaryDirectory() as root:
            _write(
                os.path.join(root, "SYSTEM-MANIFEST.yaml"),
                "system:\n  system_version: 1.43.0\n",
            )

            def reject(_root, _args, report):
                report.error("newer rule rejects historical state")

            with mock.patch("cmd.validate.run", side_effect=reject):
                skewed = ck_mod._validate_restored_state(root, Args(), "1.64.1")
                same = ck_mod._validate_restored_state(root, Args(), "1.43.0")
            self.assertTrue(skewed["passed"])
            self.assertTrue(skewed["version_skew"])
            self.assertFalse(skewed["advisory_passed"])
            self.assertIn("newer rule", skewed["advisory_errors"][0])
            self.assertFalse(same["passed"])
            self.assertFalse(same["version_skew"])

    def test_no_git_snapshot_has_explicit_path_and_sha256_identity(self):
        with tempfile.TemporaryDirectory() as outer:
            root = os.path.join(outer, "vault no git")
            os.makedirs(root)
            _write(os.path.join(root, "note.md"), "snapshot content\n")
            rep = ck_mod.run(root, Args(), Report("checkpoint"))
            self.assertTrue(rep.ok, rep.errors)
            identity = rep.info["checkpoint_identity"]
            self.assertEqual("zip-snapshot", identity["kind"])
            self.assertEqual(rep.info["checkpoint"], identity["target"])
            self.assertTrue(os.path.isabs(identity["target"]))
            self.assertTrue(os.path.isfile(identity["target"]))
            with open(identity["target"], "rb") as fh:
                actual = hashlib.sha256(fh.read()).hexdigest()
            self.assertEqual(actual, identity["sha256"])
            self.assertTrue(identity["exact_recovery"])
            self.assertEqual(
                identity["sha256"], rep.info["rollback"]["expected_sha256"]
            )
            self.assertIn("rollback_command", rep.info)

    def test_immediate_same_label_snapshots_get_unique_no_clobber_identities(self):
        with tempfile.TemporaryDirectory() as outer:
            root = os.path.join(outer, "vault no git")
            os.makedirs(root)
            _write(os.path.join(root, "note.md"), "first state\n")
            with mock.patch.object(ck_mod.time, "strftime",
                                   return_value="2026-08-09-020000"):
                first = ck_mod.run(root, Args(), Report("checkpoint"))
                first_target = first.info["checkpoint_identity"]["target"]
                with open(first_target, "rb") as stream:
                    first_archive = stream.read()
                _write(os.path.join(root, "note.md"), "second state\n")
                second = ck_mod.run(root, Args(), Report("checkpoint"))

            self.assertTrue(first.ok, first.errors)
            self.assertTrue(second.ok, second.errors)
            second_target = second.info["checkpoint_identity"]["target"]
            self.assertNotEqual(first_target, second_target)
            self.assertTrue(second_target.endswith("-2.zip"), second_target)
            with open(first_target, "rb") as stream:
                self.assertEqual(first_archive, stream.read())
            self.assertNotEqual(
                first.info["checkpoint_identity"]["sha256"],
                second.info["checkpoint_identity"]["sha256"])

    def test_no_git_printed_argv_restores_a_real_vault_copy_exactly(self):
        with tempfile.TemporaryDirectory(prefix="snapshot CLI ") as outer:
            root = os.path.join(outer, "vault no git Ω")
            shutil.copytree(
                VAULT,
                root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            state = os.path.join(root, "20 Knowledge", "_ABOUT.md")
            original = _read(state)
            rep = ck_mod.run(root, Args(), Report("checkpoint"))
            self.assertTrue(rep.ok, rep.errors)

            _write(state, original + "\ncorrupted after checkpoint\n")
            created = os.path.join(root, "20 Knowledge", "created later.md")
            _write(created, "must disappear\n")
            restored = subprocess.run(
                rep.info["rollback"]["argv"], capture_output=True, text=True
            )

            self.assertEqual(
                0, restored.returncode, restored.stdout + restored.stderr
            )
            self.assertEqual(original, _read(state))
            self.assertFalse(os.path.exists(created))
            self.assertTrue(os.path.isfile(rep.info["checkpoint_identity"]["target"]))

    def test_snapshot_validation_failure_puts_pre_restore_tree_back(self):
        with tempfile.TemporaryDirectory() as outer:
            root = os.path.join(outer, "invalid vault")
            os.makedirs(root)
            state = os.path.join(root, "note.md")
            _write(state, "invalid checkpoint state\n")
            _write(
                os.path.join(root, "bad.md"),
                "---\nid: BAD ID\ntype: note\ncreated: 2026-07-28\n"
                "updated: 2026-07-28\nsummary: invalid\n---\n",
            )
            checkpoint = ck_mod.run(root, Args(), Report("checkpoint"))
            identity = checkpoint.info["checkpoint_identity"]
            _write(state, "important pre-restore bytes\n")

            args = Args()
            args.rollback = identity["target"]
            args.confirm = True
            args.expected_sha256 = identity["sha256"]
            restored = ck_mod.run(root, args, Report("rollback"))

            self.assertFalse(restored.ok)
            self.assertIn("failed validation", restored.errors[0])
            self.assertEqual("important pre-restore bytes\n", _read(state))
            self.assertIn("semantic_revert", restored.info["recovery"])


if __name__ == "__main__":
    unittest.main()
