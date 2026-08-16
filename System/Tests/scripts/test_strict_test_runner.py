"""Seeded tests for the outer-process strict unittest gate."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from run_strict_tests import _skipped_ids


HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "run_strict_tests.py")


class TestStrictTestRunner(unittest.TestCase):
    def test_complete_owner_id_is_not_doubled(self):
        output = (
            "test_skipped (test_seeded.Seeded.test_skipped)\n"
            "A docstring on a continuation line. ... skipped 'seeded skip'\n"
        )
        self.assertEqual(
            _skipped_ids(output), {"test_seeded.Seeded.test_skipped"}
        )

    def _run(self, body, *extra):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "test_seeded.py")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(textwrap.dedent(body))
            return subprocess.run(
                [sys.executable, RUNNER, "-s", root, "-p", "test_seeded.py", *extra],
                capture_output=True, text=True,
            )

    def test_clean_suite_passes_and_tees_stdout_and_stderr(self):
        result = self._run(
            """
            import sys, unittest
            class Seeded(unittest.TestCase):
                def seeded_clean(self):
                    print("SEEDED STDOUT")
                    print("SEEDED STDERR", file=sys.stderr)
                test_clean = seeded_clean
            """
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("SEEDED STDOUT", combined)
        self.assertIn("SEEDED STDERR", combined)
        self.assertIn("STRICT TEST GATE: PASS", combined)

    def test_resource_warning_fails_even_when_unittest_passes(self):
        result = self._run(
            """
            import unittest, warnings
            class Seeded(unittest.TestCase):
                def seeded_warning(self):
                    warnings.warn("seeded resource leak", ResourceWarning)
                test_warning = seeded_warning
            """
        )
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, combined)
        self.assertIn("ResourceWarning: seeded resource leak", combined)
        self.assertIn("STRICT TEST GATE: FAIL", combined)

    def test_unraisable_exception_fails_even_when_unittest_passes(self):
        result = self._run(
            """
            import gc, unittest
            class BrokenFinalizer:
                def __del__(self):
                    raise RuntimeError("seeded unraisable")
            class Seeded(unittest.TestCase):
                def seeded_unraisable(self):
                    value = BrokenFinalizer()
                    del value
                    gc.collect()
                test_unraisable = seeded_unraisable
            """
        )
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, combined)
        self.assertIn("Exception ignored in:", combined)
        self.assertIn("seeded unraisable", combined)

    def test_unexpected_skip_fails(self):
        result = self._run(
            """
            import unittest
            class Seeded(unittest.TestCase):
                @unittest.skip("seeded skip")
                def seeded_skipped(self):
                    '''A docstring forces verbose unittest output onto two lines.'''
                    pass
                test_skipped = seeded_skipped
            """
        )
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, combined)
        self.assertIn("unexpected skip(s): test_seeded.Seeded.test_skipped", combined)

    def test_exactly_allowlisted_skip_passes(self):
        result = self._run(
            """
            import unittest
            class Seeded(unittest.TestCase):
                @unittest.skip("seeded skip")
                def seeded_skipped(self):
                    '''A docstring forces verbose unittest output onto two lines.'''
                    pass
                test_skipped = seeded_skipped
            """,
            "--allow-skip", "test_seeded.Seeded.test_skipped",
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("STRICT TEST GATE: PASS", combined)


if __name__ == "__main__":
    unittest.main()
