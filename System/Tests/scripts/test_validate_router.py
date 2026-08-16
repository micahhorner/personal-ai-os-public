"""Task Router load-path resolution (the dangling-row class).

Found live 2026-07-15: an instance's `onboarding: run-or-resume` row loaded
`System/Capabilities/method-kit.md`, that file was absent from the vault, and
`aios validate` passed — the router's own header promises "every load entry is
a real vault path" and nothing enforced it. These tests pin the enforcement.
"""
import os, shutil, sys, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from lib.report import Report          # noqa: E402
from cmd import validate as v_mod      # noqa: E402


class Args:
    json = False


def scaffold(tmp):
    """Minimal vault: schemas (copied so class checks stay quiet) + a Runtime dir."""
    for d in ("System/Schemas", "System/Runtime", "System/Capabilities", "80 User"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    for f in os.listdir(os.path.join(VAULT, "System", "Schemas")):
        shutil.copy(os.path.join(VAULT, "System", "Schemas", f),
                    os.path.join(tmp, "System", "Schemas"))
    return tmp


def write_router(tmp, body):
    with open(os.path.join(tmp, "System", "Runtime", "Task Router.yaml"), "w") as f:
        f.write(body)


class TestRouterPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = scaffold(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self):
        return v_mod.run(self.tmp, Args(), Report("validate"))

    def test_dangling_load_path_is_an_error(self):
        write_router(self.tmp,
                     "routes:\n  work:\n    do-thing: {load: [System/Capabilities/missing.md]}\n")
        rep = self._run()
        self.assertTrue(any("does not resolve" in e and "missing.md" in e for e in rep.errors),
                        f"expected dangling-path error, got: {rep.errors}")

    def test_resolving_load_path_passes(self):
        with open(os.path.join(self.tmp, "System", "Capabilities", "real.md"), "w") as stream:
            stream.write("x\n")
        write_router(self.tmp,
                     "routes:\n  work:\n    do-thing: {load: [System/Capabilities/real.md]}\n")
        rep = self._run()
        self.assertFalse(any("does not resolve" in e for e in rep.errors))

    def test_absent_load_if_present_user_file_is_fine(self):
        write_router(self.tmp,
                     "routes:\n  work:\n    do-thing: {load: [], load_if_present: [80 User/voice.md]}\n")
        rep = self._run()
        self.assertFalse(any("voice.md" in e for e in rep.errors))
        self.assertFalse(any("voice.md" in w for w in rep.warnings))

    def test_system_path_under_load_if_present_warns(self):
        write_router(self.tmp,
                     "routes:\n  work:\n    do-thing: {load: [], "
                     "load_if_present: [System/Capabilities/thing.md]}\n")
        rep = self._run()
        self.assertTrue(any("load_if_present" in w for w in rep.warnings),
                        f"expected System-in-load_if_present warning, got: {rep.warnings}")

    def test_nested_block_form_is_walked(self):
        # the developer-mode row uses the multi-line block form, not the inline map
        write_router(self.tmp,
                     "routes:\n  dev:\n    change-system:\n      load:\n"
                     "        - System/Capabilities/gone.md\n      note: full stack\n")
        rep = self._run()
        self.assertTrue(any("gone.md" in e for e in rep.errors))

    def test_no_router_is_quiet(self):
        rep = self._run()   # scaffold has a Runtime dir but no router file
        self.assertFalse(any("Task Router" in e for e in rep.errors))


if __name__ == "__main__":
    unittest.main()
