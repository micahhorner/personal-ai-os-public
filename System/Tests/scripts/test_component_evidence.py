from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "System" / "Scripts"))

from lib.component_evidence import audit_core_component_evidence


def _component(root: Path, *, kind="capability", cid="capability-demo", version="1.0.0", tests=None,
               evaluations=None):
    tests = ["System/Tests/scripts/test_demo.py"] if tests is None else tests
    if kind == "capability":
        path = root / "System/Capabilities/demo/SKILL.md"
        ctype = "component_type: capability\ntype: capability"
    elif kind == "workflow":
        path = root / "System/Workflows/demo.md"
        ctype = "type: workflow\ncomponent_type: workflow"
    else:
        path = root / "System/Agents/demo/AGENT.md"
        ctype = "component_type: agent\ntype: agent"
    path.parent.mkdir(parents=True, exist_ok=True)
    test_yaml = "\n".join(f"- {item}" for item in tests)
    evaluation_yaml = ("x_runtime_evaluations: []" if not evaluations else
                       "x_runtime_evaluations:\n" +
                       "\n".join(f"- {item}" for item in evaluations))
    path.write_text(
        f"---\nid: {cid}\n{ctype}\nstatus: active\nversion: {version}\n"
        f"tests:\n{test_yaml}\n{evaluation_yaml}\nsummary: demo\n---\n",
        encoding="utf-8",
    )
    return path


def _test_target(root: Path):
    path = root / "System/Tests/scripts/test_demo.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# evidence fixture\n", encoding="utf-8")


def _result(root: Path, cid="capability-demo", version="1.0.0", result="pass"):
    path = root / f"System/Tests/results/{cid}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"id: result-{cid}\ncomponent: {cid}\nversion: {version}\nresult: {result}\n",
        encoding="utf-8",
    )


class ComponentEvidenceTests(unittest.TestCase):
    def test_current_version_pass_is_green(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _component(root)
            _test_target(root)
            _result(root)
            self.assertTrue(audit_core_component_evidence(str(root)).ok)

    def test_missing_and_stale_results_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _component(root)
            _test_target(root)
            audit = audit_core_component_evidence(str(root))
            self.assertEqual(audit.count("result-missing"), 1)
            _result(root, version="0.9.0")
            audit = audit_core_component_evidence(str(root))
            self.assertEqual(audit.count("result-version-stale"), 1)

    def test_versioned_historical_result_does_not_compete_with_current_record(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _component(root)
            _test_target(root)
            _result(root)
            historical = root / "System/Tests/results/capability-demo-v0.9.0.yaml"
            historical.write_text(
                "component: capability-demo\nversion: 0.9.0\nresult: fail\n",
                encoding="utf-8",
            )
            self.assertTrue(audit_core_component_evidence(str(root)).ok)

    def test_workflow_and_confined_exact_test_references_are_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _component(root, kind="workflow", cid="workflow-demo", tests=["../outside.py"])
            _result(root, cid="workflow-demo")
            audit = audit_core_component_evidence(str(root))
            self.assertEqual(audit.active_components, 1)
            self.assertEqual(audit.count("test-ref-invalid"), 1)

    def test_behavioral_evaluations_are_separate_and_safely_confined(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _component(root, evaluations=["../outside"])
            _test_target(root)
            _result(root)
            audit = audit_core_component_evidence(str(root))
            self.assertEqual(audit.count("evaluation-ref-invalid"), 1)

    def test_symlink_test_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _component(root)
            external = root / "external.py"
            external.write_text("x\n", encoding="utf-8")
            link = root / "System/Tests/scripts/test_demo.py"
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(external, link)
            _result(root)
            self.assertEqual(audit_core_component_evidence(str(root)).count("test-ref-invalid"), 1)

    def test_live_inventory_has_current_automated_evidence(self):
        audit = audit_core_component_evidence(str(ROOT))
        self.assertEqual(audit.active_components, 19)
        self.assertEqual(len(audit.findings), 0)


if __name__ == "__main__":
    unittest.main()
