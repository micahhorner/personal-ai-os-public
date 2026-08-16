"""Focused tests for the real-Git historical instance fixture builder."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


VAULT = Path(__file__).resolve().parents[3]
FIXTURE_MODULES = VAULT / "System" / "Tests" / "release_qualification"
sys.path.insert(0, str(FIXTURE_MODULES))

import fixture as release_fixture  # noqa: E402


def _git(repo, *args, text=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=text,
    )


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class HistoricalRepository:
    def __init__(self, root):
        self.root = Path(root)
        self.repo = self.root / "source repository"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "fixture@example.invalid")
        _git(self.repo, "config", "user.name", "Fixture Builder")
        _write(
            self.repo / "SYSTEM-MANIFEST.yaml",
            "system:\n"
            "  name: Personal AI OS\n"
            "  instance_role: generic-master   # product seed\n"
            "  system_version: 1.43.0\n",
        )
        _write(self.repo / "README.md", "# Historical release\n")
        _write(
            self.repo / "System" / "Journal" / "change-journal.md",
            "# Change journal\n\n- historical release entry\n",
        )
        _write(
            self.repo / "System" / "Runtime" / "Task Router.yaml",
            "id: doc-task-router\nmodes: {}\nfallback: {}\n",
        )
        executable = self.repo / "System" / "Scripts" / "fixture-tool"
        _write(executable, "#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "historical release")
        self.historical = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        _write(self.repo / "ONLY-IN-LATER-RELEASE.txt", "later\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "later release")


class TestHistoricalFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.history = HistoricalRepository(self.temp.name)

    def _destination(self, name="Historical Instance Ω"):
        path = Path(self.temp.name) / name
        path.mkdir()
        return path

    def test_materializes_exact_ref_without_moving_refs_or_worktrees(self):
        before_head = _git(self.history.repo, "rev-parse", "HEAD").stdout
        before_refs = _git(self.history.repo, "show-ref").stdout
        before_worktrees = _git(
            self.history.repo, "worktree", "list", "--porcelain"
        ).stdout
        destination = self._destination()

        result = release_fixture.build_historical_instance(
            self.history.repo,
            self.history.historical,
            destination,
        )

        self.assertEqual(result.resolved_commit, self.history.historical)
        self.assertEqual(
            (destination / "README.md").read_text(encoding="utf-8"),
            "# Historical release\n",
        )
        self.assertFalse((destination / "ONLY-IN-LATER-RELEASE.txt").exists())
        self.assertFalse((destination / ".git").exists())
        self.assertEqual(_git(self.history.repo, "rev-parse", "HEAD").stdout, before_head)
        self.assertEqual(_git(self.history.repo, "show-ref").stdout, before_refs)
        self.assertEqual(
            _git(self.history.repo, "worktree", "list", "--porcelain").stdout,
            before_worktrees,
        )

    def test_personalizes_and_seeds_every_representative_surface(self):
        destination = self._destination()
        result = release_fixture.build_historical_instance(
            self.history.repo, self.history.historical, destination
        )

        manifest = (destination / "SYSTEM-MANIFEST.yaml").read_text(encoding="utf-8")
        self.assertIn("instance_role: personal-instance", manifest)
        self.assertNotIn("generic-master", manifest)
        expected = {
            "00 Inbox/Release Qualification Capture.md",
            "10 Projects/Release Qualification Ω/Project.md",
            "20 Knowledge/Release Qualification Knowledge.md",
            "80 User/release-qualification.yaml",
            ".obsidian/release-qualification.json",
            "Packs/release-qualification-pack/pack.yaml",
            "Packs/release-qualification-pack/content/Pack State.md",
            "RELEASE-QUALIFICATION-ROOT.txt",
        }
        self.assertTrue(expected.issubset(set(result.seeded_paths)))
        for relative in expected:
            self.assertTrue((destination / relative).is_file(), relative)
        self.assertIn("SYSTEM-MANIFEST.yaml", result.modified_paths)
        self.assertIn("System/Journal/change-journal.md", result.modified_paths)
        self.assertIn("System/Runtime/Task Router.yaml", result.modified_paths)
        router = (
            destination / "System" / "Runtime" / "Task Router.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("release-qualification instance customization", router)
        journal = (
            destination / "System" / "Journal" / "change-journal.md"
        ).read_text(encoding="utf-8")
        self.assertIn("historical release entry", journal)
        self.assertIn("release-qualification-fixture", journal)
        self.assertTrue(
            os.stat(destination / "System" / "Scripts" / "fixture-tool").st_mode
            & 0o100,
            "Git's executable bit must survive archive materialization",
        )

    def test_inventory_is_structured_serializable_and_deterministic(self):
        first = self._destination("First Fixture Ω")
        second = self._destination("Second Fixture Ω")
        one = release_fixture.build_historical_instance(
            self.history.repo, self.history.historical, first
        )
        two = release_fixture.build_historical_instance(
            self.history.repo, self.history.historical, second
        )

        self.assertEqual(one.base_tree_sha256, two.base_tree_sha256)
        self.assertEqual(one.final_tree_sha256, two.final_tree_sha256)
        self.assertNotEqual(one.base_tree_sha256, one.final_tree_sha256)
        self.assertEqual(one.base_files, two.base_files)
        self.assertEqual(one.final_files, two.final_files)
        payload = one.to_dict()
        json.dumps(payload)
        self.assertEqual(payload["resolved_commit"], self.history.historical)
        self.assertTrue(
            all(len(entry["sha256"]) == 64 for entry in payload["final_files"])
        )

    def test_refuses_nonempty_missing_file_and_symlink_destinations(self):
        nonempty = self._destination("not empty")
        _write(nonempty / ".hidden", "occupied")
        missing = Path(self.temp.name) / "missing"
        file_path = Path(self.temp.name) / "plain-file"
        _write(file_path, "not a directory")

        for destination in (nonempty, missing, file_path):
            with self.subTest(destination=destination):
                with self.assertRaises(release_fixture.UnsafeDestinationError):
                    release_fixture.build_historical_instance(
                        self.history.repo, self.history.historical, destination
                    )

        if hasattr(os, "symlink"):
            real = self._destination("real empty")
            linked = Path(self.temp.name) / "linked destination"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaises(release_fixture.UnsafeDestinationError):
                release_fixture.build_historical_instance(
                    self.history.repo, self.history.historical, linked
                )

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic links")
    def test_rejects_archive_symlink_and_leaves_destination_empty(self):
        outside = Path(self.temp.name) / "outside.txt"
        link = self.history.repo / "escape"
        link.symlink_to("../../outside.txt")
        _git(self.history.repo, "add", "escape")
        _git(self.history.repo, "commit", "-qm", "unsafe symlink")
        unsafe_ref = _git(self.history.repo, "rev-parse", "HEAD").stdout.strip()
        destination = self._destination("safe destination")

        with self.assertRaises(release_fixture.UnsafeArchiveError):
            release_fixture.build_historical_instance(
                self.history.repo, unsafe_ref, destination
            )

        self.assertEqual(list(destination.iterdir()), [])
        self.assertFalse(outside.exists())

    def test_git_processes_are_argument_arrays_without_shell(self):
        destination = self._destination()
        original = release_fixture.subprocess.run
        calls = []

        def recording_run(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        with mock.patch.object(
            release_fixture.subprocess, "run", side_effect=recording_run
        ):
            release_fixture.build_historical_instance(
                self.history.repo, self.history.historical, destination
            )

        self.assertTrue(calls)
        for args, kwargs in calls:
            self.assertIsInstance(args[0], list)
            self.assertNotIn("shell", kwargs)

    def test_invalid_ref_cannot_partially_populate_destination(self):
        destination = self._destination()
        with self.assertRaises(release_fixture.FixtureError):
            release_fixture.build_historical_instance(
                self.history.repo, "--definitely-not-a-ref", destination
            )
        self.assertEqual(list(destination.iterdir()), [])

    def test_refuses_destination_inside_source_worktree(self):
        destination = self.history.repo / "empty fixture destination"
        destination.mkdir()
        with self.assertRaises(release_fixture.UnsafeDestinationError):
            release_fixture.build_historical_instance(
                self.history.repo, self.history.historical, destination
            )
        self.assertEqual(list(destination.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
