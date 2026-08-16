"""Shared test-scaffold helpers. NOT a test module (unittest discovers `test*.py`).

Why this exists
---------------
Most test scaffolds build their fixture vault by copying the HOST vault's
`SYSTEM-MANIFEST.yaml` verbatim. That is fine on the product master, whose
`instance_role` is `generic-master` — and it is exactly what the scaffolds'
own docstrings assume ("a release tree: generic-master manifest at ...").

It is wrong anywhere else. Several gates scope their severity on
`instance_role` (DEC-083: master = error, instance = warning) and `aios upgrade`
refuses outright on an instance. So when the suite is run from a PERSONAL
instance — which is what happens the moment `aios certify` is run on a real
vault, since certify's regression dimension runs the suite in place — the
fixtures silently inherit `personal-instance` and 20+ tests fail for a reason
that has nothing to do with the code under test.

A fixture's role must be a stated property of the fixture, never a property of
whatever machine the suite happens to run on. `product_manifest()` states it.
"""
from __future__ import annotations
import os
import re

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_ROLE_RE = re.compile(r"^(\s*instance_role:\s*)([^\s#]+)", re.M)


def product_manifest(vault: str = VAULT, role: str = "generic-master") -> str:
    """The host manifest's text with `instance_role` forced to an EXPLICIT value.

    Defaults to `generic-master` because that is the role every scaffold in this
    suite is written against. Pass `role="personal-instance"` in a test that is
    deliberately exercising instance-scoped behaviour.
    """
    with open(os.path.join(vault, "SYSTEM-MANIFEST.yaml"), encoding="utf-8") as stream:
        text = stream.read()
    text, n = _ROLE_RE.subn(lambda m: m.group(1) + role, text, count=1)
    if not n:  # a manifest with no role key at all: state it rather than inherit nothing
        text = re.sub(r"^(system:\s*\n)", r"\1  instance_role: " + role + "\n",
                      text, count=1, flags=re.M)
    return text


def write_product_manifest(dest_root: str, vault: str = VAULT,
                           role: str = "generic-master", transform=None) -> str:
    """Write an explicit-role manifest into `dest_root`; return the path.

    `transform` is an optional callable applied to the text first, for scaffolds
    that also need to flip the kill switch or the version.
    """
    text = product_manifest(vault, role)
    if transform is not None:
        text = transform(text)
    path = os.path.join(dest_root, "SYSTEM-MANIFEST.yaml")
    os.makedirs(dest_root, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path
