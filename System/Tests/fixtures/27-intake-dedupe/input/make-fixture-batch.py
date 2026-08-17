#!/usr/bin/env python3
"""Build the fixture intake batch for fixture 27 — the proven case, at scale 1:100.

The regression bar for `aios dedupe-batch` is the case that produced it: four
documents handed over together on 2026-07-15, of which one was **97% a paste-up**
of two siblings — 95% of the first and 49% of the second — while the fourth was
genuinely independent. Those three percentages ARE the test.

The real captures are one user's private material, live under a `Local Only/`
fence and are not in this repository — so this generator builds a synthetic batch
with the same shape and the same arithmetic: four files whose overlap lands on
97 / 95 / 49 / 0 by construction. Written as code rather than committed as four
prose files because the numbers are the point, and in code the numbers are
visible and checkable rather than an artefact of how much text someone pasted.

The paragraphs are filler sentences on purpose: this command hashes normalized
paragraphs, so WHAT they say is irrelevant to what is being tested, and filler
keeps anyone from reading meaning into a regression fixture.

Usage:  python3 make-fixture-batch.py [outdir]
"""
import os
import sys

# Long enough to clear the 8-word floor (below it, paragraphs are excluded from
# the matrix as boilerplate and counted separately).
def para(tag, i):
    return (f"This is paragraph {i} of the {tag} document, written at sufficient "
            f"length that it counts as a comparable paragraph rather than "
            f"boilerplate under the intake threshold.")


SHORT = ["Yes.", "Agreed.", "## Section", "Jane Doe", "July 2026"]

FRONTMATTER = ("---\n"
               "id: source-fixture-{slug}\n"
               "type: source\n"
               "subtype: conversation\n"
               "created: '2026-07-26'\n"
               "updated: '2026-07-26'\n"
               "summary: \"Fixture capture for the intake-batch dedupe regression.\"\n"
               "status: draft\n"
               "verification: unverified\n"
               "---\n\n")


def build(outdir):
    os.makedirs(outdir, exist_ok=True)

    source_a = [para("first-source", i) for i in range(100)]      # 100 comparable
    source_b = [para("second-source", i) for i in range(100)]     # 100 comparable
    independent = [para("independent", i) for i in range(60)]     # shares nothing

    # The paste-up: 95 paragraphs lifted from A, 49 from B, 5 of its own.
    #   95 / 100  -> 95% of A                      (the recorded 95%)
    #   49 / 100  -> 49% of B                      (the recorded 49%)
    #   5 / 149   -> 3% unique, i.e. 97% repeated  (the recorded 97%)
    # Note the trap this reproduces exactly: the paste-up is the SUPERSET. It is
    # the biggest file in the batch, so "keep the biggest" would keep the copy.
    paste_up = (["Tab 1"] + source_a[:95] + ["Tab 2"] + source_b[:49]
                + [para("paste-up-original", i) for i in range(5)])

    files = {
        "capture-a.md": ("capture-a", source_a),
        "capture-b.md": ("capture-b", source_b),
        "capture-paste-up.md": ("capture-paste-up", paste_up),
        "capture-independent.md": ("capture-independent", independent),
    }
    written = []
    for name, (slug, paras) in files.items():
        path = os.path.join(outdir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(FRONTMATTER.format(slug=slug))
            # Short paragraphs go into every file: they are the boilerplate that
            # would read as corroboration if the threshold did not exclude them.
            fh.write("\n\n".join(SHORT + paras) + "\n")
        written.append(path)
    return written


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "batch"
    for p in build(out):
        print(p)
