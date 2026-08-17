"""vault.docgen — generate hand-maintained enumerations in prose, from source.

The third layer of the freshness story. `doc-audit` (DEC-064) makes a wrong
*count* fail the build; the DEC-069 stamp checks make stale *prose* fail it.
Both catch drift after a human writes it. This closes the loop: a prose
enumeration that can be derived from source is no longer typed by hand at all —
it is generated into a marked block, and a stale block fails the build.

A doc opts in by wrapping a region:

    <!-- docgen:commands -->
    ...generated content, do not edit by hand...
    <!-- /docgen:commands -->

`aios docgen` fills every such block; `aios docgen --check` (run inside `health`)
verifies them without writing. Each block key names a builder below; each builder
reads the same source-of-truth the rest of the toolchain reads (the CLI via
argparse AST, the registries, the manifest), so a generated block cannot drift by
construction — the guarantee `doc-commands` has always had, extended from command
*names* to the *prose lists* that mention them.

Read-only under `--check`. A bare run writes only inside the marked regions;
surrounding prose is never touched.
"""
from __future__ import annotations
import ast
import glob
import os
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

from lib.safepaths import (SafePathError, atomic_create_files,
                           preflight_contained_regular_files)
from lib.protectedwrites import ProtectedTargetError, protection_proof
from lib.reviewedplan import build_reviewed_plan

_OPEN = re.compile(r"<!-- docgen:([a-z0-9\-]+) -->")


def _read_text(path, *, errors=None):
    kwargs = {"encoding": "utf-8"}
    if errors is not None:
        kwargs["errors"] = errors
    with open(path, **kwargs) as stream:
        return stream.read()


def _read_yaml(path):
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _cli_commands(root):
    """The `aios` subcommand names, read from argparse `choices` (AST — never a copy)."""
    src = _read_text(os.path.join(root, "System", "Scripts", "aios.py"))
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Call):
            for kw in n.keywords:
                if kw.arg == "choices" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    vals = [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
                    if vals:
                        return vals
    return []


def block_commands(root):
    cmds = _cli_commands(root)
    return f"the {len(cmds)} `aios` subcommands: " + " · ".join(f"`{c}`" for c in cmds)


def block_capabilities(root):
    """Capabilities are `<name>/SKILL.md` folders (DEC-070). This builder still
    globbed the retired flat `Capabilities/*.md` form and therefore returned
    "the 0 capabilities" — a builder nothing used, so nothing noticed. Wiring the
    README to it before this fix would have replaced one wrong number with a
    worse one."""
    caps = sorted(os.path.basename(os.path.dirname(p))
                  for p in glob.glob(os.path.join(root, "System", "Capabilities",
                                                  "*", "SKILL.md")))
    return f"the {len(caps)} capabilities: " + " · ".join(f"`{c}`" for c in caps)


def block_capability_count(root):
    """Just the number, for prose that names the count inside a sentence
    ("8 record types · 14 AI playbooks · 3 specialist AI roles")."""
    return str(len(glob.glob(os.path.join(root, "System", "Capabilities", "*", "SKILL.md"))))


def block_agent_count(root):
    return str(len(glob.glob(os.path.join(root, "System", "Agents", "*", "AGENT.md"))))


def block_note_class_count(root):
    """User note classes exclude system component and migration contracts."""
    n = 0
    for p in glob.glob(os.path.join(root, "System", "Schemas", "*.yaml")):
        d = _read_yaml(p)
        if d and d.get("schema") and d["schema"] not in {
            "component", "migration-manifest"
        }:
            n += 1
    return str(n)


def block_principles_count(root):
    dp = _read_text(os.path.join(root, "System", "Architecture", "Design Principles.md"))
    return str(len(re.findall(r"^[0-9]+\. \*\*", dp, re.M)))


def block_vocabularies(root):
    vraw = _read_yaml(os.path.join(root, "System", "Schemas", "vocabularies.yaml"))
    vocab = vraw.get("vocabularies", vraw)
    rows = [(k, len(v)) for k, v in vocab.items() if isinstance(v, list)]
    total = sum(n for _, n in rows)
    return (f"the {len(rows)} vocabularies ({total} values total): "
            + " · ".join(f"`{k}` ({n})" for k, n in rows))


def _authority_group(rel):
    p = rel.replace("\\", "/")
    if "/" not in p:
        return "Root"
    for prefix, name in (
            ("System/Architecture", "Architecture"), ("System/Governance", "Governance"),
            ("System/Runtime", "Runtime"), ("System/Capabilities", "Capabilities"),
            ("System/Agents", "Agents"), ("System/Workflows", "Workflows"),
            ("System/Documentation", "Documentation"), ("System/Method-Kit", "Method Kit"),
            ("System/Onboarding", "Onboarding"), ("System/Tests/fixtures", "Fixtures"),
            ("System/Tests", "Tests"), ("System/Adapters", "Adapters"),
            ("System/Journal", "Journal"), ("System/Templates", "Templates"),
            ("System/Migrations", "Migrations"), ("System/Schemas", "Schemas"),
            ("System/Registries", "Registries"), ("System/Operations", "Operations"),
            ("Packs/", "Packs"), ("Decisions/", "Decisions")):
        if p.startswith(prefix):
            return name
    return "Content folders (`_ABOUT.md`)"


def block_authority_index(root):
    """The §8.2 index. It read '102 authority-marked files / 75 canonical · 27
    derived' against a live 129 / 101 / 28, and every row of the breakdown was a
    transcription. Generated, it cannot say that again."""
    groups, canon, derived = {}, 0, 0
    for path in sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True)):
        if os.sep + ".git" + os.sep in path:
            continue
        text = _read_text(path, errors="replace")
        m = re.search(r"^authority:\s*(\S+)", text, re.M)
        if not m:
            continue
        g = _authority_group(os.path.relpath(path, root))
        row = groups.setdefault(g, [0, 0])
        if m.group(1) == "canonical":
            row[0] += 1
            canon += 1
        elif m.group(1) == "derived":
            row[1] += 1
            derived += 1
    lines = [f"**{canon + derived} authority-marked files — {canon} canonical · {derived} derived.**",
             "", "| Group | Canonical | Derived |", "|---|---|---|"]
    for g in sorted(groups, key=lambda k: (-groups[k][0] - groups[k][1], k)):
        lines.append(f"| {g} | {groups[g][0]} | {groups[g][1]} |")
    lines.append(f"| **Total** | **{canon}** | **{derived}** |")
    return "\n".join(lines)


def block_derivation_tree(root):
    """§8.3. Every `derived_from` edge in the tree, with the stamp each derived
    doc actually carries for that source. Hand-drawn, it was twelve versions
    stale, called two stamped documents unstamped, and pinned a v1.3.0 that had
    reached 1.9.0 — while being the section whose whole subject is stamps."""
    sys.path.insert(0, os.path.join(root, "System", "Scripts"))
    from lib.frontmatter import iter_markdown
    meta, edges = {}, {}
    for n in iter_markdown(root):
        if n.error or not n.meta.get("id"):
            continue
        meta[str(n.meta["id"])] = n
        for src in (n.meta.get("derived_from") or []):
            edges.setdefault(str(src), []).append(n)
    out = []
    for src in sorted(edges):
        s = meta.get(src)
        ver = f" (v{s.meta['version']})" if s is not None and s.meta.get("version") else ""
        out.append(f"{src}{ver}")
        rows = sorted(edges[src], key=lambda x: x.relpath)
        for i, n in enumerate(rows):
            ra = n.meta.get("x_reviewed_against") or []
            stamp = next((e.rsplit(":", 1)[1] for e in ra
                          if isinstance(e, str) and e.startswith(src + ":")), None)
            mark = f"[{stamp} ✓]" if stamp else "[unstamped]"
            branch = "└──" if i == len(rows) - 1 else "├──"
            base = os.path.basename(n.relpath)[:-3]
            if base == "_ABOUT":     # eight of them; the folder is the identity
                base = os.path.dirname(n.relpath).replace("\\", "/") + "/_ABOUT"
            out.append(f"{branch} {base:<44} {mark}")
        out.append("")
    return "```\n" + "\n".join(out).rstrip() + "\n```"


def block_test_census(root):
    """Suites and tests, counted as `unittest discover` would instantiate them:
    every `def test_*` in `System/Tests/scripts/*.py`. The heading this replaces
    said eighty-four against a suite that had passed four hundred."""
    suites = {}
    for path in sorted(glob.glob(os.path.join(root, "System", "Tests", "scripts", "*.py"))):
        n = len([x for x in ast.walk(ast.parse(_read_text(path)))
                 if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and x.name.startswith("test_")])
        if n:
            suites[os.path.basename(path)] = n
    total = sum(suites.values())
    lines = [f"**{total} unit tests across {len(suites)} suites** "
             f"(`python3 -m unittest discover -s System/Tests/scripts`).",
             "", "| Suite | Tests |", "|---|---|"]
    for name in sorted(suites, key=lambda k: (-suites[k], k)):
        lines.append(f"| `{name}` | {suites[name]} |")
    return "\n".join(lines)


def _message_sites(path):
    n = 0
    for node in ast.walk(ast.parse(_read_text(path))):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ("error", "warn"):
            n += 1
        elif isinstance(f, ast.Call) and isinstance(f.func, ast.Name) and f.func.id == "_sev":
            n += 1
    return n


def block_message_census(root):
    """Appendix D. Two obvious extractors are both wrong: a text grep for
    `rep.error(`/`rep.warn(` misses the three modules that raise through a
    `_sev(rep)` severity switch (DEC-083), and a receiver-name match additionally
    misses the two `certify` raises through sub-reports named `hsub`/`vsub`. This
    walks the AST and counts every `.error(…)`/`.warn(…)` on any receiver plus
    every `_sev(rep)(…)` — every message a user can be shown."""
    mods = {}
    for path in sorted(glob.glob(os.path.join(root, "System", "Scripts", "**", "*.py"),
                                 recursive=True)):
        n = _message_sites(path)
        if n:
            mods[os.path.splitext(os.path.basename(path))[0]] = n
    total = sum(mods.values())
    lines = [f"**{total} call sites across {len(mods)} modules.** *Extractor: every "
             f"`.error(…)` / `.warn(…)` call on any receiver, plus every `_sev(rep)(…)` "
             f"severity switch, by AST walk over `System/Scripts/**/*.py`. A plain text "
             f"grep for `rep.error(`/`rep.warn(` undercounts twice over — it misses "
             f"`docaudit`, `doccheck` and `docpaths`, which raise through `_sev`, and the "
             f"two `certify` raises through sub-reports named `hsub`/`vsub`.*",
             "", "| Module | Messages |", "|---|---|"]
    for name in sorted(mods, key=lambda k: (-mods[k], k)):
        lines.append(f"| `{name}` | {mods[name]} |")
    return "\n".join(lines)


def block_library_census(root):
    """§6.8. It said "the four libraries" over four rows while six modules
    shipped, and every line count in it was wrong."""
    lines = ["| Module | Lines |", "|---|---|"]
    n = 0
    for path in sorted(glob.glob(os.path.join(root, "System", "Scripts", "lib", "*.py"))):
        base = os.path.basename(path)
        if base.startswith("__"):
            continue
        n += 1
        lines.append(f"| `{base}` | {len(_read_text(path).splitlines())} |")
    return f"**{n} library modules** (`System/Scripts/lib/`).\n\n" + "\n".join(lines)


def block_file_census(root):
    """Appendix E's file census. Counts what is on disk, excluding the things
    that are not the product (`.git`, generated state, caches, editor and runtime
    projections). A generated census cannot become a stale snapshot."""
    skip = {".git", ".venv", "__pycache__", ".obsidian", ".claude", "node_modules"}
    try:
        manifest = yaml.safe_load(_read_text(os.path.join(root, "SYSTEM-MANIFEST.yaml"))) or {}
        content_roots = {
            str(value).rstrip("/")
            for value in ((manifest.get("directories") or {}).get("content") or [])
            if isinstance(value, str) and value
        }
    except (OSError, yaml.YAMLError, AttributeError, TypeError):
        content_roots = set()
    by_ext, total = {}, 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_parent = os.path.relpath(dirpath, root).replace("\\", "/")
        dirnames[:] = [
            d for d in dirnames
            if d not in skip and
            ((d if rel_parent == "." else rel_parent + "/" + d) not in content_roots)
        ]
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel.startswith("System/Generated") or rel.startswith("System/Logs"):
            continue
        for fn in filenames:
            if fn.startswith("."):
                continue
            total += 1
            by_ext[os.path.splitext(fn)[1] or "(none)"] = \
                by_ext.get(os.path.splitext(fn)[1] or "(none)", 0) + 1
    lines = [f"**{total} files on disk** (excluding `.git`, generated state, caches, and the "
             f"editor/runtime projections).", "", "| Extension | Files |", "|---|---|"]
    for ext in sorted(by_ext, key=lambda k: (-by_ext[k], k)):
        if by_ext[ext] >= 3:
            lines.append(f"| `{ext}` | {by_ext[ext]} |")
    return "\n".join(lines)


def block_counted_surface(root):
    """Appendix E's "counted surface" table — every headline census in one
    place, all of them extracted. This is the table the audit called the most
    impressive-looking and least true part of the product; it was a v1.14/v1.17
    snapshot that had been selectively updated, which is the worst of both (not
    current, and no longer defensible as history)."""
    from . import docaudit
    T = docaudit.truth(root)
    order = ["commands", "flags", "operations", "capabilities", "agents", "workflows",
             "components", "note classes", "fields", "schemas", "templates",
             "note-class templates", "vocabularies", "vocabulary values", "folders",
             "protected objects", "routes", "principles", "diagrams", "documentation files",
             "authority files", "fixtures", "unit tests", "messages", "script modules",
             "libraries"]
    lines = ["| Surface | Count |", "|---|---|"]
    for k in order:
        if k in T:
            lines.append(f"| {k[0].upper() + k[1:]} | {T[k]} |")
    return "\n".join(lines)


BLOCKS = {
    "commands":          block_commands,
    "authority-index":   block_authority_index,
    "derivation-tree":   block_derivation_tree,
    "test-census":       block_test_census,
    "message-census":    block_message_census,
    "library-census":    block_library_census,
    "file-census":       block_file_census,
    "counted-surface":   block_counted_surface,
    "capabilities":      block_capabilities,
    "capability-count":  block_capability_count,
    "agent-count":       block_agent_count,
    "note-class-count":  block_note_class_count,
    "principles":        block_principles_count,
    "vocabularies":      block_vocabularies,
}


def _docs(root):
    return sorted(set(glob.glob(os.path.join(root, "System", "**", "*.md"), recursive=True)
                      + glob.glob(os.path.join(root, "*.md"))))


def _process(root, text, rel, rep, write):
    """Return (new_text, changed_count); verify or fill each marked block."""
    out, i, changed = [], 0, 0
    while True:
        m = _OPEN.search(text, i)
        if not m:
            out.append(text[i:])
            break
        key = m.group(1)
        close = f"<!-- /docgen:{key} -->"
        c = text.find(close, m.end())
        if c == -1:
            rep.error(f"{rel}: docgen block '{key}' is opened but never closed ({close})")
            out.append(text[i:])
            break
        builder = BLOCKS.get(key)
        if builder is None:
            rep.error(f"{rel}: unknown docgen key '{key}' — known: {', '.join(sorted(BLOCKS))}")
            out.append(text[i:c + len(close)])
            i = c + len(close)
            continue
        # Inline when the author wrote the markers on one line. Counts that live
        # mid-sentence — "8 record types · 14 AI playbooks · 3 specialist AI
        # roles" — cannot be block-generated without breaking the sentence, and
        # that sentence is the second line of the README, which is where the
        # capability count has now been wrong three times.
        inline = "\n" not in text[m.start():c]
        body = builder(root).strip()
        want = body if inline else "\n" + body + "\n"
        have = text[m.end():c]
        out.append(text[i:m.end()])
        if have != want:
            changed += 1
            if not write:
                rep.error(f"{rel}: docgen block '{key}' is stale — run `aios docgen` "
                          f"to regenerate it from source")
        out.append(want if write else have)
        out.append(text[c:c + len(close)])
        i = c + len(close)
    return "".join(out), changed


def regenerate_within(root, rep, keep):
    """Fill docgen blocks, but only in files `keep(rel_posix_path)` accepts.

    For `aios upgrade` (DEC-111). A release's generated blocks are counted
    against the RELEASE's tree, so the moment upgrade replaces a doc carrying
    one, that block is stale on the instance — and `docgen --check` inside
    `health` then reddens the run and blocks the version bump. The instance is
    required to regenerate; the tool has to let it, in the same breath as the
    replacement that invalidated it.

    Scoped rather than wholesale, because a USER-owned file may legitimately
    carry a block too (a live instance was found with them in its own root
    `CHANGELOG.md`). Regenerating that would rewrite user content and trip the
    integrity check — correctly. Upgrade refreshes only what upgrade owns; a
    user's own stale block stays theirs to run `aios docgen` over."""
    return _transactional_regenerate(root, rep, keep)


def _candidate_docs(root, keep):
    candidates = {}
    for path in _docs(root):
        if os.sep + "fixtures" + os.sep in path:
            continue
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if not keep(rel):
            continue
        batch = preflight_contained_regular_files(
            root, [path], require_writable=False
        )
        try:
            text = batch.read_texts()[path]
        finally:
            batch.close()
        if "<!-- docgen:" in text:
            candidates[path] = text
    return candidates


def _prepared_regeneration(root, rep, keep):
    """Compute the entire docgen write set before one all-or-nothing commit."""
    try:
        texts = _candidate_docs(root, keep)
    except SafePathError as exc:
        rep.error(f"docgen write set refused before mutation: {exc}")
        return None
    if not texts:
        return None

    error_count = len(rep.errors)
    changed_paths = []
    touched = 0
    for path in texts:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        _new, changed = _process(root, texts[path], rel, rep, write=True)
        if changed:
            changed_paths.append(path)
            touched += changed
    if len(rep.errors) != error_count or not changed_paths:
        return None

    batch = None
    try:
        batch = preflight_contained_regular_files(root, changed_paths)
        current = batch.read_texts()
        replacements = {}
        originals = {}
        files = []
        confirmed_touched = 0
        second_error_count = len(rep.errors)
        for target in batch.targets:
            original = current[target.path]
            new, changed = _process(
                root, original, target.relpath, rep, write=True
            )
            if not changed:
                raise SafePathError(
                    f"docgen target changed while preparing the transaction: "
                    f"{target.relpath}; retry"
                )
            originals[target.relpath] = original.encode("utf-8")
            replacements[target.relpath] = new.encode("utf-8")
            files.append(target.relpath)
            confirmed_touched += changed
        if len(rep.errors) != second_error_count:
            batch.close()
            return None
        return batch, originals, replacements, confirmed_touched, files
    except SafePathError as exc:
        if batch is not None:
            batch.close()
        rep.error(f"docgen transaction refused: {exc}")
        return None


def _transactional_regenerate(root, rep, keep):
    prepared = _prepared_regeneration(root, rep, keep)
    if prepared is None:
        return 0, []
    batch, _originals, replacements, touched, files = prepared
    try:
        batch.atomic_replace_many(replacements)
        return touched, files
    except SafePathError as exc:
        rep.error(f"docgen transaction refused: {exc}")
        return 0, []
    finally:
        batch.close()


def _reviewed_docgen_batch(root, rep, args, *, check):
    """Prepare, report, authorize, and optionally commit the exact docgen batch."""
    prepared = _prepared_regeneration(root, rep, lambda _rel: True)
    if prepared is None:
        if not rep.errors:
            try:
                policy = protection_proof(root)
                plan = build_reviewed_plan("docgen", root, policy, {}, {})
                rep.info["protected_targets"] = []
                rep.info["review_sha256"] = plan.review_sha256
                rep.info["review_plan"] = plan.document
            except (ProtectedTargetError, ValueError, SafePathError) as exc:
                rep.error(f"docgen protected-write review refused: {exc}")
        return 0
    batch, originals, replacements, touched, _files = prepared
    try:
        try:
            policy = protection_proof(root)
            plan = build_reviewed_plan(
                "docgen", root, policy, originals, replacements
            )
        except (ProtectedTargetError, ValueError, SafePathError) as exc:
            rep.error(f"docgen protected-write review refused: {exc}")
            return 0

        rep.info["protected_targets"] = list(plan.protected_targets)
        rep.info["review_sha256"] = plan.review_sha256
        rep.info["review_plan"] = plan.document
        if check:
            # Preserve the established --check contract: every stale block is
            # still an error, while the same read-only pass prints the exact
            # authorization object a protected write would require.
            for target in batch.targets:
                _process(
                    root,
                    originals[target.relpath].decode("utf-8"),
                    target.relpath,
                    rep,
                    write=False,
                )
            return touched

        if plan.protected_targets:
            supplied = str(getattr(args, "review_sha256", None) or "")
            if not (bool(getattr(args, "apply", False))
                    and bool(getattr(args, "confirm", False))
                    and supplied == plan.review_sha256):
                rep.error(
                    "docgen protected batch requires --apply --confirm "
                    f"--review-sha256 {plan.review_sha256} from a fresh "
                    "`aios docgen --check`; missing, wrong, stale, or expanded "
                    "plans write nothing"
                )
                return 0
            policy.reprove()
        if plan.protected_targets:
            atomic_create_files(
                root,
                replacements,
                replace_batch=batch,
                read_only_inputs=(policy.manifest,),
            )
        else:
            batch.atomic_replace_many(replacements)
        return touched
    except SafePathError as exc:
        rep.error(f"docgen transaction refused: {exc}")
        return 0
    finally:
        batch.close()


def run(root, args, rep):
    if yaml is None:
        rep.error("PyYAML required for docgen")
        return rep
    check = bool(getattr(args, "check", False))
    if not check:
        touched = _reviewed_docgen_batch(root, rep, args, check=False)
        rep.info["blocks_regenerated"] = touched
        return rep
    touched = _reviewed_docgen_batch(root, rep, args, check=True)
    rep.info["blocks_stale"] = touched
    return rep
