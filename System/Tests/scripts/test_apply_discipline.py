"""v1.17.0 regressions (DEC-065): import checkpoint-or-halt, zip-only snapshots,
the Local Only folder marking, and the derived-doc stamp warning."""
from test_io import read_file, write_file
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                     # noqa: E402
from cmd.search import permitted                  # noqa: E402


def _vault(root, git=True, identity=True):
    """Minimal writable vault: manifest + one content dir (+ git, optionally anonymous)."""
    os.makedirs(os.path.join(root, "20 Knowledge"), exist_ok=True)
    # explicit role: a fixture must not inherit the host vault's instance_role
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as stream:
        stream.write(product_manifest())
    with open(os.path.join(root, "20 Knowledge", "n.md"), "w") as stream:
        stream.write("hello\n")
    if git and shutil.which("git"):
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
        if identity:
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
        else:
            # simulate a fresh machine: repo exists, no identity anywhere
            subprocess.run(["git", "config", "user.email", ""], cwd=root, capture_output=True)
            subprocess.run(["git", "config", "user.name", ""], cwd=root, capture_output=True)
    return root


class TestImportCheckpointOrHalt(unittest.TestCase):
    """A failed pre-import checkpoint must refuse the import with NOTHING written."""

    def test_import_refuses_when_checkpoint_fails(self):
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        from cmd import import_vault as iv_mod
        with tempfile.TemporaryDirectory() as outer:
            root = _vault(os.path.join(outer, "v"), git=True, identity=False)
            src = os.path.join(outer, "src")
            os.makedirs(src)
            write_file(os.path.join(src, "old-note.md"), "legacy\n", mode="w")
            pdir = os.path.join(root, "System", "Migrations", "001-t")
            os.makedirs(pdir)
            write_file(os.path.join(pdir, "import-plan.yaml"), f"id: migration-001-t\nmode: verbatim\nsource: {src}\n", mode="w")

            class A:
                json = False; plan = "001-t"; apply = True
                allow_secret_flags = False; message = None
                rollback = None; confirm = False; clean = False
                force_zip = False; zip_only = False
            rep = Report("import")
            iv_mod.run(root, A(), rep)

            self.assertTrue(any("checkpoint FAILED" in e and "refused" in e
                                for e in rep.errors), rep.errors)
            self.assertFalse(os.path.exists(os.path.join(root, "old-note.md")),
                             "nothing may be written after a failed checkpoint")
            self.assertFalse(os.path.exists(os.path.join(pdir, "APPLIED.yaml")),
                             "a refused import must not be marked applied")


class TestZipOnly(unittest.TestCase):
    def test_zip_only_writes_snapshot_without_git_commit(self):
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        from cmd import checkpoint as ck_mod
        with tempfile.TemporaryDirectory() as outer:
            root = _vault(os.path.join(outer, "v"))
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True,
                           capture_output=True)
            write_file(os.path.join(root, "20 Knowledge", "n.md"), "unready work\n", mode="w")

            class A:
                json = False; message = "probe"; rollback = None; confirm = False
                clean = False; force_zip = False; zip_only = True
            rep = Report("checkpoint")
            ck_mod.run(root, A(), rep)

            count = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=root,
                                   capture_output=True, text=True).stdout.strip()
            self.assertEqual(count, "1", "--zip-only must not create a git commit")
            snapdir = os.path.join(outer, "v-Snapshots")
            self.assertTrue(os.path.isdir(snapdir) and os.listdir(snapdir),
                            "--zip-only must write the snapshot")
            dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                   capture_output=True, text=True).stdout.strip()
            self.assertTrue(dirty, "the unready work must remain uncommitted")


class TestLocalOnlyFolder(unittest.TestCase):
    """DEC-065: a `Local Only` path segment IS an ai_use: local-only marking."""
    HOSTED = {"hosted": True, "may_process_private": True}
    LOCAL = {"hosted": False, "may_process_private": True}

    def test_hosted_runtime_never_sees_local_only_folders(self):
        for path in ("30 Sources/Local Only/x.md",
                     "80 User/Digital Twin/local only/deep/y.md"):
            self.assertFalse(permitted({}, self.HOSTED, path), path)

    def test_local_runtime_may_read_them(self):
        self.assertTrue(permitted({}, self.LOCAL, "30 Sources/Local Only/x.md"))

    def test_stronger_frontmatter_still_wins_for_local_runtime(self):
        self.assertFalse(permitted({"ai_use": "prohibited"}, self.LOCAL,
                                   "30 Sources/Local Only/x.md"))

    def test_name_must_be_a_whole_segment(self):
        self.assertTrue(permitted({}, self.HOSTED, "20 Knowledge/Local Onlyish/x.md"))


class TestDerivedStampEnforced(unittest.TestCase):
    """DEC-069 scoped by U1 (upgrade-rehearsal finding 2): the hard error is for
    the product's own docs under System/; a USER note marked authority: derived
    gets a rolled-up advisory warning, never an error — a lived-in vault must not
    go red on the user's own content."""

    PROBE = ("---\nid: doc-derived-probe{n}\ntype: system-doc\nauthority: derived\n"
             "derived_from: [doc-source]\ncreated: 2026-07-16\nupdated: 2026-07-16\n"
             "summary: probe\n---\nbody\n")

    def _validate(self, write_to):
        from cmd import validate as v_mod
        with tempfile.TemporaryDirectory() as outer:
            root = _vault(os.path.join(outer, "v"), git=False)
            os.makedirs(os.path.join(root, "System", "Schemas"), exist_ok=True)
            os.makedirs(os.path.dirname(os.path.join(root, write_to)), exist_ok=True)
            write_file(os.path.join(root, write_to), self.PROBE.format(n=1), mode="w")

            class A:
                json = False
            rep = Report("validate")
            v_mod.run(root, A(), rep)
            return rep

    def test_unstamped_derived_SYSTEM_doc_is_an_error(self):   # DEC-069 core promise intact
        rep = self._validate("System/Documentation/d.md")
        self.assertTrue(any("x_reviewed_against" in e for e in rep.errors), rep.errors)

    def test_unstamped_derived_USER_note_is_a_warning_not_an_error(self):   # U1 regression case
        rep = self._validate("20 Knowledge/d.md")
        self.assertFalse(any("x_reviewed_against" in e for e in rep.errors), rep.errors)
        self.assertTrue(any("advisory" in w and "derived" in w for w in rep.warnings),
                        rep.warnings)


class TestPermittedFailClosed(unittest.TestCase):
    """DEC-066: a present-but-unrecognised privacy value must never widen access."""
    HOSTED = {"hosted": True, "may_process_private": True}
    LOCAL = {"hosted": False, "may_process_private": True}

    def test_typos_are_excluded_everywhere(self):
        for meta in ({"classification": "Restricted"}, {"ai_use": "local_only"},
                     {"ai_use": "localonly"}, {"ai_use": "whatever"},
                     {"classification": "x"}):
            self.assertFalse(permitted(meta, self.HOSTED), meta)
            self.assertFalse(permitted(meta, self.LOCAL), meta)

    def test_absence_still_means_allowed(self):
        # DEC-026 whole-record model unchanged: unmarked content is the user's choice
        self.assertTrue(permitted({}, self.HOSTED, "20 Knowledge/x.md"))

    def test_valid_values_unchanged(self):
        self.assertTrue(permitted({"classification": "private", "ai_use": "allowed"}, self.HOSTED))
        self.assertFalse(permitted({"classification": "restricted"}, self.LOCAL))


class TestDocTruthFires(unittest.TestCase):
    """The old latest-heading probe is superseded by the full release audit."""

    def test_manifest_and_changelog_alone_no_longer_pass_for_a_release(self):
        from cmd import certify
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
                f.write("system:\n  instance_role: generic-master\n"
                        "  system_version: 1.0.0\n")
            with open(os.path.join(tmp, "CHANGELOG.md"), "w") as f:
                f.write("# Log\n\n## [1.0.0] — latest\n")
            rep = certify._doc_truth(tmp)
            self.assertFalse(rep.ok)
            self.assertTrue(any("package-" in error or "baseline-" in error
                                for error in rep.errors))

    def test_clean_product_master_passes_the_strict_gate(self):
        from cmd import certify
        rep = certify._doc_truth(VAULT)
        self.assertTrue(rep.ok, rep.errors)


class TestSearchDisclosure(unittest.TestCase):
    def test_truncation_is_disclosed(self):
        from cmd import search as s_mod
        class A:
            query = "the"; domain = "shared"; all_states = False; json = False
        rep = Report("search")
        s_mod.run(VAULT, A(), rep)
        self.assertIn("matches_total", rep.info)
        if rep.info["matches_total"] > 25:
            self.assertIn("hits_shown", rep.info)


class TestImportRetryAfterFailedValidate(unittest.TestCase):
    """F23: a failed import removes its one-time marker so restore-then-re-run works."""

    def test_marker_removed_on_validation_failure(self):
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        from cmd import import_vault as iv_mod
        with tempfile.TemporaryDirectory() as outer:
            root = _vault(os.path.join(outer, "v"), git=True, identity=True)
            # an existing note whose id the import will duplicate → post-import validate fails
            write_file(os.path.join(root, "20 Knowledge", "existing.md"), "---\nid: note-dup\ntype: note\ncreated: 2026-07-16\nupdated: 2026-07-16\nsummary: s\n---\nx\n", mode="w")
            src = os.path.join(outer, "src"); os.makedirs(src)
            write_file(os.path.join(src, "incoming.md"), "---\nid: note-dup\ntype: note\ncreated: 2026-07-16\nupdated: 2026-07-16\nsummary: s\n---\ny\n", mode="w")
            pdir = os.path.join(root, "System", "Migrations", "001-t"); os.makedirs(pdir)
            write_file(os.path.join(pdir, "import-plan.yaml"), f"id: migration-001-t\nmode: verbatim\nsource: {src}\n", mode="w")

            class A:
                json = False; plan = "001-t"; apply = True
                allow_secret_flags = False; message = None
                rollback = None; confirm = False; clean = False
                force_zip = False; zip_only = False
            rep = Report("import")
            iv_mod.run(root, A(), rep)
            self.assertTrue(any("re-run" in e for e in rep.errors), rep.errors)
            self.assertFalse(os.path.exists(os.path.join(pdir, "APPLIED.yaml")),
                             "the marker must not survive a failed validation")


if __name__ == "__main__":
    unittest.main()
