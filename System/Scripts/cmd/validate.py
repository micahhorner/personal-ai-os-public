"""vault.validate — schema, vocabulary, ID, naming, authority, and secrets checks."""
from __future__ import annotations
import os, re, glob
import yaml
from lib.frontmatter import iter_markdown, is_placeholder, in_template_space
from lib.report import Report

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FORBIDDEN = re.compile(r'[\\:*?"<>|]')
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"), re.compile(r"gh[pos]_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
]
CORE_REQUIRED = ["id", "type", "created", "updated", "summary"]
GOV_KEYS = ("classification", "ai_use", "domain", "approval", "sync")   # validated on every record (DEC-066; sync DEC-092)
LOCAL_ONLY_DIR = "local only"   # the folder IS the marking (DEC-065; extended to sync by DEC-092)

def _read_text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()

def _load_yaml(path):
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)

def load_schemas(root, rep=None):
    schemas, vocabs = {}, {}
    sdir = os.path.join(root, "System", "Schemas")
    for f in glob.glob(os.path.join(sdir, "*.yaml")):
        # duplicate-key guard: YAML silently lets the last key win, which can
        # disable a constraint (this exact defect shipped once — subtype)
        if rep is not None:
            keys = re.findall(r"^  (\w+):", _read_text(f), re.M)
            for k in set(k for k in keys if keys.count(k) > 1):
                rep.error(f"{os.path.relpath(f, root)}: duplicate key '{k}' — later value silently wins")
        d = _load_yaml(f)
        if os.path.basename(f) == "vocabularies.yaml":
            vocabs = {k: v for k, v in d.items() if isinstance(v, list)}
            # user-owned additive extensions (M-08/DEC-014): merged read-only;
            # the protected schema file is never modified for personalization
            ux = os.path.join(root, "80 User", "vocabulary-extensions.yaml")
            if os.path.exists(ux):
                try:
                    u = _load_yaml(ux) or {}
                    for k, v in u.items():
                        if isinstance(v, list) and k in vocabs:
                            vocabs[k] = vocabs[k] + [x for x in v if x not in vocabs[k]]
                except yaml.YAMLError:
                    pass  # reported as a frontmatter/YAML error elsewhere
        elif "schema" in d:
            schemas[d["schema"]] = d
    return schemas, vocabs

def reserved_keys(schemas):
    keys = set(CORE_REQUIRED) | {"authority", "canonical_for", "derived_from", "version",
                                 "generated", "generator", "generated_at", "do_not_edit"}
    for s in schemas.values():
        keys.update(s.get("fields", {}).keys())
        keys.update(k.strip() for k in str(s.get("required", "")).strip("[]").split(",") if k.strip())
        for req in (s.get("required") or []):
            keys.add(req)
    return keys

def check_router_paths(root, rep):
    """Every Task Router `load:` path must resolve to a real file. Found live in
    an instance: the onboarding row loaded a capability the vault did not have,
    and validate passed — the router's own header promises "every load entry is
    a real vault path" and nothing checked it. `load_if_present:` entries may be
    absent by contract (user-created files), but the same header rules that
    System/ files must exist and belong in `load` — so those get a warning."""
    rp = os.path.join(root, "System", "Runtime", "Task Router.yaml")
    if not os.path.exists(rp):
        return  # minimal scaffolds have no router; nothing to check
    try:
        data = _load_yaml(rp) or {}
    except yaml.YAMLError as e:
        rep.error(f"System/Runtime/Task Router.yaml: unparseable YAML ({e})")
        return
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("load", "load_if_present") and isinstance(v, list):
                    for p in v:
                        if not isinstance(p, str):
                            continue
                        if k == "load" and not os.path.exists(os.path.join(root, p)):
                            rep.error(f"Task Router: load path does not resolve: '{p}'")
                        elif k == "load_if_present" and p.replace("\\", "/").startswith("System/"):
                            rep.warn(f"Task Router: '{p}' is a System/ path under load_if_present — "
                                     f"System files must exist and belong in load")
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(data)


def _local_only_path(relpath):
    return any(seg.strip().lower() == LOCAL_ONLY_DIR
               for seg in relpath.replace("\\", "/").split("/"))


def _is_product_doc(relpath):
    """Product-shipped documentation: everything under System/, plus the folder
    `_ABOUT.md` scaffolding the product writes into the content directories."""
    p = relpath.replace("\\", "/")
    return p.startswith("System/") or os.path.basename(p) == "_ABOUT.md"


def registry_versions(root):
    """Ids declared by the YAML registries, so a stamp against `op-registry` can
    resolve. Without this the check would fail closed on a source that is
    perfectly well versioned — it just isn't markdown, which is the same shape of
    blind spot the check exists to remove."""
    out = {}
    for path in glob.glob(os.path.join(root, "System", "**", "*.yaml"), recursive=True):
        try:
            data = _load_yaml(path)
        except Exception:
            continue
        if not isinstance(data, dict) or not data.get("id"):
            continue
        ver = data.get("version", data.get("schema_version"))
        if ver is not None:
            out[str(data["id"])] = (str(ver), "")   # YAML carries no `updated:` — version rule only
    return out


def check_stamp_integrity(stamps, doc_meta, rep):
    """`x_reviewed_against` must be a claim someone can be held to (DEC-105).

    Two ways it stops being one, both found live:

    **It names a source that has no version.** `health`'s skew check reads
    `versions.get(src)` and does nothing when that is `None`, so a stamp against
    a versionless source is silently skipped forever — it fails OPEN. Three
    shipped stamps were dead this way, and one of them (`Certification Battery`)
    is why a battery naming the wrong adversary fixtures survived a release with
    `derived_docs_behind: 0` on the board. Now an error: either the source
    declares a `version:`, or the stamp does not get to claim one.

    **It was re-applied without a re-read.** Twenty-three stamps named a source
    version whose own `updated:` date was LATER than the stamping document's —
    which is only possible if the number was bumped and the document was not
    opened. That is the exact failure the stamp exists to prevent, performed by
    the mechanism meant to prevent it. The honest alternative is always
    available and costs nothing: leave the stamp at the version you really did
    review, and let `health` report the doc as behind. A stale stamp is a true
    statement; a fresh one you did not earn is not."""
    for relpath, updated, ra in stamps:
        entries = ra.items() if isinstance(ra, dict) else (
            e.rsplit(":", 1) for e in ra if isinstance(e, str) and ":" in e)
        # Same scoping as DEC-069's unstamped-derived rule: the product's own
        # documentation is held to it; a user's note that happens to carry a
        # stamp is advised, never blocked (U1 — a lived-in vault must not go red
        # on the user's own content).
        sev = rep.error if _is_product_doc(relpath) else rep.warn
        for src, rec in entries:
            src, rec = str(src).strip(), str(rec).strip()
            if src not in doc_meta:
                continue        # an id outside this tree — links.py owns that check
            ver, src_updated = doc_meta[src]
            if ver is None:
                sev(f"{relpath}: x_reviewed_against names '{src}', which declares no "
                    f"version — the stamp can never be checked, so it fails open forever. "
                    f"Give the source a `version:` or drop the stamp (DEC-105)")
                continue
            if updated and src_updated and updated < src_updated:
                sev(f"{relpath}: claims review against {src}:{rec}, but that source was "
                    f"updated {src_updated} and this file's updated: is {updated} — a stamp "
                    f"cannot predate the version it claims. Re-read it and move updated:, "
                    f"or roll the stamp back to the version you did review (DEC-105)")


def check_sync_boundary(root, notes_meta, rep):
    """DEC-092: `sync: local-only` is a storage promise — never leaves this
    machine via sync/cloud backup. A promise the vault cannot show enforcement
    for is the trap this field replaces (a hand-written .gitignore line nothing
    validated), so `validate` cross-checks the root `.gitignore` BOTH ways:

      1. every `sync: local-only` record (field, or implied by a `Local Only/`
         path segment, DEC-065-style) must be covered by a real rule — an
         unbacked EXPLICIT field is an error; unbacked folder-IMPLIED marking
         is advisory (the folder convention predates DEC-092 — a lived-in
         vault upgrading in must not go red on its own content, U1 doctrine);
         unverifiable coverage always warns (negations/constructs the
         conservative matcher refuses to guess about: it never claims
         "covered" when unsure);
      2. a gitignored content file NOT marked `sync: local-only` draws one
         rolled-up warning — the reverse drift (enforcement without a marking).

    Also here: folder/field disagreement (`Local Only/` + `sync: allowed`) is
    an error, and `classification: restricted` draws one rolled-up explanatory
    warning — in a vault whose purpose is AI context it is almost always the
    wrong field (the defect that silently unloaded a user's own notes for four
    days). Scope fence: `sync` answers ONLY "may this leave the machine via
    sync" — retrieval stays `ai_use`, readability stays `classification`.
    """
    from lib.gitignore import GitignoreMatcher, COVERED, NOT_COVERED
    gi = GitignoreMatcher.load(root)
    content_prefixes = tuple()
    try:
        man = _load_yaml(os.path.join(root, "SYSTEM-MANIFEST.yaml")) or {}
        content_prefixes = tuple((man.get("directories") or {}).get("content") or [])
    except Exception:
        pass
    unmarked_ignored, restricted = [], []
    for relpath, m in notes_meta:
        if m.get("file_class") in ("example", "generated"):
            continue   # fixture/example material is never a live privacy promise (DEC-018)
        if "Templates" in relpath.replace("\\", "/").split("/"):
            continue
        rel = relpath.replace(os.sep, "/")
        sync = m.get("sync")
        in_local_only = _local_only_path(rel)
        if str(m.get("classification", "")) == "restricted":
            restricted.append(rel)
        if in_local_only and sync == "allowed":
            rep.error(f"{rel}: sync: allowed inside a 'Local Only/' folder — the folder "
                      f"IS a local-only marking (DEC-065/DEC-092); folder and field may "
                      f"not disagree. Move the file or drop the field.")
            continue
        effective_local = (sync == "local-only") or in_local_only
        if effective_local:
            cov = gi.coverage(rel)
            if cov == NOT_COVERED:
                if sync == "local-only":
                    rep.error(f"{rel}: sync: local-only but no .gitignore rule covers it — "
                              f"the never-leaves-this-machine promise is unbacked. Add a rule "
                              f"to the vault-root .gitignore (e.g. its folder, or the file "
                              f"path) so every sync channel that honors gitignore excludes it.")
                else:
                    # implied by the folder alone: the Local Only/ convention predates
                    # DEC-092, so a lived-in vault upgrading into this release must
                    # not go red on its own content (U1 doctrine, DEC-069/083 class).
                    # Advisory until the user backs it; fresh copies ship the rule.
                    rep.warn(f"{rel}: sits under a 'Local Only/' folder (implies "
                             f"sync: local-only) but no .gitignore rule backs it — add "
                             f"one (the product default is '**/Local Only/**') so the "
                             f"promise holds on git-based sync channels (DEC-092).")
            elif cov != COVERED:
                rep.warn(f"{rel}: sync: local-only — .gitignore coverage is UNVERIFIABLE "
                         f"(negations or patterns the conservative matcher will not guess "
                         f"about). Treat the promise as unbacked until confirmed by hand.")
        elif sync in (None, "", "allowed") and content_prefixes \
                and rel.startswith(content_prefixes) and gi.coverage(rel) == COVERED:
            unmarked_ignored.append(rel)
    if unmarked_ignored:
        rep.warn(f"{len(unmarked_ignored)} content file(s) are gitignored but not marked "
                 f"sync: local-only — enforcement without a marking is drift in reverse "
                 f"(DEC-092); mark them or un-ignore them: "
                 f"{unmarked_ignored[0]}"
                 + (f" +{len(unmarked_ignored) - 1} more" if len(unmarked_ignored) > 1 else ""))
    if restricted:
        rep.warn(f"{len(restricted)} record(s) carry classification: restricted — in a vault "
                 f"built to give an AI context this is almost always the wrong field: "
                 f"restricted means NO AI may EVER read it, and the record silently vanishes "
                 f"from retrieval. If the intent is 'never leaves this machine', use "
                 f"sync: local-only (storage) with ai_use: local-only (no hosted AI); "
                 f"classification records sensitivity only (DEC-092): "
                 f"{restricted[0]}"
                 + (f" +{len(restricted) - 1} more" if len(restricted) > 1 else ""))


FLAT_FOLDERS = (("knowledge", "20 Knowledge"), ("outputs", "40 Outputs"))
LOCAL_ONLY_DIR_NAME = "local only"


def check_flat_folders(root, rep):
    """DEC-101: `20 Knowledge` and `40 Outputs` stay flat — meaning lives in
    metadata and links, not in a folder tree (a second taxonomy carrying one
    axis, where a note belonging under two headings has to pick and the pick is
    invisible afterwards). Project affiliation rides tags + the project note as
    index; there is deliberately no second index type.

    **Warning only, never an error, always rolled up** — the DEC-092/DEC-069
    grandfathering shape: a lived-in vault must never go red on the user's own
    content (DEC-082), and the owner's live instance already has three Knowledge
    subfolders that are *his* to resolve, not the product's to force-flatten.

    The user declares a subfolder deliberate by putting an `_ABOUT.md` in it
    (the same signpost the numbered folders carry); that folder then goes silent
    permanently. `Local Only/` is a privacy fence rather than a taxonomy
    (DEC-065) and never warns. Immediate subdirectories only: a tree under a
    declared folder is the user's business, and a tree under an undeclared one
    is already named by its top folder.
    """
    from lib.vaultpaths import rel_folder
    undeclared = []
    for folder_id, default in FLAT_FOLDERS:
        rel = rel_folder(root, folder_id, default)
        base = os.path.join(root, rel)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.startswith(".") or name.lower() == LOCAL_ONLY_DIR_NAME:
                continue
            sub = os.path.join(base, name)
            if not os.path.isdir(sub):
                continue
            if os.path.exists(os.path.join(sub, "_ABOUT.md")):
                continue   # the user said what it is for — declared, so silent
            undeclared.append(f"{rel}/{name}")
    if undeclared:
        rep.warn(f"{len(undeclared)} subfolder(s) under the flat-filed directories "
                 f"({' and '.join(d for _, d in FLAT_FOLDERS)}) — these stay flat by "
                 f"design: meaning lives in metadata and links, and project affiliation "
                 f"in tags plus the project note (DEC-101). Advisory only (DEC-082), "
                 f"never an error; flatten at your own pace, or keep the folder and "
                 f"declare it deliberate by adding an `_ABOUT.md` saying what it is for: "
                 f"{undeclared[0]}"
                 + (f" +{len(undeclared) - 1} more" if len(undeclared) > 1 else ""))


def run(root, args, rep: Report):
    check_router_paths(root, rep)
    check_flat_folders(root, rep)
    schemas, vocabs = load_schemas(root, rep)
    reserved = reserved_keys(schemas)
    sync_records = []   # (relpath, meta) for the DEC-092 sync-boundary cross-check
    # DEC-096: the working/knowledge boundary is enforced, both ways, in the
    # content layer only (System/, Packs/, and templates are not user content).
    from lib.vaultpaths import rel_folder
    projects_dir = rel_folder(root, "projects", "10 Projects")
    knowledge_dir = rel_folder(root, "knowledge", "20 Knowledge")
    # F-4 (v1.0.1): folders registered with `conventions: foreign` hold
    # legacy-convention content converging gradually — per-file no-frontmatter
    # warnings there collapse to a single count
    foreign_paths, foreign_count = [], {}
    try:
        _reg = _load_yaml(os.path.join(root, "System", "Registries", "folder-registry.yaml"))
        for fid, f in (_reg.get("folders") or {}).items():
            if isinstance(f, dict) and f.get("conventions") == "foreign":
                foreign_paths.append(f["path"])
                foreign_count[f["path"]] = 0
    except Exception:
        pass
    ids, titles_ci, paths_ci = {}, {}, {}
    misfiled_notes = []   # `type: note` under the project layer — rolled up (DEC-082)
    sup_pairs, status_by_id = [], {}
    canonical_for = {}
    unstamped_derived = []
    doc_meta, stamps = {}, []      # DEC-105 stamp integrity
    unknown_types = {}
    known_types = set(schemas) | {"system-doc"} | set(vocabs.get("component_types", []))
    n = 0
    for note in iter_markdown(root):
        n += 1
        # path rules
        low = note.relpath.lower()
        if low in paths_ci and paths_ci[low] != note.relpath:
            rep.error(f"case-collision: {note.relpath} vs {paths_ci[low]}")
        paths_ci[low] = note.relpath
        base = os.path.basename(note.relpath)
        if FORBIDDEN.search(base) or base.rstrip() != base or base.rstrip(".") != base:
            rep.error(f"forbidden filename: {note.relpath}")
        # secret scan runs on raw content BEFORE any frontmatter gating (indep. finding:
        # frontmatter-less inbox captures are exactly where pasted secrets land)
        for pat in SECRET_PATTERNS:
            if pat.search(note.body):
                rep.error(f"{note.relpath}: possible secret material — remove it (Privacy §5)")
                break
        if note.error:
            rep.error(f"{note.relpath}: {note.error}")
            continue
        m = note.meta
        sync_records.append((note.relpath, m or {}))   # DEC-092 cross-check, after the loop
        if not m:
            # exempt: structural files, templates, and fixture input artifacts
            if (not base.startswith("_") and "Templates" not in note.relpath
                    and os.sep + "input" + os.sep not in note.relpath):
                fp = next((p for p in foreign_paths if note.relpath.startswith(p)), None)
                if fp is not None:
                    foreign_count[fp] += 1   # foreign-conventions folder: count, don't spam
                elif note.relpath.replace("\\", "/").startswith(projects_dir + "/"):
                    # DEC-096: the project-layer warning names the class it is
                    # inviting the file into — gently; untyped stays legal and a
                    # machine never auto-types anything.
                    rep.warn(f"{note.relpath}: untyped project file — consider `type: working` "
                             f"(System/Schemas/working.yaml; subtype: plan/log/capture/draft/scratch). "
                             f"Untyped is allowed; nothing will auto-type it")
                else:
                    rep.warn(f"{note.relpath}: no frontmatter")
            continue
        # secrets in metadata (body already scanned above)
        for pat in SECRET_PATTERNS:
            if pat.search(str(m)):
                rep.error(f"{note.relpath}: possible secret material in frontmatter — remove it (Privacy §5)")
        # Governance fields are validated on EVERY record, regardless of whether
        # `type` resolves to a schema (DEC-066): a typo'd privacy value must never
        # ride an unrecognised type past the vocabulary check and fail open.
        for gk in GOV_KEYS:
            gv = m.get(gk)
            if gv not in (None, "") and gv not in vocabs.get(gk, []):
                rep.error(f"{note.relpath}: '{gk}: {gv}' not in vocabulary '{gk}' "
                          f"(governance fields are always validated; privacy fails closed)")
        t0 = m.get("type")
        if t0 and str(t0) not in known_types:
            unknown_types.setdefault(str(t0), []).append(note.relpath)
        # id rules
        nid = m.get("id", "")
        if nid:
            if is_placeholder(nid):  # template placeholder (DEC-115: one definition)
                if not in_template_space(note.relpath):
                    rep.error(f"{note.relpath}: unfilled id placeholder")
            else:
                if not ID_RE.match(str(nid)):
                    rep.error(f"{note.relpath}: id '{nid}' violates ID grammar")
                t = str(m.get("type", ""))
                prefix_map = {"system-doc": "doc"}
                want = prefix_map.get(t, t)
                if want and not str(nid).startswith(want + "-"):
                    rep.error(f"{note.relpath}: id '{nid}' does not match type prefix '{want}-'")
                if nid in ids:
                    rep.error(f"duplicate id '{nid}': {note.relpath} and {ids[nid]}")
                ids[nid] = note.relpath
                status_by_id[str(nid)] = str(m.get("status", ""))
        # doc-freshness coverage (DEC-039): a derived doc without its review
        # stamp is invisible to skew-flagging — collected, warned once, rolled up.
        if m.get("authority") == "derived" and not m.get("x_reviewed_against"):
            unstamped_derived.append(note.relpath)
        if m.get("id"):
            doc_meta[str(m["id"])] = (m.get("version"), str(m.get("updated", "")))
        if m.get("x_reviewed_against"):
            stamps.append((note.relpath, str(m.get("updated", "")),
                           m["x_reviewed_against"]))
        # doc authority uniqueness
        cf = m.get("canonical_for")
        if cf:
            if cf in canonical_for:
                rep.error(f"two canonical owners for '{cf}': {note.relpath} and {canonical_for[cf]}")
            canonical_for[cf] = note.relpath
        # working/knowledge boundary (DEC-096) — user content layer only (System/,
        # Packs/, and Templates hold machinery and examples, not the user's filed
        # records). Asymmetric by ruling: `working` is a NEW class with no legacy
        # corpus, so misplacement is a hard error; `type: note` under the project
        # layer is a pre-existing lived-in pattern, so it rolls up to ONE advisory
        # warning (DEC-082: a lived-in vault never goes red on the user's own
        # notes — the DEC-092 grandfathering shape: legacy advisory, new strict).
        relnorm = note.relpath.replace("\\", "/")
        if (not relnorm.startswith(("System/", "Packs/"))
                and "Templates" not in note.relpath):
            t_dec = str(m.get("type", ""))
            if t_dec == "working" and not relnorm.startswith(
                    (projects_dir + "/", "00 Inbox/", "90 Archive/")):
                rep.error(f"{note.relpath}: `type: working` outside the project layer — "
                          f"working material is bound to '{projects_dir}/' (+ Inbox/Archive); "
                          f"if this is knowledge, it is a `note` (DEC-096: the boundary holds both ways)")
            elif t_dec == "note" and relnorm.startswith(projects_dir + "/"):
                misfiled_notes.append(note.relpath)
        # class schema checks (content notes only)
        t = m.get("type")
        if t in schemas and "Templates" not in note.relpath:
            sch = schemas[t]
            for r in (sch.get("required") or []):
                if r not in m or m.get(r) in (None, ""):
                    rep.error(f"{note.relpath}: missing required field '{r}'")
            for k, v in m.items():
                if k.startswith("x_"):
                    continue
                if k not in reserved:
                    rep.error(f"{note.relpath}: unknown key '{k}' (not in dictionary; use x_ prefix to experiment)")
                spec = (sch.get("fields") or {}).get(k) or {}
                vocab = spec.get("vocab") if isinstance(spec, dict) else None
                if vocab and k in GOV_KEYS:
                    continue   # governance keys are validated universally above
                if vocab and v not in (None, "") and v not in vocabs.get(vocab, []):
                    rep.error(f"{note.relpath}: '{k}: {v}' not in vocabulary '{vocab}'")
        sup = m.get("supersedes")
        if sup:
            for v in (sup if isinstance(sup, list) else [sup]):
                sup_pairs.append((str(v).strip().strip("[]"), note.relpath))
    # supersedes reciprocity: a superseded record must say so — old records are
    # marked, never silently left looking current (kernel §2)
    for target, relp in sup_pairs:
        if target in ids and status_by_id.get(target) not in ("superseded", "archived"):
            rep.warn(f"{relp}: supersedes '{target}' but that record's status is "
                     f"'{status_by_id.get(target) or 'unset'}' (expected: superseded)")
    for fp, c in foreign_count.items():
        if c:
            rep.warn(f"{fp}: {c} legacy-convention file(s) without frontmatter (folder registered conventions: foreign — converge via ingest)")
    if misfiled_notes:
        # Advisory, never blocking (DEC-082: a lived-in vault never goes red on
        # the user's own notes) — typed notes under the project layer predate the
        # working class; the fix is a frontmatter-only retype or a move, at the
        # user's pace. One rolled-up line, like the DEC-069 user-content case.
        rep.warn(f"{len(misfiled_notes)} knowledge-typed note(s) under '{projects_dir}/' — "
                 f"knowledge lives in '{knowledge_dir}/'; project working material is "
                 f"`type: working` (System/Schemas/working.yaml). Advisory only (DEC-082); "
                 f"retype or move at your own pace: {os.path.basename(misfiled_notes[0])}"
                 + (f" +{len(misfiled_notes) - 1} more" if len(misfiled_notes) > 1 else ""))
    for t0 in sorted(unknown_types):
        paths = unknown_types[t0]
        rep.warn(f"unrecognised type '{t0}' on {len(paths)} file(s) — schema checks are "
                 f"skipped for it (foreign types are tolerated, not validated): "
                 f"{os.path.basename(paths[0])}"
                 + (f" +{len(paths) - 1} more" if len(paths) > 1 else ""))
    if unstamped_derived:
        # DEC-069's hard error is scoped to the product's own docs (System/): a
        # USER note marked `authority: derived` means "I based this on something",
        # not "I am a product doc tracking a source version" — demanding a
        # machine-checkable stamp on the user's own writing is the product telling
        # them how to keep their notes (U1, upgrade-rehearsal finding 2: a lived-in
        # vault must never go red on the user's own content). User-content cases
        # surface as one rolled-up warning — visible, approval-gated, never blocking.
        sys_unstamped = [p for p in unstamped_derived
                         if p.replace("\\", "/").startswith("System/")]
        user_unstamped = [p for p in unstamped_derived if p not in sys_unstamped]
        for p in sys_unstamped:
            rep.error(f"{p}: authority: derived but no x_reviewed_against — declare which "
                      f"source version this was checked against (DEC-039 enforced, DEC-069)")
        if user_unstamped:
            rep.warn(f"{len(user_unstamped)} user note(s) marked authority: derived without "
                     f"x_reviewed_against — advisory only (DEC-069 is scoped to System/); "
                     f"stamp them if they track a source, ignore otherwise: "
                     f"{os.path.basename(user_unstamped[0])}"
                     + (f" +{len(user_unstamped) - 1} more" if len(user_unstamped) > 1 else ""))
    reg = registry_versions(root)
    reg.update(doc_meta)          # a markdown id always wins over a registry id
    check_stamp_integrity(stamps, reg, rep)
    check_sync_boundary(root, sync_records, rep)
    rep.info["files_checked"] = n
    rep.info["unique_ids"] = len(ids)
    # component contracts: scanned directly from single-file frontmatter (no hand registry)
    contract = {}
    cpath = os.path.join(root, "System", "Schemas", "component.yaml")
    if os.path.exists(cpath):
        contract = _load_yaml(cpath) or {}
    type_ext = contract.get("type_extensions", {}) or {}
    # F2 (PMM Engine migration finding): components self-identify by declaring
    # component_type in their own frontmatter, wherever they live — domain packs
    # need no wrapper files in the standard folders. System/Tests is excluded
    # (fixtures are test material, not live contracts).
    comp_files = []
    for _dp, _dn, _fn in os.walk(root):
        _dn[:] = [d for d in _dn if d not in (".git", ".obsidian")
                  and not (os.path.relpath(_dp, root) == "System" and d == "Tests")]
        for _f in _fn:
            if _f.endswith(".md"):
                comp_files.append(os.path.join(_dp, _f))
    from lib.frontmatter import parse_file
    for p in comp_files:
        n = parse_file(p, root)
        meta = n.meta or {}
        ctype = meta.get("component_type") or meta.get("type")
        if ctype not in ("capability", "agent", "workflow"):
            continue
        cid = meta.get("id", n.relpath)
        for f in ("id", "status", "version", "summary"):
            if not meta.get(f):
                rep.error(f"{cid}: missing contract field '{f}'")
        ext_req = (type_ext.get(ctype) or {}).get("required", [])
        for f in ext_req:
            if ctype != "workflow" and not meta.get(f):
                rep.error(f"{cid}: missing {ctype}-contract field '{f}'")
        if ctype == "agent":
            writes = str(meta.get("writes", ""))
            if "agent" in writes and "AGENT.md" in writes:
                rep.error(f"{cid}: agent writes include its own contract")
    # Activation is evidence, not a declaration: every active core capability,
    # agent, and workflow must point at confined tests and a passing record for
    # exactly its current contract version. Pack evidence is checked by the pack
    # lifecycle and is intentionally outside this core convention.
    # Current-version result records certify the generic product source. A
    # personal instance legitimately carries instance-local/historical results
    # while its product components advance through upgrade, so instance health
    # must not reinterpret those records as current source-release evidence.
    try:
        instance_role = str(((_load_yaml(os.path.join(
            root, "SYSTEM-MANIFEST.yaml")) or {}).get("system") or {}).get(
                "instance_role") or "generic-master")
    except (OSError, yaml.YAMLError, TypeError):
        instance_role = "generic-master"  # malformed source stays strict
    if instance_role == "generic-master":
        from lib.component_evidence import audit_core_component_evidence
        evidence = audit_core_component_evidence(root)
        rep.info["active_core_components"] = evidence.active_components
        rep.info["component_evidence_findings"] = len(evidence.findings)
        for finding in evidence.findings:
            rep.error(finding.message())
    else:
        rep.info["component_evidence"] = "source-only — skipped for personal instance"
    return rep
