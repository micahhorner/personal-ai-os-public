"""vault.resolve — the canonical-record resolver (determinism audit finding 2).

The "does this already exist?" lookup that safe-write step 1, ingest step 1,
retrieve-context step 3, and Change Control's search-before-creating all order
— previously hand-performed at every note birth. Deterministic match ladder
(exact id → exact title → exact alias → title/alias substring → body phrase),
every hit followed down its `superseded_by` chain to the terminal record.

Dedupe must see the whole lifecycle: drafts, stale, superseded and archived
records ARE dedupe targets (a duplicate of a draft is still a duplicate), so
unlike `search` this command always scans all states and reports each hit's
status instead. Privacy still filters first (H-02, fail-closed): a record the
profile may not see is invisible here too — privacy outranks dedupe by design.

Read-only. `--mint --type <t>` adds the write-side twin: the proposed
`<type>-<slug>` id and F-6-sanitized filename for the queried title, with an
id-collision check — computed at birth instead of hand-regexed (finding 5).
"""
from __future__ import annotations
import os, re, unicodedata
from lib.frontmatter import iter_markdown
from lib.report import Report
from cmd.search import load_profile, permitted

FORBIDDEN = re.compile(r'[\\/:*?"<>|]')


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "untitled"


def sanitize_filename(name: str) -> str:
    return (FORBIDDEN.sub("", name).rstrip(". ") or "untitled")


def _chain_end(nid, by_id, seen=None):
    """Follow superseded_by to the terminal record; cycles report themselves."""
    seen = seen or []
    seen.append(nid)
    n = by_id.get(nid)
    nxt = str(n.meta.get("superseded_by") or "") if n else ""
    if not nxt:
        return nid, seen, False
    if nxt in seen:
        return nid, seen + [nxt], True
    return _chain_end(nxt, by_id, seen)


def run(root, args, rep: Report):
    q = getattr(args, "query", None)
    if not q:
        rep.error("usage: aios resolve --query <id|title|alias|phrase> "
                  "[--mint --type <note-type>]")
        return rep
    profile = load_profile(root)
    ql = q.strip().lower()
    by_id, notes = {}, []
    for n in iter_markdown(root):
        if n.error or not n.meta.get("id"):
            continue
        if n.meta.get("file_class") in ("example", "generated"):
            continue
        if not permitted(n.meta, profile, n.relpath):
            continue          # privacy outranks dedupe; hidden means hidden (H-01)
        by_id[str(n.meta["id"])] = n
        notes.append(n)

    # deterministic match ladder — first rung with hits wins
    def titles_of(n):
        """Filename stem, plus the component's `name:` and parent folder for
        contract files (SKILL.md / AGENT.md), whose stem is not their name."""
        stem = os.path.splitext(os.path.basename(n.relpath))[0].strip().lower()
        out = [stem]
        if stem in ("skill", "agent", "_about"):
            out.append(os.path.basename(os.path.dirname(n.relpath)).strip().lower())
        nm = str(n.meta.get("name") or "").strip().lower()
        if nm:
            out.append(nm)
        return out

    def aliases_of(n):
        return [str(a).strip().lower() for a in (n.meta.get("aliases") or [])]

    rungs = [
        ("exact-id",       lambda n: ql == str(n.meta["id"]).lower()),
        ("exact-title",    lambda n: ql in titles_of(n)),
        ("exact-alias",    lambda n: ql in aliases_of(n)),
        ("title-or-alias-substring",
                           lambda n: any(ql in t for t in titles_of(n))
                           or any(ql in a for a in aliases_of(n))),
        ("body-phrase",    lambda n: ql in (str(n.meta.get("summary", "")) + "\n"
                                            + n.body).lower()),
    ]
    matched_rung, hits = None, []
    for name, pred in rungs:
        hits = [n for n in notes if pred(n)]
        if hits:
            matched_rung = name
            break

    if not hits:
        rep.info["resolution"] = "no existing record — safe to create"
        rep.info["query"] = q
    else:
        rep.info["query"] = q
        rep.info["matched_on"] = matched_rung
        out = []
        canonical_ids = []
        for n in hits[:10]:
            nid = str(n.meta["id"])
            end, chain, cycle = _chain_end(nid, by_id)
            tgt = by_id.get(end, n)
            line = (f"{nid} · {n.relpath} · status: {n.meta.get('status', '?')}"
                    f" · {str(n.meta.get('summary', ''))[:70]}")
            if end != nid:
                line += f" → superseded; canonical: {end}"
            if cycle:
                rep.error(f"supersession cycle: {' -> '.join(chain)} — fix the chain before writing")
            out.append(line)
            if end not in canonical_ids:
                canonical_ids.append(end)
        rep.info["candidates"] = out
        if len(hits) > 10:
            rep.info["candidates_shown"] = f"first 10 of {len(hits)} — narrow the query"
        rep.info["canonical"] = canonical_ids if len(canonical_ids) > 1 else canonical_ids[0]
        rep.warn("a record may already serve this purpose — switch to Changing against the "
                 "canonical record instead of creating (safe-write step 1: duplicates are corruption)")

    if getattr(args, "mint", False):
        ntype = getattr(args, "type", None)
        if not ntype:
            rep.error("--mint needs --type <note-type> (the id prefix)")
            return rep
        mid = f"{ntype}-{slugify(q)}"
        fname = sanitize_filename(q) + ".md"
        rep.info["mint_id"] = mid
        rep.info["mint_filename"] = fname
        if sanitize_filename(q) != q.strip():
            rep.info["mint_sanitized"] = "filename adjusted (F-6: forbidden characters/trailing dots stripped at birth)"
        if mid in by_id:
            rep.error(f"id '{mid}' already exists ({by_id[mid].relpath}) — do not create; "
                      "resolve to the existing record")
    return rep
