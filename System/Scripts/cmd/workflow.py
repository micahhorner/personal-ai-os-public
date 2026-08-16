"""vault.workflow — recurring-workflow freshness: last-run and overdue state for
every cadenced workflow component; --ran records a completed run. Fixes the
"nothing turns itself on" failure: a stalled routine becomes visible instead of
silently never happening (graduated idea-workflow-freshness)."""
from __future__ import annotations
from lib.report import Report
from lib import freshness as fr
from lib.vaultpaths import ai_writes_enabled


def run(root, args, rep: Report):
    try:
        reg = fr.load_registry(root)
    except fr.FreshnessStateError as exc:
        rep.error(f"freshness state unavailable: {exc}")
        return rep
    if reg is None:
        rep.info["freshness"] = "no System/Registries/freshness.yaml — feature not installed"
        return rep
    ran = getattr(args, "ran", None)
    if ran:
        if not ai_writes_enabled(root):
            rep.error("kill switch is off (runtime.ai_writes_enabled: false) — refusing to write.")
            return rep
        try:
            known = {wid for wid, _, _, _ in fr.workflow_status(root, reg)}
        except fr.FreshnessStateError as exc:
            rep.error(f"freshness state unavailable: {exc}")
            return rep
        if ran not in known:
            rep.error(f"'{ran}' is not a cadenced workflow (declare cadence_days in its frontmatter); "
                      f"known: {', '.join(sorted(known)) or 'none'}")
            return rep
        try:
            fr.append_event(root, event="workflow_run", id=ran)
        except fr.FreshnessStateError as exc:
            rep.error(f"workflow event was not recorded: {exc}")
            return rep
        rep.info["recorded"] = ran
        return rep
    try:
        rows = fr.workflow_status(root, reg)
    except fr.FreshnessStateError as exc:
        rep.error(f"freshness state unavailable: {exc}")
        return rep
    if not rows:
        rep.info["cadenced_workflows"] = "none (declare cadence_days in a workflow's frontmatter)"
        return rep
    for wid, cad, last, overdue in rows:
        state = "OVERDUE" if overdue else "ok"
        rep.info[wid] = f"cadence {cad}d, last run {last or 'never'} — {state}"
    rep.info["overdue_total"] = sum(1 for *_x, o in rows if o)
    return rep
