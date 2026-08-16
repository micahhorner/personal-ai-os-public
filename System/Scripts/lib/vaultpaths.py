"""Vault root discovery, manifest access, and folder-registry indirection."""
from __future__ import annotations
import os
import yaml

def find_root(start: str | None = None) -> str:
    """The vault root is the nearest ancestor containing SYSTEM-MANIFEST.yaml."""
    d = os.path.abspath(start or os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    while True:
        if os.path.exists(os.path.join(d, "SYSTEM-MANIFEST.yaml")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise SystemExit("aios: SYSTEM-MANIFEST.yaml not found — run from inside the vault")
        d = parent

def manifest(root: str) -> dict:
    with open(os.path.join(root, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as stream:
        return yaml.safe_load(stream)

def ai_writes_enabled(root: str) -> bool:
    return bool(manifest(root).get("runtime", {}).get("ai_writes_enabled", False))

def folder(root: str, folder_id: str) -> str:
    """Resolve a stable folder ID via the folder registry (never hard-code paths)."""
    regpath = os.path.join(root, "System", "Registries", "folder-registry.yaml")
    with open(regpath, encoding="utf-8") as stream:
        reg = yaml.safe_load(stream)
    entry = reg["folders"].get(folder_id)
    if not entry:
        raise KeyError(f"unknown folder id: {folder_id}")
    return os.path.join(root, entry["path"])

def rel_folder(root: str, folder_id: str, default: str) -> str:
    """The registry-relative path for a folder id (DEC-004), falling back to the
    literal default. Resolve ONCE before a scan loop, not per-file."""
    try:
        with open(os.path.join(root, "System", "Registries", "folder-registry.yaml"),
                  encoding="utf-8") as stream:
            reg = yaml.safe_load(stream)
        return reg["folders"].get(folder_id, {}).get("path", default)
    except Exception:
        return default


def content_dirs(root: str) -> list[str]:
    return manifest(root).get("directories", {}).get("content", [])


# A pack is a self-contained add-on folder (DEC-061). Inside it, the same split
# exists as in the vault around it: CONTENT the user reads and writes, and
# MACHINERY that runs it. This is the machinery half — the pack's `System/`
# equivalent, plus the vendored payload a pack carries under someone else's
# licence and may not edit.
#
# It is deliberately the PRODUCT's vocabulary, not a census of the pack author's
# folders, and that is the whole point (DEC-109's lesson, applied): the excluded
# set is bounded and defined here, so the covered set is *everything else, by
# construction*. A content folder a pack invents tomorrow — `05 PMM Wiki`,
# `03 Intelligence Hub` — is in scope without anyone remembering to add it.
# These are the same component directories `generate.py`'s index already globs.
#
# The trade-off runs one way on purpose. A machinery folder under a name not
# listed here (a pack invents `engine/`) is over-covered — it gets checked as
# content. Over-coverage can only make the check stricter; under-coverage is what
# produces a "CONFORMANT" verdict over a corpus nobody read. For a claim the
# product sells, strict-and-noisy beats quiet-and-wrong, so this list stays short
# and grows only on evidence. Every name here is one a shipped pack actually uses.
PACK_MACHINERY_DIRS = ("capabilities", "agents", "workflows", "components",
                       "templates", "schemas", "migrations", "tests", "resources")


def pack_content_trees(root: str) -> list[tuple[str, str]]:
    """[(absolute path, `Packs/<id>/<dir>` label)] for every content directory of
    every installed pack — the pack's knowledge surface.

    Two things are outside it, each mirroring the vault:

    - `PACK_MACHINERY_DIRS`, as the vault's own `System/` is outside the
      knowledge layer.
    - loose files at the pack root (`README.md`, `CHANGELOG.md`, `START HERE.md`),
      as the vault's own root files are. This also keeps the DEC-067 collision
      pair — a pack's `README.md`/`CHANGELOG.md` against the vault's — entirely
      outside anything this function feeds.

    Membership is not canon: nothing here enters the vault's id space, `dupes`,
    `validate`, or `links`. Those still prune `Packs/` via `frontmatter.SKIP_DIRS`
    and DEC-061/DEC-067 are untouched. This is a reading list, not a namespace.
    """
    packs = os.path.join(root, "Packs")
    if not os.path.isdir(packs):
        return []
    trees = []
    for pid in sorted(os.listdir(packs)):
        pack = os.path.join(packs, pid)
        if not os.path.isfile(os.path.join(pack, "pack.yaml")):
            continue        # not an installed pack — a stray folder is not this command's business
        for name in sorted(os.listdir(pack)):
            sub = os.path.join(pack, name)
            if os.path.isdir(sub) and name not in PACK_MACHINERY_DIRS and not name.startswith("."):
                trees.append((sub, f"Packs/{pid}/{name}"))
    return trees


def installed_pack_ids(root: str) -> list[str]:
    """Ids of the packs installed here — a `Packs/<id>/` folder with a `pack.yaml`."""
    packs = os.path.join(root, "Packs")
    if not os.path.isdir(packs):
        return []
    return sorted(p for p in os.listdir(packs)
                  if os.path.isfile(os.path.join(packs, p, "pack.yaml")))
