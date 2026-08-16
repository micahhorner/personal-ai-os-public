"""aios resolve — the canonical-record resolver (determinism audit finding 2+5):
match ladder, supersession chains, all-states dedupe visibility, privacy
fail-closed, and the --mint id/filename twin. Run:
    python3 -m unittest System.Tests.scripts.test_resolve
"""
import os, sys, tempfile, unittest
from types import SimpleNamespace

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from lib.report import Report            # noqa: E402
from cmd import resolve as res_mod       # noqa: E402


def _args(**kw):
    base = dict(query=None, mint=False, type=None, json=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _vault(root, hosted=False):
    os.makedirs(os.path.join(root, "20 Knowledge"), exist_ok=True)
    with open(os.path.join(root, "profile.yaml"), "w") as f:
        f.write(f"hosted: {str(hosted).lower()}\n"
                "may_process_private: false\n"
                "allowed_privacy_classifications: [public, internal, private]\n")
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as f:
        f.write("runtime:\n  ai_writes_enabled: true\n  active_profile: profile.yaml\n")


def _note(root, fname, nid, status="active", body="body", extra=""):
    p = os.path.join(root, "20 Knowledge", fname)
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"---\nid: {nid}\ntype: note\nstatus: {status}\ncreated: 2026-07-01\n"
                f"updated: 2026-07-01\nsummary: s-{nid}\n{extra}---\n\n{body}\n")


class TestLadder(unittest.TestCase):
    def test_exact_id_beats_body_phrase(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _note(tmp, "A.md", "note-alpha", body="mentions note-beta in passing")
            _note(tmp, "B.md", "note-beta")
            rep = Report("resolve"); res_mod.run(tmp, _args(query="note-beta"), rep)
            self.assertEqual(rep.info["matched_on"], "exact-id")
            self.assertEqual(rep.info["canonical"], "note-beta")

    def test_alias_and_title_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _note(tmp, "Zettelkasten Method.md", "note-zk",
                  extra="aliases: [slip box]\n")
            rep = Report("resolve"); res_mod.run(tmp, _args(query="Slip Box"), rep)
            self.assertEqual(rep.info["matched_on"], "exact-alias")
            rep2 = Report("resolve"); res_mod.run(tmp, _args(query="zettelkasten method"), rep2)
            self.assertEqual(rep2.info["matched_on"], "exact-title")

    def test_no_match_says_safe_to_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _note(tmp, "A.md", "note-alpha")
            rep = Report("resolve"); res_mod.run(tmp, _args(query="quantum basket weaving"), rep)
            self.assertIn("safe to create", rep.info["resolution"])
            self.assertFalse(rep.warnings)


class TestSupersessionAndStates(unittest.TestCase):
    def test_chain_followed_to_terminal_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _note(tmp, "Old.md", "note-old", status="superseded",
                  extra="superseded_by: note-mid\n")
            _note(tmp, "Mid.md", "note-mid", status="superseded",
                  extra="superseded_by: note-new\n")
            _note(tmp, "New.md", "note-new")
            rep = Report("resolve"); res_mod.run(tmp, _args(query="note-old"), rep)
            self.assertEqual(rep.info["canonical"], "note-new")

    def test_supersession_cycle_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _note(tmp, "A.md", "note-a", extra="superseded_by: note-b\n")
            _note(tmp, "B.md", "note-b", extra="superseded_by: note-a\n")
            rep = Report("resolve"); res_mod.run(tmp, _args(query="note-a"), rep)
            self.assertTrue(any("cycle" in e for e in rep.errors))

    def test_drafts_are_dedupe_targets(self):
        """Unlike search, resolve sees drafts — a duplicate of a draft is a duplicate."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _note(tmp, "Draft Idea.md", "note-draft-idea", status="draft")
            rep = Report("resolve"); res_mod.run(tmp, _args(query="draft idea"), rep)
            self.assertEqual(rep.info["matched_on"], "exact-title")
            self.assertTrue(rep.warnings)   # "may already serve this purpose"

    def test_privacy_outranks_dedupe(self):
        """A hosted profile may not see local-only records even to dedupe."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp, hosted=True)
            _note(tmp, "Secret Topic.md", "note-secret", extra="ai_use: local-only\n")
            rep = Report("resolve"); res_mod.run(tmp, _args(query="secret topic"), rep)
            self.assertIn("safe to create", rep.info["resolution"])


class TestMint(unittest.TestCase):
    def test_mint_slug_and_sanitized_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            rep = Report("resolve")
            res_mod.run(tmp, _args(query='What is "Truth"? ', mint=True, type="note"), rep)
            self.assertEqual(rep.info["mint_id"], "note-what-is-truth")
            self.assertEqual(rep.info["mint_filename"], "What is Truth?.md".replace("?", "") )
            self.assertIn("mint_sanitized", rep.info)

    def test_mint_id_collision_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _note(tmp, "Existing.md", "note-truth")
            rep = Report("resolve")
            res_mod.run(tmp, _args(query="Truth", mint=True, type="note"), rep)
            self.assertTrue(any("already exists" in e for e in rep.errors))

    def test_mint_requires_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            rep = Report("resolve")
            res_mod.run(tmp, _args(query="Anything", mint=True), rep)
            self.assertTrue(any("--type" in e for e in rep.errors))


if __name__ == "__main__":
    unittest.main()
