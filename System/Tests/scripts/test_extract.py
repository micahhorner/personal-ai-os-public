"""Regression tests for `aios extract` — the .docx format adapter (DEC-098).

The fixture document is built by the SAME generator the behavioral fixture uses
(`System/Tests/fixtures/26-doc-extraction/input/make-fixture-docx.py`), imported
here by path, so the unit suite and fixture 26 can never drift onto different
documents.

The centre of gravity is `TestVerificationGate`: SPEC-doc-extraction's position
is that a converter which loses a paragraph silently is worse than no converter,
so the interesting assertion is not "the Markdown is right" but "a WRONG Markdown
is refused, the original is filed, and the failure is reported".
"""
from test_io import read_file, write_file
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                       # noqa: E402
from lib import safepaths as sp                     # noqa: E402
from cmd import extract as ex                       # noqa: E402

GEN = os.path.join(VAULT, "System", "Tests", "fixtures", "26-doc-extraction",
                   "input", "make-fixture-docx.py")


def _load_generator():
    spec = importlib.util.spec_from_file_location("fixture_docx_generator", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GENERATOR = _load_generator()


class Args:
    json = False
    target = None
    dry_run = False


def mini_vault(tmp):
    """The smallest tree extract needs: a manifest with the switch on and the
    folder registry that names where attachments live."""
    os.makedirs(os.path.join(tmp, "00 Inbox"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "System", "Registries"), exist_ok=True)
    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w", encoding="utf-8") as stream:
        stream.write(product_manifest())
    shutil.copy(os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                os.path.join(tmp, "System", "Registries", "folder-registry.yaml"))
    return tmp


def fixture_doc(tmp, name="fixture-document.docx"):
    path = os.path.join(tmp, "00 Inbox", name)
    GENERATOR.build(path)
    return path


def run(tmp, path, dry=False):
    a = Args()
    a.target = os.path.relpath(path, tmp)
    a.dry_run = dry
    rep = Report("extract")
    ex.run(tmp, a, rep)
    return rep


def run_target(tmp, target, dry=False):
    """Run with the caller's exact target spelling (including absolute paths)."""
    a = Args()
    a.target = target
    a.dry_run = dry
    rep = Report("extract")
    ex.run(tmp, a, rep)
    return rep


class TestConversionFidelity(unittest.TestCase):
    """DoD-1: every feature the hand-rolled precedent preserved, asserted
    structurally rather than eyeballed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        mini_vault(self.tmp)
        self.rep = run(self.tmp, fixture_doc(self.tmp))
        with open(os.path.join(self.tmp, "00 Inbox", "fixture-document.md"),
                  encoding="utf-8") as stream:
            self.md = stream.read()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_extraction_succeeds(self):
        self.assertTrue(self.rep.ok, self.rep.errors)

    def test_heading_levels_survive(self):
        self.assertIn("\n# Verification Is The Feature\n", self.md)
        self.assertIn("\n## What v1 Preserves\n", self.md)
        self.assertIn("\n### Evidence\n", self.md)

    def test_list_nesting_and_numbering_survive(self):
        # a sub-list must not restart its parent's numbering
        self.assertIn("\n1. Structure survives conversion\n", self.md)
        self.assertIn("\n2. Formatting survives conversion\n", self.md)
        self.assertIn("\n  - Headings keep their level\n", self.md)
        self.assertIn("\n    - Even at the third level\n", self.md)

    def test_emphasis_survives(self):
        self.assertIn("**This phrase is bold.**", self.md)
        self.assertIn("*This phrase is italic.*", self.md)
        self.assertIn("***This phrase is both.***", self.md)

    def test_table_survives_as_a_table(self):
        self.assertIn("| Signal | Where it lives | Who owns it |", self.md)
        self.assertIn("| --- | --- | --- |", self.md)
        self.assertIn("| Voice split | the transcript | the human |", self.md)

    def test_image_extracted_and_referenced_at_true_position(self):
        media = os.path.join(self.tmp, "30 Sources", "Attachments",
                             "fixture-document-media", "diagram.png")
        self.assertTrue(os.path.exists(media), "image not written beside the original")
        before = self.md.index("The image below sits between two paragraphs")
        img = self.md.index("![diagram.png]")
        after = self.md.index("This paragraph follows the image.")
        self.assertLess(before, img)
        self.assertLess(img, after)

    def test_image_path_is_url_safe(self):
        # "30 Sources" has a space; an unencoded path renders as literal text
        self.assertIn("30%20Sources", self.md)

    def test_original_is_filed_immutable_and_pointed_at(self):
        orig = os.path.join(self.tmp, "30 Sources", "Attachments", "fixture-document.docx")
        self.assertTrue(os.path.exists(orig))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "00 Inbox",
                                                     "fixture-document.docx")))
        self.assertIn("original_location: \"30 Sources/Attachments/fixture-document.docx\"",
                      self.md)

    def test_derivative_is_born_draft_and_names_its_check(self):
        self.assertIn("status: draft", self.md)
        self.assertIn("x_extraction_check:", self.md)
        self.assertIn("x_extraction_paragraphs: 25", self.md)

    def test_dark_corners_are_reported_not_silent(self):
        warns = " ".join(self.rep.warnings)
        self.assertIn("1 footnotes", warns)
        self.assertIn("NOT extracted", warns)
        self.assertIn("text boxes", warns)

    def test_text_box_text_is_not_duplicated(self):
        # Word writes an alternate-content block twice; reading both doubles it
        self.assertEqual(self.md.count("Pull quote parked in a text box."), 1)


class TestVerificationGate(unittest.TestCase):
    """DoD-2: the gate is the feature. A lossy conversion must FAIL, emit no
    Markdown, file the original, and say so."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        mini_vault(self.tmp)
        self.doc = fixture_doc(self.tmp)
        self._real = ex.to_markdown

    def tearDown(self):
        ex.to_markdown = self._real
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _corrupt(self, drop="An extractor nobody can audit"):
        real = self._real

        def lossy(doc, media_prefix="media"):
            md, media = real(doc, media_prefix=media_prefix)
            return "\n\n".join(b for b in md.split("\n\n") if drop not in b), media
        ex.to_markdown = lossy

    def test_dropped_paragraph_fails_the_gate(self):
        self._corrupt()
        rep = run(self.tmp, self.doc)
        self.assertFalse(rep.ok)
        self.assertIn("VERIFICATION FAILED", " ".join(rep.errors))

    def test_failed_verification_emits_no_markdown(self):
        self._corrupt()
        run(self.tmp, self.doc)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "00 Inbox",
                                                     "fixture-document.md")),
                         "a partial extraction was emitted — the whole point is that it isn't")

    def test_failed_verification_files_the_original_with_a_pointer(self):
        self._corrupt()
        rep = run(self.tmp, self.doc)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "30 Sources", "Attachments",
                                                    "fixture-document.docx")))
        pointer = os.path.join(self.tmp, "00 Inbox", "fixture-document (unextracted).md")
        self.assertTrue(os.path.exists(pointer))
        body = read_file(pointer, encoding="utf-8")
        self.assertIn("x_extraction_status: failed", body)
        self.assertIn("parity check", body)
        self.assertIn("original_location:", body)
        self.assertIn("original_filed", rep.info)

    def test_counts_appear_in_the_report_on_every_run(self):
        rep = run(self.tmp, self.doc, dry=True)
        self.assertIn("paragraphs", rep.info)
        self.assertIn("characters", rep.info)
        self.assertIn("verification", rep.info)

    def test_verify_is_pure_and_reports_unmatched_indices_not_text(self):
        ok, detail = ex.verify(["alpha beta gamma", "delta epsilon"], "alpha beta gamma")
        self.assertFalse(ok)
        self.assertEqual(detail["unmatched_paragraphs"], 1)
        self.assertEqual(detail["unmatched_index_and_length"], [(2, len("delta epsilon"))])
        self.assertNotIn("delta", str(detail["unmatched_index_and_length"]))


class TestCommandBehavior(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        mini_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_writes_nothing(self):
        doc = fixture_doc(self.tmp)
        before = sorted(os.listdir(os.path.join(self.tmp, "00 Inbox")))
        rep = run(self.tmp, doc, dry=True)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(before, sorted(os.listdir(os.path.join(self.tmp, "00 Inbox"))))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "30 Sources")))

    def test_unsupported_format_is_refused_by_name(self):
        p = os.path.join(self.tmp, "00 Inbox", "photo.jpg")
        write_file(p, b"\xff\xd8\xff", mode="wb")
        rep = run(self.tmp, p)
        self.assertFalse(rep.ok)
        self.assertIn("unsupported format", " ".join(rep.errors))
        self.assertIn("Attachments", " ".join(rep.errors))

    def test_corrupt_zip_is_refused_without_traceback(self):
        p = os.path.join(self.tmp, "00 Inbox", "broken.docx")
        write_file(p, "not a zip", mode="w")
        rep = run(self.tmp, p)
        self.assertFalse(rep.ok)
        self.assertIn("not a readable .docx", " ".join(rep.errors))

    def test_local_only_derivatives_stay_inside_the_fence(self):
        """A Local Only capture is gitignored and ai_use: local-only. Filing its
        original into the shared Attachments folder would walk it across the
        privacy fence the user drew (DEC-065)."""
        fence = os.path.join(self.tmp, "30 Sources", "AI Chats", "Local Only")
        os.makedirs(fence)
        doc = os.path.join(fence, "private-notes.docx")
        GENERATOR.build(doc)
        rep = run(self.tmp, doc)
        self.assertTrue(rep.ok, rep.errors)
        self.assertTrue(os.path.exists(os.path.join(fence, "Attachments",
                                                    "private-notes.docx")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "30 Sources", "Attachments",
                                                     "private-notes.docx")))

    def test_external_source_is_read_only_and_outputs_default_inside_vault(self):
        external_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, external_dir, True)
        doc = os.path.join(external_dir, "outside document.docx")
        GENERATOR.build(doc)
        before_data = read_file(doc, "rb")
        before = os.stat(doc)

        rep = run_target(self.tmp, doc)

        self.assertTrue(rep.ok, rep.errors)
        self.assertTrue(os.path.exists(doc), "external input path was moved or deleted")
        after = os.stat(doc)
        self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
        self.assertEqual(before_data, read_file(doc, "rb"))
        self.assertFalse(os.path.exists(os.path.join(external_dir, "outside document.md")),
                         "derivative escaped the vault beside an external input")
        self.assertTrue(os.path.exists(os.path.join(
            self.tmp, "30 Sources", "Attachments", "outside document.docx")))
        self.assertTrue(os.path.exists(os.path.join(
            self.tmp, "00 Inbox", "outside document.md")))

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic links")
    def test_external_source_ancestor_symlink_is_refused_without_writes(self):
        real = tempfile.mkdtemp()
        linked_parent = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, real, True)
        self.addCleanup(shutil.rmtree, linked_parent, True)
        doc = os.path.join(real, "outside.docx")
        GENERATOR.build(doc)
        os.symlink(real, os.path.join(linked_parent, "redirect"))

        rep = run_target(self.tmp, os.path.join(linked_parent, "redirect", "outside.docx"))

        self.assertFalse(rep.ok)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "00 Inbox", "outside.md")))
        self.assertFalse(os.path.exists(os.path.join(
            self.tmp, "30 Sources", "Attachments", "outside.docx")))

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic links")
    def test_external_source_ancestor_swap_during_read_is_refused_without_writes(self):
        holder = tempfile.mkdtemp()
        alternate = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, holder, True)
        self.addCleanup(shutil.rmtree, alternate, True)
        source_dir = os.path.join(holder, "source")
        moved = os.path.join(holder, "moved-source")
        os.mkdir(source_dir)
        doc = os.path.join(source_dir, "outside.docx")
        GENERATOR.build(doc)
        original_open = sp._open_absolute_directory
        canonical_source_dir = sp._canonical_platform_path(source_dir)
        calls = 0

        def swap_on_reproof(path):
            nonlocal calls
            if os.path.abspath(path) == canonical_source_dir:
                calls += 1
                if calls == 2:
                    os.rename(source_dir, moved)
                    os.symlink(alternate, source_dir)
            return original_open(path)

        with mock.patch.object(sp, "_open_absolute_directory", side_effect=swap_on_reproof):
            rep = run_target(self.tmp, doc)

        self.assertFalse(rep.ok)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "00 Inbox", "outside.md")))
        self.assertFalse(os.path.exists(os.path.join(
            self.tmp, "30 Sources", "Attachments", "outside.docx")))

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic links")
    def test_symlink_source_is_refused_without_writes(self):
        external_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, external_dir, True)
        external = os.path.join(external_dir, "outside.docx")
        GENERATOR.build(external)
        linked = os.path.join(self.tmp, "00 Inbox", "linked.docx")
        os.symlink(external, linked)
        before = hashlib.sha256(read_file(external, "rb")).hexdigest()

        rep = run_target(self.tmp, "00 Inbox/linked.docx")

        self.assertFalse(rep.ok)
        self.assertIn("symlink", " ".join(rep.errors).lower())
        self.assertTrue(os.path.islink(linked))
        self.assertEqual(before, hashlib.sha256(read_file(external, "rb")).hexdigest())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "30 Sources", "Attachments")))

    def test_unsafe_attachment_registry_path_is_refused_before_writes(self):
        registry = os.path.join(self.tmp, "System", "Registries", "folder-registry.yaml")
        text = read_file(registry, encoding="utf-8")
        text = text.replace("30 Sources/Attachments", "../../outside-attachments")
        with open(registry, "w", encoding="utf-8") as fh:
            fh.write(text)
        doc = fixture_doc(self.tmp)
        before = hashlib.sha256(read_file(doc, "rb")).hexdigest()

        rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("contain", " ".join(rep.errors).lower())
        self.assertTrue(os.path.exists(doc))
        self.assertEqual(before, hashlib.sha256(read_file(doc, "rb")).hexdigest())

    def test_absolute_attachment_registry_path_is_refused_before_writes(self):
        external_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, external_dir, True)
        registry = os.path.join(self.tmp, "System", "Registries", "folder-registry.yaml")
        text = read_file(registry, encoding="utf-8")
        text = text.replace("30 Sources/Attachments", external_dir)
        with open(registry, "w", encoding="utf-8") as fh:
            fh.write(text)
        doc = fixture_doc(self.tmp)
        before = read_file(doc, "rb")

        rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("contain", " ".join(rep.errors).lower())
        self.assertEqual(before, read_file(doc, "rb"))
        self.assertEqual([], os.listdir(external_dir))

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic links")
    def test_symlink_attachment_parent_is_refused_before_writes(self):
        external_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, external_dir, True)
        registry = os.path.join(self.tmp, "System", "Registries", "folder-registry.yaml")
        text = read_file(registry, encoding="utf-8")
        text = text.replace("30 Sources/Attachments", "Redirected Attachments")
        with open(registry, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.symlink(external_dir, os.path.join(self.tmp, "Redirected Attachments"))
        doc = fixture_doc(self.tmp)
        before = read_file(doc, "rb")

        rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("symlink", " ".join(rep.errors).lower())
        self.assertEqual(before, read_file(doc, "rb"))
        self.assertEqual([], os.listdir(external_dir))

    def test_portable_case_collision_in_output_parent_is_refused(self):
        os.makedirs(os.path.join(self.tmp, "30 Sources", "attachments"))
        doc = fixture_doc(self.tmp)
        before = read_file(doc, "rb")

        rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("collision", " ".join(rep.errors).lower())
        self.assertEqual(before, read_file(doc, "rb"))

    def test_portable_unicode_collision_in_output_parent_is_refused(self):
        composed = "Caf\u00e9"
        decomposed = "Cafe\u0301"
        registry = os.path.join(self.tmp, "System", "Registries", "folder-registry.yaml")
        text = read_file(registry, encoding="utf-8")
        text = text.replace("30 Sources/Attachments", f"30 Sources/{composed}")
        with open(registry, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.makedirs(os.path.join(self.tmp, "30 Sources", decomposed))
        doc = fixture_doc(self.tmp)

        rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("collision", " ".join(rep.errors).lower())
        self.assertTrue(os.path.exists(doc))

    def test_missing_target_reports_usage(self):
        a = Args()
        rep = Report("extract")
        ex.run(self.tmp, a, rep)
        self.assertIn("usage: aios extract", " ".join(rep.errors))


class TestDocxSafetyBudgets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        mini_vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_absolute_zip_member_is_refused_without_mutation(self):
        doc = fixture_doc(self.tmp)
        with zipfile.ZipFile(doc, "a", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("/escaped.txt", b"no")
        before = read_file(doc, "rb")

        rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("unsafe member path", " ".join(rep.errors).lower())
        self.assertEqual(before, read_file(doc, "rb"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "30 Sources")))

    def test_member_count_budget_is_enforced(self):
        doc = fixture_doc(self.tmp)
        with mock.patch.object(ex, "DOCX_MAX_MEMBERS", 1):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")
        self.assertFalse(rep.ok)
        self.assertIn("zip members", " ".join(rep.errors).lower())
        self.assertTrue(os.path.exists(doc))

    def test_individual_member_budget_is_enforced(self):
        doc = fixture_doc(self.tmp)
        with mock.patch.object(ex, "DOCX_MAX_MEMBER", 1):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")
        self.assertFalse(rep.ok)
        self.assertIn("member exceeds", " ".join(rep.errors).lower())
        self.assertTrue(os.path.exists(doc))

    def test_total_uncompressed_budget_is_enforced(self):
        doc = fixture_doc(self.tmp)
        with mock.patch.object(ex, "DOCX_MAX_UNCOMPRESSED", 1):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")
        self.assertFalse(rep.ok)
        self.assertIn("uncompressed safety budget", " ".join(rep.errors).lower())
        self.assertTrue(os.path.exists(doc))

    def test_media_budget_is_enforced(self):
        doc = fixture_doc(self.tmp)
        with mock.patch.object(ex, "DOCX_MAX_MEDIA", 0):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")
        self.assertFalse(rep.ok)
        self.assertIn("media exceeds", " ".join(rep.errors).lower())
        self.assertTrue(os.path.exists(doc))

    def test_compression_ratio_budget_is_enforced(self):
        doc = fixture_doc(self.tmp)
        with mock.patch.object(ex, "DOCX_MAX_COMPRESSION_RATIO", 1):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")
        self.assertFalse(rep.ok)
        self.assertIn("compression ratio", " ".join(rep.errors).lower())
        self.assertTrue(os.path.exists(doc))

    def test_compressed_input_budget_is_enforced_before_package_loading(self):
        doc = fixture_doc(self.tmp)
        before = read_file(doc, "rb")
        with mock.patch.object(ex, "DOCX_MAX_COMPRESSED", 1):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("input", " ".join(rep.errors).lower())
        self.assertIn("safety limit", " ".join(rep.errors).lower())
        self.assertEqual(before, read_file(doc, "rb"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "30 Sources")))


class TestOutputTransactionRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        mini_vault(self.tmp)
        self.doc = fixture_doc(self.tmp)
        self.before_data = read_file(self.doc, "rb")
        before = os.stat(self.doc)
        self.before_identity = before.st_dev, before.st_ino

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _assert_exact_source_and_no_output_residue(self):
        self.assertTrue(os.path.exists(self.doc))
        after = os.stat(self.doc)
        self.assertEqual(self.before_identity, (after.st_dev, after.st_ino))
        self.assertEqual(self.before_data, read_file(self.doc, "rb"))
        self.assertEqual(["fixture-document.docx"],
                         sorted(os.listdir(os.path.join(self.tmp, "00 Inbox"))))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "30 Sources")))
        self.assertFalse(any(name.startswith(".aios-output-")
                             for name in os.listdir(self.tmp)))

    def test_failure_after_output_commit_restores_exact_old_state(self):
        def fail(event, index, target):
            del index, target
            if event == "after-output-commit":
                raise OSError("injected output commit failure")

        with mock.patch.object(sp, "_mutation_boundary", side_effect=fail):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("prior state restored", " ".join(rep.errors).lower())
        self._assert_exact_source_and_no_output_residue()

    def test_failure_after_source_file_restores_original_inode_and_outputs(self):
        def fail(event, index, target):
            del index, target
            if event == "after-source-file":
                raise OSError("injected filing failure")

        with mock.patch.object(sp, "_mutation_boundary", side_effect=fail):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertIn("prior state restored", " ".join(rep.errors).lower())
        self._assert_exact_source_and_no_output_residue()

    def test_destination_appearing_at_commit_is_never_clobbered(self):
        raced = os.path.join(self.tmp, "30 Sources", "Attachments",
                             "fixture-document.docx")
        injected = False

        def race(event, index, target):
            nonlocal injected
            del target
            if event == "before-output-commit" and index == 0 and not injected:
                injected = True
                with open(raced, "wb") as fh:
                    fh.write(b"concurrent user data")

        with mock.patch.object(sp, "_mutation_boundary", side_effect=race):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        self.assertEqual(b"concurrent user data", read_file(raced, "rb"))
        self.assertEqual(self.before_data, read_file(self.doc, "rb"))
        self.assertEqual(self.before_identity,
                         (os.stat(self.doc).st_dev, os.stat(self.doc).st_ino))

    def test_parent_moved_outside_vault_before_commit_receives_no_output(self):
        attachments = os.path.join(self.tmp, "30 Sources", "Attachments")
        os.makedirs(attachments)
        external = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, external, True)
        moved = os.path.join(external, "moved-attachments")
        injected = False

        def race(event, index, target):
            nonlocal injected
            del target
            if event == "before-output-commit" and index == 0 and not injected:
                injected = True
                os.rename(attachments, moved)

        with mock.patch.object(sp, "_mutation_boundary", side_effect=race):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertFalse(rep.ok)
        escaped_files = [os.path.join(base, name)
                         for base, _, names in os.walk(moved) for name in names]
        self.assertEqual([], escaped_files, "an output escaped through a moved parent fd")
        self.assertEqual(self.before_data, read_file(self.doc, "rb"))
        self.assertEqual(self.before_identity,
                         (os.stat(self.doc).st_dev, os.stat(self.doc).st_ino))

    def test_external_input_change_during_commit_rolls_back_outputs(self):
        external = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, external, True)
        doc = os.path.join(external, "outside.docx")
        GENERATOR.build(doc)
        injected = False

        def race(event, index, target):
            nonlocal injected
            del index, target
            if event == "before-output-commit" and not injected:
                injected = True
                with open(doc, "ab") as fh:
                    fh.write(b"changed concurrently")

        with mock.patch.object(sp, "_mutation_boundary", side_effect=race):
            rep = run_target(self.tmp, doc)

        self.assertFalse(rep.ok)
        self.assertIn("changed", " ".join(rep.errors).lower())
        self.assertFalse(os.path.exists(os.path.join(
            self.tmp, "30 Sources", "Attachments", "outside.docx")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "00 Inbox", "outside.md")))

    def test_staging_cleanup_residue_is_reported(self):
        injected = False

        def race(event, index, target):
            nonlocal injected
            del index, target
            if event == "after-output-commit" and not injected:
                injected = True
                stage = next(name for name in os.listdir(self.tmp)
                             if name.startswith(".aios-output-"))
                with open(os.path.join(self.tmp, stage, "concurrent-entry"), "wb") as fh:
                    fh.write(b"not owned by the transaction")

        with mock.patch.object(sp, "_mutation_boundary", side_effect=race):
            rep = run_target(self.tmp, "00 Inbox/fixture-document.docx")

        self.assertTrue(rep.ok, rep.errors)
        self.assertTrue(any("staging" in warning.lower() for warning in rep.warnings),
                        "staging residue was silently omitted from the report")
        self.assertTrue(any(name.startswith(".aios-output-")
                            for name in os.listdir(self.tmp)))

class TestNoThirdPartyDependency(unittest.TestCase):
    def test_stdlib_only(self):
        """PyYAML is this product's only third-party dependency (SPEC §1). A
        `.docx` is a zip of XML; python-docx would be a second one."""
        src = read_file(os.path.join(SCRIPTS, "cmd", "extract.py"), encoding="utf-8")
        self.assertNotIn("import docx", src)
        self.assertNotIn("python-docx", src.replace("no python-docx", "")
                                            .replace("NO python-docx", ""))


class TestRealCorpusSmoke(unittest.TestCase):
    """A generated fixture can only prove what its author thought to put in it.
    This runs the converter over a document built to be awkward — no heading
    styles at all, emphasis used as structure — because that is what real .docx
    files handed to a vault actually look like."""

    def test_document_without_heading_styles_still_verifies(self):
        tmp = tempfile.mkdtemp()
        try:
            mini_vault(tmp)
            body = "".join(GENERATOR.p(f"Paragraph {i} of a styleless document, long "
                                       f"enough to matter.", bold=(i % 3 == 0))
                           for i in range(50))
            path = os.path.join(tmp, "00 Inbox", "styleless.docx")
            GENERATOR.build(path)
            import zipfile
            # rewrite just the body, keeping the rest of the package
            with zipfile.ZipFile(path) as z:
                parts = {n: z.read(n) for n in z.namelist()}
            parts["word/document.xml"] = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document {GENERATOR.W}><w:body>{body}</w:body></w:document>').encode()
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                for n, d in parts.items():
                    z.writestr(n, d)
            rep = run(tmp, path)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("50/50", str(rep.info["paragraphs"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestKillSwitch(unittest.TestCase):
    def test_extract_refuses_while_the_switch_is_off(self):
        tmp = tempfile.mkdtemp()
        try:
            mini_vault(tmp)
            mp = os.path.join(tmp, "SYSTEM-MANIFEST.yaml")
            s = read_file(mp, encoding="utf-8").replace("ai_writes_enabled: true",
                                                          "ai_writes_enabled: false")
            write_file(mp, s, mode="w", encoding="utf-8")
            doc = fixture_doc(tmp)
            before = hashlib.sha256(read_file(doc, "rb")).hexdigest()
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "aios.py"), "extract",
                                os.path.relpath(doc, tmp), "--root", tmp],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("kill switch", r.stdout + r.stderr)
            self.assertTrue(os.path.exists(doc))
            self.assertEqual(before, hashlib.sha256(read_file(doc, "rb")).hexdigest())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
