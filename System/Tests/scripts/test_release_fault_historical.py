"""Real-history interruption and rerun coverage for release qualification."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


VAULT = Path(__file__).resolve().parents[3]
MODULES = VAULT / "System" / "Tests" / "release_qualification"
sys.path.insert(0, str(MODULES))

import fault_injection as faults  # noqa: E402
import fixture  # noqa: E402
import runner  # noqa: E402


SOURCE_160 = "528da66e5d58708c920acf05e6bcacac2fd74cde"
TARGET_164 = "4e54eefdec1f1ca7e0096e2d2407917ad863f3b7"


def authority_repository() -> Path:
    raw = os.environ.get("AIOS_SOURCE_AUTHORITY_REPOSITORY")
    pin = os.environ.get("AIOS_SOURCE_AUTHORITY_COMMIT")
    if not raw or not pin:
        raise RuntimeError("strict historical authority environment is required")
    repository = Path(raw)
    resolved = git(repository, "rev-parse", "--verify", "--end-of-options",
                   f"{pin}^{{commit}}").strip()
    if resolved != pin:
        raise RuntimeError("strict historical authority pin does not resolve exactly")
    return repository


def git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return process.stdout


def source_state(repository: Path) -> tuple[str, str, str, str]:
    return (
        git(repository, "rev-parse", "HEAD"),
        git(repository, "status", "--porcelain=v1", "--untracked-files=all"),
        git(repository, "show-ref"),
        git(repository, "worktree", "list", "--porcelain"),
    )


@unittest.skipIf(
    os.environ.get("AIOS_PUBLIC_CI") == "1",
    "release qualification requires the separately pinned historical authority",
)
class TestHistoricalInterruptionAndRerun(unittest.TestCase):
    def test_real_160_copy_interruption_then_rerun_stays_inspectable(self):
        authority = authority_repository()
        before_source = source_state(authority)
        with tempfile.TemporaryDirectory(
            prefix="historical fault rerun Ω "
        ) as temporary:
            root = Path(temporary)
            instance = root / "1.60 Interrupted Instance Ω"
            target = root / "1.64 Target Release Ω"
            scratch = root / "Rerun Scratch Ω"
            reports = root / "Rerun Evidence Ω"
            for path in (instance, target, scratch, reports):
                path.mkdir()

            fixture.build_historical_instance(authority, SOURCE_160, instance)
            fixture._extract_archive(
                fixture._git_archive(authority, TARGET_164),
                target,
            )
            faults.arm_fault_target(instance)

            git(instance, "init", "-q", "-b", "qualification")
            git(
                instance,
                "-c",
                "user.name=Release Qualification",
                "-c",
                "user.email=qualification@example.invalid",
                "add",
                "-A",
            )
            git(
                instance,
                "-c",
                "user.name=Release Qualification",
                "-c",
                "user.email=qualification@example.invalid",
                "commit",
                "-qm",
                "interruption fixture baseline",
            )

            copied_path = instance / "README.md"
            before_readme = copied_path.read_bytes()
            target_readme = (target / "README.md").read_bytes()
            self.assertNotEqual(before_readme, target_readme)
            interrupted = faults.run_aios_with_fault(
                target / "System" / "Scripts",
                [
                    "upgrade",
                    str(target),
                    "--root",
                    str(instance),
                    "--accept",
                    "System/Runtime/Task Router.yaml",
                ],
                faults.FaultSpec(
                    hook="copy",
                    phase="after",
                    vault_root=str(instance),
                    target_path=str(copied_path),
                ),
                timeout=60,
            )

            self.assertTrue(interrupted.interrupted, interrupted.stderr)
            self.assertEqual(target_readme, copied_path.read_bytes())
            self.assertEqual(
                "1.60.0",
                runner._manifest_version(instance),
                "the interruption must leave the historical version in place",
            )

            rerun = runner.run_upgrade(
                instance,
                target,
                scratch,
                reports,
                run_id="real-1.60-after-copy-interruption",
                timeout_seconds=120,
                extra_args=(
                    "--accept",
                    "System/Runtime/Task Router.yaml",
                ),
            )

            self.assertEqual("apply", rerun["mode"])
            self.assertEqual("apply-hybrid", rerun["phase_verdict"]["code"])
            self.assertEqual("unsafe", rerun["phase_verdict"]["status"])
            self.assertEqual("1.60.0", rerun["versions"]["after"])
            self.assertTrue(Path(rerun["evidence_path"]).is_file())

        self.assertEqual(before_source, source_state(authority))


if __name__ == "__main__":
    unittest.main()
