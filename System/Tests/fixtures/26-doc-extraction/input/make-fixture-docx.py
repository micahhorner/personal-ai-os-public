#!/usr/bin/env python3
"""Build the fixture `.docx` for fixture 26 — deterministically, from the stdlib.

Why a generator and not a committed binary: a `.docx` in git is an opaque blob
nobody can review, diff, or amend, and this one exists precisely to be argued
with ("does the converter keep a *third-level* bullet?"). Written as code, the
document IS its own specification — and it is the same document the unit suite
(`System/Tests/scripts/test_extract.py`) builds, so the behavioral fixture and
the regression test can never describe different files.

Usage:  python3 make-fixture-docx.py [outpath.docx]

What it contains, and why each piece is there:
  - Heading 1 / Heading 2 / Heading 3      → heading LEVELS must survive
  - a three-level nested list, numbered at the top level and bulleted below
                                           → nesting AND numbering must survive
  - bold, italic, and bold+italic runs      → run formatting must survive
  - a 2x3 table with a header row           → tables must survive
  - one PNG, mid-document                   → images land beside the original and
                                             are referenced AT THEIR TRUE POSITION
  - one footnote and one text box           → the dark corners: DETECTED and
                                             REPORTED with counts, never dropped
                                             in silence
"""
import os
import sys
import zipfile

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
WP = 'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
PIC = 'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'

# A 1x1 transparent PNG — the smallest real image, so the fixture proves the
# media path without carrying a payload anyone has to trust.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001" "0d0a2db4" "0000000049454e44ae426082")


def p(text, style=None, numid=None, ilvl=0, bold=False, italic=False):
    ppr = ""
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if numid is not None:
        ppr += f'<w:numPr><w:ilvl w:val="{ilvl}"/><w:numId w:val="{numid}"/></w:numPr>'
    ppr = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    rpr = ""
    if bold:
        rpr += "<w:b/>"
    if italic:
        rpr += "<w:i/>"
    rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def document_xml():
    rows = [["Signal", "Where it lives", "Who owns it"],
            ["Voice split", "the transcript", "the human"],
            ["Overlap map", "the source frontmatter", "the human"]]
    tbl = "<w:tbl>"
    for r in rows:
        tbl += "<w:tr>" + "".join(
            f'<w:tc><w:p><w:r><w:t xml:space="preserve">{c}</w:t></w:r></w:p></w:tc>' for c in r) + "</w:tr>"
    tbl += "</w:tbl>"

    image = (
        '<w:p><w:r><w:drawing><wp:inline><a:graphic><a:graphicData>'
        '<pic:pic><pic:blipFill><a:blip r:embed="rId10"/></pic:blipFill></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>")

    footnote_ref = ('<w:p><w:r><w:t xml:space="preserve">A claim that cites something.</w:t></w:r>'
                    '<w:r><w:footnoteReference w:id="2"/></w:r></w:p>')

    textbox = ('<w:p><w:r><mc:AlternateContent '
               'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
               "<mc:Fallback><w:pict><v:shape xmlns:v=\"urn:schemas-microsoft-com:vml\">"
               "<v:textbox><w:txbxContent>"
               '<w:p><w:r><w:t xml:space="preserve">Pull quote parked in a text box.</w:t></w:r></w:p>'
               "</w:txbxContent></v:textbox></v:shape></w:pict></mc:Fallback>"
               "</mc:AlternateContent></w:r></w:p>")

    body = "".join([
        p("Verification Is The Feature", style="Heading1"),
        p("An extractor nobody can audit is worse than none at all, because its "
          "losses are invisible."),
        p("What v1 Preserves", style="Heading2"),
        p("Structure survives conversion", numid=1, ilvl=0),
        p("Headings keep their level", numid=2, ilvl=1),
        p("Lists keep their nesting", numid=2, ilvl=1),
        p("Even at the third level", numid=2, ilvl=2),
        p("Formatting survives conversion", numid=1, ilvl=0),
        p("This phrase is bold.", bold=True),
        p("This phrase is italic.", italic=True),
        p("This phrase is both.", bold=True, italic=True),
        p("Evidence", style="Heading3"),
        tbl,
        p("The image below sits between two paragraphs and must stay there."),
        image,
        p("This paragraph follows the image."),
        footnote_ref,
        textbox,
    ])
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f"<w:document {W} {R} {WP} {A} {PIC}><w:body>{body}</w:body></w:document>")


NUMBERING = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering {W}>
  <w:abstractNum w:abstractNumId="1">
    <w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="2">
    <w:lvl w:ilvl="1"><w:numFmt w:val="bullet"/></w:lvl>
    <w:lvl w:ilvl="2"><w:numFmt w:val="bullet"/></w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="2"/></w:num>
</w:numbering>'''

STYLES = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {W}>
  <w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>
  <w:style w:styleId="Heading3"><w:name w:val="heading 3"/></w:style>
</w:styles>'''

FOOTNOTES = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes {W}>
  <w:footnote w:type="separator" w:id="0"><w:p/></w:footnote>
  <w:footnote w:type="continuationSeparator" w:id="1"><w:p/></w:footnote>
  <w:footnote w:id="2"><w:p><w:r><w:t>The footnote nobody extracted.</w:t></w:r></w:p></w:footnote>
</w:footnotes>'''

RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/diagram.png"/>
  <Relationship Id="rId11" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
  <Relationship Id="rId12" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId13" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

PACKAGE_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''


def build(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", PACKAGE_RELS)
        z.writestr("word/document.xml", document_xml())
        z.writestr("word/_rels/document.xml.rels", RELS)
        z.writestr("word/numbering.xml", NUMBERING)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/footnotes.xml", FOOTNOTES)
        z.writestr("word/media/diagram.png", PNG)
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "fixture-document.docx"
    print(build(out))
