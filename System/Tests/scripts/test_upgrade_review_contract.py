"""Upgrade's reviewed semantic-input gate (protected-write Batch 2B).

The review intentionally does not claim final output-byte hashes: migration
and docgen materialize those only in the isolated candidate.  These contracts
prove the exact semantic inputs are authorized before checkpoint, while the
existing candidate/transaction suites prove the later full-tree identities.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import test_upgrade as fixtures  # noqa: E402

SCRIPTS = os.path.join(fixtures.VAULT, "System", "Scripts")
sys.path.insert(0, SCRIPTS)
from cmd import upgrade  # noqa: E402
from lib.report import Report  # noqa: E402


def _read_text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _write_text(path, text, mode="w"):
    with open(path, mode, encoding="utf-8") as stream:
        stream.write(text)


class TestUpgradeReviewedSemanticInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old = fixtures.mk_release(
            os.path.join(self.temp.name, "old"), "1.5.0")
        self.release = fixtures.mk_release(
            os.path.join(self.temp.name, "release"), "1.6.0",
            cap_body="NEW BODY")
        self.live = fixtures.mk_instance(
            os.path.join(self.temp.name, "instance"), self.old)

    def args(self, *, apply=False, confirm=False, review_sha256=None,
             accept=None):
        args = fixtures.Args()
        args.target = self.release
        args.apply = apply
        args.confirm = confirm
        args.review_sha256 = review_sha256
        args.accept = accept
        return args

    def review(self, *, accept=None):
        rep = Report("upgrade")
        upgrade.run(self.live, self.args(accept=accept), rep)
        self.assertTrue(rep.ok, rep.errors)
        return rep

    def assert_refused_before_checkpoint(self, args):
        before = fixtures.tree_state(self.live)
        calls = []

        def boundary(name, phase, root):
            calls.append((name, phase))

        rep = Report("upgrade")
        with mock.patch.object(upgrade, "_transaction_boundary",
                               side_effect=boundary), \
                mock.patch.object(upgrade.candidate_mod, "build_candidate",
                                  side_effect=AssertionError("candidate staged")):
            upgrade.run(self.live, args, rep)
        self.assertFalse(rep.ok)
        self.assertFalse(any(name == "checkpoint" for name, _ in calls), calls)
        self.assertEqual(before, fixtures.tree_state(self.live))
        return rep

    def test_bare_upgrade_is_read_only_and_labels_semantic_limitation(self):
        before_tree = fixtures.tree_state(self.live)
        before_siblings = set(os.listdir(self.temp.name))
        with mock.patch.object(upgrade.ckpt_mod, "run",
                               side_effect=AssertionError("checkpoint created")), \
                mock.patch.object(upgrade.candidate_mod, "build_candidate",
                                  side_effect=AssertionError("candidate staged")):
            rep = self.review()
        self.assertEqual(before_tree, fixtures.tree_state(self.live))
        self.assertEqual(before_siblings, set(os.listdir(self.temp.name)))
        self.assertRegex(rep.info["review_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            rep.info["review_plan"]["review_scope"],
            "exact-semantic-inputs-not-materialized-output-bytes")
        inputs = rep.info["review_plan"]["semantic_inputs"]
        self.assertIn("live_upgrade_surface_sha256", inputs)
        self.assertIn("tree_sha256", inputs["release"])
        self.assertIn("classification", inputs)

    def test_missing_and_wrong_hash_refuse_before_checkpoint(self):
        review = self.review()
        for supplied in (None, "0" * 64):
            with self.subTest(supplied=supplied):
                self.assert_refused_before_checkpoint(self.args(
                    apply=True, confirm=True, review_sha256=supplied))
        self.assertNotEqual(review.info["review_sha256"], "0" * 64)

    def test_bare_review_bypasses_kill_switch_but_apply_checks_it_first(self):
        manifest = os.path.join(self.live, "SYSTEM-MANIFEST.yaml")
        text = _read_text(manifest)
        _write_text(manifest,
                    text.replace("ai_writes_enabled: true", "ai_writes_enabled: false"))
        review = self.review()
        self.assertIn("review_sha256", review.info)

        args = self.args(apply=True, confirm=True,
                         review_sha256=review.info["review_sha256"])
        args.target = os.path.join(self.temp.name, "not-a-release")
        rep = Report("upgrade")
        upgrade.run(self.live, args, rep)
        self.assertFalse(rep.ok)
        self.assertIn("kill switch", " ".join(rep.errors))

    def test_exact_hash_reaches_existing_checkpoint_and_transaction(self):
        review = self.review()
        reached = []
        product_issued = (
            "opaque-checkpoint-rendering --quoted 'path with spaces' "
            "--proof not-derivable-from-checkpoint-id")

        def fake_checkpoint(root, args, rep):
            rep.info["checkpoint"] = "test-checkpoint"
            rep.info["checkpoint_identity"] = {"kind": "git-commit"}
            rep.info["rollback_command"] = product_issued
            return rep

        def fake_finish(*args, **kwargs):
            reached.append("transaction")
            return args[3]

        rep = Report("upgrade")
        with mock.patch.object(upgrade.ckpt_mod, "run",
                               side_effect=fake_checkpoint), \
                mock.patch.object(upgrade, "_finish_upgrade_transaction",
                                  side_effect=fake_finish):
            upgrade.run(self.live, self.args(
                apply=True, confirm=True,
                review_sha256=review.info["review_sha256"]), rep)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(reached, ["transaction"])
        self.assertIs(product_issued, rep.info["rollback_command"])

    def test_upgrade_never_infers_recovery_command_when_checkpoint_omits_it(self):
        review = self.review()

        def legacy_checkpoint(_root, _args, checkpoint_report):
            checkpoint_report.info["checkpoint"] = "git " + "a" * 40
            checkpoint_report.info["checkpoint_identity"] = {
                "kind": "git-commit",
                "target": "a" * 40,
                "tracked_sha256": "b" * 64,
            }
            return checkpoint_report

        rep = Report("upgrade")
        with mock.patch.object(upgrade.ckpt_mod, "run",
                               side_effect=legacy_checkpoint), \
                mock.patch.object(upgrade, "_finish_upgrade_transaction",
                                  return_value=rep):
            upgrade.run(self.live, self.args(
                apply=True, confirm=True,
                review_sha256=review.info["review_sha256"]), rep)

        self.assertNotIn("rollback_command", rep.info)

    def test_malformed_product_recovery_command_fails_before_candidate(self):
        review = self.review()

        def malformed_checkpoint(_root, _args, checkpoint_report):
            checkpoint_report.info["checkpoint"] = "test-checkpoint"
            checkpoint_report.info["checkpoint_identity"] = {"kind": "git-commit"}
            checkpoint_report.info["rollback_command"] = ""
            return checkpoint_report

        rep = Report("upgrade")
        with mock.patch.object(upgrade.ckpt_mod, "run",
                               side_effect=malformed_checkpoint), \
                mock.patch.object(upgrade.candidate_mod, "build_candidate",
                                  side_effect=AssertionError("candidate staged")):
            upgrade.run(self.live, self.args(
                apply=True, confirm=True,
                review_sha256=review.info["review_sha256"]), rep)

        self.assertFalse(rep.ok)
        self.assertIn("rollback command is malformed", " ".join(rep.errors))

    def test_live_release_policy_and_accept_changes_invalidate(self):
        cases = {
            "live": lambda: _write_text(os.path.join(
                self.live, "System", "Documentation", "Guide.md"), "live change\n", "a"),
            "release": lambda: _write_text(os.path.join(
                self.release, "System", "Documentation", "Guide.md"), "release change\n", "a"),
            "policy": lambda: _write_text(os.path.join(
                self.live, "SYSTEM-MANIFEST.yaml"), "\n# policy proof changed\n", "a"),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                # Each mutation needs an independent exact triangle.
                self.tearDown()
                self.setUp()
                review = self.review()
                mutate()
                self.assert_refused_before_checkpoint(self.args(
                    apply=True, confirm=True,
                    review_sha256=review.info["review_sha256"]))

        self.tearDown()
        self.setUp()
        review = self.review()
        self.assert_refused_before_checkpoint(self.args(
            apply=True, confirm=True,
            review_sha256=review.info["review_sha256"],
            accept=["System/Governance/not-a-conflict.md"]))

    def test_checkpoint_failure_preserves_unreviewed_abandoned_stage_exactly(self):
        abandoned = upgrade.candidate_mod.build_candidate(
            self.live, self.release, {},
            is_product_path=lambda _path: True,
            free_bytes=lambda _path: 10**12,
        )
        stage = abandoned["stage"]
        stage_before = fixtures.tree_state(stage)
        live_before = fixtures.tree_state(self.live)
        review = self.review()

        def refuse_checkpoint(_root, _args, checkpoint_report):
            checkpoint_report.error("intentional checkpoint refusal")
            return checkpoint_report

        rep = Report("upgrade")
        with mock.patch.object(upgrade.ckpt_mod, "run",
                               side_effect=refuse_checkpoint):
            upgrade.run(self.live, self.args(
                apply=True, confirm=True,
                review_sha256=review.info["review_sha256"]), rep)

        self.assertFalse(rep.ok)
        self.assertEqual(live_before, fixtures.tree_state(self.live))
        self.assertTrue(os.path.isdir(stage))
        self.assertEqual(stage_before, fixtures.tree_state(stage))
        self.assertNotIn("abandoned_candidates_removed", rep.info)
        self.assertIn("nothing written", " ".join(rep.errors))

    def test_post_checkpoint_policy_race_is_reported_before_candidate(self):
        review = self.review()
        siblings_before = set(os.listdir(self.temp.name))
        state_after_race = []

        def successful_checkpoint(_root, _args, checkpoint_report):
            checkpoint_report.info["checkpoint"] = "test-checkpoint"
            checkpoint_report.info["checkpoint_identity"] = {
                "kind": "git-commit",
            }
            return checkpoint_report

        def mutate_policy(name, phase, root):
            if (name, phase) == ("checkpoint", "after"):
                with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"),
                          "a", encoding="utf-8") as stream:
                    stream.write("\n# concurrent policy mutation\n")
                state_after_race.append(fixtures.tree_state(root))

        rep = Report("upgrade")
        with mock.patch.object(upgrade.ckpt_mod, "run",
                               side_effect=successful_checkpoint), \
                mock.patch.object(upgrade, "_transaction_boundary",
                                  side_effect=mutate_policy), \
                mock.patch.object(upgrade.candidate_mod, "build_candidate",
                                  side_effect=AssertionError("candidate staged")):
            upgrade.run(self.live, self.args(
                apply=True, confirm=True,
                review_sha256=review.info["review_sha256"]), rep)

        self.assertFalse(rep.ok)
        self.assertEqual(1, len(state_after_race))
        self.assertEqual(state_after_race[0], fixtures.tree_state(self.live))
        self.assertEqual(siblings_before, set(os.listdir(self.temp.name)))
        self.assertIn("read-only input changed", " ".join(rep.errors))
        self.assertIn("no candidate or live-tree swap", " ".join(rep.errors))


if __name__ == "__main__":
    unittest.main()
