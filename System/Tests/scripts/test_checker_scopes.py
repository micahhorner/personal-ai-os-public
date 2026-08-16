"""Seeded contracts for Wave 6's four-verdict separation.

These tests deliberately prove negative boundaries: current-source checks do not
become runtime or release evidence, instance health does not become either, and
the shipped empty runtime profile is reported as NOT CERTIFIED.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)

from lib.report import Report  # noqa: E402
from cmd import certify, health, instancehealth, runtimecertify, sourcecheck  # noqa: E402


class Args:
    target = None
    source_authority_repository = None
    source_authority_commit = None


def _manifest(root, role="generic-master", profile=None):
    runtime = ""
    if profile is not None:
        runtime = f"runtime:\n  active_profile: {profile}\n"
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w", encoding="utf-8") as stream:
        stream.write(f"system:\n  instance_role: {role}\n" + runtime)


class TestSourceScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="checker scopes ")
        _manifest(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_lightweight(self, command):
        rep = Report(command)
        empty = lambda _root, _args, _rep: None
        with mock.patch.object(certify.health_mod, "run", side_effect=empty), \
                mock.patch.object(certify.vc_mod, "run", side_effect=empty), \
                mock.patch.object(certify, "BEHAVIORAL", []), \
                mock.patch.object(certify, "_run_regression", return_value=(True, "OK")):
            if command == "source-check":
                sourcecheck.run(self.tmp, Args(), rep)
            else:
                certify.run(self.tmp, Args(), rep)
        return rep

    def test_source_check_names_only_what_it_proves(self):
        rep = self._run_lightweight("source-check")
        self.assertTrue(rep.ok, rep.errors)
        self.assertIn("SOURCE CHECK", rep.info["verdict_scope"])
        self.assertIn("NOT RUN", rep.info["runtime_certification"])
        self.assertIn("NOT RUN", rep.info["release_qualification"])

    def test_compatibility_certify_is_explicitly_source_check(self):
        rep = self._run_lightweight("certify")
        self.assertTrue(rep.ok, rep.errors)
        self.assertIn("SOURCE CHECK", rep.info["verdict_scope"])
        self.assertIn("compatibility alias for source-check",
                      rep.info["compatibility_alias"])
        self.assertNotIn("PASS", rep.info["runtime_certification"])
        self.assertNotIn("PASS", rep.info["release_qualification"])

    def test_source_check_refuses_a_personalized_instance(self):
        _manifest(self.tmp, role="personal-instance")
        rep = self._run_lightweight("source-check")
        self.assertFalse(rep.ok)
        self.assertTrue(any("instance-health" in item for item in rep.errors))

    def test_missing_regression_suite_is_a_source_error(self):
        rep = Report("source-check")
        empty = lambda _root, _args, _rep: None
        with mock.patch.object(certify.health_mod, "run", side_effect=empty), \
                mock.patch.object(certify.vc_mod, "run", side_effect=empty), \
                mock.patch.object(certify, "BEHAVIORAL", []), \
                mock.patch.object(certify, "_run_regression",
                                  return_value=(None, "no test suite found")):
            sourcecheck.run(self.tmp, Args(), rep)
        self.assertFalse(rep.ok)
        self.assertTrue(any("cannot pass without its tests" in item
                            for item in rep.errors))

    def test_strict_regression_requires_explicit_authority(self):
        os.makedirs(os.path.join(self.tmp, "System", "Tests", "scripts"))
        ok, summary = certify._run_regression(self.tmp)
        self.assertFalse(ok)
        self.assertIn("requires --source-authority-repository", summary)

    def test_authority_must_be_separate_and_fully_pinned(self):
        fingerprint, error = certify._authority_fingerprint(
            self.tmp, self.tmp, "a" * 40)
        self.assertIsNone(fingerprint)
        self.assertIn("separate", error)
        fingerprint, error = certify._authority_fingerprint(
            self.tmp, os.path.dirname(self.tmp), "not-a-pin")
        self.assertIsNone(fingerprint)
        self.assertIn("full lowercase", error)

    def test_wrong_authority_commit_fails_closed(self):
        repository = os.path.join(self.tmp, "authority")
        os.makedirs(repository)
        subprocess.run(["git", "init", "-q", repository], check=True)
        fingerprint, error = certify._authority_fingerprint(
            self.tmp, repository, "0" * 40)
        self.assertIsNone(fingerprint)
        self.assertIn("does not resolve exactly", error)

    def test_mutated_authority_invalidates_regression(self):
        os.makedirs(os.path.join(self.tmp, "System", "Tests", "scripts"))
        repository = os.path.join(self.tmp, "authority")
        os.makedirs(repository)
        subprocess.run(["git", "init", "-q", repository], check=True)
        subprocess.run(["git", "-C", repository, "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", repository, "config", "user.email", "test@example.invalid"], check=True)
        with open(os.path.join(repository, "seed"), "w") as stream:
            stream.write("seed\n")
        subprocess.run(["git", "-C", repository, "add", "seed"], check=True)
        subprocess.run(["git", "-C", repository, "commit", "-qm", "seed"], check=True)
        pin = subprocess.run(
            ["git", "-C", repository, "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True).stdout.strip()

        completed = mock.Mock(returncode=0, stderr="", stdout="OK\n")
        real_run = subprocess.run
        def mutate_when_child_starts(command, *args, **kwargs):
            if command[:3] == [sys.executable, "-m", "unittest"]:
                real_run(
                    ["git", "-C", repository, "update-ref",
                     "refs/heads/mutated-during-check", pin],
                    check=True, capture_output=True, text=True)
                return completed
            return real_run(command, *args, **kwargs)

        with mock.patch.object(
                certify.subprocess, "run", side_effect=mutate_when_child_starts):
            ok, summary = certify._run_regression(
                self.tmp, repository, pin)
        self.assertFalse(ok)
        self.assertIn("changed during strict regression", summary)

    def test_generated_warnings_reconcile_only_after_isolated_proof(self):
        _manifest(self.tmp)
        with open(os.path.join(self.tmp, "SYSTEM-MANIFEST.yaml"), "a") as stream:
            stream.write("directories:\n  generated:\n    - System/Generated\n")
        warning = ("[doc-staleness] manifest references a missing file: "
                   "System/Generated/component-index.json "
                   "(doc moved/renamed — manifest is stale)")
        health_report = Report("health")
        health_report.warn(warning)
        health_report.info["doc_staleness_flags"] = 1
        failed = Report("command-idempotency")
        failed.error("generation failed")
        certify._reconcile_generated_health(self.tmp, health_report, failed)
        self.assertEqual(health_report.warnings, [warning])

        passed = Report("command-idempotency")
        passed.info["generated_entrypoints"] = "PASS — isolated"
        certify._reconcile_generated_health(self.tmp, health_report, passed)
        self.assertEqual(health_report.warnings, [])
        self.assertEqual(health_report.info["doc_staleness_flags"], 0)
        self.assertIn("rebuilt and validated", health_report.info["generated_state"])


class TestRuntimeScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="runtime certification ")
        os.makedirs(os.path.join(self.tmp, "System", "Runtime Profiles"))
        self.rel = "System/Runtime Profiles/test.yaml"
        _manifest(self.tmp, profile=self.rel)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_profile(self, evidence="{}", last="null"):
        with open(os.path.join(self.tmp, self.rel), "w", encoding="utf-8") as stream:
            stream.write(
                "id: runtime-test\nprovider: test\nmodel: test-model\n"
                f"certifications: {evidence}\nlast_tested: {last}\n"
            )

    def test_shipped_empty_profile_is_not_certified(self):
        self._write_profile()
        rep = Report("runtime-certify")
        runtimecertify.run(self.tmp, Args(), rep)
        self.assertFalse(rep.ok)
        self.assertEqual("NOT CERTIFIED", rep.info["certification_status"])
        self.assertEqual(0, rep.info["recorded_evidence_count"])
        self.assertIn("source checks", " ".join(rep.errors))

    def test_legacy_profile_claim_is_not_inferred_as_certification(self):
        self._write_profile(
            evidence="{fixture-one: {result: pass, date: 2026-08-09}}",
            last="2026-08-09",
        )
        rep = Report("runtime-certify")
        runtimecertify.run(self.tmp, Args(), rep)
        self.assertFalse(rep.ok)
        self.assertEqual("NOT CERTIFIED", rep.info["certification_status"])
        self.assertIn("will not infer certification", " ".join(rep.errors))

    def test_external_or_traversing_profile_path_is_refused(self):
        args = Args()
        args.target = "../outside.yaml"
        self._write_profile()
        rep = Report("runtime-certify")
        runtimecertify.run(self.tmp, args, rep)
        self.assertFalse(rep.ok)
        self.assertIn("contained relative", " ".join(rep.errors))


class TestInstanceWarningAggregation(unittest.TestCase):
    def test_health_rolls_up_subcheck_warnings(self):
        tmp = tempfile.mkdtemp(prefix="instance warnings ")
        self.addCleanup(shutil.rmtree, tmp, True)

        def warn(_root, _args, sub):
            sub.warn("planted warning")

        modules = [health.v_mod, health.l_mod, health.d_mod, health.dc_mod,
                   health.dcmd_mod, health.da_mod, health.dp_mod, health.voc_mod]
        patches = [mock.patch.object(module, "run", side_effect=warn)
                   for module in modules]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        with mock.patch("cmd.packcheck.run", return_value=None), \
                mock.patch("cmd.docgen.run", return_value=None), \
                mock.patch("lib.freshness.load_registry", return_value=None):
            rep = Report("instance-health")
            instancehealth.run(tmp, Args(), rep)
        planted = [item for item in rep.warnings if "planted warning" in item]
        self.assertEqual(8, len(planted), rep.warnings)
        self.assertIn("INSTANCE HEALTH", rep.info["verdict_scope"])
        self.assertEqual("NOT RUN", rep.info["runtime_certification"])
        self.assertEqual("NOT RUN", rep.info["release_qualification"])


class TestCommandSurface(unittest.TestCase):
    def test_three_scope_honest_commands_are_public(self):
        # Pin the actual source surface without running the CLI.
        with open(os.path.join(SCRIPTS, "aios.py"), encoding="utf-8") as stream:
            text = stream.read()
        for command in ("source-check", "instance-health", "runtime-certify"):
            self.assertIn(f'"{command}"', text)


if __name__ == "__main__":
    unittest.main()
