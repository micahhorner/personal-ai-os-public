"""Deterministic Wave 5 property corpus for shared mutation boundaries."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unicodedata

import yaml


VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
AIOS = os.path.join(SCRIPTS, "aios.py")
sys.path.insert(0, SCRIPTS)

from lib import safepaths  # noqa: E402


def tree_bytes(root: str) -> dict[str, bytes]:
    out = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(directory, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if os.path.islink(path):
                out[rel] = ("LINK:" + os.readlink(path)).encode("utf-8")
            else:
                with open(path, "rb") as stream:
                    out[rel] = stream.read()
    return out


class SharedPathProperties(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="aios-property-root-")
        self.outside = tempfile.mkdtemp(prefix="aios-property-outside-")
        os.makedirs(os.path.join(self.root, "System", "Generated"))
        with open(os.path.join(self.outside, "sentinel.txt"), "wb") as stream:
            stream.write(b"outside sentinel\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.outside, ignore_errors=True)

    @staticmethod
    def hostile_spellings():
        values = []
        for index in range(24):
            values.extend((
                f"../outside-{index}.md",
                f"nested/../../outside-{index}.md",
                f"/absolute/outside-{index}.md",
                f"C:/outside-{index}.md",
                f"nested\\outside-{index}.md",
                f"nested//outside-{index}.md",
                f"nested/./outside-{index}.md",
            ))
        values.append("nested/" + unicodedata.normalize("NFD", "Café.md"))
        return values

    def test_hostile_relative_spellings_are_zero_write(self):
        before_root = tree_bytes(self.root)
        before_outside = tree_bytes(self.outside)
        for value in self.hostile_spellings():
            with self.subTest(path=value):
                with self.assertRaises(safepaths.SafePathError):
                    safepaths.atomic_create_files(self.root, {value: b"hostile"})
                self.assertEqual(tree_bytes(self.root), before_root)
                self.assertEqual(tree_bytes(self.outside), before_outside)

    def test_symlinked_output_ancestors_never_write_outside(self):
        os.symlink(self.outside, os.path.join(self.root, "escape"))
        before = tree_bytes(self.outside)
        with self.assertRaises(safepaths.SafePathError):
            safepaths.atomic_create_files(
                self.root, {"escape/owned-by-outside.md": b"must not appear"}
            )
        with self.assertRaises(safepaths.SafePathError):
            safepaths.atomic_replace_tree(
                self.root, "escape/tree", lambda stage: None, lambda stage: None
            )
        self.assertEqual(tree_bytes(self.outside), before)

    def test_case_unicode_collisions_and_hardlinks_fail_closed(self):
        with self.assertRaisesRegex(safepaths.SafePathError, "collision"):
            safepaths.atomic_create_files(
                self.root, {"Data/File.md": b"a", "data/file.md": b"b"}
            )
        composed = "Data/Café.md"
        decomposed = unicodedata.normalize("NFD", composed)
        with self.assertRaises(safepaths.SafePathError):
            safepaths.atomic_create_files(
                self.root, {composed: b"a", decomposed: b"b"}
            )

        external = os.path.join(self.outside, "sentinel.txt")
        alias = os.path.join(self.root, "hardlink.txt")
        os.link(external, alias)
        before = tree_bytes(self.outside)
        with self.assertRaisesRegex(safepaths.SafePathError, "hardlinked"):
            safepaths.preflight_contained_regular_files(self.root, [alias])
        self.assertEqual(tree_bytes(self.outside), before)

    def test_archive_removal_refuses_symlink_source_and_archive_parent(self):
        os.makedirs(os.path.join(self.root, "Packs"))
        os.symlink(self.outside, os.path.join(self.root, "Packs", "demo"))
        before = tree_bytes(self.outside)
        with self.assertRaises(safepaths.SafePathError):
            safepaths.atomic_archive_and_remove_tree(
                self.root, "Packs/demo", "90 Archive/packs/demo", {}, lambda: None
            )
        os.unlink(os.path.join(self.root, "Packs", "demo"))
        os.makedirs(os.path.join(self.root, "Packs", "demo", "workspace"))
        with open(
            os.path.join(self.root, "Packs", "demo", "workspace", "one.md"), "wb"
        ) as stream:
            stream.write(b"owner bytes\n")
        os.makedirs(os.path.join(self.root, "90 Archive"), exist_ok=True)
        os.symlink(self.outside, os.path.join(self.root, "90 Archive", "packs"))
        with self.assertRaises(safepaths.SafePathError):
            safepaths.atomic_archive_and_remove_tree(
                self.root,
                "Packs/demo",
                "90 Archive/packs/demo",
                {"workspace/one.md": b"owner bytes\n"},
                lambda: None,
            )
        self.assertEqual(tree_bytes(self.outside), before)


class MutatingCliKillSwitchProperties(unittest.TestCase):
    MODES = (
        ("generate",),
        ("scaffold", "--type", "capability", "--name", "probe"),
        ("migrate", "--migration", "probe", "--apply"),
        ("import", "--plan", "probe", "--apply"),
        ("upgrade", "/nonexistent-release", "--apply", "--confirm"),
        ("okf-export",),
        ("okf-import", "/nonexistent-bundle"),
        ("extract", "/nonexistent.docx"),
        ("ripple", "--baseline", "note-probe"),
        ("pack", "probe", "--apply"),
        ("dedupe-batch", "00 Inbox", "--annotate"),
        ("workflow", "--ran", "workflow-probe"),
        ("review-due", "--set-missing"),
        ("measure", "/nonexistent.md", "--extract", "40 Outputs/probe.md"),
        ("docgen",),
    )

    def test_every_ordinary_mutating_mode_is_zero_write_when_disabled(self):
        for argv in self.MODES:
            with self.subTest(command=" ".join(argv)), tempfile.TemporaryDirectory(
                prefix="aios-kill-property-"
            ) as root:
                manifest = {
                    "system": {
                        "name": "Property Vault",
                        "system_version": "1.64.1",
                        "vault_profile_version": "1.0.0",
                        "instance_role": "generic-master",
                    },
                    "runtime": {"ai_writes_enabled": False},
                }
                with open(
                    os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w", encoding="utf-8"
                ) as stream:
                    yaml.safe_dump(manifest, stream)
                before = tree_bytes(root)
                result = subprocess.run(
                    [sys.executable, AIOS, *argv, "--root", root],
                    text=True, capture_output=True, check=False,
                )
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(tree_bytes(root), before)


if __name__ == "__main__":
    unittest.main()
