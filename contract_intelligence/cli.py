"""Command line interface for the deterministic workbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .actions import build_actions
from .audit import append_audit
from .conflicts import detect_conflicts
from .fixtures import generate_fixtures
from .parser import parse_contract
from .report import HONESTY_STATEMENT, assemble_report, write_report
from .rules import extract_obligations, extract_pricing, extract_renewals, extract_unusual_clauses


def _contract_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {path}")
    return sorted(
        (
            item for item in path.iterdir()
            if item.is_file()
            and item.suffix.casefold() in {".md", ".txt"}
            and item.name.casefold() != "dossier.md"
        ),
        key=lambda item: item.name.casefold(),
    )


def _load_documents(paths: list[Path]):
    return [parse_contract(path) for path in paths]


def _hashes(documents) -> dict[str, str]:
    return {doc.document_id: doc.sha256 for doc in documents}


def _counts(report: dict[str, Any]) -> dict[str, int]:
    return {
        "documents": len(report.get("documents", [])),
        "obligations": len(report.get("obligations", [])),
        "renewal_dates": len(report.get("renewal_dates", [])),
        "pricing_terms": len(report.get("pricing_terms", [])),
        "unusual_clauses": len(report.get("unusual_clauses", [])),
        "conflicts": len(report.get("conflicts", [])),
        "actions": len(report.get("actions", [])),
    }


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _print_result(value: Any) -> None:
    _print({"honesty_statement": HONESTY_STATEMENT, "result": value})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ci",
        description=HONESTY_STATEMENT,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fixtures_parser = sub.add_parser("fixtures", help="Generate synthetic fictional fixture contracts")
    fixtures_parser.add_argument("--out", required=True, type=Path)
    fixtures_parser.add_argument("--clean", action="store_true", help="Omit the planted payment conflict")

    extract_parser = sub.add_parser("extract", help="Parse a contract and extract typed evidence")
    extract_parser.add_argument("contract", type=Path)
    extract_parser.add_argument("--type", choices=("all", "parse", "obligations", "renewals", "pricing", "unusual"), default="all")

    conflicts_parser = sub.add_parser("conflicts", help="Compare clauses across a contract directory")
    conflicts_parser.add_argument("directory", type=Path)

    actions_parser = sub.add_parser("actions", help="Build an owner and deadline action register")
    actions_parser.add_argument("directory", type=Path)

    report_parser = sub.add_parser("report", help="Write report.json and dossier.md for a directory")
    report_parser.add_argument("directory", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = list(argv) if argv is not None else __import__("sys").argv[1:]
    if args.command == "fixtures":
        paths = generate_fixtures(args.out, clean=args.clean)
        hashes = {path.stem: parse_contract(path).sha256 for path in paths}
        append_audit(["fixtures", "--out", str(args.out)] + (["--clean"] if args.clean else []), hashes, {"documents": len(paths)})
        _print_result({"generated": [str(path) for path in paths], "synthetic": True, "seed": "none; fixed fixture text"})
        return 0

    paths = _contract_paths(args.contract if args.command == "extract" else args.directory)
    documents = _load_documents(paths)
    report = assemble_report(documents)
    if args.command == "extract":
        document = documents[0]
        if args.type == "parse":
            result = document.to_dict()
        elif args.type == "obligations":
            result = [item.to_dict() for item in extract_obligations(document)]
        elif args.type == "renewals":
            result = extract_renewals(document)
        elif args.type == "pricing":
            result = extract_pricing(document)
        elif args.type == "unusual":
            result = extract_unusual_clauses(document)
        else:
            result = report
        _print_result(result)
    elif args.command == "conflicts":
        result = [item.to_dict() for item in detect_conflicts(documents)]
        _print_result(result)
    elif args.command == "actions":
        result = [item.to_dict() for item in build_actions(documents)]
        _print_result(result)
    elif args.command == "report":
        json_path, markdown_path, report = write_report(documents, args.directory)
        _print_result({"json_report": str(json_path), "markdown_dossier": str(markdown_path), "counts": _counts(report)})

    append_audit(command, _hashes(documents), _counts(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
