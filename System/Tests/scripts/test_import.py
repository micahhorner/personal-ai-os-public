"""Import-command regression tests (doc 12 / v1.1.x): plan validation,
dry-run purity, mapped transforms + quarantine, verbatim byte-parity +
registry, one-time marker, secret gate, sanitization, kill switch."""
from test_io import read_file, write_file
import os, sys, shutil, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_commands import mini_vault, aios  # noqa: E402

LEGACY_NOTE = """---
created: 2025-03-01
status: complete
topic: habitats
tags: [design]
---
**The environment is continuous while intention fluctuates.** More body text.

Details follow here.
"""

PLAN_MAPPED = """
source: {src}
mode: mapped
rules:
  - match: "Permanent Notes/**"
    dest: "20 Knowledge/"
    transform: note
  - match: "Projects/*/**"
    dest: "10 Projects/"
    transform: copy
    mint_folder_note: project
  - match: "**"
    dest: "00 Inbox/legacy-import/"
    transform: copy
"""

PLAN_VERBATIM = """
source: {src}
mode: verbatim
renames:
  CLAUDE.md: OPERATIONS.md
register_folders:
  - {{path: "Permanent Notes", purpose: foreign-import, conventions: foreign}}
"""


def make_source(base, secret=False):
    src = os.path.join(base, "their-vault")
    os.makedirs(os.path.join(src, "Permanent Notes"))
    os.makedirs(os.path.join(src, "Projects", "Site"))
    os.makedirs(os.path.join(src, "Journal"))
    os.makedirs(os.path.join(src, ".obsidian"))
    for path, payload in (
        (os.path.join(src, "Permanent Notes", "Alpha Idea.md"), LEGACY_NOTE),
        (os.path.join(src, "Projects", "Site", "plan.md"), "Launch plan.\n"),
        (os.path.join(src, "Journal", "2026-01-01.md"), "Daily note. [[Missing Target]]\n"),
        (os.path.join(src, "CLAUDE.md"), "their old operator file\n"),
        (os.path.join(src, ".obsidian", "app.json"), "{}"),
    ):
        with open(path, "w") as stream:
            stream.write(payload)
    if secret:
        with open(os.path.join(src, "Journal", "oops.md"), "w") as stream:
            stream.write("api_key: 'FAKEFAKEFAKEFAKEFAKE1234'\n")
    return src


def write_plan(tmp, body):
    pdir = os.path.join(tmp, "System", "Migrations", "001-test-import")
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "import-plan.yaml"), "w") as stream:
        stream.write(body)
    return pdir


RULE_BLOCK = 'rules:\n  - match: "Chats/**"\n    dest: "30 Sources/Chats/"\n    transform: source\n    prefix_parent: true'


def tree(root):
    out = {}
    for dirpath, _, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            out[os.path.relpath(p, root)] = os.path.getsize(p)
    return out


class TestImportCommand(unittest.TestCase):
    def test_dry_run_writes_nothing_anywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            write_plan(v, PLAN_MAPPED.format(src=src))
            before_v, before_s = tree(v), tree(src)
            r = aios(v, "import", "--plan", "001-test-import")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("dry-run", r.stdout)
            self.assertEqual(tree(v), before_v, "dry-run wrote into the vault")
            self.assertEqual(tree(src), before_s, "dry-run touched the source")

    def test_mapped_apply_transforms_quarantines_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            os.makedirs(os.path.join(v, "10 Projects"), exist_ok=True)
            write_plan(v, PLAN_MAPPED.format(src=src))
            before_s = tree(src)
            r = aios(v, "import", "--plan", "001-test-import", "--apply")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            note = read_file(os.path.join(v, "20 Knowledge", "Alpha Idea.md"))
            self.assertIn("id: note-alpha-idea", note)
            self.assertIn("x_topic: habitats", note)
            self.assertIn("status: active", note)          # complete -> active
            self.assertIn("The environment is continuous", note)  # summary lifted
            self.assertTrue(os.path.exists(os.path.join(
                v, "00 Inbox", "legacy-import", "Journal", "2026-01-01.md")),
                "unmapped material must be quarantined, never dropped")
            self.assertTrue(os.path.exists(os.path.join(v, "10 Projects", "Site", "Site.md")),
                            "project folder-note not minted")
            self.assertEqual(tree(src), before_s, "apply touched the source")
            self.assertEqual(aios(v, "validate").returncode, 0)

    def test_verbatim_apply_is_byte_identical_and_registers_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            shutil.copy(os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                        os.path.join(v, "System", "Registries"))
            write_plan(v, PLAN_VERBATIM.format(src=src))
            r = aios(v, "import", "--plan", "001-test-import", "--apply")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for rel in ("Permanent Notes/Alpha Idea.md", "Projects/Site/plan.md",
                        "Journal/2026-01-01.md"):
                with open(os.path.join(src, rel)) as a, open(os.path.join(v, rel)) as b:
                    self.assertEqual(a.read(), b.read(), f"verbatim parity broken: {rel}")
            self.assertTrue(os.path.exists(os.path.join(v, "OPERATIONS.md")),
                            "root adapter-slot rename not applied")
            self.assertFalse(os.path.exists(os.path.join(v, "CLAUDE.md")))
            reg = read_file(os.path.join(v, "System", "Registries", "folder-registry.yaml"))
            self.assertIn("permanent-notes", reg)
            self.assertIn("conventions: foreign", reg)

    def test_verbatim_mirrors_empty_scaffolding_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            os.makedirs(os.path.join(src, "Battle Cards", "Drafts"))  # empty, referenced by automations
            shutil.copy(os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                        os.path.join(v, "System", "Registries"))
            write_plan(v, PLAN_VERBATIM.format(src=src))
            self.assertEqual(aios(v, "import", "--plan", "001-test-import", "--apply").returncode, 0)
            self.assertTrue(os.path.isdir(os.path.join(v, "Battle Cards", "Drafts")),
                            "empty scaffolding dirs must survive a verbatim import")

    def test_readonly_source_yields_writable_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            frozen = os.path.join(src, "Projects", "Site", "plan.md")
            os.chmod(frozen, 0o444)  # source frozen read-only (parallel-run posture)
            write_plan(v, PLAN_VERBATIM.format(src=src))
            shutil.copy(os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                        os.path.join(v, "System", "Registries"))
            self.assertEqual(aios(v, "import", "--plan", "001-test-import", "--apply").returncode, 0)
            self.assertTrue(os.access(os.path.join(v, "Projects", "Site", "plan.md"), os.W_OK),
                            "imported copy must be writable — it is the live vault now")
            os.chmod(frozen, 0o644)  # let the tempdir clean up

    def test_prefix_parent_disambiguates_colliding_basenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, 'v')); src = make_source(tmp)
            os.makedirs(os.path.join(src, 'Chats', 'A')); os.makedirs(os.path.join(src, 'Chats', 'B'))
            for sub in ('A', 'B'):
                write_file(os.path.join(src, 'Chats', sub, 'Untitled.md'), 'chat in ' + sub, mode='w')
            plan = PLAN_MAPPED.format(src=src).replace('rules:', RULE_BLOCK)
            write_plan(v, plan)
            r = aios(v, 'import', '--plan', '001-test-import', '--apply')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(os.path.exists(os.path.join(v, '30 Sources', 'Chats', 'A', 'A \u2014 Untitled.md')))
            self.assertTrue(os.path.exists(os.path.join(v, '30 Sources', 'Chats', 'B', 'B \u2014 Untitled.md')))
            self.assertEqual(aios(v, 'dupes').returncode, 0, 'typed basename collision leaked through')

    def test_import_is_one_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            write_plan(v, PLAN_MAPPED.format(src=src))
            self.assertEqual(aios(v, "import", "--plan", "001-test-import", "--apply").returncode, 0)
            r = aios(v, "import", "--plan", "001-test-import", "--apply")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("one-time", r.stdout)

    def test_secret_flags_block_apply_without_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp, secret=True)
            write_plan(v, PLAN_MAPPED.format(src=src))
            dry = aios(v, "import", "--plan", "001-test-import")
            self.assertIn("secret", dry.stdout.lower())
            r = aios(v, "import", "--plan", "001-test-import", "--apply")
            self.assertNotEqual(r.returncode, 0, "apply must refuse on unreviewed secret flags")

    def test_mapped_plan_requires_terminal_quarantine_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            plan = PLAN_MAPPED.format(src=src).replace(
                '  - match: "**"\n    dest: "00 Inbox/legacy-import/"\n    transform: copy\n', "")
            write_plan(v, plan)
            r = aios(v, "import", "--plan", "001-test-import")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("last rule", r.stdout)

    def test_forbidden_filenames_are_sanitized_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            write_file(os.path.join(src, "Journal", 'w?ird note.md'), "x\n", mode="w")
            write_plan(v, PLAN_MAPPED.format(src=src))
            r = aios(v, "import", "--plan", "001-test-import")
            self.assertIn("sanitized", r.stdout)
            self.assertEqual(aios(v, "import", "--plan", "001-test-import", "--apply").returncode, 0)
            self.assertTrue(os.path.exists(os.path.join(
                v, "00 Inbox", "legacy-import", "Journal", "wird note.md")))

    def test_patches_are_anchor_asserted(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            plan = PLAN_MAPPED.format(src=src) + (
                'patches:\n'
                '  - {file: "Projects/Site/plan.md", find: "Launch plan.", replace: "Launch plan (patched at import)."}\n')
            write_plan(v, plan)
            r = aios(v, "import", "--plan", "001-test-import", "--apply")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("patched at import",
                          read_file(os.path.join(v, "10 Projects", "Site", "plan.md")))
            src_text = read_file(os.path.join(src, "Projects", "Site", "plan.md"))
            self.assertNotIn("patched", src_text, "patch leaked into the source")

    def test_failed_patch_anchor_blocks_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            plan = PLAN_MAPPED.format(src=src) + (
                'patches:\n'
                '  - {file: "Projects/Site/plan.md", find: "NO SUCH ANCHOR", replace: "x"}\n')
            write_plan(v, plan)
            r = aios(v, "import", "--plan", "001-test-import", "--apply")
            self.assertNotEqual(r.returncode, 0, "apply must refuse on a missed patch anchor")
            self.assertFalse(os.path.exists(os.path.join(v, "10 Projects", "Site", "plan.md")))

    def test_kill_switch_blocks_import_entirely(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v"), switch="false"); src = make_source(tmp)
            write_plan(v, PLAN_MAPPED.format(src=src))
            r = aios(v, "import", "--plan", "001-test-import")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("kill switch", r.stdout)

    def test_stubs_carry_review_due_and_queue_artifact_matches(self):
        """SPEC-import-review-queue DoD-1: every minted stub carries review_due,
        `aios review-due` surfaces them (when due), and the generated queue
        artifact exists and matches the stubs one-to-one."""
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            os.makedirs(os.path.join(v, "10 Projects"), exist_ok=True)
            write_plan(v, PLAN_MAPPED.format(src=src))
            r = aios(v, "import", "--plan", "001-test-import", "--apply", "--review-days", "0")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            import datetime
            today = datetime.date.today().isoformat()
            stub = read_file(os.path.join(v, "10 Projects", "Site", "Site.md"))
            self.assertIn(f"review_due: {today}", stub.replace("'", ""))
            self.assertIn("Stage not set — owner to review", stub)
            q = os.path.join(v, "System", "Migrations", "001-test-import", "review-queue.md")
            self.assertTrue(os.path.exists(q), "review-queue artifact missing")
            qtext = read_file(q)
            self.assertIn("10 Projects/Site/Site.md", qtext)
            self.assertIn("file_class: generated", qtext)
            # one-to-one: exactly as many table rows as minted stubs (1 here)
            self.assertEqual(qtext.count("| 10 Projects/"), 1)
            rd = aios(v, "review-due")
            self.assertEqual(rd.returncode, 0, rd.stdout + rd.stderr)
            self.assertIn("project-site", rd.stdout, "due stub absent from `aios review-due`")

    def test_review_days_default_is_14_and_plan_key_tunable(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            os.makedirs(os.path.join(v, "10 Projects"), exist_ok=True)
            write_plan(v, PLAN_MAPPED.format(src=src) + "review_after_days: 3\n")
            self.assertEqual(aios(v, "import", "--plan", "001-test-import",
                                  "--apply").returncode, 0)
            import datetime
            due = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
            stub = read_file(os.path.join(v, "10 Projects", "Site", "Site.md"))
            self.assertIn(f"review_due: {due}", stub.replace("'", ""))

    def test_contains_line_counts_files_and_names_empty_scaffolding(self):
        """SPEC-import-review-queue DoD-2: real files get a correct count; empty
        scaffolding is called empty — never advertised as material."""
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            os.makedirs(os.path.join(src, "Projects", "Hollow", "Notes"))
            os.makedirs(os.path.join(src, "Projects", "Hollow", "Writing"))
            os.makedirs(os.path.join(v, "10 Projects"), exist_ok=True)
            write_plan(v, PLAN_MAPPED.format(src=src))
            self.assertEqual(aios(v, "import", "--plan", "001-test-import",
                                  "--apply").returncode, 0)
            site = read_file(os.path.join(v, "10 Projects", "Site", "Site.md"))
            self.assertIn("Contains: 1 file", site)
            hollow = read_file(os.path.join(v, "10 Projects", "Hollow", "Hollow.md"))
            self.assertIn("empty scaffolding only", hollow)
            self.assertIn("Notes", hollow); self.assertIn("Writing", hollow)
            self.assertIn("0 files", hollow)

    def test_summary_extraction_never_cuts_mid_word(self):
        """Seeded regression (SPEC-import-review-queue DoD-2): the v1.2.x
        mid-word summary-truncation fix must stay fixed — the cap lands on a
        sentence boundary, never inside a word."""
        from cmd.import_vault import extract_summary
        two = extract_summary("**First sentence stays whole. " + "Beta " * 60 + "end.**")
        self.assertEqual(two, "First sentence stays whole.",
                         "cap must land on the sentence boundary, not mid-word")
        s = extract_summary("**Sentence one is short. Sentence two is also short. "
                            + "Gamma " * 50 + "tail.**")
        self.assertLessEqual(len(s), 240)
        self.assertTrue(s.endswith("short."), f"unexpected cut: {s!r}")

    def test_source_link_baseline_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = mini_vault(os.path.join(tmp, "v")); src = make_source(tmp)
            write_plan(v, PLAN_MAPPED.format(src=src))
            r = aios(v, "import", "--plan", "001-test-import")
            self.assertIn("source_unresolved_links_baseline: 1", r.stdout,
                          "pre-existing broken links must be baselined (971-link lesson)")


if __name__ == "__main__":
    unittest.main()
