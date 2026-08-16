"""doc-audit regression tests (DEC-064): the gate reads truth from source,
catches seeded drift, respects the exemptions, and is green on the master."""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                     # noqa: E402
from cmd import docaudit                          # noqa: E402


class TestTruth(unittest.TestCase):
    def test_truth_reads_source_not_a_baseline(self):
        T = docaudit.truth(VAULT)
        self.assertGreaterEqual(T["capabilities"], 9)
        self.assertEqual(T["principles"], 26)
        self.assertEqual(T["agents"], 3)
        self.assertIn("system_version", T)
        self.assertIn("commands", T)


class TestScan(unittest.TestCase):
    """These assert the STRICT (master) severity, so they state it.

    `docaudit._STRICT` is module-global and set per run from `instance_role`
    (DEC-083). Calling `scan_text` directly inherits whatever the last `run()`
    left behind — and `TestGateOnMaster` below calls `run(VAULT)`, so on a
    personal instance these tests silently flipped to warnings and failed for a
    reason unrelated to the code under test. Same rule as `scaffold.py`: a
    fixture states its mode, it never inherits the host's."""

    def setUp(self):
        self._strict = docaudit._STRICT
        docaudit._STRICT = True

    def tearDown(self):
        docaudit._STRICT = self._strict

    def _scan(self, text, T):
        rep = Report("doc-audit")
        docaudit.scan_text("probe.md", text, T, rep)
        return rep

    def test_catches_seeded_count_drift(self):
        rep = self._scan("The product ships six capabilities.", {"capabilities": 9})
        self.assertTrue(rep.errors)
        self.assertIn("source says 9", rep.errors[0])

    def test_correct_count_passes(self):
        rep = self._scan("The product ships nine capabilities.", {"capabilities": 9})
        self.assertEqual(rep.errors, [])

    def test_blockquote_and_code_are_exempt(self):
        text = "> the spec said six capabilities\n```\nsix capabilities\n```\n"
        rep = self._scan(text, {"capabilities": 9})
        self.assertEqual(rep.errors, [])

    def test_rates_and_minimums_are_not_counts(self):
        rep = self._scan("one folder per add-on; at least one diagram each.",
                         {"folders": 12, "diagrams": 39})
        self.assertEqual(rep.errors, [])

    def test_version_claim_checked_and_transitions_exempt(self):
        T = {"system_version": "1.16.0"}
        bad = self._scan("Covers `system_version 1.8.0` of the product.", T)
        self.assertTrue(bad.errors)
        record = self._scan("system_version 1.15.0→1.16.0.", T)   # a transition record
        self.assertEqual(record.errors, [])

    def test_section_numbers_are_not_counts(self):
        rep = self._scan("### §3.5 Protected objects — all eleven\n", {"protected objects": 11})
        self.assertEqual(rep.errors, [])   # "3.5 Protected objects" is a heading, not a claim

    def test_declarations_are_not_counts(self):
        rep = self._scan("No database, no service. One folder. Nothing else.", {"folders": 12})
        self.assertEqual(rep.errors, [])   # the product's thesis line, not a registry count

    def test_amendment_log_is_history(self):
        text = "## 4. Now\n\nnine capabilities.\n\n## Amendment log\n\n- v1.0.4: six capabilities replaced the skills\n"
        rep = self._scan(text, {"capabilities": 9})
        self.assertEqual(rep.errors, [])

    def test_scaffold_vault_skips_gracefully(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            rep = Report("doc-audit")
            docaudit.run(tmp, None, rep)
            self.assertEqual(rep.errors, [])
            self.assertIn("skipped", str(rep.info.get("status", "")))

    def test_line_numbers_refer_to_the_original_file(self):
        text = "line one\n\n> quoted noise\nsix capabilities here\n"
        rep = self._scan(text, {"capabilities": 9})
        self.assertIn("probe.md:4:", rep.errors[0])


class TestWordNumbers(unittest.TestCase):
    """DEC-105 / GAP-1. The old vocabulary was a hand-listed scatter that stopped
    at twenty (plus twenty-five, twenty-six, thirty, thirty-nine, fifty, seventy).
    The constitution writes almost every census heading as a word-number, so its
    own figures were the ones the auditor could not read — and an unparseable
    word was `continue`d without even being counted as a claim checked."""

    def setUp(self):
        self._strict = docaudit._STRICT
        docaudit._STRICT = True

    def tearDown(self):
        docaudit._STRICT = self._strict

    def test_parses_the_whole_0_to_99_range(self):
        for word, n in (("zero", 0), ("nineteen", 19), ("twenty", 20),
                        ("twenty-two", 22), ("thirty-eight", 38), ("forty", 40),
                        ("fifty-three", 53), ("seventy-seven", 77),
                        ("eighty-four", 84), ("ninety-nine", 99)):
            self.assertEqual(docaudit._word_number(word), n, word)

    def test_rejects_non_numbers(self):
        for junk in ("product", "twenty-hundred", "thirty-twenty", "capabilities"):
            self.assertIsNone(docaudit._word_number(junk))

    def test_the_notation_the_constitution_uses_is_now_checked(self):
        rep = Report("doc-audit")
        docaudit.scan_text("probe.md", "The thirty-eight validate rules and the "
                           "eighty-four unit tests.", {"unit tests": 488}, rep)
        self.assertTrue(any("eighty-four unit tests" in e for e in rep.errors), rep.errors)


class TestAdjacencyGap(unittest.TestCase):
    """DEC-105 / GAP-1 second half. `9 **AI** playbooks` is the exact line that has
    been wrong on the README three times; strict adjacency is why no gate saw it."""

    def setUp(self):
        self._strict = docaudit._STRICT
        docaudit._STRICT = True

    def tearDown(self):
        docaudit._STRICT = self._strict

    def _scan(self, text, T):
        rep = Report("doc-audit")
        docaudit.scan_text("probe.md", text, T, rep)
        return rep

    def test_acronym_between_number_and_noun_is_still_a_claim(self):
        rep = self._scan("8 record types · 9 AI playbooks · 3 roles", {"capabilities": 14})
        self.assertTrue(any("9 AI playbooks" in e for e in rep.errors), rep.errors)

    def test_a_narrowing_modifier_is_a_subset_not_a_census(self):
        # "two concurrency flags" is true of a slice of forty-four. A gate that
        # reddens on subset claims is a gate people learn to ignore.
        self.assertEqual(self._scan("two concurrency flags exist", {"flags": 44}).errors, [])

    def test_identifiers_are_not_counts(self):
        for text in ("fixture 30-folder-rules", "DEC-070 adopted the Agent Skills projection",
                     "diagram 03-component-operations-map", "the 00–90 folders"):
            self.assertEqual(self._scan(text, {"folders": 13, "agents": 3,
                                               "components": 19}).errors, [], text)

    def test_a_dated_comparison_table_is_history(self):
        text = ("| Then (v1.3.0) | Four days later (v1.14.0) |\n"
                "|---|---|\n| 12 documentation files | **29** |\n")
        self.assertEqual(self._scan(text, {"documentation files": 30}).errors, [])


class TestNewTruthKeys(unittest.TestCase):
    """DEC-105 / GAP-3. Whole classes of countable fact had no key at all, which
    is how the unit-test census stayed at eighty-four while the suite grew past
    four hundred, and how the message census drifted five releases in silence."""

    def setUp(self):
        self._strict = docaudit._STRICT
        docaudit._STRICT = True
        self.T = docaudit.truth(VAULT)

    def tearDown(self):
        docaudit._STRICT = self._strict

    def test_every_new_key_is_present_and_plausible(self):
        for key in ("unit tests", "messages", "authority files", "components",
                    "schemas", "libraries", "documentation files", "script modules",
                    "note-class templates"):
            self.assertIn(key, self.T)
            self.assertGreater(self.T[key], 0, key)

    def test_unit_test_key_equals_what_unittest_would_instantiate(self):
        import re as _re
        n = 0
        for p in glob.glob(os.path.join(VAULT, "System", "Tests", "scripts", "*.py")):
            with open(p, encoding="utf-8") as stream:
                n += len(_re.findall(r"^\s+def (test_\w+)", stream.read(), _re.M))
        self.assertEqual(self.T["unit tests"], n)

    def test_message_key_counts_the_sev_switch_and_sub_reports(self):
        """A plain grep for `rep.error(`/`rep.warn(` is wrong twice: three modules
        raise through `_sev(rep)`, and `certify` raises two through sub-reports
        named `hsub`/`vsub`. The key must be strictly larger than the grep."""
        import re as _re
        grep = 0
        for p in glob.glob(os.path.join(VAULT, "System", "Scripts", "**", "*.py"),
                           recursive=True):
            with open(p, encoding="utf-8") as stream:
                grep += len(_re.findall(r"rep\.(?:error|warn)\(", stream.read()))
        self.assertGreater(self.T["messages"], grep)

    def test_a_seeded_lie_about_the_test_suite_now_fires(self):
        rep = Report("doc-audit")
        docaudit.scan_text("probe.md", "the suite has 999 unit tests", self.T, rep)
        self.assertTrue(rep.errors)


class TestBehaviourGuard(unittest.TestCase):
    """DEC-105 / GAP-5. No count is wrong in "the weekly pass drains the inbox";
    the description is. DEC-101 was contradicted in eleven documents for ten days
    and in the always-loaded Task Router for twelve more, and no gate could see it."""

    def setUp(self):
        self._strict = docaudit._STRICT
        docaudit._STRICT = True

    def tearDown(self):
        docaudit._STRICT = self._strict

    def _scan(self, text):
        rep = Report("doc-audit")
        docaudit.scan_text("probe.md", text, {}, rep)
        return rep

    def test_the_retired_promise_fails(self):
        for text in ("weekly pass drains the inbox via ingest",
                     "health, inbox drain, freshness triage",
                     "the cadenced pass empties the Inbox"):
            self.assertTrue(self._scan(text).errors, text)

    def test_stating_the_rule_is_allowed(self):
        for text in ("It never drains the Inbox on its own.",
                     "No scheduled task may drain the Inbox.",
                     "reports the Inbox rather than draining it"):
            self.assertEqual(self._scan(text).errors, [], text)

    def test_a_negation_after_the_phrase_does_not_excuse_it(self):
        # The probe that motivated the rule: the sentence promises the drain and
        # only afterwards mentions consent.
        self.assertTrue(self._scan(
            "the weekly pass drains the inbox automatically with no user consent").errors)

    def test_a_negation_on_a_neighbouring_line_does_not_excuse_it(self):
        # The Task Router stacks unrelated rows; row N-1 saying "Not every
        # preference is a decision" must not exempt row N.
        text = ("record-decision: ...  # Not every preference is a decision.\n"
                "weekly-pass: ...      # weekly pass drains the inbox via ingest\n")
        self.assertTrue(self._scan(text).errors)


class TestYamlAndSvgSurfaces(unittest.TestCase):
    """DEC-105 / GAP-2. `doc-audit` globbed `*.md` only, so the always-loaded Task
    Router, the diagram atlas's metadata, and every SVG were unscanned — and six of
    the audit's highest-severity findings lived in exactly those three file types."""

    def setUp(self):
        self._strict = docaudit._STRICT
        docaudit._STRICT = True

    def tearDown(self):
        docaudit._STRICT = self._strict

    def test_svg_text_keeps_original_line_numbers(self):
        src = ('<svg>\n<title>t</title>\n'
               '<text x="1">Capabilities (7)</text>\n</svg>\n')
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
            fh.write(src)
            path = fh.name
        try:
            out = docaudit.svg_text(path)
            self.assertEqual(out.count("\n"), src.count("\n"))
            self.assertEqual(out.splitlines()[2].strip(), "Capabilities (7)")
            self.assertNotIn("<text", out)
        finally:
            os.unlink(path)

    def test_a_diagram_label_is_a_claim(self):
        rep = Report("doc-audit")
        docaudit.scan_text("03.svg", "Capabilities (7)", {"capabilities": 14}, rep)
        self.assertTrue(any("Capabilities (7)" in e for e in rep.errors), rep.errors)

    def test_a_diagram_number_is_not_a_count(self):
        rep = Report("doc-audit")
        docaudit.scan_text("CATALOG.md", "covered by the CLI-surface diagram (22)",
                           {"diagrams": 44}, rep)
        self.assertEqual(rep.errors, [])

    def test_the_run_reports_what_it_scanned(self):
        rep = Report("doc-audit")
        docaudit.run(VAULT, None, rep)
        self.assertIn("yaml_claims_checked", rep.info)
        self.assertIn("svg_claims_checked", rep.info)
        self.assertGreater(rep.info["yaml_claims_checked"], 0)
        self.assertGreater(rep.info["svg_claims_checked"], 0)


class TestGateOnMaster(unittest.TestCase):
    def test_master_is_green(self):
        """The whole point: after DEC-064, the shipped docs contradict nothing."""
        rep = Report("doc-audit")
        docaudit.run(VAULT, None, rep)
        self.assertEqual(rep.errors, [], "doc-audit must be green on the master:\n"
                         + "\n".join(rep.errors[:5]))


class TestRollbackDirtyTreePreservation(unittest.TestCase):
    """F1 / independent audit M-02 (final half): rollback must never silently
    destroy uncommitted edits to tracked files — it archives them first."""

    def test_dirty_tracked_edits_are_snapshotted_before_restore(self):
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        from cmd import checkpoint as ck_mod
        with tempfile.TemporaryDirectory() as outer:
            root = os.path.join(outer, "v")
            os.makedirs(os.path.join(root, "20 Knowledge"))
            with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as stream:
                stream.write(product_manifest())
            note = os.path.join(root, "20 Knowledge", "n.md")
            with open(note, "w") as stream:
                stream.write("original\n")
            for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
                        ["git", "config", "user.name", "t"], ["git", "add", "-A"],
                        ["git", "commit", "-qm", "base"]):
                subprocess.run(cmd, cwd=root, check=True, capture_output=True)
            with open(note, "w") as stream:
                stream.write("uncommitted in-flight work\n")

            target = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            proof = ck_mod.recovery.inspect_commit(root, target)
            class A:
                json = False; message = None; rollback = target; confirm = True
                clean = False; force_zip = False
                expected_sha256 = proof["tracked_sha256"]
            rep = Report("rollback")
            ck_mod.run(root, A(), rep)

            with open(note) as stream:
                self.assertEqual(stream.read(), "original\n")   # restore happened
            snapdir = os.path.join(outer, "v-Snapshots")
            zips = ([f for f in os.listdir(snapdir) if f.endswith(".tar.gz")]
                    if os.path.isdir(snapdir) else [])
            self.assertTrue(zips, "dirty tree must be archived before restore")
            self.assertTrue(any("preserved" in w for w in rep.warnings), rep.warnings)

    def test_clean_tree_takes_no_extra_snapshot(self):
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        from cmd import checkpoint as ck_mod
        with tempfile.TemporaryDirectory() as outer:
            root = os.path.join(outer, "v")
            os.makedirs(os.path.join(root, "20 Knowledge"))
            with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as stream:
                stream.write(product_manifest())
            with open(os.path.join(root, "20 Knowledge", "n.md"), "w") as stream:
                stream.write("original\n")
            for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
                        ["git", "config", "user.name", "t"], ["git", "add", "-A"],
                        ["git", "commit", "-qm", "base"]):
                subprocess.run(cmd, cwd=root, check=True, capture_output=True)

            target = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            proof = ck_mod.recovery.inspect_commit(root, target)
            class A:
                json = False; message = None; rollback = target; confirm = True
                clean = False; force_zip = False
                expected_sha256 = proof["tracked_sha256"]
            rep = Report("rollback")
            ck_mod.run(root, A(), rep)
            snapdir = os.path.join(outer, "v-Snapshots")
            zips = ([f for f in os.listdir(snapdir) if f.endswith(".tar.gz")]
                    if os.path.isdir(snapdir) else [])
            self.assertEqual(zips, [], "a clean tree needs no safety snapshot")


class TestVersionClaims(unittest.TestCase):
    """DEC-109 / audit GAP-4 — `system_version` was the only version this gate
    ever checked, while the constitution alone carried seventeen component
    stamps, TEN of them stale when this check was written.

    SEEDED FAILURE: every drift assertion here passes silently against the
    pre-fix gate, because it had no version truth key beyond `system_version`.
    """

    V = {"component versions": {"safe-write": "0.6.0", "steward": "1.2.0",
                                "constitution": "2.15.2"}}

    def setUp(self):
        self._strict = docaudit._STRICT
        docaudit._STRICT = True

    def tearDown(self):
        docaudit._STRICT = self._strict

    def _scan(self, text):
        rep = Report("doc-audit")
        docaudit.scan_text("probe.md", text, self.V, rep)
        return rep

    def test_truth_reads_component_versions_from_source(self):
        v = docaudit.truth(VAULT)["component versions"]
        for name in ("safe-write", "steward", "constitution", "note schema",
                     "vault_profile_version"):
            self.assertIn(name, v, f"{name} has a machine-readable version and must be covered")
        import re as _re
        for name, ver in v.items():
            self.assertRegex(ver, r"^\d+\.\d+\.\d+$", name)

    def test_catches_a_stale_catalogue_stamp(self):
        """The real shape: a section names the component, the next line stamps it."""
        rep = self._scan("### §5.1 `safe-write` — the write procedure\n"
                         "`v0.2.1` · Router: `safe-write`\n")
        self.assertTrue(rep.errors, "a stale section stamp must fail")
        self.assertIn("0.6.0", rep.errors[0])

    def test_current_catalogue_stamp_passes(self):
        rep = self._scan("### §5.1 `safe-write` — the write procedure\n"
                         "`v0.6.0` · Router: `safe-write`\n")
        self.assertEqual(rep.errors, [])

    def test_catches_a_stale_inline_claim(self):
        rep = self._scan("The `steward` 1.0.0 agent runs the review.")
        self.assertTrue(rep.errors)
        self.assertIn("1.2.0", rep.errors[0])

    def test_transition_records_are_not_claims(self):
        """"0.4.0->0.6.0" is what a release CHANGED, not what is true now — the
        same rule the `system_version` check has always applied."""
        rep = self._scan("Capabilities `safe-write` 0.4.0\u21920.6.0 and `steward` 1.1.0 to 1.2.0.")
        self.assertEqual(rep.errors, [], rep.errors)

    def test_dated_provenance_stamps_are_not_claims(self):
        """"Source: X v0.2.1" records where a passage came from; it stays true as
        the source moves on (constitution 4.8)."""
        rep = self._scan("*Source: `safe-write` v0.2.1, shipped in v1.14.0.*")
        self.assertEqual(rep.errors, [], rep.errors)

    def test_amendment_log_is_exempt_like_any_dated_record(self):
        rep = self._scan("## Amendment log\n\n`safe-write` 0.2.0 wired the triage.\n")
        self.assertEqual(rep.errors, [], rep.errors)

    def test_a_foreign_release_tag_is_not_this_vaults_component(self):
        """`method-kit@0.2.0` names a repository release. An `@` read as a
        separator would make this gate confidently wrong about another product."""
        rep = self._scan("Distributed as `safe-write`@9.9.9 upstream.")
        self.assertEqual(rep.errors, [], rep.errors)

    def test_the_uncovered_classes_are_named_not_implied(self):
        """The instruction this key was built to: where the source is not
        machine-readable, SAY SO rather than fake coverage."""
        rep = Report("doc-audit")
        docaudit.run(VAULT, type("A", (), {"json": False})(), rep)
        named = [v for k, v in rep.info.items() if k.startswith("versions_not_covered_")]
        self.assertGreaterEqual(len(named), 3)
        self.assertTrue(any("Open Knowledge Format" in v for v in named))
        self.assertIn("version_sources", rep.info)


if __name__ == "__main__":
    unittest.main()
