"""Freshness-stamp integrity (DEC-105).

`x_reviewed_against` is the product's only machine-readable claim that a derived
document was actually read against a named version of its source. Two ways it had
stopped being a claim anyone could be held to, both found live on the mainline:

1. **It failed open.** `health`'s skew check reads `versions.get(src)` and does
   nothing at all when the named source declares no `version:`. Three shipped
   stamps were dead this way — including `Fixture Runner Protocol` →
   `Certification Battery`, which is how a battery naming the wrong adversary
   fixtures shipped while `health` printed `derived_docs_behind: 0`.

2. **It could be re-applied without a re-read.** Twenty-three stamps named a
   source version whose own `updated:` date was *later* than the stamping
   document's — arithmetically impossible unless the number was bumped and the
   document never opened. That is the failure the stamp exists to prevent,
   performed by the mechanism meant to prevent it.

The honest escape hatch matters as much as the rule: leaving a stamp at the
version you really did review is always allowed, and `health` reports the doc as
behind. A stale stamp is a true statement. A fresh one you did not earn is not.
"""
from __future__ import annotations

from test_io import write_file
import os
import sys
import tempfile
import unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from lib.report import Report          # noqa: E402
from cmd import validate as v          # noqa: E402
from cmd import health as h            # noqa: E402


def _check(stamps, meta):
    rep = Report("validate")
    v.check_stamp_integrity(stamps, meta, rep)
    return rep


class TestFailsClosed(unittest.TestCase):
    def test_versionless_source_is_an_error_not_a_silence(self):
        rep = _check([("System/Tests/Fixture Runner Protocol.md", "2026-07-16",
                       ["doc-certification-battery:1.0.0"])],
                     {"doc-certification-battery": (None, "2026-07-26")})
        self.assertTrue(any("declares no version" in e for e in rep.errors), rep.errors)

    def test_a_resolvable_stamp_is_silent(self):
        rep = _check([("System/Documentation/Quick Start.md", "2026-07-27",
                       ["doc-onboarding-specification:1.9.0"])],
                     {"doc-onboarding-specification": ("1.9.0", "2026-07-26")})
        self.assertEqual(rep.errors, [])
        self.assertEqual(rep.warnings, [])


class TestStampCannotPredateItsSource(unittest.TestCase):
    def test_a_mechanical_restamp_is_an_error(self):
        rep = _check([("System/Architecture/System Map.md", "2026-07-16",
                       ["doc-canonical-architecture:2.14.0"])],
                     {"doc-canonical-architecture": ("2.14.0", "2026-07-27")})
        self.assertTrue(any("cannot predate" in e for e in rep.errors), rep.errors)

    def test_rolling_the_stamp_back_is_a_legal_answer(self):
        """The point of the rule is honesty, not churn: a doc that keeps the
        version it really reviewed passes here and shows up in `health` as
        behind, which is exactly what it is."""
        rep = _check([("System/Architecture/System Map.md", "2026-07-16",
                       ["doc-canonical-architecture:2.13.0"])],
                     {"doc-canonical-architecture": ("2.13.0", "2026-07-16")})
        self.assertEqual(rep.errors, [])

    def test_user_content_is_advised_never_blocked(self):
        """DEC-069 scoping / U1: the product's rules go red on the product."""
        rep = _check([("20 Knowledge/My Note.md", "2026-07-01",
                       ["doc-canonical-architecture:2.14.0"])],
                     {"doc-canonical-architecture": ("2.14.0", "2026-07-27")})
        self.assertEqual(rep.errors, [])
        self.assertTrue(rep.warnings)


class TestRegistrySourcesResolve(unittest.TestCase):
    def test_a_yaml_registry_id_resolves(self):
        """`op-registry` is `operations.yaml` — versioned, but not markdown, so
        `iter_markdown` never saw it and the Operations Guide's stamp was skipped
        in silence. Failing closed on it would have been the wrong cure."""
        reg = v.registry_versions(VAULT)
        self.assertIn("op-registry", reg)
        self.assertTrue(reg["op-registry"][0])

    def test_health_resolves_registry_sources_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "System", "Operations"))
            write_file(os.path.join(tmp, "System", "Operations", "operations.yaml"), "id: op-registry\nschema_version: 9.9.9\noperations: {}\n", mode="w")
            write_file(os.path.join(tmp, "guide.md"), "---\nid: doc-guide\nx_reviewed_against: [\"op-registry:1.1.0\"]\n"
                "updated: 2026-07-27\n---\n\nbody\n", mode="w")
            behind = h.derived_doc_drift(tmp)
        self.assertTrue(any(b[1] == "op-registry" for b in behind),
                        "a stamp against a YAML registry must be skew-checkable")


class TestTheMasterIsHonest(unittest.TestCase):
    def test_no_unbacked_stamp_ships(self):
        rep = Report("validate")
        v.run(VAULT, None, rep)
        bad = [e for e in rep.errors if "DEC-105" in e]
        self.assertEqual(bad, [], "every shipped x_reviewed_against must be earned:\n"
                         + "\n".join(bad[:5]))


if __name__ == "__main__":
    unittest.main()
