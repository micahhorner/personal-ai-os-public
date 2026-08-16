"""vault.doc-audit — the documentation-truth gate (DEC-064).

Fails if any document makes a countable claim that contradicts the source of truth.

Sibling of `doc-check` (is every component covered?) and `doc-commands` (is every
command documented?). This one asks: **is what the docs say TRUE?** Every
hand-maintained enumeration in the product had drifted (the spec said six
capabilities while nine existed; the atlas header pinned a version six releases
old). `doc-commands` never drifted, because it reads argparse via AST. Same cure,
generalized: the universe of truth is read from source on every run — never from
a stored baseline, because a stored baseline is the thing that drifts.

Historical records are exempt (the record-lifecycle rule, constitution §4.8: dated evidence is never rewritten to
match now): CHANGELOG, the change journal, Tests/results, Migrations. A changelog
entry that says "10 fixtures" was true when written.

Also exempt: fenced code, blockquotes (docs may QUOTE a wrong claim), rates
("one folder per add-on"), minimums ("at least one diagram"), version-transition
records ("1.12.0→1.14.0"), and passages describing other products (PMM Engine).

Read-only. Composed into `aios health`; run standalone as `aios doc-audit`.
"""
from __future__ import annotations
import ast
import glob
import os
import re

try:
    import yaml
except ImportError:
    yaml = None


def _read_text(path, *, errors=None):
    kwargs = {"encoding": "utf-8"}
    if errors is not None:
        kwargs["errors"] = errors
    with open(path, **kwargs) as stream:
        return stream.read()


def _read_yaml(path):
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)

# Number words, parsed GENERALLY rather than enumerated. The old hard-coded set
# stopped at a scatter of values (…twenty, twenty-five, twenty-six, thirty,
# thirty-nine, fifty, seventy) and every other word-number returned None and was
# silently skipped — not even counted as a claim. The constitution writes almost
# every census heading in exactly that notation ("the thirty-eight validate
# rules", "the twenty-two read commands", "the eighty-four unit tests"), so the
# document that most needed auditing wrote its numbers in the one form the
# auditor could not read. Range: 0–99, which is what the corpus uses — the
# highest word-number anywhere in the doc set is "eighty-four".
_ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
         "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}

# Historical records: true when written, never rewritten to match now (constitution §4.8).
HIST = ("CHANGELOG.md", "change-journal.md", os.sep + "results" + os.sep,
        os.sep + "fixtures" + os.sep, os.sep + "Generated" + os.sep,
        os.sep + "Migrations" + os.sep)

# Exempt from DATED-FIGURE claims — counts and, since DEC-109, component
# versions — while still scanned for behaviour and for system_version. Every
# line of the decision register is a dated record of what one release changed
# ("two new core capabilities", "129 messages", "constitution 2.12.0",
# "`safe-write` 0.4.0"); those were true when the decision was taken, exactly
# like a CHANGELOG entry, and a version is a figure of precisely that kind.
#
# What is NOT exempt here is the register's PATHS. `docpaths` used to skip this
# file wholesale and no longer does (DEC-109 / GAP-8): a count was true when
# written, but a pointer is followed by whoever reads the entry and a dead one
# is dead in any year. The two gates now disagree about this file deliberately,
# and the disagreement is the correct shape.
HIST_COUNTS = ("Active Decisions.md",)

# What noun phrases in prose refer to which truth key. The number must be adjacent.
NOUNS = {
    # `?…`? : prose writes the tool name in backticks ("the 19 `aios` subcommands");
    # without tolerating them this matcher silently skipped exactly those claims —
    # found when adding doc-paths made the Glossary's 19 false and nothing fired
    "commands":            [r"`?aios`? subcommands?", r"CLI commands?"],
    "flags":               [r"flags?"],
    "operations":          [r"(?:stable |vault )?operations?"],
    "capabilities":        [r"(?:task-level )?capabilit(?:y|ies)", r"playbooks?"],
    "agents":              [r"agents?"],
    "workflows":           [r"workflows?"],
    # More specific first: NOUNS is order-sensitive (see `_consumed` in scan_text),
    # so "7 note-class templates" is judged against the note-class subset, not
    # against every file in Templates/.
    "note-class templates": [r"note-class templates?"],
    "templates":           [r"templates?"],
    "fixtures":            [r"fixtures?"],
    # Plural-only where the singular is also an ordinary word or a verb: "one
    # self-contained folder" is a rate, "four families route" is a sentence.
    "folders":             [r"(?:registered |numbered )?folders"],
    "vocabularies":        [r"vocabular(?:y|ies)"],
    "vocabulary values":   [r"vocabulary values?"],
    "note classes":        [r"(?:note |record |knowledge )classes", r"kinds? of record", r"(?:note |record )types?"],
    # Four documents disagreed about this one number — the constitution said
    # eight, the dictionary nine, Change Control "all 8", and `links.py` ten.
    "relationships":       [r"typed relationships", r"relationship fields"],
    # `keys` needs a qualifier: the manifest's "seven top-level keys" is not a
    # claim about the 53 schema fields.
    "fields":              [r"(?:metadata |reserved )(?:fields|keys)", r"fields"],
    "principles":          [r"(?:design )?principles?"],
    "protected objects":   [r"protected objects?"],
    "routes":              [r"routes"],
    "diagrams":            [r"diagrams?"],
    "source subtypes":     [r"source subtypes?"],
    "note subtypes":       [r"note subtypes?"],
    # DEC-105: classes of countable fact that previously had no truth key at all.
    # Every one of them was claimed in prose and every one of them had drifted —
    # the unit-test census by a factor of five, the message census by five
    # releases, the authority index by twenty-six files.
    "unit tests":          [r"unit tests", r"test suite"],
    "messages":            [r"(?:distinct |user-visible )?(?:error(?:[ /]and[ /]|[/ ])?(?:warning )?)?messages",
                            r"call sites"],
    "authority files":     [r"authority-marked (?:files|documents)"],
    "components":          [r"components"],
    "schemas":             [r"schema files"],
    "libraries":           [r"librar(?:y|ies)", r"library modules"],
    "documentation files": [r"documentation files"],
    "script modules":      [r"script modules", r"command modules"],
}

# What may sit between the number and the noun: an ACRONYM, and nothing else.
#
# The gap exists for exactly one shape — "9 **AI** playbooks", the line that has
# been wrong on the README three times because the matcher demanded strict
# adjacency. Any wider tolerance immediately starts reading *subset* claims as
# census claims: "two concurrency flags", "four governance fields", "thirteen
# contract fields" are all true statements about a slice of a set, and a gate
# that reddens on them is a gate people learn to ignore. A lowercase modifier is
# therefore treated as narrowing the set, and the claim is left alone; an
# acronym qualifies the noun's flavour without narrowing it.
GAP_TOKEN = re.compile(r"^[A-Z]{2,}$")

# Sentences that assert BEHAVIOUR the product has ruled out. A count gate cannot
# see these: no number is wrong, the description is. DEC-101 ruled that no
# scheduled pass may empty the Inbox; the phrase survived in eleven documents for
# ten days, and in the always-loaded Task Router for twelve more. Each entry is
# (regex, why) and each fires at the same severity as a wrong count.
BANNED_BEHAVIOUR = [
    (r"drain(?:s|ing)? the inbox|inbox drain(?:s|ing)?|empt(?:y|ies|ying) the inbox",
     "DEC-101: a scheduled or cadenced pass REPORTS the Inbox and offers; "
     "ingestion runs only on an explicit yes. Say 'reports the Inbox', "
     "or negate it explicitly ('never drains the Inbox')."),
]
# A negation is the whole point of the doctrine, so it is allowed — but it must
# sit BEFORE the phrase and ON THE SAME LINE. Both halves are load-bearing:
# "…drains the inbox automatically with no user consent" puts its negative word
# after the phrase and is the exact sentence the rule exists to catch, and a
# window that reaches into neighbouring lines reads an unrelated row of the Task
# Router as an exemption for the row below it. The cost is that a document
# discussing the retired phrase must negate it in the same breath — which is how
# it should have been written anyway.
_NEGATED = re.compile(r"\b(never|not|no|refuses?|without|nothing|rather than|instead of|"
                      r"must not|may not|cannot|can't|don't|does not|doesn't|forbid\w*)\b", re.I)

# 1–3 digits (a 4-digit token is a year) or a real number-word; never the tail
# of a section number (§3.5), a decimal, or an identifier — `DEC-070`,
# `30-folder-rules` and `00–90 folders` are names, not counts, and a leading
# hyphen or dash is what tells them apart.
#
# The word alternative is built from the parser's own vocabulary rather than
# left as "any lowercase word". It used to be the latter, which meant the
# matcher happily bound `product` in "the product ships six capabilities" and —
# because a regex scan does not overlap — swallowed the real claim behind it.
_WORDNUM = ("(?:" + "|".join(f"{t}(?:-(?:{'|'.join(k for k, v in _ONES.items() if 1 <= v <= 9)}))?"
                             for t in _TENS)
            + "|" + "|".join(sorted(_ONES, key=len, reverse=True)) + ")")
NUM = r"(?<![.\d§\-–—])(\d{1,3}|" + _WORDNUM + r")"

# The number may be bolded or backticked, and up to two content words may sit
# between it and the noun. "9 **AI** playbooks" slipped past three separate
# audits because the matcher demanded strict adjacency; the same blind spot hid
# every "**14** capabilities" whose closing `**` broke the space run. Bounded at
# two words on purpose: a wider window starts binding numbers across list
# separators. Intervening tokens are letters only, so punctuation (`·`, `,`, `.`)
# ends the window and a second number can never be swallowed; GAP_STOP removes
# the function words that would make the number a rate rather than a count.
# The separator also admits the one hyphenated form the corpus uses for a count
# ("the 84-test suite"), and nothing else.
_CLOSE = r"(?:\*\*|`|_)?"
_GAPWORD = rf"[ ]{{1,2}}{_CLOSE}[A-Za-z][A-Za-z\-]*{_CLOSE}"
# Lazy on purpose: the shortest gap that still matches wins, so "129 distinct
# messages" binds with no gap at all rather than swallowing "distinct" and then
# being discarded as a subset claim.
_GAP = rf"((?:{_GAPWORD}){{0,2}}?)"
_SEP = r"(?:[ ]{1,2}|-(?=test\b))"
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]*")


def _word_number(t):
    """0–99 from English words, parsed rather than looked up."""
    if t in _ONES:
        return _ONES[t]
    if t in _TENS:
        return _TENS[t]
    if "-" in t:
        tens, ones = t.split("-", 1)
        if tens in _TENS and ones in _ONES and 1 <= _ONES[ones] <= 9:
            return _TENS[tens] + _ONES[ones]
    return None


def _n(tok):
    t = tok.strip().lower().replace(",", "")
    if t.isdigit():
        return int(t)
    return _word_number(t)


# Version claims: what has a machine-readable source, and what deliberately does
# not (DEC-109, audit GAP-4).
#
# COVERED, because each of these declares its version in a file this function can
# open: capabilities (`SKILL.md` frontmatter), agents (`AGENT.md`), workflows,
# schemas (`schema_version`), the constitution, and the manifest's
# `vault_profile_version`. A claim about one of them in prose is checkable and is
# now checked.
#
# NOT COVERED, and named rather than quietly omitted — a gate that implies
# coverage it lacks is the defect this release exists to close:
UNCOVERED_VERSIONS = (
    "external specification versions (Open Knowledge Format, and the Obsidian "
    "plugin versions in the adapter docs) — the source of truth is outside this "
    "tree, so a claim about them can be stale and no local check can know",
    "the Python floor and dependency pins — declared in `pyproject.toml`, but "
    "claimed in prose as ranges ('>=3.9'), not as the equality this matcher tests",
    "documentation versions cited by document TITLE rather than by component "
    "name — the doc set has no stable prose name per file, and matching titles "
    "loosely is how a gate starts reporting sentences instead of facts",
)


def _fm_version(path):
    """The `version:` a markdown file declares in frontmatter, or None."""
    try:
        text = _read_text(path, errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    m = re.search(r"^version:\s*[\"']?([0-9]+\.[0-9]+\.[0-9]+)", text[3:end if end > 0 else 400], re.M)
    return m.group(1) if m else None


def _version_sources(j):
    """{prose name: declared version} for everything that declares one locally."""
    out = {}
    for pat, kind in ((("System", "Capabilities", "*", "SKILL.md"), "dir"),
                      (("System", "Agents", "*", "AGENT.md"), "dir")):
        for path in glob.glob(j(*pat)):
            v = _fm_version(path)
            if v:
                out[os.path.basename(os.path.dirname(path))] = v
    for path in glob.glob(j("System", "Workflows", "*.md")):
        v = _fm_version(path)
        if v:
            out[os.path.splitext(os.path.basename(path))[0]] = v
    for path in glob.glob(j("System", "Schemas", "*.yaml")):
        try:
            d = _read_yaml(path) or {}
        except Exception:                     # noqa: BLE001 — a bad schema is validate's problem
            continue
        v = d.get("schema_version")
        if v:
            out[os.path.splitext(os.path.basename(path))[0] + " schema"] = str(v)
    con = _fm_version(j("System", "Architecture", "Canonical Architecture Specification.md"))
    if con:
        # The three names the corpus actually uses for the same file.
        out["constitution"] = out["Canonical Architecture Specification"] = \
            out["architecture spec"] = con
    try:
        man = _read_yaml(j("SYSTEM-MANIFEST.yaml"))
        if man.get("system", {}).get("vault_profile_version"):
            out["vault_profile_version"] = str(man["system"]["vault_profile_version"])
    except Exception:                          # noqa: BLE001
        pass
    return out


def truth(root="."):
    """Every countable fact, read from source. The only place numbers come from."""
    T = {}
    j = lambda *p: os.path.join(root, *p)  # noqa: E731

    with open(j("System", "Scripts", "aios.py"), encoding="utf-8") as fh:
        src = fh.read()
    T["commands"] = len([e.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
                         for kw in n.keywords if kw.arg == "choices"
                         and isinstance(kw.value, (ast.List, ast.Tuple))
                         for e in kw.value.elts if isinstance(e, ast.Constant)])
    T["flags"] = len(set(re.findall(r'add_argument\(\s*["\'](--[a-z0-9\-]+)', src)))

    T["operations"] = len(_read_yaml(j("System", "Operations", "operations.yaml"))["operations"])
    T["capabilities"] = len(glob.glob(j("System", "Capabilities", "*", "SKILL.md")))
    T["agents"] = len(glob.glob(j("System", "Agents", "*", "AGENT.md")))
    T["workflows"] = len(glob.glob(j("System", "Workflows", "*.md")))
    T["templates"] = len(glob.glob(j("System", "Templates", "*.md")))
    T["fixtures"] = len([d for d in glob.glob(j("System", "Tests", "fixtures", "*"))
                         if os.path.isdir(d)])
    T["folders"] = len(_read_yaml(j("System", "Registries", "folder-registry.yaml"))["folders"])

    vraw = _read_yaml(j("System", "Schemas", "vocabularies.yaml"))
    vocab = vraw.get("vocabularies", vraw)
    T["vocabularies"] = len([k for k, v in vocab.items() if isinstance(v, list)])
    T["vocabulary values"] = sum(len(v) for v in vocab.values() if isinstance(v, list))
    for name in ("note_subtypes", "source_subtypes"):
        if name in vocab:
            T[name.replace("_", " ")] = len(vocab[name])

    schemas = [_read_yaml(p)
               for p in glob.glob(j("System", "Schemas", "*.yaml"))]
    T["note classes"] = len([d for d in schemas
                             if d and d.get("schema")
                             and d["schema"] not in {
                                 "component", "migration-manifest"
                             }])
    fields = set()
    for d in schemas:
        # Migration manifests are executable plan contracts, not canonical
        # note metadata. Including their fields makes the documentation's
        # note-field census jump whenever the migration protocol evolves.
        if d and d.get("schema") != "migration-manifest":
            fields |= set((d.get("fields") or {}).keys()) | set(d.get("required") or [])
    T["fields"] = len(fields)

    # Templates split two ways and the prose uses both: every file in Templates/,
    # and the subset that seeds a note class. `working.md` joined the second set
    # at v1.41.0 and the constitution's "all 7 note-class templates" never moved.
    # Note classes are the files that DECLARE `schema:` — `pack-manifest.yaml`
    # lives in this folder without one, on purpose (it is the contract for a
    # third-party pack manifest, not a record type), and a filename proxy would
    # count it.
    classes = {d["schema"] for d in schemas
               if isinstance(d, dict) and d.get("schema")} - {"component"}
    T["note-class templates"] = len([p for p in glob.glob(j("System", "Templates", "*.md"))
                                     if os.path.splitext(os.path.basename(p))[0] in classes])

    dp = _read_text(j("System", "Architecture", "Design Principles.md"))
    T["principles"] = len(re.findall(r"^[0-9]+\. \*\*", dp, re.M))

    man = _read_yaml(j("SYSTEM-MANIFEST.yaml"))
    T["protected objects"] = len(man.get("protected_objects") or [])
    T["system_version"] = str(man["system"]["system_version"])

    r = _read_yaml(j("System", "Runtime", "Task Router.yaml"))
    T["routes"] = sum(len(v) for v in r["modes"].values())

    cov = _read_yaml(j("System", "Documentation", "Diagrams", "coverage.yaml"))
    T["diagrams"] = len(cov["diagrams"])

    # --- DEC-109: version claims (audit GAP-4) -----------------------------
    # `system_version` was the ONLY version this gate ever verified. Every other
    # version in the corpus — capability, agent, workflow, schema, the
    # constitution's own — was prose nothing read, in a product that bumps a
    # dozen of them a week and re-states them in a dozen documents.
    T["component versions"] = _version_sources(j)
    T["_versions_uncovered"] = UNCOVERED_VERSIONS

    # --- DEC-105 additions -------------------------------------------------
    # Unit tests. `def test_*` across the suite, which is exactly what
    # `unittest discover` instantiates — verified equal (488 = 488) at the
    # release that added this key. Counting the definitions instead of running
    # the suite keeps `doc-audit` read-only and sub-second.
    T["unit tests"] = sum(
        len([n for n in ast.walk(ast.parse(_read_text(p)))
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name.startswith("test_")])
        for p in glob.glob(j("System", "Tests", "scripts", "*.py")))

    # Error and warning messages. HOW THIS COUNTS, because a plain grep for
    # `rep.error(`/`rep.warn(` is wrong twice over: `docaudit`, `doccheck` and
    # `docpaths` raise through a `_sev(rep)` severity switch (DEC-083), which no
    # text match sees; and `certify` raises two of its own through sub-reports
    # named `hsub`/`vsub`, which a receiver-name match misses. This walks the AST
    # and counts every `.error(…)`/`.warn(…)` call on ANY receiver plus every
    # `_sev(rep)(…)` call — i.e. every message the user can be shown.
    modules, sites = set(), 0
    for p in glob.glob(j("System", "Scripts", "**", "*.py"), recursive=True):
        n_here = 0
        for node in ast.walk(ast.parse(_read_text(p))):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr in ("error", "warn"):
                n_here += 1
            elif isinstance(f, ast.Call) and isinstance(f.func, ast.Name) and f.func.id == "_sev":
                n_here += 1
        if n_here:
            modules.add(p)
            sites += n_here
    T["messages"] = sites
    T["script modules"] = len(modules)

    # Authority-marked files: the §8.2 index.
    T["authority files"] = len([
        p for p in glob.glob(j("**", "*.md"), recursive=True)
        if re.search(r"^authority:", _read_text(p, errors="replace"), re.M)])

    # Components: reuse doc-check's own enumerator rather than write a second
    # one — two extractors for one number is how the number drifts.
    try:
        from . import doccheck
        T["components"] = len(doccheck._enumerate_components(root))
    except Exception:
        pass

    try:
        from . import links as _links
        T["relationships"] = len(_links.REL_FIELDS)
    except Exception:
        pass

    T["schemas"] = len(glob.glob(j("System", "Schemas", "*.yaml")))
    T["libraries"] = len([p for p in glob.glob(j("System", "Scripts", "lib", "*.py"))
                          if not os.path.basename(p).startswith("__")])
    T["documentation files"] = len(glob.glob(j("System", "Documentation", "**", "*.md"),
                                             recursive=True))
    return T


_DATED_HEADER = re.compile(r"\bv\d+\.\d+(?:\.\d+)?\b|\b20\d\d-\d\d-\d\d\b|\bat first draft\b", re.I)


def _blank_dated_tables(body):
    """Blank the rows of any table whose HEADER names a version or a date.

    "| Then (v1.3.0) | Four days later (v1.14.0) |" is a before/after record, and
    every cell under it was true on the day it was written (constitution §4.8).
    Scoped to the header deliberately: it exempts the comparison tables and
    nothing else, so a live census table stays in the gate."""
    lines = body.splitlines()
    out = list(lines)
    for i, ln in enumerate(lines):
        if not re.match(r"^\s*\|[\s|:\-]+\|\s*$", ln) or i == 0:
            continue                       # not a header separator row
        if not _DATED_HEADER.search(lines[i - 1]):
            continue
        j = i + 1
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            out[j] = ""
            j += 1
        out[i - 1] = ""
    return "\n".join(out)


def scan_text(rel, text, T, rep, counts=True):
    """Check one document's text against the truth table. Returns claims checked.
    Line numbers refer to the original file: exemptions blank lines, never remove them.
    `counts=False` runs the behavioural guard only (dated registers, §4.8)."""
    body = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    body = _blank_dated_tables(body)
    out, in_log = [], False
    for ln in body.splitlines():
        if ln.startswith("## "):
            # An amendment log is the document's own changelog — history, exempt
            # (constitution §4.8), exactly like CHANGELOG.md at file level. Both
            # of the constitution's logs count: `## Amendments` (v2) and
            # `## Amendment log` (v1) are the same kind of record.
            in_log = ln.strip().lower().startswith("## amendment")
        out.append("" if (in_log or ln.lstrip().startswith(">")) else ln)
    body = "\n".join(out)
    checked = 0
    consumed = set()   # a number belongs to the FIRST (most specific) noun that claims it
    for key, patterns in NOUNS.items():
        if key not in T or not counts:
            continue
        for pat in patterns:
            for m in re.finditer(rf"\b{NUM}{_CLOSE}{_GAP}{_SEP}{_CLOSE}{pat}(?![-\w])",
                                 body, re.I):
                val = _n(m.group(1))
                if val is None or m.start() in consumed:
                    continue
                if any(not GAP_TOKEN.match(w.group(0)) for w in _WORD.finditer(m.group(2))):
                    continue        # a narrowing modifier: a subset claim, not a census
                para = body[max(0, m.start() - 400):m.start()].lower()
                if re.search(r"(pmm|other products?|another product|reusing this)", para):
                    continue        # describing a different product's counts
                ctx = body[max(0, m.start() - 30):m.start()].lower()
                after = body[m.end():m.end() + 12].lower()
                if val == 1 and (re.search(r"\b(is|as|in|a|single|each|its own|least)\s*$", ctx)
                                 or after.strip().startswith("per")
                                 or after.strip().startswith(".")):
                    continue        # a rate, a minimum, or a declaration ("One folder.") — not a count of the set
                consumed.add(m.start())
                checked += 1
                ok = (val == T[key])
                if key == "note classes" and val == T[key] + 1:
                    ok = True       # 7 content classes, or 8 counting `component`
                if not ok:
                    line = body[:m.start()].count("\n") + 1
                    _sev(rep)(f'{rel}:{line}: claims "{m.group(0).strip()}" — '
                              f"source says {T[key]}")
    # The atlas writes its counts the other way round — a box labelled
    # "Capabilities (7)" beside a list of seven, while fourteen shipped. Same
    # claim, mirrored notation; without this the artwork can draw a superseded
    # architecture forever and every gate still passes.
    if counts:
        for key, patterns in NOUNS.items():
            if key not in T:
                continue
            for pat in patterns:
                for m in re.finditer(rf"\b{pat}[ ]?\((\d{{1,3}})\)", body, re.I):
                    if not m.group(0).split("(")[0].strip().lower().endswith("s"):
                        continue     # "the CLI-surface diagram (22)" is a diagram's number, not a count
                    checked += 1
                    if int(m.group(1)) != T[key]:
                        line = body[:m.start()].count("\n") + 1
                        _sev(rep)(f'{rel}:{line}: labels "{m.group(0).strip()}" — '
                                  f"source says {T[key]}")

    cur = T.get("system_version")
    if cur:
        # X→Y / "X to Y" are transition RECORDS (what a decision changed), not claims.
        for m in re.finditer(r"system_version[` ]*[:=]?[` ]*(\d+\.\d+\.\d+)"
                             r"(?!\s*(?:→|->|\s+to\s))", body):
            checked += 1
            if m.group(1) != cur:
                line = body[:m.start()].count("\n") + 1
                _sev(rep)(f"{rel}:{line}: claims system_version {m.group(1)} — "
                          f"manifest says {cur}")
    if counts:
        checked += scan_versions(rel, body, T, rep)
    checked += scan_behaviour(rel, body, rep)
    return checked


_SVG_TEXT = re.compile(r"<(text|tspan|title|desc)\b[^>]*>(.*?)</\1>", re.S)
_TAG = re.compile(r"<[^>]*>")


def svg_text(path):
    """The rendered words of a diagram, at their original line and column.

    Everything that is not text content is blanked to spaces rather than
    removed, so a reported line number points at the line a maintainer will
    actually open. Deliberately not an XML parse: the atlas is hand-authored and
    a strict parser turns a stray entity into a crash in a gate that should
    simply report."""
    src = _read_text(path, errors="replace")
    buf = ["\n" if ch == "\n" else " " for ch in src]
    for m in _SVG_TEXT.finditer(src):
        inner = _TAG.sub(lambda t: " " * len(t.group(0)), m.group(2))
        for i, ch in enumerate(inner):
            if ch != "\n":
                buf[m.start(2) + i] = ch
    return "".join(buf)


# A version claim is a CURRENT-STATE assertion. These shapes are not, and are
# skipped:
#   X→Y / "X to Y"  — a transition record (what a release changed). The same rule
#                     the `system_version` check has always used.
#   "Source: … v1.2.3", "shipped in v1.2.3", "as of 1.2.3", "since 1.2.3"
#                   — a dated provenance stamp: it records where a passage CAME
#                     FROM and stays true as the source moves on (§4.8).
#   an amendment log — already blanked, for every claim type, by `scan_text`.
#   the decision register — a dated figure, exempted with its counts (HIST_COUNTS).
_VER_PROVENANCE = re.compile(
    r"(?:source|origin|extracted|derived|taken|shipped|introduced|added|landed|"
    r"as of|since|at the time|written against|built on)\b[^.\n]{0,60}$", re.I)

# FORM A — the catalogue stamp, which is where these claims actually live. The
# constitution gives every capability and agent a section whose heading names it
# and whose first line is its version:
#
#     ### §5.6 `import-vault` — crossing the trust boundary
#     `v0.1.0` · Router: `import-vault` · Tests: fixture 13
#
# Ten of the seventeen such stamps were stale when this check was built, one of
# them by three minor versions, and nothing in the toolchain could see it: the
# count was not a count and the version was not `system_version`, so the corpus's
# single densest concentration of version claims had no gate at all (GAP-4).
_SECTION = re.compile(r"^#{2,4}\s*(?:§[\d.]+\s*)?`?([a-z][a-z0-9-]{2,})`?\b", re.M)
_STAMP = re.compile(r"^`?v(\d+\.\d+\.\d+)`?(?![\d.])")

# FORM B — inline: "`safe-write` 0.6.0", "`steward` v1.2.0". Separators are
# deliberately only whitespace and the catalogue's middot: `method-kit@0.2.0`
# names a repository release, not this vault's capability, and an `@` that read
# as a separator would make the gate wrong about a different product.
_INLINE_SEP = r"[ \t·]{0,3}"


def scan_versions(rel, body, T, rep):
    """Does every version this document states about a local component match the
    version that component declares? (DEC-109, audit GAP-4.)

    The complement of the `system_version` check, which was this gate's ONLY
    version key while the corpus carried dozens of others — capability, agent,
    workflow, schema and the constitution's own.
    """
    sources = T.get("component versions") or {}
    if not sources:
        return 0
    checked = 0
    lines = body.splitlines()

    # Form A
    for m in _SECTION.finditer(body):
        name = m.group(1)
        if name not in sources:
            continue
        first = body[:m.start()].count("\n")
        for j in range(first + 1, min(first + 4, len(lines))):
            stamp = _STAMP.match(lines[j].strip())
            if not stamp:
                continue
            checked += 1
            if stamp.group(1) != sources[name]:
                _sev(rep)(f"{rel}:{j + 1}: the `{name}` section is stamped "
                          f"v{stamp.group(1)} — the component declares "
                          f"{sources[name]}")
            break

    # Form B
    for name, actual in sources.items():
        pat = (rf"`{re.escape(name)}`{_INLINE_SEP}(?:capability|agent|workflow|schema)?"
               rf"{_INLINE_SEP}(?:at{_INLINE_SEP}|version{_INLINE_SEP})?v?(\d+\.\d+\.\d+)"
               rf"(?![\d.])(?!\s*(?:→|->|\s+to\s))")
        for m in re.finditer(pat, body, re.I):
            before = body[body.rfind("\n", 0, m.start()) + 1:m.start()]
            if _VER_PROVENANCE.search(before):
                continue                      # a dated stamp, not a claim about now
            checked += 1
            if m.group(1) != actual:
                line = body[:m.start()].count("\n") + 1
                _sev(rep)(f"{rel}:{line}: says `{name}` is {m.group(1)} — "
                          f"the component declares {actual}")
    return checked


def scan_behaviour(rel, body, rep):
    """The claim gate for prose that describes BEHAVIOUR rather than counts.

    Nothing else in the toolchain answers "does this sentence still describe what
    the product does?" — `doc-check` proves a diagram exists, is mapped, is
    described and is listed, never that it is *true*. This does not solve that
    problem in general; it closes the one class the estate has actually been
    burned by, by naming the phrase a ratified ruling retired and failing on it
    wherever it survives. Cheap, exact, and it grows one line per ruling."""
    checked = 0
    for pat, why in BANNED_BEHAVIOUR:
        for m in re.finditer(pat, body, re.I):
            checked += 1
            window = body[body.rfind("\n", 0, m.start()) + 1:m.start()]
            if _NEGATED.search(window):
                continue        # "never drains the Inbox" is the doctrine, not a breach
            line = body[:m.start()].count("\n") + 1
            _sev(rep)(f'{rel}:{line}: says "{m.group(0)}" — {why}')
    return checked



_STRICT = True   # set per-run from instance_role; strict by default (test scaffolds, master)

def _sev(rep):
    return rep.error if _STRICT else rep.warn

def _master(root):
    """Doc gates police the PRODUCT; on an instance they advise (DEC-083).
    Master = error; instance = warning — same scoping doctrine as DEC-082."""
    import yaml as _y, os as _o
    try:
        with open(_o.path.join(root, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as stream:
            man = _y.safe_load(stream) or {}
    except Exception:
        return True
    return str(((man.get("system") or {}).get("instance_role") or "generic-master")).strip() == "generic-master"

def run(root, args, rep):
    global _STRICT
    _STRICT = _master(root)
    if yaml is None:
        rep.error("PyYAML required for doc-audit")
        return rep
    try:
        T = truth(root)
    except (OSError, KeyError, TypeError):
        # Not a full product tree (test scaffolds, partial vaults): no source of
        # truth to compare against — skip gracefully, same as the router check.
        rep.info["status"] = "skipped — no full source-of-truth tree at this root"
        return rep
    docs = sorted(set(glob.glob(os.path.join(root, "System", "**", "*.md"), recursive=True)
                      + glob.glob(os.path.join(root, "*.md"))))
    checked = 0
    for path in docs:
        if any(h in path for h in HIST):
            continue
        rel = os.path.relpath(path, root)
        text = _read_text(path, errors="replace")
        checked += scan_text(rel, text, T, rep,
                             counts=not any(h in path for h in HIST_COUNTS))

    # DEC-105: markdown was never the whole prose surface. The always-loaded
    # `Task Router.yaml`, the diagram atlas's `diagram-metadata.yaml` and the
    # atlas artwork itself all carry sentences a reader treats as documentation,
    # and none of them was scanned. Six of the highest-severity findings of the
    # 2026-07-27 audit lived in exactly these three file types.
    yamls = sorted(set(glob.glob(os.path.join(root, "System", "**", "*.yaml"), recursive=True)
                       + glob.glob(os.path.join(root, "*.yaml"))))
    y_checked = 0
    for path in yamls:
        if any(h in path for h in HIST):
            continue
        rel = os.path.relpath(path, root)
        text = _read_text(path, errors="replace")
        y_checked += scan_text(rel, text, T, rep)

    s_checked, svgs = 0, sorted(glob.glob(
        os.path.join(root, "System", "**", "*.svg"), recursive=True))
    for path in svgs:
        rel = os.path.relpath(path, root)
        s_checked += scan_text(rel, svg_text(path), T, rep)

    rep.info["claims_checked"] = checked + y_checked + s_checked
    rep.info["yaml_claims_checked"] = y_checked
    rep.info["svg_claims_checked"] = s_checked
    rep.info["truth_keys"] = len(T)
    rep.info["version_sources"] = (
        f"{len(set((T.get('component versions') or {}).values()))} distinct versions across "
        f"{len(T.get('component versions') or {})} named sources (capabilities, agents, "
        f"workflows, schemas, the constitution, vault_profile_version)")
    # Named, not implied: this gate does not verify every version in the corpus,
    # and saying which ones it cannot reach is the difference between an honest
    # gap and a false assurance.
    for i, why in enumerate(T.get("_versions_uncovered") or (), start=1):
        rep.info[f"versions_not_covered_{i}"] = why
    return rep
