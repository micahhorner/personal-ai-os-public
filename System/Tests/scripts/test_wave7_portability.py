"""Wave 7 vendor-neutral boot and unearned-runtime-evidence contracts."""
from __future__ import annotations

import os
import unittest

import yaml


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


class TestVendorNeutralBoot(unittest.TestCase):
    def test_root_agents_pointer_names_the_complete_authority_chain(self):
        with open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8") as stream:
            text = stream.read()
        for required in (
            "SYSTEM-MANIFEST.yaml",
            "reading_order.ai",
            "System/Runtime/Task Router.yaml",
            "Runtime Kernel",
            "active runtime profile",
            "runtime.ai_writes_enabled",
        ):
            self.assertIn(required, text)
        self.assertNotIn("Claude", text)
        self.assertNotIn("Codex", text)

    def test_vendor_adapter_remains_a_thin_pointer(self):
        with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as stream:
            text = stream.read()
        self.assertIn("adapter pointer", text)
        self.assertIn("SYSTEM-MANIFEST.yaml", text)


class TestCodexProfile(unittest.TestCase):
    def test_codex_profile_ships_uncertified_and_at_the_default_ceiling(self):
        path = os.path.join(ROOT, "System", "Runtime Profiles", "codex.yaml")
        with open(path, encoding="utf-8") as stream:
            profile = yaml.safe_load(stream)
        self.assertEqual(profile["id"], "runtime-codex")
        self.assertEqual(profile["provider"], "openai")
        self.assertEqual(profile["autonomy_level"], "L2")
        self.assertEqual(profile["certifications"], {})
        self.assertIsNone(profile["last_tested"])
        self.assertEqual(profile["structured_output_reliability"], "untested")
        self.assertEqual(profile["file_write_reliability"], "untested")


class TestContributorParity(unittest.TestCase):
    def test_readme_contributing_and_ci_share_the_product_gate(self):
        paths = ("README.md", "CONTRIBUTING.md", ".github/workflows/ci.yml")
        for relative in paths:
            with self.subTest(path=relative):
                with open(os.path.join(ROOT, relative), encoding="utf-8") as stream:
                    self.assertIn("System/Scripts/gate.sh", stream.read())

    def test_setup_and_gate_are_fail_fast_and_product_local(self):
        with open(os.path.join(ROOT, "System", "Scripts", "gate.sh"), encoding="utf-8") as stream:
            gate = stream.read()
        self.assertIn("set -euo pipefail", gate)
        self.assertIn("run_strict_tests.py", gate)
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as stream:
            self.assertIn("python3 System/Scripts/setup.py", stream.read())


if __name__ == "__main__":
    unittest.main()
