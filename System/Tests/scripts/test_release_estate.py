"""Focused tests for the read-only historical release-estate loader."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


VAULT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(VAULT / "System" / "Tests"))

from release_qualification.estate import (  # noqa: E402
    EstateError,
    discover_mainline_states,
    discover_release_refs,
    inventory_releases,
    load_release,
)


def git(repo, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode:
        raise AssertionError(proc.stderr)
    return proc.stdout.strip()


def write_release(repo, version, marker):
    product = ("release %s %s\n" % (version, marker)).encode()
    product_path = repo / "System" / "product.txt"
    product_path.parent.mkdir(parents=True, exist_ok=True)
    product_path.write_bytes(product)
    manifest = {
        "system": {
            "name": "Personal AI OS",
            "system_version": version,
        }
    }
    (repo / "SYSTEM-MANIFEST.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=True), encoding="utf-8")
    baseline = {
        "system_version": version,
        "files": {
            "System/product.txt": hashlib.sha256(product).hexdigest(),
        },
        "derived": {},
    }
    (repo / "System" / ".baseline-manifest.json").write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def commit_release(repo, version, marker):
    write_release(repo, version, marker)
    git(repo, "add", "SYSTEM-MANIFEST.yaml", "System")
    git(repo, "commit", "-m", "release %s %s" % (version, marker))
    return git(repo, "rev-parse", "HEAD")


class ReleaseRepo:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="estate test ")
        self.root = Path(self.temp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "tests@example.invalid")
        git(self.root, "config", "user.name", "Estate Tests")
        self.v143 = commit_release(self.root, "1.43.0", "official")
        git(self.root, "tag", "v1.43.0")
        self.v144 = commit_release(self.root, "1.44.0", "main")
        git(self.root, "branch", "rival", self.v143)
        git(self.root, "switch", "rival")
        self.rival = commit_release(self.root, "1.43.0", "rival")
        git(self.root, "switch", "main")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.temp.cleanup()


class TestReleaseEstate(unittest.TestCase):
    def test_exact_ref_loads_blobs_and_verifies_baseline_without_checkout(self):
        with ReleaseRepo() as estate:
            before_head = git(estate.root, "rev-parse", "HEAD")
            before_status = git(estate.root, "status", "--porcelain=v1")

            record = load_release(estate.root, "refs/tags/v1.43.0")

            self.assertEqual(record.commit, estate.v143)
            self.assertEqual(record.system_version, "1.43.0")
            self.assertEqual(record.baseline_version, "1.43.0")
            self.assertTrue(record.baseline_valid)
            self.assertEqual(record.baseline_file_count, 1)
            self.assertRegex(record.release_identity, r"^[0-9a-f]{64}$")
            self.assertEqual(git(estate.root, "rev-parse", "HEAD"), before_head)
            self.assertEqual(git(estate.root, "status", "--porcelain=v1"),
                             before_status)

    def test_inventory_marks_same_version_different_baselines_as_rivals(self):
        with ReleaseRepo() as estate:
            inventory = inventory_releases(
                estate.root,
                ["refs/tags/v1.43.0", "refs/heads/rival", estate.v144],
            )
            v143 = [r for r in inventory.records
                    if r.system_version == "1.43.0"]
            self.assertEqual(len(v143), 2)
            self.assertNotEqual(v143[0].release_identity,
                                v143[1].release_identity)
            self.assertEqual(v143[0].same_version_rivals,
                             (v143[1].release_identity,))
            self.assertEqual(v143[1].same_version_rivals,
                             (v143[0].release_identity,))
            self.assertEqual(inventory.rival_groups[0][0], "1.43.0")
            payload = json.loads(inventory.to_json())
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(len(payload["records"]), 3)
            self.assertEqual(len(payload["rival_groups"]), 1)

    def test_same_version_same_baseline_is_alias_not_rival(self):
        with ReleaseRepo() as estate:
            inventory = inventory_releases(
                estate.root, ["v1.43.0", estate.v143])
            self.assertEqual(len(inventory.records), 2)
            self.assertEqual(inventory.rival_groups, ())
            self.assertEqual(inventory.records[0].release_identity,
                             inventory.records[1].release_identity)

    def test_same_version_same_baseline_but_different_tree_is_rival(self):
        with ReleaseRepo() as estate:
            git(estate.root, "switch", "-c", "undeclared", estate.v143)
            (estate.root / "UNDECLARED.md").write_text(
                "not represented by the baseline\n", encoding="utf-8")
            git(estate.root, "add", "UNDECLARED.md")
            git(estate.root, "commit", "-m", "undeclared release difference")
            inventory = inventory_releases(
                estate.root, ["v1.43.0", "refs/heads/undeclared"])
            self.assertEqual(len(inventory.rival_groups), 1)
            self.assertNotEqual(inventory.records[0].tree,
                                inventory.records[1].tree)

    def test_discovers_exact_refs_and_untagged_mainline_states(self):
        with ReleaseRepo() as estate:
            refs = discover_release_refs(
                estate.root, ("refs/tags", "refs/heads"))
            self.assertIn("refs/tags/v1.43.0", refs)
            self.assertIn("refs/heads/main", refs)
            self.assertIn("refs/heads/rival", refs)

            states = discover_mainline_states(estate.root, "refs/heads/main")
            self.assertEqual(states, (estate.v143, estate.v144))

    def test_mainline_discovery_uses_transition_for_history_and_tip_for_current(self):
        with ReleaseRepo() as estate:
            git(estate.root, "switch", "main")
            (estate.root / "after-release.md").write_text(
                "same current version\n", encoding="utf-8")
            git(estate.root, "add", "after-release.md")
            git(estate.root, "commit", "-m", "post-release state")
            tip = git(estate.root, "rev-parse", "HEAD")
            states = discover_mainline_states(
                estate.root, "main", minimum_version="1.43.0",
                maximum_version="1.44.0")
            self.assertEqual(states, (estate.v143, tip))

    def test_mainline_discovery_keeps_untagged_historical_version(self):
        with ReleaseRepo() as estate:
            git(estate.root, "switch", "main")
            v145 = commit_release(estate.root, "1.45.0", "current")
            states = discover_mainline_states(
                estate.root, "main", minimum_version="1.43.0",
                maximum_version="1.45.0")
            self.assertEqual(states, (estate.v143, estate.v144, v145))

    def test_hash_mismatch_is_machine_readable_and_does_not_abort_inventory(self):
        with ReleaseRepo() as estate:
            git(estate.root, "switch", "-c", "bad-baseline", estate.v144)
            baseline_path = estate.root / "System" / ".baseline-manifest.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["files"]["System/product.txt"] = "0" * 64
            baseline_path.write_text(
                json.dumps(baseline, sort_keys=True), encoding="utf-8")
            git(estate.root, "add", str(baseline_path))
            git(estate.root, "commit", "-m", "bad baseline")

            record = load_release(estate.root, "HEAD")
            self.assertFalse(record.baseline_valid)
            self.assertEqual(len(record.baseline_mismatches), 1)
            self.assertIn("expected", record.baseline_mismatches[0])

    def test_skipped_hash_verification_is_not_reported_as_valid(self):
        with ReleaseRepo() as estate:
            record = load_release(
                estate.root, "v1.43.0", verify_baseline=False)
            self.assertIsNone(record.baseline_valid)
            self.assertIsNone(record.to_dict()["baseline_valid"])

    def test_missing_ref_and_version_disagreement_fail_closed(self):
        with ReleaseRepo() as estate:
            with self.assertRaises(EstateError):
                load_release(estate.root, "refs/tags/does-not-exist")

            git(estate.root, "switch", "-c", "bad-version", estate.v144)
            manifest_path = estate.root / "SYSTEM-MANIFEST.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["system"]["system_version"] = "9.9.9"
            manifest_path.write_text(
                yaml.safe_dump(manifest), encoding="utf-8")
            git(estate.root, "add", str(manifest_path))
            git(estate.root, "commit", "-m", "version disagreement")
            with self.assertRaisesRegex(
                    EstateError, "manifest/baseline version mismatch"):
                load_release(estate.root, "HEAD")


if __name__ == "__main__":
    unittest.main()
