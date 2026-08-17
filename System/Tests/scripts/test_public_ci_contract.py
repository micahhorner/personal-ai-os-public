"""Public CI proves the distribution without pretending to own private history."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
GATE = ROOT / "System/Scripts/gate.sh"


class TestPublicCIContract(unittest.TestCase):
    def test_actions_are_immutable_and_token_is_read_only(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn(
            "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09", text
        )
        self.assertIn(
            "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1", text
        )
        self.assertNotRegex(text, r"uses:\s+[^\s]+@v[0-9]+(?:\s|$)")

    def test_linux_floor_and_release_macos_are_independent(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('python: "3.9"', text)
        self.assertIn('python: "3.11"', text)
        self.assertIn("fail-fast: false", text)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", text)
        self.assertIn("runs-on: macos-latest", text)

    def test_checkpoint_identity_and_public_scope_are_explicit(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("git config user.name"), 2)
        self.assertEqual(workflow.count("git config user.email"), 2)
        self.assertEqual(workflow.count("AIOS_PUBLIC_CI=1"), 2)
        self.assertNotRegex(workflow, re.compile(r"secrets\.", re.I))

    def test_public_gate_rebuilds_generated_and_names_only_external_scope(self):
        text = GATE.read_text(encoding="utf-8")
        self.assertIn("aios.py generate", text)
        self.assertIn(
            "test_historical_migrations.TestHistoricalMigrationEvidence", text
        )
        self.assertIn(
            "test_release_fault_historical.TestHistoricalInterruptionAndRerun", text
        )
        self.assertIn(
            "test_upgrade_launcher.TestHistoricalLauncherReview.", text
        )
        self.assertNotIn("AIOS_SOURCE_AUTHORITY_REPOSITORY=", text)


if __name__ == "__main__":
    unittest.main()
