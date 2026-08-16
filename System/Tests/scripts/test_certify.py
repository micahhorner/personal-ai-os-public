"""Seeded-failure tests for the certify behavioral assertions (Wave 2 gate).

Each behavioral check must (a) pass a clean vault and (b) catch a planted break.
A check that can only ever say PASS certifies nothing. Run:
    python3 -m unittest System.Tests.scripts.test_certify

Component-contract and frontmatter checks are NOT tested here — `aios validate`
owns those; certify no longer duplicates them (see CHECK-MAP.md).
"""
import hashlib, json, os, sys, tempfile, shutil, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from cmd import certify  # noqa: E402


def _clean_vault(root):
    """Minimal vault where every behavioral check passes."""
    os.makedirs(os.path.join(root, "System", "Scripts"), exist_ok=True)
    os.makedirs(os.path.join(root, "System", "Agents"), exist_ok=True)
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as f:
        f.write("runtime:\n  ai_writes_enabled: true\n"
                "protected_objects:\n  - SYSTEM-MANIFEST.yaml\n  - System/Agents/\n")
    with open(os.path.join(root, "System", "Scripts", "aios.py"), "w") as f:
        f.write("WRITE_COMMANDS = set()\nai_writes_enabled\n")


class TestGovernanceSeeded(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _clean_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_vault_passes(self):
        self.assertTrue(certify._governance(self.tmp).ok)

    def test_catches_pii_email(self):
        # synthetic, non-allowlisted, clearly-fake address — never real PII
        with open(os.path.join(self.tmp, "leak.md"), "w") as f:
            f.write("contact the owner at planted.leak@acme-corp-fake.com for details")
        rep = certify._governance(self.tmp)
        self.assertFalse(rep.ok)
        self.assertTrue(any("PII" in e for e in rep.errors))

    def test_catches_missing_kill_switch(self):
        with open(os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
            f.write("protected_objects:\n  - SYSTEM-MANIFEST.yaml\n  - System/Agents/\n")
        rep = certify._governance(self.tmp)
        self.assertFalse(rep.ok)
        self.assertTrue(any("kill switch" in e for e in rep.errors))

    def test_catches_missing_protected_object(self):
        with open(os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
            f.write("runtime:\n  ai_writes_enabled: true\n"
                    "protected_objects:\n  - System/Agents/\n  - System/DoesNotExist/\n")
        rep = certify._governance(self.tmp)
        self.assertFalse(rep.ok)
        self.assertTrue(any("does not exist" in e for e in rep.errors))

    def test_forward_looking_glob_matching_nothing_is_not_flagged(self):
        # a protected glob for user content created at onboarding (e.g. "80 User/privacy*")
        # legitimately matches nothing in the generic master — must NOT warn or error
        with open(os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
            f.write("runtime:\n  ai_writes_enabled: true\n"
                    "protected_objects:\n  - SYSTEM-MANIFEST.yaml\n  - System/Agents/\n"
                    "  - 80 User/privacy*\n")
        rep = certify._governance(self.tmp)
        self.assertTrue(rep.ok)
        self.assertFalse(any("matches nothing" in w or "privacy" in w for w in rep.warnings))

    def test_catches_agents_not_protected(self):
        # a manifest that protects everything EXCEPT System/Agents
        with open(os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
            f.write("runtime:\n  ai_writes_enabled: true\n"
                    "protected_objects:\n  - SYSTEM-MANIFEST.yaml\n")
        rep = certify._governance(self.tmp)
        self.assertFalse(rep.ok)
        self.assertTrue(any("System/Agents" in e for e in rep.errors))


class TestDocTruthSeeded(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _sha(path):
        with open(path, "rb") as stream:
            return hashlib.sha256(stream.read()).hexdigest()

    def _write(self):
        os.makedirs(os.path.join(self.tmp, "System", "product"), exist_ok=True)
        product = os.path.join(self.tmp, "System", "product", "core.txt")
        with open(product, "w") as f:
            f.write("release bytes\n")
        package = os.path.join(self.tmp, "pyproject.toml")
        with open(package, "w") as f:
            f.write('[project]\nname = "fixture"\nversion = "1.0.0"\n')
        with open(os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
            f.write("system:\n  instance_role: generic-master\n"
                    "  system_version: 1.0.0\n")
        with open(os.path.join(self.tmp, "CHANGELOG.md"), "w") as f:
            f.write("# Changelog\n\n## [1.0.0] — 2026-07-13\n\nrelease\n")
        self._refresh_baseline()

    def _refresh_baseline(self):
        paths = [
            "System/product/core.txt",
            "pyproject.toml",
        ]
        correction = "System/Release/version-record-corrections.json"
        if os.path.exists(os.path.join(self.tmp, correction)):
            paths.append(correction)
        files = {
            rel: self._sha(os.path.join(self.tmp, rel)) for rel in paths}
        os.makedirs(os.path.join(self.tmp, "System"), exist_ok=True)
        with open(os.path.join(
                self.tmp, "System", ".baseline-manifest.json"), "w") as f:
            json.dump({
                "system_version": "1.0.0",
                "files": files,
                "derived": {},
            }, f)

    def test_clean_master_passes_strict_release_gate(self):
        self._write()
        rep = certify._doc_truth(self.tmp)
        self.assertTrue(rep.ok, rep.errors)
        self.assertIn(certify._doc_truth, certify.BEHAVIORAL)
        self.assertEqual(rep.info["role"], "generic-master")
        self.assertRegex(rep.info["baseline_identity"], r"^[0-9a-f]{64}$")

    def test_package_mirror_defect_is_hard_error(self):
        self._write()
        package = os.path.join(self.tmp, "pyproject.toml")
        with open(package, "w") as f:
            f.write('[project]\nname = "fixture"\nversion = "1.0.1"\n')
        self._refresh_baseline()
        rep = certify._doc_truth(self.tmp)
        self.assertFalse(rep.ok)
        self.assertTrue(any("package-mirror-mismatch" in e for e in rep.errors))

    def test_baseline_identity_defect_is_hard_error(self):
        self._write()
        baseline = os.path.join(
            self.tmp, "System", ".baseline-manifest.json")
        with open(baseline) as f:
            data = json.load(f)
        data["files"]["System/product/core.txt"] = "0" * 64
        with open(baseline, "w") as f:
            json.dump(data, f)
        rep = certify._doc_truth(self.tmp)
        self.assertFalse(rep.ok)
        self.assertTrue(any("baseline-file-mismatch" in e for e in rep.errors))
        self.assertIsNone(rep.info["baseline_identity"])

    def test_stale_correction_target_is_hard_error(self):
        self._write()
        correction_dir = os.path.join(self.tmp, "System", "Release")
        os.makedirs(correction_dir)
        with open(os.path.join(
                correction_dir, "version-record-corrections.json"), "w") as f:
            json.dump({
                "schema_version": 1,
                "records": [{
                    "id": "stale",
                    "disposition": "amendment",
                    "target_section_sha256": "0" * 64,
                    "reason": "planted stale target",
                }],
            }, f)
        self._refresh_baseline()
        rep = certify._doc_truth(self.tmp)
        self.assertFalse(rep.ok)
        self.assertTrue(any("correction-target-missing" in e
                            for e in rep.errors))

    def test_personal_instance_uses_explicit_instance_contract(self):
        self._write()
        manifest = os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml")
        with open(manifest, "w") as f:
            f.write("system:\n  instance_role: personal-instance\n"
                    "  system_version: 1.0.0\n")
        os.remove(os.path.join(self.tmp, "CHANGELOG.md"))
        with open(os.path.join(
                self.tmp, "System", "product", "core.txt"), "w") as f:
            f.write("intentional instance customization\n")
        rep = certify._doc_truth(self.tmp)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(rep.info["role"], "personal-instance")
        self.assertEqual(rep.info["changelog_records"], 0)


if __name__ == "__main__":
    unittest.main()
