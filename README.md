# Contract Intelligence

Contract Intelligence is a deterministic contract analysis workbench. It parses plain text and Markdown, extracts typed obligations and selected clause patterns, compares related documents for conflicting language, and builds a required-action register. Every extracted item points to its source document, section, and exact quoted input line.

## Quickstart

Use Python 3.10 or newer. The package uses the Python standard library. Pytest is needed only to run the test suite.

```powershell
python -m contract_intelligence fixtures --out .\fixtures
python -m contract_intelligence extract .\fixtures\services_agreement.md --type obligations
python -m contract_intelligence conflicts .\fixtures
python -m contract_intelligence actions .\fixtures
python -m contract_intelligence report .\fixtures
python -m pytest
```

To install the `ci` console command in an environment, run `python -m pip install -e .`, then use `ci fixtures --out fixtures` and the same subcommands. `python ci.py` is also available when the package has not been installed. The report command writes `report.json` and `dossier.md` in its input directory. Each successful command appends a JSON line to `ci-audit.jsonl` in the current working directory. Audit timestamps vary by run; contract parse and report content do not.

Fixtures are generated locally from fixed source text. No random generator is used, so there is no random seed. All generated documents are marked as synthetic fictional fixtures in their text.

## Architecture

```text
Markdown or plain text
        |
        v
Parser: headings, source lines, parties, dates, SHA-256
        |
        v
Typed rules: obligations, renewal, pricing, unusual clauses
        |                                  |
        v                                  v
Cross-document conflict rules        Action register
        |                                  |
        +------------------+---------------+
                           v
                 JSON report and dossier
                           |
                           v
                  Append-only audit JSONL
```

The parser preserves each nonempty input line as a clause. An evidence reference is formed from the input filename stem as `document_id`, the parsed heading as `section`, and that exact source line as `quote`. Quotes are copied from the input, including punctuation. A multi-sentence source line remains one evidence quote. The SHA-256 hash is computed from the original file bytes.

## HONESTY BOUNDARY

Contract Intelligence performs deterministic pattern extraction on synthetic fixtures and text supplied by the user. It is not legal advice, not a lawyer's contract review, and not a substitute for professional review. Evidence pointers are exact quotes from the input text, nothing more. The rules can miss relevant language or flag language that needs no action. The output does not establish legal meaning, assess legal risk, or replace review by a qualified professional. The fixture documents are fictional and visibly labelled as such. User-provided text is treated only as text input and is not represented as a real contract reviewed by a lawyer.

## Clause-type catalogue

### Typed obligations

Each obligation has an `obligation_type`, `party`, `trigger`, optional `deadline`, tags, and exact evidence reference.

| Type | Rule detects | Example pattern |
| --- | --- | --- |
| `pay` | A party expressly says it shall, must, or will pay | `Client shall pay ... within 30 days` |
| `deliver` | A party expressly says it shall, must, or will deliver, provide, or submit | `Provider shall deliver ... within 5 days` |
| `notify` | A party expressly gives, sends, provides, or makes a notice, or says it shall notify another party | `Provider shall notify Client ... at least 10 days before` |
| `renew` | An automatic renewal clause, including its notice window when stated | `automatically renews ... unless ... notice ... 60 days before` |
| `comply` | An express duty to comply | `Provider shall comply with ...` |
| `terminate-right` | An express right using `may terminate`, including convenience and cure wording when stated | `Client may terminate for convenience ...` |

These are literal phrase rules, not a complete legal ontology. Relative deadlines remain trigger-based if the input does not supply an event date from which to calculate a calendar date. An amendment that expressly extends the term updates the renewal action's current term end and is included as a separate evidence reference.

### Renewal, pricing, and unusual clause patterns

- Renewal extraction detects `automatically renews` and a day-based notice window. The term end is taken from the term clause, or from a related document that expressly says `extended through`.
- Pricing extraction detects a numeric percentage paired with annual price, pricing, fee, or rate escalator wording, and simple increase or escalation language with a percentage.
- Unusual clause extraction flags indemnity text containing broad phrases such as `any and all`, `all claims`, or `regardless of fault`. This is a wording flag for human review, not a risk conclusion.
- Liability cap extraction flags lines containing liability and cap, limit, or `shall not exceed` wording. Termination-for-convenience wording is also surfaced.

### Conflict patterns

The conflict detector compares documents with an overlapping identified party. It reports differing extracted values for payment timing, liability caps, renewal mechanics, and governing law. A conflict includes both source quotes and a rule-based severity label. The fixture set plants one conflict: 30-day and 60-day payment terms. Different wording alone does not prove that clauses legally conflict.

### Evidence references and reports

Every obligation, renewal, pricing item, unusual clause, conflict side, and action carries an evidence object with `document_id`, `section`, and `quote`. Renewal dates also include `term_end_evidence` when a term clause or amendment supplies the date. The Markdown dossier repeats the quote and its source next to each result. JSON keys and list ordering are stable for the same input bytes and filenames. The audit log is separate and records a timestamp, command, input hashes, and extraction counts.

## CLI commands

- `ci fixtures --out DIR [--clean]` writes five fictional contracts. `--clean` omits the reseller document with the planted conflict.
- `ci extract FILE [--type all|parse|obligations|renewals|pricing|unusual]` parses one input file and returns the selected result.
- `ci conflicts DIR` compares supported `.md` and `.txt` files directly inside a directory.
- `ci actions DIR` creates the owner and deadline register, with dated actions first. A renewal action is flagged when its deadline is at the edge of the contractual notice window.
- `ci report DIR` writes a machine-readable JSON report and a readable Markdown dossier.

The default fixture set has a payment conflict. Run `ci conflicts` on a directory generated with `--clean` to see the no-conflict result.
