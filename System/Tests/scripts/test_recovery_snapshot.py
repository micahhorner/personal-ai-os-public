"""Disposable adversarial tests for the no-Git exact snapshot/restore engine."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock


VAULT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(VAULT / "System" / "Scripts"))
from lib import snapshot  # noqa: E402


def _write(root: Path, relative: str, content: bytes, mode: int = 0o644) -> None:
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(mode)


def _rewrite_zip(source: Path, destination: Path, mutate) -> None:
    with zipfile.ZipFile(source, "r") as incoming, \
            zipfile.ZipFile(destination, "w") as outgoing:
        for info in incoming.infolist():
            data = incoming.read(info)
            replacements = mutate(info, data)
            if replacements is None:
                replacements = [(info, data)]
            for replacement, replacement_data in replacements:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    outgoing.writestr(replacement, replacement_data)


class SnapshotCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.outer = Path(self.temp.name)
        self.live = self.outer / "Vault with space Ω"
        self.live.mkdir()
        _write(self.live, "20 Knowledge/naïve note.md", "hello Ω\n".encode(), 0o640)
        (self.live / "empty dir").mkdir()
        self.archive = self.outer / "snapshots" / "safe snapshot.zip"

    def tearDown(self):
        self.temp.cleanup()

    def identity(self):
        return snapshot.create_snapshot(self.live, self.archive)

    def mutate_live(self):
        _write(self.live, "20 Knowledge/naïve note.md", b"broken\n")
        _write(self.live, "newer.txt", b"must disappear\n")


class TestExactSnapshot(SnapshotCase):
    def test_identity_contains_path_archive_hash_and_exact_manifest(self):
        identity = self.identity()
        self.assertEqual(Path(identity["path"]), self.archive.resolve())
        self.assertEqual(
            identity["sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest()
        )
        self.assertEqual(identity, snapshot.validate_snapshot(identity))
        paths = [entry["path"] for entry in identity["manifest"]["entries"]]
        self.assertIn("20 Knowledge/naïve note.md", paths)
        self.assertIn("empty dir", paths)

    def test_creation_is_atomic_and_refuses_links(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links unavailable")
        (self.live / "unsafe").symlink_to("../outside")
        with self.assertRaisesRegex(snapshot.SnapshotError, "symbolic link"):
            self.identity()
        self.assertFalse(self.archive.exists())
        self.assertFalse(list(self.archive.parent.glob("*.partial")))

    def test_interrupted_creation_never_publishes_partial_archive(self):
        def interrupt(point):
            self.assertEqual(point, "before-publish")
            raise KeyboardInterrupt("power loss")

        with self.assertRaises(KeyboardInterrupt):
            snapshot.create_snapshot(self.live, self.archive, interrupt=interrupt)
        self.assertFalse(self.archive.exists())
        self.assertFalse(list(self.archive.parent.glob(".*.partial")))

    def test_existing_archive_is_never_replaced(self):
        first = self.identity()
        self.assertTrue(self.archive.is_file())
        self.assertFalse(self.archive.is_symlink())
        before = self.archive.read_bytes()
        self.mutate_live()

        with self.assertRaisesRegex(snapshot.SnapshotError, "already exists"):
            self.identity()

        self.assertEqual(self.archive.read_bytes(), before)
        self.assertEqual(snapshot.validate_snapshot(first), first)
        self.assertFalse(list(self.archive.parent.glob(".*.partial")))

    def test_existing_archive_symlink_is_never_replaced_or_followed(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symbolic links unavailable")
        outside = self.outer / "outside-sentinel.txt"
        outside.write_bytes(b"outside must remain unchanged")
        self.archive.parent.mkdir(parents=True, exist_ok=True)
        self.archive.symlink_to(outside)

        with self.assertRaisesRegex(snapshot.SnapshotError, "already exists"):
            self.identity()

        self.assertTrue(self.archive.is_symlink())
        self.assertEqual(outside.read_bytes(), b"outside must remain unchanged")
        self.assertFalse(list(self.archive.parent.glob(".*.partial")))

    def test_archive_cannot_live_inside_snapshotted_tree(self):
        with self.assertRaisesRegex(snapshot.SnapshotError, "outside"):
            snapshot.create_snapshot(self.live, self.live / "snapshot.zip")


class TestExactRestore(SnapshotCase):
    def test_path_and_archive_hash_are_sufficient_for_exact_cli_identity(self):
        identity = self.identity()
        minimal = {"path": identity["path"], "sha256": identity["sha256"]}
        self.mutate_live()

        result = snapshot.restore_snapshot(self.live, minimal, reserve_bytes=0)

        self.assertEqual(result["status"], "restored")
        self.assertEqual(
            (self.live / "20 Knowledge/naïve note.md").read_text(), "hello Ω\n"
        )
        self.assertFalse((self.live / "newer.txt").exists())

    def test_restore_is_exact_preserves_old_tree_and_is_idempotent(self):
        identity = self.identity()
        expected_mode = stat.S_IMODE(
            (self.live / "20 Knowledge/naïve note.md").stat().st_mode
        )
        self.mutate_live()
        result = snapshot.restore_snapshot(self.live, identity, reserve_bytes=0)
        self.assertEqual(result["status"], "restored")
        previous = Path(result["previous_tree"])
        self.assertEqual((self.live / "20 Knowledge/naïve note.md").read_text(), "hello Ω\n")
        self.assertFalse((self.live / "newer.txt").exists())
        self.assertEqual(
            stat.S_IMODE((self.live / "20 Knowledge/naïve note.md").stat().st_mode),
            expected_mode,
        )
        self.assertEqual((previous / "newer.txt").read_text(), "must disappear\n")
        again = snapshot.restore_snapshot(self.live, identity, reserve_bytes=0)
        self.assertEqual(again["status"], "already-restored")
        self.assertIsNone(again["previous_tree"])

    def test_restore_preserves_root_directory_mode(self):
        self.live.chmod(0o750)
        identity = self.identity()
        self.live.chmod(0o700)
        self.mutate_live()

        snapshot.restore_snapshot(self.live, identity, reserve_bytes=0)

        self.assertEqual(stat.S_IMODE(self.live.stat().st_mode), 0o750)

    def test_restore_refuses_archive_inside_live_tree(self):
        external = self.identity()
        embedded = self.live / "embedded.zip"
        embedded.write_bytes(Path(external["path"]).read_bytes())
        before = (self.live / "20 Knowledge/naïve note.md").read_bytes()

        with self.assertRaisesRegex(snapshot.RestoreError, "outside"):
            snapshot.restore_snapshot(
                self.live,
                {"path": str(embedded), "sha256": external["sha256"]},
                reserve_bytes=0,
            )

        self.assertEqual(
            (self.live / "20 Knowledge/naïve note.md").read_bytes(), before
        )

    def test_read_only_directory_is_restored_with_exact_mode(self):
        protected = self.live / "read only"
        protected.mkdir()
        _write(protected, "child.txt", b"safe")
        protected.chmod(0o500)
        try:
            identity = self.identity()
            protected.chmod(0o700)
            _write(self.live, "later.txt", b"later")
            snapshot.restore_snapshot(self.live, identity, reserve_bytes=0)
            self.assertEqual(stat.S_IMODE((self.live / "read only").stat().st_mode), 0o500)
            self.assertEqual((self.live / "read only" / "child.txt").read_bytes(), b"safe")
        finally:
            restored = self.live / "read only"
            if restored.exists():
                restored.chmod(0o700)

    def test_interruption_after_stage_never_touches_live(self):
        identity = self.identity()
        self.mutate_live()
        before = (self.live / "newer.txt").read_bytes()

        def interrupt(point):
            if point == "after-stage":
                raise KeyboardInterrupt("power loss")

        with self.assertRaises(KeyboardInterrupt):
            snapshot.restore_snapshot(
                self.live, identity, reserve_bytes=0, interrupt=interrupt
            )
        self.assertEqual((self.live / "newer.txt").read_bytes(), before)

    def test_interruption_during_swap_puts_original_live_path_back(self):
        identity = self.identity()
        self.mutate_live()

        def interrupt(point):
            if point == "after-live-move":
                raise KeyboardInterrupt("power loss")

        with self.assertRaises(KeyboardInterrupt):
            snapshot.restore_snapshot(
                self.live, identity, reserve_bytes=0, interrupt=interrupt
            )
        self.assertEqual((self.live / "newer.txt").read_text(), "must disappear\n")
        rerun = snapshot.restore_snapshot(self.live, identity, reserve_bytes=0)
        self.assertEqual(rerun["status"], "restored")
        self.assertFalse((self.live / "newer.txt").exists())

    def test_interruption_after_install_reverts_and_quarantines_candidate(self):
        identity = self.identity()
        self.mutate_live()

        def interrupt(point):
            if point == "after-install":
                raise RuntimeError("post-install fault")

        with self.assertRaisesRegex(RuntimeError, "post-install"):
            snapshot.restore_snapshot(
                self.live, identity, reserve_bytes=0, interrupt=interrupt
            )
        self.assertEqual((self.live / "newer.txt").read_text(), "must disappear\n")
        self.assertTrue(list(self.outer.glob("Vault with space Ω.failed-restore*")))

    def test_insufficient_staging_refuses_before_writing(self):
        identity = self.identity()
        self.mutate_live()
        with mock.patch.object(snapshot, "_free_bytes", return_value=0):
            with self.assertRaises(snapshot.InsufficientStagingError):
                snapshot.restore_snapshot(self.live, identity, reserve_bytes=1)
        self.assertEqual((self.live / "newer.txt").read_text(), "must disappear\n")
        self.assertFalse(list(self.outer.glob(".Vault with space Ω.restore-*")))


class TestArchiveDefenses(SnapshotCase):
    def _malicious(self, mutate) -> Path:
        # Each fixture needs a newly captured valid source archive. Production
        # snapshot publication is deliberately no-clobber.
        self.archive.unlink(missing_ok=True)
        identity = self.identity()
        bad = self.outer / "bad.zip"
        _rewrite_zip(Path(identity["path"]), bad, mutate)
        return bad

    def test_tampered_payload_refused_without_touching_live(self):
        identity = self.identity()
        self.mutate_live()
        bad = self.outer / "tampered.zip"

        def mutate(info, data):
            if info.filename.endswith("naïve note.md"):
                return [(info, b"evil")]
            return None

        _rewrite_zip(self.archive, bad, mutate)
        forged = dict(identity, path=str(bad))
        with self.assertRaisesRegex(snapshot.CorruptSnapshotError, "SHA-256"):
            snapshot.restore_snapshot(self.live, forged, reserve_bytes=0)
        self.assertTrue((self.live / "newer.txt").exists())

    def test_tampered_payload_without_external_identity_is_still_refused(self):
        self.identity()
        self.mutate_live()
        bad = self.outer / "tampered-path-only.zip"

        def mutate(info, data):
            if info.filename.endswith("naïve note.md"):
                return [(info, b"evil")]
            return None

        _rewrite_zip(self.archive, bad, mutate)
        with self.assertRaises(snapshot.CorruptSnapshotError):
            snapshot.restore_snapshot(self.live, bad, reserve_bytes=0)
        self.assertTrue((self.live / "newer.txt").exists())

    def test_path_traversal_absolute_and_backslash_are_refused(self):
        for unsafe in ("payload/../escape", "/absolute", r"payload\escape"):
            with self.subTest(unsafe=unsafe):
                bad = self._malicious(
                    lambda info, data, unsafe=unsafe: (
                        [(info, data), (zipfile.ZipInfo(unsafe), b"x")]
                        if info.filename == snapshot.MANIFEST_MEMBER else None
                    )
                )
                with self.assertRaises(snapshot.UnsafeArchiveError):
                    snapshot.validate_snapshot(bad)

    def test_symlink_member_is_refused(self):
        def mutate(info, data):
            if info.filename == snapshot.MANIFEST_MEMBER:
                link = zipfile.ZipInfo("payload/link")
                link.create_system = 3
                link.external_attr = (stat.S_IFLNK | 0o777) << 16
                return [(info, data), (link, b"../../outside")]
            return None

        with self.assertRaises(snapshot.UnsafeArchiveError):
            snapshot.validate_snapshot(self._malicious(mutate))

    def test_duplicate_member_is_refused(self):
        def mutate(info, data):
            if info.filename.endswith("naïve note.md"):
                return [(info, data), (info, data)]
            return None

        with self.assertRaisesRegex(snapshot.UnsafeArchiveError, "duplicate"):
            snapshot.validate_snapshot(self._malicious(mutate))

    def test_case_and_unicode_collisions_are_refused(self):
        for collision in ("payload/20 knowledge/NAÏVE NOTE.MD",
                          "payload/20 Knowledge/nai\u0308ve note.md"):
            with self.subTest(collision=collision):
                def mutate(info, data, collision=collision):
                    if info.filename == snapshot.MANIFEST_MEMBER:
                        return [(info, data), (zipfile.ZipInfo(collision), b"x")]
                    return None
                with self.assertRaisesRegex(snapshot.UnsafeArchiveError, "colliding"):
                    snapshot.validate_snapshot(self._malicious(mutate))

    def test_corrupt_manifest_and_unlisted_member_are_refused(self):
        bad_manifest = self._malicious(
            lambda info, data: [(info, b"{")] if info.filename == snapshot.MANIFEST_MEMBER else None
        )
        with self.assertRaises(snapshot.CorruptSnapshotError):
            snapshot.validate_snapshot(bad_manifest)
        unlisted = self._malicious(
            lambda info, data: (
                [(info, data), (zipfile.ZipInfo("payload/unlisted.txt"), b"x")]
                if info.filename == snapshot.MANIFEST_MEMBER else None
            )
        )
        with self.assertRaises(snapshot.CorruptSnapshotError):
            snapshot.validate_snapshot(unlisted)


if __name__ == "__main__":
    unittest.main()
