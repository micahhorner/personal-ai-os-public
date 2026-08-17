"""vault.upgrade — the product-update importer (DEC-073/074; root files DEC-097).

Applies a new product release's System/ plus the product-owned ROOT files
into this instance — and nothing else: user content, 80 User/, .obsidian/,
Packs/, the canonical journal, and certification records are never touched. Classification is a three-way
compare (base vs release vs instance) against the shipped baseline manifest
(System/.baseline-manifest.json, DEC-074), so an instance-customized file is
kept and a file changed on both sides is a CONFLICT — reported, never merged
(DEC-073). Discipline is migrate.py's: kill switch, checkpoint-or-halt,
dry-run writes nothing, validate/health after, journal line, loud failure
pointing at the checkpoint.

The post-run integrity proof covers the user's WORK. The open editor's own
session state (`.obsidian/workspace.json` and its siblings) is reported rather
than judged — see RUNTIME_STATE_PATHS, DEC-115.

Protected writes require a fresh semantic-input review hash plus `--apply
--confirm`.  Final output bytes do not exist at review time: migration and
docgen materialize them in the isolated candidate, whose complete identity is
then pinned by the existing transaction journal.
"""
from __future__ import annotations
import datetime
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import yaml

from lib.report import Report
from lib.vaultpaths import ai_writes_enabled, manifest
from lib import upgrade_candidate as candidate_mod
from lib.historical_sources import OFFICIAL_LEGACY_CORE_SOURCES
from lib import migrations as migrations_mod
from lib import transaction as transaction_mod
from lib import safepaths
from lib.protectedwrites import ProtectedTargetError, protection_proof
from lib.reviewedplan import build_semantic_reviewed_plan, canonical_json
from cmd import checkpoint as ckpt_mod
from cmd import migrate as migrate_mod

BASELINE = os.path.join("System", ".baseline-manifest.json")
ROUTER = "System/Runtime/Task Router.yaml"
# Inside System/ but outside the upgrade surface: disposable state is
# regenerated, the journal is the instance's canonical history (DEC-016),
# results are the instance's certification records.
EXCLUDED_PREFIXES = ("System/Generated/", "System/Logs/", "System/Journal/",
                     "System/Tests/results/")
SKIP_NAMES = {".DS_Store", "__pycache__"}
# ---------------------------------------------------------------------------
# The ROOT-files gap fix (DEC-097). Proven live by the PMM Phase 0 inventory:
# a successful upgrade left the instance's CLAUDE.md ~18 versions stale because
# the surface was System/-only. Which root files are the product's to upgrade
# is encoded HERE, explicitly, one deliberate call per file — never inferred.
ROOT_PRODUCT_FILES = (
    "CLAUDE.md",       # the Claude adapter pointer — product text, ships with every release
    "pyproject.toml",  # product tooling/config — the product's to version
    "README.md",       # the product's own front page
    "START-HERE.md",   # the product's entry document
    "CONTRIBUTING.md", # product contributor contract
    "SECURITY.md",     # product vulnerability-reporting policy
)
# Root files deliberately OUTSIDE the upgrade surface (user-owned; never touched):
#   LICENSE.md            — the user's/implementer's license choice, not the product's to change
#   CHANGELOG.md          — records THIS INSTANCE's journey; the release's history arrives in the
#                           release tree, but the instance's copy is its own record
#   SYSTEM-MANIFEST.yaml  — instance identity and runtime state; only system_version is bumped
#                           (below), exactly as before
#   CONNECT-CHECK.md      — ambiguous (product-authored sentinel a vault could adapt) → defaults
#                           user-owned by the DEC-097 rule: when in doubt, never touch
#   To-Do.md / Decisions/ — user CONTENT once present; seeded additively when absent (below)
#
# Seed files new releases add at the vault root (To-Do.md arrives v1.39.0,
# Decisions/ arrives v1.40.0 — their register entries point here): delivered by
# upgrade as ADDITIVE new files when the instance lacks them, and never replaced,
# merged, or removed once they exist — from that moment they are user content.
ADDITIVE_ROOT_SEEDS = ("To-Do.md", "Decisions")
# More instance-edited files than this inside protected paths = fused
# customizations (the PMM shape); the role-pack refactor must come first.
FUSION_LIMIT = 5
CORE_DISTRIBUTION = "personal-ai-os"
PMM_SOURCE_MARKERS = (
    "Packs/pmm",
    "PMM-OPERATIONS.md",
    "01 Messaging Hub",
    "02 Sales Enablement",
    "03 Intelligence Hub",
    "04 Published Assets",
    "05 PMM Wiki",
    "06 Claude",
    "About Me.md",
    "START HERE.md",
)
TRANSACTION_BOUNDARIES = (
    "checkpoint", "plan", "candidate-copy", "candidate-delete",
    "baseline-replacement", "migration", "generation", "validation", "version-bump",
    "report-write", "commit-swap", "cleanup",
)


def _transaction_boundary(name, phase, root):
    """Exact, patchable fault-injection seam for the upgrade state machine."""
    if name not in TRANSACTION_BOUNDARIES or phase not in ("before", "after"):
        raise ValueError(f"invalid upgrade transaction boundary: {name}/{phase}")


def _free_bytes(path):
    return candidate_mod._free_bytes(path)


def _same_filesystem(a, b):
    return candidate_mod._same_filesystem(a, b)


def _step(name, root, operation):
    _transaction_boundary(name, "before", root)
    result = operation()
    _transaction_boundary(name, "after", root)
    return result


# ---------------------------------------------------------------------------
# The bump gate's conflict distinction (DEC-111).
#
# The gate itself is right and stays: a vault must never claim a version whose
# files never arrived. What was wrong is what counted as a *blocking* conflict.
# "Conflict" was doing two unrelated jobs — "these two versions disagree and
# nobody chose" (must block) and "this instance deliberately differs" (must
# not). Proven live 2026-07-27: a green customized work instance passed every gate — validate,
# links, dupes and health all 0 errors, 318 of 322 System files byte-identical —
# and still could not record that it had upgraded, because its two divergences
# were a customized Task Router and a self-regenerated constitution census.
# Both are things the product ASKS the instance to do. An instance that accepts
# either invitation was locked out of every future version bump, permanently,
# with no path through the tool. That is the headline feature failing closed on
# its own best-behaved customers.
#
# So a protected-path conflict now blocks unless it is ACCOUNTED FOR, by one of
# exactly three routes, each of which is a recorded reason rather than a
# loosened threshold:
#
#   1. SANCTIONED   — the product itself declares the path instance-owned and
#                     never auto-merged. Divergence is the contract working.
#   2. DERIVED      — the two copies differ ONLY inside docgen-generated
#                     regions, which `docgen --check` REQUIRES this instance to
#                     regenerate against its own tree. The tool demanded the
#                     regeneration; treating the result as a conflict is a
#                     circular trap with no exit.
#   3. ACCEPTED     — a human named the path with `--accept`. This is the
#                     "somebody chose" route for a genuine conflict, and it is
#                     what keeps the gate a gate: without it there would be no
#                     way for a person to ever resolve one.
#
# Anything else still blocks, unchanged. The accounted paths are never merged,
# never overwritten, and are listed in the report, the journal and the manifest
# comment — the version claim travels WITH the divergences it was granted over.
SANCTIONED_DIVERGENCE = {
    ROUTER: ("DEC-073/DEC-083 — the Task Router is the instance's own routing "
             "surface, explicitly never auto-merged; a customized router is "
             "sanctioned divergence, not an unresolved disagreement"),
}

# A docgen region: <!-- docgen:key --> generated body <!-- /docgen:key -->.
# Mirrors cmd/docgen.py's marker grammar; the body is what legitimately differs
# per-instance, so only the body is neutralised — the markers themselves stay,
# which means adding or removing a whole block is still a real difference.
_DOCGEN_REGION = re.compile(
    r"(<!-- docgen:([a-z0-9\-]+) -->)(.*?)(<!-- /docgen:\2 -->)", re.S)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_sha256(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _upgrade_review_plan(root, release, policy, *, inst_ver, rel_ver,
                         live_distribution, release_distribution, base,
                         base_derived, base_src, plan, seeds, asked, accounted,
                         migration_plan):
    """Approve exact semantic inputs, before final candidate bytes exist.

    This intentionally is not an output-byte plan.  Upgrade's docgen and
    migration outputs exist only in the isolated candidate; the existing
    transaction then pins the complete live and candidate tree identities.
    """
    live_surface = _hash_tree(root)
    release_surface = _hash_tree(release)
    baseline = {"files": base, "derived": base_derived}
    semantic_inputs = {
        "contract": "upgrade-semantic-inputs/v1",
        "limitation": (
            "final protected output bytes are materialized and validated only "
            "inside the candidate; this review binds every semantic input"
        ),
        "live_upgrade_surface_sha256": _json_sha256(live_surface),
        "live_upgrade_surface_files": live_surface,
        "release": {
            "path": os.path.realpath(release),
            "tree_sha256": candidate_mod.tree_identity(release),
            "upgrade_surface_sha256": _json_sha256(release_surface),
            "upgrade_surface_files": release_surface,
        },
        "versions": {"installed": inst_ver, "release": rel_ver},
        "distributions": {
            "installed": live_distribution,
            "release": release_distribution,
        },
        "baseline": {
            "source": base_src,
            "sha256": _json_sha256(baseline),
            "files": base,
            "derived": base_derived,
        },
        "classification": {
            key: plan[key] for key in (
                "add", "replace", "remove", "keep", "conflict",
                "instance_added", "user_deleted", "unchanged")
        },
        "classification_plan_sha256": candidate_mod.plan_identity(plan),
        "additive_seeds": list(seeds),
        "requested_accepts": sorted(asked),
        "accounted_protected_conflicts": [
            {"path": path, "route": route, "reason": reason}
            for path, route, reason in accounted
        ],
        "migration_plan": migration_plan,
        "migration_plan_sha256": _json_sha256(migration_plan),
    }
    return build_semantic_reviewed_plan(
        "upgrade", root, policy, semantic_inputs)


def _reprove_upgrade_review_trees(root, release, policy, review):
    """Re-prove the mutable tree/policy inputs at a later safe boundary."""
    policy.reprove()
    inputs = review.document["semantic_inputs"]
    if _json_sha256(_hash_tree(root)) != inputs["live_upgrade_surface_sha256"]:
        raise candidate_mod.CandidateError(
            "live upgrade surface changed after review")
    release_input = inputs["release"]
    if candidate_mod.tree_identity(release) != release_input["tree_sha256"]:
        raise candidate_mod.CandidateError("release tree changed after review")
    if _json_sha256(_hash_tree(release)) != release_input["upgrade_surface_sha256"]:
        raise candidate_mod.CandidateError(
            "release upgrade surface changed after review")


def _upgrade_recovery_review_plan(root, release, policy, journal, data):
    """Bind an existing journal recovery without changing its frozen schema."""
    semantic_inputs = {
        "contract": "upgrade-recovery-semantic-inputs/v1",
        "limitation": (
            "recovery follows the existing journal's pinned full-tree identities; "
            "this approval does not change or extend the journal schema"
        ),
        "live_tree_sha256": candidate_mod.tree_identity(root),
        "release": {
            "path": os.path.realpath(release),
            "tree_sha256": candidate_mod.tree_identity(release),
        },
        "journal": {
            "path": os.path.realpath(journal),
            "sha256": _sha(journal),
            "document": data,
        },
    }
    return build_semantic_reviewed_plan(
        "upgrade-recovery", root, policy, semantic_inputs)


# Everything that is NOT the upgrade surface, and therefore everything this
# command promises not to touch. Derived as a COMPLEMENT rather than enumerated,
# which is the whole fix (DEC-109).
#
# It used to be a list: `manifest.directories.content` plus `.obsidian` and
# `Packs`. That list is a hand-maintained census of a set the USER controls, and
# on a real vault it was wrong by two orders of magnitude. Measured on a live
# work instance at the upgrade that found this: **160 files fingerprinted, 1,641
# in the tree, 1,102 of the difference sitting in seven content folders the
# instance had declared in its own `folder-registry.yaml`** — registered user
# content, every one of them, and every one of them invisible to a report that
# said "byte-identical (160 files verified)". The instance's manifest also
# predated `Decisions/`, so two more went unseen for a second reason. The claim
# was not slightly optimistic; it covered under a tenth of what it named.
#
# A complement cannot drift that way: a folder the user invents tomorrow is
# outside the upgrade surface by construction, so it is verified by construction.
# Two things are excluded on purpose, and they are the only two:
VERIFY_SKIP_PREFIXES = (
    ".git/",                 # not vault content; git is the checkpoint's business
    "System/Generated/",     # rebuilt by the post-upgrade `generate` — verifying it
    "System/Logs/",          # would fail every run for the one reason that is fine
)

# ---------------------------------------------------------------------------
# EDITOR SESSION STATE (DEC-115). Not user content, and not the upgrade's
# either — it belongs to whatever application has the vault open right now.
#
# The defect this closes, measured on all three live instances 2026-07-27:
# every upgrade ran `generate`, `generate` wrote index files into the vault,
# and Obsidian — running, watching the folder — reacted by re-saving its own
# `workspace.json` INSIDE the same run. The integrity comparison saw a file
# change between its two fingerprints and reported
# `CONTENT INTEGRITY FAILURE — 1 user file(s) changed`, so the version bump was
# refused. **No vault open in an editor could complete an upgrade** — and the
# obvious thing for a user to do is leave their notes app open.
#
# The check exists so an upgrade can never silently alter a user's NOTES. That
# guarantee is untouched here. What is excluded is the narrow set of files an
# editor rewrites as a side effect of its own liveness — which panes are open,
# which file was last active — none of which any human authored and none of
# which this command has ever written. `import_vault.py` already skips
# `workspace.json` for exactly this reason, recorded in the v1.0.4 lesson:
# session state, not content.
#
# Deliberately NARROW. Everything else under `.obsidian/` — `app.json`,
# `hotkeys.json`, `appearance.json`, plugin settings, the plugins themselves —
# is user CONFIGURATION, authored by the user, and stays fingerprinted: an
# upgrade that reset someone's hotkeys would still be a hard failure.
#
# And these paths are not silenced. A change to one is reported by name, in its
# own field, with the reason — the upgrade just does not call it a corruption.
RUNTIME_STATE_PATHS = (
    ".obsidian/workspace.json",          # desktop pane layout / last-open files
    ".obsidian/workspace-mobile.json",   # the same, for the mobile app
    ".obsidian/workspaces.json",         # the saved-workspaces plugin's store
)


def _is_runtime_state(rel: str) -> bool:
    """Is this the open editor's own session state rather than the user's work?"""
    return rel.replace(os.sep, "/") in RUNTIME_STATE_PATHS


def _verify_scope() -> str:
    """What the integrity claim covers, in the claim itself. A report that says
    "verified" without saying *what* is the defect this release closes; the
    reader of an upgrade report has no other way to know."""
    return ("every file outside the upgrade surface — all content and registry "
            "folders, 80 User, Packs, .obsidian settings, the journal, "
            "certification results and root user files; excludes regenerated "
            "System/Generated and System/Logs, and reports rather than fails on "
            "the open editor's own session state (DEC-115)")


def _in_upgrade_surface(rel: str) -> bool:
    """Is this path the product's to replace? Then it is not the user's world.

    Note what is deliberately NOT excluded here: `System/Journal/` and
    `System/Tests/results/`. They live inside `System/` but sit outside the
    upgrade surface (EXCLUDED_PREFIXES) — the journal is the instance's canonical
    history (DEC-016) and the results are its certification records. The docstring
    at the top of this module promises both are never touched; until this change
    nothing checked either.
    """
    if rel in ROOT_PRODUCT_FILES:
        return True
    if not rel.startswith("System/"):
        return False
    return not any(rel.startswith(p) for p in EXCLUDED_PREFIXES)


def _user_world(root):
    """{relative posix path: sha256} for every file this command promises to
    leave alone — the whole tree minus the upgrade surface minus regenerated
    state. Costs ~0.1s on a 1,641-file / 38 MB instance, so completeness here is
    bought for nothing."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES and d != ".git"]
        for fn in filenames:
            if fn in SKIP_NAMES or fn.endswith(".pyc"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if rel.startswith(VERIFY_SKIP_PREFIXES) or _in_upgrade_surface(rel):
                continue
            try:
                out[rel] = _sha(p)
            except OSError:
                pass
    return out


def _system_files(root):
    """{relative posix path: absolute path} for the upgrade surface:
    System/ (minus exclusions) + the product-owned root files (DEC-097)."""
    out = {}
    top = os.path.join(root, "System")
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
        for fn in filenames:
            if fn in SKIP_NAMES or fn.endswith(".pyc"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
            if rel == BASELINE.replace(os.sep, "/"):
                continue          # release metadata, handled separately
            if any(rel.startswith(p) for p in EXCLUDED_PREFIXES):
                continue
            out[rel] = os.path.join(dirpath, fn)
    for rel in ROOT_PRODUCT_FILES:
        p = os.path.join(root, rel)
        if os.path.exists(p):
            out[rel] = p
    return out


def _additive_seeds(root, release):
    """Release-shipped root seeds the instance lacks (ADDITIVE_ROOT_SEEDS):
    delivered as new files only. A file the instance already has is user
    content and is never touched — not even compared."""
    adds = []
    for seed in ADDITIVE_ROOT_SEEDS:
        sp = os.path.join(release, seed)
        if os.path.isfile(sp):
            if not os.path.exists(os.path.join(root, seed)):
                adds.append(seed)
        elif os.path.isdir(sp):
            for dirpath, dirnames, filenames in os.walk(sp):
                dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
                for fn in filenames:
                    if fn in SKIP_NAMES:
                        continue
                    rel = os.path.relpath(os.path.join(dirpath, fn), release).replace(os.sep, "/")
                    if not os.path.exists(os.path.join(root, rel)):
                        adds.append(rel)
    return sorted(adds)


def _hash_tree(root):
    return {rel: _sha(p) for rel, p in _system_files(root).items()}


def make_baseline(root, rep: Report, dry=False):
    """Write the release's pristine-file record. Product master only: on an
    instance this file is the shipped record of what pristine LOOKS like —
    regenerating it there would erase the very evidence classification needs."""
    role = manifest(root).get("system", {}).get("instance_role")
    if role != "generic-master":
        rep.error("--make-baseline runs on the product master only "
                  f"(this manifest says instance_role: {role}) — an instance's "
                  "baseline is shipped evidence, never regenerated locally")
        return rep
    ver = str(manifest(root).get("system", {}).get("system_version"))
    data = {"system_version": ver,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "files": _hash_tree(root),
            # DEC-111: the same files hashed with generated bodies blanked, so a
            # later upgrade can tell "the instance recounted its own censuses"
            # (not an edit) from "the instance edited this file" (an edit).
            # Absent on baselines written before v1.56.0; classification then
            # behaves exactly as it did before.
            "derived": _neutralised_tree(root)}
    if dry:
        rep.info["mode"] = "dry-run — baseline not written"
        rep.info["baseline"] = BASELINE.replace(os.sep, "/")
        rep.info["files_recorded"] = len(data["files"])
        return rep
    payload = json.dumps(data, indent=1, sort_keys=True).encode("utf-8")
    baseline_path = os.path.join(root, BASELINE)
    replacement = None
    try:
        if os.path.lexists(baseline_path):
            replacement = safepaths.preflight_contained_regular_files(
                root, [baseline_path]
            )
            replacement.read_bytes()
        safepaths.atomic_create_files(
            root,
            {BASELINE.replace(os.sep, "/"): payload},
            replace_batch=replacement,
        )
    except (OSError, safepaths.SafePathError) as exc:
        rep.error(f"baseline write refused: {exc}")
        return rep
    finally:
        if replacement is not None:
            replacement.close()
    rep.info["baseline"] = BASELINE.replace(os.sep, "/")
    rep.info["files_recorded"] = len(data["files"])
    return rep


def _declared_distribution(root):
    data = migrations_mod.load_unique_yaml_file(
        os.path.join(root, "SYSTEM-MANIFEST.yaml"), "SYSTEM-MANIFEST.yaml")
    system = data.get("system") if isinstance(data, dict) else None
    if not isinstance(system, dict):
        raise migrations_mod.MigrationError("manifest system mapping is missing")
    value = system.get("distribution_id")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise migrations_mod.MigrationError("system.distribution_id is invalid")
    return value


def _authorize_source_distribution(root, inst_ver, source_identity, args):
    declared = _declared_distribution(root)
    if declared is not None:
        if declared != CORE_DISTRIBUTION:
            raise migrations_mod.MigrationError(
                f"wrong source distribution {declared!r}; this release accepts "
                f"only {CORE_DISTRIBUTION!r}"
            )
        return declared, False
    if not getattr(args, "authorize_legacy_core", False):
        raise migrations_mod.MigrationError(
            "legacy source has no distribution_id; re-run with "
            "--authorize-legacy-core only after confirming this is an official "
            "Personal AI OS source"
        )
    markers = [
        rel for rel in PMM_SOURCE_MARKERS
        if os.path.lexists(os.path.join(root, *rel.split("/")))
    ]
    if markers:
        raise migrations_mod.MigrationError(
            "legacy core authorization refused because PMM product markers are "
            "present: " + ", ".join(markers)
        )
    license_path = Path(root) / "LICENSE.md"
    if license_path.is_symlink() or not license_path.is_file():
        raise migrations_mod.MigrationError(
            "legacy core authorization requires a regular LICENSE.md"
        )
    license_sha = hashlib.sha256(license_path.read_bytes()).hexdigest()
    if (inst_ver, source_identity, license_sha) not in OFFICIAL_LEGACY_CORE_SOURCES:
        raise migrations_mod.MigrationError(
            "legacy source does not exactly match one frozen official tuple "
            f"(version={inst_ver}, source_identity={source_identity}, "
            f"license_sha256={license_sha})"
        )
    return CORE_DISTRIBUTION, True


def _resolve_system_migration(root, release, inst_ver, rel_ver, args):
    """Select the one exact direct system edge, or prove none is required.

    Version strings route only to a candidate set. The canonical pre-overlay
    baseline identity and every exact-file old hash are the discriminators.
    This is deliberately read-only and runs before checkpoint creation.
    """
    migrations_dir = os.path.join(release, "System", "Migrations")
    if not os.path.isdir(migrations_dir):
        return None
    available = migrations_mod.discover(migrations_dir)
    target_edges = [
        item for item in available
        if item.version_target == "system_version"
        and item.to_version == rel_ver
    ]
    if not target_edges:
        return None
    version_edges = [
        item for item in target_edges if item.from_version == inst_ver]
    if not version_edges:
        raise migrations_mod.MigrationError(
            f"release declares system migrations to {rel_ver}, but none starts "
            f"at {inst_ver}")
    source_identity = migrations_mod.compute_source_identity(root)
    source_distribution, legacy_authorized = _authorize_source_distribution(
        root, inst_ver, source_identity, args)
    identity_edges = [
        item for item in version_edges
        if item.source_identity == source_identity
        and item.source_distribution == source_distribution]
    if not identity_edges:
        rivals = ", ".join(
            f"{item.directory.name}:{item.source_identity}"
            for item in version_edges)
        raise migrations_mod.MigrationError(
            "version edge exists, but no migration matches the canonical "
            f"pre-overlay source identity {source_identity}; candidates: {rivals}")
    records = migrations_mod.load_ledger(root)
    applicable = []
    refused = []
    for item in identity_edges:
        try:
            action = migrations_mod.preflight_sequence(
                item, available, records, inst_ver, source_identity)
            if action != "apply":
                raise migrations_mod.MigrationError(
                    f"unexpected pre-upgrade action {action}")
            effects = migrate_mod.exact_transform_contract(root, item)
            applicable.append((item, effects))
        except migrations_mod.MigrationError as exc:
            refused.append(f"{item.directory.name}: {exc}")
    if not applicable:
        raise migrations_mod.MigrationError(
            "no exact migration edge satisfies the live transform "
            "preconditions; " + "; ".join(refused))
    if len(applicable) != 1:
        raise migrations_mod.MigrationError(
            "ambiguous migration edge: multiple manifests match version, "
            "source identity, and transform preconditions: "
            + ", ".join(item.directory.name for item, _ in applicable))
    selected, effects = applicable[0]
    return {
        "name": selected.directory.name,
        "id": selected.id,
        "source_identity": source_identity,
        "source_distribution": source_distribution,
        "legacy_authorized": legacy_authorized,
        "manifest_hash": selected.manifest_hash,
        "effects": effects,
    }


def _migration_integrity_accounting(pre_user, post_user, effects):
    """Return exact manifest-proven user changes and any hash mismatches."""
    allowed = set()
    mismatches = []
    visible = set(pre_user) | set(post_user)
    for effect in effects:
        path = effect["path"].replace(os.sep, "/")
        if path not in visible:
            # Product-surface and excluded runtime paths are not part of the
            # user-content proof and receive no exemption here.
            continue
        matched = effect["matched_old_sha256"]
        expected_before = None if matched == "absent" else matched
        actual_before = pre_user.get(path)
        actual_after = post_user.get(path)
        if (actual_before == expected_before
                and actual_after == effect["new_sha256"]):
            allowed.add(path)
        else:
            mismatches.append({
                "path": path,
                "expected_before": expected_before,
                "actual_before": actual_before,
                "expected_after": effect["new_sha256"],
                "actual_after": actual_after,
            })
    return allowed, mismatches


def run(root, args, rep: Report):
    """Build a complete final candidate, then atomically exchange whole roots."""
    root = os.path.realpath(os.path.abspath(root))
    if getattr(args, "make_baseline", False):
        dry = getattr(args, "dry_run", False)
        if not dry and not ai_writes_enabled(root):
            rep.error("kill switch is off — refusing to write")
            return rep
        return make_baseline(root, rep, dry=dry)

    apply = bool(getattr(args, "apply", False))
    if apply and getattr(args, "dry_run", False):
        rep.error("upgrade cannot combine --apply with --dry-run")
        return rep
    dry = not apply
    # Apply is a writer even when its release argument is bad.  Preserve the
    # direct-module kill-switch guarantee before inspecting external inputs;
    # the bare semantic review remains read-only and is allowed through.
    if apply and not ai_writes_enabled(root):
        rep.error("kill switch is off — refusing to write")
        return rep

    target = getattr(args, "target", None)
    if not target:
        rep.error("usage: aios upgrade <path-to-new-release> [--dry-run] "
                  "[--base <old release tree or baseline json>]")
        return rep
    release = os.path.abspath(target)
    if not os.path.exists(os.path.join(release, "SYSTEM-MANIFEST.yaml")):
        rep.error(f"not a release tree (no SYSTEM-MANIFEST.yaml): {release}")
        return rep
    if os.path.realpath(release) == os.path.realpath(root):
        rep.error("release path IS this vault — point at a checkout/unzip of the new version")
        return rep

    try:
        active = _active_transaction(root)
    except transaction_mod.TransactionError as exc:
        rep.error(f"unfinished upgrade transaction could not be read safely: {exc}")
        return rep
    if active is not None:
        journal, journal_data = active
        try:
            policy = protection_proof(root)
            recovery_review = _upgrade_recovery_review_plan(
                root, release, policy, journal, journal_data)
        except (ProtectedTargetError, OSError, ValueError,
                candidate_mod.CandidateError) as exc:
            rep.error(f"upgrade recovery review could not be proven: {exc}")
            return rep
        rep.info["review_contract"] = (
            "exact recovery semantic inputs; existing journal pins final trees")
        rep.info["review_sha256"] = recovery_review.review_sha256
        rep.info["review_plan"] = recovery_review.document
        if dry:
            rep.info["mode"] = (
                "dry-run/read-only recovery review — no cleanup or transaction "
                f"step run; re-run with --apply --confirm --review-sha256 "
                f"{recovery_review.review_sha256}")
            return rep
        supplied = str(getattr(args, "review_sha256", None) or "")
        if not (getattr(args, "confirm", False)
                and supplied == recovery_review.review_sha256):
            rep.error(
                "upgrade recovery requires --apply --confirm --review-sha256 "
                f"{recovery_review.review_sha256} from a fresh read-only review")
            return rep
        try:
            fresh_active = _active_transaction(root)
            if fresh_active is None:
                raise transaction_mod.TransactionError(
                    "unfinished transaction disappeared after review")
            fresh_journal, fresh_data = fresh_active
            fresh_policy = protection_proof(root)
            fresh_review = _upgrade_recovery_review_plan(
                root, release, fresh_policy, fresh_journal, fresh_data)
            if fresh_review.review_sha256 != supplied:
                raise transaction_mod.TransactionError(
                    "upgrade recovery review became stale; run the read-only review again")
            _resume_transaction(root, args, rep)
            return rep
        except (ProtectedTargetError, transaction_mod.TransactionError,
                OSError, ValueError, candidate_mod.CandidateError) as exc:
            rep.error(f"unfinished upgrade transaction could not recover safely: {exc}")
            return rep

    inst_ver = str(manifest(root).get("system", {}).get("system_version"))
    try:
        rel_man = migrations_mod.load_unique_yaml_file(
            os.path.join(release, "SYSTEM-MANIFEST.yaml"),
            "release SYSTEM-MANIFEST.yaml",
        )
        release_distribution = rel_man["system"]["distribution_id"]
    except (migrations_mod.MigrationError, KeyError, TypeError) as exc:
        rep.error(f"release distribution identity is unreadable: {exc}")
        return rep
    if release_distribution != CORE_DISTRIBUTION:
        rep.error(
            f"release distribution {release_distribution!r} is not the supported "
            f"core distribution {CORE_DISTRIBUTION!r}"
        )
        return rep
    try:
        live_distribution = _declared_distribution(root)
    except migrations_mod.MigrationError as exc:
        rep.error(f"source distribution identity is invalid: {exc}")
        return rep
    if live_distribution is not None and live_distribution != release_distribution:
        rep.error(
            f"source distribution {live_distribution!r} does not match release "
            f"distribution {release_distribution!r}"
        )
        return rep
    rel_ver = str(rel_man.get("system", {}).get("system_version"))
    sv_i, sv_r = _semver(inst_ver), _semver(rel_ver)
    if sv_i is None or sv_r is None:
        rep.error(f"unreadable version(s): instance={inst_ver!r} release={rel_ver!r}")
        return rep
    rep.info["instance_version"] = inst_ver
    rep.info["release_version"] = rel_ver
    if sv_r == sv_i:
        rep.info["result"] = f"already at {inst_ver} — nothing to do"
        return rep
    if sv_r < sv_i:
        rep.error(f"release {rel_ver} is OLDER than this instance ({inst_ver}) — "
                  "downgrades are a restore, not an upgrade: use checkpoints/snapshots")
        return rep

    try:
        migration_plan = _resolve_system_migration(
            root, release, inst_ver, rel_ver, args)
    except (migrations_mod.MigrationError, OSError) as exc:
        rep.error(
            f"migration edge resolution FAILED — upgrade refused before "
            f"checkpoint or mutation: {exc}")
        return rep
    if migration_plan is not None:
        rep.info["migration_edge"] = {
            "migration": migration_plan["name"],
            "from_version": inst_ver,
            "to_version": rel_ver,
            "version_target": "system_version",
            "source_identity": migration_plan["source_identity"],
            "source_distribution": migration_plan["source_distribution"],
            "legacy_authorized": migration_plan["legacy_authorized"],
            "affected_paths": [
                item["path"] for item in migration_plan["effects"]],
        }

    planned = _step(
        "plan", root, lambda: _planned_upgrade(root, release, args, rep, inst_ver))
    if planned is None:
        return rep
    base, base_derived, base_src, plan, seeds = planned
    rep.info["classification_base"] = base_src
    if seeds:
        rep.info["seeded_root_files"] = seeds
    if base is not None:
        prot = _protected_prefixes(root)
        fused = [p for p in plan["keep"] + [
            c.split("  (")[0] for c in plan["conflict"]] if p.startswith(prot)]
        if len(fused) > FUSION_LIMIT:
            rep.error(f"this instance has fused customizations — {len(fused)} instance-edited "
                      "file(s) inside protected paths; a role-pack refactor must extract them "
                      "before an upgrade can run. Files: " + "; ".join(sorted(fused)[:12]))
            return rep
    for key in ("replace", "add", "remove", "keep", "conflict",
                "instance_added", "user_deleted"):
        if plan[key]:
            rep.info[key if key != "keep" else "kept_instance_edits"] = plan[key]
    rep.info["unchanged"] = plan["unchanged"]
    if "router_diff" in plan:
        rep.info["router_review"] = plan["router_diff"]

    prot = _protected_prefixes(root)
    prot_conflicts = [
        c for c in plan["conflict"]
        if c.split("  (")[0].startswith(prot)
        or c.split("  (")[0] == "SYSTEM-MANIFEST.yaml"]
    asked = set(getattr(args, "accept", None) or [])
    prot_blocking, accounted = _account_for_conflicts(
        root, release, prot_conflicts, asked)
    unmatched = sorted(asked - {c.split("  (")[0] for c in prot_conflicts})
    if unmatched:
        rep.warn("--accept named path(s) that are not in conflict in protected paths — "
                 "check the spelling; nothing was accepted for: " + "; ".join(unmatched))
    if accounted:
        rep.info["sanctioned_divergence"] = [
            f"{p} [{route}] — {why}" for p, route, why in accounted]
    blockers = []
    if prot_blocking:
        blockers.append(f"{len(prot_blocking)} unresolved protected conflict(s)")
        rep.warn(f"{len(prot_blocking)} unresolved conflict(s) in protected paths; "
                 "review and explicitly --accept each chosen divergence")
    if base is None and plan["conflict"]:
        blockers.append("classification has no trusted baseline")

    try:
        capacity = candidate_mod.preflight(
            root, release, plan, is_product_path=_in_upgrade_surface,
            seed_paths=seeds, free_bytes=_free_bytes,
            same_filesystem=_same_filesystem)
    except candidate_mod.CandidateError as exc:
        rep.error(f"candidate preflight FAILED — upgrade refused (nothing written): {exc}")
        return rep
    rep.info["plan_identity"] = capacity["plan_identity"]
    rep.info["candidate_preflight"] = (
        f"OK — same filesystem; {capacity['required_bytes']} bytes required, "
        f"{capacity['free_bytes']} available; {capacity['write_count']} planned write(s)")

    try:
        policy = protection_proof(root)
        review = _upgrade_review_plan(
            root, release, policy,
            inst_ver=inst_ver, rel_ver=rel_ver,
            live_distribution=live_distribution,
            release_distribution=release_distribution,
            base=base, base_derived=base_derived, base_src=base_src,
            plan=plan, seeds=seeds, asked=asked, accounted=accounted,
            migration_plan=migration_plan)
    except (ProtectedTargetError, OSError, ValueError,
            candidate_mod.CandidateError) as exc:
        rep.error(f"upgrade review plan could not be proven: {exc}")
        return rep
    rep.info["review_contract"] = "exact semantic inputs; final output bytes not yet materialized"
    rep.info["review_sha256"] = review.review_sha256
    rep.info["review_plan"] = review.document
    if dry:
        rep.info["mode"] = (
            "dry-run/read-only review — no checkpoint or candidate staged; re-run with "
            f"--apply --confirm --review-sha256 {review.review_sha256}")
        return rep
    supplied = str(getattr(args, "review_sha256", None) or "")
    if not (getattr(args, "confirm", False)
            and supplied == review.review_sha256):
        rep.error(
            "upgrade apply requires --apply --confirm --review-sha256 "
            f"{review.review_sha256} from a fresh read-only review; no checkpoint "
            "or candidate was created")
        return rep
    if blockers:
        rep.error("upgrade cannot produce a complete final candidate: " + "; ".join(blockers))
        rep.warn(f"system_version stays {inst_ver}; live vault unchanged: "
                 + "; ".join(blockers))
        return rep

    # Recompute the complete semantic plan immediately before the first write.
    # This catches live, release, policy, baseline, migration, and acceptance
    # changes without pretending final candidate bytes exist yet.
    fresh_rep = Report("upgrade-review-reproof")
    fresh_planned = _planned_upgrade(root, release, args, fresh_rep, inst_ver)
    try:
        if fresh_planned is None or not fresh_rep.ok:
            raise ValueError("classification inputs no longer produce a valid plan")
        fresh_base, fresh_derived, fresh_base_src, fresh_plan, fresh_seeds = fresh_planned
        fresh_migration = _resolve_system_migration(
            root, release, inst_ver, rel_ver, args)
        fresh_conflicts = [
            c for c in fresh_plan["conflict"]
            if c.split("  (")[0].startswith(prot)
            or c.split("  (")[0] == "SYSTEM-MANIFEST.yaml"]
        _fresh_blocking, fresh_accounted = _account_for_conflicts(
            root, release, fresh_conflicts, asked)
        fresh_policy = protection_proof(root)
        fresh_review = _upgrade_review_plan(
            root, release, fresh_policy,
            inst_ver=inst_ver, rel_ver=rel_ver,
            live_distribution=live_distribution,
            release_distribution=release_distribution,
            base=fresh_base, base_derived=fresh_derived,
            base_src=fresh_base_src, plan=fresh_plan, seeds=fresh_seeds,
            asked=asked, accounted=fresh_accounted,
            migration_plan=fresh_migration)
    except (ProtectedTargetError, migrations_mod.MigrationError, OSError,
            ValueError, candidate_mod.CandidateError) as exc:
        rep.error(f"upgrade review became stale before checkpoint: {exc}")
        return rep
    if fresh_review.review_sha256 != supplied:
        rep.error(
            "upgrade review became stale before checkpoint; run the read-only "
            f"review again (current review_sha256 {fresh_review.review_sha256})")
        return rep

    try:
        had_active_transaction = _active_transaction(root) is not None
        _resume_transaction(root, args, rep)
        if had_active_transaction:
            return rep
    except transaction_mod.TransactionError as exc:
        rep.error(f"unfinished upgrade transaction could not recover safely: {exc}")
        return rep

    ckpt = None
    checkpoint_identity = None
    checkpoint_report = Report("checkpoint")

    def checkpoint():
        setattr(args, "message", f"pre-upgrade {inst_ver} -> {rel_ver}")
        prior_zip_only = getattr(args, "zip_only", False)
        if migration_plan is not None:
            setattr(args, "zip_only", True)
        try:
            return ckpt_mod.run(root, args, checkpoint_report)
        finally:
            setattr(args, "zip_only", prior_zip_only)

    _step("checkpoint", root, checkpoint)
    if not checkpoint_report.ok:
        rep.error("checkpoint FAILED — upgrade refused (nothing written)")
        rep.errors += checkpoint_report.errors[:3]
        return rep
    ckpt = checkpoint_report.info.get("checkpoint", "?")
    rep.info["checkpoint"] = ckpt
    checkpoint_identity = checkpoint_report.info.get("checkpoint_identity")
    # Recovery qualification must execute what the product actually issued,
    # never reconstruct a plausible command from checkpoint identity fields.
    # Preserve the checkpoint rendering byte-for-byte in the public upgrade
    # report.  Older/test checkpoint providers that do not expose the field do
    # not gain an inferred substitute.
    if "rollback_command" in checkpoint_report.info:
        rollback_command = checkpoint_report.info["rollback_command"]
        if not isinstance(rollback_command, str) or not rollback_command:
            rep.error(
                "checkpoint FAILED — exact rollback command is malformed")
            return rep
        rep.info["rollback_command"] = rollback_command
    if migration_plan is not None and (
        not isinstance(checkpoint_identity, dict)
        or checkpoint_identity.get("kind") != "zip-snapshot"
        or checkpoint_identity.get("coverage") != "whole-tree"
        or checkpoint_identity.get("exact_recovery") is not True
    ):
        rep.error(
            "checkpoint FAILED — migration requires a verified whole-tree "
            "ZIP snapshot identity")
        return rep

    return _finish_upgrade_transaction(
        root, release, args, rep, inst_ver, rel_ver, ckpt,
        checkpoint_identity, base_src, plan, seeds, accounted,
        migration_plan, review, policy)


def _finish_upgrade_transaction(root, release, args, rep, inst_ver, rel_ver,
                                ckpt, checkpoint_identity, base_src, plan,
                                seeds, accounted, migration_plan, review,
                                review_policy):
    pre_user = _user_world(root)
    ledger_before = (
        migrations_mod.load_ledger(root) if migration_plan is not None else [])
    live_journal = os.path.join(root, "System", "Journal", "change-journal.md")
    journal_before = b""
    if os.path.exists(live_journal):
        with open(live_journal, "rb") as stream:
            journal_before = stream.read()
    candidate = None
    transaction_started = False
    commit_attempted = False
    try:
        _reprove_upgrade_review_trees(
            root, release, review_policy, review)
        candidate = candidate_mod.build_candidate(
            root, release, plan, is_product_path=_in_upgrade_surface,
            seed_paths=seeds, boundary=_transaction_boundary,
            free_bytes=_free_bytes, same_filesystem=_same_filesystem)
        _reprove_upgrade_review_trees(
            root, release, review_policy, review)
        candidate_root = candidate["candidate"]
        written = len(plan["replace"]) + len(plan["add"])
        rep.info["files_written"] = written

        from cmd import generate as g_mod, validate as v_mod, health as h_mod
        from cmd import docgen as dg_mod

        def bump_version():
            mpath = os.path.join(candidate_root, "SYSTEM-MANIFEST.yaml")
            with open(mpath, encoding="utf-8") as stream:
                text = stream.read()
            note = (
                f"# upgraded from {inst_ver} via aios upgrade (see CHANGELOG in the release)"
                if not accounted else
                f"# upgraded from {inst_ver} via aios upgrade — {len(accounted)} declared "
                f"divergence(s) kept: {', '.join(p for p, _, _ in accounted)} "
                "(see the upgrade report)")
            new_text = re.sub(
                r"(system_version:\s*)\S+(\s*(#.*)?)",
                rf"\g<1>{rel_ver}       {note}", text, count=1)
            if new_text == text:
                raise candidate_mod.CandidateError(
                    "candidate manifest version line could not be updated")
            declared = _declared_distribution(candidate_root)
            if declared is None:
                if migration_plan is None or not migration_plan["legacy_authorized"]:
                    raise candidate_mod.CandidateError(
                        "candidate has no distribution identity and was not "
                        "authorized as an exact legacy core source"
                    )
                new_text, inserted = re.subn(
                    r"^(system:\s*(?:#.*)?\n)",
                    rf"\g<1>  distribution_id: {CORE_DISTRIBUTION}\n",
                    new_text,
                    count=1,
                    flags=re.MULTILINE,
                )
                if inserted != 1:
                    raise candidate_mod.CandidateError(
                        "candidate distribution identity could not be inserted"
                    )
            elif declared != CORE_DISTRIBUTION:
                raise candidate_mod.CandidateError(
                    f"candidate distribution changed to {declared!r}"
                )
            with open(mpath, "w", encoding="utf-8") as stream:
                stream.write(new_text)

        _step("version-bump", root, bump_version)
        rep.info["system_version"] = f"{inst_ver} -> {rel_ver}"

        if migration_plan is not None:
            def migrate_candidate():
                authorization = candidate_mod.authorize_migration(
                    candidate,
                    root=root,
                    migration_name=migration_plan["name"],
                    source_identity=migration_plan["source_identity"],
                    source_distribution=migration_plan["source_distribution"],
                    manifest_hash=migration_plan["manifest_hash"],
                    effects=migration_plan["effects"],
                    outer_checkpoint=checkpoint_identity,
                    system_source_version=inst_ver,
                )
                sub = Report("migrate")
                migrate_mod._run_upgrade_candidate(
                    candidate_root, args, sub, authorization)
                rep.info["gate_migration"] = (
                    "OK" if sub.ok else f"{len(sub.errors)} errors")
                rep.info["migration_result"] = sub.info.get("result")
                if not sub.ok:
                    rep.errors += sub.errors[:10]

            _step("migration", root, migrate_candidate)
            if not rep.ok:
                rep.warn(
                    f"system_version stays {inst_ver} — migration failed in "
                    "candidate; live vault unchanged")
                return rep

        def generate_candidate():
            dg = Report("docgen")
            n_blocks, dg_files = dg_mod.regenerate_within(
                candidate_root, dg, _in_upgrade_surface)
            if n_blocks:
                rep.info["censuses_regenerated"] = (
                    f"{n_blocks} docgen block(s) recounted against THIS vault "
                    f"in {len(dg_files)} file(s): " + ", ".join(dg_files))
            rep.errors += dg.errors[:3]
            sub = Report("generate")
            g_mod.run(candidate_root, args, sub)
            rep.info["gate_generate"] = (
                "OK" if sub.ok else f"{len(sub.errors)} errors")
            rep.errors += sub.errors[:6]

        _step("generation", root, generate_candidate)

        _step(
            "report-write", root,
            lambda: _write_candidate_report(
                candidate_root, plan, accounted, inst_ver, rel_ver,
                ckpt, base_src, written, rep))

        def validate_candidate():
            for name, mod in (("validate", v_mod), ("health", h_mod)):
                sub = Report(name)
                mod.run(candidate_root, args, sub)
                rep.info[f"gate_{name}"] = (
                    "OK" if sub.ok else f"{len(sub.errors)} errors")
                rep.errors += sub.errors[:6]

        _step("validation", root, validate_candidate)
        post_user = _user_world(candidate_root)
        if post_user != pre_user:
            drift = sorted(k for k in set(pre_user) | set(post_user)
                           if pre_user.get(k) != post_user.get(k))
            seeded = {s.replace(os.sep, "/") for s in seeds}
            real = [k for k in drift
                    if not k.replace(os.sep, "/").startswith(".claude/skills/")
                    and k.replace(os.sep, "/") not in seeded
                    and k != "SYSTEM-MANIFEST.yaml"
                    and not _is_runtime_state(k)]
            migration_allowed, migration_mismatches = (
                _migration_integrity_accounting(
                    pre_user, post_user,
                    migration_plan["effects"] if migration_plan else []))
            real = [path for path in real if path not in migration_allowed]
            if migration_allowed:
                rep.info["migration_affected_paths"] = sorted(
                    migration_allowed)
            if migration_mismatches:
                rep.info["migration_integrity_mismatches"] = (
                    migration_mismatches)
            candidate_journal = os.path.join(
                candidate_root, "System", "Journal", "change-journal.md")
            if "System/Journal/change-journal.md" in real:
                with open(candidate_journal, "rb") as stream:
                    journal_after = stream.read()
                suffix = journal_after[len(journal_before):]
                if (journal_after.startswith(journal_before)
                        and b" \xc2\xb7 upgrade \xc2\xb7 " in suffix):
                    real.remove("System/Journal/change-journal.md")
            ledger_rel = "System/Journal/migration-ledger.jsonl"
            if migration_plan is not None and ledger_rel in real:
                try:
                    ledger_after = migrations_mod.load_ledger(candidate_root)
                    appended = ledger_after[len(ledger_before):]
                    if (
                        ledger_after[:len(ledger_before)] == ledger_before
                        and len(appended) == 1
                        and appended[0]["id"] == migration_plan["id"]
                        and appended[0]["manifest_hash"]
                        == migration_plan["manifest_hash"]
                        and appended[0]["source_identity"]
                        == migration_plan["source_identity"]
                        and appended[0]["source_distribution"]
                        == migration_plan["source_distribution"]
                    ):
                        real.remove(ledger_rel)
                        rep.info["migration_ledger"] = (
                            "one exact applied record appended")
                except migrations_mod.MigrationError as exc:
                    rep.info["migration_ledger_error"] = str(exc)
            session = [k for k in drift if _is_runtime_state(k)]
            if session:
                rep.info["editor_session_state"] = (
                    f"{', '.join(session)} — application session state changed "
                    "during candidate generation; reported, not counted")
            if real:
                rep.error(f"CONTENT INTEGRITY FAILURE in candidate — "
                          f"{len(real)} user file(s) changed")
                rep.info["changed_user_files"] = real[:20]
            else:
                rep.info["user_content"] = (
                    f"byte-identical — {len(pre_user)} files verified "
                    f"({_verify_scope()}); {len(drift)} declared final-state difference(s); "
                    f"{len(session)} editor session-state file(s) reported, not counted")
        else:
            rep.info["user_content"] = (
                f"byte-identical — {len(pre_user)} files verified ({_verify_scope()})")
        if not rep.ok:
            rep.warn(f"system_version stays {inst_ver} — gates red in candidate; "
                     "live vault unchanged after checkpoint")
            return rep
        if candidate_mod.tree_identity(root) != candidate["source_identity"]:
            raise candidate_mod.CandidateError(
                "live vault changed after candidate capture; refusing commit")

        candidate_mod.retain_as_sibling(candidate, root=root)
        candidate_path = candidate["candidate"]
        live_pin = candidate["source_identity"]
        candidate_pin = candidate["candidate_identity"]
        if candidate_mod.tree_identity(root) != live_pin:
            raise candidate_mod.CandidateError(
                "live vault changed before transaction preparation")
        if candidate_mod.tree_identity(candidate_path) != candidate_pin:
            raise candidate_mod.CandidateError(
                "final candidate changed before transaction preparation")
        suffix = os.path.basename(candidate_path).rsplit("-", 1)[-1]
        journal = os.path.join(
            os.path.dirname(root),
            f".{os.path.basename(root)}.upgrade-transaction-{suffix}.json")
        try:
            previous_cwd = os.getcwd()
        except FileNotFoundError:
            # A caller can outlive its working directory (for example, a test
            # fixture or an editor removes a temporary folder).  Whole-root
            # exchange must not depend on that stale process-local handle.
            previous_cwd = None
        inside_live = previous_cwd is not None and (
            os.path.realpath(previous_cwd) == os.path.realpath(root)
            or os.path.realpath(previous_cwd).startswith(
                os.path.realpath(root) + os.sep))
        if previous_cwd is None or inside_live:
            os.chdir(os.path.dirname(root))
        try:
            transaction_mod.prepare_swap(
                root, candidate_path, journal,
                original_content_identity=live_pin,
                candidate_content_identity=candidate_pin,
                context={
                    "schema": "aios-upgrade-recovery-v1",
                    "migration_plan": migration_plan,
                })
            transaction_started = True
            if candidate_mod.tree_identity(root) != live_pin:
                raise candidate_mod.CandidateError(
                    "live vault changed after transaction preparation")
            if candidate_mod.tree_identity(candidate_path) != candidate_pin:
                raise candidate_mod.CandidateError(
                    "final candidate changed after transaction preparation")
            commit_attempted = True
            result = transaction_mod.commit_swap(
                root, candidate_path, journal,
                boundary=_transaction_boundary,
                content_identity=candidate_mod.tree_identity)
        finally:
            if previous_cwd is not None and os.path.isdir(previous_cwd):
                os.chdir(previous_cwd)
        rep.info["transaction"] = result["status"]
        candidate = None
        if not _post_swap_proof(
                root, candidate_path, args, rep,
                migration_plan=migration_plan):
            rolled = transaction_mod.rollback_swap(
                root, candidate_path, journal,
                boundary=_transaction_boundary,
                content_identity=candidate_mod.tree_identity)
            if candidate_mod.tree_identity(root) != live_pin:
                raise transaction_mod.TransactionError(
                    "automatic post-proof rollback did not restore exact old tree")
            rep.info["transaction_rollback"] = rolled["status"]
            rep.info["failed_candidate"] = candidate_path
            rep.info["transaction_journal"] = journal
            rep.error(f"post-swap proof failed; exact old live tree restored "
                      f"automatically. Failed new tree: {candidate_path}; "
                      f"journal: {journal}")
            return rep
        try:
            cleaned = transaction_mod.cleanup_swap(
                root, candidate_path, journal, confirm=True,
                boundary=_transaction_boundary,
                content_identity=candidate_mod.tree_identity)
            rep.info["transaction_cleanup"] = cleaned["status"]
            candidate_mod.remove_retained_marker(root, candidate_path)
        except Exception as exc:
            rep.warn(f"upgrade committed, but cleanup is pending and resumable: {exc}")
        return rep
    except (candidate_mod.CandidateError, transaction_mod.TransactionError,
            safepaths.SafePathError, ProtectedTargetError, OSError) as exc:
        if commit_attempted:
            rep.error(f"transaction failed; automatic rollback was requested: {exc}")
        elif transaction_started:
            rep.error(f"transaction prepared but commit refused; live vault unchanged, "
                      f"candidate and journal preserved for recovery: {exc}")
        else:
            rep.error(
                "candidate preparation failed — no candidate or live-tree swap "
                f"was performed after checkpoint: {exc}")
        return rep
    finally:
        if candidate is not None and not transaction_started:
            try:
                candidate_mod.delete_candidate(candidate, root=root)
            except Exception as cleanup_exc:
                rep.warn(f"discarded candidate cleanup is pending: {cleanup_exc}")


def _active_transaction(root):
    """Find the one unfinished sibling upgrade journal, if any."""
    live = os.path.realpath(os.path.abspath(root))
    prefix = f".{os.path.basename(live)}.upgrade-transaction-"
    found = []
    for name in os.listdir(os.path.dirname(live)):
        if not name.startswith(prefix) or not name.endswith(".json"):
            continue
        path = os.path.join(os.path.dirname(live), name)
        try:
            with open(path, encoding="utf-8") as stream:
                data = json.load(stream)
        except Exception as exc:
            raise transaction_mod.TransactionError(
                f"upgrade journal is unreadable: {path} ({exc})") from exc
        if data.get("state") != "cleaned" and data.get("live") == live:
            found.append((path, data))
    if len(found) > 1:
        raise transaction_mod.TransactionError(
            "multiple unfinished upgrade journals exist; refusing to guess")
    return found[0] if found else None


def _post_swap_proof(root, old_side, args, rep, migration_plan=None):
    """Re-prove canonical live before authorizing destruction of the old side."""
    from cmd import validate as v_mod, health as h_mod
    errors_before = len(rep.errors)
    for name, mod in (("validate", v_mod), ("health", h_mod)):
        sub = Report(f"post-swap-{name}")
        mod.run(root, args, sub)
        rep.info[f"post_swap_{name}"] = (
            "OK" if sub.ok else f"{len(sub.errors)} errors")
        rep.errors += sub.errors[:6]
    old_user = _user_world(old_side)
    new_user = _user_world(root)
    drift = sorted(k for k in set(old_user) | set(new_user)
                   if old_user.get(k) != new_user.get(k))
    allowed = []
    real = []
    for rel in drift:
        posix = rel.replace(os.sep, "/")
        additive = (
            posix == "To-Do.md" or posix.startswith("Decisions/"))
        if (posix.startswith(".claude/skills/")
                or posix == "SYSTEM-MANIFEST.yaml"
                or _is_runtime_state(posix)
                or (additive and rel not in old_user)):
            allowed.append(rel)
        else:
            real.append(rel)
    journal_rel = "System/Journal/change-journal.md"
    if journal_rel in real:
        old_journal = os.path.join(old_side, *journal_rel.split("/"))
        new_journal = os.path.join(root, *journal_rel.split("/"))
        old_bytes = b""
        if os.path.exists(old_journal):
            with open(old_journal, "rb") as stream:
                old_bytes = stream.read()
        new_bytes = b""
        if os.path.exists(new_journal):
            with open(new_journal, "rb") as stream:
                new_bytes = stream.read()
        suffix = new_bytes[len(old_bytes):]
        if (new_bytes.startswith(old_bytes)
                and b" \xc2\xb7 upgrade \xc2\xb7 " in suffix):
            real.remove(journal_rel)
            allowed.append(journal_rel)
    if migration_plan is not None:
        migration_allowed, mismatches = _migration_integrity_accounting(
            old_user, new_user, migration_plan["effects"])
        real = [rel for rel in real if rel not in migration_allowed]
        allowed.extend(sorted(migration_allowed))
        if mismatches:
            rep.info["post_swap_migration_integrity_mismatches"] = mismatches
        ledger_rel = "System/Journal/migration-ledger.jsonl"
        if ledger_rel in real:
            try:
                old_records = migrations_mod.load_ledger(old_side)
                new_records = migrations_mod.load_ledger(root)
                appended = new_records[len(old_records):]
                if (
                    new_records[:len(old_records)] == old_records
                    and len(appended) == 1
                    and appended[0]["id"] == migration_plan["id"]
                    and appended[0]["manifest_hash"]
                    == migration_plan["manifest_hash"]
                    and appended[0]["source_identity"]
                    == migration_plan["source_identity"]
                    and appended[0]["source_distribution"]
                    == migration_plan["source_distribution"]
                ):
                    real.remove(ledger_rel)
                    allowed.append(ledger_rel)
            except migrations_mod.MigrationError as exc:
                rep.info["post_swap_migration_ledger_error"] = str(exc)
    if real:
        rep.error(f"post-swap user evidence failed — {len(real)} unexpected "
                  "user-owned path(s) differ from preserved old tree")
        rep.info["post_swap_changed_user_files"] = real[:20]
    else:
        rep.info["post_swap_user_evidence"] = (
            f"{len(old_user)} old-side files compared; "
            f"{len(allowed)} declared generated/journal/seed/session difference(s)")
    return len(rep.errors) == errors_before


def _validate_recovery_migration_plan(value):
    """Fail closed on persisted proof before granting migration exemptions."""
    if value is None:
        return None
    required = {
        "name", "id", "source_identity", "source_distribution",
        "legacy_authorized", "manifest_hash", "effects",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise transaction_mod.TransactionError(
            "upgrade recovery migration plan fields are incomplete or unknown"
        )
    if (
        not isinstance(value["name"], str)
        or not re.fullmatch(r"[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*", value["name"])
        or not isinstance(value["id"], str)
        or not re.fullmatch(
            r"migration-[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*", value["id"]
        )
        or value["source_distribution"] != CORE_DISTRIBUTION
        or not isinstance(value["legacy_authorized"], bool)
        or not isinstance(value["source_identity"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["source_identity"])
        or not isinstance(value["manifest_hash"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["manifest_hash"])
        or not isinstance(value["effects"], list)
        or not value["effects"]
    ):
        raise transaction_mod.TransactionError(
            "upgrade recovery migration plan identity is invalid"
        )
    effect_keys = {
        "path", "accepted_old_sha256", "matched_old_sha256",
        "new_sha256", "needs_write",
    }
    for effect in value["effects"]:
        accepted = effect.get("accepted_old_sha256") if isinstance(effect, dict) else None
        if (
            not isinstance(effect, dict)
            or set(effect) != effect_keys
            or not isinstance(effect["path"], str)
            or not effect["path"]
            or "\\" in effect["path"]
            or os.path.isabs(effect["path"])
            or Path(effect["path"]).as_posix() != effect["path"]
            or any(
                part in {"", ".", ".."} for part in Path(effect["path"]).parts
            )
            or not isinstance(accepted, list)
            or not accepted
            or any(
                not isinstance(item, str)
                or (item != "absent" and not re.fullmatch(r"[0-9a-f]{64}", item))
                for item in accepted
            )
            or len(set(accepted)) != len(accepted)
            or effect["matched_old_sha256"] not in accepted
            or not isinstance(effect["new_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", effect["new_sha256"])
            or not isinstance(effect["needs_write"], bool)
        ):
            raise transaction_mod.TransactionError(
                "upgrade recovery migration effect is invalid"
            )
    return value


def _resume_transaction(root, args, rep):
    active = _active_transaction(root)
    if not active:
        return
    journal, data = active
    context = data.get("context")
    if (
        not isinstance(context, dict)
        or set(context) != {"schema", "migration_plan"}
        or context.get("schema") != "aios-upgrade-recovery-v1"
    ):
        raise transaction_mod.TransactionError(
            "unfinished upgrade journal lacks exact recovery proof context"
        )
    migration_plan = _validate_recovery_migration_plan(
        context.get("migration_plan"))
    candidate = data.get("candidate")
    if not isinstance(candidate, str):
        raise transaction_mod.TransactionError(
            "unfinished journal has no candidate path")
    if data.get("state") == "cleanup":
        if not _post_swap_proof(
            root, candidate, args, rep, migration_plan=migration_plan
        ):
            raise transaction_mod.TransactionError(
                "cleanup resume refused because post-swap proof failed; "
                "preserved old tree and journal were not deleted"
            )
        cleaned = transaction_mod.cleanup_swap(
            root, candidate, journal, confirm=True,
            boundary=_transaction_boundary,
            content_identity=candidate_mod.tree_identity)
        rep.info["transaction_resume"] = "cleanup"
        rep.info["transaction_cleanup"] = cleaned["status"]
        candidate_mod.remove_retained_marker(root, candidate)
        return
    result = transaction_mod.commit_swap(
        root, candidate, journal, boundary=_transaction_boundary,
        content_identity=candidate_mod.tree_identity)
    rep.info["transaction_resume"] = result["status"]
    if result["status"] in ("committed", "already-committed"):
        if not _post_swap_proof(
                root, candidate, args, rep,
                migration_plan=migration_plan):
            old_identity = candidate_mod.tree_identity(candidate)
            rolled = transaction_mod.rollback_swap(
                root, candidate, journal,
                boundary=_transaction_boundary,
                content_identity=candidate_mod.tree_identity)
            if candidate_mod.tree_identity(root) != old_identity:
                raise transaction_mod.TransactionError(
                    "resumed post-proof rollback did not restore exact old tree")
            rep.info["transaction_rollback"] = rolled["status"]
            rep.info["failed_candidate"] = candidate
            rep.info["transaction_journal"] = journal
            raise transaction_mod.TransactionError(
                f"resumed commit failed post-swap proof and exact old live tree "
                f"was restored automatically; failed new tree: {candidate}; "
                f"journal: {journal}")
        cleaned = transaction_mod.cleanup_swap(
            root, candidate, journal, confirm=True,
            boundary=_transaction_boundary,
            content_identity=candidate_mod.tree_identity)
        rep.info["transaction_cleanup"] = cleaned["status"]
        candidate_mod.remove_retained_marker(root, candidate)
    elif result["status"] == "rolled-back":
        cleaned = transaction_mod.cleanup_swap(
            root, candidate, journal, confirm=True,
            boundary=_transaction_boundary,
            content_identity=candidate_mod.tree_identity)
        rep.info["transaction_cleanup"] = cleaned["status"]
        candidate_mod.remove_retained_marker(root, candidate)


def _planned_upgrade(root, release, args, rep, inst_ver):
    base, base_derived, base_src = _load_base(root, args, rep, inst_ver)
    if base_src == "error":
        return None
    plan = _classify(root, release, base, base_derived)
    seeds = _additive_seeds(root, release)
    if seeds:
        plan["add"] += seeds
    if any(c.split("  (")[0] == ROUTER for c in plan["conflict"]):
        plan["router_diff"] = _router_row_diff(
            os.path.join(root, ROUTER), os.path.join(release, ROUTER))
    return base, base_derived, base_src, plan, seeds


def _write_candidate_report(candidate_root, plan, accounted, inst_ver, rel_ver,
                            ckpt, base_src, written, rep):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    logs = os.path.join(candidate_root, "System", "Logs")
    os.makedirs(logs, exist_ok=True)
    rpath = os.path.join(logs, f"upgrade-report-{stamp}.md")
    lines = [f"# Upgrade report — {inst_ver} -> {rel_ver} ({stamp})",
             f"- checkpoint: {ckpt}", f"- classification base: {base_src}", ""]
    for key in ("replace", "add", "remove", "keep", "conflict",
                "instance_added", "user_deleted"):
        if plan[key]:
            lines.append(f"## {key} ({len(plan[key])})")
            lines += [f"- {p}" for p in plan[key]] + [""]
    if accounted:
        lines.append("## declared divergence — kept (DEC-111)")
        lines += [f"- **{p}** [{route}] — {why}"
                  for p, route, why in accounted] + [""]
    if "router_diff" in plan:
        lines.append("## router review (DEC-073)")
        lines += [f"- {d}" for d in plan["router_diff"]] + [""]
    with open(rpath, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    rep.info["report"] = os.path.relpath(rpath, candidate_root)
    journal = os.path.join(candidate_root, "System", "Journal", "change-journal.md")
    if os.path.exists(journal):
        with open(journal, "a", encoding="utf-8") as stream:
            stream.write(
                f"\n- {datetime.date.today().isoformat()} · upgrade · "
                f"{inst_ver} -> {rel_ver} · {written} files, "
                f"{len(plan['conflict'])} conflicts · checkpoint {ckpt}")


def _load_base(root, args, rep: Report, inst_ver):
    """The base file-hash map (what this instance's version shipped as), or
    None → fallback mode: every difference is a conflict, nothing replaced.
    A wrong base silently overwrites user work — the plan-killer — so a
    version-mismatched baseline is refused, not trusted."""
    override = getattr(args, "base", None)
    if override:
        if os.path.isdir(override):
            if not os.path.exists(os.path.join(override, "SYSTEM-MANIFEST.yaml")):
                rep.error(f"--base {override}: not a vault/release tree (no SYSTEM-MANIFEST.yaml)")
                return None, {}, "error"
            return _hash_tree(override), _neutralised_tree(override), f"tree {override}"
        try:
            with open(override, encoding="utf-8") as stream:
                data = json.load(stream)
            return dict(data["files"]), dict(data.get("derived", {})), f"baseline {override}"
        except Exception as e:                                    # noqa: BLE001
            rep.error(f"--base {override}: unreadable baseline ({e})")
            return None, {}, "error"
    own = os.path.join(root, BASELINE)
    if os.path.exists(own):
        try:
            with open(own, encoding="utf-8") as stream:
                data = json.load(stream)
        except Exception as e:                                    # noqa: BLE001
            rep.warn(f"shipped baseline unreadable ({e}) — fallback mode")
            return None, {}, "fallback"
        if str(data.get("system_version")) != str(inst_ver):
            rep.warn(f"shipped baseline records {data.get('system_version')} but the "
                     f"instance is at {inst_ver} — refusing to trust it; fallback mode "
                     "(pass --base <old release tree or baseline json> for exact classification)")
            return None, {}, "fallback"
        return dict(data.get("files", {})), dict(data.get("derived", {})), "shipped baseline"
    rep.warn("no baseline for this instance's version — fallback mode: every "
             "differing file is a conflict; nothing is replaced without evidence "
             "(pass --base <old release tree or baseline json> for exact classification)")
    return None, {}, "fallback"


def _semver(v):
    try:
        return tuple(int(x) for x in str(v).split("-")[0].split("."))
    except ValueError:
        return None


def _protected_prefixes(root):
    prot = manifest(root).get("protected_objects", []) or []
    return tuple(p.rstrip("/") + "/" if p.endswith("/") else p
                 for p in prot if p.startswith("System/"))


def _router_row_diff(inst_path, rel_path):
    """Per-row router diff (DEC-073): which intents exist only on one side or
    differ — the review list a human resolves by hand. Never merged."""
    try:
        with open(inst_path, encoding="utf-8") as stream:
            a = yaml.safe_load(stream) or {}
        with open(rel_path, encoding="utf-8") as stream:
            b = yaml.safe_load(stream) or {}
    except Exception as e:                                        # noqa: BLE001
        return [f"router unparsable ({e}) — diff the file by hand"]
    out = []
    am, bm = a.get("modes", {}) or {}, b.get("modes", {}) or {}
    for mode in sorted(set(am) | set(bm)):
        ai, bi = am.get(mode, {}) or {}, bm.get(mode, {}) or {}
        for intent in sorted(set(ai) | set(bi)):
            if intent not in bi:
                out.append(f"{mode}.{intent}: only in YOUR router (instance row — re-add after review)")
            elif intent not in ai:
                out.append(f"{mode}.{intent}: only in the NEW release (new core row)")
            elif ai[intent] != bi[intent]:
                out.append(f"{mode}.{intent}: differs (compare load lists by hand)")
    return out or ["files differ outside modes: (fallback/version keys) — diff by hand"]


def _neutralised_sha(path):
    """sha256 of a file with every docgen BODY blanked, or None if it carries no
    generated region (or cannot be read as text).

    This is what lets classification ask the right question. A file whose only
    deviation from the version it shipped with is inside a generated block was
    not edited by anybody — the instance was REQUIRED to recount it. Comparing
    raw hashes calls that an instance customization, and then a release that
    also touches the file produces a "conflict" in which nobody actually
    disagreed about anything."""
    try:
        with open(path, encoding="utf-8") as stream:
            text = stream.read()
    except (OSError, UnicodeDecodeError):
        return None
    if not _DOCGEN_REGION.search(text):
        return None
    return hashlib.sha256(_neutralise_generated(text).encode("utf-8")).hexdigest()


def _neutralised_tree(root):
    return {rel: n for rel, p in _system_files(root).items()
            if (n := _neutralised_sha(p)) is not None}


def _neutralise_generated(text):
    """Blank the BODY of every docgen region, keeping its markers.

    What survives is the hand-written prose — the only part of a generated doc a
    human can disagree about. Two copies that match after this differ solely in
    numbers each side counted from its own tree."""
    return _DOCGEN_REGION.sub(lambda m: m.group(1) + m.group(4), text)


def _derived_only(inst_path, rel_path):
    """True when instance and release differ ONLY inside docgen regions.

    Deliberately strict in three ways, because this route grants a version bump:
      * the file must contain at least one docgen region (otherwise a plain
        conflict could never qualify);
      * everything outside the regions must be byte-identical — one edited
        sentence disqualifies the whole file, which is what stops this being a
        blanket exemption for any doc that happens to carry a census;
      * unreadable/undecodable files are never derived (fail closed)."""
    try:
        with open(inst_path, encoding="utf-8") as stream:
            a = stream.read()
        with open(rel_path, encoding="utf-8") as stream:
            b = stream.read()
    except (OSError, UnicodeDecodeError):
        return False
    if not _DOCGEN_REGION.search(a) or not _DOCGEN_REGION.search(b):
        return False
    return _neutralise_generated(a) == _neutralise_generated(b)


def _account_for_conflicts(root, release, prot_conflicts, accepted):
    """Split protected-path conflicts into (blocking, accounted).

    `accounted` is a list of (path, route, reason) — every one of them a reason
    recorded in the report, never a silently skipped check."""
    blocking, accounted = [], []
    for c in prot_conflicts:
        rel = c.split("  (")[0]
        if rel in SANCTIONED_DIVERGENCE:
            accounted.append((rel, "sanctioned", SANCTIONED_DIVERGENCE[rel]))
        elif rel in accepted:
            accounted.append((rel, "accepted", "reviewed and accepted by the human "
                                               "running this upgrade (--accept)"))
        elif _derived_only(os.path.join(root, rel), os.path.join(release, rel)):
            accounted.append((rel, "derived", "differs only inside docgen-generated "
                                              "regions, which `aios docgen --check` "
                                              "requires this instance to regenerate "
                                              "from its own tree"))
        else:
            blocking.append(c)
    return blocking, accounted


def _classify(root, release, base, base_derived=None):
    """Three-way classification. Returns dict of lists keyed by action.
    conflict/keep/instance_added are never written; replace/add/remove are the
    entire write set.

    `base_derived` (DEC-111) carries the base's generated-body-blanked hashes.
    Where an instance file differs from base ONLY inside its docgen regions, the
    user edited nothing — the instance was required to recount those blocks — so
    it is treated as PRISTINE and takes the release's copy, which the post-copy
    regeneration then recounts against this vault. Without this, every instance
    that obeyed `docgen --check` looked customized in its own constitution, and
    the next release to touch that file produced a conflict in which nobody had
    disagreed about anything. Omitted/empty (a pre-v1.56.0 baseline) = exactly
    the old behaviour."""
    inst = {rel: _sha(p) for rel, p in _system_files(root).items()}
    inst_paths = _system_files(root)
    if base_derived:
        for rel, bn in base_derived.items():
            if rel in inst_paths and inst.get(rel) != (base or {}).get(rel):
                if _neutralised_sha(inst_paths[rel]) == bn:
                    inst[rel] = (base or {}).get(rel)   # censuses only: not an edit
    rel_files = {rel: _sha(p) for rel, p in _system_files(release).items()}
    plan = {"replace": [], "add": [], "remove": [], "keep": [], "conflict": [],
            "instance_added": [], "unchanged": 0, "user_deleted": []}
    for rel in sorted(set(inst) | set(rel_files) | set(base or {})):
        i, r = inst.get(rel), rel_files.get(rel)
        b = (base or {}).get(rel)
        if i is not None and r is not None and i == r:
            plan["unchanged"] += 1
        elif base is None:                       # fallback: no evidence, no writes
            if i is None:
                plan["add"].append(rel)
            elif r is None:
                plan["conflict"].append(rel + "  (present locally, absent in release — no base to judge)")
            else:
                plan["conflict"].append(rel)
        elif i is None and b is None:            # new in release
            plan["add"].append(rel)
        elif i is None:                          # user deleted a shipped file
            if b == r:
                plan["user_deleted"].append(rel)             # product unchanged: respect the deletion
            elif r is None:
                plan["user_deleted"].append(rel)             # gone on both sides
            else:
                plan["conflict"].append(rel + "  (you deleted it; the release changed it)")
        elif r is None:                          # gone from the release
            if b is None:
                plan["instance_added"].append(rel)           # never shipped: user's file
            elif i == b:
                plan["remove"].append(rel)                   # pristine + retired by product
            else:
                plan["conflict"].append(rel + "  (you changed it; the release removed it)")
        elif b is None:                          # both have it, never in base
            plan["conflict"].append(rel)
        elif i == b:
            plan["replace"].append(rel)                      # pristine → take the new one
        elif r == b:
            plan["keep"].append(rel)                         # only you changed it
        else:
            plan["conflict"].append(rel)                     # changed on both sides
    return plan
