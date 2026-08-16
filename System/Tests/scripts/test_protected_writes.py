"""Wave 5 ordinary-writer protection and live-policy proof contracts."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock


VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "System", "Scripts"))

from cmd import dedupebatch, review_due, ripple, scaffold  # noqa: E402
from lib import freshness as fr, protectedwrites, safepaths  # noqa: E402
from lib.report import Report  # noqa: E402


PARAGRAPH = "This paragraph has enough distinct words to participate in overlap measurement."


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(text)


def _bytes(path):
    with open(path, "rb") as stream:
        return stream.read()


def _text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _manifest(root, entries=None):
    entries = entries if entries is not None else [
        "SYSTEM-MANIFEST.yaml", "System/Agents/", "80 User/privacy*",
    ]
    body = "runtime:\n  ai_writes_enabled: true\nprotected_objects:\n"
    body += "".join(f"  - {entry}\n" for entry in entries)
    _write(os.path.join(root, "SYSTEM-MANIFEST.yaml"), body)


def _note(rid, *, approval=None):
    approval_line = f"approval: {approval}\n" if approval else ""
    return (
        "---\n"
        f"id: {rid}\ntype: note\nstatus: active\n{approval_line}"
        "created: 2026-08-01\nupdated: 2026-08-01\n---\n\n"
        f"{PARAGRAPH}\n"
    )


def _args(**values):
    defaults = dict(
        ack=None, ack_all=False, baseline=None, baseline_all=False,
        effect=None, from_id=None, refs=None, set_missing=False,
    )
    defaults.update(values)
    return SimpleNamespace(**defaults)


class LivePolicyProofTests(unittest.TestCase):
    def test_symlinked_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            external = os.path.join(outside, "manifest.yaml")
            _write(external, "protected_objects:\n  - SYSTEM-MANIFEST.yaml\n")
            os.symlink(external, os.path.join(root, "SYSTEM-MANIFEST.yaml"))
            before = _bytes(external)
            with self.assertRaises(protectedwrites.ProtectedTargetError):
                protectedwrites.protection_proof(root)
            self.assertEqual(_bytes(external), before)

    def test_missing_empty_and_malformed_policy_refuse_without_fallback(self):
        cases = (
            None,
            "runtime:\n  ai_writes_enabled: true\n",
            "protected_objects: []\n",
            "protected_objects: nope\n",
            "protected_objects:\n  - {not: a-string}\n",
            "protected_objects: [\n",
        )
        for body in cases:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as root:
                if body is not None:
                    _write(os.path.join(root, "SYSTEM-MANIFEST.yaml"), body)
                with self.assertRaises(protectedwrites.ProtectedTargetError):
                    protectedwrites.protection_proof(root)

    def test_manifest_change_at_commit_refuses_whole_annotation_batch(self):
        with tempfile.TemporaryDirectory() as root:
            _manifest(root)
            first = os.path.join(root, "00 Inbox", "first.md")
            second = os.path.join(root, "00 Inbox", "second.md")
            _write(first, _note("note-first"))
            _write(second, _note("note-second"))
            before = {first: _bytes(first), second: _bytes(second)}
            changed = False
            original = safepaths._mutation_boundary

            def race(event, index, target):
                nonlocal changed
                if event == "before-commit" and not changed:
                    changed = True
                    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), "a",
                              encoding="utf-8") as stream:
                        stream.write("# concurrent owner edit\n")
                return original(event, index, target)

            rep = Report("dedupe-batch")
            with mock.patch.object(safepaths, "_mutation_boundary", side_effect=race):
                dedupebatch.run(
                    root,
                    SimpleNamespace(target=f"{first},{second}", annotate=True),
                    rep,
                )
            self.assertFalse(rep.ok)
            self.assertEqual(_bytes(first), before[first])
            self.assertEqual(_bytes(second), before[second])
            self.assertFalse(any(name.startswith(".aios-output-") for name in os.listdir(root)))


class OrdinaryWriterProtectionTests(unittest.TestCase):
    def test_dedupe_refuses_protected_member_and_preserves_entire_batch(self):
        with tempfile.TemporaryDirectory() as root:
            _manifest(root)
            protected = os.path.join(root, "80 User", "privacy-rules.md")
            ordinary = os.path.join(root, "00 Inbox", "ordinary.md")
            _write(protected, _note("note-private-rules"))
            _write(ordinary, _note("note-ordinary"))
            before = {p: _bytes(p) for p in (protected, ordinary)}
            rep = Report("dedupe-batch")
            dedupebatch.run(
                root,
                SimpleNamespace(target=f"{protected},{ordinary}", annotate=True),
                rep,
            )
            self.assertFalse(rep.ok)
            for path, content in before.items():
                self.assertEqual(_bytes(path), content)

    def test_dedupe_refuses_approved_record_and_preserves_entire_batch(self):
        with tempfile.TemporaryDirectory() as root:
            _manifest(root)
            approved = os.path.join(root, "00 Inbox", "approved.md")
            ordinary = os.path.join(root, "00 Inbox", "ordinary.md")
            _write(approved, _note("note-approved", approval="approved"))
            _write(ordinary, _note("note-ordinary"))
            before = {p: _bytes(p) for p in (approved, ordinary)}
            rep = Report("dedupe-batch")
            dedupebatch.run(
                root,
                SimpleNamespace(target=f"{approved},{ordinary}", annotate=True),
                rep,
            )
            self.assertFalse(rep.ok)
            self.assertIn("approval: approved", " ".join(rep.errors))
            for path, content in before.items():
                self.assertEqual(_bytes(path), content)

    def _review_due(self, relpath, text):
        root = tempfile.mkdtemp(prefix="aios-protected-review-")
        self.addCleanup(shutil.rmtree, root, True)
        _manifest(root)
        path = os.path.join(root, *relpath.split("/"))
        _write(path, text)
        note = SimpleNamespace(
            path=path, relpath=relpath,
            meta={"id": "note-review", "type": "note", "status": "active"},
        )
        reg = {"enforced_since": "2026-01-01", "horizons_days": {"note": 30}}
        rep = Report("review-due")
        with mock.patch.object(fr, "load_registry", return_value=reg), \
                mock.patch.object(fr, "horizon_missing", return_value=[note]):
            review_due.run(root, _args(set_missing=True), rep)
        return path, rep

    def test_review_due_refuses_protected_privacy_note(self):
        path, rep = self._review_due("80 User/privacy-rules.md", _note("note-review"))
        self.assertFalse(rep.ok)
        self.assertEqual(_text(path), _note("note-review"))

    def test_review_due_refuses_approved_note(self):
        text = _note("note-review", approval="approved")
        path, rep = self._review_due("20 Knowledge/approved.md", text)
        self.assertFalse(rep.ok)
        self.assertEqual(_text(path), text)

    def _ripple_fixture(self, target_rel, target_text):
        root = tempfile.mkdtemp(prefix="aios-protected-ripple-")
        self.addCleanup(shutil.rmtree, root, True)
        _manifest(root)
        src_rel = "20 Knowledge/source.md"
        src_path = os.path.join(root, *src_rel.split("/"))
        target_path = os.path.join(root, *target_rel.split("/"))
        _write(src_path, _note("note-source"))
        _write(target_path, target_text)
        src = SimpleNamespace(
            path=src_path, relpath=src_rel,
            meta={"id": "note-source", "type": "note", "status": "active"},
        )
        target = SimpleNamespace(
            path=target_path, relpath=target_rel,
            meta={"id": "note-target", "type": "note", "status": "active"},
        )
        notes = {src_rel: src, target_rel: target}
        reg = {"dispositions": ["no-impact", "makes-stale"]}
        return root, src, target, notes, reg

    def test_ripple_refuses_protected_participant_in_ack_and_baseline_modes(self):
        for mode in ("ack", "baseline"):
            with self.subTest(mode=mode):
                root, src, target, notes, reg = self._ripple_fixture(
                    "80 User/privacy-rules.md", _note("note-target")
                )
                before = _bytes(target.path)
                rep = Report("ripple")
                args = (_args(ack="note-target", from_id="note-source", effect="no-impact")
                        if mode == "ack" else _args(baseline="note-source"))
                with mock.patch.object(fr, "load_registry", return_value=reg), \
                        mock.patch.object(fr, "scan", return_value=notes), \
                        mock.patch.object(fr, "pending", return_value=[(src, target)]):
                    ripple.run(root, args, rep)
                self.assertFalse(rep.ok)
                self.assertEqual(_bytes(target.path), before)
                self.assertFalse(os.path.lexists(os.path.join(root, fr.LOG_REL)))
                self.assertFalse(os.path.lexists(os.path.join(root, fr.LEDGER_REL)))

    def test_ripple_refuses_approved_participant(self):
        root, src, target, notes, reg = self._ripple_fixture(
            "20 Knowledge/approved.md", _note("note-target", approval="approved")
        )
        before = _bytes(target.path)
        rep = Report("ripple")
        with mock.patch.object(fr, "load_registry", return_value=reg), \
                mock.patch.object(fr, "scan", return_value=notes), \
                mock.patch.object(fr, "pending", return_value=[(src, target)]):
            ripple.run(
                root,
                _args(ack="note-target", from_id="note-source", effect="makes-stale"),
                rep,
            )
        self.assertFalse(rep.ok)
        self.assertEqual(_bytes(target.path), before)
        self.assertFalse(os.path.lexists(os.path.join(root, fr.LOG_REL)))

    def test_scaffold_register_denies_agent_contract_before_evidence_use(self):
        with tempfile.TemporaryDirectory() as root:
            _manifest(root)
            agent = os.path.join(root, "System", "Agents", "demo", "AGENT.md")
            text = (
                "---\nid: agent-demo\ntype: agent\nstatus: draft\nversion: 0.1.0\n"
                "tests: [System/Tests/scripts/test-demo.py]\n---\n\n# Demo\n"
            )
            _write(agent, text)
            _write(os.path.join(root, "System", "Tests", "scripts", "test-demo.py"),
                   "# passing test\n")
            _write(os.path.join(root, "System", "Tests", "results", "agent-demo.yaml"),
                   "component: agent-demo\nversion: 0.1.0\nresult: pass\n")
            rep = Report("scaffold")
            scaffold.register(root, "agent-demo", rep)
            self.assertFalse(rep.ok)
            self.assertIn("cannot be activated through scaffold", " ".join(rep.errors))
            self.assertEqual(_text(agent), text)


if __name__ == "__main__":
    unittest.main()
