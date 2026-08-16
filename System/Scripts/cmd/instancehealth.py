"""Scope-honest current installed-vault health verdict."""
from __future__ import annotations

from lib.report import Report
from cmd import health as health_impl


def run(root, args, rep: Report):
    rep.info["verdict_scope"] = (
        "INSTANCE HEALTH — current installed-tree integrity and advisories only"
    )
    rep.info["runtime_certification"] = "NOT RUN"
    rep.info["release_qualification"] = "NOT RUN"
    return health_impl.run(root, args, rep)
