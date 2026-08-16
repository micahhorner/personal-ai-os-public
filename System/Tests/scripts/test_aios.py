"""Unit tests for the aios deterministic utility layer (stdlib unittest + PyYAML only).
Run: python3 -m unittest discover -s System/Tests/scripts"""
from test_io import read_file, write_file
import os, sys, shutil, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from scaffold import product_manifest   # noqa: E402
from lib.frontmatter import parse_file, body_links      # noqa: E402
from lib.vaultpaths import find_root, ai_writes_enabled # noqa: E402
from lib.report import Report                           # noqa: E402
from cmd import validate as v_mod, generate as g_mod    # noqa: E402


class Args:  # minimal argparse stand-in
    json = False; message = None; rollback = None; confirm = False


def mini_vault(tmp):
    """A tiny valid vault for isolated tests."""
    os.makedirs(os.path.join(tmp, "System", "Schemas"))
    os.makedirs(os.path.join(tmp, "System", "Registries"))
    os.makedirs(os.path.join(tmp, "20 Knowledge"))
    write_file(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), product_manifest(), mode="w")
    for f in os.listdir(os.path.join(VAULT, "System", "Schemas")):
        shutil.copy(os.path.join(VAULT, "System", "Schemas", f), os.path.join(tmp, "System", "Schemas"))
    return tmp


GOOD = """---
id: note-test-example
type: note
subtype: concept
status: active
created: 2026-07-10
updated: 2026-07-10
summary: A valid test note.
---

# Test example
Body with a `[[code-span link that must be ignored]]`.
"""


class TestFrontmatter(unittest.TestCase):
    def test_parse_and_code_span_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "n.md"); write_file(p, GOOD, mode="w")
            n = parse_file(p, tmp)
            self.assertIsNone(n.error)
            self.assertEqual(n.meta["id"], "note-test-example")
            wl, ml = body_links(n.body)
            self.assertEqual(wl, [])  # code spans stripped

    def test_bad_yaml_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "n.md"); write_file(p, "---\n{{bad}}: x\n---\nbody", mode="w")
            self.assertIsNotNone(parse_file(p, tmp).error)


class TestComponentSelfIdentification(unittest.TestCase):
    """F2 (PMM Engine migration): a file declaring component_type is a
    component wherever it lives; the contract is enforced there too."""
    CONTRACT = ("---\nid: capability-anywhere\nname: anywhere\ncomponent_type: capability\n"
                "status: draft\nversion: 0.1.0\n{summary}---\nbody\n")

    def test_component_outside_standard_dirs_is_contract_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            p = os.path.join(tmp, "20 Knowledge", "tool.md")
            write_file(p, self.CONTRACT.format(summary=""), mode="w")
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            self.assertIn("missing contract field 'summary'", " ".join(rep.errors))
            write_file(p, self.CONTRACT.format(summary="summary: a tool\n"), mode="w")
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)


class TestValidate(unittest.TestCase):
    def test_good_note_passes_and_violations_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            write_file(os.path.join(tmp, "20 Knowledge", "Good.md"), GOOD, mode="w")
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)
            # unknown key + bad vocab + wrong prefix
            write_file(os.path.join(tmp, "20 Knowledge", "Bad.md"), "---\nid: wrong-prefix\ntype: note\ncreated: 2026-07-10\nupdated: 2026-07-10\n"
                "summary: x\nstatus: bogus-value\nmade_up_key: 1\n---\nbody", mode="w")
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            joined = " ".join(rep.errors)
            for frag in ("does not match type prefix", "not in vocabulary", "unknown key"):
                self.assertIn(frag, joined)

    def test_duplicate_id_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            for name in ("A.md", "B.md"):
                write_file(os.path.join(tmp, "20 Knowledge", name), GOOD, mode="w")
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            self.assertIn("duplicate id", " ".join(rep.errors))

    def test_secret_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            write_file(os.path.join(tmp, "20 Knowledge", "S.md"), GOOD.replace("Body", "api_key = 'abcdefghijklmnop1234'"), mode="w")
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            self.assertIn("secret", " ".join(rep.errors))


class TestGenerate(unittest.TestCase):
    def test_kill_switch_refuses_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            mp = os.path.join(tmp, "SYSTEM-MANIFEST.yaml")
            write_file(mp, "", mode="a")  # ensure exists
            s = read_file(mp).replace("ai_writes_enabled: true", "ai_writes_enabled: false")
            write_file(mp, s, mode="w")
            rep = Report("generate"); g_mod.run(tmp, Args(), rep)
            self.assertFalse(rep.ok)
            self.assertIn("kill switch", " ".join(rep.errors))

    def test_rebuild_is_complete_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            write_file(os.path.join(tmp, "20 Knowledge", "Good.md"), GOOD, mode="w")
            rep = Report("generate"); g_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)
            gen = os.path.join(tmp, "System", "Generated")
            first = sorted(os.listdir(gen))
            rep = Report("generate"); g_mod.run(tmp, Args(), rep)
            self.assertEqual(first, sorted(os.listdir(gen)))
            self.assertIn("index-note.md", first)
            self.assertIn("system-reference.md", first)

    def test_system_reference_generated_from_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "System", "Operations"))
            shutil.copy(os.path.join(VAULT, "System", "Operations", "operations.yaml"),
                        os.path.join(tmp, "System", "Operations"))
            os.makedirs(os.path.join(tmp, "System", "Workflows"))
            write_file(os.path.join(tmp, "System", "Workflows", "demo.md"), "---\nid: workflow-demo\ntype: workflow\ncomponent_type: workflow\n"
                "status: active\nversion: 1.0.0\ncreated: 2026-07-10\nupdated: 2026-07-10\n"
                "summary: demo\n---\nbody\n", mode="w")
            rep = Report("generate"); g_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)
            ref = os.path.join(tmp, "System", "Generated", "system-reference.md")
            self.assertTrue(os.path.exists(ref))
            text = read_file(ref, encoding="utf-8")
            self.assertIn("do_not_edit: true", text)   # carries the generated marker
            self.assertIn("vault.search", text)         # pulled from operations.yaml
            self.assertIn("workflow-demo", text)        # the component just added → reflects source
            self.assertIn("classification", text)       # pulled from vocabularies.yaml


class TestRootDiscovery(unittest.TestCase):
    def test_find_root_from_scripts_dir(self):
        self.assertEqual(find_root(os.path.join(VAULT, "System", "Scripts")), VAULT)

    def test_kill_switch_read(self):
        self.assertTrue(ai_writes_enabled(VAULT))


if __name__ == "__main__":
    unittest.main()
