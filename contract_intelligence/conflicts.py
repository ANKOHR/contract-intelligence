"""Cross-document conflict rules for payment, caps, renewal, and governing law."""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations

from .models import Conflict, ContractDocument, EvidenceRef

PAYMENT_RE = re.compile(r"\bwithin\s+(\d+)\s+(?:calendar\s+)?days?\s+after\s+receipt\s+of\s+the\s+invoice\b", re.I)
LAW_RE = re.compile(r"\bgoverned by the laws of\s+([A-Za-z ]+?)(?:[.;]|$)", re.I)
RENEW_RE = re.compile(r"automatically renews?[^.]*", re.I)
CAP_RE = re.compile(r"(?:shall not exceed|limited to|cap(?:ped)? at)[^.]*", re.I)


def _values(document: ContractDocument) -> dict[str, list[tuple[str, EvidenceRef]]]:
    values: dict[str, list[tuple[str, EvidenceRef]]] = defaultdict(list)
    for clause in document.clauses:
        for match in PAYMENT_RE.finditer(clause.text):
            values["payment_terms"].append((f"{match.group(1)} days after invoice receipt", clause.evidence))
        for match in LAW_RE.finditer(clause.text):
            values["governing_law"].append((match.group(1).strip().casefold(), clause.evidence))
        match = RENEW_RE.search(clause.text)
        if match:
            normalized = re.sub(r"\s+", " ", match.group(0).strip().casefold())
            values["renewal_mechanics"].append((normalized, clause.evidence))
        match = CAP_RE.search(clause.text)
        if match and "liability" in clause.text.casefold():
            normalized = re.sub(r"\s+", " ", match.group(0).strip().casefold())
            values["liability_cap"].append((normalized, clause.evidence))
    return values


def detect_conflicts(documents: list[ContractDocument]) -> list[Conflict]:
    by_doc = {document.document_id: _values(document) for document in documents}
    conflicts: list[Conflict] = []
    ordered_docs = sorted(documents, key=lambda d: d.document_id)
    for category in ("payment_terms", "liability_cap", "renewal_mechanics", "governing_law"):
        records = [
            (document, value, reference)
            for document in ordered_docs
            for value, reference in by_doc[document.document_id].get(category, [])
        ]
        records.sort(key=lambda item: (item[0].document_id, item[2].section, item[2].quote, item[1]))
        for (left, left_value, left_ref), (right, right_value, right_ref) in combinations(records, 2):
            if left.document_id == right.document_id:
                if left_ref.quote == right_ref.quote:
                    continue
            # Across documents, require an overlapping identified party as a
            # conservative signal that the language may govern one relationship.
            elif not set(left.parties).intersection(right.parties):
                continue
            if left_value == right_value:
                continue
            severity = "high" if category in {"payment_terms", "liability_cap", "governing_law"} else "medium"
            conflicts.append(Conflict(
                conflict_type=category,
                severity=severity,
                summary=f"{left.document_id} states {left_value}; {right.document_id} states {right_value}.",
                evidence=(left_ref, right_ref),
            ))
    return conflicts
