"""DEC-083: doc gates police the PRODUCT; on an instance they advise.
A customized instance legitimately diverges from the product's docs — the
first live v1.30.1 instance upgrade left 29 residual errors, every one this
class. Master = error, personal-instance = warning, no manifest = strict."""
import os, sys, tempfile, shutil, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from lib.report import Report                    # noqa: E402
from cmd import docpaths, docaudit, doccheck     # noqa: E402


def _vault(root, role):
    os.makedirs(os.path.join(root, "System", "Documentation"), exist_ok=True)
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as f:
        f.write(f"system:\n  instance_role: {role}\n  system_version: 1.0.0\n")


class Args:
    json = False


class TestMasterHelper(unittest.TestCase):
    def test_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp, "generic-master")
            self.assertTrue(doccheck._master(tmp))
            self.assertTrue(docaudit._master(tmp))
            self.assertTrue(docpaths._master(tmp))
            _vault(tmp, "personal-instance")
            self.assertFalse(doccheck._master(tmp))
            self.assertFalse(docaudit._master(tmp))
            self.assertFalse(docpaths._master(tmp))

    def test_no_manifest_stays_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(docpaths._master(tmp))


class TestDocPathsScoped(unittest.TestCase):
    def _run(self, role):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp, role)
            with open(os.path.join(tmp, "System", "Documentation", "probe.md"), "w") as f:
                f.write("---\nid: doc-probe\ntype: system-doc\nsummary: p\n---\n"
                        "See `System/Documentation/DOES-NOT-EXIST.md` for details.\n")
            rep = Report("doc-paths")
            docpaths.run(tmp, Args(), rep)
            return rep

    def test_master_errors(self):
        rep = self._run("generic-master")
        self.assertTrue(any("does not exist" in e for e in rep.errors), (rep.errors, rep.warnings))

    def test_instance_warns(self):
        rep = self._run("personal-instance")
        self.assertFalse(any("does not exist" in e for e in rep.errors), rep.errors)
        self.assertTrue(any("does not exist" in w for w in rep.warnings), rep.warnings)


if __name__ == "__main__":
    unittest.main()
