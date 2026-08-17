"""vault.okf-check — verify a tree against Google's Open Knowledge Format.

**Conformance is three rules, and they are identical in v0.1 and v0.2**: every
non-reserved `.md` file in the tree carries a parseable YAML frontmatter block;
every frontmatter block carries a non-empty `type`; and every reserved filename
(`index.md`, `log.md`) follows the index/log structure when present (v0.1 §9 →
v0.2 §11, with the referenced sections renumbered §6/§7 → §8/§9). Both versions
forbid rejecting a bundle for missing optional fields, unknown types, unknown
keys, broken links, or a missing index.

That is why one code path checks both, and why the version is named in the report
rather than left to be inferred: a tree that passes is conformant with the version
this command says it checked, and with no other.

**Rule 3 is checked here for the first time.** Through v1.26.0 this command
skipped the reserved files outright and still printed a conformance verdict — a
verdict for two rules out of three, worded as though it covered all of them. Only
the structural MUSTs are enforced (frontmatter is permitted in a bundle-root
`index.md` and only for `okf_version`; a `log.md` date heading is ISO 8601), since
the rest of §8/§9 is written as SHOULD and MAY.

`--okf-version 0.2` (the default) adds **advisory** shape checks over the v0.2
lifecycle, trust, and provenance families (§5–§10) — a `sources` entry with no
`resource`, a `generated` with no `by`, a `status` outside the vocabulary, an
`Attested Computation` with no `runtime`, a field the spec superseded. They are
warnings, never errors, because §11 is explicit that a consumer MUST NOT reject a
bundle over an optional family. A warning here means "a v0.2 consumer will read
less than you meant", not "this is not OKF".

This command checks exactly the tree it is pointed at — no built-in exclusions,
mirroring the spec, which defines none. Point it anywhere with an explicit target
— an export produced by `okf-export` (which runs this check, at its own declared
version, on every bundle it writes), a foreign bundle, any directory.

**The default scope is the whole knowledge surface: the manifest's content
directories AND the content of every installed pack.** Through v1.53.0 it was the
content directories alone, and on a pack-heavy vault that was a verdict about
almost nothing. Measured on a live role-pack instance at the release that fixed
it: **9 concepts checked, 236 more sitting in `Packs/pmm/` and never looked at** —
the buyer's entire messaging, enablement, intelligence and wiki corpus, outside a
"CONFORMANT" verdict they were sold as covering it. The scope is now reported in
the verdict itself, per file count and per tree, because a conformance claim that
does not say what it covered is the defect, not the cure (DEC-109).

What is still outside, and why: pack **machinery** (its capabilities, agents,
workflows, tests, and vendored third-party payload) and the pack's own root files
— excluded exactly as the vault's own `System/` and root files are, for the same
reason. `lib/vaultpaths.pack_content_trees` derives the covered set as the
complement of that bounded, product-defined list, so pack content folders are in
scope by construction rather than by enumeration.

Coverage is not canon. Nothing here enters the vault's id space: `validate`,
`links` and `dupes` still prune `Packs/` (DEC-061/DEC-067), a pack's `README.md`
still never collides with the vault's, and this command builds no index at all —
it reads each file alone against three rules, so there is no namespace to merge.

Read-only; writes nothing. Nonzero exit on any violation, so it can gate an export
or a CI run. This is the verifiable half of the product's compatibility claim:
"run one command and check it yourself."
"""
from __future__ import annotations
import os
import re

import yaml

# One definition of OKF's reserved filenames and vocabularies, shared with export/import.
from lib.okf import (DATE, OKF_STATUS, OKF_VERSION, OKF_VERSIONS, RESERVED,
                     valid_actor, verified_events)
from lib.report import Report

# The two findings a vault's own folders raise, worded once. Both are the same
# fact from two directions: `status` and `sources` are AI OS field names that OKF
# v0.2 also claims, with a different vocabulary and a different shape. Conformance
# is unaffected (§11), but a foreign v0.2 consumer reading the folders raw will
# misread them — which is exactly what `okf-export` exists to prevent, since it
# maps both on the way out.
STATUS_VOCAB = ("`status` is outside §5.4's vocabulary (draft | stable | deprecated) — in a "
                "vault's own folders this is AI OS's `status`, which shares the name; "
                "`aios okf-export` maps it")
SOURCES_SHAPE = ("`sources` is not a list of §5.1 entries — in a vault's own folders this is "
                 "AI OS's `sources` id-list, which shares the name; `aios okf-export` remaps it")
SOURCES_RESOURCE = "a `sources` entry has no `resource`, which §5.1 requires within an entry"

# RESERVED (OKF §8/§9: directory listing and update history) is exempt from the
# concept-document rules (frontmatter + type) and carries its own, rule 3.

LOG_DATE_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _check_reserved(path: str, rel: str, is_bundle_root: bool, rep: Report) -> bool:
    """Conformance rule 3: a reserved file follows §8 (`index.md`) or §9
    (`log.md`). Only the MUSTs are enforced — the rest of both sections is SHOULD
    and MAY, and a gate that promotes guidance to law is a gate that lies in the
    other direction."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        rep.error(f"{rel}: unreadable ({exc})")
        return False
    ok = True
    if os.path.basename(path) == "index.md":
        # §8: "Index files contain no frontmatter, with one exception: a
        # bundle-root index.md MAY carry an okf_version key."
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end == -1:
                rep.error(f"{rel}: frontmatter block never closes")
                return False
            if not is_bundle_root:
                rep.error(f"{rel}: an `index.md` below the bundle root carries frontmatter — "
                          f"§8 permits it only in the bundle-root index, and only for `okf_version`")
                ok = False
            else:
                try:
                    meta = yaml.safe_load(text[3:end]) or {}
                except yaml.YAMLError as exc:
                    rep.error(f"{rel}: frontmatter is not parseable YAML ({exc})")
                    return False
                extra = sorted(k for k in (meta if isinstance(meta, dict) else {})
                               if k != "okf_version")
                if extra:
                    rep.error(f"{rel}: the bundle-root `index.md` frontmatter carries "
                              f"{', '.join(repr(k) for k in extra)} — §8/§12 permit `okf_version` "
                              f"and nothing else")
                    ok = False
        if not re.search(r"^#{1,6}\s+\S", text, re.MULTILINE):
            rep.warn(f"{rel}: no headings — §8 describes an index as one or more sections, "
                     f"each grouping concepts under a heading")
    else:   # log.md — §9
        for heading in LOG_DATE_HEADING.findall(text):
            if not DATE.match(heading.strip()):
                rep.error(f"{rel}: log date heading '{heading}' is not the ISO 8601 "
                          f"`YYYY-MM-DD` form §9 requires")
                ok = False
    return ok


def _advise(rel: str, meta: dict, text: str, found: dict) -> int:
    """The v0.2 family shape checks (§5–§10). Warnings only — §11 forbids
    rejecting a bundle for an optional family.

    Findings are collected by kind rather than reported per file. A tree of a
    thousand notes that all use `status` in a different vocabulary is **one**
    fact about the tree, and a thousand identical warnings is how a real finding
    becomes scrollback. Returns the number raised."""
    n = 0

    def warn(kind, detail=""):
        nonlocal n
        n += 1
        bucket = found.setdefault(kind, {"count": 0, "examples": []})
        bucket["count"] += 1
        if len(bucket["examples"]) < 3:
            bucket["examples"].append(rel + (f" ({detail})" if detail else ""))

    # §5.1 provenance
    srcs = meta.get("sources")
    if srcs is not None:
        if not isinstance(srcs, list):
            warn(SOURCES_SHAPE)
        else:
            for i, entry in enumerate(srcs):
                if not isinstance(entry, dict):
                    warn(SOURCES_SHAPE, f"sources[{i}]")
                elif not str(entry.get("resource") or "").strip():
                    warn(SOURCES_RESOURCE, f"sources[{i}]")
    if meta.get("usage_window") is not None and not isinstance(meta["usage_window"], dict):
        warn("`usage_window` is not a `{from, to}` mapping (§5.1)")

    # §5.2 trust
    gen = meta.get("generated")
    if gen is not None:
        if not isinstance(gen, dict):
            warn("`generated` is not a `{by, at}` mapping (§5.2)")
        elif not str(gen.get("by") or "").strip():
            warn("`generated` has no `by`, which §5.2 requires within it")
        elif not valid_actor(gen.get("by")):
            warn("`generated.by` does not follow the actor convention (§7: `human:<id>`, "
                 "`process:<id>`, `<producer>/<version>`) — a consumer that classifies trust "
                 "off the `human:` prefix reads it as machine work", str(gen.get("by")))
    ver = meta.get("verified")
    if ver is not None:
        events = verified_events(ver)
        if not events:
            warn("`verified` is neither a `{by, at}` mapping nor a list of them (§5.2)")
        for i, e in enumerate(events):
            if not str(e.get("by") or "").strip() or not str(e.get("at") or "").strip():
                warn("a `verified` event is missing `by` or `at` (§5.2)", f"verified[{i}]")
            elif not valid_actor(e.get("by")):
                warn("a `verified` event's `by` does not follow the actor convention (§7)",
                     str(e.get("by")))

    # §5.4 / §5.5 lifecycle
    st = meta.get("status")
    if st is not None and str(st) not in OKF_STATUS:
        warn(STATUS_VOCAB, f"status: {st}")
    sa = meta.get("stale_after")
    if sa is not None and not DATE.match(str(sa).strip()):
        warn("`stale_after` is not the absolute `YYYY-MM-DD` date §5.5 fixes", f"stale_after: {sa}")

    # §10 attested computation
    if str(meta.get("type") or "").strip() == "Attested Computation":
        if not str(meta.get("runtime") or "").strip():
            warn("`type: Attested Computation` without `runtime`, which §10.2 requires for "
                 "this type — an executor cannot know how to run it")
        if not meta.get("computation") and "# Computation" not in text:
            warn("`type: Attested Computation` with neither a `computation` path nor a "
                 "`# Computation` body section (§10.3)")

    # §13.1 superseded forms — readable, but a v0.2 consumer only reaches them by fallback
    if meta.get("timestamp") is not None and gen is None:
        warn("`timestamp` was superseded by `generated: {by, at}` in v0.2 (§13.1) — readable "
             "only through the legacy fallback")
    if "\n# Citations" in text or text.startswith("# Citations"):
        warn("a body `# Citations` list was superseded by the `sources` field in v0.2 (§13.1)")
    return n


def _check_file(path: str, rel: str, rep: Report, version: str, found: dict) -> tuple:
    """Apply OKF's two concept-document rules to one file, plus (under v0.2) the
    advisory family checks. Returns (conformant, advisories)."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        rep.error(f"{rel}: unreadable ({exc})")
        return False, 0
    if not text.startswith("---"):
        rep.error(f"{rel}: no YAML frontmatter block (OKF requires one on every concept)")
        return False, 0
    end = text.find("\n---", 3)
    if end == -1:
        rep.error(f"{rel}: frontmatter block never closes")
        return False, 0
    try:
        meta = yaml.safe_load(text[3:end])
    except yaml.YAMLError as exc:
        rep.error(f"{rel}: frontmatter is not parseable YAML ({exc})")
        return False, 0
    if not isinstance(meta, dict):
        rep.error(f"{rel}: frontmatter is not a YAML mapping")
        return False, 0
    if not str(meta.get("type") or "").strip():
        rep.error(f"{rel}: missing or empty `type` (OKF's one required field)")
        return False, 0
    advisories = _advise(rel, meta, text[end:], found) if version == "0.2" else 0
    return True, advisories


def _declared_version(base: str):
    """§12: a bundle MAY declare the version it targets with `okf_version` in its
    root `index.md` frontmatter — the only place frontmatter is permitted there."""
    path = os.path.join(base, "index.md")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    try:
        meta = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return None
    if isinstance(meta, dict) and meta.get("okf_version") is not None:
        return str(meta["okf_version"]).strip()
    return None


def run(root, args, rep: Report):
    version = str(getattr(args, "okf_version", None) or OKF_VERSION)
    if version not in OKF_VERSIONS:
        rep.error(f"unknown OKF version '{version}' — this build checks against "
                  f"{' or '.join(OKF_VERSIONS)}")
        return rep

    if getattr(args, "target", None):
        target = os.path.abspath(args.target)
        if not os.path.isdir(target):
            rep.error(f"not a directory: {args.target}")
            return rep
        trees = [(target, os.path.basename(target) or target)]
        rep.info["scope"] = args.target
        packs = []
    else:
        from lib.vaultpaths import (PACK_MACHINERY_DIRS, content_dirs,
                                    installed_pack_ids, pack_content_trees)
        names = content_dirs(root)
        if not names:
            rep.error("no content directories declared in SYSTEM-MANIFEST.yaml and no target given")
            return rep
        trees = [(os.path.join(root, n), n) for n in names if os.path.isdir(os.path.join(root, n))]
        packs = installed_pack_ids(root)
        pack_trees = pack_content_trees(root)
        trees += pack_trees
        # The scope is part of the verdict, not a footnote to it: a reader has no
        # other way to know whether "CONFORMANT" covered nine files or nine hundred.
        # Filled in below with the real per-pack counts; claimed here only to fix
        # its position at the top of the report.
        rep.info["scope"] = ""
        scope_prefix = (
            "the vault's knowledge layer (manifest content directories: "
            + ", ".join(n for n in names if os.path.isdir(os.path.join(root, n)))
            + ") + the content of "
            + (f"{len(packs)} installed pack{'s' if len(packs) != 1 else ''}"
               if packs else "0 installed packs"))
        scope_suffix = ("; excludes System/, the vault's root files, and each pack's machinery ("
                        + ", ".join(PACK_MACHINERY_DIRS) + ") and root files")

    checked = conformant = reserved = reserved_bad = advisories = 0
    per_tree: dict = {}
    found: dict = {}
    for base, label in trees:
        declared = _declared_version(base)
        if declared:
            rep.info[f"declared_okf_version ({label})"] = declared
            if declared != version:
                rep.warn(f"{label}: the bundle declares `okf_version: \"{declared}\"` (§12) but "
                         f"this run checked it against v{version} — pass --okf-version {declared} "
                         f"to check it against what it claims")
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            for fname in sorted(filenames):
                if not fname.endswith(".md"):
                    continue
                if fname in RESERVED:
                    reserved += 1
                    rel = os.path.join(label, os.path.relpath(os.path.join(dirpath, fname), base))
                    if not _check_reserved(os.path.join(dirpath, fname), rel,
                                           os.path.abspath(dirpath) == os.path.abspath(base), rep):
                        reserved_bad += 1
                    continue
                path = os.path.join(dirpath, fname)
                rel = os.path.join(label, os.path.relpath(path, base))
                checked += 1
                per_tree[label] = per_tree.get(label, 0) + 1
                ok, adv = _check_file(path, rel, rep, version, found)
                conformant += 1 if ok else 0
                advisories += adv

    # One warning per finding kind, with a count and up to three examples.
    for kind in sorted(found):
        bucket = found[kind]
        rep.warn(f"v0.2 advisory ({bucket['count']}x, §11: not a conformance failure): {kind} "
                 f"— e.g. {', '.join(bucket['examples'])}")

    if not getattr(args, "target", None):
        # Now that the counts are real, say what each pack actually contributed.
        # A pack of pure machinery contributes 0, and saying so is the point: the
        # reader learns the pack was looked at, not skipped.
        per_pack = {p: 0 for p in packs}
        for _, label in pack_trees:
            per_pack[label.split("/")[1]] += per_tree.get(label, 0)
        rep.info["scope"] = (scope_prefix
                             + (" (" + ", ".join(f"{p}: {n}" for p, n in per_pack.items()) + ")"
                                if per_pack else "")
                             + scope_suffix)

    rep.info["okf_version"] = version
    rep.info["concepts_checked"] = checked
    rep.info["conformant"] = conformant
    if len(trees) > 1:
        # Per tree, so "236 of the 245 are the pack's" is readable off the report
        # rather than inferred. Empty trees are named too — a folder that
        # contributed nothing is a fact about the coverage.
        rep.info["coverage_by_tree"] = ", ".join(f"{label}: {per_tree.get(label, 0)}"
                                                 for _, label in trees)
    if reserved:
        rep.info["reserved_files_checked"] = f"{reserved - reserved_bad}/{reserved} (rule 3)"
    if version == "0.2":
        rep.info["v0_2_family_advisories"] = advisories
    if checked and rep.ok:
        # The verdict carries its own scope. "CONFORMANT" alone is the claim that
        # was true-but-misleading on a pack-heavy vault (DEC-109's lesson).
        where = ("this tree" if getattr(args, "target", None) else
                 "the vault's knowledge layer"
                 + (f" and {len(packs)} installed pack{'s' if len(packs) != 1 else ''} "
                    f"({', '.join(packs)})" if packs else ""))
        rep.info["verdict"] = (f"CONFORMANT — {checked} concept{'s' if checked != 1 else ''} "
                               f"across {where}, valid OKF v{version}")
    elif not checked:
        rep.warn("no markdown concepts found in the target tree")
    return rep
