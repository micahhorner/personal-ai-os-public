"""Adversarial transaction and descriptor-boundary tests for ``aios import``."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import yaml

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cmd import import_vault as iv                    # noqa: E402
from lib import safepaths as sp                       # noqa: E402
from lib.report import Report                         # noqa: E402
from test_commands import mini_vault                  # noqa: E402
from test_import import write_plan                    # noqa: E402
from test_import_trust_boundaries import fs_state     # noqa: E402


class Args:
    plan = "001-test-import"
    migration = None
    apply = True
    allow_secret_flags = False
    review_days = None
    message = None


def mapped_plan(source, dest="00 Inbox/landed/"):
    return (
        f"source: {json.dumps(source)}\nmode: mapped\nrules:\n"
        f'  - match: "Payload/**"\n    dest: {json.dumps(dest)}\n'
        "    transform: copy\n"
        '  - match: "**"\n    dest: "00 Inbox/quarantine/"\n'
        "    transform: copy\n"
    )


def fake_checkpoint(_root, _args, rep):
    rep.info["checkpoint"] = "test-checkpoint"
    return rep


def fake_validate(_root, _args, rep):
    return rep


class TestImportTransactions(unittest.TestCase):
    def _run_direct(self, vault):
        rep = Report("import")
        with mock.patch.object(iv.ckpt_mod, "run", side_effect=fake_checkpoint), \
             mock.patch.object(iv.v_mod, "run", side_effect=fake_validate):
            iv.run(vault, Args(), rep)
        return rep

    def test_source_ancestor_swap_is_refused_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = mini_vault(os.path.join(tmp, "vault"))
            parent = os.path.join(tmp, "source-parent")
            source = os.path.join(parent, "source")
            os.makedirs(os.path.join(source, "Payload"))
            with open(os.path.join(source, "Payload", "note.md"), "w") as stream:
                stream.write("bound source bytes\n")
            outside = os.path.join(tmp, "outside")
            os.makedirs(os.path.join(outside, "source", "Payload"))
            with open(os.path.join(outside, "source", "Payload", "note.md"), "w") as stream:
                stream.write("attacker bytes\n")
            write_plan(vault, mapped_plan(source))
            before = fs_state(vault)
            held = parent + "-held"
            swapped = False

            def swap(event, index, target):
                nonlocal swapped
                del index, target
                if event == "before-source-read" and not swapped:
                    swapped = True
                    os.rename(parent, held)
                    os.symlink(outside, parent)

            try:
                with mock.patch.object(sp, "_mutation_boundary", side_effect=swap):
                    rep = Report("import"); iv.run(vault, Args(), rep)
                self.assertFalse(rep.ok)
                self.assertIn("ancestor", " ".join(rep.errors).lower())
                self.assertEqual(before, fs_state(vault))
            finally:
                if os.path.islink(parent):
                    os.unlink(parent)
                if os.path.exists(held):
                    os.rename(held, parent)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX special files")
    def test_source_special_file_is_refused_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = mini_vault(os.path.join(tmp, "vault"))
            source = os.path.join(tmp, "source")
            os.makedirs(os.path.join(source, "Payload"))
            os.mkfifo(os.path.join(source, "Payload", "pipe.md"))
            write_plan(vault, mapped_plan(source))
            before = fs_state(vault)
            rep = Report("import"); iv.run(vault, Args(), rep)
            self.assertFalse(rep.ok)
            self.assertIn("not a regular file", " ".join(rep.errors))
            self.assertEqual(before, fs_state(vault))

    def test_destination_parent_moved_outside_receives_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = mini_vault(os.path.join(tmp, "vault"))
            source = os.path.join(tmp, "source")
            os.makedirs(os.path.join(source, "Payload"))
            with open(os.path.join(source, "Payload", "note.md"), "w") as stream:
                stream.write("source\n")
            write_plan(vault, mapped_plan(source))
            landed = os.path.join(vault, "00 Inbox", "landed")
            os.makedirs(landed)
            outside = os.path.join(tmp, "moved-landed")
            swapped = False

            def move(event, index, target):
                nonlocal swapped
                del target
                if event == "before-output-commit" and index == 0 and not swapped:
                    swapped = True
                    os.rename(landed, outside)

            with mock.patch.object(sp, "_mutation_boundary", side_effect=move):
                rep = self._run_direct(vault)
            self.assertFalse(rep.ok)
            self.assertEqual([], os.listdir(outside))

    def test_concurrent_destination_is_not_clobbered(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = mini_vault(os.path.join(tmp, "vault"))
            source = os.path.join(tmp, "source")
            os.makedirs(os.path.join(source, "Payload"))
            with open(os.path.join(source, "Payload", "note.md"), "w") as stream:
                stream.write("source\n")
            write_plan(vault, mapped_plan(source))
            raced = os.path.join(vault, "00 Inbox", "landed", "note.md")
            injected = False

            def race(event, index, target):
                nonlocal injected
                del target
                if event == "before-output-commit" and index == 0 and not injected:
                    injected = True
                    with open(raced, "wb") as stream:
                        stream.write(b"concurrent user bytes")

            with mock.patch.object(sp, "_mutation_boundary", side_effect=race):
                rep = self._run_direct(vault)
            self.assertFalse(rep.ok)
            with open(raced, "rb") as stream:
                self.assertEqual(b"concurrent user bytes", stream.read())

    def test_registry_values_are_safe_yaml_not_structure_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = mini_vault(os.path.join(tmp, "vault"))
            source = os.path.join(tmp, "source")
            os.makedirs(source)
            with open(os.path.join(source, "note.txt"), "w") as stream:
                stream.write("source\n")
            shutil.copy(
                os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                os.path.join(vault, "System", "Registries", "folder-registry.yaml"),
            )
            plan = {
                "source": source,
                "mode": "verbatim",
                "register_folders": [{
                    "id": "foreign-safe",
                    "path": "Foreign: [client]",
                    "purpose": "foreign\ninjected: true",
                    "conventions": "quoted: {still: data}",
                }],
            }
            write_plan(vault, yaml.safe_dump(plan, sort_keys=False))
            rep = self._run_direct(vault)
            self.assertTrue(rep.ok, rep.errors)
            registry = os.path.join(vault, "System", "Registries", "folder-registry.yaml")
            with open(registry, encoding="utf-8") as stream:
                parsed = yaml.safe_load(stream)
            self.assertNotIn("injected", parsed)
            self.assertEqual(
                "foreign\ninjected: true",
                parsed["folders"]["foreign-safe"]["purpose"],
            )

    def test_late_multi_file_fault_restores_exact_prestate_without_residue(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = mini_vault(os.path.join(tmp, "vault"))
            source = os.path.join(tmp, "source")
            os.makedirs(os.path.join(source, "Payload"))
            for name in ("a.md", "b.md"):
                with open(os.path.join(source, "Payload", name), "w") as stream:
                    stream.write(name + "\n")
            shutil.copy(
                os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                os.path.join(vault, "System", "Registries", "folder-registry.yaml"),
            )
            plan = yaml.safe_load(mapped_plan(source))
            plan["register_folders"] = [{"id": "foreign", "path": "Foreign"}]
            write_plan(vault, yaml.safe_dump(plan, sort_keys=False))
            before = fs_state(vault)

            def fail(event, index, target):
                del target
                if event == "after-output-commit" and index == 4:
                    raise OSError("injected late import failure")

            with mock.patch.object(sp, "_mutation_boundary", side_effect=fail):
                rep = self._run_direct(vault)
            self.assertFalse(rep.ok)
            self.assertIn("rolled back", " ".join(rep.errors).lower())
            self.assertEqual(before, fs_state(vault))
            leftovers = [rel for rel in fs_state(vault) if ".aios-" in rel]
            self.assertEqual([], leftovers)


if __name__ == "__main__":
    unittest.main()
