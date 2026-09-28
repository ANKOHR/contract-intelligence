"""Synthetic, fictional contract fixture generator. No external documents are used."""

from pathlib import Path

FIXTURE_NOTICE = "SYNTHETIC FICTIONAL FIXTURE. NOT A REAL CONTRACT. FOR SOFTWARE TESTING ONLY."

FIXTURES: dict[str, str] = {
    "services_agreement.md": f"""# Synthetic Services Agreement

{FIXTURE_NOTICE}

## Parties and Effective Date
This Agreement is between Northstar Labs Ltd (\"Client\") and Cedar Ridge Systems Ltd (\"Provider\"). It is effective September 1, 2026.

## Term and Renewal
The Initial Term runs from September 1, 2026 through August 31, 2027. This Agreement automatically renews for successive one-year terms unless either party gives written notice of non-renewal at least 60 days before the current term ends.

## Fees and Payment
Client shall pay each undisputed invoice within 30 calendar days after receipt of the invoice.
Provider shall deliver a monthly service report within 5 days after each month end.
Provider shall notify Client in writing at least 10 days before any subcontractor change.
Provider shall comply with the security requirements in Schedule A throughout performance.
Fees increase by a 5% annual pricing escalator on each anniversary of the Effective Date.

## Indemnity and Liability
Provider shall indemnify Client against any and all claims, losses, liabilities, and expenses arising from Provider's services, regardless of fault.
Each party's aggregate liability shall not exceed the fees paid by Client to Provider in the 12 months before the event giving rise to the claim.

## Termination
Client may terminate for convenience by giving Provider 30 days' written notice. For any material breach, the breaching party has 30 days to cure after receipt of written notice.

## Governing Law
This Agreement is governed by the laws of England and Wales.
""",
    "software_licence.md": f"""# Synthetic Software Licence

{FIXTURE_NOTICE}

## Parties
This Agreement is between Northstar Labs Ltd (\"Client\") and Cedar Ridge Systems Ltd (\"Provider\").

## Licence and Delivery
Provider shall provide access credentials within 2 days after the Effective Date.
Client shall comply with the usage limits described in this Agreement.

## Confidentiality
Each party shall protect the other party's confidential information using reasonable care.
""",
    "reseller_contract.md": f"""# Synthetic Reseller Contract

{FIXTURE_NOTICE}

## Parties and Relationship
This Agreement is between Northstar Labs Ltd (\"Client\") and Cedar Ridge Systems Ltd (\"Provider\"). This document supplements the Synthetic Services Agreement dated September 1, 2026.

## Payment Terms
Client shall pay each undisputed invoice within 60 calendar days after receipt of the invoice.

## Reseller Duties
Provider shall deliver quarterly sales statements within 10 days after each quarter end.
""",
    "nda.md": f"""# Synthetic Non-Disclosure Agreement

{FIXTURE_NOTICE}

## Parties
This Agreement is between Northstar Labs Ltd (\"Client\") and Cedar Ridge Systems Ltd (\"Provider\").

## Confidential Information
The parties value clear communication and a cooperative relationship.
Neither party is required to disclose information that it already knew lawfully.
""",
    "renewal_amendment.md": f"""# Synthetic Renewal Amendment

{FIXTURE_NOTICE}

## Parties and Effective Date
This Amendment is between Northstar Labs Ltd (\"Client\") and Cedar Ridge Systems Ltd (\"Provider\"). It is effective August 1, 2027.

## Extension
The Initial Term of the Synthetic Services Agreement is extended through August 31, 2028. All notice requirements and other terms remain unchanged.
""",
}


def generate_fixtures(out_dir: str | Path, clean: bool = False) -> list[Path]:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    selected = dict(FIXTURES)
    if clean:
        # The reseller is the sole fixture that introduces a contradictory payment term.
        selected.pop("reseller_contract.md")
        reseller_path = target / "reseller_contract.md"
        if reseller_path.is_file():
            old_content = reseller_path.read_text(encoding="utf-8")
            if FIXTURE_NOTICE in old_content and "# Synthetic Reseller Contract" in old_content:
                reseller_path.unlink()
    written: list[Path] = []
    for name, content in selected.items():
        path = target / name
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)
    return written
