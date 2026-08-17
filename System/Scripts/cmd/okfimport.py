"""vault.okf-import — land an Open Knowledge Format bundle as ingest sources.

**An OKF bundle is evidence, not knowledge.** It arrives from outside: another
vault, a vendor's catalog, Google's own sample bundles. So it lands exactly where
any other foreign capture lands — as immutable `source` notes in the sources
folder, born `status: draft` and `verification: unverified` — and stops there.
Turning a source into canon is `ingest-and-connect`'s job (dedupe, attribute,
extract, connect, promotion gate), and a machine may never auto-promote.

This script is the deterministic half only: read the bundle, map the fields, mint
ids, write the sources. The judgment half stays in the capability. That split is
the Kernel's rule — never hand-perform what a script does, never let a script
perform what needs judgment.

The OKF-native values are preserved verbatim under `x_okf_*` keys so nothing the
bundle asserted is lost in becoming a source; the round-trip proof compares them.

**v0.1 and v0.2 bundles both land, and the difference is recorded rather than
flattened.** v0.2's families arrive under their own names — `x_okf_generated`,
`x_okf_verified`, `x_okf_status`, `x_okf_stale_after`, `x_okf_sources` — and
anything else a producer wrote (an Attested Computation's `runtime`, `executor`,
`attester`, or any key this consumer has never heard of) is preserved under
`x_okf_extra`. A v0.1 bundle's legacy `timestamp` still lands as
`x_okf_timestamp`, which is the fallback §13.1 sanctions.

**Their `verified` is evidence about the bundle, never this vault's verification.**
A v0.2 bundle can arrive stating who confirmed each concept and when. That is a
real, useful signal — and it is *their* gate, not this one. The landed source stays
`verification: unverified` and `status: draft` no matter how well-attested the
bundle is. The one v0.2 field that does map is `stale_after`: the producer named
the date their content stops being current, so it becomes this vault's
`review_due` rather than a horizon invented here. The mapping itself lives in
`lib/okf.py`.
"""
from __future__ import annotations

import datetime
import os
import re
import unicodedata

import yaml

from lib.frontmatter import Note
from lib.okf import BUNDLE_MARKER, RESERVED, from_okf, safe_relpath, slugify
from lib.report import Report
from lib.protectedwrites import ProtectedTargetError, refuse_protected_targets
from lib.safepaths import (SafePathError, atomic_create_files,
                           open_readonly_tree)
from lib.vaultpaths import rel_folder


OKF_IMPORT_MAX_FILE_BYTES = 64 * 1024 * 1024
OKF_IMPORT_MAX_TOTAL_BYTES = 512 * 1024 * 1024


def _existing_ids(root) -> set:
    """Every id already in the vault — imported sources must not collide."""
    from lib.frontmatter import iter_markdown
    return {str(n.meta["id"]) for n in iter_markdown(root)
            if not n.error and n.meta and n.meta.get("id")}


def _concepts(files):
    """Every concept document in an already-bound bundle, depth-first.

    Reserved filenames (`index.md`, `log.md`) are the bundle's own navigation and
    changelog, not concepts — the spec gives them defined meanings and exempts
    them from the frontmatter rule, so importing them as evidence would file the
    table of contents as a finding."""
    for rel in sorted(files):
        parts = rel.replace("\\", "/").split("/")
        if any(part.startswith(".") for part in parts[:-1]):
            continue
        if parts[-1].endswith(".md") and parts[-1].lower() not in RESERVED:
            yield rel


def _parse_bytes(data: bytes, relpath: str) -> Note:
    """Parse a safely-bound concept without reopening it by pathname."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return Note(relpath, relpath, {}, "", f"unreadable: {exc}")
    meta, body = {}, text
    if text.startswith("---\n") or text.startswith("---\r\n"):
        match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.DOTALL)
        if not match:
            return Note(relpath, relpath, {}, text, "unterminated frontmatter fence")
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            return Note(relpath, relpath, {}, text, f"frontmatter YAML error: {exc}")
        if not isinstance(meta, dict):
            return Note(relpath, relpath, {}, text, "frontmatter is not a mapping")
        body = text[match.end():]
    return Note(relpath, relpath, meta, body)


class _BoundBundle:
    """Duck-typed read-only input for ``atomic_create_files``.

    ``ReadOnlyTree`` binds every member and ancestor descriptor. Re-reading the
    complete tree at each transaction proof catches added, removed, renamed, or
    changed source members without teaching the shared path layer about OKF.
    """

    def __init__(self, tree, files, directories, payloads):
        self.tree = tree
        self.files = tuple(files)
        self.directories = tuple(directories)
        self.payloads = payloads
        self.identities = {
            rel: (tree.files[rel].device, tree.files[rel].inode,
                  tree.files[rel].mode, tree.files[rel].size,
                  tree.files[rel].mtime_ns)
            for rel in files
        }

    def reprove(self):
        files, directories = self.tree.walk(
            prune=lambda rel: any(part.startswith(".")
                                  for part in rel.replace("\\", "/").split("/"))
        )
        if tuple(files) != self.files or tuple(directories) != self.directories:
            raise SafePathError("read-only OKF bundle tree changed after preflight")
        identities = {
            rel: (self.tree.files[rel].device, self.tree.files[rel].inode,
                  self.tree.files[rel].mode, self.tree.files[rel].size,
                  self.tree.files[rel].mtime_ns)
            for rel in files
        }
        if identities != self.identities:
            raise SafePathError("read-only OKF bundle members changed after preflight")
        current = self.tree.read_files(
            files,
            max_file_bytes=OKF_IMPORT_MAX_FILE_BYTES,
            max_total_bytes=OKF_IMPORT_MAX_TOTAL_BYTES,
        )
        if current != self.payloads:
            raise SafePathError("read-only OKF bundle bytes changed after preflight")


def run(root, args, rep: Report):
    src = getattr(args, "target", None)
    if not src:
        rep.error("usage: aios okf-import <path-to-bundle> — the directory holding the "
                  "OKF concept documents")
        return rep
    bundle = os.path.abspath(os.path.expanduser(src))
    tree = None
    try:
        tree = open_readonly_tree(bundle)
        files, directories = tree.walk(
            prune=lambda rel: any(part.startswith(".")
                                  for part in rel.replace("\\", "/").split("/"))
        )
        payloads = tree.read_files(
            files,
            max_file_bytes=OKF_IMPORT_MAX_FILE_BYTES,
            max_total_bytes=OKF_IMPORT_MAX_TOTAL_BYTES,
        )
        bound = _BoundBundle(tree, files, directories, payloads)
    except (OSError, SafePathError) as exc:
        if tree is not None:
            tree.close()
        rep.error(f"OKF import refused before writes: {exc}")
        return rep

    marker_rel = next((rel for rel in files if rel == BUNDLE_MARKER), None)
    if marker_rel:
        try:
            marker_data = yaml.safe_load(payloads[marker_rel].decode("utf-8")) or {}
            rep.info["bundle_okf_version"] = marker_data.get("okf_version", "unstated")
        except (UnicodeDecodeError, yaml.YAMLError, AttributeError):
            pass   # a foreign bundle's marker is not ours to police

    sources_rel = rel_folder(root, "sources", "30 Sources")   # DEC-067
    dest_rel = os.path.join(sources_rel, "OKF " + os.path.basename(bundle.rstrip(os.sep)))
    try:
        refuse_protected_targets(root, (dest_rel,), "okf-import")
    except ProtectedTargetError as exc:
        rep.error(f"OKF import refused before writes: {exc}")
        tree.close()
        return rep
    dest = os.path.join(root, dest_rel)
    if os.path.lexists(dest):
        rep.error(f"{dest_rel} already exists — sources are immutable (Kernel §1.4); "
                  "re-importing would overwrite captured evidence. Remove or rename it first.")
        tree.close()
        return rep
    found = list(_concepts(files))
    if not found:
        rep.error(f"no OKF concept documents found in {src} "
                  f"(a bundle is a directory of .md concepts; index.md/log.md are reserved)")
        tree.close()
        return rep

    taken = _existing_ids(root)
    today = datetime.date.today().isoformat()
    skipped = 0
    writes = {}
    output_origins = {}
    for relpath in found:
        note = _parse_bytes(payloads[relpath], relpath)
        if note.error:
            rep.warn(f"{note.relpath}: {note.error} — skipped")
            skipped += 1
            continue
        # The spec's one conformance rule for a concept document: parseable
        # frontmatter carrying a non-empty `type`. Anything else is not a concept.
        if not note.meta or not str(note.meta.get("type", "")).strip():
            rep.warn(f"{note.relpath}: no non-empty `type` — not a conformant OKF concept, skipped")
            skipped += 1
            continue

        fields = from_okf(note.meta, note.body, note.relpath)
        # The file keeps the producer's own path and name so the bundle's
        # internal links keep resolving; the *id* is minted to the vault's
        # grammar. Filename and id are separate concerns.
        rel = safe_relpath(note.relpath).replace(os.sep, "/")
        output = os.path.join(dest_rel, rel).replace(os.sep, "/")
        # atomic_create_files performs the canonical NFC+casefold gate too. This
        # earlier check names the two producer paths whose sanitization collided.
        collision = unicodedata.normalize("NFC", output).casefold()
        if collision in output_origins:
            rep.error("OKF import refused before writes: sanitized output collision: "
                      f"{output_origins[collision]} and {note.relpath} -> {output}")
            tree.close()
            return rep
        output_origins[collision] = note.relpath
        nid = f"source-{slugify(fields['x_okf_title'])}"
        if nid in taken:                       # collide with vault canon → suffix, never overwrite
            n = 2
            while f"{nid}-{n}" in taken:
                n += 1
            nid = f"{nid}-{n}"
        taken.add(nid)

        meta = {"id": nid, **fields, "created": today, "updated": today,
                "captured_at": today,
                "original_location": fields.get("original_location", note.relpath),
                "x_okf_bundle": os.path.basename(bundle.rstrip(os.sep)),
                "x_okf_path": note.relpath.replace("\\", "/")}
        # Sources are immutable captures: the concept's body is written through
        # byte-for-byte. Annotation happens below the line, later, by ingest.
        writes[output] = ("---\n"
                          + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True,
                                           default_flow_style=False)
                          + "---\n\n" + (note.body or "").lstrip("\n")).encode("utf-8")

    if not writes:
        rep.error("OKF import refused before writes: zero conformant concept documents; "
                  "no destination directory was created")
        tree.close()
        return rep

    try:
        atomic_create_files(root, writes, read_only_inputs=(bound,))
    except (OSError, SafePathError) as exc:
        rep.error(f"OKF import transaction refused or rolled back: {exc}")
        tree.close()
        return rep
    tree.close()

    rep.info["imported_to"] = dest_rel
    rep.info["sources_written"] = len(writes)
    if skipped:
        rep.info["skipped_non_concepts"] = skipped
    rep.info["next"] = ("run the ingest-and-connect capability on these sources — they are "
                        "draft/unverified evidence until it dedupes, attributes, extracts, "
                        "connects, and clears the promotion gate. Never promote by accumulation.")
    return rep
