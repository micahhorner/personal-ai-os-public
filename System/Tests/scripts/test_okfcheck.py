"""okf-check regression tests: OKF's conformance rules applied exactly —
frontmatter required, non-empty `type` required, reserved filenames held to rule 3
rather than skipped, knowledge-layer default scope, the v0.2 family advisories that
must never harden into errors, and nonzero exit routing via Report.errors.

The version under test is explicit in every case, because the whole point of the
v0.2 work is that a verdict names the version it was reached against."""
import os, sys, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from lib.report import Report            # noqa: E402
from cmd import okfcheck                 # noqa: E402


class Args:
    json = False
    target = None
    okf_version = None


def write(base, rel, text):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class OkfCheckTargetDir(unittest.TestCase):
    def check(self, tmp):
        args = Args()
        args.target = tmp
        rep = Report("okf-check")
        okfcheck.run(VAULT, args, rep)
        return rep

    def test_conformant_tree_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "concept.md", "---\ntype: note\n---\nbody\n")
            write(tmp, "sub/deeper.md", "---\ntype: runbook\ntitle: x\n---\nbody\n")
            rep = self.check(tmp)
            self.assertTrue(rep.ok)
            self.assertEqual(rep.info["concepts_checked"], 2)
            self.assertEqual(rep.info["conformant"], 2)
            self.assertIn("CONFORMANT", rep.info["verdict"])

    def test_missing_frontmatter_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "raw.md", "just prose, no metadata\n")
            rep = self.check(tmp)
            self.assertFalse(rep.ok)
            self.assertIn("no YAML frontmatter", rep.errors[0])

    def test_missing_or_empty_type_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "untyped.md", "---\ntitle: x\n---\nbody\n")
            write(tmp, "emptytype.md", "---\ntype: ''\n---\nbody\n")
            rep = self.check(tmp)
            self.assertEqual(len(rep.errors), 2)
            for e in rep.errors:
                self.assertIn("type", e)

    def test_unparseable_yaml_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "broken.md", "---\ntype: [unclosed\n---\nbody\n")
            rep = self.check(tmp)
            self.assertFalse(rep.ok)

    def test_reserved_filenames_exempt_from_the_concept_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "index.md", "no frontmatter, and that is fine — reserved\n")
            write(tmp, "log.md", "same here\n")
            write(tmp, "concept.md", "---\ntype: note\n---\nbody\n")
            rep = self.check(tmp)
            self.assertTrue(rep.ok)
            self.assertEqual(rep.info["concepts_checked"], 1)
            self.assertEqual(rep.info["reserved_files_checked"], "2/2 (rule 3)")

    def test_non_markdown_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "notes.txt", "not markdown\n")
            write(tmp, "concept.md", "---\ntype: note\n---\nbody\n")
            rep = self.check(tmp)
            self.assertTrue(rep.ok)
            self.assertEqual(rep.info["concepts_checked"], 1)

    def test_empty_tree_warns_not_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = self.check(tmp)
            self.assertTrue(rep.ok)
            self.assertEqual(len(rep.warnings), 1)

    def test_missing_target_errors(self):
        args = Args()
        args.target = "/nonexistent/nowhere"
        rep = Report("okf-check")
        okfcheck.run(VAULT, args, rep)
        self.assertFalse(rep.ok)


class OkfCheckVersioning(unittest.TestCase):
    """The version is a stated fact, never an implication."""

    def check(self, tmp, version=None):
        args = Args()
        args.target = tmp
        args.okf_version = version
        rep = Report("okf-check")
        okfcheck.run(VAULT, args, rep)
        return rep

    def test_default_is_the_current_spec_and_the_verdict_names_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "c.md", "---\ntype: note\n---\nbody\n")
            rep = self.check(tmp)
            self.assertEqual(rep.info["okf_version"], "0.2")
            self.assertIn("v0.2", rep.info["verdict"])

    def test_an_explicit_older_version_is_checked_and_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "c.md", "---\ntype: note\n---\nbody\n")
            rep = self.check(tmp, "0.1")
            self.assertEqual(rep.info["okf_version"], "0.1")
            self.assertIn("v0.1", rep.info["verdict"])
            self.assertNotIn("v0_2_family_advisories", rep.info)

    def test_an_unknown_version_is_refused_rather_than_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(self.check(tmp, "0.9").ok)

    def test_a_bundle_declaring_a_different_version_is_flagged(self):
        """§12: the root index.md may declare the version. Checking a bundle
        against a version it does not claim is a real mismatch, not a detail."""
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "index.md", '---\nokf_version: "0.1"\n---\n\n# Index\n')
            write(tmp, "c.md", "---\ntype: note\n---\nbody\n")
            rep = self.check(tmp)
            self.assertTrue(rep.ok)
            self.assertTrue(any("checked it against v0.2" in w for w in rep.warnings))

    def test_v01_bundle_is_still_conformant_under_v02(self):
        """The load-bearing compatibility fact: v0.2 retired two fields, it did
        not forbid them, and §11's rules did not change."""
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "c.md", "---\ntype: note\ntimestamp: '2026-05-28T00:00:00+00:00'\n"
                               "---\n\n# Citations\n- https://example.com\n")
            rep = self.check(tmp)
            self.assertTrue(rep.ok)
            self.assertEqual(rep.info["v0_2_family_advisories"], 2)   # timestamp + # Citations


class OkfCheckV02Advisories(unittest.TestCase):
    """§11 forbids rejecting a bundle over an optional family. Every one of these
    must be a warning — if any becomes an error, this command starts refusing
    bundles the spec calls conformant."""

    def check(self, frontmatter, body="body\n"):
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        write(tmp, "c.md", "---\n" + frontmatter + "---\n" + body)
        args = Args()
        args.target = tmp
        args.okf_version = None
        rep = Report("okf-check")
        okfcheck.run(VAULT, args, rep)
        return rep

    def assertAdvisory(self, rep, n=1):
        self.assertTrue(rep.ok, f"an optional family became a conformance error: {rep.errors}")
        self.assertEqual(rep.info["v0_2_family_advisories"], n)

    def test_a_source_entry_without_resource(self):
        self.assertAdvisory(self.check("type: note\nsources:\n  - id: x\n"))

    def test_an_ai_os_style_id_list_in_sources(self):
        self.assertAdvisory(self.check("type: note\nsources: [source-a, source-b]\n"), n=2)

    def test_generated_without_by(self):
        self.assertAdvisory(self.check("type: note\ngenerated: {at: 2026-07-01T00:00:00Z}\n"))

    def test_an_actor_outside_the_convention(self):
        self.assertAdvisory(self.check("type: note\ngenerated: {by: alice, at: '2026-07-01'}\n"))

    def test_a_bare_verified_mapping_is_accepted_not_flagged(self):
        """§5.2/§11: a single verifier MAY be written as a bare mapping and a
        consumer MUST treat it as a one-element list. Google's own spec examples
        use this form, so reading it as malformed would flag the spec itself."""
        rep = self.check("type: note\nverified: {by: 'human:jo', at: '2026-07-01T00:00:00Z'}\n")
        self.assertAdvisory(rep, n=0)

    def test_a_verified_event_missing_at(self):
        self.assertAdvisory(self.check("type: note\nverified:\n  - {by: 'human:jo'}\n"))

    def test_status_outside_the_v02_vocabulary(self):
        self.assertAdvisory(self.check("type: note\nstatus: active\n"))

    def test_stale_after_that_is_not_a_date(self):
        self.assertAdvisory(self.check("type: note\nstale_after: soon\n"))

    def test_attested_computation_without_runtime(self):
        self.assertAdvisory(self.check("type: Attested Computation\n"
                                       "computation: refs/x.sql\n"))

    def test_advisories_are_rolled_up_by_kind_not_repeated_per_file(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        for i in range(12):
            write(tmp, f"c{i}.md", "---\ntype: note\nstatus: active\n---\nbody\n")
        args = Args()
        args.target = tmp
        args.okf_version = None
        rep = Report("okf-check")
        okfcheck.run(VAULT, args, rep)
        self.assertEqual(rep.info["v0_2_family_advisories"], 12)
        self.assertEqual(len(rep.warnings), 1, "one finding became twelve warnings")
        self.assertIn("12x", rep.warnings[0])


class OkfCheckRuleThree(unittest.TestCase):
    """Conformance rule 3 — the reserved-file structure. Identical in v0.1 §9 and
    v0.2 §11, and never checked at all before this build, which is how the command
    printed a three-rule verdict off two rules."""

    def check(self, tmp):
        args = Args()
        args.target = tmp
        args.okf_version = None
        rep = Report("okf-check")
        okfcheck.run(VAULT, args, rep)
        return rep

    def test_root_index_may_declare_okf_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "index.md", '---\nokf_version: "0.2"\n---\n\n# Index\n\n* [a](a.md)\n')
            write(tmp, "a.md", "---\ntype: note\n---\nbody\n")
            self.assertTrue(self.check(tmp).ok)

    def test_root_index_frontmatter_may_carry_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "index.md", '---\nokf_version: "0.2"\ntitle: Mine\n---\n\n# Index\n')
            rep = self.check(tmp)
            self.assertFalse(rep.ok)
            self.assertIn("'title'", rep.errors[0])

    def test_a_nested_index_may_not_carry_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "sub/index.md", "---\ntype: note\n---\n\n# Sub\n")
            rep = self.check(tmp)
            self.assertFalse(rep.ok)
            self.assertIn("below the bundle root", rep.errors[0])

    def test_log_date_headings_must_be_iso_8601(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "log.md", "# Log\n\n## May 22 2026\n* **Update**: a thing.\n")
            rep = self.check(tmp)
            self.assertFalse(rep.ok)
            self.assertIn("ISO 8601", rep.errors[0])

    def test_a_well_formed_log_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "log.md", "# Log\n\n## 2026-05-22\n* **Update**: a thing.\n")
            write(tmp, "a.md", "---\ntype: note\n---\nbody\n")
            self.assertTrue(self.check(tmp).ok)

    def test_an_index_with_no_headings_warns_but_conforms(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "index.md", "just a sentence\n")
            write(tmp, "a.md", "---\ntype: note\n---\nbody\n")
            rep = self.check(tmp)
            self.assertTrue(rep.ok)
            self.assertTrue(any("no headings" in w for w in rep.warnings))


class OkfCheckKnowledgeLayerDefault(unittest.TestCase):
    def test_seed_vault_knowledge_layer_is_conformant(self):
        """The product's own knowledge layer must always verify CONFORMANT —
        this is the public compatibility claim, enforced as a test."""
        rep = Report("okf-check")
        okfcheck.run(VAULT, Args(), rep)
        self.assertTrue(rep.ok, f"seed knowledge layer non-conformant: {rep.errors}")
        self.assertIn("knowledge layer", rep.info["scope"])
        self.assertGreater(rep.info["concepts_checked"], 0)

    def test_the_verdict_states_its_own_scope(self):
        """The defect this guards is a true-but-misleading verdict: "CONFORMANT"
        over nine files on a vault holding hundreds. The count and the packs are
        IN the verdict string, so the claim cannot be quoted without its scope."""
        rep = Report("okf-check")
        okfcheck.run(VAULT, Args(), rep)
        self.assertIn(str(rep.info["concepts_checked"]), rep.info["verdict"])
        self.assertIn("installed pack", rep.info["scope"])


CONCEPT = "---\ntype: note\n---\nbody\n"
UNTYPED = "---\ntitle: x\n---\nbody\n"


def pack_vault(tmp):
    """A vault with two installed packs, each carrying content folders, machinery
    folders, and the DEC-067 collision pair at its root."""
    write(tmp, "SYSTEM-MANIFEST.yaml",
          "system: {name: t, id: t}\ndirectories:\n  content:\n    - 20 Knowledge\n")
    write(tmp, "20 Knowledge/note.md", CONCEPT)
    write(tmp, "README.md", "vault readme, no frontmatter\n")
    write(tmp, "CHANGELOG.md", "vault changelog, no frontmatter\n")
    for pid in ("alpha", "beta"):
        write(tmp, f"Packs/{pid}/pack.yaml", f"id: pack-{pid}\nversion: 1.0.0\n")
        write(tmp, f"Packs/{pid}/README.md", "pack readme, no frontmatter\n")
        write(tmp, f"Packs/{pid}/CHANGELOG.md", "pack changelog, no frontmatter\n")
        write(tmp, f"Packs/{pid}/capabilities/{pid}-cap.md", UNTYPED)      # machinery
        write(tmp, f"Packs/{pid}/tests/fixture.md", UNTYPED)               # machinery
        write(tmp, f"Packs/{pid}/resources/vendored/UPSTREAM.md", "third-party, verbatim\n")
        write(tmp, f"Packs/{pid}/01 Content/a.md", CONCEPT)                # content
        write(tmp, f"Packs/{pid}/01 Content/deep/b.md", CONCEPT)           # content
    return tmp


class OkfCheckCoversPackContent(unittest.TestCase):
    """v1.55.0 / DEC-110. Before this, the default scope was the manifest's
    content directories alone; on a live role-pack instance that was 9 concepts
    checked against 236 more sitting unread in `Packs/`, under a CONFORMANT
    verdict the landing copy sold as covering them."""

    def check(self, tmp):
        rep = Report("okf-check")
        okfcheck.run(tmp, Args(), rep)
        return rep

    def test_pack_content_is_checked_and_counted_per_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = self.check(pack_vault(tmp))
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(rep.info["concepts_checked"], 5)   # 1 vault + 2 per pack
            self.assertIn("alpha: 2", rep.info["scope"])
            self.assertIn("beta: 2", rep.info["scope"])
            self.assertIn("Packs/alpha/01 Content: 2", rep.info["coverage_by_tree"])
            self.assertIn("5 concepts", rep.info["verdict"])

    def test_a_violation_inside_a_pack_is_caught(self):
        """The whole point: a non-conformant file in pack content must turn the
        command red and name its path."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_vault(tmp)
            write(tmp, "Packs/alpha/01 Content/bad.md", UNTYPED)
            write(tmp, "Packs/beta/01 Content/raw.md", "no frontmatter at all\n")
            rep = self.check(tmp)
            self.assertFalse(rep.ok)
            self.assertEqual(len(rep.errors), 2)
            joined = " ".join(rep.errors)
            self.assertIn("Packs/alpha/01 Content/bad.md", joined)
            self.assertIn("Packs/beta/01 Content/raw.md", joined)

    def test_machinery_and_pack_root_files_stay_out_of_scope(self):
        """Each pack's fixture carries four files that would fail if scanned —
        an untyped capability, an untyped test fixture, a frontmatter-free
        vendored upstream file, and the README/CHANGELOG pair. The vault's own
        `System/` and root files are excluded for the same reason, and the tree
        is conformant only because that boundary holds."""
        with tempfile.TemporaryDirectory() as tmp:
            rep = self.check(pack_vault(tmp))
            self.assertTrue(rep.ok, rep.errors)
            self.assertNotIn("capabilities", rep.info["coverage_by_tree"])
            self.assertNotIn("resources", rep.info["coverage_by_tree"])

    def test_a_folder_without_pack_yaml_is_not_a_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_vault(tmp)
            write(tmp, "Packs/stray-download/junk.md", "no frontmatter\n")
            rep = self.check(tmp)
            self.assertTrue(rep.ok, rep.errors)
            self.assertNotIn("stray-download", rep.info["scope"])

    def test_an_explicit_target_still_checks_exactly_that_tree(self):
        """`--target` is unchanged: no pack discovery, no exclusions, mirroring
        the spec, which defines none."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_vault(tmp)
            args = Args()
            args.target = os.path.join(tmp, "Packs", "alpha")
            rep = Report("okf-check")
            okfcheck.run(tmp, args, rep)
            self.assertFalse(rep.ok)          # the machinery IS scanned under an explicit target
            self.assertNotIn("installed pack", rep.info["scope"])

    def test_a_vault_with_no_packs_is_unaffected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "SYSTEM-MANIFEST.yaml",
                  "system: {name: t}\ndirectories:\n  content:\n    - 20 Knowledge\n")
            write(tmp, "20 Knowledge/note.md", CONCEPT)
            rep = self.check(tmp)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("0 installed packs", rep.info["scope"])


if __name__ == "__main__":
    unittest.main()
