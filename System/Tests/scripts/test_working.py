"""The working class (DEC-096): project working material is typed, bounded, and
checked — and the boundary holds both ways.

Before this release the schemas' `directories:` bindings were documentation only
(verified empirically: a `type: note` under `10 Projects/` validated green), so
the layer where the user actually thinks was the one layer the system did not
check. These tests pin the new contract: a typed working plan under the projects
folder validates green; the same file typed `note` errors; a `working` file in
the knowledge folder errors; the project-layer no-frontmatter warning names the
class (gently — untyped stays legal); default search excludes working records
while `--project` scope and `read --id` surface them.

Run: python3 -m unittest System.Tests.scripts.test_working
"""
from test_io import read_file, write_file
import os, sys, shutil, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                                   # noqa: E402
from cmd import validate as val_mod, search as search_mod, read_note as read_mod  # noqa: E402


class Args:
    json = False
    query = None
    domain = None
    all_states = False
    project = None
    id = None


WORKING = """---
id: {wid}
type: working
subtype: {subtype}
status: {status}
created: 2026-07-25
updated: 2026-07-25
summary: "{summary}"
---

# {title}

{body}
"""

NOTE_IN_PROJECTS = """---
id: note-misfiled-plan
type: note
status: draft
created: 2026-07-25
updated: 2026-07-25
summary: "A knowledge-typed file misfiled in the project layer."
---

# Misfiled
"""

PROJECT = """---
id: project-garden-plan
type: project
stage: active
created: 2026-07-20
updated: 2026-07-20
summary: "Seeded project."
---

# Garden Plan
"""


def mini_vault(tmp):
    for d in ("System/Schemas", "System/Registries", "System/Journal",
              "System/Runtime Profiles", "10 Projects", "20 Knowledge",
              "00 Inbox", "90 Archive"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as stream:
        stream.write(product_manifest())
    for f in os.listdir(os.path.join(VAULT, "System", "Schemas")):
        shutil.copy(os.path.join(VAULT, "System", "Schemas", f),
                    os.path.join(tmp, "System", "Schemas"))
    shutil.copy(os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                os.path.join(tmp, "System", "Registries"))
    # search's privacy predicate loads the active profile from the manifest
    shutil.copy(os.path.join(VAULT, "System", "Runtime Profiles", "claude-code.yaml"),
                os.path.join(tmp, "System", "Runtime Profiles"))
    with open(os.path.join(tmp, "System", "Journal", "change-journal.md"), "w") as stream:
        stream.write("# Journal\n")
    return tmp


def write_working(tmp, reldir, name, wid, subtype="plan", status="draft",
                  summary="A working file.", body=""):
    p = os.path.join(tmp, reldir, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as stream:
        stream.write(WORKING.format(
            wid=wid, subtype=subtype, status=status, summary=summary,
            title=name.rsplit(".", 1)[0], body=body))
    return p


def run_validate(tmp):
    rep = Report("validate")
    val_mod.run(tmp, Args(), rep)
    return rep


class WorkingBase(unittest.TestCase):
    def setUp(self):
        self.tmp = mini_vault(tempfile.mkdtemp())
        os.makedirs(os.path.join(self.tmp, "10 Projects", "Garden Plan"), exist_ok=True)
        with open(os.path.join(self.tmp, "10 Projects", "Garden Plan", "Garden Plan.md"),
                  "w", encoding="utf-8") as stream:
            stream.write(PROJECT)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestBoundaryBothWays(WorkingBase):
    """DoD-1 as amended per DEC-082: typed working plan validates green;
    working in the knowledge folder errors (new class, strict); typed note in
    the project layer is a rolled-up ADVISORY warning, never an error (legacy
    lived-in pattern — the DEC-092 grandfathering shape)."""

    def test_working_plan_in_projects_validates_green(self):
        write_working(self.tmp, os.path.join("10 Projects", "Garden Plan"),
                      "PLAN-season.md", "working-plan-season")
        rep = run_validate(self.tmp)
        self.assertFalse(rep.errors, rep.errors)

    def test_note_in_projects_is_rolled_up_warning_never_error(self):
        # DEC-082: a lived-in vault never goes red on the user's own notes
        for name in ("PLAN-misfiled.md", "PLAN-misfiled-2.md"):
            write_file(os.path.join(self.tmp, "10 Projects", "Garden Plan", name), NOTE_IN_PROJECTS.replace("note-misfiled-plan",
                                         "note-" + name[:-3].lower()), mode="w", encoding="utf-8")
        rep = run_validate(self.tmp)
        self.assertFalse(rep.errors, rep.errors)
        w = [x for x in rep.warnings if "knowledge-typed note(s)" in x]
        self.assertEqual(len(w), 1, rep.warnings)   # ONE rolled-up line
        self.assertIn("2 knowledge-typed note(s)", w[0])
        self.assertIn("type: working", w[0])
        self.assertIn("DEC-082", w[0])

    def test_working_in_knowledge_errors(self):
        write_working(self.tmp, "20 Knowledge", "escape.md", "working-escape")
        rep = run_validate(self.tmp)
        self.assertTrue(any("outside the project layer" in e for e in rep.errors), rep.errors)

    def test_working_in_inbox_and_archive_is_legal(self):
        write_working(self.tmp, "00 Inbox", "captured.md", "working-captured",
                      subtype="capture")
        write_working(self.tmp, "90 Archive", "old-plan.md", "working-old-plan",
                      status="archived")
        rep = run_validate(self.tmp)
        self.assertFalse(rep.errors, rep.errors)

    def test_missing_light_required_fields_still_error(self):
        p = os.path.join(self.tmp, "10 Projects", "Garden Plan", "PLAN-thin.md")
        write_file(p, "---\nid: working-thin\ntype: working\ncreated: 2026-07-25\n"
            "updated: 2026-07-25\nsummary: \"thin\"\n---\n\n# Thin\n", mode="w", encoding="utf-8")
        rep = run_validate(self.tmp)
        missing = [e for e in rep.errors if "missing required field" in e]
        self.assertTrue(any("'subtype'" in e for e in missing), rep.errors)
        self.assertTrue(any("'status'" in e for e in missing), rep.errors)

    def test_subtype_vocabulary_enforced(self):
        write_working(self.tmp, os.path.join("10 Projects", "Garden Plan"),
                      "PLAN-bad.md", "working-bad", subtype="masterplan")
        rep = run_validate(self.tmp)
        self.assertTrue(any("working_subtypes" in e for e in rep.errors), rep.errors)


class TestProjectLayerWarningNamesTheClass(WorkingBase):
    """DoD-3: the no-frontmatter warning on a project-layer file names the
    class; elsewhere the message is unchanged; untyped is never an error."""

    def test_untyped_project_file_warning_names_class(self):
        write_file(os.path.join(self.tmp, "10 Projects", "Garden Plan", "scratch.md"), "loose thoughts, no frontmatter\n", mode="w", encoding="utf-8")
        rep = run_validate(self.tmp)
        self.assertFalse(rep.errors, rep.errors)
        w = [x for x in rep.warnings if "scratch.md" in x]
        self.assertEqual(len(w), 1, rep.warnings)
        self.assertIn("type: working", w[0])
        self.assertIn("auto-type", w[0])

    def test_untyped_elsewhere_keeps_plain_message(self):
        write_file(os.path.join(self.tmp, "20 Knowledge", "loose.md"), "no frontmatter\n", mode="w", encoding="utf-8")
        rep = run_validate(self.tmp)
        w = [x for x in rep.warnings if "loose.md" in x]
        self.assertEqual(len(w), 1, rep.warnings)
        self.assertIn("no frontmatter", w[0])
        self.assertNotIn("type: working", w[0])


class TestRetrievalScope(WorkingBase):
    """DoD-2: default search excludes working records; --project scope and
    read --id surface them."""

    def _seed(self):
        write_working(self.tmp, os.path.join("10 Projects", "Garden Plan"),
                      "PLAN-season.md", "working-plan-season",
                      summary="Planting order for the season.",
                      body="The xylophone-trellis goes in first.")

    def _search(self, **kw):
        a = Args()
        a.domain = "shared"
        for k, v in kw.items():
            setattr(a, k, v)
        rep = Report("search")
        search_mod.run(self.tmp, a, rep)
        return rep

    def test_default_search_excludes_working(self):
        self._seed()
        rep = self._search(query="xylophone-trellis")
        self.assertEqual(rep.info["matches_total"], 0, rep.info)

    def test_all_states_still_excludes_working(self):
        # working is a LAYER, not a lifecycle state — --all-states widens
        # states, never the knowledge boundary
        self._seed()
        rep = self._search(query="xylophone-trellis", all_states=True)
        self.assertEqual(rep.info["matches_total"], 0, rep.info)

    def test_project_scope_includes_working_even_draft(self):
        self._seed()
        rep = self._search(query="xylophone-trellis", project="Garden Plan")
        self.assertEqual(rep.info["matches_total"], 1, rep.info)
        self.assertIn("working-plan-season", rep.info["hits"][0])

    def test_project_scope_stays_inside_that_project(self):
        self._seed()
        os.makedirs(os.path.join(self.tmp, "10 Projects", "Other"), exist_ok=True)
        write_working(self.tmp, os.path.join("10 Projects", "Other"),
                      "LOG-other.md", "working-log-other", subtype="log",
                      body="xylophone-trellis mentioned elsewhere")
        rep = self._search(query="xylophone-trellis", project="Garden Plan")
        self.assertEqual(rep.info["matches_total"], 1, rep.info)

    def test_read_by_id_returns_working(self):
        self._seed()
        a = Args(); a.id = "working-plan-season"; a.domain = "shared"
        rep = Report("read")
        read_mod.run(self.tmp, a, rep)
        self.assertFalse(rep.errors, rep.errors)
        self.assertIn("xylophone-trellis", rep.info["body"])


class TestFrontmatterOnlyConvergence(WorkingBase):
    """DoD-4 shape: a legacy untyped plan converges with a frontmatter-only
    change — body byte-identical, validates green."""

    def test_retype_is_frontmatter_only(self):
        body = "# The plan\n\nLong-lived prose that must not change.\n"
        p = os.path.join(self.tmp, "10 Projects", "Garden Plan", "PLAN-legacy.md")
        write_file(p, body, mode="w", encoding="utf-8")          # untyped: warning
        rep = run_validate(self.tmp)
        self.assertTrue(any("PLAN-legacy" in w for w in rep.warnings))
        fm = ("---\nid: working-plan-legacy\ntype: working\nsubtype: plan\n"
              "status: draft\ncreated: 2026-07-25\nupdated: 2026-07-25\n"
              "summary: \"Legacy plan, converged.\"\n---\n")
        write_file(p, fm + body, mode="w", encoding="utf-8")     # typed: green
        rep2 = run_validate(self.tmp)
        self.assertFalse(rep2.errors, rep2.errors)
        self.assertFalse(any("PLAN-legacy" in w for w in rep2.warnings), rep2.warnings)
        self.assertTrue(read_file(p, encoding="utf-8").endswith(body))


if __name__ == "__main__":
    unittest.main()
