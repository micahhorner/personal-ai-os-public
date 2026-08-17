"""SPEC-ingest-triage (v1.38.0): the prose contracts of the reordered intake
pipeline, pinned as regressions.

The defect class here is DOCUMENTED PROSE THAT INSTRUCTS AN ERROR: step 2 told
every runtime to write `provider` while `source.yaml`'s real field is
`provided_by` (a validation error by instruction), and step 4 pointed at "the
four outcomes" which were defined nowhere. Prose contracts drift silently, so
the load-bearing strings are asserted here the way doc-audit asserts counts.
Run: python3 -m unittest System.Tests.scripts.test_ingest_triage (from repo root
via discover)."""
import os
import re
import unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SKILL = os.path.join(VAULT, "System", "Capabilities", "ingest-and-connect", "SKILL.md")
TEMPLATE = os.path.join(VAULT, "System", "Templates", "delta-register.md")
ONBOARD = os.path.join(VAULT, "System", "Onboarding", "AI Onboarding Procedure.md")
SCHEMA = os.path.join(VAULT, "System", "Schemas", "source.yaml")
FIXTURE = os.path.join(VAULT, "System", "Tests", "fixtures", "25-ingest-triage")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestProviderBugFixed(unittest.TestCase):
    """DoD-4: step 2's `provider` → `provided_by` (the doc instructed a
    validation error). The schema is the source of truth; the prose that
    instructs writes into it must use its real field names."""

    def test_schema_field_is_provided_by(self):
        text = _read(SCHEMA)
        self.assertIn("provided_by", text)
        self.assertIsNone(re.search(r"^\s*provider\s*:", text, re.M),
                          "source.yaml must not grow a bare `provider` field")

    def test_capability_prose_uses_real_field_name(self):
        text = _read(SKILL)
        self.assertIn("`provided_by`", text)

    def test_no_bare_provider_token_in_intake_prose(self):
        # The regression: prose telling a runtime to label a capture with
        # "provider". `provided_by` is fine; a bare `provider` token is not.
        for path in (SKILL, ONBOARD):
            text = _read(path)
            hits = [m for m in re.finditer(r"\bprovider\b(?!_|-)", text)
                    if not text[max(0, m.start() - 9):m.start()].endswith("provided_")]
            self.assertEqual([], [text[max(0, h.start() - 40):h.end() + 20] for h in hits],
                             f"{os.path.relpath(path, VAULT)} still instructs the "
                             f"`provider` field — source.yaml's field is `provided_by`")


class TestFourOutcomeFamilies(unittest.TestCase):
    """DoD-1: the four families are defined in the capability and the old
    dangling pointer ("Every effect → one of the four outcomes") resolves."""

    def test_families_defined(self):
        text = _read(SKILL)
        for family in ("**Knowledge**", "**Action**", "**Governance**", "**Nothing**"):
            self.assertIn(family, text, f"outcome family {family} must be defined in 3t")
        self.assertIn("four outcome families", text)

    def test_dangling_pointer_resolved(self):
        text = _read(SKILL)
        self.assertNotIn("one of the four outcomes.", text,
                         "step 4's four-outcomes phrase must resolve to the "
                         "defined families, not dangle")


class TestRegisterBeforeBuildOut(unittest.TestCase):
    """The reorder: extract → triage register → route → build out only what
    routed to Knowledge. The register precedes build-out in the pipeline, and
    the doc's own ordering must say so."""

    def test_triage_step_precedes_build_out(self):
        text = _read(SKILL)
        triage = text.find("3t. **Triage")
        build = text.find("Then build it out")
        self.assertGreater(triage, -1, "triage step 3t missing")
        self.assertGreater(build, -1, "build-out step 3b missing")
        self.assertLess(triage, build, "triage must come before build-out")

    def test_zero_notes_before_register(self):
        self.assertIn("zero notes exist before the register does", _read(SKILL))

    def test_build_out_scoped_to_knowledge_routed(self):
        self.assertIn("Only findings the register routed to **Knowledge** reach this step",
                      _read(SKILL))

    def test_3a_doctrine_untouched(self):
        # The fence in SPEC-ingest-triage: the reorder moves WHEN 3b runs, not
        # what 3a/3b say. Spot-check 3a/3b's load-bearing sentences.
        text = _read(SKILL)
        for sentence in (
            "the test is **fidelity, not authorship**",
            "absorbing the assistant's thesis into a note that carries their name and no attribution",
            "attribution is the floor, not the ceiling",
            "The human's claim is the thesis and the spine.",
            "measure the split — do not estimate it",
        ):
            self.assertIn(sentence, text, f"3a/3b doctrine sentence lost: {sentence!r}")


class TestDeltaRegisterArtifact(unittest.TestCase):
    """The register is a defined artifact: template shipped, columns canonized
    from the two proven 2026-07-14 prototypes."""

    COLUMNS = ("Finding", "Source line", "Voice", "Family", "Rationale", "Owner ruling")

    def test_template_exists_with_columns(self):
        self.assertTrue(os.path.exists(TEMPLATE), "System/Templates/delta-register.md missing")
        text = _read(TEMPLATE)
        for col in self.COLUMNS:
            self.assertIn(col, text, f"register column {col!r} missing from template")
        self.assertIn("subtype: finding", text)
        self.assertIn("status: draft", text)

    def test_capability_names_the_template(self):
        self.assertIn("System/Templates/delta-register.md", _read(SKILL))


class TestPromotionChecklists(unittest.TestCase):
    """DoD-3: per-class verification checklists behind the promotion gate; a
    failing record is refused WITH the failing line named."""

    def test_shared_floor_and_classes_present(self):
        text = _read(SKILL)
        self.assertIn("per-class checklists", text)
        for klass in ("**note**", "**decision**", "**entity**", "**procedure**", "**source**"):
            self.assertIn(klass, text, f"class checklist {klass} missing at the gate")

    def test_refusal_names_the_failure(self):
        self.assertIn("refused promotion with the failing line named", _read(SKILL))


class TestFixtureNineteen(unittest.TestCase):
    """DoD-1/2: the behavioral fixture exists, seeds all four families, and is
    wired into the capability's tests list."""

    def test_fixture_files_exist(self):
        for rel in ("expected.md", os.path.join("input", "run.md"),
                    os.path.join("input", "harvest-transcript.md")):
            self.assertTrue(os.path.exists(os.path.join(FIXTURE, rel)),
                            f"fixture 19 missing {rel}")

    def test_capability_lists_fixture(self):
        self.assertIn("System/Tests/fixtures/25-ingest-triage", _read(SKILL))

    def test_expected_covers_all_families_and_regression(self):
        text = _read(os.path.join(FIXTURE, "expected.md"))
        for token in ("Knowledge", "Action", "Governance", "Nothing",
                      "provided_by", "before any knowledge note", "failing line named"):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
