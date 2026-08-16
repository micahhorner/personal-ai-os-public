"""Open Knowledge Format (OKF) — the mapping between AI OS frontmatter and
Google's OKF, used by `aios okf-export`, `aios okf-import`, and `aios okf-check`.

**Two spec versions are supported and the version is always explicit.** OKF v0.2
shipped 2026-07-24 (`knowledge-catalog` commit 780fe9d3, "okf: migrate format and
tooling to Open Knowledge Format v0.2"); v0.1 shipped 2026-06-12. This module was
re-verified against the live `okf/SPEC.md` (Apache-2.0) and Google's own migrated
sample bundles on 2026-07-26. The blog post is a pointer; the repo is the source.

## What v0.2 changed (SPEC §13, read from the spec, not from a summary)

**Breaking — two renames, both with a sanctioned fallback:**

- `timestamp` is superseded by `generated: {by, at}` (§5.2). "Consumers MAY fall
  back to a legacy `timestamp` when `generated` is absent."
- The body `# Citations` list is superseded by the `sources` frontmatter field
  (§5.1). Consumers MAY still parse the legacy list.

**Additive — new optional families (§13.2):**

- `sources`: entries of `{resource (REQUIRED in an entry), id, title, author,
  usage_count, last_modified}`, with a `usage_window: {from, to}` sibling framing
  every `usage_count`. Credibility is *inferred* from these signals; OKF stores no
  score (§5.1).
- `generated: {by (REQUIRED), at}` and `verified` (a list of `{by, at}` events; a
  bare mapping MUST be read as a one-element list).
- `status: draft | stable | deprecated` (absent ⇒ `stable`) and `stale_after`, an
  absolute `YYYY-MM-DD` date (§5.4, §5.5).
- `type: Attested Computation` with `runtime` (REQUIRED for that type),
  `parameters`, `computation`, `executor`, `attester` (§10).
- The actor convention (§7): `<producer>/<version>`, `human:<id>`, `process:<id>`.

**Conformance did not change at all.** v0.2 §11 carries the same three rules as
v0.1 §9, word for word: parseable YAML frontmatter on every non-reserved `.md`; a
non-empty `type` in every block; and every reserved filename following the
structure of the index and log sections (renumbered §6/§7 → §8/§9). v0.2 adds
consumer *obligations* around the new families — a bare `verified` mapping MUST be
read as a one-element list, and a concept MUST NOT be rejected for missing an
optional family — but no new requirement on a bundle. Extra keys remain explicitly
permitted. **A conformant v0.1 bundle is therefore a conformant v0.2 bundle** —
the renames retire fields, they do not forbid them — which is why one code path
serves both here, with the version stated rather than implied.

(The first reading of §11 for this build had two rules, not three: rule 3 fell in
a gap between two chunked reads of the spec file, and the missing rule was then
written up as "v0.2 relaxed conformance". The pre-build adversary pass caught it
against the source. It is recorded here because the same slip in the other
direction — a claim resting on a rule that was never read — is the failure this
whole module is being revised to avoid.)

## The AI OS <-> OKF field mapping

| OKF v0.2      | AI OS                      | Notes                                     |
|---------------|----------------------------|-------------------------------------------|
| `type`        | `type`                     | verbatim; OKF types are free strings      |
| `title`       | H1 heading, else filename  | AI OS has no `title` field                |
| `description` | `summary`                  | same job, different key                   |
| `tags`        | `tags`                     | verbatim                                  |
| `resource`    | `original_location`        | sources only; absent for abstract concepts|
| `status`      | `status`, mapped           | six AI OS states -> OKF's three (below)   |
| `stale_after` | `review_due`               | "when this note should be re-verified"    |
| `sources`     | `sources` (an id-list)     | **remapped**, not passed through (below)  |
| `generated`   | — (`updated` supplies `at`)| only with an operator-supplied actor      |
| `verified`    | —                          | **never emitted** (below)                 |
| `timestamp`   | `updated`                  | v0.1 only; the §13.1 legacy fallback      |

Everything else (`id`, `confidence`, `verification`, `classification`, `domain`,
`created`, `updated`, `review_due`…) rides as extra top-level keys, which the spec
permits and asks consumers to preserve — that is what makes the round trip
lossless without converting anything.

### Two v0.2 collisions this module exists to handle

`sources` and `status` are AI OS field names *and* now OKF field names, with
different shapes and different vocabularies. Passing the AI OS value straight
through (correct under v0.1, where both were unknown keys) would emit a malformed
v0.2 `sources` list and an out-of-vocabulary v0.2 `status`. So under v0.2:

- `status` is **mapped** to OKF's three states and the AI OS value rides as
  `x_aios_status`, so nothing is lost and neither field lies.
- `sources` is **rebuilt** as OKF entries, and only for sources that are in the
  bundle, where `resource` can be a real bundle-relative path a consumer can
  follow. A reference to a record outside the bundle is not an OKF source — §5.1
  wants either a followable artifact or a population descriptor, and a dangling
  vault id is neither — so the AI OS id-list rides intact under `x_aios_sources`,
  where it is plainly an AI OS field.

Both of these are field-name collisions rather than mapping problems, and the same
two names are why `okf-check` reports v0.2 advisories against a vault's own
folders: read raw, `status: active` and `sources: [note-a]` are AI OS's fields
wearing OKF's names. Conformance is unaffected (§11 rejects nothing for an
optional family); the export path is where the two vocabularies are separated.

### What this module deliberately does not emit

`verified` records *who confirmed this, and when*. AI OS records a verification
**grade** (`verified | corroborated | reported | inferred | unverified`) with no
actor and no date — a different and, on this axis, weaker fact. Synthesizing
`{by, at}` from it would fabricate both halves of a trust signal, so the grade
rides under its own name and `verified` is left absent, which §5.3 defines as
"unverified" and §11 forbids rejecting a bundle for.

Likewise `generated.by` is REQUIRED inside `generated`, and AI OS does not record
who authored a note. So `generated` is emitted only when the operator supplies the
actor (`--author`); otherwise the concept carries the legacy `timestamp` that
§13.1 sanctions consumers to fall back to. The `Attested Computation` family
(§10) is not emitted at all: AI OS has no attestation machinery, and inventing one
to look conformant is the exact failure this module is written to avoid.

**Why `--author` exists and `--verified-by` deliberately does not.** They look
symmetrical and are not. `generated.by` names *who wrote the content being
exported* — a fact the operator running the export is in a position to assert, and
the export is their act. `verified` records that *a confirmation event happened*,
at a stated time. The vault holds no record that any such event ever occurred, so
a flag would not be naming an actor for a known event; it would be manufacturing
the event. The honest cost is stated rather than hidden: every concept AI OS
exports lands in §5.3's lowest trust tier, **unverified**, including its
best-verified canon, and the grade that canon actually carries rides as a
`verification` key no OKF consumer is obliged to read. That is a real gap in what
this vault records — not a gap in what it is willing to claim.
"""
from __future__ import annotations

import os
import re
import unicodedata

from lib.frontmatter import BUNDLE_MARKER   # noqa: F401 — one definition, re-exported for callers

# Every spec version this surface can emit and check against, newest first.
OKF_VERSIONS = ("0.2", "0.1")
OKF_VERSION = "0.2"                 # the default: the current published spec
OKF_SPEC_URL = "https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md"
OKF_SPEC_VERIFIED = "2026-07-26"    # the date the live SPEC.md above was read end to end

# Reserved OKF filenames — defined meanings, exempt from the concept-document rules.
RESERVED = {"index.md", "log.md"}

# OKF's own field names, in the spec's stated order, per version. Used to emit
# frontmatter with the standard fields first and the AI OS superset after.
OKF_FIELDS = {
    "0.1": ["type", "title", "description", "resource", "tags", "timestamp"],
    "0.2": ["type", "title", "description", "resource", "tags",
            # the lifecycle, trust, and provenance families (§5)
            "status", "generated", "verified", "stale_after", "sources", "usage_window",
            # the Attested Computation contract (§10) — read on import, never emitted
            "runtime", "parameters", "computation", "executor", "attester"],
}

# §5.4 lifecycle vocabulary. Absent means stable.
OKF_STATUS = ("draft", "stable", "deprecated")

# AI OS status (vocabularies.yaml) -> OKF status. Only `active`, `review-due`, and
# absent survive the export filter, so in practice an exported concept is always
# `stable`; the rest of the map exists for completeness and for `okf-check`.
STATUS_TO_OKF = {
    "active": "stable", "review-due": "stable", "draft": "draft",
    "stale": "deprecated", "superseded": "deprecated", "archived": "deprecated",
}

# §7 actor convention: `human:<id>`, `process:<id>`, or `<producer>/<version>`.
ACTOR = re.compile(r"^(?:human:\S+|process:\S+|[^\s:/]+/[^\s:/]+)$")

H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def valid_actor(value) -> bool:
    """Does this string follow §7? Consumers that classify trust key off the
    `human:` prefix, so a malformed actor silently costs a trust tier."""
    return bool(value) and bool(ACTOR.match(str(value).strip()))


def title_of(note) -> str:
    """A concept's display title: its H1 if it has one, else its filename stem.
    AI OS has no `title` field — the filename is the title, which is exactly the
    fallback the OKF spec names ("consumers MAY derive a title from the filename")."""
    m = H1.search(note.body or "")
    if m:
        return m.group(1).strip()
    return os.path.splitext(os.path.basename(note.relpath))[0]


def to_timestamp(value) -> str | None:
    """AI OS `updated` (a date) -> an ISO 8601 *datetime*, used by v0.1's
    `timestamp` and v0.2's `generated.at`. A bare date is not a datetime, so
    midnight UTC is supplied. Anything already carrying a time passes through."""
    if value in (None, ""):
        return None
    s = str(value).strip().strip("'\"")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return f"{s}T00:00:00+00:00"
    return s


def to_stale_after(value) -> str | None:
    """AI OS `review_due` -> OKF `stale_after` (§5.5). Both are absolute dates and
    both mean "on or after this day, stop treating this as current" — AI OS's own
    freshness pass flips a note to `review-due` on exactly this date. Anything
    that is not a plain `YYYY-MM-DD` is dropped rather than reshaped: §5.5 fixes
    the form, and a malformed date is worse than an absent one."""
    if value in (None, ""):
        return None
    s = str(value).strip().strip("'\"")
    return s if DATE.match(s) else None


def slugify(text: str, fallback: str = "concept") -> str:
    """A filename/id-safe slug matching the vault's ID grammar
    (`^[a-z0-9]+(-[a-z0-9]+)*$`) — imported titles are foreign and arrive with
    anything in them."""
    s = unicodedata.normalize("NFKD", str(text))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s or fallback


FORBIDDEN_IN_FILENAME = re.compile(r'[\\:*?"<>|]')


def safe_relpath(rel: str) -> str:
    """A bundle-relative path, made safe for the vault's filename rules
    (`validate`: no `\\ : * ? " < > |`, no trailing dots or spaces) while
    otherwise left **exactly as the producer wrote it**.

    Why not slugify: an OKF bundle is hierarchical and its concepts link to each
    other with ordinary relative markdown links (`../datasets/stackoverflow.md`,
    `posts_questions.md`). Flattening the tree or renaming the files breaks every
    one of those links — measured on Google's own stackoverflow bundle, which
    produced 68 broken-link warnings before this existed. A source is an
    immutable capture: it keeps its own shape, and its internal references keep
    resolving."""
    parts = []
    for seg in rel.replace("\\", "/").split("/"):
        seg = FORBIDDEN_IN_FILENAME.sub("-", seg).rstrip(". ")
        if seg in ("", ".", ".."):
            continue
        parts.append(seg)
    return os.path.join(*parts) if parts else "concept.md"


# Keys consumed by the OKF mapping, per version: emitted under an OKF name above,
# so re-emitting them as extras would state the same fact twice.
_CONSUMED = {
    "0.1": {"type", "summary", "original_location", "tags", "updated"},
    "0.2": {"type", "summary", "original_location", "tags", "updated",
            "status", "sources", "review_due"},
}


def to_okf(note, version: str = OKF_VERSION, author: str | None = None,
           sources_for=None) -> dict:
    """An AI OS note -> OKF concept frontmatter, for the named spec version.

    The OKF fields come first, then every remaining AI OS field rides along as an
    extra top-level key. Nothing is dropped: the spec permits extra keys and asks
    consumers to preserve them, which is what makes the round trip lossless.

    `author` is the §7 actor the operator asserts for `generated.by` (v0.2 only).
    `sources_for(meta)` is the caller's resolver from an AI OS `sources` id-list to
    OKF `sources` entries — it lives in the export command because only that
    command knows which notes made it into the bundle and which the privacy filter
    excluded."""
    if version not in OKF_FIELDS:
        raise ValueError(f"unknown OKF version {version!r}")
    meta = dict(note.meta or {})
    out: dict = {}

    out["type"] = meta.get("type")
    out["title"] = title_of(note)
    if meta.get("summary") not in (None, ""):
        out["description"] = str(meta["summary"])
    if meta.get("original_location") not in (None, ""):
        out["resource"] = meta["original_location"]
    if meta.get("tags"):
        out["tags"] = meta["tags"]

    if version == "0.1":
        ts = to_timestamp(meta.get("updated"))
        if ts:
            out["timestamp"] = ts
    else:
        # §5.4 — absent means `stable`, so this is emitted only where it is known.
        okf_status = STATUS_TO_OKF.get(str(meta.get("status") or "").strip())
        if okf_status:
            out["status"] = okf_status
        # §5.2 — `by` is REQUIRED inside `generated`, and the vault does not record
        # who wrote a note. With no asserted actor, the last-change time rides as
        # the legacy `timestamp` §13.1 tells consumers to fall back to.
        at = to_timestamp(meta.get("updated"))
        if author and at:
            out["generated"] = {"by": author, "at": at}
        elif author:
            out["generated"] = {"by": author}
        elif at:
            out["timestamp"] = at
        stale = to_stale_after(meta.get("review_due"))
        if stale:
            out["stale_after"] = stale
        entries = sources_for(meta) if sources_for else []
        if entries:
            out["sources"] = entries

    # The superset rides as extra keys (spec: producers MAY, consumers SHOULD
    # preserve). Keys already emitted under an OKF name are skipped.
    for k, v in meta.items():
        if k in _CONSUMED[version]:
            continue
        out[k] = v
    # `updated` (and, under v0.2, `review_due` and the AI OS `status` value) are
    # kept alongside their OKF counterparts so an AI OS re-import restores the
    # exact original rather than reconstructing it from a mapped value.
    if meta.get("updated") not in (None, ""):
        out["updated"] = meta["updated"]
    if version == "0.2":
        if meta.get("review_due") not in (None, ""):
            out["review_due"] = meta["review_due"]
        if meta.get("status") not in (None, ""):
            out["x_aios_status"] = meta["status"]
        if meta.get("sources"):
            # Under its own name, plainly an AI OS field: the id-list the OKF
            # `sources` entries above were built from, including the ids of
            # records outside this bundle that a v0.2 `resource` cannot honestly
            # point at. The export filters it for what may travel.
            out["x_aios_sources"] = meta["sources"]
    return out


# Every frontmatter field holding vault ids. A privacy filter that covers only
# `sources` would be a fence with six gates left open — `entities` ids encode
# people's names, and `contradicts` names a record by its title's slug. The
# export filters all of them to ids that may themselves travel.
ID_LIST_FIELDS = ("sources", "related", "derived_from", "depends_on", "supports",
                  "contradicts", "entities")
ID_FIELDS = ("supersedes", "superseded_by")


# OKF keys the importer lifts into named `x_okf_*` fields. Everything else a
# producer wrote is preserved under `x_okf_extra` rather than dropped.
_LIFTED = ("type", "title", "description", "resource", "tags",
           "timestamp", "generated", "verified", "status", "stale_after", "sources")


def verified_events(value) -> list:
    """`verified` as a list of events. §5.2/§11: a single verifier MAY be written
    as a bare `{by, at}` mapping, and a consumer **MUST** treat it as a
    one-element list. Anything else yields an empty list rather than a guess."""
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [e for e in value if isinstance(e, dict)]
    return []


def from_okf(meta: dict, body: str, relpath: str) -> dict:
    """An OKF concept -> the AI OS *source* note fields it becomes on import.

    An imported bundle is evidence, not knowledge: it lands as an immutable
    `source` (born `status: draft`, `verification: unverified`) and only
    `ingest-and-connect` may turn it into canon. So the concept's own `type`
    cannot occupy `type:` — that slot belongs to `source`. The OKF-native values
    are preserved verbatim under `x_okf_*` keys (the sanctioned experimental
    prefix, which `validate` skips), which is what the round-trip proof compares.

    **A producer's `verified` never raises this vault's `verification`.** The
    bundle cleared *their* gate, not this one; their verification events are
    recorded as evidence about the bundle, never adopted as this vault's own."""
    meta = dict(meta or {})
    title = meta.get("title") or os.path.splitext(os.path.basename(relpath))[0]
    fields: dict = {
        "type": "source",
        "subtype": "document",
        "status": "draft",
        "verification": "unverified",
        "summary": str(meta.get("description") or f"OKF concept: {title}"),
        "x_okf_type": meta.get("type"),
        "x_okf_title": title,
    }
    if meta.get("resource") not in (None, ""):
        fields["original_location"] = meta["resource"]
        fields["x_okf_resource"] = meta["resource"]
    if meta.get("tags"):
        fields["tags"] = meta["tags"]
    # v0.1's `timestamp` and v0.2's `generated` both answer "when did the content
    # last change" — both are kept, under their own names, so neither bundle
    # generation is read through the other's assumptions (§13.1).
    if meta.get("timestamp") not in (None, ""):
        fields["x_okf_timestamp"] = meta["timestamp"]
    if isinstance(meta.get("generated"), dict):
        fields["x_okf_generated"] = meta["generated"]
    events = verified_events(meta.get("verified"))
    if events:
        fields["x_okf_verified"] = events
    if meta.get("status") not in (None, ""):
        fields["x_okf_status"] = meta["status"]
    if meta.get("stale_after") not in (None, ""):
        fields["x_okf_stale_after"] = meta["stale_after"]
        # The one v0.2 lifecycle field with a true AI OS equivalent: the producer
        # named the date this stops being current, so the vault's own freshness
        # pass honours it instead of inventing a horizon.
        stale = to_stale_after(meta["stale_after"])
        if stale:
            fields["review_due"] = stale
    if meta.get("sources"):
        fields["x_okf_sources"] = meta["sources"]
    extra = {k: v for k, v in meta.items() if k not in _LIFTED}
    if extra:
        fields["x_okf_extra"] = extra
    return fields
