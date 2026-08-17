"""aios upgrade regressions (DEC-073/074, SPEC-upgrade-path DoD-1..4).

The command's one plan-killer is a wrong "unchanged" call that overwrites
user work — so every test here builds a real old-release/instance/new-release
triangle and checks bytes, not intentions."""
from test_io import read_file, write_file
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, unittest
from unittest import mock

import yaml

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                          # noqa: E402
from lib.migrations import (compute_manifest_hash, compute_source_identity,
                            load_ledger)               # noqa: E402
from cmd import upgrade as up_mod                      # noqa: E402


class Args:
    json = False; message = None; rollback = None; confirm = False
    clean = False; type = None; name = None; register = None
    migration = None; apply = False; target = None
    review_sha256 = None
    dry_run = False; base = None; make_baseline = False
    force_zip = False; zip_only = False; accept = None
    authorize_legacy_core = False


class TestRootProductFiles(unittest.TestCase):
    def test_new_product_root_files_arrive_only_when_absent(self):
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(
                os.path.join(outer, "new"), "1.6.0",
                extra_files={
                    "CONTRIBUTING.md": "target contributing\n",
                    "SECURITY.md": "target security\n",
                },
            )
            inst = mk_instance(os.path.join(outer, "inst"), old)
            base = json.loads(read_file(
                os.path.join(old, "System", ".baseline-manifest.json")))
            plan = up_mod._classify(inst, new, base["files"], base.get("derived"))
            self.assertIn("CONTRIBUTING.md", plan["add"])
            self.assertIn("SECURITY.md", plan["add"])

            write_file(os.path.join(inst, "CONTRIBUTING.md"), "my local file\n", mode="w")
            plan = up_mod._classify(inst, new, base["files"], base.get("derived"))
            self.assertIn("CONTRIBUTING.md", plan["conflict"])
            self.assertNotIn("CONTRIBUTING.md", plan["add"])
            self.assertNotIn("CONTRIBUTING.md", plan["replace"])
            self.assertIn("SECURITY.md", plan["add"])

    def test_root_product_surface_is_exactly_bounded(self):
        self.assertEqual(
            set(up_mod.ROOT_PRODUCT_FILES),
            {"CLAUDE.md", "pyproject.toml", "README.md", "START-HERE.md",
             "CONTRIBUTING.md", "SECURITY.md"},
        )


ROUTER = """id: doc-task-router
schema_version: 1.1.0
modes:
  normal:
    do-thing: {{load: [System/Capabilities/foo/SKILL.md]}}
{extra}fallback:
  unknown: do-thing
"""

CAP = """---
id: capability-foo
name: foo
component_type: capability
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-foo
status: active
version: {v}
summary: "Test capability."
description: "Does the thing. Use when testing upgrade."
reads: [vault]
writes: [per-procedure]
permissions: [uses-vault-operations-only]
dependencies: []
tests: [System/Tests/scripts/test_foo.py]
documentation: self
created: 2026-07-16
updated: 2026-07-16
---

# Capability — foo

{body}
"""

DOC = """---
id: doc-{slug}
type: system-doc
file_class: canonical
authority: canonical
canonical_for: {slug}
version: 1.0.0
created: 2026-07-16
updated: 2026-07-16
summary: "{slug}."
---
{body}
"""

NOTE = """---
id: note-user-{n}
type: note
created: 2026-07-16
updated: 2026-07-16
summary: user note {n}
---
USER CONTENT {n} — must survive byte-identical.
"""


def _set_version(man_text, ver):
    return re.sub(r"(system_version:\s*)\S+", r"\g<1>" + ver, man_text, count=1)


def _read_file(path, mode="r"):
    with open(path, mode) as stream:
        return stream.read()


def _write_file(path, data, mode="w"):
    with open(path, mode) as stream:
        stream.write(data)


def mk_release(path, version, cap_body="OLD BODY", router_extra="",
               extra_files=None):
    """A release tree: generic-master manifest at `version` + a small System/."""
    for d in ("System/Runtime", "System/Capabilities/foo", "System/Governance",
              "System/Documentation", "System/Schemas", "System/Migrations",
              "System/Scripts"):
        os.makedirs(os.path.join(path, d), exist_ok=True)
    # a RELEASE tree is generic-master by definition - state it, never inherit it
    man = product_manifest()
    _write_file(os.path.join(path, "SYSTEM-MANIFEST.yaml"), _set_version(man, version))
    _write_file(os.path.join(path, "pyproject.toml"),
        '[project]\nname = "test-aios"\nversion = "%s"\n' % version)
    _write_file(os.path.join(path, "System", "Runtime", "Task Router.yaml"),
        ROUTER.format(extra=router_extra))
    _write_file(os.path.join(path, "System", "Capabilities", "foo", "SKILL.md"),
        CAP.format(v=version, body=cap_body))
    _write_file(os.path.join(path, "System", "Documentation", "Guide.md"),
        DOC.format(slug="guide", body="Shipped guide text."))
    _write_file(os.path.join(path, "System", "Governance", "Rule.md"),
        DOC.format(slug="rule", body="Protected rule text."))
    for f in os.listdir(os.path.join(VAULT, "System", "Schemas")):
        shutil.copy(os.path.join(VAULT, "System", "Schemas", f),
                    os.path.join(path, "System", "Schemas"))
    # the capability's test case + diagram coverage travel WITH the release:
    # a shipped active component carries its own tests and documentation
    # (DEC-051), so a realistic release tree passes validate/health after apply
    os.makedirs(os.path.join(path, "System", "Tests", "scripts"), exist_ok=True)
    os.makedirs(os.path.join(path, "System", "Tests", "results"), exist_ok=True)
    _write_file(os.path.join(path, "System", "Tests", "scripts", "test_foo.py"),
                "import unittest\n\nclass TestFoo(unittest.TestCase):\n"
                "    def test_contract(self):\n        self.assertTrue(True)\n")
    _write_file(os.path.join(path, "System", "Tests", "results", "capability-foo.yaml"),
                f"component: capability-foo\nversion: {version}\nresult: pass\n"
                "run: 2026-08-13\nevidence_scope: automated source fixture only\n")
    dd = os.path.join(path, "System", "Documentation", "Diagrams")
    os.makedirs(os.path.join(dd, "svg"), exist_ok=True)
    _write_file(os.path.join(dd, "svg", "t.svg"), "<svg/>")
    _write_file(os.path.join(dd, "coverage.yaml"),
        'diagrams:\n  "01": {file: t.svg, title: T, theme: T}\n'
        'components:\n  capability-foo: ["01"]\n')
    _write_file(os.path.join(dd, "diagram-metadata.yaml"),
        '"01":\n  description: test diagram for capability-foo\n')
    for rel, body in (extra_files or {}).items():
        p = os.path.join(path, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        _write_file(p, body)
    rep = Report("baseline")
    up_mod.make_baseline(path, rep)
    assert rep.ok, rep.errors
    return path


def add_system_migration(release, name, start, end, source_identity,
                         relative_path, old_bytes, new_bytes, validation=None):
    """Add one exact direct system edge and refresh the release baseline."""
    directory = os.path.join(release, "System", "Migrations", name)
    os.makedirs(directory, exist_ok=True)
    payload_name = "payload.bin"
    _write_file(os.path.join(directory, payload_name), new_bytes, "wb")
    data = {
        "schema_version": "1.1.0",
        "id": "migration-" + name,
        "version_target": "system_version",
        "source_distribution": "personal-ai-os",
        "source_identity": source_identity,
        "from_version": start,
        "to_version": end,
        "prerequisites": [],
        "content_selector": {"all": True},
        "transform": {
            "replace_exact_files": [{
                "path": relative_path,
                "old_sha256": hashlib.sha256(old_bytes).hexdigest(),
                "payload": payload_name,
                "new_sha256": hashlib.sha256(new_bytes).hexdigest(),
            }]
        },
        "validation": validation or [{"check": "vault-validate"}],
        "rollback": {
            "strategy": "exact-checkpoint",
            "automatic_on_validation_failure": True,
        },
        "idempotency_key": "migration-" + name + "-v1",
        "manifest_hash": "",
    }
    data["manifest_hash"] = compute_manifest_hash(data)
    _write_file(os.path.join(directory, "migration.yaml"),
        yaml.safe_dump(data, sort_keys=False))
    baseline = Report("baseline")
    up_mod.make_baseline(release, baseline)
    assert baseline.ok, baseline.errors
    return data


def mk_instance(path, release):
    """An instance = the old release installed: copy, flip role, add user life."""
    shutil.copytree(release, path)
    mp = os.path.join(path, "SYSTEM-MANIFEST.yaml")
    man = _read_file(mp).replace("instance_role: generic-master",
                                 "instance_role: personal-instance")
    _write_file(mp, man)
    for d in ("20 Knowledge/Local Only", "00 Inbox", "80 User", "System/Journal",
              "System/Tests/results"):
        os.makedirs(os.path.join(path, d), exist_ok=True)
    # the instance's own certification record — outside the upgrade surface
    _write_file(os.path.join(path, "System", "Tests", "results", "capability-foo.yaml"),
        "component: capability-foo\nversion: 1.5.0\nresult: pass\ndate: 2026-07-16\n")
    _write_file(os.path.join(path, "20 Knowledge", "mine.md"), NOTE.format(n=1))
    _write_file(os.path.join(path, "20 Knowledge", "Local Only", "secret.md"),
        NOTE.format(n=2))
    _write_file(os.path.join(path, "System", "Journal", "change-journal.md"),
        "# Change journal\n")
    return path


def tree_state(path):
    """Every file's bytes, for whole-tree no-write assertions."""
    out = {}
    for dirpath, dirnames, files in os.walk(path):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for f in files:
            p = os.path.join(dirpath, f)
            out[os.path.relpath(p, path)] = _read_file(p, "rb")
    return out


def run_upgrade(inst, release, **kw):
    a = Args(); a.target = release
    for k, v in kw.items():
        setattr(a, k, v)
    if not getattr(a, "dry_run", False) and not getattr(a, "make_baseline", False):
        review = Report("upgrade")
        # Review is deliberately outside the mutation state machine.  Keep
        # fault-injection patches focused on the subsequent authorized apply.
        with mock.patch.object(up_mod, "_transaction_boundary",
                               return_value=None):
            up_mod.run(inst, a, review)
        if not review.ok or "review_sha256" not in review.info:
            return review
        a.apply = True
        a.confirm = True
        a.review_sha256 = review.info["review_sha256"]
    rep = Report("upgrade")
    up_mod.run(inst, a, rep)
    return rep


class TestUpgradeHappyPath(unittest.TestCase):
    """DoD-1 (minus router divergence, covered separately): pristine files
    replaced, instance edits kept, user content byte-identical, version bumped."""

    def test_clean_upgrade_end_to_end(self):
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0",
                             cap_body="NEW BODY",
                             extra_files={"System/Documentation/Added.md":
                                          DOC.format(slug="added", body="New doc.")})
            inst = mk_instance(os.path.join(outer, "inst"), old)
            # the user's instance edit to a NON-protected System file
            gp = os.path.join(inst, "System", "Documentation", "Guide.md")
            write_file(gp, DOC.format(slug="guide", body="MY LOCAL EDIT."), mode="w")
            user_before = {p: b for p, b in tree_state(inst).items()
                           if p.startswith(("20 Knowledge", "00 Inbox", "80 User"))}
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            # pristine file took the new version
            self.assertIn("NEW BODY", read_file(os.path.join(
                inst, "System", "Capabilities", "foo", "SKILL.md")))
            # new file arrived; instance edit was KEPT and reported
            self.assertTrue(os.path.exists(os.path.join(
                inst, "System", "Documentation", "Added.md")))
            self.assertIn("MY LOCAL EDIT.", read_file(gp))
            self.assertIn("System/Documentation/Guide.md",
                          rep.info.get("kept_instance_edits", []))
            # user content byte-identical (DoD-1 i + iv)
            user_after = {p: b for p, b in tree_state(inst).items()
                          if p.startswith(("20 Knowledge", "00 Inbox", "80 User"))}
            self.assertEqual(user_before, user_after)
            # version bumped; baseline now the new release's; report + journal exist
            self.assertIn("system_version: 1.6.0",
                          read_file(os.path.join(inst, "SYSTEM-MANIFEST.yaml")))
            bl = json.loads(read_file(os.path.join(inst, "System", ".baseline-manifest.json")))
            self.assertEqual(bl["system_version"], "1.6.0")
            self.assertTrue(str(rep.info.get("report", "")).startswith("System/Logs/"))
            self.assertIn("upgrade", read_file(os.path.join(
                inst, "System", "Journal", "change-journal.md")))

    def test_router_divergence_is_conflict_but_does_NOT_block_bump(self):
        """DEC-073 + DEC-111: both sides changed the router → still a conflict
        with a per-row diff, instance file still untouched — but the bump is NO
        LONGER blocked, because a customized router is sanctioned divergence.

        This test asserted the opposite until 2026-07-27. It was not wrong about
        the mechanics; it encoded a lockout. A green customized work instance passed every gate
        and still could not record its own upgrade, for exactly this reason."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0",
                             router_extra="    new-core-row: {load: [System/Capabilities/foo/SKILL.md]}\n")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            rp = os.path.join(inst, "System", "Runtime", "Task Router.yaml")
            mine = read_file(rp).replace(
                "fallback:", "    my-instance-row: {load: [System/Capabilities/foo/SKILL.md]}\nfallback:")
            write_file(rp, mine, mode="w")
            rep = run_upgrade(inst, new)
            # unchanged: still reported as a conflict, still diffed, never merged
            self.assertIn("System/Runtime/Task Router.yaml",
                          [c.split("  (")[0] for c in rep.info.get("conflict", [])])
            self.assertEqual(read_file(rp), mine, "router must be left as-is")
            rows = " ".join(rep.info.get("router_review", []))
            self.assertIn("my-instance-row", rows)
            self.assertIn("new-core-row", rows)
            # changed: the divergence is declared, and the bump goes through
            declared = " ".join(rep.info.get("sanctioned_divergence", []))
            self.assertIn("System/Runtime/Task Router.yaml", declared)
            self.assertIn("sanctioned", declared)
            man = read_file(os.path.join(inst, "SYSTEM-MANIFEST.yaml"))
            self.assertIn("system_version: 1.6.0", man)
            # and the manifest line carries the caveat with it
            self.assertIn("declared divergence", man)
            self.assertFalse(any("stays 1.5.0" in w for w in rep.warnings))


DOCGEN_DOC = """---
id: doc-{slug}
type: system-doc
file_class: canonical
authority: canonical
canonical_for: {slug}
version: 1.0.0
created: 2026-07-16
updated: 2026-07-16
summary: "{slug}."
---
{prose}

<!-- docgen:capability-count -->
{census}
<!-- /docgen:capability-count -->
"""


class TestBumpGateDistinction(unittest.TestCase):
    """DEC-111: the bump gate distinguishes deliberate divergence from an
    unresolved disagreement. It must keep blocking the second."""

    def _census_pair(self, outer, inst_prose, rel_prose):
        """Two copies of a protected doc carrying a docgen region, written to
        disk so the real `_derived_only` reads real files."""
        a = os.path.join(outer, "inst.md"); b = os.path.join(outer, "rel.md")
        write_file(a, DOCGEN_DOC.format(slug="census", prose=inst_prose, census="7"), mode="w")
        write_file(b, DOCGEN_DOC.format(slug="census", prose=rel_prose, census="14"), mode="w")
        return a, b

    def test_self_regenerated_census_is_derived_not_a_disagreement(self):
        """The circular trap: `docgen --check` REQUIRES the instance to
        regenerate this block against its own tree, and the gate then called the
        result an unresolved conflict. Identical prose, different counts."""
        with tempfile.TemporaryDirectory() as outer:
            a, b = self._census_pair(outer, "The rule.", "The rule.")
            self.assertTrue(up_mod._derived_only(a, b))

    def test_edited_prose_around_a_census_is_NOT_derived(self):
        """The distinction earning its keep. Same census divergence, but the
        instance also edited prose OUTSIDE the generated region — so the two
        versions genuinely disagree and nobody chose. One sentence disqualifies
        the whole file; this is what stops 'derived' being a blanket exemption
        for any document that happens to carry a census."""
        with tempfile.TemporaryDirectory() as outer:
            a, b = self._census_pair(outer, "MY EDITED RULE.", "The rule, revised.")
            self.assertFalse(up_mod._derived_only(a, b))

    def test_a_file_with_no_generated_region_is_never_derived(self):
        """Fail closed: the derived route requires an actual docgen region."""
        with tempfile.TemporaryDirectory() as outer:
            a = os.path.join(outer, "a.md"); b = os.path.join(outer, "b.md")
            write_file(a, DOC.format(slug="rule", body="mine"), mode="w")
            write_file(b, DOC.format(slug="rule", body="theirs"), mode="w")
            self.assertFalse(up_mod._derived_only(a, b))
            self.assertFalse(up_mod._derived_only(os.path.join(outer, "nope.md"), b),
                             "an unreadable file must never be called derived")

    def test_regenerated_censuses_are_not_an_edit_so_the_file_is_replaced(self):
        """DEC-111, the classification half. An instance that obeyed
        `docgen --check` looked *customized* in its own constitution, so the
        next release to touch that file produced a conflict in which nobody had
        disagreed about anything. Instance-vs-base differing only inside docgen
        regions = pristine → replace, then recount against this vault."""
        with tempfile.TemporaryDirectory() as outer:
            body = lambda prose, census: DOCGEN_DOC.format(          # noqa: E731
                slug="census", prose=prose, census=census)
            old = mk_release(os.path.join(outer, "old"), "1.5.0",
                             extra_files={"System/Governance/Census.md": body("Rule v1.", "5")})
            new = mk_release(os.path.join(outer, "new"), "1.6.0",
                             extra_files={"System/Governance/Census.md": body("Rule v2.", "14")})
            inst = mk_instance(os.path.join(outer, "inst"), old)
            cp = os.path.join(inst, "System", "Governance", "Census.md")
            write_file(cp, body("Rule v1.", "7"), mode="w")   # recounted, prose untouched
            base = json.loads(read_file(os.path.join(old, "System", ".baseline-manifest.json")))
            plan = up_mod._classify(inst, new, base["files"], base.get("derived"))
            self.assertIn("System/Governance/Census.md", plan["replace"])
            self.assertNotIn("System/Governance/Census.md",
                             [c.split("  (")[0] for c in plan["conflict"]])
            # and a REAL edit to the same file is still a conflict
            write_file(cp, body("MY OWN RULE.", "7"), mode="w")
            plan2 = up_mod._classify(inst, new, base["files"], base.get("derived"))
            self.assertIn("System/Governance/Census.md",
                          [c.split("  (")[0] for c in plan2["conflict"]])

    def test_a_pre_v1_56_baseline_classifies_exactly_as_before(self):
        """Backward compatibility: a baseline with no `derived` map (every
        instance in the field today) must behave identically to the old code."""
        with tempfile.TemporaryDirectory() as outer:
            body = lambda prose, census: DOCGEN_DOC.format(          # noqa: E731
                slug="census", prose=prose, census=census)
            old = mk_release(os.path.join(outer, "old"), "1.5.0",
                             extra_files={"System/Governance/Census.md": body("Rule v1.", "5")})
            new = mk_release(os.path.join(outer, "new"), "1.6.0",
                             extra_files={"System/Governance/Census.md": body("Rule v2.", "14")})
            inst = mk_instance(os.path.join(outer, "inst"), old)
            write_file(os.path.join(inst, "System", "Governance", "Census.md"), body("Rule v1.", "7"), mode="w")
            base = json.loads(read_file(os.path.join(old, "System", ".baseline-manifest.json")))
            plan = up_mod._classify(inst, new, base["files"], None)
            self.assertIn("System/Governance/Census.md",
                          [c.split("  (")[0] for c in plan["conflict"]])

    def test_account_for_conflicts_routes_each_case(self):
        """The three accounted routes and the blocking default, in one place."""
        with tempfile.TemporaryDirectory() as outer:
            root = os.path.join(outer, "root"); rel = os.path.join(outer, "rel")
            for d in (root, rel):
                os.makedirs(os.path.join(d, "System", "Governance"))
            write_file(os.path.join(root, "System/Governance/Census.md"), DOCGEN_DOC.format(slug="census", prose="Same.", census="7"), mode="w")
            write_file(os.path.join(rel, "System/Governance/Census.md"), DOCGEN_DOC.format(slug="census", prose="Same.", census="14"), mode="w")
            write_file(os.path.join(root, "System/Governance/Rule.md"), "mine", mode="w")
            write_file(os.path.join(rel, "System/Governance/Rule.md"), "theirs", mode="w")
            write_file(os.path.join(root, "System/Governance/Other.md"), "mine", mode="w")
            write_file(os.path.join(rel, "System/Governance/Other.md"), "theirs", mode="w")
            conflicts = [up_mod.ROUTER, "System/Governance/Census.md",
                         "System/Governance/Rule.md", "System/Governance/Other.md"]
            blocking, accounted = up_mod._account_for_conflicts(
                root, rel, conflicts, {"System/Governance/Rule.md"})
            routes = {p: r for p, r, _ in accounted}
            self.assertEqual(routes.get(up_mod.ROUTER), "sanctioned")
            self.assertEqual(routes.get("System/Governance/Census.md"), "derived")
            self.assertEqual(routes.get("System/Governance/Rule.md"), "accepted")
            self.assertEqual(blocking, ["System/Governance/Other.md"],
                             "an unaccounted protected conflict must still block")

    def test_genuine_protected_conflict_still_blocks(self):
        """A protected file with no generated region, changed on both sides:
        the case the gate exists for. Unchanged behaviour."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0")
            write_file(os.path.join(new, "System", "Governance", "Rule.md"), DOC.format(slug="rule", body="RELEASE REWROTE THE RULE."), mode="w")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            rpath = os.path.join(inst, "System", "Governance", "Rule.md")
            write_file(rpath, DOC.format(slug="rule", body="I REWROTE THE RULE."), mode="w")
            rep = run_upgrade(inst, new)
            self.assertIn("I REWROTE THE RULE.", read_file(rpath))
            self.assertIn("system_version: 1.5.0",
                          read_file(os.path.join(inst, "SYSTEM-MANIFEST.yaml")))
            self.assertTrue(any("unresolved conflict" in w for w in rep.warnings))

    def test_accept_lets_a_human_resolve_one(self):
        """The 'somebody chose' route: same genuine conflict as above, but the
        human named it. File still never merged; bump goes through; the reason
        is recorded rather than assumed."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0")
            write_file(os.path.join(new, "System", "Governance", "Rule.md"), DOC.format(slug="rule", body="RELEASE REWROTE THE RULE."), mode="w")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            rpath = os.path.join(inst, "System", "Governance", "Rule.md")
            write_file(rpath, DOC.format(slug="rule", body="I REWROTE THE RULE."), mode="w")
            rep = run_upgrade(inst, new, accept=["System/Governance/Rule.md"])
            self.assertIn("I REWROTE THE RULE.", read_file(rpath),
                          "--accept must keep the file, never merge it")
            self.assertIn("accepted", " ".join(rep.info.get("sanctioned_divergence", [])))
            self.assertIn("system_version: 1.6.0",
                          read_file(os.path.join(inst, "SYSTEM-MANIFEST.yaml")))

    def test_accept_on_a_path_that_is_not_in_conflict_warns(self):
        """Silently ignoring a typo'd --accept would let someone believe they
        had resolved something they had not."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            rep = run_upgrade(inst, new, accept=["System/Governance/Nope.md"])
            self.assertTrue(any("not in conflict" in w and "Nope.md" in w
                                for w in rep.warnings), rep.warnings)

    def test_gates_red_still_blocks_even_with_everything_declared(self):
        """DEC-111 relaxes ONE blocker. Red gates are still red — this is the
        two red-instance shapes, and it must stay locked."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0",
                             router_extra="    new-core-row: {load: [System/Capabilities/foo/SKILL.md]}\n")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            rp = os.path.join(inst, "System", "Runtime", "Task Router.yaml")
            write_file(rp, read_file(rp).replace(
                "fallback:", "    my-instance-row: {load: [System/Capabilities/foo/SKILL.md]}\nfallback:"), mode="w")           # a broken note the post-upgrade validate will reject
            write_file(os.path.join(inst, "20 Knowledge", "broken.md"), "---\nid: note-broken\ntype: nonsense-class\n---\nbody\n", mode="w")
            rep = run_upgrade(inst, new)
            self.assertFalse(rep.ok)
            self.assertIn("system_version: 1.5.0",
                          read_file(os.path.join(inst, "SYSTEM-MANIFEST.yaml")))
            self.assertTrue(any("gates red" in w for w in rep.warnings), rep.warnings)


class TestUpgradeSafety(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        """DoD-2: tree diff empty, and the plan matches what a real run does."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            before = tree_state(inst)
            rep = run_upgrade(inst, new, dry_run=True)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(before, tree_state(inst), "dry-run must write NOTHING")
            planned = rep.info.get("replace", [])
            rep2 = run_upgrade(inst, new)
            self.assertTrue(rep2.ok, rep2.errors)
            self.assertEqual(planned, rep2.info.get("replace", []),
                             "dry-run plan must match the real run")

    def test_idempotent_second_run(self):
        """DoD-3: already at version → nothing to do, tree unchanged."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            self.assertTrue(run_upgrade(inst, new).ok)
            mid = tree_state(inst)
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("nothing to do", str(rep.info.get("result", "")))
            self.assertEqual(mid, tree_state(inst))

    def test_fusion_refused_before_any_write(self):
        """DoD-4: PMM shape — instance edits inside protected paths beyond the
        limit → refuse, name files, write nothing."""
        with tempfile.TemporaryDirectory() as outer:
            extra = {f"System/Governance/R{i}.md": DOC.format(slug=f"r{i}", body="v1")
                     for i in range(7)}
            old = mk_release(os.path.join(outer, "old"), "1.5.0", extra_files=extra)
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY",
                             extra_files=extra)
            inst = mk_instance(os.path.join(outer, "inst"), old)
            for i in range(7):
                _write_file(os.path.join(inst, "System", "Governance", f"R{i}.md"),
                            DOC.format(slug=f"r{i}", body="FUSED LOCAL EDIT"))
            before = tree_state(inst)
            rep = run_upgrade(inst, new)
            self.assertFalse(rep.ok)
            self.assertIn("fused", " ".join(rep.errors))
            self.assertIn("System/Governance/R0.md", " ".join(rep.errors))
            self.assertEqual(before, tree_state(inst), "refusal must write NOTHING")

    def test_checkpoint_failure_halts_before_writes(self):
        """checkpoint-or-halt: if the checkpoint cannot be taken, nothing is
        written (seeded failure, DoD-1 variant)."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            before = tree_state(inst)
            real = up_mod.ckpt_mod.run
            def broken(root, args, rep):
                rep.error("simulated checkpoint failure")
                return rep
            up_mod.ckpt_mod.run = broken
            try:
                rep = run_upgrade(inst, new)
            finally:
                up_mod.ckpt_mod.run = real
            self.assertFalse(rep.ok)
            self.assertIn("checkpoint FAILED", " ".join(rep.errors))
            self.assertEqual(before, tree_state(inst))

    def test_downgrade_and_bad_targets_refused(self):
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            older = mk_release(os.path.join(outer, "older"), "1.4.0")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            self.assertIn("OLDER", " ".join(run_upgrade(inst, older).errors))
            self.assertIn("not a release tree",
                          " ".join(run_upgrade(inst, outer).errors))
            self.assertIn("IS this vault", " ".join(run_upgrade(inst, inst).errors))

    def test_fallback_mode_replaces_nothing(self):
        """No baseline, no --base → every difference is a conflict; the only
        safe transactional result is now NO mutation at all. A partial addition
        would make the live tree neither complete old nor complete new."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY",
                             extra_files={"System/Documentation/Added.md":
                                          DOC.format(slug="added", body="New doc.")})
            inst = mk_instance(os.path.join(outer, "inst"), old)
            os.remove(os.path.join(inst, "System", ".baseline-manifest.json"))
            rep = run_upgrade(inst, new)
            self.assertIn("OLD BODY", read_file(os.path.join(
                inst, "System", "Capabilities", "foo", "SKILL.md")),
                "fallback must not replace a differing file")
            self.assertIn("System/Capabilities/foo/SKILL.md", rep.info.get("conflict", []))
            self.assertFalse(os.path.exists(os.path.join(
                inst, "System", "Documentation", "Added.md")),
                "a blocked transaction may not apply even a safe-looking subset")
            self.assertIn("system_version: 1.5.0",
                          read_file(os.path.join(inst, "SYSTEM-MANIFEST.yaml")))

    def test_malformed_release_migration_refuses_before_checkpoint(self):
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY",
                             extra_files={"System/Migrations/001-fixture/migration.yaml":
                                          "id: migration-001-fixture\ntransform: {}\n"})
            inst = mk_instance(os.path.join(outer, "inst"), old)
            before = tree_state(inst)
            rep = run_upgrade(inst, new)
            self.assertFalse(rep.ok)
            self.assertIn("resolution FAILED", " ".join(rep.errors))
            self.assertEqual(before, tree_state(inst))


class TestUpgradeMigrationIntegration(unittest.TestCase):
    def _triangle(self, outer, *, validation=None, identity=None):
        old = mk_release(os.path.join(outer, "old"), "1.5.0")
        new = mk_release(
            os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY")
        inst = mk_instance(os.path.join(outer, "inst"), old)
        relative = "20 Knowledge/mine.md"
        old_bytes = read_file(os.path.join(inst, relative), "rb")
        new_bytes = old_bytes.replace(
            b"USER CONTENT 1", b"USER CONTENT 1 MIGRATED")
        add_system_migration(
            new, "001-user-surface", "1.5.0", "1.6.0",
            identity or compute_source_identity(inst),
            relative, old_bytes, new_bytes, validation=validation)
        return old, new, inst, relative, old_bytes, new_bytes

    def test_no_git_candidate_applies_exact_declared_user_change(self):
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, relative, _before, expected = self._triangle(outer)
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(read_file(os.path.join(inst, relative), "rb"), expected)
            self.assertEqual(rep.info["migration_result"], "applied")
            self.assertEqual(rep.info["migration_affected_paths"], [relative])
            self.assertEqual(load_ledger(inst)[0]["id"],
                             "migration-001-user-surface")
            self.assertIn("system_version: 1.6.0",
                          read_file(os.path.join(inst, "SYSTEM-MANIFEST.yaml")))

    def test_git_candidate_uses_whole_tree_snapshot_and_applies(self):
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, relative, _before, expected = self._triangle(outer)
            subprocess.run(["git", "init", "-q"], cwd=inst, check=True)
            subprocess.run(
                ["git", "config", "user.email", "upgrade@test.invalid"],
                cwd=inst, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Upgrade Test"],
                cwd=inst, check=True)
            subprocess.run(["git", "add", "-A"], cwd=inst, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "fixture"], cwd=inst, check=True)
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(read_file(os.path.join(inst, relative), "rb"), expected)
            record = load_ledger(inst)[0]
            self.assertEqual(record["checkpoint"]["kind"], "zip-snapshot")
            self.assertEqual(record["checkpoint"]["coverage"], "whole-tree")
            self.assertTrue(record["checkpoint"]["exact_recovery"])

    def test_failed_candidate_is_discarded_and_live_is_exact(self):
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, _relative, _before, _expected = self._triangle(
                outer,
                validation=[
                    {"check": "field-present", "field": "never_created"},
                    {"check": "vault-validate"},
                ])
            before = tree_state(inst)
            rep = run_upgrade(inst, new)
            self.assertFalse(rep.ok)
            self.assertIn("migration failed", " ".join(rep.warnings))
            self.assertEqual(before, tree_state(inst))
            self.assertFalse(any(
                ".aios-upgrade-" in name for name in os.listdir(outer)))

    def test_declared_path_with_wrong_post_hash_is_not_exempted(self):
        from cmd import generate as generate_mod
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, relative, _before, _expected = self._triangle(outer)
            before = tree_state(inst)
            real_generate = generate_mod.run

            def generate_then_tamper(root, args, report):
                result = real_generate(root, args, report)
                with open(os.path.join(root, relative), "ab") as stream:
                    stream.write(b"\nundeclared post-migration drift\n")
                return result

            with mock.patch.object(
                    generate_mod, "run", side_effect=generate_then_tamper):
                rep = run_upgrade(inst, new)
            self.assertFalse(rep.ok)
            self.assertIn("CONTENT INTEGRITY FAILURE", " ".join(rep.errors))
            self.assertTrue(rep.info.get("migration_integrity_mismatches"))
            self.assertEqual(before, tree_state(inst))

    def test_dry_run_reports_edge_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, _relative, _before, _expected = self._triangle(outer)
            before = tree_state(inst)
            rep = run_upgrade(inst, new, dry_run=True)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(rep.info["migration_edge"]["migration"],
                             "001-user-surface")
            self.assertIn("dry-run", rep.info["mode"])
            self.assertEqual(before, tree_state(inst))

    def test_ambiguous_exact_edges_refuse_before_checkpoint(self):
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, relative, old_bytes, new_bytes = self._triangle(outer)
            add_system_migration(
                new, "002-user-surface", "1.5.0", "1.6.0",
                compute_source_identity(inst), relative, old_bytes, new_bytes)
            before = tree_state(inst)
            rep = run_upgrade(inst, new)
            self.assertFalse(rep.ok)
            self.assertIn("ambiguous migration edge", " ".join(rep.errors))
            self.assertEqual(before, tree_state(inst))

    def test_transform_preconditions_choose_one_same_identity_edge(self):
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, relative, _old_bytes, new_bytes = self._triangle(outer)
            add_system_migration(
                new, "002-rival-surface", "1.5.0", "1.6.0",
                compute_source_identity(inst), relative,
                b"bytes from a different distribution", new_bytes)
            before = tree_state(inst)
            rep = run_upgrade(inst, new, dry_run=True)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(rep.info["migration_edge"]["migration"],
                             "001-user-surface")
            self.assertEqual(before, tree_state(inst))

    def test_no_matching_transform_precondition_refuses_before_checkpoint(self):
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, relative, _before, _expected = self._triangle(outer)
            with open(os.path.join(inst, relative), "ab") as stream:
                stream.write(b"\ninstance divergence\n")
            before = tree_state(inst)
            rep = run_upgrade(inst, new)
            self.assertFalse(rep.ok)
            self.assertIn("no exact migration edge", " ".join(rep.errors))
            self.assertEqual(before, tree_state(inst))

    def test_rival_identity_refuses_before_checkpoint(self):
        with tempfile.TemporaryDirectory() as outer:
            _old, new, inst, _relative, _before, _expected = self._triangle(
                outer, identity="f" * 64)
            before = tree_state(inst)
            rep = run_upgrade(inst, new)
            self.assertFalse(rep.ok)
            self.assertIn("no migration matches", " ".join(rep.errors))
            self.assertEqual(before, tree_state(inst))


class TestLegacyCoreAuthorization(unittest.TestCase):
    def _fixture(self, outer):
        release = mk_release(
            os.path.join(outer, "release"), "1.6.0",
            extra_files={"LICENSE.md": "legacy core license\n"},
        )
        source = mk_release(
            os.path.join(outer, "source-release"), "1.5.0",
            extra_files={"LICENSE.md": "legacy core license\n"},
        )
        root = mk_instance(os.path.join(outer, "instance"), source)
        manifest_path = os.path.join(root, "SYSTEM-MANIFEST.yaml")
        text = _read_file(manifest_path)
        text = re.sub(r"^\s*distribution_id:.*\n", "", text, flags=re.MULTILINE)
        _write_file(manifest_path, text)
        identity = compute_source_identity(root)
        with open(os.path.join(root, "LICENSE.md"), "rb") as stream:
            license_sha = hashlib.sha256(stream.read()).hexdigest()
        return root, release, identity, license_sha

    def test_legacy_source_requires_explicit_flag_and_exact_allowlist(self):
        with tempfile.TemporaryDirectory() as outer:
            root, release, identity, license_sha = self._fixture(outer)
            frozen = frozenset({("1.5.0", identity, license_sha)})
            with mock.patch.object(
                up_mod, "OFFICIAL_LEGACY_CORE_SOURCES", frozen
            ):
                with self.assertRaisesRegex(Exception, "--authorize-legacy-core"):
                    up_mod._authorize_source_distribution(
                        root, "1.5.0", identity, Args()
                    )
                args = Args(); args.authorize_legacy_core = True
                self.assertEqual(
                    up_mod._authorize_source_distribution(
                        root, "1.5.0", identity, args
                    ),
                    ("personal-ai-os", True),
                )
                with open(os.path.join(root, "LICENSE.md"), "a") as stream:
                    stream.write("changed\n")
                with self.assertRaisesRegex(Exception, "frozen official tuple"):
                    up_mod._authorize_source_distribution(
                        root, "1.5.0", identity, args
                    )

    def test_legacy_core_flag_cannot_override_pmm_markers(self):
        with tempfile.TemporaryDirectory() as outer:
            root, release, identity, license_sha = self._fixture(outer)
            os.makedirs(os.path.join(root, "Packs", "pmm"))
            args = Args(); args.authorize_legacy_core = True
            with mock.patch.object(
                up_mod, "OFFICIAL_LEGACY_CORE_SOURCES",
                frozenset({("1.5.0", identity, license_sha)}),
            ):
                with self.assertRaisesRegex(Exception, "PMM product markers"):
                    up_mod._authorize_source_distribution(
                        root, "1.5.0", identity, args
                    )


class TestRootFiles(unittest.TestCase):
    """DEC-097: the root-files gap fix. The PMM Phase 0 inventory proved a
    successful upgrade left CLAUDE.md ~18 versions stale — the product-owned
    root files now ride the same three-way classification as System/, the
    user-owned ones are never touched, and new-release seeds arrive additively."""

    def test_product_root_files_replaced_when_pristine_kept_when_edited(self):
        with tempfile.TemporaryDirectory() as outer:
            roots_old = {"CLAUDE.md": "OLD ADAPTER TEXT\n", "README.md": "SAME README\n"}
            roots_new = {"CLAUDE.md": "NEW ADAPTER TEXT\n", "README.md": "SAME README\n"}
            old = mk_release(os.path.join(outer, "old"), "1.5.0", extra_files=roots_old)
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY",
                             extra_files=roots_new)
            inst = mk_instance(os.path.join(outer, "inst"), old)
            write_file(os.path.join(inst, "README.md"), "MY LOCAL README EDIT\n", mode="w")
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(read_file(os.path.join(inst, "CLAUDE.md")),
                             "NEW ADAPTER TEXT\n", "pristine product root file must upgrade")
            self.assertEqual(read_file(os.path.join(inst, "README.md")),
                             "MY LOCAL README EDIT\n", "instance-edited root file must be kept")
            self.assertIn("README.md", rep.info.get("kept_instance_edits", []))
            self.assertIn("CLAUDE.md", rep.info.get("replace", []))

    def test_user_owned_root_files_never_touched(self):
        """LICENSE.md (the user's license choice) and CHANGELOG.md (the
        instance's own history) are outside the surface — never replaced,
        never even reported as conflicts."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY",
                             extra_files={"LICENSE.md": "PRODUCT LICENSE\n",
                                          "CHANGELOG.md": "PRODUCT HISTORY\n",
                                          "CONNECT-CHECK.md": "PRODUCT SENTINEL\n"})
            inst = mk_instance(os.path.join(outer, "inst"), old)
            write_file(os.path.join(inst, "LICENSE.md"), "MY LICENSE\n", mode="w")
            write_file(os.path.join(inst, "CHANGELOG.md"), "MY INSTANCE JOURNEY\n", mode="w")
            write_file(os.path.join(inst, "CONNECT-CHECK.md"), "MY SENTINEL\n", mode="w")
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            for fn, body in (("LICENSE.md", "MY LICENSE\n"),
                             ("CHANGELOG.md", "MY INSTANCE JOURNEY\n"),
                             ("CONNECT-CHECK.md", "MY SENTINEL\n")):
                self.assertEqual(read_file(os.path.join(inst, fn)), body,
                                 f"user-owned root file {fn} was touched")
                self.assertNotIn(fn, [c.split("  (")[0] for c in rep.info.get("conflict", [])],
                                 f"{fn} must not even be classified")

    def test_additive_root_seeds_delivered_only_when_absent(self):
        """To-Do.md (v1.39.0) / Decisions/ (v1.40.0) seeds: added when the
        instance lacks them; user content once present — never replaced."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY",
                             extra_files={"To-Do.md": "SEED TODO\n",
                                          "Decisions/_ABOUT.md": "SEED DECISIONS ABOUT\n"})
            inst = mk_instance(os.path.join(outer, "inst"), old)
            write_file(os.path.join(inst, "To-Do.md"), "MY LIVE TODO LIST\n", mode="w")
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(read_file(os.path.join(inst, "To-Do.md")), "MY LIVE TODO LIST\n",
                             "an existing To-Do.md is user content — never replaced")
            self.assertEqual(read_file(os.path.join(inst, "Decisions", "_ABOUT.md")),
                             "SEED DECISIONS ABOUT\n", "absent seed must be delivered")
            self.assertEqual(rep.info.get("seeded_root_files"), ["Decisions/_ABOUT.md"])

    def test_obsidian_is_never_touched_by_upgrade(self):
        """Regression pin: an instance's .obsidian is user-owned; a release
        shipping its own .obsidian seed must not overwrite it."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY",
                             extra_files={".obsidian/app.json": '{"seed": "RELEASE"}\n'})
            inst = mk_instance(os.path.join(outer, "inst"), old)
            os.makedirs(os.path.join(inst, ".obsidian"), exist_ok=True)
            write_file(os.path.join(inst, ".obsidian", "app.json"), '{"mine": "CUSTOM"}\n', mode="w")
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(read_file(os.path.join(inst, ".obsidian", "app.json")),
                             '{"mine": "CUSTOM"}\n', ".obsidian must never be touched")


class TestContentIntegrityScope(unittest.TestCase):
    """DEC-109 — the integrity claim now covers what it says it covers.

    The report said "byte-identical (N files verified)" and the module docstring
    promised user content, `80 User/`, `.obsidian/`, `Packs/`, the canonical
    journal and certification records were never touched. The fingerprint walked
    `manifest.directories.content` + `.obsidian` + `Packs` and nothing else — a
    hand-maintained list of a set the USER controls. On a live work instance it
    verified **160 of 1,641 files**; 1,102 of the gap were seven content folders
    that instance had declared in its own `folder-registry.yaml`.

    SEEDED FAILURE: each test here writes into a place the old walk could not
    see, then asserts the drift is caught. Against the pre-fix code the run
    reports success and the corruption ships.
    """

    def _corrupt_after_apply(self, rel_path):
        """Run an upgrade whose `generate` step scribbles on one user file, and
        return the report. This is the shape a real regression takes: something
        in the post-apply chain writes where it must not."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            victim = os.path.join(inst, rel_path)
            os.makedirs(os.path.dirname(victim), exist_ok=True)
            _write_file(victim, "ORIGINAL\n")

            from cmd import generate as g_mod
            real = g_mod.run

            def scribbling(root, args, rep):
                _write_file(os.path.join(root, rel_path), "CORRUPTED\n")
                return real(root, args, rep)

            g_mod.run = scribbling
            try:
                rep = run_upgrade(inst, new)
            finally:
                g_mod.run = real
            return rep

    def _assert_caught(self, rel_path):
        rep = self._corrupt_after_apply(rel_path)
        self.assertFalse(rep.ok, f"a write to {rel_path} must be an integrity failure")
        self.assertTrue(any("CONTENT INTEGRITY FAILURE" in e for e in rep.errors), rep.errors)
        self.assertIn(rel_path, str(rep.info.get("changed_user_files")))

    def test_registry_declared_folder_outside_the_manifest_is_covered(self):
        """THE LIVE DEFECT. An instance registers extra content folders in its
        own folder-registry; the manifest's `directories.content` never learns
        about them. 1,102 real files sat in exactly this blind spot."""
        self._assert_caught("Published Assets/asset.md")

    def test_root_user_file_is_covered(self):
        self._assert_caught("About Me.md")

    def test_canonical_journal_is_covered(self):
        """The module docstring has always promised this. Nothing checked it."""
        self._assert_caught("System/Journal/change-journal.md")

    def test_certification_records_are_covered(self):
        self._assert_caught("System/Tests/results/capability-foo.yaml")

    def test_regenerated_state_is_excluded_and_named(self):
        """`System/Generated` and `System/Logs` are rebuilt by the post-upgrade
        `generate`. Verifying them would fail every run for the one reason that
        is fine — so they are excluded, and the report SAYS they are."""
        self.assertTrue(up_mod._verify_scope())
        for excluded in ("System/Generated/x.json", "System/Logs/run.log"):
            self.assertTrue(any(excluded.startswith(p) for p in up_mod.VERIFY_SKIP_PREFIXES))
        self.assertIn("System/Generated", up_mod._verify_scope())

    def test_the_upgrade_surface_itself_is_not_claimed_as_untouched(self):
        """The product's own files are what the command REPLACES. Counting them
        as 'verified untouched' would be the same lie in the other direction."""
        for surface in ("System/Capabilities/foo/SKILL.md", "CLAUDE.md", "README.md"):
            self.assertTrue(up_mod._in_upgrade_surface(surface), surface)
        for theirs in ("20 Knowledge/note.md", "Published Assets/a.md", "80 User/voice.md",
                       "System/Journal/change-journal.md", "System/Tests/results/r.yaml",
                       "About Me.md", "SYSTEM-MANIFEST.yaml"):
            self.assertFalse(up_mod._in_upgrade_surface(theirs), theirs)

    def test_report_states_the_scope_of_what_it_verified(self):
        """A false assurance is worse than an honest gap: the reader of an
        upgrade report has no other way to learn what 'verified' covered."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            os.makedirs(os.path.join(inst, "Published Assets"))
            write_file(os.path.join(inst, "Published Assets", "a.md"), "mine\n", mode="w")
            rep = run_upgrade(inst, new)
            self.assertTrue(rep.ok, rep.errors)
            claim = rep.info["user_content"]
            self.assertIn("byte-identical", claim)
            self.assertIn("outside the upgrade surface", claim)
            self.assertIn("excludes regenerated", claim)

    # ---- DEC-115: the open editor must not be able to veto an upgrade -------
    #
    # Measured on all three live instances, 2026-07-27: Obsidian, running and
    # watching the vault, re-saved its own `workspace.json` in reaction to the
    # index files `generate` writes inside the upgrade. The comparison called
    # that a user file changing mid-run and refused the version bump — so NO
    # vault open in an editor could complete an upgrade. Both directions are
    # pinned here: session state must not block, a real note must still block.

    def test_editor_session_state_changing_mid_run_does_not_block(self):
        """THE LIVE DEFECT. `.obsidian/workspace.json` is rewritten by whatever
        application has the vault open — not by any human and not by this
        command. It must not be read as the user's work changing."""
        rep = self._corrupt_after_apply(".obsidian/workspace.json")
        self.assertTrue(rep.ok, rep.errors)
        self.assertFalse(any("CONTENT INTEGRITY" in e for e in rep.errors), rep.errors)

    def test_editor_session_state_is_reported_by_name_not_silenced(self):
        """Excluded from the verdict is not the same as hidden. The reader must
        still learn the file moved, and why that was not a corruption."""
        rep = self._corrupt_after_apply(".obsidian/workspace.json")
        said = str(rep.info.get("editor_session_state", ""))
        self.assertIn(".obsidian/workspace.json", said)
        self.assertIn("session state", said.lower())
        # and the headline claim counts it separately rather than folding it in
        # with the regenerated projections, which are a different thing entirely
        self.assertIn("editor session-state file(s) reported, not counted",
                      str(rep.info.get("user_content")))

    def test_a_real_note_changing_mid_run_still_blocks(self):
        """The guarantee this exclusion must not weaken. A user's NOTE changing
        during an upgrade is the hazard the check was built for, and it is still
        a hard failure that names the file and points at the checkpoint."""
        self._assert_caught("20 Knowledge/my-note.md")

    def test_obsidian_settings_are_still_user_content(self):
        """Deliberately narrow. Hotkeys, appearance and plugin settings are
        authored BY the user; only the pane-layout files are the app's own."""
        self._assert_caught(".obsidian/hotkeys.json")
        self.assertFalse(up_mod._is_runtime_state(".obsidian/hotkeys.json"))
        self.assertFalse(up_mod._is_runtime_state(".obsidian/plugins/x/data.json"))
        for live in up_mod.RUNTIME_STATE_PATHS:
            self.assertTrue(up_mod._is_runtime_state(live), live)

    def test_session_state_exclusion_is_stated_in_the_scope(self):
        """A claim that quietly narrowed itself would be the DEC-109 defect
        again. The scope sentence says what it now declines to judge."""
        self.assertIn("session state", up_mod._verify_scope())

    def test_scope_is_a_complement_not_a_list(self):
        """A folder invented tomorrow is verified by construction. This is the
        property that makes the defect unrepeatable, not just fixed."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            before = up_mod._user_world(inst)
            os.makedirs(os.path.join(inst, "Totally Novel Folder"))
            write_file(os.path.join(inst, "Totally Novel Folder", "x.md"), "new\n", mode="w")
            after = up_mod._user_world(inst)
            self.assertIn("Totally Novel Folder/x.md", after)
            self.assertEqual(len(after), len(before) + 1)


class TestBaseline(unittest.TestCase):
    def test_make_baseline_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as outer:
            release = mk_release(os.path.join(outer, "release"), "1.5.0")
            before = tree_state(release)
            a = Args(); a.make_baseline = True; a.dry_run = True
            rep = Report("upgrade"); up_mod.run(release, a, rep)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(before, tree_state(release),
                             "--make-baseline --dry-run must write NOTHING")
            self.assertIn("dry-run", rep.info.get("mode", ""))

    def test_make_baseline_refuses_on_instance(self):
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            a = Args(); a.make_baseline = True
            rep = Report("upgrade"); up_mod.run(inst, a, rep)
            self.assertFalse(rep.ok)
            self.assertIn("product master only", " ".join(rep.errors))

    def test_version_mismatched_baseline_is_not_trusted(self):
        """A stale baseline mis-describes pristine and would overwrite user
        work — it must drop to fallback, never be trusted."""
        with tempfile.TemporaryDirectory() as outer:
            old = mk_release(os.path.join(outer, "old"), "1.5.0")
            new = mk_release(os.path.join(outer, "new"), "1.6.0", cap_body="NEW BODY")
            inst = mk_instance(os.path.join(outer, "inst"), old)
            bp = os.path.join(inst, "System", ".baseline-manifest.json")
            data = json.loads(read_file(bp)); data["system_version"] = "1.1.0"
            write_file(bp, json.dumps(data), mode="w")
            rep = run_upgrade(inst, new)
            self.assertEqual(rep.info.get("classification_base"), "fallback")
            self.assertIn("OLD BODY", read_file(os.path.join(
                inst, "System", "Capabilities", "foo", "SKILL.md")))

    def test_shipped_baseline_is_fresh_on_the_master(self):
        """The committed baseline must match the committed tree — this is what
        makes DEC-074's 'every release ships one' checkable in CI instead of a
        release-day hope. Regenerate with: aios upgrade --make-baseline."""
        import yaml as _y
        man = _y.safe_load(read_file(os.path.join(VAULT, "SYSTEM-MANIFEST.yaml")))
        if man["system"].get("instance_role") != "generic-master":
            self.skipTest("instance — baseline freshness binds the product master only")
        bp = os.path.join(VAULT, "System", ".baseline-manifest.json")
        self.assertTrue(os.path.exists(bp),
                        "product master must ship System/.baseline-manifest.json (DEC-074)")
        data = json.loads(read_file(bp))
        self.assertEqual(data["system_version"], str(man["system"]["system_version"]),
                         "baseline version must match the manifest")
        self.assertEqual(data["files"], up_mod._hash_tree(VAULT),
                         "baseline is stale — run: aios upgrade --make-baseline")


if __name__ == "__main__":
    unittest.main()
