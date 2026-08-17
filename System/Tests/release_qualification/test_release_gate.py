"""Seeded contracts for the final, scope-honest release gate."""

from __future__ import annotations

from dataclasses import replace
import unittest
from unittest import mock

from .release_gate import (
    GENERIC_MASTER_SOURCE_ADVISORIES,
    LEGAL_ROOT_PATHS,
    ReleaseGateError,
    evaluate_release_gate,
    discover_and_verify_authoritative_coverage,
    verify_authoritative_coverage,
    verify_fault_evidence,
    verify_recovery_evidence,
    verify_source_check,
    verify_target_convergence,
)
from .support_matrix import ReleasePin, SourcePin, SupportMatrix
from .transaction_faults import BOUNDARIES, PHASES


TARGET = "b" * 40
SOURCE = "a" * 40


def matrix() -> SupportMatrix:
    return SupportMatrix(
        schema_version=1,
        target=ReleasePin("target-ref", TARGET, "2.0.0"),
        sources=(SourcePin(
            ref="source-ref", commit=SOURCE, version="1.0.0",
            id="source", disposition="candidate-direct"),),
    )


def target_state() -> dict:
    return {
        "distribution_id": "personal-ai-os",
        "system_version": "2.0.0",
        "license": "MIT",
        "instance_role": "generic-master",
        "exact_file_hashes": {
            path: {"kind": "file", "sha256": str(index + 1) * 64}
            for index, path in enumerate(sorted(LEGAL_ROOT_PATHS))
        },
    }


def sources() -> list[dict]:
    target = target_state()
    before = {**target, "system_version": "1.0.0"}
    return [{
        "id": "source",
        "dry_run": {"product_state": {"before": before, "after": before}},
        "apply": {"product_state": {"before": before, "after": target}},
    }]


def authority() -> dict:
    return {
        "kind": "git-mainline-estate",
        "complete": True,
        "target_commit": TARGET,
        "records": [
            {"commit": SOURCE, "version": "1.0.0"},
            {"commit": TARGET, "version": "2.0.0"},
        ],
    }


def source_check() -> dict:
    return {
        "target_commit": TARGET,
        "command": "source-check",
        "returncode": 0,
        "report": {
            "command": "source-check",
            "ok": True,
            "errors": [],
            "warnings": [],
            "info": {
                "verdict_scope": "SOURCE CHECK — source only",
                "runtime_certification": "NOT RUN — external evidence required",
                "release_qualification": "NOT RUN — separate gate",
            },
        },
    }


def fault_evidence() -> dict:
    return {
        "target_commit": TARGET,
        "fault_injection_enabled": True,
        "cases": [{
            "boundary": boundary,
            "phase": phase,
            "classification": "exact-old",
            "old_tree_sha256": "1" * 64,
            "new_tree_sha256": "2" * 64,
            "live_tree_sha256": "1" * 64,
        } for boundary in BOUNDARIES for phase in PHASES],
    }


def recovery_evidence() -> dict:
    return {
        "records": [{
            "fixture_mode": mode,
            "target_commit": TARGET,
            "product_issued_command": (
                "python '/tmp/release with spaces/aios.py' rollback checkpoint "
                "--confirm --root '/tmp/instance with spaces'"),
            "executed_argv": [
                "python", "/tmp/release with spaces/aios.py", "rollback",
                "checkpoint", "--confirm", "--root", "/tmp/instance with spaces",
            ],
            "shell": False,
            "returncode": 0,
            "recovery_qualified": True,
            "before_tree_sha256": "3" * 64,
            "after_tree_sha256": "3" * 64,
        } for mode in ("clean-git", "no-git")],
    }


class ReleaseGateContracts(unittest.TestCase):
    def test_complete_independent_evidence_passes(self):
        result = evaluate_release_gate(
            matrix=matrix(), authority=authority(), target_state=target_state(),
            sources=sources(), source_check=source_check(),
            fault_evidence=fault_evidence(),
            recovery_evidence=recovery_evidence())

        self.assertTrue(result.passed)
        self.assertEqual("passed", result.to_dict()["verdict"])
        self.assertEqual(5, len(result.checks))

    def test_matrix_omission_and_self_declared_noncoverage_fail(self):
        omitted = replace(matrix(), sources=())
        with self.assertRaisesRegex(ReleaseGateError, "missing="):
            verify_authoritative_coverage(omitted, authority())
        incomplete = authority()
        incomplete["complete"] = False
        with self.assertRaisesRegex(ReleaseGateError, "complete=true"):
            verify_authoritative_coverage(matrix(), incomplete)

    def test_authoritative_coverage_is_derived_from_pinned_git_tip(self):
        records = {
            SOURCE: mock.Mock(commit=SOURCE, system_version="1.0.0"),
            TARGET: mock.Mock(commit=TARGET, system_version="2.0.0"),
        }
        with mock.patch(
                "System.Tests.release_qualification.release_gate.estate."
                "discover_mainline_states", return_value=(SOURCE, TARGET)) as discover, \
             mock.patch(
                "System.Tests.release_qualification.release_gate.estate.load_release",
                side_effect=lambda _repo, commit: records[commit]):
            result = discover_and_verify_authoritative_coverage(
                "/repo", matrix(), minimum_version="1.0.0")

        discover.assert_called_once_with(
            "/repo", TARGET, minimum_version="1.0.0", maximum_version="2.0.0")
        self.assertEqual("estate.discover_mainline_states", result["derivation"])

    def test_target_version_only_green_is_rejected(self):
        evidence = sources()
        fake_after = dict(evidence[0]["apply"]["product_state"]["after"])
        fake_hashes = dict(fake_after["exact_file_hashes"])
        fake_hashes["README.md"] = {"kind": "file", "sha256": "f" * 64}
        fake_after["exact_file_hashes"] = fake_hashes
        evidence[0]["apply"]["product_state"]["after"] = fake_after
        with self.assertRaisesRegex(ReleaseGateError, "exact target"):
            verify_target_convergence(target_state(), evidence)

    def test_personal_role_and_regular_file_modes_are_nonsemantic(self):
        evidence = sources()
        after = evidence[0]["apply"]["product_state"]["after"]
        after["instance_role"] = "personal-instance"
        after["exact_file_hashes"]["README.md"]["mode"] = 0o644
        self.assertTrue(
            verify_target_convergence(target_state(), evidence)["passed"])

    def test_missing_or_changed_legal_file_still_fails_convergence(self):
        for mutation in ("missing", "changed"):
            evidence = sources()
            after = evidence[0]["apply"]["product_state"]["after"]
            if mutation == "missing":
                after["exact_file_hashes"]["SECURITY.md"] = {"kind": "missing"}
            else:
                after["exact_file_hashes"]["SECURITY.md"]["sha256"] = "f" * 64
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                    ReleaseGateError, "exact target"):
                verify_target_convergence(target_state(), evidence)

    def test_other_role_changes_are_not_normalized(self):
        evidence = sources()
        evidence[0]["apply"]["product_state"]["after"]["instance_role"] = "rival"
        with self.assertRaisesRegex(ReleaseGateError, "exact target"):
            verify_target_convergence(target_state(), evidence)

    def test_missing_legal_surface_and_mutating_dry_run_fail(self):
        target = target_state()
        del target["exact_file_hashes"]["LICENSE.md"]
        with self.assertRaisesRegex(ReleaseGateError, "legal/root"):
            verify_target_convergence(target, sources())
        evidence = sources()
        evidence[0]["dry_run"]["product_state"]["after"] = target_state()
        with self.assertRaisesRegex(ReleaseGateError, "dry-run changed"):
            verify_target_convergence(target_state(), evidence)

    def test_source_check_must_be_clean_bound_and_scope_honest(self):
        evidence = source_check()
        evidence["report"]["info"]["runtime_certification"] = "CERTIFIED"
        with self.assertRaisesRegex(ReleaseGateError, "overclaims"):
            verify_source_check(evidence, TARGET)
        evidence = source_check()
        evidence["target_commit"] = SOURCE
        with self.assertRaisesRegex(ReleaseGateError, "bound"):
            verify_source_check(evidence, TARGET)

    def test_only_exact_generic_master_advisory_set_is_reconciled(self):
        evidence = source_check()
        evidence["report"]["warnings"] = sorted(GENERIC_MASTER_SOURCE_ADVISORIES)
        evidence["report"]["info"].update({
            "health (mechanical)": "PASS — 0 errors, 11 warnings",
            "  health.validate": "0 errors, 10 warnings",
            "  health.pack-check": "0 errors, 1 warnings",
        })
        self.assertTrue(verify_source_check(evidence, TARGET)["passed"])

        for mutation in ("new warning", None):
            changed = source_check()
            warnings = sorted(GENERIC_MASTER_SOURCE_ADVISORIES)
            if mutation is None:
                warnings.pop()
            else:
                warnings.append(mutation)
            changed["report"]["warnings"] = warnings
            changed["report"]["info"].update({
                "health (mechanical)": "PASS — 0 errors, 11 warnings",
                "  health.validate": "0 errors, 10 warnings",
                "  health.pack-check": "0 errors, 1 warnings",
            })
            with self.assertRaisesRegex(ReleaseGateError, "not a clean"):
                verify_source_check(changed, TARGET)

        changed = source_check()
        changed["report"]["warnings"] = sorted(GENERIC_MASTER_SOURCE_ADVISORIES)
        changed["report"]["info"].update({
            "health (mechanical)": "PASS — 0 errors, 11 warnings",
            "  health.validate": "1 errors, 10 warnings",
            "  health.pack-check": "0 errors, 1 warnings",
        })
        with self.assertRaisesRegex(ReleaseGateError, "not a clean"):
            verify_source_check(changed, TARGET)

    def test_fault_matrix_requires_every_case_and_rejects_hybrid(self):
        evidence = fault_evidence()
        evidence["cases"].pop()
        with self.assertRaisesRegex(ReleaseGateError, "incomplete"):
            verify_fault_evidence(evidence, TARGET)
        evidence = fault_evidence()
        evidence["cases"][0]["classification"] = "hybrid"
        with self.assertRaisesRegex(ReleaseGateError, "hybrid"):
            verify_fault_evidence(evidence, TARGET)

    def test_recovery_requires_both_modes_and_exact_issued_argv(self):
        evidence = recovery_evidence()
        evidence["records"].pop()
        with self.assertRaisesRegex(ReleaseGateError, "both"):
            verify_recovery_evidence(evidence, TARGET)
        evidence = recovery_evidence()
        evidence["records"][0]["executed_argv"][-1] = "/tmp/other"
        with self.assertRaisesRegex(ReleaseGateError, "exact product-issued"):
            verify_recovery_evidence(evidence, TARGET)

    def test_harness_inferred_command_is_not_accepted_as_product_evidence(self):
        evidence = recovery_evidence()
        del evidence["records"][0]["product_issued_command"]
        with self.assertRaisesRegex(ReleaseGateError, "nonempty string"):
            verify_recovery_evidence(evidence, TARGET)


if __name__ == "__main__":
    unittest.main()
