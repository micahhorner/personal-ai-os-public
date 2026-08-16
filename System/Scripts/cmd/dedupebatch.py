"""vault.dedupe-batch — near-duplicate detection ACROSS an incoming batch.

Not to be confused with `aios dupes`, which is the **canon** checker: it asks
whether two records already IN the vault collide on id, title, or alias. This
command asks a different question that nothing else asked — **do the files
arriving together repeat each other?** Material does not arrive one clean file
at a time. It arrives as a folder of overlapping exports, because that is what
re-exporting, re-pasting and tab-hoarding produce.

Proven live (2026-07-15, four documents handed over as one corpus): one file was
**97% a paste-up** of two of its siblings — thousands of paragraphs reproduced
under literal `Tab 1` / `Tab 2` markers. None of the four shared a title, an id,
or an alias, so `dupes` passed them cleanly and `safe-write` step 1 passed them
cleanly, because both compare a capture to CANON and neither compares captures
to each other.

**The damage is not wasted disk — it is manufactured corroboration.** An
extraction pass reading four "independent" sources finds the same claim in three
of them and promotes it as triply-attested. It was reached once and pasted
twice. That is a knowledge-integrity failure shaped exactly like evidence, and it
lands in the layer the whole system exists to protect.

Design constraints, all of them deliberate:

- **A report, never an action.** Percentages are printed; nothing is discarded,
  moved, merged, or archived. Which file is the fuller record is a judgment the
  human owns — in the proven case the near-duplicate was the *superset*, so the
  intuitive "keep the biggest" heuristic would have been right by accident and
  wrong in general.
- **No classification.** It reports "88% of A's paragraphs also appear in B",
  never "A is a duplicate". Near-duplication is a spectrum and the verdict is the
  human's.
- **Short paragraphs are excluded from the matrix and counted separately.**
  Headers, signatures, "Yes.", and stage directions repeat across unrelated
  documents; letting them into the matrix makes boilerplate read as
  corroboration, which is the exact failure this command exists to prevent.
- **Hash-exact after normalization only.** No semantic or fuzzy similarity: cheap,
  deterministic, and explainable — a human can check any claimed match by eye.
- **Bodies stay immutable.** `--annotate` writes the overlap map into
  frontmatter (`x_overlap_*`) on the files still present in the batch; not one
  byte of any body changes.

Read-only by default. Content never reaches stdout: the report carries counts,
percentages, and file paths — never paragraph text — so a batch of Local Only
captures can be measured by a runtime that may not read them.
"""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata

from lib.report import Report
from lib.protectedwrites import ProtectedTargetError, guard_ordinary_write_set
from lib.safepaths import SafePathError, preflight_contained_regular_files

# Below this length a paragraph is boilerplate-shaped: a heading, a signature,
# a one-word answer. Counted, reported, and kept OUT of the overlap matrix.
SHORT_PARAGRAPH_WORDS = 8

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", "System"}

_WORD = re.compile(r"[0-9A-Za-z][0-9A-Za-z'’\-]*")


def normalize(text):
    """Normalization for comparison only — the file on disk is never touched.

    Unicode-folded, typographic substitutions undone (Word and the chat exporters
    disagree about quotes and dashes for the same pasted sentence), punctuation
    kept but whitespace collapsed, case folded. Deliberately NOT aggressive
    beyond that: stripping punctuation entirely would collide distinct sentences
    and inflate the very overlap the command is measuring.
    """
    t = unicodedata.normalize("NFKC", text or "")
    t = (t.replace("‘", "'").replace("’", "'")
          .replace("“", '"').replace("”", '"')
          .replace("–", "-").replace("—", "-")
          .replace(" ", " ").replace("​", ""))
    return re.sub(r"\s+", " ", t).strip().lower()


def strip_frontmatter(text):
    """Frontmatter is the vault's own metadata about a capture, not the capture.
    Two files sharing `type: source` is not evidence of anything."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    return text[end + 4:] if end != -1 else text


def paragraphs(text):
    """Blank-line-separated blocks. Returns (long, short) as normalized strings —
    long ones feed the matrix, short ones are counted and reported."""
    body = strip_frontmatter(text)
    long_p, short_p = [], []
    for block in re.split(r"\n\s*\n", body):
        n = normalize(block)
        if not n:
            continue
        (long_p if len(_WORD.findall(n)) >= SHORT_PARAGRAPH_WORDS else short_p).append(n)
    return long_p, short_p


def digest(norm):
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def collect(paths, texts=None):
    """{relpath: {"hashes": set, "count": int, "short": int}} — one entry per file."""
    out = {}
    for p in paths:
        if texts is not None:
            text = texts[p]
        else:
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
        long_p, short_p = paragraphs(text)
        out[p] = {"hashes": {digest(x) for x in long_p},
                  "count": len(long_p), "short": len(short_p)}
    return out


def resolve_targets(root, target):
    """A directory (scanned recursively, System/ excluded) or a comma-separated
    list of files. Markdown only — a batch of binaries is `aios extract`'s job."""
    if not target:
        return []
    if "," in target:
        cand = [t.strip() for t in target.split(",") if t.strip()]
        return [c if os.path.isabs(c) else os.path.join(root, c) for c in cand]
    full = target if os.path.isabs(target) else os.path.join(root, target)
    if os.path.isfile(full):
        return [full]
    files = []
    for dirpath, dirnames, filenames in os.walk(full):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if fn.lower().endswith(".md") and not fn.startswith("_"):
                files.append(os.path.join(dirpath, fn))
    return sorted(files)


def matrix(data):
    """Pairwise overlap + per-file unique contribution.

    Pair rows carry the shared count and BOTH percentages, because one number
    cannot express the asymmetry that matters: 6,200 shared paragraphs is 95% of
    a 6,500-paragraph file and 66% of a 9,400-paragraph one, and it is the 95%
    that tells you the small file was absorbed whole.
    """
    files = list(data)
    pairs = []
    for i, a in enumerate(files):
        for b in files[i + 1:]:
            shared = data[a]["hashes"] & data[b]["hashes"]
            if not shared:
                continue
            pairs.append({
                "a": a, "b": b, "shared": len(shared),
                "pct_a": round(100 * len(shared) / data[a]["count"]) if data[a]["count"] else 0,
                "pct_b": round(100 * len(shared) / data[b]["count"]) if data[b]["count"] else 0,
            })
    pairs.sort(key=lambda r: -max(r["pct_a"], r["pct_b"]))
    unique = {}
    for f in files:
        others = set()
        for g in files:
            if g != f:
                others |= data[g]["hashes"]
        u = data[f]["hashes"] - others
        unique[f] = {"unique": len(u), "total": data[f]["count"],
                     "pct_unique": round(100 * len(u) / data[f]["count"]) if data[f]["count"] else 0}
    return pairs, unique


# --------------------------------------------------------------------------
# the annotation half — written only when the human says so
# --------------------------------------------------------------------------

def _fm_bounds(text):
    """(start, end) character offsets of the frontmatter block, or None."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    return (0, end + 4) if end != -1 else None


def annotated_text(text, rows):
    """Return this file with its overlap map in frontmatter. Body untouched.

    The map exists so the NEXT extraction pass counts shared material once. It
    is recorded as `x_` extension fields — the sanctioned way to carry a fact the
    dictionary does not yet name — and it records a MEASUREMENT, never a verdict:
    which sources this file overlaps and by how much, not which file wins.
    """
    lines = [
        "x_overlap_checked: aios dedupe-batch",
        f"x_overlap_paragraphs: {rows['total']}",
        f"x_overlap_unique: {rows['unique']}",
    ]
    if rows["peers"]:
        lines.append("x_overlap_with:")
        for peer, shared, pct in rows["peers"]:
            lines.append(f"  - \"{peer}: {shared} shared paragraphs ({pct}% of this file)\"")
    block = "\n".join(lines)

    bounds = _fm_bounds(text)
    if bounds is None:
        new = f"---\n{block}\n---\n\n{text}"
    else:
        head = text[:bounds[1]]
        head = re.sub(r"^x_overlap_(checked|paragraphs|unique|with):.*(\n(  - .*|    .*))*\n",
                      "", head, flags=re.M)
        head = head.rstrip("\n")
        assert head.endswith("---")
        head = head[:-3].rstrip("\n") + "\n" + block + "\n---"
        new = head + text[bounds[1]:]
    return new


# --------------------------------------------------------------------------
# command
# --------------------------------------------------------------------------

def run(root, args, rep: Report):
    target = getattr(args, "target", None)
    if not target:
        rep.error("usage: aios dedupe-batch <dir | file1.md,file2.md> [--annotate]  "
                  "(reports overlap across an intake batch; `aios dupes` is the "
                  "separate canon-collision checker)")
        return rep
    paths = resolve_targets(root, target)
    missing = [p for p in paths if not os.path.exists(p)]
    for m in missing:
        rep.error(f"not found: {os.path.relpath(m, root)}")
    if missing:
        return rep
    safe_batch = None
    if getattr(args, "annotate", False):
        try:
            # Prove the ENTIRE mutation set before reading or writing any target.
            # The report-only form deliberately retains its external-read ability.
            safe_batch = preflight_contained_regular_files(root, paths)
        except SafePathError as exc:
            rep.error(f"annotation refused: {exc}")
            return rep
    try:
        return _run_batch(root, args, rep, paths, safe_batch)
    finally:
        if safe_batch is not None:
            safe_batch.close()


def _run_batch(root, args, rep, paths, safe_batch):
    if len(paths) < 2:
        rep.info["files"] = len(paths)
        rep.warn("a batch needs at least two files — nothing to compare. "
                 "Point this at the folder the material arrived in.")
        return rep

    safe_texts = None
    if safe_batch is not None:
        try:
            safe_texts = safe_batch.read_texts()
        except SafePathError as exc:
            rep.error(f"annotation refused: {exc}")
            return rep
    data = collect(paths, safe_texts)
    pairs, unique = matrix(data)
    rel = lambda p: os.path.relpath(p, root)   # noqa: E731

    rep.info["files"] = len(data)
    rep.info["paragraph_threshold"] = (
        f"paragraphs under {SHORT_PARAGRAPH_WORDS} words are excluded from the matrix "
        f"(boilerplate repeats across unrelated documents) and counted separately")
    for p in paths:
        d = data[p]
        rep.info[f"  {rel(p)}"] = (f"{d['count']} comparable paragraphs "
                                   f"(+{d['short']} short, excluded)")

    if not pairs:
        rep.info["overlap"] = "none — no comparable paragraph is shared by any two files"
        return rep

    rep.info["overlap_matrix"] = [
        f"{rel(r['a'])} ↔ {rel(r['b'])}: {r['shared']} shared "
        f"({r['pct_a']}% of the first, {r['pct_b']}% of the second)"
        for r in pairs
    ]
    rep.info["unique_contribution"] = [
        f"{rel(p)}: {u['unique']}/{u['total']} paragraphs appear in no other file "
        f"({u['pct_unique']}% unique)"
        for p, u in sorted(unique.items(), key=lambda kv: kv[1]["pct_unique"])
    ]

    for p, u in unique.items():
        if u["total"] and u["pct_unique"] <= 50:
            rep.warn(f"{rel(p)}: only {u['pct_unique']}% of its comparable paragraphs are its "
                     f"own — reading this batch as independent sources would count the same "
                     f"material more than once (manufactured corroboration). This is a "
                     f"MEASUREMENT, not a verdict: nothing has been discarded, and which "
                     f"file is the fuller record is yours to decide.")

    rep.info["next"] = ("report only — nothing was changed. Once you have decided which "
                        "sources to keep, remove or archive the rest and re-run with "
                        "--annotate: every file still in the batch gets the overlap map "
                        "written into its frontmatter (bodies untouched) so the next "
                        "extraction pass counts shared material once.")

    if getattr(args, "annotate", False):
        replacements = {}
        for p, safe in zip(paths, safe_batch.targets):
            peers = []
            for r in pairs:
                if r["a"] == p:
                    peers.append((rel(r["b"]), r["shared"], r["pct_a"]))
                elif r["b"] == p:
                    peers.append((rel(r["a"]), r["shared"], r["pct_b"]))
            replacements[safe.relpath] = annotated_text(
                safe_texts[p], {"total": unique[p]["total"],
                                "unique": unique[p]["unique"],
                                "peers": peers}).encode("utf-8")
        try:
            policy = guard_ordinary_write_set(
                root,
                replacements,
                "dedupe-batch --annotate",
                texts={safe.relpath: safe_texts[safe.path]
                       for safe in safe_batch.targets},
            )
            result = safe_batch.atomic_replace_many(
                replacements,
                read_only_inputs=(policy.manifest,),
            )
        except (ProtectedTargetError, SafePathError) as exc:
            rep.error(str(exc))
            return rep
        rep.info["annotated"] = [safe.relpath for safe in safe_batch.targets]
        rep.info["annotation_durable"] = result.durable
        for warning in result.cleanup_warnings:
            rep.warn(f"annotation committed durably; cleanup warning: {warning}")
        rep.info["next"] = ("overlap maps written to frontmatter; bodies unchanged. "
                            "Run `aios validate` before the session ends.")
    return rep
