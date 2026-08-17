"""DEC-101 — the flat-folder rule for `20 Knowledge` and `40 Outputs`.

The rule itself lives in `safe-write` (the folder-decision step); this suite pins
the one line of enforcement: `validate` **warns**, never errors, rolls the finding
up to a single line, honours the user's declaration, and stays silent everywhere
else. The never-an-error half is the load-bearing one — DEC-082: a lived-in vault
never goes red on the user's own content, and the owner's live instance already
carries three Knowledge subfolders that are his to resolve, not ours to force.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "Scripts"))

from cmd import validate            # noqa: E402
from lib.report import Report       # noqa: E402

MANIFEST = """system:
  name: t
  id: t
  system_version: 1.0.0
runtime:
  ai_writes_enabled: true
directories:
  content: ['20 Knowledge', '40 Outputs']
"""

REGISTRY = """id: schema-folder-registry
folders:
  knowledge: {path: "20 Knowledge", purpose: canonical-knowledge}
  outputs:   {path: "40 Outputs",   purpose: deliverables}
"""


def scaffold(tmp, subdirs=(), declared=()):
    os.makedirs(os.path.join(tmp, "System", "Registries"))
    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as fh:
        fh.write(MANIFEST)
    with open(os.path.join(tmp, "System", "Registries", "folder-registry.yaml"), "w") as fh:
        fh.write(REGISTRY)
    for d in ("20 Knowledge", "40 Outputs", "30 Sources", "10 Projects"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    for d in subdirs:
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    for d in declared:
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
        with open(os.path.join(tmp, d, "_ABOUT.md"), "w") as fh:
            fh.write("What this folder is for.\n")


def check(tmp):
    rep = Report("validate")
    validate.check_flat_folders(tmp, rep)
    return rep


class FlatFolderWarning(unittest.TestCase):

    def test_flat_vault_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp)
            rep = check(tmp)
            self.assertEqual(rep.warnings, [])
            self.assertEqual(rep.errors, [])

    def test_fires_in_knowledge_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp, subdirs=["20 Knowledge/Recipes", "40 Outputs/Client A"])
            rep = check(tmp)
            self.assertEqual(len(rep.warnings), 1, "must roll up to ONE line")
            self.assertIn("2 subfolder(s)", rep.warnings[0])
            self.assertIn("20 Knowledge/Recipes", rep.warnings[0])
            self.assertIn("+1 more", rep.warnings[0])

    def test_never_an_error(self):
        """DEC-082 — the whole point. A lived-in vault must not go red."""
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp, subdirs=["20 Knowledge/A", "20 Knowledge/B", "40 Outputs/C"])
            rep = check(tmp)
            self.assertEqual(rep.errors, [])
            self.assertEqual(len(rep.warnings), 1)
            self.assertIn("3 subfolder(s)", rep.warnings[0])

    def test_silent_elsewhere(self):
        """Sources and Projects are legitimately nested — the rule is scoped."""
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp, subdirs=["30 Sources/Attachments", "10 Projects/Some Project"])
            self.assertEqual(check(tmp).warnings, [])

    def test_declared_divergence_is_silent(self):
        """An `_ABOUT.md` in the subfolder is how the user says 'I meant this'."""
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp, declared=["20 Knowledge/Deliberate", "40 Outputs/Also Deliberate"])
            self.assertEqual(check(tmp).warnings, [])

    def test_declared_and_undeclared_mix(self):
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp, subdirs=["20 Knowledge/Sprawl"],
                     declared=["20 Knowledge/Deliberate"])
            rep = check(tmp)
            self.assertEqual(len(rep.warnings), 1)
            self.assertIn("1 subfolder(s)", rep.warnings[0])
            self.assertIn("Sprawl", rep.warnings[0])
            self.assertNotIn("Deliberate", rep.warnings[0])

    def test_local_only_is_a_privacy_fence_not_a_taxonomy(self):
        """DEC-065 — `Local Only/` must never draw a tidiness warning."""
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp, subdirs=["20 Knowledge/Local Only", "40 Outputs/local only"])
            self.assertEqual(check(tmp).warnings, [])

    def test_hidden_dirs_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp, subdirs=["20 Knowledge/.obsidian-cache"])
            self.assertEqual(check(tmp).warnings, [])

    def test_immediate_children_only(self):
        """A tree under a declared folder is the user's business."""
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp, subdirs=["20 Knowledge/Deliberate/Deeper/Deeper Still"],
                     declared=["20 Knowledge/Deliberate"])
            self.assertEqual(check(tmp).warnings, [])

    def test_renamed_folder_resolves_through_the_registry(self):
        """DEC-004 indirection — never a hard-coded path."""
        with tempfile.TemporaryDirectory() as tmp:
            scaffold(tmp)
            with open(os.path.join(tmp, "System", "Registries",
                                   "folder-registry.yaml"), "w") as fh:
                fh.write('id: schema-folder-registry\nfolders:\n'
                         '  knowledge: {path: "Brain"}\n  outputs: {path: "40 Outputs"}\n')
            os.makedirs(os.path.join(tmp, "Brain", "Sprawl"))
            rep = check(tmp)
            self.assertEqual(len(rep.warnings), 1)
            self.assertIn("Brain/Sprawl", rep.warnings[0])

    def test_missing_folder_is_not_an_error(self):
        """A minimal scaffold may not have the folders at all."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "System", "Registries"))
            with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as fh:
                fh.write(MANIFEST)
            with open(os.path.join(tmp, "System", "Registries",
                                   "folder-registry.yaml"), "w") as fh:
                fh.write(REGISTRY)
            rep = check(tmp)
            self.assertEqual(rep.warnings, [])
            self.assertEqual(rep.errors, [])

    def test_product_seed_is_flat(self):
        """The shipped vault must not trip its own rule."""
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        rep = check(root)
        self.assertEqual(rep.warnings, [], "the product seed itself must stay flat")


if __name__ == "__main__":
    unittest.main()
