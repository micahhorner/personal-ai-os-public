"""Seeded-failure tests for health.doc_staleness — the out-of-date-docs check.

Catches stale product docs that did NOT opt in via `x_reviewed_against`
(which is all that derived_doc_drift covers). Run:
    python3 -m unittest System.Tests.scripts.test_doc_staleness
"""
import os, sys, tempfile, shutil, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from cmd import health  # noqa: E402


def _vault(root, sys_ver="1.0.0", changelog_ver="1.0.0", entrypoint="START-HERE.md",
           make_entrypoint=True):
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as f:
        f.write(f"system:\n  system_version: {sys_ver}\n"
                f"entrypoints:\n  human: {entrypoint}\n")
    with open(os.path.join(root, "CHANGELOG.md"), "w") as f:
        f.write(f"# Changelog\n\n## [{changelog_ver}] — 2026-07-13\n\n- seeded.\n")
    if make_entrypoint:
        with open(os.path.join(root, entrypoint), "w") as f:
            f.write("entry\n")


class TestDocStaleness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_docs_no_flags(self):
        _vault(self.tmp, sys_ver="1.6.0", changelog_ver="1.6.0")
        self.assertEqual(health.doc_staleness(self.tmp), [])

    def test_catches_manifest_referencing_missing_file(self):
        _vault(self.tmp, sys_ver="1.6.0", changelog_ver="1.6.0",
               entrypoint="GONE.md", make_entrypoint=False)
        flags = health.doc_staleness(self.tmp)
        self.assertTrue(any("missing file" in m for m in flags))


class TestUserPrivacyCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "80 User"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _manifest(self, role):
        with open(os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
            f.write(f"system:\n  instance_role: {role}\n")

    def test_generic_master_missing_file_is_exempt(self):
        self._manifest("generic-master")
        self.assertIsNone(health.user_privacy_missing(self.tmp))

    def test_personal_instance_missing_file_is_flagged(self):
        self._manifest("personal-instance")
        msg = health.user_privacy_missing(self.tmp)
        self.assertIsNotNone(msg)
        self.assertIn("privacy", msg)

    def test_personal_instance_with_file_passes(self):
        self._manifest("personal-instance")
        with open(os.path.join(self.tmp, "80 User", "privacy-rules.md"), "w") as f:
            f.write("---\nid: doc-user-privacy-rules\n---\nrules\n")
        self.assertIsNone(health.user_privacy_missing(self.tmp))


if __name__ == "__main__":
    unittest.main()
