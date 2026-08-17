"""vault.extract — document text extraction on ingest (`.docx` → Markdown).

The defect this closes (roadmap 2026-07-15, proven live): the product could not
read a Word document. `ingest-and-connect`'s final line routed every non-Markdown
file to `Attachments/` plus a pointer note — correct for a photograph, silently
destructive for a document. The file survived; the ideas inside it never entered
the vault. Proven on ~648,000 words of `.docx` that had to be hand-converted in a
throwaway script, differently each session, because the intake path for the
world's most common document format was "the runtime improvises a parser".

**The verification gate is the feature.** The throwaway script's most valuable
output was not the Markdown — it was the character-level diff proving that zero
text-bearing paragraphs had been dropped. A converter you cannot audit is worse
than no converter, because its losses are invisible and land in the layer the
system exists to protect. So this command never emits a partial conversion: it
converts, then proves the conversion, and a FAILED proof files the original to
Attachments with a pointer note and reports the failure. There is no best-effort
mode and no flag to add one.

Scope (v1, SPEC-doc-extraction §1): `.docx` only — it is what actually arrived.
`.pdf` is v2 and `.rtf` later. Preserved: heading levels, list nesting and
numbering, bold/italic runs, hyperlinks, tables, and images (written beside the
original, referenced inline at their true position).

Dependency rule: PyYAML is this product's only third-party dependency. A `.docx`
is a zip of XML, so it is parsed with `zipfile` + `xml.etree` from the standard
library — **no python-docx**. The hand-rolled precedent proved this is enough.

Dark corners are DETECTED AND REPORTED, never silently dropped: footnotes,
endnotes, comments, tracked changes, and text boxes each produce a named warning
with a count, and any text they hold is excluded from the verification set with
that exclusion stated in the report. "We did not extract N footnotes" is a fact
the human can act on; a converter that quietly swallows them is not.
"""
from __future__ import annotations

import io
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from urllib.parse import quote

try:
    import yaml
except ImportError:  # pragma: no cover — PyYAML is a pinned dependency
    yaml = None

from lib.report import Report
from lib.protectedwrites import ProtectedTargetError, refuse_protected_targets
from lib.safepaths import (SafePathError, atomic_create_files,
                           preflight_contained_regular_files, read_regular_file,
                           safe_relative_path)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Word writes headings under a style whose id is Heading1..Heading9 (or, from
# some producers, "heading 1"). Both spellings, one rule.
_HEADING_RE = re.compile(r"^heading\s*([1-9])$", re.IGNORECASE)

# A block this converter emitted as a list item (used only for join spacing).
_LIST_LINE = re.compile(r"^\s*(-|\d+\.)\s")

# Filename sanitization, matching F-6 (safe-write / import): imported titles
# routinely carry characters that are illegal on one of the three platforms.
_ILLEGAL = r'\\/:*?"<>|'

DOCX_MAX_MEMBERS = 2048
DOCX_MAX_COMPRESSED = 128 * 1024 * 1024
DOCX_MAX_UNCOMPRESSED = 256 * 1024 * 1024
DOCX_MAX_MEMBER = 64 * 1024 * 1024
DOCX_MAX_MEDIA = 128 * 1024 * 1024
DOCX_MAX_MEDIA_MEMBER = 32 * 1024 * 1024
DOCX_MAX_COMPRESSION_RATIO = 200


# --------------------------------------------------------------------------
# reading the package
# --------------------------------------------------------------------------

class Docx:
    """The parts of a .docx this converter reads. Nothing is mutated: the file
    is opened read-only and closed before anything is written anywhere."""

    def __init__(self, source, path="document.docx"):
        self.path = path
        stream = io.BytesIO(source) if isinstance(source, bytes) else source
        with zipfile.ZipFile(stream) as z:
            infos = z.infolist()
            if len(infos) > DOCX_MAX_MEMBERS:
                raise ValueError(f"DOCX exceeds {DOCX_MAX_MEMBERS} ZIP members")
            raw_names = [info.filename.rstrip("/") for info in infos]
            if len(raw_names) != len(set(raw_names)):
                raise ValueError("DOCX ZIP contains duplicate member names")
            portable = set()
            total = media_total = 0
            for info in infos:
                name = info.filename.rstrip("/")
                parts = name.split("/")
                if (not name or "\\" in name or name.startswith("/")
                        or any(part in ("", ".", "..") for part in parts)):
                    raise ValueError(f"DOCX ZIP has an unsafe member path: {info.filename}")
                key = unicodedata.normalize("NFC", name).casefold()
                if key in portable:
                    raise ValueError("DOCX ZIP contains a case/Unicode member collision")
                portable.add(key)
                mode = (info.external_attr >> 16) & 0o170000
                if mode not in (0, 0o040000, 0o100000):
                    raise ValueError(f"DOCX ZIP contains a non-regular member: {name}")
                if info.file_size > DOCX_MAX_MEMBER:
                    raise ValueError(f"DOCX ZIP member exceeds {DOCX_MAX_MEMBER} bytes: {name}")
                if (info.file_size and info.compress_size >= 0
                        and info.file_size / max(info.compress_size, 1)
                        > DOCX_MAX_COMPRESSION_RATIO):
                    raise ValueError(f"DOCX ZIP member has an unsafe compression ratio: {name}")
                total += info.file_size
                if name.startswith("word/media/"):
                    if info.file_size > DOCX_MAX_MEDIA_MEMBER:
                        raise ValueError(f"DOCX media member exceeds its safety budget: {name}")
                    media_total += info.file_size
            if total > DOCX_MAX_UNCOMPRESSED:
                raise ValueError("DOCX ZIP exceeds its total uncompressed safety budget")
            if media_total > DOCX_MAX_MEDIA:
                raise ValueError("DOCX media exceeds its total safety budget")
            names = set(z.namelist())
            self.names = names
            self.document = ET.fromstring(z.read("word/document.xml"))
            self.rels = self._rels(z, "word/_rels/document.xml.rels")
            self.numbering = (ET.fromstring(z.read("word/numbering.xml"))
                              if "word/numbering.xml" in names else None)
            self.styles = (ET.fromstring(z.read("word/styles.xml"))
                           if "word/styles.xml" in names else None)
            self.footnotes = (ET.fromstring(z.read("word/footnotes.xml"))
                              if "word/footnotes.xml" in names else None)
            self.endnotes = (ET.fromstring(z.read("word/endnotes.xml"))
                             if "word/endnotes.xml" in names else None)
            self.comments = (ET.fromstring(z.read("word/comments.xml"))
                             if "word/comments.xml" in names else None)
            self.media = {n: z.read(n) for n in names if n.startswith("word/media/")}

    @staticmethod
    def _rels(z, name):
        out = {}
        if name not in z.namelist():
            return out
        for rel in ET.fromstring(z.read(name)):
            out[rel.get("Id")] = (rel.get("Target") or "", rel.get("TargetMode") or "")
        return out

    def style_name(self, style_id):
        """The human style NAME for a style id — producers differ on which one
        carries 'Heading 2', so both are consulted."""
        if self.styles is None or not style_id:
            return ""
        for st in self.styles.findall(f"{W}style"):
            if st.get(f"{W}styleId") == style_id:
                nm = st.find(f"{W}name")
                return (nm.get(f"{W}val") or "") if nm is not None else ""
        return ""

    def num_format(self, num_id, ilvl):
        """`bullet` or an ordered format for a numbering reference. Resolves
        numId → abstractNumId → lvl, which is where list *numbering* lives; a
        converter that renders every list as `-` has silently lost the fact
        that the author numbered it."""
        if self.numbering is None or num_id is None:
            return "bullet"
        abstract = None
        for n in self.numbering.findall(f"{W}num"):
            if n.get(f"{W}numId") == str(num_id):
                a = n.find(f"{W}abstractNumId")
                abstract = a.get(f"{W}val") if a is not None else None
                break
        if abstract is None:
            return "bullet"
        for an in self.numbering.findall(f"{W}abstractNum"):
            if an.get(f"{W}abstractNumId") == str(abstract):
                for lvl in an.findall(f"{W}lvl"):
                    if lvl.get(f"{W}ilvl") == str(ilvl):
                        fmt = lvl.find(f"{W}numFmt")
                        return (fmt.get(f"{W}val") or "bullet") if fmt is not None else "bullet"
        return "bullet"


# --------------------------------------------------------------------------
# the dark corners — detected, counted, reported
# --------------------------------------------------------------------------

def _real_notes(root):
    """Footnote/endnote entries that are actually notes. Every .docx carries two
    synthetic entries (the separator and the continuation separator); counting
    them would report footnotes in a document that has none."""
    if root is None:
        return 0
    n = 0
    for el in list(root):
        if el.get(f"{W}type") in ("separator", "continuationSeparator"):
            continue
        n += 1
    return n


def _textbox_paragraphs(document):
    """Paragraphs living inside a text box.

    Their TEXT is extracted — it appears inline where the box is anchored, so
    nothing is lost — but their true position in the printed layout is a
    floating-frame property Markdown cannot express, so the report says so and
    gives a count. They are listed here to be excluded from the verification
    denominator, where they would otherwise be counted twice: once as the boxed
    paragraph and again as the anchor paragraph that carries their text.
    """
    out = []
    for box in _walk(document):
        if box.tag.endswith("}txbxContent"):
            out.extend(box.findall(f".//{W}p"))
    return out


def survey(doc: Docx):
    """What is in this document that v1 does not extract. Counts only."""
    d = {}
    d["footnotes"] = _real_notes(doc.footnotes)
    d["endnotes"] = _real_notes(doc.endnotes)
    d["comments"] = len(doc.comments.findall(f"{W}comment")) if doc.comments is not None else 0
    d["tracked_insertions"] = len(doc.document.findall(f".//{W}ins"))
    d["tracked_deletions"] = len(doc.document.findall(f".//{W}del"))
    d["text_boxes"] = len(_textbox_paragraphs(doc.document))
    return d


# --------------------------------------------------------------------------
# conversion
# --------------------------------------------------------------------------

MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


def _walk(el):
    """Depth-first walk that reads each alternate-content block ONCE.

    Word writes a text box twice — a modern `mc:Choice` and a legacy
    `mc:Fallback` holding the same words. A walker that visits both extracts
    every one of those words twice, which shows up as duplicated prose in the
    output and an inflated paragraph count in the verification report. Take the
    Choice where there is one; take the Fallback only when it stands alone.
    """
    yield el
    if el.tag == f"{MC}AlternateContent":
        choice = el.find(f"{MC}Choice")
        children = [choice] if choice is not None else list(el)
    else:
        children = list(el)
    for child in children:
        if child is None:
            continue
        yield from _walk(child)


def _run_text(el):
    """The literal text a run contributes, in document order. `w:delText` is
    deliberately absent: it is text the author DELETED under tracked changes,
    and resurrecting it would be an invention, not a preservation."""
    parts = []
    for node in _walk(el):
        tag = node.tag
        if tag == f"{W}t":
            parts.append(node.text or "")
        elif tag == f"{W}tab":
            parts.append("\t")
        elif tag in (f"{W}br", f"{W}cr"):
            parts.append("\n")
        elif tag == f"{W}noBreakHyphen":
            parts.append("-")
    return "".join(parts)


def _emphasize(text, bold, italic):
    """Wrap a run in Markdown emphasis without wrapping its surrounding spaces —
    `**text **` does not render, and a converter that produces it has lost the
    bold it claims to preserve."""
    if not text.strip() or not (bold or italic):
        return text
    lead = text[:len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    core = text.strip()
    mark = "***" if (bold and italic) else ("**" if bold else "*")
    return f"{lead}{mark}{core}{mark}{trail}"


def _is_on(rpr, tag):
    if rpr is None:
        return False
    el = rpr.find(f"{W}{tag}")
    if el is None:
        return False
    return (el.get(f"{W}val") or "true").lower() not in ("0", "false", "off")


def _image_ref(doc: Docx, drawing, media_prefix, media_used):
    """The Markdown image reference for a drawing, or '' if it embeds nothing.
    Position matters: the reference is emitted where the drawing sits in the
    run sequence, so an image between two paragraphs stays between them."""
    for blip in drawing.iter(f"{A}blip"):
        rid = blip.get(f"{R}embed")
        if not rid or rid not in doc.rels:
            continue
        target = doc.rels[rid][0]
        name = os.path.basename(target)
        media_used.add("word/" + target.lstrip("/") if not target.startswith("word/")
                       else target)
        # percent-encode the path: document titles carry spaces, and
        # `![alt](a path/img.png)` renders as literal text in every strict
        # Markdown parser — an image reference that does not resolve is a
        # dropped image with extra steps.
        href = quote(f"{media_prefix}/{name}", safe="/#")
        return f"![{name}]({href})"
    return ""


def _paragraph_inline(doc: Docx, p, media_prefix, media_used):
    """A paragraph's inline Markdown: runs with emphasis, hyperlinks, images."""
    out = []
    for child in p:
        if child.tag == f"{W}hyperlink":
            inner = "".join(_emphasize(_run_text(r), _is_on(r.find(f"{W}rPr"), "b"),
                                       _is_on(r.find(f"{W}rPr"), "i"))
                            for r in child.findall(f"{W}r"))
            rid = child.get(f"{R}id")
            href = doc.rels.get(rid, ("", ""))[0] if rid else ""
            out.append(f"[{inner}]({href})" if href and inner.strip() else inner)
        elif child.tag == f"{W}r":
            rpr = child.find(f"{W}rPr")
            for d in child.findall(f".//{W}drawing"):
                ref = _image_ref(doc, d, media_prefix, media_used)
                if ref:
                    out.append(ref)
            txt = _run_text(child)
            if txt:
                out.append(_emphasize(txt, _is_on(rpr, "b"), _is_on(rpr, "i")))
        elif child.tag in (f"{W}ins", f"{W}del"):
            # Tracked insertions ARE in the document (they are the current text);
            # deletions are not. Both are counted and reported by survey().
            if child.tag == f"{W}ins":
                for r in child.findall(f"{W}r"):
                    rpr = r.find(f"{W}rPr")
                    txt = _run_text(r)
                    if txt:
                        out.append(_emphasize(txt, _is_on(rpr, "b"), _is_on(rpr, "i")))
    return "".join(out)


def _paragraph_block(doc: Docx, p, media_prefix, media_used, counters):
    """One paragraph rendered as a Markdown block, honoring heading level and
    list nesting/numbering."""
    inline = _paragraph_inline(doc, p, media_prefix, media_used).strip()
    ppr = p.find(f"{W}pPr")
    style_id = ""
    if ppr is not None:
        st = ppr.find(f"{W}pStyle")
        style_id = (st.get(f"{W}val") or "") if st is not None else ""

    # heading?
    level = None
    m = _HEADING_RE.match(style_id.replace("Heading", "heading "))
    if m:
        level = int(m.group(1))
    else:
        m2 = _HEADING_RE.match(doc.style_name(style_id))
        if m2:
            level = int(m2.group(1))
        elif ppr is not None:
            ol = ppr.find(f"{W}outlineLvl")
            if ol is not None and (ol.get(f"{W}val") or "").isdigit():
                level = int(ol.get(f"{W}val")) + 1
    if level:
        counters.clear()
        return ("#" * min(level, 6)) + " " + inline if inline else ""

    # list?
    numpr = ppr.find(f"{W}numPr") if ppr is not None else None
    if numpr is not None:
        ilvl_el, numid_el = numpr.find(f"{W}ilvl"), numpr.find(f"{W}numId")
        ilvl = int(ilvl_el.get(f"{W}val")) if ilvl_el is not None else 0
        num_id = numid_el.get(f"{W}val") if numid_el is not None else None
        fmt = doc.num_format(num_id, ilvl)
        indent = "  " * ilvl
        # A nested sub-list must NEVER reset its parent's numbering. Word models
        # the sub-list as a different numId, so a blanket reset renumbered every
        # top-level item back to 1 the moment a bullet appeared under it — the
        # document said "1. … 2. …" and the Markdown said "1. … 1. …". Only
        # levels DEEPER THAN THIS ONE, in this same list, restart.
        for k in list(counters):
            if k[1] > ilvl:
                del counters[k]
        if fmt == "bullet":
            return f"{indent}- {inline}"
        key = (num_id, ilvl)
        counters[key] = counters.get(key, 0) + 1
        return f"{indent}{counters[key]}. {inline}"

    counters.clear()
    return inline


def _table_block(doc: Docx, tbl, media_prefix, media_used):
    """A table as a GitHub-flavoured pipe table. Cell text is flattened to one
    line: a newline inside a pipe cell ends the table, so preserving the break
    would destroy the table it claims to preserve."""
    rows = []
    for tr in tbl.findall(f"{W}tr"):
        cells = []
        for tc in tr.findall(f"{W}tc"):
            texts = [_paragraph_inline(doc, p, media_prefix, media_used).strip()
                     for p in tc.findall(f"{W}p")]
            cells.append(" ".join(t for t in texts if t).replace("|", r"\|"))
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "|".join([" --- "] * width) + "|"]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _body_children(document):
    """Body-level blocks in document order, descending into structured document
    tags (content controls) so their paragraphs keep their true position."""
    body = document.find(f"{W}body")
    if body is None:
        return []
    out = []

    def walk(node):
        for child in node:
            if child.tag == f"{W}sdt":
                content = child.find(f"{W}sdtContent")
                if content is not None:
                    walk(content)
            elif child.tag in (f"{W}p", f"{W}tbl"):
                out.append(child)
    walk(body)
    return out


def to_markdown(doc: Docx, media_prefix="media"):
    """Convert the document body to Markdown. Returns (markdown, media_used).

    Module-level by design: the verification gate's own regression test replaces
    this function with a lossy one to prove the gate fires (SPEC DoD-2).
    """
    blocks, media_used, counters = [], set(), {}
    for el in _body_children(doc.document):
        if el.tag == f"{W}tbl":
            counters.clear()
            b = _table_block(doc, el, media_prefix, media_used)
        else:
            b = _paragraph_block(doc, el, media_prefix, media_used, counters)
        blocks.append(b)
    # Drop empty blocks (a Word document is mostly empty paragraphs), then join:
    # consecutive list items with a single newline so the list stays one list,
    # everything else with a blank line. A blank line between every item makes a
    # loose list that renders as separated paragraphs — the nesting survives the
    # conversion and then dies in the renderer.
    kept = [b for b in blocks if b.strip()]
    out = ""
    for i, b in enumerate(kept):
        if i == 0:
            out = b
            continue
        both_list = bool(_LIST_LINE.match(b) and _LIST_LINE.match(kept[i - 1]))
        out += ("\n" if both_list else "\n\n") + b
    return out + "\n", media_used


# --------------------------------------------------------------------------
# the verification gate — the feature
# --------------------------------------------------------------------------

def normalize(text):
    """Compare-normalization: Unicode-folded, whitespace-collapsed, and with the
    typographic substitutions Word makes silently (curly quotes, en/em dashes,
    non-breaking spaces) folded to their ASCII forms. Normalizing this far is
    what makes the comparison CHARACTER-level rather than word-level: two
    strings that survive it are the same characters, not merely the same words.
    """
    t = unicodedata.normalize("NFKC", text or "")
    t = (t.replace("‘", "'").replace("’", "'")
          .replace("“", '"').replace("”", '"')
          .replace("–", "-").replace("—", "-")
          .replace(" ", " ").replace("​", ""))
    return re.sub(r"\s+", " ", t).strip()


_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_EMPH = re.compile(r"\*{1,3}")
_LEAD = re.compile(r"^\s{0,8}(#{1,6}\s+|[-*]\s+|\d+\.\s+)", re.M)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def plain(markdown, strip_lead=True):
    """The AUTHOR's text with OUR markup removed.

    The comparison must be against the words, not against the syntax this
    converter added: a hyperlink the author wrote as `ReferralCandy` becomes
    `[ReferralCandy](https://…)` in the output, and a naive substring check would
    call that a dropped paragraph. Every construct removed here is one this
    converter INTRODUCED — link and image syntax, emphasis markers, the pipes of
    a table row (recognised line by line, so a pipe the AUTHOR typed inside
    ordinary prose is left exactly where it is), and — under `strip_lead` — the
    heading and list prefixes. That last one is ambiguous by nature, which is why
    it is optional: `1.` at the start of a line may be Word's list numbering
    (ours to remove) or characters the author typed (never ours to remove), and
    the two are indistinguishable in the output. `verify` therefore checks both
    renderings rather than betting on one.
    """
    out = []
    for line in _EMPH.sub("", _LINK.sub(r"\1", _IMG.sub(" ", markdown))).split("\n"):
        if _TABLE_ROW.match(line):
            line = line.strip().strip("|")
            line = line.replace(r"\|", "\x00").replace("|", " ").replace("\x00", "|")
        out.append(line)
    joined = "\n".join(out)
    return _LEAD.sub("", joined) if strip_lead else joined


def text_bearing_paragraphs(doc: Docx):
    """Every paragraph in the main flow that carries text, in document order.

    This is the set the extractor is ANSWERABLE FOR — and the denominator is
    never quietly shrunk to make the pass rate look better. The only paragraphs
    excluded are the ones INSIDE text boxes, and they are excluded because their
    text is already counted through the paragraph the box is anchored in;
    counting them again would inflate both sides of the report by the same
    amount and prove nothing. Anything genuinely not extracted (footnotes,
    endnotes, comments) lives in a different part of the package, is counted by
    survey(), and is named in the report with its count.
    """
    boxed = {id(p) for p in _textbox_paragraphs(doc.document)}
    out = []
    for p in _walk(doc.document):
        if p.tag != f"{W}p" or id(p) in boxed:
            continue
        txt = "".join(t.text or "" for t in _walk(p) if t.tag == f"{W}t")
        if normalize(txt):
            out.append(txt)
    return out


def verify(paragraphs, markdown):
    """Prove that zero text-bearing paragraphs were dropped.

    Returns (ok, detail). Every source paragraph must appear, normalized, inside
    the normalized Markdown. `detail` reports the counts on both sides and the
    INDEX of every unmatched paragraph — indices and lengths, never the text, so
    a verification report can be shown for a source the caller may not read.
    """
    # Three renderings of the SAME output, because each covers the others' blind
    # spots: the raw Markdown preserves everything the converter emitted; the
    # markup-stripped rendering restores link text that link syntax broke up; and
    # the prefix-stripped rendering removes list/heading markers the converter
    # added. A paragraph that genuinely failed to survive appears in NONE of the
    # three, so the gate still fires on every real loss. What this removes is the
    # false failure — a paragraph reported as dropped because of markup this
    # converter introduced. A gate that cries wolf gets switched off, and a
    # switched-off gate is how silent loss returns.
    hay = "\n⋮\n".join([normalize(markdown),
                        normalize(plain(markdown, strip_lead=False)),
                        normalize(plain(markdown, strip_lead=True))])
    unmatched = []
    matched_chars = 0
    for i, p in enumerate(paragraphs, start=1):
        n = normalize(p)
        if n and n in hay:
            matched_chars += len(n)
        else:
            unmatched.append((i, len(n)))
    total_chars = sum(len(normalize(p)) for p in paragraphs)
    detail = {
        "check": "paragraph-parity + character-parity (normalized)",
        "source_paragraphs": len(paragraphs),
        "matched_paragraphs": len(paragraphs) - len(unmatched),
        "unmatched_paragraphs": len(unmatched),
        "source_characters": total_chars,
        "matched_characters": matched_chars,
        "unmatched_index_and_length": unmatched[:20],
    }
    return (not unmatched), detail


# --------------------------------------------------------------------------
# placement
# --------------------------------------------------------------------------

def _reg_path(root, fid, default):
    if yaml is None:
        return default
    try:
        with open(os.path.join(root, "System", "Registries", "folder-registry.yaml"),
                  encoding="utf-8") as stream:
            reg = yaml.safe_load(stream)
        value = reg["folders"].get(fid, {}).get("path", default)
    except Exception as exc:
        raise SafePathError(f"folder registry cannot resolve {fid}: {exc}") from exc
    return safe_relative_path(str(value), f"folder registry path for {fid}")


def _local_only_dir(path):
    """The nearest enclosing `Local Only/` directory, or None.

    A capture under Local Only is `ai_use: local-only` and gitignored (DEC-065 /
    privacy rule 7). Filing its original or its images into the shared
    Attachments folder would walk private material straight across the fence the
    user drew — so the derivative stays inside the same fence as its source.
    """
    cur = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.basename(cur).strip().lower() == "local only":
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def sanitize(name):
    """F-6 filename sanitization: strip characters illegal on any of the three
    platforms plus trailing dots/spaces, which imported titles routinely carry."""
    out = "".join("-" if c in _ILLEGAL else c for c in name)
    return out.strip().rstrip(". ").strip() or "document"


def _slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "document"


def _unique(path):
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    i = 2
    while os.path.exists(f"{stem}-{i}{ext}"):
        i += 1
    return f"{stem}-{i}{ext}"


def _unique_rel(root, relpath, reserved=None):
    """Choose a non-existing contained name; the transaction re-proves it."""
    relpath = safe_relative_path(relpath)
    reserved = reserved or set()
    candidate = relpath
    stem, ext = os.path.splitext(relpath)
    i = 2
    while candidate in reserved or os.path.lexists(os.path.join(root, candidate)):
        candidate = f"{stem}-{i}{ext}"
        i += 1
    return candidate


def _pointer_note(rel_original, stem, reason):
    """The note that stands in for a document the extractor could not vouch for.
    It says what failed, in the note itself — a pointer that does not name the
    failure is how a silent loss looks from the inside."""
    today = date.today().isoformat()
    return (
        "---\n"
        f"id: source-{_slug(stem)}\n"
        "type: source\n"
        "subtype: document\n"
        f"created: '{today}'\n"
        f"updated: '{today}'\n"
        f"summary: \"Unextracted document — {reason}. The original is preserved; "
        "its text has NOT entered the vault.\"\n"
        "status: draft\n"
        "verification: unverified\n"
        f"original_location: \"{rel_original}\"\n"
        "x_extraction_status: failed\n"
        "---\n\n"
        f"# {stem}\n\n"
        f"**Extraction failed — {reason}.**\n\n"
        f"The original is preserved unchanged at `{rel_original}`. No Markdown was "
        "emitted, deliberately: a partial conversion is worse than none, because its "
        "losses are invisible. Re-run `aios extract` after resolving the cause, or "
        "convert by hand and capture the result through `ingest-and-connect` step 2.\n"
    )


def _derivative_frontmatter(stem, rel_original, detail, notices):
    today = date.today().isoformat()
    lines = ["---",
             f"id: source-{_slug(stem)}",
             "type: source",
             "subtype: document",
             f"created: '{today}'",
             f"updated: '{today}'",
             f"summary: \"Text extracted from {os.path.basename(rel_original)} by "
             f"aios extract; {detail['source_paragraphs']} text-bearing paragraphs, "
             f"all verified present.\"",
             "status: draft",
             "verification: unverified",
             f"original_location: \"{rel_original}\"",
             f"x_extraction_check: \"{detail['check']}\"",
             f"x_extraction_paragraphs: {detail['source_paragraphs']}",
             f"x_extraction_characters: {detail['source_characters']}"]
    if notices:
        lines.append("x_extraction_not_extracted:")
        for n in notices:
            lines.append(f"  - \"{n}\"")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


# --------------------------------------------------------------------------
# command
# --------------------------------------------------------------------------

SUPPORTED = (".docx",)


def run(root, args, rep: Report):
    path = getattr(args, "target", None)
    if not path:
        rep.error("usage: aios extract <file.docx> [--dry-run]  "
                  "(v1 extracts .docx only; .pdf is not implemented)")
        return rep
    root = os.path.abspath(root)
    full = os.path.abspath(path if os.path.isabs(path) else os.path.join(root, path))
    ext = os.path.splitext(full)[1].lower()
    if ext not in SUPPORTED:
        rep.error(f"unsupported format '{ext}' — v1 extracts {', '.join(SUPPORTED)} only. "
                  f"Other binaries follow ingest-and-connect's attachment path "
                  f"(Attachments/ + a pointer source note); nothing is dropped.")
        return rep

    dry = bool(getattr(args, "dry_run", False))
    stem = sanitize(os.path.splitext(os.path.basename(full))[0])
    internal = _inside_root(root, full)
    source_batch = None
    explicit_input = None
    try:
        if internal and not dry:
            source_batch = preflight_contained_regular_files(root, [full])
            source_bytes = source_batch.read_bytes(max_bytes=DOCX_MAX_COMPRESSED)[full]
        else:
            explicit_input = read_regular_file(full, max_bytes=DOCX_MAX_COMPRESSED)
            source_bytes = explicit_input.data
    except SafePathError as exc:
        rep.error(f"input refused: {exc}")
        return rep

    try:
        return _run_loaded(root, full, internal, dry, stem, source_bytes,
                           source_batch, explicit_input, rep)
    finally:
        if source_batch is not None:
            source_batch.close()


def _inside_root(root, path):
    try:
        return os.path.commonpath((root, path)) == root
    except ValueError:
        return False


def _run_loaded(root, full, internal, dry, stem, source_bytes,
                source_batch, explicit_input, rep):
    source_dir = os.path.dirname(full)
    source_dir_rel = os.path.relpath(source_dir, root) if internal else None

    try:
        attachments_rel = _reg_path(root, "attachments", "30 Sources/Attachments")
        inbox_rel = _reg_path(root, "inbox", "00 Inbox")
        fence = _local_only_dir(full) if internal else None
        if fence:
            attachments_rel = safe_relative_path(
                os.path.relpath(os.path.join(fence, "Attachments"), root).replace(os.sep, "/"),
                "Local Only attachment path",
            )
        derivative_dir_rel = safe_relative_path(
            source_dir_rel.replace(os.sep, "/") if internal else inbox_rel,
            "derivative output directory",
        )
    except SafePathError as exc:
        rep.error(f"output containment refused: {exc}")
        return rep

    reserved = set()
    original_rel = _unique_rel(
        root, f"{attachments_rel}/{stem}.docx", reserved
    ); reserved.add(original_rel)
    media_dir_rel = _unique_rel(
        root, f"{attachments_rel}/{stem}-media", reserved
    )
    if not dry:
        selected = [derivative_dir_rel, original_rel, media_dir_rel]
        if internal:
            selected.append(os.path.relpath(full, root).replace(os.sep, "/"))
        try:
            refuse_protected_targets(root, selected, "extract")
        except ProtectedTargetError as exc:
            rep.error(f"output containment refused: {exc}")
            return rep
    derivative_parent = os.path.join(root, derivative_dir_rel)
    media_dir = os.path.join(root, media_dir_rel)
    media_prefix = os.path.relpath(media_dir, derivative_parent).replace(os.sep, "/")

    try:
        doc = Docx(source_bytes, path=full)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, KeyError, ET.ParseError,
            ValueError, RuntimeError) as e:
        rep.error(f"not a readable .docx ({type(e).__name__}: {e}) — the input "
                  f"remains unchanged and its text has NOT entered the vault")
        return rep

    found = survey(doc)
    notices = []
    for key, label in (("footnotes", "footnotes"), ("endnotes", "endnotes"),
                       ("comments", "comments")):
        if found[key]:
            notices.append(f"contains {found[key]} {label} — NOT extracted (v1); "
                           f"their text is not in the Markdown")
    if found["text_boxes"]:
        notices.append(f"contains {found['text_boxes']} paragraphs in text boxes — their "
                       f"text IS extracted, inline where the box is anchored, but a "
                       f"floating frame's true position cannot be expressed in Markdown")
    if found["tracked_deletions"]:
        notices.append(f"contains {found['tracked_deletions']} tracked deletions — "
                       f"deleted text is not resurrected")
    if found["tracked_insertions"]:
        notices.append(f"contains {found['tracked_insertions']} tracked insertions — "
                       f"kept (they are the current text); accept/reject in Word to settle them")
    for n in notices:
        rep.warn(n)

    markdown, media_used = to_markdown(doc, media_prefix=media_prefix)
    paragraphs = text_bearing_paragraphs(doc)
    ok, detail = verify(paragraphs, markdown)

    rep.info["source"] = (os.path.relpath(full, root) if internal else full)
    rep.info["verification"] = detail["check"]
    rep.info["paragraphs"] = (f"{detail['matched_paragraphs']}/{detail['source_paragraphs']} "
                              f"text-bearing paragraphs verified present")
    rep.info["characters"] = (f"{detail['matched_characters']:,}/"
                              f"{detail['source_characters']:,} characters accounted for")
    rep.info["images"] = len(media_used)

    if not ok:
        rep.info["unmatched"] = detail["unmatched_index_and_length"]
        rep.error(f"VERIFICATION FAILED — {detail['unmatched_paragraphs']} text-bearing "
                  f"paragraph(s) did not survive conversion. No Markdown was written: a "
                  f"partial extraction is refused by design (SPEC-doc-extraction §3). The "
                  f"original is filed to Attachments with a pointer note saying so.")
        if dry:
            rep.info["dry_run"] = "nothing written"
            return rep
        pointer_rel = _unique_rel(
            root, f"{derivative_dir_rel}/{stem} (unextracted).md", reserved
        ); reserved.add(pointer_rel)
        writes = {
            original_rel: source_bytes,
            pointer_rel: _pointer_note(
                original_rel, stem,
                f"{detail['unmatched_paragraphs']} paragraph(s) failed the parity check",
            ).encode("utf-8"),
        }
        if not _commit_outputs(root, writes, internal, source_batch,
                               explicit_input, rep):
            return rep
        rep.info["original_filed"] = original_rel
        rep.info["pointer_note"] = pointer_rel
        return rep

    if dry:
        rep.info["dry_run"] = ("verification PASSED — nothing written. Re-run without "
                               "--dry-run to emit the Markdown and file the original.")
        return rep

    out_rel = _unique_rel(root, f"{derivative_dir_rel}/{stem}.md", reserved)
    reserved.add(out_rel)
    writes = {
        original_rel: source_bytes,
        out_rel: (_derivative_frontmatter(stem, original_rel, detail, notices)
                  + markdown).encode("utf-8"),
    }
    media_outputs = set()
    for name in sorted(media_used):
        data = doc.media.get(name)
        if data is None:
            continue
        basename = os.path.basename(name)
        media_rel = safe_relative_path(f"{media_dir_rel}/{basename}", "DOCX media output")
        key = unicodedata.normalize("NFC", media_rel).casefold()
        if key in media_outputs:
            rep.error("output containment refused: DOCX media names have a case/Unicode collision")
            return rep
        media_outputs.add(key)
        writes[media_rel] = data
    if not _commit_outputs(root, writes, internal, source_batch, explicit_input, rep):
        return rep

    rep.info["markdown"] = out_rel
    rep.info["original_filed"] = original_rel
    if media_used:
        rep.info["media"] = media_dir_rel
    rep.info["next"] = ("the derivative is born status: draft — carry it through "
                        "ingest-and-connect from step 1 (it is a capture, not canon)")
    return rep


def _commit_outputs(root, writes, internal, source_batch, explicit_input, rep):
    try:
        if explicit_input is not None:
            explicit_input.reprove()
        result = atomic_create_files(
            root, writes,
            remove_batch=source_batch if internal else None,
            remove_target=source_batch.targets[0] if internal else None,
            read_only_inputs=(explicit_input,) if explicit_input is not None else (),
        )
    except SafePathError as exc:
        rep.error(str(exc))
        return False
    rep.info["output_transaction_durable"] = result.durable
    for warning in result.cleanup_warnings:
        rep.warn(f"outputs committed durably; cleanup warning: {warning}")
    return True
