"""vault.health_check — composite health report."""
from __future__ import annotations
import os, datetime
from lib.frontmatter import iter_markdown
from lib.report import Report
from cmd import validate as v_mod, links as l_mod, dupes as d_mod, doccheck as dc_mod
from cmd import doccommands as dcmd_mod
from cmd import docaudit as da_mod
from cmd import docpaths as dp_mod
from cmd import vocab as voc_mod

def _ver(s):
    try:
        return tuple(int(x) for x in str(s).split("."))
    except (TypeError, ValueError):
        return (0,)


def doc_staleness(root):
    """Out-of-date product-documentation signals that need no opt-in frontmatter
    (unlike derived_doc_drift, which only catches docs that DECLARED what they
    track). Deterministic, advisory: checks that every entrypoint / reading-order
    path the manifest names still exists — a dangling one means a doc moved out
    from under the manifest and the manifest prose is stale. (The stricter
    version-coherence gate — manifest vs CHANGELOG — is a HARD error in `certify`,
    not an advisory here, since a version mismatch is a release-integrity break.)
    """
    try:
        import yaml
    except ImportError:
        return ["doc-staleness: PyYAML unavailable — skipped"]
    out = []
    manifest = os.path.join(root, "SYSTEM-MANIFEST.yaml")
    if not os.path.exists(manifest):
        return out
    try:
        with open(manifest, encoding="utf-8") as f:
            man = yaml.safe_load(f) or {}
    except Exception as e:
        return [f"doc-staleness: SYSTEM-MANIFEST.yaml failed to parse: {e}"]
    # manifest entrypoints / reading_order must point to files that exist
    referenced = []
    ep = man.get("entrypoints") or {}
    if isinstance(ep, dict):
        referenced += [v for v in ep.values() if isinstance(v, str)]
    for group in (man.get("reading_order") or {}).values():
        if isinstance(group, list):
            referenced += [v for v in group if isinstance(v, str)]
    for rel in sorted(set(referenced)):
        if not os.path.exists(os.path.join(root, rel)):
            out.append(f"[doc-staleness] manifest references a missing file: {rel} "
                       f"(doc moved/renamed — manifest is stale)")
    return out

def derived_doc_drift(root):
    """Derived docs that recorded the source version they were written against
    (frontmatter `x_reviewed_against: ["source-id:version", ...]`) and have since
    fallen BEHIND that source's current version. Advisory only — the prose needs a
    human/AI refresh; facts self-update via `aios generate`, prose is NEVER
    auto-rewritten (DEC-039 Phase 2). Returns (doc_id, source_id, reviewed, current).

    Sources declared in YAML seed the version map first (DEC-105): `op-registry`
    is `operations.yaml`, which `iter_markdown` never sees, so the Operations
    Guide's stamp resolved to `None` and was skipped in silence for every release
    since it was written. `validate` now errors on a stamp that cannot resolve at
    all; this is the other half — resolving the ones that legitimately can."""
    from .validate import registry_versions
    versions = {k: v[0] for k, v in registry_versions(root).items()}
    marked = []
    for n in iter_markdown(root):
        if n.error:
            continue
        cid = n.meta.get("id")
        if cid and n.meta.get("version") is not None:
            versions[str(cid)] = str(n.meta["version"])
        ra = n.meta.get("x_reviewed_against")
        if ra:
            marked.append((n, ra))
    behind = []
    for n, ra in marked:
        entries = ra.items() if isinstance(ra, dict) else (
            e.rsplit(":", 1) for e in ra if isinstance(e, str) and ":" in e)
        for src, rec in entries:
            src, rec = str(src).strip(), str(rec).strip()
            cur = versions.get(src)
            if cur and _ver(rec) < _ver(cur):
                behind.append((str(n.meta.get("id")), src, rec, cur))
    return behind

STALE_GEN_DAYS = 10   # weekly maintenance + buffer; older generated state = time to rebuild
INBOX_STALE_DAYS = 14  # the >14-day triage rule, now a computed health line
# The detector for import-minted project stubs (SPEC-import-review-queue):
# `aios import` writes this exact sentence into every stub summary. Counting on
# the marker keeps the finding scoped to import's own output — a hand-made
# project without a stage is none of this check's business.
IMPORT_STUB_MARKER = "Stage not set — owner to review"


def inbox_ages(root, today):
    """(count over window, oldest age in days) for real Inbox items. Age comes
    from frontmatter `created` when parseable (deterministic, survives clones),
    else file mtime (covers non-markdown drops). _-prefixed and dotfiles skipped."""
    top = os.path.join(root, "00 Inbox")
    if not os.path.isdir(top):
        return 0, 0
    created_by_path = {}
    for n in iter_markdown(root):
        if n.relpath.startswith("00 Inbox") and not n.error:
            c = str(n.meta.get("created", ""))
            if len(c) >= 10:
                created_by_path[os.path.normpath(n.relpath)] = c[:10]
    t = datetime.date.fromisoformat(today)
    over, oldest = 0, 0
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if fn.startswith(("_", ".")):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.normpath(os.path.relpath(p, root))
            c = created_by_path.get(rel)
            try:
                born = (datetime.date.fromisoformat(c) if c else
                        datetime.date.fromtimestamp(os.path.getmtime(p)))
            except (ValueError, OSError):
                continue
            age = (t - born).days
            if age > INBOX_STALE_DAYS:
                over += 1
                oldest = max(oldest, age)
    return over, oldest


def generated_tamper(root):
    """Generated files whose content no longer matches what the last
    `aios generate` recorded (System/Generated/.digests.json) — i.e. hand
    edits to machine-owned state, which the next generate will silently
    destroy. Silent when no digest record exists (feature activates on the
    next generate; rollback-clean). Returns a sorted list of relpaths."""
    from cmd.generate import generated_digests, DIGESTS_NAME
    import json as _json
    p = os.path.join(root, "System", "Generated", DIGESTS_NAME)
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as stream:
            stored = (_json.load(stream) or {}).get("files", {})
    except (OSError, ValueError):
        return ["<.digests.json unreadable — re-run `aios generate`>"]
    current = generated_digests(root)
    return sorted(set(k for k in set(stored) | set(current)
                      if stored.get(k) != current.get(k)))

def generated_age_days(root):
    """Days since `aios generate` last rebuilt the generated docs, read from the
    generated_at stamp on implementation-status.md. None if never generated.
    This is the self-monitoring half of the 'keep everything current' loop: facts
    self-update when generate runs; this tells you when a generate is overdue."""
    p = os.path.join(root, "System", "Generated", "implementation-status.md")
    try:
        with open(p, encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("generated_at:"):
                    when = datetime.datetime.fromisoformat(line.split(":", 1)[1].strip())
                    now = datetime.datetime.now(when.tzinfo) if when.tzinfo else datetime.datetime.now()
                    return (now - when).days
    except (OSError, ValueError):
        return None
    return None

def user_privacy_missing(root):
    """On a PERSONAL INSTANCE, the user's privacy-rules file (created at onboarding
    stage 2, matching `80 User/privacy*`) should exist. The generic-master correctly
    ships without it (clean seed), and disposable test scaffolds are exempt. Returns a
    warning string if a personal instance is missing it, else None.

    Advisory, not fatal: a missing file falls back to the always-present
    `System/Governance/Privacy and Boundaries.md` defaults (private-by-default per
    `80 User/_ABOUT.md`), so privacy still holds conservatively meanwhile. This is the
    instance-side counterpart to certify's master-side handling — certify does not
    require the file on the master; health verifies a real instance actually got it."""
    import glob as _glob
    try:
        import yaml
    except ImportError:
        return None
    manifest = os.path.join(root, "SYSTEM-MANIFEST.yaml")
    if not os.path.exists(manifest):
        return None
    try:
        with open(manifest, encoding="utf-8") as f:
            man = yaml.safe_load(f) or {}
    except Exception:
        return None
    role = str(((man.get("system") or {}).get("instance_role") or "")).strip()
    if role != "personal-instance":
        return None  # generic-master and test/rehearsal scaffolds are exempt by design
    if _glob.glob(os.path.join(root, "80 User", "privacy*")):
        return None
    return ("[privacy] personal instance has no 80 User/privacy-rules file — onboarding "
            "stage 2 may be incomplete; conservative governance defaults apply until it exists")


BACKUP_MARKER = os.path.join("80 User", "LAST-BACKUP.txt")
BACKUP_STALE_DAYS = 30   # default staleness window; tunable via `window_days:` in the marker
_BACKUP_SKIP = {".git", ".obsidian", "node_modules"}

def backup_evidence(root):
    """Does content that exists ONLY on this machine have any recorded off-machine
    copy? (SPEC-backup-onboarding.) Counts sync-excluded records — any `Local Only`
    path segment (the DEC-065 marking) plus markdown carrying `ai_use: local-only` —
    then reads the evidence marker `80 User/LAST-BACKUP.txt`, written by
    `System/Scripts/backup-clone.sh` at the end of a successful run or touched
    manually after any copy (the one-line command is in Backup and Recovery
    Options.md).

    Never a false positive (the spec's hard fence): no marker = never, period; a
    malformed marker counts as never; and a readable marker is evidence of THAT
    recorded run only, worded as such. A finding, not an error — health informs,
    the human decides. Returns (local_only_count, last_iso_date|None,
    age_days|None, window_days, problems)."""
    from cmd.search import LOCAL_ONLY_DIR
    counted, count = set(), 0
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath == root:
            # user content only: the product's own internals (System/ carries
            # privacy-fixture material by design; Packs/ is install-managed)
            # are never the user's unbacked knowledge.
            dirnames[:] = [d for d in dirnames if d not in ("System", "Packs")]
        dirnames[:] = [d for d in dirnames if d not in _BACKUP_SKIP and not d.startswith(".")]
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if any(seg.strip().lower() == LOCAL_ONLY_DIR for seg in rel_dir.split("/")):
            for f in filenames:
                if not f.startswith("."):
                    counted.add(rel_dir + "/" + f); count += 1
    for n in iter_markdown(root):
        if n.error:
            continue
        rel = n.relpath.replace(os.sep, "/")
        if rel.startswith(("System/", "Packs/")):
            continue
        if (str(n.meta.get("ai_use", "")).strip() == "local-only"
                and rel not in counted):
            count += 1
    last, age, window, problems = None, None, BACKUP_STALE_DAYS, []
    marker = os.path.join(root, BACKUP_MARKER)
    if os.path.exists(marker):
        try:
            with open(marker, encoding="utf-8") as stream:
                for line in stream:
                    if line.startswith("last_backup:"):
                        raw = line.split(":", 1)[1].strip()
                        when = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        now = datetime.datetime.now(when.tzinfo) if when.tzinfo else datetime.datetime.now()
                        last, age = raw, max(0, (now - when).days)
                    elif line.startswith("window_days:"):
                        window = int(line.split(":", 1)[1].strip())
        except (OSError, ValueError):
            last, age = None, None   # unreadable evidence is NOT evidence
            problems.append(f"[backup] {BACKUP_MARKER.replace(os.sep, '/')} exists but its "
                            f"last_backup date is unreadable — treated as never; rewrite it "
                            f"(format: `last_backup: 2026-07-25T12:00:00Z`)")
        if os.path.exists(marker) and last is None and not problems:
            problems.append(f"[backup] {BACKUP_MARKER.replace(os.sep, '/')} exists but has no "
                            f"`last_backup:` line — treated as never")
    return count, last, age, window, problems


def run(root, args, rep: Report):
    # Scope is part of the verdict.  Health describes one tree's present state;
    # it is not source certification, runtime certification, or a release gate.
    rep.info.setdefault(
        "verdict_scope",
        "INSTANCE HEALTH — current installed-tree integrity and advisories only",
    )
    # vocab rides the composite so the banned-term guard runs whenever health does
    # (determinism audit I-2: it was mandated by no procedure surface, so it ran
    # only on memory). Unconfigured instances no-op; violations stay warnings.
    for name, mod in [("validate", v_mod), ("links", l_mod), ("dupes", d_mod),
                      ("doc-check", dc_mod), ("doc-commands", dcmd_mod),
                      ("doc-audit", da_mod), ("doc-paths", dp_mod),
                      ("vocab", voc_mod)]:
        sub = Report(name); mod.run(root, args, sub)
        rep.info[name] = f"{len(sub.errors)} errors, {len(sub.warnings)} warnings"
        rep.errors += [f"[{name}] {e}" for e in sub.errors]
        rep.warnings += [f"[{name}] {w}" for w in sub.warnings]
    today = datetime.date.today().isoformat()
    from lib.vaultpaths import rel_folder
    _knowledge = rel_folder(root, "knowledge", "20 Knowledge")
    review_due, inbox, unverified_canon = 0, 0, 0
    stub_overdue, stub_oldest = 0, None
    for n in iter_markdown(root):
        rd = str(n.meta.get("review_due", ""))
        if rd and rd <= today:
            review_due += 1
        # Import review queue (SPEC-import-review-queue): ONLY import-minted
        # stubs — the marker sentence is the detector, so ordinary stage-less
        # projects never flood this. Overdue = past review_due, or minted
        # before the feature existed and never stamped (the six-live-stubs
        # defect this spec opened with). One rolled-up finding, below.
        if (n.meta.get("type") == "project"
                and IMPORT_STUB_MARKER in str(n.meta.get("summary", ""))
                and (not rd or rd <= today)):
            stub_overdue += 1
            key = rd or str(n.meta.get("created", "")) or "?"
            if stub_oldest is None or key < stub_oldest:
                stub_oldest = key
        if n.relpath.startswith("00 Inbox") and not os.path.basename(n.relpath).startswith("_"):
            inbox += 1
        # Canonical-core doctrine (Principle 26): a note filed in the canon folder,
        # presented as active but never actually verified, is staging masquerading as
        # knowledge. Advisory count for the weekly checkup — not an error; promotion is
        # a judgment the human/Steward completes, never an automatic flip.
        if (n.relpath.startswith(_knowledge) and n.meta.get("type") == "note"
                and str(n.meta.get("status", "")) == "active"
                and str(n.meta.get("verification", "")).strip() in ("", "unverified")):
            unverified_canon += 1
    rep.info["review_due"] = review_due
    rep.info["inbox_items"] = inbox
    rep.info["unverified_in_knowledge"] = unverified_canon
    if stub_overdue:
        rep.info["import_stubs_unreviewed"] = stub_overdue
        rep.warn(f"[import-review] {stub_overdue} imported project(s) have never been reviewed "
                 f"(oldest: {stub_oldest}) — set the stage, confirm contents, or archive; "
                 f"see `aios review-due`")
    # Per-item Inbox age (determinism-audit finding 4): the count above says how
    # many; this says how long — an item sitting past the triage window is the
    # 'nothing turns itself on' failure in miniature. Rolled-up, warning only.
    old_items, oldest_days = inbox_ages(root, today)
    if old_items:
        rep.info["inbox_items_over_window"] = old_items
        rep.warn(f"[inbox] {old_items} Inbox item(s) older than {INBOX_STALE_DAYS} days "
                 f"(oldest: {oldest_days}d) — run process-inbox-item; the Inbox is a "
                 f"loading dock, not storage")
    # pack-check (DEC-113): pack CONTENT is invisible to validate/links/dupes by
    # design (DEC-061/067), which on a pack-heavy vault left the majority of the
    # markdown outside every mechanical check. Composed here so `certify`'s
    # health gate carries it. It reads each pack in its own namespace and merges
    # nothing — the checks above see exactly what they saw before.
    from cmd import packcheck as pc_mod
    pc = Report("pack-check")
    pc_mod.run(root, args, pc)
    if pc.info.get("packs_checked"):
        rep.info["pack-check"] = f"{len(pc.errors)} errors, {len(pc.warnings)} warnings"
        rep.errors += [f"[pack-check] {e}" for e in pc.errors]
        # Warnings roll UP as one line rather than flooding health with a pack's
        # every missing README frontmatter — the count is the signal; `aios
        # pack-check` is where the detail lives.
        if pc.warnings:
            rep.warn(f"[pack-check] {len(pc.warnings)} advisory finding(s) across "
                     f"{len(pc.info['packs_checked'])} installed pack(s) — run "
                     f"`aios pack-check` for the detail")

    dg = Report("docgen")
    class _DGCheck:
        check = True
    from cmd import docgen as dg_mod
    dg_mod.run(root, _DGCheck(), dg)
    rep.info["docgen"] = f"{len(dg.errors)} errors"
    rep.errors += [f"[docgen] {e}" for e in dg.errors]

    behind = derived_doc_drift(root)
    rep.info["derived_docs_behind"] = len(behind)
    for doc, src, rec, cur in behind:
        rep.error(f"[doc-freshness] {doc} was reviewed against {src} v{rec}, now v{cur} — "
                  f"re-read it against the new source and re-stamp (DEC-069 enforced)")
    stale = doc_staleness(root)
    rep.info["doc_staleness_flags"] = len(stale)
    for msg in stale:
        rep.warn(msg)
    privacy_gap = user_privacy_missing(root)
    if privacy_gap:
        rep.info["user_privacy_file"] = "MISSING (personal instance)"
        rep.warn(privacy_gap)
    # Knowledge freshness (SPEC-knowledge-freshness): ripple triage, review
    # horizons, workflow cadence. All warnings at ship (owner D5 — the error
    # flip is a later release, gated on live vaults running clean); all
    # rolled-up counts only, so no note ids cross the privacy floor here.
    # Registry absent = feature absent = silent skip (rollback-clean).
    # A null epoch means installed-but-not-activated: the generic master ships
    # that way (instance state never ships in the product); an instance's first
    # `aios generate` stamps its own epoch and activation begins there.
    from lib import freshness as fr
    f_reg = fr.load_registry(root)
    if f_reg is not None and not fr.epoch(f_reg):
        rep.info["freshness"] = "installed, not yet activated (epoch stamps on first `aios generate`)"
    if f_reg is not None and fr.epoch(f_reg):
        f_notes = fr.scan(root)
        f_ch, f_unseen = fr.changed(root, f_notes)
        if f_unseen and not fr.load_ledger(root):
            rep.warn(f"[freshness] ledger not initialized ({len(f_unseen)} notes unbaselined) — "
                     f"run `aios generate` (or `aios ripple --baseline-all`)")
        else:
            f_pend = fr.pending(root, f_notes)
            rep.info["ripple_pending"] = len(f_pend)
            if f_pend:
                rep.warn(f"[freshness] {len(f_pend)} neighbor(s) of {len(f_ch)} changed note(s) "
                         f"awaiting ripple triage — see `aios ripple`")
        f_miss = fr.horizon_missing(root, f_reg, f_notes)
        rep.info["review_horizon_missing"] = len(f_miss)
        if f_miss:
            rep.warn(f"[freshness] {len(f_miss)} promoted note(s) have no review_due — "
                     f"run `aios review-due --set-missing`")
        f_over = [(w, c, l) for w, c, l, o in fr.workflow_status(root, f_reg) if o]
        rep.info["workflows_overdue"] = len(f_over)
        for wid, cad, last in f_over:
            rep.warn(f"[freshness] workflow '{wid}' last ran {last or 'never'} "
                     f"(cadence {cad}d — overdue)")
    # Backup evidence (SPEC-backup-onboarding): content that never syncs must not
    # be silently unprotected. Fires only when local-only content exists, so the
    # generic master and clean scaffolds stay silent. Warning, never error.
    b_count, b_last, b_age, b_window, b_problems = backup_evidence(root)
    for msg in b_problems:
        rep.warn(msg)
    if b_count:
        rep.info["local_only_files"] = b_count
        if b_last is None:
            rep.info["backup_evidence"] = "never"
            rep.warn(f"[backup] {b_count} file(s) marked local-only exist on this machine "
                     f"only — no off-machine copy recorded; last recorded backup: never "
                     f"(see System/Documentation/Backup and Recovery Options.md)")
        elif b_age is not None and b_age > b_window:
            rep.info["backup_evidence"] = f"stale — last recorded backup {b_last} ({b_age}d ago)"
            rep.warn(f"[backup] last recorded backup was {b_last} ({b_age} days ago, window "
                     f"{b_window}d) — {b_count} local-only file(s) may have changed since; "
                     f"re-run System/Scripts/backup-clone.sh or update the marker after your "
                     f"next copy")
        else:
            rep.info["backup_evidence"] = (f"last recorded backup {b_last} ({b_age}d ago; "
                                           f"evidence of that run only)")
    elif b_last is not None:
        rep.info["backup_evidence"] = (f"last recorded backup {b_last} ({b_age}d ago; "
                                       f"evidence of that run only)")
    gen = os.path.join(root, "System", "Generated")
    rep.info["generated_state"] = "present" if os.path.isdir(gen) and os.listdir(gen) else "empty (run: aios generate)"
    # Generated-tamper check (determinism-audit finding 4): hand edits to
    # machine-owned files are lost work waiting to happen — the next generate
    # overwrites them without a trace. Warning, not error: health informs.
    tampered = generated_tamper(root)
    if tampered:
        rep.info["generated_tampered"] = len(tampered)
        shown = ", ".join(tampered[:6]) + (f" … +{len(tampered) - 6} more" if len(tampered) > 6 else "")
        rep.warn(f"[generated-tamper] {len(tampered)} generated file(s) differ from the last "
                 f"`aios generate` output ({shown}) — generated state is disposable and hand "
                 f"edits will NOT survive; move real content to its canonical source, then "
                 f"re-run `aios generate`")
    age = generated_age_days(root)
    if age is not None:
        rep.info["generated_docs_age_days"] = age
        if age > STALE_GEN_DAYS:
            rep.warn(f"[doc-freshness] generated docs last rebuilt {age} days ago — run `aios generate` to refresh them")
    return rep
