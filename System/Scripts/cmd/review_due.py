"""vault review-due — notes due for review, stale, missing provenance, or unprocessed.
--set-missing stamps review_due (today + the type's horizon) on active, non-exempt,
post-epoch notes that lack one — the deterministic backstop behind promotion-time
stamping (SPEC-knowledge-freshness §5). Grandfathered notes are never stamped."""
from __future__ import annotations
import os, datetime, re
import yaml
from lib.frontmatter import iter_markdown
from lib.protectedwrites import ProtectedTargetError, guard_ordinary_write_set
from lib.report import Report
from lib.safepaths import SafePathError, atomic_create_files, preflight_contained_regular_files


def _frontmatter(text):
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        raise ValueError("note has no valid frontmatter fence")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("note frontmatter is not a mapping")
    return meta

def run(root, args, rep: Report):
    today = datetime.date.today().isoformat()
    if getattr(args, "set_missing", False):
        from lib import freshness as fr
        from lib.vaultpaths import ai_writes_enabled
        if not ai_writes_enabled(root):
            rep.error("kill switch is off (runtime.ai_writes_enabled: false) — refusing to write.")
            return rep
        try:
            reg = fr.load_registry(root)
        except fr.FreshnessStateError as exc:
            rep.error(f"freshness state unavailable: {exc}")
            return rep
        if reg is None:
            rep.info["freshness"] = "no System/Registries/freshness.yaml — feature not installed"
            return rep
        if not fr.epoch(reg):
            rep.error("freshness registry has no enforced_since date — run `aios generate` once to stamp it")
            return rep
        try:
            selected = fr.horizon_missing(root, reg)
        except fr.FreshnessStateError as exc:
            rep.error(f"freshness state unavailable: {exc}")
            return rep
        stamped = []
        if selected:
            batch = None
            try:
                batch = preflight_contained_regular_files(root, [n.path for n in selected])
                current = batch.read_texts()
                writes = {}
                for n in selected:
                    text = current[os.path.abspath(n.path)]
                    meta = _frontmatter(text)
                    if (str(meta.get("id")) != str(n.meta.get("id"))
                            or meta.get("type") != n.meta.get("type")
                            or str(meta.get("status")) != "active"
                            or meta.get("review_due")):
                        raise ValueError(f"{n.relpath} changed during review-due preflight")
                    days = fr.horizon_for(reg, meta.get("type"))
                    if days is None:
                        raise ValueError(f"{n.relpath} has no review horizon")
                    due = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
                    updated = fr.frontmatter_field_text(text, "review_due", due)
                    if updated is None:
                        raise ValueError(f"{n.relpath} has invalid frontmatter")
                    writes[n.relpath.replace(os.sep, "/")] = updated.encode("utf-8")
                    stamped.append(f"{meta.get('id')} → {due}")
                policy = guard_ordinary_write_set(
                    root,
                    writes,
                    "review-due --set-missing",
                    texts={target.relpath: current[target.path]
                           for target in batch.targets},
                )
                atomic_create_files(
                    root,
                    writes,
                    replace_batch=batch,
                    read_only_inputs=(policy.manifest,),
                )
            except (ProtectedTargetError, SafePathError, ValueError, yaml.YAMLError) as exc:
                rep.error(f"review-due transaction refused: {exc}")
                return rep
            finally:
                if batch is not None:
                    batch.close()
        rep.info["stamped"] = stamped or "none needed"
        return rep
    due, stale, noprov, inbox = [], [], [], []
    for n in iter_markdown(root):
        if n.error or not n.meta:
            continue
        rid = n.meta.get("id", n.relpath)
        if n.relpath.startswith("00 Inbox") and not os.path.basename(n.relpath).startswith("_"):
            inbox.append(rid); continue
        if str(n.meta.get("status")) == "stale":
            stale.append(rid)
        rd = str(n.meta.get("review_due", ""))
        if rd and rd <= today and str(n.meta.get("status")) not in ("superseded", "archived"):
            due.append(rid)
        if (n.meta.get("subtype") in ("claim", "finding") and not n.meta.get("sources")):
            noprov.append(rid)
    for label, items in [("review_due", due), ("stale", stale),
                         ("claims_without_sources", noprov), ("unprocessed_inbox", inbox)]:
        rep.info[label] = items or "none"
        if label == "claims_without_sources":
            for i in items: rep.warn(f"claim/finding without sources: {i}")
    return rep
