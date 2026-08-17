"""The adversary pre-build gate (DEC-099).

A red-team pass is unfalsifiable by nature: plausible objections are free, and a
report full of them looks exactly like a report full of real findings. The
capability's whole defence against becoming theater is structural — a fixed report
shape, a falsifier on every finding, a mandatory "one thing this gets right", and
two permanent evals (a seeded-flaw fixture and a retrodiction against a real plan
with a known post-hoc correction).

These tests pin that structure. They cannot test judgment — the fixtures do that,
behaviourally — but they can prove the machinery that makes judgment checkable is
still wired: the gate is named in `build-extension`, the router can reach the
capability, both evals exist and are in the battery, and the seeded artifacts still
contain the defects they are supposed to plant.

One of them is a leak regression. The first run of fixture 29 was partly spoiled
because the capability's own SKILL.md illustrated itself with the very case the
retrodiction eval uses — and SKILL.md is loaded on every run. A worked example
inside the procedure hands the answer to the eval that keeps the procedure honest,
so the file must stay unillustrated.

Run: python3 -m unittest System.Tests.scripts.test_adversary
"""
import os
import unittest

try:
    import yaml
except ImportError:                                              # pragma: no cover
    yaml = None

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SKILL = os.path.join(VAULT, "System", "Capabilities", "adversary", "SKILL.md")
BUILD = os.path.join(VAULT, "System", "Capabilities", "build-extension", "SKILL.md")
ROUTER = os.path.join(VAULT, "System", "Runtime", "Task Router.yaml")
BATTERY = os.path.join(VAULT, "System", "Tests", "Certification Battery.md")
FIXTURES = os.path.join(VAULT, "System", "Tests", "fixtures")
SEEDED = os.path.join(FIXTURES, "28-adversary-seeded-flaw")
RETRO = os.path.join(FIXTURES, "29-adversary-retrodiction")


def read(path):
    """Whitespace-normalized: these are prose files, so a rule can move across a
    line break without changing meaning, and a test that breaks on rewrapping is a
    test that gets deleted."""
    with open(path, encoding="utf-8") as fh:
        return " ".join(fh.read().split())


def read_raw(path):
    """Structure preserved — for YAML, where whitespace IS the syntax."""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestCapabilityContract(unittest.TestCase):
    def test_capability_exists_and_is_active(self):
        text = read(SKILL)
        self.assertIn("id: capability-adversary", text)
        self.assertIn("status: active", text)

    def test_declares_both_evals_as_its_tests(self):
        text = read(SKILL)
        self.assertIn("System/Tests/fixtures/28-adversary-seeded-flaw", text)
        self.assertIn("System/Tests/fixtures/29-adversary-retrodiction", text)

    def test_report_carries_all_five_fixed_sections(self):
        """Fixed shape, because a variable shape drops the section that hurt."""
        text = read(SKILL).lower()
        for phrase in ("load-bearing assumptions",
                       "failure modes the plan doesn't name",
                       "the cheaper version",
                       "scope traps and hidden dependencies",
                       "plan-killer"):
            self.assertIn(phrase, text, "report section missing: %s" % phrase)

    def test_verdict_scale_is_exactly_three_values(self):
        text = read(SKILL)
        for verdict in ("proceed", "proceed-with-amendments", "redesign"):
            self.assertIn(verdict, text)
        self.assertIn("one of exactly three", text)

    def test_every_finding_needs_a_line_and_a_falsifier(self):
        text = read(SKILL).lower()
        self.assertIn("cites the line it attacks", text)
        self.assertIn("falsif", text)

    def test_anti_theater_rule_is_stated(self):
        """A pass that only objects is as unfalsifiable as one that only praises."""
        text = read(SKILL).lower()
        self.assertIn("at least one thing the plan gets right", text)

    def test_mandatory_closing_line_about_demand(self):
        text = read(SKILL).lower()
        self.assertIn("did not test demand", text)

    def test_report_is_working_material_never_knowledge(self):
        text = read(SKILL)
        self.assertIn("type: working", text)
        self.assertIn("never lands in `20 Knowledge/`", text)

    def test_it_advises_and_never_blocks(self):
        text = read(SKILL).lower()
        self.assertIn("advises, never approves, and never blocks", text)

    def test_skips_are_recorded_never_silent(self):
        text = read(SKILL)
        self.assertIn("skipped — owner OK", text)
        self.assertIn("absence of evidence", text)

    def test_skill_md_carries_no_worked_example_of_the_retrodiction_case(self):
        """Leak regression, found by the eval itself on the first run.

        SKILL.md is loaded on every pass. Naming the retrodiction fixture's real
        case in it means the runtime is told the answer before it reads the plan,
        which silently disarms fixture 29. The fix is to keep the file
        unillustrated — the cases live in the constitution's amendment log.
        """
        text = read(SKILL).lower()
        for leak in ("three jobs", "aios measure", "measurement command"):
            self.assertNotIn(leak, text,
                             "SKILL.md leaks the retrodiction eval's answer: %r" % leak)


class TestTheGateIsWired(unittest.TestCase):
    """A gate nobody calls is decoration — the spec's own words."""

    def test_build_extension_names_the_gate_before_construction(self):
        text = read(BUILD)
        self.assertIn("adversary", text)
        self.assertIn("3b", text)
        self.assertIn("before anything is created", text)

    def test_gate_is_high_tier_only(self):
        """Gating a typo fix is how a gate becomes decoration."""
        text = read(BUILD)
        self.assertIn("High-tier build", text)
        self.assertIn("Low- and Medium-tier changes are **not** gated", text)

    def test_build_extension_depends_on_the_capability(self):
        text = read(BUILD)
        self.assertIn("capability-adversary", text)

    def test_build_extension_records_a_skip(self):
        text = read(BUILD)
        self.assertIn("adversary gate skipped", text)

    @unittest.skipIf(yaml is None, "PyYAML not installed")
    def test_router_can_reach_the_capability_on_demand(self):
        """DEC-094/DEC-095's lesson: a capability nothing routes to is the next
        forgotten convention. The on-demand trigger needs its own row."""
        router = yaml.safe_load(read_raw(ROUTER))
        row = router["modes"]["normal"].get("red-team-plan")
        self.assertIsNotNone(row, "no `red-team-plan` route — the capability is unreachable")
        self.assertIn("System/Capabilities/adversary/SKILL.md", row["load"])
        # audit-2 H-01: a row lists its FULL dependency set. adversary step 8 files
        # the report through safe-write, so the row must carry it. The omission was
        # caught by this capability's own retrodiction eval, not by review.
        self.assertIn("System/Capabilities/safe-write/SKILL.md", row["load"],
                      "red-team-plan omits safe-write, which adversary step 8 requires")

    @unittest.skipIf(yaml is None, "PyYAML not installed")
    def test_developer_lane_loads_the_capability(self):
        router = yaml.safe_load(read_raw(ROUTER))
        loads = router["modes"]["developer"]["_all"]["load"]
        self.assertIn("System/Capabilities/adversary/SKILL.md", loads)


class TestTheEvalsExistAndStillHaveTeeth(unittest.TestCase):
    """The evals ARE the justification for a component over a checklist. If they
    are ever hollowed out, the capability should be retired to five questions."""

    def test_both_fixtures_are_complete(self):
        for d in (SEEDED, RETRO):
            self.assertTrue(os.path.isdir(d), "missing fixture dir %s" % d)
            self.assertTrue(os.path.exists(os.path.join(d, "expected.md")))
            self.assertTrue(os.path.exists(os.path.join(d, "input", "run.md")))

    def test_both_are_in_the_certification_battery(self):
        text = read(BATTERY)
        self.assertIn("28 adversary-seeded-flaw", text)
        self.assertIn("29 adversary-retrodiction", text)

    def test_seeded_fixture_demands_three_of_three(self):
        text = read(os.path.join(SEEDED, "expected.md"))
        self.assertIn("Fewer than three", text)
        self.assertIn("FAIL", text)

    def test_seeded_artifact_still_contains_all_three_planted_defects(self):
        """A fixture whose input drifted is a fixture that passes for free."""
        spec = read(os.path.join(SEEDED, "input", "spec-weekly-digest.md"))
        # 1. the false assumption: a scheduler this product does not have
        self.assertIn("automatically every Sunday", spec)
        # 2. the unnamed failure mode: content leaves the machine
        self.assertIn("sends that file to my email", spec)
        # 3. the unconsidered cheaper path: it reaches for the top of the ladder
        self.assertIn("Why an agent", spec)
        # and the one thing it gets right, for the anti-theater rule
        self.assertIn("read-only", spec)

    def test_seeded_artifact_does_not_name_its_own_defects(self):
        """The planted list lives in run.md, which the runtime under test never
        reads. If it migrates into the artifact, the eval is scoring recall."""
        spec = read(os.path.join(SEEDED, "input", "spec-weekly-digest.md")).lower()
        for leak in ("planted", "seeded", "privacy", "local-only", "scheduler"):
            self.assertNotIn(leak, spec, "seeded artifact leaks its own answer: %r" % leak)

    def test_retrodiction_artifact_still_carries_the_three_job_scope(self):
        spec = read(os.path.join(RETRO, "input", "spec-aios-measure-original.md"))
        self.assertIn("The three jobs it does", spec)
        self.assertIn("Why one command", spec)

    def test_retrodiction_artifact_does_not_disclose_the_correction(self):
        spec = read(os.path.join(RETRO, "input", "spec-aios-measure-original.md")).lower()
        for leak in ("demoted", "correction", "cut to one", "shipped as one"):
            self.assertNotIn(leak, spec, "retrodiction artifact discloses its answer: %r" % leak)

    def test_retrodiction_run_sheet_fences_the_recorded_answer(self):
        run = read(os.path.join(RETRO, "input", "run.md")).lower()
        self.assertIn("changelog", run)
        self.assertIn("amendment log", run)


if __name__ == "__main__":
    unittest.main()
