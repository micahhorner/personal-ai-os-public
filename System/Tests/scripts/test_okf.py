"""Regression tests for `aios okf-export` / `aios okf-import` — the Open
Knowledge Format surface (OKF v0.2 by default, v0.1 on request; Google,
Apache-2.0).

Four things are proven here, because four things could silently go wrong:

1. **The emitted bundle conforms to OKF** — every concept carries a non-empty
   `type` (the spec's single hard requirement) and the reserved filenames are
   respected.
2. **Privacy fails closed on the way OUT, independently of the runtime profile.**
   This is the test that matters most: `search.permitted()` asks "may this
   runtime read it?", which a `hosted: false` profile answers "yes" for
   `local-only`. Export asks "may this leave the vault?" — and the answer for
   `local-only` is no on every profile. If someone ever "simplifies" the two
   filters into one, this test fails, and it should.
3. **The round trip is lossless on the shared fields** — the portability claim,
   proven against an external yardstick rather than asserted. The comparison runs
   from the ORIGINAL note to the LANDED note, not from the emitted bundle to the
   landed note: a loss introduced on the way *out* is invisible to the second
   comparison, and every mapping v0.2 added happens on the way out.
4. **A bundle does not corrupt the vault that holds it** — the exported copy must
   not collide with the notes it came from.
"""
from test_io import write_file
import os
import shutil
import sys
import tempfile
import unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)

import yaml                                          # noqa: E402
from cmd import okfexport, okfimport                 # noqa: E402
from lib.frontmatter import BUNDLE_MARKER, parse_file   # noqa: E402
from lib.okf import to_okf, to_timestamp             # noqa: E402
from lib.report import Report                        # noqa: E402


class Args:
    json = False

    def __init__(self, target=None, okf_version=None, author=None):
        self.target = target
        self.okf_version = okf_version
        self.author = author


def make_vault(tmp):
    """A minimal vault with the two folders the OKF commands resolve."""
    for d in ("20 Knowledge", "30 Sources", "40 Outputs",
              os.path.join("System", "Registries")):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as fh:
        yaml.safe_dump({"system": {"name": "Test Vault", "system_version": "0.0.0"},
                        "runtime": {"ai_writes_enabled": True},
                        "protected_objects": [
                            "SYSTEM-MANIFEST.yaml", "System/Agents/",
                            "80 User/privacy*",
                        ]}, fh)
    with open(os.path.join(tmp, "System", "Registries", "folder-registry.yaml"), "w") as fh:
        yaml.safe_dump({"folders": {"knowledge": {"path": "20 Knowledge"},
                                    "sources": {"path": "30 Sources"},
                                    "outputs": {"path": "40 Outputs"}}}, fh)
    return tmp


def note(tmp, relpath, meta, body="# Title\n\nBody text.\n"):
    p = os.path.join(tmp, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n\n" + body)
    return p


BASE = {"type": "note", "created": "2026-07-14", "updated": "2026-07-15",
        "summary": "A summary.", "status": "active", "verification": "verified"}


def exported_names(tmp):
    b = os.path.join(tmp, "40 Outputs", "okf-knowledge")
    if not os.path.isdir(b):
        return set()
    return {f for f in os.listdir(b) if f.endswith(".md")} - {"index.md"}


class TestExportPrivacy(unittest.TestCase):
    """The planted-privacy gate: content that must never travel, never travels."""

    def _export_with(self, meta, relpath="20 Knowledge/x.md", body="# X\n\nPLANTED\n"):
        tmp = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        note(tmp, relpath, meta, body)
        okfexport.run(tmp, Args("knowledge"), Report("okf-export"))
        return tmp

    def test_exports_an_ordinary_note(self):
        tmp = self._export_with(dict(BASE, id="note-ok"))
        self.assertEqual(exported_names(tmp), {"x.md"})

    def test_local_only_folder_never_exports(self):
        tmp = self._export_with(dict(BASE, id="note-secret"),
                                relpath="20 Knowledge/Local Only/x.md")
        self.assertEqual(exported_names(tmp), set())

    def test_local_only_never_exports_even_on_a_local_profile(self):
        """The regression that guards the whole design: a local runtime may READ
        local-only content, but a bundle is built to travel. Export must not
        consult the profile at all — so there is no profile to pass, and the
        marking excludes unconditionally."""
        tmp = self._export_with(dict(BASE, id="note-secret", ai_use="local-only"))
        self.assertEqual(exported_names(tmp), set())

    def test_private_never_exports_without_review(self):
        tmp = self._export_with(dict(BASE, id="note-p", classification="private"))
        self.assertEqual(exported_names(tmp), set())

    def test_restricted_and_prohibited_never_export(self):
        for meta in (dict(BASE, id="note-r", classification="restricted"),
                     dict(BASE, id="note-q", ai_use="prohibited")):
            tmp = self._export_with(meta)
            self.assertEqual(exported_names(tmp), set())

    def test_unrecognised_governance_value_fails_closed(self):
        """DEC-066 on the export path: a typo must never widen access."""
        for meta in (dict(BASE, id="note-a", classification="Private"),
                     dict(BASE, id="note-b", ai_use="local_only")):
            tmp = self._export_with(meta)
            self.assertEqual(exported_names(tmp), set())

    def test_draft_and_stale_never_export(self):
        """Staging is not knowledge (Principle 26)."""
        for st in ("draft", "stale", "superseded", "archived"):
            tmp = self._export_with(dict(BASE, id="note-d", status=st))
            self.assertEqual(exported_names(tmp), set(), f"status {st} exported")

    def test_structural_signposts_never_export(self):
        tmp = self._export_with(dict(BASE, id="doc-about", type="system-doc"),
                                relpath="20 Knowledge/_ABOUT.md")
        self.assertEqual(exported_names(tmp), set())


class TestExportConformance(unittest.TestCase):
    def setUp(self):
        self.tmp = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_bundle_is_okf_conformant(self):
        note(self.tmp, "20 Knowledge/a.md",
             dict(BASE, id="note-a", tags=["x"]), "# Alpha\n\nBody.\n")
        okfexport.run(self.tmp, Args("knowledge"), Report("okf-export"))
        b = os.path.join(self.tmp, "40 Outputs", "okf-knowledge")
        # Conformance rule 1: every non-reserved .md has frontmatter with a
        # non-empty `type`.
        n = parse_file(os.path.join(b, "alpha.md"), b)
        self.assertEqual(n.meta["type"], "note")
        self.assertEqual(n.meta["title"], "Alpha")
        self.assertEqual(n.meta["description"], "A summary.")
        self.assertEqual(n.meta["tags"], ["x"])
        # Conformance rule 3: reserved files present and structured.
        self.assertTrue(os.path.exists(os.path.join(b, "index.md")))
        self.assertTrue(os.path.exists(os.path.join(b, BUNDLE_MARKER)))

    def test_superset_rides_as_extra_keys(self):
        """The spec permits extra keys and asks consumers to preserve them — which
        is precisely why AI OS loses nothing by emitting the standard."""
        note(self.tmp, "20 Knowledge/a.md", dict(BASE, id="note-a", domain="shared"))
        okfexport.run(self.tmp, Args("knowledge"), Report("okf-export"))
        b = os.path.join(self.tmp, "40 Outputs", "okf-knowledge")
        n = parse_file(os.path.join(b, "title.md"), b)
        for k in ("id", "verification", "domain", "created", "updated"):
            self.assertIn(k, n.meta, f"AI OS field '{k}' dropped on export")
        # `status` is the one AI OS name v0.2 took: the OKF key holds the mapped
        # value and the vault's own value rides beside it, so neither field lies.
        self.assertEqual(n.meta["status"], "stable")
        self.assertEqual(n.meta["x_aios_status"], "active")

    def test_title_falls_back_to_filename(self):
        note(self.tmp, "20 Knowledge/some-note.md", dict(BASE, id="note-a"),
             "No heading here.\n")
        okfexport.run(self.tmp, Args("knowledge"), Report("okf-export"))
        self.assertEqual(exported_names(self.tmp), {"some-note.md"})

    def test_concept_never_takes_a_reserved_filename(self):
        note(self.tmp, "20 Knowledge/n.md", dict(BASE, id="note-a"), "# Index\n\nBody.\n")
        okfexport.run(self.tmp, Args("knowledge"), Report("okf-export"))
        self.assertEqual(exported_names(self.tmp), {"index-concept.md"})

    def test_refuses_to_overwrite_a_foreign_directory(self):
        os.makedirs(os.path.join(self.tmp, "40 Outputs", "okf-knowledge"))
        write_file(os.path.join(self.tmp, "40 Outputs", "okf-knowledge", "mine.md"), "x", mode="w")
        rep = Report("okf-export")
        okfexport.run(self.tmp, Args("knowledge"), rep)
        self.assertFalse(rep.ok)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "40 Outputs",
                                                    "okf-knowledge", "mine.md")))

    def test_unknown_scope_is_an_error(self):
        rep = Report("okf-export")
        okfexport.run(self.tmp, Args("nonsuch"), rep)
        self.assertFalse(rep.ok)


class TestTimestamp(unittest.TestCase):
    def test_date_becomes_iso_datetime(self):
        self.assertEqual(to_timestamp("2026-07-15"), "2026-07-15T00:00:00+00:00")

    def test_existing_datetime_passes_through(self):
        self.assertEqual(to_timestamp("2026-05-28T23:31:54+00:00"),
                         "2026-05-28T23:31:54+00:00")

    def test_absent_updated_yields_no_timestamp(self):
        self.assertIsNone(to_timestamp(None))


class TestImport(unittest.TestCase):
    def setUp(self):
        self.tmp = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bundle = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.bundle, True)

    def concept(self, name, meta, body="Body.\n"):
        p = os.path.join(self.bundle, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n\n" + body)

    def imported(self):
        d = os.path.join(self.tmp, "30 Sources", "OKF " + os.path.basename(self.bundle))
        if not os.path.isdir(d):
            return d, []
        found = []
        for dp, _dn, fns in os.walk(d):
            found += [os.path.relpath(os.path.join(dp, f), d).replace("\\", "/")
                      for f in fns]
        return d, sorted(found)

    def test_lands_as_immutable_draft_evidence_never_canon(self):
        """The load-bearing rule: an OKF bundle is a *source*. A machine may not
        turn foreign material into canon on its own."""
        self.concept("a.md", {"type": "BigQuery Table", "title": "Posts",
                              "description": "A table.",
                              "resource": "https://example.com/t"})
        okfimport.run(self.tmp, Args(self.bundle), Report("okf-import"))
        d, files = self.imported()
        self.assertEqual(files, ["a.md"])
        n = parse_file(os.path.join(d, "a.md"), d)
        self.assertEqual(n.meta["type"], "source")
        self.assertEqual(n.meta["status"], "draft")
        self.assertEqual(n.meta["verification"], "unverified")
        self.assertEqual(n.meta["x_okf_type"], "BigQuery Table")
        self.assertEqual(n.meta["original_location"], "https://example.com/t")

    def test_reserved_filenames_are_not_concepts(self):
        self.concept("index.md", {"type": "x", "title": "Index"})
        self.concept("log.md", {"type": "x", "title": "Log"})
        self.concept("real.md", {"type": "x", "title": "Real"})
        okfimport.run(self.tmp, Args(self.bundle), Report("okf-import"))
        self.assertEqual(self.imported()[1], ["real.md"])

    def test_document_without_type_is_skipped(self):
        """The spec's one conformance rule for a concept document."""
        self.concept("bad.md", {"title": "No type"})
        self.concept("good.md", {"type": "x", "title": "Good"})
        rep = Report("okf-import")
        okfimport.run(self.tmp, Args(self.bundle), rep)
        self.assertEqual(self.imported()[1], ["good.md"])
        self.assertTrue(any("not a conformant OKF concept" in w for w in rep.warnings))

    def test_refuses_to_overwrite_captured_evidence(self):
        self.concept("a.md", {"type": "x", "title": "A"})
        okfimport.run(self.tmp, Args(self.bundle), Report("okf-import"))
        rep = Report("okf-import")
        okfimport.run(self.tmp, Args(self.bundle), rep)
        self.assertFalse(rep.ok)
        self.assertTrue(any("immutable" in e for e in rep.errors))

    def test_id_collision_with_vault_canon_is_suffixed_never_overwritten(self):
        note(self.tmp, "20 Knowledge/x.md", dict(BASE, id="source-posts", type="source",
                                                 subtype="document"))
        self.concept("a.md", {"type": "x", "title": "Posts"})
        okfimport.run(self.tmp, Args(self.bundle), Report("okf-import"))
        d, files = self.imported()
        n = parse_file(os.path.join(d, files[0]), d)
        self.assertEqual(n.meta["id"], "source-posts-2")

    def test_bundle_hierarchy_and_filenames_survive_so_internal_links_resolve(self):
        """OKF bundles are hierarchical and their concepts link to each other with
        ordinary relative paths. Flattening or renaming breaks every such link —
        68 of them on Google's own stackoverflow bundle, before this guard."""
        self.concept("tables/comments.md", {"type": "T", "title": "Comments"},
                     "See [posts](posts_questions.md) and "
                     "[ds](../datasets/stackoverflow.md).\n")
        self.concept("tables/posts_questions.md", {"type": "T", "title": "Questions"})
        self.concept("datasets/stackoverflow.md", {"type": "D", "title": "Dataset"})
        okfimport.run(self.tmp, Args(self.bundle), Report("okf-import"))
        d, files = self.imported()
        self.assertEqual(files, ["datasets/stackoverflow.md",
                                 "tables/comments.md",
                                 "tables/posts_questions.md"])
        # The links the producer wrote still point at real files.
        for target in ("tables/posts_questions.md", "datasets/stackoverflow.md"):
            self.assertTrue(os.path.exists(os.path.join(d, target)))

    def test_forbidden_filename_characters_are_sanitised(self):
        self.concept("a.md", {"type": "x", "title": "A"})
        os.rename(os.path.join(self.bundle, "a.md"), os.path.join(self.bundle, "we|ird.md"))
        okfimport.run(self.tmp, Args(self.bundle), Report("okf-import"))
        self.assertEqual(self.imported()[1], ["we-ird.md"])

    def test_empty_bundle_is_an_error(self):
        rep = Report("okf-import")
        okfimport.run(self.tmp, Args(self.bundle), rep)
        self.assertFalse(rep.ok)


class TestExportV02(unittest.TestCase):
    """What v0.2 adds on the way out, and what it deliberately declines to add."""

    def setUp(self):
        self.tmp = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def emit(self, meta, **kw):
        note(self.tmp, "20 Knowledge/a.md", meta, "# Alpha\n\nBody.\n")
        rep = Report("okf-export")
        okfexport.run(self.tmp, Args("knowledge", **kw), rep)
        b = os.path.join(self.tmp, "40 Outputs", "okf-knowledge")
        return parse_file(os.path.join(b, "alpha.md"), b), rep, b

    def test_status_is_mapped_into_the_okf_vocabulary(self):
        n, _, _ = self.emit(dict(BASE, id="note-a", status="review-due"))
        self.assertEqual(n.meta["status"], "stable")
        self.assertEqual(n.meta["x_aios_status"], "review-due")

    def test_review_due_becomes_stale_after(self):
        n, _, _ = self.emit(dict(BASE, id="note-a", review_due="2026-12-31"))
        self.assertEqual(n.meta["stale_after"], "2026-12-31")
        self.assertEqual(n.meta["review_due"], "2026-12-31")   # the AI OS field also rides

    def test_verified_is_never_emitted_however_verified_the_note_is(self):
        """The honesty gate. AI OS records a verification *grade*, with no actor
        and no date; v0.2's `verified` records confirmation *events*. Emitting one
        from the other would invent both halves of a trust signal."""
        n, _, _ = self.emit(dict(BASE, id="note-a", verification="verified"))
        self.assertNotIn("verified", n.meta)
        self.assertEqual(n.meta["verification"], "verified")

    def test_no_author_means_no_generated_and_the_legacy_timestamp_instead(self):
        n, rep, _ = self.emit(dict(BASE, id="note-a"))
        self.assertNotIn("generated", n.meta)
        self.assertEqual(n.meta["timestamp"], "2026-07-15T00:00:00+00:00")
        self.assertTrue(any("no --author given" in w for w in rep.warnings))

    def test_an_asserted_author_becomes_generated(self):
        n, _, _ = self.emit(dict(BASE, id="note-a"), author="human:jo")
        self.assertEqual(n.meta["generated"],
                         {"by": "human:jo", "at": "2026-07-15T00:00:00+00:00"})
        self.assertNotIn("timestamp", n.meta)

    def test_a_malformed_actor_is_refused_before_anything_is_written(self):
        note(self.tmp, "20 Knowledge/a.md", dict(BASE, id="note-a"), "# A\n")
        rep = Report("okf-export")
        okfexport.run(self.tmp, Args("knowledge", author="Jo Bloggs"), rep)
        self.assertFalse(rep.ok)
        self.assertFalse(os.path.isdir(os.path.join(self.tmp, "40 Outputs", "okf-knowledge")))

    def test_the_bundle_declares_its_version_in_index_and_marker(self):
        _, _, b = self.emit(dict(BASE, id="note-a"))
        with open(os.path.join(b, "index.md"), encoding="utf-8") as fh:
            self.assertTrue(fh.read().startswith('---\nokf_version: "0.2"\n---'))
        with open(os.path.join(b, BUNDLE_MARKER), encoding="utf-8") as fh:
            self.assertEqual(yaml.safe_load(fh)["okf_version"], "0.2")

    def test_sources_become_okf_entries_for_records_in_the_bundle(self):
        note(self.tmp, "20 Knowledge/cited.md", dict(BASE, id="note-cited"), "# Cited\n")
        n, _, _ = self.emit(dict(BASE, id="note-a", sources=["note-cited"]))
        self.assertEqual(n.meta["sources"],
                         [{"id": "note-cited", "resource": "/cited.md", "title": "Cited",
                           "last_modified": "2026-07-15"}])
        self.assertEqual(n.meta["x_aios_sources"], ["note-cited"])

    def test_a_reference_outside_the_bundle_is_not_dressed_up_as_provenance(self):
        """§5.1 wants a followable artifact or a population descriptor. A vault id
        from a folder that was not exported is neither, so it stays an AI OS field
        under an AI OS name rather than becoming a dangling `resource`."""
        note(self.tmp, "30 Sources/s.md",
             dict(BASE, id="source-off", type="source", subtype="document"), "# Off\n")
        n, _, _ = self.emit(dict(BASE, id="note-a", sources=["source-off"]))
        self.assertNotIn("sources", n.meta)
        self.assertEqual(n.meta["x_aios_sources"], ["source-off"])

    def test_v01_mode_emits_the_older_shape_unchanged(self):
        n, rep, b = self.emit(dict(BASE, id="note-a", sources=["source-x"],
                                   review_due="2026-12-31"),
                              okf_version="0.1")
        self.assertEqual(rep.info["okf_version"], "0.1")
        self.assertEqual(n.meta["timestamp"], "2026-07-15T00:00:00+00:00")
        self.assertNotIn("generated", n.meta)
        self.assertNotIn("stale_after", n.meta)
        self.assertEqual(n.meta["status"], "active")   # the AI OS value, unmapped

    def test_author_is_refused_for_v01_rather_than_silently_dropped(self):
        note(self.tmp, "20 Knowledge/a.md", dict(BASE, id="note-a"), "# A\n")
        rep = Report("okf-export")
        okfexport.run(self.tmp, Args("knowledge", okf_version="0.1", author="human:jo"), rep)
        self.assertFalse(rep.ok)

    def test_an_unknown_version_is_refused(self):
        rep = Report("okf-export")
        okfexport.run(self.tmp, Args("knowledge", okf_version="0.9"), rep)
        self.assertFalse(rep.ok)


class TestExportReferenceFence(unittest.TestCase):
    """The privacy fence applied to *references*, not just content.

    A vault id is a slug of its record's title, so `entities: [person-jane-doe]`
    carries a name out of the vault even when the record itself stayed home. The
    content fence has always held; before this build the reference did not."""

    def _export(self, extra):
        tmp = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        note(tmp, "20 Knowledge/private.md",
             dict(BASE, id="note-private-thing", classification="private"), "# Private\n")
        note(tmp, "20 Knowledge/a.md", dict(BASE, id="note-a", **extra), "# Alpha\n")
        okfexport.run(tmp, Args("knowledge"), Report("okf-export"))
        b = os.path.join(tmp, "40 Outputs", "okf-knowledge")
        blob = ""
        for dp, _dn, fns in os.walk(b):
            for f in fns:
                with open(os.path.join(dp, f), encoding="utf-8") as fh:
                    blob += fh.read()
        return blob

    def test_no_id_list_field_carries_an_excluded_record_out(self):
        for field in ("sources", "related", "derived_from", "depends_on",
                      "supports", "contradicts", "entities"):
            blob = self._export({field: ["note-private-thing"]})
            self.assertNotIn("note-private-thing", blob,
                             f"'{field}' carried an excluded record's id out of the vault")

    def test_supersedes_and_superseded_by_are_fenced_too(self):
        for field in ("supersedes", "superseded_by"):
            blob = self._export({field: "note-private-thing"})
            self.assertNotIn("note-private-thing", blob)

    def test_a_reference_to_a_record_that_may_travel_is_kept(self):
        tmp = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        note(tmp, "20 Knowledge/ok.md", dict(BASE, id="note-ok"), "# Ok\n")
        note(tmp, "20 Knowledge/a.md", dict(BASE, id="note-a", related=["note-ok"]), "# Alpha\n")
        okfexport.run(tmp, Args("knowledge"), Report("okf-export"))
        b = os.path.join(tmp, "40 Outputs", "okf-knowledge")
        self.assertEqual(parse_file(os.path.join(b, "alpha.md"), b).meta["related"], ["note-ok"])

    def test_an_unrecognised_status_fails_closed_instead_of_becoming_stable(self):
        """DEC-066 on a branch that had only a blacklist: `status: Active` is not
        `active`, and v0.2's mapping would otherwise have laundered it to
        `status: stable` — an unknown value promoted to a published lifecycle."""
        tmp = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        note(tmp, "20 Knowledge/a.md", dict(BASE, id="note-a", status="Active"), "# Alpha\n")
        okfexport.run(tmp, Args("knowledge"), Report("okf-export"))
        self.assertEqual(exported_names(tmp), set())


class TestImportV02(unittest.TestCase):
    """A v0.2 producer's own claims land as evidence — all of them, and none of
    them promoted."""

    def setUp(self):
        self.tmp = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bundle = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.bundle, True)

    def land(self, meta, body="Body.\n"):
        with open(os.path.join(self.bundle, "c.md"), "w", encoding="utf-8") as fh:
            fh.write("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n\n" + body)
        okfimport.run(self.tmp, Args(self.bundle), Report("okf-import"))
        d = os.path.join(self.tmp, "30 Sources", "OKF " + os.path.basename(self.bundle))
        return parse_file(os.path.join(d, "c.md"), d)

    def test_the_v02_families_land_verbatim(self):
        n = self.land({"type": "Metric", "title": "Revenue", "status": "deprecated",
                       "stale_after": "2026-12-31",
                       "generated": {"by": "agent/1.0", "at": "2026-06-20T22:53:05Z"},
                       "verified": [{"by": "human:jo", "at": "2026-06-25T09:00:00Z"}],
                       "sources": [{"id": "p", "resource": "https://example.com"}]})
        self.assertEqual(n.meta["x_okf_status"], "deprecated")
        self.assertEqual(n.meta["x_okf_stale_after"], "2026-12-31")
        self.assertEqual(n.meta["x_okf_generated"]["by"], "agent/1.0")
        self.assertEqual(n.meta["x_okf_verified"][0]["by"], "human:jo")
        self.assertEqual(n.meta["x_okf_sources"][0]["id"], "p")

    def test_a_bare_verified_mapping_is_read_as_a_one_element_list(self):
        """§5.2/§11: a consumer MUST treat it that way. The spec's own examples
        and Appendix A use the bare form."""
        n = self.land({"type": "Metric", "title": "R",
                       "verified": {"by": "human:jo", "at": "2026-06-25T09:00:00Z"}})
        self.assertEqual(len(n.meta["x_okf_verified"]), 1)
        self.assertEqual(n.meta["x_okf_verified"][0]["by"], "human:jo")

    def test_a_producers_verified_never_raises_this_vaults_verification(self):
        """It cleared *their* gate, not this one."""
        n = self.land({"type": "Metric", "title": "R",
                       "verified": {"by": "human:jo", "at": "2026-06-25T09:00:00Z"},
                       "status": "stable"})
        self.assertEqual(n.meta["verification"], "unverified")
        self.assertEqual(n.meta["status"], "draft")

    def test_stale_after_becomes_the_vaults_own_review_horizon(self):
        n = self.land({"type": "Metric", "title": "R", "stale_after": "2026-12-31"})
        self.assertEqual(n.meta["review_due"], "2026-12-31")

    def test_an_unmapped_producer_field_is_preserved_not_dropped(self):
        """An Attested Computation's contract (§10) has no AI OS equivalent, and
        a source is an immutable capture: nothing the bundle asserted is lost."""
        n = self.land({"type": "Attested Computation", "title": "Revenue",
                       "runtime": "bigquery",
                       "executor": {"resource": "skills/run.md", "receipt": ["job_id"]},
                       "attester": {"resource": "attesters/x.py"}})
        self.assertEqual(n.meta["x_okf_extra"]["runtime"], "bigquery")
        self.assertEqual(n.meta["x_okf_extra"]["attester"]["resource"], "attesters/x.py")

    def test_a_v01_bundle_still_lands_through_the_legacy_fallback(self):
        n = self.land({"type": "BigQuery Table", "title": "Old",
                       "timestamp": "2026-05-28T00:00:00+00:00"})
        self.assertEqual(n.meta["x_okf_timestamp"], "2026-05-28T00:00:00+00:00")


class TestRoundTrip(unittest.TestCase):
    """The portability claim, proven: export → re-import → zero loss on the
    fields the two formats share.

    The comparison is ORIGINAL note → LANDED note. Comparing the emitted bundle to
    the landed note instead would pass over a build that dropped a field on the way
    out, which is exactly where v0.2's mapping work happens."""

    def _round_trip(self, meta, body, **kw):
        a = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, a, True)
        note(a, "20 Knowledge/attention.md", meta, body)
        okfexport.run(a, Args("knowledge", **kw), Report("okf-export"))
        bundle = os.path.join(a, "40 Outputs", "okf-knowledge")
        b = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, b, True)
        okfimport.run(b, Args(bundle), Report("okf-import"))
        d = os.path.join(b, "30 Sources", "OKF okf-knowledge")
        return parse_file(os.path.join(d, "attention-economics.md"), d)

    def test_round_trip_preserves_every_shared_field(self):
        meta = dict(BASE, id="note-attention", tags=["economics", "attention"],
                    review_due="2026-12-31", original_location="https://example.com/src")
        body = "# Attention Economics\n\nAttention is the binding constraint.\n"
        landed = self._round_trip(meta, body, author="human:jo")

        self.assertEqual(landed.meta["x_okf_type"], meta["type"])
        self.assertEqual(landed.meta["x_okf_title"], "Attention Economics")
        self.assertEqual(landed.meta["summary"], meta["summary"])
        self.assertEqual(landed.meta["tags"], meta["tags"])
        self.assertEqual(landed.meta["x_okf_resource"], meta["original_location"])
        self.assertEqual(landed.meta["review_due"], meta["review_due"])
        self.assertTrue(landed.meta["x_okf_generated"]["at"].startswith(meta["updated"]))
        self.assertEqual(landed.meta["x_okf_generated"]["by"], "human:jo")
        # The AI OS superset is recoverable from the extras it rode out in.
        extra = landed.meta["x_okf_extra"]
        for k in ("id", "created", "updated", "verification"):
            self.assertEqual(extra[k], meta[k], f"AI OS field '{k}' lost in the round trip")
        self.assertEqual(extra["x_aios_status"], meta["status"])
        # And the concept's prose is evidence: byte-identical, never reworded.
        self.assertEqual(landed.body.strip(), body.strip())

    def test_round_trip_at_v01_preserves_the_same_fields(self):
        meta = dict(BASE, id="note-attention", tags=["economics"],
                    original_location="https://example.com/src")
        body = "# Attention Economics\n\nAttention is the binding constraint.\n"
        landed = self._round_trip(meta, body, okf_version="0.1")
        self.assertEqual(landed.meta["x_okf_title"], "Attention Economics")
        self.assertEqual(landed.meta["summary"], meta["summary"])
        self.assertEqual(landed.meta["tags"], meta["tags"])
        self.assertEqual(landed.meta["x_okf_timestamp"], "2026-07-15T00:00:00+00:00")
        self.assertEqual(landed.body.strip(), body.strip())

    def test_export_of_a_bundle_does_not_collide_with_its_own_source_notes(self):
        """A bundle lives inside the vault's own folders. Without the marker
        pruning it, the exported copy of every note duplicates that note's `id`
        — proven live before this guard existed."""
        from lib.frontmatter import iter_markdown
        a = make_vault(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, a, True)
        note(a, "20 Knowledge/x.md", dict(BASE, id="note-x"))
        okfexport.run(a, Args("knowledge"), Report("okf-export"))
        ids = [n.meta["id"] for n in iter_markdown(a) if n.meta and n.meta.get("id")]
        self.assertEqual(ids.count("note-x"), 1,
                         "the exported bundle was scanned as vault canon")


if __name__ == "__main__":
    unittest.main()
