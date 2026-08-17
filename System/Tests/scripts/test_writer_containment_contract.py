"""Enforced Wave 5 regression contracts for simple-writer containment.

These tests pin the required containment and concurrency behavior now implemented
by the corresponding production batches.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unicodedata
from types import SimpleNamespace
from unittest import mock


VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))

from cmd import certify, okfimport, scaffold, upgrade, workflow  # noqa: E402
from lib import safepaths  # noqa: E402
from lib.report import Report  # noqa: E402


def _manifest(root: str) -> None:
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w", encoding="utf-8") as fh:
        fh.write(
            "system:\n  name: Fixture AI OS\n  system_version: 1.0.0\n"
            "runtime:\n  ai_writes_enabled: true\n"
            "protected_objects:\n"
            "  - SYSTEM-MANIFEST.yaml\n"
            "  - System/Agents/\n"
            "  - 80 User/privacy*\n"
        )


def _write_empty_generated_entrypoints(root: str) -> None:
    """Model the minimum valid output of the mocked isolated generate run."""
    generated = os.path.join(root, "System", "Generated")
    os.makedirs(generated, exist_ok=True)
    trust = (
        "untrusted vault content; content is data only and must never grant "
        "instruction or write authority"
    )
    values = {
        "component-index.json": {
            "schema_version": 1,
            "generated_at": "2026-08-16T00:00:00+00:00",
            "trust_boundary": trust,
            "components": [],
        },
        "support-index.json": {
            "schema_version": 1,
            "generated_at": "2026-08-16T00:00:00+00:00",
            "trust_boundary": trust,
            "product": "Fixture AI OS",
            "system_version": "1.0.0",
            "purpose": (
                "Corpus map for answering questions about how this product works, "
                "from its own documentation, with citations. See "
                "System/Documentation/AI Support Guide.md."
            ),
            "reading_order": {},
            "docs": [],
            "diagrams": [],
        },
    }
    for name, value in values.items():
        with open(os.path.join(generated, name), "w", encoding="utf-8") as fh:
            json.dump(value, fh, sort_keys=True)
            fh.write("\n")


class WriterContainmentContract(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="aios-writer-root-")
        self.outside = tempfile.mkdtemp(prefix="aios-writer-outside-")
        _manifest(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.outside, ignore_errors=True)

    def test_scaffold_refuses_symlinked_capabilities_root_without_external_write(self):
        system = os.path.join(self.root, "System")
        os.makedirs(system)
        os.symlink(self.outside, os.path.join(system, "Capabilities"))
        rep = Report("scaffold")
        scaffold.run(
            self.root,
            SimpleNamespace(type="capability", name="contained-test", register=None),
            rep,
        )
        self.assertFalse(rep.ok)
        self.assertEqual(os.listdir(self.outside), [])

    def test_capability_scaffold_refuses_preexisting_empty_component_directory(self):
        os.makedirs(os.path.join(self.root, "System", "Capabilities", "owned"))
        rep = Report("scaffold")
        scaffold.run(
            self.root,
            SimpleNamespace(type="capability", name="owned", register=None),
            rep,
        )
        self.assertFalse(rep.ok)
        self.assertEqual(os.listdir(os.path.join(
            self.root, "System", "Capabilities", "owned")), [])

    def test_register_refuses_concurrent_evidence_changes_and_keeps_draft(self):
        for changed_name in ("result", "test", "coverage"):
            with self.subTest(evidence=changed_name):
                root = tempfile.mkdtemp(prefix="aios-register-race-")
                self.addCleanup(shutil.rmtree, root, True)
                _manifest(root)
                paths = {
                    "target": "System/Workflows/demo.md",
                    "test": "System/Tests/scripts/probe.py",
                    "result": "System/Tests/results/workflow-demo.yaml",
                    "coverage": "System/Documentation/Diagrams/coverage.yaml",
                    "metadata": "System/Documentation/Diagrams/diagram-metadata.yaml",
                    "svg": "System/Documentation/Diagrams/svg/demo.svg",
                }
                for rel in paths.values():
                    os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
                with open(os.path.join(root, paths["target"]), "w", encoding="utf-8") as fh:
                    fh.write("---\nid: workflow-demo\ntype: workflow\nstatus: draft\n"
                             "version: 0.1.0\ntests: [System/Tests/scripts/probe.py]\n---\n")
                with open(os.path.join(root, paths["test"]), "w", encoding="utf-8") as fh:
                    fh.write("# passing probe\n")
                with open(os.path.join(root, paths["result"]), "w", encoding="utf-8") as fh:
                    fh.write("component: workflow-demo\nversion: 0.1.0\nresult: pass\n")
                with open(os.path.join(root, paths["coverage"]), "w", encoding="utf-8") as fh:
                    fh.write("diagrams: {'01': {file: demo.svg}}\n"
                             "components: {workflow-demo: ['01']}\n")
                with open(os.path.join(root, paths["metadata"]), "w", encoding="utf-8") as fh:
                    fh.write("'01': {description: demo}\n")
                with open(os.path.join(root, paths["svg"]), "w", encoding="utf-8") as fh:
                    fh.write("<svg/>\n")
                changed_path = os.path.join(root, paths[changed_name])
                changed = False

                def race(event, _index, _target):
                    nonlocal changed
                    if event == "before-output-commit" and not changed:
                        changed = True
                        with open(changed_path, "a", encoding="utf-8") as fh:
                            fh.write("# concurrent evidence edit\n")

                rep = Report("register")
                with mock.patch.object(safepaths, "_mutation_boundary", side_effect=race):
                    scaffold.register(root, "workflow-demo", rep)
                self.assertFalse(rep.ok)
                with open(os.path.join(root, paths["target"]), encoding="utf-8") as fh:
                    self.assertIn("status: draft", fh.read())

    def test_register_refuses_agent_contract_even_with_passing_evidence(self):
        paths = {
            "target": "System/Agents/demo/AGENT.md",
            "test": "System/Tests/scripts/agent-demo.py",
            "result": "System/Tests/results/agent-demo.yaml",
            "coverage": "System/Documentation/Diagrams/coverage.yaml",
            "metadata": "System/Documentation/Diagrams/diagram-metadata.yaml",
            "svg": "System/Documentation/Diagrams/svg/demo.svg",
        }
        for rel in paths.values():
            os.makedirs(os.path.dirname(os.path.join(self.root, rel)), exist_ok=True)
        target = os.path.join(self.root, paths["target"])
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(
                "---\nid: agent-demo\ntype: agent\ncomponent_type: agent\n"
                "status: draft\nversion: 1.0.0\n"
                "tests: [System/Tests/scripts/agent-demo.py]\n---\n"
            )
        with open(os.path.join(self.root, paths["test"]), "w", encoding="utf-8") as fh:
            fh.write("# passing agent test\n")
        with open(os.path.join(self.root, paths["result"]), "w", encoding="utf-8") as fh:
            fh.write("component: agent-demo\nversion: 1.0.0\nresult: pass\n")
        with open(os.path.join(self.root, paths["coverage"]), "w", encoding="utf-8") as fh:
            fh.write("diagrams: {'01': {file: demo.svg}}\ncomponents: {agent-demo: ['01']}\n")
        with open(os.path.join(self.root, paths["metadata"]), "w", encoding="utf-8") as fh:
            fh.write("'01': {description: demo}\n")
        with open(os.path.join(self.root, paths["svg"]), "w", encoding="utf-8") as fh:
            fh.write("<svg/>\n")
        with open(target, "rb") as fh:
            before = fh.read()

        rep = Report("register")
        scaffold.register(self.root, "agent-demo", rep)

        self.assertFalse(rep.ok)
        self.assertIn("developer/amendment lane", " ".join(rep.errors))
        with open(target, "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_safe_relative_path_rejects_non_nfc_spelling(self):
        decomposed = unicodedata.normalize("NFD", "Café.md")
        with self.assertRaisesRegex(safepaths.SafePathError, "NFC"):
            safepaths.safe_relative_path(f"00 Inbox/{decomposed}")

    def test_tmp_alias_is_only_rewritten_on_macos(self):
        with mock.patch.object(safepaths.sys, "platform", "linux"):
            self.assertEqual(safepaths._canonical_platform_path("/tmp/example"), "/tmp/example")
        with mock.patch.object(safepaths.sys, "platform", "darwin"):
            self.assertEqual(safepaths._canonical_platform_path("/tmp/example"),
                             "/private/tmp/example")

    def test_upgrade_make_baseline_refuses_symlink_without_external_write(self):
        os.makedirs(os.path.join(self.root, "System"), exist_ok=True)
        with open(
            os.path.join(self.root, "SYSTEM-MANIFEST.yaml"),
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write(
                "system:\n  instance_role: generic-master\n"
                "  system_version: 1.64.1\n"
            )
        outside = os.path.join(self.outside, "baseline.json")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write("outside sentinel\n")
        os.symlink(outside, os.path.join(
            self.root, "System", ".baseline-manifest.json"))

        rep = Report("baseline")
        upgrade.make_baseline(self.root, rep)

        self.assertFalse(rep.ok)
        with open(outside, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "outside sentinel\n")

    def test_workflow_refuses_symlinked_logs_root_without_external_write(self):
        os.makedirs(os.path.join(self.root, "System", "Registries"), exist_ok=True)
        with open(
            os.path.join(self.root, "System", "Registries", "freshness.yaml"),
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write("enforced_since: 2026-01-01\n")
        os.makedirs(os.path.join(self.root, "System", "Workflows"), exist_ok=True)
        with open(
            os.path.join(self.root, "System", "Workflows", "weekly.md"),
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write(
                "---\nid: workflow-weekly\ntype: workflow\nstatus: active\n"
                "cadence_days: 7\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
                "summary: weekly\n---\n\nrun\n"
            )
        os.symlink(self.outside, os.path.join(self.root, "System", "Logs"))
        rep = Report("workflow")
        workflow.run(self.root, SimpleNamespace(ran="workflow-weekly"), rep)
        self.assertFalse(rep.ok)
        self.assertEqual(os.listdir(self.outside), [])

    def test_okf_import_refuses_symlinked_sources_root_without_external_write(self):
        os.makedirs(os.path.join(self.root, "System", "Registries"), exist_ok=True)
        with open(
            os.path.join(self.root, "System", "Registries", "folder-registry.yaml"),
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write("folders:\n  sources:\n    path: 30 Sources\n")
        os.symlink(self.outside, os.path.join(self.root, "30 Sources"))
        bundle = tempfile.mkdtemp(prefix="aios-okf-bundle-")
        self.addCleanup(shutil.rmtree, bundle, True)
        with open(os.path.join(bundle, "concept.md"), "w", encoding="utf-8") as fh:
            fh.write("---\ntype: Concept\ntitle: Example\n---\n\nbody\n")
        rep = Report("okf-import")
        okfimport.run(self.root, SimpleNamespace(target=bundle), rep)
        self.assertFalse(rep.ok)
        self.assertEqual(os.listdir(self.outside), [])

    def _regular_okf_root(self):
        os.makedirs(os.path.join(self.root, "System", "Registries"), exist_ok=True)
        with open(
            os.path.join(self.root, "System", "Registries", "folder-registry.yaml"),
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write("folders:\n  sources:\n    path: 30 Sources\n")
        os.makedirs(os.path.join(self.root, "30 Sources"), exist_ok=True)

    def _bundle(self, files):
        bundle = tempfile.mkdtemp(prefix="aios-okf-bundle-")
        self.addCleanup(shutil.rmtree, bundle, True)
        for rel, text in files.items():
            path = os.path.join(bundle, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        return bundle

    @staticmethod
    def _concept(title="Example", body="body"):
        return f"---\ntype: Concept\ntitle: {title}\n---\n\n{body}\n"

    def test_okf_import_rolls_back_every_output_after_mid_commit_failure(self):
        self._regular_okf_root()
        bundle = self._bundle({
            "one.md": self._concept("One"),
            "nested/two.md": self._concept("Two"),
        })
        original_boundary = safepaths._mutation_boundary

        def fail_after_first(event, index, target):
            if event == "after-output-commit" and index == 0:
                raise OSError("injected commit failure")
            return original_boundary(event, index, target)

        rep = Report("okf-import")
        with mock.patch.object(safepaths, "_mutation_boundary", fail_after_first):
            okfimport.run(self.root, SimpleNamespace(target=bundle), rep)
        self.assertFalse(rep.ok)
        destination = os.path.join(
            self.root, "30 Sources", "OKF " + os.path.basename(bundle))
        self.assertFalse(os.path.lexists(destination))

    def test_okf_import_detects_source_change_and_leaves_source_untouched(self):
        self._regular_okf_root()
        bundle = self._bundle({"one.md": self._concept("One")})
        source = os.path.join(bundle, "one.md")
        original_boundary = safepaths._mutation_boundary
        changed = False

        def change_source(event, index, target):
            nonlocal changed
            if event == "before-output-commit" and not changed:
                changed = True
                with open(source, "a", encoding="utf-8") as fh:
                    fh.write("concurrent source edit\n")
            return original_boundary(event, index, target)

        rep = Report("okf-import")
        with mock.patch.object(safepaths, "_mutation_boundary", change_source):
            okfimport.run(self.root, SimpleNamespace(target=bundle), rep)
        self.assertFalse(rep.ok)
        with open(source, encoding="utf-8") as fh:
            self.assertIn("concurrent source edit", fh.read())
        destination = os.path.join(
            self.root, "30 Sources", "OKF " + os.path.basename(bundle))
        self.assertFalse(os.path.lexists(destination))

    def test_okf_import_sanitized_collision_is_zero_write(self):
        self._regular_okf_root()
        bundle = self._bundle({
            "same?.md": self._concept("One"),
            "same*.md": self._concept("Two"),
        })
        rep = Report("okf-import")
        okfimport.run(self.root, SimpleNamespace(target=bundle), rep)
        self.assertFalse(rep.ok)
        destination = os.path.join(
            self.root, "30 Sources", "OKF " + os.path.basename(bundle))
        self.assertFalse(os.path.lexists(destination))

    def test_okf_import_zero_valid_concepts_leaves_no_directory(self):
        self._regular_okf_root()
        bundle = self._bundle({"invalid.md": "no frontmatter\n"})
        rep = Report("okf-import")
        okfimport.run(self.root, SimpleNamespace(target=bundle), rep)
        self.assertFalse(rep.ok)
        destination = os.path.join(
            self.root, "30 Sources", "OKF " + os.path.basename(bundle))
        self.assertFalse(os.path.lexists(destination))

    def test_okf_import_refuses_symlink_member(self):
        self._regular_okf_root()
        bundle = self._bundle({"one.md": self._concept("One")})
        os.symlink(os.path.join(bundle, "one.md"), os.path.join(bundle, "alias.md"))
        rep = Report("okf-import")
        okfimport.run(self.root, SimpleNamespace(target=bundle), rep)
        self.assertFalse(rep.ok)
        destination = os.path.join(
            self.root, "30 Sources", "OKF " + os.path.basename(bundle))
        self.assertFalse(os.path.lexists(destination))

    def test_certify_probe_does_not_overwrite_a_concurrent_generated_edit(self):
        generated = os.path.join(self.root, "System", "Generated")
        os.makedirs(generated, exist_ok=True)
        live = os.path.join(generated, "index.md")
        with open(live, "w", encoding="utf-8") as fh:
            fh.write("before\n")
        os.makedirs(os.path.join(self.root, "System", "Scripts"), exist_ok=True)
        with open(
            os.path.join(self.root, "System", "Scripts", "aios.py"),
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write("# fixture\n")

        calls = 0

        def concurrent_generate(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                with open(live, "w", encoding="utf-8") as fh:
                    fh.write("concurrent-owner-edit\n")
            return subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(certify.subprocess, "run", side_effect=concurrent_generate):
            rep = certify._idempotency(self.root)

        self.assertFalse(rep.ok)
        with open(live, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "concurrent-owner-edit\n")

    def test_certify_runs_generate_only_in_an_isolated_copy(self):
        generated = os.path.join(self.root, "System", "Generated")
        os.makedirs(generated, exist_ok=True)
        live = os.path.join(generated, "index.md")
        with open(live, "w", encoding="utf-8") as fh:
            fh.write("live\n")
        os.makedirs(os.path.join(self.root, "System", "Scripts"), exist_ok=True)
        with open(
            os.path.join(self.root, "System", "Scripts", "aios.py"),
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write("# fixture\n")
        working_directories = []

        def isolated_generate(*_args, **kwargs):
            working_directories.append(kwargs["cwd"])
            _write_empty_generated_entrypoints(kwargs["cwd"])
            with open(
                os.path.join(kwargs["cwd"], "System", "Generated", "index.md"),
                "w",
                encoding="utf-8",
            ) as fh:
                fh.write("isolated\n")
            return subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(certify.subprocess, "run", side_effect=isolated_generate):
            rep = certify._idempotency(self.root)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(len(working_directories), 2)
        self.assertTrue(all(path != self.root for path in working_directories))
        with open(live, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "live\n")

    def test_certify_does_not_copy_irrelevant_binary_attachment(self):
        generated = os.path.join(self.root, "System", "Generated")
        os.makedirs(generated, exist_ok=True)
        with open(os.path.join(generated, "index.md"), "w", encoding="utf-8") as fh:
            fh.write("live\n")
        os.makedirs(os.path.join(self.root, "System", "Scripts"), exist_ok=True)
        with open(os.path.join(self.root, "System", "Scripts", "aios.py"),
                  "w", encoding="utf-8") as fh:
            fh.write("# fixture\n")
        attachment = os.path.join(self.root, "30 Sources", "Attachments", "large.bin")
        os.makedirs(os.path.dirname(attachment), exist_ok=True)
        with open(attachment, "wb") as fh:
            fh.seek(32 * 1024 * 1024)
            fh.write(b"x")
        observed = []

        def isolated_generate(*_args, **kwargs):
            _write_empty_generated_entrypoints(kwargs["cwd"])
            copied = os.path.join(
                kwargs["cwd"], "30 Sources", "Attachments", "large.bin")
            observed.append(os.path.lexists(copied))
            return subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(certify.subprocess, "run", side_effect=isolated_generate):
            rep = certify._idempotency(self.root)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(observed, [False, False])
        self.assertEqual(os.path.getsize(attachment), 32 * 1024 * 1024 + 1)

    def test_certify_detects_changed_relevant_note_without_overwriting_it(self):
        generated = os.path.join(self.root, "System", "Generated")
        os.makedirs(generated, exist_ok=True)
        with open(os.path.join(generated, "index.md"), "w", encoding="utf-8") as fh:
            fh.write("live\n")
        os.makedirs(os.path.join(self.root, "System", "Scripts"), exist_ok=True)
        with open(os.path.join(self.root, "System", "Scripts", "aios.py"),
                  "w", encoding="utf-8") as fh:
            fh.write("# fixture\n")
        note = os.path.join(self.root, "20 Knowledge", "live.md")
        os.makedirs(os.path.dirname(note), exist_ok=True)
        with open(note, "w", encoding="utf-8") as fh:
            fh.write("before\n")
        calls = 0

        def concurrent_note_edit(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                with open(note, "w", encoding="utf-8") as fh:
                    fh.write("concurrent relevant edit\n")
            return subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(certify.subprocess, "run", side_effect=concurrent_note_edit):
            rep = certify._idempotency(self.root)
        self.assertFalse(rep.ok)
        with open(note, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "concurrent relevant edit\n")

    def test_certify_copies_freshness_ledger_only_into_isolated_probe(self):
        generated = os.path.join(self.root, "System", "Generated")
        os.makedirs(generated, exist_ok=True)
        with open(os.path.join(generated, "index.md"), "w", encoding="utf-8") as fh:
            fh.write("live\n")
        os.makedirs(os.path.join(self.root, "System", "Scripts"), exist_ok=True)
        with open(os.path.join(self.root, "System", "Scripts", "aios.py"),
                  "w", encoding="utf-8") as fh:
            fh.write("# fixture\n")
        ledger = os.path.join(
            self.root, "System", "Logs", "freshness-ledger.json")
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        seeded = b'{"schema":1,"notes":{"20 Knowledge/a.md":{"h":"seed"}}}\n'
        with open(ledger, "wb") as fh:
            fh.write(seeded)
        observed = []

        def isolated_generate(*_args, **kwargs):
            _write_empty_generated_entrypoints(kwargs["cwd"])
            copied = os.path.join(
                kwargs["cwd"], "System", "Logs", "freshness-ledger.json")
            with open(copied, "rb") as fh:
                observed.append(fh.read())
            return subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(certify.subprocess, "run", side_effect=isolated_generate):
            rep = certify._idempotency(self.root)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(observed, [seeded, seeded])
        with open(ledger, "rb") as fh:
            self.assertEqual(fh.read(), seeded)


if __name__ == "__main__":
    unittest.main()
