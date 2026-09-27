"""Run ledger ledger.jsonl (#34). Shape: graduate/contracts.md §2."""

import fcntl
import json
import os

LEDGER_PATH = "ledger.jsonl"


def append(row: dict) -> None:
    # The lock keeps rows from parallel runners whole, one per line.
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(row) + "\n")


def rows() -> list[dict]:
    if not os.path.exists(LEDGER_PATH):
        return []
    with open(LEDGER_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
