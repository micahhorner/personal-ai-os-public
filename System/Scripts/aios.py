#!/usr/bin/env python3
"""aios — deterministic utilities for the Personal AI OS vault.

Usage: python3 System/Scripts/aios.py <command> [options]
Commands: validate | links | dupes | dedupe-batch | checkpoint | rollback | health
          | source-check | instance-health | runtime-certify | checkup | generate
          | scaffold | migrate | import | extract | upgrade
          review-due | search | read | vocab | doc-check | doc-commands | doc-audit
          doc-paths | docgen | certify | okf-check | okf-export | okf-import
          pack | pack-check
          measure | ripple | workflow | resolve | pack
          (the authority is the argparse `choices` below, which `aios doc-commands`
           reads by AST; this list is a courtesy and had drifted three short)
Vault-writing commands honor the kill switch (runtime.ai_writes_enabled).
Checkpoint creation is deliberately exempt: you can always save state.
"""
from __future__ import annotations
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.vaultpaths import find_root
from lib.report import Report

def main(argv=None):
    p = argparse.ArgumentParser(prog="aios", description=__doc__)
    p.add_argument("command", choices=["validate", "links", "dupes", "dedupe-batch",
                                       "checkpoint", "rollback", "health", "checkup",
                                       "source-check", "instance-health", "runtime-certify",
                                       "generate", "scaffold", "migrate", "import",
                                       "extract", "upgrade",
                                       "review-due", "search", "read", "vocab",
                                       "doc-check", "doc-commands", "doc-audit",
                                       "doc-paths", "certify", "okf-check",
                                       "okf-export", "okf-import", "measure",
                                       "ripple", "workflow", "docgen", "resolve", "pack",
                                       "pack-check"])
    p.add_argument("target", nargs="?", help="rollback: checkpoint ref or snapshot zip; "
                   "upgrade: path to the new release; "
                   "okf-check: directory to verify (default: the knowledge layer plus "
                   "every installed pack's content); "
                   "okf-export: folder id to emit (default: knowledge); "
                   "okf-import: path to an OKF bundle; "
                   "measure: path to the transcript to measure; "
                   "extract: path to the .docx to convert; "
                   "dedupe-batch: the intake folder, or a comma-separated file list; "
                   "runtime-certify: optional contained runtime-profile path")
    # No argparse `choices=` here on purpose: the command positional above is the
    # ONE `choices` list `doc-commands` and `docgen` read out of this file by AST,
    # and a second one is an ambiguity waiting to pick the wrong list. The version
    # is validated inside the commands, which can also say what they do support.
    p.add_argument("--okf-version", dest="okf_version",
                   help="okf-check / okf-export: which Open Knowledge Format spec version to "
                        "check against or emit (default 0.2, the current published spec)")
    p.add_argument("--author", help="okf-export: the OKF actor (§7 — human:<id>, process:<id>, "
                        "or <producer>/<version>) to record as `generated.by` on every exported "
                        "concept. Omitted, no `generated` is emitted, because this vault does "
                        "not record who wrote a note")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument(
        "--source-authority-repository",
        dest="source_authority_repository",
        help="source-check: separate Git repository carrying the historical objects "
             "required by strict regression tests (never emitted in evidence)",
    )
    p.add_argument(
        "--source-authority-commit",
        dest="source_authority_commit",
        help="source-check: full lowercase commit pin for the separate historical "
             "authority repository",
    )
    p.add_argument("--message", "-m", help="checkpoint label")
    p.add_argument("--rollback", help="checkpoint ref or snapshot zip to restore")
    p.add_argument("--confirm", action="store_true",
                   help="confirm destructive action; upgrade: confirm the exact reviewed semantic plan")
    p.add_argument("--clean", action="store_true", help="rollback: also remove files created after the checkpoint")
    p.add_argument(
        "--expected-sha256",
        dest="expected_sha256",
        help="rollback: exact checkpoint tree/archive SHA-256 printed by checkpoint",
    )
    p.add_argument("--zip", action="store_true", dest="force_zip",
                   help="checkpoint: also write a human-restorable zip snapshot even when git is present")
    p.add_argument("--zip-only", action="store_true", dest="zip_only",
                   help="checkpoint: write ONLY the zip snapshot — no git commit (safe on a tree with unready work)")
    p.add_argument("--paths", nargs="+", metavar="PATH",
                   help="checkpoint: commit ONLY these paths (files or directories); "
                        "everything else is left uncommitted and reported")
    p.add_argument("--strict", action="store_true",
                   help="checkpoint: refuse (do not commit) when the tree carries changes "
                        "outside --paths — for automation on a tree it does not own")
    p.add_argument("--root", help="vault root (default: auto-detect)")
    p.add_argument("--type", help="scaffold: component type")
    p.add_argument("--name", help="scaffold: component name (kebab-case)")
    p.add_argument("--register", help="scaffold: activate a draft component by id")
    p.add_argument("--migration", help="migrate: which migration to run")
    p.add_argument("--plan", help="import: which System/Migrations/<NNN-name> plan to run")
    p.add_argument("--allow-secret-flags", action="store_true", dest="allow_secret_flags",
                   help="import: apply despite owner-reviewed secret-pattern hits")
    p.add_argument("--review-days", type=int, dest="review_days",
                   help="import: review_due horizon for minted project stubs "
                        "(default 14, or the plan's review_after_days)")
    p.add_argument("--apply", action="store_true",
                   help="migrate: apply (default dry-run); docgen: apply an exact reviewed protected batch; "
                        "upgrade: enter the reviewed checkpoint/candidate transaction")
    p.add_argument("--query", help="search: text to find")
    p.add_argument("--domain", help="search/read: required task domain (work|personal|shared); "
                                    "missing or invalid values fail closed")
    p.add_argument("--all-states", action="store_true", dest="all_states",
                   help="search: include inbox/archive/draft/stale/superseded records (default: current knowledge only)")
    p.add_argument("--project",
                   help="search: scope to one project's folder under the projects layer and "
                        "include its working material (type: working), which default search excludes")
    p.add_argument("--id", help="read: stable id")
    p.add_argument("--check", action="store_true", help="docgen: verify blocks are current without writing")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="upgrade: explicit alias for the default read-only semantic review; "
                        "extract: convert and verify only — emit nothing")
    p.add_argument("--annotate", action="store_true",
                   help="dedupe-batch: after the human's decision, write the overlap map "
                        "into the frontmatter of every file still in the batch "
                        "(bodies are never touched)")
    p.add_argument("--base", help="upgrade: old release tree or baseline json for exact "
                                  "classification when the instance predates baselines")
    p.add_argument("--make-baseline", action="store_true", dest="make_baseline",
                   help="upgrade: (product master only) record the release's pristine file hashes")
    p.add_argument("--accept", action="append", metavar="PATH",
                   help="upgrade: a protected-path conflict you have REVIEWED and chosen to "
                        "keep as-is; repeatable. The file is still never merged or "
                        "overwritten — this records that a human decided, so the conflict "
                        "stops blocking the version bump (DEC-111)")
    p.add_argument(
        "--authorize-legacy-core", action="store_true",
        dest="authorize_legacy_core",
        help="upgrade: one-run authorization for an unlabelled legacy Personal AI OS "
             "source; requires an exact allowlisted source identity in the updater's "
             "frozen historical allowlist and refuses PMM markers")
    p.add_argument("--terms", help="measure: comma-separated terms to trace to their first speaker")
    p.add_argument("--extract", help="measure: write the human's turns, in isolation, to this path")
    p.add_argument("--ack", help="ripple: record a disposition for this neighbor id")
    p.add_argument("--from", dest="from_id", help="ripple: the changed note the disposition answers")
    p.add_argument("--effect", help="ripple: one of the registry's dispositions (e.g. no-impact, makes-stale)")
    p.add_argument("--all", action="store_true", dest="ack_all",
                   help="ripple: with --ack, disposition every pending neighbor of --from at once")
    p.add_argument("--refs", help="ripple: read-only sweep for a literal name (old path/id/filename) "
                   "across operational surfaces — the rename-time reference check")
    p.add_argument("--mint", action="store_true",
                   help="resolve: also propose the <type>-<slug> id and F-6-sanitized filename")
    p.add_argument("--verify", action="store_true",
                   help="pack: read-only manifest gate + install/update plan (the default)")
    p.add_argument("--review-sha256", dest="review_sha256",
                   help="pack/docgen/upgrade --apply: exact review hash printed by the read-only review step")
    p.add_argument("--remove", action="store_true", dest="remove_pack",
                   help="pack: uninstall Packs/<name>/ — vendor scaffold is deleted, and any "
                        "user-owned workspace/seed content the pack declared is ARCHIVED to "
                        "90 Archive/packs/<name>-<date>/, never deleted (DEC-112)")
    p.add_argument("--purge", action="store_true",
                   help="pack: with --remove, DELETE the whole pack folder including the "
                        "user's own workspace content — the only route to the pre-DEC-112 "
                        "behaviour; needs --confirm and prints the file count it will take")
    p.add_argument("--baseline", help="ripple: accept this changed note's content as the new reference")
    p.add_argument("--baseline-all", action="store_true", dest="baseline_all",
                   help="ripple: baseline unseen notes and accept every pending change")
    p.add_argument("--ran", help="workflow: record that this workflow id completed a run today")
    p.add_argument("--set-missing", action="store_true", dest="set_missing",
                   help="review-due: stamp review_due on active post-epoch notes missing one")
    args = p.parse_args(argv)
    root = os.path.abspath(args.root) if args.root else find_root()
    cmd = args.command
    # Centralized kill switch (H-05): every vault-content-writing command is
    # denied while runtime.ai_writes_enabled is false. checkpoint (snapshot
    # creation) is deliberately allowed: it preserves content, never changes it.
    # okf-export writes a bundle into the outputs folder; okf-import writes
    # source notes. Both put content in the vault, so both are gated.
    # (okf-check is read-only and deliberately not gated.)
    # extract joins unconditionally, on upgrade's precedent: it emits Markdown and
    # files the original, and its --dry-run form simply writes nothing anyway.
    WRITE_COMMANDS = {"generate", "scaffold", "migrate", "import", "rollback",
                      "okf-export", "okf-import", "extract"}
    # Recovery exception (final audit H-07): rollback with --confirm is an
    # explicitly human-authorized recovery act — the kill switch exists to stop
    # AI writing, not to lock the human out of restoring their own vault.
    # freshness commands write only in their flagged forms (SPEC §8); the
    # modules re-check, this is the same centralized gate every writer passes
    if cmd == "ripple" and (args.ack or args.baseline or args.baseline_all):
        WRITE_COMMANDS = WRITE_COMMANDS | {"ripple"}
    if cmd == "pack" and (args.apply or args.remove_pack):
        WRITE_COMMANDS = WRITE_COMMANDS | {"pack"}
    if cmd == "upgrade" and (
            args.apply or (args.make_baseline and not args.dry_run)):
        WRITE_COMMANDS = WRITE_COMMANDS | {"upgrade"}
    # dedupe-batch is a report; only its --annotate form writes (frontmatter only)
    if cmd == "dedupe-batch" and args.annotate:
        WRITE_COMMANDS = WRITE_COMMANDS | {"dedupe-batch"}
    if cmd == "workflow" and args.ran:
        WRITE_COMMANDS = WRITE_COMMANDS | {"workflow"}
    if cmd == "review-due" and args.set_missing:
        WRITE_COMMANDS = WRITE_COMMANDS | {"review-due"}
    if cmd == "measure" and args.extract:
        WRITE_COMMANDS = WRITE_COMMANDS | {"measure"}
    if cmd == "docgen" and not args.check:
        WRITE_COMMANDS = WRITE_COMMANDS | {"docgen"}
    if cmd == "rollback" and args.confirm:
        pass
    elif cmd in WRITE_COMMANDS:
        from lib.vaultpaths import ai_writes_enabled
        if not ai_writes_enabled(root):
            rep = Report(cmd)
            rep.error("kill switch is off (runtime.ai_writes_enabled: false) — refusing to write. "
                      "Humans can restore by hand: see Maintenance and Recovery Guide Part 3.")
            return rep.emit(as_json=args.json)
    if cmd == "review-due":
        cmd = "review_due"
    if cmd == "dedupe-batch":
        cmd = "dedupebatch"
    if cmd == "doc-check":
        cmd = "doccheck"
    if cmd == "doc-commands":
        cmd = "doccommands"
    if cmd == "docgen":
        cmd = "docgen"
    if cmd == "doc-audit":
        cmd = "docaudit"
    if cmd == "doc-paths":
        cmd = "docpaths"
    if cmd == "source-check":
        cmd = "sourcecheck"
    if cmd == "instance-health":
        cmd = "instancehealth"
    if cmd == "runtime-certify":
        cmd = "runtimecertify"
    if cmd == "okf-check":
        cmd = "okfcheck"
    if cmd == "pack-check":
        cmd = "packcheck"
    if cmd == "import":
        cmd = "import_vault"
    if cmd == "okf-export":
        cmd = "okfexport"
    if cmd == "okf-import":
        cmd = "okfimport"
    if cmd == "read":
        cmd = "read_note"
    if cmd == "rollback":
        target = args.target or args.rollback
        if not target:   # destructive commands never guess their target
            rep = Report(cmd)
            rep.error("rollback needs an explicit target: aios rollback <ref|snapshot.zip> --confirm "
                      "(find refs with 'git log --oneline'; zips live in the Snapshots folder)")
            return rep.emit(as_json=args.json)
        cmd, args.rollback = "checkpoint", target
    mod = __import__(f"cmd.{cmd}", fromlist=["run"])
    rep = Report(args.command)
    mod.run(root, args, rep)
    return rep.emit(as_json=args.json)

if __name__ == "__main__":
    raise SystemExit(main())
