"""aios pack — scaffold vs workspace (DEC-112, SPEC-pack-workspace-split).

DEC-061's "update replaces the folder wholesale; delete removes it
leave-no-trace" is correct for a pure vendor scaffold and destructive for a
content-bearing role pack: it takes the client's messaging hub, enablement
library, intelligence hub, published assets and voice profile with it, and
reports success.

THE ACCEPTANCE BAR IS BACKWARD COMPATIBILITY. A pack that declares no `layout:`
must behave bit-identically to before, which is asserted here directly and also
by the untouched `test_pack.py::test_update_replaces_never_merges`.
"""
import os, sys, tempfile, unittest, zipfile

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)

from test_pack import _vault, aios, SKILL          # noqa: E402
from cmd import pack as pack_mod                   # noqa: E402

LAYOUT_MANIFEST = """id: pack-demo
name: Demo
version: {version}
kind: role-pack
summary: demo pack
license: MIT
source: https://example.com/demo
min_system_version: '{minv}'
components: {{capabilities: [capabilities/demo/SKILL.md]}}
layout:
  scaffold:
    - capabilities/
    - "05 Wiki/"
    - pack.yaml
  workspace:
    - "01 Messaging Hub/"
  seed:
    - "About Me.md"
"""


def _layout_zip(root, version="1.0.0", fname="demo.zip",
                minv=None, manifest=None, extra=None):
    """A pack ZIP carrying scaffold, workspace and seed content."""
    minv = minv or pack_mod.LAYOUT_MIN_SYSTEM_VERSION
    man = manifest if manifest is not None else LAYOUT_MANIFEST.format(
        version=version, minv=minv)
    zp = os.path.join(root, fname)
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("pack.yaml", man)
        z.writestr("capabilities/demo/SKILL.md", SKILL)
        z.writestr("05 Wiki/Guide.md", f"# vendor guide {version}\n")
        z.writestr("01 Messaging Hub/EXAMPLE - Positioning.md", "# example positioning\n")
        z.writestr("About Me.md", "# about me (vendor template)\n")
        for rel, body in (extra or {}).items():
            z.writestr(rel, body)
    return zp


def _vault_at(tmp, version="1.57.0"):
    """The test vault ships 1.32.0; a layout pack needs a core new enough."""
    _vault(tmp)
    mp = os.path.join(tmp, "SYSTEM-MANIFEST.yaml")
    text = _read_text(mp).replace("system_version: 1.32.0", f"system_version: {version}")
    _write_text(mp, text)


def _p(tmp, *parts):
    return os.path.join(tmp, "Packs", "demo", *parts)


def _read_text(path):
    with open(path) as stream:
        return stream.read()


def _write_text(path, text):
    with open(path, "w") as stream:
        stream.write(text)


class TestClassification(unittest.TestCase):
    """Longest declared prefix wins; undeclared is scaffold."""

    def test_longest_prefix_wins_in_both_directions(self):
        layout = {"scaffold": ["01 Messaging Hub/Templates"],
                  "workspace": ["01 Messaging Hub"], "seed": []}
        c = pack_mod._classify_path
        self.assertEqual(c("01 Messaging Hub/mine.md", layout), "workspace")
        # a scaffold folder carved OUT of a workspace tree
        self.assertEqual(c("01 Messaging Hub/Templates/t.md", layout), "scaffold")
        # and the reverse nesting
        rev = {"scaffold": ["docs"], "workspace": ["docs/user"], "seed": []}
        self.assertEqual(c("docs/readme.md", rev), "scaffold")
        self.assertEqual(c("docs/user/notes.md", rev), "workspace")

    def test_undeclared_is_scaffold_and_no_layout_is_all_scaffold(self):
        self.assertEqual(pack_mod._classify_path("anything/at/all.md", None), "scaffold")
        layout = {"scaffold": [], "workspace": ["ws"], "seed": []}
        self.assertEqual(pack_mod._classify_path("elsewhere/x.md", layout), "scaffold")

    def test_a_path_in_two_classes_is_refused(self):
        errs = []
        pack_mod._read_layout({"layout": {"scaffold": ["shared/"], "workspace": ["shared/"]}}, errs)
        self.assertTrue(any("only be one" in e for e in errs), errs)

    def test_parent_segments_refused_in_layout(self):
        errs = []
        pack_mod._read_layout({"layout": {"workspace": ["../escape"]}}, errs)
        self.assertTrue(errs)


class TestBackwardCompatibility(unittest.TestCase):
    """The acceptance bar: silence means today's behaviour, exactly."""

    def test_pack_without_layout_is_still_wholesale_replaced(self):
        from test_pack import GOOD_MANIFEST, _make_zip
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp)
            aios(tmp, "pack", "--apply", "--confirm")
            stray = _p(tmp, "user-work.md")
            _write_text(stray, "the user's own file\n")
            _make_zip(tmp, manifest=GOOD_MANIFEST.replace("1.0.0", "1.1.0"))
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertIn("UPDATE OK", r.stdout)
            self.assertFalse(os.path.exists(stray), "no layout: = wholesale replace, as before")
            self.assertFalse(os.path.exists(_p(tmp, pack_mod.SCAFFOLD_BASELINE)),
                             "a layout-less pack writes no scaffold baseline")

    def test_pack_without_layout_is_still_deleted_leave_no_trace(self):
        from test_pack import _make_zip
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp)
            aios(tmp, "pack", "--apply", "--confirm")
            _write_text(_p(tmp, "user-work.md"), "mine\n")
            r = aios(tmp, "pack", "demo", "--remove", "--confirm")
            self.assertIn("leave_no_trace", r.stdout)
            self.assertFalse(os.path.isdir(os.path.join(tmp, "Packs", "demo")))
            self.assertFalse(os.path.isdir(os.path.join(tmp, "90 Archive", "packs")),
                             "nothing to evacuate when no workspace is declared")

    def test_the_plan_says_so_when_no_workspace_is_declared(self):
        """§4.7 — silence must not read as safety."""
        from test_pack import _make_zip
        with tempfile.TemporaryDirectory() as tmp:
            _vault(tmp); _make_zip(tmp)
            r = aios(tmp, "pack", "--verify")
            self.assertIn("declares no workspace", r.stdout)
            self.assertIn("will be replaced", r.stdout)


class TestMinSystemVersionGate(unittest.TestCase):
    def test_layout_without_a_new_enough_min_system_version_is_refused(self):
        """The protection itself: an older core would replace the folder
        wholesale, so the manifest must declare a floor that stops it."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault_at(tmp); _layout_zip(tmp, minv="1.0.0")
            r = aios(tmp, "pack", "--verify")
            self.assertIn("does not understand layout:", r.stdout)
            self.assertIn("REJECTED", r.stdout)

    def test_layout_with_the_floor_declared_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault_at(tmp); _layout_zip(tmp)
            r = aios(tmp, "pack", "--verify")
            self.assertIn("manifest gate PASSED", r.stdout)
            self.assertIn("workspace", r.stdout)


class TestUpdateSemantics(unittest.TestCase):
    def _installed(self, tmp):
        _vault_at(tmp); _layout_zip(tmp, "1.0.0")
        r = aios(tmp, "pack", "--apply", "--confirm")
        self.assertIn("INSTALL OK", r.stdout, r.stdout + r.stderr)
        return r

    def test_update_preserves_a_modified_workspace_file(self):
        """§4.1 — the failure this whole feature exists to prevent."""
        with tempfile.TemporaryDirectory() as tmp:
            self._installed(tmp)
            mine = _p(tmp, "01 Messaging Hub", "Our Positioning.md")
            _write_text(mine, "# THE CLIENT'S OWN POSITIONING\n")
            edited = _p(tmp, "01 Messaging Hub", "EXAMPLE - Positioning.md")
            _write_text(edited, "# I edited the example\n")
            _layout_zip(tmp, "1.1.0")
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertIn("UPDATE OK", r.stdout, r.stdout + r.stderr)
            self.assertEqual(_read_text(mine), "# THE CLIENT'S OWN POSITIONING\n")
            self.assertEqual(_read_text(edited), "# I edited the example\n",
                             "the vendor never re-seeds over an existing workspace path")

    def test_update_replaces_an_untouched_scaffold_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._installed(tmp)
            guide = _p(tmp, "05 Wiki", "Guide.md")
            self.assertIn("1.0.0", _read_text(guide))
            _layout_zip(tmp, "1.1.0")
            aios(tmp, "pack", "--apply", "--confirm")
            self.assertIn("1.1.0", _read_text(guide))

    def test_update_never_merges_an_edited_scaffold_file(self):
        """§4.3 — keep the user's copy, write the incoming one beside it."""
        with tempfile.TemporaryDirectory() as tmp:
            self._installed(tmp)
            guide = _p(tmp, "05 Wiki", "Guide.md")
            _write_text(guide, "# I customised the vendor guide\n")
            _layout_zip(tmp, "1.1.0")
            r = aios(tmp, "pack", "--apply", "--confirm")
            self.assertEqual(_read_text(guide), "# I customised the vendor guide\n")
            self.assertTrue(os.path.exists(guide + ".incoming"))
            self.assertIn("1.1.0", _read_text(guide + ".incoming"))
            self.assertIn("never auto-merged", r.stdout)

    def test_seed_file_is_placed_only_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._installed(tmp)
            about = _p(tmp, "About Me.md")
            _write_text(about, "# my own voice profile\n")
            _layout_zip(tmp, "1.1.0")
            aios(tmp, "pack", "--apply", "--confirm")
            self.assertEqual(_read_text(about), "# my own voice profile\n")
            # and when it IS absent, it arrives
            os.remove(about)
            _layout_zip(tmp, "1.2.0")
            aios(tmp, "pack", "--apply", "--confirm")
            self.assertTrue(os.path.exists(about))

    def test_a_retired_scaffold_file_is_removed_but_user_work_never_is(self):
        """§4.4 vs §4.6."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault_at(tmp)
            _layout_zip(tmp, "1.0.0", extra={"05 Wiki/Retired.md": "# going away\n"})
            aios(tmp, "pack", "--apply", "--confirm")
            self.assertTrue(os.path.exists(_p(tmp, "05 Wiki", "Retired.md")))
            mine = _p(tmp, "01 Messaging Hub", "mine.md")
            _write_text(mine, "# mine\n")
            _layout_zip(tmp, "1.1.0")                     # no Retired.md this time
            aios(tmp, "pack", "--apply", "--confirm")
            self.assertFalse(os.path.exists(_p(tmp, "05 Wiki", "Retired.md")))
            self.assertTrue(os.path.exists(mine), "workspace content is never removed")

    def test_scaffold_baseline_is_written_at_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._installed(tmp)
            bl = _p(tmp, pack_mod.SCAFFOLD_BASELINE)
            self.assertTrue(os.path.exists(bl))
            import json
            with open(bl) as stream:
                files = json.load(stream)["files"]
            self.assertIn("05 Wiki/Guide.md", files)
            self.assertNotIn("01 Messaging Hub/EXAMPLE - Positioning.md", files,
                             "only scaffold is fingerprinted")


class TestUninstallEvacuates(unittest.TestCase):
    def test_uninstall_archives_workspace_instead_of_deleting_it(self):
        """§5 — the promise that mattered (no vendor residue) is kept; the one
        that was dangerous (taking the user's corpus) is not."""
        with tempfile.TemporaryDirectory() as tmp:
            _vault_at(tmp); _layout_zip(tmp, "1.0.0")
            aios(tmp, "pack", "--apply", "--confirm")
            mine = _p(tmp, "01 Messaging Hub", "Our Positioning.md")
            _write_text(mine, "# the client's corpus\n")
            r = aios(tmp, "pack", "demo", "--remove", "--confirm")
            self.assertFalse(os.path.isdir(os.path.join(tmp, "Packs", "demo")))
            self.assertIn("was NOT deleted", r.stdout)
            arch = os.path.join(tmp, "90 Archive", "packs")
            hits = []
            for dp, _, fns in os.walk(arch):
                hits += [os.path.join(dp, f) for f in fns]
            self.assertTrue(any(h.endswith("Our Positioning.md") for h in hits), hits)
            # relative structure preserved
            self.assertTrue(any(os.path.join("01 Messaging Hub", "Our Positioning.md")
                                in h for h in hits), hits)
            # the seed file is user-owned too, once placed
            self.assertTrue(any(h.endswith("About Me.md") for h in hits), hits)
            # vendor scaffold left no residue
            self.assertFalse(any("Guide.md" in h for h in hits), hits)
            self.assertIn("leave_no_trace", r.stdout)

    def test_purge_is_the_only_route_to_deletion_and_states_the_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault_at(tmp); _layout_zip(tmp, "1.0.0")
            aios(tmp, "pack", "--apply", "--confirm")
            _write_text(_p(tmp, "01 Messaging Hub", "Our Positioning.md"), "# corpus\n")
            r = aios(tmp, "pack", "demo", "--remove", "--purge", "--confirm")
            self.assertIn("PURGE", r.stdout)
            self.assertIn("file(s) under", r.stdout)
            self.assertIn("user-owned workspace/seed paths", r.stdout)
            self.assertFalse(os.path.isdir(os.path.join(tmp, "Packs", "demo")))
            self.assertFalse(os.path.isdir(os.path.join(tmp, "90 Archive", "packs")),
                             "purge archives nothing — that is the whole point of it")

    def test_purge_still_requires_confirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            _vault_at(tmp); _layout_zip(tmp, "1.0.0")
            aios(tmp, "pack", "--apply", "--confirm")
            r = aios(tmp, "pack", "demo", "--remove", "--purge")
            self.assertIn("--confirm", r.stdout)
            self.assertTrue(os.path.isdir(os.path.join(tmp, "Packs", "demo")))


if __name__ == "__main__":
    unittest.main()
