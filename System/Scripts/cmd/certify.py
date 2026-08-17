"""Compatibility source check (historically named ``certify``).

Certification composite (Layer 3, see CHECK-MAP.md). It REUSES rather than
re-implements:
  - mechanical integrity  -> delegates to `aios health` (validate/links/dupes/
                             doc-check + freshness). Single source of truth.
  - vocabulary            -> runs `vocab` (health omits it).
It then adds only the certification-specific assertions nothing else covers:
  - governance/safety     : kill switch enforced; protected_objects exist and
                            include System/Agents; NO personal data in the
                            generic master (PII scan — a MASTER-ONLY invariant,
                            and gated on instance_role since v1.49.0: a personal
                            instance legitimately holds PII, so the scan does not
                            run there. It used to run everywhere, which made
                            certification unreachable on any real vault).
  - command-idempotency   : `aios generate` run twice yields identical derived
                            state (volatile timestamps normalized out).
  - release-records       : the manifest authority, package/baseline mirrors,
                            baseline identity, and role-scoped changelog records
                            must be coherent.
  - regression            : runs the unittest suite as a gate.

This command does not certify an AI runtime and does not qualify a release.
``aios source-check`` is its scope-honest name; ``aios certify`` remains a
compatibility alias for one release and emits the same SOURCE CHECK verdict.

Emits a ranked report to stdout (and `--json`), exactly like every other aios
command — it writes NO live-vault files. The idempotency probe copies a safely
bound read-only snapshot to a disposable directory and runs both generations
there. It never runs generate against the live tree and never restores over it;
if the source changes during the probe, certification reports that the result is
not reliable and leaves the concurrent edit untouched.

Deliberately does NOT check component contracts / frontmatter — `aios validate`
already owns those (component_type, required fields, active-needs-tests, and the
agent-can't-write-own-contract rule). Duplicating them was removed 2026-07-13.
"""
from __future__ import annotations
import os, re, sys, tempfile, hashlib, subprocess
from lib.report import Report
from lib.safepaths import SafePathError, open_readonly_tree
from lib.version_records import audit_version_records
from cmd import health as health_mod, vocab as vc_mod

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _read(path):
    """Read a file fully, closing the handle; '' if absent/unreadable."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules"}
# Tests legitimately carry PII-shaped fixtures (that is their job); the PII scan
# skips them along with derived/log state. Real product content is still scanned.
SKIP_REL = {os.path.join("System", "Generated"), os.path.join("System", "Logs"),
            os.path.join("System", "Tests")}
SCAN_EXT = {".md", ".py", ".yaml", ".yml", ".txt", ".json"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PII_ALLOW_FILES = {"LICENSE.md"}                    # owner copyright excepted by design
PII_ALLOW_EMAILS = {"noreply@anthropic.com", "you@example.com",
                    "user@example.com", "name@example.com", "someone@example.com"}
VOLATILE_RE = re.compile(r'("?generated_at"?\s*[:=].*|"?mtime"?\s*[:=].*)')

# Instance state `aios generate` writes OUTSIDE System/Generated. The idempotency
# probe runs `generate` twice, so these must be preserved and restored with it or
# certify is not the read-only command its docstring promises. (The generic master
# never activates freshness — which is exactly why this escaped notice until a
# read-only audit mutated a personal instance's tracked ledger.)
PROBE_SKIP_DIRS = {".git", ".trash", "node_modules"}
PROBE_MAX_FILE_BYTES = 256 * 1024 * 1024
PROBE_MAX_TOTAL_BYTES = 512 * 1024 * 1024
PROBE_TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".py", ".svg"}
PROBE_STATE_INPUTS = {
    "System/Logs/freshness-ledger.json",
    "System/Logs/freshness-log.jsonl",
    "System/Registries/freshness.yaml",
}


def _probe_input(rel: str) -> bool:
    """Files generate can execute or observe; binary attachments stay outside."""
    norm = rel.replace("\\", "/")
    parts = norm.split("/")
    if norm in PROBE_STATE_INPUTS:
        return True
    if parts[0] == "Packs":
        return True  # pack activation hashes every member, including resources
    if norm.startswith(("System/Generated/", "System/Logs/", "System/Tests/")):
        return False
    if parts[0] in (".obsidian", ".git", ".trash", "node_modules"):
        return False
    return os.path.splitext(parts[-1])[1].lower() in PROBE_TEXT_EXTENSIONS


def _probe_monitor(rel: str) -> bool:
    """Inputs plus live derived state the old probe could have overwritten."""
    norm = rel.replace("\\", "/")
    return _probe_input(norm) or norm.startswith("System/Generated/")


def _is_master(root) -> bool:
    """Is this vault the generic master (the product), or a user's instance?

    Master-only invariants must not fire on a personal instance — the same
    scoping doctrine `doc-check`, `doc-paths` and `doc-audit` already apply
    (DEC-083), and the same reason DEC-082 gives: a lived-in vault never goes
    red on the user's own content. An unreadable/absent manifest means a test
    scaffold or a product context: stay strict."""
    if not yaml:
        return True
    try:
        man = yaml.safe_load(_read(os.path.join(root, "SYSTEM-MANIFEST.yaml"))) or {}
    except Exception:
        return True
    return str(((man.get("system") or {}).get("instance_role")
                or "generic-master")).strip() == "generic-master"


# ----------------------------- behavioral dimensions -----------------------------

def _iter_scan_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, root)
        if any(rel == s or rel.startswith(s + os.sep) for s in SKIP_REL):
            continue
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in SCAN_EXT:
                yield os.path.join(dirpath, fn)


def _governance(root):
    rep = Report("governance/safety")
    manifest = os.path.join(root, "SYSTEM-MANIFEST.yaml")
    mtext = _read(manifest)
    # (a) kill switch present and actually enforced in the dispatcher
    if "ai_writes_enabled" not in mtext:
        rep.error("kill switch runtime.ai_writes_enabled missing from SYSTEM-MANIFEST.yaml")
    aios = os.path.join(root, "System", "Scripts", "aios.py")
    atext = _read(aios)
    if "ai_writes_enabled" not in atext or "WRITE_COMMANDS" not in atext:
        rep.error("aios.py does not enforce the kill switch on write commands")
    # (b) protected_objects: every path exists, and System/Agents is among them
    #     (an agent may never edit its own contract — the manifest must protect it)
    agents_protected = False
    if yaml and mtext:
        try:
            man = yaml.safe_load(mtext) or {}
        except Exception as e:
            man = {}
            rep.error(f"SYSTEM-MANIFEST.yaml failed to parse: {e}")
        for entry in (man.get("protected_objects") or []):
            e = str(entry).rstrip("/")
            if e.startswith("System/Agents"):
                agents_protected = True
            # Glob patterns (e.g. "80 User/privacy*") are forward-looking: they may
            # legitimately match nothing in the generic-master, because that content is
            # created per-user at onboarding and deliberately kept out of the clean seed
            # (enforced by test_clean_seed_content_dirs). Only a LITERAL protected path
            # that is missing is a real integrity problem.
            if "*" not in e and not os.path.exists(os.path.join(root, e)):
                rep.error(f"protected_objects path does not exist: {entry}")
        if not agents_protected:
            rep.error("System/Agents is not listed under protected_objects — "
                      "an agent could edit its own contract")
    # (c) PII-in-product: the generic-master must carry no personal data.
    #     This is a MASTER-ONLY invariant — a personal instance legitimately holds
    #     PII (colleagues' work addresses, contact records, correspondence), which
    #     is the whole point of a personal vault. The comment saying so has been
    #     here since the check was written; the code never read `instance_role`, so
    #     the invariant fired everywhere and `certify` could never pass on a
    #     personal instance (found live: 34 errors on a real instance, every one of
    #     them legitimate content). Scoped now, on the same doctrine as DEC-082 and
    #     DEC-083: the product's own rules go red on the product, never on the
    #     user's own content.
    if _is_master(root):
        for path in _iter_scan_files(root):
            if os.path.basename(path) in PII_ALLOW_FILES:
                continue
            text = _read(path)
            if not text:
                continue
            for m in set(EMAIL_RE.findall(text)):
                if m.lower() not in PII_ALLOW_EMAILS and not m.lower().endswith("example.com"):
                    rep.error(f"PII: email '{m}' in {os.path.relpath(path, root)} "
                              f"(generic-master prohibits personal data)")
    else:
        rep.info["pii_scan"] = ("skipped — master-only invariant; this vault's "
                                "instance_role is not generic-master")
    return rep


def _idempotency(root):
    """Run `aios generate` twice; derived state must match once volatile timestamps
    are normalized out. Both runs happen in an isolated copy assembled from a
    no-follow tree snapshot. The live vault is read and reproved, never written."""
    rep = Report("command-idempotency")
    gen_dir = os.path.join(root, "System", "Generated")
    if os.path.islink(gen_dir):
        rep.error("live System/Generated is a symlink — isolated probe refused")
        return rep

    def snapshot(probe_root):
        generated = os.path.join(probe_root, "System", "Generated")
        state = {}
        for dirpath, dirnames, filenames in os.walk(generated):
            dirnames.sort()
            for name in sorted(filenames):
                path = os.path.join(dirpath, name)
                norm = VOLATILE_RE.sub("<volatile>", _read(path))
                state[os.path.relpath(path, generated)] = hashlib.sha256(
                    norm.encode()).hexdigest()
        return state

    def run_generate(probe_root):
        aios = os.path.join(probe_root, "System", "Scripts", "aios.py")
        return subprocess.run([sys.executable, aios, "generate"], cwd=probe_root,
                              capture_output=True, text=True, timeout=300)

    tree = None
    try:
        tree = open_readonly_tree(root)
        files, directories = tree.walk(
            prune=lambda rel: any(part in PROBE_SKIP_DIRS
                                  for part in rel.replace("\\", "/").split("/"))
        )
        probe_files = [rel for rel in files if _probe_input(rel)]
        monitor_files = [rel for rel in files if _probe_monitor(rel)]
        total = sum(tree.files[rel].size for rel in monitor_files)
        oversized = [rel for rel in monitor_files
                     if tree.files[rel].size > PROBE_MAX_FILE_BYTES]
        if oversized or total > PROBE_MAX_TOTAL_BYTES:
            detail = (f"file exceeds {PROBE_MAX_FILE_BYTES // (1024 * 1024)} MiB: "
                      f"{oversized[0]}" if oversized else
                      f"relevant inputs total {total} bytes")
            raise SafePathError(
                "isolated generate probe relevant-input budget exceeded "
                f"({detail}; total limit {PROBE_MAX_TOTAL_BYTES // (1024 * 1024)} MiB). "
                "Archive or split oversized Markdown/config/pack inputs, then retry."
            )
        original_monitor = tree.read_files(
            monitor_files,
            max_file_bytes=PROBE_MAX_FILE_BYTES,
            max_total_bytes=PROBE_MAX_TOTAL_BYTES,
        )
        original_identities = {
            rel: (tree.files[rel].device, tree.files[rel].inode,
                  tree.files[rel].mode, tree.files[rel].size,
                  tree.files[rel].mtime_ns)
            for rel in monitor_files
        }
        original = {rel: original_monitor[rel] for rel in probe_files}
    except (OSError, SafePathError) as exc:
        if tree is not None:
            tree.close()
        rep.error(f"isolated generate probe refused before launch: {exc}")
        return rep

    try:
        with tempfile.TemporaryDirectory(prefix="certify-isolated-") as probe_root:
            required_dirs = {"System/Generated", "System/Logs"}
            required_dirs.update(
                rel for rel in directories if rel == "Packs" or rel.startswith("Packs/")
            )
            required_dirs.update(
                os.path.dirname(rel).replace("\\", "/") for rel in probe_files
                if os.path.dirname(rel)
            )
            for rel in sorted(required_dirs, key=lambda value: len(value.split("/"))):
                os.makedirs(os.path.join(probe_root, *rel.split("/")), exist_ok=True)
            for rel, payload in original.items():
                target = os.path.join(probe_root, *rel.split("/"))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as stream:
                    stream.write(payload)
                os.chmod(target, tree.files[rel].mode)

            r1 = run_generate(probe_root)
            if r1.returncode != 0:
                rep.error(f"generate failed on first isolated run: "
                          f"{(r1.stderr or r1.stdout).strip()[-200:]}")
            else:
                from cmd import generate as generate_mod
                entrypoint_findings = generate_mod.audit_live_generated_entrypoints(
                    probe_root)
                for finding in entrypoint_findings:
                    rep.error(
                        "isolated generate did not produce a valid manifest entrypoint: "
                        + finding)
                snap1 = snapshot(probe_root)
                r2 = run_generate(probe_root)
                if r2.returncode != 0:
                    rep.error(f"generate failed on second isolated run: "
                              f"{(r2.stderr or r2.stdout).strip()[-200:]}")
                else:
                    snap2 = snapshot(probe_root)
                    for key in set(snap1) | set(snap2):
                        if snap1.get(key) != snap2.get(key):
                            rep.error("non-idempotent: generated file changed on "
                                      f"re-run (beyond timestamps): {key}")
                if not entrypoint_findings:
                    rep.info["generated_entrypoints"] = (
                        "PASS — component and support indexes rebuilt and validated "
                        "in isolation")

        # Re-enumerate and re-read after both isolated runs. This detects a live
        # writer without ever attempting to roll that writer back.
        current_files, _current_dirs = tree.walk(
            prune=lambda rel: any(part in PROBE_SKIP_DIRS
                                  for part in rel.replace("\\", "/").split("/"))
        )
        current_monitor_files = [rel for rel in current_files if _probe_monitor(rel)]
        current = tree.read_files(
            current_monitor_files,
            max_file_bytes=PROBE_MAX_FILE_BYTES,
            max_total_bytes=PROBE_MAX_TOTAL_BYTES,
        )
        current_identities = {
            rel: (tree.files[rel].device, tree.files[rel].inode,
                  tree.files[rel].mode, tree.files[rel].size,
                  tree.files[rel].mtime_ns)
            for rel in current_monitor_files
        }
        changed = (tuple(current_monitor_files) != tuple(monitor_files)
                   or current != original_monitor
                   or current_identities != original_identities)
        if changed:
            rep.error("live vault changed during isolated generate probe — result is "
                      "not reliable; the live change was left untouched")
    except (OSError, SafePathError) as exc:
        rep.error(f"isolated generate probe failed safely: {exc}")
    finally:
        tree.close()
    return rep


def _doc_truth(root):
    """Strict release-record gate, role-scoped like the rest of certification.

    The product master proves its exact release surface and complete changelog.
    A personal instance still proves the manifest authority and synchronized
    mirrors, but DEC-097 leaves its changelog and product customizations
    instance-owned.  Missing/unreadable role fails closed to generic-master via
    ``_is_master``; the checker also verifies the manifest agrees with the
    explicit role selected here.
    """
    rep = Report("release-records")
    expected_role = (
        "generic-master" if _is_master(root) else "personal-instance")
    try:
        audit = audit_version_records(root, expected_role=expected_role)
    except Exception as exc:
        rep.error("version-record audit raised: %s" % exc)
        return rep
    rep.info["role"] = expected_role
    rep.info["authority"] = audit.versions.get("authority")
    rep.info["package_mirror"] = audit.versions.get("package_mirror")
    rep.info["baseline_mirror"] = audit.versions.get("baseline_mirror")
    rep.info["baseline_identity"] = audit.baseline_identity
    rep.info["changelog_records"] = len(audit.records)
    for finding in audit.findings:
        location = finding.path
        if finding.line is not None:
            location += ":%d" % finding.line
        rep.error("%s [%s] %s" %
                  (location, finding.code, finding.message))
    return rep


BEHAVIORAL = [_governance, _idempotency, _doc_truth]

AUTHORITY_REPOSITORY_ENV = "AIOS_SOURCE_AUTHORITY_REPOSITORY"
AUTHORITY_COMMIT_ENV = "AIOS_SOURCE_AUTHORITY_COMMIT"
FULL_SHA1_RE = re.compile(r"[0-9a-f]{40}")


def _git_authority(repository, *args):
    return subprocess.run(
        ["git", "-C", repository, *args],
        capture_output=True, text=True, timeout=30,
    )


def _authority_fingerprint(root, repository, commit):
    """Validate and fingerprint a separate, commit-pinned history authority.

    The fingerprint deliberately contains no filesystem path and is used only
    inside this process to prove the authority did not change while the strict
    regression child was running.
    """
    if not repository or not commit:
        return None, (
            "strict regression requires --source-authority-repository and "
            "--source-authority-commit"
        )
    if not FULL_SHA1_RE.fullmatch(str(commit)):
        return None, "source authority commit must be a full lowercase SHA-1"
    try:
        authority = os.path.realpath(os.path.abspath(str(repository)))
        target = os.path.realpath(os.path.abspath(root))
    except (OSError, TypeError, ValueError):
        return None, "source authority repository is invalid"
    if authority == target:
        return None, "source authority repository must be separate from the checked tree"
    probe = _git_authority(authority, "rev-parse", "--git-dir")
    if probe.returncode != 0:
        return None, "source authority repository is not a readable Git repository"
    resolved = _git_authority(
        authority, "rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}"
    )
    if resolved.returncode != 0 or resolved.stdout.strip() != commit:
        return None, "source authority commit pin does not resolve exactly"
    refs = _git_authority(authority, "show-ref", "--head", "--dereference")
    if refs.returncode not in (0, 1):
        return None, "source authority refs cannot be read"
    object_type = _git_authority(authority, "cat-file", "-t", commit)
    if object_type.returncode != 0 or object_type.stdout.strip() != "commit":
        return None, "source authority pinned object is not a commit"
    fingerprint = hashlib.sha256(
        (commit + "\0" + refs.stdout).encode("utf-8", "surrogateescape")
    ).hexdigest()
    return (authority, commit, fingerprint), None


# ----------------------------- orchestration -----------------------------

def _run_regression(root, authority_repository=None, authority_commit=None):
    scripts = os.path.join(root, "System", "Tests", "scripts")
    if not os.path.isdir(scripts):
        return None, "no test suite found"
    before, error = _authority_fingerprint(
        root, authority_repository, authority_commit)
    if error:
        return False, error
    authority, commit, fingerprint = before
    environment = os.environ.copy()
    environment[AUTHORITY_REPOSITORY_ENV] = authority
    environment[AUTHORITY_COMMIT_ENV] = commit
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", scripts, "-p", "test_*.py"],
            cwd=root, capture_output=True, text=True, timeout=600,
            env=environment)
    except Exception as e:  # pragma: no cover
        return False, f"suite failed to launch: {e}"
    after, error = _authority_fingerprint(root, authority, commit)
    if error or after[2] != fingerprint:
        return False, "source authority changed during strict regression"
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()
    return proc.returncode == 0, (tail[-1] if tail else "(no output)")


def _fold(rep, name, sub):
    """Roll a sub-check's result into the top-level report (info line + findings)."""
    status = "PASS" if sub.ok else "FAIL"
    rep.info[name] = f"{status} — {len(sub.errors)} errors, {len(sub.warnings)} warnings"
    rep.errors += [f"[{name}] {e}" for e in sub.errors]
    rep.warnings += [f"[{name}] {w}" for w in sub.warnings]


def _reconcile_generated_health(root, health_report, generation_report):
    """Replace missing-generated warnings only after isolated reconstruction.

    The standalone health command remains advisory.  Source-check may classify
    ignored generated entrypoints as rebuildable only when its isolated generate
    has just produced and schema/census-validated both entrypoints.
    """
    if not generation_report or not generation_report.ok:
        return
    if not str(generation_report.info.get("generated_entrypoints", "")).startswith(
            "PASS"):
        return
    try:
        with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as stream:
            manifest = yaml.safe_load(stream) or {}
    except (OSError, yaml.YAMLError, TypeError):
        return
    generated_roots = tuple(
        str(value).replace("\\", "/").rstrip("/") + "/"
        for value in (manifest.get("directories") or {}).get("generated", [])
        if isinstance(value, str) and value.rstrip("/")
    )
    if not generated_roots:
        return
    kept = []
    removed = 0
    for warning in health_report.warnings:
        normalized = warning.replace("\\", "/")
        is_missing_generated = (
            "[doc-staleness] manifest references a missing file:" in normalized
            and any(f"missing file: {prefix}" in normalized
                    for prefix in generated_roots)
        )
        if is_missing_generated:
            removed += 1
        else:
            kept.append(warning)
    if removed:
        health_report.warnings = kept
        current = health_report.info.get("doc_staleness_flags")
        if isinstance(current, int):
            health_report.info["doc_staleness_flags"] = max(0, current - removed)
        health_report.info["generated_state"] = (
            "empty in distribution; required entrypoints rebuilt and validated "
            "by isolated source-check generation")


def run(root, args, rep: Report):
    # Put the scope before every detailed dimension so it is impossible to quote
    # the output honestly as a runtime or release certification.  The generic
    # product source is the only valid subject of this verdict; a personalized
    # vault belongs to instance-health instead.
    rep.info["verdict_scope"] = (
        "SOURCE CHECK — repository structure, docs, schemas, code, and tests only"
    )
    rep.info["runtime_certification"] = (
        "NOT RUN — use runtime-certify with externally produced runtime evidence"
    )
    rep.info["release_qualification"] = (
        "NOT RUN — historical lifecycle qualification is a separate release gate"
    )
    if rep.command == "certify":
        rep.info["compatibility_alias"] = (
            "certify is a compatibility alias for source-check; it grants no "
            "runtime autonomy and no release qualification"
        )
    if not _is_master(root):
        rep.error(
            "source-check requires system.instance_role: generic-master; "
            "use instance-health for a personalized vault"
        )
        return rep
    # Run the isolated generation proof before health.  Health correctly warns
    # about missing manifest entrypoints on its own; source-check may reconcile
    # only the generated ones after this proof has succeeded.
    generation_report = (
        _idempotency(root) if _idempotency in BEHAVIORAL else None)
    # mechanical integrity — delegate to health (the single source of truth for
    # WHICH mechanical checks run: validate/links/dupes/doc-check + freshness).
    hsub = Report("health")
    try:
        health_mod.run(root, args, hsub)
    except Exception as e:
        hsub.error(f"health raised: {e}")
    _reconcile_generated_health(root, hsub, generation_report)
    _fold(rep, "health (mechanical)", hsub)
    for k, v in hsub.info.items():
        rep.info[f"  health.{k}"] = v
    # vocabulary — health omits it, so run it directly
    vsub = Report("vocab")
    try:
        vc_mod.run(root, args, vsub)
    except Exception as e:
        vsub.error(f"vocab raised: {e}")
    _fold(rep, "vocab", vsub)
    # certification-specific behavioral assertions
    for fn in BEHAVIORAL:
        sub = generation_report if fn is _idempotency else fn(root)
        _fold(rep, sub.command, sub)
    # regression suite as a gate
    authority_repository = (
        getattr(args, "source_authority_repository", None)
        or os.environ.get(AUTHORITY_REPOSITORY_ENV)
    )
    authority_commit = (
        getattr(args, "source_authority_commit", None)
        or os.environ.get(AUTHORITY_COMMIT_ENV)
    )
    ok, summary = _run_regression(
        root, authority_repository=authority_repository,
        authority_commit=authority_commit)
    if ok is None:
        rep.info["regression"] = f"SKIP — {summary}"
        rep.error(f"[regression] {summary}; source-check cannot pass without its tests")
    else:
        rep.info["regression"] = f"{'PASS' if ok else 'FAIL'} — {summary}"
        if not ok:
            rep.error(f"[regression] suite failed: {summary}")
    return rep
