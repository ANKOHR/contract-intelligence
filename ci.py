"""Convenience entry point when the package is not installed."""

from contract_intelligence.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
