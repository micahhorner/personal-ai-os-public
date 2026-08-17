"""Executable source-contract regressions for active core procedures.

These tests prove that the shipped procedure still contains its load-bearing
rules and wiring.  They do not execute or certify a runtime's judgment in the
separate behavioral evaluations.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "System" / "Scripts"))

from lib.frontmatter import parse_file


class CoreProcedureContractTests(unittest.TestCase):
    def assert_contract(self, rel, *, cid, required=(), meta_contains=None):
        note = parse_file(str(ROOT / rel), str(ROOT))
        self.assertIsNone(note.error)
        self.assertEqual(note.meta.get("id"), cid)
        self.assertEqual(note.meta.get("status"), "active")
        for token in required:
            self.assertIn(token, note.body, f"{cid} lost source-contract rule: {token}")
        for field, values in (meta_contains or {}).items():
            actual = note.meta.get(field) or []
            for value in values:
                self.assertIn(value, actual, f"{cid} lost {field}: {value}")

    def test_adversary(self):
        self.assert_contract("System/Capabilities/adversary/SKILL.md", cid="capability-adversary",
                             required=("construction starts", "human decides", "falsifier"))

    def test_build_extension(self):
        self.assert_contract("System/Capabilities/build-extension/SKILL.md", cid="capability-build-extension",
                             required=("human sign-off", "adversary gate", "Activate"),
                             meta_contains={"dependencies": ["capability-adversary"]})

    def test_import_vault(self):
        self.assert_contract("System/Capabilities/import-vault/SKILL.md", cid="capability-import-vault",
                             required=("read-only", "dry-run", "never invent mappings", "checkpoint"))

    def test_ingest_and_connect(self):
        self.assert_contract("System/Capabilities/ingest-and-connect/SKILL.md",
                             cid="capability-ingest-and-connect",
                             required=("measure the split", "third-voice", "status: draft", "never auto-promote"))

    def test_maintain_vault(self):
        self.assert_contract("System/Capabilities/maintain-vault/SKILL.md", cid="capability-maintain-vault",
                             required=("freshness", "recommend", "never"))

    def test_manage_packs(self):
        self.assert_contract("System/Capabilities/manage-packs/SKILL.md", cid="capability-manage-packs",
                             required=("review", "receipt", "rollback"))

    def test_manage_todo(self):
        self.assert_contract("System/Capabilities/manage-todo/SKILL.md", cid="capability-manage-todo",
                             required=("The item contract", "Ask at most ONE", "Link-check", "never silently deleted"))

    def test_method_kit(self):
        self.assert_contract("System/Capabilities/method-kit/SKILL.md", cid="capability-method-kit",
                             required=("one question at a time", "conservative default", "user layer", "Ratify"))

    def test_record_decision(self):
        self.assert_contract("System/Capabilities/record-decision/SKILL.md", cid="capability-record-decision",
                             required=("human", "decision", "supersed"))

    def test_recover(self):
        self.assert_contract("System/Capabilities/recover/SKILL.md", cid="capability-recover",
                             required=("checkpoint", "confirm", "validate"))

    def test_retrieve_context(self):
        self.assert_contract("System/Capabilities/retrieve-context/SKILL.md", cid="capability-retrieve-context",
                             required=("privacy predicate", "fail closed", "abstain honestly"))

    def test_safe_write(self):
        self.assert_contract("System/Capabilities/safe-write/SKILL.md", cid="capability-safe-write",
                             required=("approval", "Resolve first", "aios validate"))

    def test_session_handoff(self):
        self.assert_contract("System/Capabilities/session-handoff/SKILL.md", cid="capability-session-handoff",
                             required=("Journal sweep", "Checkpoint", "Verify before relying", "honest stopping point"))

    def test_start_project(self):
        self.assert_contract("System/Capabilities/start-project/SKILL.md", cid="capability-start-project",
                             required=("project", "working", "user"))

    def test_extension_builder_agent(self):
        self.assert_contract("System/Agents/extension-builder/AGENT.md", cid="agent-extension-builder",
                             required=("human sign-off", "documentation", "human approval"),
                             meta_contains={"capabilities_used": ["capability-build-extension"]})

    def test_onboarding_guide_agent(self):
        self.assert_contract("System/Agents/onboarding-guide/AGENT.md", cid="agent-onboarding-guide",
                             required=("One question at a time", "Interruption must always be free", "never rush consent"),
                             meta_contains={"capabilities_used": ["capability-method-kit", "capability-manage-todo"]})

    def test_steward_agent(self):
        self.assert_contract("System/Agents/steward/AGENT.md", cid="agent-steward",
                             required=("never drain", "lessons come first", "recommend-only"))

    def test_inbox_processing_workflow(self):
        self.assert_contract("System/Workflows/inbox-processing.md", cid="workflow-inbox-processing",
                             required=("user starts this", "never runs on its own", "prompt, never a run"))

    def test_weekly_maintenance_workflow(self):
        self.assert_contract("System/Workflows/weekly-maintenance.md", cid="workflow-weekly-maintenance",
                             required=("Report the Inbox", "do not drain", "aios checkpoint --zip"))


if __name__ == "__main__":
    unittest.main()
