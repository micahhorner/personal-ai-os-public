"""Wave 7 single-command setup contracts."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "System" / "Scripts"))
SETUP = ROOT / "System" / "Scripts" / "setup.py"
SPEC = importlib.util.spec_from_file_location("aios_setup", SETUP)
setup_mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(setup_mod)
from cmd import generate as generate_mod  # noqa: E402


class TestSetup(unittest.TestCase):
    def test_one_flow_creates_isolated_env_installs_pin_generates_and_checks(self):
        with tempfile.TemporaryDirectory() as outer:
            root = Path(outer) / "Product With Space Ω"
            root.mkdir()
            (root / "SYSTEM-MANIFEST.yaml").write_text("system: {}\n")
            environment = Path(outer) / ".Product With Space Ω.aios-venv"
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            calls = []

            def create(_builder, target):
                python.parent.mkdir(parents=True)
                python.write_bytes(b"")

            def run(argv, cwd):
                calls.append((argv, cwd))

            with mock.patch.object(setup_mod.venv.EnvBuilder, "create", create), \
                    mock.patch.object(setup_mod, "_run", side_effect=run):
                setup_mod.setup(root, environment)

            self.assertEqual(calls[0][0][-2:], ["install", setup_mod.DEPENDENCY])
            self.assertEqual(calls[1][0][-2:], ["--root", str(root.resolve())])
            self.assertIn("generate", calls[1][0])
            self.assertIn("instance-health", calls[2][0])
            self.assertTrue(all(cwd == root.resolve() for _, cwd in calls))

    def test_environment_inside_vault_refuses_before_creation(self):
        with tempfile.TemporaryDirectory() as outer:
            root = Path(outer) / "product"
            root.mkdir()
            (root / "SYSTEM-MANIFEST.yaml").write_text("system: {}\n")
            with mock.patch.object(setup_mod.venv.EnvBuilder, "create") as create:
                with self.assertRaises(setup_mod.SetupError):
                    setup_mod.setup(root, root / ".venv")
            create.assert_not_called()

    def test_generate_ignores_the_declared_product_environment(self):
        with tempfile.TemporaryDirectory() as outer:
            root = Path(outer)
            (root / "ordinary.txt").write_text("source\n")
            environment = root / ".venv" / "bin"
            environment.mkdir(parents=True)
            os.symlink(sys.executable, environment / "python")
            first = generate_mod._generation_source_digest(str(root))
            (environment / "state.txt").write_text("environment drift\n")
            second = generate_mod._generation_source_digest(str(root))
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
