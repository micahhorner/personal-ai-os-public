from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from . import compose_gate


class TestComposeGate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.matrix = self.root / "matrix.json"
        self.matrix.write_text(json.dumps({
            "schema_version": 1,
            "target": {"ref": "a" * 40, "commit": "a" * 40,
                       "version": "1.64.1"},
            "sources": [{"id": "old", "ref": "b" * 40,
                         "commit": "b" * 40, "version": "1.43.0",
                         "disposition": "candidate-anchor"}],
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    def recovery(self, mode, marker):
        return {"fixture_mode": mode, "recovery_qualified": True,
                "product_issued_command": marker}

    def qualification(self):
        return {
            "verdict": "passed",
            "target": {"commit": "a" * 40, "version": "1.64.1",
                       "product_state": {"exact_file_hashes": {}}},
            "sources": [
                {"id": "clean", "recovery": self.recovery("clean-git", "a")},
                {"id": "zip", "recovery": self.recovery("no-git", "zip")},
            ],
        }

    def test_refuses_failed_qualification_before_gate(self):
        with self.assertRaisesRegex(compose_gate.ComposeError, "must be passed"):
            compose_gate.compose(
                repository=str(self.root), matrix_path=str(self.matrix),
                qualification_path=self.write("q.json", {"verdict": "failed"}),
                source_check_path=self.write("s.json", {}),
                fault_path=self.write("f.json", {}), minimum_version="1.43.0")

    def test_passes_exact_evidence_to_final_gate(self):
        qualification = {
            "verdict": "passed",
            "target": {"commit": "a" * 40, "version": "1.64.1",
                       "product_state": {"exact_file_hashes": {}}},
            "sources": [
                {"id": "z-clean", "recovery": self.recovery("clean-git", "z")},
                {"id": "a-clean", "recovery": self.recovery("clean-git", "a")},
                {"id": "no-git", "recovery": self.recovery("no-git", "zip")},
            ],
        }
        record = mock.Mock(commit="a" * 40, system_version="1.64.1")
        gate = mock.Mock(to_dict=lambda: {"verdict": "passed", "checks": []})
        with mock.patch.object(compose_gate, "discover_and_verify_authoritative_coverage",
                               return_value={"name": "coverage", "passed": True}), \
             mock.patch.object(compose_gate.estate, "discover_mainline_states",
                               return_value=["a" * 40]), \
             mock.patch.object(compose_gate.estate, "load_release", return_value=record), \
             mock.patch.object(compose_gate, "evaluate_release_gate", return_value=gate) as evaluate:
            result = compose_gate.compose(
                repository=str(self.root), matrix_path=str(self.matrix),
                qualification_path=self.write("q.json", qualification),
                source_check_path=self.write("s.json", {"command": "source-check"}),
                fault_path=self.write("f.json", {"cases": []}),
                minimum_version="1.43.0")
        self.assertEqual("passed", result["gate"]["verdict"])
        self.assertEqual(
            [self.recovery("clean-git", "a"), self.recovery("no-git", "zip")],
            evaluate.call_args.kwargs["recovery_evidence"]["records"])

    def test_missing_mode_fails_before_authority_or_gate(self):
        qualification = {
            "verdict": "passed",
            "target": {"commit": "a" * 40, "version": "1.64.1",
                       "product_state": {}},
            "sources": [{"id": "clean", "recovery":
                         self.recovery("clean-git", "clean")}],
        }
        with self.assertRaisesRegex(compose_gate.ComposeError, "no-git"):
            compose_gate.compose(
                repository=str(self.root), matrix_path=str(self.matrix),
                qualification_path=self.write("missing.json", qualification),
                source_check_path=self.write("s2.json", {}),
                fault_path=self.write("f2.json", {}), minimum_version="1.43.0")

    def test_malformed_selected_record_is_left_for_gate_to_reject(self):
        qualification = {
            "verdict": "passed",
            "target": {"commit": "a" * 40, "version": "1.64.1",
                       "product_state": {}},
            "sources": [
                {"id": "clean", "recovery": self.recovery("clean-git", "")},
                {"id": "zip", "recovery": self.recovery("no-git", "zip")},
            ],
        }
        record = mock.Mock(commit="a" * 40, system_version="1.64.1")
        with mock.patch.object(compose_gate, "discover_and_verify_authoritative_coverage",
                               return_value={}), \
             mock.patch.object(compose_gate.estate, "discover_mainline_states",
                               return_value=["a" * 40]), \
             mock.patch.object(compose_gate.estate, "load_release", return_value=record), \
             mock.patch.object(compose_gate, "evaluate_release_gate",
                               side_effect=ValueError("malformed selected record")):
            with self.assertRaisesRegex(ValueError, "malformed selected"):
                compose_gate.compose(
                    repository=str(self.root), matrix_path=str(self.matrix),
                    qualification_path=self.write("bad.json", qualification),
                    source_check_path=self.write("s3.json", {}),
                    fault_path=self.write("f3.json", {}), minimum_version="1.43.0")

    def test_split_authority_derives_history_without_disclosing_private_path(self):
        target = mock.Mock(commit="a" * 40, system_version="1.64.1")
        historical = mock.Mock(commit="b" * 40, system_version="1.43.0")
        private = "/private/sensitive/history"

        def load(repository, ref):
            return target if repository == str(self.root) else historical

        gate = mock.Mock(to_dict=lambda: {"verdict": "passed", "checks": []})
        with mock.patch.object(compose_gate.estate, "load_release", side_effect=load), \
             mock.patch.object(compose_gate.estate, "discover_mainline_states",
                               return_value=("b" * 40,)), \
             mock.patch.object(compose_gate, "evaluate_release_gate",
                               return_value=gate):
            result = compose_gate.compose(
                repository=str(self.root), matrix_path=str(self.matrix),
                qualification_path=self.write("split-q.json", self.qualification()),
                source_check_path=self.write("split-s.json", {}),
                fault_path=self.write("split-f.json", {}),
                minimum_version="1.43.0", authority_repository=private,
                authority_ref="refs/heads/main", authority_commit="b" * 40)

        self.assertEqual("split-git-mainline-estate",
                         result["authority"]["derivation"])
        self.assertNotIn(private, json.dumps(result))

    def test_split_authority_requires_complete_immutable_pin(self):
        with self.assertRaisesRegex(compose_gate.ComposeError, "requires"):
            compose_gate.compose(
                repository=str(self.root), matrix_path=str(self.matrix),
                qualification_path=self.write("partial-q.json", self.qualification()),
                source_check_path=self.write("partial-s.json", {}),
                fault_path=self.write("partial-f.json", {}),
                minimum_version="1.43.0", authority_repository="/private/history")

    def test_split_authority_ref_movement_fails_closed(self):
        target = mock.Mock(commit="a" * 40, system_version="1.64.1")
        moved = mock.Mock(commit="c" * 40, system_version="1.43.0")
        with mock.patch.object(
                compose_gate.estate, "load_release",
                side_effect=(target, moved)):
            with self.assertRaisesRegex(compose_gate.ComposeError, "pinned commit"):
                compose_gate.compose(
                    repository=str(self.root), matrix_path=str(self.matrix),
                    qualification_path=self.write("moved-q.json", self.qualification()),
                    source_check_path=self.write("moved-s.json", {}),
                    fault_path=self.write("moved-f.json", {}),
                    minimum_version="1.43.0", authority_repository="/private/history",
                    authority_ref="refs/heads/main", authority_commit="b" * 40)

    def test_split_authority_omission_fails_matrix_coverage(self):
        target = mock.Mock(commit="a" * 40, system_version="1.64.1")
        historical = mock.Mock(commit="b" * 40, system_version="1.43.0")
        with mock.patch.object(
                compose_gate.estate, "load_release",
                side_effect=(target, historical)), \
             mock.patch.object(compose_gate.estate, "discover_mainline_states",
                               return_value=()):
            with self.assertRaisesRegex(ValueError, "authoritative-complete"):
                compose_gate.compose(
                    repository=str(self.root), matrix_path=str(self.matrix),
                    qualification_path=self.write("omit-q.json", self.qualification()),
                    source_check_path=self.write("omit-s.json", {}),
                    fault_path=self.write("omit-f.json", {}),
                    minimum_version="1.43.0", authority_repository="/private/history",
                    authority_ref="refs/heads/main", authority_commit="b" * 40)


if __name__ == "__main__":
    unittest.main()
