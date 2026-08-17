"""The decisions space (DEC-095): the generated register derives numbering from
frontmatter, so two decisions recorded in parallel cannot collide by construction.

The estate this product grew from logged FOUR live register collisions from
hand-claimed numbers ("check the register first" empirically fails under parallel
sessions). The cure is structural: ids are dated slugs, the human-readable
register is generated newest-first from frontmatter on every `aios generate`,
and no record ever claims a number. These tests simulate the two-parallel-creates
race and prove the register is deterministic regardless of creation order.

Run: python3 -m unittest System.Tests.scripts.test_decisions
"""
import os, sys, shutil, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                                   # noqa: E402
from cmd import generate as gen_mod, links as links_mod, validate as val_mod  # noqa: E402


class Args:
    json = False


DECISION = """---
id: {did}
type: decision
status: active
decided_at: {decided}
decision_makers:
- Test Owner
project: {project}
created: {decided}
updated: {decided}
summary: "{summary}"
---

# {title}

## Decision

{summary}
"""

PROJECT = """---
id: project-garden-plan
type: project
stage: active
created: 2026-07-20
updated: 2026-07-20
summary: "Seeded project for decision scoping."
---

# Garden Plan
"""


def mini_vault(tmp):
    for d in ("System/Schemas", "System/Registries", "System/Journal",
              "Decisions", "10 Projects", "20 Knowledge"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as stream:
        stream.write(product_manifest())
    for f in os.listdir(os.path.join(VAULT, "System", "Schemas")):
        shutil.copy(os.path.join(VAULT, "System", "Schemas", f),
                    os.path.join(tmp, "System", "Schemas"))
    shutil.copy(os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                os.path.join(tmp, "System", "Registries"))
    with open(os.path.join(tmp, "System", "Journal", "change-journal.md"), "w") as stream:
        stream.write("# Journal\n")
    return tmp


def write_decision(tmp, slug, decided, summary, project=""):
    did = f"decision-{decided}-{slug}"
    p = os.path.join(tmp, "Decisions", f"Decision - {slug}.md")
    with open(p, "w", encoding="utf-8") as stream:
        stream.write(DECISION.format(
            did=did, decided=decided, project=project, summary=summary,
            title=slug.replace("-", " ")))
    return did


def register_text(tmp):
    p = os.path.join(tmp, "System", "Generated", "index-decision.md")
    with open(p, encoding="utf-8") as f:
        # normalize the volatile generation timestamp out before comparing
        return "\n".join(l for l in f.read().splitlines()
                         if not l.startswith("generated_at:"))


class TestParallelCreatesCannotCollide(unittest.TestCase):
    """DoD-2: the two-parallel-creates race, simulated. Two sessions each record
    a decision on the same day without seeing each other's work; after both land,
    the register must be identical regardless of which landed first, both records
    must be present, and neither ever claimed a number."""

    def _branch(self, order):
        tmp = mini_vault(tempfile.mkdtemp())
        try:
            with open(os.path.join(tmp, "10 Projects", "Garden Plan.md"), "w") as stream:
                stream.write(PROJECT)
            for slug, summary in order:
                write_decision(tmp, slug, "2026-07-25", summary)
            rep = Report("generate"); gen_mod.run(tmp, Args(), rep)
            self.assertFalse(rep.errors, rep.errors)
            return register_text(tmp)
        finally:
            self._tmps.append(tmp)

    def setUp(self):
        self._tmps = []

    def tearDown(self):
        for t in self._tmps:
            shutil.rmtree(t, ignore_errors=True)

    def test_register_identical_regardless_of_creation_order(self):
        a = [("annual-plan", "Go with the annual plan."),
             ("backup-approach", "Weekly drive rotation.")]
        reg1 = self._branch(a)
        reg2 = self._branch(list(reversed(a)))   # the other branch landed first
        self.assertEqual(reg1, reg2)
        self.assertIn("decision-2026-07-25-annual-plan", reg1)
        self.assertIn("decision-2026-07-25-backup-approach", reg1)

    def test_same_day_ties_break_on_id_deterministically(self):
        reg = self._branch([("zeta-choice", "Z."), ("alpha-choice", "A.")])
        lines = [l for l in reg.splitlines() if l.startswith("- 2026-07-25")]
        self.assertEqual(len(lines), 2)
        # same decided_at: reverse sort on (date, id) puts the LATER id first —
        # arbitrary but deterministic, which is the whole point
        self.assertIn("zeta-choice", lines[0])
        self.assertIn("alpha-choice", lines[1])

    def test_no_number_is_ever_claimed(self):
        reg = self._branch([("annual-plan", "Go with the annual plan.")])
        self.assertNotIn("DEC-", reg)
        for line in reg.splitlines():
            if line.startswith("- "):
                self.assertNotRegex(line, r"\bD-\d")

    def test_identical_slug_collision_is_surfaced_not_silent(self):
        """The one way two parallel creates CAN collide is minting the same dated
        slug. That must surface as a validate error (duplicate id), never merge
        silently."""
        tmp = mini_vault(tempfile.mkdtemp()); self._tmps.append(tmp)
        write_decision(tmp, "annual-plan", "2026-07-25", "First.")
        did = "decision-2026-07-25-annual-plan"
        with open(os.path.join(tmp, "Decisions", "Decision - annual-plan (2).md"), "w") as stream:
            stream.write(DECISION.format(did=did, decided="2026-07-25", project="",
                                         summary="Second.", title="annual plan"))
        rep = Report("validate"); val_mod.run(tmp, Args(), rep)
        self.assertTrue(any("duplicate id" in e for e in rep.errors), rep.errors)


class TestRegisterView(unittest.TestCase):
    def setUp(self):
        self.tmp = mini_vault(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_newest_first_and_grouped_by_project(self):
        with open(os.path.join(self.tmp, "10 Projects", "Garden Plan.md"), "w") as stream:
            stream.write(PROJECT)
        write_decision(self.tmp, "old-choice", "2026-07-01", "Old.")
        write_decision(self.tmp, "garden-beds", "2026-07-25", "Raised beds.",
                       project="project-garden-plan")
        rep = Report("generate"); gen_mod.run(self.tmp, Args(), rep)
        reg = register_text(self.tmp)
        # newest first in the flat list
        self.assertLess(reg.index("garden-beds"), reg.index("old-choice"))
        # per-project view (D2): the scoped decision appears under its project
        self.assertIn("## By project", reg)
        self.assertIn("### `project-garden-plan`", reg)
        # the project note gains an inbound decisions line in the reverse views
        with open(os.path.join(self.tmp, "System", "Generated",
                               "reverse-relationships.md"), encoding="utf-8") as stream:
            rev = stream.read()
        self.assertIn("project-garden-plan", rev)
        self.assertIn("decisions: decision-2026-07-25-garden-beds", rev)

    def test_superseded_records_leave_the_register_but_not_the_folder(self):
        write_decision(self.tmp, "kept", "2026-07-25", "Current.")
        did = write_decision(self.tmp, "gone", "2026-07-10", "Replaced.")
        p = os.path.join(self.tmp, "Decisions", "Decision - gone.md")
        with open(p) as stream:
            text = stream.read()
        with open(p, "w") as stream:
            stream.write(text.replace("status: active", "status: superseded"))
        rep = Report("generate"); gen_mod.run(self.tmp, Args(), rep)
        reg = register_text(self.tmp)
        self.assertIn("decision-2026-07-25-kept", reg)
        self.assertNotIn(did, reg)
        self.assertTrue(os.path.exists(p))   # marked, never deleted

    def test_project_reference_is_link_checked(self):
        """D2's scoping field is a real reference: a dead project id must be an
        error, same as any relation field."""
        write_decision(self.tmp, "scoped", "2026-07-25", "Scoped.",
                       project="project-does-not-exist")
        rep = Report("links"); links_mod.run(self.tmp, Args(), rep)
        self.assertTrue(any("project" in e and "project-does-not-exist" in e
                            for e in rep.errors), rep.errors)


if __name__ == "__main__":
    unittest.main()
