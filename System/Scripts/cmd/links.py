"""vault.links — broken link, missing target, and orphan-attachment detection."""
from __future__ import annotations
import os
from lib.frontmatter import iter_markdown, body_links
from lib.report import Report

REL_FIELDS = ["related", "sources", "derived_from", "depends_on", "supports",
              "contradicts", "entities", "supersedes", "superseded_by",
              "project"]   # decision→project scoping (DEC-095) is a real reference; check it like one

def norm_wiki(v):  # tolerate "[[x]]" wrapping in yaml values
    v = str(v).strip()
    return v[2:-2].strip() if v.startswith("[[") and v.endswith("]]") else v

def yaml_ids(root):
    import glob, yaml as _yaml
    found = set()
    for f in glob.glob(os.path.join(root, "System", "**", "*.yaml"), recursive=True):
        try:
            with open(f, encoding="utf-8") as stream:
                d = _yaml.safe_load(stream)
            if isinstance(d, dict) and d.get("id"):
                found.add(str(d["id"]))
        except Exception:
            pass
    return found

def pack_ids(root):
    """Pack note ids as a SECONDARY index (spec §6, option (a); DEC-113).

    A vault note that declares its provenance — `sources: [source-example-...]`
    pointing into an installed pack — used to be a hard `links` ERROR, so a
    compliant note that cited its source turned the suite red while a note that
    stayed green could not cite it. The packs are instructed to write exactly
    those notes.

    This index is consulted ONLY here. Pack ids never enter the canon id space,
    so `validate` and `dupes` are untouched and DEC-067 holds: resolution is not
    membership. Read through pack-check's own walker so there is one definition
    of what a pack contains."""
    try:
        from cmd.packcheck import pack_id_index
        return pack_id_index(root)
    except Exception:                                    # noqa: BLE001
        return {}


def run(root, args, rep: Report):
    notes = list(iter_markdown(root))
    ids, titles = yaml_ids(root), {}
    packs = pack_ids(root)
    for n in notes:
        if n.meta.get("id"): ids.add(str(n.meta["id"]))
        title = os.path.splitext(os.path.basename(n.relpath))[0]
        titles.setdefault(title.lower(), n.relpath)
        for a in (n.meta.get("aliases") or []):
            titles.setdefault(str(a).lower(), n.relpath)
    # F-2: Obsidian resolves non-note wikilinks (images, PDFs, any file) by
    # vault-wide basename; the checker must honor the same semantics.
    #
    # The extension bug (fixed separately from the pack work that found it):
    # this set held every filename WITH its extension, and the lookup below uses
    # the raw link text. Obsidian resolves `[[Guide]]` to `Guide.md`, so a link
    # to a markdown file that is not in `titles` — anything under a pruned
    # directory — was reported broken, while the SAME link written `[[Guide.md]]`
    # silently passed. Two spellings of one link, opposite verdicts, and the
    # passing one bypassed the id/title check entirely. Markdown files now enter
    # under both spellings, so the two agree.
    file_basenames = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".obsidian", ".git", "__pycache__"}]
        for fn in filenames:
            file_basenames.add(fn.lower())
            if fn.lower().endswith(".md"):
                file_basenames.add(fn[:-3].lower())
    broken = 0
    for n in notes:
        if n.error: continue
        wl, ml = body_links(n.body)
        for target in wl:
            if target.lower() in file_basenames:
                continue   # embedded file exists somewhere in the vault (Obsidian semantics)
            if target.lower() not in titles and target not in ids:
                rep.warn(f"{n.relpath}: unresolved wikilink [[{target}]]")
                broken += 1
        for target in ml:
            tp = os.path.normpath(os.path.join(root, os.path.dirname(n.relpath), target.replace("%20", " ")))
            if not os.path.exists(tp) and not os.path.exists(tp + ".md"):
                rep.warn(f"{n.relpath}: broken relative link ({target})")
                broken += 1
        for f in REL_FIELDS:
            vals = n.meta.get(f)
            if not vals: continue
            for v in (vals if isinstance(vals, list) else [vals]):
                t = norm_wiki(v)
                if t and "<" not in t and t not in ids and t.lower() not in titles:
                    if t in packs:
                        # Resolved across the pack boundary. One-way by default:
                        # a vault note may cite a pack note. Reported so the
                        # dependency is visible, never an error.
                        rep.info.setdefault("pack_references", []).append(
                            f"{n.relpath}: {f} -> {t} ({packs[t]})")
                        continue
                    rep.error(f"{n.relpath}: frontmatter {f} references unknown id '{t}'")
    # orphan attachments
    from lib.vaultpaths import rel_folder
    att = os.path.join(root, rel_folder(root, "attachments", "30 Sources/Attachments"))
    if os.path.isdir(att):
        all_bodies = "\n".join(n.body for n in notes)
        for fn in os.listdir(att):
            if fn.startswith("."): continue
            if fn not in all_bodies:
                rep.warn(f"orphan attachment: 30 Sources/Attachments/{fn}")
    rep.info["notes_scanned"] = len(notes)
    return rep
