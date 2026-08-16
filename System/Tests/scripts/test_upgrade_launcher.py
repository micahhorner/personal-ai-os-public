from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "upgrade-existing.py"
SPEC = importlib.util.spec_from_file_location("upgrade_existing", LAUNCHER)
assert SPEC and SPEC.loader
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


def _manifest(root: Path) -> None:
    (root / "System" / "Scripts").mkdir(parents=True)
    (root / "SYSTEM-MANIFEST.yaml").write_text("system: {id: personal-ai-os}\n")
    (root / "System" / "Scripts" / "aios.py").write_text("# target sentinel\n")


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


class TestLauncherUnit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.release = self.tmp / "release"
        self.installed = self.tmp / "installed"
        _manifest(self.release)
        _manifest(self.installed)

    def build(self, *extra: str) -> list[str]:
        return launcher.build_command(
            ["--installed", str(self.installed), *extra],
            release_root=self.release)

    def test_review_uses_only_target_engine_old_code_sentinel(self):
        old = self.installed / "System" / "Scripts" / "aios.py"
        old.write_text("raise RuntimeError('OLD CODE EXECUTED')\n")
        command = self.build("--authorize-official-legacy-core")
        self.assertEqual(Path(command[1]).resolve(),
                         (self.release / "System/Scripts/aios.py").resolve())
        self.assertEqual(Path(command[3]).resolve(), self.release.resolve())
        self.assertEqual(Path(command[command.index("--root") + 1]).resolve(),
                         self.installed.resolve())
        self.assertNotIn("--apply", command)
        self.assertIn("--authorize-legacy-core", command)

    def test_executed_launcher_never_runs_installed_old_code(self):
        shutil.copy2(LAUNCHER, self.release / "upgrade-existing.py")
        target_marker = self.tmp / "target-ran"
        old_marker = self.tmp / "old-ran"
        (self.release / "System/Scripts/aios.py").write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            f"Path({str(target_marker)!r}).write_text('review')\n"
            "print('review_sha256: ' + 'a' * 64)\n")
        (self.installed / "System/Scripts/aios.py").write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            f"Path({str(old_marker)!r}).write_text('unsafe')\n")
        result = subprocess.run(
            [sys.executable, str(self.release / "upgrade-existing.py"),
             "--installed", str(self.installed)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(target_marker.is_file())
        self.assertFalse(old_marker.exists())

    def test_apply_requires_confirm_and_exact_hash(self):
        for tail in (["--apply"], ["--apply", "--confirm"],
                     ["--apply", "--review-sha256", "a" * 64]):
            with self.subTest(tail=tail), self.assertRaises(launcher.LauncherError):
                self.build(*tail)
        command = self.build("--apply", "--confirm", "--review-sha256", "a" * 64)
        self.assertEqual(command[-4:],
                         ["--apply", "--confirm", "--review-sha256", "a" * 64])

    def test_relative_missing_same_nested_and_symlink_roots(self):
        for installed in ("relative", str(self.tmp / "missing"), str(self.release)):
            with self.subTest(installed=installed), self.assertRaises(launcher.LauncherError):
                launcher.build_command(["--installed", installed],
                                       release_root=self.release)
        nested = self.release / "nested"
        _manifest(nested)
        with self.assertRaises(launcher.LauncherError):
            launcher.build_command(["--installed", str(nested)],
                                   release_root=self.release)
        alias = self.tmp / "installed-alias"
        alias.symlink_to(self.installed, target_is_directory=True)
        release_alias = self.tmp / "release-alias"
        release_alias.symlink_to(self.release, target_is_directory=True)
        command = launcher.build_command(["--installed", str(alias)],
                                         release_root=release_alias)
        self.assertEqual(Path(command[1]).resolve(),
                         (self.release / "System/Scripts/aios.py").resolve())
        self.assertEqual(Path(command[command.index("--root") + 1]).resolve(),
                         self.installed.resolve())
        with self.assertRaises(launcher.LauncherError):
            launcher.build_command(["--installed", str(release_alias)],
                                   release_root=self.release)

    def test_only_reviewed_flags_are_forwarded(self):
        command = self.build("--base", "/tmp/base", "--accept", "System/A.md",
                             "--accept", "System/B.md")
        self.assertEqual(command.count("--accept"), 2)
        self.assertIn("--base", command)


class TestHistoricalLauncherReview(unittest.TestCase):
    def test_official_143_163_164_reviews_are_read_only(self):
        refs = ("v1.43.0", "v1.63.0", "v1.64.0")
        if shutil.which("git") is None:
            self.skipTest("git unavailable")
        for ref in refs:
            probe = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", ref],
                                   capture_output=True)
            if probe.returncode:
                self.skipTest(f"historical ref unavailable: {ref}")
        with tempfile.TemporaryDirectory() as td:
            for ref in refs:
                installed = Path(td) / ref
                installed.mkdir()
                archive = subprocess.Popen(["git", "-C", str(ROOT), "archive", ref],
                                           stdout=subprocess.PIPE)
                assert archive.stdout is not None
                untar = subprocess.run(["tar", "-x", "-C", str(installed)],
                                       stdin=archive.stdout, capture_output=True)
                archive.stdout.close()
                self.assertEqual(archive.wait(), 0)
                self.assertEqual(untar.returncode, 0, untar.stderr.decode())
                old = installed / "System/Scripts/aios.py"
                old_digest = hashlib.sha256(old.read_bytes()).hexdigest()
                before = _tree_digest(installed)
                result = subprocess.run(
                    [sys.executable, str(LAUNCHER), "--installed", str(installed),
                     "--authorize-official-legacy-core"],
                    cwd=str(ROOT), capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("review_sha256:", result.stdout)
                self.assertIn("mode: dry-run/read-only review", result.stdout)
                self.assertEqual(_tree_digest(installed), before)
                self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(), old_digest)


class TestUpgradeDocumentation(unittest.TestCase):
    def test_cross_version_examples_never_invoke_installed_relative_cli(self):
        docs = [ROOT / "System/Documentation/Upgrading.md",
                ROOT / "System/Documentation/Maintenance and Recovery Guide.md",
                ROOT / "System/Documentation/Human User Manual.md"]
        for path in docs:
            with self.subTest(path=path):
                self.assertNotIn("python3 System/Scripts/aios.py upgrade ", path.read_text())
        self.assertIn("upgrade-existing.py", docs[0].read_text())


if __name__ == "__main__":
    unittest.main()
