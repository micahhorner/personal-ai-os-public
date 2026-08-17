"""v1.37.0 (DEC-092): the sync storage boundary.

Pins: the conservative .gitignore matcher (never a false "covered"); validate's
two-directional cross-check (unbacked promise = error, gitignored-but-unmarked =
warning); Local Only folder/field agreement; the rolled-up restricted warning;
fail-closed unknown `sync` values (validate + okf-export); and the DEC-062
onboarding-trio parity for the new stage-2 storage question.
"""
import os
import shutil
import tempfile
import unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
import sys
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                                   # noqa: E402
from lib.gitignore import (GitignoreMatcher, COVERED,           # noqa: E402
                           NOT_COVERED, UNVERIFIABLE)
from cmd.okfexport import exportable                            # noqa: E402
from cmd import validate as v_mod                               # noqa: E402


NOTE = ("---\nid: note-{n}\ntype: note\ncreated: 2026-07-25\nupdated: 2026-07-25\n"
        "summary: probe\n{extra}---\nbody\n")


def _read_text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _vault(outer):
    """Scratch vault: real manifest + real schemas, empty knowledge folder."""
    root = os.path.join(outer, "v")
    os.makedirs(os.path.join(root, "20 Knowledge"))
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as stream:
        stream.write(product_manifest())
    shutil.copytree(os.path.join(VAULT, "System", "Schemas"),
                    os.path.join(root, "System", "Schemas"))
    return root


def _write(root, rel, extra="", n="p"):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(NOTE.format(n=n, extra=extra))


def _validate(root):
    class A:
        json = False
    rep = Report("validate")
    v_mod.run(root, A(), rep)
    return rep


class TestConservativeMatcher(unittest.TestCase):
    """The spec's fence: when unsure, say so — never claim covered."""

    def test_plain_rules_cover(self):
        gi = GitignoreMatcher("secret.md\nHidden/\n20 Knowledge/x.md\n*.key\n")
        self.assertEqual(gi.coverage("a/b/secret.md"), COVERED)
        self.assertEqual(gi.coverage("deep/Hidden/note.md"), COVERED)
        self.assertEqual(gi.coverage("20 Knowledge/x.md"), COVERED)
        self.assertEqual(gi.coverage("k/private.key"), COVERED)
        self.assertEqual(gi.coverage("20 Knowledge/other.md"), NOT_COVERED)

    def test_local_only_default_rule_covers_the_folder_convention(self):
        gi = GitignoreMatcher("**/Local Only/**\n")
        self.assertEqual(gi.coverage("80 User/Local Only/twin.md"), COVERED)
        self.assertEqual(gi.coverage("20 Knowledge/Local Only/deep/n.md"), COVERED)
        self.assertEqual(gi.coverage("20 Knowledge/open.md"), NOT_COVERED)

    def test_negation_never_yields_covered(self):
        gi = GitignoreMatcher("stuff/\n!stuff/keep.md\n")
        self.assertEqual(gi.coverage("stuff/other.md"), COVERED)   # negation clearly elsewhere
        self.assertEqual(gi.coverage("stuff/keep.md"), UNVERIFIABLE)

    def test_out_of_model_patterns_are_unverifiable_not_covered(self):
        self.assertEqual(GitignoreMatcher("th[i]ng.md\n").coverage("thing.md"),
                         UNVERIFIABLE)
        self.assertEqual(GitignoreMatcher("a/**/b.md\n").coverage("a/x/b.md"),
                         UNVERIFIABLE)

    def test_missing_gitignore_covers_nothing(self):
        self.assertEqual(GitignoreMatcher(None).coverage("x.md"), NOT_COVERED)


class TestValidateCrossCheck(unittest.TestCase):
    """DoD-1: unbacked promise = error; backed = green; ignored-but-unmarked =
    warning; folder/field disagreement = error."""

    def _run(self, extra="", gitignore=None, rel="20 Knowledge/n.md"):
        with tempfile.TemporaryDirectory() as outer:
            root = _vault(outer)
            _write(root, rel, extra=extra)
            if gitignore is not None:
                with open(os.path.join(root, ".gitignore"), "w") as stream:
                    stream.write(gitignore)
            return _validate(root)

    def test_unbacked_promise_is_an_error(self):
        rep = self._run(extra="sync: local-only\n")
        self.assertTrue(any("promise is unbacked" in e for e in rep.errors), rep.errors)

    def test_backed_promise_is_green(self):
        rep = self._run(extra="sync: local-only\n", gitignore="20 Knowledge/n.md\n")
        self.assertFalse(any("unbacked" in e for e in rep.errors), rep.errors)
        self.assertFalse(any("UNVERIFIABLE" in w for w in rep.warnings), rep.warnings)

    def test_unverifiable_coverage_is_a_warning_not_covered(self):
        rep = self._run(extra="sync: local-only\n",
                        gitignore="20 Knowledge/n.md\n!20 Knowledge/n.md\n")
        self.assertFalse(any("unbacked" in e for e in rep.errors), rep.errors)
        self.assertTrue(any("UNVERIFIABLE" in w for w in rep.warnings), rep.warnings)

    def test_gitignored_but_unmarked_warns(self):
        rep = self._run(extra="", gitignore="20 Knowledge/n.md\n")
        self.assertTrue(any("gitignored but not marked" in w for w in rep.warnings),
                        rep.warnings)

    def test_local_only_folder_implies_the_marking_advisory(self):
        # implied-by-folder only: WARNING, not error — the folder convention
        # predates DEC-092 and a lived-in vault upgrading in must not go red
        # on its own content (U1). An explicit field is the strict case above.
        rep = self._run(rel="20 Knowledge/Local Only/n.md")
        self.assertFalse(any("unbacked" in e for e in rep.errors), rep.errors)
        self.assertTrue(any("no .gitignore rule backs it" in w for w in rep.warnings),
                        rep.warnings)

    def test_explicit_field_under_local_only_folder_stays_strict(self):
        rep = self._run(rel="20 Knowledge/Local Only/n.md", extra="sync: local-only\n")
        self.assertTrue(any("promise is unbacked" in e for e in rep.errors), rep.errors)

    def test_folder_field_disagreement_is_an_error(self):
        rep = self._run(rel="20 Knowledge/Local Only/n.md", extra="sync: allowed\n",
                        gitignore="**/Local Only/**\n")
        self.assertTrue(any("may not disagree" in e for e in rep.errors), rep.errors)

    def test_unknown_sync_value_is_a_validate_error(self):
        rep = self._run(extra="sync: Local-Only\n", gitignore="20 Knowledge/n.md\n")
        self.assertTrue(any("'sync: Local-Only' not in vocabulary" in e
                            for e in rep.errors), rep.errors)


class TestRestrictedWarning(unittest.TestCase):
    """DoD-2: `restricted` on any record → the explanatory warning, once, rolled up."""

    def test_fires_once_rolled_up(self):
        with tempfile.TemporaryDirectory() as outer:
            root = _vault(outer)
            _write(root, "20 Knowledge/a.md", extra="classification: restricted\n", n="a")
            _write(root, "20 Knowledge/b.md", extra="classification: restricted\n", n="b")
            rep = _validate(root)
        hits = [w for w in rep.warnings if "classification: restricted" in w]
        self.assertEqual(len(hits), 1, rep.warnings)
        self.assertIn("2 record(s)", hits[0])
        self.assertIn("sync: local-only", hits[0])   # the message names the right pair

    def test_example_material_is_exempt(self):
        with tempfile.TemporaryDirectory() as outer:
            root = _vault(outer)
            _write(root, "20 Knowledge/a.md",
                   extra="classification: restricted\nfile_class: example\n")
            rep = _validate(root)
        self.assertFalse(any("classification: restricted" in w for w in rep.warnings),
                         rep.warnings)


class TestExportFailsClosed(unittest.TestCase):
    """DoD-3: the DEC-066 fail-closed pattern extended to `sync` on the export surface."""

    BASE = {"id": "note-x", "status": "active", "classification": "internal",
            "ai_use": "allowed"}

    def test_unrecognised_sync_never_exports(self):
        for bad in ("Local-Only", "local_only", "never", "yes"):
            meta = dict(self.BASE, sync=bad)
            self.assertFalse(exportable(meta, "20 Knowledge/x.md"), bad)

    def test_local_only_never_exports_on_any_profile(self):
        meta = dict(self.BASE, sync="local-only")
        self.assertFalse(exportable(meta, "20 Knowledge/x.md"))

    def test_allowed_and_absent_still_export(self):
        self.assertTrue(exportable(dict(self.BASE), "20 Knowledge/x.md"))
        self.assertTrue(exportable(dict(self.BASE, sync="allowed"), "20 Knowledge/x.md"))


class TestOnboardingTrioParity(unittest.TestCase):
    """DoD-4 (DEC-062): the stage-2 storage question exists in all three files,
    they agree it is separate from the sensitivity question, and the stage
    structure still matches across the trio."""

    FILES = ["System/Onboarding/Onboarding Specification.md",
             "System/Onboarding/Human Onboarding Guide.md",
             "System/Onboarding/AI Onboarding Procedure.md"]

    def _texts(self):
        return {f: _read_text(os.path.join(VAULT, f))
                for f in self.FILES}

    def test_storage_question_present_in_all_three(self):
        for f, text in self._texts().items():
            self.assertIn("sync: local-only", text, f)
            self.assertIn("storage", text.lower(), f)
            # each file must carry the never-use-restricted-for-storage guidance
            # in its own register (spec/procedure cite the field; guide says "no AI")
            self.assertTrue("restricted" in text or "no AI may read this" in text, f)

    def test_stage_structure_matches(self):
        t = self._texts()
        spec = t[self.FILES[0]]
        spec_stages = [f"### Stage {i} — " in spec for i in range(1, 9)]
        self.assertTrue(all(spec_stages), "spec must define stages 1-8")
        guide = t[self.FILES[1]]
        for i in range(1, 9):
            self.assertIn(f"**{i} · ", guide, f"guide missing stage {i}")
        proc = t[self.FILES[2]]
        for i in range(1, 9):
            self.assertIn(f"- **{i}**:", proc, f"procedure missing stage {i}")

    def test_trio_versions_move_together(self):
        t = self._texts()
        import re
        vers = {f: re.search(r"^version: (\S+)", txt, re.M).group(1)
                for f, txt in t.items()}
        self.assertEqual(len(set(vers.values())), 1, vers)


if __name__ == "__main__":
    unittest.main()
