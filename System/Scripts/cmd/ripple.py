"""vault.ripple — connected-knowledge triage: list neighbors of changed notes,
record dispositions, accept new baselines. Listing is privacy-filtered with the
same predicate as search (H-02); a hosted runtime never sees excluded notes here."""
from __future__ import annotations
import datetime, json, os, re
import yaml
from lib.report import Report
from lib import freshness as fr
from lib.vaultpaths import ai_writes_enabled
from lib.protectedwrites import ProtectedTargetError, guard_ordinary_write_set
from lib.safepaths import (SafePathError, atomic_create_files,
                           preflight_contained_regular_files, read_regular_file)


def _note_text(text):
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        raise ValueError("note has no valid frontmatter fence")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("note frontmatter is not a mapping")
    return meta, text[match.end():]


def _error(rep, context, exc):
    rep.error(f"{context}: {exc}")
    return rep


def _writes(args) -> bool:
    return bool(getattr(args, "ack", None) or getattr(args, "baseline", None)
                or getattr(args, "baseline_all", False))


def _refs(root, needle: str, rep: Report):
    """Read-only reference sweep: every occurrence of a literal name (old path,
    id, filename) across the operational surfaces Change Control's medium tier
    orders checked on a rename/move — scripts, capabilities, agents, workflows,
    runtime, docs, registries. Determinism audit finding 3: this grep was
    hand-performed (or skipped) per rename; now it is computed."""
    import os
    SURFACES = ["System/Scripts", "System/Capabilities", "System/Agents",
                "System/Workflows", "System/Runtime", "System/Runtime Profiles",
                "System/Adapters", "System/Operations", "System/Registries",
                "System/Documentation", "System/Governance", "System/Onboarding",
                "System/Templates", "System/Schemas"]
    EXTS = (".md", ".yaml", ".yml", ".py", ".json")
    hits = []
    for rel in SURFACES:
        base = os.path.join(root, rel)
        if not os.path.isdir(base):
            continue
        for dirpath, _, files in os.walk(base):
            for name in files:
                if not name.endswith(EXTS):
                    continue
                fp = os.path.join(dirpath, name)
                try:
                    with open(fp, encoding="utf-8") as stream:
                        lines = stream.read().splitlines()
                except (OSError, UnicodeDecodeError):
                    continue
                for i, line in enumerate(lines, 1):
                    if needle in line:
                        hits.append(f"{os.path.relpath(fp, root)}:{i}: {line.strip()[:120]}")
    rep.info["refs_query"] = needle
    rep.info["refs_hits"] = len(hits)
    if hits:
        rep.info["refs"] = hits
        rep.warn(f"'{needle}' is still referenced in {len(hits)} place(s) — "
                 "every hit must be updated, confirmed unaffected, or journaled before the rename is done")
    else:
        rep.info["refs"] = "none — no operational surface references this name"
    return rep


def run(root, args, rep: Report):
    if getattr(args, "refs", None):
        return _refs(root, args.refs, rep)   # read-only; needs no freshness registry
    try:
        reg = fr.load_registry(root)
    except fr.FreshnessStateError as exc:
        return _error(rep, "freshness state unavailable", exc)
    if reg is None:
        rep.info["freshness"] = "no System/Registries/freshness.yaml — feature not installed"
        return rep
    if _writes(args) and not ai_writes_enabled(root):
        rep.error("kill switch is off (runtime.ai_writes_enabled: false) — refusing to write.")
        return rep
    notes = fr.scan(root)
    by_id = {str(n.meta.get("id")): n for n in notes.values()}

    if getattr(args, "ack", None):
        from_id = getattr(args, "from_id", None)
        effect = getattr(args, "effect", None)
        dispositions = reg.get("dispositions", [])
        if not from_id or not effect:
            rep.error("usage: aios ripple --ack <neighbor-id> --from <changed-id> --effect <effect> "
                      f"(effects: {', '.join(dispositions)})")
            return rep
        if effect not in dispositions:
            rep.error(f"unknown effect '{effect}' — one of: {', '.join(dispositions)}")
            return rep
        src = by_id.get(from_id)
        if src is None:
            rep.error(f"changed note '{from_id}' not found among typed notes")
            return rep
        try:
            targets = ([str(n2.meta.get("id")) for changed, n2 in fr.pending(root, notes)
                        if str(changed.meta.get("id")) == from_id]
                       if getattr(args, "ack_all", False) else [args.ack])
        except fr.FreshnessStateError as exc:
            return _error(rep, "freshness state unavailable", exc)
        valid = []
        for nid in targets:
            tgt = by_id.get(nid)
            if tgt is None:
                rep.warn(f"neighbor '{nid}' not found — skipped")
            else:
                valid.append(tgt)
        if not valid:
            rep.info["acked"] = 0
            return rep
        evidence = []
        writes_batch = None
        try:
            evidence_paths = ([src.path] if effect == "makes-stale"
                              else [src.path] + [n.path for n in valid])
            evidence = [read_regular_file(path) for path in evidence_paths]
            evidence_text = {os.path.abspath(path): item.data.decode("utf-8")
                             for path, item in zip(evidence_paths, evidence)}
            src_meta, src_body = _note_text(evidence_text[os.path.abspath(src.path)])
            if str(src_meta.get("id")) != from_id:
                raise ValueError("changed source identity changed during preflight")
            h = fr.body_hash(src_body)

            log_path = os.path.join(root, fr.LOG_REL)
            stale_paths = [n.path for n in valid] if effect == "makes-stale" else []
            existing_writes = list(stale_paths)
            if os.path.lexists(log_path):
                existing_writes.append(log_path)
            if existing_writes:
                writes_batch = preflight_contained_regular_files(root, existing_writes)
                current = writes_batch.read_texts()
            else:
                current = {}
            prior = current.get(os.path.abspath(log_path), "")
            fr.parse_events_text(prior)
            lines = prior
            for tgt in valid:
                lines += json.dumps({
                    "date": datetime.date.today().isoformat(), "event": "ripple_ack",
                    "from": from_id, "neighbor": str(tgt.meta.get("id")),
                    "effect": effect, "from_hash": h,
                }, sort_keys=True) + "\n"
            writes = {fr.LOG_REL.replace(os.sep, "/"): lines.encode("utf-8")}
            if effect == "makes-stale":
                for tgt in valid:
                    text = current[os.path.abspath(tgt.path)]
                    meta, _body = _note_text(text)
                    if str(meta.get("id")) != str(tgt.meta.get("id")):
                        raise ValueError(f"{tgt.relpath} identity changed during preflight")
                    updated = fr.frontmatter_field_text(text, "status", "stale")
                    if updated is None:
                        raise ValueError(f"{tgt.relpath} has invalid frontmatter")
                    writes[tgt.relpath.replace(os.sep, "/")] = updated.encode("utf-8")
            participants = [src] + valid
            participant_texts = {}
            for note in participants:
                absolute = os.path.abspath(note.path)
                text = current.get(absolute, evidence_text.get(absolute))
                if text is None:
                    raise ValueError(f"{note.relpath} was not bound during preflight")
                participant_texts[note.relpath.replace(os.sep, "/")] = text
            policy = guard_ordinary_write_set(
                root,
                participant_texts,
                "ripple acknowledgement",
                texts=participant_texts,
            )
            atomic_create_files(root, writes, replace_batch=writes_batch,
                                read_only_inputs=evidence + [policy.manifest])
        except (ProtectedTargetError, SafePathError, fr.FreshnessStateError, ValueError,
                UnicodeDecodeError, yaml.YAMLError) as exc:
            return _error(rep, "ripple acknowledgement transaction refused", exc)
        finally:
            if writes_batch is not None:
                writes_batch.close()
        if effect == "makes-stale":
            rep.info["marked_stale"] = [str(n.meta.get("id")) for n in valid]
        rep.info["acked"] = len(valid)
        return rep

    if getattr(args, "baseline", None) or getattr(args, "baseline_all", False):
        selected = None
        if not getattr(args, "baseline_all", False):
            selected = by_id.get(args.baseline)
            if selected is None:
                rep.error(f"note '{args.baseline}' not found among typed notes")
                return rep
        evidence = []
        ledger_batch = None
        try:
            evidence_paths = [n.path for n in notes.values()]
            evidence = [read_regular_file(path) for path in evidence_paths]
            note_texts = {os.path.abspath(path): item.data.decode("utf-8")
                          for path, item in zip(evidence_paths, evidence)}
            current_notes = {}
            for rel, note in notes.items():
                meta, body = _note_text(note_texts[os.path.abspath(note.path)])
                if str(meta.get("id")) != str(note.meta.get("id")):
                    raise ValueError(f"{rel} identity changed during preflight")
                current_notes[rel] = (note, body)

            ledger_path = os.path.join(root, fr.LEDGER_REL)
            if os.path.lexists(ledger_path):
                ledger_batch = preflight_contained_regular_files(root, [ledger_path])
                ledger_raw = ledger_batch.read_texts()[os.path.abspath(ledger_path)]
                ledger = fr.parse_ledger_text(ledger_raw)
            else:
                ledger = {}
            today = datetime.date.today().isoformat()
            unseen = [rel for rel in current_notes if rel not in ledger]
            for rel in unseen:
                ledger[rel] = {"h": fr.body_hash(current_notes[rel][1]), "seen": today}
            for rel in list(ledger):
                if rel not in current_notes:
                    del ledger[rel]
            if getattr(args, "baseline_all", False):
                accepted = 0
                for rel, (_note, body) in current_notes.items():
                    h = fr.body_hash(body)
                    if rel not in unseen and ledger.get(rel, {}).get("h") != h:
                        ledger[rel] = {"h": h, "seen": today, "edited": True}
                        accepted += 1
            else:
                rel = selected.relpath
                ledger[rel] = {"h": fr.body_hash(current_notes[rel][1]),
                               "seen": today, "edited": True}
                accepted = str(selected.meta.get("id"))
            participant_texts = {
                note.relpath.replace(os.sep, "/"):
                    note_texts[os.path.abspath(note.path)]
                for note in notes.values()
            }
            policy = guard_ordinary_write_set(
                root,
                participant_texts,
                "ripple baseline",
                texts=participant_texts,
            )
            atomic_create_files(
                root, {fr.LEDGER_REL.replace(os.sep, "/"): fr.ledger_text(ledger).encode("utf-8")},
                replace_batch=ledger_batch,
                read_only_inputs=evidence + [policy.manifest],
            )
        except (ProtectedTargetError, SafePathError, fr.FreshnessStateError, ValueError,
                UnicodeDecodeError, yaml.YAMLError) as exc:
            return _error(rep, "baseline transaction refused", exc)
        finally:
            if ledger_batch is not None:
                ledger_batch.close()
        if unseen:
            rep.info["newly_baselined"] = len(unseen)
        rep.info["accepted"] = accepted
        return rep

    # read-only listing (privacy-filtered)
    from cmd.search import RetrievalPolicyError, permitted, load_profile
    try:
        profile = load_profile(root)
    except RetrievalPolicyError as exc:
        rep.error(f"retrieval policy unavailable: {exc}")
        return rep
    try:
        items = fr.pending(root, notes)
    except fr.FreshnessStateError as exc:
        return _error(rep, "freshness state unavailable", exc)
    shown, excluded = [], 0
    for src, tgt in items:
        if permitted(src.meta, profile, src.relpath) and permitted(tgt.meta, profile, tgt.relpath):
            shown.append(f"{src.meta.get('id')} → {tgt.meta.get('id')}")
        else:
            excluded += 1
    try:
        _, unseen = fr.changed(root, notes)
    except fr.FreshnessStateError as exc:
        return _error(rep, "freshness state unavailable", exc)
    rep.info["pending"] = shown or "none"
    rep.info["pending_total"] = len(items)
    if excluded:
        rep.info["excluded_by_privacy"] = excluded
    if unseen:
        rep.info["unbaselined_notes"] = len(unseen)
    return rep
