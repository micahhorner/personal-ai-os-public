"""vault.vocab — banned-term guard for domain content.

Ported from the PMM starter's check_vocabulary.py (Migration 001, Wave 4).
Generic mechanism, user-owned configuration: `80 User/vocab-guard.yaml`
declares where banned terms come from and which folders to scan. Domains
that ship an approved-vocabulary table (the PMM Config.md pattern) point a
markdown-config source at it; anyone else can list inline terms.

Read-only. Violations are warnings, never errors: vocabulary drift is an
editorial finding, not a structural fault, and EXAMPLE/legacy content must
not redden health. Verbatim quote material (blockquotes, quoted table rows)
is skipped, matching the original scanner's contract.
"""
from __future__ import annotations
import os, re
import yaml
from lib.report import Report

CONFIG_REL = os.path.join("80 User", "vocab-guard.yaml")
QUOTE_LINE = re.compile(r'^\s*>|^\s*\|.*"')


def _terms_from_markdown_config(path: str) -> list[str]:
    """Harvest banned terms from an approved-vocabulary markdown file:
    the second column ("never say") of tables under '## Approved Vocabulary'
    plus every bullet under '## Banned Terms...'."""
    terms: list[str] = []
    with open(path, encoding="utf-8") as stream:
        text = stream.read()
    in_vocab = in_banned = False
    for line in text.splitlines():
        if line.startswith("## "):
            low = line.lower()
            in_vocab = low.startswith("## approved vocabulary")
            in_banned = low.startswith("## banned terms")
            continue
        if in_vocab and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[1] and not set(cells[1]) <= {"-", " "}:
                if "never say" not in cells[1].lower() and "PLACEHOLDER" not in cells[1]:
                    for t in re.split(r"[,/]", cells[1]):
                        t = t.strip().strip('"').strip()
                        if t:
                            terms.append(t)
        if in_banned and line.strip().startswith("-"):
            t = line.strip().lstrip("-").strip().strip('"')
            if t and "PLACEHOLDER" not in t:
                terms.append(t)
    return terms


def run(root, args, rep: Report):
    cfg_path = os.path.join(root, CONFIG_REL)
    if not os.path.exists(cfg_path):
        rep.info["status"] = f"no {CONFIG_REL} — vocab guard not configured for this instance"
        return
    try:
        with open(cfg_path, encoding="utf-8") as stream:
            cfg = yaml.safe_load(stream) or {}
    except yaml.YAMLError as e:
        rep.error(f"{CONFIG_REL} is not valid YAML: {e}")
        return

    terms: list[str] = [str(t) for t in cfg.get("extra_terms") or []]
    for src in cfg.get("term_sources") or []:
        if src.get("type") == "markdown-config":
            p = os.path.join(root, src.get("path", ""))
            if os.path.exists(p):
                terms.extend(_terms_from_markdown_config(p))
            else:
                rep.warn(f"term source not found: {src.get('path')}")
    terms = sorted(set(t for t in terms if t))
    rep.info["banned_terms_loaded"] = len(terms)
    if not terms:
        rep.info["status"] = "no banned terms defined (config not yet personalized) — nothing to scan"
        return

    scan_dirs = cfg.get("scan_dirs") or []
    pattern = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)
    violations = 0
    for rel in scan_dirs:
        base = os.path.join(root, rel)
        if not os.path.isdir(base):
            rep.warn(f"scan dir not found: {rel}")
            continue
        for dirpath, _, files in os.walk(base):
            for name in files:
                if not name.endswith(".md"):
                    continue
                fp = os.path.join(dirpath, name)
                try:
                    with open(fp, encoding="utf-8") as stream:
                        lines = stream.read().splitlines()
                except OSError:
                    continue
                for i, line in enumerate(lines, 1):
                    if QUOTE_LINE.match(line):
                        continue
                    m = pattern.search(line)
                    if m:
                        violations += 1
                        rep.warn(f"banned term '{m.group(0)}' — "
                                 f"{os.path.relpath(fp, root)}:{i}: {line.strip()[:120]}")
    rep.info["violations"] = violations
