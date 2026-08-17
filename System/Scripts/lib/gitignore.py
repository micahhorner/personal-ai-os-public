"""Conservative .gitignore coverage evaluation (DEC-092 sync boundary).

`validate` cross-checks `sync: local-only` records against the vault-root
`.gitignore` in both directions. This matcher deliberately answers a THREE-way
question — COVERED / NOT_COVERED / UNVERIFIABLE — because the spec's fence is
absolute: when unsure whether a rule covers a file, say so, **never claim
"covered"**. A false "covered" converts an unbacked privacy promise into a
green checkmark, which is the exact failure the sync field exists to kill.

Modeled confidently (the constructs this product's own .gitignore and the
overwhelming majority of real ones use):
  - comments / blank lines
  - `name` (no slash): matches that basename anywhere, file or directory
  - `dir/` (trailing slash): a directory anywhere by that name; everything under it
  - patterns containing an interior `/`: anchored to the vault root (gitignore rule)
  - leading `/`: anchored to the vault root
  - `*` and `?` within a segment (fnmatch, never crossing `/`)
  - leading `**/` and trailing `/**`

Escalated to UNVERIFIABLE rather than guessed:
  - negation rules (`!pattern`) that might re-include the path
  - character classes (`[...]`), escapes (`\\`), and interior `**` segments
    on a rule that otherwise might match

Only the vault-root `.gitignore` is read. Nested .gitignore files, global
excludes, and `info/exclude` are out of model — a rule that lives elsewhere
never yields COVERED, which errs closed, as required.
"""
from __future__ import annotations

import fnmatch
import os

COVERED = "covered"
NOT_COVERED = "not-covered"
UNVERIFIABLE = "unverifiable"

_UNSURE_TOKENS = ("[", "\\")


class _Rule:
    __slots__ = ("pattern", "negated", "dir_only", "anchored", "unsure")

    def __init__(self, raw: str):
        line = raw.rstrip("\n")
        self.negated = line.startswith("!")
        if self.negated:
            line = line[1:]
        # trailing spaces are ignored by git unless escaped; conservative strip
        line = line.rstrip()
        self.dir_only = line.endswith("/")
        line = line.rstrip("/")
        self.anchored = line.startswith("/") or "/" in line.lstrip("/")
        line = line.lstrip("/")
        # interior ** detection: any ** not at the very start (**/) or very
        # end (/**) of the pattern is out of model
        core = line
        if core.startswith("**/"):
            core = core[3:]
        if core.endswith("/**"):
            core = core[:-3]
        self.unsure = any(t in line for t in _UNSURE_TOKENS) or "**" in core
        # `**/a/b` (a multi-segment pattern floating at any depth) is out of
        # model — matching it confidently needs full gitignore semantics
        if line.startswith("**/") and "/" in core:
            self.unsure = True
        self.pattern = line

    def _segments_match(self, pat: str, path: str) -> bool:
        """fnmatch per path-segment; `*`/`?` never cross a slash."""
        ps, xs = pat.split("/"), path.split("/")
        if len(ps) != len(xs):
            return False
        return all(fnmatch.fnmatchcase(x, p) for p, x in zip(ps, xs))

    def matches(self, relpath: str) -> bool:
        """Does this rule apply to relpath (a posix-style vault-relative FILE path)?
        For unsure rules the answer is a 'maybe' the caller must not trust as
        a definite match — callers check `.unsure` first."""
        pat = self.pattern
        anchored = self.anchored
        if pat.startswith("**/"):
            pat = pat[3:]
            anchored = False
        suffix_all = pat.endswith("/**")
        if suffix_all:
            pat = pat[:-3]
        parts = relpath.split("/")

        def named(prefix_parts):
            """Does pat name the file/dir at this prefix?"""
            if anchored or "/" in pat:
                return self._segments_match(pat, "/".join(prefix_parts))
            return fnmatch.fnmatchcase(prefix_parts[-1], pat)

        # the rule may name the file itself or any ancestor directory
        # (a matched directory covers everything under it)
        for i in range(1, len(parts) + 1):
            is_dir = i < len(parts)
            if suffix_all:
                # `X/**` covers what is UNDER X, never X itself
                if is_dir and named(parts[:i]):
                    return True
                continue
            if self.dir_only and not is_dir:
                continue
            if named(parts[:i]):
                return True
        return False


class GitignoreMatcher:
    def __init__(self, text: str | None):
        self.exists = text is not None
        self.rules: list[_Rule] = []
        for raw in (text or "").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            self.rules.append(_Rule(raw.strip()))

    @classmethod
    def load(cls, root: str) -> "GitignoreMatcher":
        p = os.path.join(root, ".gitignore")
        if not os.path.exists(p):
            return cls(None)
        try:
            with open(p, encoding="utf-8", errors="replace") as stream:
                return cls(stream.read())
        except OSError:
            return cls(None)

    def coverage(self, relpath: str) -> str:
        """COVERED / NOT_COVERED / UNVERIFIABLE for a vault-relative file path.
        Never returns COVERED unless a confidently-modeled positive rule matches
        and no negation could plausibly re-include the file."""
        rel = relpath.replace(os.sep, "/").replace("\\", "/")
        if not self.exists:
            return NOT_COVERED
        hit_sure = hit_unsure = renegade = False
        for r in self.rules:
            if not r.matches(rel):
                continue
            if r.negated:
                # any matching negation, sure or not, poisons certainty:
                # git applies rules in order with last-match-wins semantics
                # we do not fully model — say "unverifiable", never "covered"
                renegade = True
            elif r.unsure:
                hit_unsure = True
            else:
                hit_sure = True
        if hit_sure and not renegade:
            return COVERED
        if hit_sure or hit_unsure:
            return UNVERIFIABLE
        return NOT_COVERED
