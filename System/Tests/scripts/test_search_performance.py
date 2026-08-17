from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from cmd import search
from lib.report import Report


class Args:
    query = "needle-9999"
    domain = "shared"
    project = None
    all_states = False


class TestSearchPerformance(unittest.TestCase):
    def test_prefilter_preserves_yaml_decoded_search_semantics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            notes = root / "20 Knowledge"
            profile = root / "System/Runtime Profiles/runtime.yaml"
            notes.mkdir(parents=True)
            profile.parent.mkdir(parents=True)
            (root / "SYSTEM-MANIFEST.yaml").write_text(
                "runtime:\n  active_profile: System/Runtime Profiles/runtime.yaml\n")
            profile.write_text(
                "hosted: true\nmay_process_private: false\n"
                "allowed_privacy_classifications: [public, internal]\n")
            (notes / "escaped.md").write_text(
                '---\nid: note-escaped\ntype: note\nstatus: active\n'
                'domain: shared\nsummary: "nee\\u0064le-escaped"\n---\n')
            (notes / "folded.md").write_text(
                "---\nid: note-folded\ntype: note\nstatus: active\n"
                "domain: shared\nsummary: >-\n  folded\n  phrase\n---\n")
            for query, expected in (("needle-escaped", "note-escaped"),
                                    ("folded phrase", "note-folded")):
                args = Args()
                args.query = query
                report = Report("search")
                search.run(str(root), args, report)
                self.assertTrue(report.ok, report.errors)
                self.assertEqual(report.info["matches_total"], 1)
                self.assertIn(expected, report.info["hits"][0])

    def test_flat_10000_note_exact_search_stays_under_two_seconds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            notes = root / "20 Knowledge"
            profile = root / "System/Runtime Profiles/runtime.yaml"
            notes.mkdir(parents=True)
            profile.parent.mkdir(parents=True)
            (root / "SYSTEM-MANIFEST.yaml").write_text(
                "runtime:\n  active_profile: System/Runtime Profiles/runtime.yaml\n")
            profile.write_text(
                "hosted: true\nmay_process_private: false\n"
                "allowed_privacy_classifications: [public, internal]\n")
            template = (
                "---\nid: note-{i}\ntype: note\nstatus: active\n"
                "classification: internal\ndomain: shared\nai_use: allowed\n"
                "summary: synthetic fixture {i}\n---\n\nBody {token}.\n"
            )
            for index in range(10000):
                token = "needle-9999" if index == 9999 else "ordinary"
                (notes / f"n-{index:05d}.md").write_text(
                    template.format(i=index, token=token))

            report = Report("search")
            started = time.perf_counter()
            search.run(str(root), Args(), report)
            elapsed = time.perf_counter() - started
            self.__class__.last_elapsed = elapsed

            self.assertTrue(report.ok, report.errors)
            self.assertEqual(report.info["matches_total"], 1)
            self.assertIn("note-9999", report.info["hits"][0])
            self.assertLess(elapsed, 2.0, f"10k search took {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
