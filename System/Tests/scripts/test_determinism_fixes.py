"""Determinism-audit fix regressions (AUDIT-determinism findings I-2 and 3):
vocab rides the health composite, and `ripple --refs` computes the rename-time
operational reference sweep Change Control's medium tier orders. Run:
    python3 -m unittest System.Tests.scripts.test_determinism_fixes
"""
import os, sys, tempfile, shutil, unittest
from types import SimpleNamespace

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from scaffold import product_manifest   # noqa: E402
from lib.report import Report            # noqa: E402
from cmd import health as health_mod     # noqa: E402
from cmd import ripple as ripple_cmd     # noqa: E402


def _args(**kw):
    base = dict(ack=None, from_id=None, effect=None, ack_all=False, baseline=None,
                baseline_all=False, refs=None, json=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _write_text(path, text):
    with open(path, "w") as stream:
        stream.write(text)


def _mini_vault(tmp):
    for d in ("System/Schemas", "System/Registries", "System/Journal",
              "System/Scripts", "System/Capabilities", "20 Knowledge", "00 Inbox"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    _write_text(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), product_manifest())
    for f in os.listdir(os.path.join(VAULT, "System", "Schemas")):
        shutil.copy(os.path.join(VAULT, "System", "Schemas", f),
                    os.path.join(tmp, "System", "Schemas"))
    _write_text(os.path.join(tmp, "System", "Journal", "change-journal.md"), "# J\n")
    return tmp


class TestVocabInHealth(unittest.TestCase):
    def test_health_composite_includes_vocab(self):
        """I-2: the banned-term guard runs whenever health does; an instance
        with no vocab-guard.yaml no-ops without reddening the report."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = _mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(outer, "v"), exist_ok=True)
            rep = Report("health")
            health_mod.run(tmp, _args(), rep)
            self.assertIn("vocab", rep.info)          # composite ran it
            self.assertFalse([e for e in rep.errors if e.startswith("[vocab]")])

    def test_health_surfaces_vocab_violations_as_warnings_not_errors(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = _mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(tmp, "80 User"), exist_ok=True)
            _write_text(os.path.join(tmp, "80 User", "vocab-guard.yaml"),
                "extra_terms: [datalake]\nscan_dirs: ['20 Knowledge']\n")
            _write_text(os.path.join(tmp, "20 Knowledge", "n.md"),
                "---\nid: note-v1\ntype: note\ncreated: 2026-07-01\nupdated: 2026-07-01\n"
                "summary: t\n---\nour datalake strategy\n")
            rep = Report("health")
            health_mod.run(tmp, _args(), rep)
            self.assertFalse([e for e in rep.errors if e.startswith("[vocab]")])
            self.assertIn("1 warnings", str(rep.info.get("vocab", "")))


class TestRippleRefs(unittest.TestCase):
    def test_refs_finds_operational_references(self):
        """Finding 3's uncovered slice: an old filename still referenced from a
        script and a capability is reported with file:line, as a warning."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = _mini_vault(os.path.join(outer, "v"))
            _write_text(os.path.join(tmp, "System", "Scripts", "helper.py"),
                "TARGET = 'Old Note Name.md'\n")
            _write_text(os.path.join(tmp, "System", "Capabilities", "cap.md"),
                "read `Old Note Name.md` first\n")
            rep = Report("ripple")
            ripple_cmd.run(tmp, _args(refs="Old Note Name.md"), rep)
            self.assertEqual(rep.info["refs_hits"], 2)
            self.assertTrue(any("helper.py:1" in h for h in rep.info["refs"]))
            self.assertTrue(any("cap.md:1" in h for h in rep.info["refs"]))
            self.assertTrue(rep.warnings)

    def test_refs_clean_when_nothing_references_the_name(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = _mini_vault(os.path.join(outer, "v"))
            rep = Report("ripple")
            ripple_cmd.run(tmp, _args(refs="never-existed.md"), rep)
            self.assertEqual(rep.info["refs_hits"], 0)
            self.assertFalse(rep.warnings)
            self.assertFalse(rep.errors)

    def test_refs_needs_no_freshness_registry(self):
        """--refs is read-only and must work on a vault without freshness.yaml
        (ripple's other modes require the registry)."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = _mini_vault(os.path.join(outer, "v"))
            rep = Report("ripple")
            ripple_cmd.run(tmp, _args(refs="x"), rep)
            self.assertNotIn("freshness", rep.info)


if __name__ == "__main__":
    unittest.main()
