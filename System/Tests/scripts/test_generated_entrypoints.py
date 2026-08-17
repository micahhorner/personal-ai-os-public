from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "System" / "Scripts"))

from cmd.generate import (
    COMPONENT_INDEX_SCHEMA_VERSION,
    CONTENT_TRUST,
    _validate_component_index,
    _validate_support_index,
    audit_live_generated_entrypoints,
    compare_live_to_fresh_generated,
    support_index,
)
from lib.component_evidence import component_census
from lib.safepaths import SafePathError


class GeneratedEntrypointTests(unittest.TestCase):
    def _root(self, base: str):
        root = Path(base)
        component = root / "System/Capabilities/demo/SKILL.md"
        component.parent.mkdir(parents=True)
        component.write_text(
            "---\nid: capability-demo\ncomponent_type: capability\ntype: capability\n"
            "status: active\nversion: 1.0.0\ndependencies: []\nsummary: demo\n---\n",
            encoding="utf-8",
        )
        manifest = {
            "system": {"name": "Demo", "system_version": "1.0.0"},
            "reading_order": {},
        }
        (root / "SYSTEM-MANIFEST.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
        return root, component, manifest

    def _indexes(self, root: Path, manifest):
        rows, _ = component_census(str(root))
        component = {
            "schema_version": COMPONENT_INDEX_SCHEMA_VERSION,
            "generated_at": "2026-08-09T00:00:00-05:00",
            "trust_boundary": CONTENT_TRUST,
            "components": rows,
        }
        support = support_index(str(root), manifest)
        return component, support

    def test_component_index_schema_and_live_census(self):
        with tempfile.TemporaryDirectory() as td:
            root, source, manifest = self._root(td)
            component, _support = self._indexes(root, manifest)
            _validate_component_index(str(root), component)
            malformed = dict(component)
            malformed.pop("schema_version")
            with self.assertRaisesRegex(SafePathError, "top-level fields"):
                _validate_component_index(str(root), malformed)
            source.write_text(source.read_text().replace("1.0.0", "1.0.1"), encoding="utf-8")
            with self.assertRaisesRegex(SafePathError, "live component census"):
                _validate_component_index(str(root), component)

    def test_support_index_schema_is_strict(self):
        with tempfile.TemporaryDirectory() as td:
            root, _source, manifest = self._root(td)
            _component, support = self._indexes(root, manifest)
            _validate_support_index(str(root), support)
            support["extra"] = True
            with self.assertRaisesRegex(SafePathError, "top-level fields"):
                _validate_support_index(str(root), support)

    def test_read_only_seam_detects_live_staleness(self):
        with tempfile.TemporaryDirectory() as td:
            root, source, manifest = self._root(td)
            component, support = self._indexes(root, manifest)
            generated = root / "System/Generated"
            generated.mkdir(parents=True)
            (generated / "component-index.json").write_text(json.dumps(component), encoding="utf-8")
            (generated / "support-index.json").write_text(json.dumps(support), encoding="utf-8")
            self.assertEqual(audit_live_generated_entrypoints(str(root)), [])
            source.write_text(source.read_text().replace("1.0.0", "2.0.0"), encoding="utf-8")
            findings = audit_live_generated_entrypoints(str(root))
            self.assertEqual(len(findings), 1)
            self.assertTrue(any("component-index.json" in finding for finding in findings))

    def test_isolated_comparison_seam_ignores_only_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            root, _source, manifest = self._root(td)
            component, support = self._indexes(root, manifest)
            live = root / "System/Generated"
            fresh = root / "fresh-isolated"
            live.mkdir(parents=True)
            fresh.mkdir()
            for directory in (live, fresh):
                (directory / "component-index.json").write_text(json.dumps(component), encoding="utf-8")
                (directory / "support-index.json").write_text(json.dumps(support), encoding="utf-8")
            live_component = dict(component)
            live_component["generated_at"] = "different-but-volatile"
            (live / "component-index.json").write_text(json.dumps(live_component), encoding="utf-8")
            self.assertEqual(compare_live_to_fresh_generated(str(root), str(fresh)), [])
            live_component["components"][0]["version"] = "0.9.0"
            (live / "component-index.json").write_text(json.dumps(live_component), encoding="utf-8")
            findings = compare_live_to_fresh_generated(str(root), str(fresh))
            self.assertEqual(findings, [
                "component-index.json: live entrypoint differs from fresh isolated output"
            ])


if __name__ == "__main__":
    unittest.main()
