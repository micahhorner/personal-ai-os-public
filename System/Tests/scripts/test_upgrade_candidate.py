"""Focused candidate-tree and transaction-preflight tests (Wave 3 / DoD-12)."""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)

from cmd import upgrade as upgrade  # noqa: E402
from lib import upgrade_candidate as candidate  # noqa: E402


def write(root, rel, body):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(body)


def state(root):
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            with open(path, "rb") as stream:
                result[os.path.relpath(path, root)] = stream.read()
    return result


class CandidateFixture(unittest.TestCase):
    def setUp(self):
        self.outer = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.outer.name, "instance")
        self.release = os.path.join(self.outer.name, "release")
        os.makedirs(self.root)
        os.makedirs(self.release)
        for rel, body in {
            "System/Core/replace.txt": "old",
            "System/Core/remove.txt": "retired",
            "System/Journal/change-journal.md": "history",
            "System/Tests/results/local.yaml": "certification",
            "20 Knowledge/note.md": "human note",
            "80 User/preferences.md": "preferences",
            ".obsidian/app.json": "settings",
            "Packs/local/pack.md": "local pack",
        }.items():
            write(self.root, rel, body)
        for rel, body in {
            "System/Core/replace.txt": "new",
            "System/Core/add.txt": "added",
            "Decisions/_ABOUT.md": "seed",
            "System/.baseline-manifest.json": "{}",
        }.items():
            write(self.release, rel, body)
        self.plan = {
            "replace": ["System/Core/replace.txt"],
            "add": ["System/Core/add.txt", "Decisions/_ABOUT.md"],
            "remove": ["System/Core/remove.txt"],
        }

    def tearDown(self):
        self.outer.cleanup()

    @staticmethod
    def product(rel):
        return rel.startswith("System/") and not rel.startswith(
            ("System/Journal/", "System/Tests/results/"))


class TestCandidateSurface(CandidateFixture):
    def test_complete_candidate_changes_only_declared_surface(self):
        before = state(self.root)
        observed = {}
        boundaries = []

        def validate(candidate_root):
            observed.update(state(candidate_root))
            return True

        info = candidate.build_candidate(
            self.root, self.release, self.plan, is_product_path=self.product,
            seed_paths=("Decisions/_ABOUT.md",), validator=validate,
            boundary=lambda name, phase, root: boundaries.append((name, phase, root)))
        self.assertEqual(state(self.root), before, "candidate construction mutated live vault")
        self.assertEqual(observed["System/Core/replace.txt"], b"new")
        self.assertEqual(observed["System/Core/add.txt"], b"added")
        self.assertNotIn("System/Core/remove.txt", observed)
        self.assertEqual(observed["20 Knowledge/note.md"], b"human note")
        self.assertEqual(observed["System/Journal/change-journal.md"], b"history")
        self.assertEqual(observed["System/Tests/results/local.yaml"], b"certification")
        self.assertEqual(observed["80 User/preferences.md"], b"preferences")
        self.assertEqual(observed[".obsidian/app.json"], b"settings")
        self.assertEqual(observed["Packs/local/pack.md"], b"local pack")
        candidate.delete_candidate(
            info, root=self.root,
            boundary=lambda name, phase, root: boundaries.append((name, phase, root)))
        self.assertFalse(os.path.exists(info["stage"]))
        self.assertEqual(
            [(name, phase) for name, phase, _ in boundaries],
            [("candidate-copy", "before"), ("candidate-copy", "after"),
             ("candidate-delete", "before"), ("candidate-delete", "after"),
             ("baseline-replacement", "before"),
             ("baseline-replacement", "after")])

    def test_user_owned_write_is_rejected_before_staging(self):
        bad = dict(self.plan)
        bad["replace"] = ["80 User/preferences.md"]
        write(self.release, "80 User/preferences.md", "hostile")
        before = state(self.root)
        with self.assertRaisesRegex(candidate.CandidateError, "outside declared"):
            candidate.build_candidate(
                self.root, self.release, bad, is_product_path=self.product,
                seed_paths=("Decisions/_ABOUT.md",))
        self.assertEqual(state(self.root), before)
        self.assertFalse(any(".aios-upgrade-" in n
                             for n in os.listdir(self.outer.name)))

    def test_validation_failure_cleans_candidate_and_preserves_live_tree(self):
        before = state(self.root)
        with self.assertRaisesRegex(candidate.CandidateError, "invalid candidate"):
            candidate.build_candidate(
                self.root, self.release, self.plan, is_product_path=self.product,
                seed_paths=("Decisions/_ABOUT.md",),
                validator=lambda _root: (_ for _ in ()).throw(
                    candidate.CandidateError("invalid candidate")))
        self.assertEqual(state(self.root), before)
        self.assertFalse(any(".aios-upgrade-" in n
                             for n in os.listdir(self.outer.name)))

    def test_product_target_symlink_is_rejected_before_staging(self):
        external = os.path.join(self.outer.name, "external")
        os.makedirs(external)
        os.remove(os.path.join(self.root, "System", "Core", "replace.txt"))
        os.symlink(os.path.join(external, "escaped.txt"),
                   os.path.join(self.root, "System", "Core", "replace.txt"))
        with self.assertRaisesRegex(candidate.CandidateError, "traverses a symlink"):
            candidate.preflight(
                self.root, self.release, self.plan, is_product_path=self.product,
                seed_paths=("Decisions/_ABOUT.md",))
        self.assertFalse(os.path.exists(os.path.join(external, "escaped.txt")))

    def test_git_directory_and_pointer_file_are_preserved_exactly(self):
        for kind in ("directory", "pointer"):
            with self.subTest(kind=kind):
                git = os.path.join(self.root, ".git")
                if os.path.isdir(git):
                    import shutil
                    shutil.rmtree(git)
                elif os.path.exists(git):
                    os.remove(git)
                if kind == "directory":
                    write(self.root, ".git/HEAD", "ref: refs/heads/main\n")
                    write(self.root, ".git/refs/heads/main", "abc123\n")
                else:
                    with open(git, "w", encoding="utf-8") as stream:
                        stream.write("gitdir: /tmp/external-worktree\n")
                expected = candidate.path_identity(git)
                info = candidate.build_candidate(
                    self.root, self.release, self.plan,
                    is_product_path=self.product,
                    seed_paths=("Decisions/_ABOUT.md",))
                self.assertEqual(
                    expected,
                    candidate.path_identity(os.path.join(info["candidate"], ".git")))
                candidate.delete_candidate(info, root=self.root)


class TestCandidatePreflight(CandidateFixture):
    def test_plan_identity_is_order_independent_and_repeatable(self):
        reordered = {
            "add": list(reversed(self.plan["add"])),
            "remove": list(self.plan["remove"]),
            "replace": list(self.plan["replace"]),
        }
        first = candidate.plan_identity(self.plan)
        self.assertEqual(first, candidate.plan_identity(reordered))
        self.assertEqual(first, candidate.plan_identity(self.plan))

    def test_insufficient_space_refuses_before_write(self):
        before = state(self.root)
        with mock.patch.object(candidate, "_free_bytes", return_value=1):
            with self.assertRaisesRegex(candidate.CandidateError, "insufficient free space"):
                candidate.preflight(
                    self.root, self.release, self.plan,
                    is_product_path=self.product,
                    seed_paths=("Decisions/_ABOUT.md",))
        self.assertEqual(state(self.root), before)

    def test_cross_filesystem_refuses_before_write(self):
        before = state(self.root)
        with mock.patch.object(candidate, "_same_filesystem", return_value=False):
            with self.assertRaisesRegex(candidate.CandidateError, "different filesystems"):
                candidate.preflight(
                    self.root, self.release, self.plan,
                    is_product_path=self.product,
                    seed_paths=("Decisions/_ABOUT.md",))
        self.assertEqual(state(self.root), before)

    def test_5k_and_10k_planning_complete_within_180_second_budget(self):
        notes = os.path.join(self.root, "20 Knowledge", "scale")
        os.makedirs(notes)
        write(self.root, "System/Core/stable.txt", "stable")
        write(self.release, "System/Core/stable.txt", "stable")
        base = upgrade._hash_tree(self.root)
        measurements = {}
        for target in (5000, 10000):
            current = len(os.listdir(notes))
            for number in range(current, target):
                write(self.root, f"20 Knowledge/scale/note-{number:05d}.md", "representative note")
            started = time.monotonic()
            plan = upgrade._classify(self.root, self.release, base)
            candidate.preflight(
                self.root, self.release, plan, is_product_path=self.product,
                reserve_bytes=0)
            elapsed = time.monotonic() - started
            measurements[target] = elapsed
            self.assertLess(elapsed, 180.0)
            self.assertEqual(candidate.plan_identity(plan), candidate.plan_identity(plan))
        self.assertLess(measurements[10000], 180.0)


if __name__ == "__main__":
    unittest.main()
