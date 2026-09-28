from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from contract_intelligence.actions import build_actions
from contract_intelligence.conflicts import detect_conflicts
from contract_intelligence.fixtures import FIXTURES, generate_fixtures
from contract_intelligence.parser import parse_contract, parse_text
from contract_intelligence.report import HONESTY_STATEMENT, assemble_report, render_json, render_markdown, write_report
from contract_intelligence.rules import (
    extract_obligations,
    extract_pricing,
    extract_renewals,
    extract_unusual_clauses,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture

def fixture_dir(tmp_path: Path) -> Path:
    target = tmp_path / "contracts"
    generate_fixtures(target)
    return target


def test_fixture_generation_is_deterministic_and_plants_all_scenarios(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    paths_a = generate_fixtures(first)
    paths_b = generate_fixtures(second)
    assert [path.name for path in paths_a] == [path.name for path in paths_b]
    assert {path.name: path.read_bytes() for path in paths_a} == {path.name: path.read_bytes() for path in paths_b}
    assert len(paths_a) == 5
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths_a)
    for phrase in (
        "SYNTHETIC FICTIONAL FIXTURE",
        "automatically renews",
        "60 days before",
        "5% annual pricing escalator",
        "any and all claims",
        "terminate for convenience",
        "30 days to cure",
        "aggregate liability shall not exceed",
        "within 30 calendar days",
        "within 60 calendar days",
    ):
        assert phrase in combined
    assert "synthetic" in paths_a[0].read_text(encoding="utf-8").casefold()


def test_clean_fixture_generation_omits_only_planted_conflict(tmp_path: Path) -> None:
    target = tmp_path / "clean"
    generate_fixtures(target)
    paths = generate_fixtures(target, clean=True)
    assert len(paths) == 4
    assert "reseller_contract.md" not in {path.name for path in paths}
    assert not (target / "reseller_contract.md").exists()
    docs = [parse_contract(path) for path in paths]
    assert detect_conflicts(docs) == []


def test_parser_sections_parties_dates_and_repeatability(fixture_dir: Path) -> None:
    path = fixture_dir / "services_agreement.md"
    first = parse_contract(path)
    second = parse_contract(path)
    assert [section.title for section in first.sections] == [
        "Preamble",
        "Synthetic Services Agreement",
        "Parties and Effective Date",
        "Term and Renewal",
        "Fees and Payment",
        "Indemnity and Liability",
        "Termination",
        "Governing Law",
    ]
    assert first.parties == ["Northstar Labs Ltd", "Cedar Ridge Systems Ltd", "Client", "Provider"]
    assert {fact.value for fact in first.dates} >= {"2026-09-01", "2027-08-31"}
    assert first.to_dict() == second.to_dict()
    assert first.sha256 == second.sha256
    assert all(clause.text == clause.evidence.quote for clause in first.clauses)
    assert all(clause.evidence.section in {section.title for section in first.sections} for clause in first.clauses)


def test_parser_handles_plain_text_and_iso_dates() -> None:
    parsed = parse_text(
        '## Parties\nThis Agreement is between Acme Ltd ("Buyer") and Beta Ltd ("Seller").\n'
        '## Start Date\nThe Effective Date is 2026-10-02.\n',
        "simple.txt",
    )
    assert parsed.document_id == "simple"
    assert parsed.parties == ["Acme Ltd", "Beta Ltd", "Buyer", "Seller"]
    assert [(item.value, item.evidence.section) for item in parsed.dates] == [("2026-10-02", "Start Date")]


def test_obligations_extract_planted_types_with_party_trigger_and_exact_quote(fixture_dir: Path) -> None:
    document = parse_contract(fixture_dir / "services_agreement.md")
    obligations = extract_obligations(document)
    by_type = {item.obligation_type: item for item in obligations}
    assert set(by_type) == {"renew", "pay", "deliver", "notify", "comply", "terminate-right"}
    expected = {
        "renew": ("Either party", "60 days before", "This Agreement automatically renews"),
        "pay": ("Client", "30 days", "Client shall pay each undisputed invoice"),
        "deliver": ("Provider", "5 days", "Provider shall deliver a monthly service report"),
        "notify": ("Provider", "10 days", "Provider shall notify Client in writing"),
        "comply": ("Provider", "Throughout performance", "Provider shall comply with the security requirements"),
        "terminate-right": ("Client", "30 days", "Client may terminate for convenience"),
    }
    for kind, (party, trigger_part, quote_part) in expected.items():
        item = by_type[kind]
        assert item.party == party
        assert trigger_part in item.trigger
        assert quote_part in item.evidence.quote
        assert item.evidence.quote in document.text
        assert item.evidence.document_id == document.document_id
        assert item.evidence.section in {section.title for section in document.sections}
    assert by_type["pay"].deadline == "30 days after invoice receipt"
    assert "cure_days:30" in by_type["terminate-right"].tags
    assert "termination_for_convenience" in by_type["terminate-right"].tags


def test_obligation_rules_do_not_invent_from_control_paragraph() -> None:
    document = parse_text(
        "## Relationship\nThe parties value a clear relationship and cooperative communication. "
        "This paragraph describes shared goals and creates no payment, delivery, notice, renewal, "
        "compliance, or termination duty.\n",
        "control.md",
    )
    assert extract_obligations(document) == []


def test_pricing_renewal_and_unusual_clause_patterns_have_evidence(fixture_dir: Path) -> None:
    document = parse_contract(fixture_dir / "services_agreement.md")
    pricing = extract_pricing(document)
    renewals = extract_renewals(document)
    unusual = extract_unusual_clauses(document)
    assert len(pricing) == 1 and pricing[0]["rate_percent"] == 5.0
    assert pricing[0]["evidence"]["quote"].startswith("Fees increase by a 5%")
    assert len(renewals) == 1
    assert renewals[0]["term_end"] == "2027-08-31"
    assert renewals[0]["evidence"]["quote"].startswith("The Initial Term runs")
    assert {item["kind"] for item in unusual} == {
        "broad_indemnity",
        "liability_cap",
        "termination_for_convenience",
    }
    for item in pricing + renewals + unusual:
        assert item["evidence"]["quote"] in document.text
        assert item["evidence"]["document_id"] == document.document_id


def test_conflict_detector_reports_both_planted_payment_sources(fixture_dir: Path) -> None:
    documents = [parse_contract(path) for path in sorted(fixture_dir.glob("*.md"))]
    conflicts = detect_conflicts(documents)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.conflict_type == "payment_terms"
    assert conflict.severity == "high"
    assert "30 days" in conflict.summary and "60 days" in conflict.summary
    assert len(conflict.evidence) == 2
    quotes = {reference.quote for reference in conflict.evidence}
    assert any("within 30 calendar days" in quote for quote in quotes)
    assert any("within 60 calendar days" in quote for quote in quotes)
    for reference in conflict.evidence:
        assert reference.document_id in {doc.document_id for doc in documents}
        assert reference.quote in next(doc.text for doc in documents if doc.document_id == reference.document_id)


@pytest.mark.parametrize(
    ("category", "left_clause", "right_clause"),
    [
        ("payment_terms", "Buyer shall pay invoices within 20 days after receipt of the invoice.", "Buyer shall pay invoices within 45 days after receipt of the invoice."),
        ("liability_cap", "Each party's liability shall not exceed fees paid in the prior year.", "Each party's liability is capped at fees paid and payable in the prior year."),
        ("renewal_mechanics", "This Agreement automatically renews for one-year terms unless notice is given 30 days before expiry.", "This Agreement automatically renews for two-year terms unless notice is given 90 days before expiry."),
        ("governing_law", "This Agreement is governed by the laws of England and Wales.", "This Agreement is governed by the laws of Scotland."),
    ],
)
def test_conflict_rules_cover_each_supported_category(category: str, left_clause: str, right_clause: str) -> None:
    parties = 'This Agreement is between Acme Ltd ("Buyer") and Beta Ltd ("Seller").'
    left = parse_text(f"{parties}\n## Terms\n{left_clause}\n", "left.md")
    right = parse_text(f"{parties}\n## Terms\n{right_clause}\n", "right.md")
    conflicts = detect_conflicts([left, right])
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == category
    assert conflicts[0].evidence[0].quote == left_clause
    assert conflicts[0].evidence[1].quote == right_clause


def test_conflict_detector_compares_clauses_across_sections_in_one_document() -> None:
    document = parse_text(
        'This Agreement is between Acme Ltd ("Buyer") and Beta Ltd ("Seller").\n'
        "## Fees\nBuyer shall pay invoices within 20 days after receipt of the invoice.\n"
        "## Schedule A\nBuyer shall pay invoices within 45 days after receipt of the invoice.\n",
        "single.md",
    )
    conflicts = detect_conflicts([document])
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "payment_terms"
    assert {ref.section for ref in conflicts[0].evidence} == {"Fees", "Schedule A"}


def test_action_register_computes_amended_notice_deadline_and_sorts(fixture_dir: Path) -> None:
    documents = [parse_contract(path) for path in sorted(fixture_dir.glob("*.md"))]
    actions = build_actions(documents)
    dated = [item for item in actions if item.due_date]
    undated = [item for item in actions if not item.due_date]
    assert [item.due_date for item in actions] == [item.due_date for item in dated] + [None] * len(undated)
    renewal = next(item for item in actions if item.notice_window)
    assert renewal.due_date == "2028-07-02"
    assert renewal.owner == "Either party"
    assert "60-day notice window" in renewal.warning
    assert "automatically renews" in renewal.evidence.quote
    assert all(item.evidence.document_id for item in actions)


def test_clean_fixture_report_has_no_conflicts(tmp_path: Path) -> None:
    paths = generate_fixtures(tmp_path / "clean", clean=True)
    report = assemble_report([parse_contract(path) for path in paths])
    assert report["conflicts"] == []


def test_report_has_evidence_everywhere_and_is_byte_stable(fixture_dir: Path) -> None:
    documents = [parse_contract(path) for path in sorted(fixture_dir.glob("*.md"))]
    first = assemble_report(documents)
    second = assemble_report(documents)
    json_bytes = render_json(first).encode("utf-8")
    assert json_bytes == render_json(second).encode("utf-8")
    assert HONESTY_STATEMENT in first["honesty_statement"]
    assert first["honesty_statement"] in render_markdown(first)
    for key in ("obligations", "renewal_dates", "pricing_terms", "unusual_clauses", "actions"):
        assert all(item.get("evidence") for item in first[key])
    assert all(len(item["evidence"]) == 2 for item in first["conflicts"])
    renewal = first["renewal_dates"][0]
    assert renewal["term_end"] == "2028-08-31"
    assert renewal["term_end_evidence"]["document_id"] == "renewal_amendment"
    markdown = render_markdown(first)
    for key in ("obligations", "renewal_dates", "pricing_terms", "unusual_clauses", "actions"):
        for item in first[key]:
            assert item["evidence"]["quote"] in markdown
    for item in first["conflicts"]:
        for evidence in item["evidence"]:
            assert evidence["quote"] in markdown
    assert renewal["term_end_evidence"]["quote"] in markdown
    json_path, md_path, _ = write_report(documents, fixture_dir)
    json_before, md_before = json_path.read_bytes(), md_path.read_bytes()
    write_report(documents, fixture_dir)
    assert json_path.read_bytes() == json_before
    assert md_path.read_bytes() == md_before


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, "-m", "contract_intelligence", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_cli_smoke_all_subcommands_audit_and_end_to_end_repeatability(tmp_path: Path) -> None:
    first = tmp_path / "run_one"
    second = tmp_path / "run_two"
    first.mkdir()
    second.mkdir()
    for cwd in (first, second):
        fixture_path = cwd / "contracts"
        generated = _run_cli(["fixtures", "--out", str(fixture_path)], cwd)
        assert HONESTY_STATEMENT in generated.stdout
        extracted = _run_cli(["extract", str(fixture_path / "services_agreement.md"), "--type", "obligations"], cwd)
        assert HONESTY_STATEMENT in extracted.stdout
        assert json.loads(extracted.stdout)["result"]
        conflicts = _run_cli(["conflicts", str(fixture_path)], cwd)
        assert len(json.loads(conflicts.stdout)["result"]) == 1
        actions = _run_cli(["actions", str(fixture_path)], cwd)
        assert next(item for item in json.loads(actions.stdout)["result"] if item["notice_window"])["due_date"] == "2028-07-02"
        report_result = _run_cli(["report", str(fixture_path)], cwd)
        assert HONESTY_STATEMENT in report_result.stdout
        assert (fixture_path / "report.json").exists()
        assert (fixture_path / "dossier.md").exists()
        assert HONESTY_STATEMENT in (fixture_path / "dossier.md").read_text(encoding="utf-8")
        assert len((cwd / "ci-audit.jsonl").read_text(encoding="utf-8").splitlines()) == 5
    assert (first / "contracts" / "report.json").read_bytes() == (second / "contracts" / "report.json").read_bytes()
    assert (first / "contracts" / "dossier.md").read_bytes() == (second / "contracts" / "dossier.md").read_bytes()
    audit = [json.loads(line) for line in (first / "ci-audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["command"][0] for entry in audit] == ["fixtures", "extract", "conflicts", "actions", "report"]
    assert all(entry["input_hashes"] for entry in audit)
