"""Parser for contract section structure, parties, and explicit date facts."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

from .models import Clause, ContractDocument, DateFact, EvidenceRef, Section

HEADING_RE = re.compile(r"^\s{0,3}(?:#{1,6}\s+(.+?)\s*#*|(?:(?:section\s+)?\d+(?:\.\d+)*[.)]?\s+(.+)))\s*$", re.I)
PARTY_RE = re.compile(
    r"between\s+(.+?)\s*\(\s*[\"']([^\"']+)[\"']\s*\)\s+and\s+(.+?)\s*\(\s*[\"']([^\"']+)[\"']\s*\)",
    re.I,
)
DATE_PATTERNS = (
    ("iso_date", re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")),
    ("named_date", re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}\b", re.I)),
)


def _date_value(match: str, kind: str) -> str | None:
    try:
        if kind == "iso_date":
            return date.fromisoformat(match).isoformat()
        from datetime import datetime
        return datetime.strptime(match, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def _section_blocks(text: str) -> list[Section]:
    sections: list[Section] = []
    current_title = "Preamble"
    current_lines: list[str] = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            body = "\n".join(current_lines).strip()
            if body or not sections:
                sections.append(Section(current_title, body))
            current_title = (match.group(1) or match.group(2)).strip()
            current_lines = []
        else:
            current_lines.append(line.rstrip())
    body = "\n".join(current_lines).strip()
    if body or not sections:
        sections.append(Section(current_title, body))
    return sections


def _parse_content(source_name: str, raw_bytes: bytes) -> ContractDocument:
    source = Path(source_name)
    text = raw_bytes.decode("utf-8-sig")
    document_id = source.stem
    sections = _section_blocks(text)
    clauses: list[Clause] = []
    for section in sections:
        for line in section.text.splitlines():
            quote = line.strip()
            if quote and not quote.startswith("<!--"):
                clauses.append(Clause(EvidenceRef(document_id, section.title, quote), quote))

    parties: list[str] = []
    party_match = PARTY_RE.search(text)
    if party_match:
        parties = [party_match.group(1).strip(), party_match.group(3).strip()]
        parties.extend([party_match.group(2).strip(), party_match.group(4).strip()])
    else:
        # Also recognize simple defined-party declarations used in user text.
        for match in re.finditer(r"([A-Z][A-Za-z0-9 &.,'-]+?)\s+\(\s*([\"'])([^\"']+)\2\s*\)", text):
            parties.extend([match.group(3).strip(), match.group(1).strip()])
    # Preserve order while removing duplicates.
    parties = list(dict.fromkeys(p for p in parties if p))

    dates: list[DateFact] = []
    for clause in clauses:
        for kind, pattern in DATE_PATTERNS:
            for match in pattern.finditer(clause.text):
                value = _date_value(match.group(0), kind)
                if value:
                    dates.append(DateFact(value, kind, clause.evidence))
    return ContractDocument(
        document_id=document_id,
        source_name=source.name,
        text=text,
        sections=sections,
        clauses=clauses,
        parties=parties,
        dates=dates,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def parse_contract(path: str | Path) -> ContractDocument:
    source = Path(path)
    return _parse_content(source.name, source.read_bytes())


def parse_text(text: str, document_id: str = "input.txt") -> ContractDocument:
    """Parse in-memory UTF-8 text using the same rules as file parsing."""
    source_name = Path(document_id).name
    return _parse_content(source_name, text.encode("utf-8"))
