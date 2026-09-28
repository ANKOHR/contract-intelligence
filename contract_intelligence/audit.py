"""Append-only run audit trail."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_audit(command: list[str], input_hashes: dict[str, str], counts: dict[str, int], path: str | Path = "ci-audit.jsonl") -> None:
    record: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": command,
        "input_hashes": dict(sorted(input_hashes.items())),
        "extraction_counts": dict(sorted(counts.items())),
    }
    with Path(path).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
