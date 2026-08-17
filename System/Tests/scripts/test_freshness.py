"""Knowledge-freshness tests (SPEC-knowledge-freshness §9): hash normalization,
grandfathering baseline, ripple detection/disposition/re-change, horizon
stamping with epoch rules, workflow cadence, kill switch, rollback-clean skip,
and the 90-day no-nag acceptance. Run:
    python3 -m unittest System.Tests.scripts.test_freshness
"""
import datetime, os, sys, tempfile, shutil, unittest
from types import SimpleNamespace
from unittest import mock

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))
from lib import freshness as fr          # noqa: E402
from lib.report import Report            # noqa: E402
from cmd import ripple as ripple_cmd     # noqa: E402
from cmd import workflow as workflow_cmd # noqa: E402
from cmd import review_due as rd_cmd     # noqa: E402
from lib import safepaths                # noqa: E402


def _read_text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _args(**kw):
    base = dict(ack=None, from_id=None, effect=None, ack_all=False, baseline=None,
                baseline_all=False, ran=None, set_missing=False, json=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _note(root, relpath, nid, ntype="note", status="active", created="2026-07-01",
          body="body text", extra=""):
    p = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"---\nid: {nid}\ntype: {ntype}\nstatus: {status}\n"
                f"created: {created}\nupdated: {created}\nsummary: t\n{extra}---\n\n{body}\n")
    return p


def _vault(root, epoch="2026-06-01", writes=True):
    os.makedirs(os.path.join(root, "System", "Schemas"), exist_ok=True)
    os.makedirs(os.path.join(root, "System", "Registries"), exist_ok=True)
    for t in ("note", "entity", "source", "procedure"):
        with open(os.path.join(root, "System", "Schemas", f"{t}.yaml"), "w") as f:
            f.write(f"schema: {t}\nfields: {{}}\n")
    with open(os.path.join(root, "System", "Registries", "freshness.yaml"), "w") as f:
        f.write(f"enforced_since: {epoch}\n"
                "horizons_days: {note: 90, entity: 180, procedure: 365}\n"
                "exempt_types: [source]\n"
                "dispositions: [changes, contradicts, makes-stale, no-impact]\n")
    with open(os.path.join(root, "profile.yaml"), "w") as f:
        f.write("hosted: false\n"
                "may_process_private: true\n"
                "allowed_privacy_classifications: [public, internal, private]\n")
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "w") as f:
        f.write(f"runtime:\n  ai_writes_enabled: {str(writes).lower()}\n"
                f"  active_profile: profile.yaml\n"
                "protected_objects:\n"
                "  - SYSTEM-MANIFEST.yaml\n"
                "  - System/Agents/\n"
                "  - 80 User/privacy*\n")


class FreshnessBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _vault(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestHashing(FreshnessBase):
    def test_whitespace_and_line_endings_do_not_change_hash(self):
        a = fr.body_hash("line one\nline two\n")
        self.assertEqual(a, fr.body_hash("line one   \r\nline two\r\n\n"))
        self.assertNotEqual(a, fr.body_hash("line one\nline 2\n"))


class TestGrandfathering(FreshnessBase):
    def test_first_sight_baselines_silently(self):
        _note(self.tmp, "20 Knowledge/A.md", "note-a")
        ch, unseen = fr.changed(self.tmp)
        self.assertEqual((ch, len(unseen)), ([], 1))
        fr.ensure_baseline(self.tmp)
        ch, unseen = fr.changed(self.tmp)
        self.assertEqual((ch, unseen), ([], []))
        self.assertEqual(fr.pending(self.tmp), [])

    def test_ledger_loss_forgives(self):
        p = _note(self.tmp, "20 Knowledge/A.md", "note-a")
        fr.ensure_baseline(self.tmp)
        with open(p, "a") as f:
            f.write("changed\n")
        self.assertEqual(len(fr.changed(self.tmp)[0]), 1)
        os.remove(os.path.join(self.tmp, fr.LEDGER_REL))
        fr.ensure_baseline(self.tmp)
        self.assertEqual(fr.changed(self.tmp)[0], [])


class TestRipple(FreshnessBase):
    def setUp(self):
        super().setUp()
        self.a = _note(self.tmp, "20 Knowledge/Note A.md", "note-a", body="See [[Note B]].")
        _note(self.tmp, "20 Knowledge/Note B.md", "note-b")
        _note(self.tmp, "20 Knowledge/Note C.md", "note-c", extra="related: [note-a]\n")
        _note(self.tmp, "20 Knowledge/Note D.md", "note-d", status="draft",
              extra="related: [note-a]\n")   # drafts never become triage items
        fr.ensure_baseline(self.tmp)
        with open(self.a, "a") as f:
            f.write("\nnew fact\n")

    def pending_ids(self):
        return sorted(str(t.meta.get("id")) for _, t in fr.pending(self.tmp))

    def test_change_flags_link_and_backlink_neighbors_not_drafts(self):
        self.assertEqual(self.pending_ids(), ["note-b", "note-c"])

    def test_ack_clears_one_pair(self):
        rep = Report("ripple")
        ripple_cmd.run(self.tmp, _args(ack="note-b", from_id="note-a", effect="no-impact"), rep)
        self.assertTrue(rep.ok)
        self.assertEqual(self.pending_ids(), ["note-c"])

    def test_batch_ack_clears_all(self):
        ripple_cmd.run(self.tmp, _args(ack="x", ack_all=True, from_id="note-a",
                                       effect="no-impact"), Report("ripple"))
        self.assertEqual(self.pending_ids(), [])

    def test_makes_stale_sets_neighbor_status_only(self):
        body_before = _read_text(os.path.join(self.tmp, "20 Knowledge/Note B.md")).split("---")[-1]
        ripple_cmd.run(self.tmp, _args(ack="note-b", from_id="note-a", effect="makes-stale"),
                       Report("ripple"))
        text = _read_text(os.path.join(self.tmp, "20 Knowledge/Note B.md"))
        self.assertIn("status: stale", text)
        self.assertEqual(text.split("---")[-1], body_before)   # prose untouched

    def test_no_impact_ack_allows_read_only_evidence(self):
        target = os.path.join(self.tmp, "20 Knowledge/Note B.md")
        os.chmod(self.a, 0o444); os.chmod(target, 0o444)
        rep = Report("ripple")
        ripple_cmd.run(self.tmp, _args(ack="note-b", from_id="note-a",
                                       effect="no-impact"), rep)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(self.pending_ids(), ["note-c"])

    def test_makes_stale_refuses_read_only_target(self):
        target = os.path.join(self.tmp, "20 Knowledge/Note B.md")
        os.chmod(target, 0o444)
        rep = Report("ripple")
        ripple_cmd.run(self.tmp, _args(ack="note-b", from_id="note-a",
                                       effect="makes-stale"), rep)
        self.assertFalse(rep.ok)
        self.assertNotIn("status: stale", _read_text(target))

    def test_ack_and_stale_mark_roll_back_together(self):
        target = os.path.join(self.tmp, "20 Knowledge/Note B.md")
        before = _read_text(target)

        def fail(event, index, _target):
            if event == "after-output-commit" and index == 0:
                raise OSError("injected")

        rep = Report("ripple")
        with mock.patch.object(safepaths, "_mutation_boundary", side_effect=fail):
            ripple_cmd.run(self.tmp, _args(ack="note-b", from_id="note-a",
                                           effect="makes-stale"), rep)
        self.assertFalse(rep.ok)
        self.assertEqual(_read_text(target), before)
        self.assertFalse(os.path.lexists(os.path.join(self.tmp, fr.LOG_REL)))

    def test_corrupt_ledger_refuses_baseline_without_replacing_it(self):
        ledger = os.path.join(self.tmp, fr.LEDGER_REL)
        with open(ledger, "w", encoding="utf-8") as fh:
            fh.write("not json\n")
        rep = Report("ripple")
        ripple_cmd.run(self.tmp, _args(baseline="note-a"), rep)
        self.assertFalse(rep.ok)
        self.assertEqual(_read_text(ledger), "not json\n")

    def test_second_change_reopens_acked_pair(self):
        ripple_cmd.run(self.tmp, _args(ack="x", ack_all=True, from_id="note-a",
                                       effect="no-impact"), Report("ripple"))
        with open(self.a, "a") as f:
            f.write("changed again\n")
        self.assertEqual(self.pending_ids(), ["note-b", "note-c"])

    def test_baseline_accepts_and_clears(self):
        ripple_cmd.run(self.tmp, _args(baseline="note-a"), Report("ripple"))
        self.assertEqual(fr.changed(self.tmp)[0], [])
        self.assertEqual(fr.pending(self.tmp), [])

    def test_unknown_effect_rejected(self):
        rep = Report("ripple")
        ripple_cmd.run(self.tmp, _args(ack="note-b", from_id="note-a", effect="banana"), rep)
        self.assertFalse(rep.ok)

    def test_kill_switch_blocks_writes_allows_reads(self):
        _vault(self.tmp, writes=False)
        rep = Report("ripple")
        ripple_cmd.run(self.tmp, _args(ack="note-b", from_id="note-a", effect="no-impact"), rep)
        self.assertFalse(rep.ok)
        rep2 = Report("ripple")
        ripple_cmd.run(self.tmp, _args(), rep2)
        self.assertTrue(rep2.ok)

    def test_malformed_profile_fails_closed_without_note_ids(self):
        with open(os.path.join(self.tmp, "profile.yaml"), "w") as f:
            f.write("hosted: false\n"
                    "may_process_private: maybe\n"
                    "allowed_privacy_classifications: [public, internal, private]\n")
        rep = Report("ripple")
        ripple_cmd.run(self.tmp, _args(), rep)
        self.assertFalse(rep.ok)
        rendered = repr(rep.info) + repr(rep.errors) + repr(rep.warnings)
        for note_id in ("note-a", "note-b", "note-c", "note-d"):
            self.assertNotIn(note_id, rendered)


class TestHorizons(FreshnessBase):
    def test_post_epoch_active_flagged_grandfathered_and_exempt_not(self):
        _note(self.tmp, "20 Knowledge/new.md", "note-new", created="2026-07-10")
        _note(self.tmp, "20 Knowledge/old.md", "note-old", created="2026-01-01")
        _note(self.tmp, "30 Sources/s.md", "src-1", ntype="source", created="2026-07-10")
        _note(self.tmp, "00 Inbox/d.md", "note-draft", status="draft", created="2026-07-10")
        reg = fr.load_registry(self.tmp)
        ids = sorted(n.meta["id"] for n in fr.horizon_missing(self.tmp, reg))
        self.assertEqual(ids, ["note-new"])

    def test_set_missing_stamps_and_clears(self):
        _note(self.tmp, "20 Knowledge/new.md", "note-new", created="2026-07-10")
        rep = Report("review-due")
        rd_cmd.run(self.tmp, _args(set_missing=True), rep)
        self.assertTrue(rep.ok)
        text = _read_text(os.path.join(self.tmp, "20 Knowledge/new.md"))
        due = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
        self.assertIn(f"review_due: {due}", text)
        self.assertEqual(fr.horizon_missing(self.tmp, fr.load_registry(self.tmp)), [])

    def test_batch_stamp_rolls_back_every_note(self):
        paths = [_note(self.tmp, f"20 Knowledge/{name}.md", f"note-{name.lower()}",
                       created="2026-07-10") for name in ("A", "B")]
        before = [_read_text(path) for path in paths]

        def fail(event, index, _target):
            if event == "after-output-commit" and index == 0:
                raise OSError("injected")

        rep = Report("review-due")
        with mock.patch.object(safepaths, "_mutation_boundary", side_effect=fail):
            rd_cmd.run(self.tmp, _args(set_missing=True), rep)
        self.assertFalse(rep.ok)
        self.assertEqual([_read_text(path) for path in paths], before)

    def test_edited_grandfathered_note_reenters(self):
        p = _note(self.tmp, "20 Knowledge/old.md", "note-old", created="2026-01-01")
        fr.ensure_baseline(self.tmp)
        reg = fr.load_registry(self.tmp)
        self.assertEqual(fr.horizon_missing(self.tmp, reg), [])
        with open(p, "a") as f:
            f.write("rewritten\n")
        notes = fr.scan(self.tmp)
        fr.accept_baseline(self.tmp, notes["20 Knowledge/old.md"])
        ids = [n.meta["id"] for n in fr.horizon_missing(self.tmp, reg)]
        self.assertEqual(ids, ["note-old"])

    def test_no_nag_90_days_when_nothing_promoted(self):
        """Plan D5 acceptance: drafts and grandfathered content produce zero output."""
        _note(self.tmp, "00 Inbox/i.md", "note-i", status="draft", created="2026-07-10")
        _note(self.tmp, "20 Knowledge/old.md", "note-old", created="2026-01-01")
        fr.ensure_baseline(self.tmp)
        reg = fr.load_registry(self.tmp)
        self.assertEqual(fr.horizon_missing(self.tmp, reg), [])
        self.assertEqual(fr.pending(self.tmp), [])
        self.assertEqual([w for w in fr.workflow_status(self.tmp, reg) if w[3]], [])


class TestWorkflows(FreshnessBase):
    def _wf(self, cadence=True):
        extra = "cadence_days: 7\n" if cadence else ""
        p = os.path.join(self.tmp, "System", "Workflows", "wf.md")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(f"---\nid: workflow-test\ntype: workflow\nstatus: active\n"
                    f"created: 2026-06-01\nupdated: 2026-06-01\nsummary: t\n{extra}---\nsteps\n")

    def test_never_run_counts_from_epoch(self):
        self._wf()
        reg = fr.load_registry(self.tmp)   # epoch 2026-06-01, cadence 7 → overdue
        rows = fr.workflow_status(self.tmp, reg)
        self.assertEqual([(r[0], r[3]) for r in rows], [("workflow-test", True)])

    def test_ran_clears_and_uncadenced_ignored(self):
        self._wf()
        rep = Report("workflow")
        workflow_cmd.run(self.tmp, _args(ran="workflow-test"), rep)
        self.assertTrue(rep.ok)
        rows = fr.workflow_status(self.tmp, fr.load_registry(self.tmp))
        self.assertEqual([(r[0], r[3]) for r in rows], [("workflow-test", False)])
        self._wf(cadence=False)
        self.assertEqual(fr.workflow_status(self.tmp, fr.load_registry(self.tmp)), [])

    def test_unknown_workflow_rejected(self):
        rep = Report("workflow")
        workflow_cmd.run(self.tmp, _args(ran="workflow-nope"), rep)
        self.assertFalse(rep.ok)

    def test_malformed_log_refuses_append_without_replacing_it(self):
        self._wf()
        log = os.path.join(self.tmp, fr.LOG_REL)
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w", encoding="utf-8") as fh:
            fh.write("not json\n")
        rep = Report("workflow")
        workflow_cmd.run(self.tmp, _args(ran="workflow-test"), rep)
        self.assertFalse(rep.ok)
        self.assertEqual(_read_text(log), "not json\n")

    def test_concurrent_log_edit_is_preserved(self):
        self._wf()
        log = os.path.join(self.tmp, fr.LOG_REL)
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w", encoding="utf-8") as fh:
            fh.write('{"event":"workflow_run","id":"old","date":"2026-01-01"}\n')
        changed = False

        def race(event, _index, _target):
            nonlocal changed
            if event == "before-output-commit" and not changed:
                changed = True
                with open(log, "w", encoding="utf-8") as fh:
                    fh.write('{"event":"owner_edit"}\n')

        rep = Report("workflow")
        with mock.patch.object(safepaths, "_mutation_boundary", side_effect=race):
            workflow_cmd.run(self.tmp, _args(ran="workflow-test"), rep)
        self.assertFalse(rep.ok)
        self.assertEqual(_read_text(log),
                         '{"event":"owner_edit"}\n')


class TestRollbackClean(unittest.TestCase):
    def test_no_registry_means_quiet_skip(self):
        tmp = tempfile.mkdtemp()
        try:
            self.assertIsNone(fr.load_registry(tmp))
            rep = Report("ripple")
            ripple_cmd.run(tmp, _args(), rep)
            self.assertTrue(rep.ok and not rep.warnings)
            rep2 = Report("workflow")
            workflow_cmd.run(tmp, _args(), rep2)
            self.assertTrue(rep2.ok and not rep2.warnings)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
