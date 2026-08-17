"""vault.doc-check — the documentation coverage gate.

Fails if any component (capability / agent / workflow) on disk lacks a diagram
in the atlas, if any referenced diagram SVG is missing, or if any diagram lacks
a description. This is what makes "is every capability documented?" a checkable
fact instead of a hope. Run standalone (`aios doc-check`) or rolled into
`aios health`; enforced at component activation and in the weekly pass.

Source of truth: System/Documentation/Diagrams/coverage.yaml (+ diagram-metadata.yaml).
"""
from __future__ import annotations
import glob
import os
import re

try:
    import yaml
except ImportError:
    yaml = None

from lib.report import Report

_STRICT = True   # set per-run from instance_role; strict by default (test scaffolds, master)


def _read_text(path, *, errors=None):
    kwargs = {"encoding": "utf-8"}
    if errors is not None:
        kwargs["errors"] = errors
    with open(path, **kwargs) as stream:
        return stream.read()


def _read_yaml(path):
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)

def _sev(rep):
    return rep.error if _STRICT else rep.warn

def _master(root):
    """Doc gates police the PRODUCT; on an instance they advise (DEC-083).
    A customized instance legitimately diverges from the product's own docs —
    instance-added components, deleted optional docs, extended counts — and a
    gate that reddens that divergence forever punishes sanctioned customization
    (found live: first v1.30.1 instance upgrade, 29 residual errors, all this
    class). Master = error; instance = warning. Same scoping doctrine as
    DEC-082."""
    import yaml as _y, os as _o
    try:
        with open(_o.path.join(root, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as stream:
            man = _y.safe_load(stream) or {}
    except Exception:
        return True   # no manifest = test scaffold/product context: stay strict
    return str(((man.get("system") or {}).get("instance_role") or "generic-master")).strip() == "generic-master"


DIAGRAMS_REL = os.path.join("System", "Documentation", "Diagrams")

# The enumerable component surface — every file matching these must be mapped.
COMPONENT_GLOBS = [
    os.path.join("System", "Capabilities", "*", "SKILL.md"),
    os.path.join("System", "Agents", "*", "AGENT.md"),
    os.path.join("System", "Workflows", "*.md"),
]


def _frontmatter_id(path):
    """Extract `id:` from a note's YAML frontmatter, or None."""
    try:
        text = _read_text(path, errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else text
    m = re.search(r"^id:\s*(\S+)", block, re.MULTILINE)
    return m.group(1).strip() if m else None


def _enumerate_components(root):
    found = {}
    for g in COMPONENT_GLOBS:
        for path in sorted(glob.glob(os.path.join(root, g))):
            cid = _frontmatter_id(path) or os.path.splitext(os.path.basename(path))[0]
            found[cid] = os.path.relpath(path, root)
    return found


def run(root, args, rep: Report):
    global _STRICT
    _STRICT = _master(root)
    if yaml is None:
        rep.error("PyYAML required for doc-check")
        return rep

    dphys = os.path.join(root, DIAGRAMS_REL)
    cov_path = os.path.join(dphys, "coverage.yaml")
    meta_path = os.path.join(dphys, "diagram-metadata.yaml")
    svg_dir = os.path.join(dphys, "svg")

    if not os.path.exists(cov_path):
        rep.error(f"no coverage.yaml at {DIAGRAMS_REL}/ — the diagram atlas is missing")
        return rep

    cov = _read_yaml(cov_path) or {}
    meta = _read_yaml(meta_path) if os.path.exists(meta_path) else {}
    diagrams = cov.get("diagrams", {})
    components_cov = cov.get("components", {})
    areas = cov.get("areas", {})
    flows_cov = cov.get("flows", {})

    on_disk = _enumerate_components(root)

    # 1. Every component on disk must be mapped to a diagram.
    for cid in sorted(on_disk):
        if cid not in components_cov:
            _sev(rep)(f"UNDIAGRAMMED component: {cid} ({on_disk[cid]}) — add a diagram + coverage entry")

    # 1b. Every user-flow walkthrough (System/Documentation/Flows/*.md) must map to a diagram.
    flowdir = os.path.join(root, "System", "Documentation", "Flows")
    if os.path.isdir(flowdir):
        for f in sorted(glob.glob(os.path.join(flowdir, "*.md"))):
            stem = os.path.splitext(os.path.basename(f))[0]
            if stem not in flows_cov:
                _sev(rep)(f"UNDIAGRAMMED flow doc: {stem} — add a diagram + a flows entry in coverage.yaml")

    # 2. No stale coverage rows (mapped component no longer exists).
    for cid in sorted(components_cov):
        if cid not in on_disk:
            rep.warn(f"stale coverage entry (no such component): {cid}")

    # 3. Every referenced diagram id must exist and its SVG file must be present.
    def check_refs(refs, ctx):
        for did in refs or []:
            did = str(did).zfill(2)
            if did not in diagrams:
                rep.error(f"{ctx} references unknown diagram id {did}")
            elif not os.path.exists(os.path.join(svg_dir, diagrams[did]["file"])):
                rep.error(f"missing SVG {diagrams[did]['file']} (diagram {did}, {ctx})")

    for cid, refs in components_cov.items():
        check_refs(refs, f"component {cid}")
    for aid, spec in areas.items():
        check_refs(spec.get("diagrams", []), f"area {aid}")
    for stem, refs in flows_cov.items():
        check_refs(refs, f"flow {stem}")

    # 4. Every SVG on disk should be registered (catch orphans).
    registered = {d["file"] for d in diagrams.values()}
    for svg in sorted(glob.glob(os.path.join(svg_dir, "*.svg"))):
        if os.path.basename(svg) not in registered:
            rep.warn(f"orphan SVG (not registered in coverage.yaml): {os.path.basename(svg)}")

    # 5. Every diagram must carry a non-empty description.
    for did in sorted(diagrams):
        entry = (meta or {}).get(did)
        if not entry or not str(entry.get("description", "")).strip():
            rep.error(f"missing description in diagram-metadata.yaml for diagram {did}")

    # 6. CATALOG.md (the human index) must list every registered diagram — it is
    # hand-maintained and not otherwise gated, so it drifts silently without this.
    catalog = os.path.join(dphys, "CATALOG.md")
    if os.path.exists(catalog):
        ctext = _read_text(catalog)
        for did in sorted(diagrams):
            if diagrams[did]["file"] not in ctext:
                _sev(rep)(f"CATALOG.md does not list diagram {did} ({diagrams[did]['file']})")

    rep.info["components_on_disk"] = len(on_disk)
    rep.info["components_mapped"] = len(components_cov)
    rep.info["diagrams"] = len(diagrams)
    return rep


def component_gap(root, cid):
    """Return None if component `cid` is fully documented — mapped to an existing,
    described diagram — else a human-readable reason string. Used by
    vault.register_component to hard-block activation of an undocumented component
    (documentation is a peer of tests: neither may be skipped, DEC-051)."""
    if yaml is None:
        return "PyYAML unavailable — cannot verify documentation coverage"
    dphys = os.path.join(root, DIAGRAMS_REL)
    cov_path = os.path.join(dphys, "coverage.yaml")
    if not os.path.exists(cov_path):
        return f"no diagram atlas at {DIAGRAMS_REL}/ — cannot verify documentation"
    cov = _read_yaml(cov_path) or {}
    diagrams = cov.get("diagrams", {})
    refs = (cov.get("components", {}) or {}).get(cid)
    if not refs:
        return (f"{cid} is not mapped to any diagram in {DIAGRAMS_REL}/coverage.yaml — "
                "author a diagram, add its description, and map the component before activating")
    meta_path = os.path.join(dphys, "diagram-metadata.yaml")
    meta = _read_yaml(meta_path) if os.path.exists(meta_path) else {}
    svg_dir = os.path.join(dphys, "svg")
    for did in refs:
        did = str(did).zfill(2)
        d = diagrams.get(did)
        if not d:
            return f"{cid} references unknown diagram id {did}"
        if not os.path.exists(os.path.join(svg_dir, d["file"])):
            return f"{cid}: diagram {did} SVG missing ({d['file']})"
        entry = (meta or {}).get(did)
        if not entry or not str(entry.get("description", "")).strip():
            return f"{cid}: diagram {did} has no description in diagram-metadata.yaml"
    return None
