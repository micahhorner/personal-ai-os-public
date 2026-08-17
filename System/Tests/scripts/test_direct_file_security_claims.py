"""Contract tests for honest direct-file and brokered-privacy claims."""
from __future__ import annotations

import os
import unittest


VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _read(relative):
    with open(os.path.join(VAULT, relative), encoding="utf-8") as stream:
        return stream.read()


class TestDirectFileSecurityClaims(unittest.TestCase):
    def test_public_entrypoint_names_compliance_not_sandbox(self):
        text = _read("README.md")
        self.assertIn("compliance rules", text)
        self.assertIn("not an OS sandbox", text)
        self.assertIn("does not ship a mechanically isolated brokered mode", text)

    def test_canonical_privacy_doc_names_native_bypass(self):
        text = _read("System/Governance/Privacy and Boundaries.md")
        self.assertIn("not a physical barrier", text)
        self.assertIn("does not currently ship a qualifying launcher or sandbox", text)

    def test_broker_design_cannot_be_mistaken_for_a_feature(self):
        text = _read("System/Documentation/Brokered Retrieval Design.md")
        self.assertIn("DESIGN ONLY / NOT IMPLEMENTED", text)
        self.assertIn("**FOLLOW-ON.**", text)
        self.assertIn("does not create brokered mode", text)

    def test_hostile_content_is_in_security_scope(self):
        text = _read("SECURITY.md")
        self.assertIn("Hostile-content instruction attacks", text)
        self.assertIn("ability to cross the instruction boundary is in scope", text)


if __name__ == "__main__":
    unittest.main()
