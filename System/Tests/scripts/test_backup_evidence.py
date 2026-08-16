"""Backup evidence check + backup-clone.sh + onboarding-trio parity
(SPEC-backup-onboarding, DEC-091).

The spec's hard fence, locked here: NO false "covered" is possible.
- local-only content + no marker  -> finding, worded "never"
- fresh marker                    -> clean (no [backup] warning), worded as
                                     evidence of that run only
- stale marker                    -> the staleness line
- malformed marker                -> treated as never (unreadable evidence is
                                     not evidence)
"""
import os, stat, subprocess, sys, tempfile, unittest, datetime

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from lib.report import Report                  # noqa: E402
from cmd import health as health_mod           # noqa: E402
from test_commands import mini_vault, NOTE     # noqa: E402

CLONE_SH = os.path.join(SCRIPTS, "backup-clone.sh")


def _local_only_note(tmp, name="Secret.md", n=90):
    d = os.path.join(tmp, "20 Knowledge", "Local Only")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "w") as stream:
        stream.write(NOTE.format(n=n, extra="", body="s"))


def _marker(tmp, when, extra=""):
    os.makedirs(os.path.join(tmp, "80 User"), exist_ok=True)
    with open(os.path.join(tmp, "80 User", "LAST-BACKUP.txt"), "w") as stream:
        stream.write("last_backup: %s\n%s" % (when, extra))


def _iso(days_ago=0):
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestBackupEvidence(unittest.TestCase):
    def test_local_only_and_no_marker_is_a_never_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp); _local_only_note(tmp)
            count, last, age, window, problems = health_mod.backup_evidence(tmp)
            self.assertEqual(count, 1)
            self.assertIsNone(last)
            self.assertEqual(problems, [])

    def test_frontmatter_local_only_counts_without_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            with open(os.path.join(tmp, "20 Knowledge", "M.md"), "w") as stream:
                stream.write(NOTE.format(n=91, extra="ai_use: local-only\n", body="m"))
            count, _, _, _, _ = health_mod.backup_evidence(tmp)
            self.assertEqual(count, 1)

    def test_no_local_only_content_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            rep = Report("health"); health_mod.run(tmp, None, rep)
            self.assertFalse([w for w in rep.warnings if "[backup]" in w])

    def test_never_warning_wording_in_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp); _local_only_note(tmp)
            rep = Report("health"); health_mod.run(tmp, None, rep)
            hits = [w for w in rep.warnings if "[backup]" in w]
            self.assertEqual(len(hits), 1)
            self.assertIn("never", hits[0])
            self.assertIn("Backup and Recovery Options", hits[0])
            self.assertEqual(rep.info.get("backup_evidence"), "never")
            self.assertFalse([e for e in rep.errors if "[backup]" in e],
                             "a finding, not an error — backup must never redden health")

    def test_fresh_marker_is_clean_and_worded_as_that_run_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp); _local_only_note(tmp); _marker(tmp, _iso(1))
            rep = Report("health"); health_mod.run(tmp, None, rep)
            self.assertFalse([w for w in rep.warnings if "[backup]" in w])
            self.assertIn("evidence of that run only", rep.info.get("backup_evidence", ""))

    def test_stale_marker_gets_the_staleness_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp); _local_only_note(tmp); _marker(tmp, _iso(45))
            rep = Report("health"); health_mod.run(tmp, None, rep)
            hits = [w for w in rep.warnings if "[backup]" in w]
            self.assertEqual(len(hits), 1)
            self.assertIn("days ago", hits[0])
            self.assertIn("stale", rep.info.get("backup_evidence", ""))

    def test_window_days_is_tunable_in_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp); _local_only_note(tmp)
            _marker(tmp, _iso(45), extra="window_days: 60\n")
            rep = Report("health"); health_mod.run(tmp, None, rep)
            self.assertFalse([w for w in rep.warnings if "[backup]" in w])

    def test_malformed_marker_is_treated_as_never(self):
        """Unreadable evidence is not evidence — a garbage marker can never
        yield a clean 'covered' state."""
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp); _local_only_note(tmp)
            _marker(tmp, "sometime last week, probably")
            rep = Report("health"); health_mod.run(tmp, None, rep)
            hits = [w for w in rep.warnings if "[backup]" in w]
            self.assertTrue(any("never" in w for w in hits))
            self.assertTrue(any("unreadable" in w for w in hits))
            self.assertEqual(rep.info.get("backup_evidence"), "never")


@unittest.skipUnless(os.name == "posix", "backup-clone.sh is a POSIX helper")
class TestBackupCloneScript(unittest.TestCase):
    def _run(self, *argv):
        return subprocess.run(["bash", CLONE_SH, *argv], capture_output=True, text=True)

    @staticmethod
    def _install_script(src):
        sh = os.path.join(src, "System", "Scripts", "backup-clone.sh")
        os.makedirs(os.path.dirname(sh), exist_ok=True)
        with open(CLONE_SH, encoding="utf-8") as source:
            payload = source.read()
        with open(sh, "w", encoding="utf-8") as target:
            target.write(payload)
        os.chmod(sh, os.stat(sh).st_mode | stat.S_IEXEC)
        return sh

    @staticmethod
    def _inventory(root):
        items = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort(); filenames.sort()
            rel_dir = os.path.relpath(dirpath, root)
            if rel_dir != ".":
                items[rel_dir.replace(os.sep, "/") + "/"] = stat.S_IMODE(os.stat(dirpath).st_mode)
            for name in filenames:
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                with open(path, "rb") as stream:
                    items[rel] = (stat.S_IMODE(os.stat(path).st_mode), stream.read())
        return items

    def test_clone_copies_and_writes_marker_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "vault"); os.makedirs(src)
            mini_vault(src); _local_only_note(src)
            sh = self._install_script(src)
            dest = os.path.join(tmp, "drive", "clone")
            r = subprocess.run(["bash", sh, dest], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.exists(os.path.join(dest, "SYSTEM-MANIFEST.yaml")))
            self.assertTrue(os.path.exists(
                os.path.join(dest, "20 Knowledge", "Local Only", "Secret.md")))
            for root_dir in (src, dest):
                marker = os.path.join(root_dir, "80 User", "LAST-BACKUP.txt")
                self.assertTrue(os.path.exists(marker), marker)
                with open(marker, encoding="utf-8") as stream:
                    self.assertIn("last_backup:", stream.read())
            # and health on the source is now clean
            rep = Report("health"); health_mod.run(src, None, rep)
            self.assertFalse([w for w in rep.warnings if "[backup]" in w])

    def test_refuses_nonempty_unrelated_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "vault"); os.makedirs(src); mini_vault(src)
            sh = self._install_script(src)
            dest = os.path.join(tmp, "documents"); os.makedirs(dest)
            with open(os.path.join(dest, "unrelated.txt"), "w") as stream:
                stream.write("x")
            r = subprocess.run(["bash", sh, dest], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("refusing", r.stderr)
            self.assertFalse(os.path.exists(os.path.join(src, "80 User", "LAST-BACKUP.txt")))

    def test_refuses_destination_inside_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "vault"); os.makedirs(src); mini_vault(src)
            sh = self._install_script(src)
            r = subprocess.run(["bash", sh, os.path.join(src, "backup")],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("inside the vault", r.stderr)

    def test_repeat_clone_deletes_stale_files_and_restores_exact_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "vault"); os.makedirs(src); mini_vault(src)
            sh = self._install_script(src)
            stale = os.path.join(src, "20 Knowledge", "stale.md")
            os.makedirs(os.path.dirname(stale), exist_ok=True)
            with open(stale, "w") as stream:
                stream.write("remove before second backup\n")
            dest = os.path.join(tmp, "drive", "clone")
            first = subprocess.run(["bash", sh, dest], capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            os.unlink(stale)
            with open(os.path.join(src, "20 Knowledge", "current.md"), "w") as stream:
                stream.write("current bytes\n")
            second = subprocess.run(["bash", sh, dest], capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertFalse(os.path.exists(os.path.join(dest, "20 Knowledge", "stale.md")))
            self.assertEqual(self._inventory(src), self._inventory(dest))

            restored = os.path.join(tmp, "restored")
            subprocess.run(["cp", "-R", dest, restored], check=True)
            self.assertEqual(self._inventory(src), self._inventory(restored))


class TestOnboardingTrioParity(unittest.TestCase):
    """DEC-062: the Onboarding Specification, Human Onboarding Guide, and AI
    Onboarding Procedure move together. Scripted proof that they agree: the
    derived pair is stamped against the spec's CURRENT version, and all three
    carry the same eight stages."""
    SPEC = os.path.join(VAULT, "System", "Onboarding", "Onboarding Specification.md")
    GUIDE = os.path.join(VAULT, "System", "Onboarding", "Human Onboarding Guide.md")
    PROC = os.path.join(VAULT, "System", "Onboarding", "AI Onboarding Procedure.md")

    def _fm_version(self, path):
        import re
        with open(path, encoding="utf-8") as stream:
            text = stream.read()
        m = re.search(r"^version:\s*([\d.]+)\s*$", text, re.M)
        return m.group(1), text

    def test_derived_docs_are_stamped_against_current_spec(self):
        spec_ver, _ = self._fm_version(self.SPEC)
        for path in (self.GUIDE, self.PROC):
            _, text = self._fm_version(path)
            self.assertIn('doc-onboarding-specification:%s' % spec_ver, text,
                          "%s is not re-derived against spec %s" % (os.path.basename(path), spec_ver))

    def test_all_three_carry_the_same_eight_stages(self):
        _, spec = self._fm_version(self.SPEC)
        _, guide = self._fm_version(self.GUIDE)
        _, proc = self._fm_version(self.PROC)
        for n in range(1, 9):
            self.assertIn("### Stage %d" % n, spec, "spec missing stage %d" % n)
            self.assertIn("**%d " % n, guide.replace("·", " "), "guide missing stage %d" % n)
            self.assertIn("- **%d**" % n, proc, "procedure missing stage %d" % n)
        self.assertNotIn("### Stage 9", spec)


if __name__ == "__main__":
    unittest.main()
