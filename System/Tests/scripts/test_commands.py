"""Per-command regression tests (independent audit M-04): links, dupes,
checkpoint/rollback, health, scaffold, migrate, review-due, and the
centralized kill switch for every write command."""
from test_io import read_file, write_file
import os, sys, shutil, tempfile, subprocess, unittest, datetime, hashlib
import yaml

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from scaffold import product_manifest   # noqa: E402
from lib.report import Report                          # noqa: E402
from lib.migrations import compute_manifest_hash, compute_source_identity  # noqa: E402
from cmd import links as links_mod, dupes as dupes_mod, health as health_mod  # noqa: E402
from cmd import checkpoint as ck_mod, review_due as rd_mod                     # noqa: E402


class Args:
    json = False; message = None; rollback = None; confirm = False
    clean = False; type = None; name = None; register = None
    migration = None; apply = False; target = None


def mini_vault(tmp, switch="true"):
    for d in ("System/Schemas", "System/Registries", "System/Scripts",
              "System/Skills", "System/Workflows", "System/Templates",
              "System/Migrations", "System/Journal", "20 Knowledge", "00 Inbox"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    man = product_manifest()   # explicit generic-master, never the host's role
    man = man.replace("ai_writes_enabled: true", f"ai_writes_enabled: {switch}")
    with open(os.path.join(tmp, "SYSTEM-MANIFEST.yaml"), "w") as stream:
        stream.write(man)
    shutil.copy(
        os.path.join(VAULT, "System", ".baseline-manifest.json"),
        os.path.join(tmp, "System", ".baseline-manifest.json"),
    )
    for f in os.listdir(os.path.join(VAULT, "System", "Schemas")):
        shutil.copy(os.path.join(VAULT, "System", "Schemas", f), os.path.join(tmp, "System", "Schemas"))
    with open(os.path.join(tmp, "System", "Journal", "change-journal.md"), "w") as stream:
        stream.write("# Change journal\n")
    return tmp

def give_doc_coverage(tmp, cid, did="01"):
    """Minimal diagram coverage so DEC-051's documentation gate lets a component
    activate: map the component to one described diagram whose SVG exists."""
    dd = os.path.join(tmp, "System", "Documentation", "Diagrams")
    os.makedirs(os.path.join(dd, "svg"), exist_ok=True)
    write_file(os.path.join(dd, "svg", "t.svg"), "<svg/>", mode="w")
    write_file(os.path.join(dd, "coverage.yaml"), 'diagrams:\n  "%s": {file: t.svg, title: T, theme: T}\ncomponents:\n  %s: ["%s"]\n' % (did, cid, did), mode="w")
    write_file(os.path.join(dd, "diagram-metadata.yaml"), '"%s":\n  description: test diagram for %s\n' % (did, cid), mode="w")

NOTE = """---
id: note-t{n}
type: note
created: 2026-07-10
updated: 2026-07-10
summary: t{n}
{extra}---
Body {body}
"""

REC = """---
id: {i}
type: {t}
created: 2026-07-10
updated: 2026-07-10
summary: {i}
{extra}---
Body {body}
"""

def aios(tmp, *argv):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "aios.py"),
                           *argv, "--root", tmp], capture_output=True, text=True)


def migration_yaml(name, transform, validation=None):
    data = {
        "schema_version": "1.1.0",
        "id": f"migration-{name}",
        "version_target": "vault_profile_version",
        "source_distribution": "personal-ai-os",
        "source_identity": compute_source_identity(VAULT),
        "from_version": "1.1.0",
        "to_version": "1.1.1",
        "prerequisites": [],
        "content_selector": {"all": True} if "script" in transform else {"type": "note"},
        "transform": transform,
        "validation": validation or [{"check": "vault-validate"}],
        "rollback": {
            "strategy": "exact-checkpoint",
            "automatic_on_validation_failure": True,
        },
        "idempotency_key": f"migration-{name}-v1",
        "manifest_hash": "",
    }
    data["manifest_hash"] = compute_manifest_hash(data)
    return yaml.safe_dump(data, sort_keys=False)


class TestLinksAndDupes(unittest.TestCase):
    def test_broken_frontmatter_ref_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            write_file(os.path.join(tmp, "20 Knowledge", "A.md"), NOTE.format(n=1, extra="related: [note-does-not-exist]\n", body="x"), mode="w")
            rep = Report("links"); links_mod.run(tmp, Args(), rep)
            self.assertIn("unknown id", " ".join(rep.errors))

    def test_duplicate_titles_detected_and_underscore_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "00 Inbox", "sub"), exist_ok=True)
            write_file(os.path.join(tmp, "20 Knowledge", "Same Title.md"), NOTE.format(n=2, extra="", body="x"), mode="w")
            write_file(os.path.join(tmp, "00 Inbox", "Same Title.md"), NOTE.format(n=3, extra="", body="y"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "_ABOUT.md"), "about", mode="w")
            write_file(os.path.join(tmp, "00 Inbox", "_ABOUT.md"), "about", mode="w")
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertIn("duplicate title", " ".join(rep.errors))
            self.assertNotIn("_about", " ".join(rep.errors).lower())

    def test_convention_basename_across_folders_warns_not_errors(self):
        """A method may REQUIRE the same filename once per project folder (a
        method-mandated per-project HANDOFF.md — live case, found on the first
        fully-synced instance run on v1.30.x): distinct ids in distinct folders
        = the method working, not ambiguity."""
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "10 Projects", "Alpha"), exist_ok=True)
            os.makedirs(os.path.join(tmp, "10 Projects", "Beta"), exist_ok=True)
            write_file(os.path.join(tmp, "10 Projects", "Alpha", "HANDOFF.md"), NOTE.format(n=4, extra="", body="alpha handoff"), mode="w")
            write_file(os.path.join(tmp, "10 Projects", "Beta", "HANDOFF.md"), NOTE.format(n=5, extra="", body="beta handoff"), mode="w")
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertNotIn("HANDOFF", " ".join(rep.errors))
            self.assertIn("convention filename", " ".join(rep.warnings))

    def test_convention_name_same_folder_still_errors(self):
        """Two typed notes normalizing to a convention name in ONE folder is
        genuine ambiguity — the exemption must not swallow it."""
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            write_file(os.path.join(tmp, "20 Knowledge", "HANDOFF.md"), NOTE.format(n=6, extra="", body="one"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "Hand-off.md"), NOTE.format(n=7, extra="", body="two"), mode="w")   # normalizes to "hand off" — distinct key
            write_file(os.path.join(tmp, "20 Knowledge", "Handoff+.md"), NOTE.format(n=8, extra="", body="three"), mode="w")  # normalizes to "handoff" — same key, same folder
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertTrue(any("duplicate title" in e for e in rep.errors), (rep.errors, rep.warnings))

    def test_user_extends_convention_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "80 User"), exist_ok=True)
            write_file(os.path.join(tmp, "80 User", "dupes-conventions.yaml"), "basenames: [WEEKLY.md]\n", mode="w")
            os.makedirs(os.path.join(tmp, "10 Projects", "Alpha"), exist_ok=True)
            os.makedirs(os.path.join(tmp, "10 Projects", "Beta"), exist_ok=True)
            for i, proj in ((9, "Alpha"), (10, "Beta")):
                write_file(os.path.join(tmp, "10 Projects", proj, "WEEKLY.md"), NOTE.format(n=i, extra="", body="w"), mode="w")
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertNotIn("WEEKLY", " ".join(rep.errors))
            self.assertIn("convention filename", " ".join(rep.warnings))

    def test_declared_derivation_shares_a_title_without_reddening(self):
        """DEC-114: capture a source, write the note that develops it, cite the
        source by id — the documented ingest path — and the note keeps the
        source's title. A lived-in instance did that 24 times and went red for
        it. Different `type`, distinct folders, distinct ids and a declared
        `sources` edge is a derivation, not a duplicate: a WARNING, so the
        pairing stays visible, and never an error."""
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "30 Sources"), exist_ok=True)
            write_file(os.path.join(tmp, "30 Sources", "Charisma.md"), REC.format(i="source-notion-charisma", t="source", extra="", body="verbatim capture"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "Charisma.md"), REC.format(i="note-journal-charisma", t="note",
                           extra="sources: [source-notion-charisma]\n", body="developed thinking"), mode="w")
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("declared derivation", " ".join(rep.warnings))

    def test_derivation_downgrade_requires_the_citation(self):
        """The citation is the whole test. A synthetic fixture also holds an
        unrelated cross-type pair — a personal planning note and a team capture
        both named "Weekly Plan", neither citing the other — and that is a real
        collision the check must keep reporting. Different types alone must
        never buy the downgrade."""
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            os.makedirs(os.path.join(tmp, "30 Sources"), exist_ok=True)
            write_file(os.path.join(tmp, "30 Sources", "Weekly Plan.md"), REC.format(i="source-imported-weekly-plan", t="source", extra="", body="team planning capture"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "Weekly-Plan.md"), REC.format(i="note-personal-weekly-plan", t="note", extra="", body="personal planning note"), mode="w")
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertFalse(rep.ok)
            self.assertIn("typed canon", " ".join(rep.errors))

    def test_derivation_downgrade_never_swallows_the_errors_it_exists_for(self):
        """Each clause of the lineage test, probed one at a time: a cited
        SAME-TYPE pair, a cited SAME-FOLDER pair, and a cited pair sharing one
        id all stay errors. `related` is association, not lineage, so it buys
        nothing either."""
        cases = {
            "same type": [("20 Knowledge/A.md", "note-a1", "note", "sources: [note-a2]\n"),
                          ("00 Inbox/A.md", "note-a2", "note", "")],
            "same folder": [("00 Inbox/B.md", "source-b", "source", ""),
                            ("00 Inbox/B .md", "note-b", "note", "sources: [source-b]\n")],
            "duplicate id": [("30 Sources/C.md", "rec-c", "source", ""),
                             ("20 Knowledge/C.md", "rec-c", "note", "sources: [rec-c]\n")],
            "related is not lineage": [("30 Sources/D.md", "source-d", "source", ""),
                                       ("20 Knowledge/D.md", "note-d", "note", "related: [source-d]\n")],
        }
        for label, recs in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                mini_vault(tmp)
                os.makedirs(os.path.join(tmp, "30 Sources"), exist_ok=True)
                for rel, i, t, extra in recs:
                    write_file(os.path.join(tmp, *rel.split("/")), REC.format(i=i, t=t, extra=extra, body=label), mode="w")
                rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
                self.assertFalse(rep.ok, f"{label}: downgraded, warnings={rep.warnings}")

    def test_derivation_lineage_must_be_connected(self):
        """A source, the note citing it, and an output citing that note is ONE
        lineage and passes. A third same-titled record that cites nobody is not
        part of it, and drags the whole group back to an error."""
        def build(tmp, third_extra):
            mini_vault(tmp)
            for d in ("30 Sources", "40 Outputs"):
                os.makedirs(os.path.join(tmp, d), exist_ok=True)
            write_file(os.path.join(tmp, "30 Sources", "Delta.md"), REC.format(i="source-delta", t="source", extra="", body="capture"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "Delta.md"), REC.format(i="note-delta", t="note", extra="sources: [source-delta]\n", body="note"), mode="w")
            write_file(os.path.join(tmp, "40 Outputs", "Delta.md"), REC.format(i="output-delta", t="output", extra=third_extra, body="deliverable"), mode="w")
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, "derived_from: [note-delta]\n")
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("declared derivation", " ".join(rep.warnings))
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, "")                       # the output cites nothing
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertFalse(rep.ok, rep.warnings)

    def test_pack_content_never_enters_vault_canon(self):
        """DEC-061/DEC-067 non-regression guard, standing behind v1.55.0's
        widening of `okf-check` to pack content.

        DEC-067 exists because a well-formed pack ships its own `README.md` and
        `CHANGELOG.md`, and its notes carry their own ids — merged into canon,
        every correct pack reddened `dupes`. `okf-check` now READS pack content;
        it must never make it MEMBERS. Two packs plus the vault, all three
        carrying the collision pair and a duplicate id, and canon must not
        notice: coverage is not canon."""
        with tempfile.TemporaryDirectory() as tmp:
            mini_vault(tmp)
            write_file(os.path.join(tmp, "20 Knowledge", "README.md"), NOTE.format(n=61, extra="", body="the vault's own readme"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "CHANGELOG.md"), NOTE.format(n=62, extra="", body="the vault's own changelog"), mode="w")
            for pid in ("alpha", "beta"):
                base = os.path.join(tmp, "Packs", pid)
                os.makedirs(os.path.join(base, "01 Content"), exist_ok=True)
                write_file(os.path.join(base, "pack.yaml"), f"id: pack-{pid}\nversion: 1.0.0\n", mode="w")
                write_file(os.path.join(base, "README.md"), NOTE.format(n=61, extra="", body="colliding id AND colliding basename"), mode="w")
                write_file(os.path.join(base, "CHANGELOG.md"), NOTE.format(n=62, extra="", body="colliding id AND colliding basename"), mode="w")
                write_file(os.path.join(base, "01 Content", "Shared Title.md"), NOTE.format(n=63, extra="", body="same id in both packs"), mode="w")
            rep = Report("dupes"); dupes_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, f"pack content reached canon: {rep.errors}")
            self.assertNotIn("Packs", " ".join(rep.errors) + " ".join(rep.warnings))

            from lib.frontmatter import iter_markdown          # the one canon walker
            ids = [str(n.meta.get("id")) for n in iter_markdown(tmp) if n.meta.get("id")]
            self.assertEqual(sorted(ids), sorted(set(ids)), "canon id space has duplicates")
            self.assertFalse([n for n in iter_markdown(tmp) if "Packs" in n.path],
                             "a Packs/ file entered the canon walk")

            from cmd import okfcheck as okf_mod                # and yet okf-check reads them
            orep = Report("okf-check"); okf_mod.run(tmp, Args(), orep)
            self.assertIn("alpha: 1", orep.info["scope"])
            self.assertIn("beta: 1", orep.info["scope"])


class TestCheckpointRollback(unittest.TestCase):
    def test_git_rollback_restores_exact_tree(self):
        """Audit-2 H-07: rollback must also delete files COMMITTED after the
        checkpoint — `git checkout <ref> -- .` alone leaves them in place."""
        if not shutil.which("git"):
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            def git(*a):
                return subprocess.run(["git", *a], cwd=tmp, capture_output=True, text=True)
            git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
            write_file(os.path.join(tmp, "20 Knowledge", "keep.md"), NOTE.format(n=31, extra="", body="ORIGINAL"), mode="w")
            a = Args(); a.message = "base"
            rep = Report("checkpoint"); ck_mod.run(tmp, a, rep)
            ref1 = str(rep.info["checkpoint"]).split()[-1]
            write_file(os.path.join(tmp, "20 Knowledge", "keep.md"), NOTE.format(n=31, extra="", body="MODIFIED"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "later.md"), NOTE.format(n=32, extra="", body="added after checkpoint"), mode="w")
            a2 = Args(); a2.message = "after"
            ck_mod.run(tmp, a2, Report("checkpoint"))          # later.md is now TRACKED
            write_file(os.path.join(tmp, "20 Knowledge", "wip.md"), NOTE.format(n=33, extra="", body="never committed"), mode="w")
            back = Args(); back.rollback = ref1; back.confirm = True
            rrep = Report("rollback"); ck_mod.run(tmp, back, rrep)
            self.assertTrue(rrep.ok, rrep.errors)
            self.assertIn("ORIGINAL", read_file(os.path.join(tmp, "20 Knowledge", "keep.md")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "20 Knowledge", "later.md")),
                             "tracked post-checkpoint file must be removed by exact restore")
            self.assertTrue(os.path.exists(os.path.join(tmp, "20 Knowledge", "wip.md")),
                            "never-committed work survives unless --clean")
            self.assertEqual(rrep.info.get("post_rollback_validate"), "OK")

    def test_zip_snapshot_without_git(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v")); os.makedirs(tmp, exist_ok=True)
            a = Args(); a.message = "test"
            rep = Report("checkpoint"); ck_mod.run(tmp, a, rep)
            self.assertTrue(rep.ok, rep.errors)
            self.assertTrue(str(rep.info["checkpoint"]).endswith(".zip"))
            self.assertTrue(os.path.exists(rep.info["checkpoint"]))

    def test_rollback_requires_confirm(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            a = Args(); a.rollback = "HEAD"
            rep = Report("rollback"); ck_mod.run(tmp, a, rep)
            self.assertFalse(rep.ok)
            self.assertIn("--confirm", " ".join(rep.errors))


class TestKillSwitchCoverage(unittest.TestCase):
    def test_every_write_command_refuses(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"), switch="false")
            for cmd in (["generate"], ["scaffold", "--type", "workflow", "--name", "x"],
                        ["migrate"], ["import"],
                        ["upgrade", "some-release-path", "--apply"],
                        # DEC-098: extract emits Markdown and files the original;
                        # dedupe-batch is a report EXCEPT in its --annotate form,
                        # which writes the overlap map into frontmatter
                        ["extract", "some.docx"],
                        ["measure", "some-transcript.md", "--extract", "00 Inbox/human.md"],
                        ["docgen"],
                        ["dedupe-batch", "some-folder", "--annotate"]):
                r = aios(tmp, *cmd)
                self.assertIn("kill switch", r.stdout + r.stderr, cmd)
                self.assertNotEqual(r.returncode, 0, cmd)
            # final-audit H-07: rollback WITH --confirm is human-authorized
            # recovery and must NOT deadlock behind the kill switch (it may
            # fail for other reasons here — no git — but never on the switch)
            r = aios(tmp, "rollback", "HEAD", "--confirm")
            self.assertNotIn("kill switch", r.stdout + r.stderr)
            r = aios(tmp, "docgen", "--check")
            self.assertNotIn("kill switch", r.stdout + r.stderr)
            r = aios(tmp, "upgrade", "some-release-path")
            self.assertNotIn("kill switch", r.stdout + r.stderr)
            r = aios(tmp, "measure", "some-transcript.md")
            self.assertNotIn("kill switch", r.stdout + r.stderr)

    def test_checkpoint_allowed_while_off_by_design(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"), switch="false")
            r = aios(tmp, "checkpoint", "-m", "protective")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestScaffoldMigrateReviewDue(unittest.TestCase):
    def test_scaffold_creates_draft_and_refuses_activation_without_tests(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            r = aios(tmp, "scaffold", "--type", "workflow", "--name", "demo-flow")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(os.path.exists(os.path.join(tmp, "System", "Workflows", "demo-flow.md")))
            r = aios(tmp, "scaffold", "--register", "workflow-demo-flow")
            self.assertIn("no tests listed", r.stdout + r.stderr)

    def test_support_index_integrity(self):
        """The support harness map (support-index.json) must be well-formed: every
        doc path and diagram file it references exists, and every diagram carries a
        description. Read-only; skips if the index has not been generated."""
        import json
        p = os.path.join(VAULT, "System", "Generated", "support-index.json")
        if not os.path.exists(p):
            self.skipTest("support-index.json not generated (run aios generate)")
        idx = json.loads(read_file(p, encoding="utf-8"))
        self.assertTrue(idx.get("docs") and idx.get("diagrams"), "empty support index")
        for d in idx["docs"]:
            self.assertTrue(os.path.exists(os.path.join(VAULT, d["path"])), f"missing doc: {d['path']}")
        for g in idx["diagrams"]:
            self.assertTrue(os.path.exists(os.path.join(VAULT, g["file"])), f"missing diagram: {g['file']}")
            self.assertTrue(str(g.get("description", "")).strip(), f"undescribed diagram: {g['id']}")

    def test_register_refuses_activation_without_documentation(self):
        """DEC-051: documentation is a peer of tests. A component that satisfies the
        test gate but is not mapped to a described diagram must still refuse to
        activate — the documentation gate hard-blocks it."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            self.assertEqual(aios(tmp, "scaffold", "--type", "workflow", "--name", "demo-doc").returncode, 0)
            comp = os.path.join(tmp, "System", "Workflows", "demo-doc.md")
            txt = read_file(comp).replace("tests: []", "tests: [System/Tests/t.md]")
            write_file(comp, txt, mode="w")
            os.makedirs(os.path.join(tmp, "System", "Tests", "results"), exist_ok=True)
            write_file(os.path.join(tmp, "System", "Tests", "t.md"), "# t\n", mode="w")
            write_file(os.path.join(tmp, "System", "Tests", "results", "workflow-demo-doc.yaml"), "result: pass\nversion: 0.1.0\n", mode="w")
            # tests satisfied, but no diagram coverage → must refuse on the doc gate
            r = aios(tmp, "scaffold", "--register", "workflow-demo-doc")
            self.assertIn("documentation gate", r.stdout + r.stderr)

    def test_migrate_dry_run_and_live_apply_refusal(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            old_note = NOTE.format(n=9, extra="x_old_field: 1\n", body="m")
            new_note = old_note.replace("x_old_field:", "x_new_field:")
            write_file(os.path.join(tmp, "20 Knowledge", "M.md"), old_note, mode="w")
            md = os.path.join(tmp, "System", "Migrations", "001-test")
            os.makedirs(md)
            write_file(os.path.join(md, "payload.md"), new_note, mode="w")
            write_file(os.path.join(md, "migration.yaml"), migration_yaml(
                    "001-test",
                    {"replace_exact_files": [{
                        "path": "20 Knowledge/M.md",
                        "old_sha256": hashlib.sha256(old_note.encode()).hexdigest(),
                        "payload": "payload.md",
                        "new_sha256": hashlib.sha256(new_note.encode()).hexdigest(),
                    }]},
                    [{"check": "vault-validate"}],
                ), mode="w")
            r = aios(tmp, "migrate", "--migration", "001-test")
            self.assertIn("dry-run", r.stdout)
            r = aios(tmp, "migrate", "--migration", "001-test", "--apply")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("standalone live-vault", r.stdout + r.stderr)
            self.assertIn("x_old_field", read_file(os.path.join(tmp, "20 Knowledge", "M.md")))

    def test_review_due_flags_unsourced_claims_and_inbox(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            write_file(os.path.join(tmp, "20 Knowledge", "C.md"), NOTE.format(n=5, extra="subtype: claim\n", body="c"), mode="w")
            write_file(os.path.join(tmp, "00 Inbox", "raw.md"), NOTE.format(n=6, extra="", body="raw"), mode="w")
            rep = Report("review-due"); rd_mod.run(tmp, Args(), rep)
            self.assertIn("note-t5", str(rep.info["claims_without_sources"]))
            self.assertIn("note-t6", str(rep.info["unprocessed_inbox"]))


class TestHealth(unittest.TestCase):
    def test_health_aggregates(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            rep = Report("health"); health_mod.run(tmp, Args(), rep)
            self.assertIn("validate", rep.info)
            self.assertIn("inbox_items", rep.info)

    def test_health_flags_unverified_canon(self):
        """Canonical-core doctrine (Principle 26): a note filed in 20 Knowledge as
        active but still unverified is counted as staging masquerading as canon;
        an active + verified note is not."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            write_file(os.path.join(tmp, "20 Knowledge", "U.md"), NOTE.format(n=7, extra="status: active\nverification: unverified\n", body="u"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "V.md"), NOTE.format(n=8, extra="status: active\nverification: verified\n", body="v"), mode="w")
            rep = Report("health"); health_mod.run(tmp, Args(), rep)
            self.assertEqual(rep.info["unverified_in_knowledge"], 1)

    def test_checkup_reads_the_doctrine_signals(self):
        """checkup: a light, pull-only readout of inbox / review-due / unverified-canon,
        with a plain friendly line — and a 'tidy' message when all clear."""
        from cmd import checkup as checkup_mod
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            rep = Report("checkup"); checkup_mod.run(tmp, Args(), rep)
            self.assertEqual((rep.info["inbox_items"], rep.info["review_due"],
                              rep.info["unverified_in_knowledge"]), (0, 0, 0))
            self.assertIn("tidy", rep.info["checkup"])
            write_file(os.path.join(tmp, "00 Inbox", "raw.md"), NOTE.format(n=9, extra="", body="r"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "U.md"), NOTE.format(n=10, extra="status: active\nverification: unverified\n", body="u"), mode="w")
            rep = Report("checkup"); checkup_mod.run(tmp, Args(), rep)
            self.assertEqual(rep.info["inbox_items"], 1)
            self.assertEqual(rep.info["unverified_in_knowledge"], 1)
            self.assertNotIn("tidy", rep.info["checkup"])
            self.assertIn("waiting in staging", rep.info["checkup"])

    def test_generated_docs_freshness_flagged(self):
        """DEC-039 Phase 3: health flags when the generated docs are overdue for a
        rebuild (stale generated_at), and stays quiet when they're fresh."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            gen = os.path.join(tmp, "System", "Generated"); os.makedirs(gen)
            write_file(os.path.join(gen, "implementation-status.md"), "---\nfile_class: generated\ngenerated_at: 2020-01-01T00:00:00\n---\n# Implementation Status\n", mode="w")
            rep = Report("health"); health_mod.run(tmp, Args(), rep)
            self.assertIn("generated_docs_age_days", rep.info)
            self.assertTrue(any("last rebuilt" in w for w in rep.warnings))
            write_file(os.path.join(gen, "implementation-status.md"), f"---\ngenerated_at: {datetime.datetime.now().isoformat(timespec='seconds')}\n---\nx\n", mode="w")
            rep = Report("health"); health_mod.run(tmp, Args(), rep)
            self.assertFalse(any("last rebuilt" in w for w in rep.warnings))

    def test_derived_doc_drift_flagged(self):
        """Phase 2 (DEC-039): a derived doc reviewed against an older source
        version is flagged for prose refresh; bumping the marker clears it."""
        SRC = ("---\nid: doc-src\ntype: system-doc\nauthority: canonical\nversion: 2.0.0\n"
               "created: 2026-07-10\nupdated: 2026-07-10\nsummary: source\n---\nbody\n")
        DER = ("---\nid: doc-der\ntype: system-doc\nauthority: derived\nderived_from: [doc-src]\n"
               "version: 1.0.0\nx_reviewed_against: [\"doc-src:{v}\"]\n"
               "created: 2026-07-10\nupdated: 2026-07-10\nsummary: derived\n---\nbody\n")
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            write_file(os.path.join(tmp, "20 Knowledge", "src.md"), SRC, mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "der.md"), DER.format(v="1.0.0"), mode="w")
            rep = Report("health"); health_mod.run(tmp, Args(), rep)
            self.assertGreaterEqual(rep.info.get("derived_docs_behind", 0), 1)
            self.assertTrue(any("doc-der" in e and "doc-src" in e for e in rep.errors))   # DEC-069: drift is now an error
            write_file(os.path.join(tmp, "20 Knowledge", "der.md"), DER.format(v="2.0.0"), mode="w")
            rep = Report("health"); health_mod.run(tmp, Args(), rep)
            self.assertEqual(rep.info.get("derived_docs_behind", 0), 0)


class TestPrivacyEnforcement(unittest.TestCase):
    """H-02/DEC-013: deterministic filtering happens before content is returned."""
    def _probe(self, tmp, cls, use):
        write_file(os.path.join(tmp, "20 Knowledge", "P.md"), NOTE.format(n=7, extra=f"classification: {cls}\nai_use: {use}\n", body="XYZZY-PROBE"), mode="w")

    def test_hosted_excludes_local_only_and_unapproved_private(self):
        from cmd.search import permitted
        hosted_unapproved = {"hosted": True, "may_process_private": False}
        hosted_approved = {"hosted": True, "may_process_private": True}
        local = {"hosted": False}
        self.assertFalse(permitted({"classification": "private", "ai_use": "local-only"}, hosted_approved))
        self.assertFalse(permitted({"classification": "private"}, hosted_unapproved))
        self.assertTrue(permitted({"classification": "private"}, hosted_approved))
        self.assertTrue(permitted({"classification": "private", "ai_use": "local-only"}, local))
        self.assertFalse(permitted({"classification": "restricted"}, local))     # hard, even local
        self.assertFalse(permitted({"ai_use": "prohibited"}, local))              # hard, even local

    def test_search_and_read_withhold_content(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(tmp, "System", "Runtime Profiles"), exist_ok=True)
            shutil.copy(os.path.join(VAULT, "System", "Runtime Profiles", "claude-code.yaml"),
                        os.path.join(tmp, "System", "Runtime Profiles"))
            self._probe(tmp, "private", "local-only")
            r = aios(tmp, "search", "--query", "XYZZY-PROBE", "--domain", "shared")
            self.assertIn("none", r.stdout)                      # invisible
            self.assertNotIn("XYZZY-PROBE", r.stdout)            # no content leak
            r = aios(tmp, "read", "--id", "note-t7", "--domain", "shared")
            self.assertNotIn("XYZZY-PROBE", r.stdout)
            # final-audit H-01: a hidden record is INDISTINGUISHABLE from an
            # absent one — same message, no existence confirmation
            r2 = aios(tmp, "read", "--id", "note-never-existed", "--domain", "shared")
            hidden = (r.stdout + r.stderr).replace("note-t7", "X")
            absent = (r2.stdout + r2.stderr).replace("note-never-existed", "X")
            self.assertEqual(hidden, absent)
            self.assertNotIn("privacy_excluded_count",
                             aios(tmp, "search", "--query", "anything",
                                  "--domain", "shared").stdout)


class TestV101Findings(unittest.TestCase):
    """v1.0.1 regressions for the real-workload findings (F-1..F-4)."""

    def test_f1_supersede_and_archive_keeps_health_green(self):
        """F-1: following the documented supersede-and-archive workflow must
        never redden dupes/health (live case: a lived-in personal instance at
        commit 5d7782a)."""
        from cmd import dupes as d_mod
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(tmp, "90 Archive"), exist_ok=True)
            write_file(os.path.join(tmp, "20 Knowledge", "Framework.md"), NOTE.format(n=61, extra="status: active\n", body="v2"), mode="w")
            write_file(os.path.join(tmp, "90 Archive", "Framework.md"), NOTE.format(n=62, extra="status: archived\nsuperseded_by: note-t61\n", body="v1"), mode="w")
            rep = Report("dupes"); d_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)
            # superseded-in-place (not yet moved) is equally exempt
            write_file(os.path.join(tmp, "20 Knowledge", "Framework old.md"), NOTE.format(n=63, extra="status: superseded\n", body="v0")
                .replace("id: note-t63", "id: note-t63\naliases: []"), mode="w")
            rep2 = Report("dupes"); d_mod.run(tmp, Args(), rep2)
            self.assertTrue(rep2.ok, rep2.errors)

    def test_f1_untyped_collisions_warn_typed_collisions_error(self):
        """F-1 (TX case): foreign-corpus basename reuse warns; ambiguous typed
        canon still errors."""
        from cmd import dupes as d_mod
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(tmp, "20 Knowledge", "A"), exist_ok=True)
            os.makedirs(os.path.join(tmp, "20 Knowledge", "B"), exist_ok=True)
            for d in ("A", "B"):   # untyped legacy files, same basename
                write_file(os.path.join(tmp, "20 Knowledge", d, "Key Differentiators.md"), "legacy, no frontmatter\n", mode="w")
            rep = Report("dupes"); d_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)             # no ERROR
            self.assertTrue(any("untyped" in w for w in rep.warnings))
            for i, d in enumerate(("A", "B")):              # now typed canon collides
                write_file(os.path.join(tmp, "20 Knowledge", d, "Pricing.md"), NOTE.format(n=70 + i, extra="", body="x"), mode="w")
            rep2 = Report("dupes"); d_mod.run(tmp, Args(), rep2)
            self.assertFalse(rep2.ok)
            self.assertTrue(any("typed canon" in e for e in rep2.errors))

    def test_f2_file_embeds_resolve_by_basename(self):
        from cmd import links as l_mod
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(tmp, "30 Sources", "Attachments"), exist_ok=True)
            write_file(os.path.join(tmp, "30 Sources", "Attachments", "Pasted image 20260623.png"), b"png", mode="wb")
            write_file(os.path.join(tmp, "20 Knowledge", "Doc.md"), NOTE.format(n=80, extra="", body="see ![[Pasted image 20260623.png]] and ![[missing-file.png]]"), mode="w")
            rep = Report("links"); l_mod.run(tmp, Args(), rep)
            joined = " ".join(rep.warnings)
            self.assertNotIn("Pasted image", joined)   # existing file resolves
            self.assertIn("missing-file.png", joined)  # absent file still flagged

    def test_f3_executable_migration_is_refused_before_any_checkpoint_or_write(self):
        from cmd import migrate as m_mod
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            md = os.path.join(tmp, "System", "Migrations", "001-scripted")
            os.makedirs(md)
            write_file(os.path.join(md, "migration.yaml"), migration_yaml("001-scripted", {"script": "go.py"}), mode="w")
            write_file(os.path.join(md, "go.py"), "import sys, os\n"
                "if '--apply' in sys.argv:\n"
                "    open('20 Knowledge/migrated-marker.md','w').write('---\\nid: note-mig-marker\\ntype: note\\nsubtype: concept\\nstatus: active\\nconfidence: low\\nsources: []\\ncreated: 2026-07-10\\nupdated: 2026-07-10\\nsummary: \"marker\"\\n---\\nok\\n')\n"
                "print('dry-run report: 1 file would be created' if '--apply' not in sys.argv else 'applied')\n", mode="w")
            outside = os.path.join(outer, "outside.txt")
            write_file(os.path.join(md, "go.py"), f"open({outside!r},'w').write('unsafe')\n", mode="w")
            a = Args(); a.migration = "001-scripted"
            rep = Report("migrate"); m_mod.run(tmp, a, rep)
            self.assertFalse(rep.ok)
            self.assertIn("script", " ".join(rep.errors))
            self.assertFalse(os.path.exists(os.path.join(tmp, "20 Knowledge", "migrated-marker.md")),
                             "refusal must write nothing")
            self.assertFalse(os.path.exists(outside), "migration code must never execute")
            self.assertNotIn("checkpoint", rep.info)

    def test_f4_foreign_conventions_collapse_warnings(self):
        from cmd import validate as v_mod
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(tmp, "System", "Registries"), exist_ok=True)
            shutil.copy(os.path.join(VAULT, "System", "Registries", "folder-registry.yaml"),
                        os.path.join(tmp, "System", "Registries", "folder-registry.yaml"))
            reg = read_file(os.path.join(tmp, "System", "Registries", "folder-registry.yaml"))
            reg = reg.replace('inbox:        {path: "00 Inbox",     purpose: capture-and-quarantine}',
                              'inbox:        {path: "00 Inbox",     purpose: capture-and-quarantine, conventions: foreign}')
            write_file(os.path.join(tmp, "System", "Registries", "folder-registry.yaml"), reg, mode="w")
            for i in range(5):
                write_file(os.path.join(tmp, "00 Inbox", f"legacy-{i}.md"), "raw, no frontmatter\n", mode="w")
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            per_file = [w for w in rep.warnings if ".md: no frontmatter" in w and "legacy-" in w]
            rollup = [w for w in rep.warnings if "5 legacy-convention" in w]
            self.assertEqual(per_file, [], "per-file warnings must collapse")
            self.assertEqual(len(rollup), 1, rep.warnings)


class TestCurrentKnowledgeEligibility(unittest.TestCase):
    """Final-audit H-03: deterministic search returns CURRENT knowledge by
    default — inbox, archive, and lifecycle-retired records need --all-states."""
    def test_search_excludes_quarantined_and_retired_by_default(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(tmp, "System", "Runtime Profiles"), exist_ok=True)
            shutil.copy(os.path.join(VAULT, "System", "Runtime Profiles", "claude-code.yaml"),
                        os.path.join(tmp, "System", "Runtime Profiles"))
            os.makedirs(os.path.join(tmp, "90 Archive"), exist_ok=True)
            write_file(os.path.join(tmp, "20 Knowledge", "cur.md"), NOTE.format(n=41, extra="status: active\n", body="LIFEPROBE current"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "old.md"), NOTE.format(n=42, extra="status: stale\n", body="LIFEPROBE stale"), mode="w")
            write_file(os.path.join(tmp, "00 Inbox", "raw.md"), NOTE.format(n=43, extra="", body="LIFEPROBE inbox"), mode="w")
            write_file(os.path.join(tmp, "90 Archive", "gone.md"), NOTE.format(n=44, extra="", body="LIFEPROBE archived"), mode="w")
            r = aios(tmp, "search", "--query", "LIFEPROBE", "--domain", "shared")
            self.assertIn("note-t41", r.stdout)
            for absent in ("note-t42", "note-t43", "note-t44"):
                self.assertNotIn(absent, r.stdout)
            r2 = aios(tmp, "search", "--query", "LIFEPROBE", "--all-states",
                      "--domain", "shared")
            for present in ("note-t41", "note-t42", "note-t43", "note-t44"):
                self.assertIn(present, r2.stdout)


class TestGenericSeed(unittest.TestCase):
    """DEC-018/M-06: the shipped generic core has no retrievable user history."""
    def test_examples_are_classed_and_excluded_from_search(self):
        import glob
        ex = glob.glob(os.path.join(VAULT, "System", "Tests", "examples", "*.md"))
        self.assertGreaterEqual(len(ex), 9)
        for f in ex:
            self.assertIn("file_class: example", read_file(f), f)
        r = aios(VAULT, "search", "--query", "Gradual Personalization",
                 "--domain", "shared")
        self.assertIn("none", r.stdout)  # example content is not retrievable

    def test_generic_seed_carries_no_owner_certification(self):
        """Audit-2 H-04/H-06 + DEC-025: the seed ships read-write with working
        defaults, but a copied generic master must not inherit the construction
        owner's certification record or test results. Binds the master only."""
        import yaml as _y
        man = _y.safe_load(read_file(os.path.join(VAULT, "SYSTEM-MANIFEST.yaml")))
        if man["system"].get("instance_role") != "generic-master":
            self.skipTest("personal/test instance — seed rules bind the generic master only")
        prof = _y.safe_load(read_file(os.path.join(VAULT, man["runtime"]["active_profile"])))
        self.assertFalse(prof.get("certifications"),
                         "generic master must not ship another user's certification record")
        self.assertIsNone(prof.get("last_tested"))
        # delta-audit B-01 / DEC-026: an uncertified profile ships at most L2 —
        # everyday reads and safe writes work out of the box; L3+ is earned
        self.assertIn(prof.get("autonomy_level"), ("L0", "L1", "L2"),
                      "uncertified seed must not claim L3+")
        self.assertFalse(os.path.exists(os.path.join(VAULT, "System", "Tests", "results",
                                                     "runtime-claude-code.yaml")),
                         "owner fixture results must not ship in the generic master")

    def test_clean_seed_content_dirs(self):
        """On the generic master (manifest instance_role), personal data is prohibited:
        content dirs AND 80 User must be structurally empty. Personal instances skip."""
        import yaml as _y
        role = _y.safe_load(read_file(os.path.join(VAULT, "SYSTEM-MANIFEST.yaml")))["system"].get("instance_role")
        if role != "generic-master":
            self.skipTest("personal instance — seed check not applicable")
        # F4 (PMM Engine migration finding): a DOMAIN product master legitimately
        # ships seed files (starter config, vocabulary seams). Shipped seeds
        # self-declare with a `product_seed: true` line; anything undeclared is
        # still treated as leaked personal data. Directories cannot declare —
        # only individual, deliberately marked files pass.
        def _declares_seed(path):
            if not os.path.isfile(path):
                return False
            try:
                head = read_file(path, encoding="utf-8", errors="ignore", size=2048)
            except OSError:
                return False
            return "product_seed: true" in head
        for d in ("00 Inbox", "10 Projects", "20 Knowledge", "30 Sources", "40 Outputs", "90 Archive", "80 User"):
            entries = [f for f in os.listdir(os.path.join(VAULT, d))
                       if not f.startswith(("_", ".")) and f != "Attachments"
                       and not _declares_seed(os.path.join(VAULT, d, f))]
            self.assertEqual(entries, [], f"{d} contains non-structural files in the generic master")


class TestRouterIntegrity(unittest.TestCase):
    """Audit-2 M-03/L-01/H-01: the router is machine-checkable — every route
    resolves to real files and the fallback is deterministic. This is what
    keeps progressive disclosure from silently drifting."""
    def _router(self):
        import yaml as _y
        return _y.safe_load(read_file(os.path.join(VAULT, "System", "Runtime", "Task Router.yaml")))

    def test_every_route_loads_only_existing_files(self):
        r = self._router()
        checked = 0
        for mode, routes in r["modes"].items():
            for intent, row in routes.items():
                for path in (row.get("load") or []):
                    self.assertTrue(os.path.exists(os.path.join(VAULT, path)),
                                    f"{mode}.{intent} loads missing file: {path}")
                    checked += 1
        self.assertGreater(checked, 10, "router shrank suspiciously — check modes/loads")

    def test_load_if_present_entries_are_wellformed_user_paths(self):
        """Workstyle (router v1.1.0): load_if_present names user-created files
        that legitimately don't exist on a fresh seed. Entries must be relative
        vault paths outside System/ (System files must exist — they belong in
        load), and at least one route must consult the workstyle map, or the
        feature is unwired."""
        r = self._router()
        seen = []
        for mode, routes in r["modes"].items():
            for intent, row in routes.items():
                for path in (row.get("load_if_present") or []):
                    self.assertIsInstance(path, str,
                                          f"{mode}.{intent}: non-string load_if_present entry")
                    self.assertFalse(os.path.isabs(path),
                                     f"{mode}.{intent}: absolute path {path}")
                    self.assertFalse(path.replace("\\", "/").startswith("System/"),
                                     f"{mode}.{intent}: {path} is a System file — it must exist; use load")
                    seen.append(path.replace("\\", "/"))
        self.assertIn("80 User/workstyle.md", seen,
                      "no route consults the workstyle map — feature unwired")

    def test_fallback_is_deterministic_and_targets_real_intents(self):
        r = self._router()
        intents = {i for routes in r["modes"].values() for i in routes}
        fb = r["fallback"]
        self.assertIsInstance(fb, dict, "fallback must be a mapping, not prose")
        for k, v in fb.items():
            self.assertIn(v, intents, f"fallback '{k}' points at unknown intent '{v}'")

    def test_routes_load_every_capability_their_procedures_invoke(self):
        """Delta-audit B-03: a route must contain everything needed to execute.
        Mechanical closure check: if any PROCEDURE file a route loads mentions
        a hyphenated capability by name, that capability file must be in the
        same route's load list. Reference material (Documentation, Governance,
        Architecture, Operations) describes capabilities without invoking
        them, so only procedure-bearing files are scanned. (Hyphenated names
        only — unambiguous tokens; 'recover' is English prose too often.)"""
        import re
        capdir = os.path.join(VAULT, "System", "Capabilities")
        caps = {d: f"System/Capabilities/{d}/SKILL.md"
                for d in os.listdir(capdir)
                if os.path.isfile(os.path.join(capdir, d, "SKILL.md")) and "-" in d}
        PROCEDURAL = ("System/Capabilities/", "System/Agents/", "System/Onboarding/")
        r = self._router()
        for mode, routes in r["modes"].items():
            for intent, row in routes.items():
                load = row.get("load") or []
                bodies = ""
                for path in load:
                    fp = os.path.join(VAULT, path)
                    if (os.path.exists(fp) and path.endswith(".md")
                            and path.startswith(PROCEDURAL)):
                        with open(fp, encoding="utf-8") as stream:
                            bodies += stream.read()
                for name, cpath in caps.items():
                    if re.search(rf"\b{re.escape(name)}\b", bodies) and cpath not in load:
                        self.fail(f"{mode}.{intent} loads a procedure that invokes "
                                  f"'{name}' but does not load {cpath}")

    def test_reading_order_and_entrypoints_resolve(self):
        import yaml as _y
        man = _y.safe_load(read_file(os.path.join(VAULT, "SYSTEM-MANIFEST.yaml")))
        for seq in man["reading_order"].values():
            for path in seq:
                self.assertTrue(os.path.exists(os.path.join(VAULT, path)),
                                f"reading_order names missing file: {path}")
        for key, path in man["entrypoints"].items():
            if str(path).startswith("System/Generated"):
                continue   # disposable; absent until `aios generate` on a fresh copy
            self.assertTrue(os.path.exists(os.path.join(VAULT, path)),
                            f"entrypoint {key} names missing file: {path}")


class TestNoRetiredMachinery(unittest.TestCase):
    """Release-audit H-06/M-03: executable surfaces must never reference the
    retired skills/registry architecture. Historical records (amendment log,
    CHANGELOG, Active Decisions, journal) are exempt — they SHOULD remember."""
    # "SKILL.md" left this list under DEC-070: the filename returns as the
    # Agent Skills packaging standard (<name>/SKILL.md), not the retired
    # pre-v1.0 skills/registry architecture — System/Skills still catches that.
    RETIRED = ["System/Skills", "skill.yaml", "agent.yaml",
               "component-registry.yaml", "process-source", "create-note-safely",
               "update-note-safely", "capture-tacit-context", "enrich-note",
               "compile-context", "find-canonical"]
    SURFACES = ("System/Capabilities", "System/Agents", "System/Workflows",
                "System/Runtime", "System/Onboarding", "System/Operations",
                "System/Schemas", "System/Documentation", "System/Tests/fixtures",
                "System/Governance",
                "00 Inbox", "90 Archive")

    def test_executable_surfaces_are_clean(self):
        hits = []
        for base in self.SURFACES:
            root = os.path.join(VAULT, base)
            if not os.path.isdir(root):
                continue
            for dirpath, _, files in os.walk(root):
                for fn in files:
                    if not fn.endswith((".md", ".yaml")):
                        continue
                    if fn == "Active Decisions.md":
                        continue   # the historical register REMEMBERS retired machinery by design
                    if base in ("00 Inbox", "90 Archive") and not fn.startswith("_"):
                        continue   # content folders: only the structural _ABOUT guides are
                                   # product surface — USER content may say anything (v1.0.2)
                    with open(os.path.join(dirpath, fn), encoding="utf-8") as stream:
                        numbered_lines = list(enumerate(stream, 1))
                    for i, line in numbered_lines:
                        if line.strip().startswith("- skill-"):
                            continue   # `consolidates:` lists historical ids by design
                        if "skills_used" in line:
                            continue   # legacy-compat key name, documented in the schema
                        # DEC-032: the bare-word 'skill(s)' rule is retired — it fought the
                        # ecosystem's own vocabulary (Claude 'skills'; domain packs' folder
                        # names) and produced three false-positive incidents (v1.0.2, v1.0.3,
                        # PMM migration F1) against zero catches the artifact terms below
                        # missed. Machinery drift is caught by artifact names, not English words.
                        for term in self.RETIRED:
                            if term in line:
                                hits.append(f"{os.path.relpath(os.path.join(dirpath, fn), VAULT)}:{i}: {term}")
        self.assertEqual(hits, [], "retired machinery referenced on an executable surface:\n"
                         + "\n".join(hits[:12]))


class TestBugFixRegressions(unittest.TestCase):
    """Durable regressions for the four promoted bug fixes (2026-07-10)."""

    def test_secret_caught_in_frontmatterless_file(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            write_file(os.path.join(tmp, "00 Inbox", "raw.md"), 'password = "hunter2hunter2hunter2"\n', mode="w")
            from cmd import validate as v_mod
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            self.assertIn("secret", " ".join(rep.errors))

    def test_hosted_ineligible_notes_fully_absent_from_generated(self):
        """Audit-2 H-03: generated files are hosted-readable, so restricted,
        prohibited, local-only, AND private notes leave no id, filename,
        summary, hash, or relationship trace — not just a withheld summary."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            write_file(os.path.join(tmp, "20 Knowledge", "LEAKFILE-R.md"), NOTE.format(
                n=21, extra="classification: restricted\n", body="x").replace("summary: t21", "summary: LEAK-R-21"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "LEAKFILE-L.md"), NOTE.format(
                n=22, extra="classification: private\nai_use: local-only\n", body="x").replace("summary: t22", "summary: LEAK-L-22"), mode="w")
            write_file(os.path.join(tmp, "20 Knowledge", "LEAKFILE-P.md"), NOTE.format(
                n=23, extra="classification: private\n", body="x").replace("summary: t23", "summary: LEAK-P-23"), mode="w")
            # visible note pointing AT a hidden note: the hidden id must not
            # surface as a reverse-relationship key either
            write_file(os.path.join(tmp, "20 Knowledge", "V.md"), NOTE.format(
                n=24, extra="depends_on: [note-t22]\n", body="x"), mode="w")
            from cmd import generate as g_mod
            rep = Report("generate"); g_mod.run(tmp, Args(), rep)
            self.assertTrue(rep.ok, rep.errors)
            blob = ""
            gen = os.path.join(tmp, "System", "Generated")
            for f in os.listdir(gen):
                blob += read_file(os.path.join(gen, f), encoding="utf-8")
            for marker in ("note-t21", "LEAK-R-21", "note-t22", "LEAK-L-22",
                           "note-t23", "LEAK-P-23", "LEAKFILE"):
                self.assertNotIn(marker, blob, marker)
            self.assertIn("note-t24", blob)          # the visible note still indexed

    def test_activation_requires_existing_test_paths_and_flips_status(self):
        """Audit-2 M-06/M-02: a listed-but-nonexistent test path must block
        activation; a real one activates and verifiably flips status."""
        from cmd import scaffold as sc_mod
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            r = aios(tmp, "scaffold", "--type", "workflow", "--name", "act-probe")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            p = os.path.join(tmp, "System", "Workflows", "act-probe.md")
            text = read_file(p).replace("tests: []", "tests: [System/Tests/does-not-exist.md]")
            write_file(p, text, mode="w")
            rep = Report("register"); sc_mod.register(tmp, "workflow-act-probe", rep)
            self.assertFalse(rep.ok)
            self.assertIn("do not exist", " ".join(rep.errors))
            self.assertIn("status: draft", read_file(p))      # unchanged on refusal
            os.makedirs(os.path.join(tmp, "System", "Tests", "cases"), exist_ok=True)
            write_file(os.path.join(tmp, "System", "Tests", "cases", "act-probe-test.md"), "# test\n", mode="w")
            text = read_file(p).replace("tests: [System/Tests/does-not-exist.md]",
                                          "tests: [System/Tests/cases/act-probe-test.md]")
            write_file(p, text, mode="w")
            # delta-audit B-04: existing path alone is NOT enough — needs a recorded pass
            rep2 = Report("register"); sc_mod.register(tmp, "workflow-act-probe", rep2)
            self.assertFalse(rep2.ok)
            self.assertIn("no recorded test result", " ".join(rep2.errors))
            os.makedirs(os.path.join(tmp, "System", "Tests", "results"), exist_ok=True)
            write_file(os.path.join(tmp, "System", "Tests", "results", "workflow-act-probe.yaml"), "component: workflow-act-probe\nversion: 0.0.9\nresult: pass\n", mode="w")
            rep3 = Report("register"); sc_mod.register(tmp, "workflow-act-probe", rep3)
            self.assertFalse(rep3.ok, "version-mismatched result must not activate")
            write_file(os.path.join(tmp, "System", "Tests", "results", "workflow-act-probe.yaml"), "component: workflow-act-probe\nversion: 0.1.0\nresult: pass\ndate: 2026-07-10\n", mode="w")
            give_doc_coverage(tmp, "workflow-act-probe")  # DEC-051: activation now also requires docs
            rep4 = Report("register"); sc_mod.register(tmp, "workflow-act-probe", rep4)
            self.assertTrue(rep4.ok, rep4.errors)
            self.assertIn("status: active", read_file(p))     # really flipped

    def test_capability_end_to_end_lifecycle(self):
        """Release-audit H-03: every supported extension type must complete
        scaffold → test-record → activate. Workflow is covered above; this
        proves capability. Also: unsupported types are refused with guidance."""
        from cmd import scaffold as sc_mod
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            os.makedirs(os.path.join(tmp, "System", "Capabilities"), exist_ok=True)
            r = aios(tmp, "scaffold", "--type", "capability", "--name", "cap-probe")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            p = os.path.join(tmp, "System", "Capabilities", "cap-probe", "SKILL.md")
            os.makedirs(os.path.join(tmp, "System", "Tests", "cases"), exist_ok=True)
            write_file(os.path.join(tmp, "System", "Tests", "cases", "cap-probe-test.md"), "# t\n", mode="w")
            text = read_file(p).replace(
                "tests: []", "tests: [System/Tests/cases/cap-probe-test.md]")
            write_file(p, text, mode="w")
            os.makedirs(os.path.join(tmp, "System", "Tests", "results"), exist_ok=True)
            write_file(os.path.join(tmp, "System", "Tests", "results", "capability-cap-probe.yaml"), "component: capability-cap-probe\nversion: 0.1.0\nresult: pass\ndate: 2026-07-10\n", mode="w")
            give_doc_coverage(tmp, "capability-cap-probe")  # DEC-051: activation now also requires docs
            rep = Report("register"); sc_mod.register(tmp, "capability-cap-probe", rep)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("status: active", read_file(p))
            # unsupported types refuse with guidance instead of a dead-end path
            r2 = aios(tmp, "scaffold", "--type", "script", "--name", "nope")
            self.assertNotEqual(r2.returncode, 0)
            self.assertIn("developer lane", r2.stdout + r2.stderr)

    def test_scaffold_refuses_duplicates_single_file_model(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            r1 = aios(tmp, "scaffold", "--type", "workflow", "--name", "reg-test")
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            r2 = aios(tmp, "scaffold", "--type", "workflow", "--name", "reg-test")
            self.assertNotEqual(r2.returncode, 0)
            self.assertIn("already exists", r2.stdout + r2.stderr)
            # single-file model: the component IS the record — exactly one file
            self.assertTrue(os.path.exists(os.path.join(tmp, "System", "Workflows", "reg-test.md")))

    def test_invalid_subtype_rejected_and_duplicate_schema_keys_flagged(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = mini_vault(os.path.join(outer, "v"))
            write_file(os.path.join(tmp, "20 Knowledge", "S.md"), NOTE.format(n=23, extra="subtype: not-a-real-subtype\n", body="x"), mode="w")
            from cmd import validate as v_mod
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            self.assertIn("not in vocabulary", " ".join(rep.errors))
            # duplicate-key guard
            with open(os.path.join(tmp, "System", "Schemas", "note.yaml"), "a") as f:
                f.write("  status: {}\n")
            rep = Report("validate"); v_mod.run(tmp, Args(), rep)
            self.assertIn("duplicate key", " ".join(rep.errors))


CAP_SKILL = """---
id: capability-{name}
name: {name}
component_type: capability
type: capability
file_class: canonical
authority: canonical
canonical_for: capability-{name}
status: {status}
version: 0.1.0
summary: "Test capability."
description: "Does the test thing. Use when testing emission."
reads: [vault]
writes: [per-procedure]
permissions: [uses-vault-operations-only]
dependencies: [doc-runtime-kernel]
tests: []
documentation: self
created: 2026-07-16
updated: 2026-07-16
---

# Capability — {name}

1. Step one.
"""


class TestAgentSkillsEmission(unittest.TestCase):
    """DEC-070/071: `aios generate` projects every ACTIVE capability as a
    spec-valid Agent Skill under .claude/skills/aios-<name>/. Canonical keeps
    the superset frontmatter; the projection carries ONLY the spec's fields
    (extra top-level keys are a skills-ref validator ERROR, proven 2026-07-16),
    with AI OS extras stringified under `metadata`."""

    SPEC_FIELDS = {"name", "description", "license", "compatibility",
                   "metadata", "allowed-tools"}

    def _vault_with_cap(self, outer, name="cap-alpha", status="active"):
        tmp = mini_vault(os.path.join(outer, "v"))
        d = os.path.join(tmp, "System", "Capabilities", name)
        os.makedirs(d)
        write_file(os.path.join(d, "SKILL.md"), CAP_SKILL.format(name=name, status=status), mode="w")
        return tmp

    def _emit(self, tmp):
        from cmd import generate as g_mod
        rep = Report("generate"); g_mod.run(tmp, Args(), rep)
        self.assertTrue(rep.ok, rep.errors)
        return rep

    def _frontmatter(self, path):
        import yaml as _y
        return _y.safe_load(read_file(path, encoding="utf-8").split("---", 2)[1])

    def test_active_capability_emits_spec_valid_projection(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault_with_cap(outer)
            self._emit(tmp)
            sk = os.path.join(tmp, ".claude", "skills", "aios-cap-alpha", "SKILL.md")
            self.assertTrue(os.path.exists(sk))
            fm = self._frontmatter(sk)
            # spec fields ONLY at top level; name matches its directory
            self.assertTrue(set(fm) <= self.SPEC_FIELDS, sorted(set(fm) - self.SPEC_FIELDS))
            self.assertEqual(fm["name"], "aios-cap-alpha")
            self.assertIn("Use when", fm["description"])
            self.assertIn("aios CLI", fm["compatibility"])
            # AI OS extras ride under metadata as plain strings (never str(list))
            self.assertEqual(fm["metadata"]["aios-reads"], "vault")
            self.assertEqual(fm["metadata"]["aios-id"], "capability-cap-alpha")
            for v in fm["metadata"].values():
                self.assertIsInstance(v, str)
                self.assertNotIn("[", v)
            # the body says loudly that governance does not travel
            self.assertIn("not the OS", read_file(sk, encoding="utf-8"))

    def test_draft_capability_is_not_emitted(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault_with_cap(outer, status="draft")
            self._emit(tmp)
            self.assertFalse(os.path.exists(
                os.path.join(tmp, ".claude", "skills", "aios-cap-alpha")))

    def test_foreign_skill_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault_with_cap(outer)
            foreign = os.path.join(tmp, ".claude", "skills", "aios-cap-alpha")
            os.makedirs(foreign)
            write_file(os.path.join(foreign, "SKILL.md"), "---\nname: aios-cap-alpha\ndescription: user's own skill\n---\nMine.\n", mode="w")
            rep = self._emit(tmp)
            self.assertIn("Mine.", read_file(os.path.join(foreign, "SKILL.md")))
            self.assertTrue(any("not ours" in w for w in rep.warnings), rep.warnings)

    def test_stale_projection_is_removed_on_regenerate(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault_with_cap(outer)
            self._emit(tmp)
            gone = os.path.join(tmp, ".claude", "skills", "aios-cap-alpha")
            self.assertTrue(os.path.isdir(gone))
            shutil.rmtree(os.path.join(tmp, "System", "Capabilities", "cap-alpha"))
            self._emit(tmp)
            self.assertFalse(os.path.exists(gone),
                             "renamed/removed capability left a stale projection")


class TestDocPaths(unittest.TestCase):
    """doc-paths gate: backticked vault paths in prose must resolve. Backticks
    are exactly what `links` strips (code spans = literal text), so this gate
    covers the reference class every other checker ignores. Noise discipline:
    only always-committed System/ roots; placeholders, runtime-born dirs, and
    historical records exempt (the DEC-032 retired-for-noise lesson)."""

    def _vault(self, outer):
        tmp = mini_vault(os.path.join(outer, "v"))
        os.makedirs(os.path.join(tmp, "System", "Documentation"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "System", "Governance"), exist_ok=True)
        write_file(os.path.join(tmp, "System", "Governance", "Real Doc.md"), "---\nid: doc-real\ntype: system-doc\ncreated: 2026-07-16\n"
            "updated: 2026-07-16\nsummary: target\n---\nBody.\n", mode="w")
        return tmp

    def _run(self, tmp):
        from cmd import docpaths as dp_mod
        rep = Report("doc-paths"); dp_mod.run(tmp, Args(), rep)
        return rep

    def _doc(self, tmp, body, name="Guide.md", where=("System", "Documentation")):
        write_file(os.path.join(tmp, *where, name), "---\nid: doc-guide-%s\ntype: system-doc\ncreated: 2026-07-16\n"
            "updated: 2026-07-16\nsummary: t\n---\n%s\n" % (name.split(".")[0].lower(), body), mode="w")

    def test_resolving_path_passes_and_is_counted(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "See `System/Governance/Real Doc.md` for the rule.")
            rep = self._run(tmp)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(rep.info["path_references_checked"], 1)

    def test_dead_path_is_an_error(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "See `System/Governance/Gone Doc.md` for the rule.")
            rep = self._run(tmp)
            self.assertFalse(rep.ok)
            self.assertIn("Gone Doc.md", rep.errors[0])

    def test_dead_path_with_spaces_is_caught(self):
        # the real v1.22.0 escape had spaces in sibling citations; a tokenizer
        # that splits on whitespace would silently skip the whole class
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "Read `System/Governance/Privacy and Boundaries.md` first.")
            rep = self._run(tmp)
            self.assertFalse(rep.ok)

    def test_placeholders_and_unchecked_roots_are_ignored(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "Plans live in `System/Migrations/NNN-name/` as "
                           "`System/Capabilities/<name>/SKILL.md`; packs land in "
                           "`Packs/tool/`; caches in `System/Generated/x.json`; "
                           "globs like `System/Workflows/*.md` are shapes.")
            rep = self._run(tmp)
            self.assertTrue(rep.ok, rep.errors)
            self.assertEqual(rep.info["path_references_checked"], 0)

    def test_historical_records_are_exempt_but_migrations_readme_is_not(self):
        # docaudit's HIST exempts ALL of Migrations/; this gate must not — the
        # README there is a live doc (the gate's own origin bug). Numbered
        # migration record dirs stay exempt as dated evidence.
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            os.makedirs(os.path.join(tmp, "System", "Migrations", "001-old"))
            write_file(os.path.join(tmp, "System", "Migrations", "001-old", "notes.md"), "---\nid: doc-mig-notes\ntype: system-doc\ncreated: 2026-07-16\n"
                "updated: 2026-07-16\nsummary: t\n---\nMoved `System/Governance/Old Name.md`.\n", mode="w")
            write_file(os.path.join(tmp, "CHANGELOG.md"), "---\nid: doc-changelog-t\ntype: system-doc\ncreated: 2026-07-16\n"
                "updated: 2026-07-16\nsummary: t\n---\nWas `System/Governance/Old Name.md`.\n", mode="w")
            rep = self._run(tmp)
            self.assertTrue(rep.ok, rep.errors)   # both exempt: record dir + changelog
            os.makedirs(os.path.join(tmp, "System", "Migrations"), exist_ok=True)
            write_file(os.path.join(tmp, "System", "Migrations", "README.md"), "---\nid: doc-mig-readme\ntype: system-doc\ncreated: 2026-07-16\n"
                "updated: 2026-07-16\nsummary: t\n---\nProcedure: `System/Governance/Gone.md`.\n", mode="w")
            rep = self._run(tmp)
            self.assertFalse(rep.ok, "live Migrations README must NOT be exempt")

    def test_decision_register_paths_are_checked(self):
        """DEC-109 / GAP-8. The register used to be exempt WHOLESALE, which hid a
        real dead capability path in it for three releases. SEEDED FAILURE:
        passes (wrongly) against the pre-fix gate, which skipped the file."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "- **DEC-001** — See `System/Governance/Gone Doc.md`, diagram 39.",
                      name="Active Decisions.md", where=("System", "Governance"))
            rep = self._run(tmp)
            self.assertFalse(rep.ok, "a dead path in the decision register is still a dead path")
            self.assertTrue(any("Gone Doc.md" in e for e in rep.errors), rep.errors)

    def test_decision_register_count_claims_stay_doc_audits_business(self):
        """The narrowing is to PATHS only. A dated count in the register is still
        exempt — that exemption lives in `doc-audit`'s HIST_COUNTS and this gate
        never had an opinion about counts at all."""
        from cmd import docaudit as da_mod
        self.assertIn("Active Decisions.md", da_mod.HIST_COUNTS)
        from cmd import docpaths as dp_mod
        self.assertNotIn("Active Decisions.md", dp_mod.HIST_FILES)

    def test_a_path_recorded_as_removed_is_not_reported(self):
        """An entry whose job is to record a removal necessarily names a file
        that is gone; calling that 'stale — moved/renamed?' is a false positive
        about the one document that is telling the truth."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "- **DEC-002** — The Backlog (`System/Governance/Gone Doc.md`, "
                           "formerly canonical) is removed from the product master.",
                      name="Active Decisions.md", where=("System", "Governance"))
            rep = self._run(tmp)
            self.assertTrue(rep.ok, rep.errors)
            self.assertIn("paths_exempt_as_removed", rep.info)

    def test_the_removal_allowance_is_scoped_to_the_sentence(self):
        """A register entry is one 900-word line. A line-scoped window would let
        one 'is removed' anywhere in an entry exempt every path in it."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "- **DEC-003** — The Backlog (`System/Governance/Gone Doc.md`) is "
                           "removed from the product master. Procedure lives in "
                           "`System/Governance/Still Missing.md` and is unchanged.",
                      name="Active Decisions.md", where=("System", "Governance"))
            rep = self._run(tmp)
            self.assertFalse(rep.ok, "the second sentence's dead path must still fire")
            self.assertTrue(any("Still Missing.md" in e for e in rep.errors), rep.errors)
            self.assertFalse(any("Gone Doc.md" in e for e in rep.errors), rep.errors)

    def test_removal_allowance_does_not_leak_into_ordinary_docs(self):
        """Guard against the allowance becoming a way to silence any dead path
        by writing the word 'removed' near it in a live procedure."""
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "Step 4 removes the folder. Then read "
                           "`System/Governance/Gone Doc.md` for the rule.")
            rep = self._run(tmp)
            self.assertFalse(rep.ok, rep.errors)

    def test_composed_into_health(self):
        with tempfile.TemporaryDirectory() as outer:
            tmp = self._vault(outer)
            self._doc(tmp, "See `System/Governance/Gone Doc.md`.")
            from cmd import health as h_mod
            rep = Report("health"); h_mod.run(tmp, Args(), rep)
            self.assertIn("doc-paths", rep.info)
            self.assertTrue(any("doc-paths" in e for e in rep.errors),
                            "a dead path must fail health, or CI never sees it")


if __name__ == "__main__":
    unittest.main()
