"""vault.pack-check — validate installed pack CONTENT, inside its own namespace.

`Packs/` is in `frontmatter.SKIP_DIRS`, and that is **correct and stays**: a pack
legitimately ships its own `README.md` and `CHANGELOG.md`, which would otherwise
collide with the vault's in `dupes`, and its note ids would collide with vault
ids (DEC-061, DEC-067).

The consequence on a pack-heavy instance is severe. Measured on a live role-pack
instance, 2026-07-27:

    markdown files in the vault                446
    scanned by validate / links / dupes        165
    inside Packs/ and never scanned            260

The client's entire messaging, enablement, intelligence, published-assets and
wiki corpus sat outside every mechanical check. **A green suite was evidence
about the vault around the pack, not about the pack.** Found by hand in that
blind spot: 20 broken wikilinks live for a day, an invalid `type`, two invalid
`subtype`s, an id/type mismatch, 3 duplicate titles, 34 files with no
frontmatter — and a fabricated attributed customer quote whose own remediation
had concluded "exactly one file", because the second copy was inside `Packs/`.

So this command reads each pack **as a pack**, in a separate pass, resolving its
ids, titles and links against *itself plus the vault* — and merges nothing back.
`iter_markdown`'s default is untouched, vault `validate` still reports the same
file count, `dupes` still never collides a pack README with the vault's, and the
canon id space never learns a pack id. **Coverage is not canon** — the crux, and
guarded by test rather than asserted (see `test_pack_check.py`).

A TEMPLATE IS NOT A RECORD (DEC-115). A pack ships templates, and a template's
`id: note-<slug>` is a blank waiting for a value — it is not a malformed id, and
two templates carrying it are not two notes claiming one id. `validate` has known
that since the id rules were written; this command re-derived the rules without
it and reported the product's own convention as 19 errors on the first pack that
had templates, while `dupes` stayed green on the identical convention in
`System/Templates/`. Both readers now call `frontmatter.is_placeholder` /
`in_template_space`, so there is one definition. The tolerance is not a blind
spot: a placeholder id OUTSIDE a Templates folder is an error this command did
not previously make at all.

Severity is role-dependent (DEC-083): on `generic-master` these are errors —
that role means "ships to customers this way" — and on a `personal-instance`
they are warnings, because it is the user's own content and the product must not
redden their vault forever (DEC-082). The classes in ALWAYS_STRICT are never
downgraded: they are not stylistic, they are the pack being malformed or unsafe.
"""
from __future__ import annotations
import os
import re

from lib.frontmatter import (SKIP_DIRS, iter_markdown, body_links,
                             is_placeholder, in_template_space)
from lib.report import Report
from cmd.validate import load_schemas
from cmd.links import REL_FIELDS, norm_wiki, yaml_ids

# Read a pack's own tree: prune runtime state, but NOT `Packs` — we are inside
# one. Everything else the vault prunes, a pack prunes for the same reasons.
PACK_SKIP_DIRS = SKIP_DIRS - {"Packs"}

# Never downgraded to a warning, on any instance_role. These are not matters of
# taste on the user's own content: a file that will not parse, an id that breaks
# the grammar every index depends on, two notes claiming one id, a pack quietly
# redefining governance vocabulary, or a credential committed into a shipped
# artifact. A personal instance is entitled to messy notes; it is not entitled
# to a pack that cannot be read or that ships a secret.
ALWAYS_STRICT = ("parse", "id-grammar", "duplicate-id", "governance-vocabulary", "secret")
ADVISORY = ("no-frontmatter", "duplicate-title", "id-shared-with-vault",
            "link-placeholder")

# Governance words a pack may use but must not REDEFINE: a pack that ships its
# own `canonical_for: system-architecture` is claiming the vault's own authority.
GOVERNANCE_CANONICAL_FOR = {
    "system-architecture", "change-control", "privacy-and-boundaries",
    "active-decision-summary", "system-version-history", "operations-contract",
}

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*"
               r"['\"]?[A-Za-z0-9/+_\-]{16,}", re.I),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
# A documented placeholder is not a secret. Measured against the real corpus:
# the product's own prose about the OpenSSH header and a fixture's obviously
# fake key both matched before this.
FAKE_MARKERS = ("FAKE", "EXAMPLE", "PLACEHOLDER", "XXXX", "<your", "your-", "dummy")


def _master(root):
    """DEC-083, the same helper shape doc-audit uses. Master = error;
    instance = warning."""
    import yaml
    try:
        with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as stream:
            man = yaml.safe_load(stream) or {}
    except Exception:                                    # noqa: BLE001
        return True
    role = str(((man.get("system") or {}).get("instance_role") or "generic-master")).strip()
    return role == "generic-master"


def installed_packs(root):
    """Every `Packs/*/` holding a pack.yaml — the definition of installed."""
    base = os.path.join(root, "Packs")
    if not os.path.isdir(base):
        return []
    return sorted(os.path.join(base, d) for d in os.listdir(base)
                  if os.path.isfile(os.path.join(base, d, "pack.yaml")))


def pack_notes(pack_root):
    """Every markdown file under one pack, parsed. The separate pass."""
    return list(iter_markdown(pack_root, skip_dirs=PACK_SKIP_DIRS))


def pack_id_index(root):
    """{note id: 'Packs/<name>/<rel>'} across every installed pack.

    The SECONDARY index (spec §6a). `links` consults it to resolve a vault →
    pack citation, and NOTHING else does: it is never unioned into the canon id
    space, so `dupes` and `validate` are unaffected and DEC-067 holds. Resolution
    is not membership."""
    out = {}
    for pack_root in installed_packs(root):
        for n in pack_notes(pack_root):
            nid = n.meta.get("id")
            # A template's blank is not an addressable record (DEC-115): nothing
            # may cite `note-<slug>` and be told it resolved.
            if nid and is_placeholder(nid):
                continue
            if nid and str(nid) not in out:
                rel = os.path.join(os.path.relpath(pack_root, root),
                                   n.relpath).replace(os.sep, "/")
                out[str(nid)] = rel
    return out


def _looks_fake(line):
    upper = line.upper()
    return any(m.upper() in upper for m in FAKE_MARKERS)


def _vault_ids_and_titles(root):
    ids, titles = yaml_ids(root), set()
    for n in iter_markdown(root):
        if n.meta.get("id"):
            ids.add(str(n.meta["id"]))
        titles.add(os.path.splitext(os.path.basename(n.relpath))[0].lower())
        for a in (n.meta.get("aliases") or []):
            titles.add(str(a).lower())
    return ids, titles


def check_pack(root, pack_root, schemas, vocabs, vault_ids, vault_titles, emit):
    """Check one pack against ITSELF ∪ the vault. `emit(kind, message)` decides
    severity; this function never does."""
    name = os.path.basename(pack_root)
    notes = pack_notes(pack_root)
    ids, titles, seen_titles = {}, set(), {}
    # Exactly `validate`'s own type vocabulary — reused, never re-derived, or a
    # pack would be judged by a narrower rule than the vault it installs into.
    # (`type: capability` and `type: system-doc` are legitimate and were flagged
    # while this set was just the note-class schemas.)
    classes = (set(schemas or {}) | {"system-doc"}
               | set((vocabs or {}).get("component_types", []) or []))
    subtypes = set()
    for key, v in (vocabs or {}).items():
        if key != "component_types" and isinstance(v, (list, tuple)):
            subtypes.update(str(x) for x in v)

    for n in notes:
        rel = f"Packs/{name}/{n.relpath}"
        if n.error:
            emit("parse", f"{rel}: {n.error}")
            continue
        if not n.meta:
            emit("no-frontmatter", f"{rel}: no frontmatter")
            continue

        t = n.meta.get("type")
        if t is not None and classes and str(t) not in classes:
            emit("type", f"{rel}: type '{t}' is not a schema class "
                         f"({', '.join(sorted(classes))})")
        st = n.meta.get("subtype")
        if st is not None and subtypes and str(st) not in subtypes:
            emit("subtype", f"{rel}: subtype '{st}' is in no vocabulary")

        nid = n.meta.get("id")
        if nid and is_placeholder(nid):
            # DEC-115. A template's `id: note-<slug>` is a blank, not a record.
            # Judged as one it produced 19 duplicate-id ERRORS on a live pack
            # shipping 22 templates — the identical convention the product's own
            # `System/Templates/` uses, and which `dupes` calls green. It never
            # enters the id space, so it can neither duplicate nor collide.
            # OUTSIDE template space the same value is a note nobody finished,
            # and that is an error `pack-check` did not previously make at all.
            if not in_template_space(n.relpath):
                emit("id-grammar", f"{rel}: unfilled id placeholder '{nid}' outside "
                                   f"a Templates folder — a shipped record must "
                                   f"carry a real id")
        elif nid:
            nid = str(nid)
            want = {"system-doc": "doc"}.get(str(t), str(t)) if t else None
            if want and not nid.startswith(want + "-"):
                emit("id-grammar",
                     f"{rel}: id '{nid}' does not match type prefix '{want}-'")
            if nid in ids:
                emit("duplicate-id",
                     f"{rel}: duplicate id '{nid}' within this pack "
                     f"(also {ids[nid]})")
            else:
                ids[nid] = rel
            # A pack is ENTITLED to its own namespace — this can never be an
            # error, only a note that the two spaces overlap (spec §3).
            if nid in vault_ids:
                emit("id-shared-with-vault",
                     f"{rel}: id '{nid}' also exists in the vault — the pack keeps "
                     f"its own namespace; nothing is merged")
        cf = str(n.meta.get("canonical_for") or "")
        if cf in GOVERNANCE_CANONICAL_FOR:
            emit("governance-vocabulary",
                 f"{rel}: claims canonical_for '{cf}' — a pack may use the vault's "
                 f"governance vocabulary but may never redefine it")

        title = os.path.splitext(os.path.basename(n.relpath))[0]
        if title.lower() in seen_titles:
            emit("duplicate-title",
                 f"{rel}: duplicate H1/title '{title}' within this pack "
                 f"(also {seen_titles[title.lower()]})")
        else:
            seen_titles[title.lower()] = rel
        titles.add(title.lower())
        for a in (n.meta.get("aliases") or []):
            titles.add(str(a).lower())

        for i, line in enumerate(n.body.splitlines(), 1):
            if _looks_fake(line):
                continue
            for pat in SECRET_PATTERNS:
                if pat.search(line):
                    emit("secret", f"{rel}:{i}: looks like a committed credential "
                                   f"— a pack is a distributed artifact")
                    break

    # Links resolve against pack ∪ vault. Non-markdown members resolve by
    # basename, as Obsidian does.
    files = set()
    for dp, dns, fns in os.walk(pack_root):
        dns[:] = [d for d in dns if d not in PACK_SKIP_DIRS]
        for fn in fns:
            files.add(fn.lower())
            if fn.lower().endswith(".md"):
                files.add(fn[:-3].lower())
    known_titles = titles | vault_titles | files
    known_ids = set(ids) | vault_ids
    for n in notes:
        if n.error:
            continue
        rel = f"Packs/{name}/{n.relpath}"
        wl, ml = body_links(n.body)
        for target in wl:
            if not target or is_placeholder(target):
                # DEC-115. `[[ ]]` and `[[<topic>]]` are fill-in slots: they name
                # nothing, so there is nothing to resolve and nothing is broken.
                # "unresolved wikilink [[]]" was a false description of them, and
                # on `generic-master` it was a hard error — 12 of them on a live
                # pack, 11 inside its own template folder. The same value in the
                # frontmatter relation fields below has always been skipped for
                # this exact reason; the body now agrees with the frontmatter.
                # Reported, never silent, and advisory on every role: an empty
                # slot is cosmetic, where a link promising a note that does not
                # exist stays an error below.
                emit("link-placeholder",
                     f"{rel}: empty or placeholder wikilink [[{target}]] — a link slot "
                     f"with no target; fill it in or remove it")
                continue
            if target.lower() not in known_titles and target not in known_ids:
                emit("link", f"{rel}: unresolved wikilink [[{target}]]")
        for target in ml:
            tp = os.path.normpath(os.path.join(pack_root, os.path.dirname(n.relpath),
                                               target.replace("%20", " ")))
            if not os.path.exists(tp) and not os.path.exists(tp + ".md"):
                emit("link", f"{rel}: broken relative link ({target})")
        for f in REL_FIELDS:
            vals = n.meta.get(f)
            if not vals:
                continue
            for v in (vals if isinstance(vals, list) else [vals]):
                target = norm_wiki(v)
                if (target and "<" not in target and target not in known_ids
                        and target.lower() not in known_titles):
                    emit("relation",
                         f"{rel}: frontmatter {f} references unknown id '{target}'")
    return len(notes)


def check_candidate(root, pack_root, rep: Report):
    """Strict pre-install check of one staged candidate.

    Personal-instance severity is intentionally irrelevant here: an incoming
    artifact is vendor input until accepted. Only the globally advisory classes
    remain warnings; every substantive finding blocks placement.
    """
    schemas, vocabs = load_schemas(root, None)
    vault_ids, vault_titles = _vault_ids_and_titles(root)
    counts = {}

    def emit(kind, message):
        counts[kind] = counts.get(kind, 0) + 1
        if kind in ADVISORY:
            rep.warn(message)
        else:
            rep.error(message)

    scanned = check_pack(root, pack_root, schemas, vocabs,
                         vault_ids, vault_titles, emit)
    rep.info["files_checked"] = scanned
    if counts:
        rep.info["findings"] = dict(sorted(counts.items()))
    return rep


def run(root, args, rep: Report):
    packs = installed_packs(root)
    rep.info["packs_checked"] = [os.path.basename(p) for p in packs]
    if not packs:
        rep.info["result"] = "no installed packs (a Packs/<name>/ holding a pack.yaml)"
        return rep

    schemas, vocabs = load_schemas(root, None)
    vault_ids, vault_titles = _vault_ids_and_titles(root)
    strict = _master(root)
    rep.info["severity"] = ("errors (instance_role: generic-master — this pack ships "
                            "to customers as it is)" if strict else
                            "warnings (instance_role: personal-instance — your own "
                            "content is never an error, DEC-082/083); parse errors, id "
                            "grammar, duplicate ids, governance vocabulary and secrets "
                            "stay errors")
    counts = {}

    def emit(kind, message):
        counts[kind] = counts.get(kind, 0) + 1
        # Advisory classes are warnings everywhere: a pack's READMEs have no
        # frontmatter by nature, and an overlapping id is the namespace working.
        if kind in ADVISORY:
            rep.warn(message)
        elif strict or kind in ALWAYS_STRICT:
            rep.error(message)
        else:
            rep.warn(message)

    scanned = 0
    for pack_root in packs:
        scanned += check_pack(root, pack_root, schemas, vocabs,
                              vault_ids, vault_titles, emit)
    rep.info["files_checked"] = scanned
    rep.info["scope"] = (
        "every *.md under each installed pack, resolved against that pack plus the "
        "vault. Pack ids are NEVER merged into vault canon: `validate`, `links` and "
        "`dupes` see exactly what they saw before (DEC-061/DEC-067). A green `validate` "
        "is evidence about the vault AROUND the pack; this is the evidence about the pack.")
    if counts:
        rep.info["findings"] = dict(sorted(counts.items()))
    return rep
