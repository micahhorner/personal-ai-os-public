"""Evidence tests for generated historical migration data."""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


VAULT = Path(__file__).resolve().parents[3]
SCRIPTS = VAULT / "System/Scripts"
sys.path.insert(0, str(SCRIPTS))

from cmd import migrate as migrate_mod  # noqa: E402
from lib.historical_sources import OFFICIAL_LEGACY_CORE_SOURCES  # noqa: E402
from lib.migrations import (  # noqa: E402
    MigrationError,
    discover,
    load_manifest,
    preflight_sequence,
)


GENERATOR_PATH = VAULT / "System/Migrations/generate_historical.py"
SPEC = importlib.util.spec_from_file_location("historical_generator", GENERATOR_PATH)
generator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generator)


class TestHistoricalMigrationEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = generator.load_catalog()
        cls.outputs = generator.expected_files(cls.catalog)

    def test_official_and_refused_identity_coverage_is_exact_and_unique(self):
        official = self.catalog["official_sources"]
        refused = self.catalog["refused_sources"]
        self.assertEqual(len(official), 21)
        self.assertEqual(len(refused), 3)
        self.assertEqual(
            [str(item["version"]) for item in official],
            [
                "1.43.0", "1.44.0", "1.46.0", "1.47.0", "1.48.0",
                "1.49.0", "1.50.0", "1.51.0", "1.52.0", "1.53.0",
                "1.54.0", "1.55.0", "1.56.0", "1.57.0", "1.58.0",
                "1.59.0", "1.60.0", "1.62.0", "1.63.0", "1.64.0",
                "1.64.1",
            ],
        )
        identities = [item["source_identity"] for item in official + refused]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertNotIn("1.45.0", [str(item["version"]) for item in official])
        self.assertNotIn("1.61.0", [str(item["version"]) for item in official])
        self.assertEqual(
            OFFICIAL_LEGACY_CORE_SOURCES,
            frozenset(
                (
                    str(item["version"]),
                    item["source_identity"],
                    item["old_license_sha256"],
                )
                for item in official
                if item.get("transform") != "license-postcondition-only"
            ),
            "trusted updater allowlist drifted from audited historical evidence",
        )

    def test_generated_files_and_manifest_hashes_are_current(self):
        for path, expected in self.outputs.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_bytes(), expected, path)
        manifests = sorted(
            (VAULT / "System/Migrations").glob(
                "[0-9][0-9][0-9]-about-stamp-from-*/migration.yaml"
            )
        )
        self.assertEqual(len(manifests), 19)
        manifests.append(
            VAULT / "System/Migrations/021-official-1-64-0/migration.yaml"
        )
        manifests.append(
            VAULT / "System/Migrations/022-official-1-64-1/migration.yaml"
        )
        for path in manifests:
            manifest = load_manifest(path)
            self.assertEqual(manifest.data["schema_version"], "1.1.0")
            self.assertEqual(
                manifest.data["source_distribution"], "personal-ai-os"
            )
            self.assertEqual(
                manifest.data["manifest_hash"], manifest.manifest_hash
            )

    def test_every_old_and_payload_hash_matches_exact_git_evidence(self):
        target = self.catalog["target"]
        about_surfaces = target["about_surfaces"]
        license_target = target["license"]
        self.assertEqual(len(about_surfaces), 8)
        for about in about_surfaces:
            target_bytes = generator.git_bytes(
                about["payload_ref"], about["path"]
            )
            self.assertEqual(
                hashlib.sha256(target_bytes).hexdigest(),
                about["payload_sha256"],
            )
        license_bytes = generator.git_bytes(
            license_target["payload_ref"], license_target["path"]
        )
        self.assertEqual(
            hashlib.sha256(license_bytes).hexdigest(),
            license_target["payload_sha256"],
        )
        for index, source in enumerate(self.catalog["official_sources"], 1):
            version = str(source["version"])
            name = (
                "021-official-1-64-0"
                if source.get("transform") == "postcondition-only"
                else "022-official-1-64-1"
                if source.get("transform") == "license-postcondition-only"
                else generator.edge_name(index, version)
            )
            manifest = load_manifest(
                VAULT / "System/Migrations" / name / "migration.yaml"
            )
            effects = {
                effect["path"]: effect
                for effect in manifest.data["transform"]["replace_exact_files"]
            }
            if source.get("transform") != "license-postcondition-only":
                for about in about_surfaces:
                    old = generator.git_bytes(source["commit"], about["path"])
                    self.assertEqual(
                        hashlib.sha256(old).hexdigest(),
                        effects[about["path"]]["old_sha256"],
                    )
                    self.assertEqual(
                        effects[about["path"]]["new_sha256"],
                        about["payload_sha256"],
                    )
                old = generator.git_bytes(source["commit"], "80 User/_ABOUT.md")
                self.assertEqual(
                    hashlib.sha256(old).hexdigest(), source["old_about_sha256"]
                )
            old_license = generator.git_bytes(
                source["commit"], license_target["path"]
            )
            self.assertEqual(
                hashlib.sha256(old_license).hexdigest(),
                source["old_license_sha256"],
            )

    def test_143_and_160_combined_payloads_rehearse_byte_for_byte(self):
        for sequence, version in ((1, "1.43.0"), (17, "1.60.0")):
            source = next(
                item
                for item in self.catalog["official_sources"]
                if str(item["version"]) == version
            )
            name = generator.edge_name(sequence, version)
            source_dir = VAULT / "System/Migrations" / name
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "vault"
                migration_dir = root / "System/Migrations" / name
                shutil.copytree(source_dir, migration_dir)
                destinations = {}
                for about in self.catalog["target"]["about_surfaces"]:
                    destination = root / about["path"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(
                        generator.git_bytes(source["commit"], about["path"])
                    )
                    destinations[about["path"]] = destination
                license_path = root / "LICENSE.md"
                license_path.write_bytes(
                    generator.git_bytes(source["commit"], "LICENSE.md")
                )
                manifest = load_manifest(migration_dir / "migration.yaml")
                changed = migrate_mod._replace_exact_files(
                    str(root), manifest, apply=True
                )
                expected_paths = [
                    about["path"]
                    for about in self.catalog["target"]["about_surfaces"]
                ] + ["LICENSE.md"]
                self.assertEqual(changed, expected_paths)
                for about in self.catalog["target"]["about_surfaces"]:
                    self.assertEqual(
                        hashlib.sha256(
                            destinations[about["path"]].read_bytes()
                        ).hexdigest(),
                        about["payload_sha256"],
                    )
                self.assertEqual(
                    hashlib.sha256(license_path.read_bytes()).hexdigest(),
                    self.catalog["target"]["license"]["payload_sha256"],
                )

    def test_wrong_about_or_license_refuses_before_any_write(self):
        source = self.catalog["official_sources"][0]
        name = generator.edge_name(1, "1.43.0")
        source_dir = VAULT / "System/Migrations" / name
        protected_paths = [
            about["path"]
            for about in self.catalog["target"]["about_surfaces"]
        ] + ["LICENSE.md"]
        for damaged in protected_paths:
            with self.subTest(damaged=damaged), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "vault"
                migration_dir = root / "System/Migrations" / name
                shutil.copytree(source_dir, migration_dir)
                destinations = {}
                for about in self.catalog["target"]["about_surfaces"]:
                    destination = root / about["path"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(
                        generator.git_bytes(source["commit"], about["path"])
                    )
                    destinations[about["path"]] = destination
                license_path = root / "LICENSE.md"
                license_path.write_bytes(
                    generator.git_bytes(source["commit"], "LICENSE.md")
                )
                (root / damaged).write_bytes(b"locally edited\n")
                before = {
                    path: (root / path).read_bytes() for path in protected_paths
                }
                manifest = load_manifest(migration_dir / "migration.yaml")
                with self.assertRaisesRegex(
                    MigrationError, "old_sha256 precondition mismatch"
                ):
                    migrate_mod._replace_exact_files(
                        str(root), manifest, apply=True
                    )
                self.assertEqual(
                    {path: (root / path).read_bytes() for path in protected_paths},
                    before,
                )

    def test_020_and_021_keep_identical_mit_while_021_updates_abouts(self):
        for name in ("020-core-license-boundary", "021-official-1-64-0"):
            source_dir = VAULT / "System/Migrations" / name
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "vault"
                migration_dir = root / "System/Migrations" / name
                shutil.copytree(source_dir, migration_dir)
                manifest = load_manifest(migration_dir / "migration.yaml")
                license_effect = next(
                    effect
                    for effect in manifest.data["transform"]["replace_exact_files"]
                    if effect["path"] == "LICENSE.md"
                )
                payload_rel = license_effect["payload"]
                for effect in manifest.data["transform"]["replace_exact_files"]:
                    if effect["path"] == "LICENSE.md":
                        continue
                    destination = root / effect["path"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if name == "021-official-1-64-0":
                        destination.write_bytes(generator.git_bytes(
                            self.catalog["official_sources"][-2]["commit"],
                            effect["path"],
                        ))
                    else:
                        destination.write_bytes(
                            (source_dir / effect["payload"]).read_bytes()
                        )
                license_path = root / "LICENSE.md"
                license_path.write_bytes((source_dir / payload_rel).read_bytes())
                contract = migrate_mod.exact_transform_contract(
                    str(root), manifest
                )
                self.assertTrue(contract)
                for effect in contract:
                    self.assertIn(
                        effect["matched_old_sha256"],
                        effect["accepted_old_sha256"],
                    )
                    if name == "021-official-1-64-0" and effect["path"] != "LICENSE.md":
                        self.assertNotEqual(
                            effect["matched_old_sha256"], effect["new_sha256"])
                        self.assertTrue(effect["needs_write"])
                    else:
                        self.assertEqual(
                            effect["matched_old_sha256"], effect["new_sha256"])
                        self.assertFalse(effect["needs_write"])
                license_contract = next(
                    effect for effect in contract if effect["path"] == "LICENSE.md"
                )
                self.assertEqual(
                    license_contract["matched_old_sha256"],
                    license_contract["new_sha256"],
                )
                self.assertIn(
                    license_contract["matched_old_sha256"],
                    license_contract["accepted_old_sha256"],
                )
                self.assertFalse(license_contract["needs_write"])
                with mock.patch.object(
                    migrate_mod, "_replace_bytes"
                ) as replace_bytes:
                    changed = migrate_mod._replace_exact_files(
                        str(root), manifest, apply=True
                    )
                self.assertEqual(changed, [
                    effect["path"] for effect in contract
                ])
                self.assertEqual(
                    replace_bytes.call_count,
                    10 if name == "021-official-1-64-0" else 0,
                )

    def test_official_164_custom_root_bytes_refuse_before_replacement(self):
        source = self.catalog["official_sources"][-1]
        source_dir = VAULT / "System/Migrations/021-official-1-64-0"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "vault"
            migration_dir = root / "System/Migrations/021-official-1-64-0"
            shutil.copytree(source_dir, migration_dir)
            manifest = load_manifest(migration_dir / "migration.yaml")
            for effect in manifest.data["transform"]["replace_exact_files"]:
                destination = root / effect["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(generator.git_bytes(
                    source["commit"], effect["path"]
                ))
            original_security = (root / "SECURITY.md").read_bytes()
            (root / "CONTRIBUTING.md").write_text("CUSTOM CONTRIBUTING\n")
            with self.assertRaises(MigrationError):
                migrate_mod.exact_transform_contract(str(root), manifest)
            self.assertEqual((root / "CONTRIBUTING.md").read_text(),
                             "CUSTOM CONTRIBUTING\n")
            self.assertEqual((root / "SECURITY.md").read_bytes(), original_security)

    def test_bridge_and_final_release_ref_status_are_explicit(self):
        bridge = self.catalog["official_sources"][-2]
        self.assertEqual(str(bridge["version"]), "1.64.0")
        self.assertEqual(bridge["transform"], "postcondition-only")
        primary = next(
            about
            for about in self.catalog["target"]["about_surfaces"]
            if about["path"] == "80 User/_ABOUT.md"
        )
        self.assertNotEqual(bridge["old_about_sha256"], primary["payload_sha256"])
        unresolved = self.catalog["unresolved"]
        self.assertEqual(
            unresolved["target_release_ref"], "refs/tags/v1.64.2"
        )
        self.assertEqual(
            unresolved["legal_lane"]["status"],
            "exact-payload-evidence-pinned",
        )
        self.assertEqual(unresolved["legal_lane"]["required_inputs"], [])
        self.assertEqual(unresolved["legal_lane"]["blocks"], [])
        self.assertEqual(
            unresolved["bridge_1_64_0"]["status"], "alternative-edge-021"
        )
        source_identities = {
            load_manifest(path).source_identity
            for path in (VAULT / "System/Migrations").glob(
                "[0-9][0-9][0-9]-about-stamp-from-*/migration.yaml"
            )
        }
        for refused in self.catalog["refused_sources"]:
            self.assertNotIn(refused["source_identity"], source_identities)

    def test_non_main_rival_identities_are_rehearsed_as_refusals(self):
        available = discover(VAULT / "System/Migrations")
        by_version = {}
        for manifest in available:
            by_version.setdefault(manifest.from_version, []).append(manifest)
        for refused in self.catalog["refused_sources"]:
            version = str(refused["version"])
            if version == "1.61.0":
                self.assertNotIn(version, by_version)
                continue
            with self.subTest(refused=refused["id"]):
                with self.assertRaisesRegex(MigrationError, "wrong source identity"):
                    preflight_sequence(
                        by_version[version][0],
                        available,
                        [],
                        version,
                        refused["source_identity"],
                    )

    def test_164_alternative_edges_are_identity_disjoint(self):
        available = discover(VAULT / "System/Migrations")
        edges = [
            item for item in available
            if item.from_version == "1.64.0"
            and item.to_version == "1.64.2"
        ]
        self.assertEqual(
            {item.id for item in edges},
            {
                "migration-020-core-license-boundary",
                "migration-021-official-1-64-0",
            },
        )
        self.assertEqual(len({item.source_identity for item in edges}), 2)
        official = next(
            item for item in edges
            if item.id == "migration-021-official-1-64-0"
        )
        dev = next(
            item for item in edges
            if item.id == "migration-020-core-license-boundary"
        )
        with self.assertRaisesRegex(MigrationError, "wrong source identity"):
            preflight_sequence(
                official, available, [], "1.64.0", dev.source_identity
            )

    def test_direct_estate_has_21_supported_sources_to_1642(self):
        available = discover(VAULT / "System/Migrations")
        direct = [
            item for item in available
            if item.version_target == "system_version"
            and item.to_version == "1.64.2"
            and item.from_version in {
                str(source["version"])
                for source in self.catalog["official_sources"]
            }
        ]
        generated_direct = [
            item for item in direct
            if item.id != "migration-020-core-license-boundary"
        ]
        self.assertEqual(len(generated_direct), 21)
        self.assertEqual(len({item.from_version for item in direct}), 21)
        self.assertTrue(all(item.data["prerequisites"] == [] for item in direct))

    def test_022_identity_exact_no_write_and_custom_license_refusal(self):
        source = self.catalog["official_sources"][-1]
        self.assertEqual(str(source["version"]), "1.64.1")
        self.assertEqual(
            source["source_identity"],
            "1ddcc0e5c5ce8dc582538f478e2923468a14fae1eebfb3e1a25527d618bfbb3d",
        )
        source_dir = VAULT / "System/Migrations/022-official-1-64-1"
        manifest = load_manifest(source_dir / "migration.yaml")
        self.assertEqual(manifest.from_version, "1.64.1")
        self.assertEqual(manifest.to_version, "1.64.2")
        self.assertEqual(manifest.source_identity, source["source_identity"])
        effect = manifest.data["transform"]["replace_exact_files"]
        self.assertEqual(len(effect), 1)
        effect = effect[0]
        self.assertEqual(effect["path"], "LICENSE.md")
        self.assertEqual(
            effect["old_sha256"],
            "56fad99676a39687067146891cdcc88e068bf364bc91531b97aefd904be903c5",
        )
        self.assertEqual(effect["old_sha256"], effect["new_sha256"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "vault"
            shutil.copytree(source_dir, root / "System/Migrations/022-official-1-64-1")
            license_path = root / "LICENSE.md"
            license_path.parent.mkdir(parents=True, exist_ok=True)
            license_path.write_bytes((source_dir / effect["payload"]).read_bytes())
            contract = migrate_mod.exact_transform_contract(str(root), manifest)
            self.assertEqual(len(contract), 1)
            self.assertFalse(contract[0]["needs_write"])
            with mock.patch.object(migrate_mod, "_replace_bytes") as replace_bytes:
                migrate_mod._replace_exact_files(str(root), manifest, apply=True)
            replace_bytes.assert_not_called()
            license_path.write_text("custom license\n")
            before = license_path.read_bytes()
            with self.assertRaisesRegex(
                MigrationError, "old_sha256 precondition mismatch"
            ):
                migrate_mod._replace_exact_files(str(root), manifest, apply=True)
            self.assertEqual(license_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
