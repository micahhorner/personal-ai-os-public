#!/usr/bin/env python3
"""Generate evidence-bound historical core migration edges.

Versions 1.43.0--1.63.0 require exact transitions for all eight pristine
user-surface stamps and the legacy core license. Official 1.64.0 has a direct
bridge edge. Official 1.64.1 has a source-identity-bound, license-only exact
postcondition edge. Every supported source moves directly to the target;
the runner deliberately does not rewrite identical bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import yaml


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "System/Migrations"
CATALOG = MIGRATIONS / "historical-sources.yaml"
ABOUT_PATHS = [
    "00 Inbox/_ABOUT.md",
    "10 Projects/_ABOUT.md",
    "20 Knowledge/_ABOUT.md",
    "30 Sources/_ABOUT.md",
    "40 Outputs/_ABOUT.md",
    "80 User/_ABOUT.md",
    "90 Archive/_ABOUT.md",
    "Decisions/_ABOUT.md",
]
sys.path.insert(0, str(ROOT / "System/Scripts"))

from lib.migrations import compute_manifest_hash  # noqa: E402


class GenerationError(RuntimeError):
    pass


def _history_repository() -> Path:
    """Use a source-check-only history authority when the strict runner sets it."""
    repository = os.environ.get("AIOS_SOURCE_AUTHORITY_REPOSITORY")
    commit = os.environ.get("AIOS_SOURCE_AUTHORITY_COMMIT")
    if not repository and not commit:
        return ROOT
    if not repository or not commit or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise GenerationError("strict historical authority environment is incomplete")
    return Path(repository)


def git_bytes(commit: str, path: str) -> bytes:
    repository = _history_repository()
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=repository,
        capture_output=True,
    )
    if completed.returncode:
        raise GenerationError(
            f"cannot read exact Git object {commit}:{path}: "
            f"{completed.stderr.decode(errors='replace').strip()}"
        )
    return completed.stdout


def source_identity(commit: str) -> tuple[str, str]:
    try:
        baseline = json.loads(
            git_bytes(commit, "System/.baseline-manifest.json"),
            object_pairs_hook=_unique_json,
        )
        version = baseline["system_version"]
        files = baseline["files"]
    except (KeyError, json.JSONDecodeError) as exc:
        raise GenerationError(f"{commit}: invalid baseline manifest: {exc}") from exc
    canonical = json.dumps(
        {"files": files, "system_version": version},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return str(version), hashlib.sha256(canonical).hexdigest()


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GenerationError(f"duplicate baseline JSON key: {key}")
        result[key] = value
    return result


def load_catalog() -> dict:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise GenerationError("historical source catalog schema is invalid")
    return data


def edge_name(sequence: int, version: str) -> str:
    return f"{sequence:03d}-about-stamp-from-{version.replace('.', '-')}"


def expected_files(catalog: dict) -> dict[Path, bytes]:
    target = catalog["target"]
    about_surfaces = target["about_surfaces"]
    bridge_root_surfaces = target["official_1_64_root_surfaces"]
    license_target = target["license"]
    if not isinstance(about_surfaces, list) or [
        item.get("path") for item in about_surfaces if isinstance(item, dict)
    ] != ABOUT_PATHS:
        raise GenerationError("target must declare the canonical eight ABOUT surfaces")
    target_abouts = []
    seen_paths = set()
    seen_payloads = set()
    for about in about_surfaces:
        path = about["path"]
        payload = about["payload"]
        if path in seen_paths or payload in seen_payloads:
            raise GenerationError("target ABOUT paths and payloads must be unique")
        payload_path = PurePosixPath(payload)
        if (
            not path.endswith("/_ABOUT.md")
            or payload_path.is_absolute()
            or payload_path.parts[0] != "payloads"
            or ".." in payload_path.parts
        ):
            raise GenerationError("target ABOUT path or payload is unsafe")
        seen_paths.add(path)
        seen_payloads.add(payload)
        target_bytes = git_bytes(about["payload_ref"], path)
        target_hash = hashlib.sha256(target_bytes).hexdigest()
        if target_hash != about["payload_sha256"]:
            raise GenerationError(
                f"{path}: target payload hash does not match exact bridge ref"
            )
        target_abouts.append((about, target_bytes, target_hash))
    target_bridge_roots = []
    if [item.get("path") for item in bridge_root_surfaces] != [
        "CONTRIBUTING.md", "SECURITY.md"
    ]:
        raise GenerationError("official 1.64 root surfaces are not canonical")
    for surface in bridge_root_surfaces:
        target_bytes = git_bytes(surface["payload_ref"], surface["path"])
        target_hash = hashlib.sha256(target_bytes).hexdigest()
        if target_hash != surface["payload_sha256"]:
            raise GenerationError(
                f"{surface['path']}: target root payload hash does not match exact ref"
            )
        target_bridge_roots.append((surface, target_bytes, target_hash))
    license_bytes = git_bytes(
        license_target["payload_ref"], license_target["path"]
    )
    license_hash = hashlib.sha256(license_bytes).hexdigest()
    if license_hash != license_target["payload_sha256"]:
        raise GenerationError("target license hash does not match exact legal ref")

    outputs: dict[Path, bytes] = {}
    seen_versions = set()
    seen_identities = set()
    sequence = 0
    for source in catalog["official_sources"]:
        version = str(source["version"])
        commit = source["commit"]
        if version in seen_versions or source["source_identity"] in seen_identities:
            raise GenerationError("official source versions and identities must be unique")
        seen_versions.add(version)
        seen_identities.add(source["source_identity"])
        actual_version, actual_identity = source_identity(commit)
        if (actual_version, actual_identity) != (
            version,
            source["source_identity"],
        ):
            raise GenerationError(f"{version}: baseline identity evidence drifted")
        if source.get("transform") == "license-postcondition-only":
            old_license = git_bytes(commit, license_target["path"])
            old_license_hash = hashlib.sha256(old_license).hexdigest()
            if old_license_hash != source["old_license_sha256"]:
                raise GenerationError(f"{version}: exact old license hash drifted")
            if old_license != license_bytes:
                raise GenerationError(f"{version}: declared MIT postcondition is different")
            suffix = version.replace(".", "-")
            sequence_number = {
                "1.64.1": 22,
                "1.64.2": 23,
                "1.64.3": 24,
                "1.64.4": 25,
                "1.64.5": 26,
            }.get(version)
            if sequence_number is None:
                raise GenerationError(
                    f"{version}: postcondition edge has no permanent sequence"
                )
            name = f"{sequence_number:03d}-official-{suffix}"
            directory = MIGRATIONS / name
            license_payload_rel = "payloads/LICENSE.payload"
            manifest = {
                "schema_version": "1.1.0",
                "id": f"migration-{name}",
                "version_target": "system_version",
                "source_distribution": "personal-ai-os",
                "source_identity": actual_identity,
                "from_version": version,
                "to_version": str(target["version"]),
                "prerequisites": [],
                "content_selector": {"all": True},
                "transform": {"replace_exact_files": [{
                    "path": license_target["path"],
                    "old_sha256": old_license_hash,
                    "payload": license_payload_rel,
                    "new_sha256": license_hash,
                }]},
                "validation": [{"check": "vault-validate"}],
                "rollback": {
                    "strategy": "exact-checkpoint",
                    "automatic_on_validation_failure": True,
                },
                "idempotency_key": f"migration-{name}-v1",
                "manifest_hash": "",
            }
            manifest["manifest_hash"] = compute_manifest_hash(manifest)
            outputs[directory / "migration.yaml"] = yaml.safe_dump(
                manifest, sort_keys=False
            ).encode()
            outputs[directory / license_payload_rel] = license_bytes
            outputs[directory / "README.md"] = (
                "---\n"
                f"id: doc-{name}\n"
                "type: system-doc\n"
                "file_class: canonical\n"
                "authority: derived\n"
                'x_reviewed_against: ["doc-versioning-and-migration:1.4.0"]\n'
                "derived_from: [doc-versioning-and-migration]\n"
                "created: 2026-08-14\n"
                "updated: 2026-08-16\n"
                f"summary: Exact official {version} direct edge to {target['version']}.\n"
                "---\n\n"
                f"# Official {version} edge\n\n"
                f"Generated from exact source commit `{commit}` and source identity "
                f"`{actual_identity}`. `LICENSE.md` is bound as an exact MIT "
                "postcondition: its old and new SHA-256 are both "
                f"`{license_hash}`. The runner performs no physical license write "
                "when the bytes match and refuses an edited or custom license before "
                f"any transform. This is a direct edge to {target['version']}, not a chain.\n"
            ).encode()
            continue
        old_abouts = []
        for about, target_bytes, target_hash in target_abouts:
            old_bytes = git_bytes(commit, about["path"])
            old_hash = hashlib.sha256(old_bytes).hexdigest()
            old_abouts.append((about, old_bytes, old_hash, target_bytes, target_hash))
        primary_old_hash = next(
            old_hash
            for about, _, old_hash, _, _ in old_abouts
            if about["path"] == "80 User/_ABOUT.md"
        )
        if primary_old_hash != source["old_about_sha256"]:
            raise GenerationError(f"{version}: exact old user-surface hash drifted")
        old_license = git_bytes(commit, license_target["path"])
        old_license_hash = hashlib.sha256(old_license).hexdigest()
        if old_license_hash != source["old_license_sha256"]:
            raise GenerationError(f"{version}: exact old license hash drifted")
        if source.get("transform") == "postcondition-only":
            if old_license != license_bytes:
                raise GenerationError(f"{version}: declared MIT postcondition is different")
            name = "021-official-1-64-0"
            directory = MIGRATIONS / name
            license_payload_rel = "payloads/LICENSE.payload"
            manifest = {
                "schema_version": "1.1.0",
                "id": f"migration-{name}",
                "version_target": "system_version",
                "source_distribution": "personal-ai-os",
                "source_identity": actual_identity,
                "from_version": version,
                "to_version": str(target["version"]),
                "prerequisites": [],
                "content_selector": {"all": True},
                "transform": {"replace_exact_files": [
                    {
                        "path": about["path"],
                        "old_sha256": old_hash,
                        "payload": about["payload"],
                        "new_sha256": target_hash,
                    }
                    for about, _, old_hash, _, target_hash in old_abouts
                ] + [
                    {
                        "path": surface["path"],
                        "old_sha256": source[
                            "old_" + surface["path"].split(".")[0].lower() + "_sha256"
                        ],
                        "payload": surface["payload"],
                        "new_sha256": target_hash,
                    }
                    for surface, _, target_hash in target_bridge_roots
                ] + [{
                    "path": license_target["path"],
                    "old_sha256": license_hash,
                    "payload": license_payload_rel,
                    "new_sha256": license_hash,
                }]},
                "validation": [{"check": "vault-validate"}],
                "rollback": {
                    "strategy": "exact-checkpoint",
                    "automatic_on_validation_failure": True,
                },
                "idempotency_key": f"migration-{name}-v4",
                "manifest_hash": "",
            }
            manifest["manifest_hash"] = compute_manifest_hash(manifest)
            outputs[directory / "migration.yaml"] = yaml.safe_dump(
                manifest, sort_keys=False
            ).encode()
            for about, target_bytes, _ in target_abouts:
                outputs[directory / about["payload"]] = target_bytes
            for surface, target_bytes, _ in target_bridge_roots:
                old_hash = hashlib.sha256(
                    git_bytes(commit, surface["path"])
                ).hexdigest()
                key = "old_" + surface["path"].split(".")[0].lower() + "_sha256"
                if old_hash != source[key]:
                    raise GenerationError(
                        f"{version}: exact old {surface['path']} hash drifted"
                    )
                outputs[directory / surface["payload"]] = target_bytes
            outputs[directory / license_payload_rel] = license_bytes
            outputs[directory / "README.md"] = (
                "---\n"
                f"id: doc-{name}\n"
                "type: system-doc\n"
                "file_class: canonical\n"
                "authority: derived\n"
                'x_reviewed_against: ["doc-versioning-and-migration:1.4.0"]\n'
                "derived_from: [doc-versioning-and-migration]\n"
                "created: 2026-07-28\n"
                "updated: 2026-08-16\n"
                f"summary: Exact official 1.64.0 alternative edge to {target['version']}.\n"
                "---\n\n"
                "# Official 1.64.0 edge\n\n"
                f"Generated from exact source commit `{commit}` and source identity "
                f"`{actual_identity}`. The MIT license is an exact postcondition. "
                "The migration runner keeps the already-correct MIT license as an "
                "exact no-write postcondition and replaces each byte-exact legacy "
                "`_ABOUT.md` surface plus `CONTRIBUTING.md` and `SECURITY.md` "
                "with the current reviewed target payloads. Unknown or customized "
                "root bytes refuse before replacement.\n"
            ).encode()
            continue
        if old_license == license_bytes:
            raise GenerationError(f"{version}: expected legacy license is already target")
        if not any(old != new for _, old, _, new, _ in old_abouts):
            raise GenerationError(f"{version}: refusing a dummy ABOUT transform")

        sequence += 1
        name = edge_name(sequence, version)
        directory = MIGRATIONS / name
        license_payload_rel = "payloads/LICENSE.payload"
        manifest = {
            "schema_version": "1.1.0",
            "id": f"migration-{name}",
            "version_target": "system_version",
            "source_distribution": "personal-ai-os",
            "source_identity": actual_identity,
            "from_version": version,
            "to_version": str(target["version"]),
            "prerequisites": [],
            "content_selector": {"all": True},
            "transform": {"replace_exact_files": [
                {
                    "path": about["path"],
                    "old_sha256": old_hash,
                    "payload": about["payload"],
                    "new_sha256": target_hash,
                }
                for about, _, old_hash, _, target_hash in old_abouts
            ] + [{
                "path": license_target["path"],
                "old_sha256": old_license_hash,
                "payload": license_payload_rel,
                "new_sha256": license_hash,
            }]},
            "validation": [{"check": "vault-validate"}],
            "rollback": {
                "strategy": "exact-checkpoint",
                "automatic_on_validation_failure": True,
            },
            "idempotency_key": f"migration-{name}-v3",
            "manifest_hash": "",
        }
        manifest["manifest_hash"] = compute_manifest_hash(manifest)
        outputs[directory / "migration.yaml"] = yaml.safe_dump(
            manifest, sort_keys=False
        ).encode()
        for about, target_bytes, _ in target_abouts:
            outputs[directory / about["payload"]] = target_bytes
        outputs[directory / license_payload_rel] = license_bytes
        outputs[directory / "README.md"] = (
            "---\n"
            f"id: doc-{name}\n"
            "type: system-doc\n"
            "file_class: canonical\n"
            "authority: derived\n"
            'x_reviewed_against: ["doc-versioning-and-migration:1.4.0"]\n'
            "derived_from: [doc-versioning-and-migration]\n"
            "created: 2026-07-28\n"
            "updated: 2026-08-09\n"
            f"summary: Exact historical user-surface migration edge from {version}.\n"
            "---\n\n"
            f"# Historical user-surface edge from {version}\n\n"
            f"Generated from exact source commit `{commit}`. This edge replaces "
            f"all eight byte-exact pristine `_ABOUT.md` surfaces and legacy "
            f"`{license_target['path']}` with payloads pinned to "
            f"`{target_abouts[0][0]['payload_ref']}` and "
            f"`{license_target['payload_ref']}`. Unknown or edited bytes refuse.\n"
        ).encode()

    refused_identities = set()
    for source in catalog["refused_sources"]:
        actual_version, actual_identity = source_identity(source["commit"])
        if (actual_version, actual_identity) != (
            str(source["version"]),
            source["source_identity"],
        ):
            raise GenerationError(f"{source['id']}: refusal identity drifted")
        if actual_identity in seen_identities or actual_identity in refused_identities:
            raise GenerationError(f"{source['id']}: refusal identity is not distinct")
        refused_identities.add(actual_identity)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    catalog = load_catalog()
    outputs = expected_files(catalog)
    stale_payloads = list(
        MIGRATIONS.glob(
            "[0-9][0-9][0-9]-about-stamp-from-*/payloads/LICENSE.md"
        )
    )
    stale_payloads.extend(
        (MIGRATIONS / "021-official-1-64-0/payloads").glob("LICENSE.md")
    )
    stale_payloads.extend(
        (MIGRATIONS / "022-official-1-64-1/payloads").glob("LICENSE.md")
    )
    stale_payloads.extend(
        (MIGRATIONS / "023-official-1-64-2/payloads").glob("LICENSE.md")
    )
    stale_payloads.extend(
        (MIGRATIONS / "024-official-1-64-3/payloads").glob("LICENSE.md")
    )
    stale_payloads.extend(
        (MIGRATIONS / "025-official-1-64-4/payloads").glob("LICENSE.md")
    )
    stale_payloads.extend(
        (MIGRATIONS / "026-official-1-64-5/payloads").glob("LICENSE.md")
    )
    if args.write:
        for stale in stale_payloads:
            stale.unlink()
    mismatches = []
    for path, expected in outputs.items():
        if not path.is_file() or path.read_bytes() != expected:
            mismatches.append(path.relative_to(ROOT).as_posix())
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(expected)
    if mismatches and not args.write:
        raise GenerationError(
            "historical migration outputs are stale: " + ", ".join(mismatches)
        )
    print(
        f"{'wrote' if args.write else 'verified'} {len(outputs)} files "
        f"for {len(catalog['official_sources'])} exact historical edges"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GenerationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
