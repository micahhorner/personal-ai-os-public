"""Report whether one runtime profile has demonstrated certification evidence.

Batch A intentionally verifies only the evidence boundary.  It never converts
defaults, model metadata, source tests, or an autonomy claim into evidence.  A
later live-run orchestrator may supply a complete battery-bound record through
this seam; until then even legacy profile entries are reported as recorded but
not independently re-proved.
"""
from __future__ import annotations

import os

from lib.report import Report
from lib.safepaths import SafePathError, read_regular_file, safe_relative_path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


MAX_PROFILE_BYTES = 1024 * 1024


def _yaml_bytes(payload: bytes, label: str):
    if yaml is None:
        raise ValueError("PyYAML is required to inspect runtime certification evidence")
    try:
        value = yaml.safe_load(payload.decode("utf-8")) or {}
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"{label} is unreadable YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a YAML object")
    return value


def _manifest_profile(root: str) -> str:
    manifest = read_regular_file(
        os.path.join(root, "SYSTEM-MANIFEST.yaml"), max_bytes=MAX_PROFILE_BYTES
    )
    document = _yaml_bytes(manifest.data, "SYSTEM-MANIFEST.yaml")
    runtime = document.get("runtime") or {}
    if not isinstance(runtime, dict) or not runtime.get("active_profile"):
        raise ValueError("SYSTEM-MANIFEST.yaml has no runtime.active_profile")
    return str(runtime["active_profile"])


def _profile_path(root: str, args) -> tuple[str, str]:
    requested = getattr(args, "target", None) or _manifest_profile(root)
    rel = safe_relative_path(str(requested), "runtime profile path")
    return rel, os.path.join(root, *rel.split("/"))


def run(root, args, rep: Report):
    rep.info["verdict_scope"] = (
        "RUNTIME CERTIFICATION — one named runtime/profile's demonstrated behavior only"
    )
    rep.info["source_check"] = "NOT RUN"
    rep.info["release_qualification"] = "NOT RUN"
    try:
        rel, path = _profile_path(root, args)
        profile_file = read_regular_file(path, max_bytes=MAX_PROFILE_BYTES)
        profile = _yaml_bytes(profile_file.data, rel)
    except (OSError, SafePathError, ValueError) as exc:
        rep.info["certification_status"] = "NOT CERTIFIED"
        rep.error(f"runtime certification evidence unavailable: {exc}")
        return rep

    rep.info["profile"] = rel
    rep.info["profile_id"] = profile.get("id")
    rep.info["provider"] = profile.get("provider")
    rep.info["model"] = profile.get("model")
    evidence = profile.get("certifications")
    last_tested = profile.get("last_tested")
    if not isinstance(evidence, dict) or not evidence or not last_tested:
        rep.info["certification_status"] = "NOT CERTIFIED"
        rep.info["recorded_evidence_count"] = len(evidence) if isinstance(evidence, dict) else 0
        rep.error(
            "NOT CERTIFIED — this profile has no complete recorded runtime evidence "
            "and last_tested date; source checks and shipped defaults are not evidence"
        )
        return rep

    rep.info["recorded_evidence_count"] = len(evidence)
    rep.info["last_tested"] = last_tested
    rep.info["certification_status"] = "NOT CERTIFIED"
    rep.error(
        "NOT CERTIFIED — legacy profile evidence is present but is not bound to a "
        "complete battery identity and externally captured live-run record; Batch A "
        "will not infer certification from self-reported profile fields"
    )
    return rep
