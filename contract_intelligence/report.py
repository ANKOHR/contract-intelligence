"""Build byte-stable JSON and Markdown contract dossiers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .actions import build_actions
from .conflicts import detect_conflicts
from .models import ContractDocument
from .rules import (
    extract_obligations,
    extract_pricing,
    extract_renewals,
    extract_unusual_clauses,
)

HONESTY_STATEMENT = (
    "Contract Intelligence performs deterministic pattern extraction on synthetic fixtures "
    "and text supplied by the user. It is not legal advice, not a lawyer's contract review, "
    "and not a substitute for professional review. Evidence pointers are exact quotes from "
    "the input text, nothing more."
)


def assemble_report(documents: list[ContractDocument]) -> dict[str, Any]:
    return {
        "product": "Contract Intelligence",
        "honesty_statement": HONESTY_STATEMENT,
        "method": "deterministic pattern extraction",
        "documents": [document.to_dict() for document in sorted(documents, key=lambda d: d.document_id)],
        "obligations": [item.to_dict() for doc in documents for item in extract_obligations(doc, documents)],
        "renewal_dates": [item for doc in documents for item in extract_renewals(doc, documents)],
        "pricing_terms": [item for doc in documents for item in extract_pricing(doc)],
        "unusual_clauses": [item for doc in documents for item in extract_unusual_clauses(doc)],
        "conflicts": [item.to_dict() for item in detect_conflicts(documents)],
        "actions": [item.to_dict() for item in build_actions(documents)],
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _evidence_line(evidence: dict[str, str]) -> str:
    return f"Evidence: `{evidence['document_id']}` / {evidence['section']}\n\n> {evidence['quote']}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Contract Intelligence Dossier",
        "",
        f"> {report['honesty_statement']}",
        "",
        "This dossier contains deterministic pattern extraction results. Each evidence quote is copied from the input text.",
        "",
        "## Obligations",
        "",
    ]
    for item in report["obligations"]:
        lines.extend([
            f"### {item['obligation_type'].replace('-', ' ').title()} for {item['party']}",
            "",
            f"Trigger: {item['trigger']}",
            f"Deadline: {item['deadline'] or 'Depends on the stated trigger'}",
            "",
            _evidence_line(item["evidence"]),
            "",
        ])
    lines.extend(["## Renewal dates", ""])
    for item in report["renewal_dates"]:
        lines.extend([
            f"- Renewal term: {item['renewal_term']}; term end: {item['term_end'] or 'not extracted'}.",
            "",
            _evidence_line(item["evidence"]),
            "",
        ])
        if item.get("term_end_evidence"):
            lines.extend(["Term end evidence:", "", _evidence_line(item["term_end_evidence"]), ""])
    lines.extend(["## Pricing terms", ""])
    for item in report["pricing_terms"]:
        lines.extend([
            f"- {item['rate_percent']:g}% annual pricing escalator.",
            "",
            _evidence_line(item["evidence"]),
            "",
        ])
    lines.extend(["## Unusual clauses", ""])
    for item in report["unusual_clauses"]:
        lines.extend([
            f"- {item['kind'].replace('_', ' ').title()}: {item['note']}",
            "",
            _evidence_line(item["evidence"]),
            "",
        ])
    lines.extend(["## Conflicts", ""])
    if not report["conflicts"]:
        lines.append("No conflicting language was detected by the configured rules.")
        lines.append("")
    for item in report["conflicts"]:
        lines.extend([f"- **{item['severity'].title()} {item['conflict_type'].replace('_', ' ')}:** {item['summary']}", ""])
        for evidence in item["evidence"]:
            lines.extend([_evidence_line(evidence), ""])
    lines.extend(["## Required actions", ""])
    if not report["actions"]:
        lines.append("No actions were extracted.")
        lines.append("")
    for item in report["actions"]:
        due = item["due_date"] or "Trigger-based date not computable from input"
        lines.extend([
            f"- **{due} | {item['owner']} | {item['title']}**",
            f"  Trigger: {item['trigger']}",
        ])
        if item["warning"]:
            lines.append(f"  Window warning: {item['warning']}")
        lines.extend(["", _evidence_line(item["evidence"]), ""])
    return "\n".join(lines).rstrip() + "\n"


def write_report(documents: list[ContractDocument], out_dir: str | Path) -> tuple[Path, Path, dict[str, Any]]:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    report = assemble_report(documents)
    json_path = target / "report.json"
    markdown_path = target / "dossier.md"
    json_path.write_text(render_json(report), encoding="utf-8", newline="\n")
    markdown_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return json_path, markdown_path, report
