"""Frontmatter parsing and vault file iteration. PyYAML is the only dependency."""
from __future__ import annotations
import os, re
import yaml

SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

SKIP_DIRS = {".obsidian", ".git", ".claude", "__pycache__", "Packs"}   # runtime/app state + self-contained add-ons (DEC-061): pack internals are the pack's, discovered via generate/doc-check globs, never canon-validated as the vault's
GENERATED_DIRS = {os.path.join("System", "Generated"), os.path.join("System", "Logs")}

# A directory holding this file is an OKF bundle: a foreign-format artifact in
# the vault's own folders, and NOT vault canon. It is pruned for the same reason
# `Packs/` is (DEC-067) — a well-formed artifact must not fail the vault's checks
# just for existing. Measured, not assumed: an exported bundle carries a copy of
# each note's frontmatter, so without this every export duplicates the `id` of
# every note it emitted ("duplicate id 'note-x': 20 Knowledge/x.md and
# 40 Outputs/okf-knowledge/x.md") and its OKF keys (`title`, `resource`,
# `timestamp`) trip the unknown-key check against the note's own schema.
# The bundle is still the user's file, readable and diffable; it is simply not
# judged as though the vault had authored it.
BUNDLE_MARKER = "okf.yaml"

# ---------------------------------------------------------------------------
# TEMPLATE SPACE and the PLACEHOLDER GRAMMAR (DEC-115).
#
# A template's `id: note-<slug>` is not a malformed id and two templates sharing
# it are not duplicate records — they are two blanks waiting for a value. The
# product has always known this: `validate` has exempted template placeholders
# since the id rules were written. It was known in exactly one place, so
# `pack-check` (v1.58.0) re-derived the id rules without it and reported the
# product's own convention as an error — 19 duplicate-id errors on a live
# instance whose pack ships 22 templates, while `dupes` was green on the very
# same convention in `System/Templates/` (which carries `procedure-<slug>`
# twice). Both readers now call the same two functions, so the rule cannot drift
# apart again.
#
# The grammar is `<...>`: the angle bracket is not legal in an id (ID_RE), so a
# value carrying one is unambiguously an unfilled slot rather than a real id.
# Outside template space that is still an ERROR — an unfilled placeholder in a
# real record is a note nobody finished.


def is_placeholder(value) -> bool:
    """An unfilled template slot — `note-<slug>`, `<yyyy-mm-dd>`, or bare `<>`."""
    return "<" in str(value)


def in_template_space(relpath: str) -> bool:
    """Does this file live where blanks are the point? Deliberately the same
    substring test `validate` has always used, factored out unchanged rather
    than tightened, so nothing that was exempt yesterday becomes an error today.
    Covers `System/Templates/`, a pack's `05 PMM Wiki/Templates/`, and any
    template folder a user invents — the folder name is the declaration."""
    return "Templates" in str(relpath).replace("\\", "/")

class Note:
    __slots__ = ("path", "relpath", "meta", "body", "error")
    def __init__(self, path, relpath, meta, body, error=None):
        self.path, self.relpath, self.meta, self.body, self.error = path, relpath, meta, body, error

def parse_file(path: str, root: str) -> Note:
    rel = os.path.relpath(path, root)
    try:
        with open(path, encoding="utf-8") as stream:
            text = stream.read()
    except (UnicodeDecodeError, OSError) as e:
        return Note(path, rel, {}, "", f"unreadable: {e}")
    return parse_text(path, rel, text)


def parse_text(path: str, rel: str, text: str) -> Note:
    """Parse already-read Markdown bytes without a second filesystem read."""
    meta, body = {}, text
    if text.startswith("---\n") or text.startswith("---\r\n"):
        m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.DOTALL)
        if m:
            try:
                meta = yaml.load(m.group(1), Loader=SAFE_LOADER) or {}
                if not isinstance(meta, dict):
                    return Note(path, rel, {}, text, "frontmatter is not a mapping")
            except yaml.YAMLError as e:
                return Note(path, rel, {}, text, f"frontmatter YAML error: {e}")
            body = text[m.end():]
        else:
            return Note(path, rel, {}, text, "unterminated frontmatter fence")
    return Note(path, rel, meta, body)

def iter_markdown(root: str, include_generated: bool = False, skip_dirs=None,
                  text_filter=None):
    """Walk `root` yielding parsed Notes.

    `skip_dirs` defaults to SKIP_DIRS and EVERY existing caller keeps exactly
    today's behaviour — `Packs` stays pruned from the default, which is what
    keeps DEC-067 intact (a pack's own README.md/CHANGELOG.md and its note ids
    never enter vault canon). `aios pack-check` passes a narrowed set to read a
    pack IN ITS OWN NAMESPACE, in a separate pass. Coverage is not canon."""
    skip = SKIP_DIRS if skip_dirs is None else skip_dirs
    root_real = os.path.realpath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in skip and not os.path.islink(os.path.join(dirpath, d))]
        if BUNDLE_MARKER in filenames:      # an OKF bundle root — prune it and everything under it
            dirnames[:] = []
            continue
        rel = os.path.relpath(dirpath, root)
        if not include_generated and any(rel == g or rel.startswith(g + os.sep) for g in GENERATED_DIRS):
            continue
        for fn in sorted(filenames):
            if fn.endswith(".md"):
                path = os.path.join(dirpath, fn)
                if os.path.islink(path) or not os.path.isfile(path):
                    continue
                try:
                    if os.path.commonpath((root_real, os.path.realpath(path))) != root_real:
                        continue
                except ValueError:
                    continue
                if text_filter is None:
                    yield parse_file(path, root)
                    continue
                relpath = os.path.relpath(path, root)
                try:
                    with open(path, encoding="utf-8") as stream:
                        text = stream.read()
                except (UnicodeDecodeError, OSError) as exc:
                    yield Note(path, relpath, {}, "", f"unreadable: {exc}")
                    continue
                if text_filter(relpath, text):
                    yield parse_text(path, relpath, text)

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MDLINK = re.compile(r"\[[^\]]*\]\(([^)\s#]+)(?:#[^)\s]*)?\)")

CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
CODE_SPAN = re.compile(r"`[^`\n]*`")

def body_links(body: str):
    body = CODE_SPAN.sub("", CODE_FENCE.sub("", body))
    wl = [w.strip() for w in WIKILINK.findall(body)]
    ml = [m for m in MDLINK.findall(body) if not m.startswith(("http://", "https://", "mailto:", "obsidian://"))]
    return wl, ml
