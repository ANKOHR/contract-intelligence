"""Typed records shared by parsing and extraction rules."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceRef:
    document_id: str
    section: str
    quote: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class Section:
    title: str
    text: str


@dataclass(frozen=True)
class DateFact:
    value: str
    kind: str
    evidence: EvidenceRef

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "kind": self.kind, "evidence": self.evidence.to_dict()}


@dataclass(frozen=True)
class Clause:
    evidence: EvidenceRef
    text: str


@dataclass
class ContractDocument:
    document_id: str
    source_name: str
    text: str
    sections: list[Section]
    clauses: list[Clause]
    parties: list[str]
    dates: list[DateFact]
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_name": self.source_name,
            "sha256": self.sha256,
            "parties": list(self.parties),
            "sections": [{"title": s.title, "text": s.text} for s in self.sections],
            "clauses": [
                {"text": c.text, "evidence": c.evidence.to_dict()} for c in self.clauses
            ],
            "dates": [d.to_dict() for d in self.dates],
        }


@dataclass(frozen=True)
class Obligation:
    obligation_type: str
    party: str
    trigger: str
    deadline: str | None
    evidence: EvidenceRef
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_type": self.obligation_type,
            "party": self.party,
            "trigger": self.trigger,
            "deadline": self.deadline,
            "tags": list(self.tags),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True)
class Conflict:
    conflict_type: str
    severity: str
    summary: str
    evidence: tuple[EvidenceRef, EvidenceRef]

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "summary": self.summary,
            "evidence": [ref.to_dict() for ref in self.evidence],
        }


@dataclass(frozen=True)
class Action:
    action_id: str
    title: str
    owner: str
    due_date: str | None
    trigger: str
    notice_window: bool
    warning: str | None
    evidence: EvidenceRef

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "title": self.title,
            "owner": self.owner,
            "due_date": self.due_date,
            "trigger": self.trigger,
            "notice_window": self.notice_window,
            "warning": self.warning,
            "evidence": self.evidence.to_dict(),
        }


def evidence_for(document: ContractDocument, section: str, quote: str) -> EvidenceRef:
    return EvidenceRef(document.document_id, section, quote)
