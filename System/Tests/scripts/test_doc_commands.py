"""Regression tests for `aios doc-commands` — the command-documentation gate.
Proves both directions: an undocumented command fails the gate; a fully
documented command surface passes. The command list is read from aios.py
source, so the test also proves the list isn't a hand-kept copy."""
import os, sys, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from lib.report import Report                       # noqa: E402
from cmd import doccommands as dc                    # noqa: E402


class Args:
    json = False


def make_root(tmp, choices, docs_text):
    """A minimal vault: an aios.py carrying `choices`, and one doc file."""
    scr = os.path.join(tmp, "System", "Scripts")
    os.makedirs(scr)
    # Only the argparse choices line matters; AST-parsed, never executed.
    with open(os.path.join(scr, "aios.py"), "w") as stream:
        stream.write('p.add_argument("command", choices=%r)\n' % (list(choices),))
    docdir = os.path.join(tmp, "System", "Documentation")
    os.makedirs(docdir)
    with open(os.path.join(docdir, "guide.md"), "w") as stream:
        stream.write(docs_text)
    return tmp


class TestDocCommands(unittest.TestCase):
    def test_reads_command_list_from_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_root(tmp, ["alpha", "beta"], "`alpha` and `beta`.")
            self.assertEqual(set(dc.cli_commands(tmp)), {"alpha", "beta"})

    def test_flags_an_undocumented_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_root(tmp, ["health", "frobnicate"], "Run `aios health` regularly.")
            rep = Report("doc-commands"); dc.run(tmp, Args(), rep)
            self.assertFalse(rep.ok)
            self.assertTrue(any("frobnicate" in e for e in rep.errors))
            self.assertFalse(any("`aios health`" in e for e in rep.errors))
            self.assertEqual(rep.info["commands_undocumented"], 1)

    def test_passes_when_every_command_documented(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_root(tmp, ["health", "validate"],
                      "Use `aios health` for the full picture and `aios validate` to check.")
            rep = Report("doc-commands"); dc.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(rep.info["commands_undocumented"], 0)

    def test_short_name_not_matched_inside_prose(self):
        # "read" must not count as documented just because the word appears in text
        with tempfile.TemporaryDirectory() as tmp:
            make_root(tmp, ["read"], "Please read the manual carefully before you begin.")
            rep = Report("doc-commands"); dc.run(tmp, Args(), rep)
            self.assertFalse(rep.ok)

    def test_backticked_command_counts_as_documented(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_root(tmp, ["read"], "The `read` command fetches a note by id.")
            rep = Report("doc-commands"); dc.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)

    def test_skips_gracefully_when_no_cli_present(self):
        # A minimal vault with no System/Scripts/aios.py has no CLI to check:
        # the gate skips without error or crash (so it's safe inside `health`).
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "System", "Documentation"))
            rep = Report("doc-commands"); dc.run(tmp, Args(), rep)
            self.assertTrue(rep.ok)
            self.assertIn("skipped", str(rep.info.get("commands_checked", "")))


if __name__ == "__main__":
    unittest.main()
