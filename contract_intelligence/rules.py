"""Named deterministic patterns for obligations and highlighted clause types."""

from __future__ import annotations

import re
from datetime import datetime

from .models import ContractDocument, EvidenceRef, Obligation

DURATION_RE = re.compile(r"\b(\d+)\s+(calendar\s+|business\s+)?days?\b", re.I)
DATE_WORD_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}\b",
    re.I,
)


def _subject(text: str) -> str:
    match = re.match(r"^\s*(.+?)\s+(?:shall|must|may|will)\b", text, re.I)
    if match:
        return match.group(1).strip().strip(",")
    return "Unspecified party"


def _first_duration(text: str) -> tuple[int, str] | None:
    match = DURATION_RE.search(text)
    if not match:
        return None
    return int(match.group(1)), (match.group(2) or "").strip().casefold()


def _term_end(document: ContractDocument) -> str | None:
    for clause in document.clauses:
        if re.search(r"\b(?:initial term|term expires|term ends|through)\b", clause.text, re.I):
            facts = [fact for fact in document.dates if fact.evidence == clause.evidence]
            if facts:
                return facts[-1].value
            matches = DATE_WORD_RE.findall(clause.text)
            for date_text in matches:
                try:
                    return datetime.strptime(date_text, "%B %d, %Y").date().isoformat()
                except ValueError:
                    pass
    return None


def effective_term_end(
    document: ContractDocument,
    related_documents: list[ContractDocument] | None = None,
) -> tuple[str | None, EvidenceRef | None]:
    """Use an explicit related amendment extension when one is present."""
    candidates: list[tuple[str, object]] = []
    if related_documents:
        for related in related_documents:
            if related.document_id == document.document_id or not set(document.parties).intersection(related.parties):
                continue
            for clause in related.clauses:
                if not re.search(r"\bextended through\b", clause.text, re.I):
                    continue
                facts = [fact for fact in related.dates if fact.evidence == clause.evidence]
                if facts:
                    candidates.append((facts[-1].value, clause.evidence))
    if candidates:
        return max(candidates, key=lambda item: item[0])
    for clause in document.clauses:
        if re.search(r"\b(?:initial term|term expires|term ends|through)\b", clause.text, re.I):
            facts = [fact for fact in document.dates if fact.evidence == clause.evidence]
            if facts:
                return facts[-1].value, clause.evidence
    return _term_end(document), None


def extract_obligations(
    document: ContractDocument,
    related_documents: list[ContractDocument] | None = None,
) -> list[Obligation]:
    results: list[Obligation] = []
    for clause in document.clauses:
        text = clause.text
        lower = text.casefold()
        kind: str | None = None
        trigger = "When the stated contractual condition occurs"
        deadline: str | None = None
        tags: list[str] = []

        if re.search(r"\bautomatically renews?\b", lower):
            kind = "renew"
            duration = _first_duration(text)
            if duration and re.search(r"\b(?:notice|notifies|notify)\b", lower):
                days, _unit = duration
                tags.extend([f"notice_days:{days}", "notice_window"])
                end, _end_evidence = effective_term_end(document, related_documents)
                if end:
                    tags.append(f"term_end:{end}")
                    trigger = f"Give written notice at least {days} days before the current term ends on {end}"
                    deadline = f"{days} days before {end}"
                else:
                    trigger = f"Give written notice at least {days} days before the current term ends"
                    deadline = f"{days} days before term end"
            else:
                trigger = "At the end of the then-current term unless a party gives notice"
        elif re.search(r"\bmay terminate\b", lower):
            kind = "terminate-right"
            duration = _first_duration(text)
            if duration:
                tags.append(f"notice_days:{duration[0]}")
                trigger = f"After {duration[0]} days' written notice"
            cure = re.search(r"(\d+)\s+days?\s+to cure", lower)
            if cure:
                tags.append(f"cure_days:{cure.group(1)}")
            if "convenience" in lower:
                tags.append("termination_for_convenience")
        elif re.search(r"\b(?:shall|must|will)\s+pay\b", lower):
            kind = "pay"
            duration = _first_duration(text)
            if duration:
                trigger = f"Within {duration[0]} days after the stated payment trigger"
                deadline = f"{duration[0]} days after invoice receipt"
            else:
                trigger = "As stated in the payment clause"
        elif re.search(r"\b(?:shall|must|will)\s+(?:deliver|provide|submit)\b", lower):
            kind = "deliver"
            duration = _first_duration(text)
            if duration:
                trigger = f"Within {duration[0]} days after the stated delivery trigger"
                deadline = f"{duration[0]} days after the stated trigger"
            else:
                trigger = "As stated in the delivery clause"
        elif re.search(r"\b(?:shall|must|will)\s+(?:notify|give|provide|send|deliver)\b", lower) and re.search(r"\b(?:notice|notify)\b", lower):
            kind = "notify"
            duration = _first_duration(text)
            if duration:
                trigger = f"At least {duration[0]} days before the stated event"
                deadline = f"{duration[0]} days before the stated event"
        elif re.search(r"\b(?:shall|must|will)\s+comply\b", lower):
            kind = "comply"
            trigger = "Throughout performance of the agreement"

        if kind:
            party = "Either party" if kind == "renew" and re.search(r"\beither party\b", lower) else _subject(text)
            results.append(
                Obligation(kind, party, trigger, deadline, clause.evidence, tuple(tags))
            )
    return results


def extract_pricing(document: ContractDocument) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    patterns = (
        ("annual_escalator", re.compile(r"\b(\d+(?:\.\d+)?)\s*%\s+(?:annual\s+)?(?:price|pricing|fee|rate)\s+escalator\b", re.I)),
        ("annual_escalator", re.compile(r"\b(?:increase|escalat\w*)\b[^.]{0,80}?\b(\d+(?:\.\d+)?)\s*%\b", re.I)),
    )
    for clause in document.clauses:
        for kind, pattern in patterns:
            match = pattern.search(clause.text)
            if match:
                found.append({"kind": kind, "rate_percent": float(match.group(1)), "evidence": clause.evidence.to_dict()})
                break
    return found


def extract_renewals(
    document: ContractDocument,
    related_documents: list[ContractDocument] | None = None,
) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for clause in document.clauses:
        match = re.search(r"automatically renews?[^.]*", clause.text, re.I)
        if match:
            duration = _first_duration(match.group(0))
            term, term_evidence = effective_term_end(document, related_documents)
            found.append({
                "renewal_term": f"{duration[0]} days' notice" if duration else "Automatic renewal",
                "term_end": term,
                "term_end_evidence": term_evidence.to_dict() if term_evidence else None,
                "evidence": clause.evidence.to_dict(),
            })
    return found


def extract_unusual_clauses(document: ContractDocument) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for clause in document.clauses:
        lower = clause.text.casefold()
        if "indemnif" in lower and ("any and all" in lower or "regardless of fault" in lower or "all claims" in lower):
            found.append({"kind": "broad_indemnity", "note": "Pattern flags broad indemnity wording for human review.", "evidence": clause.evidence.to_dict()})
        if "liability" in lower and re.search(r"cap|shall not exceed|limited to", lower):
            found.append({"kind": "liability_cap", "note": "Liability cap wording detected by a named pattern.", "evidence": clause.evidence.to_dict()})
        if "terminate for convenience" in lower:
            found.append({"kind": "termination_for_convenience", "note": "Termination for convenience wording detected.", "evidence": clause.evidence.to_dict()})
    return found
