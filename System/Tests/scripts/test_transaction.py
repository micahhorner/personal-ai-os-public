"""Disposable destructive tests for the durable directory transaction primitive."""
from __future__ import annotations

import json
import hashlib
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


VAULT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(VAULT / "System" / "Scripts"))
from lib import transaction as tx  # noqa: E402


def _tree(path: Path, text: str) -> Path:
    path.mkdir()
    (path / "identity.txt").write_text(text, encoding="utf-8")
    return path


def _content_identity(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


class TransactionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.parent = Path(self.temp.name).resolve()
        self.live = _tree(self.parent / "Vault Ω", "old")
        self.candidate = _tree(self.parent / "Candidate Ω", "new")
        self.journal = self.parent / "swap journal.json"

    def tearDown(self):
        self.temp.cleanup()

    def state(self):
        return json.loads(self.journal.read_text(encoding="utf-8"))


class TestCommitSwap(TransactionCase):
    def test_commit_preserves_previous_and_emits_stable_boundaries(self):
        calls = []

        def boundary(name, phase, root):
            calls.append((name, phase, root))

        result = tx.commit_swap(
            self.live, self.candidate, self.journal, boundary=boundary
        )
        self.assertEqual(result["status"], "committed")
        self.assertEqual((self.live / "identity.txt").read_text(), "new")
        previous = Path(result["previous"])
        self.assertEqual((previous / "identity.txt").read_text(), "old")
        self.assertEqual(previous, self.candidate)
        self.assertTrue(self.candidate.exists())
        self.assertEqual(self.state()["state"], "committed")
        self.assertEqual(
            calls,
            [
                ("commit-swap", "before", self.live),
                ("commit-swap", "after", self.live),
            ],
        )

    def test_prepare_is_durable_nonmutating_and_idempotent(self):
        first = tx.prepare_swap(self.live, self.candidate, self.journal)
        second = tx.prepare_swap(self.live, self.candidate, self.journal)
        self.assertEqual(first["transaction_id"], second["transaction_id"])
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "prepared")
        self.assertGreaterEqual(self.state()["sequence"], 1)

    def test_before_boundary_exception_rolls_back_everything(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)

        def boundary(name, phase, root):
            if (name, phase) == ("commit-swap", "before"):
                raise RuntimeError("fault before swap")

        with self.assertRaisesRegex(RuntimeError, "fault before"):
            tx.commit_swap(
                self.live, self.candidate, self.journal, boundary=boundary
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_after_boundary_exception_rolls_back_even_after_commit_record(self):
        def boundary(name, phase, root):
            if (name, phase) == ("commit-swap", "after"):
                raise RuntimeError("fault after swap")

        with self.assertRaisesRegex(RuntimeError, "fault after"):
            tx.commit_swap(
                self.live, self.candidate, self.journal, boundary=boundary
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_exchange_syscall_failure_leaves_old_live_untouched(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        with mock.patch.object(
            tx, "_atomic_exchange", side_effect=OSError("simulated exchange failure")
        ):
            with self.assertRaisesRegex(OSError, "simulated"):
                tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_journal_failure_after_exchange_still_restores_live_first(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        real_write = tx._write_journal
        failed = [False]

        def fail_once(path, record):
            if record["state"] == "exchanged" and not failed[0]:
                failed[0] = True
                raise OSError("journal unavailable")
            return real_write(path, record)

        with mock.patch.object(tx, "_write_journal", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "journal unavailable"):
                tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_fsync_failure_after_rename_still_restores_live(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        real_fsync = tx._fsync_dir
        failed = [False]

        def fail_once(path):
            if not failed[0]:
                failed[0] = True
                raise OSError("fsync unavailable")
            return real_fsync(path)

        with mock.patch.object(tx, "_fsync_dir", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "fsync unavailable"):
                tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")

    def test_default_transaction_boundary_is_a_patchable_exact_seam(self):
        with mock.patch.object(tx, "_transaction_boundary") as boundary:
            tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual(
            boundary.call_args_list,
            [
                mock.call("commit-swap", "before", self.live),
                mock.call("commit-swap", "after", self.live),
            ],
        )

    def test_committed_rerun_is_an_idempotent_noop(self):
        first = tx.commit_swap(self.live, self.candidate, self.journal)
        previous = Path(first["previous"])
        second = tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual(second["status"], "already-committed")
        self.assertEqual((self.live / "identity.txt").read_text(), "new")
        self.assertEqual((previous / "identity.txt").read_text(), "old")


class TestCrashResume(TransactionCase):
    def test_resume_after_exchange_finishes_commit(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        tx._atomic_exchange(self.live, self.candidate)

        result = tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual(result["status"], "committed")
        self.assertEqual((self.live / "identity.txt").read_text(), "new")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "old")

    def test_resume_after_exchange_state_record_is_idempotent(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        tx._atomic_exchange(self.live, self.candidate)
        record = self.state()
        record["state"] = "exchanged"
        tx._write_journal(self.journal, record)

        result = tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual(result["status"], "committed")
        self.assertEqual((self.live / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "committed")

    def test_resume_rolling_back_finishes_rollback(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        tx._atomic_exchange(self.live, self.candidate)
        record = self.state()
        record["state"] = "rolling-back"
        tx._write_journal(self.journal, record)

        result = tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual(result["status"], "rolled-back")
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")

    @unittest.skipUnless(
        sys.platform == "darwin" or sys.platform.startswith("linux"),
        "atomic directory exchange is macOS/Linux only",
    )
    def test_sigkill_immediately_after_exchange_never_removes_live_path(self):
        (self.live / "old-only.txt").write_text("old-only")
        (self.candidate / "new-only.txt").write_text("new-only")
        tx.prepare_swap(self.live, self.candidate, self.journal)
        scripts = str(VAULT / "System" / "Scripts")
        program = (
            "import os,signal,sys\n"
            f"sys.path.insert(0, {scripts!r})\n"
            "from lib import transaction as tx\n"
            "tx._exchange_completed=lambda root: os.kill(os.getpid(), signal.SIGKILL)\n"
            f"tx.commit_swap({str(self.live)!r}, {str(self.candidate)!r}, "
            f"{str(self.journal)!r})\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", program], cwd=str(self.parent)
        )
        returncode = process.wait(timeout=10)
        self.assertEqual(returncode, -signal.SIGKILL)
        self.assertTrue(self.live.is_dir(), "canonical live path may never be absent")
        observed = {path.name: path.read_text() for path in self.live.iterdir()}
        old = {"identity.txt": "old", "old-only.txt": "old-only"}
        new = {"identity.txt": "new", "new-only.txt": "new-only"}
        self.assertIn(observed, (old, new), "canonical tree must be exact old or new")
        resumed = tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual(resumed["status"], "committed")
        again = tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual(again["status"], "already-committed")

    def test_unrecognized_layout_fails_closed(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        foreign = self.parent / "foreign"
        os.rename(self.live, foreign)
        _tree(self.live, "impostor")
        with self.assertRaisesRegex(tx.TransactionError, "recoverable layout"):
            tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual((foreign / "identity.txt").read_text(), "old")
        self.assertEqual((self.live / "identity.txt").read_text(), "impostor")


class TestPublicRollback(TransactionCase):
    def test_committed_post_validation_failure_restores_old_and_retains_new(self):
        tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual((self.live / "identity.txt").read_text(), "new")

        result = tx.rollback_swap(self.live, self.candidate, self.journal)

        self.assertEqual(result["status"], "rolled-back")
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_rollback_resumes_crash_after_exchange_with_prepared_journal(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        tx._atomic_exchange(self.live, self.candidate)
        self.assertEqual(self.state()["state"], "prepared")

        result = tx.rollback_swap(self.live, self.candidate, self.journal)

        self.assertEqual(result["status"], "rolled-back")
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")

    def test_rollback_resumes_durable_exchanged_and_rolling_back_states(self):
        for state in ("exchanged", "rolling-back"):
            with self.subTest(state=state):
                with tempfile.TemporaryDirectory() as outer:
                    live = _tree(Path(outer) / "live", "old")
                    candidate = _tree(Path(outer) / "candidate", "new")
                    journal = Path(outer) / "journal.json"
                    tx.prepare_swap(live, candidate, journal)
                    tx._atomic_exchange(live, candidate)
                    record = json.loads(journal.read_text())
                    record["state"] = state
                    tx._write_journal(journal, record)
                    result = tx.rollback_swap(live, candidate, journal)
                    self.assertEqual(result["status"], "rolled-back")
                    self.assertEqual((live / "identity.txt").read_text(), "old")
                    self.assertEqual((candidate / "identity.txt").read_text(), "new")

    def test_repeated_rollback_is_idempotent(self):
        tx.commit_swap(self.live, self.candidate, self.journal)
        first = tx.rollback_swap(self.live, self.candidate, self.journal)
        second = tx.rollback_swap(self.live, self.candidate, self.journal)
        self.assertEqual(first["status"], "rolled-back")
        self.assertEqual(second["status"], "already-rolled-back")
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")

    def test_rollback_boundary_uses_exact_commit_swap_before_after(self):
        tx.commit_swap(self.live, self.candidate, self.journal)
        calls = []
        tx.rollback_swap(
            self.live,
            self.candidate,
            self.journal,
            boundary=lambda name, phase, root: calls.append((name, phase, root)),
        )
        self.assertEqual(
            calls,
            [
                ("commit-swap", "before", self.live),
                ("commit-swap", "after", self.live),
            ],
        )

    def test_boundary_failures_never_reverse_a_completed_restoration(self):
        tx.commit_swap(self.live, self.candidate, self.journal)

        def fail_before(name, phase, root):
            if phase == "before":
                raise RuntimeError("before rollback")

        with self.assertRaisesRegex(RuntimeError, "before rollback"):
            tx.rollback_swap(
                self.live, self.candidate, self.journal, boundary=fail_before
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "committed")

        def fail_after(name, phase, root):
            if phase == "after":
                raise RuntimeError("after rollback")

        with self.assertRaisesRegex(RuntimeError, "after rollback"):
            tx.rollback_swap(
                self.live, self.candidate, self.journal, boundary=fail_after
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_rollback_refuses_cleanup_and_ambiguous_layouts(self):
        tx.commit_swap(self.live, self.candidate, self.journal)
        tx.cleanup_swap(self.live, self.candidate, self.journal, confirm=True)
        with self.assertRaisesRegex(tx.TransactionError, "cleanup boundary"):
            tx.rollback_swap(self.live, self.candidate, self.journal)

        with tempfile.TemporaryDirectory() as outer:
            live = _tree(Path(outer) / "live", "old")
            candidate = _tree(Path(outer) / "candidate", "new")
            journal = Path(outer) / "journal.json"
            tx.prepare_swap(live, candidate, journal)
            displaced = Path(outer) / "displaced"
            os.rename(live, displaced)
            _tree(live, "impostor")
            with self.assertRaisesRegex(tx.TransactionError, "recoverable layout"):
                tx.rollback_swap(live, candidate, journal)
            self.assertEqual((live / "identity.txt").read_text(), "impostor")


class TestContentIdentityBinding(TransactionCase):
    def test_recovery_context_is_durable_strict_and_idempotent(self):
        context = {
            "schema": "test-recovery-v1",
            "proof": {"hash": "a" * 64, "paths": ["LICENSE.md"]},
        }
        first = tx.prepare_swap(
            self.live, self.candidate, self.journal, context=context
        )
        self.assertEqual(first["context"], context)
        second = tx.prepare_swap(
            self.live, self.candidate, self.journal, context=context
        )
        self.assertEqual(second["context"], context)
        with self.assertRaisesRegex(tx.TransactionError, "context does not match"):
            tx.prepare_swap(
                self.live, self.candidate, self.journal,
                context={"schema": "different"},
            )

    def test_recovery_context_rejects_non_json_values(self):
        with self.assertRaisesRegex(tx.TransactionError, "non-JSON"):
            tx.prepare_swap(
                self.live, self.candidate, self.journal,
                context={"bad": {"set"}},
            )
        self.assertFalse(self.journal.exists())

    def prepare_bound(self):
        self.original_hash = _content_identity(self.live)
        self.candidate_hash = _content_identity(self.candidate)
        return tx.prepare_swap(
            self.live,
            self.candidate,
            self.journal,
            original_content_identity=self.original_hash,
            candidate_content_identity=self.candidate_hash,
        )

    def test_identities_are_strict_both_or_neither_sha256(self):
        with self.assertRaisesRegex(tx.TransactionError, "supplied together"):
            tx.prepare_swap(
                self.live,
                self.candidate,
                self.journal,
                original_content_identity="0" * 64,
            )
        with self.assertRaisesRegex(tx.TransactionError, "lowercase SHA-256"):
            tx.prepare_swap(
                self.live,
                self.candidate,
                self.journal,
                original_content_identity="A" * 64,
                candidate_content_identity="b" * 64,
            )
        self.assertFalse(self.journal.exists())

    def test_content_callback_is_mandatory_for_bound_transaction(self):
        self.prepare_bound()
        with self.assertRaisesRegex(tx.TransactionError, "callback is required"):
            tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")

    def test_candidate_mutation_inside_before_boundary_fails_before_exchange(self):
        self.prepare_bound()

        def mutate(name, phase, root):
            if phase == "before":
                (self.candidate / "identity.txt").write_text("tampered")

        with self.assertRaisesRegex(tx.TransactionError, "candidate content identity"):
            tx.commit_swap(
                self.live,
                self.candidate,
                self.journal,
                boundary=mutate,
                content_identity=_content_identity,
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "tampered")
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_live_mutation_inside_before_boundary_is_detected_not_mislabeled(self):
        self.prepare_bound()

        def mutate(name, phase, root):
            if phase == "before":
                (self.live / "identity.txt").write_text("tampered-old")

        with self.assertRaisesRegex(
            tx.TransactionError, "automatic rollback failed"
        ):
            tx.commit_swap(
                self.live,
                self.candidate,
                self.journal,
                boundary=mutate,
                content_identity=_content_identity,
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "tampered-old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")
        self.assertNotEqual(self.state()["state"], "rolled-back")

    def test_crash_resume_reproves_content_before_commit(self):
        self.prepare_bound()
        tx._atomic_exchange(self.live, self.candidate)
        result = tx.commit_swap(
            self.live,
            self.candidate,
            self.journal,
            content_identity=_content_identity,
        )
        self.assertEqual(result["status"], "committed")
        again = tx.commit_swap(
            self.live,
            self.candidate,
            self.journal,
            content_identity=_content_identity,
        )
        self.assertEqual(again["status"], "already-committed")

    def test_crash_resume_mismatch_rolls_back_to_proven_old(self):
        self.prepare_bound()
        tx._atomic_exchange(self.live, self.candidate)
        (self.live / "identity.txt").write_text("corrupt-new")
        with self.assertRaisesRegex(tx.TransactionError, "candidate content identity"):
            tx.commit_swap(
                self.live,
                self.candidate,
                self.journal,
                content_identity=_content_identity,
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "corrupt-new")
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_committed_rerun_mismatch_automatically_restores_old(self):
        self.prepare_bound()
        tx.commit_swap(
            self.live,
            self.candidate,
            self.journal,
            content_identity=_content_identity,
        )
        (self.live / "identity.txt").write_text("changed-after-commit")
        with self.assertRaisesRegex(tx.TransactionError, "candidate content identity"):
            tx.commit_swap(
                self.live,
                self.candidate,
                self.journal,
                content_identity=_content_identity,
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual(
            (self.candidate / "identity.txt").read_text(), "changed-after-commit"
        )
        self.assertEqual(self.state()["state"], "rolled-back")

    def test_journal_identity_tamper_is_refused(self):
        self.prepare_bound()
        record = self.state()
        record["candidate_content_identity"] = "NOT-A-HASH"
        self.journal.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(tx.TransactionError, "lowercase SHA-256"):
            tx.commit_swap(
                self.live,
                self.candidate,
                self.journal,
                content_identity=_content_identity,
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "old")

    def test_valid_but_false_journal_identity_fails_closed(self):
        self.prepare_bound()
        record = self.state()
        record["candidate_content_identity"] = "0" * 64
        tx._write_journal(self.journal, record)
        with self.assertRaisesRegex(tx.TransactionError, "candidate content identity"):
            tx.commit_swap(
                self.live,
                self.candidate,
                self.journal,
                content_identity=_content_identity,
            )
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")

    def test_rolled_back_cleanup_refuses_changed_failed_candidate(self):
        self.prepare_bound()
        tx.commit_swap(
            self.live,
            self.candidate,
            self.journal,
            content_identity=_content_identity,
        )
        tx.rollback_swap(
            self.live,
            self.candidate,
            self.journal,
            content_identity=_content_identity,
        )
        (self.candidate / "identity.txt").write_text("changed failed candidate")
        with self.assertRaisesRegex(tx.TransactionError, "candidate content identity"):
            tx.cleanup_swap(
                self.live,
                self.candidate,
                self.journal,
                confirm=True,
                content_identity=_content_identity,
            )
        self.assertTrue(self.candidate.exists())
        self.assertNotEqual(self.state()["state"], "cleanup")

    def test_cleanup_resume_reproves_target_and_preserves_new_bytes(self):
        self.prepare_bound()
        tx.commit_swap(
            self.live,
            self.candidate,
            self.journal,
            content_identity=_content_identity,
        )

        def interrupt_before_delete(name, phase, root):
            if (name, phase) == ("cleanup", "before"):
                raise RuntimeError("cleanup interrupted")

        with self.assertRaisesRegex(RuntimeError, "cleanup interrupted"):
            tx.cleanup_swap(
                self.live,
                self.candidate,
                self.journal,
                confirm=True,
                boundary=interrupt_before_delete,
                content_identity=_content_identity,
            )
        self.assertEqual(self.state()["state"], "cleanup")
        added = self.candidate / "arrived-after-authorization.txt"
        added.write_text("preserve me")

        with self.assertRaisesRegex(tx.TransactionError, "original content identity"):
            tx.cleanup_swap(
                self.live,
                self.candidate,
                self.journal,
                confirm=True,
                content_identity=_content_identity,
            )
        self.assertTrue(self.candidate.is_dir())
        self.assertEqual(added.read_text(), "preserve me")
        self.assertEqual(self.state()["state"], "cleanup")


class TestCleanupBoundary(TransactionCase):
    def test_cleanup_requires_confirmation_and_is_idempotent(self):
        committed = tx.commit_swap(self.live, self.candidate, self.journal)
        previous = Path(committed["previous"])
        with self.assertRaisesRegex(tx.TransactionError, "confirm=True"):
            tx.cleanup_swap(self.live, self.candidate, self.journal)
        self.assertTrue(previous.exists())
        result = tx.cleanup_swap(
            self.live, self.candidate, self.journal, confirm=True
        )
        self.assertEqual(result["status"], "cleaned")
        self.assertFalse(previous.exists())
        self.assertTrue(self.journal.exists(), "durable cleanup tombstone remains")
        again = tx.cleanup_swap(
            self.live, self.candidate, self.journal, confirm=True
        )
        self.assertEqual(again["status"], "already-cleaned")

    def test_rolled_back_cleanup_discards_candidate_not_live(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)

        def boundary(name, phase, root):
            raise RuntimeError("abort")

        with self.assertRaises(RuntimeError):
            tx.commit_swap(
                self.live, self.candidate, self.journal, boundary=boundary
            )
        tx.cleanup_swap(self.live, self.candidate, self.journal, confirm=True)
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertFalse(self.candidate.exists())

    def test_cleanup_boundaries_have_exact_standard_names(self):
        calls = []
        tx.commit_swap(self.live, self.candidate, self.journal)
        tx.cleanup_swap(
            self.live,
            self.candidate,
            self.journal,
            confirm=True,
            boundary=lambda name, phase, root: calls.append((name, phase, root)),
        )
        self.assertEqual(
            calls,
            [
                ("cleanup", "before", self.live),
                ("cleanup", "after", self.live),
            ],
        )

    def test_partial_cleanup_is_resumable(self):
        committed = tx.commit_swap(self.live, self.candidate, self.journal)
        previous = Path(committed["previous"])
        (previous / "extra.txt").write_text("extra")
        real_remove = tx._remove_tree

        def partial(path):
            (path / "extra.txt").unlink()
            raise OSError("cleanup interrupted")

        with mock.patch.object(tx, "_remove_tree", side_effect=partial):
            with self.assertRaisesRegex(OSError, "interrupted"):
                tx.cleanup_swap(
                    self.live, self.candidate, self.journal, confirm=True
                )
        self.assertEqual(self.state()["state"], "cleanup")
        tx.cleanup_swap(self.live, self.candidate, self.journal, confirm=True)
        self.assertFalse(previous.exists())
        self.assertEqual(self.state()["state"], "cleaned")

    def test_cleanup_never_deletes_a_replaced_target(self):
        committed = tx.commit_swap(self.live, self.candidate, self.journal)
        previous = Path(committed["previous"])

        def stop_before_delete(name, phase, root):
            if phase == "before":
                raise RuntimeError("stop")

        with self.assertRaises(RuntimeError):
            tx.cleanup_swap(
                self.live,
                self.candidate,
                self.journal,
                confirm=True,
                boundary=stop_before_delete,
            )
        displaced = previous.with_name(previous.name + ".displaced")
        os.rename(previous, displaced)
        _tree(previous, "unrelated")
        with self.assertRaisesRegex(tx.TransactionError, "replaced"):
            tx.cleanup_swap(self.live, self.candidate, self.journal, confirm=True)
        self.assertEqual((previous / "identity.txt").read_text(), "unrelated")


class TestSafetyChecks(TransactionCase):
    def test_refuses_cross_filesystem_at_explicit_seam(self):
        with mock.patch.object(tx, "_same_filesystem", return_value=False):
            with self.assertRaisesRegex(tx.TransactionError, "same filesystem"):
                tx.prepare_swap(self.live, self.candidate, self.journal)
        self.assertFalse(self.journal.exists())

    def test_refuses_when_atomic_exchange_is_unsupported_without_fallback(self):
        with mock.patch.object(tx, "_atomic_exchange_supported", return_value=False):
            with self.assertRaisesRegex(
                tx.TransactionError, "refusing gapful fallback"
            ):
                tx.prepare_swap(self.live, self.candidate, self.journal)
        self.assertFalse(self.journal.exists())
        self.assertEqual((self.live / "identity.txt").read_text(), "old")
        self.assertEqual((self.candidate / "identity.txt").read_text(), "new")

    def test_commit_uses_one_exchange_syscall_not_two_renames(self):
        tx.prepare_swap(self.live, self.candidate, self.journal)
        with mock.patch.object(
            tx, "_exchange_syscall", wraps=tx._exchange_syscall
        ) as syscall:
            tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertEqual(syscall.call_count, 1)

    def test_refuses_symlink_candidate_and_non_sibling_journal(self):
        if hasattr(os, "symlink"):
            linked = self.parent / "linked"
            linked.symlink_to(self.candidate, target_is_directory=True)
            with self.assertRaisesRegex(tx.TransactionError, "symbolic link"):
                tx.prepare_swap(self.live, linked, self.journal)
        elsewhere = self.parent / "elsewhere"
        elsewhere.mkdir()
        with self.assertRaisesRegex(tx.TransactionError, "direct siblings"):
            tx.prepare_swap(self.live, self.candidate, elsewhere / "journal.json")

    def test_fsync_and_rename_seams_are_exercised(self):
        with mock.patch.object(
            tx, "_fsync_dir", wraps=tx._fsync_dir
        ) as fsync_call:
            tx.commit_swap(self.live, self.candidate, self.journal)
        self.assertGreaterEqual(fsync_call.call_count, 4)


if __name__ == "__main__":
    unittest.main()
