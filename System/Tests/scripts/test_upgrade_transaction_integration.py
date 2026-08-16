"""Production upgrade transaction integration tests (Wave 3)."""
from test_io import read_file, write_file
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from unittest import mock

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import test_upgrade as fixtures  # noqa: E402

SCRIPTS = os.path.join(fixtures.VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
RQ = os.path.join(fixtures.VAULT, "System", "Tests", "release_qualification")
sys.path.insert(0, RQ)
from cmd import upgrade  # noqa: E402
from lib import transaction  # noqa: E402
from lib import upgrade_candidate  # noqa: E402
import transaction_faults as rq_faults  # noqa: E402


class UpgradeTransactionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old = fixtures.mk_release(
            os.path.join(self.temp.name, "old"), "1.5.0")
        self.new = fixtures.mk_release(
            os.path.join(self.temp.name, "new"), "1.6.0",
            cap_body="NEW BODY")
        self.live = fixtures.mk_instance(
            os.path.join(self.temp.name, "instance"), self.old)

    def run_upgrade(self):
        return fixtures.run_upgrade(self.live, self.new)


class TestProductionTransaction(UpgradeTransactionCase):
    def test_success_is_complete_preserves_user_hashes_and_reruns_noop(self):
        user_before = upgrade._user_world(self.live)
        first = self.run_upgrade()
        self.assertTrue(first.ok, first.errors)
        self.assertIn("system_version: 1.6.0",
                      read_file(os.path.join(self.live, "SYSTEM-MANIFEST.yaml"), mode="r"))
        self.assertIn("NEW BODY", read_file(os.path.join(
            self.live, "System", "Capabilities", "foo", "SKILL.md"), mode="r"))
        user_after = upgrade._user_world(self.live)
        expected = dict(user_before)
        expected["SYSTEM-MANIFEST.yaml"] = user_after["SYSTEM-MANIFEST.yaml"]
        expected["System/Journal/change-journal.md"] = \
            user_after["System/Journal/change-journal.md"]
        projected = {k: v for k, v in user_after.items()
                     if not k.startswith(".claude/skills/")}
        self.assertEqual(expected, projected)
        snapshot = fixtures.tree_state(self.live)
        second = self.run_upgrade()
        self.assertTrue(second.ok, second.errors)
        self.assertIn("nothing to do", second.info["result"])
        self.assertEqual(snapshot, fixtures.tree_state(self.live))

    def test_gate_failure_leaves_complete_old_tree(self):
        with open(os.path.join(self.live, "20 Knowledge", "broken.md"),
                  "w", encoding="utf-8") as stream:
            stream.write("---\nid: note-broken\ntype: nonsense-class\n---\nbody\n")
        before = fixtures.tree_state(self.live)
        result = self.run_upgrade()
        self.assertFalse(result.ok)
        self.assertEqual(before, fixtures.tree_state(self.live))
        self.assertIn("system_version: 1.5.0",
                      read_file(os.path.join(self.live, "SYSTEM-MANIFEST.yaml"), mode="r"))

    def test_invalid_state_created_by_report_phase_is_validated_and_never_swapped(self):
        before = fixtures.tree_state(self.live)
        real_report = upgrade._write_candidate_report

        def corrupt_after_report(candidate_root, *args, **kwargs):
            real_report(candidate_root, *args, **kwargs)
            with open(os.path.join(candidate_root, "20 Knowledge", "late-broken.md"),
                      "w", encoding="utf-8") as stream:
                stream.write("---\nid: note-late-broken\ntype: nonsense-class\n---\n")

        with mock.patch.object(upgrade, "_write_candidate_report",
                               side_effect=corrupt_after_report):
            result = self.run_upgrade()
        self.assertFalse(result.ok)
        self.assertEqual(before, fixtures.tree_state(self.live))
        self.assertFalse(os.path.exists(
            os.path.join(self.live, "20 Knowledge", "late-broken.md")))

    def test_exact_eleven_boundary_contract_without_migration_and_no_live_write_before_exchange(self):
        calls = []
        real_exchange = transaction._atomic_exchange

        def boundary(name, phase, root):
            calls.append((name, phase))

        def inspect_then_exchange(live, candidate):
            if os.path.exists(os.path.join(live, "SYSTEM-MANIFEST.yaml")):
                self.assertIn("system_version: 1.5.0",
                              read_file(os.path.join(live, "SYSTEM-MANIFEST.yaml"), mode="r"))
                self.assertIn("system_version: 1.6.0",
                              read_file(os.path.join(candidate, "SYSTEM-MANIFEST.yaml"), mode="r"))
            return real_exchange(live, candidate)

        with mock.patch.object(upgrade, "_transaction_boundary",
                               side_effect=boundary), \
                mock.patch.object(transaction, "_atomic_exchange",
                                  side_effect=inspect_then_exchange):
            result = self.run_upgrade()
        self.assertTrue(result.ok, result.errors)
        execution = (
            "plan", "checkpoint", "candidate-copy", "candidate-delete",
            "baseline-replacement", "version-bump", "generation",
            "report-write", "validation", "commit-swap", "cleanup")
        expected = [(name, phase)
                    for name in execution
                    for phase in ("before", "after")]
        self.assertEqual(expected, calls)

    def test_deleted_process_cwd_does_not_block_atomic_upgrade(self):
        original_fd = os.open(".", os.O_RDONLY)
        vanished = tempfile.mkdtemp(dir=self.temp.name)
        try:
            os.chdir(vanished)
            os.rmdir(vanished)
            result = self.run_upgrade()
        finally:
            os.fchdir(original_fd)
            os.close(original_fd)
        self.assertTrue(result.ok, result.errors)
        self.assertIn(
            "system_version: 1.6.0",
            read_file(os.path.join(self.live, "SYSTEM-MANIFEST.yaml"), mode="r"),
        )

    def test_git_directory_and_pointer_are_identical_after_whole_root_swap(self):
        for kind in ("directory", "pointer"):
            with self.subTest(kind=kind):
                git = os.path.join(self.live, ".git")
                if os.path.isdir(git):
                    shutil.rmtree(git)
                elif os.path.exists(git):
                    os.remove(git)
                if kind == "directory":
                    os.makedirs(os.path.join(git, "refs", "heads"))
                    with open(os.path.join(git, "HEAD"), "w") as stream:
                        stream.write("ref: refs/heads/main\n")
                    with open(os.path.join(git, "refs", "heads", "main"), "w") as stream:
                        stream.write("abc123\n")
                else:
                    with open(git, "w") as stream:
                        stream.write("gitdir: /tmp/external-worktree\n")
                before = upgrade_candidate.path_identity(git)
                with mock.patch.object(upgrade.ckpt_mod, "run",
                                       side_effect=lambda root, args, rep: rep):
                    result = self.run_upgrade()
                self.assertTrue(result.ok, result.errors)
                self.assertEqual(before, upgrade_candidate.path_identity(
                    os.path.join(self.live, ".git")))
                if kind == "directory":
                    # reset fixture to old for the pointer subcase
                    shutil.rmtree(self.live)
                    self.live = fixtures.mk_instance(
                        os.path.join(self.temp.name, "instance"), self.old)

    def test_concurrent_live_and_candidate_mutations_are_refused(self):
        real_retain = upgrade_candidate.retain_as_sibling

        def mutate_live(info, *, root):
            result = real_retain(info, root=root)
            with open(os.path.join(root, "20 Knowledge", "mine.md"), "a") as stream:
                stream.write("external concurrent edit\n")
            return result

        with mock.patch.object(upgrade_candidate, "retain_as_sibling",
                               side_effect=mutate_live):
            result = self.run_upgrade()
        self.assertFalse(result.ok)
        self.assertTrue(any("live vault changed" in e for e in result.errors))
        self.assertIn("system_version: 1.5.0",
                      read_file(os.path.join(self.live, "SYSTEM-MANIFEST.yaml"), mode="r"))

        shutil.rmtree(self.live)
        self.live = fixtures.mk_instance(
            os.path.join(self.temp.name, "instance"), self.old)
        real_prepare = transaction.prepare_swap

        def mutate_candidate(live, candidate, journal, **kwargs):
            result = real_prepare(live, candidate, journal, **kwargs)
            with open(os.path.join(candidate, "System", "concurrent.txt"), "w") as stream:
                stream.write("mutation")
            return result

        before = fixtures.tree_state(self.live)
        with mock.patch.object(transaction, "prepare_swap",
                               side_effect=mutate_candidate):
            result = self.run_upgrade()
        self.assertFalse(result.ok)
        self.assertTrue(any("final candidate changed" in e for e in result.errors))
        self.assertEqual(before, fixtures.tree_state(self.live))

    def test_mutation_inside_commit_before_callback_is_content_pin_refused(self):
        before = fixtures.tree_state(self.live)
        real_boundary = upgrade._transaction_boundary
        mutated = [False]

        def mutate_then_verify(name, phase, root):
            if (name, phase) == ("commit-swap", "before") and not mutated[0]:
                mutated[0] = True
                journals = [n for n in os.listdir(self.temp.name)
                            if n.startswith(".instance.upgrade-transaction-")
                            and n.endswith(".json")]
                data = __import__("json").loads(
                    read_file(os.path.join(self.temp.name, journals[0])))
                with open(os.path.join(data["candidate"], "System", "late.txt"),
                          "w") as stream:
                    stream.write("late mutation")
            return real_boundary(name, phase, root)

        with mock.patch.object(upgrade, "_transaction_boundary",
                               side_effect=mutate_then_verify):
            result = self.run_upgrade()
        self.assertFalse(result.ok)
        self.assertEqual(before, fixtures.tree_state(self.live))
        self.assertTrue(any("content identity mismatch" in e for e in result.errors))

    def test_capacity_and_filesystem_refusals_use_production_seams(self):
        for seam, value, phrase in (
                ("_free_bytes", 0, "insufficient free space"),
                ("_same_filesystem", False, "different filesystems")):
            with self.subTest(seam=seam):
                before = fixtures.tree_state(self.live)
                with mock.patch.object(upgrade, seam, return_value=value):
                    result = self.run_upgrade()
                self.assertFalse(result.ok)
                self.assertTrue(any(phrase in e for e in result.errors), result.errors)
                self.assertEqual(before, fixtures.tree_state(self.live))

    def test_resume_proves_live_before_cleanup(self):
        with mock.patch.object(
                transaction, "cleanup_swap",
                side_effect=transaction.TransactionError("cleanup interrupted")):
            first = self.run_upgrade()
        self.assertTrue(first.ok, first.errors)
        order = []
        real_proof = upgrade._post_swap_proof
        real_cleanup = transaction.cleanup_swap

        def proof(*args, **kwargs):
            order.append("proof")
            return real_proof(*args, **kwargs)

        def cleanup(*args, **kwargs):
            order.append("cleanup")
            return real_cleanup(*args, **kwargs)

        with mock.patch.object(upgrade, "_post_swap_proof", side_effect=proof), \
                mock.patch.object(transaction, "cleanup_swap", side_effect=cleanup):
            second = self.run_upgrade()
        self.assertTrue(second.ok, second.errors)
        self.assertEqual(["proof", "cleanup"], order[:2])

    def test_cleanup_resume_preserves_unreviewed_abandoned_stage_exactly(self):
        real_boundary = upgrade._transaction_boundary

        def interrupt_cleanup(name, phase, root):
            if (name, phase) == ("cleanup", "before"):
                raise RuntimeError("cleanup boundary interruption")
            return real_boundary(name, phase, root)

        with mock.patch.object(upgrade, "_transaction_boundary",
                               side_effect=interrupt_cleanup):
            first = self.run_upgrade()
        self.assertTrue(first.ok, first.errors)
        lookalike = os.path.join(
            self.temp.name, ".instance.aios-upgrade-lookalike")
        os.makedirs(lookalike)
        candidate_id = str(uuid.uuid4())
        abandoned = os.path.join(
            self.temp.name, f".instance.aios-upgrade-{candidate_id}")
        os.makedirs(abandoned)
        owner = {
            "schema": upgrade_candidate.OWNER_SCHEMA,
            "candidate_id": candidate_id,
            "live": os.path.realpath(self.live),
            "stage": os.path.realpath(abandoned),
        }
        upgrade_candidate._write_owner(
            os.path.join(abandoned, upgrade_candidate.OWNER_FILE), owner)
        with open(os.path.join(abandoned, "partial"), "w") as stream:
            stream.write("partial")
        abandoned_before = fixtures.tree_state(abandoned)
        second = self.run_upgrade()
        self.assertTrue(second.ok, second.errors)
        self.assertTrue(os.path.isdir(abandoned))
        self.assertEqual(abandoned_before, fixtures.tree_state(abandoned))
        self.assertTrue(os.path.exists(lookalike))
        self.assertNotIn("abandoned_candidates_removed", second.info)
        self.assertIn(second.info.get("transaction_resume"), ("cleanup", None))

    def test_post_swap_proof_failure_automatically_restores_exact_old_tree(self):
        before = fixtures.tree_state(self.live)
        with mock.patch.object(upgrade, "_post_swap_proof", return_value=False):
            result = self.run_upgrade()
        self.assertFalse(result.ok)
        self.assertEqual(before, fixtures.tree_state(self.live))
        self.assertEqual("rolled-back", result.info["transaction_rollback"])
        failed = result.info["failed_candidate"]
        self.assertTrue(os.path.isdir(failed))
        self.assertIn("system_version: 1.6.0",
                      read_file(os.path.join(failed, "SYSTEM-MANIFEST.yaml"), mode="r"))
        self.assertTrue(os.path.isfile(result.info["transaction_journal"]))

    def test_resumed_post_swap_failure_also_restores_exact_old_tree(self):
        before = fixtures.tree_state(self.live)
        with mock.patch.object(
                transaction, "cleanup_swap",
                side_effect=transaction.TransactionError("cleanup interrupted")):
            first = self.run_upgrade()
        self.assertTrue(first.ok, first.errors)
        with mock.patch.object(upgrade, "_post_swap_proof", return_value=False):
            second = self.run_upgrade()
        self.assertFalse(second.ok)
        self.assertEqual(before, fixtures.tree_state(self.live))
        self.assertEqual("rolled-back", second.info["transaction_rollback"])
        self.assertTrue(os.path.isdir(second.info["failed_candidate"]))

    def test_all_22_real_process_interruptions_rerun_to_exact_safe_state(self):
        new_boundaries = {"commit-swap": {"after"},
                          "cleanup": {"before", "after"}}
        scripts_before = rq_faults.capture_tree(SCRIPTS)["sha256"]
        for boundary in rq_faults.BOUNDARIES:
            for phase in rq_faults.PHASES:
                with self.subTest(boundary=boundary, phase=phase), \
                        tempfile.TemporaryDirectory() as outer:
                    old = fixtures.mk_release(
                        os.path.join(outer, "old"), "1.5.0")
                    new = fixtures.mk_release(
                        os.path.join(outer, "new"), "1.6.0",
                        cap_body="NEW BODY")
                    live = fixtures.mk_instance(
                        os.path.join(outer, "instance"), old)
                    rq_faults.arm_fault_target(live)
                    old_hash = rq_faults.capture_tree(live)["sha256"]
                    release_hash = rq_faults.capture_tree(new)["sha256"]
                    with open(os.path.join(
                            live, "20 Knowledge", "mine.md"), "rb") as stream:
                        protected = stream.read()
                    review = fixtures.run_upgrade(live, new, dry_run=True)
                    self.assertTrue(review.ok, review.errors)
                    argv = [
                        "upgrade", new, "--root", live, "--apply", "--confirm",
                        "--review-sha256", review.info["review_sha256"],
                    ]
                    interrupted = rq_faults.run_with_fault(
                        SCRIPTS, argv,
                        rq_faults.TransactionFaultSpec(boundary, phase, live),
                        timeout=60)
                    self.assertTrue(
                        interrupted.interrupted,
                        interrupted.stdout + interrupted.stderr)
                    after_fault = rq_faults.capture_tree(live)["sha256"]
                    should_be_new = phase in new_boundaries.get(boundary, set())
                    if should_be_new:
                        self.assertIn(
                            "system_version: 1.6.0",
                            read_file(os.path.join(live, "SYSTEM-MANIFEST.yaml"), mode="r"))
                    else:
                        self.assertEqual(old_hash, after_fault)
                    rerun = fixtures.run_upgrade(live, new)
                    self.assertTrue(rerun.ok, rerun.errors)
                    after_rerun = rq_faults.capture_tree(live)["sha256"]
                    if should_be_new:
                        self.assertEqual(after_fault, after_rerun)
                    self.assertIn(
                        "system_version: 1.6.0",
                        read_file(os.path.join(live, "SYSTEM-MANIFEST.yaml"), mode="r"))
                    self.assertEqual(
                        protected,
                        read_file(os.path.join(
                            live, "20 Knowledge", "mine.md"), mode="rb"))
                    self.assertEqual(
                        release_hash, rq_faults.capture_tree(new)["sha256"])
                    self.assertEqual(
                        scripts_before, rq_faults.capture_tree(SCRIPTS)["sha256"])


if __name__ == "__main__":
    unittest.main()
