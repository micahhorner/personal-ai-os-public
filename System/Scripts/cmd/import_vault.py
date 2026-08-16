"""vault.import — bulk-import an existing external vault from a declarative plan.

Two modes, both proven on real corpora before this command existed (doc 12):
  verbatim — byte-identical copy, foreign structure registered as-is
             (a lived-in work vault, 1,095 files)
  mapped   — per-rule transforms into OS schema, unmapped material
             quarantined to the Inbox (a lived-in personal vault, 426 files)

The pipeline order is fixed and cannot be skipped: preflight → dry-run
(default, writes NOTHING) → human approval → --apply (checkpoint first,
validate after, one-time marker refuses re-runs). The source tree is opened
strictly read-only and is never modified.

Plan file: System/Migrations/<NNN-name>/import-plan.yaml
  source: /abs/path            mode: verbatim | mapped
  exclude: {dirs: [], files: [], paths: []}   keep: [regexes kept inside excluded paths]
  renames: {"CLAUDE.md": "NEW.md"}            # root-level only (adapter slot)
  rules:   [{match: glob, dest: "prefix/", transform: copy|note|source|user,
             prefix_parent: true?, ...}]   # prefix_parent: "<parent> — <name>" filenames,
           # for corpora that reuse basenames across sibling folders (dupes stay unambiguous)
           # mapped mode; first match wins; last rule MUST match "**"
  register_folders: [{id?, path: "Their Folder", purpose: ..., conventions: foreign}]
  patches:  [{file: rel-path, find: "...", replace: "..."}]   # declared adaptations,
            # anchor-asserted: each find must match its file exactly once, or apply refuses
  obsidian_config: import-minus-workspace | skip
  posture: gradual | side-by-side | full-adoption-later
  review_after_days: 14   # review_due horizon stamped on minted project stubs
                          # (CLI --review-days overrides; SPEC-import-review-queue)

Every minted project stub carries `review_due` (default +14 days) and a truthful
"Contains:" line (empty scaffolding is named, never advertised as material); on
apply, a generated review-queue artifact (review-queue.md) lands beside the plan,
and `aios health` reports stubs still unreviewed past their date.
"""
from __future__ import annotations
import fnmatch, os, re, unicodedata, datetime
import yaml
from lib.vaultpaths import ai_writes_enabled
from lib.report import Report
from lib.protectedwrites import ProtectedTargetError, protected_target
from lib.safepaths import (SafePathError, atomic_create_files, open_readonly_tree,
                           preflight_contained_regular_files)
from cmd.validate import SECRET_PATTERNS, FORBIDDEN
from cmd import checkpoint as ckpt_mod, validate as v_mod

WIKILINK = re.compile(r"!?\[\[([^\]|#]+)")
TRANSFORMS = ("copy", "note", "source", "user")
STATUS_MAP = {"complete": "active", "developing": "draft", "draft": "draft",
              "active": "active"}

BOOT_FILENAMES = {"AGENTS.md", "CLAUDE.md"}
RUNTIME_AUTHORITY_DIRS = {".agents", ".claude", ".codex"}
ROOT_AUTHORITY_PREFIXES = {".github", ".obsidian", "Packs", "System"}
ROUTED_USER_OVERLAYS = {
    "80 User/voice.md", "80 User/authoring.md",
    "80 User/workstyle.md", "80 User/handoff.md",
}
IMPORT_MAX_FILE_BYTES = 64 * 1024 * 1024
IMPORT_MAX_TOTAL_BYTES = 1024 * 1024 * 1024
IMPORT_MAX_FILES = 20_000
IMPORT_MAX_PLAN_BYTES = 2 * 1024 * 1024


class UnsafeImportError(RuntimeError):
    """An import path crosses the content-to-instruction trust boundary."""


def _collision_key(relpath: str) -> str:
    return "/".join(unicodedata.normalize("NFC", part).casefold()
                    for part in relpath.replace(os.sep, "/").split("/"))


def _portable_relpath(value: str, label: str) -> str:
    if (not isinstance(value, str) or not value or "\\" in value
            or any(ord(char) < 32 for char in value)):
        raise UnsafeImportError(f"{label} must be a non-empty portable relative path")
    posix = value.replace(os.sep, "/")
    if (posix.startswith("/") or re.match(r"^[A-Za-z]:", posix)
            or any(part in ("", ".", "..") for part in posix.split("/"))):
        raise UnsafeImportError(f"{label} must be a contained canonical relative path: {value}")
    if unicodedata.normalize("NFC", posix) != posix:
        raise UnsafeImportError(f"{label} must use Unicode NFC: {value}")
    return posix


def _authority_destination(relpath: str, root: str | None = None) -> str | None:
    posix = _portable_relpath(relpath, "import destination")
    manifest_root = root or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    try:
        protected = protected_target(manifest_root, posix)
    except ProtectedTargetError as exc:
        return f"unverifiable protected target ({exc})"
    if protected is not None:
        return f"manifest protected object {protected}"
    parts = [_collision_key(part) for part in posix.split("/")]
    boot = {_collision_key(name) for name in BOOT_FILENAMES}
    runtime_dirs = {_collision_key(name) for name in RUNTIME_AUTHORITY_DIRS}
    root_prefixes = {_collision_key(name) for name in ROOT_AUTHORITY_PREFIXES}
    if any(part in boot for part in parts):
        return "boot filename"
    if any(part in runtime_dirs for part in parts):
        return "runtime or product authority root"
    if parts and parts[0] in root_prefixes:
        return "runtime or product authority root"
    key = _collision_key(posix)
    if key in {_collision_key(path) for path in ROUTED_USER_OVERLAYS}:
        return "router-loaded user instruction overlay"
    if key == _collision_key("SYSTEM-MANIFEST.yaml"):
        return "boot manifest"
    return None


def _destination_path_issue(root: str, relpath: str) -> str | None:
    """Reject noncanonical paths and every existing symlink ancestor/target."""
    try:
        posix = _portable_relpath(relpath, "import destination")
    except UnsafeImportError as exc:
        return str(exc)
    cursor = os.path.abspath(root)
    for part in posix.split("/"):
        cursor = os.path.join(cursor, part)
        if os.path.islink(cursor):
            return f"destination traverses a symlink: {posix}"
    return None


def _today() -> str:
    return datetime.date.today().isoformat()


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "untitled"


def sanitize(name: str) -> str:
    clean = FORBIDDEN.sub("", name).rstrip(". ") or "untitled"
    return unicodedata.normalize("NFC", clean)


def _plan_folder(value, label, rep):
    """Validate one plan-authored destination prefix; one trailing slash is allowed."""
    if not isinstance(value, str) or not value:
        rep.error(f"{label} must be a non-empty canonical relative folder")
        return
    stripped = value[:-1] if value.endswith("/") else value
    try:
        _portable_relpath(stripped, label)
    except UnsafeImportError as exc:
        rep.error(str(exc))


def _existing_path_keys(root):
    """Portable collision census of every existing file, directory, and link."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        for name in sorted(dirnames + filenames):
            rel = "/".join(p for p in (rel_dir, name) if p)
            found.setdefault(_collision_key(rel), rel)
        dirnames[:] = [name for name in dirnames
                       if not os.path.islink(os.path.join(dirpath, name))]
    return found


def parse_note(text: str):
    meta, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError:
                meta = {}
            body = text[end + 4:].lstrip("\n")
    return meta, body


def extract_summary(body: str, cap: int = 240) -> str:
    m = re.search(r"^\*\*(.+?)\*\*", body, re.M | re.S)
    if not m:
        return ""
    text = re.sub(r"\s+", " ", m.group(1)).strip()
    out = ""  # cap at sentence boundaries — never mid-word (proven in the PV migration)
    for part in re.split(r"(?<=[.!?]) ", text):
        if out and len(out) + len(part) + 1 > cap:
            break
        out = (out + " " + part).strip()
        if len(out) >= cap:
            break
    return out[:cap].rstrip()


def fm_block(d: dict) -> str:
    return "---\n" + yaml.safe_dump(d, sort_keys=False, allow_unicode=True,
                                    width=1000) + "---\n\n"


def load_plan(root, args, rep):
    mdir = os.path.join(root, "System", "Migrations")
    target = getattr(args, "plan", None) or getattr(args, "migration", None)
    if not target:
        rep.error("import needs a plan: aios import --plan <NNN-name> [--apply]")
        return None, None
    try:
        target = _portable_relpath(target, "import plan")
    except UnsafeImportError as exc:
        rep.error(str(exc))
        return None, None
    if "/" in target:
        rep.error("import plan must name one directory directly under System/Migrations")
        return None, None
    pdir = os.path.join(mdir, target)
    ppath = os.path.join(pdir, "import-plan.yaml")
    if os.path.islink(pdir) or os.path.islink(ppath) or not os.path.exists(ppath):
        rep.error(f"plan not found: {ppath}")
        return None, None
    try:
        batch = preflight_contained_regular_files(
            root, [ppath], require_writable=False
        )
        try:
            raw = batch.read_bytes(max_bytes=IMPORT_MAX_PLAN_BYTES)[ppath]
        finally:
            batch.close()
        plan = yaml.safe_load(raw.decode("utf-8")) or {}
    except (SafePathError, UnicodeDecodeError, yaml.YAMLError) as exc:
        rep.error(f"import plan is not safe, bounded UTF-8 YAML: {exc}")
        return None, None
    src = plan.get("source", "")
    if not isinstance(src, str) or not os.path.isabs(src):
        rep.error("source vault path must be absolute")
    elif os.path.islink(src):
        rep.error("source vault must be a real directory, not a symlink")
    elif not os.path.isdir(src):
        rep.error(f"source vault not found: {src}")
    elif os.path.commonpath([os.path.abspath(src), root]) == root:
        rep.error("source must lie outside this vault")
    if plan.get("mode") not in ("verbatim", "mapped"):
        rep.error("plan mode must be 'verbatim' or 'mapped'")
    if plan.get("obsidian_config") not in (None, "skip"):
        rep.error("automatic Obsidian configuration import is disabled at the trust boundary — "
                  "migrate reviewed settings manually; plugins and runtime configuration "
                  "cannot enter through `aios import`")
    renames = plan.get("renames") or {}
    if not isinstance(renames, dict):
        rep.error("renames must be a mapping of canonical source path to canonical destination path")
        renames = {}
    for old, new in renames.items():
        try:
            _portable_relpath(old, "rename source")
            _portable_relpath(new, "rename destination")
        except UnsafeImportError as exc:
            rep.error(str(exc))
    for pt in (plan.get("patches") or []):
        if not all(isinstance(pt.get(k), str) and pt.get(k) for k in ("file", "find", "replace")):
            rep.error("each patch needs string fields: file, find, replace")
        else:
            try:
                _portable_relpath(pt["file"], "patch file")
            except UnsafeImportError as exc:
                rep.error(str(exc))
    regs = plan.get("register_folders") or []
    if not isinstance(regs, list):
        rep.error("register_folders must be a list")
    else:
        for item in regs:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                rep.error("each registered folder needs a string path")
                continue
            _plan_folder(item["path"], "registered folder path", rep)
            for key in ("id", "purpose", "conventions"):
                if key in item and not isinstance(item[key], str):
                    rep.error(f"registered folder {key} must be a string")
    rules = plan.get("rules") or []
    if plan.get("mode") == "mapped":
        if not rules or rules[-1].get("match") != "**":
            rep.error("mapped mode: last rule must match '**' (nothing is ever dropped; unmapped → quarantine)")
        for r in rules:
            if not isinstance(r, dict) or not isinstance(r.get("match"), str):
                rep.error("each mapped rule needs a string match and canonical destination")
                continue
            if r.get("transform", "copy") not in TRANSFORMS:
                rep.error(f"unknown transform '{r.get('transform')}' (allowed: {', '.join(TRANSFORMS)})")
            _plan_folder(r.get("dest"), f"rule {r.get('match')} destination", rep)
    return (None, None) if rep.errors else (plan, pdir)


def walk_source(plan, source_tree):
    ex = plan.get("exclude") or {}
    ex_dirs = set(ex.get("dirs") or [".git", ".obsidian", ".smart-env", "__pycache__", ".trash"])
    ex_files = set(ex.get("files") or [".DS_Store"])
    ex_paths = [p.rstrip("/") for p in (ex.get("paths") or [])]
    keep = [re.compile(k) for k in (plan.get("keep") or [])]
    all_files, all_dirs = source_tree.walk(
        prune=lambda rel: rel.rsplit("/", 1)[-1] in ex_dirs
    )
    files, dirs = [], []
    for rel in all_dirs:
        native = rel.replace("/", os.sep)
        in_ex = any(native == e or native.startswith(e + os.sep) for e in ex_paths)
        if not in_ex:
            dirs.append(native)
    for rel in all_files:
        native = rel.replace("/", os.sep)
        fn = os.path.basename(native)
        if fn in ex_files:
            continue
        parent = os.path.dirname(native)
        in_ex = any(parent == e or parent.startswith(e + os.sep) for e in ex_paths)
        if in_ex and not any(k.search(fn) for k in keep):
            continue
        files.append(native)
    if len(files) > IMPORT_MAX_FILES:
        raise UnsafeImportError(
            f"source vault exceeds the {IMPORT_MAX_FILES}-file safety limit"
        )
    return files, dirs


def _rule_for(rules, rel):
    posix = rel.replace(os.sep, "/")
    for r in rules:
        if fnmatch.fnmatch(posix, r["match"]):
            return r
    return None


def _dest_rel(rule, rel):
    """dest prefix + the part of rel beyond the pattern's static prefix."""
    pat = rule["match"]
    static = pat.split("*", 1)[0].split("?", 1)[0]
    static = static[:static.rfind("/") + 1] if "/" in static else ""
    remainder = rel.replace(os.sep, "/")[len(static):]
    return os.path.join(rule["dest"].rstrip("/"), *remainder.split("/"))


class Minted:
    def __init__(self):
        self.ids = {}

    def mint(self, prefix, name, relpath):
        base = f"{prefix}-{slugify(name)}"
        cand, i = base, 2
        while cand in self.ids:
            cand, i = f"{base}-{i}", i + 1
        self.ids[cand] = relpath
        return cand


def transform_content(rule, rel, text, plan, minted):
    """Return transformed file content for note/source/user rules (md only)."""
    kind = rule.get("transform", "copy")
    stem = os.path.splitext(os.path.basename(rel))[0]
    today = _today()
    defaults = plan.get("defaults") or {}
    domain = rule.get("domain", defaults.get("domain", "personal"))
    cls = rule.get("classification", defaults.get("classification", "internal"))
    if kind == "note" or kind == "user":
        old, body = parse_note(text)
        fm = {"id": minted.mint("note", stem, rel), "type": "note",
              "subtype": rule.get("subtype", "concept"),
              "created": str(old.get("created") or today), "updated": today,
              "summary": extract_summary(body) or f"Imported: {stem}.",
              "status": STATUS_MAP.get(str(old.get("status", "")).lower(), "draft"),
              "domain": domain, "classification": cls}
        for k in ("tags", "aliases"):
            if old.get(k):
                fm[k] = old[k]
        # every other legacy key survives as an x_ extension — nothing is lost
        for k, v in old.items():
            if k in ("id", "type", "subtype", "created", "updated", "summary",
                     "status", "tags", "aliases") or v in (None, "", []):
                continue
            fm["x_" + re.sub(r"[^a-z0-9_]+", "_", str(k).lower()).strip("_")] = v
        return fm_block(fm) + body
    if kind == "source":
        fm = {"id": minted.mint("source", stem, rel), "type": "source",
              "subtype": rule.get("subtype", "document"),
              "created": today, "updated": today,
              "summary": f"Imported source: {rel}.",
              "captured_at": today, "original_location": rel.replace(os.sep, "/"),
              "domain": domain, "classification": cls}
        return fm_block(fm) + text
    return text


def _contains_line(name, pfiles, subdirs):
    """One truthful sentence about what a minted project stub actually holds.
    SPEC-import-review-queue summary truth: empty scaffolding (preserved dirs,
    0 files) is said to be empty — never advertised as material that doesn't
    exist (the 'Contains: Notes, Writing' data-loss scare, both dirs empty)."""
    total = len(pfiles)
    parts = []
    for sub in sorted(subdirs):
        m = sum(1 for f in pfiles if f.startswith(sub + "/"))
        parts.append(f"{sub} (empty scaffolding — 0 files)" if m == 0
                     else f"{sub} ({m} file{'s' if m != 1 else ''})")
    top = sum(1 for f in pfiles if "/" not in f)
    if total == 0:
        inner = ", ".join(sorted(subdirs)) or "no files, no folders"
        return f"Contains: empty scaffolding only — {inner} (0 files)."
    if top and subdirs:
        parts.append(f"{top} file{'s' if top != 1 else ''} at top level")
    detail = f" — {', '.join(parts)}" if parts else ""
    return f"Contains: {total} file{'s' if total != 1 else ''}{detail}."


def build_plan_entries(root, plan, files, dirs, source_data, rep, review_days=14):
    """(dest_rel, source_rel, transformed_or_None) per file + issue lists +
    the minted project-stub records (for the review queue)."""
    minted = Minted()
    entries, issues = [], {"collisions": [], "sanitized": [], "case_collisions": [],
                           "unsafe_paths": [], "authority_paths": [],
                           "neutralized_authority": [],
                           "secret_flags": [], "quarantined": 0}
    stubs = []
    renames = plan.get("renames") or {}
    rules = plan.get("rules") or []
    seen_ci = {}
    for rel in files:
        if plan["mode"] == "verbatim":
            out = renames.get(rel, rel)  # root-level adapter-slot rename
            rule = {"transform": "copy"}
        else:
            rule = _rule_for(rules, rel)
            out = _dest_rel(rule, renames.get(rel, rel))
            if rule.get("prefix_parent"):
                parent = os.path.basename(os.path.dirname(rel))
                if parent:
                    d, fn = os.path.split(out)
                    out = os.path.join(d, f"{parent} — {fn}")
            if rule is rules[-1]:
                issues["quarantined"] += 1
                # The terminal rule is the explicit nothing-dropped quarantine.
                # Preserve boot-named content there under an inert filename; a
                # file named AGENTS.md/CLAUDE.md can acquire subtree authority
                # merely through placement even when its prose is never copied.
                parts = out.replace(os.sep, "/").split("/")
                boot = {_collision_key(name) for name in BOOT_FILENAMES}
                runtime_dirs = {_collision_key(name) for name in RUNTIME_AUTHORITY_DIRS}
                neutral = []
                for part in parts:
                    if _collision_key(part) in boot | runtime_dirs:
                        prior = part
                        part = part + ".untrusted-content"
                        issues["neutralized_authority"].append(f"{prior} -> {part}")
                    neutral.append(part)
                out = "/".join(neutral)
        parts = []
        for part in out.split(os.sep):
            clean = sanitize(part)
            if clean != part:
                issues["sanitized"].append(f"{part} -> {clean}")
            parts.append(clean)
        out = os.path.join(*parts)
        issue = _destination_path_issue(root, out)
        if issue:
            issues["unsafe_paths"].append(issue)
        authority = _authority_destination(out, root)
        if authority:
            issues["authority_paths"].append(
                f"{out}: untrusted import cannot write to {authority}"
            )
        content = None
        if rel.endswith(".md"):
            text = source_data[rel.replace(os.sep, "/")].decode("utf-8", errors="replace")
            for pat in SECRET_PATTERNS:
                if pat.search(text):
                    issues["secret_flags"].append(rel)
                    break
            if rule.get("transform", "copy") != "copy":
                content = transform_content(rule, rel, text, plan, minted)
        entries.append((out, rel, content))
    # declared adaptations: anchor-asserted content patches (the TX-checker seam)
    patched = []
    by_rel = {rel: i for i, (_, rel, _) in enumerate(entries) if rel}
    for pt in (plan.get("patches") or []):
        prel = pt["file"].replace("/", os.sep)
        if prel not in by_rel:
            issues.setdefault("patch_failures", []).append(f"{pt['file']}: not in the import set")
            continue
        i = by_rel[prel]
        out, rel, content = entries[i]
        text = (content if content is not None else
                source_data[rel.replace(os.sep, "/")].decode("utf-8", errors="replace"))
        hits = text.count(pt["find"])
        if hits != 1:
            issues.setdefault("patch_failures", []).append(
                f"{pt['file']}: anchor matched {hits} times (must be exactly 1) — patch refused")
            continue
        entries[i] = (out, rel, text.replace(pt["find"], pt["replace"]))
        patched.append(pt["file"])
    if patched:
        issues["patched"] = patched
    # minted folder-notes (one project record per immediate subfolder of the rule
    # prefix — dirs count too, so a files-empty project still gets its stub)
    review_due = (datetime.date.today()
                  + datetime.timedelta(days=int(review_days))).isoformat()
    for r in rules:
        if r.get("mint_folder_note") != "project":
            continue
        static = r["match"].split("*", 1)[0].rstrip("/")
        posix_dirs = [d.replace(os.sep, "/") for d in dirs]
        tops = sorted({p[len(static) + 1:].split("/")[0]
                       for p in ([f.replace(os.sep, "/") for f in files] + posix_dirs)
                       if p.startswith(static + "/")})
        for name in tops:
            prefix = f"{static}/{name}"
            pfiles = [f.replace(os.sep, "/")[len(prefix) + 1:] for f in files
                      if f.replace(os.sep, "/").startswith(prefix + "/")]
            subdirs = {d[len(prefix) + 1:].split("/")[0] for d in posix_dirs
                       if d.startswith(prefix + "/")}
            contains = _contains_line(name, pfiles, subdirs)
            dest = os.path.join(r["dest"].rstrip("/"), name, f"{sanitize(name)}.md")
            fm = {"id": minted.mint("project", name, dest), "type": "project",
                  "created": _today(), "updated": _today(),
                  "summary": f"Imported project: {name}. Stage not set — owner to review.",
                  "review_due": review_due,
                  "domain": r.get("domain", "personal"),
                  "classification": r.get("classification", "internal")}
            entries.append((dest, None,
                            fm_block(fm) + f"# {name}\n\n{contains}\n\nImported on {_today()}; "
                            f"owner to review (set the stage, confirm contents, or archive) — "
                            f"due {review_due}.\n"))
            stubs.append({"path": dest.replace(os.sep, "/"),
                          "source_folder": prefix, "files": len(pfiles),
                          "review_due": review_due, "contains": contains})
    existing = _existing_path_keys(root)
    planned = {}

    def record_planned(dest, kind):
        key = _collision_key(dest)
        if key in planned:
            issues["case_collisions"].append(
                f"{dest} ({kind}) vs {planned[key]} (duplicate planned destination)"
            )
        else:
            planned[key] = dest
        if key in existing:
            issues["collisions"].append(f"{dest} vs existing {existing[key]}")

    for dest, _, _ in entries:
        issue = _destination_path_issue(root, dest)
        if issue and issue not in issues["unsafe_paths"]:
            issues["unsafe_paths"].append(issue)
        authority = _authority_destination(dest, root)
        message = f"{dest}: untrusted import cannot write to {authority}" if authority else None
        if message and message not in issues["authority_paths"]:
            issues["authority_paths"].append(message)
        record_planned(dest, "file")
    for directory in dirs if plan["mode"] == "verbatim" else []:
        issue = _destination_path_issue(root, directory)
        if issue and issue not in issues["unsafe_paths"]:
            issues["unsafe_paths"].append(issue)
        authority = _authority_destination(directory, root)
        message = (f"{directory}: untrusted import cannot create {authority}"
                   if authority else None)
        if message and message not in issues["authority_paths"]:
            issues["authority_paths"].append(message)
        record_planned(directory, "directory")
    return entries, issues, stubs


def link_baseline(files, source_data):
    """Unresolved wikilinks inside the source itself — pre-existing breakage
    the import must not be blamed for (971-link lesson, doc 12)."""
    basenames = set()
    for f in files:
        b = os.path.splitext(os.path.basename(f))[0].lower()
        basenames.add(b)
        basenames.add(os.path.basename(f).lower())
    unresolved = 0
    for f in files:
        if not f.endswith(".md"):
            continue
        text = source_data[f.replace(os.sep, "/")].decode("utf-8", errors="replace")
        for m in WIKILINK.finditer(text):
            t = m.group(1).strip().split("/")[-1].lower()
            if t and t not in basenames and t + ".md" not in basenames:
                unresolved += 1
    return unresolved


def registry_payload(text, plan):
    """Return safely serialized registry YAML plus the number of additions."""
    regs = plan.get("register_folders") or []
    if not regs:
        return None, 0
    document = yaml.safe_load(text)
    if not isinstance(document, dict) or not isinstance(document.get("folders"), dict):
        raise UnsafeImportError("folder registry is not a folders mapping")
    existing = document["folders"]
    added = 0
    taken = set(existing)
    for r in regs:
        if any(isinstance(v, dict) and v.get("path") == r["path"]
               for v in existing.values()):
            continue  # this path is already registered — nothing to add
        fid = r.get("id") or slugify(r["path"])
        while fid in taken:  # id collision with a DIFFERENT path — disambiguate, never skip
            fid = "imported-" + fid if not fid.startswith("imported-") else fid + "-2"
        taken.add(fid)
        attrs = {"path": r["path"], "purpose": r.get("purpose", "foreign-import")}
        if r.get("conventions"):
            attrs["conventions"] = r["conventions"]
        existing[fid] = attrs
        added += 1
    payload = yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=1000)
    yaml.safe_load(payload)  # serialization must itself remain parseable
    return payload, added


def review_queue_text(stubs):
    """The generated review-queue artifact (SPEC-import-review-queue): one file
    listing every import-minted stub — the delta-register pattern. A convenience
    VIEW over `review_due` + `aios review-due` (which are the actual queue);
    generated, never hand-maintained. Lands beside the import report."""
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    lines = ["---", "type: system-doc", "file_class: generated", "generated: true",
             "generator: aios-import", f"generated_at: {now}", "do_not_edit: true",
             "summary: Review queue for the project stubs this import minted "
             "(generated view; the queue itself is review_due + `aios review-due`).",
             "---", "", "# Import review queue", "",
             "Every project stub this import minted, each carrying `review_due`. "
             "\"Review\" means: set the stage, confirm the contents, or archive it. "
             "`aios review-due` surfaces these when due; `aios health` reports any "
             "left unreviewed past their date.", "",
             "| stub | source folder | files | review_due |",
             "| --- | --- | --- | --- |"]
    for s in stubs:
        lines.append(f"| {s['path']} | {s['source_folder']} | {s['files']} | {s['review_due']} |")
    lines += ["", "Contains lines (as written into each stub):", ""]
    lines += [f"- {s['path']}: {s['contains']}" for s in stubs]
    return "\n".join(lines) + "\n"


def run(root, args, rep: Report):
    if not ai_writes_enabled(root):
        rep.error("kill switch is off — refusing to run (dry-run included: import is a write command)")
        return rep
    plan, pdir = load_plan(root, args, rep)
    if not plan:
        return rep
    marker = os.path.join(pdir, "APPLIED.yaml")
    if os.path.lexists(marker):
        rep.error(f"this import already ran ({marker}) — imports are one-time; "
                  "start a new numbered plan for another pass")
        return rep
    review_days = getattr(args, "review_days", None)
    if review_days is None:
        review_days = plan.get("review_after_days", 14)
    try:
        review_days = int(review_days)
    except (TypeError, ValueError):
        rep.error(f"review days must be an integer (got {review_days!r})")
        return rep
    source_tree = None
    try:
        try:
            source_tree = open_readonly_tree(plan["source"])
            files, dirs = walk_source(plan, source_tree)
            source_data = source_tree.read_files(
                files, max_file_bytes=IMPORT_MAX_FILE_BYTES,
                max_total_bytes=IMPORT_MAX_TOTAL_BYTES,
            )
        except (SafePathError, UnsafeImportError) as exc:
            rep.error(f"import refused before writes: {exc}")
            return rep
        entries, issues, stubs = build_plan_entries(
            root, plan, files, dirs, source_data, rep, review_days
        )
        baseline = link_baseline(files, source_data)
    except Exception:
        if source_tree is not None:
            source_tree.close()
        raise

    if plan.get("register_folders"):
        registry_path = os.path.join(
            root, "System", "Registries", "folder-registry.yaml"
        )
        try:
            registry_batch = preflight_contained_regular_files(
                root, [registry_path], require_writable=False
            )
            try:
                registry_current = registry_batch.read_texts()[registry_path]
            finally:
                registry_batch.close()
            registry_payload(registry_current, plan)
        except (SafePathError, UnsafeImportError, yaml.YAMLError) as exc:
            rep.error(f"import refused before writes: folder registry is unsafe: {exc}")
            source_tree.close()
            return rep
    rep.info["mode"] = plan["mode"]
    rep.info["files_in_source"] = len(files)
    rep.info["files_planned"] = len(entries)
    rep.info["source_unresolved_links_baseline"] = baseline
    for k, v in issues.items():
        if v:
            rep.info[k] = v if not isinstance(v, list) or len(v) <= 12 else v[:12] + [f"... +{len(v) - 12} more"]
    blocking = (issues["collisions"] or issues["case_collisions"]
                or issues["unsafe_paths"] or issues["authority_paths"]
                or issues.get("patch_failures"))
    if issues["secret_flags"] and not getattr(args, "allow_secret_flags", False):
        blocking = True
        rep.warn(f"{len(issues['secret_flags'])} file(s) match secret patterns — "
                 "owner must review; apply needs --allow-secret-flags")
    if stubs:
        rep.info["project_stubs"] = len(stubs)
    if blocking:
        rep.error("import plan REJECTED before writes: resolve path, authority, "
                  "collision, or secret flags first (see dry-run report)")
        source_tree.close()
        return rep
    if not getattr(args, "apply", False):
        for out, _, _ in entries[:8]:
            rep.info.setdefault("sample", []).append(out)
        rep.info["result"] = "dry-run only — nothing written; re-run with --apply after owner approval"
        source_tree.close()
        return rep
    sub = Report("checkpoint")
    setattr(args, "message", f"pre-import {os.path.basename(pdir)}")
    ckpt_mod.run(root, args, sub)
    if not sub.ok:
        # checkpoint-or-halt (the migrate.py discipline): an import with no
        # recovery point must never write a single file. Trigger seen in the
        # wild: `git init` without a git identity — checkpoint fails, and
        # before this check the import proceeded and reported "checkpoint ?".
        rep.error(f"{os.path.basename(pdir)}: checkpoint FAILED — import refused (nothing written)")
        rep.errors += sub.errors[:3]
        source_tree.close()
        return rep
    rep.info["checkpoint"] = sub.info.get("checkpoint", "?")

    writes = {}
    for out, rel, content in entries:
        writes[out.replace(os.sep, "/")] = (
            content.encode("utf-8") if content is not None
            else source_data[rel.replace(os.sep, "/")]
        )
    marker_rel = os.path.relpath(marker, root).replace(os.sep, "/")
    marker_data = {
        "applied": _today(), "files": len(entries),
        "checkpoint": rep.info["checkpoint"],
        "source_unresolved_links_baseline": baseline,
        "posture": plan.get("posture", "gradual"),
    }
    writes[marker_rel] = yaml.safe_dump(
        marker_data, sort_keys=False, allow_unicode=True
    ).encode("utf-8")

    if stubs:
        queue_rel = os.path.relpath(
            os.path.join(pdir, "review-queue.md"), root
        ).replace(os.sep, "/")
        writes[queue_rel] = review_queue_text(stubs).encode("utf-8")

    replacement_paths = []
    registry_rel = "System/Registries/folder-registry.yaml"
    if plan.get("register_folders"):
        replacement_paths.append(os.path.join(root, *registry_rel.split("/")))
    journal_rel = "System/Journal/change-journal.md"
    journal_path = os.path.join(root, *journal_rel.split("/"))
    if os.path.lexists(journal_path):
        replacement_paths.append(journal_path)

    replace_batch = None
    registered = 0
    try:
        if replacement_paths:
            replace_batch = preflight_contained_regular_files(root, replacement_paths)
            current = replace_batch.read_texts()
            if plan.get("register_folders"):
                registry_text, registered = registry_payload(
                    current[os.path.join(root, *registry_rel.split("/"))], plan
                )
                if registry_text is not None:
                    writes[registry_rel] = registry_text.encode("utf-8")
            if journal_path in current:
                journal_text = current[journal_path]
                journal_text += (
                    f"\n- {_today()} · import · {os.path.basename(pdir)} · {len(entries)} files "
                    f"({plan['mode']}) · checkpoint {rep.info['checkpoint']}"
                )
                writes[journal_rel] = journal_text.encode("utf-8")
        atomic_create_files(
            root, writes,
            replace_batch=replace_batch,
            create_dirs=tuple(d.replace(os.sep, "/") for d in dirs)
            if plan["mode"] == "verbatim" else (),
        )
    except (SafePathError, UnsafeImportError, yaml.YAMLError) as exc:
        rep.error(f"import transaction refused or rolled back: {exc}")
        source_tree.close()
        return rep
    finally:
        if replace_batch is not None:
            replace_batch.close()
    source_tree.close()

    if registered:
        rep.info["registered_folders"] = registered
    if stubs:
        rep.info["review_queue"] = queue_rel
        rep.info["review_note"] = (f"{len(stubs)} project stub(s) minted, review due "
                                   f"{stubs[0]['review_due']} — review = set the stage, confirm "
                                   f"contents, or archive; `aios review-due` tracks them")
    vr = Report("validate")
    v_mod.run(root, args, vr)
    if not vr.ok:
        # F23: the one-time marker guards against double-apply on SUCCESS, not
        # against recovery. Remove it so restore-then-re-run works; the pre-import
        # checkpoint is the way back and register_folders is idempotent.
        try:
            os.remove(marker)
        except OSError:
            pass
        rep.error(f"post-import validation FAILED ({len(vr.errors)} errors) — the import WAS applied; "
                  f"restore checkpoint {rep.info['checkpoint']}, then fix the plan and re-run")
        rep.errors += vr.errors[:10]
        return rep
    rep.info["applied"] = len(entries)
    return rep
