"""Wave 5 RED contracts for whole-tree-safe ``aios okf-export`` replacement.

An OKF bundle is one logical artifact.  These tests require it to be built and
self-checked away from the live path, then committed as one concurrency-checked
directory transaction.  A refusal must preserve the prior live tree exactly.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import yaml


VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))

from cmd import okfexport  # noqa: E402
from lib.report import Report  # noqa: E402


BASE = {
    "type": "note",
    "created": "2026-07-14",
    "updated": "2026-07-15",
    "summary": "A summary.",
    "status": "active",
    "verification": "verified",
}


def make_vault(root: str) -> str:
    for rel in ("20 Knowledge", "40 Outputs", os.path.join("System", "Registries")):
        os.makedirs(os.path.join(root, rel), exist_ok=True)
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w", encoding="utf-8") as fh:
        yaml.safe_dump(
            {
                "system": {"name": "Test Vault", "system_version": "0.0.0"},
                "runtime": {"ai_writes_enabled": True},
            },
            fh,
        )
    with open(
        os.path.join(root, "System", "Registries", "folder-registry.yaml"),
        "w",
        encoding="utf-8",
    ) as fh:
        yaml.safe_dump(
            {
                "folders": {
                    "knowledge": {"path": "20 Knowledge"},
                    "outputs": {"path": "40 Outputs"},
                }
            },
            fh,
        )
    return root


def write_note(root: str, name: str = "alpha.md", body: str = "Body one.\n") -> str:
    path = os.path.join(root, "20 Knowledge", name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            "---\n"
            + yaml.safe_dump(dict(BASE, id="note-" + name[:-3]), sort_keys=False)
            + "---\n\n# "
            + name[:-3].title()
            + "\n\n"
            + body
        )
    return path


def export(root: str) -> Report:
    rep = Report("okf-export")
    okfexport.run(
        root,
        SimpleNamespace(target="knowledge", okf_version=None, author=None),
        rep,
    )
    return rep


def tree_bytes(path: str) -> dict[str, bytes]:
    result = {}
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                result[os.path.relpath(full, path)] = fh.read()
    return result


def fake_note(relpath: str, title: str):
    return SimpleNamespace(
        path=relpath,
        relpath=relpath,
        error=None,
        meta=dict(BASE, id="note-" + title.lower(), title=title),
        body=f"# {title}\n\nBody.\n",
    )


class TestOkfExportTransactions(unittest.TestCase):
    def setUp(self):
        self.root = make_vault(tempfile.mkdtemp(prefix="aios-okf-export-root-"))
        self.outside = tempfile.mkdtemp(prefix="aios-okf-export-outside-")
        self.bundle = os.path.join(self.root, "40 Outputs", "okf-knowledge")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.outside, ignore_errors=True)

    def seed_good_bundle(self) -> dict[str, bytes]:
        write_note(self.root)
        rep = export(self.root)
        self.assertTrue(rep.ok, rep.errors)
        return tree_bytes(self.bundle)

    def assert_no_transaction_residue(self):
        residue = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            for name in dirnames + filenames:
                if (name.startswith(".aios-output-") or ".stage" in name
                        or ".backup" in name):
                    residue.append(os.path.relpath(os.path.join(dirpath, name), self.root))
        self.assertEqual(residue, [])

    def test_symlinked_output_root_refuses_without_external_write(self):
        write_note(self.root)
        shutil.rmtree(os.path.join(self.root, "40 Outputs"))
        os.symlink(self.outside, os.path.join(self.root, "40 Outputs"))

        rep = export(self.root)

        self.assertFalse(rep.ok)
        self.assertEqual(os.listdir(self.outside), [])

    def test_late_self_check_failure_preserves_existing_good_bundle(self):
        before = self.seed_good_bundle()
        write_note(self.root, body="A changed source that must not replace the live bundle.\n")

        def reject(_root, _args, report):
            report.error("injected late conformance failure")
            return report

        with mock.patch("cmd.okfcheck.run", side_effect=reject):
            rep = export(self.root)

        self.assertFalse(rep.ok)
        self.assertEqual(tree_bytes(self.bundle), before)
        self.assert_no_transaction_residue()

    def test_destination_parent_moved_outside_before_commit_is_refused(self):
        write_note(self.root)
        outputs = os.path.join(self.root, "40 Outputs")
        moved = os.path.join(self.outside, "moved-outputs")
        original_dump = okfexport._dump
        attacked = False

        def move_parent(meta, version):
            nonlocal attacked
            if not attacked:
                attacked = True
                os.rename(outputs, moved)
                os.symlink(moved, outputs)
            return original_dump(meta, version)

        with mock.patch.object(okfexport, "_dump", side_effect=move_parent):
            rep = export(self.root)

        self.assertFalse(rep.ok)
        escaped = os.path.join(moved, "okf-knowledge", "alpha.md")
        self.assertFalse(os.path.exists(escaped), "export payload escaped with its moved parent")
        self.assert_no_transaction_residue()

    def test_concurrent_existing_bundle_change_is_not_clobbered(self):
        before = self.seed_good_bundle()
        write_note(self.root, "beta.md", "Second concept.\n")
        original_to_okf = okfexport.to_okf
        changed = False

        def concurrent_edit(*args, **kwargs):
            nonlocal changed
            if not changed:
                changed = True
                with open(os.path.join(self.bundle, "owner-concurrent.txt"), "w") as fh:
                    fh.write("owner change\n")
            return original_to_okf(*args, **kwargs)

        with mock.patch.object(okfexport, "to_okf", side_effect=concurrent_edit):
            rep = export(self.root)

        expected = dict(before)
        expected["owner-concurrent.txt"] = b"owner change\n"
        self.assertFalse(rep.ok)
        self.assertEqual(tree_bytes(self.bundle), expected)
        self.assert_no_transaction_residue()

    def test_case_ambiguous_source_tree_is_refused_before_output(self):
        notes = [fake_note("20 Knowledge/A.md", "Alpha"),
                 fake_note("20 Knowledge/a.md", "Beta")]
        with mock.patch.object(okfexport, "iter_markdown", return_value=iter(notes)):
            rep = export(self.root)
        self.assertFalse(rep.ok)
        self.assertFalse(os.path.lexists(self.bundle))

    def test_nfc_ambiguous_source_tree_is_refused_before_output(self):
        notes = [fake_note("20 Knowledge/caf\N{LATIN SMALL LETTER E WITH ACUTE}.md", "Alpha"),
                 fake_note("20 Knowledge/cafe\N{COMBINING ACUTE ACCENT}.md", "Beta")]
        with mock.patch.object(okfexport, "iter_markdown", return_value=iter(notes)):
            rep = export(self.root)
        self.assertFalse(rep.ok)
        self.assertFalse(os.path.lexists(self.bundle))

    def test_source_note_symlink_refuses_and_preserves_existing_bundle(self):
        before = self.seed_good_bundle()
        external_note = os.path.join(self.outside, "external.md")
        with open(external_note, "w", encoding="utf-8") as fh:
            fh.write("---\nid: note-external\ntype: note\nstatus: active\n---\n\nSECRET\n")
        os.symlink(external_note, os.path.join(self.root, "20 Knowledge", "linked.md"))

        rep = export(self.root)

        self.assertFalse(rep.ok)
        self.assertEqual(tree_bytes(self.bundle), before)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixture requires POSIX")
    def test_special_source_note_refuses_and_preserves_existing_bundle(self):
        before = self.seed_good_bundle()
        os.mkfifo(os.path.join(self.root, "20 Knowledge", "hostile.md"))

        rep = export(self.root)

        self.assertFalse(rep.ok)
        self.assertEqual(tree_bytes(self.bundle), before)

    def test_source_change_during_build_refuses_and_preserves_existing_bundle(self):
        before = self.seed_good_bundle()
        source = os.path.join(self.root, "20 Knowledge", "alpha.md")
        original_to_okf = okfexport.to_okf
        changed = False

        def mutate_source(*args, **kwargs):
            nonlocal changed
            result = original_to_okf(*args, **kwargs)
            if not changed:
                changed = True
                with open(source, "a", encoding="utf-8") as fh:
                    fh.write("CONCURRENT SOURCE CHANGE\n")
            return result

        with mock.patch.object(okfexport, "to_okf", side_effect=mutate_source):
            rep = export(self.root)

        self.assertFalse(rep.ok)
        self.assertEqual(tree_bytes(self.bundle), before)
        self.assert_no_transaction_residue()

    def test_failed_first_build_leaves_no_live_bundle_or_staging_residue(self):
        write_note(self.root)

        def reject(_root, _args, report):
            report.error("injected self-check failure")
            return report

        with mock.patch("cmd.okfcheck.run", side_effect=reject):
            rep = export(self.root)

        self.assertFalse(rep.ok)
        self.assertFalse(os.path.lexists(self.bundle))
        self.assert_no_transaction_residue()


if __name__ == "__main__":
    unittest.main()
