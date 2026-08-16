"""Knowledge-freshness machinery: body-hash ledger, ripple triage, horizons, workflow runs.

Doctrine (SPEC-knowledge-freshness / PLAN-knowledge-freshness): scripts detect,
capabilities judge, humans approve. State is exactly two files under System/Logs —
the regenerable ledger (body hashes) and the durable append-only event log
(dispositions + workflow runs). Everything else is computed per run (store truth
once). First sight of a note baselines it silently: obligations are never
retroactive, which covers install, upgrade, import, and ledger loss with one rule.
System/Logs, not System/Generated: generate wipes Generated on every run, and
Generated artifacts are built at the hosted privacy floor — neither survives here.
"""
from __future__ import annotations
import datetime, glob, hashlib, json, os, re
import yaml
from lib.frontmatter import iter_markdown, body_links
from lib.safepaths import (SafePathError, atomic_create_files,
                           open_readonly_tree, preflight_contained_regular_files,
                           safe_relative_path)

LEDGER_REL = os.path.join("System", "Logs", "freshness-ledger.json")
LOG_REL = os.path.join("System", "Logs", "freshness-log.jsonl")
REGISTRY_REL = os.path.join("System", "Registries", "freshness.yaml")
OVERRIDES_REL = os.path.join("80 User", "freshness-overrides.yaml")

# frontmatter fields whose values are note ids participating in the knowledge
# graph — the relationship half of a changed note's neighbor set
RELATION_FIELDS = ("supports", "weakens", "contradicts", "clarifies", "connects",
                   "enables", "related", "derived_from", "supersedes")
TRIAGE_STATUSES = ("active", "stale")   # only live canon produces triage items


class FreshnessStateError(RuntimeError):
    """Freshness state is malformed or cannot be read/written safely."""


def _safe_optional_text(root, rel):
    rel = safe_relative_path(rel.replace(os.sep, "/"), "freshness state path")
    path = os.path.abspath(os.path.join(root, *rel.split("/")))
    if not os.path.lexists(path):
        return None
    try:
        batch = preflight_contained_regular_files(
            root, [path], require_writable=False
        )
        try:
            return batch.read_texts()[path]
        finally:
            batch.close()
    except SafePathError as exc:
        raise FreshnessStateError(f"{rel} cannot be read safely: {exc}") from exc


def commit_texts(root, writes):
    """Commit new/replaced freshness files as one contained transaction."""
    normalized = {safe_relative_path(rel.replace(os.sep, "/"), "freshness write path"): text
                  for rel, text in writes.items()}
    existing = [os.path.join(root, *rel.split("/")) for rel in normalized
                if os.path.lexists(os.path.join(root, *rel.split("/")))]
    batch = None
    try:
        if existing:
            batch = preflight_contained_regular_files(root, existing)
            batch.read_texts()
        atomic_create_files(
            root, {rel: text.encode("utf-8") for rel, text in normalized.items()},
            replace_batch=batch,
        )
    except SafePathError as exc:
        raise FreshnessStateError(f"freshness transaction refused: {exc}") from exc
    finally:
        if batch is not None:
            batch.close()


def body_hash(body: str) -> str:
    """Hash of the note BODY only — frontmatter/bookkeeping edits never ripple.
    Line endings normalized, per-line trailing whitespace stripped: a
    whitespace-only touch is not a change (noise control, plan §7)."""
    norm = "\n".join(line.rstrip() for line in body.replace("\r\n", "\n").split("\n")).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def load_registry(root):
    """The freshness registry, or None when the feature is not installed
    (feature-absent = every check skips quietly — rollback-clean)."""
    path = os.path.join(root, REGISTRY_REL)
    if not os.path.lexists(path):
        return None
    reg = parse_registry_text(_safe_optional_text(root, REGISTRY_REL))
    # user tuning merges read-only, same pattern as vocabulary-extensions (DEC-014)
    opath = os.path.join(root, OVERRIDES_REL)
    if os.path.lexists(opath):
        try:
            ov = yaml.safe_load(_safe_optional_text(root, OVERRIDES_REL)) or {}
            if not isinstance(ov, dict):
                raise FreshnessStateError(f"{OVERRIDES_REL} is not a mapping")
            if isinstance(ov.get("horizons_days"), dict):
                reg.setdefault("horizons_days", {}).update(ov["horizons_days"])
            if isinstance(ov.get("exempt_types"), list):
                reg["exempt_types"] = sorted(set(reg.get("exempt_types", [])) | set(ov["exempt_types"]))
        except yaml.YAMLError as exc:
            raise FreshnessStateError(f"{OVERRIDES_REL} is malformed YAML: {exc}") from exc
    return reg


def parse_registry_text(text: str) -> dict:
    """Strictly validate one already-bound freshness registry payload."""
    try:
        reg = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise FreshnessStateError(f"{REGISTRY_REL} is malformed YAML: {exc}") from exc
    if not isinstance(reg, dict):
        raise FreshnessStateError(f"{REGISTRY_REL} is not a mapping")
    for key, kind in (("horizons_days", dict), ("exempt_types", list),
                      ("dispositions", list)):
        if key in reg and not isinstance(reg[key], kind):
            raise FreshnessStateError(f"{REGISTRY_REL} field {key} has the wrong type")
    return reg


def epoch(registry) -> str | None:
    e = (registry or {}).get("enforced_since")
    return str(e) if e else None


def schema_types(root) -> set:
    types = set()
    for f in glob.glob(os.path.join(root, "System", "Schemas", "*.yaml")):
        try:
            with open(f, encoding="utf-8") as stream:
                d = yaml.safe_load(stream) or {}
        except yaml.YAMLError:
            continue
        if isinstance(d, dict) and d.get("schema") and d.get("schema") != "component":
            types.add(d["schema"])
    return types


def load_ledger(root) -> dict:
    text = _safe_optional_text(root, LEDGER_REL)
    if text is None:
        return {}
    return parse_ledger_text(text)


def parse_ledger_text(text: str) -> dict:
    """Parse ledger text strictly; corruption must never become a rebaseline."""
    try:
        d = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FreshnessStateError(f"{LEDGER_REL} is malformed JSON: {exc}") from exc
    if not isinstance(d, dict) or not isinstance(d.get("notes"), dict):
        raise FreshnessStateError(f"{LEDGER_REL} must contain a notes mapping")
    return d["notes"]


def save_ledger(root, notes: dict):
    commit_texts(root, {LEDGER_REL: ledger_text(notes)})


def ledger_text(notes: dict) -> str:
    return json.dumps({"schema": 1, "notes": notes}, indent=1, sort_keys=True) + "\n"


def _stamped_registry_text(text: str, today: str) -> str:
    """Replace the one null epoch scalar without reserializing human comments."""
    pattern = re.compile(
        r"^(?P<prefix>\s*enforced_since:\s*)"
        r"(?P<value>[^#\r\n]*?)"
        r"(?P<suffix>\s*(?:#.*)?)$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise FreshnessStateError(
            f"{REGISTRY_REL} must contain exactly one enforced_since field"
        )
    match = matches[0]
    if match.group("value").strip().lower() not in ("", "null", "~"):
        raise FreshnessStateError(
            f"{REGISTRY_REL} enforced_since is not a null epoch"
        )
    return text[:match.start()] + match.group("prefix") + today + \
        match.group("suffix") + text[match.end():]


class GenerateFreshnessPlan:
    """A pure generate-time plan plus its held registry/ledger CAS binding."""

    def __init__(self, root, *, batch=None, writes=None, added=0, stamped=False):
        self.root = root
        self.batch = batch
        self.writes = writes or {}
        self.added = added
        self.stamped = stamped

    @property
    def active(self):
        return bool(self.writes)

    def commit(self):
        if not self.writes:
            return
        create_dirs = []
        logs = os.path.join(self.root, "System", "Logs")
        if not os.path.lexists(logs):
            create_dirs.append("System/Logs")
        try:
            atomic_create_files(
                self.root,
                {rel: text.encode("utf-8") for rel, text in self.writes.items()},
                replace_batch=self.batch,
                create_dirs=create_dirs,
            )
        except SafePathError as exc:
            raise FreshnessStateError(
                f"generate freshness transaction refused: {exc}"
            ) from exc
        finally:
            self.close()

    def close(self):
        if self.batch is not None:
            self.batch.close()
            self.batch = None


def plan_generate_update(root, instance_role: str) -> GenerateFreshnessPlan:
    """Validate first and plan generate's epoch+ledger update without writing.

    Existing registry and ledger files are read as one descriptor-bound set.
    A personal instance with an installed registry may later commit both files
    through one CAS transaction. Generic masters and feature-absent vaults are
    validation-only and never create Logs or a ledger.
    """
    registry_path = os.path.abspath(os.path.join(root, REGISTRY_REL))
    ledger_path = os.path.abspath(os.path.join(root, LEDGER_REL))
    logs_path = os.path.abspath(os.path.join(root, "System", "Logs"))
    if os.path.lexists(logs_path):
        logs_tree = None
        try:
            logs_tree = open_readonly_tree(logs_path)
        except (OSError, SafePathError) as exc:
            raise FreshnessStateError(
                f"System/Logs cannot contain freshness state safely: {exc}"
            ) from exc
        finally:
            if logs_tree is not None:
                logs_tree.close()
    registry_exists = os.path.lexists(registry_path)
    ledger_exists = os.path.lexists(ledger_path)
    existing = [path for path, present in (
        (registry_path, registry_exists), (ledger_path, ledger_exists)
    ) if present]
    read_batch = None
    try:
        if existing:
            read_batch = preflight_contained_regular_files(
                root, existing, require_writable=False
            )
            texts = read_batch.read_texts()
        else:
            texts = {}
        registry_text = texts.get(registry_path)
        ledger_source = texts.get(ledger_path)
        registry = (parse_registry_text(registry_text)
                    if registry_text is not None else None)
        ledger = (parse_ledger_text(ledger_source)
                  if ledger_source is not None else {})

        if instance_role == "generic-master" or registry is None:
            return GenerateFreshnessPlan(root)

        today = datetime.date.today().isoformat()
        stamped = not epoch(registry)
        next_registry = (_stamped_registry_text(registry_text, today)
                         if stamped else registry_text)
        notes = scan(root)
        next_ledger = dict(ledger)
        added = 0
        for rel, note in notes.items():
            if rel not in next_ledger:
                next_ledger[rel] = {"h": body_hash(note.body), "seen": today}
                added += 1
        for rel in [value for value in next_ledger if value not in notes]:
            del next_ledger[rel]
        next_ledger_text = ledger_text(next_ledger)
        if next_registry == registry_text and next_ledger_text == ledger_source:
            return GenerateFreshnessPlan(root)

        originals = {path: texts[path] for path in existing}
    finally:
        if read_batch is not None:
            read_batch.close()

    # Re-open writable CAS bindings before any caller is allowed to publish.
    write_batch = None
    try:
        if existing:
            write_batch = preflight_contained_regular_files(root, existing)
            rebound = write_batch.read_texts()
            if any(rebound.get(path) != text for path, text in originals.items()):
                raise FreshnessStateError(
                    "freshness registry or ledger changed during generate planning"
                )
        return GenerateFreshnessPlan(
            root,
            batch=write_batch,
            writes={REGISTRY_REL.replace(os.sep, "/"): next_registry,
                    LEDGER_REL.replace(os.sep, "/"): next_ledger_text},
            added=added,
            stamped=stamped,
        )
    except BaseException:
        if write_batch is not None:
            write_batch.close()
        raise


def events(root) -> list:
    text = _safe_optional_text(root, LOG_REL)
    if text is None:
        return []
    return parse_events_text(text)


def parse_events_text(text: str) -> list:
    """Parse an event log strictly; corruption is never treated as an empty log."""
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FreshnessStateError(
                f"{LOG_REL} has malformed JSON on line {number}: {exc}"
            ) from exc
        if not isinstance(event, dict):
            raise FreshnessStateError(f"{LOG_REL} line {number} is not an event object")
        out.append(event)
    return out


def append_event(root, **event):
    """Append one event with an fd-bound compare-and-swap replacement."""
    event.setdefault("date", datetime.date.today().isoformat())
    path = os.path.join(root, LOG_REL)
    batch = None
    try:
        if os.path.lexists(path):
            batch = preflight_contained_regular_files(root, [path])
            prior = batch.read_texts()[os.path.abspath(path)]
            parse_events_text(prior)
        else:
            prior = ""
        atomic_create_files(
            root,
            {LOG_REL.replace(os.sep, "/"): (
                prior + json.dumps(event, sort_keys=True) + "\n"
            ).encode("utf-8")},
            replace_batch=batch,
        )
    except SafePathError as exc:
        raise FreshnessStateError(f"freshness event append refused: {exc}") from exc
    finally:
        if batch is not None:
            batch.close()


def scan(root) -> dict:
    """relpath -> Note for every typed user note (untyped/foreign files are
    validate's business, not freshness's)."""
    types = schema_types(root)
    out = {}
    for n in iter_markdown(root):
        if n.error or not n.meta:
            continue
        if n.meta.get("type") in types and n.meta.get("id"):
            out[n.relpath] = n
    return out


def changed(root, notes: dict | None = None):
    """(changed, unseen): notes whose body hash differs from their baseline, and
    notes the ledger has never seen (these carry no obligation — grandfathering)."""
    notes = notes if notes is not None else scan(root)
    ledger = load_ledger(root)
    ch, unseen = [], []
    for rel, n in notes.items():
        entry = ledger.get(rel)
        if entry is None:
            unseen.append(rel)
        elif entry.get("h") != body_hash(n.body):
            ch.append(n)
    return ch, unseen


def ensure_baseline(root, notes: dict | None = None) -> int:
    """Baseline UNSEEN notes and prune deleted paths. Never touches an existing
    entry whose hash differs — that would silently swallow a pending ripple.
    Returns how many notes were newly baselined. (Write operation.)"""
    notes = notes if notes is not None else scan(root)
    ledger = load_ledger(root)
    today = datetime.date.today().isoformat()
    added = 0
    for rel, n in notes.items():
        if rel not in ledger:
            ledger[rel] = {"h": body_hash(n.body), "seen": today}
            added += 1
    for rel in [r for r in ledger if r not in notes]:
        del ledger[rel]
    save_ledger(root, ledger)
    return added


def accept_baseline(root, note) -> None:
    """Accept a changed note's current content as the new reference (post-triage).
    Marks the entry `edited`: the note has re-entered live knowledge, so it is
    post-epoch for horizon purposes even if created before enforcement."""
    ledger = load_ledger(root)
    ledger[note.relpath] = {"h": body_hash(note.body),
                            "seen": datetime.date.today().isoformat(),
                            "edited": True}
    save_ledger(root, ledger)


def _stems(notes: dict):
    """filename-stem -> relpath and id -> relpath lookup for link resolution."""
    by_stem, by_id = {}, {}
    for rel, n in notes.items():
        by_stem[os.path.splitext(os.path.basename(rel))[0].lower()] = rel
        by_id[str(n.meta.get("id"))] = rel
    return by_stem, by_id


def neighbors(root, note, notes: dict) -> list:
    """A changed note's neighbor set: outgoing links, frontmatter relations, and
    backlinks — restricted to live canon (active/stale). Sorted for determinism."""
    by_stem, by_id = _stems(notes)
    found = set()
    wl, ml = body_links(note.body)
    for w in wl:
        rel = by_stem.get(w.lower()) or by_id.get(w)
        if rel:
            found.add(rel)
    for m in ml:
        target = os.path.normpath(os.path.join(os.path.dirname(note.relpath), m))
        if target in notes:
            found.add(target)
    for field in RELATION_FIELDS:
        v = note.meta.get(field)
        for ref in (v if isinstance(v, list) else [v] if v else []):
            rel = by_id.get(str(ref))
            if rel:
                found.add(rel)
    my_stem = os.path.splitext(os.path.basename(note.relpath))[0].lower()
    my_id = str(note.meta.get("id"))
    for rel, n in notes.items():
        if rel == note.relpath or rel in found:
            continue
        wl2, _ = body_links(n.body)
        if any(w.lower() == my_stem or w == my_id for w in wl2):
            found.add(rel)
        else:
            for field in RELATION_FIELDS:
                v = n.meta.get(field)
                refs = v if isinstance(v, list) else [v] if v else []
                if my_id in [str(r) for r in refs]:
                    found.add(rel)
                    break
    found.discard(note.relpath)
    return sorted(r for r in found
                  if str(notes[r].meta.get("status", "")) in TRIAGE_STATUSES)


def pending(root, notes: dict | None = None) -> list:
    """[(changed_note, neighbor_note)] awaiting disposition. An ack clears a pair
    only while the changed note's hash matches the hash recorded at ack time —
    change the note again and its neighbors return for triage."""
    notes = notes if notes is not None else scan(root)
    ch, _ = changed(root, notes)
    if not ch:
        return []
    acks = {}
    for e in events(root):
        if e.get("event") == "ripple_ack":
            acks[(e.get("from"), e.get("neighbor"))] = e.get("from_hash")
    out = []
    for note in ch:
        h = body_hash(note.body)
        nid = str(note.meta.get("id"))
        for rel in neighbors(root, note, notes):
            n2 = notes[rel]
            if acks.get((nid, str(n2.meta.get("id")))) != h:
                out.append((note, n2))
    return out


def horizon_missing(root, registry, notes: dict | None = None) -> list:
    """Active, non-exempt, post-epoch notes with no review_due. Post-epoch =
    created on/after enforcement, or body-edited since (accepting a triaged
    change re-enters the note into live knowledge). Grandfathered notes are
    never flagged (owner D5: never retroactive)."""
    ep = epoch(registry)
    if not ep:
        return []
    notes = notes if notes is not None else scan(root)
    ledger = load_ledger(root)
    exempt = set(registry.get("exempt_types", []))
    horizons = registry.get("horizons_days", {})
    out = []
    for rel, n in notes.items():
        m = n.meta
        t = m.get("type")
        if (t in exempt or t not in horizons or m.get("review_due")
                or str(m.get("status", "")) != "active"):
            continue
        post = str(m.get("created", "")) >= ep or ledger.get(rel, {}).get("edited")
        if post:
            out.append(n)
    return out


def horizon_for(registry, note_type: str) -> int | None:
    h = (registry or {}).get("horizons_days", {}).get(note_type)
    return int(h) if h else None


def workflow_status(root, registry) -> list:
    """[(id, cadence_days, last_run, overdue)] for every cadenced workflow
    component. Never-run counts from enforcement, not from zero — a fresh
    install is not born overdue."""
    ep = epoch(registry)
    runs = {}
    for e in events(root):
        if e.get("event") == "workflow_run" and e.get("id"):
            d = str(e.get("date", ""))
            if d > runs.get(e["id"], ""):
                runs[e["id"]] = d
    today = datetime.date.today()
    out = []
    for n in iter_markdown(root):
        if n.error or not n.meta or n.meta.get("type") != "workflow":
            continue
        cad = n.meta.get("cadence_days")
        if not isinstance(cad, int) or cad <= 0:
            continue
        wid = str(n.meta.get("id"))
        last = runs.get(wid)
        anchor = last or ep
        overdue = False
        if anchor:
            try:
                days = (today - datetime.date.fromisoformat(anchor)).days
                overdue = days > cad
            except ValueError:
                pass
        out.append((wid, cad, last, overdue))
    return sorted(out)


def frontmatter_field_text(text: str, key: str, value: str) -> str | None:
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)
    line = f"{key}: {value}"
    if re.search(rf"(?m)^{re.escape(key)}:", fm):
        fm2 = re.sub(rf"(?m)^{re.escape(key)}:.*$", line, fm, count=1)
    else:
        fm2 = fm + "\n" + line
    return text[:m.start(1)] + fm2 + text[m.end(1):]
