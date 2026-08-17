"""Focused tests for child-process release fault injection."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import textwrap
import unittest


VAULT = Path(__file__).resolve().parents[3]
FIXTURE_MODULES = VAULT / "System" / "Tests" / "release_qualification"
sys.path.insert(0, str(FIXTURE_MODULES))

import fault_injection as fi  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


class FakeUpgrade:
    """Small call graph with the same patch surfaces as the real upgrade."""

    def __init__(self, outer: str) -> None:
        self.outer = Path(outer)
        self.scripts = self.outer / "scripts"
        self.vault = self.outer / "fixture"
        self.release = self.outer / "release"
        self.vault.mkdir()
        self.release.mkdir()
        self._build_modules()
        self._build_tree()
        fi.arm_fault_target(self.vault)

    def _build_modules(self) -> None:
        _write(self.scripts / "cmd" / "__init__.py", "")
        _write(
            self.scripts / "cmd" / "checkpoint.py",
            """
            def run(root, args, rep):
                open(root + "/checkpoint.marker", "w").write("checkpoint")
            """,
        )
        _write(
            self.scripts / "cmd" / "generate.py",
            """
            def run(root, args, rep):
                open(root + "/generation.marker", "w").write("generated")
            """,
        )
        _write(
            self.scripts / "cmd" / "validate.py",
            """
            def run(root, args, rep):
                open(root + "/validation.marker", "w").write("validated")
            """,
        )
        _write(
            self.scripts / "cmd" / "upgrade.py",
            """
            import os
            import shutil
            from cmd import checkpoint as ckpt_mod

            def _classify(root, release, base=None, derived=None):
                open(root + "/classification.marker", "w").write("classified")
                return {}

            def run(root, args, rep):
                _classify(root, args.target)
                ckpt_mod.run(root, args, rep)
                shutil.copyfile(
                    os.path.join(args.target, "copy-source.txt"),
                    os.path.join(root, "copied.txt"),
                )
                os.remove(os.path.join(root, "delete-me.txt"))
                os.rmdir(os.path.join(root, "remove-dir"))
                shutil.copyfile(
                    os.path.join(args.target, ".baseline-manifest.json"),
                    os.path.join(root, "System", ".baseline-manifest.json"),
                )
                from cmd import generate, validate
                generate.run(root, args, rep)
                validate.run(root, args, rep)
                open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w").write("new")
                open(
                    os.path.join(root, "System", "Logs", "upgrade-report-fixed.md"),
                    "w",
                ).write("report")
            """,
        )
        _write(
            self.scripts / "aios.py",
            """
            import argparse
            from cmd import upgrade

            def main(argv=None):
                parser = argparse.ArgumentParser()
                parser.add_argument("command")
                parser.add_argument("target")
                parser.add_argument("--root", required=True)
                args = parser.parse_args(argv)
                upgrade.run(args.root, args, object())
                return 0
            """,
        )

    def _build_tree(self) -> None:
        _write(self.release / "copy-source.txt", "copied")
        _write(self.release / ".baseline-manifest.json", "new baseline")
        _write(self.vault / "delete-me.txt", "delete")
        (self.vault / "remove-dir").mkdir()
        _write(self.vault / "SYSTEM-MANIFEST.yaml", "old")
        _write(self.vault / "System" / ".baseline-manifest.json", "old baseline")
        (self.vault / "System" / "Logs").mkdir(parents=True)

    def run(self, hook: str, phase: str, target: Path | None = None) -> fi.FaultRun:
        spec = fi.FaultSpec(
            hook=hook,
            phase=phase,
            vault_root=str(self.vault),
            target_path=str(target) if target is not None else None,
        )
        return fi.run_aios_with_fault(
            self.scripts,
            ["upgrade", str(self.release), "--root", str(self.vault)],
            spec,
        )


class TestFaultInjection(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def fixture(self) -> FakeUpgrade:
        return FakeUpgrade(self.temp.name)

    def assertInterrupted(self, result: fi.FaultRun) -> None:
        self.assertEqual(result.returncode, fi.ABRUPT_EXIT_CODE, result.stderr)
        self.assertTrue(result.interrupted)

    def test_classification_before_and_after_have_distinct_mutation_semantics(self):
        before = self.fixture()
        result = before.run("classification", "before")
        self.assertInterrupted(result)
        self.assertFalse((before.vault / "classification.marker").exists())

        after_root = Path(self.temp.name) / "after"
        after_root.mkdir()
        after = FakeUpgrade(str(after_root))
        result = after.run("classification", "after")
        self.assertInterrupted(result)
        self.assertEqual(
            (after.vault / "classification.marker").read_text(encoding="utf-8"),
            "classified",
        )
        self.assertFalse((after.vault / "checkpoint.marker").exists())

    def test_filtered_copy_before_and_after_leave_parent_inspectable(self):
        before = self.fixture()
        target = before.vault / "copied.txt"
        result = before.run("copy", "before", target)
        self.assertInterrupted(result)
        self.assertFalse(target.exists())

        after_root = Path(self.temp.name) / "after-copy"
        after_root.mkdir()
        after = FakeUpgrade(str(after_root))
        target = after.vault / "copied.txt"
        result = after.run("copy", "after", target)
        self.assertInterrupted(result)
        self.assertEqual(target.read_text(encoding="utf-8"), "copied")
        self.assertTrue((after.vault / "delete-me.txt").exists())

    def test_delete_and_rmdir_are_exact_path_scoped(self):
        delete = self.fixture()
        result = delete.run(
            "delete", "after", delete.vault / "delete-me.txt"
        )
        self.assertInterrupted(result)
        self.assertFalse((delete.vault / "delete-me.txt").exists())
        self.assertTrue((delete.vault / "remove-dir").exists())

        rmdir_root = Path(self.temp.name) / "rmdir"
        rmdir_root.mkdir()
        rmdir = FakeUpgrade(str(rmdir_root))
        result = rmdir.run("rmdir", "before", rmdir.vault / "remove-dir")
        self.assertInterrupted(result)
        self.assertTrue((rmdir.vault / "remove-dir").exists())

    def test_named_boundaries_interrupt_at_checkpoint_baseline_generation_validation(self):
        cases = [
            ("checkpoint", "checkpoint.marker", None),
            (
                "baseline-replacement",
                "System/.baseline-manifest.json",
                "new baseline",
            ),
            ("generation", "generation.marker", None),
            ("validation", "validation.marker", None),
        ]
        for index, (hook, relative, expected) in enumerate(cases):
            with self.subTest(hook=hook):
                parent = Path(self.temp.name) / f"case-{index}"
                parent.mkdir()
                fixture = FakeUpgrade(str(parent))
                result = fixture.run(hook, "after")
                self.assertInterrupted(result)
                path = fixture.vault / relative
                self.assertTrue(path.exists())
                if expected is not None:
                    self.assertEqual(path.read_text(encoding="utf-8"), expected)

    def test_version_and_report_writes_are_durable_before_after_boundaries(self):
        before = self.fixture()
        result = before.run("version-bump", "before")
        self.assertInterrupted(result)
        self.assertEqual(
            (before.vault / "SYSTEM-MANIFEST.yaml").read_text(encoding="utf-8"),
            "old",
        )

        version_root = Path(self.temp.name) / "version-after"
        version_root.mkdir()
        version = FakeUpgrade(str(version_root))
        result = version.run("version-bump", "after")
        self.assertInterrupted(result)
        self.assertEqual(
            (version.vault / "SYSTEM-MANIFEST.yaml").read_text(encoding="utf-8"),
            "new",
        )

        report_root = Path(self.temp.name) / "report-after"
        report_root.mkdir()
        report = FakeUpgrade(str(report_root))
        result = report.run("report-write", "after")
        self.assertInterrupted(result)
        self.assertEqual(
            (
                report.vault
                / "System"
                / "Logs"
                / "upgrade-report-fixed.md"
            ).read_text(encoding="utf-8"),
            "report",
        )

    def test_unscoped_global_hooks_and_cleanup_claims_are_rejected(self):
        root_path = Path(self.temp.name) / "vault"
        root_path.mkdir()
        root = str(root_path)
        for hook in ("copy", "delete", "rmdir"):
            with self.subTest(hook=hook):
                with self.assertRaisesRegex(
                    fi.FaultInjectionError, "unscoped/global"
                ):
                    fi.FaultSpec(hook, "before", root)
        with self.assertRaisesRegex(
            fi.FaultInjectionError,
            fi.CLEANUP_COVERAGE,
        ):
            fi.FaultSpec("cleanup", "before", root)
        self.assertEqual(
            fi.CLEANUP_COVERAGE,
            "unavailable-no-production-boundary",
        )

    def test_every_named_boundary_supports_true_before_and_after(self):
        expected = {
            "classification": ("classification.marker", None, "classified", None),
            "checkpoint": ("checkpoint.marker", None, "checkpoint", None),
            "copy": ("copied.txt", None, "copied", "copied.txt"),
            "delete": ("delete-me.txt", "delete", None, "delete-me.txt"),
            "rmdir": ("remove-dir", "directory", None, "remove-dir"),
            "baseline-replacement": (
                "System/.baseline-manifest.json",
                "old baseline",
                "new baseline",
                None,
            ),
            "generation": ("generation.marker", None, "generated", None),
            "validation": ("validation.marker", None, "validated", None),
            "version-bump": ("SYSTEM-MANIFEST.yaml", "old", "new", None),
            "report-write": (
                "System/Logs/upgrade-report-fixed.md",
                None,
                "report",
                None,
            ),
        }
        self.assertEqual(set(expected), set(fi.HOOKS))
        case = 0
        for hook, (relative, before_value, after_value, scoped) in expected.items():
            for phase in ("before", "after"):
                with self.subTest(hook=hook, phase=phase):
                    parent = Path(self.temp.name) / f"all-{case}"
                    case += 1
                    parent.mkdir()
                    fixture = FakeUpgrade(str(parent))
                    target = fixture.vault / scoped if scoped else None
                    result = fixture.run(hook, phase, target)
                    self.assertInterrupted(result)
                    path = fixture.vault / relative
                    wanted = before_value if phase == "before" else after_value
                    if wanted is None:
                        self.assertFalse(path.exists())
                    elif wanted == "directory":
                        self.assertTrue(path.is_dir())
                    else:
                        self.assertEqual(path.read_text(encoding="utf-8"), wanted)

    def test_refuses_unarmed_source_overlap_and_symlink_scopes(self):
        fixture = self.fixture()
        marker = fixture.vault / fi.FAULT_TARGET_MARKER
        marker.unlink()
        spec = fi.FaultSpec("classification", "before", str(fixture.vault))
        with self.assertRaisesRegex(fi.FaultInjectionError, "unarmed"):
            fi.run_aios_with_fault(fixture.scripts, [], spec)

        fi.arm_fault_target(fixture.vault)
        with self.assertRaisesRegex(fi.FaultInjectionError, "separate trees"):
            fi.run_aios_with_fault(
                fixture.vault,
                [],
                fi.FaultSpec("classification", "before", str(fixture.vault)),
            )

        if hasattr(Path, "symlink_to"):
            real = Path(self.temp.name) / "real-vault"
            real.mkdir()
            linked = Path(self.temp.name) / "linked-vault"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(fi.FaultInjectionError, "symlinks"):
                fi.FaultSpec("classification", "before", str(linked))


if __name__ == "__main__":
    unittest.main()
