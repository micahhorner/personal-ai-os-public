"""docgen regressions (DEC-084): marked blocks regenerate from source, a stale
block fails --check, surrounding prose is untouched, and the master is current."""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from lib.report import Report          # noqa: E402
from lib import safepaths as sp         # noqa: E402
from cmd import docgen                 # noqa: E402


def _read_text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _read_bytes(path):
    with open(path, "rb") as stream:
        return stream.read()


def _write_text(path, text):
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(text)


class _Fill:
    check = False
    apply = False
    confirm = False
    review_sha256 = None


class _Check:
    check = True
    apply = False
    confirm = False
    review_sha256 = None


class _Apply:
    check = False
    apply = True
    confirm = True

    def __init__(self, review_sha256):
        self.review_sha256 = review_sha256


class TestBuildersReadSource(unittest.TestCase):
    def test_file_census_excludes_the_product_local_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_text(os.path.join(tmp, "product.md"), "product\n")
            os.makedirs(os.path.join(tmp, ".venv", "bin"))
            _write_text(os.path.join(tmp, ".venv", "bin", "dependency.py"), "ignored\n")
            census = docgen.block_file_census(tmp)
            self.assertIn("**1 files on disk**", census)

    def test_file_census_excludes_user_content_declared_by_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_text(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"),
                        "directories:\n  content: [00 Inbox, 20 Knowledge]\n")
            os.makedirs(os.path.join(tmp, "00 Inbox"))
            _write_text(os.path.join(tmp, "00 Inbox", "capture.md"), "ordinary content\n")
            before = docgen.block_file_census(tmp)
            _write_text(os.path.join(tmp, "00 Inbox", "second.md"), "more content\n")
            self.assertEqual(before, docgen.block_file_census(tmp))

    def test_command_block_lists_the_real_cli(self):
        text = docgen.block_commands(VAULT)
        cmds = docgen._cli_commands(VAULT)
        self.assertIn(str(len(cmds)), text)
        for c in cmds:
            self.assertIn(f"`{c}`", text)

    def test_capabilities_block_counts_the_folder(self):
        # Against `*/SKILL.md`, the shipped form since DEC-070. This test used to
        # glob the retired flat `Capabilities/*.md`, which matches nothing — so it
        # asserted that "0" appears in "the 0 capabilities" and passed while the
        # builder was dead. A test that agrees with the bug is worse than none.
        n = len(glob.glob(os.path.join(VAULT, "System", "Capabilities", "*", "SKILL.md")))
        self.assertGreater(n, 1, "the master ships more than one capability")
        self.assertIn(f"the {n} capabilities", docgen.block_capabilities(VAULT))

    def test_capability_count_block_matches_disk(self):
        n = len(glob.glob(os.path.join(VAULT, "System", "Capabilities", "*", "SKILL.md")))
        self.assertEqual(docgen.block_capability_count(VAULT), str(n))

    def test_agent_and_note_class_counts_match_disk(self):
        agents = len(glob.glob(os.path.join(VAULT, "System", "Agents", "*", "AGENT.md")))
        self.assertEqual(docgen.block_agent_count(VAULT), str(agents))
        # A note class is a schema file that DECLARES `schema:` — not merely a
        # file in the folder. The filename proxy this used to apply was exact
        # until `pack-manifest.yaml` arrived: a contract for a third-party
        # artifact, deliberately carrying no `schema:` key so that
        # `validate.load_schemas` never registers it as a phantom record type.
        import yaml
        classes = []
        for p in glob.glob(os.path.join(VAULT, "System", "Schemas", "*.yaml")):
            with open(p, encoding="utf-8") as fh:
                d = yaml.safe_load(fh) or {}
            if (isinstance(d, dict) and d.get("schema")
                    and d["schema"] not in {"component", "migration-manifest"}):
                classes.append(p)
        self.assertEqual(docgen.block_note_class_count(VAULT), str(len(classes)))

    def test_note_class_count_excludes_system_contract_schemas(self):
        with tempfile.TemporaryDirectory() as tmp:
            schemas = os.path.join(tmp, "System", "Schemas")
            os.makedirs(schemas)
            _write_text(os.path.join(schemas, "note.yaml"), "schema: note\n")
            _write_text(os.path.join(schemas, "component.yaml"),
                        "schema: component\n")
            _write_text(os.path.join(schemas, "migration-manifest.yaml"),
                        "schema: migration-manifest\n")
            self.assertEqual(docgen.block_note_class_count(tmp), "1")


class TestRoundTrip(unittest.TestCase):
    def _doc(self, tmp, body):
        os.makedirs(os.path.join(tmp, "System", "Scripts"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "System", "Capabilities"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "System", "Documentation"), exist_ok=True)
        shutil.copy(os.path.join(VAULT, "System", "Scripts", "aios.py"),
                    os.path.join(tmp, "System", "Scripts", "aios.py"))
        with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w", encoding="utf-8") as fh:
            fh.write("runtime:\n  ai_writes_enabled: true\nprotected_objects:\n"
                     "  - SYSTEM-MANIFEST.yaml\n  - System/Governance/\n")
        for c in ("safe-write.md", "recover.md"):
            _write_text(os.path.join(tmp, "System", "Capabilities", c), "x")
        p = os.path.join(tmp, "System", "Documentation", "d.md")
        _write_text(p, body)
        return p

    def test_fill_then_check_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._doc(tmp, "a\n<!-- docgen:commands -->\nWRONG\n<!-- /docgen:commands -->\nb\n")
            r = Report("docgen"); docgen.run(tmp, _Fill(), r)
            self.assertEqual(r.errors, [])
            self.assertNotIn("WRONG", _read_text(p))
            c = Report("docgen"); docgen.run(tmp, _Check(), c)
            self.assertEqual(c.errors, [], "a freshly filled block must pass --check")

    def test_stale_block_fails_check_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._doc(tmp, "<!-- docgen:commands -->\nSTALE\n<!-- /docgen:commands -->\n")
            before = _read_text(p)
            c = Report("docgen"); docgen.run(tmp, _Check(), c)
            self.assertTrue(any("stale" in e for e in c.errors), c.errors)
            self.assertEqual(_read_text(p), before, "--check must never write")

    def test_unclosed_block_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._doc(tmp, "<!-- docgen:commands -->\nno close\n")
            r = Report("docgen"); docgen.run(tmp, _Fill(), r)
            self.assertTrue(any("never closed" in e for e in r.errors), r.errors)

    def test_unknown_key_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._doc(tmp, "<!-- docgen:bogus -->\nx\n<!-- /docgen:bogus -->\n")
            r = Report("docgen"); docgen.run(tmp, _Fill(), r)
            self.assertTrue(any("unknown docgen key" in e for e in r.errors), r.errors)

    def test_surrounding_prose_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._doc(tmp, "KEEP A\n<!-- docgen:commands -->\nx\n<!-- /docgen:commands -->\nKEEP B\n")
            docgen.run(tmp, _Fill(), Report("docgen"))
            out = _read_text(p)
            self.assertIn("KEEP A", out)
            self.assertIn("KEEP B", out)

    def test_malformed_file_refuses_all_docgen_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            valid = self._doc(
                tmp, "<!-- docgen:commands -->\nSTALE\n<!-- /docgen:commands -->\n"
            )
            broken = os.path.join(tmp, "System", "Documentation", "broken.md")
            with open(broken, "w") as stream:
                stream.write("<!-- docgen:commands -->\nno close\n")
            before = _read_bytes(valid)

            rep = Report("docgen"); docgen.run(tmp, _Fill(), rep)

            self.assertFalse(rep.ok)
            self.assertEqual(before, _read_bytes(valid))

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic links")
    def test_symlink_target_is_refused_without_external_mutation(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            self._doc(tmp, "ordinary text\n")
            external = os.path.join(outside, "external.md")
            body = "<!-- docgen:commands -->\nEXTERNAL\n<!-- /docgen:commands -->\n"
            with open(external, "w") as stream:
                stream.write(body)
            os.symlink(external, os.path.join(tmp, "System", "Documentation", "linked.md"))

            rep = Report("docgen"); docgen.run(tmp, _Fill(), rep)

            self.assertFalse(rep.ok)
            self.assertIn("symlink", " ".join(rep.errors).lower())
            self.assertEqual(body, _read_text(external))

    def test_case_alias_targets_are_refused_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self._doc(
                tmp, "<!-- docgen:commands -->\nONE\n<!-- /docgen:commands -->\n"
            )
            second = os.path.join(tmp, "System", "Documentation", "D.MD")
            if os.path.abspath(second) == os.path.abspath(first) or os.path.exists(second):
                self.skipTest("filesystem does not preserve case-distinct aliases")
            with open(second, "w") as stream:
                stream.write("<!-- docgen:commands -->\nTWO\n<!-- /docgen:commands -->\n")
            before = {path: _read_bytes(path) for path in (first, second)}

            rep = Report("docgen"); docgen.run(tmp, _Fill(), rep)

            self.assertFalse(rep.ok)
            self.assertIn("case/Unicode", " ".join(rep.errors))
            self.assertEqual(before, {path: _read_bytes(path)
                                      for path in (first, second)})

    def test_second_commit_fault_rolls_back_every_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self._doc(
                tmp, "<!-- docgen:commands -->\nONE\n<!-- /docgen:commands -->\n"
            )
            second = os.path.join(tmp, "System", "Documentation", "second.md")
            with open(second, "w") as stream:
                stream.write("<!-- docgen:commands -->\nTWO\n<!-- /docgen:commands -->\n")
            before = {path: _read_bytes(path) for path in (first, second)}

            def fail(event, index, target):
                del target
                if event == "after-commit" and index == 1:
                    raise OSError("injected docgen commit fault")

            with mock.patch.object(sp, "_mutation_boundary", side_effect=fail):
                rep = Report("docgen"); docgen.run(tmp, _Fill(), rep)

            self.assertFalse(rep.ok)
            self.assertIn("rolled back", " ".join(rep.errors).lower())
            self.assertEqual(before, {path: _read_bytes(path)
                                      for path in (first, second)})
            leftovers = []
            for directory, _dirs, files in os.walk(tmp):
                leftovers += [os.path.join(directory, name) for name in files
                              if ".aios-" in name]
            self.assertEqual([], leftovers)


class TestProtectedReviewPlan(unittest.TestCase):
    def _doc(self, tmp, body):
        return TestRoundTrip._doc(self, tmp, body)

    def _protected_batch(self, tmp):
        ordinary = self._doc(
            tmp, "<!-- docgen:commands -->\nOLD\n<!-- /docgen:commands -->\n"
        )
        governance = os.path.join(tmp, "System", "Governance", "g.md")
        os.makedirs(os.path.dirname(governance), exist_ok=True)
        with open(governance, "w", encoding="utf-8") as fh:
            fh.write("<!-- docgen:commands -->\nOLD\n<!-- /docgen:commands -->\n")
        return ordinary, governance

    def test_check_reports_deterministic_exact_protected_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            _ordinary, governance = self._protected_batch(tmp)
            first = Report("docgen"); docgen.run(tmp, _Check(), first)
            second = Report("docgen"); docgen.run(tmp, _Check(), second)
            self.assertEqual(first.info["review_sha256"], second.info["review_sha256"])
            self.assertEqual(first.info["protected_targets"], [
                os.path.relpath(governance, tmp).replace(os.sep, "/")
            ])
            self.assertEqual(
                [row["path"] for row in first.info["review_plan"]["targets"]],
                ["System/Documentation/d.md", "System/Governance/g.md"],
            )

    def test_missing_or_wrong_review_is_zero_write_for_whole_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._protected_batch(tmp)
            before = {path: _read_bytes(path) for path in paths}
            for args in (_Fill(), _Apply("0" * 64)):
                rep = Report("docgen"); docgen.run(tmp, args, rep)
                self.assertFalse(rep.ok)
                self.assertEqual(before, {path: _read_bytes(path) for path in paths})

    def test_exact_fresh_review_applies_entire_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._protected_batch(tmp)
            review = Report("docgen"); docgen.run(tmp, _Check(), review)
            applied = Report("docgen")
            docgen.run(tmp, _Apply(review.info["review_sha256"]), applied)
            self.assertTrue(applied.ok, applied.errors)
            for path in paths:
                self.assertNotIn(b"OLD", _read_bytes(path))

    def test_review_binds_root_and_desired_bytes(self):
        with tempfile.TemporaryDirectory() as first_root, tempfile.TemporaryDirectory() as second_root:
            first_paths = self._protected_batch(first_root)
            self._protected_batch(second_root)
            first = Report("docgen"); docgen.run(first_root, _Check(), first)
            second = Report("docgen"); docgen.run(second_root, _Check(), second)
            self.assertNotEqual(first.info["review_sha256"], second.info["review_sha256"])

            cli = os.path.join(first_root, "System", "Scripts", "aios.py")
            with open(cli, encoding="utf-8") as fh:
                source = fh.read()
            source = source.replace('"pack-check"])', '"pack-check", "review-probe"])', 1)
            with open(cli, "w", encoding="utf-8") as fh:
                fh.write(source)
            before = {path: _read_bytes(path) for path in first_paths}
            stale = Report("docgen")
            docgen.run(first_root, _Apply(first.info["review_sha256"]), stale)
            self.assertFalse(stale.ok)
            self.assertEqual(before, {path: _read_bytes(path) for path in first_paths})

    def test_stale_or_expanded_review_refuses_every_write(self):
        for change in ("preimage", "expanded", "policy"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                paths = list(self._protected_batch(tmp))
                review = Report("docgen"); docgen.run(tmp, _Check(), review)
                if change == "preimage":
                    with open(paths[0], "a", encoding="utf-8") as fh:
                        fh.write("owner edit\n")
                elif change == "expanded":
                    extra = os.path.join(tmp, "EXTRA.md")
                    with open(extra, "w", encoding="utf-8") as fh:
                        fh.write("<!-- docgen:commands -->\nOLD\n<!-- /docgen:commands -->\n")
                    paths.append(extra)
                else:
                    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "a",
                              encoding="utf-8") as fh:
                        fh.write("  - System/Architecture/\n")
                before = {path: _read_bytes(path) for path in paths}
                rep = Report("docgen")
                docgen.run(tmp, _Apply(review.info["review_sha256"]), rep)
                self.assertFalse(rep.ok)
                self.assertEqual(before, {path: _read_bytes(path) for path in paths})

    def test_cli_review_flags_enforce_the_same_exact_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._protected_batch(tmp)
            cli = os.path.join(VAULT, "System", "Scripts", "aios.py")

            def invoke(*argv):
                return subprocess.run(
                    [sys.executable, cli, "docgen", *argv, "--json", "--root", tmp],
                    capture_output=True, text=True,
                )

            checked = invoke("--check")
            self.assertNotEqual(checked.returncode, 0, "stale blocks keep --check red")
            review = json.loads(checked.stdout)["info"]["review_sha256"]
            before = {path: _read_bytes(path) for path in paths}
            refused = invoke()
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(before, {path: _read_bytes(path) for path in paths})
            applied = invoke("--apply", "--confirm", "--review-sha256", review)
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            for path in paths:
                self.assertNotIn(b"OLD", _read_bytes(path))

    def test_policy_change_during_commit_rolls_back_whole_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._protected_batch(tmp)
            review = Report("docgen"); docgen.run(tmp, _Check(), review)
            before = {path: _read_bytes(path) for path in paths}
            manifest = os.path.join(tmp, "SYSTEM-MANIFEST.yaml")
            changed = False

            def race(event, _index, _target):
                nonlocal changed
                if event == "before-output-commit" and _index == 1 and not changed:
                    changed = True
                    with open(manifest, "a", encoding="utf-8") as fh:
                        fh.write("  - System/Architecture/\n")

            with mock.patch.object(sp, "_mutation_boundary", side_effect=race):
                rep = Report("docgen")
                docgen.run(tmp, _Apply(review.info["review_sha256"]), rep)
            self.assertFalse(rep.ok)
            self.assertEqual(before, {path: _read_bytes(path) for path in paths})


class TestMasterCurrent(unittest.TestCase):
    def test_every_block_on_the_master_is_current(self):
        r = Report("docgen"); docgen.run(VAULT, _Check(), r)
        self.assertEqual(r.errors, [], "docgen blocks on the master must be current:\n"
                         + "\n".join(r.errors[:5]))


if __name__ == "__main__":
    unittest.main()
