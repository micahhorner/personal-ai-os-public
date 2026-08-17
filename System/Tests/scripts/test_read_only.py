"""Seeded-failure tests for three safety properties the product DOCUMENTS but,
until v1.49.0, never asserted:

  1. `certify`'s PII invariant is MASTER-ONLY. It must fire on a generic-master
     fixture and must NOT fire on a personal-instance one. (It fired everywhere,
     so `aios certify` could never pass on a real personal vault — 34 errors on a
     live instance, every one of them legitimate content.)

  2. `health` and `certify` are READ-ONLY. Asserted by hashing the whole tree
     before and after and requiring byte-identity — not by reading a docstring.
     `certify` failed this: its idempotency probe runs `aios generate` twice, and
     `generate` baselines notes into the TRACKED `System/Logs/freshness-ledger.json`,
     which the probe restored for `System/Generated` only. Every "read-only audit"
     claim that rested on certify was false by exactly that much.

  3. `checkpoint` never silently commits work the caller did not declare. It may
     still commit everything — that guarantee is deliberate (you can always save
     state) — but the commit message must enumerate what it contains, `--paths`
     must scope it, and `--strict` must refuse and explain.

Each test plants the failure it is meant to catch. A check that can only ever say
PASS proves nothing.
"""
import os, sys, json, shutil, hashlib, subprocess, tempfile, unittest
from unittest import mock

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from lib.report import Report          # noqa: E402
from cmd import certify as certify_mod  # noqa: E402
from cmd import health as health_mod    # noqa: E402
from cmd import checkpoint as ck_mod    # noqa: E402
from scaffold import product_manifest   # noqa: E402


class Args:
    json = False; message = None; rollback = None; confirm = False
    clean = False; force_zip = False; zip_only = False
    paths = None; strict = False


def tree_hash(root, skip=(".git",)):
    """A single digest over every file's path AND content. The assertion that a
    command is read-only has to be made against the tree, not against a comment."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            h.update(rel.encode("utf-8") + b"\0")
            try:
                with open(p, "rb") as fh:
                    h.update(fh.read())
            except OSError:
                h.update(b"<unreadable>")
            h.update(b"\0")
    return h.hexdigest()


def tree_files(root, skip=(".git",)):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                with open(p, "rb") as stream:
                    out[os.path.relpath(p, root)] = stream.read()
            except OSError:
                pass
    return out


def _min_vault(root, role):
    """A vault whose governance checks pass, at an EXPLICIT instance_role."""
    os.makedirs(os.path.join(root, "System", "Scripts"), exist_ok=True)
    os.makedirs(os.path.join(root, "System", "Agents"), exist_ok=True)
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as f:
        f.write(f"system:\n  instance_role: {role}\n"
                "runtime:\n  ai_writes_enabled: true\n"
                "protected_objects:\n  - SYSTEM-MANIFEST.yaml\n  - System/Agents/\n")
    with open(os.path.join(root, "System", "Scripts", "aios.py"), "w") as f:
        f.write("WRITE_COMMANDS = set()\nai_writes_enabled\n")


# Synthetic and clearly fake. Never a real address.
PLANTED = "planted.colleague@acme-corp-fake.com"


class TestPiiIsMasterOnly(unittest.TestCase):
    """(1) the invariant the comment always claimed, now actually scoped."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_pii(self):
        with open(os.path.join(self.tmp, "colleague.md"), "w") as f:
            f.write(f"Her work address is {PLANTED} — the kind of record a "
                    f"personal vault exists to hold.\n")

    def test_master_still_fails_on_pii(self):
        """The seeded failure. If this ever passes, the scoping went too far and
        the product master can ship personal data."""
        _min_vault(self.tmp, "generic-master")
        self._seed_pii()
        rep = certify_mod._governance(self.tmp)
        self.assertFalse(rep.ok, "generic-master must still reject PII")
        self.assertTrue(any("PII" in e and PLANTED in e for e in rep.errors), rep.errors)

    def test_personal_instance_passes_with_pii(self):
        """The defect. Identical content, different role -> must certify clean."""
        _min_vault(self.tmp, "personal-instance")
        self._seed_pii()
        rep = certify_mod._governance(self.tmp)
        self.assertTrue(rep.ok, f"personal instance must not fail on its own PII: {rep.errors}")
        self.assertIn("pii_scan", rep.info)

    def test_absent_role_stays_strict(self):
        """No manifest role at all = test scaffold or product context. Fail closed."""
        os.makedirs(os.path.join(self.tmp, "System", "Agents"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp, "System", "Scripts"), exist_ok=True)
        with open(os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml"), "w") as f:
            f.write("runtime:\n  ai_writes_enabled: true\n"
                    "protected_objects:\n  - SYSTEM-MANIFEST.yaml\n  - System/Agents/\n")
        with open(os.path.join(self.tmp, "System", "Scripts", "aios.py"), "w") as f:
            f.write("WRITE_COMMANDS = set()\nai_writes_enabled\n")
        self._seed_pii()
        rep = certify_mod._governance(self.tmp)
        self.assertFalse(rep.ok, "an unstated role must stay strict")

    def test_scaffold_manifest_states_its_role(self):
        """The regression that broke the doc-gate severity tests: a fixture must
        declare generic-master, not inherit whatever vault the suite runs from."""
        self.assertIn("instance_role: generic-master", product_manifest())
        self.assertIn("instance_role: personal-instance",
                      product_manifest(role="personal-instance"))


class TestCommandsAreReadOnly(unittest.TestCase):
    """(2) tree-diff assertions. The whole point is that they are not docstrings."""

    def setUp(self):
        self.outer = tempfile.mkdtemp()
        self.root = os.path.join(self.outer, "v")
        # a real product tree, re-roled as a personal instance: the ONLY
        # configuration in which freshness activates and the ledger is written
        archive_path = os.path.join(self.outer, "t.tar")
        with open(archive_path, "wb") as stream:
            subprocess.run(["git", "-C", VAULT, "archive", "HEAD"], check=False,
                           stdout=stream, stderr=subprocess.DEVNULL)
        os.makedirs(self.root, exist_ok=True)
        if os.path.getsize(archive_path) == 0:
            self.skipTest("no git archive of the product tree available")
        locale_env = os.environ.copy()
        locale_env.update({"LANG": "C", "LC_ALL": "C"})
        subprocess.run(["tar", "-xf", archive_path, "-C", self.root],
                       check=True, env=locale_env)
        # `git archive` gives the COMMITTED tree; overlay the live scripts so the
        # fixture exercises the code under test rather than the last commit's copy
        # (without this the test silently certifies HEAD and proves nothing).
        shutil.rmtree(os.path.join(self.root, "System", "Scripts"), ignore_errors=True)
        shutil.copytree(SCRIPTS, os.path.join(self.root, "System", "Scripts"))
        # Drop the fixture's test suite so certify's regression dimension reports
        # "no test suite found" instead of re-running this entire suite inside
        # itself. Every dimension that can touch the tree — health, vocab, and all
        # of BEHAVIORAL including the idempotency probe — still runs.
        shutil.rmtree(os.path.join(self.root, "System", "Tests", "scripts"),
                      ignore_errors=True)
        man = product_manifest(role="personal-instance")
        with open(os.path.join(self.root, "SYSTEM-MANIFEST.yaml"), "w") as f:
            f.write(man)
        os.makedirs(os.path.join(self.root, "20 Knowledge"), exist_ok=True)
        with open(os.path.join(self.root, "20 Knowledge", "Probe.md"), "w") as f:
            f.write("---\nid: note-probe\ntype: note\ntitle: Probe\nstatus: draft\n"
                    "created: 2026-07-27\nupdated: 2026-07-27\n"
                    "summary: A scratch note that gives the freshness ledger something to baseline.\n"
                    "---\n\n# Probe\n\nBody.\n")
        r = subprocess.run([sys.executable, os.path.join(self.root, "System", "Scripts", "aios.py"),
                            "generate", "--root", self.root], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        ledger = os.path.join(self.root, "System", "Logs", "freshness-ledger.json")
        self.assertTrue(os.path.isfile(ledger),
                        "fixture precondition: freshness must be active, or this proves nothing")
        # and the ledger must be missing an entry, so a `generate` inside the
        # probe has something to write. That is the seeded failure.
        with open(os.path.join(self.root, "20 Knowledge", "Unseen.md"), "w") as f:
            f.write("---\nid: note-unseen\ntype: note\ntitle: Unseen\nstatus: draft\n"
                    "created: 2026-07-27\nupdated: 2026-07-27\n"
                    "summary: Created after the baseline, so the ledger has never seen it.\n"
                    "---\n\n# Unseen\n\nBody.\n")

    def tearDown(self):
        shutil.rmtree(self.outer, ignore_errors=True)

    def _assert_unchanged(self, fn, what):
        before_h, before_f = tree_hash(self.root), tree_files(self.root)
        fn()
        after_h, after_f = tree_hash(self.root), tree_files(self.root)
        if before_h != after_h:
            changed = sorted(set(before_f) ^ set(after_f)) + \
                sorted(k for k in set(before_f) & set(after_f) if before_f[k] != after_f[k])
            self.fail(f"{what} modified the tree: {changed[:10]}")

    def test_health_leaves_the_tree_byte_identical(self):
        self._assert_unchanged(
            lambda: health_mod.run(self.root, Args(), Report("health")), "health")

    def test_certify_leaves_the_tree_byte_identical(self):
        """The defect: certify's generate-twice probe baselined `Unseen.md` into
        the tracked ledger and never put it back."""
        def _run():
            subprocess.run([sys.executable, os.path.join(self.root, "System", "Scripts", "aios.py"),
                            "certify", "--root", self.root], capture_output=True, text=True)
        self._assert_unchanged(_run, "certify")

    def test_probe_runs_generate_only_in_an_isolated_working_directory(self):
        calls = []
        real_run = certify_mod.subprocess.run

        def observe(*args, **kwargs):
            calls.append(kwargs.get("cwd"))
            return real_run(*args, **kwargs)

        with mock.patch.object(certify_mod.subprocess, "run", side_effect=observe):
            rep = certify_mod._idempotency(self.root)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(cwd and os.path.abspath(cwd) != os.path.abspath(self.root)
                            for cwd in calls))

    def test_probe_never_creates_a_missing_live_ledger(self):
        ledger = os.path.join(self.root, "System", "Logs", "freshness-ledger.json")
        os.remove(ledger)
        certify_mod._idempotency(self.root)
        self.assertFalse(os.path.exists(ledger),
                         "isolated probing must never create a live-vault ledger")


def _git_vault(root):
    os.makedirs(os.path.join(root, "20 Knowledge"), exist_ok=True)
    with open(os.path.join(root, "20 Knowledge", "mine.md"), "w") as stream:
        stream.write("mine v1\n")
    for c in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
              ["git", "config", "user.name", "t"], ["git", "add", "-A"],
              ["git", "commit", "-qm", "base"]):
        subprocess.run(c, cwd=root, capture_output=True)


def _log_body(root, ref="HEAD"):
    return subprocess.run(["git", "log", "-1", "--format=%B", ref], cwd=root,
                          capture_output=True, text=True).stdout


@unittest.skipUnless(shutil.which("git"), "git required")
class TestCheckpointConcurrency(unittest.TestCase):
    """(3) the failure mode that must be gone: a checkpoint that silently commits
    another session's work under a message that mentions none of it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _git_vault(self.tmp)
        # my work, and a concurrent session's work, in one shared tree
        with open(os.path.join(self.tmp, "20 Knowledge", "mine.md"), "w") as stream:
            stream.write("mine v2\n")
        with open(os.path.join(self.tmp, "20 Knowledge", "theirs.md"), "w") as stream:
            stream.write("another session\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_still_saves_everything(self):
        """The guarantee that must survive: you can always save state."""
        a = Args(); a.message = "save all"
        rep = ck_mod.run(self.tmp, a, Report("checkpoint"))
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual("", subprocess.run(["git", "status", "--porcelain"], cwd=self.tmp,
                                            capture_output=True, text=True).stdout.strip())

    def test_the_commit_message_names_what_it_swept(self):
        """The defect. The old commit body said only the label, so a record could
        read 'nothing committed' over a commit containing three sessions' files."""
        a = Args(); a.message = "nothing committed, that stays his call"
        ck_mod.run(self.tmp, a, Report("checkpoint"))
        body = _log_body(self.tmp)
        self.assertIn("20 Knowledge/theirs.md", body,
                      "a checkpoint must disclose the foreign file it committed")
        self.assertIn("20 Knowledge/mine.md", body)

    def test_report_returns_the_committed_paths(self):
        a = Args(); a.message = "x"
        rep = ck_mod.run(self.tmp, a, Report("checkpoint"))
        self.assertIn("20 Knowledge/theirs.md", rep.info.get("committed_paths", []))

    def test_paths_scopes_the_commit_and_reports_the_rest(self):
        a = Args(); a.message = "only mine"; a.paths = ["20 Knowledge/mine.md"]
        rep = ck_mod.run(self.tmp, a, Report("checkpoint"))
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(["20 Knowledge/mine.md"], rep.info.get("committed_paths"))
        self.assertIn("20 Knowledge/theirs.md", rep.info.get("left_uncommitted", []))
        # the foreign file is still sitting there, untouched
        left = subprocess.run(["git", "status", "--porcelain"], cwd=self.tmp,
                              capture_output=True, text=True).stdout
        self.assertIn("theirs.md", left)

    def test_strict_refuses_and_explains(self):
        a = Args(); a.message = "x"; a.paths = ["20 Knowledge/mine.md"]; a.strict = True
        rep = ck_mod.run(self.tmp, a, Report("checkpoint"))
        self.assertFalse(rep.ok)
        self.assertTrue(any("theirs.md" in e for e in rep.errors), rep.errors)
        self.assertTrue(any("--zip-only" in e or "--paths" in e for e in rep.errors))
        # and it refused BEFORE committing
        self.assertIn("mine.md", subprocess.run(["git", "status", "--porcelain"], cwd=self.tmp,
                                                capture_output=True, text=True).stdout)

    def test_strict_on_a_clean_scope_commits(self):
        a = Args(); a.message = "x"
        a.paths = ["20 Knowledge/mine.md", "20 Knowledge/theirs.md"]; a.strict = True
        rep = ck_mod.run(self.tmp, a, Report("checkpoint"))
        self.assertTrue(rep.ok, rep.errors)

    def test_paths_accepts_a_directory(self):
        with open(os.path.join(self.tmp, "root-file.md"), "w") as stream:
            stream.write("elsewhere\n")
        a = Args(); a.message = "dir scope"; a.paths = ["20 Knowledge"]
        rep = ck_mod.run(self.tmp, a, Report("checkpoint"))
        self.assertIn("root-file.md", rep.info.get("left_uncommitted", []))
        self.assertNotIn("root-file.md", rep.info.get("committed_paths", []))

    def test_zip_only_still_never_commits(self):
        a = Args(); a.message = "snap"; a.zip_only = True
        rep = ck_mod.run(self.tmp, a, Report("checkpoint"))
        self.assertTrue(rep.ok, rep.errors)
        self.assertIn("theirs.md", subprocess.run(["git", "status", "--porcelain"], cwd=self.tmp,
                                                  capture_output=True, text=True).stdout)
        shutil.rmtree(os.path.join(os.path.dirname(self.tmp),
                                   os.path.basename(self.tmp) + "-Snapshots"),
                      ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
