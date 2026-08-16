"""Adversarial tests for the strict internal version-record checker."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import yaml


VAULT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(VAULT / "System" / "Scripts"))

from lib.version_records import BASELINE_ROOT_FILES, audit_version_records  # noqa: E402
from cmd.upgrade import _neutralised_sha  # noqa: E402


class TestBaselineRootSurface(unittest.TestCase):
    def test_product_root_surface_is_exactly_bounded(self):
        self.assertEqual(
            set(BASELINE_ROOT_FILES),
            {"CLAUDE.md", "pyproject.toml", "README.md", "START-HERE.md",
             "CONTRIBUTING.md", "SECURITY.md"},
        )


def sha(body):
    return hashlib.sha256(body).hexdigest()


class VersionVault:
    def __init__(self, root, version="1.2.0", role="generic-master"):
        self.root = Path(root)
        (self.root / "System" / "Release").mkdir(parents=True)
        self.version = version
        self.role = role
        self.product = b"product bytes\n"
        (self.root / "System" / "product.txt").write_bytes(self.product)
        self.write_authorities()
        self.write_changelog([
            ("## [1.2.0] — 2026-01-03", "current"),
            ("## [1.1.0] — 2026-01-02", "middle"),
            ("## [1.0.0] — 2026-01-01", "first"),
        ])

    def write_authorities(self, manifest=None, package=None, baseline=None,
                          role=None):
        manifest = manifest or self.version
        package = package or self.version
        baseline = baseline or self.version
        self.role = role or self.role
        (self.root / "SYSTEM-MANIFEST.yaml").write_text(
            yaml.safe_dump({"system": {
                "system_version": manifest,
                "instance_role": self.role,
            }}), encoding="utf-8")
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "%s"\n' % package,
            encoding="utf-8")
        self.refresh_baseline(baseline)

    def release_files(self):
        paths = [
            self.root / "System" / "product.txt",
            self.root / "pyproject.toml",
        ]
        correction = (self.root / "System" / "Release"
                      / "version-record-corrections.json")
        if correction.exists():
            paths.append(correction)
        doc = self.root / "System" / "doc.md"
        if doc.exists():
            paths.append(doc)
        return paths

    def refresh_baseline(self, version=None):
        version = version or self.version
        files = {}
        derived = {}
        for path in self.release_files():
            rel = path.relative_to(self.root).as_posix()
            files[rel] = sha(path.read_bytes())
            neutral = _neutralised_sha(str(path))
            if neutral is not None:
                derived[rel] = neutral
        data = {
            "system_version": version,
            "files": files,
            "derived": derived,
            "generated_at": "2026-01-03T00:00:00",
        }
        (self.root / "System" / ".baseline-manifest.json").write_text(
            json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def write_changelog(self, sections, trailing=""):
        body = ["# Changelog\n\n"]
        for item in sections:
            heading, text = item if isinstance(item, tuple) else (item, "text")
            body.append("%s\n\n%s\n\n" % (heading, text))
        body.append(trailing)
        (self.root / "CHANGELOG.md").write_text(
            "".join(body), encoding="utf-8")

    def section_digest(self, heading):
        text = (self.root / "CHANGELOG.md").read_text(encoding="utf-8")
        start = text.index(heading)
        next_heading = text.find("\n## ", start + len(heading))
        section = text[start:] if next_heading < 0 else text[start:next_heading + 1]
        return sha(section.encode("utf-8"))

    def write_corrections(self, records):
        path = (self.root / "System" / "Release"
                / "version-record-corrections.json")
        path.write_text(json.dumps({
            "schema_version": 1,
            "records": records,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.refresh_baseline()


class TestVersionRecords(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="version records ")
        self.vault = VersionVault(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def audit(self, role="generic-master"):
        return audit_version_records(self.temp.name, expected_role=role)

    @staticmethod
    def codes(audit):
        return [finding.code for finding in audit.findings]

    def test_manifest_is_sole_authority_and_both_mirrors_must_match(self):
        audit = self.audit()
        self.assertTrue(audit.ok, audit.findings)
        self.assertEqual(audit.versions, {
            "authority": "1.2.0",
            "package_mirror": "1.2.0",
            "baseline_mirror": "1.2.0",
        })
        self.vault.write_authorities(package="1.2.1", baseline="1.1.0")
        codes = self.codes(self.audit())
        self.assertIn("package-mirror-mismatch", codes)
        self.assertIn("baseline-mirror-mismatch", codes)
        self.assertNotIn("current-version-mismatch", codes)

    def test_baseline_identity_is_only_emitted_for_a_valid_baseline(self):
        good = self.audit()
        self.assertRegex(good.baseline_identity, r"^[0-9a-f]{64}$")
        (self.vault.root / "System" / "product.txt").write_text(
            "tampered\n", encoding="utf-8")
        bad = self.audit()
        self.assertIn("baseline-file-mismatch", self.codes(bad))
        self.assertIsNone(bad.baseline_identity)

    def test_duplicate_release_headings_are_rejected(self):
        self.vault.write_changelog([
            ("## [1.2.0] — now", "now"),
            ("## [1.1.0] — first", "first body"),
            ("## [1.1.0] — duplicate", "different body"),
            ("## [1.0.0] — old", "old"),
        ])
        codes = self.codes(self.audit())
        self.assertIn("changelog-record-id-duplicate", codes)
        self.assertIn("changelog-release-version-duplicate", codes)

    def test_section_digest_targets_one_of_two_identical_headings(self):
        heading = "## [1.1.0] — repeated"
        self.vault.write_changelog([
            ("## [1.2.0] — now", "now"),
            (heading, "official body"),
            (heading, "rolling amendment body"),
            ("## [1.0.0] — old", "old"),
        ])
        text = (self.vault.root / "CHANGELOG.md").read_text()
        second = text.index(heading, text.index(heading) + 1)
        end = text.find("\n## ", second + len(heading))
        digest = sha(text[second:end + 1].encode("utf-8"))
        self.vault.write_corrections([{
            "id": "amendment-rolling-1-1",
            "disposition": "amendment",
            "target_section_sha256": digest,
            "reason": "A dated rolling amendment, not another release.",
        }])
        audit = self.audit()
        self.assertTrue(audit.ok, audit.findings)
        self.assertEqual(
            [record.disposition for record in audit.records].count("amendment"),
            1)

    def test_identical_sections_make_a_correction_target_ambiguous(self):
        heading = "## [1.1.0] — repeated"
        self.vault.write_changelog([
            ("## [1.2.0] — now", "now"),
            (heading, "same"),
            (heading, "same"),
            ("## [1.0.0] — old", "old"),
        ])
        digest = self.vault.section_digest(heading)
        self.vault.write_corrections([{
            "id": "ambiguous",
            "disposition": "amendment",
            "target_section_sha256": digest,
            "reason": "Cannot identify an occurrence.",
        }])
        self.assertIn("correction-target-ambiguous", self.codes(self.audit()))

    def test_actual_style_misplaced_release_retains_release_status(self):
        misplaced = "## [0.1.0] — 2026-01-01"
        self.vault.write_changelog([
            ("## [1.2.0] — now", "now"),
            (misplaced, "Foundational construction genuinely released."),
            ("## [1.1.0] — middle", "middle"),
            ("## [1.0.0] — old", "old"),
        ])
        self.assertIn("changelog-order", self.codes(self.audit()))
        self.vault.write_corrections([{
            "id": "misplaced-foundational-release",
            "disposition": "misplaced-release",
            "target_section_sha256": self.vault.section_digest(misplaced),
            "reason": "Genuine release retained; section is physically misplaced.",
        }])
        audit = self.audit()
        self.assertTrue(audit.ok, audit.findings)
        record = next(item for item in audit.records if item.version == "0.1.0")
        self.assertEqual(record.disposition, "misplaced-release")
        self.assertEqual(record.record_id, "release:0.1.0")

    def test_full_semver_prerelease_precedence_is_descending(self):
        """Stable outranks prerelease; identifiers use SemVer numeric rules."""
        self.vault.write_changelog([
            ("## [1.2.0] — stable", "stable"),
            ("## [1.2.0-rc.alpha] — alpha identifier", "candidate"),
            ("## [1.2.0-rc.10] — numeric ten", "candidate"),
            ("## [1.2.0-rc.2] — numeric two", "candidate"),
            ("## [1.2.0-rc.1] — numeric one", "candidate"),
            ("## [1.1.0] — prior minor", "prior"),
            ("## [1.0.0] — first", "first"),
        ])
        self.assertNotIn("changelog-order", self.codes(self.audit()))

    def test_semver_numeric_prerelease_is_not_lexically_ordered(self):
        self.vault.write_changelog([
            ("## [1.2.0] — stable", "stable"),
            ("## [1.2.0-rc.2] — incorrectly before ten", "candidate"),
            ("## [1.2.0-rc.10] — should precede two", "candidate"),
            ("## [1.1.0] — prior minor", "prior"),
            ("## [1.0.0] — first", "first"),
        ])
        self.assertIn("changelog-order", self.codes(self.audit()))

    def test_build_metadata_cannot_manufacture_strict_precedence(self):
        """Build metadata differs in identity but is equal in SemVer precedence."""
        self.vault.write_changelog([
            ("## [1.2.0] — current", "current"),
            ("## [1.1.0+build.2] — build two", "same precedence"),
            ("## [1.1.0+build.1] — build one", "same precedence"),
            ("## [1.0.0] — first", "first"),
        ])
        self.assertIn("changelog-order", self.codes(self.audit()))

    def test_missing_minor_needs_exact_stable_reservation(self):
        self.vault.write_changelog([
            ("## [1.2.0] — now", "now"),
            ("## [1.1.0-rc.1] — candidate", "candidate"),
            ("## [1.0.0] — old", "old"),
        ])
        self.assertIn("changelog-minor-gap", self.codes(self.audit()))
        self.vault.write_corrections([{
            "id": "reservation-1-1-0",
            "disposition": "reserved",
            "version": "1.1.0",
            "reason": "Number intentionally never released.",
        }])
        self.assertTrue(self.audit().ok)

    def test_non_main_release_accounts_for_gap_without_claiming_main_release(self):
        self.vault.write_changelog([
            ("## [1.2.0] — now", "now"),
            ("## [1.0.0] — old", "old"),
        ])
        self.vault.write_corrections([{
            "id": "non-main-release-1-1-0",
            "disposition": "non-main-release",
            "version": "1.1.0",
            "reason": "Genuine historical branch release, unsupported on main.",
        }])
        audit = self.audit()
        self.assertTrue(audit.ok, audit.findings)
        record = next(item for item in audit.records
                      if item.version == "1.1.0")
        self.assertEqual(record.disposition, "non-main-release")
        self.assertEqual(record.record_id, "non-main-release:1.1.0")
        self.assertNotEqual(record.record_id, "release:1.1.0")

    def test_malformed_version_like_headings_fail_closed(self):
        self.vault.write_changelog([
            ("## [1.2.0] — now", "now"),
            ("### [1.1.2] — wrong depth", "bad"),
            (" ## [1.1.1] — leading space", "bad"),
            ("## [1.1.0]junk", "bad"),
            ("## [1.0.0] — old", "old"),
        ])
        findings = [
            finding for finding in self.audit().findings
            if finding.code == "changelog-heading-malformed"]
        self.assertEqual(
            [(item.line, item.path) for item in findings],
            [(7, "CHANGELOG.md"), (11, "CHANGELOG.md"),
             (15, "CHANGELOG.md")])

    def test_strict_semver_yaml_and_heading_tokens_fail_closed(self):
        self.vault.write_changelog([
            ("## [1.2.0] — now", "now"),
            ("## [1.1.0oops] — partial", "bad"),
            ("## [1.0.0-01] — leading zero", "bad"),
            ("## [1.0.0] — old", "old"),
        ])
        codes = self.codes(self.audit())
        self.assertIn("changelog-token-partial", codes)
        self.assertIn("changelog-version-invalid", codes)
        (self.vault.root / "SYSTEM-MANIFEST.yaml").write_text(
            "system:\n  instance_role: generic-master\n"
            "  system_version: 1.2.0\n  system_version: 1.1.0\n",
            encoding="utf-8")
        self.assertIn("manifest-unreadable", self.codes(self.audit()))

    def test_correction_dispositions_cannot_duplicate_or_contradict(self):
        heading = "## [1.1.0] — 2026-01-02"
        digest = self.vault.section_digest(heading)
        self.vault.write_corrections([
            {
                "id": "one",
                "disposition": "withdrawn",
                "target_section_sha256": digest,
                "reason": "one",
            },
            {
                "id": "two",
                "disposition": "amendment",
                "target_section_sha256": digest,
                "reason": "two",
            },
            {
                "id": "reserve",
                "disposition": "reserved",
                "version": "1.2.0",
                "reason": "contradicts current release",
            },
        ])
        codes = self.codes(self.audit())
        self.assertIn("correction-target-duplicate", codes)
        self.assertIn("correction-version-contradictory", codes)

    def test_product_master_surface_detects_missing_extra_symlink_and_special(self):
        baseline = self.vault.root / "System" / ".baseline-manifest.json"
        data = json.loads(baseline.read_text())
        data["files"].pop("System/product.txt")
        data["files"]["not-in-surface.txt"] = "0" * 64
        baseline.write_text(json.dumps(data), encoding="utf-8")
        (self.vault.root / "System" / "link").symlink_to("/tmp")
        fifo = self.vault.root / "System" / "pipe"
        os.mkfifo(fifo)
        audit = self.audit()
        codes = self.codes(audit)
        self.assertIn("baseline-surface-missing", codes)
        self.assertIn("baseline-surface-extra", codes)
        self.assertIn("baseline-surface-special", codes)
        self.assertIsNone(audit.baseline_identity)

    def test_symlink_record_never_hashes_outside_root(self):
        outside = self.vault.root.parent / "outside-version-record-test"
        outside.write_text("outside", encoding="utf-8")
        link = self.vault.root / "System" / "escape"
        link.symlink_to(outside)
        data_path = self.vault.root / "System" / ".baseline-manifest.json"
        data = json.loads(data_path.read_text())
        data["files"]["System/escape"] = sha(outside.read_bytes())
        data_path.write_text(json.dumps(data), encoding="utf-8")
        audit = self.audit()
        self.assertIn("baseline-file-invalid", self.codes(audit))
        outside.unlink()

    def test_derived_digest_is_recomputed_with_production_contract(self):
        doc = self.vault.root / "System" / "doc.md"
        doc.write_text(
            "before\n<!-- docgen:count -->seven<!-- /docgen:count -->\nafter\n",
            encoding="utf-8")
        self.vault.refresh_baseline()
        data_path = self.vault.root / "System" / ".baseline-manifest.json"
        data = json.loads(data_path.read_text())
        data["derived"]["System/doc.md"] = "0" * 64
        data_path.write_text(json.dumps(data), encoding="utf-8")
        audit = self.audit()
        self.assertIn("baseline-derived-mismatch", self.codes(audit))
        self.assertIsNone(audit.baseline_identity)

    def test_role_is_caller_selected_and_instances_own_their_changelog(self):
        self.vault.write_authorities(role="personal-instance")
        (self.vault.root / "CHANGELOG.md").unlink()
        (self.vault.root / "System" / "product.txt").write_text(
            "intentional customization\n", encoding="utf-8")
        instance = self.audit("personal-instance")
        self.assertTrue(instance.ok, instance.findings)
        self.assertRegex(instance.baseline_identity, r"^[0-9a-f]{64}$")
        master = self.audit("generic-master")
        self.assertIn("manifest-role-mismatch", self.codes(master))
        self.assertIn("changelog-unreadable", self.codes(master))

    def test_missing_role_cannot_silently_disable_master_checks(self):
        (self.vault.root / "SYSTEM-MANIFEST.yaml").write_text(
            "system:\n  system_version: 1.2.0\n", encoding="utf-8")
        (self.vault.root / "System" / "extra.txt").write_text(
            "unbaselined", encoding="utf-8")
        codes = self.codes(self.audit("generic-master"))
        self.assertIn("manifest-role-mismatch", codes)
        self.assertIn("baseline-surface-missing", codes)

    def test_duplicate_json_keys_and_decode_errors_return_no_identity(self):
        baseline = self.vault.root / "System" / ".baseline-manifest.json"
        baseline.write_text(
            '{"system_version":"1.2.0","system_version":"1.1.0",'
            '"files":{},"derived":{}}', encoding="utf-8")
        audit = self.audit()
        self.assertIn("baseline-unreadable", self.codes(audit))
        self.assertIsNone(audit.baseline_identity)
        baseline.write_bytes(b"\xff\xfe")
        audit = self.audit()
        self.assertIn("baseline-unreadable", self.codes(audit))
        self.assertIsNone(audit.baseline_identity)


if __name__ == "__main__":
    unittest.main()
