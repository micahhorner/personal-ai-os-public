"""vault.scaffold_component / vault.register_component — controlled component creation."""
from __future__ import annotations
import glob, os, datetime, re
import yaml
from lib.vaultpaths import ai_writes_enabled
from lib.protectedwrites import ProtectedTargetError, guard_ordinary_write_set
from lib.report import Report
from lib.safepaths import (SafePathError, atomic_create_files,
                           preflight_contained_regular_files, read_regular_file,
                           safe_relative_path)

TYPES = ("capability", "workflow")   # the two types with a full scaffold→test→activate lifecycle;
# scripts, templates, note classes, agents, and schemas go through the developer/amendment
# lane instead (delta-audit H-03: never advertise an activation path that cannot complete)

def run(root, args, rep: Report):
    if not ai_writes_enabled(root):
        rep.error("kill switch is off — refusing to write"); return rep
    ctype, name = getattr(args, "type", None), getattr(args, "name", None)
    if getattr(args, "register", None):
        return register(root, args.register, rep)
    if not ctype or not name:
        rep.error("usage: aios scaffold --type <capability|workflow> --name <kebab-name>"); return rep
    if ctype not in TYPES:
        rep.error(f"type '{ctype}' cannot be scaffolded — only capability and workflow have the full "
                  "scaffold→test→activate lifecycle; scripts, templates, note classes, agents, and "
                  "schemas are system changes (developer lane, human-approved)"); return rep
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        rep.error("name must be kebab-case"); return rep
    d = datetime.date.today().isoformat()
    if ctype == "capability":
        # Agent Skills packaging (DEC-070): a capability is a directory whose
        # procedure lives in <name>/SKILL.md; `description` says what it does
        # AND when to use it (the spec's required field; summary stays canonical)
        created = f"System/Capabilities/{name}/SKILL.md"
        payload = (
            f'---\nid: capability-{name}\nname: {name}\ncomponent_type: capability\ntype: capability\n'
            f'file_class: canonical\nauthority: canonical\ncanonical_for: capability-{name}\n'
            f'status: draft\nversion: 0.1.0\nsummary: "TODO"\ndescription: "TODO — what it does and when to use it"\n'
            f'consolidates: []\n'
            f'reads: [vault]\nwrites: [per-procedure]\npermissions: [uses-vault-operations-only]\n'
            f'dependencies: [doc-runtime-kernel]\ntests: []\ndocumentation: self\n'
            f'created: {d}\nupdated: {d}\n---\n\n# Capability — {name}\n\n1. TODO\n')
    else:  # workflow
        created = f"System/Workflows/{name}.md"
        payload = (f'---\nid: workflow-{name}\ntype: workflow\nfile_class: canonical\n'
                   f'authority: canonical\ncanonical_for: workflow-{name}\nstatus: draft\n'
                   f'version: 0.1.0\ncreated: {d}\nupdated: {d}\nsummary: "TODO"\ntests: []\n'
                   f'---\n\n# Workflow — {name}\n\n1. TODO\n')
    try:
        _component_meta(payload)
        atomic_create_files(
            root, {created: payload.encode("utf-8")},
            create_dirs=([f"System/Capabilities/{name}"] if ctype == "capability" else []),
        )
    except (SafePathError, ValueError, yaml.YAMLError) as exc:
        rep.error(f"scaffold refused; nothing changed: {exc}")
        return rep
    rep.info["scaffolded"] = created
    rep.info["registry"] = f"{ctype}-{name} added as draft — activate with: aios scaffold --register {ctype}-{name} (after tests pass, with human approval)"
    return rep


def _component_meta(text):
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.DOTALL)
    if not match:
        raise ValueError("component frontmatter is missing or unterminated")
    meta = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict):
        raise ValueError("component frontmatter is not a mapping")
    return meta


def _safe_read_set(root, paths, *, writable=False):
    batch = preflight_contained_regular_files(
        root, paths, require_writable=writable
    )
    try:
        return batch.read_texts()
    finally:
        batch.close()


def _readonly_inputs(paths):
    inputs = [read_regular_file(path) for path in paths]
    texts = {os.path.abspath(path): item.data.decode("utf-8")
             for path, item in zip(paths, inputs)}
    return inputs, texts


def _documentation_inputs(root, cid):
    base = "System/Documentation/Diagrams"
    coverage_rel = f"{base}/coverage.yaml"
    metadata_rel = f"{base}/diagram-metadata.yaml"
    paths = [os.path.join(root, *coverage_rel.split("/")),
             os.path.join(root, *metadata_rel.split("/"))]
    inputs, texts = _readonly_inputs(paths)
    coverage = yaml.safe_load(texts[paths[0]]) or {}
    metadata = yaml.safe_load(texts[paths[1]]) or {}
    if not isinstance(coverage, dict) or not isinstance(metadata, dict):
        raise ValueError("diagram coverage and metadata must be mappings")
    components = coverage.get("components", {}) or {}
    diagrams = coverage.get("diagrams", {}) or {}
    if not isinstance(components, dict) or not isinstance(diagrams, dict):
        raise ValueError("diagram coverage components and diagrams must be mappings")
    refs = components.get(cid)
    if not isinstance(refs, list) or not refs:
        raise ValueError(f"{cid} is not mapped to any diagram in {coverage_rel}")
    svg_paths = []
    for raw in refs:
        did = str(raw).zfill(2)
        diagram = diagrams.get(did)
        if not isinstance(diagram, dict) or not diagram.get("file"):
            raise ValueError(f"{cid} references unknown diagram id {did}")
        diagram_meta = metadata.get(did) or {}
        if not isinstance(diagram_meta, dict) or not diagram_meta.get("description"):
            raise ValueError(f"{cid}: diagram {did} has no description")
        svg_rel = safe_relative_path(f"{base}/svg/{diagram['file']}", "diagram SVG")
        svg_paths.append(os.path.join(root, *svg_rel.split("/")))
    svg_inputs, _ = _readonly_inputs(svg_paths)
    return inputs + svg_inputs


def _component_candidates(root):
    return sorted(
        glob.glob(os.path.join(root, "System", "Capabilities", "*", "SKILL.md"))
        + glob.glob(os.path.join(root, "System", "Agents", "*", "AGENT.md"))
        + glob.glob(os.path.join(root, "System", "Workflows", "*.md"))
    )

def register(root, cid, rep: Report):
    try:
        candidates = _component_candidates(root)
        texts = _safe_read_set(root, candidates) if candidates else {}
    except (SafePathError, UnicodeDecodeError) as exc:
        rep.error(f"component registry read refused: {exc}")
        return rep
    for p in candidates:
        try:
            meta = _component_meta(texts[p])
        except (ValueError, yaml.YAMLError) as exc:
            rep.error(f"component registry read refused: {os.path.relpath(p, root)}: {exc}")
            return rep
        if str(meta.get("id")) == cid:
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if rel.startswith("System/Agents/"):
                rep.error(
                    f"{cid}: agent contracts cannot be activated through scaffold; "
                    "System/Agents is protected and requires the developer/amendment lane "
                    "with explicit human approval"
                )
                return rep
            evidence = []
            if not isinstance(meta.get("tests"), list) or not meta.get("tests"):
                rep.error(f"{cid}: no tests listed — components without tests cannot activate")
                return rep
            try:
                test_rels = [safe_relative_path(str(t), "component test path")
                             for t in meta["tests"]]
                test_paths = [os.path.join(root, *rel.split("/")) for rel in test_rels]
                test_inputs, _ = _readonly_inputs(test_paths)
                evidence.extend(test_inputs)
            except (SafePathError, UnicodeDecodeError, ValueError) as exc:
                rep.error(f"{cid}: listed test path(s) do not exist or are unsafe: {exc} — "
                          "cannot activate")
                return rep
            result_rel = safe_relative_path(
                f"System/Tests/results/{cid}.yaml", "component result path"
            )
            result_path = os.path.join(root, *result_rel.split("/"))
            try:
                result_inputs, result_texts = _readonly_inputs([result_path])
                evidence.extend(result_inputs)
                res = yaml.safe_load(result_texts[os.path.abspath(result_path)]) or {}
                if not isinstance(res, dict):
                    raise ValueError("result record is not a mapping")
            except (SafePathError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
                rep.error(f"{cid}: no recorded test result at {result_rel}, or result is unsafe "
                          f"({exc}) — run the listed tests, record the outcome, then activate")
                return rep
            if res.get("result") != "pass" or str(res.get("version")) != str(meta.get("version")):
                rep.error(f"{cid}: recorded result must be 'pass' for version {meta.get('version')} "
                          f"(found: result={res.get('result')}, version={res.get('version')})")
                return rep
            try:
                evidence.extend(_documentation_inputs(root, cid))
            except (SafePathError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
                rep.error(f"{cid}: documentation gate — {exc}")
                return rep
            if meta.get("status") != "draft":
                rep.error(f"{cid}: status is '{meta.get('status')}', not draft — nothing to activate")
                return rep
            try:
                batch = preflight_contained_regular_files(root, [p])
                try:
                    original = batch.read_texts()[p]
                    current_meta = _component_meta(original)
                    if (str(current_meta.get("id")) != cid
                            or current_meta.get("status") != "draft"
                            or current_meta.get("tests") != meta.get("tests")
                            or str(current_meta.get("version")) != str(meta.get("version"))):
                        raise SafePathError("component changed while activation was being prepared")
                    text = original.replace("status: draft", "status: active", 1)
                    if _component_meta(text).get("status") != "active":
                        raise SafePathError("activation edit did not produce active status")
                    policy = guard_ordinary_write_set(
                        root,
                        (batch.targets[0].relpath,),
                        "scaffold --register",
                        texts={batch.targets[0].relpath: original},
                    )
                    atomic_create_files(
                        root, {batch.targets[0].relpath: text.encode("utf-8")},
                        replace_batch=batch,
                        read_only_inputs=evidence + [policy.manifest],
                    )
                finally:
                    batch.close()
            except (ProtectedTargetError, SafePathError, ValueError, yaml.YAMLError) as exc:
                rep.error(f"{cid}: activation transaction refused: {exc}")
                return rep
            rep.info["activated"] = cid
            return rep
    rep.error(f"unknown component: {cid}")
    return rep
