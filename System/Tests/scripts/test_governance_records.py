"""Focused tests for the read-only product decision-register checker."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


VAULT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(VAULT / "System" / "Scripts"))

from lib.governance_records import audit_active_decisions  # noqa: E402


def _write(path: Path, rows: list[str]) -> Path:
    path.write_text(
        "# Active decisions (compact)\n\n" + "\n\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return path


class TestGovernanceRecordIntegrity(unittest.TestCase):
    def audit(self, rows: list[str]):
        temporary = tempfile.TemporaryDirectory(prefix="governance records ")
        self.addCleanup(temporary.cleanup)
        return audit_active_decisions(
            _write(Path(temporary.name) / "Active Decisions.md", rows)
        )

    def test_clean_descending_register_with_gaps_and_reference_is_green(self):
        audit = self.audit([
            "- **DEC-121 (product)** — Current rule.",
            "- **DEC-016 + DEC-121** — Earlier rule, now qualified by DEC-121.",
            "- **DEC-005/007** — Stable identifiers and references.",
        ])
        self.assertTrue(audit.ok, audit.findings)
        self.assertEqual(
            [item.decision_id for item in audit.definitions],
            ["DEC-121", "DEC-016", "DEC-005"],
        )

    def test_duplicate_id_is_reported_once_per_excess_definition(self):
        audit = self.audit([
            "- **DEC-010** — First body.",
            "- **DEC-010 (product)** — Different body.",
        ])
        self.assertEqual(audit.count("decision-id-duplicate"), 1)
        finding = next(
            item for item in audit.findings
            if item.code == "decision-id-duplicate"
        )
        self.assertEqual((finding.other_line, finding.line), (3, 5))

    def test_duplicate_normalized_body_across_distinct_ids_is_reported(self):
        audit = self.audit([
            "- **DEC-011** — The   SAME standing rule.",
            "- **DEC-010** — the same STANDING rule.",
        ])
        self.assertEqual(audit.count("decision-body-duplicate"), 1)
        finding = next(
            item for item in audit.findings
            if item.code == "decision-body-duplicate"
        )
        self.assertEqual(finding.decision_id, "DEC-010")
        self.assertEqual((finding.other_line, finding.line), (3, 5))

    def test_ascending_or_equal_adjacent_id_is_an_ordering_defect(self):
        audit = self.audit([
            "- **DEC-010** — Ten.",
            "- **DEC-011** — Eleven is misplaced.",
        ])
        self.assertEqual(audit.count("decision-order"), 1)
        self.assertEqual(
            next(item for item in audit.findings
                 if item.code == "decision-order").decision_id,
            "DEC-011",
        )


class TestCurrentProductRegister(unittest.TestCase):
    def test_current_register_is_unique_and_strictly_descending(self):
        audit = audit_active_decisions(
            VAULT / "System" / "Governance" / "Active Decisions.md"
        )
        self.assertEqual(audit.definition_count, 85)
        self.assertEqual(audit.unique_id_count, 85)
        self.assertEqual(audit.count("decision-id-duplicate"), 0)
        self.assertEqual(audit.count("decision-body-duplicate"), 0)
        self.assertEqual(audit.count("decision-order"), 0)
        self.assertTrue(audit.ok, audit.findings)


if __name__ == "__main__":
    unittest.main()
