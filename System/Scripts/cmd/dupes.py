"""vault.dupes — duplicate and near-duplicate candidate detection ACROSS CANON.

Sibling, different question — do not confuse the two (DEC-098): this command
asks whether records already IN the vault collide on id, title, or alias, so its
frame of reference is canon. `aios dedupe-batch` asks whether the files ARRIVING
TOGETHER repeat each other, which no id/title/alias check can see: four
documents handed over as one corpus, one of them 97% a paste-up of two siblings,
passed every check here cleanly because they shared no id, no title, and no
alias. Run `dedupe-batch` at intake; run this one over the vault.

Scope (v1.0.1, F-1): canon must be unambiguous — collisions are ERRORS only
when two or more colliding notes carry an OS `id` (typed canon). Collisions
among untyped/legacy files (foreign corpora mid-convergence) are warnings.
Archived and superseded records are exempt entirely: the product's own
supersede-and-archive workflow must never redden health.

Convention basenames (found on the first fully-synced live instance run, on
v1.30.x): a user's method may REQUIRE the same filename once per project folder
— a method mandating a per-project HANDOFF.md is the proven case, two projects
and two handoffs on that run — so recurring per-folder convention names with
DISTINCT ids in DISTINCT folders are the method working, not ambiguity. Those
collisions are warnings (visible, never red). A convention-name collision
inside the SAME folder tree level, or with duplicate ids, stays an error.
Users extend the set via `80 User/dupes-conventions.yaml` (basenames: [...]),
merged read-only — the vocabulary-extensions pattern.

Declared derivations (v1.59.0, DEC-114; found on a lived-in instance where the
owner had followed the documented path 24 times): capture a source, write the
note that develops it, cite the source by id — the note keeps the source's
title, because that IS its title. Twenty-four such pairs reddened that vault for
doing exactly what the product's own ingest procedure says to do. A collision is
therefore not ambiguity when the colliding records are ONE DECLARED DERIVATION
LINEAGE: every record typed, ids distinct, `type` distinct, folders distinct,
and the records joined into a single connected graph by their own `sources` /
`derived_from` edges. Those are warnings — visible, never red — because the
pairing is worth seeing even when it is correct.

The citation is the whole test, and it is required. Two records that merely
happen to be of different types are not a derivation; the live vault also held
one such pair — a personal to-do list and an unrelated work capture named "To
Do" — which is a real collision the check must keep reporting. Same-type
collisions, same-folder collisions, duplicate ids, and undeclared pairs all stay
errors."""
from __future__ import annotations
import os, re
from collections import defaultdict
import yaml
from lib.frontmatter import iter_markdown
from lib.report import Report

def _reg_path(root, fid, default):
    try:
        with open(os.path.join(root, "System", "Registries", "folder-registry.yaml")) as stream:
            reg = yaml.safe_load(stream)
        return reg["folders"][fid]["path"]
    except Exception:
        return default

def normalize(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()

CONVENTION_BASENAMES = {"handoff"}   # normalized; per-project-folder by design

def _convention_names(root):
    names = set(CONVENTION_BASENAMES)
    upath = os.path.join(root, "80 User", "dupes-conventions.yaml")
    if os.path.exists(upath):
        try:
            with open(upath, encoding="utf-8") as stream:
                u = yaml.safe_load(stream) or {}
            for b in (u.get("basenames") or []):
                names.add(normalize(os.path.splitext(str(b))[0]))
        except yaml.YAMLError:
            pass
    return names

# The two lineage relations in the Metadata and Relationship Dictionary:
# `sources` (is grounded in this evidence) and `derived_from` (was produced from
# this material). `related` and `depends_on` are association and operational
# coupling — neither one earns a shared title, so neither counts here.
DERIVATION_FIELDS = ("sources", "derived_from")

def _idlist(v):
    if v is None:
        return []
    return [str(x) for x in v] if isinstance(v, (list, tuple, set)) else [str(v)]

def _is_declared_derivation(entries) -> bool:
    """True when these same-titled records are one declared derivation lineage.

    Every clause is load-bearing, and each keeps an error the check exists for:
    duplicate ids, same-type collisions and same-folder collisions can never
    reach the downgrade, an untyped file in the group disqualifies it, and an
    undeclared pair — no citation either way — stays an error. The graph must be
    CONNECTED, so a source + its note + an output drawn from that note all pass
    as one lineage, while two unrelated pairs that share a title do not."""
    if len(entries) < 2:
        return False
    ids = [e["id"] for e in entries]
    if not all(ids) or len(set(ids)) != len(ids):
        return False                                     # untyped, or duplicate ids
    types = [e["type"] for e in entries]
    if not all(types) or len(set(types)) != len(types):
        return False                                     # same-type collision
    if len({os.path.dirname(e["path"]) for e in entries}) != len(entries):
        return False                                     # same-folder collision
    pos = {i: n for n, i in enumerate(ids)}
    adj, edges = {n: set() for n in range(len(entries))}, 0
    for n, e in enumerate(entries):
        for target in e["derives"]:
            m = pos.get(target)
            if m is not None and m != n:
                adj[n].add(m); adj[m].add(n); edges += 1
    if not edges:
        return False                                     # nobody cited anybody
    seen, stack = {0}, [0]
    while stack:
        for nxt in adj[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt); stack.append(nxt)
    return len(seen) == len(entries)

def run(root, args, rep: Report):
    sys_p = _reg_path(root, "system", "System")
    arch_p = _reg_path(root, "archive", "90 Archive")
    by_title, by_alias = defaultdict(list), defaultdict(list)
    for n in iter_markdown(root):
        if n.relpath.startswith(sys_p + os.sep) or n.relpath.startswith(sys_p):
            continue  # content notes only
        if n.relpath.startswith(arch_p):
            continue  # archived history may legitimately mirror live titles (F-1)
        if str(n.meta.get("status", "")) in ("superseded", "archived"):
            continue  # lifecycle-retired records are not canon candidates (F-1)
        base = os.path.basename(n.relpath)
        if base.startswith("_"):
            continue
        title = os.path.splitext(base)[0]
        by_title[normalize(title)].append({
            "path": n.relpath,
            "id": str(n.meta.get("id") or ""),
            "type": str(n.meta.get("type") or ""),
            "derives": [d for f in DERIVATION_FIELDS for d in _idlist(n.meta.get(f))],
        })
        for a in (n.meta.get("aliases") or []):
            by_alias[normalize(str(a))].append((n.relpath, a))
    for key, entries in by_title.items():
        if len(entries) > 1:
            paths = [e["path"] for e in entries]
            typed = [e["path"] for e in entries if e["id"]]
            if len(typed) >= 2:
                dirs = {os.path.dirname(p) for p in paths}
                if key in _convention_names(root) and len(dirs) == len(paths):
                    rep.warn(f"convention filename recurs across folders (per-project by design): {paths}")
                elif _is_declared_derivation(entries):
                    kinds = " + ".join(e["type"] for e in entries)
                    rep.warn(f"declared derivation keeps its source's title ({kinds}; cited, not duplicated): {paths}")
                else:
                    rep.error(f"duplicate title candidates (typed canon must be unambiguous): {paths}")
            else:
                rep.warn(f"duplicate basenames among untyped/legacy files (converge when ingested): {paths}")
    for key, hits in by_alias.items():
        if key in by_title and len([e["path"] for e in by_title[key]] + [h[0] for h in hits]) > 1:
            uniq = {e["path"] for e in by_title[key]} | {h[0] for h in hits}
            if len(uniq) > 1:
                rep.warn(f"alias/title collision '{key}': {sorted(uniq)}")
    rep.info["distinct_titles"] = len(by_title)
    return rep
