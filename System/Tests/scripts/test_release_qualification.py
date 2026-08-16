"""Integration tests for the historical release qualification orchestrator."""

from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml


VAULT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(VAULT / "System" / "Tests"))

from release_qualification import qualify  # noqa: E402
from release_qualification.support_matrix import (  # noqa: E402
    MatrixError,
    load_support_matrix,
)


FAKE_CLI = r'''#!/usr/bin/env python3
import pathlib
import json
import re
import shlex
import subprocess
import sys

root = pathlib.Path(sys.argv[sys.argv.index("--root") + 1])
if sys.argv[1] == "rollback":
    rollback_ref = sys.argv[2]
    if not (root / ".git").exists():
        manifest = root / "SYSTEM-MANIFEST.yaml"
        manifest.write_text(re.sub(r"(system_version:\s*)\S+", r"\g<1>1.43.0",
                                   manifest.read_text(encoding="utf-8"), count=1),
                            encoding="utf-8")
        raise SystemExit(0)
    subprocess.run(
        ["git", "-C", str(root), "reset", "--hard", rollback_ref],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "clean", "-fd"],
        check=True,
        capture_output=True,
    )
    print("fake rollback")
    raise SystemExit(0)
if "--dry-run" in sys.argv:
    if (pathlib.Path(__file__).parents[2] / "MUTATE-DRY-RUN").exists():
        (root / "DRY-RUN-MUTATION.txt").write_text("unsafe\n", encoding="utf-8")
    print(json.dumps({"command":"upgrade","ok":True,"errors":[],"warnings":[],"info":{}}))
    raise SystemExit(0)
if "--apply" not in sys.argv:
    print(json.dumps({"command":"upgrade","ok":True,"errors":[],"warnings":[],
                      "info":{"review_sha256":"b" * 64}}))
    raise SystemExit(0)
assert sys.argv[sys.argv.index("--review-sha256") + 1] == "b" * 64
if (root / "DRY-RUN-MUTATION.txt").exists():
    print("dry-run fixture was reused", file=sys.stderr)
    raise SystemExit(9)
manifest = root / "SYSTEM-MANIFEST.yaml"
text = manifest.read_text(encoding="utf-8")
text = re.sub(
    r"(system_version:\s*)\S+",
    r"\g<1>1.64.0",
    text,
    count=1,
)
manifest.write_text(text, encoding="utf-8")
rollback_target = (subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=True).stdout.strip()
                   if (root / ".git").exists() else "snapshot.zip")
rollback = shlex.join([sys.executable, str(pathlib.Path(__file__)), "rollback", rollback_target,
                       "--expected-sha256", "a" * 64, "--confirm", "--root", str(root)])
print(json.dumps({"command":"upgrade","ok":True,"errors":[],"warnings":[],
                  "info":{"rollback_command":rollback}}))
'''


def git(repo: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return process.stdout.strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class FakeReleaseRepository:
    def __init__(self, root: Path, *, mutate_dry_run: bool = False):
        self.repo = root / "Source Repository Ω"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Qualification Tests")
        git(self.repo, "config", "user.email", "tests@example.invalid")
        self._manifest("1.43.0")
        write(
            self.repo / "System" / "Runtime" / "Task Router.yaml",
            "id: doc-task-router\nmodes: {}\nfallback: {}\n",
        )
        write(
            self.repo / "System" / "Journal" / "change-journal.md",
            "# Change journal\n\n- historical state\n",
        )
        write(self.repo / "README.md", "# Fake source release\n")
        self.source = self._commit_release("source 1.43.0")
        git(self.repo, "tag", "v1.43.0", self.source)

        self._manifest("1.64.0")
        write(
            self.repo / "System" / "Scripts" / "aios.py",
            FAKE_CLI,
        )
        if mutate_dry_run:
            write(self.repo / "MUTATE-DRY-RUN", "true\n")
        write(self.repo / "README.md", "# Fake target release\n")
        self.target = self._commit_release("target 1.64.0")

    def _manifest(self, version: str) -> None:
        write(
            self.repo / "SYSTEM-MANIFEST.yaml",
            "system:\n"
            "  name: Personal AI OS\n"
            "  instance_role: generic-master\n"
            f"  system_version: {version}\n",
        )

    def _commit_release(self, message: str) -> str:
        files = {}
        for path in sorted(self.repo.rglob("*")):
            if (not path.is_file() or ".git" in path.parts
                    or path.name == ".baseline-manifest.json"):
                continue
            relative = path.relative_to(self.repo).as_posix()
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        version = yaml.safe_load(
            (self.repo / "SYSTEM-MANIFEST.yaml").read_text(encoding="utf-8")
        )["system"]["system_version"]
        write(
            self.repo / "System" / ".baseline-manifest.json",
            json.dumps({
                "system_version": version,
                "files": files,
                "derived": {},
            }, indent=2, sort_keys=True) + "\n",
        )
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", message)
        return git(self.repo, "rev-parse", "HEAD")

    def matrix(self, path: Path, *, fixture_mode: str = "clean-git",
               source_commit: str | None = None) -> Path:
        document = {
            "schema_version": 1,
            "target": {
                "ref": self.target,
                "commit": self.target,
                "version": "1.64.0",
            },
            "sources": [{
                "id": "official-1.43.0",
                "ref": "v1.43.0",
                "commit": source_commit or self.source,
                "version": "1.43.0",
                "disposition": "candidate-direct",
                "fixture_mode": fixture_mode,
                "accepted_paths": [
                    "System/Runtime/Task Router.yaml",
                ],
            }],
        }
        path.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        return path


class QualificationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="qualification test Ω ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "Evidence Output Ω"
        self.work = self.root / "Disposable Work Ω"
        self.output.mkdir()
        self.work.mkdir()

    def run_qualification(self, history: FakeReleaseRepository,
                          matrix: Path) -> dict:
        return qualify.qualify_matrix(
            history.repo,
            matrix,
            self.output,
            self.work,
            timeout_seconds=10,
        )


class TestSupportMatrix(QualificationTestCase):
    def test_loader_defaults_clean_git_and_is_round_trip_serializable(self):
        history = FakeReleaseRepository(self.root)
        matrix_path = history.matrix(self.root / "matrix.yaml")
        document = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
        del document["sources"][0]["fixture_mode"]
        matrix_path.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

        loaded = load_support_matrix(matrix_path)

        self.assertEqual("clean-git", loaded.sources[0].fixture_mode)
        self.assertFalse(loaded.sources[0].authorize_legacy_core)
        json.dumps(loaded.to_dict())

    def test_loader_accepts_explicit_legacy_core_authorization(self):
        history = FakeReleaseRepository(self.root)
        matrix_path = history.matrix(self.root / "matrix.yaml")
        document = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
        document["sources"][0]["authorize_legacy_core"] = True
        matrix_path.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

        loaded = load_support_matrix(matrix_path)

        self.assertTrue(loaded.sources[0].authorize_legacy_core)

    def test_loader_refuses_legacy_authorization_for_unsupported_source(self):
        history = FakeReleaseRepository(self.root)
        matrix_path = history.matrix(self.root / "matrix.yaml")
        document = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
        document["sources"][0]["disposition"] = "not-supported"
        document["sources"][0]["authorize_legacy_core"] = True
        matrix_path.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

        with self.assertRaisesRegex(MatrixError, "unsupported source"):
            load_support_matrix(matrix_path)

    def test_loader_rejects_unpinned_and_duplicate_sources(self):
        history = FakeReleaseRepository(self.root)
        matrix_path = history.matrix(self.root / "matrix.yaml")
        document = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
        document["sources"].append(dict(document["sources"][0]))
        matrix_path.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        with self.assertRaisesRegex(MatrixError, "duplicate ids"):
            load_support_matrix(matrix_path)

        del document["sources"][1]
        document["sources"][0]["commit"] = "moving-branch"
        matrix_path.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        with self.assertRaisesRegex(MatrixError, "full lowercase SHA-1"):
            load_support_matrix(matrix_path)

        document["sources"][0]["commit"] = history.source
        document["sources"][0]["accepted_paths"] = ["../outside"]
        matrix_path.write_text(
            yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        with self.assertRaisesRegex(MatrixError, "contained relative paths"):
            load_support_matrix(matrix_path)


class TestQualificationOrchestration(QualificationTestCase):
    def make_root_target(self, history: FakeReleaseRepository) -> tuple[Path, Path]:
        target = self.root / "Clean Public Target Ω"
        target.mkdir()
        archive = subprocess.run(
            ["git", "-C", str(history.repo), "archive", history.target],
            capture_output=True, check=True).stdout
        qualify.fixture._extract_archive(archive, target)
        git(target, "init", "-q")
        git(target, "config", "user.name", "Qualification Tests")
        git(target, "config", "user.email", "tests@example.invalid")
        git(target, "add", "-A")
        git(target, "commit", "-qm", "clean public root")
        target_commit = git(target, "rev-parse", "HEAD")
        matrix = history.matrix(self.root / "split-matrix.yaml")
        document = yaml.safe_load(matrix.read_text(encoding="utf-8"))
        document["target"]["ref"] = target_commit
        document["target"]["commit"] = target_commit
        matrix.write_text(yaml.safe_dump(document, sort_keys=False),
                          encoding="utf-8")
        return target, matrix

    def test_disjoint_root_target_and_historical_repository_qualify(self):
        history = FakeReleaseRepository(self.root)
        target, matrix = self.make_root_target(history)

        result = qualify.qualify_matrix(
            target, matrix, self.output, self.work,
            source_repository=history.repo, timeout_seconds=10)

        self.assertEqual("passed", result["verdict"])
        self.assertTrue(result["source_repository_unchanged"])
        self.assertTrue(result["historical_repository_unchanged"])
        encoded = json.dumps(result)
        self.assertNotIn(str(history.repo), encoded)
        self.assertNotIn(str(target), encoded)

    def test_mutating_either_split_repository_fails_closed(self):
        history = FakeReleaseRepository(self.root)
        target, matrix = self.make_root_target(history)
        original = qualify._phase
        calls = 0

        def mutating_phase(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                write(history.repo / "UNAUTHORIZED-MUTATION", "changed\n")
            return result

        with mock.patch.object(qualify, "_phase", side_effect=mutating_phase):
            with self.assertRaisesRegex(
                    qualify.QualificationError, "historical repository changed"):
                qualify.qualify_matrix(
                    target, matrix, self.output, self.work,
                    source_repository=history.repo, timeout_seconds=10)

    def test_clean_git_qualifies_fresh_dry_and_apply_fixtures(self):
        history = FakeReleaseRepository(self.root)
        matrix = history.matrix(self.root / "matrix.yaml")
        before = {
            "head": git(history.repo, "rev-parse", "HEAD"),
            "status": git(history.repo, "status", "--porcelain=v1"),
            "refs": git(history.repo, "show-ref"),
        }

        result = self.run_qualification(history, matrix)

        self.assertEqual("passed", result["verdict"])
        self.assertTrue(result["source_repository_unchanged"])
        self.assertEqual(
            "1.64.0", result["target"]["product_state"]["system_version"]
        )
        source = result["sources"][0]
        self.assertTrue(source["qualified"])
        self.assertTrue(source["upgrade_qualified"])
        self.assertTrue(source["recovery_qualified"])
        self.assertNotEqual(
            source["dry_run"]["fixture_paths"]["instance"],
            source["apply"]["fixture_paths"]["instance"],
        )
        for phase in ("dry_run", "apply"):
            evidence = source[phase]
            self.assertIn(" ", evidence["fixture_paths"]["instance"])
            self.assertIn("Ω", evidence["fixture_paths"]["instance"])
            self.assertTrue(
                evidence["protected_surfaces"]["seeded_paths_preserved"])
            self.assertIsNotNone(evidence["git"]["before"]["head"])
            self.assertEqual(
                evidence["git"]["before"]["head"],
                evidence["git"]["after"]["head"],
            )
            self.assertTrue(Path(evidence["evidence_path"]).is_file())
            self.assertTrue(
                Path(evidence["runner_evidence_path"]).is_file())
        self.assertEqual(
            source["dry_run"]["git"]["before"]["head"],
            source["apply"]["git"]["before"]["head"],
            "fixed fixture commit metadata should produce deterministic HEADs",
        )
        self.assertEqual(
            "dry-run-passed",
            source["dry_run"]["runner"]["phase_verdict"]["code"],
        )
        self.assertEqual(
            "apply-complete",
            source["apply"]["runner"]["phase_verdict"]["code"],
        )
        self.assertEqual(
            result["target"]["product_state"]["system_version"],
            source["apply"]["product_state"]["after"]["system_version"],
        )
        recovery = source["recovery"]
        self.assertEqual("recovery-passed", recovery["status"])
        self.assertEqual(0, recovery["returncode"])
        self.assertEqual(
            recovery["before_tree_sha256"], recovery["after_tree_sha256"])
        self.assertEqual(
            "harness-captured-pre-apply-head",
            recovery["rollback_target"]["origin"],
        )
        self.assertFalse(recovery["rollback_target"]["product_generated"])
        self.assertEqual(
            source["apply"]["git"]["before"]["head"],
            recovery["rollback_target"]["value"],
        )
        self.assertTrue(Path(recovery["evidence_path"]).is_file())
        self.assertTrue((self.output / "qualification.json").is_file())
        summary = (self.output / "qualification.md").read_text(encoding="utf-8")
        self.assertIn("Overall verdict: **PASSED**", summary)
        after = {
            "head": git(history.repo, "rev-parse", "HEAD"),
            "status": git(history.repo, "status", "--porcelain=v1"),
            "refs": git(history.repo, "show-ref"),
        }
        self.assertEqual(before, after)

    def test_dry_run_mutation_cannot_contaminate_fresh_no_git_apply(self):
        history = FakeReleaseRepository(self.root, mutate_dry_run=True)
        matrix = history.matrix(
            self.root / "matrix.yaml", fixture_mode="no-git")

        result = self.run_qualification(history, matrix)

        self.assertEqual("failed", result["verdict"])
        source = result["sources"][0]
        self.assertEqual(
            "dry-run-mutated",
            source["dry_run"]["runner"]["phase_verdict"]["code"],
        )
        self.assertEqual(
            "apply-complete",
            source["apply"]["runner"]["phase_verdict"]["code"],
            "apply must use a fresh fixture without the dry-run mutation",
        )
        self.assertIsNone(source["dry_run"]["git"]["before"]["head"])
        self.assertIsNone(source["apply"]["git"]["after"]["head"])
        self.assertEqual("recovery-passed", source["recovery"]["status"])
        self.assertTrue(source["recovery_qualified"])
        apply_changes = source["apply"]["runner"]["tree"]["changes"]
        self.assertNotIn("DRY-RUN-MUTATION.txt", apply_changes["added"])

    def test_successful_no_git_upgrade_proves_product_issued_recovery(self):
        history = FakeReleaseRepository(self.root)
        matrix = history.matrix(
            self.root / "matrix.yaml", fixture_mode="no-git")

        result = self.run_qualification(history, matrix)

        source = result["sources"][0]
        self.assertTrue(source["upgrade_qualified"])
        self.assertTrue(source["recovery_qualified"])
        self.assertTrue(source["qualified"])
        self.assertEqual("passed", result["verdict"])
        self.assertEqual("recovery-passed", source["recovery"]["status"])
        self.assertEqual(
            source["recovery"]["executed_argv"],
            shlex.split(source["recovery"]["product_issued_command"]),
        )
        self.assertTrue(Path(source["recovery"]["evidence_path"]).is_file())

    def test_pin_mismatch_fails_before_any_fixture_run(self):
        history = FakeReleaseRepository(self.root)
        wrong = "0" * 40
        matrix = history.matrix(
            self.root / "matrix.yaml", source_commit=wrong)
        before = git(history.repo, "status", "--porcelain=v1")

        with self.assertRaisesRegex(
                qualify.QualificationError, "pinned commit/version"):
            self.run_qualification(history, matrix)

        self.assertEqual([], list(self.output.iterdir()))
        self.assertEqual(
            before, git(history.repo, "status", "--porcelain=v1"))

    def test_direct_cli_emits_paths_and_success_status(self):
        history = FakeReleaseRepository(self.root)
        matrix = history.matrix(self.root / "matrix.yaml")
        script = (
            VAULT / "System" / "Tests" / "release_qualification" / "qualify.py")

        process = subprocess.run(
            [
                sys.executable,
                str(script),
                "--repository", str(history.repo),
                "--matrix", str(matrix),
                "--output-dir", str(self.output),
                "--work-root", str(self.work),
                "--timeout-seconds", "10",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, process.returncode, process.stderr)
        response = json.loads(process.stdout)
        self.assertEqual("passed", response["verdict"])
        self.assertTrue(Path(response["qualification"]).is_file())
        self.assertTrue(Path(response["summary"]).is_file())


if __name__ == "__main__":
    unittest.main()
