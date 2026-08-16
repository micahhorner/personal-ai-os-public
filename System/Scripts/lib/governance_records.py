"""Read-only integrity checks for the compact product decision register.

The register is standing governance, not the historical changelog.  Each
definition is one bullet beginning with ``- **DEC-NNN``.  References to other
decisions inside that bullet remain references; only the first identifier is
the definition's stable identity.  This distinction permits legitimate
summary rows such as ``DEC-016 + DEC-121`` without defining DEC-121 twice.

This module deliberately exposes one narrow callable API and is not wired into
``health``, ``certify``, or the CLI yet.  Wave 6 integration owns that decision.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import unicodedata
from typing import Dict, List, Optional, Tuple


ACTIVE_DECISIONS = os.path.join(
    "System", "Governance", "Active Decisions.md"
)
DEFINITION_RE = re.compile(
    r"^-\s+\*\*DEC-(?P<number>[0-9]{3})\b"
    r"(?P<label>.*?\*\*)\s*(?:—|-)\s*(?P<body>.*)$"
)


@dataclass(frozen=True)
class DecisionDefinition:
    decision_id: str
    number: int
    line: int
    body: str
    normalized_body: str


@dataclass(frozen=True)
class GovernanceFinding:
    code: str
    message: str
    line: int
    decision_id: str
    other_line: Optional[int] = None


@dataclass(frozen=True)
class GovernanceAudit:
    path: str
    definitions: Tuple[DecisionDefinition, ...]
    findings: Tuple[GovernanceFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def definition_count(self) -> int:
        return len(self.definitions)

    @property
    def unique_id_count(self) -> int:
        return len({item.decision_id for item in self.definitions})

    def count(self, code: str) -> int:
        return sum(item.code == code for item in self.findings)


def _normalized_body(value: str) -> str:
    """Normalize presentation-only differences without erasing semantics."""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _definitions(text: str) -> Tuple[DecisionDefinition, ...]:
    records: List[DecisionDefinition] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = DEFINITION_RE.match(line)
        if not match:
            continue
        number = int(match.group("number"))
        body = match.group("body").strip()
        records.append(DecisionDefinition(
            decision_id="DEC-%03d" % number,
            number=number,
            line=line_no,
            body=body,
            normalized_body=_normalized_body(body),
        ))
    return tuple(records)


def audit_active_decisions(path: os.PathLike[str] | str) -> GovernanceAudit:
    """Audit one compact decision-register file without modifying it.

    Findings are emitted once per definition after the first occurrence, so
    counts are exact counts of excess definitions rather than pair counts.
    Ordering is checked on adjacent definition rows and must be strictly
    descending.  Missing numbers are permitted: gaps preserve historical
    decisions that are no longer standing rules.
    """
    absolute = os.path.abspath(os.fspath(path))
    with open(absolute, encoding="utf-8") as stream:
        records = _definitions(stream.read())

    findings: List[GovernanceFinding] = []
    by_id: Dict[str, DecisionDefinition] = {}
    by_body: Dict[str, DecisionDefinition] = {}
    for record in records:
        prior_id = by_id.get(record.decision_id)
        if prior_id is not None:
            findings.append(GovernanceFinding(
                code="decision-id-duplicate",
                message=(f"{record.decision_id} is defined at lines "
                         f"{prior_id.line} and {record.line}"),
                line=record.line,
                decision_id=record.decision_id,
                other_line=prior_id.line,
            ))
        else:
            by_id[record.decision_id] = record

        prior_body = by_body.get(record.normalized_body)
        if prior_body is not None:
            findings.append(GovernanceFinding(
                code="decision-body-duplicate",
                message=(f"{record.decision_id} at line {record.line} repeats "
                         f"the normalized body of {prior_body.decision_id} at "
                         f"line {prior_body.line}"),
                line=record.line,
                decision_id=record.decision_id,
                other_line=prior_body.line,
            ))
        else:
            by_body[record.normalized_body] = record

    for earlier, later in zip(records, records[1:]):
        if earlier.number <= later.number:
            findings.append(GovernanceFinding(
                code="decision-order",
                message=("decision definitions are not strictly descending: "
                         f"{earlier.decision_id} at line {earlier.line} before "
                         f"{later.decision_id} at line {later.line}"),
                line=later.line,
                decision_id=later.decision_id,
                other_line=earlier.line,
            ))

    findings.sort(key=lambda item: (
        item.line, item.code, item.decision_id,
        item.other_line if item.other_line is not None else 0,
    ))
    return GovernanceAudit(
        path=absolute,
        definitions=records,
        findings=tuple(findings),
    )


__all__ = [
    "ACTIVE_DECISIONS",
    "DecisionDefinition",
    "GovernanceAudit",
    "GovernanceFinding",
    "audit_active_decisions",
]
