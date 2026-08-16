"""vault.okf-export — emit a scope of the vault as an Open Knowledge Format bundle.

OKF (Google, Apache-2.0) is a subset of what AI OS already carries, so this is an
emitter, not a conversion: the standard fields map across and the AI OS superset
rides as extra keys, which the spec explicitly permits and asks consumers to
preserve. Emit the standard; do not inherit its weaknesses.

**The target version is explicit, never implied.** `--okf-version 0.2` (the
default, and the current published spec) emits the v0.2 lifecycle, trust, and
provenance families; `--okf-version 0.1` emits the older shape, unchanged, for a
consumer that has not moved. The chosen version is written into the bundle three
times — the root `index.md` frontmatter (§12's version marker), the `okf.yaml`
marker, and the index prose — and the bundle is self-verified by `okf-check`
against *that* version before this command reports success. The field-by-field
mapping and what it deliberately declines to emit are in `lib/okf.py`.

**Privacy is fail-closed and stricter than `aios search`, deliberately.**
`search`'s `permitted()` answers "may *this runtime* read this?" — a question
whose answer depends on the runtime profile. An export asks a different question:
"may this **leave the vault** in a portable artifact?" A local runtime
(`hosted: false`) may legitimately read `local-only` content, but writing that
content into a bundle built for exchange would launder a hard boundary through a
profile flag. So `local-only` never exports, on any profile, and `private` never
exports without review (Privacy §3: material for external use is the human's
call). The two filters answer different questions and must not be shared.

The v0.2 `sources` field extends that fence to *references*. A vault id is a slug
of its note's title, so a provenance entry pointing at a record the filter
excluded would carry that record's title out inside a field advertised as
provenance. Excluded references are withheld and counted in the report; they never
reach the bundle.
"""
from __future__ import annotations

import datetime
import os
import re

import yaml

from lib.frontmatter import Note, iter_markdown
from lib.okf import (BUNDLE_MARKER, ID_FIELDS, ID_LIST_FIELDS, OKF_FIELDS,
                     OKF_SPEC_URL, OKF_VERSION, OKF_VERSIONS, slugify, title_of,
                     to_okf, to_stale_after, valid_actor)
from lib.report import Report
from lib.safepaths import (SafePathError, atomic_replace_tree,
                           preflight_contained_regular_files, safe_tree_digest)
from lib.vaultpaths import manifest, rel_folder

# Governance vocabularies, restated here rather than imported from `validate`:
# an unrecognised value must fail closed (DEC-066), and this filter must keep
# working even if the schema file is unreadable.
CLASSIFICATIONS = ("public", "internal", "private", "restricted")
AI_USES = ("allowed", "local-only", "prohibited")
SYNCS = ("allowed", "local-only")   # DEC-092 storage boundary

# Classifications an export may carry without a human review step (Privacy §3).
EXPORTABLE_CLASSIFICATIONS = ("public", "internal")

LOCAL_ONLY_DIR = "local only"   # DEC-065: the folder IS the marking

# `index.md` and `log.md` are OKF's reserved filenames — a concept may never
# take one, or a consumer reads it as the bundle's index.
RESERVED_STEMS = {"index", "log"}

# The full `status` vocabulary (vocabularies.yaml), restated for the same reason
# the governance vocabularies above are: an unrecognised value must fail closed.
STATUSES = ("draft", "active", "review-due", "stale", "superseded", "archived")

# Never user truth (DEC-018), never canon (status), never evidence-in-waiting.
NON_CANON_STATUS = ("draft", "stale", "superseded", "archived")


def exportable(meta: dict, relpath: str) -> bool:
    """May this record leave the vault inside a portable bundle?

    Fail-closed at every branch. Independent of the runtime profile by design —
    see the module docstring."""
    # DEC-065: a "Local Only" path segment is a privacy marking. Unlike
    # `search.permitted()`, it excludes on EVERY profile: the bundle travels.
    if any(seg.strip().lower() == LOCAL_ONLY_DIR
           for seg in relpath.replace("\\", "/").split("/")):
        return False

    # Structural signposts (`_ABOUT.md`) and templates are the vault's own
    # furniture, not the user's knowledge — `validate` already treats a leading
    # underscore as the marker for this, so the convention is reused, not reinvented.
    base = os.path.basename(relpath)
    if base.startswith("_") or "Templates" in relpath.replace("\\", "/").split("/"):
        return False

    cls = meta.get("classification", "internal")
    use = meta.get("ai_use", "allowed")
    syn = meta.get("sync", "allowed")
    # DEC-066: present-but-unrecognised fails closed. An absent field still means
    # the default (DEC-026: what enters the vault is the user's choice).
    if cls not in CLASSIFICATIONS or use not in AI_USES or syn not in SYNCS:
        return False
    # DEC-092: `sync: local-only` is the storage boundary — "never leaves this
    # machine". A bundle is built for exchange; writing the content into one
    # would launder that boundary exactly like the profile-flag case above.
    if syn != "allowed":
        return False
    if cls not in EXPORTABLE_CLASSIFICATIONS:
        return False        # private and restricted both stop here
    if use != "allowed":
        return False        # local-only and prohibited never travel
    if meta.get("file_class") in ("example", "generated"):
        return False        # never retrievable as user truth (DEC-018)
    # DEC-066 again, and it was missing here: testing `status` against the
    # non-canon *blacklist* alone let an unrecognised value ("Active", "final")
    # through, and v0.2's mapping would then have laundered it into
    # `status: stable`. A status the vocabulary does not know is not an active one.
    st = meta.get("status")
    if st not in (None, "") and str(st) not in STATUSES:
        return False
    if str(meta.get("status", "")) in NON_CANON_STATUS:
        return False        # staging is not knowledge (Principle 26)
    return True


def _dump(meta: dict, version: str) -> str:
    """OKF frontmatter: the standard fields first, in the spec's order for the
    target version, then the AI OS superset. Ordering is presentation only — but a
    reader opening a bundle should meet the standard, not our extras."""
    fields = OKF_FIELDS[version]
    ordered = {k: meta[k] for k in fields if k in meta and meta[k] is not None}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    return yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True,
                          default_flow_style=False)


def _note_from_bound_bytes(path: str, relpath: str, raw: bytes) -> Note:
    """Parse the bytes bound by safepaths, never the earlier pathname read."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return Note(path, relpath, {}, "", f"unreadable: {exc}")
    meta, body = {}, text
    if text.startswith("---\n") or text.startswith("---\r\n"):
        match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.DOTALL)
        if not match:
            return Note(path, relpath, {}, text, "unterminated frontmatter fence")
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            return Note(path, relpath, {}, text, f"frontmatter YAML error: {exc}")
        if not isinstance(meta, dict):
            return Note(path, relpath, {}, text, "frontmatter is not a mapping")
        body = text[match.end():]
    return Note(path, relpath, meta, body)


def run(root, args, rep: Report):
    scope = getattr(args, "target", None) or "knowledge"
    version = str(getattr(args, "okf_version", None) or OKF_VERSION)
    if version not in OKF_VERSIONS:
        rep.error(f"unknown OKF version '{version}' — this build emits "
                  f"{' or '.join(OKF_VERSIONS)}")
        return rep
    author = getattr(args, "author", None)
    if author and not valid_actor(author):
        rep.error(f"--author '{author}' does not follow the OKF actor convention (§7): "
                  f"human:<id>, process:<id>, or <producer>/<version>")
        return rep
    if author and version == "0.1":
        rep.error("--author sets OKF v0.2's `generated.by`; v0.1 has no `generated` "
                  "field. Drop --author or emit v0.2.")
        return rep

    try:
        scope_rel = rel_folder(root, scope, None)
    except Exception:
        scope_rel = None
    if not scope_rel:
        rep.error(f"unknown scope '{scope}' — name a folder id from "
                  f"System/Registries/folder-registry.yaml (e.g. knowledge, projects, sources)")
        return rep
    scope_dir = os.path.join(root, scope_rel)
    if not os.path.isdir(scope_dir):
        rep.error(f"scope '{scope}' resolves to '{scope_rel}', which does not exist")
        return rep

    source_batch = None
    try:
        scope_identity = safe_tree_digest(scope_dir, markdown_only=True)
        discovered = list(iter_markdown(root))
        source_batch = preflight_contained_regular_files(
            root, [note.path for note in discovered], require_writable=False
        )
        bound = source_batch.read_bytes()
        all_notes = [
            _note_from_bound_bytes(note.path, note.relpath, bound[note.path])
            for note in discovered
        ]
    except (OSError, SafePathError) as exc:
        if source_batch is not None:
            source_batch.close()
        rep.error(f"source tree is unsafe or changed during export: {exc}")
        return rep

    outputs_rel = rel_folder(root, "outputs", "40 Outputs")   # DEC-067: never the literal name
    bundle_rel = os.path.join(outputs_rel, f"okf-{slugify(scope)}")

    # Pass 1 — decide the bundle's membership before writing any of it, because a
    # v0.2 `sources` entry has to know whether the record it points at is in this
    # bundle, merely allowed to travel, or excluded by the privacy filter.
    selected, names, may_travel = [], {}, set()
    for note in all_notes:
        if note.error or not note.meta or not note.meta.get("id"):
            continue
        nid = str(note.meta["id"])
        if exportable(note.meta, note.relpath):
            may_travel.add(nid)
        else:
            continue
        if not note.relpath.startswith(scope_rel + os.sep):
            continue
        if not str(note.meta.get("type") or "").strip():
            continue          # OKF's one hard requirement — a typeless doc is not a concept

        stem = slugify(title_of(note), fallback=slugify(nid))
        if stem in RESERVED_STEMS:
            stem = f"{stem}-concept"      # never collide with a reserved filename
        if stem in names:                 # distinct notes, same title → stable suffix
            names[stem] += 1
            stem = f"{stem}-{names[stem]}"
        else:
            names[stem] = 1
        selected.append((note, stem))

    in_bundle = {str(n.meta["id"]): (stem, title_of(n), n.meta.get("updated"))
                 for n, stem in selected}
    withheld = {"count": 0}

    def sources_for(meta: dict) -> list:
        """An AI OS `sources` id-list → OKF v0.2 `sources` entries (§5.1).

        Only sources that are **in this bundle** become entries, because only
        those give `resource` something a consumer can follow. §5.1 allows a
        `resource` the consumer cannot follow only when it is a population or
        scope descriptor ("all queries in project X"); a dangling id from another
        vault is neither, and dressing one up as provenance is the kind of
        stronger-than-the-evidence claim this build exists to remove. The
        remaining ids stay in `x_aios_sources` under their own name."""
        out = []
        for sid in meta.get("sources") or []:
            sid = str(sid)
            if sid in in_bundle:
                stem, title, updated = in_bundle[sid]
                entry = {"id": sid, "resource": f"/{stem}.md", "title": title}
                last = to_stale_after(updated)
                if last:
                    entry["last_modified"] = last
                out.append(entry)
        return out

    def travel_filter(okf: dict) -> None:
        """Strip vault ids that may not leave, from every field that holds one.

        A vault id is a slug of its record's title, so `entities: [person-jane-doe]`
        or `contradicts: [note-the-thing-we-got-wrong]` carries the title of a
        record out of the vault even when the record itself was excluded. The
        content fence has always held; this is the same fence applied to the
        references, across all seven id-list fields rather than the one v0.2
        happens to have renamed."""
        # Under v0.2 the `sources` key holds OKF entries built from in-bundle
        # records only, which are travel-safe by construction; the raw id-list
        # moved to `x_aios_sources` and is filtered in its place.
        keys = [("x_aios_sources" if (k == "sources" and version == "0.2") else k)
                for k in ID_LIST_FIELDS]
        for key in keys:
            vals = okf.get(key)
            if not isinstance(vals, list):
                continue
            kept = [v for v in vals if str(v) in may_travel]
            withheld["count"] += len(vals) - len(kept)
            if kept:
                okf[key] = kept
            else:
                okf.pop(key, None)
        for key in ID_FIELDS:
            val = okf.get(key)
            if val not in (None, "") and str(val) not in may_travel:
                withheld["count"] += 1
                okf.pop(key, None)

    def build_bundle(bundle: str):
        concepts, max_cls = [], "public"
        for note, stem in selected:
            okf = to_okf(note, version=version, author=author, sources_for=sources_for)
            travel_filter(okf)
            with open(os.path.join(bundle, stem + ".md"), "w", encoding="utf-8") as fh:
                fh.write("---\n" + _dump(okf, version) + "---\n\n"
                         + (note.body or "").lstrip("\n"))
            concepts.append((stem, okf["title"], okf.get("description", "")))
            cls = note.meta.get("classification", "internal")
            if EXPORTABLE_CLASSIFICATIONS.index(cls) > \
                    EXPORTABLE_CLASSIFICATIONS.index(max_cls):
                max_cls = cls

        lines = [f"---\nokf_version: \"{version}\"\n---", "",
                 f"# {manifest(root)['system']['name']} — {scope_rel}", "",
                 f"An Open Knowledge Format v{version} bundle of "
                 f"{len(concepts)} concept(s).", ""]
        for stem, title, desc in sorted(concepts, key=lambda c: c[1].lower()):
            lines.append(f"- [{title}](/{stem}.md)" + (f" — {desc}" if desc else ""))
        with open(os.path.join(bundle, "index.md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

        marker = {
            "okf_version": version,
            "okf_spec": OKF_SPEC_URL,
            "generated_by": f"aios okf-export ({manifest(root)['system']['system_version']})",
            "generated_at": datetime.datetime.now(datetime.timezone.utc)
                            .replace(microsecond=0).isoformat(),
            "scope": scope,
            "source_folder": scope_rel,
            "concepts": len(concepts),
            "classification": max_cls,
            "approval": "none",
        }
        if version == "0.2":
            marker["generated_actor"] = author or "not asserted"
            marker["verified_events"] = (
                "none — this producer records a verification grade, not verification events"
            )
        with open(os.path.join(bundle, BUNDLE_MARKER), "w", encoding="utf-8") as fh:
            yaml.safe_dump(marker, fh, sort_keys=False, allow_unicode=True)
        return concepts, max_cls

    def validate_bundle(bundle: str) -> None:
        from cmd import okfcheck
        chk = Report("okf-check")
        okfcheck.run(
            root, type("_Target", (), {"target": bundle, "okf_version": version})(), chk
        )
        if not chk.ok:
            raise SafePathError(
                "exported bundle failed okf-check: " + "; ".join(chk.errors)
            )

    def reprove_sources() -> None:
        if safe_tree_digest(scope_dir, markdown_only=True) != scope_identity:
            raise SafePathError("source scope changed during export")
        source_batch.reprove()

    try:
        built, _result = atomic_replace_tree(
            root, bundle_rel, build_bundle, validate_bundle,
            reprovers=(reprove_sources,), existing_marker=BUNDLE_MARKER,
        )
        concepts, max_cls = built
    except (OSError, SafePathError) as exc:
        rep.error(str(exc))
        return rep
    finally:
        source_batch.close()

    rep.info["okf_conformance"] = (
        f"CONFORMANT (OKF v{version}) — verified by aios okf-check"
    )

    rep.info["okf_version"] = version
    rep.info["bundle"] = bundle_rel
    rep.info["concepts_exported"] = len(concepts)
    rep.info["classification"] = max_cls
    if version == "0.2":
        rep.info["generated_actor"] = author or "not asserted (no `generated`; legacy `timestamp` emitted)"
        if not author:
            rep.warn("no --author given, so no `generated` field: v0.2 requires `generated.by`, "
                     "and this vault does not record who wrote a note. The last-change time "
                     "rides as the legacy `timestamp` (§13.1's sanctioned fallback). Pass "
                     "--author human:<id> to assert it.")
    if withheld["count"]:
        rep.info["id_refs_withheld"] = withheld["count"]
        rep.warn(f"{withheld['count']} reference(s) to records the privacy filter excluded were "
                 f"withheld from the bundle — a vault id is a slug of its record's title, so a "
                 f"reference carries the title even when the record stays home")
    if not concepts:
        rep.warn(f"no exportable concepts in '{scope_rel}' — a scope with only draft, private, "
                 f"or local-only records exports nothing, which is the filter working")
    # Privacy §3: the vault decides what MAY travel; the human decides what DOES.
    rep.warn(f"{bundle_rel} is classified '{max_cls}' and is NOT approved for publication — "
             f"review it before sharing (Privacy §2/§3).")
    return rep
