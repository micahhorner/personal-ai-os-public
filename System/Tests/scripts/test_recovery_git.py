"""Focused tests for exact, fail-closed Git restoration."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


VAULT = Path(__file__).resolve().parents[3]
MODULE = VAULT / "System" / "Scripts" / "lib" / "recovery.py"
SPEC = importlib.util.spec_from_file_location("recovery", MODULE)
assert SPEC and SPEC.loader
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


class RecoveryGitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="recovery git Ω ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "disposable repo with spaces Ω"
        self.root.mkdir()
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Recovery Test")
        self.write("kept.txt", "version one\n")
        self.write("folder/old.txt", "old only\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "one")
        self.one = git(self.root, "rev-parse", "HEAD")
        self.one_info = recovery.inspect_commit(self.root, self.one)

        self.write("kept.txt", "version two\n")
        (self.root / "folder" / "old.txt").unlink()
        self.write("new.txt", "new only\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "two")
        self.two = git(self.root, "rev-parse", "HEAD")

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def restore_one(self, **kwargs):
        return recovery.restore_commit(
            self.root,
            self.one,
            expected_tracked_sha256=self.one_info["tracked_sha256"],
            **kwargs,
        )


class TestExactRestore(RecoveryGitTestCase):
    def test_scoped_restore_is_exact_without_touching_outside_work(self):
        scope = ["folder"]
        identity = recovery.inspect_commit(
            self.root, self.one, scope_paths=scope
        )
        self.write("folder/later.txt", "remove within scope\n")
        self.write("outside loose.txt", "preserve outside\n")
        outside_before = (self.root / "kept.txt").read_bytes()

        evidence = recovery.restore_commit(
            self.root,
            self.one,
            expected_tracked_sha256=identity["tracked_sha256"],
            clean=True,
            scope_paths=scope,
        )

        self.assertEqual(b"old only\n", (self.root / "folder/old.txt").read_bytes())
        self.assertFalse((self.root / "folder/later.txt").exists())
        self.assertEqual(outside_before, (self.root / "kept.txt").read_bytes())
        self.assertTrue((self.root / "new.txt").exists())
        self.assertTrue((self.root / "outside loose.txt").exists())
        self.assertEqual("declared-paths-only", evidence["coverage"])
        self.assertTrue(evidence["exact_restoration"])

    def test_scoped_identity_is_bound_to_the_declared_paths(self):
        identity = recovery.inspect_commit(
            self.root, self.one, scope_paths=["folder"]
        )
        before = (self.root / "kept.txt").read_bytes()
        with self.assertRaisesRegex(recovery.RecoveryError, "does not match"):
            recovery.restore_commit(
                self.root,
                self.one,
                expected_tracked_sha256=identity["tracked_sha256"],
                scope_paths=["kept.txt"],
            )
        self.assertEqual(before, (self.root / "kept.txt").read_bytes())
        with self.assertRaisesRegex(recovery.RecoveryError, "overlaps"):
            recovery.inspect_commit(
                self.root, self.one, scope_paths=["folder", "folder/old.txt"]
            )

    def test_clean_restore_removes_newer_tracked_paths_without_moving_head(self):
        evidence = self.restore_one(validator=lambda root: (root / "kept.txt").exists())
        self.assertEqual(self.two, git(self.root, "rev-parse", "HEAD"))
        self.assertEqual("version one\n", (self.root / "kept.txt").read_text())
        self.assertEqual("old only\n", (self.root / "folder/old.txt").read_text())
        self.assertFalse((self.root / "new.txt").exists())
        self.assertTrue(evidence["exact_restoration"])
        self.assertEqual(
            self.one_info["tracked_sha256"], evidence["post"]["tracked_sha256"]
        )
        self.assertNotEqual(
            evidence["before"]["tree_sha256"], evidence["post"]["tree_sha256"]
        )
        self.assertIsNone(evidence["snapshot"])
        self.assertTrue(evidence["validation"]["passed"])

    def test_dirty_restore_preserves_snapshot_before_overwrite(self):
        self.write("kept.txt", "uncommitted irreplaceable edit\n")
        evidence = self.restore_one()
        snapshot = Path(evidence["snapshot"])
        self.assertTrue(snapshot.is_file())
        with tarfile.open(snapshot, "r:gz") as archive:
            saved = archive.extractfile("kept.txt")
            assert saved is not None
            self.assertEqual(b"uncommitted irreplaceable edit\n", saved.read())
        self.assertEqual("version one\n", (self.root / "kept.txt").read_text())
        self.assertTrue(evidence["before"]["tracked_status"])

    def test_spaces_unicode_and_executable_modes_restore_exactly(self):
        self.write("folder/space Ω.txt", "snowman ☃\n")
        executable = self.write("bin/tool Ω", "#!/bin/sh\n")
        executable.chmod(0o755)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "unicode")
        target = git(self.root, "rev-parse", "HEAD")
        info = recovery.inspect_commit(self.root, target)
        self.write("folder/space Ω.txt", "wrong\n")
        executable.chmod(0o644)

        evidence = recovery.restore_commit(
            self.root,
            target,
            expected_tracked_sha256=info["tracked_sha256"],
        )
        self.assertEqual("snowman ☃\n", (self.root / "folder/space Ω.txt").read_text())
        self.assertTrue(os.access(executable, os.X_OK))
        self.assertEqual(info["tracked_sha256"], evidence["post"]["tracked_sha256"])

    def test_rerun_is_idempotent_and_does_not_create_a_second_snapshot(self):
        first = self.restore_one()
        second = self.restore_one()
        self.assertTrue(first["exact_restoration"])
        self.assertTrue(second["exact_restoration"])
        self.assertEqual(
            first["post"]["tracked_sha256"], second["post"]["tracked_sha256"]
        )
        self.assertIsNone(second["snapshot"])
        self.assertEqual(
            second["before"]["tree_sha256"], second["post"]["tree_sha256"]
        )


class TestUntrackedAndIgnoredPolicy(RecoveryGitTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write(".gitignore", "ignored/\n")
        git(self.root, "add", ".gitignore")
        git(self.root, "commit", "-qm", "ignore policy")
        self.write("loose.txt", "keep unless clean\n")
        self.write("ignored/private.txt", "ignored\n")

    def test_default_preserves_untracked_and_ignored_files(self):
        evidence = self.restore_one()
        self.assertTrue((self.root / "loose.txt").exists())
        self.assertTrue((self.root / "ignored/private.txt").exists())
        self.assertFalse(evidence["clean"])

    def test_explicit_clean_removes_untracked_but_preserves_ignored_runtime_state(self):
        evidence = self.restore_one(clean=True)
        self.assertFalse((self.root / "loose.txt").exists())
        self.assertTrue((self.root / "ignored/private.txt").exists())
        self.assertTrue(evidence["clean"])
        self.assertTrue(evidence["clean_preview"])

    def test_clean_preserves_untracked_bytes_when_tracked_tree_is_already_exact(self):
        commit = git(self.root, "rev-parse", "HEAD")
        identity = recovery.inspect_commit(self.root, commit)
        evidence = recovery.restore_commit(
            self.root,
            commit,
            expected_tracked_sha256=identity["tracked_sha256"],
            clean=True,
        )

        self.assertFalse((self.root / "loose.txt").exists())
        self.assertTrue((self.root / "ignored/private.txt").exists())
        snapshot = Path(evidence["snapshot"])
        self.assertTrue(snapshot.is_file())
        with tarfile.open(snapshot, "r:gz") as archive:
            loose = archive.extractfile("loose.txt")
            self.assertIsNotNone(loose)
            self.assertEqual(loose.read(), b"keep unless clean\n")


class TestRefusalAndValidation(RecoveryGitTestCase):
    def test_invalid_or_nonexact_refs_and_wrong_expected_hash_fail_before_restore(self):
        original = (self.root / "kept.txt").read_text()
        cases = ["HEAD", self.one[:12], "f" * 40]
        for target in cases:
            with self.subTest(target=target):
                with self.assertRaises(recovery.RecoveryError):
                    recovery.restore_commit(
                        self.root,
                        target,
                        expected_tracked_sha256=self.one_info["tracked_sha256"],
                    )
        with self.assertRaisesRegex(recovery.RecoveryError, "does not match"):
            recovery.restore_commit(
                self.root,
                self.one,
                expected_tracked_sha256="0" * 64,
            )
        self.assertEqual(original, (self.root / "kept.txt").read_text())

    def test_validation_failure_is_a_hard_error_with_evidence(self):
        with self.assertRaisesRegex(recovery.RecoveryError, "failed validation") as caught:
            self.restore_one(validator=lambda root: {"ok": False, "reason": "probe"})
        self.assertFalse(caught.exception.evidence["exact_restoration"])
        self.assertEqual("probe", caught.exception.evidence["validation"]["reason"])

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic links")
    def test_commit_with_escaping_symlink_is_rejected_before_mutation(self):
        link = self.root / "unsafe-link"
        link.symlink_to("../../outside")
        git(self.root, "add", "unsafe-link")
        git(self.root, "commit", "-qm", "unsafe link")
        unsafe = git(self.root, "rev-parse", "HEAD")
        before = (self.root / "kept.txt").read_text()
        with self.assertRaisesRegex(recovery.RecoveryError, "escapes repository"):
            recovery.inspect_commit(self.root, unsafe)
        self.assertEqual(before, (self.root / "kept.txt").read_text())


if __name__ == "__main__":
    unittest.main()
