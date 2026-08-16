"""vault.checkup — a friendly one-line "state of your core" readout (Principle 26).

Pull, not push: run it whenever you want it; it never nags on its own. Light by
design — it counts, it does not validate (that is `aios health`). The numbers are
the same doctrine signals `health` reports; this command just says them plainly so
a human or any runtime can ask "how am I doing?" and get one honest line back.
"""
from __future__ import annotations
import os, datetime
from lib.frontmatter import iter_markdown
from lib.report import Report


def run(root, args, rep: Report):
    today = datetime.date.today().isoformat()
    from lib.vaultpaths import rel_folder
    _knowledge = rel_folder(root, "knowledge", "20 Knowledge")
    inbox = review_due = unverified = 0
    for n in iter_markdown(root):
        if n.error:
            continue
        rel = n.relpath
        if rel.startswith("00 Inbox") and not os.path.basename(rel).startswith("_"):
            inbox += 1
        rd = str(n.meta.get("review_due", ""))
        if rd and rd <= today:
            review_due += 1
        # staging masquerading as canon: active knowledge note never verified (Principle 26)
        if (rel.startswith(_knowledge) and n.meta.get("type") == "note"
                and str(n.meta.get("status", "")) == "active"
                and str(n.meta.get("verification", "")).strip() in ("", "unverified")):
            unverified += 1
    rep.info["inbox_items"] = inbox
    rep.info["review_due"] = review_due
    rep.info["unverified_in_knowledge"] = unverified
    if inbox == 0 and review_due == 0 and unverified == 0:
        rep.info["checkup"] = ("your vault is tidy — nothing waiting in staging, "
                               "nothing overdue for review, nothing filed as knowledge unverified.")
    else:
        parts = []
        if inbox:
            parts.append(f"{inbox} waiting in staging (inbox)")
        if review_due:
            parts.append(f"{review_due} due for review")
        if unverified:
            parts.append(f"{unverified} filed as knowledge but never verified")
        rep.info["checkup"] = (" · ".join(parts)
                               + ". Ask me to process your inbox, verify a note, or run the weekly pass anytime.")
    return rep
