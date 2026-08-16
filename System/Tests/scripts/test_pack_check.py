"""aios pack-check — pack content validated inside its own namespace (DEC-113).

`Packs/` is pruned from the canon walk (DEC-061/DEC-067) and that is correct: a
pack ships its own README.md and CHANGELOG.md, and its ids are its own. The
consequence was that on a pack-heavy vault most of the markdown was outside
every mechanical check — 260 of 446 files on the instance this was measured on.

THE HARD BAR IS DEC-067 NON-REGRESSION. `TestDEC067NotRegressed` is the guard:
two packs and the vault each carrying README.md/CHANGELOG.md and a colliding id
must stay clean, and `test_packs_stays_in_the_default_skip_set` fails loudly if
anyone later removes `Packs` from `frontmatter.SKIP_DIRS` to "make pack-check
simpler". Coverage is not canon.
"""
import os, sys, subprocess, tempfile, unittest

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)

from test_pack import _vault, aios                 # noqa: E402
from lib import frontmatter                        # noqa: E402
from lib.report import Report                      # noqa: E402
from cmd import packcheck as pc_mod                # noqa: E402
from cmd import dupes as dupes_mod, validate as val_mod, links as links_mod  # noqa: E402


class Args:
    json = False; message = None; confirm = False; target = None


NOTE = """---
id: note-{slug}
type: note
status: active
created: 2026-07-27
updated: 2026-07-27
summary: {slug}
---
# {title}

{body}
"""


def _write_text(path, text):
    with open(path, "w") as stream:
        stream.write(text)


def _pack(tmp, name, files, manifest=None):
    """An INSTALLED pack: Packs/<name>/ with a pack.yaml."""
    root = os.path.join(tmp, "Packs", name)
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "pack.yaml"), "w") as stream:
        stream.write(manifest or (
            f"id: pack-{name}\nname: {name}\nversion: 1.0.0\nkind: role-pack\n"
            f"license: MIT\nsource: https://example.com/{name}\n"))
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as stream:
            stream.write(body)
    return root


def _run(tmp):
    rep = Report("pack-check")
    pc_mod.run(tmp, Args(), rep)
    return rep


def _master(tmp, is_master=True):
    mp = os.path.join(tmp, "SYSTEM-MANIFEST.yaml")
    role = "generic-master" if is_master else "personal-instance"
    with open(mp) as stream:
        text = stream.read().replace("instance_role: personal-instance",
                                     f"instance_role: {role}")
    with open(mp, "w") as stream:
        stream.write(text)


class TestDEC067NotRegressed(unittest.TestCase):
    """The crux. Nothing here may ever go red."""

    def _colliding(self, tmp):
        _vault(tmp)
        _write_text(os.path.join(tmp, "README.md"), "# The vault README\n")
        _write_text(os.path.join(tmp, "CHANGELOG.md"), "# The vault changelog\n")
        _write_text(os.path.join(tmp, "20 Knowledge", "shared.md"),
                    NOTE.format(slug="shared", title="Shared", body="vault copy"))
        for name in ("alpha", "beta"):
            _pack(tmp, name, {
                "README.md": f"# {name} README\n",
                "CHANGELOG.md": f"# {name} changelog\n",
                "content/shared.md": NOTE.format(slug="shared", title="Shared",
                                                 body=f"{name} copy"),
            })

    def test_two_packs_and_the_vault_can_all_carry_readme_and_a_colliding_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._colliding(tmp)
            for name, mod in (("dupes", dupes_mod), ("validate", val_mod),
                              ("links", links_mod)):
                rep = Report(name); mod.run(tmp, Args(), rep)
                self.assertEqual(
                    [e for e in rep.errors if "README" in e or "CHANGELOG" in e
                     or "note-shared" in e], [],
                    f"{name} must never collide a pack's files with the vault's")

    def test_no_pack_path_ever_enters_the_canon_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._colliding(tmp)
            scanned = [n.relpath for n in frontmatter.iter_markdown(tmp)]
            self.assertFalse([p for p in scanned if p.startswith("Packs")],
                             f"canon walk must not see Packs/: {scanned}")

    def test_the_canon_id_space_has_no_duplicate_from_a_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._colliding(tmp)
            ids = [str(n.meta["id"]) for n in frontmatter.iter_markdown(tmp)
                   if n.meta.get("id")]
            self.assertEqual(len(ids), len(set(ids)), ids)

    def test_packs_stays_in_the_default_skip_set(self):
        """THE GUARD. If a later change removes `Packs` from SKIP_DIRS to make
        pack-check simpler, DEC-067 regresses silently and every pack README
        starts colliding with the vault's. Fail here, loudly, first."""
        self.assertIn("Packs", frontmatter.SKIP_DIRS,
                      "DEC-067: `Packs` must stay pruned from the DEFAULT canon "
                      "walk. pack-check reads packs by passing a narrowed skip "
                      "set, never by widening this one.")

    def test_iter_markdown_default_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._colliding(tmp)
            default = {n.relpath for n in frontmatter.iter_markdown(tmp)}
            explicit = {n.relpath for n in
                        frontmatter.iter_markdown(tmp, skip_dirs=frontmatter.SKIP_DIRS)}
            self.assertEqual(default, explicit)


class TestFindings(unittest.TestCase):
    def test_clean_pack_reports_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp)
            _pack(tmp, "alpha", {"content/a.md":
                                 NOTE.format(slug="a", title="A", body="clean")})
            rep = _run(tmp)
            self.assertEqual(rep.errors, [], rep.errors)
            self.assertIn("alpha", rep.info["packs_checked"])

    def test_broken_wikilink_inside_a_pack_is_found(self):
        """The 20-link class: live for a day, invisible to every gate."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp)
            _pack(tmp, "alpha", {"content/a.md": NOTE.format(
                slug="a", title="A", body="see [[No Such Note]]")})
            rep = _run(tmp)
            self.assertTrue(any("No Such Note" in e for e in rep.errors), rep.errors)

    def test_invalid_subtype_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp)
            _pack(tmp, "alpha", {"content/a.md": NOTE.format(
                slug="a", title="A", body="x").replace(
                    "type: note", "type: note\nsubtype: competitive-analysis")})
            rep = _run(tmp)
            self.assertTrue(any("subtype" in e for e in rep.errors), rep.errors)

    def test_id_type_prefix_mismatch_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp)
            _pack(tmp, "alpha", {"content/a.md": NOTE.format(
                slug="a", title="A", body="x").replace("id: note-a", "id: report-a")})
            rep = _run(tmp)
            self.assertTrue(any("type prefix" in e for e in rep.errors), rep.errors)

    def test_duplicate_id_within_one_pack_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp)
            body = NOTE.format(slug="a", title="A", body="x")
            _pack(tmp, "alpha", {"content/a.md": body, "content/b.md": body})
            rep = _run(tmp)
            self.assertTrue(any("duplicate id" in e for e in rep.errors), rep.errors)

    def test_id_shared_with_the_vault_is_a_warning_never_an_error(self):
        """A pack is entitled to its own namespace (spec §3)."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp)
            _write_text(os.path.join(tmp, "20 Knowledge", "a.md"),
                        NOTE.format(slug="a", title="A", body="vault"))
            _pack(tmp, "alpha", {"content/a.md":
                                 NOTE.format(slug="a", title="A2", body="pack")})
            rep = _run(tmp)
            self.assertEqual([e for e in rep.errors if "note-a" in e], [], rep.errors)
            self.assertTrue(any("keeps" in w and "own namespace" in w
                                for w in rep.warnings), rep.warnings)

    def test_missing_frontmatter_is_a_warning_not_an_error(self):
        """34 of them today, mostly READMEs — an error and nobody runs the check."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp)
            _pack(tmp, "alpha", {"content/readme.md": "# just a readme\n"})
            rep = _run(tmp)
            self.assertEqual(rep.errors, [], rep.errors)
            self.assertTrue(any("no frontmatter" in w for w in rep.warnings))


class TestRoleScopedSeverity(unittest.TestCase):
    """DEC-083: master = error, instance = warning — except ALWAYS_STRICT."""

    def _broken(self, tmp, master):
        _vault(tmp); _master(tmp, master)
        _pack(tmp, "alpha", {"content/a.md": NOTE.format(
            slug="a", title="A", body="see [[No Such Note]]")})
        return _run(tmp)

    def test_master_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._broken(tmp, True)
            self.assertTrue(rep.errors)

    def test_personal_instance_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._broken(tmp, False)
            self.assertEqual(rep.errors, [], rep.errors)
            self.assertTrue(any("No Such Note" in w for w in rep.warnings))

    def test_always_strict_classes_are_never_downgraded(self):
        """A parse failure, a broken id grammar, a duplicate id, a pack claiming
        governance authority, or a committed secret is not a matter of taste on
        the user's own content."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp, False)          # personal-instance
            dup = NOTE.format(slug="d", title="D", body="x")
            _pack(tmp, "alpha", {
                "content/broken.md": "---\nid: [unclosed\ntype: note\n---\nbody\n",
                "content/prefix.md": NOTE.format(slug="p", title="P", body="x"
                                                 ).replace("id: note-p", "id: report-p"),
                "content/d1.md": dup,
                "content/d2.md": dup,
                "content/gov.md": NOTE.format(slug="g", title="G", body="x").replace(
                    "type: note", "type: note\ncanonical_for: system-architecture"),
                "content/leak.md": NOTE.format(
                    slug="k", title="K", body="api_key: sk9dK2mQ7vB4nR8tZ1xW5yE0"),
            })
            rep = _run(tmp)
            joined = " ".join(rep.errors)
            for expected in ("frontmatter", "type prefix", "duplicate id",
                             "canonical_for", "credential"):
                self.assertIn(expected, joined,
                              f"{expected} must stay an ERROR on a personal instance")

    def test_a_documented_placeholder_is_not_reported_as_a_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _master(tmp)
            _pack(tmp, "alpha", {"content/a.md": NOTE.format(
                slug="a", title="A", body="api_key: 'FAKEFAKEFAKEFAKEFAKE1234'")})
            rep = _run(tmp)
            self.assertEqual([e for e in rep.errors if "credential" in e], [], rep.errors)


class TestCrossBoundaryCitation(unittest.TestCase):
    """Spec §6, option (a): a vault note may cite a pack id without erroring."""

    def _cited(self, tmp):
        _vault(tmp)
        _pack(tmp, "alpha", {"content/src.md": """---
id: source-northwind
type: source
status: active
created: 2026-07-27
updated: 2026-07-27
summary: case study
---
# Northwind
"""})
        _write_text(os.path.join(tmp, "20 Knowledge", "cite.md"),
            NOTE.format(slug="cite", title="Cite", body="body").replace(
                "summary: cite", "summary: cite\nsources: [source-northwind]"))

    def test_vault_note_citing_a_pack_id_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._cited(tmp)
            rep = Report("links"); links_mod.run(tmp, Args(), rep)
            self.assertEqual(rep.errors, [], rep.errors)
            self.assertTrue(any("source-northwind" in r
                                for r in rep.info.get("pack_references", [])))

    def test_a_genuinely_unknown_id_is_still_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._cited(tmp)
            _write_text(os.path.join(tmp, "20 Knowledge", "bad.md"),
                NOTE.format(slug="bad", title="Bad", body="b").replace(
                    "summary: bad", "summary: bad\nsources: [source-does-not-exist]"))
            rep = Report("links"); links_mod.run(tmp, Args(), rep)
            self.assertTrue(any("source-does-not-exist" in e for e in rep.errors))

    def test_pack_ids_never_enter_the_canon_id_space(self):
        """Resolution is not membership — the whole basis of option (a)."""
        with tempfile.TemporaryDirectory() as tmp:
            self._cited(tmp)
            ids = {str(n.meta["id"]) for n in frontmatter.iter_markdown(tmp)
                   if n.meta.get("id")}
            self.assertNotIn("source-northwind", ids)

    def test_remove_refuses_and_names_the_citing_notes(self):
        """§6.3 — removing the pack would leave those notes citing nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            self._cited(tmp)
            r = aios(tmp, "pack", "alpha", "--remove", "--confirm")
            self.assertIn("refusing to remove", r.stdout)
            self.assertIn("source-northwind", r.stdout)
            self.assertIn("cite.md", r.stdout)
            self.assertTrue(os.path.isdir(os.path.join(tmp, "Packs", "alpha")))

    def test_remove_proceeds_when_nothing_cites_the_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            _pack(tmp, "alpha", {"content/a.md":
                                 NOTE.format(slug="a", title="A", body="x")})
            r = aios(tmp, "pack", "alpha", "--remove", "--confirm")
            self.assertNotIn("refusing to remove", r.stdout)
            self.assertFalse(os.path.isdir(os.path.join(tmp, "Packs", "alpha")))


class TestLinksExtensionBug(unittest.TestCase):
    """A separate defect, found by the pack work and fixed on its own terms:
    `[[Guide]]` and `[[Guide.md]]` returned opposite verdicts, and the passing
    spelling bypassed the id/title check."""

    def test_both_spellings_of_a_markdown_wikilink_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp)
            os.makedirs(os.path.join(tmp, "30 Sources"), exist_ok=True)
            _write_text(os.path.join(tmp, "30 Sources", "Guide.md"),
                NOTE.format(slug="guide", title="Guide", body="target"))
            _write_text(os.path.join(tmp, "20 Knowledge", "a.md"),
                NOTE.format(slug="a", title="A", body="[[Guide]] and [[Guide.md]]"))
            rep = Report("links"); links_mod.run(tmp, Args(), rep)
            unresolved = [w for w in rep.warnings if "unresolved wikilink" in w]
            self.assertEqual(unresolved, [], unresolved)


class TestTemplatePlaceholders(unittest.TestCase):
    """DEC-115 — a template's placeholder id is a blank, not a malformed id.

    THE LIVE DEFECT: a `generic-master` instance whose role pack ships 22
    templates reported **19 duplicate-id errors** — `note-<slug>` and
    `source-<slug>`, the identical convention the product's own
    `System/Templates/` uses (it carries `procedure-<slug>` twice), on which
    `aios dupes` is green. `pack-check` re-derived the id rules without the
    placeholder tolerance `validate` has always had. The bump was blocked by
    the checker being wrong about the product's own shipped shape.

    Both directions are pinned: templates tolerated, real records not.
    """

    TEMPLATE = ("---\nid: {pid}\ntype: note\nstatus: draft\ncreated: 2026-07-27\n"
                "updated: 2026-07-27\nsummary: \"\"\n---\n# {title}\n\n{body}\n")

    def _rep(self, tmp, files):
        _vault(tmp)
        _master(tmp, True)          # the strict role — this is where it surfaced
        _pack(tmp, "alpha", files)
        return _run(tmp)

    def test_two_templates_sharing_a_placeholder_id_is_not_a_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._rep(tmp, {
                "Templates/Persona - TEMPLATE.md":
                    self.TEMPLATE.format(pid="note-<slug>", title="Persona", body="x"),
                "Templates/Battle Card - TEMPLATE.md":
                    self.TEMPLATE.format(pid="note-<slug>", title="Battle Card", body="x"),
                "Templates/Case Study - TEMPLATE.md":
                    self.TEMPLATE.format(pid="source-<slug>", title="Case Study", body="x"),
            })
            self.assertEqual(rep.errors, [], rep.errors)

    def test_a_placeholder_id_never_enters_the_pack_id_space(self):
        """Not merely forgiven — never indexed, so it can neither duplicate nor
        be reported as overlapping the vault's own template ids."""
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._rep(tmp, {
                "Templates/A - TEMPLATE.md":
                    self.TEMPLATE.format(pid="note-<slug>", title="A", body="x")})
            self.assertNotIn("note-<slug>", str(pc_mod.pack_id_index(tmp)))
            self.assertEqual([w for w in rep.warnings if "also exists in the vault" in w], [])

    def test_a_placeholder_id_outside_templates_is_an_error(self):
        """The tolerance must not become a blind spot. An unfilled id in a
        shipped RECORD is a note nobody finished — and this is an error the
        command did not previously make at all."""
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._rep(tmp, {"content/persona.md":
                                  self.TEMPLATE.format(pid="note-<slug>",
                                                       title="Persona", body="x")})
            self.assertTrue(any("unfilled id placeholder" in e for e in rep.errors),
                            rep.errors)

    def test_genuinely_malformed_and_duplicated_ids_still_error(self):
        """The classes the fix must not blind: a real id with the wrong type
        prefix, and two real records claiming one id."""
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._rep(tmp, {
                "content/a.md": NOTE.format(slug="shared", title="A", body="x"),
                "content/b.md": NOTE.format(slug="shared", title="B", body="x"),
                "content/c.md": self.TEMPLATE.format(pid="wrong-prefix",
                                                     title="C", body="x")})
            self.assertTrue(any("duplicate id 'note-shared'" in e for e in rep.errors),
                            rep.errors)
            self.assertTrue(any("does not match type prefix" in e for e in rep.errors),
                            rep.errors)

    def test_the_rule_has_one_definition(self):
        """`validate` and `pack-check` must not drift apart again — the whole
        reason this defect existed."""
        self.assertTrue(frontmatter.is_placeholder("note-<slug>"))
        self.assertFalse(frontmatter.is_placeholder("note-real-slug"))
        self.assertTrue(frontmatter.in_template_space("Packs/p/05 Wiki/Templates/x.md"))
        self.assertTrue(frontmatter.in_template_space("System/Templates/note.md"))
        self.assertFalse(frontmatter.in_template_space("content/persona.md"))

    def test_the_products_own_templates_pass_their_own_checker(self):
        """The shipped tree is the proof: `System/Templates/` carries
        `procedure-<slug>` twice, and both readers must accept it."""
        seen = {}
        for n in frontmatter.iter_markdown(os.path.join(VAULT, "System", "Templates")):
            nid = str(n.meta.get("id") or "")
            if nid:
                self.assertTrue(frontmatter.is_placeholder(nid), nid)
                seen[nid] = seen.get(nid, 0) + 1
        self.assertGreaterEqual(max(seen.values()), 2,
                                "the duplicate placeholder this defect tripped on")


class TestEmptyWikilinkSlots(unittest.TestCase):
    """DEC-115 — `[[ ]]` names nothing, so nothing is unresolved.

    Twelve of the live instance's 31 errors were `unresolved wikilink [[]]`,
    which is a false description of a fill-in slot. The frontmatter relation
    fields have always skipped `<...>` for exactly this reason; the body now
    agrees. A link that promises a note which does not exist is untouched.
    """

    def _rep(self, tmp, body, master=True):
        _vault(tmp)
        _master(tmp, master)
        _pack(tmp, "alpha", {"content/a.md":
                             NOTE.format(slug="a", title="A", body=body)})
        return _run(tmp)

    def test_an_empty_slot_is_a_warning_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._rep(tmp, "- [[ ]]\n")
            self.assertEqual(rep.errors, [], rep.errors)
            self.assertTrue(any("link slot with no target" in w for w in rep.warnings),
                            rep.warnings)

    def test_an_angle_bracket_slot_is_a_warning_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._rep(tmp, "- [[<the competitor>]]\n")
            self.assertEqual(rep.errors, [], rep.errors)

    def test_a_link_to_a_note_that_does_not_exist_is_still_an_error(self):
        """The guarantee the tolerance must not weaken."""
        with tempfile.TemporaryDirectory() as tmp:
            rep = self._rep(tmp, "See [[No Such Note At All]].\n")
            self.assertTrue(any("unresolved wikilink [[No Such Note At All]]" in e
                                for e in rep.errors), rep.errors)


if __name__ == "__main__":
    unittest.main()
