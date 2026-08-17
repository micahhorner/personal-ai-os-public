"""vault.measure — deterministic measurement of a multi-voice transcript.

`ingest-and-connect` step 3a says: measure the voice split BEFORE extracting,
read the human's turns in isolation where his share is small, and check where a
term first appears before naming a note after it. All three are measurements,
and until now all three were hand-performed — written three times in throwaway
Python on 2026-07-14, which the Runtime Kernel forbids ("never hand-perform what
a script does"). That harvest found the assistant outwrote the human 8:1 and that
11 of 18 note titles were its coinages: facts no rule prevents and no model
reliably notices, because they must be COMPUTED. This is that computation.

Read-only by default. Content never reaches stdout — see "Privacy" below.

Scope (spec §4): the transcript job only. The note-check and register-baseline
halves were explicitly demoted and are not implemented here.

Privacy — why this command can measure what its caller may not read
------------------------------------------------------------------
A transcript under `Local Only/` is `ai_use: local-only` (DEC-065): invisible to
a hosted runtime, fail-closed. That is exactly where the highest-value
transcripts live, so the naive design ("just read it") is not available to the
runtime that needs the answer.

This script is not a hosted runtime. It runs locally, and it resolves the
tension by separating MEASUREMENT from CONTENT:

  - Measurements (turn counts, word counts, the split, a term's first-speaker
    and line number) go to stdout. They are facts ABOUT the text, not the text.
    The terms in the origin table are the caller's own query echoed back, not
    text discovered in the source.
  - Content (the human's turns, extracted for isolated reading) NEVER goes to
    stdout. It is written to a file with --extract, for a human or a local
    runtime to read, and the report returns only the path and a count.

So no transcript text crosses into a hosted context by running this command.
The one judgment left to the owner is whether the derived STATISTICS of a
local-only source may be shown to a hosted runtime at all; the conservative
reading of Kernel §1.2 ("invisible to you entirely") would say no. This build
prints them and labels the source, because a split the runtime cannot see is a
split it will hand-perform instead. Flagged for ruling; see the Phase E report.
"""
from __future__ import annotations
import os
import re

import yaml

from lib.report import Report
from lib.protectedwrites import ProtectedTargetError, refuse_protected_targets
from lib.safepaths import SafePathError, atomic_create_files, safe_relative_path

# Voice markers, by export dialect. A transcript declares its voices by heading;
# these are the forms seen in the wild. Matched at line start, case-insensitively.
# The value is the canonical voice name this script reports.
#
# GENERIC ONLY, and that is a rule rather than a preference (DEC-109). This list
# carried the product owner's given name as a `human` alternative from the day it
# was written — a personal identifier compiled into a shipped regex, on a master
# whose manifest declares `instance_role: generic-master` with "personal data is
# PROHIBITED here". DEC-106 found it and deliberately did NOT delete it, because
# deleting it is not a neutral act: a transcript whose headings carry the owner's
# own name would stop being attributed, and the measurement that
# `ingest-and-connect` step 3a depends on would silently change. The ruling was
# to make it CONFIGURABLE, which is what these two halves now are: a generic
# shipped vocabulary here, and the user's own speaker labels in the file below.
VOICE_PATTERNS: list[tuple[str, str]] = [
    (r"^##+\s*you\s*:?\s*$", "human"),
    (r"^##+\s*(human|user|me)\s*:?\s*$", "human"),
    (r"^##+\s*(chatgpt|assistant|claude|gpt-?\d*|ai)\s*:?\s*$", "assistant"),
    (r"^\*\*(you|human|user|me)\*\*\s*:?\s*$", "human"),
    (r"^\*\*(chatgpt|assistant|claude|ai)\*\*\s*:?\s*$", "assistant"),
]

# User-owned configuration, the `80 User/` pattern this estate already uses for
# `vocab-guard.yaml`, `voice.md`, `authoring.md` and `handoff.md`: loaded IF IT
# EXISTS, absent it the shipped defaults stand and nothing breaks.
#
#     # 80 User/transcript-voices.yaml
#     human: [alex, aj]           # extra speaker labels that mean YOU
#     assistant: [copilot]        # extra labels that mean the AI
#
# Deliberately NOT named `voice.md`: that file is how your outward writing should
# sound. This one is who is who in a transcript — a different question, and one
# file answering both is how a hook stops being loaded for either.
CONFIG_REL = os.path.join("80 User", "transcript-voices.yaml")
_ALIAS_OK = re.compile(r"^[0-9A-Za-z][0-9A-Za-z '’._-]{0,63}$")


def load_voice_aliases(root) -> tuple[dict[str, list[str]], str]:
    """The user's own speaker labels, and one line saying where they came from.

    Never raises: a malformed hook must not take down a measurement. A bad file
    is reported (in `voice_markers`, which the report always prints) rather than
    swallowed — a config silently ignored is worse than no config, because the
    caller reads a split computed with markers they think they replaced.
    """
    path = os.path.join(root, CONFIG_REL)
    if not os.path.exists(path):
        return {}, f"shipped defaults ({CONFIG_REL} not present)"
    try:
        with open(path, encoding="utf-8") as stream:
            cfg = yaml.safe_load(stream) or {}
        if not isinstance(cfg, dict):
            raise ValueError("top level is not a mapping of voice -> [labels]")
    except Exception as e:                       # noqa: BLE001 — report, never crash
        return {}, f"shipped defaults — {CONFIG_REL} IGNORED, not usable ({e})"
    out, bad = {}, []
    for voice in ("human", "assistant"):
        vals = cfg.get(voice) or []
        if isinstance(vals, str):
            vals = [vals]
        keep = [str(v).strip() for v in vals if _ALIAS_OK.match(str(v).strip())]
        bad += [str(v) for v in vals if str(v).strip() not in keep]
        if keep:
            out[voice] = keep
    note = f"shipped defaults + {CONFIG_REL} (" + ", ".join(
        f"{v}: {', '.join(a)}" for v, a in sorted(out.items())) + ")" if out else \
        f"shipped defaults ({CONFIG_REL} present but adds no labels)"
    if bad:
        note += f" — {len(bad)} label(s) rejected as unusable: {', '.join(bad[:3])}"
    return out, note


def compile_markers(root=None) -> list[tuple[re.Pattern, str]]:
    """The shipped patterns, plus one pattern per configured alias."""
    compiled = [(re.compile(p, re.IGNORECASE), v) for p, v in VOICE_PATTERNS]
    aliases = load_voice_aliases(root)[0] if root else {}
    for voice, labels in aliases.items():
        alt = "|".join(re.escape(a) for a in labels)
        compiled.append((re.compile(rf"^##+\s*(?:{alt})\s*:?\s*$", re.IGNORECASE), voice))
        compiled.append((re.compile(rf"^\*\*(?:{alt})\*\*\s*:?\s*$", re.IGNORECASE), voice))
    return compiled


_COMPILED = compile_markers()

WORD_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z'’\-]*")


def voice_of(line: str, markers=None) -> str | None:
    """The voice a line declares, or None if it is not a turn marker.

    `markers` is what `compile_markers(root)` returned. It defaults to the
    shipped-only set so the helper stays usable standalone; `run` always passes
    the instance's, so a configured alias is honoured everywhere a marker is
    matched — including the annotation split, which is the one place a missed
    marker silently reclassifies the whole file.
    """
    for rx, voice in (markers or _COMPILED):
        if rx.match(line.strip()):
            return voice
    return None


class Turn:
    """One speaker's turn: their own lines, and the third-voice lines inside it."""

    def __init__(self, voice: str, start_line: int):
        self.voice = voice
        self.start_line = start_line    # line number within the transcript body
        self.own: list[str] = []        # the speaker's own words
        self.quoted: list[str] = []     # pasted/quoted material — a third voice

    @property
    def words(self) -> int:
        return sum(len(WORD_RE.findall(l)) for l in self.own)

    @property
    def quoted_words(self) -> int:
        return sum(len(WORD_RE.findall(l)) for l in self.quoted)

    @property
    def substantive(self) -> bool:
        """A turn that contributes words of the speaker's own. An empty marker,
        or a turn that is nothing but pasted material, is not the speaker
        speaking — it is a container."""
        return self.words > 0


def split_annotation(text: str, markers=None) -> tuple[str, str]:
    """Separate the vault's own annotation block from the verbatim transcript.

    An imported source carries a header the VAULT wrote about the source (origin,
    import date, format, integrity), then a `---` divider, then the transcript
    "byte-for-byte below the divider". That header is the vault's commentary — it
    is nobody's turn, and it discusses the transcript using the transcript's own
    vocabulary. Scanning it is how a term-origin check reports that the assistant's
    coinage "first appeared" in the annotation that was written to describe it:
    a false clean bill of health for the exact term you are trying to catch.

    The transcript begins after the last `---` divider that precedes the first
    voice marker. With no divider or no marker, everything is transcript.

    Returns (annotation, transcript). Line numbers reported to the user are
    relative to the transcript, matching the "body line N" convention used in
    the source notes.
    """
    lines = text.splitlines()
    first_turn = next((i for i, l in enumerate(lines) if voice_of(l, markers) is not None), None)
    if first_turn is None:
        return "", text
    divider = None
    for i in range(first_turn - 1, -1, -1):
        if lines[i].strip() == "---":
            divider = i
            break
    if divider is None:
        return "", text
    return "\n".join(lines[:divider]), "\n".join(lines[divider + 1:])


def parse(text: str, markers=None) -> list[Turn]:
    """Split a transcript into turns, separating each speaker's own words from
    third-voice material pasted inside their turn.

    THE THIRD-VOICE TRAP (the reason this is a script and not a glance): a
    pasted article, a quoted email, or a forwarded message sits INSIDE a human
    turn. Counting it as his inflates his apparent share and puts another
    person's thesis in his mouth. Blockquoted lines are that third voice and are
    counted separately, credited to no speaker — in either direction: an
    assistant turn quoting the human back at him is not the assistant's words
    either.

    Fenced blocks are NOT third voice. A ``` block is the speaker's own output,
    and a ::: block is the export's own wrapper around the speaker's prose (the
    ChatGPT export wraps its drafts in `:::writing`). Excluding them cost the
    assistant ~7,400 of its own words on the first run of this script. What a
    fence does do is suppress voice markers: a `## You` inside a fence is quoted
    text, not a real turn, so fences are tracked before markers are matched.
    """
    turns: list[Turn] = []
    current: Turn | None = None
    fence: str | None = None            # the fence token we are inside, if any

    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()

        # --- fence tracking (must precede marker matching) ---
        if fence is None:
            if stripped.startswith("```"):
                fence = "```"
            elif stripped.startswith(":::") and len(stripped) > 3:
                fence = ":::"
            if fence is not None:
                continue        # the delimiter is markup, not anyone's words
        else:
            if (fence == "```" and stripped.startswith("```")) or \
               (fence == ":::" and stripped in (":::", ":::end")):
                fence = None
                continue        # ditto the closing delimiter
            if current is not None:
                current.own.append(line)
            continue

        # --- turn markers ---
        v = voice_of(line, markers)
        if v is not None:
            current = Turn(v, i)
            turns.append(current)
            continue

        if current is None:
            continue

        # --- blockquote = quoted third voice ---
        if stripped.startswith(">"):
            current.quoted.append(line)
        else:
            current.own.append(line)

    return turns


def strip_frontmatter(text: str) -> tuple[str, int]:
    """Return the body and the number of lines removed. Frontmatter is metadata,
    never anyone's speech."""
    if not text.startswith("---"):
        return text, 0
    end = text.find("\n---", 3)
    if end == -1:
        return text, 0
    head = text[: end + 4]
    return text[end + 4:], head.count("\n") + 1


def load_profile(root) -> dict:
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as stream:
        m = yaml.safe_load(stream)
    with open(os.path.join(root, m["runtime"]["active_profile"]), encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def term_origin(text: str, terms: list[str], turns: list[Turn], offset: int) -> list[str]:
    """For each term: which voice said it FIRST, and on what line.

    The check that caught 11 of 18 titles built on the assistant's coinages. A
    term first spoken by the assistant is not the human's vocabulary and must
    not become canon vocabulary without his explicit adoption.

    Returns measurements only — term, voice, line — never surrounding text.
    """
    # line -> voice, from the turn each line falls in
    bounds: list[tuple[int, int, str]] = []
    for idx, t in enumerate(turns):
        end = turns[idx + 1].start_line - 1 if idx + 1 < len(turns) else 10 ** 9
        bounds.append((t.start_line, end, t.voice))

    def voice_at(line_no: int) -> str:
        for start, end, v in bounds:
            if start <= line_no <= end:
                return v
        return "preamble"

    rows = []
    lines = text.splitlines()
    for term in terms:
        rx = re.compile(re.escape(term), re.IGNORECASE)
        found = None
        for i, line in enumerate(lines, start=1):
            if rx.search(line):
                found = i
                break
        if found is None:
            rows.append(f"{term} — not found")
        else:
            rows.append(f"{term} — first said by {voice_at(found)} (body line {found - offset})")
    return rows


def run(root, args, rep: Report):
    path = getattr(args, "target", None) or getattr(args, "transcript", None)
    if not path:
        rep.error("usage: aios measure <transcript.md> [--terms \"a,b\"] [--extract out.md]")
        return rep
    full = path if os.path.isabs(path) else os.path.join(root, path)
    if not os.path.exists(full):
        rep.error(f"transcript not found: {path}")
        return rep

    with open(full, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    body, _fm_lines = strip_frontmatter(text)
    markers = compile_markers(root)
    _aliases, marker_note = load_voice_aliases(root)
    annotation, transcript = split_annotation(body, markers)
    turns = parse(transcript, markers)

    if not turns:
        rep.info["voice_markers"] = marker_note
        rep.error("no voice markers found — this file has no turns to attribute. "
                  "Recognised: '## You' / '## ChatGPT' / '## Human' / '## Assistant' "
                  "(and **bold** equivalents). A single-voice source needs no split.")
        return rep

    relpath = os.path.relpath(full, root)
    profile = load_profile(root)
    hosted = bool(profile.get("hosted", True))
    local_only = any(seg.strip().lower() == "local only"
                     for seg in relpath.replace("\\", "/").split("/"))

    voices = sorted({t.voice for t in turns})
    totals = {v: sum(t.words for t in turns if t.voice == v) for v in voices}
    subst = {v: sum(1 for t in turns if t.voice == v and t.substantive) for v in voices}
    raw = {v: sum(1 for t in turns if t.voice == v) for v in voices}
    quoted = sum(t.quoted_words for t in turns)
    grand = sum(totals.values())

    rep.info["source"] = relpath
    # Always printed, never only on failure: the split is only as trustworthy as
    # the markers it was computed with, so the caller is told which set ran.
    rep.info["voice_markers"] = marker_note
    rep.info["voices"] = ", ".join(voices)
    for v in voices:
        rep.info[f"turns_{v}"] = f"{subst[v]} substantive of {raw[v]} marked"
        pct = round(100 * totals[v] / grand) if grand else 0
        rep.info[f"words_{v}"] = f"{totals[v]:,} ({pct}%)"
    if quoted:
        rep.info["words_quoted_third_voice"] = (
            f"{quoted:,} — blockquoted material inside turns, credited to NO speaker")
    if annotation.strip():
        rep.info["annotation_excluded"] = (
            f"{len(WORD_RE.findall(annotation)):,} words above the verbatim divider — "
            f"the vault's own note about this source, excluded from every count")

    # The line ingest-and-connect 3a asks to be recorded in the source note's
    # body metadata block, formatted exactly as the capability specifies.
    if "human" in totals and "assistant" in totals:
        hp = round(100 * totals["human"] / grand) if grand else 0
        rep.info["source_note_line"] = (
            f"- words: human {totals['human']:,} · assistant {totals['assistant']:,} "
            f"(human {hp}%)")
        if hp < 35:
            rep.warn(f"human share is {hp}% — any whole-transcript reading returns the "
                     f"assistant's framing. Step 3a: read his turns in ISOLATION first "
                     f"(--extract) and build the claim inventory from that alone.")

    terms = [t.strip() for t in (getattr(args, "terms", None) or "").split(",") if t.strip()]
    if terms:
        rep.info["term_origin"] = term_origin(transcript, terms, turns, offset=0)

    out = getattr(args, "extract", None)
    if out:
        from lib.vaultpaths import ai_writes_enabled
        if not ai_writes_enabled(root):
            rep.error("kill switch is off (runtime.ai_writes_enabled: false) — "
                      "refusing to write the extraction. Measurement above still stands.")
            return rep
        human_turns = [t for t in turns if t.voice == "human" and t.substantive]
        content = [f"# Human turns in isolation — {os.path.basename(relpath)}\n\n",
                   f"> Extracted by `aios measure` from `{relpath}`.\n"
                   f"> {len(human_turns)} substantive turns, "
                   f"{totals.get('human', 0):,} words.\n"
                   f"> Quoted/pasted material inside his turns is EXCLUDED — "
                   f"it is not his voice.\n"
                   f"> Read this alone and build the claim inventory before opening "
                   f"a single assistant turn (ingest-and-connect 3a).\n\n---\n\n"]
        for t in human_turns:
            content.append(f"## line {t.start_line}\n\n")
            content.append("\n".join(l for l in t.own).strip() + "\n\n")
        try:
            output_rel = safe_relative_path(str(out), "measure --extract path")
            refuse_protected_targets(root, (output_rel,), "measure --extract")
            atomic_create_files(root, {output_rel: "".join(content).encode("utf-8")})
        except (SafePathError, ProtectedTargetError) as exc:
            rep.error(f"extraction output refused: {exc}")
            return rep
        rep.info["extract_written"] = f"{output_rel} ({len(human_turns)} turns)"
        if local_only and hosted:
            rep.info["extract_notice"] = (
                "source is Local Only (DEC-065) — the extraction holds content a hosted "
                "runtime may not read. It is on disk for the human or a local runtime. "
                "Do not open it from a hosted session; keep it under a Local Only path.")

    if local_only and hosted:
        rep.info["privacy"] = (
            "Local Only source (DEC-065): measurements shown, content withheld. "
            "No transcript text was returned by this command.")
    return rep
