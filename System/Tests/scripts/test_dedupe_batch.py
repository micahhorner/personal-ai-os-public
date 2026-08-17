"""Regression tests for `aios dedupe-batch` — intake-batch overlap (DEC-098).

The batch is built by the SAME generator fixture 27 uses
(`System/Tests/fixtures/27-intake-dedupe/input/make-fixture-batch.py`), so the
behavioral fixture and the regression suite can never diverge onto different
corpora.

`TestProvenCaseReproduces` is the spec's regression bar: the 2026-07-15 case
where one of four handed-over documents was 97% a paste-up — 95% of one sibling,
49% of another — while the fourth was independent. Those percentages are the
test, and the fixture is sized so they fall out of the arithmetic rather than out
of a threshold tuned until they appeared.
"""
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                          # noqa: E402
from lib import safepaths as sp                        # noqa: E402
from cmd import dedupebatch as db                      # noqa: E402

GEN = os.path.join(VAULT, "System", "Tests", "fixtures", "27-intake-dedupe",
                   "input", "make-fixture-batch.py")


def _load_generator():
    spec = importlib.util.spec_from_file_location("fixture_batch_generator", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GENERATOR = _load_generator()


class Args:
    json = False
    target = None
    annotate = False


def batch_vault(tmp):
    d = os.path.join(tmp, "00 Inbox", "batch")
    GENERATOR.build(d)
    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w", encoding="utf-8") as fh:
        fh.write(product_manifest())
    return d


def run(tmp, target, annotate=False):
    a = Args()
    a.target = target
    a.annotate = annotate
    rep = Report("dedupe-batch")
    db.run(tmp, a, rep)
    return rep


def pct_of(rep, needle):
    """Pull the reported percentages for the matrix row naming `needle`."""
    for row in rep.info.get("overlap_matrix", []):
        if needle in row:
            return row
    return ""


def _read_text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def tree_hash(root):
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            h.update(os.path.relpath(p, root).encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


class TestProvenCaseReproduces(unittest.TestCase):
    """DoD-2 — the spec's numbers are the regression test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.batch = batch_vault(self.tmp)
        self.rep = run(self.tmp, "00 Inbox/batch")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_paste_up_is_97_percent_repeated(self):
        rows = [r for r in self.rep.info["unique_contribution"] if "paste-up" in r]
        self.assertEqual(len(rows), 1)
        self.assertIn("(3% unique)", rows[0])     # 100 - 3 = the recorded 97%

    def test_paste_up_absorbed_95_percent_of_the_first_source(self):
        row = pct_of(self.rep, "capture-a.md")
        self.assertIn("95 shared", row)
        self.assertIn("95% of the first", row)

    def test_paste_up_absorbed_49_percent_of_the_second_source(self):
        row = pct_of(self.rep, "capture-b.md")
        self.assertIn("49 shared", row)
        self.assertIn("49% of the first", row)

    def test_the_independent_file_reads_as_independent(self):
        rows = [r for r in self.rep.info["unique_contribution"] if "independent" in r]
        self.assertIn("(100% unique)", rows[0])
        self.assertNotIn("capture-independent", str(self.rep.info["overlap_matrix"]))

    def test_both_percentages_are_reported_per_pair(self):
        """One number cannot express the asymmetry that matters: 95 shared
        paragraphs is 95% of a 100-paragraph file and 64% of a 149-paragraph one,
        and it is the 95% that says the small file was absorbed whole."""
        row = pct_of(self.rep, "capture-a.md")
        self.assertIn("% of the first", row)
        self.assertIn("% of the second", row)

    def test_the_superset_is_the_copy(self):
        """The trap the real case set: the paste-up was the BIGGEST file, so
        'keep the biggest' would have kept the copy and dropped the originals."""
        sizes = {os.path.basename(p): db.collect([os.path.join(self.batch, p)])
                 for p in os.listdir(self.batch)}
        biggest = max(sizes, key=lambda k: list(sizes[k].values())[0]["count"])
        self.assertEqual(biggest, "capture-paste-up.md")


class TestReportNeverAction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.batch = batch_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_run_is_read_only(self):
        before = tree_hash(self.batch)
        rep = run(self.tmp, "00 Inbox/batch")
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(before, tree_hash(self.batch), "dedupe-batch modified the batch")

    def test_nothing_is_discarded_or_classified(self):
        rep = run(self.tmp, "00 Inbox/batch")
        self.assertEqual(len(os.listdir(self.batch)), 4)
        text = " ".join(rep.warnings) + str(rep.info)
        # It reports overlap; it never returns a verdict. (The report is allowed
        # to SAY "nothing has been discarded" — what it may not do is classify.)
        for verdict in ("is a duplicate", "duplicate file", "was discarded",
                        "were discarded", "was removed", "was deleted"):
            self.assertNotIn(verdict, text)
        self.assertIn("MEASUREMENT, not a verdict", " ".join(rep.warnings))
        self.assertIn("nothing has been discarded", " ".join(rep.warnings))

    def test_warning_fires_on_the_near_duplicate_only(self):
        rep = run(self.tmp, "00 Inbox/batch")
        warned = " ".join(rep.warnings)
        self.assertIn("capture-paste-up.md", warned)
        self.assertNotIn("capture-independent.md", warned)


class TestThresholdAndNormalization(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.batch = batch_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_short_paragraphs_are_excluded_and_counted_separately(self):
        """Boilerplate (headers, signatures, one-word answers) repeats across
        unrelated documents; letting it into the matrix makes boilerplate read as
        corroboration — the exact failure the command exists to prevent."""
        rep = run(self.tmp, "00 Inbox/batch")
        line = [v for k, v in rep.info.items() if "capture-independent.md" in str(k)][0]
        self.assertIn("60 comparable paragraphs", line)
        self.assertIn("+5 short, excluded", line)

    def test_short_boilerplate_does_not_create_overlap(self):
        # every file carries the same 5 short lines; the independent file must
        # still report zero overlap
        rep = run(self.tmp, "00 Inbox/batch")
        self.assertNotIn("capture-independent", str(rep.info["overlap_matrix"]))

    def test_frontmatter_is_not_compared(self):
        """Two captures sharing `type: source` is not evidence of anything."""
        body = "This is a paragraph long enough to clear the comparison threshold easily."
        a = "---\nid: x\ntype: source\n---\n\n" + body
        b = "---\nid: y\ntype: source\nstatus: draft\n---\n\n" + body
        pa, _ = db.paragraphs(a)
        pb, _ = db.paragraphs(b)
        self.assertEqual(pa, pb)
        self.assertEqual(len(pa), 1)

    def test_typographic_variants_are_the_same_paragraph(self):
        """The same sentence pasted through Word and through a chat export
        differs only in quote and dash glyphs. Treating those as distinct is how
        a 97% copy reads as original."""
        a = "The author's point - stated plainly - survives every export path here."
        b = "The author’s point — stated plainly — survives every export path here."
        self.assertEqual(db.normalize(a).replace("—", "-"), db.normalize(b).replace("—", "-"))
        self.assertEqual(db.digest(db.normalize(a)), db.digest(db.normalize(b)))


class TestAnnotate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.batch = batch_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _bodies(self):
        out = {}
        for fn in sorted(os.listdir(self.batch)):
            text = _read_text(os.path.join(self.batch, fn))
            end = text.find("\n---", 3)
            out[fn] = text[end + 4:]
        return out

    def test_annotate_writes_the_map_and_leaves_bodies_byte_identical(self):
        before = self._bodies()
        rep = run(self.tmp, "00 Inbox/batch", annotate=True)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(before, self._bodies(), "annotate touched a source body")
        text = _read_text(os.path.join(self.batch, "capture-paste-up.md"))
        self.assertIn("x_overlap_checked: aios dedupe-batch", text)
        self.assertIn("x_overlap_paragraphs: 149", text)
        self.assertIn("x_overlap_unique: 5", text)
        self.assertIn("capture-a.md: 95 shared paragraphs", text)

    def test_annotate_is_idempotent(self):
        run(self.tmp, "00 Inbox/batch", annotate=True)
        first = _read_text(os.path.join(self.batch, "capture-a.md"))
        run(self.tmp, "00 Inbox/batch", annotate=True)
        second = _read_text(os.path.join(self.batch, "capture-a.md"))
        self.assertEqual(first, second)
        self.assertEqual(second.count("x_overlap_checked"), 1)

    def test_independent_file_gets_a_map_with_no_peers(self):
        run(self.tmp, "00 Inbox/batch", annotate=True)
        text = _read_text(os.path.join(self.batch, "capture-independent.md"))
        self.assertIn("x_overlap_unique: 60", text)
        self.assertNotIn("x_overlap_with:", text)

    def test_annotate_refuses_while_the_kill_switch_is_off(self):
        mp = os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml")
        s = _read_text(mp).replace("ai_writes_enabled: true",
                                   "ai_writes_enabled: false")
        with open(mp, "w", encoding="utf-8") as fh:
            fh.write(s)
        before = tree_hash(self.batch)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "aios.py"), "dedupe-batch",
                            "00 Inbox/batch", "--annotate", "--root", self.tmp],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("kill switch", r.stdout + r.stderr)
        self.assertEqual(before, tree_hash(self.batch))

    def test_read_only_form_still_runs_while_the_switch_is_off(self):
        """The report is not a write. A user who has stopped AI writing can
        still be told what overlaps."""
        mp = os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml")
        s = _read_text(mp).replace("ai_writes_enabled: true",
                                   "ai_writes_enabled: false")
        with open(mp, "w", encoding="utf-8") as fh:
            fh.write(s)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "aios.py"), "dedupe-batch",
                            "00 Inbox/batch", "--root", self.tmp],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("kill switch", r.stdout)

    def test_external_files_remain_readable_but_cannot_be_annotated(self):
        external = tempfile.mkdtemp()
        try:
            a = os.path.join(external, "a.md")
            b = os.path.join(external, "b.md")
            body = "This paragraph is long enough to be compared and is shared by both files.\n"
            for path in (a, b):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(body)
            before = {}
            for path in (a, b):
                with open(path, "rb") as fh:
                    before[path] = fh.read()
            report = run(self.tmp, f"{a},{b}")
            self.assertTrue(report.ok, report.errors)
            refused = run(self.tmp, f"{a},{b}", annotate=True)
            self.assertFalse(refused.ok)
            self.assertIn("outside the vault", " ".join(refused.errors))
            after = {}
            for path in (a, b):
                with open(path, "rb") as fh:
                    after[path] = fh.read()
            self.assertEqual(before, after)
        finally:
            shutil.rmtree(external, ignore_errors=True)

    def test_one_symlink_refuses_the_whole_batch_before_any_write(self):
        external = tempfile.mkdtemp()
        try:
            outside = os.path.join(external, "outside.md")
            with open(outside, "w", encoding="utf-8") as fh:
                fh.write("External content that must remain byte identical after refusal.\n")
            linked = os.path.join(self.batch, "linked.md")
            os.symlink(outside, linked)
            before_batch = tree_hash(self.batch)
            with open(outside, "rb") as fh:
                before_outside = fh.read()
            rep = run(self.tmp, "00 Inbox/batch", annotate=True)
            self.assertFalse(rep.ok)
            self.assertIn("symlink", " ".join(rep.errors))
            self.assertEqual(before_batch, tree_hash(self.batch))
            with open(outside, "rb") as fh:
                self.assertEqual(before_outside, fh.read())
        finally:
            shutil.rmtree(external, ignore_errors=True)

    def test_hardlink_alias_refuses_before_any_write(self):
        original = os.path.join(self.batch, "capture-a.md")
        alias = os.path.join(self.batch, "capture-a-hardlink.md")
        os.link(original, alias)
        before = tree_hash(self.batch)
        rep = run(self.tmp, "00 Inbox/batch", annotate=True)
        self.assertFalse(rep.ok)
        self.assertIn("same file", " ".join(rep.errors))
        self.assertEqual(before, tree_hash(self.batch))

    def test_case_alias_refuses_before_any_write(self):
        alias = os.path.join(self.batch, "CAPTURE-A.MD")
        if not os.path.lexists(alias):
            with open(alias, "w", encoding="utf-8") as fh:
                fh.write("A distinct case-spelling must still be refused portably.\n")
        target = ("00 Inbox/batch/capture-a.md,"
                  "00 Inbox/batch/CAPTURE-A.MD")
        before = tree_hash(self.batch)
        rep = run(self.tmp, target, annotate=True)
        self.assertFalse(rep.ok)
        self.assertIn("case/Unicode", " ".join(rep.errors))
        self.assertEqual(before, tree_hash(self.batch))

    def test_nfc_alias_refuses_before_any_write(self):
        composed = os.path.join(self.batch, "caf\N{LATIN SMALL LETTER E WITH ACUTE}.md")
        decomposed = os.path.join(self.batch, "cafe\N{COMBINING ACUTE ACCENT}.md")
        for path in (composed, decomposed):
            if not os.path.lexists(path):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("Unicode spelling aliases cannot both enter a write set.\n")
        before = tree_hash(self.batch)
        rep = run(self.tmp, f"{composed},{decomposed}", annotate=True)
        self.assertFalse(rep.ok)
        self.assertIn("case/Unicode", " ".join(rep.errors))
        self.assertEqual(before, tree_hash(self.batch))

    def test_non_regular_target_refuses_before_any_write(self):
        directory = os.path.join(self.batch, "not-a-file.md")
        os.makedirs(directory)
        before = tree_hash(self.batch)
        target = ("00 Inbox/batch/capture-a.md,"
                  "00 Inbox/batch/not-a-file.md")
        rep = run(self.tmp, target, annotate=True)
        self.assertFalse(rep.ok)
        self.assertIn("not a regular file", " ".join(rep.errors))
        self.assertEqual(before, tree_hash(self.batch))

    def test_read_only_target_refuses_the_whole_batch(self):
        target = os.path.join(self.batch, "capture-b.md")
        os.chmod(target, 0o444)
        before = tree_hash(self.batch)
        rep = run(self.tmp, "00 Inbox/batch", annotate=True)
        self.assertFalse(rep.ok)
        self.assertIn("not writable", " ".join(rep.errors))
        self.assertEqual(before, tree_hash(self.batch))

    def test_unsupported_platform_fails_closed(self):
        before = tree_hash(self.batch)
        with mock.patch.object(sp, "_platform_supported", return_value=False):
            rep = run(self.tmp, "00 Inbox/batch", annotate=True)
        self.assertFalse(rep.ok)
        self.assertIn("unsupported", " ".join(rep.errors))
        self.assertEqual(before, tree_hash(self.batch))

    def test_second_member_commit_failure_rolls_back_the_whole_batch(self):
        before = tree_hash(self.batch)

        def fail_after_second(event, index, _target):
            if event == "after-commit" and index == 1:
                raise OSError("injected second-member commit failure")

        with mock.patch.object(sp, "_mutation_boundary", side_effect=fail_after_second):
            rep = run(self.tmp, "00 Inbox/batch", annotate=True)
        self.assertFalse(rep.ok)
        self.assertIn("all targets rolled back", " ".join(rep.errors))
        self.assertEqual(before, tree_hash(self.batch))
        leftovers = [n for n in os.listdir(self.batch) if ".aios-" in n]
        self.assertEqual(leftovers, [])

    def test_rollback_failure_is_reported_as_incomplete(self):
        def fail_commit_and_one_rollback(event, index, _target):
            if event == "after-commit" and index == 1:
                raise OSError("injected second-member commit failure")
            if event == "before-rollback" and index == 0:
                raise OSError("injected rollback failure")

        with mock.patch.object(sp, "_mutation_boundary",
                               side_effect=fail_commit_and_one_rollback):
            rep = run(self.tmp, "00 Inbox/batch", annotate=True)
        self.assertFalse(rep.ok)
        self.assertIn("ROLLBACK IS INCOMPLETE", " ".join(rep.errors))
        self.assertIn("recovery backup retained", " ".join(rep.errors))
        leftovers = [n for n in os.listdir(self.batch) if n.endswith(".backup")]
        self.assertEqual(len(leftovers), 1)

    def test_ancestor_swap_is_refused_without_touching_external_tree(self):
        external = tempfile.mkdtemp()
        moved = self.batch + "-held"
        marker = os.path.join(external, "marker.txt")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("external bytes must not change\n")
        with open(marker, "rb") as fh:
            before_external = fh.read()

        swapped = {"done": False}

        def swap_before_reproof(event, _index, _target):
            if event == "before-final-reproof" and not swapped["done"]:
                os.rename(self.batch, moved)
                os.symlink(external, self.batch)
                swapped["done"] = True

        try:
            with mock.patch.object(sp, "_mutation_boundary", side_effect=swap_before_reproof):
                rep = run(self.tmp, "00 Inbox/batch", annotate=True)
            self.assertFalse(rep.ok)
            self.assertIn("parent", " ".join(rep.errors))
            with open(marker, "rb") as fh:
                self.assertEqual(before_external, fh.read())
            for name in os.listdir(moved):
                self.assertNotIn(".aios-", name)
        finally:
            shutil.rmtree(external, ignore_errors=True)


class TestTargets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.batch = batch_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_comma_separated_file_list(self):
        rep = run(self.tmp, "00 Inbox/batch/capture-a.md,00 Inbox/batch/capture-paste-up.md")
        self.assertEqual(rep.info["files"], 2)
        self.assertIn("95 shared", pct_of(rep, "capture-a.md"))

    def test_single_file_is_not_a_batch(self):
        rep = run(self.tmp, "00 Inbox/batch/capture-a.md")
        self.assertTrue(rep.ok)
        self.assertIn("at least two files", " ".join(rep.warnings))

    def test_missing_file_is_an_error(self):
        rep = run(self.tmp, "00 Inbox/batch/capture-a.md,00 Inbox/batch/nope.md")
        self.assertFalse(rep.ok)
        self.assertIn("not found", " ".join(rep.errors))

    def test_missing_target_reports_usage_and_names_dupes(self):
        """`dupes` is the canon checker and this is the batch checker; the usage
        line says so, because two commands with similar names and different jobs
        is exactly how the wrong one gets run."""
        rep = run(self.tmp, None)
        joined = " ".join(rep.errors)
        self.assertIn("usage: aios dedupe-batch", joined)
        self.assertIn("aios dupes", joined)


if __name__ == "__main__":
    unittest.main()
