"""Health riders (determinism-audit finding 4 + SPEC-import-review-queue DoD-3):
per-item Inbox age, generated-tamper evidence, and the import-stub review
finding. Each is a warning that fires on the seeded condition and stays silent
when the condition is absent — health informs, never nags."""
import json, os, sys, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_commands import mini_vault, Args  # noqa: E402
from lib.report import Report               # noqa: E402
from cmd import health as health_mod        # noqa: E402
from cmd.generate import generated_digests, DIGESTS_NAME  # noqa: E402

STUB = """---
id: project-imported-{n}
type: project
created: 2026-01-01
updated: 2026-01-01
summary: "Imported project: Thing{n}. Stage not set — owner to review."
{extra}---
# Thing{n}

Imported; owner to review.
"""

INBOX_NOTE = """---
id: note-inbox-{n}
type: note
created: {created}
updated: {created}
summary: inbox item {n}
---
Waiting for triage.
"""


def run_health(tmp):
    rep = Report("health")
    health_mod.run(tmp, Args(), rep)
    return rep


def _write_text(path, text):
    with open(path, "w") as stream:
        stream.write(text)


class TestImportStubFinding(unittest.TestCase):
    def test_overdue_unreviewed_stub_fires_one_rolled_up_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "10 Projects", "Thing1"))
            _write_text(os.path.join(tmp, "10 Projects", "Thing1", "Thing1.md"),
                        STUB.format(n=1, extra="review_due: 2026-01-15\n"))
            rep = run_health(tmp)
            hits = [w for w in rep.warnings if "[import-review]" in w]
            self.assertEqual(len(hits), 1, rep.warnings)
            self.assertIn("1 imported project", hits[0])
            self.assertIn("2026-01-15", hits[0])

    def test_unstamped_marker_stub_counts_as_never_reviewed(self):
        # the live defect this spec opened with: six pre-feature stubs, no
        # review_due at all — they must not stay invisible forever
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "10 Projects", "Thing2"))
            _write_text(os.path.join(tmp, "10 Projects", "Thing2", "Thing2.md"),
                        STUB.format(n=2, extra=""))
            rep = run_health(tmp)
            self.assertTrue(any("[import-review]" in w for w in rep.warnings), rep.warnings)

    def test_future_due_and_ordinary_projects_stay_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "10 Projects", "Thing3"))
            _write_text(os.path.join(tmp, "10 Projects", "Thing3", "Thing3.md"),
                        STUB.format(n=3, extra="review_due: 2099-01-01\n"))
            # an ordinary stage-less project WITHOUT the marker sentence
            _write_text(os.path.join(tmp, "10 Projects", "Thing3", "other.md"),
                "---\nid: project-plain\ntype: project\ncreated: 2026-01-01\n"
                "updated: 2026-01-01\nsummary: A hand-made project, no stage yet.\n---\nBody.\n")
            rep = run_health(tmp)
            self.assertFalse(any("[import-review]" in w for w in rep.warnings), rep.warnings)


class TestInboxAge(unittest.TestCase):
    def test_old_inbox_item_warns_with_oldest_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            _write_text(os.path.join(tmp, "00 Inbox", "old-drop.md"),
                        INBOX_NOTE.format(n=1, created="2026-01-01"))
            rep = run_health(tmp)
            hits = [w for w in rep.warnings if "[inbox]" in w]
            self.assertEqual(len(hits), 1, rep.warnings)
            self.assertIn("older than 14 days", hits[0])
            self.assertEqual(rep.info.get("inbox_items_over_window"), 1)

    def test_fresh_items_and_underscore_files_stay_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            import datetime
            today = datetime.date.today().isoformat()
            _write_text(os.path.join(tmp, "00 Inbox", "new-drop.md"),
                        INBOX_NOTE.format(n=2, created=today))
            _write_text(os.path.join(tmp, "00 Inbox", "_ABOUT.md"), "about")
            _write_text(os.path.join(tmp, "00 Inbox", "binary-drop.pdf"), "x")  # mtime = now
            rep = run_health(tmp)
            self.assertFalse(any("[inbox]" in w for w in rep.warnings), rep.warnings)


class TestGeneratedTamper(unittest.TestCase):
    def _seed_generated(self, tmp):
        gen = os.path.join(tmp, "System", "Generated")
        os.makedirs(gen, exist_ok=True)
        _write_text(os.path.join(gen, "implementation-status.md"),
            "---\ngenerated: true\ngenerated_at: 2026-07-25T12:00:00\n---\n# Status\n- fact: 1\n")
        with open(os.path.join(gen, DIGESTS_NAME), "w") as stream:
            json.dump({"generated_at": "2026-07-25T12:00:00",
                       "files": generated_digests(tmp)}, stream)
        return gen

    def test_hand_edit_after_generate_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            gen = self._seed_generated(tmp)
            with open(os.path.join(gen, "implementation-status.md"), "a") as f:
                f.write("- HAND EDIT sneaked in\n")
            rep = run_health(tmp)
            hits = [w for w in rep.warnings if "[generated-tamper]" in w]
            self.assertEqual(len(hits), 1, rep.warnings)
            self.assertIn("implementation-status.md", hits[0])

    def test_untouched_generated_state_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            self._seed_generated(tmp)
            rep = run_health(tmp)
            self.assertFalse(any("[generated-tamper]" in w for w in rep.warnings), rep.warnings)

    def test_timestamp_only_difference_is_not_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            gen = self._seed_generated(tmp)
            p = os.path.join(gen, "implementation-status.md")
            with open(p) as stream:
                text = stream.read().replace("generated_at: 2026-07-25T12:00:00",
                                             "generated_at: 2027-01-01T00:00:00")
            _write_text(p, text)
            rep = run_health(tmp)
            self.assertFalse(any("[generated-tamper]" in w for w in rep.warnings), rep.warnings)

    def test_no_digest_record_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            gen = os.path.join(tmp, "System", "Generated")
            os.makedirs(gen, exist_ok=True)
            _write_text(os.path.join(gen, "orphan.md"), "no record exists\n")
            rep = run_health(tmp)
            self.assertFalse(any("[generated-tamper]" in w for w in rep.warnings), rep.warnings)


if __name__ == "__main__":
    unittest.main()
