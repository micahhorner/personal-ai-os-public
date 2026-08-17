"""Wave 5 contracts for generate's final freshness-state transaction."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from test_commands import Args, CAP_SKILL, mini_vault
from test_generate_skills_transactions import bytes_snapshot
from cmd import generate
from lib import freshness, safepaths
from lib.report import Report


REGISTRY = """schema_version: 1.0.0
enforced_since: null
horizons_days: {note: 90}
exempt_types: [source]
dispositions: [changes, no-impact]
"""


def _read_text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _read_bytes(path):
    with open(path, "rb") as stream:
        return stream.read()


class TestGenerateFreshnessTransaction(unittest.TestCase):
    def setUp(self):
        self.outer = tempfile.mkdtemp(prefix="aios-generate-freshness-")
        self.root = mini_vault(os.path.join(self.outer, "vault"))

    def tearDown(self):
        shutil.rmtree(self.outer)

    def personal(self):
        manifest = os.path.join(self.root, "SYSTEM-MANIFEST.yaml")
        with open(manifest, encoding="utf-8") as stream:
            text = stream.read()
        with open(manifest, "w", encoding="utf-8") as stream:
            stream.write(text.replace("instance_role: generic-master",
                                      "instance_role: personal-instance"))

    def install_registry(self, text=REGISTRY):
        path = os.path.join(self.root, freshness.REGISTRY_REL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(text)
        return path

    def note(self):
        path = os.path.join(self.root, "20 Knowledge", "Fresh.md")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(
                "---\nid: note-fresh\ntype: note\nstatus: active\n"
                "created: 2026-08-09\nupdated: 2026-08-09\nsummary: fresh\n"
                "---\n\nFresh body.\n"
            )
        return path

    def run_generate(self):
        report = Report("generate")
        generate.run(self.root, Args(), report)
        return report

    def seed_publish_surfaces(self):
        generated = os.path.join(self.root, "System", "Generated")
        os.makedirs(generated, exist_ok=True)
        with open(os.path.join(generated, "old.bin"), "wb") as stream:
            stream.write(b"old generated exact")
        cap = os.path.join(self.root, "System", "Capabilities", "cap-alpha")
        os.makedirs(cap)
        with open(os.path.join(cap, "SKILL.md"), "w", encoding="utf-8") as stream:
            stream.write(CAP_SKILL.format(name="cap-alpha", status="active"))
        skill = os.path.join(self.root, ".claude", "skills", "aios-cap-alpha")
        os.makedirs(skill)
        with open(os.path.join(skill, "SKILL.md"), "w", encoding="utf-8") as stream:
            stream.write(generate.EMIT_MARKER + "\nold projection exact\n")
        return generated, os.path.join(self.root, ".claude", "skills")

    def test_generic_master_registry_creates_neither_logs_nor_ledger(self):
        registry = self.install_registry()
        before = _read_text(registry)

        report = self.run_generate()

        self.assertTrue(report.ok, report.errors)
        self.assertFalse(os.path.lexists(os.path.join(self.root, "System", "Logs")))
        self.assertEqual(before, _read_text(registry))

    def test_absent_registry_on_personal_instance_creates_no_freshness_state(self):
        self.personal()
        self.note()

        report = self.run_generate()

        self.assertTrue(report.ok, report.errors)
        self.assertFalse(os.path.lexists(os.path.join(self.root, "System", "Logs")))
        self.assertFalse(os.path.lexists(os.path.join(self.root, freshness.LEDGER_REL)))

    def test_malformed_registry_refuses_before_generated_or_skills_publish(self):
        self.personal()
        self.install_registry("horizons_days: [not, a, mapping]\n")
        generated, skills = self.seed_publish_surfaces()
        before_generated, before_skills = bytes_snapshot(generated), bytes_snapshot(skills)

        report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertEqual(before_generated, bytes_snapshot(generated))
        self.assertEqual(before_skills, bytes_snapshot(skills))
        self.assertFalse(os.path.lexists(os.path.join(self.root, "System", "Logs")))

    def test_malformed_ledger_refuses_before_generated_or_skills_publish(self):
        self.personal()
        self.install_registry()
        generated, skills = self.seed_publish_surfaces()
        ledger = os.path.join(self.root, freshness.LEDGER_REL)
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        with open(ledger, "w", encoding="utf-8") as stream:
            stream.write("not json\n")
        before_generated, before_skills = bytes_snapshot(generated), bytes_snapshot(skills)

        report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertEqual(before_generated, bytes_snapshot(generated))
        self.assertEqual(before_skills, bytes_snapshot(skills))
        self.assertEqual("not json\n", _read_text(ledger))

    def test_orphan_malformed_ledger_is_validated_even_without_registry(self):
        self.personal()
        generated, skills = self.seed_publish_surfaces()
        ledger = os.path.join(self.root, freshness.LEDGER_REL)
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        with open(ledger, "w", encoding="utf-8") as stream:
            stream.write("orphan malformed ledger\n")
        before_generated, before_skills = bytes_snapshot(generated), bytes_snapshot(skills)

        report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertEqual(before_generated, bytes_snapshot(generated))
        self.assertEqual(before_skills, bytes_snapshot(skills))
        self.assertEqual("orphan malformed ledger\n",
                         _read_text(ledger))

    def test_registry_and_ledger_commit_together_preserving_other_logs(self):
        self.personal()
        registry = self.install_registry()
        self.note()
        logs = os.path.join(self.root, "System", "Logs")
        os.makedirs(logs)
        event_log = os.path.join(logs, "freshness-log.jsonl")
        unrelated = os.path.join(logs, "foreign.bin")
        with open(event_log, "wb") as stream:
            stream.write(b'{"event":"owner_exact"}\n')
        with open(unrelated, "wb") as stream:
            stream.write(b"\x00unrelated\xff")

        report = self.run_generate()

        self.assertTrue(report.ok, report.errors)
        self.assertNotIn("enforced_since: null", _read_text(registry))
        with open(os.path.join(self.root, freshness.LEDGER_REL), encoding="utf-8") as stream:
            ledger = json.load(stream)
        self.assertIn("20 Knowledge/Fresh.md", ledger["notes"])
        self.assertEqual(b'{"event":"owner_exact"}\n', _read_bytes(event_log))
        self.assertEqual(b"\x00unrelated\xff", _read_bytes(unrelated))

    def test_concurrent_ledger_edit_refuses_and_restores_registry(self):
        self.personal()
        registry = self.install_registry()
        self.note()
        ledger = os.path.join(self.root, freshness.LEDGER_REL)
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        with open(ledger, "w", encoding="utf-8") as stream:
            stream.write('{"schema":1,"notes":{}}\n')
        registry_before = _read_text(registry)
        changed = False

        def race(event, index, _target):
            nonlocal changed
            if event == "before-output-commit" and index == 0 and not changed:
                changed = True
                with open(ledger, "w", encoding="utf-8") as stream:
                    stream.write('{"schema":1,"notes":{"owner":{}}}\n')

        with mock.patch.object(safepaths, "_mutation_boundary", side_effect=race):
            report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertEqual(registry_before, _read_text(registry))
        self.assertEqual('{"schema":1,"notes":{"owner":{}}}\n',
                         _read_text(ledger))

    def test_mid_commit_failure_rolls_registry_and_ledger_back_together(self):
        self.personal()
        registry = self.install_registry()
        self.note()
        ledger = os.path.join(self.root, freshness.LEDGER_REL)
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        with open(ledger, "w", encoding="utf-8") as stream:
            stream.write('{"schema":1,"notes":{}}\n')
        before = (_read_text(registry), _read_text(ledger))

        def fail(event, index, _target):
            if event == "after-output-commit" and index == 0:
                raise OSError("injected freshness commit failure")

        with mock.patch.object(safepaths, "_mutation_boundary", side_effect=fail):
            report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertEqual(before, (_read_text(registry), _read_text(ledger)))

    def test_symlinked_ledger_refuses_without_external_write_or_publish(self):
        self.personal()
        self.install_registry()
        generated, skills = self.seed_publish_surfaces()
        outside = os.path.join(self.outer, "outside-ledger.json")
        with open(outside, "w", encoding="utf-8") as stream:
            stream.write('{"schema":1,"notes":{}}\n')
        ledger = os.path.join(self.root, freshness.LEDGER_REL)
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        os.symlink(outside, ledger)
        before_generated, before_skills = bytes_snapshot(generated), bytes_snapshot(skills)

        report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertEqual(before_generated, bytes_snapshot(generated))
        self.assertEqual(before_skills, bytes_snapshot(skills))
        self.assertEqual('{"schema":1,"notes":{}}\n',
                         _read_text(outside))

    def test_symlinked_logs_root_refuses_before_publish_when_ledger_is_absent(self):
        self.personal()
        self.install_registry()
        generated, skills = self.seed_publish_surfaces()
        outside = os.path.join(self.outer, "outside-logs")
        os.makedirs(outside)
        with open(os.path.join(outside, "sentinel.bin"), "wb") as stream:
            stream.write(b"outside exact")
        os.symlink(outside, os.path.join(self.root, "System", "Logs"))
        before_generated, before_skills = bytes_snapshot(generated), bytes_snapshot(skills)

        report = self.run_generate()

        self.assertFalse(report.ok)
        self.assertEqual(before_generated, bytes_snapshot(generated))
        self.assertEqual(before_skills, bytes_snapshot(skills))
        self.assertEqual(["sentinel.bin"], os.listdir(outside))
        self.assertEqual(b"outside exact",
                         _read_bytes(os.path.join(outside, "sentinel.bin")))


if __name__ == "__main__":
    unittest.main()
