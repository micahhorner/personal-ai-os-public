"""Focused tests for the historical release qualification runner."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest


VAULT = Path(__file__).resolve().parents[3]
RUNNER_PATH = VAULT / "System" / "Tests" / "release_qualification" / "runner.py"
SPEC = importlib.util.spec_from_file_location("release_qualification_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


MANIFEST = """system:
  system_version: {version}
  instance_role: {role}
runtime:
  ai_writes_enabled: true
"""


FAKE_AIOS = r'''#!/usr/bin/env python3
import os
import json
from pathlib import Path
import re
import sys
import time

if sys.argv[1] == "rollback":
    assert re.fullmatch(r"[0-9a-fA-F]{7,64}", sys.argv[2])
    assert sys.argv[3:8] == [
        "--expected-sha256", "a" * 64, "--confirm", "--clean", "--root"
    ]
    instance = Path(sys.argv[8])
    mode = os.environ.get("FAKE_ROLLBACK_MODE", "restore")
    print("rollback argv=" + repr(sys.argv[1:]), flush=True)
    if mode == "restore":
        manifest = instance / "SYSTEM-MANIFEST.yaml"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            re.sub(r"(system_version:\s*)[^\s#]+", r"\g<1>1.43.0", text, count=1),
            encoding="utf-8",
        )
        marker = instance / "System" / "changed-by-upgrade.txt"
        if marker.exists():
            marker.unlink()
        system_dir = instance / "System"
        if system_dir.exists() and not any(system_dir.iterdir()):
            system_dir.rmdir()
        raise SystemExit(0)
    if mode == "timeout":
        time.sleep(30)
    if mode == "mismatch":
        raise SystemExit(0)
    raise SystemExit(7)

assert sys.argv[1] == "upgrade"
release = Path(sys.argv[2])
assert sys.argv[3] == "--root"
instance = Path(sys.argv[4])
mode = os.environ.get("FAKE_UPGRADE_MODE", "complete")
review_hash = "b" * 64
if "--apply" not in sys.argv and "--dry-run" not in sys.argv:
    print(json.dumps({"command":"upgrade","ok":True,"errors":[],"warnings":[],
                      "info":{"review_sha256":review_hash}}))
    raise SystemExit(0)
if "--apply" in sys.argv:
    assert sys.argv[sys.argv.index("--review-sha256") + 1] == review_hash
if mode in {"complete", "hybrid", "timeout", "dry-run-mutates"}:
    marker = instance / "System" / "changed-by-upgrade.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(mode + "\n", encoding="utf-8")
if mode in {"complete", "dry-run-mutates"}:
    target = re.search(
        r"system_version:\s*([^\s#]+)",
        (release / "SYSTEM-MANIFEST.yaml").read_text(encoding="utf-8"),
    ).group(1)
    manifest = instance / "SYSTEM-MANIFEST.yaml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        re.sub(r"(system_version:\s*)[^\s#]+", r"\g<1>" + target, text, count=1),
        encoding="utf-8",
    )
    print(json.dumps({"command":"upgrade","ok":True,"errors":[],"warnings":[],"info":{}}))
    raise SystemExit(0)
if mode == "dry-run-success":
    assert "--dry-run" in sys.argv
    print(json.dumps({"command":"upgrade","ok":True,"errors":[],"warnings":[],"info":{}}))
    raise SystemExit(0)
if mode == "timeout":
    time.sleep(30)
raise SystemExit(7)
'''


class ReleaseRunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="release runner Ω ")
        self.outer = Path(self.temp.name)
        self.instance = self.outer / "instance with space"
        self.release = self.outer / "release"
        self.scratch = self.outer / "scratch"
        self.reports = self.outer / "reports"
        for path in (self.instance, self.release, self.scratch, self.reports):
            path.mkdir()
        (self.instance / "SYSTEM-MANIFEST.yaml").write_text(
            MANIFEST.format(version="1.43.0", role="personal-instance"),
            encoding="utf-8",
        )
        (self.instance / "20 Knowledge").mkdir()
        (self.instance / "20 Knowledge" / "mine.md").write_text(
            "user content\n", encoding="utf-8"
        )
        (self.release / "SYSTEM-MANIFEST.yaml").write_text(
            MANIFEST.format(version="1.64.0", role="generic-master"),
            encoding="utf-8",
        )
        scripts = self.release / "System" / "Scripts"
        scripts.mkdir(parents=True)
        aios = scripts / "aios.py"
        aios.write_text(FAKE_AIOS, encoding="utf-8")
        aios.chmod(aios.stat().st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.temp.cleanup()

    def run_upgrade(self, mode, **kwargs):
        environment = dict(kwargs.pop("environment", {}))
        environment["FAKE_UPGRADE_MODE"] = mode
        return runner.run_upgrade(
            self.instance,
            self.release,
            self.scratch,
            self.reports,
            run_id=kwargs.pop("run_id", "v143-to-v164"),
            environment=environment,
            **kwargs,
        )


class TestExecutionAndClassification(ReleaseRunnerTestCase):
    def test_complete_captures_explicit_argv_output_timing_and_evidence(self):
        shell_payload = "$(touch shell-owned)"
        result = self.run_upgrade(
            "complete",
            extra_args=["--accept", "literal path", shell_payload],
        )
        self.assertEqual("complete", result["classification"])
        self.assertEqual("apply", result["mode"])
        self.assertEqual(
            {
                "status": "passed",
                "code": "apply-complete",
                "reason": "apply completed at the target release version",
            },
            result["phase_verdict"],
        )
        self.assertEqual(0, result["process"]["returncode"])
        self.assertFalse(result["process"]["timed_out"])
        self.assertGreaterEqual(result["process"]["elapsed_seconds"], 0)
        self.assertIn("--review-sha256", result["command"]["argv"])
        self.assertEqual("", result["process"]["stderr"])
        self.assertFalse(result["command"]["shell"])
        self.assertEqual(
            [
                sys.executable,
                str((self.release / "System" / "Scripts" / "aios.py").resolve()),
                "upgrade",
                str(self.release.resolve()),
                "--root",
                str(self.instance.resolve()),
                "--accept",
                "literal path",
                shell_payload,
                "--apply",
                "--confirm",
                "--review-sha256",
                "b" * 64,
                "--json",
            ],
            result["command"]["argv"],
        )
        self.assertFalse((self.scratch / "shell-owned").exists())
        self.assertEqual(
            {"before": "1.43.0", "target": "1.64.0", "after": "1.64.0"},
            result["versions"],
        )
        evidence_path = Path(result["evidence_path"])
        self.assertTrue(evidence_path.is_file())
        persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(1, persisted["attempt"])
        self.assertEqual("complete", persisted["classification"])
        self.assertEqual("apply", persisted["mode"])
        self.assertEqual("apply-complete", persisted["phase_verdict"]["code"])

    def test_nonzero_after_writes_is_hybrid(self):
        result = self.run_upgrade("hybrid")
        self.assertEqual("hybrid", result["classification"])
        self.assertEqual(7, result["process"]["returncode"])
        self.assertIn(
            "System/changed-by-upgrade.txt",
            result["tree"]["changes"]["added"],
        )
        self.assertNotEqual(
            result["tree"]["before"]["sha256"],
            result["tree"]["after"]["sha256"],
        )

    def test_nonzero_without_writes_is_unchanged(self):
        result = self.run_upgrade("unchanged")
        self.assertEqual("unchanged", result["classification"])
        self.assertEqual("apply", result["mode"])
        self.assertEqual(
            {
                "status": "failed",
                "code": "apply-failed-unchanged",
                "reason": "apply did not complete but left the instance tree unchanged",
            },
            result["phase_verdict"],
        )
        self.assertEqual(7, result["process"]["returncode"])
        self.assertEqual(
            result["tree"]["before"]["sha256"],
            result["tree"]["after"]["sha256"],
        )
        self.assertEqual(
            {"added": [], "removed": [], "modified": []},
            result["tree"]["changes"],
        )

    def test_timeout_kills_process_group_and_classifies_changed_tree(self):
        started = time.monotonic()
        result = self.run_upgrade("timeout", timeout_seconds=0.1)
        self.assertLess(time.monotonic() - started, 5)
        self.assertTrue(result["process"]["timed_out"])
        self.assertEqual("hybrid", result["classification"])
        self.assertEqual("unsafe", result["phase_verdict"]["status"])
        self.assertIn("--review-sha256", result["command"]["argv"])

    def test_successful_unchanged_dry_run_has_distinct_pass_verdict(self):
        result = self.run_upgrade(
            "dry-run-success",
            run_id="dry-run-pass",
            extra_args=["--dry-run"],
        )
        self.assertEqual("dry-run", result["mode"])
        self.assertEqual("unchanged", result["classification"])
        self.assertEqual(
            {
                "status": "passed",
                "code": "dry-run-passed",
                "reason": "dry-run exited zero and left the instance tree unchanged",
            },
            result["phase_verdict"],
        )
        persisted = json.loads(
            Path(result["evidence_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual("dry-run", persisted["mode"])
        self.assertEqual("dry-run-passed", persisted["phase_verdict"]["code"])

    def test_dry_run_of_already_current_instance_is_still_unchanged(self):
        (self.instance / "SYSTEM-MANIFEST.yaml").write_text(
            MANIFEST.format(version="1.64.0", role="personal-instance"),
            encoding="utf-8",
        )
        result = self.run_upgrade(
            "dry-run-success",
            run_id="dry-run-current",
            extra_args=["--dry-run"],
        )
        self.assertEqual("unchanged", result["classification"])
        self.assertEqual("dry-run-passed", result["phase_verdict"]["code"])

    def test_any_dry_run_mutation_is_hybrid_and_unsafe(self):
        result = self.run_upgrade(
            "dry-run-mutates",
            run_id="dry-run-mutates",
            extra_args=["--dry-run"],
        )
        self.assertEqual(0, result["process"]["returncode"])
        self.assertEqual("1.64.0", result["versions"]["after"])
        self.assertEqual("hybrid", result["classification"])
        self.assertEqual(
            {
                "status": "unsafe",
                "code": "dry-run-mutated",
                "reason": "dry-run changed the instance tree",
            },
            result["phase_verdict"],
        )


class TestEvidenceAndSnapshots(ReleaseRunnerTestCase):
    def test_rerun_appends_attempt_instead_of_overwriting(self):
        first = self.run_upgrade("unchanged", run_id="repeat")
        second = self.run_upgrade("unchanged", run_id="repeat")
        self.assertNotEqual(first["evidence_path"], second["evidence_path"])
        self.assertEqual(
            ["repeat.attempt-0001.json", "repeat.attempt-0002.json"],
            sorted(path.name for path in self.reports.iterdir()),
        )
        self.assertEqual(1, first["attempt"])
        self.assertEqual(2, second["attempt"])

    def test_tree_hash_ignores_mtime_and_git_internals_but_tracks_mode(self):
        first = runner.capture_tree(self.instance)
        note = self.instance / "20 Knowledge" / "mine.md"
        os.utime(note, (1, 1))
        (self.instance / ".git").mkdir()
        (self.instance / ".git" / "noise").write_text("changes\n", encoding="utf-8")
        second = runner.capture_tree(self.instance)
        self.assertEqual(first["sha256"], second["sha256"])
        note.chmod(note.stat().st_mode | stat.S_IXUSR)
        third = runner.capture_tree(self.instance)
        self.assertNotEqual(second["sha256"], third["sha256"])

    def test_recovery_tree_ignores_untracked_directory_modes_only(self):
        physical_before = runner.capture_tree(self.instance)
        recovery_before = runner.capture_tree(
            self.instance, normalize_directory_modes=True
        )
        directory = self.instance / "20 Knowledge"
        directory.chmod(0o755 if stat.S_IMODE(directory.stat().st_mode) != 0o755 else 0o775)
        physical_after = runner.capture_tree(self.instance)
        recovery_after = runner.capture_tree(
            self.instance, normalize_directory_modes=True
        )
        self.assertNotEqual(physical_before["sha256"], physical_after["sha256"])
        self.assertEqual(recovery_before["sha256"], recovery_after["sha256"])

    def test_git_status_is_captured_without_changing_refs(self):
        subprocess.run(["git", "init", "-q"], cwd=self.instance, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "add", "-A"],
            cwd=self.instance,
            check=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "commit", "-qm", "base"],
            cwd=self.instance,
            check=True,
        )
        before_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.instance,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        result = self.run_upgrade("unchanged")
        after_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.instance,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertTrue(result["git"]["before"]["available"])
        self.assertEqual(before_head, after_head)


class TestSafetyValidation(ReleaseRunnerTestCase):
    def test_rejects_report_or_scratch_inside_instance(self):
        inside = self.instance / "runner-output"
        inside.mkdir()
        with self.assertRaisesRegex(runner.RunnerError, "outside instance_dir"):
            runner.run_upgrade(
                self.instance,
                self.release,
                self.scratch,
                inside,
                run_id="unsafe-report",
            )

    def test_rejects_overlapping_instance_and_release(self):
        nested = self.instance / "release"
        nested.mkdir()
        with self.assertRaisesRegex(runner.RunnerError, "must not contain"):
            runner.run_upgrade(
                self.instance,
                nested,
                self.scratch,
                self.reports,
                run_id="unsafe-overlap",
            )

    def test_rejects_invalid_run_id_and_missing_release_cli(self):
        with self.assertRaisesRegex(runner.RunnerError, "run_id"):
            self.run_upgrade("unchanged", run_id="../escape")
        (self.release / "System" / "Scripts" / "aios.py").unlink()
        with self.assertRaisesRegex(runner.RunnerError, "release CLI"):
            self.run_upgrade("unchanged")


class TestRollbackRunner(ReleaseRunnerTestCase):
    ROLLBACK_REF = "a1b2c3d4e5f6"

    def expected_hash(self):
        return runner.capture_tree(self.instance)["sha256"]

    def mutate_instance(self):
        manifest = self.instance / "SYSTEM-MANIFEST.yaml"
        manifest.write_text(
            MANIFEST.format(version="1.64.0", role="personal-instance"),
            encoding="utf-8",
        )
        marker = self.instance / "System" / "changed-by-upgrade.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("partial apply\n", encoding="utf-8")

    def run_rollback(self, mode, expected_hash, **kwargs):
        environment = dict(kwargs.pop("environment", {}))
        environment["FAKE_ROLLBACK_MODE"] = mode
        return runner.run_rollback(
            self.instance,
            self.release,
            self.scratch,
            self.reports,
            run_id=kwargs.pop("run_id", "rollback-v143"),
            rollback_ref=kwargs.pop("rollback_ref", self.ROLLBACK_REF),
            expected_pre_apply_tree_hash=expected_hash,
            expected_tracked_sha256=kwargs.pop(
                "expected_tracked_sha256", "a" * 64
            ),
            environment=environment,
            **kwargs,
        )

    def test_exact_rollback_uses_explicit_safe_argv_and_persists_proof(self):
        expected = self.expected_hash()
        self.mutate_instance()
        result = self.run_rollback("restore", expected)
        self.assertEqual("exact-restoration", result["classification"])
        self.assertEqual("rollback", result["mode"])
        self.assertEqual("passed", result["phase_verdict"]["status"])
        self.assertTrue(result["tree"]["exact_restoration"])
        self.assertEqual(expected, result["tree"]["after"]["sha256"])
        self.assertEqual(
            [
                sys.executable,
                str((self.release / "System" / "Scripts" / "aios.py").resolve()),
                "rollback",
                self.ROLLBACK_REF,
                "--expected-sha256",
                "a" * 64,
                "--confirm",
                "--clean",
                "--root",
                str(self.instance.resolve()),
            ],
            result["command"]["argv"],
        )
        self.assertFalse(result["command"]["shell"])
        persisted = json.loads(
            Path(result["evidence_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual("rollback-exact", persisted["phase_verdict"]["code"])
        self.assertEqual(self.ROLLBACK_REF, persisted["rollback_ref"])

    def test_zero_exit_with_wrong_tree_is_unsafe_mismatch(self):
        expected = self.expected_hash()
        self.mutate_instance()
        result = self.run_rollback("mismatch", expected)
        self.assertEqual("restoration-mismatch", result["classification"])
        self.assertEqual("unsafe", result["phase_verdict"]["status"])
        self.assertFalse(result["tree"]["exact_restoration"])

    def test_failed_process_on_already_exact_tree_is_not_a_pass(self):
        expected = self.expected_hash()
        result = self.run_rollback("failure", expected)
        self.assertEqual("rollback-failed", result["classification"])
        self.assertEqual("failed", result["phase_verdict"]["status"])
        self.assertTrue(result["tree"]["exact_restoration"])

    def test_timeout_after_wrong_state_is_unsafe(self):
        expected = self.expected_hash()
        self.mutate_instance()
        result = self.run_rollback("timeout", expected, timeout_seconds=0.1)
        self.assertTrue(result["process"]["timed_out"])
        self.assertEqual("restoration-mismatch", result["classification"])
        self.assertEqual("unsafe", result["phase_verdict"]["status"])

    def test_rerun_appends_rollback_evidence(self):
        expected = self.expected_hash()
        first = self.run_rollback("failure", expected, run_id="rollback-repeat")
        second = self.run_rollback("failure", expected, run_id="rollback-repeat")
        self.assertNotEqual(first["evidence_path"], second["evidence_path"])
        self.assertEqual(1, first["attempt"])
        self.assertEqual(2, second["attempt"])

    def test_rejects_zip_display_and_unsafe_refs(self):
        expected = self.expected_hash()
        zip_target = self.outer / "snapshot.zip"
        zip_target.write_bytes(b"zip")
        for bad_ref, message in (
            ("", "must not be empty"),
            (str(zip_target), "ZIP/manual"),
            ("snapshot.zip", "ZIP/manual"),
            ("git a1b2c3d", "hexadecimal"),
            ("HEAD~1", "hexadecimal"),
            ("--help", "hexadecimal"),
        ):
            with self.subTest(ref=bad_ref):
                with self.assertRaisesRegex(runner.RunnerError, message):
                    self.run_rollback(
                        "failure",
                        expected,
                        run_id="bad-ref",
                        rollback_ref=bad_ref,
                    )

    def test_rejects_invalid_expected_hash(self):
        with self.assertRaisesRegex(runner.RunnerError, "SHA-256"):
            self.run_rollback("failure", "not-a-hash")
        with self.assertRaisesRegex(runner.RunnerError, "expected_tracked"):
            self.run_rollback(
                "failure", self.expected_hash(), expected_tracked_sha256="bad"
            )


if __name__ == "__main__":
    unittest.main()
