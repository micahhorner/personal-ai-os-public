"""Wave 5 contracts for the separate `.claude/skills` projection transaction."""
from __future__ import annotations
from test_io import read_file, write_file

import os
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from test_commands import Args, CAP_SKILL, mini_vault
from cmd import generate
from lib.report import Report


def bytes_snapshot(root):
    if not os.path.lexists(root):
        return None
    out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        for name in sorted(dirnames):
            path = os.path.join(dirpath, name)
            info = os.stat(path, follow_symlinks=False)
            rel = (rel_dir + "/" + name).lstrip("/")
            out[rel + "/"] = (stat.S_IFMT(info.st_mode), b"")
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            info = os.stat(path, follow_symlinks=False)
            rel = (rel_dir + "/" + name).lstrip("/")
            if stat.S_ISREG(info.st_mode):
                with open(path, "rb") as stream:
                    payload = stream.read()
            else:
                payload = b""
            out[rel] = (stat.S_IFMT(info.st_mode), payload)
    return out


class TestAgentSkillsTreeTransaction(unittest.TestCase):
    def setUp(self):
        self.outer = tempfile.mkdtemp(prefix="aios-skills-transaction-")
        self.root = mini_vault(os.path.join(self.outer, "vault"))
        cap = os.path.join(self.root, "System", "Capabilities", "cap-alpha")
        os.makedirs(cap)
        with open(os.path.join(cap, "SKILL.md"), "w", encoding="utf-8") as stream:
            stream.write(CAP_SKILL.format(name="cap-alpha", status="active"))
        self.skills = os.path.join(self.root, ".claude", "skills")

    def tearDown(self):
        shutil.rmtree(self.outer)

    def run_generate(self):
        report = Report("generate")
        generate.run(self.root, Args(), report)
        return report

    def seed_foreign(self):
        foreign = os.path.join(self.skills, "foreign", "nested")
        os.makedirs(os.path.join(foreign, "empty"))
        with open(os.path.join(foreign, "payload.bin"), "wb") as stream:
            stream.write(b"\x00foreign\xffbytes\n")
        return os.path.join(foreign, "payload.bin")

    def test_foreign_tree_is_byte_preserved_while_marker_owned_projection_replaces(self):
        foreign_file = self.seed_foreign()
        old = os.path.join(self.skills, "aios-cap-alpha")
        os.makedirs(old)
        with open(os.path.join(old, "SKILL.md"), "w", encoding="utf-8") as stream:
            stream.write(generate.EMIT_MARKER + "\nstale\n")
        with open(os.path.join(old, "stale-extra.bin"), "wb") as stream:
            stream.write(b"remove only with the marker-owned directory")
        foreign_before = bytes_snapshot(os.path.join(self.skills, "foreign"))

        report = self.run_generate()

        self.assertTrue(report.ok, report.errors)
        self.assertEqual(foreign_before, bytes_snapshot(os.path.join(self.skills, "foreign")))
        self.assertEqual(b"\x00foreign\xffbytes\n", read_file(foreign_file, mode="rb"))
        self.assertFalse(os.path.exists(os.path.join(old, "stale-extra.bin")))
        with open(os.path.join(old, "SKILL.md"), encoding="utf-8") as stream:
            self.assertIn("name: aios-cap-alpha", stream.read())

    def test_concurrent_foreign_edit_is_preserved_and_candidate_refused(self):
        foreign_file = self.seed_foreign()
        original = generate._populate_skills_candidate

        def edit_after_build(*args, **kwargs):
            result = original(*args, **kwargs)
            with open(foreign_file, "wb") as stream:
                stream.write(b"owner concurrent edit")
            return result

        with mock.patch.object(generate, "_populate_skills_candidate",
                               side_effect=edit_after_build):
            report = self.run_generate()

        self.assertFalse(report.ok)
        with open(foreign_file, "rb") as stream:
            self.assertEqual(b"owner concurrent edit", stream.read())
        self.assertFalse(any(name.startswith(".aios-tree-")
                             for name in os.listdir(os.path.join(self.root, ".claude"))))

    def test_partial_first_build_leaves_no_skills_or_parent_residue(self):
        original = generate._populate_skills_candidate

        def fail_after_build(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("injected late projection failure")

        with mock.patch.object(generate, "_populate_skills_candidate",
                               side_effect=fail_after_build):
            report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertFalse(os.path.lexists(os.path.join(self.root, ".claude")))

    def test_symlinked_skills_root_refuses_without_external_write(self):
        outside = os.path.join(self.outer, "outside")
        os.makedirs(outside)
        marker = os.path.join(outside, "sentinel.bin")
        with open(marker, "wb") as stream:
            stream.write(b"outside exact")
        os.makedirs(os.path.join(self.root, ".claude"))
        os.symlink(outside, self.skills)

        report = self.run_generate()

        self.assertFalse(report.ok)
        with open(marker, "rb") as stream:
            self.assertEqual(b"outside exact", stream.read())
        self.assertEqual(["sentinel.bin"], os.listdir(outside))

    def test_special_member_refuses_and_preserves_live_tree(self):
        os.makedirs(os.path.join(self.skills, "foreign"))
        fifo = os.path.join(self.skills, "foreign", "pipe")
        os.mkfifo(fifo)

        report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertTrue(stat.S_ISFIFO(os.stat(fifo, follow_symlinks=False).st_mode))

    def test_case_alias_collision_with_foreign_skill_refuses(self):
        foreign = os.path.join(self.skills, "AIOS-cap-alpha")
        os.makedirs(foreign)
        skill = os.path.join(foreign, "SKILL.md")
        with open(skill, "wb") as stream:
            stream.write(b"foreign exact\n")

        report = self.run_generate()

        self.assertFalse(report.ok)
        with open(skill, "rb") as stream:
            self.assertEqual(b"foreign exact\n", stream.read())


if __name__ == "__main__":
    unittest.main()
