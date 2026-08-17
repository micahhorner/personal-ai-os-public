"""Wave 3 qualification for an atomic transactional-upgrade contract."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import types
import unittest
from unittest import mock


VAULT = Path(__file__).resolve().parents[3]
HARNESS_DIR = VAULT / "System" / "Tests" / "release_qualification"
sys.path.insert(0, str(HARNESS_DIR))
import transaction_faults as tf  # noqa: E402


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


FAKE_UPGRADE = r'''
from pathlib import Path
import os
import shutil

BOUNDARIES = (
    "checkpoint", "plan", "candidate-copy", "candidate-delete",
    "baseline-replacement", "generation", "validation", "version-bump",
    "report-write", "commit-swap", "cleanup",
)

def _transaction_boundary(name, phase, root):
    if name not in BOUNDARIES or phase not in ("before", "after"):
        raise ValueError("invalid boundary")

def _free_bytes(path):
    return shutil.disk_usage(str(path)).free

def _same_filesystem(a, b):
    return os.stat(str(a)).st_dev == os.stat(str(b)).st_dev

def _step(name, root, operation):
    _transaction_boundary(name, "before", str(root))
    operation()
    _transaction_boundary(name, "after", str(root))

def run(root, args, rep):
    live = Path(root)
    parent = live.parent
    candidate = parent / (live.name + ".candidate")
    previous = parent / (live.name + ".previous")
    checkpoint = parent / (live.name + ".checkpoint")
    plan = parent / (live.name + ".plan")

    required = sum(p.stat().st_size for p in live.rglob("*") if p.is_file())
    if _free_bytes(parent) < required:
        raise RuntimeError("insufficient staging space")
    probe = parent / (live.name + ".filesystem-probe")
    probe.mkdir(exist_ok=False)
    try:
        if not _same_filesystem(live, probe):
            raise RuntimeError("candidate staging crosses filesystems")
    finally:
        probe.rmdir()

    _step("checkpoint", live, lambda: checkpoint.write_text("saved\n"))
    _step("plan", live, lambda: plan.write_text("planned\n"))
    _step("candidate-copy", live, lambda: shutil.copytree(live, candidate))
    _step("candidate-delete", live, lambda: (candidate / "System" / "old.txt").unlink())
    _step(
        "baseline-replacement",
        live,
        lambda: (candidate / "System" / ".baseline-manifest.json").write_text("new baseline\n"),
    )
    _step(
        "generation",
        live,
        lambda: (candidate / "System" / "Generated" / "index.txt").write_text("new generated\n"),
    )
    _step(
        "validation",
        live,
        lambda: (candidate / "System" / "validation.ok").write_text("valid\n"),
    )
    _step(
        "version-bump",
        live,
        lambda: (candidate / "SYSTEM-MANIFEST.yaml").write_text("system_version: 2.0.0\n"),
    )
    _step(
        "report-write",
        live,
        lambda: (candidate / "System" / "Logs" / "upgrade-report.md").write_text("complete\n"),
    )

    def swap():
        if previous.exists():
            shutil.rmtree(previous)
        os.rename(live, previous)
        try:
            os.rename(candidate, live)
        except BaseException:
            os.rename(previous, live)
            raise
    _step("commit-swap", live, swap)
    _step("cleanup", live, lambda: shutil.rmtree(previous))
    return rep
'''


FAKE_AIOS = r'''
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
'''


class TransactionFixture:
    def __init__(self, outer: Path, name: str) -> None:
        self.outer = outer
        self.scripts = outer / f"{name}-scripts"
        self.live = outer / f"{name}-vault Ω"
        self.release = outer / f"{name}-release"
        (self.scripts / "cmd").mkdir(parents=True)
        self.live.mkdir()
        self.release.mkdir()
        write(self.scripts / "cmd" / "__init__.py", "")
        write(self.scripts / "cmd" / "upgrade.py", FAKE_UPGRADE)
        write(self.scripts / "aios.py", FAKE_AIOS)
        write(self.live / "SYSTEM-MANIFEST.yaml", "system_version: 1.0.0\n")
        write(self.live / "System" / "old.txt", "old product\n")
        write(
            self.live / "System" / ".baseline-manifest.json",
            "old baseline\n",
        )
        (self.live / "System" / "Generated").mkdir()
        write(
            self.live / "System" / "Generated" / "index.txt",
            "old generated\n",
        )
        (self.live / "System" / "Logs").mkdir()
        write(self.live / "20 Knowledge" / "user note.md", "preserve me\n")
        tf.arm_fault_target(self.live)

    @property
    def argv(self):
        return ["upgrade", str(self.release), "--root", str(self.live)]

    def source_sha256(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(self.scripts.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(self.scripts).as_posix().encode()
            content = path.read_bytes()
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
        return digest.hexdigest()

    def run_success(self) -> None:
        spec = importlib.util.spec_from_file_location(
            f"fake_aios_{self.live.name}", self.scripts / "aios.py"
        )
        assert spec and spec.loader
        old_path = list(sys.path)
        old_cmd = sys.modules.pop("cmd", None)
        old_upgrade = sys.modules.pop("cmd.upgrade", None)
        old_bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            sys.path.insert(0, str(self.scripts))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.return_value = module.main(self.argv)
        finally:
            sys.dont_write_bytecode = old_bytecode
            sys.path[:] = old_path
            sys.modules.pop("cmd", None)
            sys.modules.pop("cmd.upgrade", None)
            if old_cmd is not None:
                sys.modules["cmd"] = old_cmd
            if old_upgrade is not None:
                sys.modules["cmd.upgrade"] = old_upgrade


class TestTransactionFaultQualification(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="transaction fault Ω ")
        self.addCleanup(self.temp.cleanup)
        self.outer = Path(self.temp.name)

        reference_old = TransactionFixture(self.outer, "reference-old")
        self.old_sha = tf.capture_tree(reference_old.live)["sha256"]
        reference_new = TransactionFixture(self.outer, "reference-new")
        reference_new.run_success()
        self.new_sha = tf.capture_tree(reference_new.live)["sha256"]
        self.assertNotEqual(self.old_sha, self.new_sha)

    def test_every_before_after_interruption_is_complete_old_or_complete_new(self):
        observed = {}
        for index, boundary in enumerate(tf.BOUNDARIES):
            for phase in tf.PHASES:
                with self.subTest(boundary=boundary, phase=phase):
                    fixture = TransactionFixture(
                        self.outer, f"case-{index}-{phase}"
                    )
                    source_before = fixture.source_sha256()
                    result = tf.run_with_fault(
                        fixture.scripts,
                        fixture.argv,
                        tf.TransactionFaultSpec(
                            boundary, phase, str(fixture.live)
                        ),
                    )
                    self.assertTrue(
                        result.interrupted,
                        result.stdout + result.stderr,
                    )
                    state = tf.classify_atomic_state(
                        fixture.live,
                        old_sha256=self.old_sha,
                        new_sha256=self.new_sha,
                    )
                    observed[(boundary, phase)] = state
                    self.assertEqual(source_before, fixture.source_sha256())
                    self.assertEqual(
                        "preserve me\n",
                        (fixture.live / "20 Knowledge" / "user note.md").read_text(),
                    )
        self.assertEqual(
            set(observed),
            {
                (boundary, phase)
                for boundary in tf.BOUNDARIES
                for phase in tf.PHASES
            },
        )
        self.assertEqual("old", observed[("commit-swap", "before")])
        self.assertEqual("new", observed[("commit-swap", "after")])
        self.assertEqual("new", observed[("cleanup", "before")])
        self.assertEqual("new", observed[("cleanup", "after")])

    def test_contract_names_and_required_helpers_are_exact(self):
        module = types.ModuleType("upgrade_contract_probe")
        module._transaction_boundary = lambda name, phase, root: None
        module._free_bytes = lambda path: 1
        module._same_filesystem = lambda a, b: True
        tf.assert_upgrade_contract(module)
        self.assertEqual(
            (
                "checkpoint",
                "plan",
                "candidate-copy",
                "candidate-delete",
                "baseline-replacement",
                "generation",
                "validation",
                "version-bump",
                "report-write",
                "commit-swap",
                "cleanup",
            ),
            tf.BOUNDARIES,
        )
        del module._free_bytes
        with self.assertRaisesRegex(tf.TransactionFaultError, "_free_bytes"):
            tf.assert_upgrade_contract(module)

    def test_insufficient_space_and_cross_filesystem_refuse_before_live_mutation(self):
        for mode in ("space", "filesystem"):
            with self.subTest(mode=mode):
                fixture = TransactionFixture(self.outer, f"refusal-{mode}")
                before = tf.capture_tree(fixture.live)["sha256"]
                source_before = fixture.source_sha256()
                spec = importlib.util.spec_from_file_location(
                    f"fake_upgrade_{mode}",
                    fixture.scripts / "cmd" / "upgrade.py",
                )
                assert spec and spec.loader
                upgrade = importlib.util.module_from_spec(spec)
                old_bytecode = sys.dont_write_bytecode
                try:
                    sys.dont_write_bytecode = True
                    spec.loader.exec_module(upgrade)
                finally:
                    sys.dont_write_bytecode = old_bytecode
                tf.assert_upgrade_contract(upgrade)
                args = types.SimpleNamespace(target=str(fixture.release))
                replacement = (
                    mock.patch.object(upgrade, "_free_bytes", return_value=0)
                    if mode == "space"
                    else mock.patch.object(
                        upgrade, "_same_filesystem", return_value=False
                    )
                )
                with replacement, self.assertRaisesRegex(
                    RuntimeError,
                    "insufficient staging space"
                    if mode == "space"
                    else "crosses filesystems",
                ):
                    upgrade.run(str(fixture.live), args, object())
                self.assertEqual(before, tf.capture_tree(fixture.live)["sha256"])
                self.assertEqual(source_before, fixture.source_sha256())

    def test_refuses_unarmed_overlapping_and_invalid_specs(self):
        fixture = TransactionFixture(self.outer, "safety")
        (fixture.live / tf.FAULT_TARGET_MARKER).unlink()
        spec = tf.TransactionFaultSpec("plan", "before", str(fixture.live))
        with self.assertRaisesRegex(tf.TransactionFaultError, "unarmed"):
            tf.run_with_fault(fixture.scripts, fixture.argv, spec)
        tf.arm_fault_target(fixture.live)
        with self.assertRaisesRegex(tf.TransactionFaultError, "separate trees"):
            tf.run_with_fault(
                fixture.live,
                fixture.argv,
                tf.TransactionFaultSpec("plan", "before", str(fixture.live)),
            )
        with self.assertRaisesRegex(tf.TransactionFaultError, "boundary"):
            tf.TransactionFaultSpec("unknown", "before", str(fixture.live))
        with self.assertRaisesRegex(tf.TransactionFaultError, "phase"):
            tf.TransactionFaultSpec("plan", "during", str(fixture.live))

    def test_hybrid_classifier_fails_closed(self):
        fixture = TransactionFixture(self.outer, "hybrid")
        write(fixture.live / "System" / "partial.txt", "hybrid\n")
        with self.assertRaisesRegex(tf.HybridStateError, "live tree is hybrid"):
            tf.classify_atomic_state(
                fixture.live,
                old_sha256=self.old_sha,
                new_sha256=self.new_sha,
            )


if __name__ == "__main__":
    unittest.main()
