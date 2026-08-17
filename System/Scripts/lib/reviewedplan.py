"""Deterministic, byte-bound approval plans for protected write batches."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Mapping, Any

from lib.protectedwrites import ProtectionProof


def canonical_json(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True)
class ReviewedPlan:
    document: dict
    review_sha256: str
    protected_targets: tuple[str, ...]


def build_semantic_reviewed_plan(
    operation: str,
    root: str,
    policy: ProtectionProof,
    semantic_inputs: Mapping[str, Any],
) -> ReviewedPlan:
    """Bind exact inputs to a deterministic operation whose outputs are materialized later.

    Unlike ``build_reviewed_plan``, this contract deliberately does not claim
    to contain final output-byte hashes.  It is for transactional operations
    such as upgrade, where final bytes are produced only inside a validated
    candidate after authorization.  The operation must retain its own
    candidate/output identity proofs.
    """
    root_info = os.stat(os.path.abspath(root), follow_symlinks=False)
    document = {
        "schema": "aios-reviewed-semantic-plan/v1",
        "operation": operation,
        "review_scope": "exact-semantic-inputs-not-materialized-output-bytes",
        "root": {
            "path": os.path.abspath(root),
            "device": int(root_info.st_dev),
            "inode": int(root_info.st_ino),
        },
        "policy": {
            "path": "SYSTEM-MANIFEST.yaml",
            "sha256": policy.manifest.digest,
            "protected_objects": list(policy.entries),
        },
        "semantic_inputs": dict(semantic_inputs),
    }
    return ReviewedPlan(
        document=document,
        review_sha256=hashlib.sha256(canonical_json(document)).hexdigest(),
        protected_targets=(),
    )


def build_reviewed_plan(
    operation: str,
    root: str,
    policy: ProtectionProof,
    originals: Mapping[str, bytes],
    desired: Mapping[str, bytes],
) -> ReviewedPlan:
    """Bind one complete proposed batch, including live policy and both byte sets."""
    if set(originals) != set(desired):
        raise ValueError("reviewed-plan preimage and desired target sets differ")
    targets = []
    protected = []
    for relpath in sorted(originals):
        matched = policy.match(relpath)
        if matched is not None:
            protected.append(relpath)
        targets.append({
            "path": relpath,
            "preimage_sha256": hashlib.sha256(originals[relpath]).hexdigest(),
            "desired_sha256": hashlib.sha256(desired[relpath]).hexdigest(),
            "protected_by": matched,
        })
    root_info = os.stat(os.path.abspath(root), follow_symlinks=False)
    document = {
        "schema": "aios-reviewed-write-plan/v1",
        "operation": operation,
        "root": {
            "path": os.path.abspath(root),
            "device": int(root_info.st_dev),
            "inode": int(root_info.st_ino),
        },
        "policy": {
            "path": "SYSTEM-MANIFEST.yaml",
            "sha256": policy.manifest.digest,
            "protected_objects": list(policy.entries),
        },
        "targets": targets,
    }
    return ReviewedPlan(
        document=document,
        review_sha256=hashlib.sha256(canonical_json(document)).hexdigest(),
        protected_targets=tuple(protected),
    )
