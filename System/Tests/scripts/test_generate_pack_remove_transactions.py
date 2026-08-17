"""Wave 5 RED contracts for generated-tree replacement and pack removal."""
from __future__ import annotations

from test_io import read_file

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import yaml


VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)

from cmd import generate, pack  # noqa: E402
from lib.report import Report  # noqa: E402


def manifest(root: str, writes: bool = True) -> None:
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w", encoding="utf-8") as fh:
        yaml.safe_dump(
            {
                "system": {
                    "name": "Test Vault", "system_version": "1.64.1",
                    "vault_profile_version": "1.0.0", "instance_role": "generic-master",
                },
                "runtime": {"ai_writes_enabled": writes},
            },
            fh,
        )


def snapshot(path: str) -> dict[str, bytes]:
    out = {}
    if not os.path.isdir(path):
        return out
    for dp, dns, fns in os.walk(path):
        dns.sort()
        for name in sorted(fns):
            full = os.path.join(dp, name)
            if os.path.islink(full):
                out[os.path.relpath(full, path)] = ("LINK:" + os.readlink(full)).encode()
            else:
                with open(full, "rb") as fh:
                    out[os.path.relpath(full, path)] = fh.read()
    return out


def residue(root: str) -> list[str]:
    found = []
    for dp, dns, fns in os.walk(root):
        for name in dns + fns:
            if (name.startswith(".aios-") or ".stage" in name or ".backup" in name):
                found.append(os.path.relpath(os.path.join(dp, name), root))
    return sorted(found)


def generate_root(root: str, writes: bool = True) -> str:
    manifest(root, writes)
    os.makedirs(os.path.join(root, "System", "Generated"), exist_ok=True)
    os.makedirs(os.path.join(root, "System", "Journal"), exist_ok=True)
    with open(os.path.join(root, "System", "Journal", "change-journal.md"), "w") as fh:
        fh.write("# Journal\n")
    return root


def run_generate(root: str):
    rep = Report("generate")
    error = None
    try:
        generate.run(root, SimpleNamespace(), rep)
    except BaseException as exc:  # the contract requires a report, never a torn-tree traceback
        error = exc
        rep.error(f"unhandled generation failure: {type(exc).__name__}: {exc}")
    return rep, error


PACK_MANIFEST = """id: pack-demo
name: Demo
version: 1.0.0
kind: role-pack
summary: demo
license: MIT
source: https://example.com/demo
layout:
  scaffold: [pack.yaml, vendor/]
  workspace: [workspace/]
  seed: []
"""


def pack_root(root: str, writes: bool = True, work_files=("one.md",)) -> str:
    manifest(root, writes)
    dest = os.path.join(root, "Packs", "demo")
    os.makedirs(os.path.join(dest, "workspace"), exist_ok=True)
    os.makedirs(os.path.join(dest, "vendor"), exist_ok=True)
    with open(os.path.join(dest, "pack.yaml"), "w", encoding="utf-8") as fh:
        fh.write(PACK_MANIFEST)
    with open(os.path.join(dest, "vendor", "guide.md"), "w") as fh:
        fh.write("vendor\n")
    for name in work_files:
        with open(os.path.join(dest, "workspace", name), "w") as fh:
            fh.write("owner " + name + "\n")
    return dest


def pack_args(*, purge=False):
    return SimpleNamespace(
        target="demo", remove_pack=True, apply=False, confirm=True, purge=purge,
        json=False,
    )


def run_remove(root: str, *, purge=False):
    rep = Report("pack")
    error = None

    def green_sub(_root, _module, outer, label, **_kwargs):
        sub = Report(label)
        outer.info[label] = "0 errors, 0 warnings"
        return sub

    try:
        with mock.patch.object(pack, "_sub", side_effect=green_sub):
            pack.run(root, pack_args(purge=purge), rep)
    except BaseException as exc:
        error = exc
        rep.error(f"unhandled removal failure: {type(exc).__name__}: {exc}")
    return rep, error


class TestGenerateTreeTransaction(unittest.TestCase):
    def setUp(self):
        self.root = generate_root(tempfile.mkdtemp(prefix="aios-generate-root-"))
        self.outside = tempfile.mkdtemp(prefix="aios-generate-outside-")
        self.gen = os.path.join(self.root, "System", "Generated")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.outside, ignore_errors=True)

    def seed_old(self):
        with open(os.path.join(self.gen, "known-good.txt"), "w") as fh:
            fh.write("known good\n")
        return snapshot(self.gen)

    def test_symlinked_generated_root_refuses_without_external_write(self):
        shutil.rmtree(self.gen)
        os.symlink(self.outside, self.gen)
        rep, error = run_generate(self.root)
        self.assertFalse(rep.ok)
        self.assertIsNone(error)
        self.assertEqual(os.listdir(self.outside), [])

    def test_concurrent_live_generated_edit_is_not_clobbered(self):
        before = self.seed_old()
        original = generate.system_reference
        changed = False

        def owner_edit(*args, **kwargs):
            nonlocal changed
            if not changed:
                changed = True
                with open(os.path.join(self.gen, "owner-concurrent.txt"), "w") as fh:
                    fh.write("owner change\n")
            return original(*args, **kwargs)

        with mock.patch.object(generate, "system_reference", side_effect=owner_edit):
            rep, error = run_generate(self.root)
        expected = dict(before, **{"owner-concurrent.txt": b"owner change\n"})
        self.assertFalse(rep.ok)
        self.assertEqual(snapshot(self.gen), expected)
        self.assertIsNone(error)
        self.assertEqual(residue(self.root), [])

    def test_partial_generation_failure_leaves_complete_old_tree_and_no_residue(self):
        before = self.seed_old()
        with mock.patch.object(generate, "support_index", side_effect=OSError("late failure")):
            rep, error = run_generate(self.root)
        self.assertFalse(rep.ok)
        self.assertEqual(snapshot(self.gen), before, "live generated tree was neither old nor new")
        self.assertIsNone(error)
        self.assertEqual(residue(self.root), [])

    def test_concurrent_source_change_refuses_publish_and_preserves_old_tree(self):
        before = self.seed_old()
        source_dir = os.path.join(self.root, "20 Knowledge")
        os.makedirs(source_dir)
        source = os.path.join(source_dir, "source.md")
        with open(source, "w") as fh:
            fh.write("source before\n")
        original = generate.system_reference
        changed = False

        def owner_edit(*args, **kwargs):
            nonlocal changed
            if not changed:
                changed = True
                with open(source, "a") as fh:
                    fh.write("owner concurrent edit\n")
            return original(*args, **kwargs)

        with mock.patch.object(generate, "system_reference", side_effect=owner_edit):
            rep, error = run_generate(self.root)
        self.assertFalse(rep.ok)
        self.assertIsNone(error)
        self.assertEqual(snapshot(self.gen), before)
        self.assertIn("owner concurrent edit", read_file(source))
        self.assertEqual(residue(self.root), [])

    def test_successful_candidate_digest_record_matches_published_bytes(self):
        rep, error = run_generate(self.root)
        self.assertTrue(rep.ok, rep.errors)
        self.assertIsNone(error)
        with open(os.path.join(self.gen, generate.DIGESTS_NAME), encoding="utf-8") as fh:
            record = json.load(fh)
        self.assertEqual(record["files"], generate.generated_digests(self.root))
        self.assertEqual(residue(self.root), [])

    def test_generate_kill_switch_preserves_exact_live_tree(self):
        before = self.seed_old()
        manifest(self.root, writes=False)
        rep, error = run_generate(self.root)
        self.assertFalse(rep.ok)
        self.assertIsNone(error)
        self.assertEqual(snapshot(self.gen), before)
        self.assertEqual(residue(self.root), [])


class TestPackRemovalTransaction(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="aios-pack-remove-root-")
        self.outside = tempfile.mkdtemp(prefix="aios-pack-remove-outside-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.outside, ignore_errors=True)

    def test_symlinked_pack_root_refuses_without_moving_external_workspace(self):
        external_pack = pack_root(self.outside)
        manifest(self.root)
        os.makedirs(os.path.join(self.root, "Packs"))
        os.symlink(external_pack, os.path.join(self.root, "Packs", "demo"))
        before = snapshot(external_pack)
        rep, error = run_remove(self.root)
        self.assertFalse(rep.ok)
        self.assertEqual(snapshot(external_pack), before)
        self.assertIsNone(error)
        self.assertFalse(os.path.exists(os.path.join(self.root, "90 Archive")))

    def test_symlinked_archive_parent_refuses_without_external_write(self):
        dest = pack_root(self.root)
        os.makedirs(os.path.join(self.root, "90 Archive"))
        os.symlink(self.outside, os.path.join(self.root, "90 Archive", "packs"))
        before = snapshot(dest)
        rep, error = run_remove(self.root)
        self.assertFalse(rep.ok)
        self.assertEqual(snapshot(dest), before)
        self.assertEqual(os.listdir(self.outside), [])
        self.assertIsNone(error)

    def test_concurrent_workspace_edit_is_preserved_live_and_removal_refused(self):
        dest = pack_root(self.root)
        live = os.path.join(dest, "workspace", "one.md")
        changed = False

        def owner_edit(event):
            nonlocal changed
            if event == "after-pack-quarantine" and not changed:
                changed = True
                quarantine = next(
                    name for name in os.listdir(os.path.join(self.root, "Packs"))
                    if name.startswith(".aios-remove-demo-")
                )
                held_live = os.path.join(
                    self.root, "Packs", quarantine, "workspace", "one.md"
                )
                with open(held_live, "a") as fh:
                    fh.write("concurrent owner edit\n")

        with mock.patch.object(pack, "_pack_remove_boundary", side_effect=owner_edit):
            rep, error = run_remove(self.root)
        self.assertFalse(rep.ok)
        self.assertTrue(os.path.isfile(live))
        self.assertIn("concurrent owner edit", read_file(live))
        self.assertIsNone(error)

    def test_second_archive_move_failure_rolls_back_first_move(self):
        dest = pack_root(self.root, work_files=("one.md", "two.md"))
        before = snapshot(dest)
        def fail_after_publish(event):
            if event == "after-archive-publish":
                raise OSError("injected archive publish failure")

        with mock.patch.object(pack, "_pack_remove_boundary", side_effect=fail_after_publish):
            rep, error = run_remove(self.root)
        self.assertFalse(rep.ok)
        self.assertEqual(snapshot(dest), before)
        self.assertIsNone(error)
        self.assertEqual(residue(self.root), [])

    def test_checkpoint_failure_halts_before_pack_archive_or_generated_write(self):
        dest = pack_root(self.root)
        generated = os.path.join(self.root, "System", "Generated")
        os.makedirs(generated, exist_ok=True)
        with open(os.path.join(generated, "known-good.txt"), "w") as fh:
            fh.write("known good\n")
        with open(os.path.join(self.outside, "untouched.txt"), "w") as fh:
            fh.write("outside\n")
        before_root = snapshot(self.root)
        before_outside = snapshot(self.outside)

        def failed_checkpoint(_root, _module, outer, label, **_kwargs):
            self.assertEqual(label, "checkpoint")
            sub = Report(label)
            sub.error("injected checkpoint failure")
            outer.info[label] = "1 errors, 0 warnings"
            return sub

        rep = Report("pack")
        with mock.patch.object(pack, "_sub", side_effect=failed_checkpoint):
            result = pack.run(self.root, pack_args(), rep)

        self.assertIs(result, rep)
        self.assertFalse(rep.ok)
        self.assertTrue(any("checkpoint FAILED" in error for error in rep.errors))
        self.assertEqual(snapshot(self.root), before_root)
        self.assertEqual(snapshot(self.outside), before_outside)
        self.assertTrue(os.path.isdir(dest))
        self.assertFalse(os.path.lexists(os.path.join(self.root, "90 Archive")))
        self.assertEqual(residue(self.root), [])

    def test_successful_remove_preserves_workspace_bytes_in_archive(self):
        dest = pack_root(self.root)
        wanted = read_file(os.path.join(dest, "workspace", "one.md"), "rb")
        rep, error = run_remove(self.root)
        archived = os.path.join(
            self.root, "90 Archive", "packs",
            "demo-" + datetime.date.today().isoformat(), "workspace", "one.md",
        )
        self.assertTrue(rep.ok, rep.errors)
        self.assertIsNone(error)
        self.assertFalse(os.path.lexists(dest))
        self.assertEqual(read_file(archived, "rb"), wanted)

    def test_purge_refuses_symlink_member_and_preserves_external_target(self):
        dest = pack_root(self.root)
        victim = os.path.join(self.outside, "precious.txt")
        with open(victim, "w") as fh:
            fh.write("precious\n")
        os.symlink(victim, os.path.join(dest, "workspace", "linked.md"))
        before = snapshot(dest)
        rep, error = run_remove(self.root, purge=True)
        self.assertFalse(rep.ok)
        self.assertEqual(read_file(victim), "precious\n")
        self.assertEqual(snapshot(dest), before)
        self.assertIsNone(error)

    def test_pack_remove_and_purge_are_blocked_by_cli_kill_switch(self):
        for purge in (False, True):
            with self.subTest(purge=purge):
                case = tempfile.mkdtemp(dir=self.root)
                dest = pack_root(case, writes=False)
                before = snapshot(dest)
                argv = [sys.executable, os.path.join(SCRIPTS, "aios.py"), "pack", "demo",
                        "--remove", "--confirm", "--root", case]
                if purge:
                    argv.insert(-2, "--purge")
                result = subprocess.run(argv, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("kill switch", result.stdout + result.stderr)
                self.assertEqual(snapshot(dest), before)


if __name__ == "__main__":
    unittest.main()
