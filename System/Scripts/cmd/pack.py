"""vault.pack — the mechanical core of pack install/update/remove.

Determinism audit finding 1: manage-packs was the one trust-boundary procedure
whose mechanics a model still hand-performed — the manifest validation of a
third-party ZIP, the semver compare, the place/replace, the DEC-077 recovery
ordering. The first foreign artifact ever pushed through the hand path
(kepano/obsidian-skills) found a real hole; this command owns those guarantees
the way `aios import` owns the vault-import ones. The manage-packs capability
keeps the human side: presenting the plan and obtaining the explicit OK.

Modes (mirrors import's verify-then-apply discipline):
  aios pack <zip> --verify            read-only: manifest gate + install/update plan
  aios pack <zip> --apply --confirm   checkpoint, place/replace, generate, validate;
                                      on failure: remove-placed-pack FIRST, then
                                      rollback, regenerate, and trust only validate
                                      (DEC-077); on success delete the source ZIP
  aios pack <id> --remove --confirm   checkpoint, delete Packs/<name>/, generate,
                                      validate, leave-no-trace check

--apply / --remove honor the kill switch (wired in aios.py). --confirm carries
the owner's OK from the capability's step 4 — the command never asks questions.

A PACK ZIP IS A STRANGER'S ARTIFACT. Nothing inside one may produce a traceback:
every malformed manifest — wrong type, wrong shape, unexpected nesting, invalid
YAML, non-UTF-8 bytes, a corrupt or encrypted ZIP, a member that escapes the
pack folder — must come back as an actionable error with a non-zero exit, having
changed nothing on disk. The contract itself lives in
`System/Schemas/pack-manifest.yaml`; this module loads it and gates against it.
"""
from __future__ import annotations
import datetime, hashlib, json, os, re, shutil, stat, tempfile, unicodedata, zipfile
import yaml
from lib.frontmatter import iter_markdown
from lib.packtrust import append_receipt, canonical_json, pack_tree_sha256
from lib.report import Report

# Fallback contract, used only if System/Schemas/pack-manifest.yaml is missing or
# unreadable — the gate must still work in a vault whose schema folder is damaged.
# `test_pack.py::test_schema_and_code_constants_agree` keeps the two identical.
KINDS = ("capability", "role-pack", "life-skill-pack", "governance-kit", "starter-bundle")
ID_PATTERN = r"^pack-[a-z0-9-]+$"
SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"
REQUIRED_KEYS = ("id", "name", "version", "kind", "license", "source")
SPDX_LICENSE_IDS = (
    "0BSD", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0",
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
    "ISC", "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only",
    "LGPL-3.0-or-later", "MIT", "MPL-2.0", "Unlicense",
)
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
LICENSE_MAX_BYTES = 256 * 1024
ZIP_MAX_MEMBERS = 10_000
ZIP_MAX_MEMBER_BYTES = 64 * 1024 * 1024
ZIP_MAX_TOTAL_BYTES = 512 * 1024 * 1024
ZIP_MAX_COMPRESSION_RATIO = 200
PMM_LICENSE_SHA256 = "e5bb369acb43cb5c66c1c1b97cbc45586d78cbe18adba33f9c3ae78e0940d50a"
ID_RE = re.compile(ID_PATTERN)
SEMVER_RE = re.compile(SEMVER_PATTERN)

SCHEMA_REL = os.path.join("System", "Schemas", "pack-manifest.yaml")


def _contract(root, rep: Report):
    """The manifest contract as data. Falls back to the constants above, loudly."""
    c = {"kinds": KINDS, "id_pattern": ID_PATTERN,
         "version_pattern": SEMVER_PATTERN, "required": REQUIRED_KEYS}
    path = os.path.join(root, SCHEMA_REL)
    try:
        with open(path, encoding="utf-8") as stream:
            d = yaml.safe_load(stream) or {}
        pm = d.get("pack_manifest") if isinstance(d, dict) else None
        if not isinstance(pm, dict):
            raise ValueError("no `pack_manifest:` mapping")
        keys = pm.get("keys") or {}
        kinds = ((keys.get("kind") or {}).get("vocabulary")
                 if isinstance(keys.get("kind"), dict) else None)
        if isinstance(kinds, list) and kinds:
            c["kinds"] = tuple(str(k) for k in kinds)
        for key, field in (("id_pattern", "id"), ("version_pattern", "version")):
            pat = (keys.get(field) or {}).get("pattern") if isinstance(keys.get(field), dict) else None
            if isinstance(pat, str) and pat:
                re.compile(pat)          # a bad pattern falls back, never raises
                c[key] = pat
        req = pm.get("required_keys")
        if isinstance(req, list) and req:
            c["required"] = tuple(str(k) for k in req)
    except (OSError, yaml.YAMLError, ValueError, re.error, UnicodeDecodeError) as e:
        rep.warn(f"{SCHEMA_REL} unreadable ({type(e).__name__}) — gating on the "
                 f"built-in contract; restore the schema file")
    return c


def _ver(s):
    try:
        return tuple(int(x) for x in str(s).split("."))
    except (TypeError, ValueError):
        return (0,)


# ---------------------------------------------------------------------------
# SCAFFOLD vs WORKSPACE (DEC-112, SPEC-pack-workspace-split).
#
# DEC-061's contract — "install places the folder; update replaces it wholesale;
# delete removes it leave-no-trace" — is correct for a pack that is pure vendor
# scaffold. It is destructive for a CONTENT-BEARING role pack, which is now the
# commercial shape: once a client's vault is in use, `Packs/<name>/` holds their
# messaging hub, enablement library, intelligence hub, published assets, voice
# profile and company config. An update destroyed all of it and reported
# success; "leave-no-trace" actively reassured the person about to lose it.
#
# A pack may now declare a `layout:` block naming three path classes. Silence is
# the old behaviour, exactly: an undeclared path is scaffold, so **every pack
# that ships no `layout:` block behaves bit-identically to before** — the
# acceptance bar for this change, and a test.
LAYOUT_CLASSES = ("scaffold", "workspace", "seed")
# The first release that understands `layout:`. A pack declaring one MUST also
# declare at least this as its min_system_version — see _layout_min_gate.
LAYOUT_MIN_SYSTEM_VERSION = "1.57.0"
SCAFFOLD_BASELINE = ".pack-scaffold-baseline.json"


def _norm_prefix(p):
    """A declared layout path, normalised for prefix matching: posix separators,
    no leading `./` or `/`, no trailing `/`."""
    p = str(p).replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.strip("/")


def _read_layout(man, errs):
    """Parse `layout:` into {class: [normalised paths]}. Absent → None, which
    means 'this pack declares no workspace' and selects the legacy path."""
    raw = man.get("layout")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errs.append(f"layout: must be a mapping of {list(LAYOUT_CLASSES)} → path "
                    f"lists, got {type(raw).__name__}")
        return None
    out = {c: [] for c in LAYOUT_CLASSES}
    for key, value in raw.items():
        if key not in LAYOUT_CLASSES:
            errs.append(f"layout.{key}: unknown class — expected one of "
                        f"{list(LAYOUT_CLASSES)}")
            continue
        for p in _norm_paths(value, f"layout.{key}", errs):
            why = _bad_path(p)
            if why:
                errs.append(f"layout.{key} path '{p}': {why}")
                continue
            out[key].append(_norm_prefix(p))
    # One path in two classes is an authoring error with a destructive reading —
    # refuse rather than let longest-prefix silently pick a winner.
    seen = {}
    for cls, paths in out.items():
        for p in paths:
            if p in seen:
                errs.append(f"layout: path '{p}' is declared both as {seen[p]} and "
                            f"as {cls} — it can only be one")
            seen[p] = cls
    return out


def _classify_path(rel, layout):
    """Which layout class owns this pack-relative path?

    LONGEST DECLARED PREFIX WINS, so a pack can carve a scaffold subfolder out
    of a workspace tree (or the reverse) and the more specific declaration is
    the one that counts. Undeclared → scaffold, which is what makes a pack with
    no `layout:` behave exactly as it always has."""
    if not layout:
        return "scaffold"
    rel = _norm_prefix(rel)
    best, best_len = "scaffold", -1
    for cls in LAYOUT_CLASSES:
        for p in layout.get(cls, []):
            if p and (rel == p or rel.startswith(p + "/")) and len(p) > best_len:
                best, best_len = cls, len(p)
    return best


def _scaffold_hashes(dest, layout):
    """{pack-relative path: sha256} for every scaffold file on disk. Written at
    install (§4.3) so a later update can tell a file the USER edited from one
    still exactly as the vendor shipped it."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(dest):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn == SCAFFOLD_BASELINE:
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, dest).replace(os.sep, "/")
            if _classify_path(rel, layout) != "scaffold":
                continue
            h = hashlib.sha256()
            try:
                with open(p, "rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        h.update(chunk)
            except OSError:
                continue
            out[rel] = h.hexdigest()
    return out


def _load_scaffold_baseline(dest):
    try:
        with open(os.path.join(dest, SCAFFOLD_BASELINE), encoding="utf-8") as fh:
            d = json.load(fh)
        return dict(d.get("files", {})) if isinstance(d, dict) else {}
    except (OSError, ValueError, UnicodeDecodeError):
        return {}


def _write_scaffold_baseline(dest, layout, version):
    data = {"version": str(version),
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "files": _scaffold_hashes(dest, layout)}
    try:
        with open(os.path.join(dest, SCAFFOLD_BASELINE), "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
    except OSError:
        pass
    return len(data["files"])


# --- shape guards ------------------------------------------------------------
# Everything below turns a malformed third-party manifest into a message.

def _norm_paths(value, where, errs):
    """Normalize a path group into a list of strings. Accepts a mapping of
    group → paths, a flat list, or a single string; both shapes are real in the
    field (Content Engine nests resources under components; PMM Engine declares
    a flat top-level resources list). Anything else is reported, never raised."""
    out = []
    if value is None:
        return out
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        for group, paths in value.items():
            if isinstance(paths, dict):
                errs.append(f"{where}.{group}: nested mapping — a group holds a "
                            f"list of paths, not another mapping")
                continue
            out.extend(_norm_paths(paths, f"{where}.{group}", errs))
        return out
    if isinstance(value, (list, tuple)):
        for i, p in enumerate(value):
            if isinstance(p, str):
                out.append(p)
            else:
                errs.append(f"{where}[{i}]: path must be a string, got "
                            f"{type(p).__name__} ({str(p)[:40]!r})")
        return out
    errs.append(f"{where}: must be a list of paths or a mapping of group → paths, "
                f"got {type(value).__name__}")
    return out


def _bad_path(p):
    """Reason this listed path is unusable, or None. Rejected at the gate so a
    traversing pack never reaches placement."""
    if not p.strip():
        return "empty path"
    if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        return "must be relative to the pack root, not absolute"
    parts = re.split(r"[/\\]", p)
    if ".." in parts:
        return "contains a `..` segment — a pack may not reach outside its own folder"
    return None


def _bad_attached_file_path(path):
    """Return why an attached-license path is unsafe or non-canonical."""
    if not isinstance(path, str):
        return f"must be a string, got {type(path).__name__}"
    if not path or not path.strip():
        return "empty path"
    if "\x00" in path or "\\" in path:
        return "must use a canonical relative POSIX path"
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        return "must be relative to the pack root, not absolute"
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "must not contain empty, `.` or `..` path segments"
    return None


def _zip_member_is_regular(info):
    """ZIP members default to DOS metadata; when Unix mode exists, enforce it."""
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    return not info.is_dir() and (file_type == 0 or stat.S_ISREG(mode))


def _license_gate(pid, license_value, archive, prefix, errs):
    """Validate one unambiguous license form against actual archive bytes."""
    if isinstance(license_value, str):
        if license_value not in SPDX_LICENSE_IDS:
            errs.append(
                f"license '{license_value}' is not a supported SPDX identifier; "
                "use an attached license mapping with file and sha256"
            )
        if pid == "pack-pmm":
            errs.append(
                "pack-pmm must attach its approved proprietary license using "
                "license: {file: ..., sha256: ...}"
            )
        return
    if not isinstance(license_value, dict):
        errs.append(
            f"license must be a supported SPDX string or an attached-file "
            f"mapping, got {type(license_value).__name__}"
        )
        return
    if set(license_value) != {"file", "sha256"}:
        errs.append("attached license mapping must contain exactly file and sha256")
        return
    relative = license_value.get("file")
    expected = license_value.get("sha256")
    why = _bad_attached_file_path(relative)
    if why:
        errs.append(f"license.file '{relative}': {why}")
        return
    if not isinstance(expected, str) or not HASH_RE.fullmatch(expected):
        errs.append("license.sha256 must be an exact lowercase SHA-256")
        return
    if pid == "pack-pmm" and expected != PMM_LICENSE_SHA256:
        errs.append(
            "pack-pmm license.sha256 does not match the approved proprietary "
            "license bytes"
        )
        return
    full = prefix + relative
    matches = [info for info in archive.infolist() if info.filename == full]
    if len(matches) != 1:
        errs.append(
            f"license file must appear exactly once in ZIP: {relative} "
            f"(found {len(matches)})"
        )
        return
    info = matches[0]
    if not _zip_member_is_regular(info):
        errs.append(f"license file is not a regular file: {relative}")
        return
    if info.file_size > LICENSE_MAX_BYTES:
        errs.append(
            f"license file exceeds {LICENSE_MAX_BYTES} byte safety limit: {relative}"
        )
        return
    try:
        with archive.open(info) as stream:
            digest = hashlib.sha256(stream.read(LICENSE_MAX_BYTES + 1)).hexdigest()
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        errs.append(f"license file cannot be read: {relative} ({exc})")
        return
    if digest != expected:
        errs.append(
            f"license file hash mismatch: {relative} expected {expected}, got {digest}"
        )


def _escapes(name):
    """True if this ZIP member would be written outside the pack folder."""
    parts = re.split(r"[/\\]", name)
    return name.startswith("/") or ".." in parts or (len(name) > 1 and name[1] == ":")


def _in_zip(names, full):
    """A listed path is present if the ZIP carries it as a file, as a directory
    entry, or as anything beneath it — ZIPs need not store directory entries,
    and role packs legitimately list folders (PMM's '01 Messaging Hub')."""
    if full in names or (full + "/") in names:
        return True
    pre = full.rstrip("/") + "/"
    return any(n.startswith(pre) for n in names)


def _dup_top_level_keys(text):
    """YAML lets a repeated key silently win, which can disable a gate clause —
    a manifest declaring `kind: capability` then `kind: role-pack` is gated on
    the second. The note-class schemas already carry this guard."""
    keys = re.findall(r"^([A-Za-z_][\w-]*):", text, re.M)
    return sorted({k for k in keys if keys.count(k) > 1})


def _strings(value, where, errs):
    """A list of strings, strictly — a bare string here is an author error, not
    a 12-character iteration."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        out = []
        for i, v in enumerate(value):
            if isinstance(v, str):
                out.append(v)
            else:
                errs.append(f"{where}[{i}]: must be a string, got {type(v).__name__}")
        return out
    errs.append(f"{where}: must be a list of strings, got {type(value).__name__}")
    return []


def _find_zips(root):
    out = []
    for f in sorted(os.listdir(root)):
        if not f.lower().endswith(".zip"):
            continue
        p = os.path.join(root, f)
        try:
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
        except (zipfile.BadZipFile, OSError):
            continue
        if any(n.split("/", 1)[-1] == "pack.yaml" and n.count("/") <= 1 for n in names):
            out.append(p)
    return out


def _manifest_and_prefix(zpath):
    """Return (manifest dict, prefix, raw text, error). `pack.yaml` may sit at
    the zip root or inside one top-level folder (GitHub's Download ZIP shape).

    Every way a third-party file can be unreadable — not a ZIP, truncated,
    encrypted, non-UTF-8, invalid YAML, not a mapping — comes back as the
    `error` string. This function never raises on a hostile input."""
    base = os.path.basename(zpath)
    try:
        with zipfile.ZipFile(zpath) as z:
            cand = next((n for n in z.namelist()
                         if n.split("/")[-1] == "pack.yaml" and n.count("/") <= 1), None)
            if cand is None:
                return None, "", "", f"{base}: no top-level pack.yaml — not a pack ZIP"
            prefix = cand[: -len("pack.yaml")]
            raw = z.read(cand)
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
        return None, "", "", f"{base}: not a readable ZIP archive ({e})"
    except RuntimeError as e:      # zipfile raises this for encrypted members
        return None, "", "", f"{base}: cannot read pack.yaml — {e}"
    except (OSError, EOFError) as e:
        return None, "", "", f"{base}: cannot be opened ({type(e).__name__}: {e})"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return None, prefix, "", (f"{base}: pack.yaml is not valid UTF-8 "
                                  f"(byte {e.start}) — re-save it as UTF-8")
    try:
        man = yaml.safe_load(text)
    except yaml.YAMLError as e:
        detail = str(getattr(e, "problem", None) or e).strip().splitlines()[0]
        mark = getattr(e, "problem_mark", None)
        at = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        return None, prefix, text, f"{base}: pack.yaml is not valid YAML — {detail}{at}"
    if man is None:
        return None, prefix, text, f"{base}: pack.yaml is empty"
    if not isinstance(man, dict):
        return None, prefix, text, (f"{base}: pack.yaml must be a YAML mapping of "
                                    f"manifest keys, got {type(man).__name__}")
    return man, prefix, text, None


def _zip_preflight(zpath, prefix, errs):
    """Reject ambiguous paths and special file types before any vault write.

    ZIP names are compared using the filesystem-portable identity NFC +
    casefold. This prevents two archive members from becoming one path on a
    case-insensitive or normalization-insensitive filesystem.
    """
    seen_exact, seen_portable = {}, {}
    try:
        with zipfile.ZipFile(zpath) as archive:
            infos = archive.infolist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError) as exc:
        errs.append(f"ZIP is not readable during member preflight: {exc}")
        return
    if len(infos) > ZIP_MAX_MEMBERS:
        errs.append(f"ZIP contains {len(infos)} members; safety limit is "
                    f"{ZIP_MAX_MEMBERS}")
        return
    total = sum(info.file_size for info in infos if not info.is_dir())
    if total > ZIP_MAX_TOTAL_BYTES:
        errs.append(f"ZIP expands to {total} bytes; safety limit is "
                    f"{ZIP_MAX_TOTAL_BYTES}")
    for info in infos:
        name = info.filename.replace("\\", "/")
        key = unicodedata.normalize("NFC", name.rstrip("/")).casefold()
        if name in seen_exact:
            errs.append(f"duplicate ZIP member name: {name}")
        else:
            seen_exact[name] = name
        previous = seen_portable.get(key)
        if previous is not None and previous != name:
            errs.append(f"ZIP member path collision after NFC/case normalization: "
                        f"{previous} and {name}")
        else:
            seen_portable[key] = name

        # external_attr is meaningful for Unix-created entries. Zero mode is a
        # common regular-file encoding; otherwise only regular files/directories
        # are accepted. Symlinks, devices, sockets and FIFOs are never materialized.
        mode = (info.external_attr >> 16) & 0xFFFF
        kind = stat.S_IFMT(mode)
        is_dir = info.is_dir() or name.endswith("/")
        if not is_dir and info.file_size > ZIP_MAX_MEMBER_BYTES:
            errs.append(f"ZIP member exceeds {ZIP_MAX_MEMBER_BYTES}-byte safety "
                        f"limit: {name}")
        if (not is_dir and info.file_size > 0
                and info.file_size / max(1, info.compress_size)
                > ZIP_MAX_COMPRESSION_RATIO):
            errs.append(f"ZIP member compression ratio exceeds "
                        f"{ZIP_MAX_COMPRESSION_RATIO}:1 safety limit: {name}")
        if info.create_system == 3 and kind not in (
                0, stat.S_IFREG, stat.S_IFDIR if is_dir else stat.S_IFREG):
            errs.append(f"ZIP member is not a regular file or directory: {name}")
        elif info.create_system == 3 and is_dir and kind not in (0, stat.S_IFDIR):
            errs.append(f"ZIP directory member has an unsafe file type: {name}")
        elif info.create_system == 3 and not is_dir and kind not in (0, stat.S_IFREG):
            errs.append(f"ZIP file member has an unsafe file type: {name}")


def _review(zpath, prefix, man, listed, action):
    """Return the exact byte-bound approval object for this archive."""
    member_sha = {}
    with zipfile.ZipFile(zpath) as archive:
        for info in archive.infolist():
            if info.is_dir() or info.filename.endswith("/"):
                continue
            rel = info.filename[len(prefix):] if prefix and info.filename.startswith(prefix) \
                else info.filename
            member_sha[rel] = hashlib.sha256(archive.read(info)).hexdigest()
    archive_sha = hashlib.sha256()
    with open(zpath, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            archive_sha.update(chunk)

    license_value = man.get("license")
    license_file = (license_value.get("file")
                    if isinstance(license_value, dict) else None)

    def declared(rel):
        if rel == "pack.yaml":
            return True
        if license_file and rel == license_file:
            return True
        return any(rel == path or rel.startswith(path.rstrip("/") + "/")
                   for path in listed)

    def instruction(rel):
        normalized = unicodedata.normalize("NFC", rel.replace("\\", "/")).casefold()
        parts = normalized.split("/")
        base = parts[-1].casefold()
        return (base in ("agents.md", "claude.md", "skill.md", "agent.md")
                or normalized.startswith(("capabilities/", "agents/", "workflows/",
                                           ".claude/skills/")))

    return {
        "action": action,
        "archive_sha256": archive_sha.hexdigest(),
        "instruction_files": sorted(rel for rel in member_sha if instruction(rel)),
        "member_sha256": dict(sorted(member_sha.items())),
        "pack_id": str(man.get("id")),
        "undeclared_members": sorted(rel for rel in member_sha if not declared(rel)),
        "version": str(man.get("version")),
    }


def _verify(root, zpath, rep: Report):
    """The manifest gate (manage-packs step 2), computed. Returns the plan dict
    on pass, None on failure — errors already on the report.

    Contract in `System/Schemas/pack-manifest.yaml`. Every clause reports; none
    raises. A REJECTED verdict means nothing was touched."""
    man, prefix, raw, err = _manifest_and_prefix(zpath)
    if err:
        rep.error(err)
        rep.info["verdict"] = "REJECTED — change nothing (manage-packs step 2)"
        return None
    con = _contract(root, rep)
    id_re, ver_re = re.compile(con["id_pattern"]), re.compile(con["version_pattern"])
    errs = []
    _zip_preflight(zpath, prefix, errs)

    for k in _dup_top_level_keys(raw):
        errs.append(f"key '{k}' is declared more than once — YAML silently keeps "
                    f"the last, which can disable a gate clause")
    for k in con["required"]:
        if k not in man:
            errs.append(f"required key '{k}' is missing")

    pid = man.get("id")
    if not isinstance(pid, str):
        errs.append(f"id must be a string, got {type(pid).__name__}")
        pid = ""
    elif not id_re.match(pid):
        errs.append(f"id '{pid}' must match pack-[a-z0-9-]+")
    ver = man.get("version")
    if not isinstance(ver, str) or not ver_re.match(ver):
        errs.append(f"version '{ver}' is not semver (X.Y.Z) — quote it if YAML "
                    f"read it as a number or a date")
    kind = man.get("kind")
    if not isinstance(kind, str) or kind not in con["kinds"]:
        errs.append(f"kind '{kind}' not in vocabulary {list(con['kinds'])}")
    license_value = man.get("license")
    if not license_value:
        errs.append("license missing")
    src = man.get("source")
    if not isinstance(src, str) or not src.startswith("https://"):
        errs.append(f"source '{src if src is not None else '(absent)'}' must be an https URL")
    if not isinstance(man.get("name"), str) or not man.get("name", "").strip():
        rep.warn("manifest: no usable `name` — the install plan will show the id instead")
    if not man.get("summary"):
        rep.warn("manifest: no `summary` — the user sees no description of what this pack is")

    try:
        with zipfile.ZipFile(zpath) as z:
            names = set(z.namelist())
            _license_gate(pid, license_value, z, prefix, errs)
    except (zipfile.BadZipFile, OSError, RuntimeError) as e:
        rep.error(f"{os.path.basename(zpath)}: ZIP became unreadable ({e})")
        rep.info["verdict"] = "REJECTED — change nothing (manage-packs step 2)"
        return None

    # A member that would land outside Packs/<name>/ condemns the whole ZIP, and
    # it is caught HERE — before the checkpoint, before any placement. Placement
    # keeps its own assertion, but by then it would be too late to be a report.
    escaping = sorted(n for n in names if _escapes(n))
    for n in escaping[:5]:
        errs.append(f"ZIP entry escapes the pack folder: {n}")
    if len(escaping) > 5:
        errs.append(f"...and {len(escaping) - 5} more escaping ZIP entries")

    listed = []
    for group in ("components", "resources"):
        listed.extend(_norm_paths(man.get(group), group, errs))
    for p in listed:
        why = _bad_path(p)
        if why:
            errs.append(f"listed path '{p}': {why}")
        elif not _in_zip(names, prefix + p):
            errs.append(f"listed path missing from ZIP: {p}")

    # `layout:` (DEC-112). Parsed before the min_system_version check below,
    # which depends on whether one was declared at all.
    layout = _read_layout(man, errs)

    dep = man.get("depends_on")
    if dep is None:
        dep = {}
    elif not isinstance(dep, dict):
        errs.append(f"depends_on must be a mapping, got {type(dep).__name__}")
        dep = {}
    want = _strings(dep.get("core_primitives"), "depends_on.core_primitives", errs)
    if want:
        have = {str(n.meta.get("id")) for n in iter_markdown(root) if n.meta.get("id")}
        for cid in want:
            if cid not in have:
                errs.append(f"core primitive '{cid}' not present in this vault")
    minv = dep.get("min_system_version") or man.get("min_system_version")
    # A pack that declares `layout:` MUST also declare a min_system_version the
    # layout is understood by. This is the whole protection: an older core does
    # not know what `layout:` means and would replace the folder wholesale —
    # taking the user's workspace with it — but every core has always enforced
    # min_system_version, so the declaration is what stops it installing there.
    # Refused at the gate, because the failure it prevents is silent and total.
    if layout is not None and (minv is None or _ver(minv) < _ver(LAYOUT_MIN_SYSTEM_VERSION)):
        errs.append(f"declares layout: but min_system_version is "
                    f"{minv if minv is not None else '(absent)'} — a core older than "
                    f"{LAYOUT_MIN_SYSTEM_VERSION} does not understand layout: and would "
                    f"replace the whole pack folder, destroying the user's workspace. "
                    f"Declare min_system_version: '{LAYOUT_MIN_SYSTEM_VERSION}' or newer")
    if minv is not None:
        if not isinstance(minv, str) or not ver_re.match(minv):
            errs.append(f"min_system_version '{minv}' is not semver (X.Y.Z) — quote it")
        else:
            try:
                with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"),
                          encoding="utf-8") as stream:
                    cur = yaml.safe_load(stream)["system"]["system_version"]
            except Exception:
                cur = "0.0.0"
            if _ver(cur) < _ver(minv):
                errs.append(f"needs system {minv}, this vault is {cur}")
    for e in errs:
        rep.error(f"manifest gate: {e}")
    if errs:
        rep.info["verdict"] = "REJECTED — change nothing (manage-packs step 2)"
        return None

    name = pid[len("pack-"):]
    dest = os.path.join(root, "Packs", name)
    action = "UPDATE" if os.path.isdir(dest) else "INSTALL"
    review = _review(zpath, prefix, man, listed, action)
    plan = {"zip": zpath, "prefix": prefix, "id": pid, "name": name,
            "version": str(man.get("version")), "kind": man.get("kind"),
            "action": action, "dest": dest, "layout": layout,
            "gates": man.get("gates") or man.get("behavior") or "none declared",
            "review": review,
            "review_sha256": hashlib.sha256(canonical_json(review)).hexdigest()}
    if action == "UPDATE":
        old = os.path.join(dest, "pack.yaml")
        try:
            with open(old, encoding="utf-8") as stream:
                prev = yaml.safe_load(stream)
            installed = str(prev.get("version")) if isinstance(prev, dict) else "unknown"
        except (OSError, yaml.YAMLError, UnicodeDecodeError):
            installed = "unknown"
        plan["installed_version"] = installed
        plan["version_direction"] = (
            "newer" if _ver(plan["version"]) > _ver(installed)
            else "same" if _ver(plan["version"]) == _ver(installed) else "DOWNGRADE")
    # §4.7 — silence must not read as safety. The shown plan states, in words,
    # what will be replaced and what is protected, INCLUDING when nothing is.
    if layout is None:
        plan["layout_summary"] = (
            f"this pack declares no workspace — EVERYTHING under Packs/{name}/ "
            f"will be replaced on update, and removed on uninstall")
    else:
        plan["layout_summary"] = "; ".join(
            [f"{cls}: " + (", ".join(layout[cls]) if layout[cls] else "(none)")
             for cls in LAYOUT_CLASSES]
            + ["workspace and seed paths are never replaced by an update, and are "
               "archived rather than deleted on uninstall"])
    rep.info["plan"] = {k: v for k, v in plan.items() if k not in ("zip", "prefix", "dest")}
    rep.info["verdict"] = "manifest gate PASSED"
    return plan


def _vault_notes_citing_this_pack(root, dest):
    """[(vault note, relation field, id)] for every vault note whose frontmatter
    cites an id that ONLY the pack at `dest` defines.

    "Only this pack" is the point: an id the vault also defines, or that another
    installed pack defines, still resolves after removal and is not a reason to
    refuse."""
    try:
        from cmd.packcheck import installed_packs, pack_notes
        from cmd.links import REL_FIELDS, norm_wiki, yaml_ids
    except Exception:                                    # noqa: BLE001
        return []
    mine, others = set(), set(yaml_ids(root))
    for pack_root in installed_packs(root):
        target = mine if os.path.abspath(pack_root) == os.path.abspath(dest) else others
        for n in pack_notes(pack_root):
            if n.meta.get("id"):
                target.add(str(n.meta["id"]))
    for n in iter_markdown(root):
        if n.meta.get("id"):
            others.add(str(n.meta["id"]))
    only_mine = mine - others
    if not only_mine:
        return []
    out = []
    for n in iter_markdown(root):
        for f in REL_FIELDS:
            vals = n.meta.get(f)
            if not vals:
                continue
            for v in (vals if isinstance(vals, list) else [vals]):
                cid = norm_wiki(v)
                if cid in only_mine:
                    out.append((n.relpath, f, cid))
    return out


def _walk_files(dest):
    for dirpath, dirnames, filenames in os.walk(dest):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def _installed_layout(dest):
    """The `layout:` of the pack as INSTALLED — read from the pack's own
    pack.yaml on disk, because uninstall has no incoming ZIP to consult.
    Unreadable or absent → None → today's leave-no-trace deletion (§5.4)."""
    try:
        with open(os.path.join(dest, "pack.yaml"), encoding="utf-8") as stream:
            man = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return None
    if not isinstance(man, dict):
        return None
    return _read_layout(man, [])


def _user_owned_files(dest, layout):
    """Pack-relative paths of everything in a workspace or seed path — the
    user's own work, which an uninstall must never delete."""
    if not layout:
        return []
    out = []
    for p in _walk_files(dest):
        rel = _norm_prefix(os.path.relpath(p, dest))
        if rel == SCAFFOLD_BASELINE:
            continue
        if _classify_path(rel, layout) in ("workspace", "seed"):
            out.append(rel)
    return out


def _sub(root, module, rep: Report, label, **argv):
    from types import SimpleNamespace
    base = dict(json=False, message=None, rollback=None, confirm=False,
                clean=False, force_zip=False, zip_only=False)
    base.update(argv)
    args = SimpleNamespace(**base)
    sub = Report(label)
    module.run(root, args, sub)
    rep.info[label] = f"{len(sub.errors)} errors, {len(sub.warnings)} warnings"
    return sub


def _zip_members(plan):
    """[(zip name, pack-relative path)] for every file member of this pack."""
    out = []
    with zipfile.ZipFile(plan["zip"]) as z:
        for n in z.namelist():
            if plan["prefix"] and not n.startswith(plan["prefix"]):
                continue
            rel = n[len(plan["prefix"]):]
            if not rel or rel.endswith("/"):
                continue
            out.append((n, rel))
    return out


def _place(plan):
    """Write the incoming pack.

    NO `layout:` → the DEC-061 path, byte-for-byte as it always was: rmtree the
    folder, then write every member. A pack that declares nothing must behave
    exactly as it did before this feature existed.

    WITH `layout:` → per-path, by declared class:
      scaffold   replaced (and an edited one is preserved beside `.incoming`)
      workspace  written only if the declared path does not yet exist; once it
                 exists it is the user's and is not read, diffed or replaced
      seed       written per file, only where that file is absent
    Nothing under a workspace or seed path is ever deleted.
    """
    dest, layout = plan["dest"], plan.get("layout")
    report = {"replaced": [], "added": [], "kept_user_edit": [], "incoming": [],
              "workspace_untouched": [], "seed_skipped": [], "removed": []}

    if not layout:
        if os.path.isdir(dest):
            shutil.rmtree(dest)      # full replacement, never a merge
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(plan["zip"]) as z:
            for n, rel in _zip_members(plan):
                tgt = os.path.join(dest, rel)
                if not os.path.abspath(tgt).startswith(os.path.abspath(dest) + os.sep):
                    raise RuntimeError(f"zip entry escapes the pack folder: {n}")
                os.makedirs(os.path.dirname(tgt), exist_ok=True)
                with z.open(n) as fsrc, open(tgt, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
        return report

    fresh = not os.path.isdir(dest)
    baseline = {} if fresh else _load_scaffold_baseline(dest)
    os.makedirs(dest, exist_ok=True)
    # A declared workspace path that already exists is the user's: everything
    # beneath it is skipped wholesale. Decided per DECLARED path, not per file,
    # so a user who deleted an EXAMPLE file never has it re-seeded (§3).
    live_ws = {p for p in layout.get("workspace", [])
               if p and os.path.exists(os.path.join(dest, p))}
    incoming_rels = set()

    with zipfile.ZipFile(plan["zip"]) as z:
        for n, rel in _zip_members(plan):
            tgt = os.path.join(dest, rel)
            if not os.path.abspath(tgt).startswith(os.path.abspath(dest) + os.sep):
                raise RuntimeError(f"zip entry escapes the pack folder: {n}")
            incoming_rels.add(_norm_prefix(rel))
            cls = _classify_path(rel, layout)

            if cls == "workspace":
                owner = next((p for p in sorted(live_ws, key=len, reverse=True)
                              if _norm_prefix(rel) == p
                              or _norm_prefix(rel).startswith(p + "/")), None)
                if owner is not None:
                    report["workspace_untouched"].append(rel)      # §4.1
                    continue
            elif cls == "seed" and os.path.exists(tgt):
                report["seed_skipped"].append(rel)
                continue
            elif cls == "scaffold" and os.path.exists(tgt):
                # §4.3 — never auto-merged. A scaffold file the user edited is
                # KEPT; the incoming version lands beside it for review.
                cur = _sha_file(tgt)
                if baseline and baseline.get(_norm_prefix(rel)) not in (None, cur):
                    tgt = tgt + ".incoming"
                    report["kept_user_edit"].append(rel)
                    report["incoming"].append(rel + ".incoming")
                else:
                    report["replaced"].append(rel)
            else:
                report["added"].append(rel)

            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            with z.open(n) as fsrc, open(tgt, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)

    # §4.4 — a scaffold file the release retired goes, UNLESS the user edited it.
    # Workspace and seed paths are never removed for any reason (§4.6).
    if not fresh:
        for dirpath, dirnames, filenames in os.walk(dest):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                if fn == SCAFFOLD_BASELINE or fn.endswith(".incoming"):
                    continue
                p = os.path.join(dirpath, fn)
                rel = _norm_prefix(os.path.relpath(p, dest))
                if rel in incoming_rels or _classify_path(rel, layout) != "scaffold":
                    continue
                if baseline and baseline.get(rel) not in (None, _sha_file(p)):
                    report["kept_user_edit"].append(rel)   # edited + retired: keep
                    continue
                try:
                    os.remove(p)
                    report["removed"].append(rel)
                except OSError:
                    pass
    _prune_empty_dirs(dest)
    plan["placement"] = report
    return report


def _stage_pack_check(root, plan, rep: Report):
    """Freeze, extract and strictly inspect candidate without touching vault."""
    from cmd import packcheck as packcheck_mod
    tmp = tempfile.mkdtemp(prefix="aios-pack-review-")
    original = plan["zip"]
    snapshot = os.path.join(tmp, "reviewed.zip")
    try:
        shutil.copyfile(original, snapshot)
        snapshot_sha = hashlib.sha256()
        with open(snapshot, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                snapshot_sha.update(chunk)
        if snapshot_sha.hexdigest() != plan["review"]["archive_sha256"]:
            rep.error("pack-check: archive changed while it was being reviewed; "
                      "refusing to install bytes the approval plan did not name")
            rep.info["verdict"] = "REJECTED — change nothing (review hash changed)"
            shutil.rmtree(tmp, ignore_errors=True)
            return False
        staged = os.path.join(tmp, "Packs", plan["name"])
        stage_plan = dict(plan, zip=snapshot, dest=staged, layout=None)
        try:
            _place(stage_plan)
        except Exception as exc:                         # noqa: BLE001 — trust boundary
            rep.error(f"pack-check staging failed: {type(exc).__name__}: {exc}")
            rep.info["verdict"] = "REJECTED — change nothing (staged pack-check)"
            shutil.rmtree(tmp, ignore_errors=True)
            return False
        check = Report("pack-check staged candidate")
        packcheck_mod.check_candidate(root, staged, check)
        rep.info["pack-check"] = (
            f"{len(check.errors)} errors, {len(check.warnings)} warnings; "
            f"review {plan['review_sha256']}")
        for message in check.warnings:
            rep.warn(f"pack-check: {message}")
        for message in check.errors:
            rep.error(f"pack-check: {message}")
        if check.errors:
            rep.info["verdict"] = "REJECTED — change nothing (staged pack-check)"
            shutil.rmtree(tmp, ignore_errors=True)
            return False
        # Placement consumes the frozen snapshot, so the reviewed bytes cannot
        # be swapped after approval/staging. The caller-owned original is kept
        # separately for the post-success disposition rule.
        plan["source_zip"] = original
        plan["zip"] = snapshot
        plan["stage_dir"] = tmp
        return True
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        rep.error(f"pack-check snapshot failed: {type(exc).__name__}: {exc}")
        rep.info["verdict"] = "REJECTED — change nothing (staged pack-check)"
        return False


def _source_is_vault_owned(root, path):
    """Only an input physically inside this vault is disposable on success."""
    try:
        return os.path.commonpath((os.path.realpath(root), os.path.realpath(path))) \
            == os.path.realpath(root)
    except (OSError, ValueError):
        return False


def _pack_install_boundary(event, plan):
    """No-op crash-injection seam for trust-ordering regression tests."""
    del event, plan


def _sha_file(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _prune_empty_dirs(top):
    for dirpath, dirnames, filenames in os.walk(top, topdown=False):
        if dirpath == top:
            continue
        try:
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
        except OSError:
            pass


def _pack_remove_boundary(event):
    """No-op fault/race injection seam for removal transaction tests."""
    del event


def _safe_installed_pack_snapshot(dest):
    """Bind every installed-pack byte without following links or special files."""
    from lib.safepaths import open_readonly_tree

    tree = open_readonly_tree(dest)
    try:
        payloads, digest = tree.snapshot(
            max_file_bytes=ZIP_MAX_MEMBER_BYTES,
            max_total_bytes=ZIP_MAX_TOTAL_BYTES,
        )
    finally:
        tree.close()
    manifest_bytes = payloads.get("pack.yaml")
    layout = None
    if manifest_bytes is not None:
        try:
            manifest = yaml.safe_load(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, yaml.YAMLError):
            manifest = None
        if isinstance(manifest, dict):
            layout = _read_layout(manifest, [])
    return payloads, digest, layout


def run(root, args, rep: Report):
    from cmd import checkpoint as ck_mod, generate as gen_mod, validate as val_mod
    target = getattr(args, "target", None)
    remove = getattr(args, "remove_pack", False)
    apply_ = getattr(args, "apply", False)

    if remove:
        from lib.safepaths import SafePathError, atomic_archive_and_remove_tree
        if not target:
            rep.error("usage: aios pack <pack-id or name> --remove --confirm"); return rep
        if not getattr(args, "confirm", False):
            rep.error("--remove is destructive — pass --confirm after the owner's explicit OK"); return rep
        name = target[len("pack-"):] if target.startswith("pack-") else target
        # A pack name is a single folder under Packs/, nothing else. Without this
        # `aios pack ../../anything --remove --confirm` resolved outside the vault
        # and rmtree'd it, then reported "leave_no_trace: validate green".
        if not name or name != os.path.basename(name.rstrip("/")) or name in (".", ".."):
            rep.error(f"'{target}' is not a pack name — expected a single folder name "
                      f"under Packs/ (or its pack-<name> id), with no path separators")
            return rep
        dest = os.path.join(root, "Packs", name)
        if not os.path.lexists(dest):
            rep.error(f"no installed pack at Packs/{name}/"); return rep
        try:
            pack_payloads, pack_digest, layout = _safe_installed_pack_snapshot(dest)
        except (OSError, SafePathError) as exc:
            rep.error(f"refusing to remove unsafe Packs/{name}/ tree: {exc}")
            return rep
        # §6.3 — removing a pack must not silently break a vault note that cites
        # it. Resolution across the boundary (DEC-113) means a vault note may
        # legitimately declare a pack note as its source; deleting the pack turns
        # that into an unknown id and reddens the user's own vault, which would
        # make packs feel unsafe to remove. So the removal is REFUSED and the
        # citing notes are NAMED — the user edits or accepts, then re-runs.
        citing = _vault_notes_citing_this_pack(root, dest)
        if citing:
            rep.error(
                f"refusing to remove pack-{name}: {len(citing)} vault note(s) cite an id "
                f"that ONLY this pack defines — removing it would leave them referencing "
                f"nothing. Edit or remove these references first: "
                + "; ".join(f"{rel} ({field} -> {cid})" for rel, field, cid in citing[:10])
                + ("" if len(citing) <= 10 else f"; ...and {len(citing) - 10} more"))
            return rep

        # DEC-112. "Leave-no-trace" was written when a pack held nothing but
        # vendor files. On a content-bearing role pack it means the client's
        # entire corpus goes with the uninstall — and the phrase reassures the
        # person about to lose it. Removal now EVACUATES the user's side.
        purge = bool(getattr(args, "purge", False))
        keep = [] if purge else sorted(
            rel for rel in pack_payloads
            if rel != SCAFFOLD_BASELINE
            and _classify_path(rel, layout) in ("workspace", "seed")
        ) if layout else []

        if purge:
            # The only route to the old destructive behaviour, and it must be
            # asked for by name, with a count of what it will take stated first.
            n_user = sum(
                1 for rel in pack_payloads
                if rel != SCAFFOLD_BASELINE
                and layout
                and _classify_path(rel, layout) in ("workspace", "seed")
            )
            rep.info["purge"] = (
                f"PURGE — deleting all {len(pack_payloads)} file(s) under "
                f"Packs/{name}/, including {n_user} in user-owned workspace/seed paths. "
                f"Nothing is archived.")
        checkpoint = _sub(
            root, ck_mod, rep, "checkpoint",
            message=f"pre-uninstall pack-{name}",
        )
        if not checkpoint.ok:
            rep.error(
                f"checkpoint FAILED — refusing to remove pack-{name}; "
                "the installed pack and generated state are unchanged"
            )
            return rep

        archived = list(keep)
        archive_rel = None
        if archived:
            stamp = datetime.date.today().isoformat()
            archive_rel = f"90 Archive/packs/{name}-{stamp}"

        gate_started = False

        def removal_gate():
            nonlocal gate_started
            gate_started = True
            generated = _sub(root, gen_mod, rep, "generate")
            if generated.errors:
                raise SafePathError("generate failed while pack removal was reversible")
            validated = _sub(root, val_mod, rep, "validate")
            if validated.errors:
                raise SafePathError("validate failed while pack removal was reversible")

        try:
            atomic_archive_and_remove_tree(
                root,
                f"Packs/{name}",
                archive_rel,
                {rel: pack_payloads[rel] for rel in archived},
                removal_gate,
                boundary=_pack_remove_boundary,
                expected_source_digest=pack_digest,
            )
        except (OSError, SafePathError) as exc:
            rep.error(f"pack removal transaction failed: {exc}")
            if gate_started:
                # The pack/archive transaction restored its own live state, but
                # generate may already have published derived indexes for the
                # temporarily quarantined pack. Rebuild those derived bytes from
                # the restored source. Any failure is reported as incomplete
                # recovery rather than hidden behind the original refusal.
                recovered_generate = _sub(root, gen_mod, rep, "recovery-generate")
                recovered_validate = _sub(root, val_mod, rep, "recovery-validate")
                if recovered_generate.errors or recovered_validate.errors:
                    rep.error(
                        "ROLLBACK IS INCOMPLETE: pack/archive state was restored, "
                        "but generated-state recovery did not pass"
                    )
            return rep

        if archived:
            rep.info["workspace_archived"] = (
                f"{len(archived)} file(s) copied exactly to {archive_rel}/ "
                f"— your work was NOT deleted")
            rep.info["archived_files"] = archived[:20]

        packs = os.path.join(root, "Packs")
        if os.path.isdir(packs) and not os.listdir(packs):
            try:
                os.rmdir(packs)
            except OSError:
                pass
        rep.info["removed"] = f"Packs/{name}/"
        # The guarantee that MATTERS is preserved either way: no vendor
        # residue, the vault returns to a clean state. What changes is that
        # it can no longer take the user's own work with it.
        rep.info["leave_no_trace"] = (
            "validate green; pack components no longer indexed"
            + ("" if not archived else
               f"; {len(archived)} user file(s) evacuated to 90 Archive/, not deleted"))
        return rep

    # verify / apply need a pack ZIP
    if target:
        zips = [target] if os.path.isabs(target) else [os.path.join(root, target)]
        if not os.path.exists(zips[0]):
            rep.error(f"no such file: {target}"); return rep
    else:
        zips = _find_zips(root)
        if not zips:
            rep.error("no pack ZIP (containing a top-level pack.yaml) in the OS root — "
                      "drop the pack ZIP there first (manage-packs step 1)")
            return rep
        if len(zips) > 1 and apply_:
            rep.error("multiple pack ZIPs in the root — name the one to apply: aios pack <zip> --apply --confirm")
            return rep

    if not apply_:
        for zp in zips:
            # Verify is read-only: an unforeseen shape in a stranger's manifest
            # must still leave a report, not a traceback. The named classes above
            # each carry their own message; this is the floor under them.
            try:
                _verify(root, zp, rep)
            except Exception as e:                      # noqa: BLE001 — trust boundary
                rep.error(f"{os.path.basename(zp)}: unreadable pack manifest "
                          f"({type(e).__name__}: {e}) — nothing was changed")
                rep.info["verdict"] = "REJECTED — change nothing (manage-packs step 2)"
        return rep

    if not getattr(args, "confirm", False):
        rep.error("--apply changes the vault — pass --confirm after the owner has seen the plan and said yes "
                  "(manage-packs step 4; the plan comes from --verify)")
        return rep
    try:
        plan = _verify(root, zips[0], rep)
    except Exception as e:                              # noqa: BLE001 — trust boundary
        rep.error(f"{os.path.basename(zips[0])}: unreadable pack manifest "
                  f"({type(e).__name__}: {e}) — nothing was changed")
        rep.info["verdict"] = "REJECTED — change nothing (manage-packs step 2)"
        return rep
    if plan is None:
        return rep
    approved_review = str(getattr(args, "review_sha256", None) or "")
    if approved_review != plan["review_sha256"]:
        rep.error("--apply requires --review-sha256 with the exact hash printed by "
                  "a fresh `aios pack <zip> --verify`; --confirm alone does not "
                  "authorize instruction-bearing archive bytes")
        rep.info["verdict"] = "REJECTED — change nothing (review authority missing or stale)"
        return rep
    if plan.get("version_direction") in ("same", "DOWNGRADE"):
        rep.warn(f"incoming {plan['version']} is not newer than installed "
                 f"{plan.get('installed_version')} — proceeding on the owner's explicit --confirm")

    # Trust boundary: the exact archive named in the approval review is fully
    # extracted and pack-checked in a temporary directory before checkpoint,
    # placement, receipt, generated state, or any other vault write.
    if not _stage_pack_check(root, plan, rep):
        return rep

    ck = _sub(root, ck_mod, rep, "checkpoint",
              message=f"pre-{plan['action'].lower()} {plan['id']} v{plan['version']}")
    ref = str(ck.info.get("checkpoint", ""))
    # Placement is the one irreversible step. On UPDATE it deletes the installed
    # pack FIRST, so a failure part-way through — a corrupt member, a permission
    # error, an entry that escapes — used to escape as a traceback and leave the
    # vault holding a half-written pack with the old one already gone and no
    # recovery run. Any failure here now falls into the same DEC-077 recovery as
    # a red validate.
    placed_ok, place_err = True, None
    try:
        _place(plan)
    except Exception as e:                              # noqa: BLE001 — trust boundary
        placed_ok, place_err = False, f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(plan.pop("stage_dir", ""), ignore_errors=True)
    installed_sha = None
    if placed_ok:
        if plan.get("layout"):
            # The baseline is part of the installed tree identity. Write it
            # before hashing/receipting, never after activation.
            plan["baseline_count"] = _write_scaffold_baseline(
                plan["dest"], plan["layout"], plan["version"])
        try:
            installed_sha = pack_tree_sha256(plan["dest"])
        except (OSError, ValueError) as exc:
            placed_ok = False
            place_err = f"installed tree hashing failed: {type(exc).__name__}: {exc}"

    if placed_ok:
        # Staged strict pack-check has already judged the exact archive. Validate
        # the surrounding live vault now, while the new pack has no receipt and
        # therefore cannot enter generated boot state. Only a green gate earns
        # durable activation authority.
        v = _sub(root, val_mod, rep, "validate-preactivation")
        if not v.errors:
            _pack_install_boundary("after-preactivation-validate", plan)
            try:
                append_receipt(
                    root, action="activate", pack_id=plan["id"],
                    version=plan["version"], installed_tree_sha256=installed_sha,
                    review_sha256=plan["review_sha256"],
                    archive_sha256=plan["review"]["archive_sha256"])
                rep.info["activation_receipt"] = (
                    f"hash-bound to review {plan['review_sha256']} and installed tree "
                    f"{installed_sha}; written only after strict staged pack-check "
                    f"and live pre-activation validate passed")
            except (OSError, ValueError) as exc:
                placed_ok = False
                place_err = f"activation receipt failed: {type(exc).__name__}: {exc}"
        if not v.errors and placed_ok:
            _pack_install_boundary("after-activation-receipt", plan)
            g = _sub(root, gen_mod, rep, "generate")
            if g.errors:
                rep.error(
                    f"{plan['action']} ACCEPTED but component-index refresh failed "
                    f"({len(g.errors)} generate errors). The reviewed pack and its "
                    f"durable receipt remain installed; source ZIP is preserved. "
                    f"Run `aios generate` after correcting the generation failure. "
                    f"No rollback was attempted because that could leave receipt "
                    f"authority inconsistent with installed bytes.")
                rep.info["result"] = (
                    f"ACCEPTED-BUT-INDEX-REFRESH-FAILED — {plan['id']} "
                    f"v{plan['version']} remains installed and receipted")
                return rep
            source_disposition = "preserved (caller-owned input outside vault)"
            source_zip = plan.get("source_zip", plan["zip"])
            if _source_is_vault_owned(root, source_zip):
                os.remove(source_zip)
                source_disposition = "removed (vault-owned input)"
            if plan.get("layout"):
                # §4.3 — record what the vendor's scaffold looks like RIGHT NOW,
                # so the next update can tell an untouched file from an edited
                # one instead of overwriting both. The DEC-074 mechanism, scoped
                # to a pack.
                n = plan.get("baseline_count", 0)
                rep.info["scaffold_baseline"] = (
                    f"{n} scaffold file(s) fingerprinted in "
                    f"Packs/{plan['name']}/{SCAFFOLD_BASELINE}")
                pl = plan.get("placement") or {}
                for k in ("replaced", "added", "kept_user_edit", "incoming",
                          "workspace_untouched", "seed_skipped", "removed"):
                    if pl.get(k):
                        rep.info[f"placement_{k}"] = pl[k] if len(pl[k]) <= 20 else \
                            pl[k][:20] + [f"...and {len(pl[k]) - 20} more"]
                if pl.get("kept_user_edit"):
                    rep.warn(f"{len(pl['kept_user_edit'])} scaffold file(s) you had edited were "
                             f"KEPT and the incoming versions written beside them as "
                             f"`.incoming` — review and merge by hand (never auto-merged)")
            rep.info["result"] = (f"{plan['action']} OK — {plan['id']} v{plan['version']} at "
                                  f"Packs/{plan['name']}/; source ZIP {source_disposition}; "
                                  f"validate green")
            return rep

    # DEC-077 recovery: the pack we placed is untracked — remove it OURSELVES,
    # then roll back (restores the previous pack on UPDATE), then trust only validate.
    if placed_ok:
        rep.error(f"pre-activation validate failed after placement ({len(v.errors)} errors) "
                  f"— recovering per DEC-077 before any activation receipt")
    else:
        rep.error(f"pack install transaction failed ({place_err}) — "
                  f"recovering per DEC-077")
    shutil.rmtree(plan["dest"], ignore_errors=True)
    packs = os.path.join(root, "Packs")
    if os.path.isdir(packs) and not os.listdir(packs):
        os.rmdir(packs)
    if ref.startswith("git "):
        _sub(root, ck_mod, rep, "rollback", rollback=ref[4:], confirm=True)
    else:
        rep.warn("no git checkpoint ref — pack folder removed; restore the zip snapshot "
                 "by hand if anything else changed (Recovery Guide Part 3)")
    _sub(root, gen_mod, rep, "generate-postrecovery")
    v2 = _sub(root, val_mod, rep, "validate-postrecovery")
    if v2.errors:
        rep.error("recovery NOT clean — validate still red; stop and follow the Recovery Guide")
    else:
        rep.info["result"] = ("recovered — pack removed, prior state restored, validate green "
                              "(judged on validate, never on rollback's headline)")
    return rep
